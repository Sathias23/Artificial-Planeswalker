"""Integration tests for the first-run data-initialization feature.

Covers, all offline (a fake importer + the deterministic ``FakeEmbedder`` — no Scryfall network, no
model download):

* ``initialize_database`` — imports on an empty DB, is idempotent on a populated one, and reports
  import failures as ``status="error"`` rather than raising.
* ``build_search_index`` — builds the ``card_vec`` index when cards are present, and guards an
  un-imported database with ``database_not_initialized``.
* The ``database_not_initialized`` guard across the relational tools (one per result model) and the
  two-state semantic contract (``database_not_initialized`` with no cards → ``index_unavailable``
  once cards exist but the index does not).
"""

from pathlib import Path

import pytest
from sqlalchemy import text

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.importer import ImportStatistics, ReconcileStatistics
from src.data.importers.transformers import TransformReject
from src.data.models.card import CardModel
from src.mcp_server.tools.build_search_index import build_search_index
from src.mcp_server.tools.card_lookup import lookup_card
from src.mcp_server.tools.card_search import search_cards
from src.mcp_server.tools.deck_analysis import analyze_mana_curve, validate_deck
from src.mcp_server.tools.deck_management import add_card_to_deck, create_deck, list_decks
from src.mcp_server.tools.find_similar import find_similar_cards
from src.mcp_server.tools.initialize_database import initialize_database
from src.mcp_server.tools.semantic_search import semantic_search_cards
from src.mcp_server.tools.view_deck import view_deck
from src.search import ConnectionFactory, compose_card_text
from src.search.query import index_is_populated
from tests.fixtures.embedder import FakeEmbedder

# --- shared helpers -----------------------------------------------------------------------------


def _card(card_id: str, name: str) -> CardModel:
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Deals 3 damage.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        keywords=[],  # real Scryfall data uses an empty array, not null, for no keywords
        legalities={"standard": "legal"},
    )


async def _fake_importer(session, *, bulk_type: str = "oracle_cards") -> ImportStatistics:
    """Stand-in for the Scryfall importer: inserts two cards, no network."""
    session.add(_card("c-1", "Lightning Bolt"))
    session.add(_card("c-2", "Counterspell"))
    await session.commit()
    stats = ImportStatistics()
    stats.total_processed = 2
    stats.total_inserted = 2
    return stats


def _sync_cards_factory(tmp_path: Path, *, seed: bool) -> ConnectionFactory:
    """A sqlite-vec ConnectionFactory whose ``cards`` table exists and is optionally seeded."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()
    conn.execute(
        "CREATE TABLE cards ("
        "id TEXT PRIMARY KEY, oracle_id TEXT NOT NULL, name TEXT NOT NULL, type_line TEXT, "
        "mana_cost TEXT, oracle_text TEXT, keywords TEXT, colors TEXT, cmc REAL, "
        "rarity TEXT, set_code TEXT, legalities TEXT, games TEXT)"
    )
    if seed:
        conn.executemany(
            "INSERT INTO cards (id, oracle_id, name, type_line, mana_cost, oracle_text, keywords, "
            "colors, cmc) VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ("c-1", "o-1", "Bolt", "Instant", "{R}", "Deals 3 damage.", "[]", '["R"]', 1.0),
                (
                    "c-2",
                    "o-2",
                    "Negate",
                    "Instant",
                    "{U}",
                    "Counter target spell.",
                    "[]",
                    '["U"]',
                    2.0,
                ),
            ],
        )
    conn.commit()
    return factory


@pytest.fixture
async def empty_session_factory(tmp_path: Path):
    """Async session factory bound to a schema-created but un-imported (no cards) DB."""
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'empty.db').as_posix()}")
    await init_database(engine)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


# --- initialize_database --------------------------------------------------------------------------


async def test_initialize_database_imports_then_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'init.db').as_posix()}"
    )

    result = await initialize_database(import_fn=_fake_importer)
    assert result.status == "ok"
    assert result.cards_imported == 2
    assert result.cards_total == 2
    assert "build_search_index" in result.message

    async def _must_not_run(session, *, bulk_type: str = "oracle_cards") -> ImportStatistics:
        raise AssertionError("importer must not run when the DB is already initialized")

    again = await initialize_database(import_fn=_must_not_run)
    assert again.status == "already_initialized"
    assert again.cards_total == 2


async def test_initialize_database_update_refreshes_populated_db(tmp_path, monkeypatch) -> None:
    """``update=True`` re-runs the importer on a populated DB, adding new cards (``updated``)."""
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'update.db').as_posix()}"
    )

    first = await initialize_database(import_fn=_fake_importer)
    assert first.status == "ok"
    assert first.cards_total == 2

    async def _new_set_importer(session, *, bulk_type: str = "oracle_cards") -> ImportStatistics:
        """Upserts an existing card (refresh) and a brand-new one (new set release)."""
        await session.merge(_card("c-1", "Lightning Bolt"))  # existing id → refreshed in place
        session.add(_card("c-3", "Boros Charm"))  # new id → added
        await session.commit()
        stats = ImportStatistics()
        stats.total_processed = 2
        stats.total_inserted = 2
        return stats

    updated = await initialize_database(import_fn=_new_set_importer, update=True)
    assert updated.status == "updated"
    assert updated.cards_imported == 1  # one *new* card (c-3); c-1 was refreshed, not added
    assert updated.cards_total == 3


async def test_initialize_database_surfaces_reject_and_stale_diagnostics(
    tmp_path, monkeypatch
) -> None:
    """The result message names the error count, up to 5 sample rejects, and stale rows."""
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'diag.db').as_posix()}"
    )

    async def _importer_with_rejects(
        session, *, bulk_type: str = "oracle_cards"
    ) -> ImportStatistics:
        session.add(_card("c-1", "Lightning Bolt"))
        await session.commit()
        stats = ImportStatistics()
        stats.total_processed = 8
        stats.total_inserted = 1
        stats.total_errors = 7
        stats.rejects = [
            TransformReject(identity=f"Reject Card {i}", reason="missing required field(s): id")
            for i in range(7)
        ]
        stats.reconcile.stale_remaining = 3
        return stats

    result = await initialize_database(import_fn=_importer_with_rejects)
    assert result.status == "ok"
    assert "7 card(s) could not be imported" in result.message
    assert "Reject Card 0" in result.message
    assert "Reject Card 4" in result.message  # five samples ...
    assert "Reject Card 5" not in result.message  # ... and no more
    assert (
        "3 oracle identities kept pre-existing rows because their "
        "current printing was rejected this run" in result.message
    )


async def test_initialize_database_update_clamps_negative_added_and_recommends_prune(
    tmp_path, monkeypatch
) -> None:
    """Reconcile deletions can shrink the total: ``cards_imported`` clamps at 0, msg explains."""
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'clamp.db').as_posix()}"
    )

    first = await initialize_database(import_fn=_fake_importer)
    assert first.status == "ok"
    assert first.cards_total == 2

    async def _dedup_importer(session, *, bulk_type: str = "oracle_cards") -> ImportStatistics:
        """Simulates a reconcile-heavy update: a stale duplicate row is deleted, none added."""
        await session.execute(text("DELETE FROM cards WHERE id = 'c-2'"))
        await session.commit()
        stats = ImportStatistics()
        stats.total_processed = 1
        stats.total_inserted = 1
        stats.reconcile.rows_deleted = 1
        return stats

    updated = await initialize_database(import_fn=_dedup_importer, update=True)
    assert updated.status == "updated"
    assert updated.cards_imported == 0  # 1 total - 2 before = -1, clamped
    assert updated.cards_total == 1
    assert "Removed 1 stale duplicate row(s) during reconcile." in updated.message
    assert "prune=true" in updated.message  # deleted rows leave vectors to prune


async def test_initialize_database_surfaces_reconcile_failure_warning(
    tmp_path, monkeypatch
) -> None:
    """A failed reconcile stage is named in the message instead of masquerading as clean."""
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'recfail.db').as_posix()}"
    )

    async def _reconcile_failed_importer(
        session, *, bulk_type: str = "oracle_cards"
    ) -> ImportStatistics:
        session.add(_card("c-1", "Lightning Bolt"))
        await session.commit()
        stats = ImportStatistics()
        stats.total_processed = 1
        stats.total_inserted = 1
        stats.reconcile = ReconcileStatistics(failed=True)
        return stats

    result = await initialize_database(import_fn=_reconcile_failed_importer)
    assert result.status == "ok"
    assert "reconcile stage failed" in result.message
    assert "stale duplicates may remain" in result.message
    assert "update=true" in result.message


async def test_initialize_database_update_on_empty_db_is_a_first_run(tmp_path, monkeypatch) -> None:
    """``update=True`` against an empty DB behaves as a normal first-run import (status ``ok``)."""
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'update_empty.db').as_posix()}"
    )

    result = await initialize_database(import_fn=_fake_importer, update=True)
    assert result.status == "ok"
    assert result.cards_total == 2


async def test_initialize_database_failed_update_preserves_existing_cards(
    tmp_path, monkeypatch
) -> None:
    """A failed ``update`` reports ``error`` but never wipes the already-populated database."""
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'update_err.db').as_posix()}"
    )

    first = await initialize_database(import_fn=_fake_importer)
    assert first.status == "ok"

    async def _boom(session, *, bulk_type: str = "oracle_cards") -> ImportStatistics:
        raise RuntimeError("network down mid-update")

    failed = await initialize_database(import_fn=_boom, update=True)
    assert failed.status == "error"

    # The existing cards must survive the failed update — a plain re-init still sees them.
    async def _must_not_run(session, *, bulk_type: str = "oracle_cards") -> ImportStatistics:
        raise AssertionError("importer must not run — existing cards should remain")

    again = await initialize_database(import_fn=_must_not_run)
    assert again.status == "already_initialized"
    assert again.cards_total == 2


async def test_initialize_database_reports_error_on_import_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'err.db').as_posix()}"
    )

    async def _boom(session, *, bulk_type: str = "oracle_cards") -> ImportStatistics:
        raise RuntimeError("network down")

    result = await initialize_database(import_fn=_boom)
    assert result.status == "error"
    assert "network down" in result.message


# --- build_search_index ---------------------------------------------------------------------------


def test_build_search_index_builds_when_cards_present(tmp_path) -> None:
    factory = _sync_cards_factory(tmp_path, seed=True)
    try:
        result = build_search_index(factory, embedder=FakeEmbedder())
        assert result.status == "ok"
        assert result.cards_indexed == 2
        assert index_is_populated(factory.get_connection()) is True
    finally:
        factory.close()


def test_build_search_index_guards_uninitialized_db(tmp_path) -> None:
    factory = _sync_cards_factory(tmp_path, seed=False)
    try:
        result = build_search_index(factory, embedder=FakeEmbedder())
        assert result.status == "database_not_initialized"
        assert "initialize_database" in result.message
    finally:
        factory.close()


# --- database_not_initialized guard across relational tools ---------------------------------------


async def test_lookup_card_guards_uninitialized_db(empty_session_factory) -> None:
    async with empty_session_factory() as session:
        result = await lookup_card(session, "Lightning Bolt")
    assert result.status == "database_not_initialized"
    assert "initialize_database" in result.message


async def test_search_cards_guards_uninitialized_db(empty_session_factory) -> None:
    async with empty_session_factory() as session:
        result = await search_cards(session, colors=["R"])
    assert result.status == "database_not_initialized"


async def test_list_decks_guards_uninitialized_db(empty_session_factory) -> None:
    async with empty_session_factory() as session:
        result = await list_decks(session)
    assert result.status == "database_not_initialized"


async def test_create_deck_guards_uninitialized_db(empty_session_factory) -> None:
    async with empty_session_factory() as session:
        result = await create_deck(session, name="My Deck")
    assert result.status == "database_not_initialized"


async def test_add_card_to_deck_guards_uninitialized_db(empty_session_factory) -> None:
    async with empty_session_factory() as session:
        result = await add_card_to_deck(session, deck_id="d-1", name="Bolt")
    assert result.status == "database_not_initialized"


async def test_view_deck_guards_uninitialized_db(empty_session_factory) -> None:
    async with empty_session_factory() as session:
        result = await view_deck(session, deck_id="d-1")
    assert result.status == "database_not_initialized"
    assert "initialize_database" in result.message


async def test_analyze_mana_curve_guards_uninitialized_db(empty_session_factory) -> None:
    async with empty_session_factory() as session:
        result = await analyze_mana_curve(session, deck_id="d-1")
    assert result.status == "database_not_initialized"


async def test_validate_deck_guards_uninitialized_db(empty_session_factory) -> None:
    async with empty_session_factory() as session:
        result = await validate_deck(session, deck_id="d-1")
    assert result.status == "database_not_initialized"


# --- semantic tools: two-state contract -----------------------------------------------------------


def test_semantic_search_guards_uninitialized_db(tmp_path) -> None:
    factory = _sync_cards_factory(tmp_path, seed=False)
    try:
        result = semantic_search_cards(factory.get_connection(), FakeEmbedder(), "anything")
        assert result.status == "database_not_initialized"
    finally:
        factory.close()


def test_semantic_search_index_unavailable_when_cards_present(tmp_path) -> None:
    factory = _sync_cards_factory(tmp_path, seed=True)
    try:
        result = semantic_search_cards(factory.get_connection(), FakeEmbedder(), "anything")
        assert result.status == "index_unavailable"
        assert "build_search_index" in result.message
    finally:
        factory.close()


def test_find_similar_guards_uninitialized_db(tmp_path) -> None:
    factory = _sync_cards_factory(tmp_path, seed=False)
    try:
        result = find_similar_cards(factory.get_connection(), card_name="Bolt")
        assert result.status == "database_not_initialized"
    finally:
        factory.close()


def test_find_similar_index_unavailable_when_cards_present(tmp_path) -> None:
    factory = _sync_cards_factory(tmp_path, seed=True)
    try:
        result = find_similar_cards(factory.get_connection(), card_name="Bolt")
        assert result.status == "index_unavailable"
        assert "build_search_index" in result.message
    finally:
        factory.close()


# --- end-to-end first-run loop (AC2) --------------------------------------------------------------


async def test_end_to_end_first_run_loop(tmp_path, monkeypatch) -> None:
    """initialize_database → build_search_index → semantic_search_cards returns ``ok`` (AC2).

    The whole loop runs offline against one DB file: the fake importer seeds the cards (no network),
    the FakeEmbedder builds the index (no model download), and a query of a seeded card's composed
    text ranks it at distance 0 — proving the first-run path leaves the server fully working.
    """
    db_path = tmp_path / "e2e.db"
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")

    init_result = await initialize_database(import_fn=_fake_importer)
    assert init_result.status == "ok"

    fake = FakeEmbedder()
    factory = ConnectionFactory(db_path=str(db_path))  # same DB file as the async importer wrote
    try:
        built = build_search_index(factory, embedder=fake)
        assert built.status == "ok"
        # The fake importer seeds "Lightning Bolt" (Instant, {R}, "Deals 3 damage.").
        query = compose_card_text("Lightning Bolt", "Instant", "{R}", "Deals 3 damage.", [])
        result = semantic_search_cards(factory.get_connection(), fake, query)
        assert result.status == "ok"
        assert result.cards
    finally:
        factory.close()

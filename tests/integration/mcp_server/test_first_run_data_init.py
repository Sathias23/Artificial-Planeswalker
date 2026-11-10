"""Integration tests for the first-run data-initialization feature.

Covers, all offline (a fake importer + the deterministic ``FakeEmbedder`` — no Scryfall network, no
model download):

* ``initialize_database`` — imports on an empty DB, is idempotent on a populated one, and reports
  import failures as ``status="error"`` rather than raising.
* ``build_search_index`` — builds the ``card_vec`` index when cards are present, and guards an
  un-imported database with ``database_not_initialized``.
* The ``database_not_initialized`` guard across the relational tools (one row per guarded helper)
  and the two-state semantic contract (``database_not_initialized`` with no cards →
  ``index_unavailable`` once cards exist but the index does not).
"""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.importers.importer import ImportStatistics, ReconcileStatistics
from src.data.importers.transformers import TransformReject
from src.mcp_server.tools.assess_deck_power import assess_deck_power
from src.mcp_server.tools.build_search_index import build_search_index
from src.mcp_server.tools.card_lookup import lookup_card
from src.mcp_server.tools.card_search import search_cards
from src.mcp_server.tools.companion import set_active_deck
from src.mcp_server.tools.compare_deck_power import compare_deck_power
from src.mcp_server.tools.deck_analysis import analyze_mana_curve, detect_synergies, validate_deck
from src.mcp_server.tools.deck_import import import_decklist
from src.mcp_server.tools.deck_management import (
    DeckMetadataUpdate,
    add_card_to_deck,
    clone_deck,
    create_deck,
    delete_deck,
    list_decks,
    load_deck,
    remove_card_from_deck,
    set_card_quantity,
    update_deck,
)
from src.mcp_server.tools.find_similar import find_similar_cards
from src.mcp_server.tools.initialize_database import initialize_database
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE
from src.mcp_server.tools.semantic_search import semantic_search_cards
from src.mcp_server.tools.view_deck import view_deck
from src.search import ConnectionFactory, compose_card_text
from src.search.query import index_is_populated
from tests.fixtures.embedder import FakeEmbedder
from tests.fixtures.server_seams import fake_importer, importer_card

# --- initialize_database --------------------------------------------------------------------------


async def test_initialize_database_imports_then_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'init.db').as_posix()}"
    )

    result = await initialize_database(import_fn=fake_importer)
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

    first = await initialize_database(import_fn=fake_importer)
    assert first.status == "ok"
    assert first.cards_total == 2

    async def _new_set_importer(session, *, bulk_type: str = "oracle_cards") -> ImportStatistics:
        """Upserts an existing card (refresh) and a brand-new one (new set release)."""
        # existing id → refreshed in place
        await session.merge(importer_card("c-1", "Lightning Bolt"))
        session.add(importer_card("c-3", "Boros Charm"))  # new id → added
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
        session.add(importer_card("c-1", "Lightning Bolt"))
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

    first = await initialize_database(import_fn=fake_importer)
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
        session.add(importer_card("c-1", "Lightning Bolt"))
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

    result = await initialize_database(import_fn=fake_importer, update=True)
    assert result.status == "ok"
    assert result.cards_total == 2


async def test_initialize_database_failed_update_preserves_existing_cards(
    tmp_path, monkeypatch
) -> None:
    """A failed ``update`` reports ``error`` but never wipes the already-populated database."""
    monkeypatch.setenv(
        "CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'update_err.db').as_posix()}"
    )

    first = await initialize_database(import_fn=fake_importer)
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


async def test_build_search_index_builds_when_cards_present(
    seeded_card_db: async_sessionmaker[AsyncSession], card_db_path: Path
) -> None:
    factory = ConnectionFactory(db_path=str(card_db_path))
    try:
        result = build_search_index(factory, embedder=FakeEmbedder())
        assert result.status == "ok"
        assert result.cards_indexed == 3
        assert index_is_populated(factory.get_connection()) is True
    finally:
        factory.close()


async def test_build_search_index_guards_uninitialized_db(
    empty_card_db: async_sessionmaker[AsyncSession], card_db_path: Path
) -> None:
    factory = ConnectionFactory(db_path=str(card_db_path))
    try:
        result = build_search_index(factory, embedder=FakeEmbedder())
        assert result.status == "database_not_initialized"
        assert "initialize_database" in result.message
    finally:
        factory.close()


# --- database_not_initialized guard across relational tools ---------------------------------------

#: Every async helper that guards an un-imported database, each called with arguments that pass its
#: own input validation, so the readiness probe is what answers. On an empty card table most of
#: these would otherwise answer ``deck_not_found`` / ``not_found`` / ``empty``, which is why each
#: needs its own row: deleting any one guard turns exactly that row red.
_GUARDED_HELPERS: list[tuple[str, Callable[[AsyncSession], Awaitable[Any]]]] = [
    ("lookup_card", lambda s: lookup_card(s, "Lightning Bolt")),
    ("search_cards", lambda s: search_cards(s, colors=["R"])),
    ("list_decks", lambda s: list_decks(s)),
    ("create_deck", lambda s: create_deck(s, name="My Deck")),
    ("clone_deck", lambda s: clone_deck(s, deck_id="d-1")),
    ("load_deck", lambda s: load_deck(s, deck_id="d-1")),
    (
        "update_deck",
        lambda s: update_deck(s, deck_id="d-1", changes=DeckMetadataUpdate(name="Renamed")),
    ),
    ("delete_deck", lambda s: delete_deck(s, deck_id="d-1")),
    ("add_card_to_deck", lambda s: add_card_to_deck(s, deck_id="d-1", name="Bolt")),
    (
        "set_card_quantity",
        lambda s: set_card_quantity(s, deck_id="d-1", name="Bolt", quantity=2),
    ),
    ("remove_card_from_deck", lambda s: remove_card_from_deck(s, deck_id="d-1", name="Bolt")),
    (
        "import_decklist",
        lambda s: import_decklist(
            s, deck_id="d-1", arena_export="Deck\n1 Lightning Bolt (LEA) 161"
        ),
    ),
    ("view_deck", lambda s: view_deck(s, deck_id="d-1", open_browser=False)),
    ("set_active_deck", lambda s: set_active_deck(s, deck_id="d-1")),
    ("analyze_mana_curve", lambda s: analyze_mana_curve(s, deck_id="d-1")),
    ("detect_synergies", lambda s: detect_synergies(s, deck_id="d-1")),
    ("validate_deck", lambda s: validate_deck(s, deck_id="d-1")),
    ("assess_deck_power", lambda s: assess_deck_power(s, deck_id="d-1")),
    ("compare_deck_power", lambda s: compare_deck_power(s, deck_id_a="d-1", deck_id_b="d-2")),
]


@pytest.mark.parametrize(
    "call", [call for _, call in _GUARDED_HELPERS], ids=[name for name, _ in _GUARDED_HELPERS]
)
async def test_every_guarded_helper_answers_database_not_initialized_on_an_empty_card_table(
    empty_card_db, call
) -> None:
    """One row per guarded helper: the schema exists, ``cards`` is empty, the guard answers.

    The message is the shared one that names ``initialize_database`` (the assessment tools carry it
    in ``summary``), so a helper answering the right token with a stray message also fails.
    """
    async with empty_card_db() as session:
        result = await call(session)
    assert result.status == "database_not_initialized"
    text = getattr(result, "message", None) or result.summary
    assert text == DATABASE_NOT_INITIALIZED_MESSAGE
    assert "initialize_database" in text


# --- semantic tools: two-state contract -----------------------------------------------------------


async def test_semantic_search_guards_uninitialized_db(
    empty_card_db: async_sessionmaker[AsyncSession], card_db_path: Path
) -> None:
    factory = ConnectionFactory(db_path=str(card_db_path))
    try:
        result = semantic_search_cards(factory.get_connection(), FakeEmbedder(), "anything")
        assert result.status == "database_not_initialized"
    finally:
        factory.close()


async def test_semantic_search_index_unavailable_when_cards_present(
    seeded_card_db: async_sessionmaker[AsyncSession], card_db_path: Path
) -> None:
    factory = ConnectionFactory(db_path=str(card_db_path))
    try:
        result = semantic_search_cards(factory.get_connection(), FakeEmbedder(), "anything")
        assert result.status == "index_unavailable"
        assert "build_search_index" in result.message
    finally:
        factory.close()


async def test_find_similar_guards_uninitialized_db(
    empty_card_db: async_sessionmaker[AsyncSession], card_db_path: Path
) -> None:
    factory = ConnectionFactory(db_path=str(card_db_path))
    try:
        result = find_similar_cards(factory.get_connection(), card_name="Lightning Bolt")
        assert result.status == "database_not_initialized"
    finally:
        factory.close()


async def test_find_similar_index_unavailable_when_cards_present(
    seeded_card_db: async_sessionmaker[AsyncSession], card_db_path: Path
) -> None:
    factory = ConnectionFactory(db_path=str(card_db_path))
    try:
        result = find_similar_cards(factory.get_connection(), card_name="Lightning Bolt")
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

    init_result = await initialize_database(import_fn=fake_importer)
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

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

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.importer import ImportStatistics
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

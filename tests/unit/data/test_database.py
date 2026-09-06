"""Unit tests for database configuration and the connect-time hooks.

Covers the NOCASE index migration, per-connection foreign-key enforcement, and the one-time
orphan ``deck_cards`` sweep that repairs a database written before enforcement existed.
"""

import logging
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import text

from src.companion.app import deps as companion_deps
from src.data import database as database_module
from src.data.database import (
    create_engine,
    create_session_factory,
    enable_foreign_keys,
    ensure_nocase_indexes,
    init_database,
    remove_orphan_deck_cards,
)
from src.data.models.card import NOCASE_NAME_INDEX, NOCASE_PRINTED_NAME_INDEX

NOCASE_INDEXES = {NOCASE_NAME_INDEX, NOCASE_PRINTED_NAME_INDEX}


def test_create_engine_default_url() -> None:
    """Test engine creation with the default (central) database URL."""
    engine = create_engine()

    assert engine is not None
    assert "sqlite" in str(engine.url)


def test_create_engine_custom_url() -> None:
    """Test engine creation with custom database URL."""
    custom_url = "sqlite+aiosqlite:///:memory:"
    engine = create_engine(custom_url)

    assert engine is not None
    assert str(engine.url) == custom_url


def test_create_session_factory() -> None:
    """Test session factory creation."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)

    assert session_factory is not None
    assert session_factory.kw["expire_on_commit"] is False
    assert session_factory.kw["autoflush"] is False
    assert session_factory.kw["autocommit"] is False


def test_session_factory_creates_sessions() -> None:
    """Test that session factory can create AsyncSession instances."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)

    # Verify factory can create a session (don't actually use it in sync test)
    assert callable(session_factory)


# --- Connect-time NOCASE index migration -------------------------------------------------------


def _card_indexes(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'cards'"
        ).fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def _old_schema(path: Path) -> None:
    """A ``cards`` table from before the NOCASE indexes existed."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE cards (id TEXT PRIMARY KEY, name TEXT NOT NULL, printed_name TEXT)"
        )
        conn.execute("CREATE INDEX ix_cards_name ON cards (name)")
        conn.commit()
    finally:
        conn.close()


async def _connect_once(url: str) -> None:
    engine = create_engine(url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


async def test_an_existing_database_gains_the_nocase_indexes_on_connect(tmp_path: Path) -> None:
    """No migration script: the first connection of the new engine adds both indexes."""
    db = tmp_path / "old.db"
    _old_schema(db)
    assert not (NOCASE_INDEXES & _card_indexes(db))

    await _connect_once(f"sqlite+aiosqlite:///{db.as_posix()}")

    assert NOCASE_INDEXES <= _card_indexes(db)


async def test_a_fresh_database_gets_the_indexes_from_create_all(tmp_path: Path) -> None:
    """With no ``cards`` table the hook skips (it would raise); ``init_database`` creates them."""
    db = tmp_path / "fresh.db"
    url = f"sqlite+aiosqlite:///{db.as_posix()}"

    await _connect_once(url)
    assert _card_indexes(db) == set()

    engine = create_engine(url)
    try:
        await init_database(engine)
    finally:
        await engine.dispose()

    assert NOCASE_INDEXES <= _card_indexes(db)


async def test_a_locked_database_is_logged_and_the_next_connect_retries(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A competing writer's lock is an ``OperationalError`` the hook logs, never raises."""
    db = tmp_path / "locked.db"
    _old_schema(db)
    writer = sqlite3.connect(db)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("INSERT INTO cards VALUES ('x', 'Held', NULL)")
    reader = sqlite3.connect(db, timeout=0)
    try:
        with caplog.at_level(logging.WARNING, logger="src.data.database"):
            ensure_nocase_indexes(reader)
    finally:
        reader.close()
        writer.rollback()
        writer.close()

    assert any("NOCASE" in record.getMessage() for record in caplog.records)
    assert not (NOCASE_INDEXES & _card_indexes(db))

    await _connect_once(f"sqlite+aiosqlite:///{db.as_posix()}")

    assert NOCASE_INDEXES <= _card_indexes(db)


class _RecordingCursor:
    """A cursor that answers the catalog reads and records every statement it is handed."""

    def __init__(self, indexes: list[tuple[str]]) -> None:
        self.indexes = indexes
        self.statements: list[str] = []
        self._pending: list = []

    def execute(self, sql: str, params=()) -> None:
        self.statements.append(sql)
        if "type = 'table'" in sql:
            self._pending = [(1,)]
        elif "type = 'index'" in sql:
            self._pending = list(self.indexes)

    def fetchone(self):
        return self._pending[0] if self._pending else None

    def fetchall(self):
        return list(self._pending)

    def close(self) -> None:
        pass


class _RecordingConnection:
    def __init__(self, indexes: list[tuple[str]]) -> None:
        self.cursor_obj = _RecordingCursor(indexes)

    def cursor(self) -> _RecordingCursor:
        return self.cursor_obj


def test_no_ddl_is_issued_when_both_indexes_already_exist() -> None:
    """A current database never pays a busy-timeout wait or a warning for DDL it does not need."""
    conn = _RecordingConnection([(NOCASE_NAME_INDEX,), (NOCASE_PRINTED_NAME_INDEX,)])

    ensure_nocase_indexes(conn)

    assert not any(s.startswith("CREATE INDEX") for s in conn.cursor_obj.statements)


def test_a_missing_index_is_created() -> None:
    conn = _RecordingConnection([(NOCASE_NAME_INDEX,)])

    ensure_nocase_indexes(conn)

    assert sum(s.startswith("CREATE INDEX") for s in conn.cursor_obj.statements) == 2


def test_a_corrupt_file_still_connects_and_only_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """``sqlite3.DatabaseError`` (not just a lock) is swallowed so the connection opens."""
    db = tmp_path / "corrupt.db"
    db.write_bytes(b"this is not a sqlite file, just enough bytes to be opened as one\n" * 40)
    reader = sqlite3.connect(db)
    try:
        with caplog.at_level(logging.WARNING, logger="src.data.database"):
            ensure_nocase_indexes(reader)
    finally:
        reader.close()

    assert any("NOCASE" in record.getMessage() for record in caplog.records)


def test_ensure_indexes_false_registers_no_connect_hook() -> None:
    opted_out = create_engine("sqlite+aiosqlite:///:memory:", ensure_indexes=False)
    default = create_engine("sqlite+aiosqlite:///:memory:")

    assert not database_module.event.contains(
        opted_out.sync_engine, "connect", ensure_nocase_indexes
    )
    assert database_module.event.contains(default.sync_engine, "connect", ensure_nocase_indexes)


async def test_the_companion_engine_opts_out_of_the_index_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-2: the companion is a read-only shell of cards.db and must never issue DDL."""
    db = tmp_path / "cards.db"
    _old_schema(db)
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{db.as_posix()}")
    seen: list[bool] = []
    real_create_engine = companion_deps.create_engine

    def observing_create_engine(url, **kwargs):
        seen.append(kwargs.get("ensure_indexes", True))
        return real_create_engine(url, **kwargs)

    monkeypatch.setattr(companion_deps, "create_engine", observing_create_engine)
    holder = companion_deps.Database()
    factory = await holder.session_factory()
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    finally:
        await holder.dispose()

    assert seen == [False]
    assert not (NOCASE_INDEXES & _card_indexes(db))


# --- Connect-time foreign-key enforcement and the orphan deck_cards sweep ----------------------


def _deck_schema(path: Path, *, import_in_progress: bool | None = None) -> None:
    """A pre-enforcement database: the three association tables, two orphans and one valid row.

    Written over plain ``sqlite3`` (foreign keys off by default) so the orphan rows can exist at
    all. ``import_in_progress`` adds the ``import_state`` marker table with that flag; ``None``
    leaves the table absent, the state of every legacy database.
    """
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE decks (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute("CREATE TABLE cards (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE deck_cards (deck_id TEXT NOT NULL, card_id TEXT NOT NULL, "
            "quantity INTEGER NOT NULL, sideboard BOOLEAN NOT NULL, "
            "PRIMARY KEY (deck_id, card_id, sideboard))"
        )
        conn.execute("INSERT INTO decks VALUES ('deck-live', 'Live')")
        conn.execute("INSERT INTO cards VALUES ('card-live', 'Live Card')")
        conn.executemany(
            "INSERT INTO deck_cards VALUES (?, ?, 1, 0)",
            [
                ("deck-live", "card-live"),  # valid
                ("deck-dead", "card-live"),  # dangling deck
                ("deck-live", "card-dead"),  # dangling card
            ],
        )
        if import_in_progress is not None:
            conn.execute(
                "CREATE TABLE import_state "
                "(id INTEGER PRIMARY KEY CHECK (id = 1), in_progress INTEGER NOT NULL)"
            )
            conn.execute(
                "INSERT INTO import_state VALUES (1, ?)", (1 if import_in_progress else 0,)
            )
        conn.commit()
    finally:
        conn.close()


def _deck_card_pairs(path: Path) -> set[tuple[str, str]]:
    conn = sqlite3.connect(path)
    try:
        return set(conn.execute("SELECT deck_id, card_id FROM deck_cards").fetchall())
    finally:
        conn.close()


_ALL_PAIRS = {("deck-live", "card-live"), ("deck-dead", "card-live"), ("deck-live", "card-dead")}
_VALID_PAIRS = {("deck-live", "card-live")}


async def _read_foreign_keys_pragma(url: str, *, ensure_indexes: bool = True) -> int:
    engine = create_engine(url, ensure_indexes=ensure_indexes)
    try:
        async with engine.connect() as conn:
            value = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
    finally:
        await engine.dispose()
    assert isinstance(value, int)
    return value


async def test_the_mcp_engine_enforces_foreign_keys_on_a_fresh_connection(tmp_path: Path) -> None:
    db = tmp_path / "fk.db"
    assert await _read_foreign_keys_pragma(f"sqlite+aiosqlite:///{db.as_posix()}") == 1


async def test_the_companion_engine_enforces_foreign_keys_too(tmp_path: Path) -> None:
    """AD-2 opts the companion out of the repair hooks, never out of the pragma."""
    db = tmp_path / "fk.db"
    url = f"sqlite+aiosqlite:///{db.as_posix()}"
    assert await _read_foreign_keys_pragma(url, ensure_indexes=False) == 1


async def test_the_companion_database_holder_enforces_foreign_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through ``companion_deps.Database`` (the real companion entry point), the pragma is on."""
    db = tmp_path / "cards.db"
    _deck_schema(db)
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{db.as_posix()}")
    holder = companion_deps.Database()
    factory = await holder.session_factory()
    try:
        async with factory() as session:
            value = (await session.execute(text("PRAGMA foreign_keys"))).scalar()
    finally:
        await holder.dispose()

    assert value == 1
    # No sweep on the read-only shell: every orphan is still there.
    assert _deck_card_pairs(db) == _ALL_PAIRS


async def test_seeded_orphans_are_swept_by_the_first_mcp_connection(tmp_path: Path) -> None:
    """A database written with enforcement off loses exactly its orphan rows on connect."""
    db = tmp_path / "orphans.db"
    _deck_schema(db)
    assert _deck_card_pairs(db) == _ALL_PAIRS

    await _connect_once(f"sqlite+aiosqlite:///{db.as_posix()}")

    assert _deck_card_pairs(db) == _VALID_PAIRS


async def test_orphans_survive_a_companion_engine_connection(tmp_path: Path) -> None:
    db = tmp_path / "orphans.db"
    _deck_schema(db)
    engine = create_engine(f"sqlite+aiosqlite:///{db.as_posix()}", ensure_indexes=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()

    assert _deck_card_pairs(db) == _ALL_PAIRS


async def test_orphans_are_left_alone_while_a_first_run_import_is_in_progress(
    tmp_path: Path,
) -> None:
    """A killed first-run import's partial ``cards`` table must not cost the user deck rows."""
    db = tmp_path / "partial.db"
    _deck_schema(db, import_in_progress=True)

    await _connect_once(f"sqlite+aiosqlite:///{db.as_posix()}")

    assert _deck_card_pairs(db) == _ALL_PAIRS


async def test_a_finished_import_marker_does_not_block_the_sweep(tmp_path: Path) -> None:
    db = tmp_path / "finished.db"
    _deck_schema(db, import_in_progress=False)

    await _connect_once(f"sqlite+aiosqlite:///{db.as_posix()}")

    assert _deck_card_pairs(db) == _VALID_PAIRS


async def test_a_database_without_the_association_tables_still_connects(tmp_path: Path) -> None:
    """The ``cards``-only legacy shape skips the sweep without raising."""
    db = tmp_path / "cards_only.db"
    _old_schema(db)

    await _connect_once(f"sqlite+aiosqlite:///{db.as_posix()}")

    conn = sqlite3.connect(db)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master").fetchall()}
    finally:
        conn.close()
    assert "deck_cards" not in tables


async def test_a_locked_database_defers_the_sweep_to_the_next_connect(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A competing writer's lock is logged, the connection opens, and the next connect sweeps."""
    db = tmp_path / "locked.db"
    _deck_schema(db)
    writer = sqlite3.connect(db)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("INSERT INTO decks VALUES ('deck-held', 'Held')")
    reader = sqlite3.connect(db, timeout=0)
    try:
        with caplog.at_level(logging.WARNING, logger="src.data.database"):
            remove_orphan_deck_cards(reader)
    finally:
        reader.close()
        writer.rollback()
        writer.close()

    assert any("orphan deck_cards" in record.getMessage() for record in caplog.records)
    assert _deck_card_pairs(db) == _ALL_PAIRS

    await _connect_once(f"sqlite+aiosqlite:///{db.as_posix()}")

    assert _deck_card_pairs(db) == _VALID_PAIRS


class _TracingConnection:
    """A real ``sqlite3`` connection whose statements are recorded through the trace callback."""

    def __init__(self, path: Path) -> None:
        self.statements: list[str] = []
        self._conn = sqlite3.connect(path)
        self._conn.set_trace_callback(self.statements.append)

    def cursor(self) -> sqlite3.Cursor:
        return self._conn.cursor()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def _deletes(statements: list[str]) -> list[str]:
    return [s for s in statements if s.lstrip().upper().startswith("DELETE")]


def test_no_delete_is_issued_on_a_database_without_orphans(tmp_path: Path) -> None:
    """A current database pays the probe ``SELECT`` only — no write, no lock wait."""
    db = tmp_path / "clean.db"
    _deck_schema(db)
    cleanup = sqlite3.connect(db)
    try:
        cleanup.execute(
            "DELETE FROM deck_cards WHERE deck_id = 'deck-dead' OR card_id = 'card-dead'"
        )
        cleanup.commit()
    finally:
        cleanup.close()
    conn = _TracingConnection(db)
    try:
        remove_orphan_deck_cards(conn)
    finally:
        conn.close()

    assert _deletes(conn.statements) == []
    assert any("deck_cards" in s for s in conn.statements)  # the probe ran
    assert _deck_card_pairs(db) == _VALID_PAIRS


def test_a_database_with_orphans_issues_exactly_one_delete(tmp_path: Path) -> None:
    db = tmp_path / "dirty.db"
    _deck_schema(db)
    conn = _TracingConnection(db)
    try:
        remove_orphan_deck_cards(conn)
    finally:
        conn.close()

    assert len(_deletes(conn.statements)) == 1
    assert _deck_card_pairs(db) == _VALID_PAIRS


def test_the_companion_engine_registers_the_pragma_but_not_the_sweep() -> None:
    opted_out = create_engine("sqlite+aiosqlite:///:memory:", ensure_indexes=False)
    default = create_engine("sqlite+aiosqlite:///:memory:")

    for engine in (opted_out, default):
        assert database_module.event.contains(engine.sync_engine, "connect", enable_foreign_keys)
    assert not database_module.event.contains(
        opted_out.sync_engine, "connect", remove_orphan_deck_cards
    )
    assert database_module.event.contains(default.sync_engine, "connect", remove_orphan_deck_cards)


async def test_an_empty_cards_table_blocks_the_sweep(tmp_path: Path) -> None:
    """With no cards every association looks orphaned (a legacy killed import has no
    ``import_state`` marker), so the sweep must not run until the cards are back."""
    db = tmp_path / "no_cards.db"
    _deck_schema(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute("DELETE FROM cards")
        conn.commit()
    finally:
        conn.close()

    await _connect_once(f"sqlite+aiosqlite:///{db.as_posix()}")

    assert _deck_card_pairs(db) == _ALL_PAIRS

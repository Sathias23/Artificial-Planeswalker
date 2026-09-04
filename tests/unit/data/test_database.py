"""Unit tests for database configuration and the connect-time NOCASE index migration."""

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
    ensure_nocase_indexes,
    init_database,
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

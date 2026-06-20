"""Unit tests for the synchronous SQLite ConnectionFactory (sqlite-vec + WAL + per-thread)."""

import sqlite3
import threading

import pytest

from src.search import ConnectionFactory
from src.search.connection import _resolve_db_path


def test_connection_loads_sqlite_vec(tmp_path) -> None:
    """AC5(a): a factory connection has sqlite-vec loaded (vec_version is truthy)."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()

    version = conn.execute("select vec_version()").fetchone()[0]
    assert version  # e.g. "v0.1.9"

    factory.close()


def test_wal_enabled_on_file_db(tmp_path) -> None:
    """AC5(b): WAL journal mode is active for a file-backed DB."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()

    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"

    factory.close()


def test_relational_round_trip(tmp_path) -> None:
    """AC5(c): a relational CREATE/INSERT/SELECT round-trips through a factory connection."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()

    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO t (name) VALUES (?)", ("Black Lotus",))
    conn.commit()
    row = conn.execute("SELECT name FROM t WHERE id = 1").fetchone()
    assert row[0] == "Black Lotus"

    factory.close()


def test_same_thread_returns_cached_connection(tmp_path) -> None:
    """Repeated calls on one thread return the same cached connection object."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))

    assert factory.get_connection() is factory.get_connection()

    factory.close()


def test_distinct_connection_per_thread(tmp_path) -> None:
    """AC5(d): two worker threads each receive their own distinct connection object."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    main_conn = factory.get_connection()
    results: dict[str, sqlite3.Connection] = {}

    def worker(key: str) -> None:
        # Capture this thread's connection, then close it from *within* the thread that
        # created it (check_same_thread=True forbids cross-thread use — closing from the
        # main thread would raise, which is itself proof the connection is thread-bound).
        results[key] = factory.get_connection()
        factory.close()

    threads = [threading.Thread(target=worker, args=(key,)) for key in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Pure object-identity checks (no SQLite call) are safe to make across threads.
    assert results["a"] is not results["b"]
    assert results["a"] is not main_conn
    assert results["b"] is not main_conn

    factory.close()  # closes the main thread's connection


def test_apsw_driver_raises_not_implemented(tmp_path) -> None:
    """AC4: selecting the documented apsw seam raises NotImplementedError (Phase-1 contingency)."""
    with pytest.raises(NotImplementedError):
        ConnectionFactory(db_path=str(tmp_path / "cards.db"), driver="apsw")


def test_default_driver_is_sqlite3(tmp_path) -> None:
    """AC4: the factory defaults to the stdlib sqlite3 driver."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))

    assert isinstance(factory.get_connection(), sqlite3.Connection)

    factory.close()


def test_resolve_db_path_explicit_wins() -> None:
    """An explicit db_path is returned verbatim, ignoring the environment."""
    assert _resolve_db_path("/tmp/explicit.db") == "/tmp/explicit.db"


def test_resolve_db_path_strips_aiosqlite_prefix(monkeypatch) -> None:
    """The SQLAlchemy ``sqlite+aiosqlite:///`` prefix is stripped to a bare file path."""
    monkeypatch.setenv("CARDS_DATABASE_URL", "sqlite+aiosqlite:///./data/cards.db")
    assert _resolve_db_path(None) == "./data/cards.db"


def test_resolve_db_path_strips_bare_sqlite_prefix(monkeypatch) -> None:
    """The bare ``sqlite:///`` prefix is also stripped."""
    monkeypatch.setenv("CARDS_DATABASE_URL", "sqlite:///./data/cards.db")
    assert _resolve_db_path(None) == "./data/cards.db"


def test_resolve_db_path_defaults_when_env_absent(monkeypatch) -> None:
    """With no explicit path and no env var, the default ./data/cards.db is used."""
    monkeypatch.delenv("CARDS_DATABASE_URL", raising=False)
    assert _resolve_db_path(None) == "./data/cards.db"

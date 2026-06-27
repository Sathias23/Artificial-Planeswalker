"""Sync SQLite connection factory: loads sqlite-vec, enables WAL, one connection per thread."""

import logging
import os
import sqlite3
import threading
from typing import Literal

import sqlite_vec

from src.paths import database_path

logger = logging.getLogger(__name__)

# SQLAlchemy-style URL prefixes the async engine uses; the sync factory needs the bare file path.
_SQLALCHEMY_PREFIXES = ("sqlite+aiosqlite:///", "sqlite:///")


def _resolve_db_path(db_path: str | None) -> str:
    """Resolve the SQLite *file* path the factory should open.

    The async SQLAlchemy engine consumes a URL (e.g. ``sqlite+aiosqlite:///./data/cards.db``),
    but ``sqlite3.connect`` needs a filesystem path. Resolution order:

    1. An explicit ``db_path`` argument (tests pass ``tmp_path / "x.db"``).
    2. The ``CARDS_DATABASE_URL`` env var (empty/whitespace treated as unset — mirrors
       ``src.paths.database_url()`` so the async engine and this factory can never diverge), with
       the SQLAlchemy prefix stripped to a file path. (``CARDS_DATABASE_URL`` — *not*
       ``DATABASE_URL``, which Chainlit hijacks.)
    3. ``src.paths.database_path()`` — ``cards.db`` in the shared central OS data dir, the same
       file the async engine resolves to by default.

    Args:
        db_path: Explicit filesystem path, or ``None`` to derive from the environment.

    Returns:
        A filesystem path string suitable for ``sqlite3.connect``.
    """
    if db_path is not None:
        return db_path

    url = (os.getenv("CARDS_DATABASE_URL") or "").strip()
    if not url:
        return str(database_path())

    for prefix in _SQLALCHEMY_PREFIXES:
        if url.startswith(prefix):
            return url[len(prefix) :]
    return url


class ConnectionFactory:
    """Hands out synchronous ``sqlite3`` connections with sqlite-vec loaded and WAL enabled.

    This is the single seam for **synchronous** SQLite access in the MCP/RAG stack. The async
    SQLAlchemy + aiosqlite engine in ``src/data`` is a separate mechanism and is intentionally
    left untouched. No module should call ``sqlite3.connect`` directly; obtaining connections
    here guarantees the ``sqlite-vec`` extension is always loaded and WAL is always on.

    **Concurrency (AC3 / NFR6):** FastMCP dispatches sync tools to a threadpool, and a
    ``sqlite3`` connection is not safe to share across threads. Each thread therefore receives
    its **own** connection, created lazily on first ``get_connection()`` call and cached in a
    ``threading.local`` store. The stdlib default ``check_same_thread=True`` guard is kept
    (never set it to ``False`` to "share" a connection — that risks corruption).

    **apsw seam (AC4):** a future environment whose driver lacks ``enable_load_extension`` can
    select ``driver="apsw"``. apsw is a Phase-1 *contingency only* — it is **not** implemented,
    so selecting it raises ``NotImplementedError`` with guidance. The default and only supported
    driver is stdlib ``sqlite3``. (An ``ApswConnectionFactory`` adapter would slot in here.)

    Args:
        db_path: Explicit SQLite file path. If ``None``, derived from ``CARDS_DATABASE_URL``
            (SQLAlchemy prefix stripped) or the central ``src.paths.database_path()`` default.
        driver: Connection driver. ``"sqlite3"`` (default) uses the stdlib. ``"apsw"`` is the
            documented contingency seam and raises ``NotImplementedError``.

    Raises:
        NotImplementedError: If ``driver`` is anything other than ``"sqlite3"``.

    Example:
        >>> factory = ConnectionFactory(db_path="./data/cards.db")
        >>> conn = factory.get_connection()
        >>> conn.execute("select vec_version()").fetchone()[0]
        'v0.1.9'
    """

    def __init__(
        self, db_path: str | None = None, driver: Literal["sqlite3", "apsw"] = "sqlite3"
    ) -> None:
        if driver != "sqlite3":
            raise NotImplementedError(
                f"driver={driver!r} is not implemented. The apsw seam is a documented Phase-1 "
                "contingency for environments whose driver lacks sqlite3.enable_load_extension; "
                "the default and only supported driver is stdlib 'sqlite3'."
            )
        self._db_path = _resolve_db_path(db_path)
        self._local = threading.local()

    @property
    def db_path(self) -> str:
        """The resolved SQLite file path this factory opens."""
        return self._db_path

    def get_connection(self) -> sqlite3.Connection:
        """Return this thread's connection, creating and configuring it on first use.

        The connection is cached per thread via ``threading.local``: repeated calls on the same
        thread return the same object, while a different thread receives a distinct one.

        Returns:
            A ``sqlite3.Connection`` with sqlite-vec loaded and WAL journal mode enabled.
        """
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._build_connection()
            self._local.conn = conn
        return conn

    def _build_connection(self) -> sqlite3.Connection:
        """Create a new connection and run the verified load sequence.

        Order (verified on CPython 3.12 / SQLite 3.50 / Windows): connect → enable extension
        loading → ``sqlite_vec.load`` → disable extension loading (hardening: only sqlite-vec
        needs it) → enable WAL. Extension loading is per-connection (not persisted to the file),
        so every connection must repeat it; WAL is per-file but reporting it per-connection is
        idempotent.

        Returns:
            A fully configured ``sqlite3.Connection``.
        """
        conn = sqlite3.connect(self._db_path)  # default check_same_thread=True — keep it
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            wal_result = conn.execute("PRAGMA journal_mode=WAL").fetchone()
            logger.debug(
                "Created sqlite3 connection (db_path=%s, journal_mode=%s)",
                self._db_path,
                wal_result[0] if wal_result else "unknown",
            )
        except Exception:
            conn.close()
            raise
        return conn

    def close(self) -> None:
        """Close and discard this thread's connection, if one exists.

        Intended for test teardown and graceful worker shutdown. Only affects the calling
        thread's connection, since the ``threading.local`` store is per-thread. After calling
        ``close()``, the next ``get_connection()`` call on this thread will build a fresh
        connection.
        """
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            finally:
                self._local.conn = None

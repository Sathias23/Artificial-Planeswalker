"""Database engine and session management for async SQLAlchemy."""

import logging
import sqlite3
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.data.import_state import is_import_in_progress
from src.data.models.base import Base

# Import models to register them with Base.metadata
# These imports ensure SQLAlchemy knows about all tables when creating the schema
from src.data.models.card import (  # noqa: F401
    NOCASE_NAME_INDEX,
    NOCASE_PRINTED_NAME_INDEX,
    CardModel,
)
from src.data.models.combo import (  # noqa: F401
    ComboSnapshotMetaModel,
    ComboVariantModel,
    ComboVariantPieceModel,
)
from src.data.models.deck import DeckModel  # noqa: F401
from src.data.models.deck_card import DeckCardModel  # noqa: F401
from src.paths import database_url as default_database_url

logger = logging.getLogger(__name__)

_NOCASE_INDEX_DDL: tuple[str, ...] = (
    f"CREATE INDEX IF NOT EXISTS {NOCASE_NAME_INDEX} ON cards (name COLLATE NOCASE)",
    f"CREATE INDEX IF NOT EXISTS {NOCASE_PRINTED_NAME_INDEX} "
    "ON cards (printed_name COLLATE NOCASE)",
)


def ensure_nocase_indexes(dbapi_connection: Any, _connection_record: Any = None) -> None:
    """Create the ``COLLATE NOCASE`` name indexes on an existing ``cards`` table, if absent.

    The migration path for databases created before the indexes existed: the MCP server never
    runs ``init_database`` at startup, so the engine's ``connect`` hook calls this on every new
    pooled connection. ``CREATE INDEX IF NOT EXISTS`` is a catalog check once the indexes exist,
    and it raises on a missing table, hence the ``sqlite_master`` guard — a fresh database gets the
    indexes from ``create_all`` instead.

    The index names are checked first and no DDL is issued when both already exist, so a
    read-only or locked database never pays the busy-timeout wait (nor warns) once it is current.

    Never fails the connection: a competing writer holding the lock (a bulk import or index build)
    surfaces as ``sqlite3.OperationalError``, and a corrupt or non-SQLite file as another
    ``sqlite3.DatabaseError``; both are logged so the connection still opens and
    :func:`is_database_initialized` can report the state gracefully. The next new connection
    retries.

    Args:
        dbapi_connection: The raw (aiosqlite-adapted or plain ``sqlite3``) DBAPI connection.
        _connection_record: SQLAlchemy's pool record, unused.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cards'")
        if cursor.fetchone() is None:
            return
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'cards' "
            "AND name IN (?, ?)",
            (NOCASE_NAME_INDEX, NOCASE_PRINTED_NAME_INDEX),
        )
        if len(cursor.fetchall()) == len(_NOCASE_INDEX_DDL):
            return
        for ddl in _NOCASE_INDEX_DDL:
            cursor.execute(ddl)
    except sqlite3.DatabaseError as exc:
        logger.warning("Could not ensure the cards NOCASE indexes (%s); will retry", exc)
    finally:
        cursor.close()


def enable_foreign_keys(dbapi_connection: Any, _connection_record: Any = None) -> None:
    """Turn on SQLite foreign-key enforcement for one new connection.

    SQLite leaves ``PRAGMA foreign_keys`` off by default and the setting is per connection, so
    every engine (the MCP writer and the companion's read-only shell alike) registers this on
    ``connect``. It must run *before* any transaction opens — the pragma is a no-op inside one —
    which is why it lives on the pool's ``connect`` hook rather than a session ``begin`` event.
    With it on, ``deck_cards.deck_id`` cascades on deck deletion and an association naming a
    missing deck or card is rejected with ``IntegrityError``.

    Never fails the connection: a ``sqlite3.DatabaseError`` (a corrupt or non-SQLite file) is
    logged and the connection still opens so :func:`is_database_initialized` can report the
    state gracefully.

    Args:
        dbapi_connection: The raw (aiosqlite-adapted or plain ``sqlite3``) DBAPI connection.
        _connection_record: SQLAlchemy's pool record, unused.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
    except sqlite3.DatabaseError as exc:
        logger.warning("Could not enable SQLite foreign-key enforcement (%s)", exc)
    finally:
        cursor.close()


_ORPHAN_DECK_CARDS_PREDICATE = (
    "NOT EXISTS (SELECT 1 FROM decks d WHERE d.id = deck_cards.deck_id) "
    "OR NOT EXISTS (SELECT 1 FROM cards c WHERE c.id = deck_cards.card_id)"
)
_ORPHAN_DECK_CARDS_PROBE_SQL = (
    f"SELECT 1 FROM deck_cards WHERE {_ORPHAN_DECK_CARDS_PREDICATE} LIMIT 1"
)
_ORPHAN_DECK_CARDS_DELETE_SQL = f"DELETE FROM deck_cards WHERE {_ORPHAN_DECK_CARDS_PREDICATE}"
_SWEEP_TABLES = frozenset({"decks", "cards", "deck_cards"})


def remove_orphan_deck_cards(dbapi_connection: Any, _connection_record: Any = None) -> None:
    """Delete ``deck_cards`` rows whose deck or card no longer exists (connect-time repair).

    Databases written before :func:`enable_foreign_keys` existed can hold associations
    stranded by a deck deletion or a stale-printing removal. Like
    :func:`ensure_nocase_indexes`, this rides the MCP engine's ``connect`` hook because the
    server never runs ``init_database`` at startup; the companion engine (AD-2, read-only)
    never registers it. It runs on every new pooled connection; a clean database pays three
    reads (the catalog check, the ``cards`` emptiness probe, the orphan probe) and no write.

    Guards, in order: all three tables must exist (a fresh database has none); ``cards`` must
    hold at least one row, because an empty card table makes every association look orphaned
    (a never-imported database, or a legacy killed import that predates the marker); a
    first-run import still marked in progress (:mod:`src.data.import_state`) is skipped for the
    same reason; and a probe ``SELECT`` runs before the ``DELETE`` so a current database never
    issues one. When rows are deleted the raw connection commits them.

    Never fails the connection: a lock held by a competing writer or a corrupt file surfaces
    as ``sqlite3.DatabaseError``, which is rolled back and logged; the next new connection
    retries.

    Args:
        dbapi_connection: The raw (aiosqlite-adapted or plain ``sqlite3``) DBAPI connection.
        _connection_record: SQLAlchemy's pool record, unused.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('decks', 'cards', 'deck_cards', 'import_state')"
        )
        tables = {row[0] for row in cursor.fetchall()}
        if not _SWEEP_TABLES <= tables:
            return
        cursor.execute("SELECT 1 FROM cards LIMIT 1")
        if cursor.fetchone() is None:
            return
        if "import_state" in tables:
            cursor.execute("SELECT in_progress FROM import_state WHERE id = 1")
            row = cursor.fetchone()
            if row is not None and row[0]:
                return
        cursor.execute(_ORPHAN_DECK_CARDS_PROBE_SQL)
        if cursor.fetchone() is None:
            return
        cursor.execute(_ORPHAN_DECK_CARDS_DELETE_SQL)
        deleted = cursor.rowcount
        dbapi_connection.commit()
        logger.info("Removed %d orphan deck_cards row(s) left by a pre-enforcement write", deleted)
    except sqlite3.DatabaseError as exc:
        try:
            dbapi_connection.rollback()
        except sqlite3.DatabaseError:
            pass
        logger.warning("Could not sweep orphan deck_cards rows (%s); will retry", exc)
    finally:
        cursor.close()


def create_engine(database_url: str | None = None, *, ensure_indexes: bool = True) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    Args:
        database_url: Database connection string. If None, resolves the shared central-data-dir
            URL via ``src.paths.database_url()`` (an explicit ``CARDS_DATABASE_URL`` still wins).
        ensure_indexes: Register the connect hooks that repair an existing database (the
            no-script migration path): the ``cards`` NOCASE indexes and the orphan
            ``deck_cards`` sweep. The companion app passes ``False``: it is a read-only shell of
            ``cards.db`` (AD-2) and must never issue DDL or a ``DELETE``. Foreign-key enforcement
            (:func:`enable_foreign_keys`) is registered on every SQLite engine regardless.

    Returns:
        Configured AsyncEngine instance for aiosqlite.
    """
    url = database_url or default_database_url()
    engine = create_async_engine(
        url,
        echo=False,  # Set to True for SQL query logging during development
        # Wait up to 5s for a competing writer's lock instead of failing instantly with
        # "database is locked" — the bulk import and index build are both writers, and WAL
        # lets a reader proceed but not a second writer. (aiosqlite forwards this to
        # sqlite3.connect(timeout=...), which sets SQLite's busy timeout.)
        connect_args={"timeout": 5},
    )
    if engine.dialect.name == "sqlite":
        # The pragma is per connection and must precede any transaction, so it is the first
        # connect hook on every engine flavour.
        event.listen(engine.sync_engine, "connect", enable_foreign_keys)
        if ensure_indexes:
            event.listen(engine.sync_engine, "connect", ensure_nocase_indexes)
            event.listen(engine.sync_engine, "connect", remove_orphan_deck_cards)

    # Instrument SQLAlchemy with Logfire if observability is enabled
    # This is safe to call even if Logfire is not configured (it will be a no-op)
    try:
        import logfire

        # Instrument this specific engine for query tracing
        logfire.instrument_sqlalchemy(engine=engine.sync_engine)
        logger.debug(f"SQLAlchemy instrumentation added for engine: {url}")
    except Exception:
        # If logfire is not installed or not configured, skip instrumentation
        # This is expected when Logfire observability is disabled
        pass

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Args:
        engine: AsyncEngine instance to bind sessions to.

    Returns:
        Configured async_sessionmaker with expire_on_commit=False.
    """
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Prevents async detached instance errors
        autoflush=False,
        autocommit=False,
    )
    return session_factory


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session as a context manager.

    Args:
        session_factory: Configured async_sessionmaker instance.

    Yields:
        AsyncSession for database operations.
    """
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_database(engine: AsyncEngine) -> None:
    """Initialize database by creating all tables from model metadata.

    Args:
        engine: AsyncEngine instance to use for table creation.

    Raises:
        Exception: If database initialization fails.
    """
    try:
        logger.info("Initializing database schema...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def is_database_initialized(session: AsyncSession) -> bool:
    """Return whether the ``cards`` table exists **and** holds at least one row.

    A fresh first-run install ships no data (the card set is excluded by design — Scryfall
    license): the ``cards.db`` file, the schema, or the ``cards`` table itself may be absent, or
    present-but-empty. All three states mean "the one-time ``initialize_database`` step has not
    run yet", so this returns ``False`` **without raising** — letting every relational tool surface
    a graceful ``database_not_initialized`` status instead of leaking a raw ``OperationalError``
    (*no such table: cards*).

    A fourth "not ready" state is a **partial** database — rows present but a first-run import
    killed mid-way (see :mod:`src.data.import_state`). That also returns ``False`` so the truncated
    data is treated as not-initialized and ``initialize_database`` re-imports rather than trusting
    it.

    The existence probe reads ``sqlite_master`` (always present) so the missing-table case returns
    ``False`` rather than raising; ``cards`` is a schema constant, never interpolated input. This is
    the async counterpart of :func:`src.search.query.is_database_initialized` (used by the sync
    sqlite-vec tools); the two never share a call site.

    Args:
        session: An ``AsyncSession`` from the server's session factory.

    Returns:
        ``True`` if ``cards`` exists and contains at least one row, else ``False``.
    """
    table = (
        await session.execute(
            text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cards'")
        )
    ).first()
    if table is None:
        return False
    populated = (await session.execute(text("SELECT EXISTS(SELECT 1 FROM cards)"))).scalar()
    if not populated:
        return False
    # A partial (killed mid-import) database has rows but its first-run import never finished; treat
    # it as not-yet-initialized so tools stay graceful and ``initialize_database`` re-imports.
    return not await is_import_in_progress(session)


async def health_check(session: AsyncSession) -> bool:
    """Verify database connectivity and basic operations.

    Performs a test INSERT, SELECT, and DELETE operation to ensure
    the database is functioning properly.

    Args:
        session: AsyncSession to use for health check operations.

    Returns:
        True if health check passes.

    Raises:
        Exception: If any database operation fails.
    """

    try:
        # Create test card
        test_card = CardModel(
            id="00000000-0000-0000-0000-000000000000",
            name="__HEALTH_CHECK__",
            printed_name=None,
            mana_cost="{0}",
            cmc=0.0,
            type_line="Test",
            oracle_text="Health check test card",
            rarity="common",
            set_code="TEST",
            set_name="Test Set",
            oracle_id="00000000-0000-0000-0000-000000000001",
            collector_number="0",
            colors=[],
            color_identity=[],
        )

        # Insert test card
        session.add(test_card)
        await session.commit()

        # Verify retrieval
        from sqlalchemy import select

        stmt = select(CardModel).where(CardModel.id == test_card.id)
        result = await session.execute(stmt)
        retrieved_card = result.scalar_one_or_none()

        if retrieved_card is None:
            raise RuntimeError("Health check failed: Could not retrieve test card")

        # Cleanup
        await session.delete(retrieved_card)
        await session.commit()

        logger.info("Database health check passed")
        return True

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        await session.rollback()
        raise

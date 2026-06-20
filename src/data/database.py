"""Database engine and session management for async SQLAlchemy."""

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.data.models.base import Base

# Import models to register them with Base.metadata
# These imports ensure SQLAlchemy knows about all tables when creating the schema
from src.data.models.bug_report import BugReportModel  # noqa: F401
from src.data.models.card import CardModel  # noqa: F401
from src.data.models.deck import DeckModel  # noqa: F401
from src.data.models.deck_card import DeckCardModel  # noqa: F401

logger = logging.getLogger(__name__)

# Database URL from environment variable
# Using CARDS_DATABASE_URL instead of DATABASE_URL to avoid conflict with Chainlit
DATABASE_URL = os.getenv("CARDS_DATABASE_URL", "sqlite+aiosqlite:///./data/cards.db")


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    Args:
        database_url: Database connection string. If None, uses DATABASE_URL env var.

    Returns:
        Configured AsyncEngine instance for aiosqlite.
    """
    url = database_url or DATABASE_URL
    engine = create_async_engine(
        url,
        echo=False,  # Set to True for SQL query logging during development
    )

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

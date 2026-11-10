"""Manual migration script to add strategy column to decks table.

This script adds the optional strategy column to the existing decks table
for the add-deck-strategy feature, and its ``ix_decks_strategy`` index.

Idempotent: the column is added only when missing, and the index step runs on
every run (``CREATE INDEX IF NOT EXISTS``), so a run whose index step failed is
completed by running the script again.

Run with: uv run python scripts/migrate_add_deck_strategy.py
"""

import asyncio
import logging
import sys

from sqlalchemy import text

from src.data.database import create_engine, create_session_factory

logger = logging.getLogger(__name__)


async def migrate() -> None:
    """Add strategy column to decks table, and its index."""
    engine = create_engine()
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            try:
                result = await session.execute(text("PRAGMA table_info(decks)"))
                column_names = {col[1] for col in result.fetchall()}

                if "strategy" in column_names:
                    logger.info("✓ Strategy column already exists in decks table")
                else:
                    logger.info("Adding strategy column to decks table...")
                    await session.execute(
                        text("ALTER TABLE decks ADD COLUMN strategy VARCHAR NULL")
                    )
                    logger.info("✓ Strategy column added successfully")

                # Always, not only after the ALTER: SQLite's driver autocommits DDL, so a run
                # whose index step failed has already added the column, and a re-run that keyed
                # on the column alone would never create the index.
                logger.info("Ensuring index ix_decks_strategy on strategy column...")
                await session.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_decks_strategy ON decks(strategy)")
                )
                await session.commit()
                logger.info("✓ Index ix_decks_strategy is present")

                # Verify migration
                result = await session.execute(text("PRAGMA table_info(decks)"))
                logger.info("\nCurrent decks table schema:")
                for col in result.fetchall():
                    logger.info("  - %s (%s)", col[1], col[2])

                logger.info("\n✅ Migration completed successfully!")

            except Exception as e:
                logger.error("❌ Migration failed: %s", e)
                await session.rollback()
                sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(migrate())

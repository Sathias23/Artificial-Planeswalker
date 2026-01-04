"""Manual migration script to add strategy column to decks table.

This script adds the optional strategy column to the existing decks table
for the add-deck-strategy feature.

Run with: uv run python scripts/migrate_add_deck_strategy.py
"""

import asyncio
import logging
import sys

from sqlalchemy import text

from src.data.database import create_engine, create_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate() -> None:
    """Add strategy column to decks table."""
    engine = create_engine()
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        try:
            # Check if column already exists
            result = await session.execute(text("PRAGMA table_info(decks)"))
            columns = result.fetchall()
            column_names = [col[1] for col in columns]

            if "strategy" in column_names:
                logger.info("✓ Strategy column already exists in decks table")
                return

            # Add strategy column
            logger.info("Adding strategy column to decks table...")
            await session.execute(text("ALTER TABLE decks ADD COLUMN strategy VARCHAR NULL"))
            await session.commit()
            logger.info("✓ Strategy column added successfully")

            # Create index on strategy column
            logger.info("Creating index on strategy column...")
            await session.execute(
                text("CREATE INDEX IF NOT EXISTS ix_decks_strategy ON decks(strategy)")
            )
            await session.commit()
            logger.info("✓ Index ix_decks_strategy created successfully")

            # Verify migration
            result = await session.execute(text("PRAGMA table_info(decks)"))
            columns = result.fetchall()
            logger.info("\nCurrent decks table schema:")
            for col in columns:
                logger.info(f"  - {col[1]} ({col[2]})")

            logger.info("\n✅ Migration completed successfully!")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            await session.rollback()
            sys.exit(1)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())

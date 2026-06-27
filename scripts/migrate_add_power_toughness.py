"""Manual migration script to add power/toughness columns to the cards table.

Adds the optional ``power`` and ``toughness`` columns to the existing cards
table for the viewer power/toughness-display feature. Idempotent: skips any
column that already exists. After running this, re-import Scryfall data
(``uv run python scripts/import_scryfall_data.py --type oracle_cards``) to
backfill P/T for the existing corpus.

Run with: uv run python scripts/migrate_add_power_toughness.py
"""

import asyncio
import logging
import sys

from sqlalchemy import text

from src.data.database import create_engine, create_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_NEW_COLUMNS = ("power", "toughness")


async def migrate() -> None:
    """Add power/toughness columns to the cards table."""
    engine = create_engine()
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        try:
            result = await session.execute(text("PRAGMA table_info(cards)"))
            existing = {col[1] for col in result.fetchall()}

            for column in _NEW_COLUMNS:
                if column in existing:
                    logger.info("✓ %s column already exists in cards table", column)
                    continue
                logger.info("Adding %s column to cards table...", column)
                await session.execute(text(f"ALTER TABLE cards ADD COLUMN {column} VARCHAR NULL"))
                await session.commit()
                logger.info("✓ %s column added successfully", column)

            result = await session.execute(text("PRAGMA table_info(cards)"))
            logger.info("\nCurrent cards table schema:")
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
    asyncio.run(migrate())

"""Database migration script to add color_identity and tags fields to decks table.

This migration adds two new nullable TEXT columns to the decks table:
- color_identity: JSON array of color codes (e.g., ["W", "R"])
- tags: JSON array of tag strings (e.g., ["aggro", "burn"])

The migration is idempotent - it will skip adding columns if they already exist.

Usage:
    uv run python scripts/migrate_deck_fields.py
"""

import asyncio
import logging
import sys

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.data.database import create_engine, create_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_deck_fields() -> bool:
    """Add color_identity and tags columns to decks table if they don't exist.

    Returns:
        True if migration succeeded or columns already exist, False on error
    """
    logger.info("Starting deck fields migration...")

    engine = create_engine()
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            # Check if columns already exist by attempting to query them
            try:
                result = await session.execute(
                    text("SELECT color_identity, tags FROM decks LIMIT 1")
                )
                result.fetchall()  # Consume results
                logger.info("Columns already exist - migration not needed")
                return True
            except OperationalError:
                # Columns don't exist - proceed with migration
                logger.info("Columns not found - adding them now...")

            # Add color_identity column
            try:
                await session.execute(
                    text("ALTER TABLE decks ADD COLUMN color_identity TEXT DEFAULT NULL")
                )
                logger.info("Added color_identity column")
            except OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.info("color_identity column already exists")
                else:
                    raise

            # Add tags column
            try:
                await session.execute(text("ALTER TABLE decks ADD COLUMN tags TEXT DEFAULT NULL"))
                logger.info("Added tags column")
            except OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.info("tags column already exists")
                else:
                    raise

            await session.commit()
            logger.info("Migration completed successfully")
            return True

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False
    finally:
        await engine.dispose()


if __name__ == "__main__":
    success = asyncio.run(migrate_deck_fields())
    sys.exit(0 if success else 1)

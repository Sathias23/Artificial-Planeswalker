"""Manual migration script to add the commander column to the deck_cards table.

Adds the ``commander`` (BOOLEAN NOT NULL DEFAULT 0) column to the existing
deck_cards table for commander identity (Story 6.1 / FR25 / AD-13). The flag is
two-state: ``True`` = this row is one of the deck's commanders (two flagged rows
= partners), ``False`` = not a commander. Unlike ``game_changer`` there is no
"unknown" state — an unflagged card is simply not a commander, so the column is
NOT nullable.

Idempotent: skips the column if it already exists. The ``DEFAULT 0`` on the
ALTER is the entire backfill — existing rows read back ``False`` and no
follow-up backfill step exists for this migration. A fresh database created via
``Base.metadata.create_all`` includes the column automatically.

Run with: uv run python scripts/migrate_add_deck_card_commander.py
"""

import asyncio
import logging
import sys

from sqlalchemy import text

from src.data.database import create_engine, create_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_NEW_COLUMN = "commander"


async def migrate() -> None:
    """Add the commander column to the deck_cards table."""
    engine = create_engine()
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        try:
            result = await session.execute(text("PRAGMA table_info(deck_cards)"))
            existing = {col[1] for col in result.fetchall()}

            if _NEW_COLUMN in existing:
                logger.info("✓ %s column already exists in deck_cards table", _NEW_COLUMN)
            else:
                logger.info("Adding %s column to deck_cards table...", _NEW_COLUMN)
                ddl = f"ALTER TABLE deck_cards ADD COLUMN {_NEW_COLUMN} BOOLEAN NOT NULL DEFAULT 0"
                await session.execute(text(ddl))
                await session.commit()
                logger.info("✓ %s column added successfully", _NEW_COLUMN)

            result = await session.execute(text("PRAGMA table_info(deck_cards)"))
            logger.info("\nCurrent deck_cards table schema:")
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

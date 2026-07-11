"""Manual migration script to add the game_changer column to the cards table.

Adds the optional ``game_changer`` (BOOLEAN) column to the existing cards table
for the deck power-level assessment feature. The column is three-state and
nullable: ``None`` = "unknown / not yet backfilled", ``True`` = confirmed Game
Changer, ``False`` = confirmed not. Never coalesce ``None`` to ``False`` (AD-4).

Idempotent: skips the column if it already exists. This migration only performs
the additive ``ALTER TABLE`` — it leaves every existing row ``NULL`` (unknown)
and does NOT trigger the re-import. Backfilling with real values is a separate,
deliberate, operator-invoked step (the Scryfall re-import is heavy, ~60k cards).

After running this migration, backfill ``game_changer`` for the existing corpus
by explicitly running the Scryfall re-import:

    uv run python scripts/import_scryfall_data.py --type oracle_cards

``oracle_cards`` is sufficient (and lighter than ``default_cards``) because
``game_changer`` is a per-oracle-identity property. The re-import replays
``transform_scryfall_card`` and overwrites every card's ``game_changer`` with the
real bulk value. This migration does NOT run that step for you.

Run with: uv run python scripts/migrate_add_game_changer.py
"""

import asyncio
import logging
import sys

from sqlalchemy import text

from src.data.database import create_engine, create_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_NEW_COLUMN = "game_changer"


async def migrate() -> None:
    """Add the game_changer column to the cards table."""
    engine = create_engine()
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        try:
            result = await session.execute(text("PRAGMA table_info(cards)"))
            existing = {col[1] for col in result.fetchall()}

            if _NEW_COLUMN in existing:
                logger.info("✓ %s column already exists in cards table", _NEW_COLUMN)
            else:
                logger.info("Adding %s column to cards table...", _NEW_COLUMN)
                await session.execute(
                    text(f"ALTER TABLE cards ADD COLUMN {_NEW_COLUMN} BOOLEAN NULL")
                )
                await session.commit()
                logger.info("✓ %s column added successfully", _NEW_COLUMN)

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

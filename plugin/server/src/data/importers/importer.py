"""Batch import logic for inserting cards into the database."""

import logging
import time
from collections.abc import Iterator

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.card import CardModel

logger = logging.getLogger(__name__)


class ImportStatistics:
    """Track statistics during import process."""

    def __init__(self) -> None:
        self.total_processed = 0
        self.total_inserted = 0
        self.total_errors = 0
        self.start_time = time.time()

    def elapsed_time(self) -> float:
        """Get elapsed time in seconds since import started."""
        return time.time() - self.start_time

    def cards_per_second(self) -> float:
        """Calculate import throughput in cards per second."""
        elapsed = self.elapsed_time()
        return self.total_processed / elapsed if elapsed > 0 else 0.0

    def summary(self) -> str:
        """Generate summary statistics string."""
        return (
            f"Import complete: {self.total_inserted:,} cards inserted, "
            f"{self.total_errors} errors, "
            f"{self.elapsed_time():.1f} seconds "
            f"({self.cards_per_second():.1f} cards/sec)"
        )


async def import_cards(
    session: AsyncSession,
    cards_iterator: Iterator[CardModel | None],
    batch_size: int = 1000,
) -> ImportStatistics:
    """Import cards into database with batch upserts.

    Processes cards in batches, using INSERT OR REPLACE for SQLite upsert logic.
    Commits after each batch to avoid long-running transactions.

    Args:
        session: AsyncSession for database operations.
        cards_iterator: Iterator yielding CardModel instances or None (for skipped cards).
        batch_size: Number of cards to insert per batch (default 1,000).

    Returns:
        ImportStatistics object with import metrics.
    """
    stats = ImportStatistics()
    batch: list[CardModel] = []

    logger.info(f"Starting import with batch size: {batch_size}")

    for card in cards_iterator:
        stats.total_processed += 1

        # Skip None cards (transformation failures)
        if card is None:
            stats.total_errors += 1
            continue

        batch.append(card)

        # Insert batch when it reaches batch_size
        if len(batch) >= batch_size:
            await _insert_batch(session, batch, stats)
            batch.clear()

            # Log progress
            logger.info(
                f"Processed {stats.total_processed:,} cards "
                f"({stats.total_inserted:,} inserted, {stats.total_errors} errors) "
                f"- {stats.cards_per_second():.1f} cards/sec"
            )

    # Insert remaining cards in final partial batch
    if batch:
        await _insert_batch(session, batch, stats)
        logger.info(f"Inserted final batch of {len(batch)} cards")

    logger.info(stats.summary())
    return stats


async def _insert_batch(
    session: AsyncSession,
    batch: list[CardModel],
    stats: ImportStatistics,
) -> None:
    """Insert a batch of cards with upsert logic.

    Uses SQLite's INSERT OR REPLACE to handle duplicate primary keys.

    Args:
        session: AsyncSession for database operations.
        batch: List of CardModel instances to insert.
        stats: ImportStatistics to update with insert count.
    """
    try:
        # Convert CardModel instances to dictionaries
        card_dicts = []
        for card in batch:
            card_dict = {
                "id": card.id,
                "name": card.name,
                "printed_name": card.printed_name,
                "oracle_id": card.oracle_id,
                "mana_cost": card.mana_cost,
                "cmc": card.cmc,
                "type_line": card.type_line,
                "oracle_text": card.oracle_text,
                "power": card.power,
                "toughness": card.toughness,
                "rarity": card.rarity,
                "set_code": card.set_code,
                "set_name": card.set_name,
                "collector_number": card.collector_number,
                "colors": card.colors,
                "color_identity": card.color_identity,
                "color_indicator": card.color_indicator,
                "keywords": card.keywords,
                "legalities": card.legalities,
                "card_faces": card.card_faces,
                "image_uris": card.image_uris,
                "games": card.games,
            }
            card_dicts.append(card_dict)

        # Use SQLite INSERT OR REPLACE for upsert
        stmt = sqlite_insert(CardModel).values(card_dicts)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": stmt.excluded.name,
                "printed_name": stmt.excluded.printed_name,
                "oracle_id": stmt.excluded.oracle_id,
                "mana_cost": stmt.excluded.mana_cost,
                "cmc": stmt.excluded.cmc,
                "type_line": stmt.excluded.type_line,
                "oracle_text": stmt.excluded.oracle_text,
                "power": stmt.excluded.power,
                "toughness": stmt.excluded.toughness,
                "rarity": stmt.excluded.rarity,
                "set_code": stmt.excluded.set_code,
                "set_name": stmt.excluded.set_name,
                "collector_number": stmt.excluded.collector_number,
                "colors": stmt.excluded.colors,
                "color_identity": stmt.excluded.color_identity,
                "color_indicator": stmt.excluded.color_indicator,
                "keywords": stmt.excluded.keywords,
                "legalities": stmt.excluded.legalities,
                "card_faces": stmt.excluded.card_faces,
                "image_uris": stmt.excluded.image_uris,
                "games": stmt.excluded.games,
            },
        )

        await session.execute(stmt)
        await session.commit()

        stats.total_inserted += len(batch)

    except Exception as e:
        logger.error(f"Batch insert failed: {e}")
        await session.rollback()
        stats.total_errors += len(batch)
        raise

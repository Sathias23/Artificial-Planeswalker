"""Batch import logic for inserting cards into the database."""

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.importers.transformers import TransformReject
from src.data.models.card import CardModel

logger = logging.getLogger(__name__)


@dataclass
class ReconcileStatistics:
    """Outcome of the post-import oracle-identity reconcile stage.

    Attributes:
        games_updated: Surviving pre-existing rows whose ``games`` was rewritten to the
            cross-printing union.
        rows_deleted: Stale (non-canonical) ``cards`` rows deleted.
        deck_cards_repointed: ``deck_cards`` rows whose ``card_id`` was repointed from a
            stale printing to the canonical row.
        deck_cards_merged: ``deck_cards`` rows merged (quantity summed) into an existing
            canonical-row entry because the deck held both printings.
        stale_remaining: Oracle identities left untouched because their canonical row is
            absent from the database (its printing was rejected this run).
        stale_sample: Up to five sorted sample oracle ids of those skipped identities,
            for user-facing diagnostics (the full set is in the logs).
        failed: ``True`` when the reconcile stage itself failed and was skipped — the
            zeroed counters then mean "unknown", not "clean".
    """

    games_updated: int = 0
    rows_deleted: int = 0
    deck_cards_repointed: int = 0
    deck_cards_merged: int = 0
    stale_remaining: int = 0
    stale_sample: tuple[str, ...] = ()
    failed: bool = False


class ImportStatistics:
    """Track statistics during import process."""

    def __init__(self) -> None:
        self.total_processed = 0
        self.total_inserted = 0
        self.total_errors = 0
        self.rejects: list[TransformReject] = []
        self.reconcile = ReconcileStatistics()
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
    rejects: list[TransformReject] | None = None,
) -> ImportStatistics:
    """Import cards into database with batch upserts.

    Processes cards in batches, using INSERT OR REPLACE for SQLite upsert logic.
    Commits after each batch to avoid long-running transactions.

    Args:
        session: AsyncSession for database operations.
        cards_iterator: Iterator yielding CardModel instances or None (for skipped cards).
        batch_size: Number of cards to insert per batch (default 1,000).
        rejects: Optional shared reject collector (the same list the transformer behind
            *cards_iterator* appends to). It becomes ``ImportStatistics.rejects``, so each
            ``None`` counted as an error carries its identity + reason.

    Returns:
        ImportStatistics object with import metrics.
    """
    stats = ImportStatistics()
    if rejects is not None:
        # Alias, don't copy: the transformer appends to this list lazily as the iterator
        # is consumed, so by the time the loop below finishes it holds one record per None.
        stats.rejects = rejects
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
                "game_changer": card.game_changer,
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
                "game_changer": stmt.excluded.game_changer,
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

"""Main orchestrator for Scryfall bulk data import process."""

import logging
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select, update
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.import_state import (
    is_import_in_progress,
    mark_import_finished,
    mark_import_started,
)
from src.data.importers.aggregate import OracleAggregate, build_oracle_aggregates, group_key
from src.data.importers.importer import ImportStatistics, import_cards
from src.data.importers.parser import stream_cards
from src.data.importers.scryfall_api import download_bulk_data, fetch_bulk_data_list
from src.data.importers.transformers import transform_scryfall_card
from src.data.models.card import CardModel

logger = logging.getLogger(__name__)

#: Bulk files are served from data.scryfall.io (metadata from api.scryfall.com).
_ALLOWED_DOWNLOAD_SUFFIXES = (".scryfall.io", ".scryfall.com")

#: Ceiling when Scryfall's metadata advertises no size (largest bulk set is ~2 GiB).
DEFAULT_MAX_DOWNLOAD_BYTES = 4 * 1024**3

#: Slack over the advertised size — the live file may have grown since the metadata call.
DOWNLOAD_SIZE_SLACK_BYTES = 64 * 1024 * 1024


class ScryfallImportError(Exception):
    """Raised when Scryfall import process fails."""

    pass


def _validate_download_uri(uri: str) -> None:
    """Refuse a metadata-supplied download_uri that isn't https on a Scryfall host."""
    parsed = urlparse(uri)
    host = (parsed.hostname or "").lower()
    trusted = host.endswith(_ALLOWED_DOWNLOAD_SUFFIXES) or host in ("scryfall.io", "scryfall.com")
    if parsed.scheme != "https" or not trusted:
        raise ScryfallImportError(
            f"Refusing untrusted download_uri (want https on a scryfall.io/.com host): {uri!r}"
        )


def _max_download_bytes(advertised_size: int) -> int:
    """Byte ceiling for the download: advertised size plus slack, or a hard default."""
    if advertised_size <= 0:
        return DEFAULT_MAX_DOWNLOAD_BYTES
    return advertised_size + max(advertised_size // 2, DOWNLOAD_SIZE_SLACK_BYTES)


def iter_canonical_models(
    file_path: Path, aggregates: dict[str, OracleAggregate]
) -> Iterator[CardModel | None]:
    """Stream pass 2: transform each identity's canonical printing with union ``games``.

    Re-streams the bulk file, skips every printing that is not its group's canonical pick,
    and overrides each kept card's ``games`` with the sorted union across all printings of
    its oracle identity. Cards outside the aggregate map (no usable group key) are passed
    through untouched — they are never dropped here.

    Args:
        file_path: Path to the bulk JSON file (same file pass 1 aggregated).
        aggregates: Per-identity aggregates from
            :func:`~src.data.importers.aggregate.build_oracle_aggregates`.

    Yields:
        A transformed :class:`CardModel` per canonical printing, or ``None`` when the
        transformer rejects a card (counted as an error by ``import_cards``).
    """
    for card_json in stream_cards(file_path):
        key = group_key(card_json)
        aggregate = aggregates.get(key) if key is not None else None
        if aggregate is not None:
            card_id = str(card_json.get("id") or "")
            if card_id != aggregate.canonical_id:
                continue  # non-canonical printing — deduplicated away
        card = transform_scryfall_card(card_json)
        if card is not None and aggregate is not None:
            card.games = sorted(aggregate.games)
        yield card


async def reconcile_games(session: AsyncSession, aggregates: dict[str, OracleAggregate]) -> int:
    """Batch-update ``games`` on pre-existing rows whose value differs from the union.

    The importer upserts by printing ``id`` and never deletes, so rows imported by an
    older run (e.g. Scryfall's own ``oracle_cards`` canonical picks) can carry a stale,
    single-printing ``games`` value while decks still reference them. This scans the
    ``cards`` table and rewrites ``games`` to the sorted union for every row whose
    ``oracle_id`` has an aggregate and whose stored value differs — no rows are deleted
    or re-pointed.

    Args:
        session: AsyncSession for database operations.
        aggregates: Per-identity aggregates from pass 1 (keyed by oracle id / group key).

    Returns:
        Number of rows updated.

    Raises:
        IntegrityError: Re-raised after rollback on constraint failure.
        DatabaseError: Re-raised after rollback on database failure.
    """
    if not aggregates:
        return 0
    rows = await session.execute(select(CardModel.id, CardModel.oracle_id, CardModel.games))
    params: list[dict[str, Any]] = []
    for row_id, oracle_id, games in rows.all():
        aggregate = aggregates.get(oracle_id or "")
        if aggregate is None:
            continue
        union = sorted(aggregate.games)
        if (games or []) != union:
            params.append({"id": row_id, "games": union})
    if not params:
        return 0
    try:
        # ORM bulk UPDATE by primary key: each param dict carries the pk + new value.
        await session.execute(update(CardModel), params)
        await session.commit()
    except (IntegrityError, DatabaseError):
        await session.rollback()
        raise
    logger.info("Reconciled games on %d pre-existing card rows", len(params))
    return len(params)


async def import_scryfall_bulk_data(
    session: AsyncSession,
    bulk_type: str = "oracle_cards",
    temp_dir: Path | None = None,
) -> ImportStatistics:
    """Import Scryfall bulk data into database, deduplicated to one row per oracle identity.

    Orchestrates the complete import process:
    1. Fetch bulk data metadata from Scryfall API
    2. Download the specified bulk data file
    3. Pass 1 — stream the file to aggregate every printing per oracle identity
       (union of ``games`` + deterministic canonical-printing choice)
    4. Pass 2 — re-stream, keep only canonical printings, override ``games`` with the
       sorted union, and batch-upsert into the database
    5. Reconcile — batch-update ``games`` on pre-existing rows (stale printings from an
       older import) whose value differs from the union

    The dedup/union runs uniformly for any ``bulk_type``; for ``oracle_cards`` (one
    printing per oracle id) it is a natural no-op. Importing ``default_cards`` yields
    roughly the oracle-distinct card count, not the per-printing count.

    Args:
        session: AsyncSession for database operations.
        bulk_type: Type of bulk data to import (default: "oracle_cards").
                   Options: "oracle_cards", "default_cards", "unique_artwork".
                   ``default_cards`` (~500 MB download) covers all printings, so ``games``
                   reflects true cross-printing availability.
        temp_dir: Directory for temporary download files. Uses system temp if None.

    Returns:
        ImportStatistics with import metrics.

    Raises:
        ScryfallImportError: If any stage of the import fails.
    """
    logger.info(f"Starting Scryfall bulk data import (type: {bulk_type})")

    try:
        # Stage 1: Fetch bulk data metadata
        logger.info("Stage 1/6: Fetching bulk data metadata...")
        bulk_data_list = await fetch_bulk_data_list()

        # Find the requested bulk data type
        bulk_data = None
        for entry in bulk_data_list:
            if entry.get("type") == bulk_type:
                bulk_data = entry
                break

        if not bulk_data:
            available_types = [entry.get("type") for entry in bulk_data_list]
            raise ScryfallImportError(
                f"Bulk data type '{bulk_type}' not found. Available types: {available_types}"
            )

        download_uri = bulk_data["download_uri"]
        _validate_download_uri(download_uri)
        advertised_size = int(bulk_data.get("size") or 0)
        file_size_mb = advertised_size / (1024 * 1024)
        logger.info(f"Found bulk data: {bulk_type} ({file_size_mb:.1f} MB)")

        # Stage 2: Download bulk data file. Without a caller-supplied temp_dir, use a
        # fresh private (0700) per-run directory — never a fixed path in the shared temp
        # root, where another local user could pre-seed or symlink the filename.
        logger.info("Stage 2/6: Downloading bulk data file...")
        created_dir: Path | None = None
        if temp_dir is None:
            created_dir = Path(tempfile.mkdtemp(prefix="scryfall-import-"))
            temp_dir = created_dir

        try:
            output_file = temp_dir / f"scryfall_{bulk_type}.json"
            downloaded_file = await download_bulk_data(
                download_uri, output_file, max_bytes=_max_download_bytes(advertised_size)
            )

            # Stage 3: Pass 1 — aggregate every printing per oracle identity
            logger.info("Stage 3/6: Aggregating printings per oracle identity (pass 1)...")
            aggregates = build_oracle_aggregates(downloaded_file)

            # Stage 4: Pass 2 — re-stream, keep canonical printings, union games
            logger.info("Stage 4/6: Transforming canonical printings (pass 2)...")

            # First-run completion marker: import_cards commits per batch, so a hard process kill
            # between batches would otherwise leave a partial DB indistinguishable from a complete
            # one. Flag the import in progress (its own commit, before the first batch) and clear it
            # only once everything below finishes. Skip for a clean update of an already-populated
            # DB — it stays usable throughout its upsert — but still manage the marker when resuming
            # a previously-killed partial import (rows present, flag still set).
            existing = await session.scalar(select(func.count()).select_from(CardModel)) or 0
            manage_marker = existing == 0 or await is_import_in_progress(session)
            if manage_marker:
                await mark_import_started(session)

            # Stage 5: Import cards into database
            logger.info("Stage 5/6: Batch importing into database...")
            stats = await import_cards(session, iter_canonical_models(downloaded_file, aggregates))

            # Stage 6: Reconcile pre-existing rows to the union games. Non-fatal: the card
            # import above has already committed, so a reconcile failure (a transient lock/disk
            # error on the bulk UPDATE) must not fail the whole run and leave the tool reporting
            # status="error" over a fully-populated database — where a plain retry would then
            # short-circuit as already_initialized with games left stale. The only cost of
            # skipping it is that some pre-existing rows keep stale games until the next
            # `update=true` run, which re-runs this reconcile.
            logger.info("Stage 6/6: Reconciling games on pre-existing rows...")
            try:
                await reconcile_games(session, aggregates)
            except (IntegrityError, DatabaseError) as exc:
                logger.warning(
                    "games reconciliation failed; the card import still succeeded, so some "
                    "pre-existing rows may keep stale games until the next update: %s",
                    exc,
                )

            if manage_marker:
                await mark_import_finished(session)
        finally:
            # Cleanup: the per-run directory (and anything in it), or just the file
            # when the caller owns the directory.
            try:
                if created_dir is not None:
                    shutil.rmtree(created_dir, ignore_errors=True)
                else:
                    output_file.unlink(missing_ok=True)
                logger.info("Cleaned up temporary download")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary download: {e}")

        logger.info("Import process completed successfully")
        return stats

    except Exception as e:
        error_msg = f"Scryfall import failed: {e}"
        logger.error(error_msg)
        raise ScryfallImportError(error_msg) from e

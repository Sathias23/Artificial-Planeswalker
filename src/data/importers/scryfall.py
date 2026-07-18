"""Main orchestrator for Scryfall bulk data import process."""

import logging
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.import_state import (
    is_import_in_progress,
    mark_import_finished,
    mark_import_started,
)
from src.data.importers.aggregate import OracleAggregate, build_oracle_aggregates, group_key
from src.data.importers.importer import ImportStatistics, ReconcileStatistics, import_cards
from src.data.importers.parser import stream_cards
from src.data.importers.scryfall_api import download_bulk_data, fetch_bulk_data_list
from src.data.importers.transformers import TransformReject, transform_scryfall_card
from src.data.models.card import CardModel
from src.data.models.deck_card import DeckCardModel

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
    file_path: Path,
    aggregates: dict[str, OracleAggregate],
    rejects: list[TransformReject] | None = None,
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
        rejects: Optional collector passed through to the transformer; gains one
            :class:`TransformReject` (identity + reason) per rejected card.

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
        card = transform_scryfall_card(card_json, rejects)
        if card is not None and aggregate is not None:
            card.games = sorted(aggregate.games)
        yield card


def plan_identity_dedup(
    aggregates: dict[str, OracleAggregate],
    rows_by_oracle: dict[str, list[str]],
) -> tuple[dict[str, str], set[str]]:
    """Pure dedup decision: which stale rows to collapse into which canonical row.

    For every oracle id present in *rows_by_oracle* whose aggregate exists, the survivor
    is the aggregate's ``canonical_id``. Rows with any other id are marked stale. When
    the canonical row is absent from the database (its printing was rejected this run),
    the whole identity is skipped — nothing may be touched for it, because deleting the
    old rows would lose the card entirely.

    Args:
        aggregates: Per-identity aggregates from pass 1 (keyed by oracle id / group key).
        rows_by_oracle: Mapping of ``cards.oracle_id`` to the row ids currently stored
            under that identity. Identities absent from *aggregates* are left untouched.

    Returns:
        A ``(remap, skipped)`` pair: *remap* maps each stale row id to its canonical row
        id; *skipped* holds the oracle ids left untouched because their canonical row is
        absent (counted as stale-remaining).
    """
    remap: dict[str, str] = {}
    skipped: set[str] = set()
    for oracle_id, row_ids in rows_by_oracle.items():
        aggregate = aggregates.get(oracle_id)
        if aggregate is None or not aggregate.canonical_id:
            continue  # out-of-snapshot identity — not this run's concern
        if aggregate.canonical_id not in row_ids:
            skipped.add(oracle_id)  # canonical printing rejected this run — touch nothing
            continue
        for row_id in row_ids:
            if row_id != aggregate.canonical_id:
                remap[row_id] = aggregate.canonical_id
    return remap, skipped


#: Chunk size for bulk ``DELETE ... WHERE id IN (...)`` (stays well under SQLite's
#: bound-parameter limit even on conservative builds).
_DELETE_CHUNK_SIZE = 500

#: How many skipped oracle ids to surface on ``ReconcileStatistics.stale_sample``.
_STALE_SAMPLE_SIZE = 5


async def reconcile_oracle_identities(
    session: AsyncSession, aggregates: dict[str, OracleAggregate]
) -> ReconcileStatistics:
    """Collapse duplicate rows per oracle identity and reconcile ``games`` (one transaction).

    The importer upserts by printing ``id`` and never deletes, so when the canonical
    printing shifts between snapshots each refresh inserts a new row while the old one
    persists. Per oracle id in *aggregates* this keeps only the aggregate's
    ``canonical_id`` row: ``deck_cards`` references are repointed to the canonical row
    **before** the stale rows are deleted (FK enforcement is OFF — a delete would
    silently dangle), merging quantities when the deck already holds the canonical
    printing under the same ``(deck_id, card_id, sideboard)`` key. Surviving rows whose
    ``games`` differs from the cross-printing union are batch-updated (the pre-existing
    games propagation). Identities whose canonical row is absent (rejected this run) and
    rows whose oracle id has no aggregate are left untouched. Idempotent: a clean
    database yields all-zero statistics and no write transaction.

    Args:
        session: AsyncSession for database operations.
        aggregates: Per-identity aggregates from pass 1 (keyed by oracle id / group key).

    Returns:
        A :class:`~src.data.importers.importer.ReconcileStatistics` with counts of games
        updates, deleted rows, deck repoints/merges, and stale-remaining identities
        (plus up to five sample skipped oracle ids).

    Raises:
        IntegrityError: Re-raised after rollback on constraint failure.
        DatabaseError: Re-raised after rollback on database failure.
    """
    stats = ReconcileStatistics()
    if not aggregates:
        return stats

    rows = await session.execute(select(CardModel.id, CardModel.oracle_id, CardModel.games))
    rows_by_oracle: dict[str, list[str]] = {}
    games_by_id: dict[str, list[str]] = {}
    for row_id, oracle_id, games in rows.all():
        rows_by_oracle.setdefault(oracle_id or "", []).append(row_id)
        games_by_id[row_id] = games or []

    remap, skipped = plan_identity_dedup(aggregates, rows_by_oracle)
    stats.stale_remaining = len(skipped)
    stats.stale_sample = tuple(sorted(skipped)[:_STALE_SAMPLE_SIZE])

    # Games propagation on surviving rows only: stale rows are about to be deleted, and
    # skipped identities (canonical rejected) must not be touched at all.
    games_params: list[dict[str, Any]] = []
    for oracle_id, row_ids in rows_by_oracle.items():
        if oracle_id in skipped:
            continue
        aggregate = aggregates.get(oracle_id)
        if aggregate is None:
            continue
        union = sorted(aggregate.games)
        for row_id in row_ids:
            if row_id not in remap and games_by_id[row_id] != union:
                games_params.append({"id": row_id, "games": union})

    # Plan deck_cards repoints/merges. The deck_cards table is small (user decks), so one
    # full scan beats chunked IN-queries over potentially tens of thousands of stale ids.
    repoints: list[tuple[str, str, bool, str]] = []  # (deck_id, stale_id, sideboard, canonical)
    merges: list[tuple[str, str, bool, str, int]] = []  # ... + quantity to sum
    if remap:
        deck_rows = await session.execute(
            select(
                DeckCardModel.deck_id,
                DeckCardModel.card_id,
                DeckCardModel.sideboard,
                DeckCardModel.quantity,
            )
        )
        all_deck_cards = deck_rows.all()
        occupied = {
            (deck_id, card_id, sideboard) for deck_id, card_id, sideboard, _ in all_deck_cards
        }
        for deck_id, card_id, sideboard, quantity in all_deck_cards:
            canonical = remap.get(card_id)
            if canonical is None:
                continue
            target_key = (deck_id, canonical, sideboard)
            if target_key in occupied:
                # Composite-PK collision: the deck holds both printings — merge quantities.
                merges.append((deck_id, card_id, sideboard, canonical, quantity))
            else:
                repoints.append((deck_id, card_id, sideboard, canonical))
                occupied.add(target_key)  # later stale printings of the same identity merge

    if not (games_params or remap):
        return stats  # already clean — no write transaction at all

    try:
        if games_params:
            # ORM bulk UPDATE by primary key: each param dict carries the pk + new value.
            await session.execute(update(CardModel), games_params)
        # Repoint/merge deck references BEFORE deleting stale rows, in the same transaction.
        for deck_id, stale_id, sideboard, canonical in repoints:
            await session.execute(
                update(DeckCardModel)
                .where(
                    DeckCardModel.deck_id == deck_id,
                    DeckCardModel.card_id == stale_id,
                    DeckCardModel.sideboard == sideboard,
                )
                .values(card_id=canonical)
            )
        for deck_id, stale_id, sideboard, canonical, quantity in merges:
            await session.execute(
                update(DeckCardModel)
                .where(
                    DeckCardModel.deck_id == deck_id,
                    DeckCardModel.card_id == canonical,
                    DeckCardModel.sideboard == sideboard,
                )
                .values(quantity=DeckCardModel.quantity + quantity)
            )
            await session.execute(
                delete(DeckCardModel).where(
                    DeckCardModel.deck_id == deck_id,
                    DeckCardModel.card_id == stale_id,
                    DeckCardModel.sideboard == sideboard,
                )
            )
        stale_ids = list(remap)
        for start in range(0, len(stale_ids), _DELETE_CHUNK_SIZE):
            chunk = stale_ids[start : start + _DELETE_CHUNK_SIZE]
            await session.execute(delete(CardModel).where(CardModel.id.in_(chunk)))
        await session.commit()
    except (IntegrityError, DatabaseError):
        await session.rollback()
        raise

    stats.games_updated = len(games_params)
    stats.rows_deleted = len(remap)
    stats.deck_cards_repointed = len(repoints)
    stats.deck_cards_merged = len(merges)
    logger.info(
        "Oracle-identity reconcile: %d stale rows deleted, %d deck references repointed, "
        "%d merged, %d games updates, %d identities skipped (canonical absent)",
        stats.rows_deleted,
        stats.deck_cards_repointed,
        stats.deck_cards_merged,
        stats.games_updated,
        stats.stale_remaining,
    )
    return stats


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
    5. Reconcile — collapse duplicate rows per oracle identity (stale printings from an
       older import: repoint ``deck_cards`` to the canonical row, then delete the stale
       rows) and batch-update ``games`` on surviving rows whose value differs from the
       union; the outcome lands on ``ImportStatistics.reconcile``

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
            rejects: list[TransformReject] = []
            stats = await import_cards(
                session,
                iter_canonical_models(downloaded_file, aggregates, rejects),
                rejects=rejects,
            )

            # Stage 6: Reconcile pre-existing rows per oracle identity (dedup stale
            # printings, repoint decks, propagate union games). Non-fatal: the card
            # import above has already committed, so a reconcile failure (a transient lock/disk
            # error on the bulk UPDATE) must not fail the whole run and leave the tool reporting
            # status="error" over a fully-populated database — where a plain retry would then
            # short-circuit as already_initialized with games left stale. The only cost of
            # skipping it is that some pre-existing rows keep stale data until the next
            # `update=true` run, which re-runs this reconcile.
            logger.info("Stage 6/6: Reconciling oracle identities on pre-existing rows...")
            try:
                stats.reconcile = await reconcile_oracle_identities(session, aggregates)
            except (IntegrityError, DatabaseError) as exc:
                # The reconcile's read phase runs before its internal write-guard, so a
                # failure there (e.g. "database is locked") reaches this handler with the
                # session still in pending-rollback state. Roll back here, or the next
                # session use (mark_import_finished below, or the caller's follow-up
                # queries) raises PendingRollbackError and escalates a non-fatal stage
                # into a failed import.
                try:
                    await session.rollback()
                except Exception:
                    logger.warning(
                        "session rollback after failed reconciliation also failed",
                        exc_info=True,
                    )
                stats.reconcile = ReconcileStatistics(failed=True)
                logger.warning(
                    "oracle-identity reconciliation failed; the card import still succeeded, "
                    "so some pre-existing rows may keep stale data until the next update: %s",
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

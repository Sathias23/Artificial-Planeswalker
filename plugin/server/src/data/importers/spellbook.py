"""Spellbook wire → ``ComboRecord`` normalization and snapshot import (Story 6.2).

The normalize-at-import seam (AD-11): each wire variant from the Commander Spellbook
bulk export becomes a validated :class:`~src.data.schemas.combo.ComboRecord`
(``bucket=None``) exactly once, HERE — the snapshot tables store canonical rows, never
raw wire JSON. The bracket vocabulary is a **closed letter→token map**: anything
outside the seven known letters is a hard error that aborts the import (the 5.6 "no
speculative aliases" contract; the ``ComboBracketTag`` Literal is the second line of
defense). No fuzzy fallback, ever — an unknown tag must never map to a wrong Bracket
floor.

Atomicity model (deliberately different from the card importer): normalization of the
ENTIRE export completes before any table write, then ONE transaction deletes the
previous snapshot rows, inserts the new variant + piece rows, and upserts the metadata
row. Any failure rolls back and leaves the previous snapshot intact — no
``import_state``-style marker is needed because a partial snapshot is unrepresentable.
"""

import gzip
import json
import logging
import shutil
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import ijson
from sqlalchemy import delete, insert
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.importers.spellbook_api import download_variants_export
from src.data.models.combo import (
    ComboSnapshotMetaModel,
    ComboVariantModel,
    ComboVariantPieceModel,
)
from src.data.schemas.combo import ComboBracketTag, ComboRecord, name_keys

logger = logging.getLogger(__name__)

#: The closed wire-letter → canonical-token bracket map (AC 2). Spellbook renamed its
#: tag vocabulary after the spine froze the six ``ComboBracketTag`` tokens; this map is
#: semantically lossless — Spellbook's own derived bracket numbers coincide exactly
#: with ``BRACKET_TAG_TO_BRACKET`` under ``C→PRECON_APPROPRIATE``, ``E→CASUAL``.
SPELLBOOK_TAG_TO_CANONICAL: Final[dict[str, ComboBracketTag]] = {
    "R": "RUTHLESS",
    "S": "SPICY",
    "P": "POWERFUL",
    "O": "ODDBALL",
    "C": "PRECON_APPROPRIATE",
    "E": "CASUAL",
}

#: Banned variants have no canonical token (Spellbook brackets them ``null``) — they
#: are skipped and counted, never imported: a banned combo must not set a Bracket
#: floor; deck-legality problems are the legality checker's job.
_BANNED_TAG: Final = "B"


class SpellbookImportError(Exception):
    """Raised when the Spellbook snapshot import fails."""


@dataclass(frozen=True, slots=True)
class VariantSkip:
    """Identity and reason for a wire variant the normalizer skipped (counted, not
    imported).

    Attributes:
        spellbook_id: The skipped variant's id (``"unknown"`` when absent).
        reason: One of ``"status"`` (non-OK), ``"requires_template"`` (generic
            template requirement the name matcher cannot verify), or ``"banned_tag"``.
    """

    spellbook_id: str
    reason: str


@dataclass
class SpellbookImportStats:
    """Outcome of one snapshot import run (mirrors the ``ImportStatistics`` shape).

    Attributes:
        total_variants: Variants present in the export.
        imported: Variants normalized and written to ``combo_variants``.
        skipped_status: Variants skipped for a non-``"OK"`` status.
        skipped_requires: Variants skipped for a non-empty ``requires[]`` template.
        skipped_banned: Variants skipped for the banned (``B``) bracket tag.
        piece_rows: Rows written to ``combo_variant_pieces``.
        export_timestamp: The bulk file's top-level ``timestamp`` (data vintage).
        export_version: The bulk file's top-level ``version`` (backend release).
        elapsed_seconds: Wall-clock duration of the whole import.
    """

    total_variants: int = 0
    imported: int = 0
    skipped_status: int = 0
    skipped_requires: int = 0
    skipped_banned: int = 0
    piece_rows: int = 0
    export_timestamp: str = ""
    export_version: str = ""
    elapsed_seconds: float = field(default=0.0)


def transform_spellbook_variant(
    variant: dict[str, Any],
    skips: list[VariantSkip] | None = None,
) -> ComboRecord | None:
    """Normalize one wire variant into a validated ``ComboRecord``, or skip it.

    Pydantic construction IS the validation: an empty piece list or a bad normalized
    tag raises ``ValidationError`` and aborts the import — never catch-and-continue.
    ``commander_required`` derives from ``any(uses[].mustBeCommander)`` — the
    authoritative flag; ``zoneLocations`` is neither necessary nor sufficient (backend
    data has ``mustBeCommander: true`` with zone ``["B"]`` and zone ``["C","H"]`` with
    ``mustBeCommander: false``).

    Args:
        variant: One wire variant dict from the bulk export.
        skips: Optional collector; gains one :class:`VariantSkip` per skipped variant
            (the ``TransformReject`` precedent).

    Returns:
        The normalized record (``bucket=None``), or ``None`` for the three counted
        skip cases: non-OK status, non-empty ``requires``, banned bracket tag.

    Raises:
        SpellbookImportError: On a bracket tag outside the seven known letters.
        pydantic.ValidationError: On a malformed variant (e.g. no pieces).
    """
    variant_id = str(variant.get("id") or "unknown")

    def _skip(reason: str) -> None:
        if skips is not None:
            skips.append(VariantSkip(spellbook_id=variant_id, reason=reason))

    if variant.get("status") != "OK":
        _skip("status")
        return None

    if variant.get("requires"):
        # The name-based matcher cannot verify a generic template piece ("a sac
        # outlet"); importing these would let match_combos report false `included`s.
        _skip("requires_template")
        return None

    wire_tag = variant.get("bracketTag")
    if wire_tag == _BANNED_TAG:
        _skip("banned_tag")
        return None
    if wire_tag not in SPELLBOOK_TAG_TO_CANONICAL:
        raise SpellbookImportError(
            f"Unknown bracketTag {wire_tag!r} on variant {variant_id!r} — the closed "
            "letter map has no entry for it; aborting (no fuzzy fallback)"
        )

    cards: list[str] = []
    for use in variant.get("uses", []):
        # ijson parses numbers as Decimal; coerce before list repetition.
        quantity = int(use.get("quantity") or 1)
        cards.extend([use["card"]["name"]] * quantity)

    popularity = variant.get("popularity")

    return ComboRecord(
        spellbook_id=variant_id,
        cards=tuple(cards),
        commander_required=any(bool(use.get("mustBeCommander")) for use in variant.get("uses", [])),
        bracket_tag=SPELLBOOK_TAG_TO_CANONICAL[wire_tag],
        produces=tuple(entry["feature"]["name"] for entry in variant.get("produces", [])),
        popularity=int(popularity) if popularity is not None else None,
    )


def _read_export_header(file_path: Path) -> tuple[str, str]:
    """Read the export's top-level ``timestamp`` and ``version`` scalars.

    Both precede the ``variants`` array in the file (verified live), so this pass
    terminates after decompressing only the first few bytes.

    Args:
        file_path: Path to the downloaded ``variants.json.gz``.

    Returns:
        The export ``(timestamp, version)`` pair.

    Raises:
        SpellbookImportError: If either scalar or the ``variants`` array is missing —
            a broken or truncated file.
    """
    timestamp: str | None = None
    version: str | None = None
    with gzip.open(file_path, "rb") as fh:
        for prefix, event, value in ijson.parse(fh):
            if prefix == "timestamp":
                timestamp = str(value)
            elif prefix == "version":
                version = str(value)
            elif prefix == "variants" and event == "start_array":
                if timestamp is None or version is None:
                    raise SpellbookImportError(
                        "Export is missing the top-level 'timestamp'/'version' "
                        "header — broken or truncated file"
                    )
                return timestamp, version
    raise SpellbookImportError("Export has no 'variants' array — broken or truncated file")


def _stream_variants(file_path: Path) -> Iterator[dict[str, Any]]:
    """Stream each wire variant dict from the gzipped export.

    ijson over the decompressing stream with prefix ``variants.item`` (the
    ``parser.stream_cards`` precedent) — the raw JSON is ~579 MB and must never be
    loaded whole. The trailing top-level ``aliases`` array is naturally ignored by
    the prefix filter.

    Args:
        file_path: Path to the downloaded ``variants.json.gz``.

    Yields:
        One wire variant dict per export entry.
    """
    with gzip.open(file_path, "rb") as fh:
        yield from ijson.items(fh, "variants.item")


async def import_spellbook_snapshot(
    session: AsyncSession,
    *,
    temp_dir: Path | None = None,
) -> SpellbookImportStats:
    """Download, normalize, and atomically replace the local combo snapshot.

    Orchestrates: download (a failure here never reaches the DB) → normalize ALL
    variants into memory (~100k small records — fail fast while the DB is untouched)
    → guard against zero eligible variants (a healthy export has tens of thousands;
    zero means a broken file) → ONE transaction: delete previous piece + variant rows,
    batch-insert the new rows, upsert the metadata row, commit. Rollback on any
    database error leaves the previous snapshot intact.

    Args:
        session: AsyncSession for database operations.
        temp_dir: Directory for the downloaded file. A fresh private per-run
            directory (removed afterwards) when ``None``.

    Returns:
        A :class:`SpellbookImportStats` with totals, per-reason skip counts, piece-row
        count, and the export's version metadata.

    Raises:
        SpellbookImportError: On an unknown bracket tag, a missing/broken export
            header, or zero eligible variants.
        SpellbookAPIError: If the download fails.
        IntegrityError | DatabaseError: Re-raised after rollback on write failure
            (e.g. a duplicate ``spellbook_id`` in a corrupt export).
    """
    start = time.monotonic()
    stats = SpellbookImportStats()

    created_dir: Path | None = None
    if temp_dir is None:
        created_dir = Path(tempfile.mkdtemp(prefix="spellbook-import-"))
        temp_dir = created_dir

    try:
        downloaded = await download_variants_export(temp_dir / "variants.json.gz")

        logger.info("Normalizing variants (streaming parse)...")
        skips: list[VariantSkip] = []
        records: list[ComboRecord] = []
        export_timestamp, export_version = _read_export_header(downloaded)
        for wire_variant in _stream_variants(downloaded):
            stats.total_variants += 1
            record = transform_spellbook_variant(wire_variant, skips)
            if record is not None:
                records.append(record)
            if stats.total_variants % 20_000 == 0:
                logger.info("Normalized %d variants...", stats.total_variants)

        for skip in skips:
            if skip.reason == "status":
                stats.skipped_status += 1
            elif skip.reason == "requires_template":
                stats.skipped_requires += 1
            elif skip.reason == "banned_tag":
                stats.skipped_banned += 1

        if not records:
            raise SpellbookImportError(
                f"Zero eligible variants after normalizing {stats.total_variants} — "
                "a healthy export has tens of thousands; refusing to replace the "
                "existing snapshot with an empty one"
            )

        # The *_list setters can't serve an executemany batch, so the JSON encoding
        # happens here — same json.dumps contract as the paired properties.
        variant_rows = [
            {
                "spellbook_id": record.spellbook_id,
                "cards": json.dumps(list(record.cards)),
                "commander_required": record.commander_required,
                "bracket_tag": record.bracket_tag,
                "produces": json.dumps(list(record.produces)),
                "popularity": record.popularity,
            }
            for record in records
        ]
        piece_rows = [
            {"spellbook_id": record.spellbook_id, "name_key": key}
            for record in records
            # Dedup'd set per variant: a quantity-2 piece or a DFC key collision must
            # not produce duplicate PK rows. Sorted for deterministic insert order.
            for key in sorted({k for name in record.cards for k in name_keys(name)})
        ]
        imported_at = datetime.now(UTC).isoformat()

        logger.info(
            "Replacing snapshot: %d variants, %d piece rows (one transaction)...",
            len(variant_rows),
            len(piece_rows),
        )
        try:
            await session.execute(delete(ComboVariantPieceModel))
            await session.execute(delete(ComboVariantModel))
            await session.execute(insert(ComboVariantModel), variant_rows)
            await session.execute(insert(ComboVariantPieceModel), piece_rows)
            await session.execute(delete(ComboSnapshotMetaModel))
            await session.execute(
                insert(ComboSnapshotMetaModel).values(
                    id=1,
                    imported_at=imported_at,
                    export_timestamp=export_timestamp,
                    export_version=export_version,
                    variant_count=len(variant_rows),
                )
            )
            await session.commit()
        except (IntegrityError, DatabaseError):
            await session.rollback()
            raise

        stats.imported = len(variant_rows)
        stats.piece_rows = len(piece_rows)
        stats.export_timestamp = export_timestamp
        stats.export_version = export_version
        stats.elapsed_seconds = time.monotonic() - start
        logger.info(
            "Snapshot import complete: %d/%d variants imported "
            "(%d status, %d requires-template, %d banned-tag skips), %d piece rows",
            stats.imported,
            stats.total_variants,
            stats.skipped_status,
            stats.skipped_requires,
            stats.skipped_banned,
            stats.piece_rows,
        )
        return stats

    finally:
        if created_dir is not None:
            shutil.rmtree(created_dir, ignore_errors=True)

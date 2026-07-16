"""End-to-end integration tests for the Spellbook combo-snapshot import (Story 6.2).

The ``test_scryfall_import_e2e.py`` pattern: a tmp-path database plus a monkeypatched
``download_variants_export`` that drops a locally gzipped fixture payload — no live
network. Proves the full pipeline: fresh import populates all three tables (including
DFC piece keys), a re-run replaces idempotently, and a poisoned or empty second payload
aborts leaving the FIRST snapshot fully intact (single-transaction atomicity).
"""

import gzip
import json
from typing import Any

import pytest
from sqlalchemy import select

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers import spellbook
from src.data.importers.spellbook import SpellbookImportError, import_spellbook_snapshot
from src.data.models.combo import (
    ComboSnapshotMetaModel,
    ComboVariantModel,
    ComboVariantPieceModel,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_cards.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_engine(database_url)
    await init_database(engine)

    session_factory = create_session_factory(engine)

    yield session_factory

    await engine.dispose()


def make_wire_variant(
    variant_id: str,
    card_names: list[str],
    *,
    bracket_tag: str = "P",
    status: str = "OK",
    must_be_commander: bool = False,
    requires: list[dict[str, Any]] | None = None,
    popularity: int | None = 10,
) -> dict[str, Any]:
    return {
        "id": variant_id,
        "status": status,
        "uses": [
            {
                "card": {"name": name},
                "quantity": 1,
                "mustBeCommander": must_be_commander,
                "zoneLocations": ["H"],
            }
            for name in card_names
        ],
        "requires": requires or [],
        "produces": [{"feature": {"name": "Infinite mana"}, "quantity": 1}],
        "popularity": popularity,
        "bracketTag": bracket_tag,
    }


def gzipped_payload(
    variants: list[dict[str, Any]],
    *,
    timestamp: str = "2026-07-16T07:00:00+00:00",
    version: str = "5.6.0",
) -> bytes:
    doc = {
        "timestamp": timestamp,
        "version": version,
        "variants": variants,
        "aliases": [],
    }
    return gzip.compress(json.dumps(doc).encode("utf-8"))


def patch_download(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    """Monkeypatch the downloader to drop *payload* at the requested output path."""

    async def fake_download(output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(payload)
        return output_path

    monkeypatch.setattr(spellbook, "download_variants_export", fake_download)


FIRST_VARIANTS = [
    make_wire_variant("1-2", ["Basalt Monolith", "Rings of Brighthearth"]),
    make_wire_variant("3-4", ["Alive // Well", "Sanguine Bond"], bracket_tag="S"),
    make_wire_variant("5-6", ["Heliod, Sun-Crowned", "Walking Ballista"], bracket_tag="R"),
]


async def _snapshot_state(session) -> tuple[set[str], set[tuple[str, str]], Any]:
    variant_ids = set((await session.execute(select(ComboVariantModel.spellbook_id))).scalars())
    pieces = set(
        (
            await session.execute(
                select(ComboVariantPieceModel.spellbook_id, ComboVariantPieceModel.name_key)
            )
        ).all()
    )
    meta = (await session.execute(select(ComboSnapshotMetaModel))).scalar_one_or_none()
    return variant_ids, pieces, meta


async def test_fresh_import_populates_all_three_tables(test_db, monkeypatch):
    patch_download(monkeypatch, gzipped_payload(FIRST_VARIANTS))

    async with test_db() as session:
        stats = await import_spellbook_snapshot(session)

        assert stats.total_variants == 3
        assert stats.imported == 3
        assert stats.export_timestamp == "2026-07-16T07:00:00+00:00"
        assert stats.export_version == "5.6.0"

        variant_ids, pieces, meta = await _snapshot_state(session)
        assert variant_ids == {"1-2", "3-4", "5-6"}

        # DFC piece: "Alive // Well" yields BOTH key rows.
        assert ("3-4", "alive // well") in pieces
        assert ("3-4", "alive") in pieces
        assert ("1-2", "basalt monolith") in pieces
        assert stats.piece_rows == len(pieces) == 7  # 2 + 3 + 2

        assert meta is not None
        assert meta.export_timestamp == "2026-07-16T07:00:00+00:00"
        assert meta.export_version == "5.6.0"
        assert meta.imported_at  # non-null import-time stamp
        assert meta.variant_count == 3

        # Stored variant rows are ComboRecord-shaped (sorted names, canonical tag).
        variant = (
            await session.execute(
                select(ComboVariantModel).where(ComboVariantModel.spellbook_id == "1-2")
            )
        ).scalar_one()
        assert variant.cards_list == ["Basalt Monolith", "Rings of Brighthearth"]
        assert variant.bracket_tag == "POWERFUL"
        assert variant.produces_list == ["Infinite mana"]
        assert variant.popularity == 10


async def test_rerun_replaces_snapshot_idempotently(test_db, monkeypatch):
    async with test_db() as session:
        patch_download(monkeypatch, gzipped_payload(FIRST_VARIANTS))
        await import_spellbook_snapshot(session)

        second = [
            make_wire_variant("7-8", ["Thassa's Oracle", "Demonic Consultation"], bracket_tag="R")
        ]
        patch_download(
            monkeypatch,
            gzipped_payload(second, timestamp="2026-07-17T09:00:00+00:00", version="5.7.0"),
        )
        stats = await import_spellbook_snapshot(session)

        assert stats.imported == 1
        variant_ids, pieces, meta = await _snapshot_state(session)
        assert variant_ids == {"7-8"}, "old snapshot rows must be gone"
        assert {p[0] for p in pieces} == {"7-8"}
        assert meta is not None
        assert meta.export_timestamp == "2026-07-17T09:00:00+00:00"
        assert meta.export_version == "5.7.0"
        assert meta.variant_count == 1


async def test_poisoned_second_payload_leaves_first_snapshot_intact(test_db, monkeypatch):
    async with test_db() as session:
        patch_download(monkeypatch, gzipped_payload(FIRST_VARIANTS))
        first_stats = await import_spellbook_snapshot(session)
        assert first_stats.imported == 3

        poisoned = FIRST_VARIANTS + [
            make_wire_variant("9-9", ["Some Card"], bracket_tag="X")  # unknown tag
        ]
        patch_download(monkeypatch, gzipped_payload(poisoned, version="5.7.0"))

        with pytest.raises(SpellbookImportError, match="9-9"):
            await import_spellbook_snapshot(session)

    async with test_db() as session:
        variant_ids, pieces, meta = await _snapshot_state(session)
        assert variant_ids == {"1-2", "3-4", "5-6"}, "first snapshot must survive"
        assert len(pieces) == 7
        assert meta is not None
        assert meta.export_version == "5.6.0", "meta must still describe the first import"


async def test_zero_eligible_variants_aborts_and_preserves_snapshot(test_db, monkeypatch):
    async with test_db() as session:
        patch_download(monkeypatch, gzipped_payload(FIRST_VARIANTS))
        await import_spellbook_snapshot(session)

        # All-banned payload: parses fine, zero eligible after skips.
        all_banned = [make_wire_variant("8-8", ["Card A", "Card B"], bracket_tag="B")]
        patch_download(monkeypatch, gzipped_payload(all_banned, version="5.7.0"))

        with pytest.raises(SpellbookImportError, match="[Zz]ero eligible"):
            await import_spellbook_snapshot(session)

    async with test_db() as session:
        variant_ids, _, meta = await _snapshot_state(session)
        assert variant_ids == {"1-2", "3-4", "5-6"}
        assert meta is not None
        assert meta.export_version == "5.6.0"


async def test_skip_counters_reported(test_db, monkeypatch):
    variants = FIRST_VARIANTS + [
        make_wire_variant("10-1", ["Card A"], status="E"),
        make_wire_variant("10-2", ["Card B"], bracket_tag="B"),
        make_wire_variant(
            "10-3",
            ["Card C"],
            requires=[{"template": {"name": "A sac outlet"}, "quantity": 1}],
        ),
    ]
    patch_download(monkeypatch, gzipped_payload(variants))

    async with test_db() as session:
        stats = await import_spellbook_snapshot(session)

        assert stats.total_variants == 6
        assert stats.imported == 3
        assert stats.skipped_status == 1
        assert stats.skipped_banned == 1
        assert stats.skipped_requires == 1

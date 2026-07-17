"""Shared combo-snapshot seeding helpers for assessment tests.

Consolidates the ``_snapshot_variant`` / ``_seed_snapshot`` helpers that
previously lived in ``tests/integration/mcp_server/test_assess_deck_power_tool.py``
(Story 7.4 decide-once #1, following the ``FakeEmbedder`` consolidation
precedent in :mod:`tests.fixtures.embedder`). Story 7.4's e2e suite and Story
7.5's ``compare_deck_power`` tests seed the same snapshot shape — one
:class:`~src.data.models.combo.ComboSnapshotMetaModel` row plus variant rows
with their piece-index rows — so the seeding pattern lives here once.

Commit semantics: :func:`seed_snapshot` commits the session, so file-backed
(WAL) databases make the snapshot visible to the tool's own sessions opened
from the same factory.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.combo import (
    ComboSnapshotMetaModel,
    ComboVariantModel,
    ComboVariantPieceModel,
)
from src.data.schemas.combo import name_keys


def snapshot_variant(
    spellbook_id: str,
    cards: list[str],
    *,
    commander_required: bool = False,
    bracket_tag: str = "POWERFUL",
) -> tuple[ComboVariantModel, list[ComboVariantPieceModel]]:
    """One variant row + its piece-index rows (the 6.3 test-suite seeding pattern)."""
    variant = ComboVariantModel(
        spellbook_id=spellbook_id,
        commander_required=commander_required,
        bracket_tag=bracket_tag,
        popularity=None,
    )
    variant.cards_list = cards
    variant.produces_list = ["Infinite value"]
    keys = {key for name in cards for key in name_keys(name)}
    pieces = [
        ComboVariantPieceModel(spellbook_id=spellbook_id, name_key=key) for key in sorted(keys)
    ]
    return variant, pieces


async def seed_snapshot(
    session: AsyncSession,
    variants: list[tuple[ComboVariantModel, list[ComboVariantPieceModel]]],
) -> None:
    """Seed the meta row + the supplied variants — a healthy, available snapshot."""
    session.add(
        ComboSnapshotMetaModel(
            imported_at="2026-07-16T09:07:00+00:00",
            export_timestamp="2026-07-16T07:28:23+00:00",
            export_version="5.6.0",
            variant_count=len(variants),
        )
    )
    for variant, pieces in variants:
        session.add(variant)
        session.add_all(pieces)
    await session.commit()

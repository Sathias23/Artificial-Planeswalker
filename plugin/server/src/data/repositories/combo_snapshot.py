"""Read-only repository over the local Commander Spellbook combo snapshot (Story 6.3).

The read side of AD-5: the three snapshot tables are written ONLY by
``scripts/import_spellbook_combos.py`` — this module exposes no write/commit path.
Like ``card_vec``, the snapshot is a build prerequisite, never committed: a fresh
checkout has empty tables, and every method here reads missing-or-empty tables as
absent (``False`` / ``None`` / ``()``) rather than raising — the probe the edge maps
to ``combo_data_unavailable`` (AD-6, Story 7.2).

No matching and no degradation decisions happen here: bucket assignment, shortfall
math, and commander gating belong to :func:`src.logic.assessment.combos.match_combos`
(AD-9), and confidence tokens belong to the edge. This repository reports facts;
callers decide.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from src.data.models.combo import (
    ComboSnapshotMetaModel,
    ComboVariantModel,
    ComboVariantPieceModel,
)
from src.data.repositories.base import BaseRepository
from src.data.schemas.combo import ComboRecord, ComboSnapshotMeta, name_keys


class ComboSnapshotRepository(BaseRepository):
    """Read access to the local combo snapshot and its vintage (AD-5).

    Read-only by contract: no ``add``/``update``/``delete`` methods and no
    ``session.commit()`` anywhere in this module. Every public method returns Pydantic
    schemas or plain values — never ORM models — and tolerates the snapshot tables
    being absent entirely (a pre-6.2 ``cards.db``), mirroring
    :func:`src.data.database.is_database_initialized`'s no-raise contract.
    """

    async def snapshot_is_available(self) -> bool:
        """Return whether a usable combo snapshot exists.

        ``True`` iff the ``combo_snapshot_meta`` row exists AND ``combo_variants``
        holds at least one row — cheap EXISTS-style scalar probes, no row
        materialization. This is the edge's ``combo_data_unavailable`` probe (AD-6).

        Returns:
            ``True`` when both the metadata row and at least one variant are present;
            ``False`` when either is missing or the tables do not exist at all.
        """
        try:
            meta_row = await self.session.execute(select(ComboSnapshotMetaModel.id).limit(1))
            if meta_row.first() is None:
                return False
            variant_row = await self.session.execute(
                select(ComboVariantModel.spellbook_id).limit(1)
            )
            return variant_row.first() is not None
        except OperationalError:
            return False

    async def get_metadata(self) -> ComboSnapshotMeta | None:
        """Return the single snapshot-metadata row — the ``data_vintage`` source.

        Returns:
            The :class:`ComboSnapshotMeta` row (``imported_at``, ``export_timestamp``,
            ``export_version``, ``variant_count``), or ``None`` when the row or the
            table itself is absent (AD-5/AD-7).
        """
        try:
            result = await self.session.execute(select(ComboSnapshotMetaModel))
        except OperationalError:
            return None
        meta_model = result.scalar_one_or_none()
        if meta_model is None:
            return None
        return ComboSnapshotMeta.model_validate(meta_model)

    async def get_variants_for_names(self, names: Sequence[str]) -> tuple[ComboRecord, ...]:
        """Return the variants relevant to the supplied deck-card names.

        Expands ``names`` through the shared :func:`name_keys` normalization (the one
        DFC-safe policy the importer also used to build the piece index) and returns
        every variant with **at least one** piece key in that set, ordered ascending by
        ``spellbook_id`` (deterministic for identical input). Records carry
        ``bucket=None`` — only the core matcher assigns buckets (AD-11).

        Decide-once consequences of the ≥1-overlap filter (epic-blessed):

        - Over-fetch is fine — the pure matcher is the exactness authority (shortfall
          ≥ 2 variants are excluded there, AD-9).
        - Zero-overlap variants never surface — a 1-piece variant whose piece is
          absent from the deck cannot appear as ``almost_included``. Accepted bound.

        Args:
            names: Deck-card names as stored on ``Card.name`` (mainboard/sideboard
                filtering is the caller's policy, not applied here). An empty input
                returns ``()`` without touching the database.

        Returns:
            Matching :class:`ComboRecord` tuples with ``bucket=None``; ``()`` when
            nothing overlaps or the snapshot tables do not exist.

        Raises:
            pydantic.ValidationError: When a stored row is corrupt (e.g. a
                ``bracket_tag`` outside the closed six-token enum) — loud by design,
                the second line of defense behind 6.2's import normalization (AD-11).
        """
        if not names:
            return ()
        keys = sorted({key for name in names for key in name_keys(name)})
        piece_subquery = (
            select(ComboVariantPieceModel.spellbook_id)
            .distinct()
            .where(ComboVariantPieceModel.name_key.in_(keys))
        )
        statement = (
            select(ComboVariantModel)
            .where(ComboVariantModel.spellbook_id.in_(piece_subquery))
            .order_by(ComboVariantModel.spellbook_id)
        )
        try:
            result = await self.session.execute(statement)
        except OperationalError:
            return ()
        return tuple(
            ComboRecord.model_validate(
                {
                    "spellbook_id": row.spellbook_id,
                    "cards": tuple(row.cards_list),
                    "commander_required": row.commander_required,
                    "bracket_tag": row.bracket_tag,
                    "produces": tuple(row.produces_list),
                    "popularity": row.popularity,
                }
            )
            for row in result.scalars()
        )

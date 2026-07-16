"""SQLAlchemy ORM models for the local Commander Spellbook combo snapshot (Story 6.2).

All three tables are written ONLY by ``scripts/import_spellbook_combos.py`` and are
read-only everywhere else (AD-5). Rows are canonical ``ComboRecord``-shaped data, not
raw wire JSON (AD-11): ``bucket`` and the derived ``type`` /
``earliest_turn_estimate`` values are deliberately never stored — the pure core
computes them per assessment, so re-tuning heuristics never forces a re-import.

Like ``card_vec``, the snapshot is a build prerequisite, never committed: a fresh
checkout has empty tables and Story 6.3's repository treats empty as absent
(``combo_data_unavailable``).
"""

import json

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.base import Base


class ComboVariantModel(Base):
    """One imported Spellbook combo variant, mirroring ``ComboRecord``'s stored fields.

    ``cards`` and ``produces`` are JSON-in-Text columns — always read/write through
    the paired ``cards_list`` / ``produces_list`` property+setter (the
    ``DeckModel.tags`` pattern); never assign raw JSON strings from outside.
    """

    __tablename__ = "combo_variants"

    spellbook_id: Mapped[str] = mapped_column(String, primary_key=True, init=True)

    # Piece names, multiplicity-inclusive (JSON array of strings).
    cards: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, init=False)
    commander_required: Mapped[bool] = mapped_column(Boolean, nullable=False, init=True)
    bracket_tag: Mapped[str] = mapped_column(String, nullable=False, init=True)
    # Produced results, e.g. "Infinite mana" (JSON array of strings).
    produces: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, init=False)
    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None, init=True)

    @property
    def cards_list(self) -> list[str]:
        """Parse the ``cards`` JSON field into a Python list."""
        if not self.cards:
            return []
        try:
            parsed = json.loads(self.cards)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @cards_list.setter
    def cards_list(self, names: list[str] | None) -> None:
        """Set the ``cards`` field from a Python list."""
        if names is None or not names:
            self.cards = None
        else:
            self.cards = json.dumps(names)

    @property
    def produces_list(self) -> list[str]:
        """Parse the ``produces`` JSON field into a Python list."""
        if not self.produces:
            return []
        try:
            parsed = json.loads(self.produces)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @produces_list.setter
    def produces_list(self, names: list[str] | None) -> None:
        """Set the ``produces`` field from a Python list."""
        if names is None or not names:
            self.produces = None
        else:
            self.produces = json.dumps(names)

    def __repr__(self) -> str:
        """String representation of the combo variant."""
        return (
            f"<ComboVariantModel(spellbook_id='{self.spellbook_id}', "
            f"bracket_tag='{self.bracket_tag}')>"
        )


class ComboVariantPieceModel(Base):
    """Piece-name lookup index row for Story 6.3's relevance filter.

    One row per (``spellbook_id``, ``name_key``), where the keys come from the shared
    :func:`src.data.schemas.combo.name_keys` normalization — a DFC piece name
    ``"A // B"`` yields two rows. No FK to ``combo_variants``: both tables are written
    and deleted together in one transaction.
    """

    __tablename__ = "combo_variant_pieces"
    __table_args__ = (Index("ix_combo_variant_pieces_name_key", "name_key"),)

    spellbook_id: Mapped[str] = mapped_column(String, primary_key=True, init=True)
    name_key: Mapped[str] = mapped_column(String, primary_key=True, init=True)

    def __repr__(self) -> str:
        """String representation of the piece index row."""
        return (
            f"<ComboVariantPieceModel(spellbook_id='{self.spellbook_id}', "
            f"name_key='{self.name_key}')>"
        )


class ComboSnapshotMetaModel(Base):
    """The single snapshot-metadata row (``id`` pinned to 1, ``import_state`` precedent).

    Carries ``imported_at`` (import-time UTC, ISO-8601), the bulk file's top-level
    ``timestamp`` / ``version`` (the ``data_vintage`` source, AD-5/AD-7), and the
    imported ``variant_count``.
    """

    __tablename__ = "combo_snapshot_meta"
    __table_args__ = (CheckConstraint("id = 1", name="combo_snapshot_meta_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1, init=False)
    imported_at: Mapped[str] = mapped_column(String, nullable=False, init=True)
    export_timestamp: Mapped[str] = mapped_column(String, nullable=False, init=True)
    export_version: Mapped[str] = mapped_column(String, nullable=False, init=True)
    variant_count: Mapped[int] = mapped_column(Integer, nullable=False, init=True)

    def __repr__(self) -> str:
        """String representation of the snapshot metadata row."""
        return (
            f"<ComboSnapshotMetaModel(imported_at='{self.imported_at}', "
            f"export_version='{self.export_version}', variant_count={self.variant_count})>"
        )

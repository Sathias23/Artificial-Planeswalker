"""Unit tests for the combo-snapshot ORM models (Story 6.2, AC 3).

Pins the schema shape the import script writes and Story 6.3's repository will read:
JSON-in-Text list round-trips, composite piece PK, the single-row meta constraint, and
registration in ``Base.metadata`` (the side-effect import rule — an unregistered model
is silently skipped by ``create_all``).
"""

from src.data.models.base import Base
from src.data.models.combo import (
    ComboSnapshotMetaModel,
    ComboVariantModel,
    ComboVariantPieceModel,
)


class TestMetadataRegistration:
    """All three tables must be registered with Base.metadata via src.data.database."""

    def test_tables_registered_in_metadata(self):
        # Importing src.data.database must have registered every model.
        import src.data.database  # noqa: F401

        for table in ("combo_variants", "combo_variant_pieces", "combo_snapshot_meta"):
            assert table in Base.metadata.tables, f"{table} missing from Base.metadata"


class TestComboVariantModel:
    def test_json_list_round_trip(self):
        variant = ComboVariantModel(
            spellbook_id="1-2-3",
            commander_required=False,
            bracket_tag="CASUAL",
            popularity=None,
        )
        variant.cards_list = ["Basalt Monolith", "Rings of Brighthearth"]
        variant.produces_list = ["Infinite colorless mana"]

        assert variant.cards_list == ["Basalt Monolith", "Rings of Brighthearth"]
        assert variant.produces_list == ["Infinite colorless mana"]
        # The base columns hold JSON strings, not raw lists.
        assert isinstance(variant.cards, str)
        assert isinstance(variant.produces, str)

    def test_empty_list_reads_back_as_empty(self):
        variant = ComboVariantModel(
            spellbook_id="1-2-3",
            commander_required=True,
            bracket_tag="RUTHLESS",
            popularity=42,
        )
        assert variant.cards_list == []
        assert variant.produces_list == []

    def test_spellbook_id_is_primary_key(self):
        pk_cols = [c.name for c in ComboVariantModel.__table__.primary_key.columns]
        assert pk_cols == ["spellbook_id"]

    def test_bucket_is_never_stored(self):
        # AD-11: bucket is matcher-assigned; derived fields never persisted.
        columns = {c.name for c in ComboVariantModel.__table__.columns}
        assert "bucket" not in columns
        assert "type" not in columns
        assert "earliest_turn_estimate" not in columns


class TestComboVariantPieceModel:
    def test_composite_primary_key(self):
        pk_cols = {c.name for c in ComboVariantPieceModel.__table__.primary_key.columns}
        assert pk_cols == {"spellbook_id", "name_key"}

    def test_name_key_is_indexed(self):
        indexed = {
            col.name for index in ComboVariantPieceModel.__table__.indexes for col in index.columns
        }
        assert "name_key" in indexed


class TestComboSnapshotMetaModel:
    def test_single_row_check_constraint(self):
        from sqlalchemy import CheckConstraint

        checks = [
            c
            for c in ComboSnapshotMetaModel.__table__.constraints
            if isinstance(c, CheckConstraint)
        ]
        assert any("id = 1" in str(c.sqltext) for c in checks)

    def test_constructs_with_metadata_fields(self):
        meta = ComboSnapshotMetaModel(
            imported_at="2026-07-16T00:00:00+00:00",
            export_timestamp="2026-07-16T07:28:23.230742+00:00",
            export_version="5.6.0",
            variant_count=98_000,
        )
        assert meta.id == 1
        assert meta.export_version == "5.6.0"
        assert meta.variant_count == 98_000

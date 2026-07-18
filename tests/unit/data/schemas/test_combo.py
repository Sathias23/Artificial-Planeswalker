"""Unit tests for the combo schema module's shared name-key normalization (Story 6.2)
and the snapshot-metadata schema (Story 6.3).

``name_keys`` relocated here from ``src.logic.assessment.combos._name_keys`` (epic-5
retro action item 9) so the data-layer importer and the pure matcher share ONE
normalization — the DFC front-face hazard that bit stories 5.3, 5.6, and 5.9.
"""

import pytest
from pydantic import ValidationError

from src.data.models.combo import ComboSnapshotMetaModel
from src.data.schemas.combo import ComboSnapshotMeta, name_keys


class TestNameKeys:
    """Pin the decide-once name normalization policy at its new schema-layer home."""

    def test_plain_name_yields_one_lowercased_key(self):
        assert name_keys("Basalt Monolith") == ("basalt monolith",)

    def test_multi_face_name_yields_full_name_and_front_face(self):
        assert name_keys("Alive // Well") == ("alive // well", "alive")

    def test_already_lowercase_name_passes_through(self):
        assert name_keys("sol ring") == ("sol ring",)

    def test_front_face_key_is_lowercased(self):
        keys = name_keys("Wear // Tear")
        assert keys == ("wear // tear", "wear")


class TestComboSnapshotMeta:
    """Pin the frozen ``data_vintage`` source schema (Story 6.3, AD-5/AD-7)."""

    def test_frozen_assignment_raises(self):
        meta = ComboSnapshotMeta(
            imported_at="2026-07-16T09:07:00+00:00",
            export_timestamp="2026-07-16T07:28:23+00:00",
            export_version="5.6.0",
            variant_count=94962,
        )
        with pytest.raises(ValidationError):
            meta.export_version = "9.9.9"

    def test_model_validate_from_orm_model_round_trips_all_fields(self):
        model = ComboSnapshotMetaModel(
            imported_at="2026-07-16T09:07:00+00:00",
            export_timestamp="2026-07-16T07:28:23+00:00",
            export_version="5.6.0",
            variant_count=94962,
        )
        meta = ComboSnapshotMeta.model_validate(model)
        assert meta.imported_at == "2026-07-16T09:07:00+00:00"
        assert meta.export_timestamp == "2026-07-16T07:28:23+00:00"
        assert meta.export_version == "5.6.0"
        assert meta.variant_count == 94962

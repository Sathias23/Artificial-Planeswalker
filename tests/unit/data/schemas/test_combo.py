"""Unit tests for the combo schema module's shared name-key normalization (Story 6.2).

``name_keys`` relocated here from ``src.logic.assessment.combos._name_keys`` (epic-5
retro action item 9) so the data-layer importer and the pure matcher share ONE
normalization — the DFC front-face hazard that bit stories 5.3, 5.6, and 5.9.
"""

from src.data.schemas.combo import name_keys


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

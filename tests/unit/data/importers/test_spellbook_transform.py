"""Unit tests for the Spellbook wire → ComboRecord normalizer (Story 6.2, AC 2/9).

Pins the field mapping, the closed letter→token bracket map (totality over the seven
known letters), and the skip-vs-error policy: non-OK status / non-empty ``requires`` /
banned tag are skipped AND counted; any unknown tag is a loud abort naming the variant.
"""

from typing import Any

import pytest

from src.data.importers.spellbook import (
    SPELLBOOK_TAG_TO_CANONICAL,
    SpellbookImportError,
    VariantSkip,
    transform_spellbook_variant,
)


def make_wire_variant(**overrides: Any) -> dict[str, Any]:
    """A representative wire variant covering exactly the fields the story consumes."""
    variant: dict[str, Any] = {
        "id": "1000-2000",
        "status": "OK",
        "uses": [
            {
                "card": {"name": "Basalt Monolith"},
                "quantity": 1,
                "mustBeCommander": False,
                "zoneLocations": ["H"],
            },
            {
                "card": {"name": "Rings of Brighthearth"},
                "quantity": 1,
                "mustBeCommander": False,
                "zoneLocations": ["H"],
            },
        ],
        "requires": [],
        "produces": [
            {"feature": {"name": "Infinite colorless mana"}, "quantity": 1},
        ],
        "popularity": 703,
        "bracketTag": "P",
    }
    variant.update(overrides)
    return variant


class TestFieldMapping:
    def test_maps_wire_fields_to_combo_record(self):
        record = transform_spellbook_variant(make_wire_variant())

        assert record is not None
        assert record.spellbook_id == "1000-2000"
        assert record.cards == ("Basalt Monolith", "Rings of Brighthearth")
        assert record.commander_required is False
        assert record.bucket is None
        assert record.bracket_tag == "POWERFUL"
        assert record.produces == ("Infinite colorless mana",)
        assert record.popularity == 703

    def test_quantity_repeats_piece_names(self):
        variant = make_wire_variant(
            uses=[
                {
                    "card": {"name": "Relentless Rats"},
                    "quantity": 2,
                    "mustBeCommander": False,
                    "zoneLocations": ["H"],
                }
            ]
        )
        record = transform_spellbook_variant(variant)

        assert record is not None
        assert record.cards == ("Relentless Rats", "Relentless Rats")

    def test_commander_required_is_any_must_be_commander(self):
        variant = make_wire_variant()
        variant["uses"][1]["mustBeCommander"] = True

        record = transform_spellbook_variant(variant)

        assert record is not None
        assert record.commander_required is True

    def test_zone_locations_do_not_drive_commander_required(self):
        """zoneLocations=["C"] with mustBeCommander=false → False (authoritative flag)."""
        variant = make_wire_variant()
        for use in variant["uses"]:
            use["zoneLocations"] = ["C"]
            use["mustBeCommander"] = False

        record = transform_spellbook_variant(variant)

        assert record is not None
        assert record.commander_required is False

    def test_null_popularity_survives(self):
        record = transform_spellbook_variant(make_wire_variant(popularity=None))

        assert record is not None
        assert record.popularity is None


class TestBracketTagMap:
    def test_letter_map_is_exactly_the_six_canonical_pairs(self):
        assert SPELLBOOK_TAG_TO_CANONICAL == {
            "R": "RUTHLESS",
            "S": "SPICY",
            "P": "POWERFUL",
            "O": "ODDBALL",
            "C": "PRECON_APPROPRIATE",
            "E": "CASUAL",
        }

    @pytest.mark.parametrize(
        ("letter", "token"),
        [
            ("R", "RUTHLESS"),
            ("S", "SPICY"),
            ("P", "POWERFUL"),
            ("O", "ODDBALL"),
            ("C", "PRECON_APPROPRIATE"),
            ("E", "CASUAL"),
        ],
    )
    def test_each_letter_normalizes(self, letter, token):
        record = transform_spellbook_variant(make_wire_variant(bracketTag=letter))

        assert record is not None
        assert record.bracket_tag == token

    def test_banned_tag_is_skipped_and_counted(self):
        skips: list[VariantSkip] = []

        record = transform_spellbook_variant(make_wire_variant(bracketTag="B"), skips)

        assert record is None
        assert len(skips) == 1
        assert skips[0].spellbook_id == "1000-2000"
        assert skips[0].reason == "banned_tag"

    def test_unknown_tag_is_a_loud_error_naming_the_variant(self):
        with pytest.raises(SpellbookImportError, match="1000-2000") as excinfo:
            transform_spellbook_variant(make_wire_variant(bracketTag="X"))
        assert "X" in str(excinfo.value)

    def test_unknown_tag_error_beats_skip_collector(self):
        """An unknown tag aborts even when a collector is present — never a skip."""
        skips: list[VariantSkip] = []
        with pytest.raises(SpellbookImportError):
            transform_spellbook_variant(make_wire_variant(bracketTag="Z"), skips)
        assert skips == []


class TestSkipPolicy:
    def test_non_ok_status_is_skipped_and_counted(self):
        skips: list[VariantSkip] = []

        record = transform_spellbook_variant(make_wire_variant(status="E"), skips)

        assert record is None
        assert [s.reason for s in skips] == ["status"]

    def test_non_empty_requires_is_skipped_and_counted(self):
        skips: list[VariantSkip] = []
        variant = make_wire_variant(
            requires=[{"template": {"name": "A sac outlet"}, "quantity": 1}]
        )

        record = transform_spellbook_variant(variant, skips)

        assert record is None
        assert [s.reason for s in skips] == ["requires_template"]

    def test_empty_cards_is_a_hard_error(self):
        """A malformed variant with no pieces must abort, never masquerade as matched."""
        with pytest.raises(Exception):  # noqa: B017 — ValidationError or import error
            transform_spellbook_variant(make_wire_variant(uses=[]))

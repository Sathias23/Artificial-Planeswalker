"""The Arena card database reader: ids to names and rules text, degrading instead of raising."""

from pathlib import Path

import pytest

from src.arena.card_database import ArenaCardDatabase, format_mana_cost
from tests.fixtures.arena import (
    ANGEL,
    BEAR,
    BEAR_TRIGGER,
    FOREST,
    GIANT_GROWTH,
    UNKNOWN_CARD,
    build_card_database,
)


@pytest.fixture
def cards(tmp_path: Path):
    database = ArenaCardDatabase(build_card_database(tmp_path / "cards.mtga"))
    yield database
    database.close()


class TestManaCost:
    @pytest.mark.parametrize(
        ("old_school", "expected"),
        [
            ("o1oG", "{1}{G}"),
            ("oXoGoG", "{X}{G}{G}"),
            ("o10", "{10}"),
            ("o(W/U)oB", "{W/U}{B}"),
            ("", None),
            (None, None),
        ],
    )
    def test_converts_the_database_notation(self, old_school, expected):
        assert format_mana_cost(old_school) == expected


class TestLookups:
    def test_names_a_card_with_markup_stripped(self, cards):
        assert cards.card_name(BEAR) == "Grizzly Bears"

    def test_reads_cost_type_line_and_stats(self, cards):
        card = cards.card(ANGEL)

        assert card.mana_cost == "{3}{W}{W}"
        assert card.type_line == "Creature — Angel"
        assert card.power_toughness == "4/4"

    def test_a_card_without_subtype_or_stats_has_neither(self, cards):
        card = cards.card(GIANT_GROWTH)

        assert card.type_line == "Instant"
        assert card.power_toughness is None

    def test_card_text_joins_the_parts_and_names_the_card_in_its_own_text(self, cards):
        assert cards.card_text(BEAR) == (
            "{1}{G} | Creature — Bear | 2/2 | When Grizzly Bears enters, you gain 1 life."
        )

    def test_costs_inside_rules_text_are_reformatted(self, cards):
        assert cards.card_text(FOREST) == "Basic Land — Forest | {T}: Add {G}."

    def test_ability_text_substitutes_the_source_name(self, cards):
        assert cards.ability_text(BEAR_TRIGGER, "Grizzly Bears") == (
            "When Grizzly Bears enters, you gain 1 life."
        )

    def test_counter_kind_is_named(self, cards):
        assert cards.counter_name(1) == "+1/+1"

    def test_prompt_fills_its_placeholders(self, cards):
        assert cards.prompt_text(34, {"NumberOfCards": "6"}) == (
            "Would you like to mulligan to 6 card(s)?"
        )

    def test_prompt_with_an_unfilled_placeholder_is_withheld(self, cards):
        assert cards.prompt_text(34, {}) is None

    def test_internal_prompt_text_is_withheld(self, cards):
        assert cards.prompt_text(2, {}) is None

    @pytest.mark.parametrize("grp_id", [UNKNOWN_CARD, 0, None])
    def test_unknown_ids_answer_none(self, cards, grp_id):
        assert cards.card(grp_id) is None
        assert cards.card_name(grp_id) is None
        assert cards.card_text(grp_id) is None
        assert cards.ability_text(grp_id) is None
        assert cards.counter_name(grp_id) is None


class TestDegradation:
    def test_no_path_answers_none_to_everything(self):
        cards = ArenaCardDatabase(None)

        assert cards.available is False
        assert cards.card_name(BEAR) is None
        assert cards.ability_text(BEAR_TRIGGER) is None
        assert cards.counter_name(1) is None
        assert cards.prompt_text(10, {}) is None

    def test_missing_file_is_unavailable_not_an_error(self, tmp_path: Path):
        cards = ArenaCardDatabase(tmp_path / "absent.mtga")

        assert cards.available is False
        assert cards.card_name(BEAR) is None

    def test_a_file_that_is_not_a_card_database_is_unavailable(self, tmp_path: Path):
        junk = tmp_path / "junk.mtga"
        junk.write_bytes(b"not a database at all")

        assert ArenaCardDatabase(junk).available is False

    def test_an_older_localization_table_without_the_formatted_column_still_reads(
        self, tmp_path: Path
    ):
        cards = ArenaCardDatabase(
            build_card_database(tmp_path / "old.mtga", formatted_column=False)
        )
        try:
            assert cards.available is True
            assert cards.card_name(ANGEL) == "Serra Angel"
        finally:
            cards.close()

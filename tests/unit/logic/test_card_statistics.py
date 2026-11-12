"""The shared card-statistics rules: land, mana-value bucket, colour pips, and the deck figures.

These are the rule cases the companion UI's ``curve.test.ts`` and ``colours.test.ts`` used to
carry, moved here because the UI now draws the server's figures rather than computing them. The
agent/companion parity over a real database lives in
``tests/integration/mcp_server/test_card_statistics_parity.py``.
"""

import typing

import pytest

from src.logic.card_statistics import (
    CURVE_BUCKETS,
    PIP_COLOURS,
    DeckStatistics,
    colour_pips,
    curve_distribution,
    deck_statistics,
    front_face_mana_cost,
    front_face_type_line,
    has_land_face,
    is_land,
    mana_value_bucket,
)
from tests.fixtures.card_statistics import (
    EDGE_CARDS,
    VERIFY_CARDS,
    card_fields,
    make_card,
    make_deck_card,
    verify_deck_cards,
)


def _card(type_line: str, **overrides: object):
    return make_card(card_fields("card-x", "Card X", type_line=type_line, **overrides))


def _pips(**counts: int) -> dict[str, int]:
    return {colour: counts.get(colour, 0) for colour in PIP_COLOURS}


# ---------------------------------------------------------------------------
# Land
# ---------------------------------------------------------------------------


class TestFrontFaceTypeLine:
    def test_first_face_type_line_wins_when_present(self) -> None:
        card = make_card(EDGE_CARDS["card-card-card"])
        assert front_face_type_line(card) == "Land"

    def test_top_level_before_the_separator_otherwise(self) -> None:
        assert front_face_type_line(_card("Sorcery // Land")) == "Sorcery"

    def test_single_faced_is_the_whole_type_line(self) -> None:
        assert front_face_type_line(_card("Basic Land — Forest")) == "Basic Land — Forest"

    def test_face_without_a_type_line_falls_back_to_the_top_level(self) -> None:
        card = _card("Instant // Land", card_faces=[{"name": "A"}, {"name": "B"}])
        assert front_face_type_line(card) == "Instant"


@pytest.mark.parametrize(
    ("type_line", "expected"),
    [
        ("Basic Land — Forest", True),
        ("Land", True),
        ("Artifact Land", True),
        ("Land Creature — Forest Dryad", True),
        ("Land // Legendary Creature — Demon", True),
        ("Sorcery // Land", False),
        ("Creature — Elemental // Land", False),
        ("Legendary Enchantment — Aura // Legendary Land", False),
        ("Artifact Creature — Lander", False),
        ("Token Artifact — Lander", False),
        ("Instant", False),
        ("Card", False),
        # Synthetic: no printed subtype is the word "Land", so this holds the type-half split
        # (before the em-dash) on its own.
        ("Enchantment Creature — Land Spirit", False),
    ],
)
def test_is_land_reads_the_front_face_type_half(type_line: str, expected: bool) -> None:
    assert is_land(_card(type_line)) is expected


def test_card_card_printing_is_a_land_by_its_first_face() -> None:
    assert is_land(make_card(EDGE_CARDS["card-card-card"])) is True


@pytest.mark.parametrize(
    ("card_id", "expected"),
    [
        ("card-florahedron", True),  # land back face: kept out of ramp, as before
        ("card-card-card", True),  # the land is only in card_faces[0]
        ("card-dryad-arbor", True),
        ("card-lander", False),  # whole word: "Lander" is not "land"
        ("card-half", False),
    ],
)
def test_has_land_face_checks_every_face(card_id: str, expected: bool) -> None:
    assert has_land_face(make_card(EDGE_CARDS[card_id])) is expected


# ---------------------------------------------------------------------------
# Mana-value buckets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cmc", "bucket"),
    [
        (0.0, 1),
        (0.5, 1),
        (1.0, 1),
        (1.5, 2),
        (2.5, 3),
        (6.4, 6),
        (6.5, 7),
        (7.0, 7),
        (9.0, 7),
        (12.0, 7),
        (1_000_000.0, 7),
    ],
)
def test_mana_value_bucket_rounds_half_up_and_folds_both_ends(cmc: float, bucket: int) -> None:
    assert mana_value_bucket(cmc) == bucket


def test_curve_buckets_are_one_to_seven() -> None:
    assert CURVE_BUCKETS == (1, 2, 3, 4, 5, 6, 7)


def test_curve_buckets_match_the_payload_tuple_arity() -> None:
    """``CURVE_BUCKETS`` and ``DeckStatistics.curve`` must have the same length.

    The payload's tuple type is what the UI's generated ``DeckStatistics['curve']`` comes from,
    so a bucket added on one side and not the other would draw the wrong bars.
    """
    annotation = DeckStatistics.model_fields["curve"].annotation
    assert len(typing.get_args(annotation)) == len(CURVE_BUCKETS)
    statistics = deck_statistics(verify_deck_cards())
    assert len(statistics.curve) == len(CURVE_BUCKETS)
    assert tuple(curve_distribution(statistics)) == CURVE_BUCKETS


# ---------------------------------------------------------------------------
# Colour pips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cost", "expected"),
    [
        ("{W}", _pips(W=1)),
        ("{2}{U}{U}", _pips(U=2)),
        ("{W/U}", _pips(W=1, U=1)),  # a hybrid credits each colour
        ("{G/W}{G/W}", _pips(G=2, W=2)),
        ("{U/P}", _pips(U=1)),  # Phyrexian is a modifier
        ("{G/W/P}", _pips(G=1, W=1)),
        ("{2/R}", _pips(R=1)),  # a generic-hybrid credits its colour
        ("{C}", _pips(C=1)),  # colourless is a colour here
        ("{C/P}", _pips(C=1)),
        ("{2}", _pips()),  # generic credits nothing
        ("{X}{R}", _pips(R=1)),
        ("{0}", _pips()),
        ("{1000000}", _pips()),
        ("{S}", _pips()),  # unknown symbols credit nothing
        ("{HW}", _pips()),
        ("{W/W}", _pips()),
        ("{P/P}", _pips()),
        ("{R/W/G}", _pips()),
        ("{2/X}", _pips()),
        ("", _pips()),
        ("{W", _pips()),  # an unclosed brace is text
    ],
)
def test_colour_pips_follow_the_ui_symbol_rules(cost: str, expected: dict[str, int]) -> None:
    assert colour_pips(cost) == expected


def test_colour_pips_are_case_insensitive() -> None:
    assert colour_pips("{g/w}") == _pips(G=1, W=1)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"mana_cost": "{3}{B} // {1}{B}"}, "{3}{B}"),  # the split shape first
        ({"mana_cost": "{2}{R}"}, "{2}{R}"),  # a real top-level cost
        (
            {"mana_cost": "", "card_faces": [{"mana_cost": "{1}{G}"}, {"mana_cost": ""}]},
            "{1}{G}",
        ),  # the hydrated-face shape
        (
            {"mana_cost": "", "card_faces": [{"mana_cost": "{U} // {B}"}, {"mana_cost": ""}]},
            "{U}",
        ),
        ({"mana_cost": "", "card_faces": [{"mana_cost": None}, {"mana_cost": "{W}"}]}, ""),
        ({"mana_cost": ""}, ""),
    ],
)
def test_front_face_mana_cost_resolves_the_three_shapes(
    overrides: dict[str, object], expected: str
) -> None:
    assert front_face_mana_cost(_card("Instant", **overrides)) == expected


# ---------------------------------------------------------------------------
# Deck statistics
# ---------------------------------------------------------------------------


class TestVerifyDeck:
    """The story's verify deck: every figure the tool and the panels report."""

    def test_counts(self) -> None:
        statistics = deck_statistics(verify_deck_cards())
        # The Forests only: the Sorcery // Land MDFC is a spell.
        assert statistics.land_count == 2
        assert statistics.spell_count == 7

    def test_curve(self) -> None:
        statistics = deck_statistics(verify_deck_cards())
        # 1: the 0-cost Mox and the 1-cost MDFC; 3: the two hybrids; 4: the commander;
        # 7: the 7-drop and the 9-drop.
        assert statistics.curve == (2, 0, 2, 1, 0, 0, 2)

    def test_colour_pips(self) -> None:
        statistics = deck_statistics(verify_deck_cards())
        assert [(entry.colour, entry.count) for entry in statistics.colour_pips] == [
            ("W", 5),
            ("U", 0),
            ("B", 0),
            ("R", 0),
            ("G", 10),
            ("C", 0),
        ]

    def test_the_sideboard_is_counted_nowhere(self) -> None:
        rows = verify_deck_cards()
        with_sideboard = deck_statistics(rows)
        without = deck_statistics([row for row in rows if not row.sideboard])
        assert with_sideboard == without
        # The sideboard card is the only red in the deck.
        assert dict((e.colour, e.count) for e in with_sideboard.colour_pips)["R"] == 0


def test_a_land_face_behind_a_spell_counts_its_front_face_pips() -> None:
    statistics = deck_statistics([make_deck_card(make_card(EDGE_CARDS["card-florahedron"]))])
    assert (statistics.land_count, statistics.spell_count) == (0, 1)
    assert statistics.curve == (0, 1, 0, 0, 0, 0, 0)
    assert dict((e.colour, e.count) for e in statistics.colour_pips)["G"] == 1


def test_a_lands_cost_is_never_counted() -> None:
    land = make_card(card_fields("card-glade", "Glade", type_line="Land", mana_cost="{2}{G}"))
    statistics = deck_statistics([make_deck_card(land, quantity=3)])
    assert statistics.land_count == 3
    assert all(entry.count == 0 for entry in statistics.colour_pips)


def test_quantity_multiplies_every_figure() -> None:
    hybrid = make_card(VERIFY_CARDS["card-hybrid"])
    statistics = deck_statistics([make_deck_card(hybrid, quantity=4)])
    assert statistics.spell_count == 4
    assert statistics.curve == (0, 0, 4, 0, 0, 0, 0)
    pips = dict((e.colour, e.count) for e in statistics.colour_pips)
    assert (pips["G"], pips["W"]) == (8, 8)


def test_the_commander_counts() -> None:
    commander = make_card(VERIFY_CARDS["card-commander"])
    statistics = deck_statistics([make_deck_card(commander, commander=True)])
    assert statistics.spell_count == 1
    assert statistics.curve == (0, 0, 0, 1, 0, 0, 0)


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [make_deck_card(make_card(VERIFY_CARDS["card-forest"]), quantity=20)],
    ],
    ids=["empty", "all-lands"],
)
def test_empty_and_all_land_decks_are_all_zeros(rows) -> None:
    statistics = deck_statistics(rows)
    assert statistics.spell_count == 0
    assert statistics.curve == (0, 0, 0, 0, 0, 0, 0)
    assert [entry.colour for entry in statistics.colour_pips] == list(PIP_COLOURS)
    assert all(entry.count == 0 for entry in statistics.colour_pips)

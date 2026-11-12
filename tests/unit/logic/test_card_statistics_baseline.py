"""Pins of what the agent's figures are for the card-statistics matrix decks.

Written before the shared ``card_statistics`` rules landed, and passing on that baseline, so the
diff of this file is the record of what moved: each pin that changed was rewritten in the commit
that changed it. Three readers are pinned per deck: ``analyze_mana_curve``'s logic (the tool's
figures, over the mainboard expanded by quantity), and the assessment's ``compute_curve`` and
``compute_pip_signals`` (over the mainboard rows), plus the classifier's ramp/tutor exclusion.
"""

import pytest

from src.logic.assessment import classify_card, compute_curve, compute_pip_signals
from src.logic.mana_curve import analyze_mana_curve
from tests.fixtures.card_statistics import (
    EDGE_CARDS,
    expanded_mainboard,
    make_card,
    make_deck_card,
    verify_deck_cards,
)


def _mainboard():
    return [dc for dc in verify_deck_cards() if not dc.sideboard]


class TestVerifyDeck:
    """The verify deck: an MDFC, a 0-drop, a 7-drop, a 9-drop, lands, hybrids, a commander."""

    def test_tool_figures(self) -> None:
        analysis = analyze_mana_curve(expanded_mainboard(verify_deck_cards()))
        # The ``Sorcery // Land`` MDFC is a land: "Land" appears in its joined type line.
        assert analysis.total_lands == 3
        assert analysis.total_spells == 6
        # Sparse, floor-bucketed: the 0-drop sits in 0 and the 9-drop in 9.
        assert analysis.distribution == {0: 1, 3: 2, 4: 1, 7: 1, 9: 1}
        assert analysis.average_cmc == pytest.approx(26 / 6)
        assert analysis.playable_cards_by_turn == {1: 1, 2: 1, 3: 3, 4: 4, 5: 4, 6: 4, 7: 5}

    def test_assessment_curve(self) -> None:
        signals = compute_curve(_mainboard())
        assert signals.land_count == 3
        assert signals.spell_count == 6
        assert signals.distribution == ((0, 1), (3, 2), (4, 1), (7, 1), (9, 1))
        assert signals.average_mana_value == pytest.approx(26 / 6)

    def test_assessment_pips_and_sources(self) -> None:
        signals = {s.color: s for s in compute_pip_signals(_mainboard(), formula="commander")}
        # Bare pips only: the hybrids count for nothing, and the MDFC (a land here) adds none.
        assert {c: s.pip_count for c, s in signals.items()} == {
            "W": 1,
            "U": 0,
            "B": 0,
            "R": 0,
            "G": 5,
        }
        # The MDFC's back face "Add {W}" makes it a white source; the Forests are green.
        assert {c: s.source_count for c, s in signals.items()} == {
            "W": 1,
            "U": 0,
            "B": 0,
            "R": 0,
            "G": 2,
        }


@pytest.mark.parametrize(
    ("card_id", "lands", "spells", "tool_distribution", "curve_distribution"),
    [
        # Land face behind a spell: a land today, since "Land" is in the joined type line.
        ("card-florahedron", 1, 0, {}, ()),
        # Card // Card printing: a spell today, since its top-level type line says nothing.
        ("card-card-card", 0, 1, {0: 1}, ((0, 1),)),
        # The Lander subtype: a land today, by substring.
        ("card-lander", 1, 0, {}, ()),
        ("card-dryad-arbor", 1, 0, {}, ()),
        # Fractional and huge mana values bucket by floor, uncapped.
        ("card-half", 0, 1, {0: 1}, ((0, 1),)),
        ("card-huge", 0, 1, {1000000: 1}, ((1000000, 1),)),
    ],
)
def test_edge_card(
    card_id: str,
    lands: int,
    spells: int,
    tool_distribution: dict[int, int],
    curve_distribution: tuple[tuple[int, int], ...],
) -> None:
    card = make_card(EDGE_CARDS[card_id])
    analysis = analyze_mana_curve([card])
    assert (analysis.total_lands, analysis.total_spells) == (lands, spells)
    assert analysis.distribution == tool_distribution
    signals = compute_curve([make_deck_card(card)])
    assert (signals.land_count, signals.spell_count) == (lands, spells)
    assert signals.distribution == curve_distribution


@pytest.mark.parametrize(
    ("card_id", "tags"),
    [
        # Excluded from ramp: "land" appears in the joined type line.
        ("card-florahedron", set()),
        # Not excluded: the top-level "Card // Card" names no land, so its land face's
        # "Add {U}" reads as ramp.
        ("card-card-card", {"ramp"}),
        # Excluded from ramp by the substring "land" inside "Lander".
        ("card-lander", set()),
    ],
)
def test_classifier_land_exclusion(card_id: str, tags: set[str]) -> None:
    assert set(classify_card(make_card(EDGE_CARDS[card_id]))) == tags


def test_all_land_deck() -> None:
    forest = make_card(EDGE_CARDS["card-dryad-arbor"])
    analysis = analyze_mana_curve([forest, forest])
    assert (analysis.total_lands, analysis.total_spells, analysis.distribution) == (2, 0, {})

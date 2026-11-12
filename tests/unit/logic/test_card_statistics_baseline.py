"""Pins of what the agent's figures are for the card-statistics matrix decks.

Written before the shared ``card_statistics`` rules landed, and passing on that baseline, so the
diff of this file is the record of what moved: each pin that changed was rewritten in the commit
that changed it, and carries a ``MOVED`` note saying what it was. Three readers are pinned per
deck: ``analyze_mana_curve``'s logic (the tool's figures, over the mainboard expanded by
quantity), and the assessment's ``compute_curve`` and ``compute_pip_signals`` (over the mainboard
rows), plus the classifier's ramp/tutor exclusion.
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


def _tool(*buckets: int) -> dict[int, int]:
    """The tool's seven-bucket distribution with one count in each of *buckets*."""
    distribution = dict.fromkeys(range(1, 8), 0)
    for bucket in buckets:
        distribution[bucket] += 1
    return distribution


def _mainboard():
    return [dc for dc in verify_deck_cards() if not dc.sideboard]


class TestVerifyDeck:
    """The verify deck: an MDFC, a 0-drop, a 7-drop, a 9-drop, lands, hybrids, a commander."""

    def test_tool_figures(self) -> None:
        analysis = analyze_mana_curve(expanded_mainboard(verify_deck_cards()))
        # MOVED (shared rules): the ``Sorcery // Land`` MDFC is a spell by its front face
        # (was a land: "Land" appeared in its joined type line).
        assert analysis.total_lands == 2
        assert analysis.total_spells == 7
        # MOVED: all seven buckets, zeros kept; the 0-drop folds into 1 and the 9-drop into 7
        # (was sparse and floor-bucketed: {0: 1, 3: 2, 4: 1, 7: 1, 9: 1}).
        assert analysis.distribution == {1: 2, 2: 0, 3: 2, 4: 1, 5: 0, 6: 0, 7: 2}
        # Exact cmc, now over seven spells (the MDFC's 1 joins).
        assert analysis.average_cmc == pytest.approx(27 / 7)
        assert analysis.playable_cards_by_turn == {1: 2, 2: 2, 3: 4, 4: 5, 5: 5, 6: 5, 7: 6}

    def test_assessment_curve(self) -> None:
        signals = compute_curve(_mainboard())
        # MOVED: the MDFC is a spell (was 3 lands / 6 spells). The internal distribution keeps
        # its floor buckets, unchanged in kind.
        assert signals.land_count == 2
        assert signals.spell_count == 7
        assert signals.distribution == ((0, 1), (1, 1), (3, 2), (4, 1), (7, 1), (9, 1))
        assert signals.average_mana_value == pytest.approx(27 / 7)

    def test_assessment_pips_and_sources(self) -> None:
        signals = {s.color: s for s in compute_pip_signals(_mainboard(), formula="commander")}
        # Bare pips only: the hybrids count for nothing. MOVED: the MDFC is a spell, so its
        # front-face {G} is demand (G was 5).
        assert {c: s.pip_count for c, s in signals.items()} == {
            "W": 1,
            "U": 0,
            "B": 0,
            "R": 0,
            "G": 6,
        }
        # MOVED: the MDFC is no longer a land, so its back face's "Add {W}" is no white source
        # (W was 1). The Forests are green.
        assert {c: s.source_count for c, s in signals.items()} == {
            "W": 0,
            "U": 0,
            "B": 0,
            "R": 0,
            "G": 2,
        }


@pytest.mark.parametrize(
    ("card_id", "lands", "spells", "tool_distribution", "curve_distribution"),
    [
        # MOVED: a land face behind a spell is a spell (was a land, by the joined type line).
        ("card-florahedron", 0, 1, _tool(2), ((2, 1),)),
        # MOVED: a Card // Card printing whose first face is a Land is a land (was a spell).
        ("card-card-card", 1, 0, _tool(), ()),
        # MOVED: the Lander subtype is a spell, by whole word (was a land, by substring).
        ("card-lander", 0, 1, _tool(2), ((2, 1),)),
        ("card-dryad-arbor", 1, 0, _tool(), ()),
        # MOVED (tool only): fractional rounds half up into 1 and huge folds into 7 (was floor,
        # uncapped). The assessment's internal floor buckets do not move.
        ("card-half", 0, 1, _tool(1), ((0, 1),)),
        ("card-huge", 0, 1, _tool(7), ((1000000, 1),)),
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
        # Unchanged: excluded from ramp, since its back face is a land (has_land_face).
        ("card-florahedron", set()),
        # MOVED: excluded, since card_faces[0] is a land (was ramp: the top-level
        # "Card // Card" named no land, so its land face's "Add {U}" read as ramp).
        ("card-card-card", set()),
        # MOVED: "Lander" is not the word "land", so its land search now reads as ramp (was
        # excluded by substring).
        ("card-lander", {"ramp"}),
    ],
)
def test_classifier_land_exclusion(card_id: str, tags: set[str]) -> None:
    assert set(classify_card(make_card(EDGE_CARDS[card_id]))) == tags


def test_all_land_deck() -> None:
    forest = make_card(EDGE_CARDS["card-dryad-arbor"])
    analysis = analyze_mana_curve([forest, forest])
    # MOVED: the distribution keeps all seven buckets at zero (was {}).
    assert (analysis.total_lands, analysis.total_spells, analysis.distribution) == (
        2,
        0,
        _tool(),
    )

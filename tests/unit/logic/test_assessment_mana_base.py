"""Offline behavior tests for the FR5/FR8 mana-base & curve signals (Story 5.4).

Exact-value assertions are used only for *published* constants (the Karsten regression
coefficients — the AC6 carve-out); provisional tunables (flood/screw tolerance, pip-source
anchors, deck-size scaling) are asserted *by reference to the module constant* so Story 5.9's
benchmark tuning never shreds these tests (the 5.1/5.2 verify-by-shape lesson).
"""

import math

import pytest

from src.data.schemas.card import Card
from src.data.schemas.deck import DeckCard
from src.logic.assessment import (
    ColorPipSignal,
    CurveSignals,
    KarstenLandSignal,
    compute_curve,
    compute_pip_signals,
    karsten_land_delta,
)
from src.logic.assessment.mana_base import (
    KARSTEN_TOLERANCE_LANDS,
    PIP_SOURCE_ANCHORS_COMMANDER,
    PIP_SOURCE_ANCHORS_SIXTY_CARD,
)
from tests.fixtures.assessment import make_card, make_deck_card

# ---------------------------------------------------------------------------
# Canonical fixture cards
# ---------------------------------------------------------------------------


def forest() -> Card:
    return make_card(
        name="Forest",
        type_line="Basic Land — Forest",
        mana_cost="",
        cmc=0.0,
        oracle_text="({T}: Add {G}.)",
    )


def llanowar_elves() -> Card:  # cmc 1 ramp creature
    return make_card(
        name="Llanowar Elves",
        type_line="Creature — Elf Druid",
        mana_cost="{G}",
        cmc=1.0,
        oracle_text="{T}: Add {G}.",
        power="1",
        toughness="1",
    )


def divination() -> Card:  # cmc 3 card draw
    return make_card(
        name="Divination",
        type_line="Sorcery",
        mana_cost="{2}{U}",
        cmc=3.0,
        oracle_text="Draw two cards.",
    )


def grizzly_bears() -> Card:  # cmc 2 vanilla creature
    return make_card(
        name="Grizzly Bears",
        type_line="Creature — Bear",
        mana_cost="{1}{G}",
        cmc=2.0,
        oracle_text="",
        power="2",
        toughness="2",
    )


# ---------------------------------------------------------------------------
# FR5 curve signals (AC2)
# ---------------------------------------------------------------------------


class TestComputeCurve:
    def test_mixed_deck_quantity_aware_buckets_exclude_lands(self) -> None:
        deck = [
            make_deck_card(llanowar_elves(), quantity=4),
            make_deck_card(grizzly_bears(), quantity=3),
            make_deck_card(divination(), quantity=2),
            make_deck_card(forest(), quantity=24),
        ]
        signals = compute_curve(deck)
        assert signals.distribution == ((1, 4), (2, 3), (3, 2))
        assert signals.land_count == 24
        assert signals.spell_count == 9

    def test_average_mana_value_is_quantity_weighted_over_spells_only(self) -> None:
        deck = [
            make_deck_card(llanowar_elves(), quantity=4),  # 4 x 1.0
            make_deck_card(divination(), quantity=2),  # 2 x 3.0
            make_deck_card(forest(), quantity=10),  # excluded
        ]
        signals = compute_curve(deck)
        assert signals.average_mana_value == (4 * 1.0 + 2 * 3.0) / 6

    def test_empty_deck_returns_zeroed_signals_without_raising(self) -> None:
        signals = compute_curve([])
        assert signals == CurveSignals(
            distribution=(),
            average_mana_value=0.0,
            land_count=0,
            spell_count=0,
        )

    def test_all_lands_deck_returns_zero_spells_without_raising(self) -> None:
        signals = compute_curve([make_deck_card(forest(), quantity=40)])
        assert signals.distribution == ()
        assert signals.average_mana_value == 0.0
        assert signals.land_count == 40
        assert signals.spell_count == 0

    def test_mdfc_with_land_face_counts_as_land(self) -> None:
        # Land detection is "land" in type_line — an MDFC "Creature // Land" joins faces
        # in the top-level type_line, so it counts as a land (documented v1 policy).
        mdfc = make_card(
            name="Tangled Florahedron // Tangled Vale",
            type_line="Creature — Elemental // Land",
            mana_cost="{1}{G}",
            cmc=2.0,
        )
        signals = compute_curve([make_deck_card(mdfc, quantity=2)])
        assert signals.land_count == 2
        assert signals.spell_count == 0
        assert signals.distribution == ()

    def test_fractional_cmc_buckets_by_floor(self) -> None:
        half = make_card(name="Little Girl", mana_cost="{HW}", cmc=0.5)
        signals = compute_curve([make_deck_card(half)])
        assert signals.distribution == ((0, 1),)

    def test_distribution_is_sorted_by_bucket(self) -> None:
        deck = [
            make_deck_card(divination(), quantity=1),
            make_deck_card(llanowar_elves(), quantity=1),
        ]
        buckets = [bucket for bucket, _ in compute_curve(deck).distribution]
        assert buckets == sorted(buckets)

    def test_determinism_two_calls_equal(self) -> None:
        deck = [
            make_deck_card(llanowar_elves(), quantity=4),
            make_deck_card(divination(), quantity=3),
            make_deck_card(forest(), quantity=20),
        ]
        assert compute_curve(deck) == compute_curve(list(deck))


# ---------------------------------------------------------------------------
# FR8 Karsten land-count delta (AC3)
# ---------------------------------------------------------------------------


def cheap_draw() -> Card:  # cmc 2, CARD_DRAW — inside the cheap cutoff
    return make_card(
        name="Cheap Draw",
        type_line="Sorcery",
        mana_cost="{1}{U}",
        cmc=2.0,
        oracle_text="Draw a card.",
    )


def filler_four_drop() -> Card:  # cmc 4, no tags
    return make_card(
        name="Filler Four-Drop",
        type_line="Creature — Golem",
        mana_cost="{4}",
        cmc=4.0,
        oracle_text="",
        power="3",
        toughness="3",
    )


def pinned_karsten_deck(lands: int) -> list[DeckCard]:
    """avgMV 3.0 (10 x cmc-2 + 10 x cmc-4) with exactly 10 cheap draw/ramp cards."""
    return [
        make_deck_card(cheap_draw(), quantity=10),
        make_deck_card(filler_four_drop(), quantity=10),
        make_deck_card(forest(), quantity=lands),
    ]


class TestKarstenLandDelta:
    def test_commander_formula_exact_arithmetic(self) -> None:
        # 31.42 + 3.13 * 3.0 - 0.28 * 10 = 38.01 (published coefficients — exact check)
        signal = karsten_land_delta(pinned_karsten_deck(lands=30), formula="commander")
        assert signal.recommended_lands == pytest.approx(38.01)
        assert signal.actual_lands == 30
        assert signal.delta == pytest.approx(30 - 38.01)
        assert signal.cheap_draw_ramp_count == 10

    def test_sixty_card_formula_exact_arithmetic(self) -> None:
        # 19.59 + 1.90 * 3.0 - 0.28 * 10 = 22.49 (published coefficients — exact check)
        signal = karsten_land_delta(pinned_karsten_deck(lands=24), formula="sixty_card")
        assert signal.recommended_lands == pytest.approx(22.49)
        assert signal.actual_lands == 24
        assert signal.delta == pytest.approx(24 - 22.49)

    def test_flood_and_screw_flags_flip_at_the_tolerance_boundary(self) -> None:
        # Boundaries computed FROM the module constant so 5.9 retuning doesn't break this.
        recommended = 22.49  # published-arithmetic value for the pinned deck, sixty_card
        just_inside_high = math.floor(recommended + KARSTEN_TOLERANCE_LANDS)
        flood = just_inside_high + 1
        just_inside_low = math.ceil(recommended - KARSTEN_TOLERANCE_LANDS)
        screw = just_inside_low - 1

        inside_hi = karsten_land_delta(pinned_karsten_deck(just_inside_high), formula="sixty_card")
        assert not inside_hi.mana_flood_risk and not inside_hi.mana_screw_risk

        flooded = karsten_land_delta(pinned_karsten_deck(flood), formula="sixty_card")
        assert flooded.mana_flood_risk and not flooded.mana_screw_risk

        inside_lo = karsten_land_delta(pinned_karsten_deck(just_inside_low), formula="sixty_card")
        assert not inside_lo.mana_flood_risk and not inside_lo.mana_screw_risk

        screwed = karsten_land_delta(pinned_karsten_deck(screw), formula="sixty_card")
        assert screwed.mana_screw_risk and not screwed.mana_flood_risk

    def test_cmc_three_ramp_is_not_cheap(self) -> None:
        cultivate = make_card(
            name="Cultivate",
            type_line="Sorcery",
            mana_cost="{2}{G}",
            cmc=3.0,
            oracle_text=(
                "Search your library for up to two basic land cards, reveal those cards, "
                "put one onto the battlefield tapped and the other into your hand."
            ),
        )
        deck = [make_deck_card(cultivate, quantity=4), make_deck_card(forest(), quantity=20)]
        signal = karsten_land_delta(deck, formula="sixty_card")
        assert signal.cheap_draw_ramp_count == 0

    def test_dual_tagged_cheap_card_counts_once_per_copy(self) -> None:
        # RAMP + CARD_DRAW on one card = one spell slot, not two (AC3); 4 copies count 4.
        dual = make_card(
            name="Ramp And Draw",
            type_line="Artifact",
            mana_cost="{2}",
            cmc=2.0,
            oracle_text="{T}: Add {C}.\nWhen this artifact enters, draw a card.",
        )
        signal = karsten_land_delta([make_deck_card(dual, quantity=4)], formula="sixty_card")
        assert signal.cheap_draw_ramp_count == 4

    def test_land_typed_card_never_counts_as_cheap(self) -> None:
        draw_land = make_card(
            name="Draw Land",
            type_line="Land",
            mana_cost="",
            cmc=0.0,
            oracle_text="{T}, Sacrifice this land: Draw a card.",
        )
        signal = karsten_land_delta([make_deck_card(draw_land, quantity=4)], formula="sixty_card")
        assert signal.cheap_draw_ramp_count == 0
        assert signal.actual_lands == 4

    def test_empty_deck_returns_signal_without_raising(self) -> None:
        signal = karsten_land_delta([], formula="commander")
        assert signal.actual_lands == 0
        assert signal.cheap_draw_ramp_count == 0
        # avgMV 0 collapses the formula to its intercept — still a well-formed signal.
        assert signal.recommended_lands == pytest.approx(31.42)

    def test_determinism_two_calls_equal(self) -> None:
        deck = pinned_karsten_deck(lands=30)
        first = karsten_land_delta(deck, formula="commander")
        second = karsten_land_delta(list(deck), formula="commander")
        assert first == second
        assert isinstance(first, KarstenLandSignal)


# ---------------------------------------------------------------------------
# FR8 pip demand & colored sources (AC4)
# ---------------------------------------------------------------------------


def by_color(signals: tuple[ColorPipSignal, ...]) -> dict[str, ColorPipSignal]:
    return {signal.color: signal for signal in signals}


class TestPipDemand:
    def test_always_all_five_colors_in_wubrg_order(self) -> None:
        signals = compute_pip_signals([], formula="sixty_card")
        assert tuple(signal.color for signal in signals) == ("W", "U", "B", "R", "G")

    def test_plain_pips_counted_quantity_aware_with_max_single_card(self) -> None:
        double_green = make_card(
            name="Double Green",
            type_line="Creature — Wurm",
            mana_cost="{2}{G}{G}",
            cmc=4.0,
            power="4",
            toughness="4",
        )
        deck = [
            make_deck_card(grizzly_bears(), quantity=4),  # {1}{G} -> 4 G pips, max 1
            make_deck_card(double_green, quantity=1),  # {2}{G}{G} -> 2 G pips, max 2
        ]
        green = by_color(compute_pip_signals(deck, formula="sixty_card"))["G"]
        assert green.pip_count == 6
        assert green.max_pips_single_card == 2

    def test_hybrid_phyrexian_and_twobrid_pips_are_excluded(self) -> None:
        # Each is payable without the color's source — counting them as hard pips would
        # overstate the requirement (documented v1 policy; 5.9 tunes).
        tricosts = make_card(
            name="Flexible Costs",
            type_line="Sorcery",
            mana_cost="{G/U}{G/P}{2/W}",
            cmc=3.0,
        )
        signals = by_color(compute_pip_signals([make_deck_card(tricosts)], formula="sixty_card"))
        assert all(signals[color].pip_count == 0 for color in "WUBRG")

    def test_empty_mana_cost_with_faces_uses_front_face(self) -> None:
        # Transform DFCs persist mana_cost="" with the real cost on the front face; a
        # back face's mana_cost can be an explicit None (the 5.3 null-face lesson).
        dfc = make_card(
            name="Village Watch // Village Reavers",
            type_line="Creature — Human Werewolf // Creature — Werewolf",
            mana_cost="",
            cmc=5.0,
            card_faces=[{"mana_cost": "{4}{R}"}, {"mana_cost": None}],
        )
        signals = by_color(compute_pip_signals([make_deck_card(dfc)], formula="sixty_card"))
        assert signals["R"].pip_count == 1

    def test_land_mdfc_is_excluded_from_pip_demand(self) -> None:
        # The land-detection policy wins: a "Creature // Land" MDFC is land-slot material,
        # so its front-face cost contributes no pip demand (documented v1 consequence).
        mdfc = make_card(
            name="Tangled Florahedron // Tangled Vale",
            type_line="Creature — Elemental // Land",
            mana_cost="",
            cmc=2.0,
            card_faces=[{"mana_cost": "{1}{G}"}, {"mana_cost": None}],
        )
        signals = by_color(compute_pip_signals([make_deck_card(mdfc)], formula="sixty_card"))
        assert signals["G"].pip_count == 0

    def test_split_card_joined_cost_parses_as_written(self) -> None:
        split = make_card(
            name="Grow // Know",
            type_line="Sorcery // Sorcery",
            mana_cost="{G} // {1}{U}",
            cmc=3.0,
        )
        signals = by_color(compute_pip_signals([make_deck_card(split)], formula="sixty_card"))
        assert signals["G"].pip_count == 1
        assert signals["U"].pip_count == 1

    def test_land_costs_never_contribute_pips(self) -> None:
        signals = by_color(
            compute_pip_signals([make_deck_card(forest(), quantity=20)], formula="sixty_card")
        )
        assert all(signals[color].pip_count == 0 for color in "WUBRG")


class TestColoredSources:
    def test_basic_forest_is_a_green_source(self) -> None:
        signals = by_color(
            compute_pip_signals([make_deck_card(forest(), quantity=12)], formula="sixty_card")
        )
        assert signals["G"].source_count == 12
        assert signals["U"].source_count == 0

    def test_typed_dual_counts_for_both_colors(self) -> None:
        steam_vents = make_card(
            name="Steam Vents",
            type_line="Land — Island Mountain",
            mana_cost="",
            cmc=0.0,
            oracle_text="As this land enters, you may pay 2 life.",
        )
        signals = by_color(
            compute_pip_signals([make_deck_card(steam_vents, quantity=4)], formula="sixty_card")
        )
        assert signals["U"].source_count == 4
        assert signals["R"].source_count == 4
        assert signals["G"].source_count == 0

    def test_add_symbol_text_counts_untype_land(self) -> None:
        painland = make_card(
            name="Adarkar Wastes",
            type_line="Land",
            mana_cost="",
            cmc=0.0,
            oracle_text=("{T}: Add {C}.\n{T}: Add {W} or {U}. This land deals 1 damage to you."),
        )
        signals = by_color(compute_pip_signals([make_deck_card(painland)], formula="sixty_card"))
        assert signals["W"].source_count == 1
        assert signals["U"].source_count == 1
        assert signals["B"].source_count == 0

    def test_any_color_land_counts_for_all_five(self) -> None:
        tower = make_card(
            name="Command Tower",
            type_line="Land",
            mana_cost="",
            cmc=0.0,
            oracle_text="{T}: Add one mana of any color in your commander's color identity.",
        )
        signals = by_color(compute_pip_signals([make_deck_card(tower)], formula="commander"))
        assert all(signals[color].source_count == 1 for color in "WUBRG")

    def test_fetchland_is_not_a_source(self) -> None:
        # Fetches produce nothing themselves — documented, accepted v1 undercount.
        fetch = make_card(
            name="Windswept Heath",
            type_line="Land",
            mana_cost="",
            cmc=0.0,
            oracle_text=(
                "{T}, Pay 1 life, Sacrifice this land: Search your library for a Forest "
                "or Plains card, put it onto the battlefield, then shuffle."
            ),
        )
        signals = by_color(compute_pip_signals([make_deck_card(fetch)], formula="sixty_card"))
        assert all(signals[color].source_count == 0 for color in "WUBRG")

    def test_nonland_mana_rock_is_not_a_source(self) -> None:
        # Karsten's primary tables count lands; rocks/dorks are a 5.9 calibration option.
        sol_ring = make_card(
            name="Sol Ring",
            type_line="Artifact",
            mana_cost="{1}",
            cmc=1.0,
            oracle_text="{T}: Add {C}{C}.",
        )
        signals = by_color(compute_pip_signals([make_deck_card(sol_ring)], formula="sixty_card"))
        assert all(signals[color].source_count == 0 for color in "WUBRG")


class TestPipAdequacy:
    def test_sixty_card_anchors_match_published_values(self) -> None:
        # 1 pip ≈ 14 sources, 2 pips ≈ 18 (docs/deck-assess.md:155 — published anchors).
        assert PIP_SOURCE_ANCHORS_SIXTY_CARD[1] == 14
        assert PIP_SOURCE_ANCHORS_SIXTY_CARD[2] == 18

    def test_recommended_and_deficit_follow_the_anchor_for_max_pips(self) -> None:
        deck = [
            make_deck_card(grizzly_bears(), quantity=4),  # max 1 G pip
            make_deck_card(forest(), quantity=10),
        ]
        green = by_color(compute_pip_signals(deck, formula="sixty_card"))["G"]
        anchor = PIP_SOURCE_ANCHORS_SIXTY_CARD[1]
        assert green.recommended_sources == anchor
        assert green.deficit == max(0, anchor - 10)

    def test_deficit_is_zero_when_sources_exceed_recommendation(self) -> None:
        deck = [
            make_deck_card(grizzly_bears(), quantity=4),
            make_deck_card(forest(), quantity=20),
        ]
        green = by_color(compute_pip_signals(deck, formula="sixty_card"))["G"]
        assert green.deficit == 0

    def test_three_plus_pips_use_the_top_anchor(self) -> None:
        triple = make_card(
            name="Triple White",
            type_line="Sorcery",
            mana_cost="{W}{W}{W}",
            cmc=3.0,
        )
        white = by_color(compute_pip_signals([make_deck_card(triple)], formula="sixty_card"))["W"]
        assert white.recommended_sources == PIP_SOURCE_ANCHORS_SIXTY_CARD[3]

    def test_commander_formula_selects_the_scaled_anchor_table(self) -> None:
        deck = [make_deck_card(grizzly_bears(), quantity=1)]
        green = by_color(compute_pip_signals(deck, formula="commander"))["G"]
        assert green.recommended_sources == PIP_SOURCE_ANCHORS_COMMANDER[1]

    def test_zero_demand_color_has_no_recommendation_or_deficit(self) -> None:
        deck = [
            make_deck_card(grizzly_bears(), quantity=4),
            make_deck_card(forest(), quantity=10),
        ]
        signals = by_color(compute_pip_signals(deck, formula="sixty_card"))
        for color in ("W", "U", "B", "R"):
            assert signals[color].pip_count == 0
            assert signals[color].recommended_sources == 0
            assert signals[color].deficit == 0

    def test_empty_deck_returns_five_zeroed_signals_without_raising(self) -> None:
        signals = compute_pip_signals([], formula="commander")
        assert len(signals) == 5
        for signal in signals:
            assert signal.pip_count == 0
            assert signal.max_pips_single_card == 0
            assert signal.source_count == 0
            assert signal.recommended_sources == 0
            assert signal.deficit == 0

    def test_determinism_two_calls_equal(self) -> None:
        deck = [
            make_deck_card(grizzly_bears(), quantity=4),
            make_deck_card(divination(), quantity=2),
            make_deck_card(forest(), quantity=12),
        ]
        assert compute_pip_signals(deck, formula="sixty_card") == compute_pip_signals(
            list(deck), formula="sixty_card"
        )

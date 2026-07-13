"""Offline behavior tests for the FR17/FR7/FR9 consistency & coverage signals (Story 5.5).

Exact-value assertions are used only for *published/derived* constants (the hypergeometric
anchors — pure math, safe to pin); provisional tunables (the structural-gap baseline tables)
are asserted *by reference to the module constant* so Story 5.9's benchmark tuning never
shreds these tests (the 5.1/5.2 verify-by-shape lesson).

The ~91% trap (story Dev Notes, verified by direct computation): the research doc's "24
lands in 60 → ~91% for ≥2 lands in the opening 7" is actually the value at EIGHT seen
cards (7 seen gives ≈ 0.857). Both values are pinned below at their true seen-counts so
the ``cards_seen(turn) = 7 + turn`` convention is regression-locked — do not "fix" the
math to chase the prose.
"""

import dataclasses

import pytest

from src.data.schemas.card import Card
from src.logic.assessment import (
    CARD_DRAW_BELOW_BASELINE,
    INTERACTION_BELOW_BASELINE,
    OPENING_HAND_SIZE,
    RAMP_BELOW_BASELINE,
    STRUCTURAL_GAP_TOKENS,
    WINCON_MISSING,
    InteractionSignals,
    RedundancySignal,
    cards_seen_by_turn,
    interaction_signals,
    land_access_by_turn,
    probability_at_least,
    redundancy_signals,
    structural_gaps,
)
from src.logic.assessment.classifiers import (
    CARD_DRAW,
    CATEGORIES,
    INTERACTION,
    RAMP,
    classify_deck,
)
from src.logic.assessment.consistency import STRUCTURAL_GAP_BASELINES
from tests.fixtures.assessment import make_card, make_deck_card

# ---------------------------------------------------------------------------
# Canonical fixture cards (wordings quote the classifier patterns' canon)
# ---------------------------------------------------------------------------


def forest() -> Card:
    return make_card(
        name="Forest",
        type_line="Basic Land — Forest",
        mana_cost="",
        cmc=0.0,
        oracle_text="({T}: Add {G}.)",
    )


def grizzly_bears() -> Card:  # untagged filler creature
    return make_card(
        name="Grizzly Bears",
        type_line="Creature — Bear",
        mana_cost="{1}{G}",
        cmc=2.0,
        oracle_text="",
        power="2",
        toughness="2",
    )


def lightning_bolt() -> Card:  # INTERACTION, instant-speed via type line, cmc 1
    return make_card(
        name="Lightning Bolt",
        type_line="Instant",
        mana_cost="{R}",
        cmc=1.0,
        oracle_text="Lightning Bolt deals 3 damage to any target.",
    )


def doom_blade() -> Card:  # INTERACTION, instant-speed via type line, cmc 2
    return make_card(
        name="Doom Blade",
        type_line="Instant",
        mana_cost="{1}{B}",
        cmc=2.0,
        oracle_text="Destroy target nonblack creature.",
    )


def day_of_judgment() -> Card:  # INTERACTION (mass wipe), sorcery-speed, cmc 4
    return make_card(
        name="Day of Judgment",
        type_line="Sorcery",
        mana_cost="{2}{W}{W}",
        cmc=4.0,
        oracle_text="Destroy all creatures.",
    )


def ambush_removal() -> Card:  # INTERACTION on a flash creature — instant-speed via keyword
    return make_card(
        name="Ambush Removal",
        type_line="Creature — Faerie",
        mana_cost="{2}{U}",
        cmc=3.0,
        oracle_text="Flash\nWhen this creature enters, destroy target artifact.",
        keywords=["Flash", "Flying"],
        power="2",
        toughness="1",
    )


def sol_ring() -> Card:  # RAMP, cmc 1
    return make_card(
        name="Sol Ring",
        type_line="Artifact",
        mana_cost="{1}",
        cmc=1.0,
        oracle_text="{T}: Add {C}{C}.",
    )


def divination() -> Card:  # CARD_DRAW, cmc 3
    return make_card(
        name="Divination",
        type_line="Sorcery",
        mana_cost="{2}{U}",
        cmc=3.0,
        oracle_text="Draw two cards.",
    )


def oracle_wincon() -> Card:  # WINCON_EXPLICIT
    return make_card(
        name="Test Oracle",
        type_line="Creature — Merfolk Wizard",
        mana_cost="{U}{U}",
        cmc=2.0,
        oracle_text="When this creature enters, if your library is empty, you win the game.",
        power="1",
        toughness="3",
    )


# ---------------------------------------------------------------------------
# FR17 hypergeometric primitive (AC2, AC8)
# ---------------------------------------------------------------------------


class TestProbabilityAtLeast:
    def test_rule_of_eight_published_anchors_are_exact(self) -> None:
        # 60-card opener (7 seen): published 39.9% / 65.4% / 80.9% (docs/deck-assess.md:124).
        # Values below are the exact math.comb results, verified by direct computation.
        assert probability_at_least(deck_size=60, copies=4, drawn=7) == pytest.approx(
            0.3995, abs=1e-3
        )
        assert probability_at_least(deck_size=60, copies=8, drawn=7) == pytest.approx(
            0.6536, abs=1e-3
        )
        assert probability_at_least(deck_size=60, copies=12, drawn=7) == pytest.approx(
            0.8094, abs=1e-3
        )

    def test_single_copy_reduces_to_drawn_over_deck_size(self) -> None:
        # The 12/99 worked example (docs/deck-assess.md:154): 1 copy, turn 5 = 12 seen.
        assert probability_at_least(deck_size=99, copies=1, drawn=12) == pytest.approx(12 / 99)

    def test_the_91_percent_trap_pins_both_seen_counts(self) -> None:
        # The doc's "~91% for ≥2 lands in the opening 7" is the EIGHT-seen value; 7 seen
        # gives ≈ 0.857 (story Dev Notes trap). Pin both so nobody bends the convention.
        assert probability_at_least(deck_size=60, copies=24, drawn=7, min_count=2) == pytest.approx(
            0.8573, abs=1e-3
        )
        assert probability_at_least(deck_size=60, copies=24, drawn=8, min_count=2) == pytest.approx(
            0.9099, abs=1e-3
        )

    def test_min_count_zero_or_negative_is_trivially_satisfied(self) -> None:
        assert probability_at_least(deck_size=60, copies=4, drawn=7, min_count=0) == 1.0
        assert probability_at_least(deck_size=60, copies=4, drawn=7, min_count=-3) == 1.0

    def test_min_count_precedence_beats_empty_deck(self) -> None:
        # AC2: min_count <= 0 is checked FIRST — an empty deck at turn 0 still reads 1.0.
        assert probability_at_least(deck_size=0, copies=0, drawn=0, min_count=0) == 1.0

    def test_zero_or_negative_inputs_degrade_to_zero(self) -> None:
        assert probability_at_least(deck_size=0, copies=4, drawn=7) == 0.0
        assert probability_at_least(deck_size=-5, copies=4, drawn=7) == 0.0
        assert probability_at_least(deck_size=60, copies=0, drawn=7) == 0.0
        assert probability_at_least(deck_size=60, copies=-1, drawn=7) == 0.0
        assert probability_at_least(deck_size=60, copies=4, drawn=0) == 0.0
        assert probability_at_least(deck_size=60, copies=4, drawn=-2) == 0.0

    def test_drawn_beyond_deck_size_clamps_to_certainty(self) -> None:
        assert probability_at_least(deck_size=10, copies=2, drawn=50) == 1.0

    def test_copies_beyond_deck_size_clamp(self) -> None:
        assert probability_at_least(deck_size=10, copies=100, drawn=3) == 1.0

    def test_min_count_beyond_reach_is_zero(self) -> None:
        assert probability_at_least(deck_size=60, copies=2, drawn=7, min_count=3) == 0.0
        assert probability_at_least(deck_size=60, copies=10, drawn=3, min_count=4) == 0.0

    def test_min_count_defaults_to_one(self) -> None:
        assert probability_at_least(deck_size=60, copies=4, drawn=7) == probability_at_least(
            deck_size=60, copies=4, drawn=7, min_count=1
        )

    def test_determinism_two_calls_bit_identical(self) -> None:
        first = probability_at_least(deck_size=99, copies=13, drawn=12, min_count=2)
        second = probability_at_least(deck_size=99, copies=13, drawn=12, min_count=2)
        assert first == second


class TestCardsSeenByTurn:
    def test_turn_zero_is_the_opening_hand(self) -> None:
        assert cards_seen_by_turn(0) == OPENING_HAND_SIZE == 7

    def test_turn_five_matches_the_worked_example(self) -> None:
        # "1 copy in 99 cards ≈ 12% by turn 5" = 12 seen cards (docs/deck-assess.md:154).
        assert cards_seen_by_turn(5) == 12


# ---------------------------------------------------------------------------
# FR17 mana access by turn (AC3)
# ---------------------------------------------------------------------------


def sixty_card_twenty_four_lands() -> list:
    return [
        make_deck_card(forest(), quantity=24),
        make_deck_card(grizzly_bears(), quantity=36),
    ]


class TestLandAccessByTurn:
    def test_matches_the_primitive_on_a_pinned_deck(self) -> None:
        # 24 lands / 60 cards, turn 2: P(≥2 lands among 9 seen) — wiring check against the
        # primitive, whose math is pinned above.
        expected = probability_at_least(deck_size=60, copies=24, drawn=9, min_count=2)
        assert land_access_by_turn(sixty_card_twenty_four_lands(), 2) == expected

    def test_turn_zero_needs_no_land_drops(self) -> None:
        # min_count = turn = 0 → trivially satisfied via the primitive's AC2 rule.
        assert land_access_by_turn(sixty_card_twenty_four_lands(), 0) == 1.0

    def test_empty_deck_returns_zero_for_positive_turns(self) -> None:
        assert land_access_by_turn([], 3) == 0.0

    def test_empty_deck_at_turn_zero_reads_one(self) -> None:
        assert land_access_by_turn([], 0) == 1.0

    def test_quantity_aware_land_count(self) -> None:
        # One 24-quantity row must read identically to the pinned deck above.
        single_rows = [
            make_deck_card(forest(), quantity=24),
            make_deck_card(grizzly_bears(), quantity=36),
        ]
        assert land_access_by_turn(single_rows, 3) == probability_at_least(
            deck_size=60, copies=24, drawn=10, min_count=3
        )

    def test_sideboard_cards_are_not_filtered(self) -> None:
        # Deck-composition policy belongs to the caller (the 5.3/5.4 precedent).
        deck = [
            make_deck_card(forest(), quantity=24),
            make_deck_card(grizzly_bears(), quantity=35),
            make_deck_card(grizzly_bears(), quantity=1, sideboard=True),
        ]
        assert land_access_by_turn(deck, 2) == probability_at_least(
            deck_size=60, copies=24, drawn=9, min_count=2
        )

    def test_determinism_two_calls_equal(self) -> None:
        deck = sixty_card_twenty_four_lands()
        assert land_access_by_turn(deck, 4) == land_access_by_turn(list(deck), 4)


# ---------------------------------------------------------------------------
# FR9 redundancy signals (AC4)
# ---------------------------------------------------------------------------


class TestRedundancySignals:
    def test_always_all_nine_categories_in_fixed_order(self) -> None:
        signals = redundancy_signals([])
        assert tuple(signal.category for signal in signals) == CATEGORIES
        assert len(signals) == 9

    def test_rule_of_eight_anchor_falls_out_of_the_math(self) -> None:
        # 4 ramp copies in a 60-card deck: opener probability ≈ 39.9% — computed, not stored.
        deck = [
            make_deck_card(sol_ring(), quantity=4),
            make_deck_card(grizzly_bears(), quantity=32),
            make_deck_card(forest(), quantity=24),
        ]
        by_category = {signal.category: signal for signal in redundancy_signals(deck)}
        assert by_category[RAMP].count == 4
        assert by_category[RAMP].opener_probability == pytest.approx(0.3995, abs=1e-3)

    def test_counts_match_classify_deck(self) -> None:
        # The redundancy count is classify_deck's count — assert the equivalence once here
        # (dev-notes contract) instead of computing both in production code.
        deck = [
            make_deck_card(sol_ring(), quantity=4),
            make_deck_card(divination(), quantity=3),
            make_deck_card(doom_blade(), quantity=2, sideboard=True),
        ]
        counts = classify_deck(deck)
        for signal in redundancy_signals(deck):
            assert signal.count == counts[signal.category].count

    def test_zero_count_categories_carry_probability_zero(self) -> None:
        deck = [make_deck_card(grizzly_bears(), quantity=40)]
        for signal in redundancy_signals(deck):
            assert signal.count == 0
            assert signal.opener_probability == 0.0

    def test_opener_probability_uses_actual_deck_size(self) -> None:
        # 4 draw spells in a 40-card deck, not a hard-coded 60.
        deck = [
            make_deck_card(divination(), quantity=4),
            make_deck_card(grizzly_bears(), quantity=36),
        ]
        by_category = {signal.category: signal for signal in redundancy_signals(deck)}
        assert by_category[CARD_DRAW].opener_probability == probability_at_least(
            deck_size=40, copies=4, drawn=OPENING_HAND_SIZE
        )

    def test_quantity_aware_four_ofs_count_four(self) -> None:
        deck = [make_deck_card(doom_blade(), quantity=4)]
        by_category = {signal.category: signal for signal in redundancy_signals(deck)}
        assert by_category[INTERACTION].count == 4

    def test_empty_deck_returns_zeroed_signals_without_raising(self) -> None:
        for signal in redundancy_signals([]):
            assert signal.count == 0
            assert signal.opener_probability == 0.0

    def test_sideboard_cards_are_not_filtered(self) -> None:
        deck = [make_deck_card(sol_ring(), quantity=2, sideboard=True)]
        by_category = {signal.category: signal for signal in redundancy_signals(deck)}
        assert by_category[RAMP].count == 2

    def test_result_shape_is_frozen(self) -> None:
        signal = redundancy_signals([])[0]
        with pytest.raises(dataclasses.FrozenInstanceError):
            signal.count = 99  # type: ignore[misc]

    def test_determinism_two_calls_equal(self) -> None:
        deck = [
            make_deck_card(sol_ring(), quantity=4),
            make_deck_card(divination(), quantity=2),
            make_deck_card(forest(), quantity=20),
        ]
        assert redundancy_signals(deck) == redundancy_signals(list(deck))


# ---------------------------------------------------------------------------
# FR7 interaction detail (AC5)
# ---------------------------------------------------------------------------


class TestInteractionSignals:
    def test_mixed_suite_counts_and_ratio(self) -> None:
        # 4 instants + 2 sorcery wipes + 2 flash-creature removal = 8 interaction,
        # of which 4 + 2 (flash) = 6 are instant-speed → ratio 0.75.
        deck = [
            make_deck_card(lightning_bolt(), quantity=4),
            make_deck_card(day_of_judgment(), quantity=2),
            make_deck_card(ambush_removal(), quantity=2),
            make_deck_card(grizzly_bears(), quantity=10),  # not interaction
        ]
        signals = interaction_signals(deck)
        assert signals.count == 8
        assert signals.instant_speed_count == 6
        assert signals.instant_speed_ratio == pytest.approx(6 / 8)

    def test_count_matches_classify_deck_interaction_count(self) -> None:
        deck = [
            make_deck_card(lightning_bolt(), quantity=4),
            make_deck_card(day_of_judgment(), quantity=2),
        ]
        assert interaction_signals(deck).count == classify_deck(deck)[INTERACTION].count

    def test_flash_creature_with_removal_text_counts_instant_speed(self) -> None:
        signals = interaction_signals([make_deck_card(ambush_removal())])
        assert signals.count == 1
        assert signals.instant_speed_count == 1
        assert signals.instant_speed_ratio == 1.0

    def test_sorcery_speed_interaction_is_not_instant_speed(self) -> None:
        signals = interaction_signals([make_deck_card(day_of_judgment(), quantity=3)])
        assert signals.count == 3
        assert signals.instant_speed_count == 0
        assert signals.instant_speed_ratio == 0.0

    def test_ratio_is_zero_on_zero_interaction(self) -> None:
        # Documented convention — never NaN, never raises.
        assert interaction_signals([]).instant_speed_ratio == 0.0
        no_interaction = [make_deck_card(grizzly_bears(), quantity=20)]
        assert interaction_signals(no_interaction).instant_speed_ratio == 0.0

    def test_cmc_distribution_sorted_and_quantity_aware(self) -> None:
        deck = [
            make_deck_card(day_of_judgment(), quantity=2),  # bucket 4
            make_deck_card(lightning_bolt(), quantity=4),  # bucket 1
            make_deck_card(doom_blade(), quantity=3),  # bucket 2
        ]
        signals = interaction_signals(deck)
        assert signals.cmc_distribution == ((1, 4), (2, 3), (4, 2))

    def test_non_interaction_cards_are_excluded_from_distribution(self) -> None:
        deck = [
            make_deck_card(lightning_bolt(), quantity=2),
            make_deck_card(grizzly_bears(), quantity=4),  # cmc 2, not interaction
        ]
        assert interaction_signals(deck).cmc_distribution == ((1, 2),)

    def test_empty_deck_returns_zeroed_signals_without_raising(self) -> None:
        signals = interaction_signals([])
        assert signals == InteractionSignals(
            count=0,
            instant_speed_count=0,
            instant_speed_ratio=0.0,
            cmc_distribution=(),
        )

    def test_sideboard_cards_are_not_filtered(self) -> None:
        deck = [make_deck_card(lightning_bolt(), quantity=2, sideboard=True)]
        assert interaction_signals(deck).count == 2

    def test_determinism_two_calls_equal(self) -> None:
        deck = [
            make_deck_card(lightning_bolt(), quantity=4),
            make_deck_card(ambush_removal(), quantity=2),
        ]
        assert interaction_signals(deck) == interaction_signals(list(deck))


# ---------------------------------------------------------------------------
# FR9 structural gaps (AC6)
# ---------------------------------------------------------------------------


def commander_deck_at_baselines() -> list:
    """A deck sitting exactly AT every commander baseline (no tokens fire)."""
    baselines = STRUCTURAL_GAP_BASELINES["commander"]
    return [
        make_deck_card(sol_ring(), quantity=baselines[RAMP]),
        make_deck_card(divination(), quantity=baselines[CARD_DRAW]),
        make_deck_card(doom_blade(), quantity=baselines[INTERACTION]),
        make_deck_card(oracle_wincon(), quantity=1),
    ]


class TestStructuralGaps:
    def test_token_vocabulary_is_closed_and_bytewise_sorted(self) -> None:
        assert STRUCTURAL_GAP_TOKENS == (
            CARD_DRAW_BELOW_BASELINE,
            INTERACTION_BELOW_BASELINE,
            RAMP_BELOW_BASELINE,
            WINCON_MISSING,
        )
        assert list(STRUCTURAL_GAP_TOKENS) == sorted(STRUCTURAL_GAP_TOKENS)

    def test_tokens_are_count_free_snake_case(self) -> None:
        # AD-6: tokens never embed counts or phrases.
        for token in STRUCTURAL_GAP_TOKENS:
            assert token == token.lower()
            assert not any(character.isdigit() for character in token)
            assert " " not in token

    def test_deck_at_every_commander_baseline_emits_no_tokens(self) -> None:
        assert structural_gaps(commander_deck_at_baselines(), formula="commander") == ()

    @pytest.mark.parametrize(
        ("category", "token"),
        [
            (RAMP, RAMP_BELOW_BASELINE),
            (CARD_DRAW, CARD_DRAW_BELOW_BASELINE),
            (INTERACTION, INTERACTION_BELOW_BASELINE),
        ],
    )
    def test_commander_token_flips_exactly_at_the_baseline(self, category: str, token: str) -> None:
        # Reference the module constant (provisional — 5.9 may move it): count == baseline
        # is NOT a gap; count == baseline - 1 is (strictly-less semantics).
        baselines = STRUCTURAL_GAP_BASELINES["commander"]
        fixtures = {RAMP: sol_ring, CARD_DRAW: divination, INTERACTION: doom_blade}

        def deck_with(count: int) -> list:
            rows = [
                make_deck_card(fixture(), quantity=baselines[cat] if cat != category else count)
                for cat, fixture in fixtures.items()
            ]
            return [*rows, make_deck_card(oracle_wincon(), quantity=1)]

        assert token not in structural_gaps(deck_with(baselines[category]), formula="commander")
        assert token in structural_gaps(deck_with(baselines[category] - 1), formula="commander")

    def test_sixty_card_table_flips_at_its_own_baselines(self) -> None:
        # The 5.4 review lesson: exercise BOTH formula tables.
        baselines = STRUCTURAL_GAP_BASELINES["sixty_card"]
        deck = [
            make_deck_card(divination(), quantity=baselines[CARD_DRAW] - 1),
            make_deck_card(doom_blade(), quantity=baselines[INTERACTION]),
            make_deck_card(oracle_wincon(), quantity=1),
        ]
        gaps = structural_gaps(deck, formula="sixty_card")
        assert CARD_DRAW_BELOW_BASELINE in gaps
        assert INTERACTION_BELOW_BASELINE not in gaps

    def test_sixty_card_zero_ramp_baseline_never_fires(self) -> None:
        # Ramp is not a structural requirement in 60-card decks (baseline 0).
        assert STRUCTURAL_GAP_BASELINES["sixty_card"][RAMP] == 0
        deck = [
            make_deck_card(divination(), quantity=4),
            make_deck_card(doom_blade(), quantity=6),
            make_deck_card(oracle_wincon(), quantity=1),
        ]
        assert structural_gaps(deck, formula="sixty_card") == ()

    def test_wincon_missing_fires_only_when_all_three_wincon_tags_are_empty(self) -> None:
        without_wincon = [
            make_deck_card(sol_ring(), quantity=6),
            make_deck_card(divination(), quantity=6),
            make_deck_card(doom_blade(), quantity=6),
        ]
        assert WINCON_MISSING in structural_gaps(without_wincon, formula="commander")
        with_wincon = [*without_wincon, make_deck_card(oracle_wincon(), quantity=1)]
        assert WINCON_MISSING not in structural_gaps(with_wincon, formula="commander")

    def test_finisher_counts_as_a_wincon(self) -> None:
        # Any WINCON_* tag clears the union check — an evasive finisher is enough.
        finisher = make_card(
            name="Inkwell Leviathan",
            type_line="Artifact Creature — Leviathan",
            mana_cost="{7}{U}{U}",
            cmc=9.0,
            oracle_text="Islandwalk\nThis creature can't be blocked.",
            power="7",
            toughness="11",
        )
        deck = [make_deck_card(finisher, quantity=1)]
        assert WINCON_MISSING not in structural_gaps(deck, formula="commander")

    def test_empty_deck_emits_below_baseline_tokens_without_raising(self) -> None:
        # Commander: all three below-baseline tokens + wincon_missing; sixty_card: the
        # zero ramp baseline means the ramp token cannot fire even on an empty deck.
        assert structural_gaps([], formula="commander") == STRUCTURAL_GAP_TOKENS
        assert structural_gaps([], formula="sixty_card") == (
            CARD_DRAW_BELOW_BASELINE,
            INTERACTION_BELOW_BASELINE,
            WINCON_MISSING,
        )

    def test_output_is_sorted_bytewise(self) -> None:
        gaps = structural_gaps([], formula="commander")
        assert list(gaps) == sorted(gaps)

    def test_sideboard_cards_are_not_filtered(self) -> None:
        # A sideboard wincon still clears wincon_missing (caller filters if unwanted).
        deck = [make_deck_card(oracle_wincon(), quantity=1, sideboard=True)]
        assert WINCON_MISSING not in structural_gaps(deck, formula="commander")

    def test_determinism_two_calls_equal(self) -> None:
        deck = commander_deck_at_baselines()
        assert structural_gaps(deck, formula="commander") == structural_gaps(
            list(deck), formula="commander"
        )


# ---------------------------------------------------------------------------
# Result-shape guards (AC1)
# ---------------------------------------------------------------------------


class TestResultShapes:
    def test_interaction_signals_is_frozen(self) -> None:
        signals = interaction_signals([])
        with pytest.raises(dataclasses.FrozenInstanceError):
            signals.count = 5  # type: ignore[misc]

    def test_redundancy_signal_shape(self) -> None:
        signal = redundancy_signals([])[0]
        assert isinstance(signal, RedundancySignal)
        assert signal.category in CATEGORIES

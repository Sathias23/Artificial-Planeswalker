"""Offline unit tests for the Story 5.9 scorer module (AC4/AC8/AC11 matrix).

Pins the composition equalities (``score()`` fields equal the composed calls run
manually), the rubric fork (floor/cedh only under ``brackets``; everything else
rubric-invariant), the AC3 commander-parity trigger semantics, the fixed
``CoreAssessment`` shape, empty-input zero-safety, determinism/non-mutation, and the
PRD §6 metric-4 literal-add monotonicity + diff-sensitivity properties that 5.7's
SWAP-based tests deferred here. Properties are deterministic parametrized loops over
distinct synthetic base decks — no ``hypothesis``, no DB, no marker.
"""

import dataclasses
from collections.abc import Sequence

import pytest

from src.data.schemas.combo import ComboRecord
from src.data.schemas.deck import DeckCard
from src.logic.assessment import (
    BASELINE_BRACKET_FLOOR,
    BRACKET_FLOOR_MAX,
    COMMANDER_PROFILE,
    INTERACTION,
    STANDARD_PROFILE,
    CoreAssessment,
    FormatProfile,
    aggregate_score,
    bracket_floor,
    classify_card,
    dimension_vector,
    game_changer_signal,
    match_combos,
    score,
    structural_gaps,
    tier_label,
)
from tests.fixtures.assessment import (
    make_combo_record,
    make_deck_card,
    make_draw_card,
    make_extra_turn_card,
    make_gc_card,
    make_interaction_card,
    make_land_card,
    make_mld_card,
    make_ramp_card,
    make_tutor_card,
    make_vanilla_card,
    make_wincon_card,
)

_PROFILES: dict[str, FormatProfile] = {
    "COMMANDER_PROFILE": COMMANDER_PROFILE,
    "STANDARD_PROFILE": STANDARD_PROFILE,
}


@pytest.fixture(params=sorted(_PROFILES), ids=sorted(_PROFILES))
def profile(request: pytest.FixtureRequest) -> FormatProfile:
    """Parametrize over both module-level profile constants."""
    return _PROFILES[str(request.param)]


# ---------------------------------------------------------------------------
# Synthetic base decks — >= 2 distinct shapes for the AC8 property loops
# ---------------------------------------------------------------------------


def _filler_rows(count: int, cmc: float = 2.0) -> list[DeckCard]:
    """``count`` distinct single-copy untagged filler rows."""
    return [make_deck_card(make_vanilla_card(name=f"Filler {i}", cmc=cmc)) for i in range(count)]


def _base_deck_lean() -> list[DeckCard]:
    """A lean low-curve deck: lands, filler, light draw + interaction."""
    return (
        [make_deck_card(make_land_card(), quantity=14)]
        + _filler_rows(12, cmc=1.0)
        + [
            make_deck_card(make_draw_card("Lean Draw", cmc=2.0)),
            make_deck_card(make_interaction_card("Lean Answer A", cmc=1.0)),
            make_deck_card(make_interaction_card("Lean Answer B", cmc=2.0)),
        ]
    )


def _base_deck_broad() -> list[DeckCard]:
    """A broader midrange deck: more categories populated, higher curve."""
    return (
        [make_deck_card(make_land_card("Broad Land"), quantity=17)]
        + _filler_rows(15, cmc=3.0)
        + [
            make_deck_card(make_ramp_card("Broad Rock")),
            make_deck_card(make_draw_card("Broad Draw A")),
            make_deck_card(make_draw_card("Broad Draw B", cmc=4.0)),
            make_deck_card(make_interaction_card("Broad Answer A")),
            make_deck_card(make_interaction_card("Broad Answer B", type_line="Sorcery", cmc=3.0)),
            make_deck_card(make_wincon_card("Broad Wincon")),
            make_deck_card(make_tutor_card("Broad Tutor")),
        ]
    )


_BASE_DECKS = {"broad": _base_deck_broad, "lean": _base_deck_lean}


@pytest.fixture(params=sorted(_BASE_DECKS), ids=sorted(_BASE_DECKS))
def base_deck(request: pytest.FixtureRequest) -> list[DeckCard]:
    """Parametrize the property loops over the distinct synthetic base decks."""
    return _BASE_DECKS[str(request.param)]()


def _rich_inputs() -> tuple[list[DeckCard], tuple[str, ...], tuple[ComboRecord, ...]]:
    """A deck + commanders + unmatched variants exercising every composed stage."""
    deck = _base_deck_broad() + [
        make_deck_card(make_vanilla_card("Combo Piece A", cmc=1.0)),
        make_deck_card(make_vanilla_card("Combo Piece B", cmc=1.0)),
        make_deck_card(make_gc_card("Rich GC", True)),
        make_deck_card(make_gc_card("Rich Unknown", None)),
    ]
    commanders = ("Broad Wincon",)
    variants = (
        make_combo_record(),  # both pieces present -> included
        make_combo_record(
            spellbook_id="2000-3000",
            cards=("Combo Piece A", "Missing Piece"),
            produces=("Card advantage",),
        ),  # one short -> almost_included
    )
    return deck, commanders, variants


def _score(
    deck: Sequence[DeckCard],
    profile: FormatProfile,
    commanders: Sequence[str] = (),
    variants: Sequence[ComboRecord] = (),
) -> CoreAssessment:
    return score(deck, commanders=commanders, variants=variants, profile=profile)


# ---------------------------------------------------------------------------
# AC11 — composition equalities
# ---------------------------------------------------------------------------


class TestCompositionEqualities:
    """score() fields equal the composed public calls run manually on the same inputs."""

    def test_fields_equal_manual_composition(self, profile: FormatProfile) -> None:
        deck, commanders, variants = _rich_inputs()
        assessment = score(deck, commanders=commanders, variants=variants, profile=profile)
        matched = match_combos(deck, commanders=commanders, variants=variants)
        assert assessment.combos == matched, (
            f"combos must equal match_combos output (same records, same order); "
            f"got {assessment.combos!r} vs {matched!r}"
        )
        vector = dimension_vector(deck, matched_combos=matched, profile=profile)
        assert assessment.vector == vector, (
            f"vector must equal dimension_vector on the matched combos; "
            f"got {assessment.vector} vs {vector}"
        )
        expected_score = aggregate_score(vector, profile=profile)
        assert assessment.for_format_score == expected_score, (
            f"for_format_score must equal aggregate_score(vector); "
            f"got {assessment.for_format_score} vs {expected_score}"
        )
        expected_tier = tier_label(expected_score, profile=profile)
        assert assessment.tier == expected_tier, (
            f"tier must equal tier_label(for_format_score); "
            f"got {assessment.tier} vs {expected_tier}"
        )
        assert assessment.game_changers == game_changer_signal(deck), (
            "game_changers must equal game_changer_signal on the same deck"
        )
        expected_gaps = structural_gaps(deck, formula=profile.karsten_formula)
        assert assessment.structural_gaps == expected_gaps, (
            f"structural_gaps must equal consistency.structural_gaps under the profile's "
            f"formula; got {assessment.structural_gaps} vs {expected_gaps}"
        )

    def test_matching_happens_inside(self, profile: FormatProfile) -> None:
        deck, commanders, variants = _rich_inputs()
        assessment = score(deck, commanders=commanders, variants=variants, profile=profile)
        buckets = {record.spellbook_id: record.bucket for record in assessment.combos}
        assert buckets == {"1000-2000": "included", "2000-3000": "almost_included"}, (
            f"score() must bucket the unmatched variants via match_combos; got {buckets}"
        )


# ---------------------------------------------------------------------------
# AC11 — rubric fork + AC4 rubric-swap invariance
# ---------------------------------------------------------------------------


class TestRubricFork:
    """Floor/cedh exist only under brackets; everything else is rubric-invariant."""

    def test_brackets_floor_from_signal(self) -> None:
        deck, commanders, variants = _rich_inputs()
        assessment = score(
            deck, commanders=commanders, variants=variants, profile=COMMANDER_PROFILE
        )
        matched = match_combos(deck, commanders=commanders, variants=variants)
        signal = bracket_floor(deck, matched_combos=matched)
        assert assessment.bracket_floor == signal.floor, (
            f"bracket_floor must equal BracketFloorSignal.floor; "
            f"got {assessment.bracket_floor} vs {signal.floor}"
        )
        assert assessment.bracket_floor is not None, "brackets rubric must populate the floor"
        assert BASELINE_BRACKET_FLOOR <= assessment.bracket_floor <= BRACKET_FLOOR_MAX, (
            f"the floor must stay in {{2, 3, 4}}; got {assessment.bracket_floor}"
        )
        assert assessment.cedh_candidate == signal.cedh_candidate, (
            f"cedh_candidate must come from the signal; "
            f"got {assessment.cedh_candidate} vs {signal.cedh_candidate}"
        )

    def test_heuristic_only_floor_none_cedh_false(self) -> None:
        deck, commanders, variants = _rich_inputs()
        assessment = score(deck, commanders=commanders, variants=variants, profile=STANDARD_PROFILE)
        assert assessment.bracket_floor is None, (
            f"heuristic_only must never populate bracket_floor; got {assessment.bracket_floor}"
        )
        assert assessment.cedh_candidate is False, (
            f"heuristic_only must never flag cedh_candidate; got {assessment.cedh_candidate}"
        )

    def test_rubric_swap_changes_only_floor_and_cedh(self) -> None:
        deck, commanders, variants = _rich_inputs()
        swapped_profile = dataclasses.replace(COMMANDER_PROFILE, rubric="heuristic_only")
        brackets = score(deck, commanders=commanders, variants=variants, profile=COMMANDER_PROFILE)
        heuristic = score(deck, commanders=commanders, variants=variants, profile=swapped_profile)
        for field in (
            "vector",
            "for_format_score",
            "tier",
            "game_changers",
            "combos",
            "structural_gaps",
            "mass_land_denial",
            "extra_turn_chains",
        ):
            assert getattr(brackets, field) == getattr(heuristic, field), (
                f"rubric swap must not change {field!r}: "
                f"{getattr(brackets, field)!r} vs {getattr(heuristic, field)!r}"
            )
        assert brackets.bracket_floor is not None, "brackets side must populate the floor"
        assert heuristic.bracket_floor is None, "heuristic side must hold bracket_floor=None"
        assert heuristic.cedh_candidate is False, "heuristic side must hold cedh_candidate=False"


# ---------------------------------------------------------------------------
# AC3/AC11 — commander parity for the decide-once trigger booleans
# ---------------------------------------------------------------------------


def _trigger_deck() -> list[DeckCard]:
    """A deck WITH both triggers: one MLD card, an extra-turn chain (2 copies)."""
    return _filler_rows(6) + [
        make_deck_card(make_mld_card()),
        make_deck_card(make_extra_turn_card(), quantity=2),
    ]


class TestTriggerParity:
    """mass_land_denial / extra_turn_chains equal the BracketFloorSignal fields (AC3)."""

    @pytest.mark.parametrize(
        "deck_factory", [_trigger_deck, lambda: _filler_rows(6)], ids=["with", "without"]
    )
    def test_parity_with_bracket_floor_signal(self, deck_factory: object) -> None:
        deck = deck_factory()  # type: ignore[operator]
        assessment = _score(deck, COMMANDER_PROFILE)
        signal = bracket_floor(deck, matched_combos=())
        assert assessment.mass_land_denial == signal.mass_land_denial, (
            f"mass_land_denial must equal the signal's field; "
            f"got {assessment.mass_land_denial} vs {signal.mass_land_denial}"
        )
        assert assessment.extra_turn_chains == signal.extra_turn_chain, (
            f"extra_turn_chains must equal the signal's field; "
            f"got {assessment.extra_turn_chains} vs {signal.extra_turn_chain}"
        )

    def test_triggers_computed_under_heuristic_only(self) -> None:
        assessment = _score(_trigger_deck(), STANDARD_PROFILE)
        assert assessment.mass_land_denial is True, (
            "a Standard deck running mass land denial factually HAS it — the flag is "
            "explainability, not a bracket verdict"
        )
        assert assessment.extra_turn_chains is True, (
            "the extra-turn chain flag must be computed under heuristic_only too"
        )
        assert assessment.bracket_floor is None, (
            "bracket_floor=None is what says 'no bracket' — not suppressed trigger flags"
        )

    def test_single_extra_turn_is_not_a_chain(self, profile: FormatProfile) -> None:
        deck = _filler_rows(6) + [make_deck_card(make_extra_turn_card())]
        assessment = _score(deck, profile)
        assert assessment.extra_turn_chains is False, (
            "a single extra-turn card must never read as a chain (quantity-aware rule)"
        )


# ---------------------------------------------------------------------------
# AC3/AC11 — fixed shape
# ---------------------------------------------------------------------------

_EXPECTED_FIELDS = (
    "vector",
    "for_format_score",
    "tier",
    "bracket_floor",
    "cedh_candidate",
    "game_changers",
    "combos",
    "structural_gaps",
    "mass_land_denial",
    "extra_turn_chains",
)


class TestFixedShape:
    """CoreAssessment carries exactly the AC3 field set under both profiles."""

    def test_field_names_exact(self) -> None:
        field_names = tuple(field.name for field in dataclasses.fields(CoreAssessment))
        assert field_names == _EXPECTED_FIELDS, (
            f"CoreAssessment must carry exactly the AC3 fields in order; got {field_names}"
        )

    def test_all_fields_present_both_profiles(self, profile: FormatProfile) -> None:
        deck, commanders, variants = _rich_inputs()
        assessment = score(deck, commanders=commanders, variants=variants, profile=profile)
        for field in dataclasses.fields(CoreAssessment):
            assert hasattr(assessment, field.name), (
                f"field {field.name!r} must always be present (no format-conditional shape)"
            )

    def test_assessment_is_frozen(self, profile: FormatProfile) -> None:
        assessment = _score(_filler_rows(3), profile)
        with pytest.raises(dataclasses.FrozenInstanceError):
            assessment.for_format_score = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AC11 — empty inputs (zero-safe like every 5.3-5.8 primitive)
# ---------------------------------------------------------------------------


class TestEmptyInputs:
    """variants=(), commanders=(), and an empty deck all score without raising."""

    def test_empty_everything(self, profile: FormatProfile) -> None:
        assessment = _score((), profile)
        assert assessment.combos == (), (
            f"an empty deck with no variants must match no combos; got {assessment.combos!r}"
        )
        assert type(assessment.for_format_score) is int, (
            f"for_format_score must be an int even for an empty deck; "
            f"got {type(assessment.for_format_score).__name__}"
        )

    def test_empty_deck_commander_floor_baseline(self) -> None:
        assessment = _score((), COMMANDER_PROFILE)
        assert assessment.bracket_floor == BASELINE_BRACKET_FLOOR, (
            f"an empty deck must floor at the baseline under brackets; "
            f"got {assessment.bracket_floor}"
        )
        assert assessment.cedh_candidate is False, "an empty deck is never a cEDH candidate"

    def test_empty_variants_populated_deck(self, profile: FormatProfile) -> None:
        assessment = _score(_base_deck_broad(), profile)
        assert assessment.combos == (), (
            "variants=() must yield no matched combos and still score (NFR3 core side)"
        )


# ---------------------------------------------------------------------------
# AC4 — determinism & non-mutation
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Identical input -> equal CoreAssessment; inputs never mutated."""

    def test_repeat_calls_equal(self, profile: FormatProfile) -> None:
        deck, commanders, variants = _rich_inputs()
        first = score(deck, commanders=commanders, variants=variants, profile=profile)
        second = score(deck, commanders=commanders, variants=variants, profile=profile)
        assert first == second, "two calls on equal input must yield equal CoreAssessment"

    def test_input_order_irrelevant(self, profile: FormatProfile) -> None:
        deck, commanders, variants = _rich_inputs()
        forward = score(deck, commanders=commanders, variants=variants, profile=profile)
        reversed_call = score(
            list(reversed(deck)),
            commanders=tuple(reversed(commanders)),
            variants=tuple(reversed(variants)),
            profile=profile,
        )
        assert forward == reversed_call, (
            "shuffled deck/commanders/variants order must yield an identical CoreAssessment"
        )

    def test_inputs_not_mutated(self, profile: FormatProfile) -> None:
        deck, commanders, variants = _rich_inputs()
        deck_snapshot = list(deck)
        variants_snapshot = [record.model_copy() for record in variants]
        score(deck, commanders=commanders, variants=variants, profile=profile)
        assert deck == deck_snapshot, "deck_cards must never be mutated"
        assert list(variants) == variants_snapshot, (
            "variants must never be mutated (buckets must not be rewritten in place)"
        )
        assert all(record.bucket is None for record in variants), (
            "input variants must keep bucket=None after score()"
        )


# ---------------------------------------------------------------------------
# AC8 — literal-add monotonicity properties (PRD §6 metric 4)
# ---------------------------------------------------------------------------


class TestMonotonicityProperties:
    """Literal adds/cuts through score() — never weakened back to swaps."""

    def test_gc_add_never_lowers_floor(self, base_deck: list[DeckCard]) -> None:
        before = _score(base_deck, COMMANDER_PROFILE).bracket_floor
        grown = base_deck + [make_deck_card(make_gc_card("Added GC", True))]
        after = _score(grown, COMMANDER_PROFILE).bracket_floor
        assert before is not None and after is not None, "commander profile must floor both"
        assert after >= before, (
            f"appending a game_changer=True card must never lower bracket_floor: "
            f"{before} -> {after}"
        )

    def test_tutor_add_never_lowers_consistency(
        self, base_deck: list[DeckCard], profile: FormatProfile
    ) -> None:
        before = _score(base_deck, profile).vector.consistency
        grown = base_deck + [make_deck_card(make_tutor_card("Added Tutor", cmc=1.0))]
        after = _score(grown, profile).vector.consistency
        assert after >= before, (
            f"appending a tutor-tagged card must never lower consistency: {before} -> {after}"
        )

    def test_interaction_cut_never_raises_interaction(
        self, base_deck: list[DeckCard], profile: FormatProfile
    ) -> None:
        cut = [
            deck_card for deck_card in base_deck if INTERACTION not in classify_card(deck_card.card)
        ]
        assert len(cut) < len(base_deck), (
            "the base deck must contain interaction-tagged cards for this property"
        )
        before = _score(base_deck, profile).vector.interaction
        after = _score(cut, profile).vector.interaction
        assert after <= before, (
            f"removing ALL interaction-tagged cards must never raise interaction: "
            f"{before} -> {after}"
        )

    def test_diff_sensitivity_second_piece(self, base_deck: list[DeckCard]) -> None:
        variant = make_combo_record()
        with_a = base_deck + [make_deck_card(make_vanilla_card("Combo Piece A", cmc=1.0))]
        before = score(with_a, commanders=(), variants=(variant,), profile=COMMANDER_PROFILE)
        assert before.combos and before.combos[0].bucket == "almost_included", (
            f"piece A only must match almost_included; got {before.combos!r}"
        )
        with_ab = with_a + [make_deck_card(make_vanilla_card("Combo Piece B", cmc=1.0))]
        after = score(with_ab, commanders=(), variants=(variant,), profile=COMMANDER_PROFILE)
        assert after.combos and after.combos[0].bucket == "included", (
            f"adding piece B must complete the combo to included; got {after.combos!r}"
        )
        assert after.vector.combo_potential > before.vector.combo_potential, (
            f"adding the completing piece must STRICTLY raise combo_potential: "
            f"{before.vector.combo_potential} -> {after.vector.combo_potential}"
        )
        assert before.bracket_floor is not None and after.bracket_floor is not None, (
            "commander profile must floor both sides of the diff"
        )
        assert after.bracket_floor >= before.bracket_floor, (
            f"adding the completing piece must never lower bracket_floor: "
            f"{before.bracket_floor} -> {after.bracket_floor}"
        )

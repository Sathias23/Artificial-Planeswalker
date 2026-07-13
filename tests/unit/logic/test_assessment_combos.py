"""Offline unit tests for the Story 5.6 combo seam (AC8 matrix).

Covers the frozen ``ComboRecord`` shape, the pure matcher's buckets / name
normalization / commander policy / determinism, the ``BRACKET_TAG_TO_BRACKET``
totality, the derived ``combo_type`` / ``earliest_turn_estimate`` helpers, and the
degradation edges. Schema tests for ``ComboRecord`` live here (this story's seam),
not in ``tests/unit/data/test_schemas.py``. No DB, no network, no markers — part of
the ``-m "not integration"`` fast subset.
"""

from typing import get_args

import pytest
from pydantic import ValidationError

from src.data.schemas.combo import ComboBracketTag, ComboBucket, ComboRecord
from src.data.schemas.deck import DeckCard
from src.logic.assessment.combos import (
    BRACKET_TAG_TO_BRACKET,
    COMBO_TYPE_TOKENS,
    MULTI_CARD_INFINITE,
    NON_INFINITE,
    TWO_CARD_INFINITE,
    combo_type,
    earliest_turn_estimate,
    match_combos,
)
from tests.fixtures.assessment import make_card, make_combo_record, make_deck_card


def _deck_card(name: str, quantity: int = 1, cmc: float = 1.0, sideboard: bool = False) -> DeckCard:
    """Build a DeckCard whose card has the given name/cmc — the matcher's only inputs."""
    return make_deck_card(make_card(name=name, cmc=cmc), quantity=quantity, sideboard=sideboard)


class TestComboRecordShape:
    """AC1/AC2: frozen single shape, normalized tuples, closed enums."""

    def test_frozen_assignment_raises(self) -> None:
        record = make_combo_record()
        with pytest.raises(ValidationError):
            record.bucket = "included"  # type: ignore[misc]

    def test_cards_normalized_sorted_on_construction(self) -> None:
        record = make_combo_record(cards=("Zealous Piece", "Alpha Piece"))
        assert record.cards == (
            "Alpha Piece",
            "Zealous Piece",
        ), "cards must normalize to ascending bytewise order on construction"

    def test_produces_normalized_sorted_on_construction(self) -> None:
        record = make_combo_record(produces=("Infinite mana", "Infinite draw"))
        assert record.produces == (
            "Infinite draw",
            "Infinite mana",
        ), "produces must normalize to ascending bytewise order on construction"

    def test_duplicate_piece_names_preserved(self) -> None:
        record = make_combo_record(cards=("Twin Piece", "Twin Piece"))
        assert record.cards == (
            "Twin Piece",
            "Twin Piece",
        ), "multiplicity-inclusive piece list must keep duplicates"

    def test_cards_is_immutable_tuple(self) -> None:
        record = make_combo_record()
        assert isinstance(record.cards, tuple), "cards must be a tuple, never a list"
        assert isinstance(record.produces, tuple), "produces must be a tuple, never a list"

    def test_unknown_bracket_tag_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_combo_record(bracket_tag="MYTHIC")

    def test_unknown_bucket_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_combo_record(bucket="matched")

    def test_bucket_defaults_none(self) -> None:
        record = ComboRecord(
            spellbook_id="1-2",
            cards=("A", "B"),
            commander_required=False,
            bracket_tag="CASUAL",
            produces=("Infinite mana",),
        )
        assert record.bucket is None, "bucket must default to None (the stored/repo state)"
        assert record.popularity is None, "popularity must default to None"

    def test_bucket_literal_is_closed(self) -> None:
        assert set(get_args(ComboBucket)) == {
            "included",
            "almost_included",
        }, "ComboBucket must hold exactly the two AD-11 bucket tokens"


class TestMatcherBuckets:
    """AC3: shortfall buckets, quantity awareness."""

    def test_all_pieces_present_is_included(self) -> None:
        deck = [_deck_card("Combo Piece A"), _deck_card("Combo Piece B")]
        matched = match_combos(deck, commanders=(), variants=(make_combo_record(),))
        assert len(matched) == 1, "variant 1000-2000 with all pieces present must match"
        assert matched[0].bucket == "included", "zero shortfall must bucket as included"

    def test_exactly_one_missing_is_almost_included(self) -> None:
        deck = [_deck_card("Combo Piece A")]
        matched = match_combos(deck, commanders=(), variants=(make_combo_record(),))
        assert len(matched) == 1, "variant 1000-2000 missing one piece must still match"
        assert matched[0].bucket == "almost_included", (
            "a shortfall of exactly 1 must bucket as almost_included"
        )

    def test_two_missing_is_excluded(self) -> None:
        deck = [_deck_card("Unrelated Card")]
        matched = match_combos(deck, commanders=(), variants=(make_combo_record(),))
        assert matched == (), "variant 1000-2000 with 2 missing pieces must be excluded"

    def test_quantity_shortfall_needs_two_has_one(self) -> None:
        variant = make_combo_record(cards=("Twin Piece", "Twin Piece"))
        deck = [_deck_card("Twin Piece", quantity=1)]
        matched = match_combos(deck, commanders=(), variants=(variant,))
        assert len(matched) == 1, "needing 2x with 1 in deck is a shortfall of 1, not exclusion"
        assert matched[0].bucket == "almost_included", (
            "quantity-aware shortfall of 1 must bucket as almost_included"
        )

    def test_quantity_satisfied_needs_two_has_two(self) -> None:
        variant = make_combo_record(cards=("Twin Piece", "Twin Piece"))
        deck = [_deck_card("Twin Piece", quantity=2)]
        matched = match_combos(deck, commanders=(), variants=(variant,))
        assert len(matched) == 1, "needing 2x with quantity 2 in deck must match"
        assert matched[0].bucket == "included", "quantity 2 covers a 2x need — included"

    def test_matched_record_is_same_shape_and_input_unmutated(self) -> None:
        variant = make_combo_record()
        deck = [_deck_card("Combo Piece A"), _deck_card("Combo Piece B")]
        matched = match_combos(deck, commanders=(), variants=(variant,))
        assert isinstance(matched[0], ComboRecord), (
            "matcher output must be ComboRecord — no parallel MatchedCombo type (AD-11)"
        )
        assert variant.bucket is None, "input variant must never be mutated"
        assert matched[0].spellbook_id == variant.spellbook_id, (
            "model_copy must carry all non-bucket fields verbatim"
        )


class TestNameNormalization:
    """AC3: lowercased comparison, DFC front-face indexing."""

    def test_case_insensitive_match(self) -> None:
        variant = make_combo_record(cards=("lightning bolt", "storm crow"))
        deck = [_deck_card("Lightning Bolt"), _deck_card("STORM CROW")]
        matched = match_combos(deck, commanders=(), variants=(variant,))
        assert len(matched) == 1, "name comparison must be case-insensitive"
        assert matched[0].bucket == "included", "case-folded names must fully match"

    def test_dfc_front_face_matches(self) -> None:
        variant = make_combo_record(cards=("Alive", "Combo Piece B"))
        deck = [_deck_card("Alive // Well"), _deck_card("Combo Piece B")]
        matched = match_combos(deck, commanders=(), variants=(variant,))
        assert len(matched) == 1, (
            "a deck 'A // B' DFC must match a variant naming just the front face 'A'"
        )
        assert matched[0].bucket == "included", "front-face indexing must count as available"


class TestCommanderPolicy:
    """AC3: zone requirement — satisfied via commanders list or excluded entirely."""

    def test_commander_required_empty_commanders_excluded(self) -> None:
        variant = make_combo_record(commander_required=True)
        deck = [_deck_card("Combo Piece A"), _deck_card("Combo Piece B")]
        matched = match_combos(deck, commanders=(), variants=(variant,))
        assert matched == (), (
            "commander_required with no resolved commanders must exclude the variant (FR25)"
        )

    def test_commander_required_commander_is_piece_matches(self) -> None:
        variant = make_combo_record(commander_required=True)
        deck = [_deck_card("Combo Piece A"), _deck_card("Combo Piece B")]
        matched = match_combos(deck, commanders=("Combo Piece A",), variants=(variant,))
        assert len(matched) == 1, "a commander among the variant's pieces satisfies the gate"
        assert matched[0].bucket == "included", "gate satisfied + all pieces present → included"

    def test_commander_required_commander_not_a_piece_excluded(self) -> None:
        variant = make_combo_record(commander_required=True)
        deck = [_deck_card("Combo Piece A"), _deck_card("Combo Piece B")]
        matched = match_combos(deck, commanders=("Unrelated Commander",), variants=(variant,))
        assert matched == (), (
            "commander_required with no piece among the commanders must exclude the variant"
        )

    def test_commander_comparison_is_case_insensitive(self) -> None:
        variant = make_combo_record(commander_required=True)
        deck = [_deck_card("Combo Piece A"), _deck_card("Combo Piece B")]
        matched = match_combos(deck, commanders=("COMBO PIECE A",), variants=(variant,))
        assert len(matched) == 1, "commander names must be compared lowercased"

    def test_commander_gate_does_not_add_availability(self) -> None:
        variant = make_combo_record(commander_required=True)
        deck = [_deck_card("Combo Piece B")]
        matched = match_combos(deck, commanders=("Combo Piece A",), variants=(variant,))
        assert len(matched) == 1, "gate satisfied; shortfall computed from deck rows only"
        assert matched[0].bucket == "almost_included", (
            "the commander gate is availability-neutral — a piece not among deck rows "
            "is still a shortfall"
        )

    def test_commander_not_required_ignores_commanders(self) -> None:
        variant = make_combo_record(commander_required=False)
        deck = [_deck_card("Combo Piece A"), _deck_card("Combo Piece B")]
        matched = match_combos(deck, commanders=("Unrelated Commander",), variants=(variant,))
        assert len(matched) == 1, "commander_required=False must ignore commanders entirely"
        assert matched[0].bucket == "included", "non-commander variant matches on deck alone"


class TestDeterminism:
    """AC3: spellbook_id-sorted output, identical input → identical output."""

    def test_output_sorted_by_spellbook_id(self) -> None:
        deck = [_deck_card("Combo Piece A"), _deck_card("Combo Piece B")]
        variants = (
            make_combo_record(spellbook_id="9999-1"),
            make_combo_record(spellbook_id="1111-1"),
            make_combo_record(spellbook_id="5555-1"),
        )
        matched = match_combos(deck, commanders=(), variants=variants)
        ids = tuple(record.spellbook_id for record in matched)
        assert ids == (
            "1111-1",
            "5555-1",
            "9999-1",
        ), "output must be sorted ascending bytewise by spellbook_id regardless of input order"

    def test_identical_input_yields_identical_output(self) -> None:
        deck = [_deck_card("Combo Piece A")]
        variants = (
            make_combo_record(spellbook_id="2-1"),
            make_combo_record(spellbook_id="1-1"),
        )
        first = match_combos(deck, commanders=(), variants=variants)
        second = match_combos(deck, commanders=(), variants=variants)
        assert first == second, "two calls on equal input must yield equal output"

    def test_inputs_not_mutated(self) -> None:
        deck = [_deck_card("Combo Piece A"), _deck_card("Combo Piece B")]
        variants = [make_combo_record(spellbook_id="3-1")]
        match_combos(deck, commanders=(), variants=variants)
        assert variants[0].bucket is None, "input variants must keep bucket=None after matching"
        assert len(deck) == 2, "deck_cards input must not be modified"


class TestBracketMap:
    """AC4: exact six pairs, total over the closed enum."""

    def test_exact_pairs_pinned(self) -> None:
        assert BRACKET_TAG_TO_BRACKET == {
            "CASUAL": 1,
            "ODDBALL": 2,
            "PRECON_APPROPRIATE": 2,
            "POWERFUL": 3,
            "SPICY": 3,
            "RUTHLESS": 4,
        }, "the combo→bracket map must pin exactly the six addendum §C pairs"

    def test_map_is_total_over_the_literal(self) -> None:
        assert set(BRACKET_TAG_TO_BRACKET) == set(get_args(ComboBracketTag)), (
            "BRACKET_TAG_TO_BRACKET keys must equal the ComboBracketTag Literal values — "
            "a future seventh tag cannot be silently unmapped"
        )


class TestComboType:
    """AC5: closed derived-type tokens."""

    def test_two_piece_infinite(self) -> None:
        combo = make_combo_record(cards=("A", "B"), produces=("Infinite mana",))
        assert combo_type(combo) == TWO_CARD_INFINITE, (
            "2 pieces + infinite produces must derive two_card_infinite"
        )

    def test_three_piece_infinite(self) -> None:
        combo = make_combo_record(cards=("A", "B", "C"), produces=("Infinite mana",))
        assert combo_type(combo) == MULTI_CARD_INFINITE, (
            "3 pieces + infinite produces must derive multi_card_infinite"
        )

    def test_non_infinite(self) -> None:
        combo = make_combo_record(produces=("Win the game",))
        assert combo_type(combo) == NON_INFINITE, (
            "produces without an 'infinite' entry must derive non_infinite"
        )

    def test_infinite_detection_is_case_insensitive(self) -> None:
        combo = make_combo_record(produces=("INFINITE storm count",))
        assert combo_type(combo) == TWO_CARD_INFINITE, (
            "the 'infinite' substring check must be case-insensitive"
        )

    def test_token_tuple_closed_and_sorted(self) -> None:
        assert COMBO_TYPE_TOKENS == (
            MULTI_CARD_INFINITE,
            NON_INFINITE,
            TWO_CARD_INFINITE,
        ), "COMBO_TYPE_TOKENS must hold exactly the three tokens"
        assert COMBO_TYPE_TOKENS == tuple(sorted(COMBO_TYPE_TOKENS)), (
            "COMBO_TYPE_TOKENS must be defined already bytewise-sorted"
        )


class TestEarliestTurnEstimate:
    """AC5: the documented v1 one-land-per-turn model — verify-by-shape pins."""

    def test_two_two_cost_pieces(self) -> None:
        # Docstring worked example: pieces (2, 2) → total 4, max 2 → T=3 (T=2: 3 < 4).
        combo = make_combo_record(cards=("Alpha", "Beta"))
        deck = [_deck_card("Alpha", cmc=2.0), _deck_card("Beta", cmc=2.0)]
        assert earliest_turn_estimate(combo, deck) == 3, "pieces (2, 2) must estimate turn 3"

    def test_two_one_cost_pieces(self) -> None:
        # Docstring worked example: pieces (1, 1) → T=2 (T=1: 1 < 2).
        combo = make_combo_record(cards=("Alpha", "Beta"))
        deck = [_deck_card("Alpha", cmc=1.0), _deck_card("Beta", cmc=1.0)]
        assert earliest_turn_estimate(combo, deck) == 2, "pieces (1, 1) must estimate turn 2"

    def test_single_six_cost_piece(self) -> None:
        # Docstring worked example: pieces (6,) → T=6 (must cast the biggest piece).
        combo = make_combo_record(cards=("Alpha",))
        deck = [_deck_card("Alpha", cmc=6.0)]
        assert earliest_turn_estimate(combo, deck) == 6, "pieces (6,) must estimate turn 6"

    def test_zero_resolvable_pieces_floor(self) -> None:
        combo = make_combo_record(cards=("Alpha", "Beta"))
        assert earliest_turn_estimate(combo, []) == 1, (
            "a combo with zero resolvable pieces must return the floor 1, never raise"
        )

    def test_unresolvable_piece_skipped(self) -> None:
        # The missing almost_included piece is skipped — documented optimistic undercount.
        combo = make_combo_record(cards=("Alpha", "Beta", "Missing Piece"))
        deck = [_deck_card("Alpha", cmc=2.0), _deck_card("Beta", cmc=2.0)]
        assert earliest_turn_estimate(combo, deck) == 3, (
            "unresolvable pieces must be skipped from the sum (optimistic undercount)"
        )

    def test_fractional_cmc_ceils_to_int(self) -> None:
        combo = make_combo_record(cards=("Alpha",))
        deck = [_deck_card("Alpha", cmc=2.5)]
        estimate = earliest_turn_estimate(combo, deck)
        assert estimate == 3, "fractional cmc must ceil before comparison (2.5 → 3)"
        assert isinstance(estimate, int), "the estimate must be an int"

    def test_monotonic_adding_expensive_piece_never_lowers(self) -> None:
        base = make_combo_record(cards=("Alpha", "Beta"))
        bigger = make_combo_record(cards=("Alpha", "Beta", "Gamma"))
        deck = [
            _deck_card("Alpha", cmc=2.0),
            _deck_card("Beta", cmc=2.0),
            _deck_card("Gamma", cmc=6.0),
        ]
        assert earliest_turn_estimate(bigger, deck) >= earliest_turn_estimate(base, deck), (
            "adding a more expensive piece must never lower the estimate"
        )

    def test_dfc_front_face_cmc_join(self) -> None:
        combo = make_combo_record(cards=("Alive",))
        deck = [_deck_card("Alive // Well", cmc=2.0)]
        assert earliest_turn_estimate(combo, deck) == 2, (
            "the name→cmc join must use the same front-face normalization as the matcher"
        )


class TestEdges:
    """AC8 edges: empty inputs, sideboard availability."""

    def test_empty_variants_returns_empty_tuple(self) -> None:
        deck = [_deck_card("Combo Piece A")]
        assert match_combos(deck, commanders=(), variants=()) == (), "empty variants must return ()"

    def test_empty_deck_one_piece_variant_almost_included(self) -> None:
        variant = make_combo_record(cards=("Solo Piece",))
        matched = match_combos([], commanders=(), variants=(variant,))
        assert len(matched) == 1, "an empty deck leaves a 1-piece variant one short — matched"
        assert matched[0].bucket == "almost_included", (
            "1-piece variant against an empty deck must bucket as almost_included"
        )

    def test_empty_deck_two_piece_variant_excluded(self) -> None:
        matched = match_combos([], commanders=(), variants=(make_combo_record(),))
        assert matched == (), "a 2-piece variant against an empty deck must be excluded"

    def test_sideboard_rows_count_toward_availability(self) -> None:
        # The standing 5.3/5.4/5.5 policy: sideboard rows are NOT filtered here —
        # deck-composition belongs to the caller/edge. Pin it so a regression is caught.
        deck = [
            _deck_card("Combo Piece A", sideboard=True),
            _deck_card("Combo Piece B", sideboard=True),
        ]
        matched = match_combos(deck, commanders=(), variants=(make_combo_record(),))
        assert len(matched) == 1, "sideboard=True rows must count toward availability"
        assert matched[0].bucket == "included", (
            "sideboard rows are not filtered — the caller owns deck composition"
        )


class TestPackageExports:
    """AC1/Task 5: the additive re-export surface."""

    def test_assessment_package_reexports(self) -> None:
        import src.logic.assessment as assessment

        for name in (
            "BRACKET_TAG_TO_BRACKET",
            "COMBO_TYPE_TOKENS",
            "MULTI_CARD_INFINITE",
            "NON_INFINITE",
            "TWO_CARD_INFINITE",
            "ComboBracketTag",
            "ComboBucket",
            "ComboRecord",
            "combo_type",
            "earliest_turn_estimate",
            "match_combos",
        ):
            assert name in assessment.__all__, f"{name} missing from assessment __all__"
            assert hasattr(assessment, name), f"{name} not importable from assessment package"

    def test_schemas_package_reexports(self) -> None:
        import src.data.schemas as schemas

        for name in ("ComboBracketTag", "ComboBucket", "ComboRecord"):
            assert name in schemas.__all__, f"{name} missing from schemas __all__"
            assert hasattr(schemas, name), f"{name} not importable from schemas package"

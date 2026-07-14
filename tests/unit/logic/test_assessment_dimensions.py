"""Offline unit tests for the Story 5.7 dimensions module (AC8 matrix).

Verify-by-shape for the provisional mapping curves — clamps, fixed vector shape, and
monotone SWAP directions only (deck size held constant so hypergeometric denominators and
``avgMV`` cannot drown the intended direction; the literal "adding X" monotonicity
properties are Story 5.9's). Exact pins are reserved for derived facts: the Bracket floor
gates, the Game Changer three-state read, and the empty-deck ``combo_potential == 0``
anchor. The curve numbers themselves are Story 5.9's to tune (NFR8).
"""

import dataclasses
from collections.abc import Sequence
from typing import Any

import pytest

from src.data.schemas.combo import ComboRecord
from src.data.schemas.deck import DeckCard
from src.logic.assessment import (
    BASELINE_BRACKET_FLOOR,
    BRACKET_FLOOR_MAX,
    CEDH_TUTOR_MIN,
    COMMANDER_PROFILE,
    DIMENSIONS,
    EXTRA_TURN_CHAIN_MIN,
    GC_BRACKET_FOUR_MIN,
    GC_BRACKET_THREE_MIN,
    STANDARD_PROFILE,
    BracketFloorSignal,
    DimensionVector,
    FormatProfile,
    GameChangerSignal,
    bracket_floor,
    dimension_vector,
    game_changer_signal,
)
from tests.fixtures.assessment import make_card, make_combo_record, make_deck_card

_PROFILES: dict[str, FormatProfile] = {
    "COMMANDER_PROFILE": COMMANDER_PROFILE,
    "STANDARD_PROFILE": STANDARD_PROFILE,
}


@pytest.fixture(params=sorted(_PROFILES), ids=sorted(_PROFILES))
def profile(request: pytest.FixtureRequest) -> FormatProfile:
    """Parametrize over both module-level profile constants."""
    return _PROFILES[str(request.param)]


# ---------------------------------------------------------------------------
# Card builders — every card sets game_changer EXPLICITLY where a GC test reads it
# (make_card's default omits it -> None, the AD-4 unknown state).
# ---------------------------------------------------------------------------


def _vanilla(name: str = "Vanilla Bear", cmc: float = 2.0, **overrides: Any) -> Any:
    """An untagged filler creature — matches no classifier category."""
    defaults: dict[str, Any] = {
        "name": name,
        "cmc": cmc,
        "mana_cost": "{2}",
        "type_line": "Creature — Bear",
        "oracle_text": "",
    }
    defaults.update(overrides)
    return make_card(**defaults)


def _land(name: str = "Barren Land") -> Any:
    """A colorless land (no colored sources, no ramp tag)."""
    return make_card(
        name=name, cmc=0.0, mana_cost="", type_line="Land", oracle_text="{T}: Add {C}."
    )


def _ramp(name: str = "Mana Rock", cmc: float = 2.0) -> Any:
    """A RAMP-tagged non-land mana producer."""
    return make_card(
        name=name, cmc=cmc, mana_cost="{2}", type_line="Artifact", oracle_text="{T}: Add {C}{C}."
    )


def _tutor(name: str = "Grim Tutor Copy", cmc: float = 2.0) -> Any:
    """A TUTOR-tagged generic library search to hand."""
    return make_card(
        name=name,
        cmc=cmc,
        mana_cost="{2}",
        type_line="Sorcery",
        oracle_text="Search your library for a card, put it into your hand, then shuffle.",
    )


def _draw(name: str = "Divination Copy", cmc: float = 3.0) -> Any:
    """A CARD_DRAW-tagged spell."""
    return make_card(
        name=name, cmc=cmc, mana_cost="{3}", type_line="Sorcery", oracle_text="Draw two cards."
    )


def _interaction(
    name: str = "Doom Blade Copy", cmc: float = 2.0, type_line: str = "Instant"
) -> Any:
    """An INTERACTION-tagged removal spell (instant-speed unless overridden)."""
    return make_card(
        name=name,
        cmc=cmc,
        mana_cost="{2}",
        type_line=type_line,
        oracle_text="Destroy target creature.",
    )


def _wincon(name: str = "Lab Man Copy", cmc: float = 3.0) -> Any:
    """A WINCON_EXPLICIT-tagged card."""
    return make_card(
        name=name,
        cmc=cmc,
        mana_cost="{3}",
        type_line="Creature — Human Wizard",
        oracle_text="You win the game.",
    )


def _extra_turn(name: str = "Time Warp Copy", cmc: float = 5.0) -> Any:
    """An EXTRA_TURN-tagged spell."""
    return make_card(
        name=name,
        cmc=cmc,
        mana_cost="{5}",
        type_line="Sorcery",
        oracle_text="Take an extra turn after this one.",
    )


def _mld(name: str = "Armageddon Copy", cmc: float = 4.0) -> Any:
    """A MASS_LAND_DENIAL-tagged spell."""
    return make_card(
        name=name, cmc=cmc, mana_cost="{4}", type_line="Sorcery", oracle_text="Destroy all lands."
    )


def _gc(name: str, value: bool | None) -> Any:
    """An otherwise-untagged creature with an EXPLICIT game_changer state."""
    return _vanilla(name=name, game_changer=value)


def _gc_rows(count: int, value: bool | None) -> list[DeckCard]:
    """``count`` distinct single-copy rows with the given game_changer state."""
    return [make_deck_card(_gc(f"GC {value} {i}", value)) for i in range(count)]


def _filler_rows(count: int, cmc: float = 2.0) -> list[DeckCard]:
    """``count`` distinct single-copy untagged filler rows."""
    return [make_deck_card(_vanilla(name=f"Filler {i}", cmc=cmc)) for i in range(count)]


def _piece_rows(cmc: float) -> list[DeckCard]:
    """The two standard combo pieces ('Combo Piece A'/'B') at the given mana value."""
    return [
        make_deck_card(_vanilla(name="Combo Piece A", cmc=cmc)),
        make_deck_card(_vanilla(name="Combo Piece B", cmc=cmc)),
    ]


def _floor(
    deck_cards: Sequence[DeckCard], combos: Sequence[ComboRecord] = ()
) -> BracketFloorSignal:
    return bracket_floor(deck_cards, matched_combos=combos)


# ---------------------------------------------------------------------------
# AC8 — vector shape
# ---------------------------------------------------------------------------


class TestDimensionVectorShape:
    """Fixed closed shape, integer 0-100, both formats, degrade-not-raise (AC2)."""

    def test_field_names_equal_dimensions_in_order(self) -> None:
        field_names = tuple(field.name for field in dataclasses.fields(DimensionVector))
        assert field_names == DIMENSIONS, (
            f"DimensionVector fields must equal profiles.DIMENSIONS in order; got {field_names}"
        )

    def test_vector_is_frozen(self, profile: FormatProfile) -> None:
        vector = dimension_vector(_filler_rows(5), matched_combos=(), profile=profile)
        with pytest.raises(dataclasses.FrozenInstanceError):
            vector.speed = 0  # type: ignore[misc]

    def test_populated_deck_all_dimensions_int_in_range(self, profile: FormatProfile) -> None:
        deck = (
            _filler_rows(5)
            + _piece_rows(1.0)
            + [
                make_deck_card(_land(), quantity=10),
                make_deck_card(_ramp()),
                make_deck_card(_draw()),
                make_deck_card(_tutor()),
                make_deck_card(_interaction()),
                make_deck_card(_wincon()),
                make_deck_card(_gc("GC True populated", True)),
            ]
        )
        combos = (make_combo_record(bucket="included"),)
        vector = dimension_vector(deck, matched_combos=combos, profile=profile)
        for dimension in DIMENSIONS:
            value = getattr(vector, dimension)
            assert type(value) is int, (
                f"dimension {dimension!r} must be an int, got {type(value).__name__}"
            )
            assert 0 <= value <= 100, f"dimension {dimension!r} must be in [0, 100], got {value}"

    def test_empty_deck_yields_full_vector(self, profile: FormatProfile) -> None:
        vector = dimension_vector((), matched_combos=(), profile=profile)
        for dimension in DIMENSIONS:
            value = getattr(vector, dimension)
            assert type(value) is int and 0 <= value <= 100, (
                f"empty deck must still yield dimension {dimension!r} as int in [0, 100], "
                f"got {value!r}"
            )


# ---------------------------------------------------------------------------
# AC8 — Game Changer signal (AD-4 three-state)
# ---------------------------------------------------------------------------


class TestGameChangerSignal:
    """True/False/None stay distinct; quantity-aware; names sorted, unique, True-only (AC3)."""

    def test_three_states_stay_distinct(self) -> None:
        deck = [
            make_deck_card(_gc("Zzz True GC", True), quantity=3),
            make_deck_card(_gc("Confirmed Not GC", False), quantity=2),
            make_deck_card(_gc("Unknown GC", None), quantity=2),
        ]
        signal = game_changer_signal(deck)
        assert signal.known_count == 3, (
            f"known_count must count only game_changer=True copies, got {signal.known_count}"
        )
        assert signal.unknown_count == 2, (
            f"unknown_count must count only game_changer=None copies, got {signal.unknown_count}"
        )

    def test_none_never_counts_as_known(self) -> None:
        deck = [make_deck_card(_gc("Unknown Only", None), quantity=4)]
        signal = game_changer_signal(deck)
        assert signal.known_count == 0, (
            f"game_changer=None must NEVER contribute to known_count (AD-4), "
            f"got {signal.known_count}"
        )
        assert signal.unknown_count == 4, (
            f"unknown_count must be quantity-aware, got {signal.unknown_count}"
        )

    def test_names_sorted_unique_true_only(self) -> None:
        deck = [
            make_deck_card(_gc("Zeta GC", True)),
            make_deck_card(_gc("Zeta GC", True)),  # duplicate name -> one entry
            make_deck_card(_gc("Alpha GC", True)),
            make_deck_card(_gc("Not A GC", False)),
            make_deck_card(_gc("Unknown One", None)),
        ]
        signal = game_changer_signal(deck)
        assert signal.card_names == ("Alpha GC", "Zeta GC"), (
            f"card_names must be unique, bytewise-sorted, and True-only; got {signal.card_names}"
        )

    def test_signal_is_frozen(self) -> None:
        signal = game_changer_signal(())
        with pytest.raises(dataclasses.FrozenInstanceError):
            signal.known_count = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AC8 — Bracket floor gates, each branch
# ---------------------------------------------------------------------------


class TestBracketFloorGates:
    """Every AC4 gate, pinned exactly (derived facts, not provisional curves)."""

    def test_zero_gc_floor_is_baseline(self) -> None:
        signal = _floor(_gc_rows(3, False) + _filler_rows(3))
        assert signal.floor == BASELINE_BRACKET_FLOOR == 2, (
            f"0 Game Changers must keep the baseline floor 2, got {signal.floor}"
        )

    def test_one_gc_floor_three(self) -> None:
        signal = _floor(_gc_rows(GC_BRACKET_THREE_MIN, True))
        assert signal.floor == 3, f"1 Game Changer must floor at 3 (§C), got {signal.floor}"

    def test_three_gc_floor_three(self) -> None:
        signal = _floor(_gc_rows(3, True))
        assert signal.floor == 3, f"3 Game Changers must floor at 3 (§C), got {signal.floor}"

    def test_four_gc_floor_four(self) -> None:
        signal = _floor(_gc_rows(GC_BRACKET_FOUR_MIN, True))
        assert signal.floor == 4, f"4 Game Changers must floor at 4 (§C), got {signal.floor}"

    def test_gc_quantity_aware(self) -> None:
        signal = _floor([make_deck_card(_gc("Quad GC", True), quantity=4)])
        assert signal.floor == 4, (
            f"a 4-copy game_changer=True row must floor at 4 (quantity-aware), got {signal.floor}"
        )

    def test_mass_land_denial_floor_four(self) -> None:
        signal = _floor([make_deck_card(_mld())] + _filler_rows(2))
        assert signal.floor == 4, f"mass land denial must floor at 4, got {signal.floor}"
        assert signal.mass_land_denial is True, "mass_land_denial flag must be True"
        assert signal.mass_land_denial_names == ("Armageddon Copy",), (
            f"mass_land_denial_names must name the trigger card, "
            f"got {signal.mass_land_denial_names}"
        )

    def test_single_extra_turn_never_raises(self) -> None:
        signal = _floor([make_deck_card(_extra_turn())] + _filler_rows(2))
        assert signal.floor == BASELINE_BRACKET_FLOOR, (
            f"a single extra-turn card must never raise the floor, got {signal.floor}"
        )
        assert signal.extra_turn_chain is False, (
            "extra_turn_chain must be False below the chain threshold"
        )
        assert signal.extra_turn_names == ("Time Warp Copy",), (
            f"extra_turn_names must still name the card for explainability, "
            f"got {signal.extra_turn_names}"
        )

    def test_extra_turn_chain_floor_four(self) -> None:
        deck = [
            make_deck_card(_extra_turn("Time Warp Copy")),
            make_deck_card(_extra_turn("Temporal Mastery Copy", cmc=7.0)),
        ]
        assert EXTRA_TURN_CHAIN_MIN == 2, "chain threshold pinned by AC4 as 2 (provisional)"
        signal = _floor(deck)
        assert signal.floor == 4, (
            f"two extra-turn cards must floor at 4 (chain), got {signal.floor}"
        )
        assert signal.extra_turn_chain is True, "extra_turn_chain must be True at the threshold"
        assert signal.extra_turn_names == ("Temporal Mastery Copy", "Time Warp Copy"), (
            f"extra_turn_names must be sorted, got {signal.extra_turn_names}"
        )

    def test_extra_turn_chain_quantity_aware(self) -> None:
        signal = _floor([make_deck_card(_extra_turn(), quantity=2)])
        assert signal.floor == 4, (
            f"two copies of one extra-turn card must count as a chain, got {signal.floor}"
        )

    def test_included_early_two_card_infinite_floor_four(self) -> None:
        deck = _piece_rows(1.0)  # earliest turn 2 <= 6 -> early
        combo = make_combo_record(bucket="included")
        signal = _floor(deck, (combo,))
        assert signal.floor == 4, (
            f"an included early two-card infinite must floor at 4, got {signal.floor}"
        )
        assert signal.early_two_card_infinite is True, "early_two_card_infinite must be True"
        assert signal.early_two_card_infinite_ids == (combo.spellbook_id,), (
            f"the driving spellbook_id must be reported, got {signal.early_two_card_infinite_ids}"
        )

    def test_included_late_two_card_infinite_floor_three(self) -> None:
        deck = _piece_rows(7.0)  # earliest turn 7 > 6 -> late
        signal = _floor(deck, (make_combo_record(bucket="included"),))
        assert signal.floor == 3, (
            f"an included LATE two-card infinite must floor at 3, got {signal.floor}"
        )
        assert signal.early_two_card_infinite is False, (
            "early_two_card_infinite must be False for a late combo"
        )

    def test_one_gc_plus_late_infinite_still_three(self) -> None:
        deck = _gc_rows(1, True) + _piece_rows(7.0)
        signal = _floor(deck, (make_combo_record(bucket="included"),))
        assert signal.floor == 3, (
            f"1 GC + included late two-card infinite -> both gates say 3, got {signal.floor}"
        )

    def test_included_multi_card_infinite_floor_three(self) -> None:
        deck = _piece_rows(1.0) + [make_deck_card(_vanilla(name="Combo Piece C", cmc=1.0))]
        combo = make_combo_record(
            cards=("Combo Piece A", "Combo Piece B", "Combo Piece C"), bucket="included"
        )
        signal = _floor(deck, (combo,))
        assert signal.floor == 3, (
            f"an included multi-card infinite must floor at 3 (never the two-card trigger), "
            f"got {signal.floor}"
        )

    def test_included_ruthless_tag_floor_four(self) -> None:
        deck = _piece_rows(1.0)
        combo = make_combo_record(
            bucket="included", bracket_tag="RUTHLESS", produces=("Card advantage",)
        )
        signal = _floor(deck, (combo,))
        assert signal.floor == 4, (
            f"an included RUTHLESS combo must floor at 4 via BRACKET_TAG_TO_BRACKET, "
            f"got {signal.floor}"
        )

    def test_almost_included_never_raises(self) -> None:
        deck = _piece_rows(1.0)
        combo = make_combo_record(bucket="almost_included", bracket_tag="RUTHLESS")
        signal = _floor(deck, (combo,))
        assert signal.floor == BASELINE_BRACKET_FLOOR, (
            f"an almost_included combo must NEVER raise the floor (not in the deck), "
            f"got {signal.floor}"
        )

    def test_bucket_none_contributes_nothing(self) -> None:
        deck = _piece_rows(1.0)
        combo = make_combo_record(bucket=None, bracket_tag="RUTHLESS")
        signal = _floor(deck, (combo,))
        assert signal.floor == BASELINE_BRACKET_FLOOR, (
            f"a bucket=None record must contribute nothing to the floor, got {signal.floor}"
        )

    def test_floor_never_exceeds_max(self) -> None:
        deck = (
            _gc_rows(6, True)
            + _piece_rows(1.0)
            + [make_deck_card(_mld()), make_deck_card(_extra_turn(), quantity=3)]
        )
        combos = (
            make_combo_record(bucket="included", bracket_tag="RUTHLESS"),
            make_combo_record(spellbook_id="2000-3000", bucket="included"),
        )
        signal = _floor(deck, combos)
        assert signal.floor == BRACKET_FLOOR_MAX == 4, (
            f"the floor must cap at BRACKET_FLOOR_MAX=4 whatever stacks, got {signal.floor}"
        )

    def test_empty_deck_floor_baseline_all_flags_false(self) -> None:
        signal = _floor(())
        assert signal.floor == BASELINE_BRACKET_FLOOR == 2, (
            f"an empty deck must floor at the baseline 2, got {signal.floor}"
        )
        assert signal.mass_land_denial is False, "empty deck: mass_land_denial must be False"
        assert signal.extra_turn_chain is False, "empty deck: extra_turn_chain must be False"
        assert signal.early_two_card_infinite is False, (
            "empty deck: early_two_card_infinite must be False"
        )
        assert signal.cedh_candidate is False, "empty deck: cedh_candidate must be False"
        assert signal.game_changers == GameChangerSignal(
            known_count=0, card_names=(), unknown_count=0
        ), "empty deck: the nested GameChangerSignal must be zeroed"

    def test_signal_is_frozen(self) -> None:
        signal = _floor(())
        with pytest.raises(dataclasses.FrozenInstanceError):
            signal.floor = 5  # type: ignore[misc]

    def test_ad4_pin_unknowns_neither_raise_nor_lower(self) -> None:
        deck = _gc_rows(5, None)  # 5 unknowns, 0 confirmed
        signal = _floor(deck)
        assert signal.floor == BASELINE_BRACKET_FLOOR, (
            f"game_changer=None cards must not move the floor in either direction (AD-4), "
            f"got {signal.floor}"
        )
        assert signal.game_changers.unknown_count == 5, (
            f"the unknown count must still be reported, got {signal.game_changers.unknown_count}"
        )
        assert signal.game_changers.known_count == 0, (
            f"unknowns must not leak into known_count, got {signal.game_changers.known_count}"
        )


# ---------------------------------------------------------------------------
# AC8 — cEDH candidacy
# ---------------------------------------------------------------------------


def _cedh_deck(*, tutors: int = CEDH_TUTOR_MIN, piece_cmc: float = 1.0) -> list[DeckCard]:
    """A dense cEDH-shaped deck: 4 GC, cheap combo pieces, tutors, low curve."""
    deck = _gc_rows(4, True) + _piece_rows(piece_cmc)
    if tutors:
        deck.append(make_deck_card(_tutor(cmc=1.0), quantity=tutors))
    return deck


class TestCedhCandidacy:
    """Candidacy flagged, never asserted; every missing leg drops it (AC5)."""

    def test_dense_fixture_is_candidate(self) -> None:
        signal = _floor(_cedh_deck(), (make_combo_record(bucket="included"),))
        assert signal.floor == 4, f"the cEDH fixture must floor at 4, got {signal.floor}"
        assert signal.cedh_candidate is True, (
            "dense fixture (4 GC, turn-2 included infinite, 4 tutors, low curve) must flag "
            "cedh_candidate"
        )

    def test_floor_never_five(self) -> None:
        signal = _floor(_cedh_deck(), (make_combo_record(bucket="included"),))
        assert signal.floor <= BRACKET_FLOOR_MAX, (
            f"no code path may emit floor 5 — candidacy is the only Bracket-5 surface, "
            f"got {signal.floor}"
        )

    def test_missing_floor_leg_drops_candidacy(self) -> None:
        # A cheap included MULTI-card infinite is fast (turn 2 <= 4) but only floors at 3;
        # with no GC the floor==4 leg fails while every other leg holds.
        deck = (
            _piece_rows(1.0)
            + [make_deck_card(_vanilla(name="Combo Piece C", cmc=1.0))]
            + [make_deck_card(_tutor(cmc=1.0), quantity=CEDH_TUTOR_MIN)]
        )
        combo = make_combo_record(
            cards=("Combo Piece A", "Combo Piece B", "Combo Piece C"), bucket="included"
        )
        signal = _floor(deck, (combo,))
        assert signal.floor == 3, f"fixture must floor at 3 for this leg test, got {signal.floor}"
        assert signal.cedh_candidate is False, (
            "cedh_candidate requires floor == 4 — a floor-3 deck must not be flagged"
        )

    def test_missing_fast_combo_leg_drops_candidacy(self) -> None:
        # Pieces at cmc 5 -> earliest turn 5: still an early (<=6) Bracket trigger, but
        # slower than the cEDH turn-4 gate.
        signal = _floor(_cedh_deck(piece_cmc=5.0), (make_combo_record(bucket="included"),))
        assert signal.floor == 4, f"fixture must still floor at 4, got {signal.floor}"
        assert signal.cedh_candidate is False, (
            "cedh_candidate requires an included infinite at earliest turn <= 4"
        )

    def test_missing_tutor_leg_drops_candidacy(self) -> None:
        signal = _floor(
            _cedh_deck(tutors=CEDH_TUTOR_MIN - 1), (make_combo_record(bucket="included"),)
        )
        assert signal.floor == 4, f"fixture must still floor at 4, got {signal.floor}"
        assert signal.cedh_candidate is False, (
            f"cedh_candidate requires tutor count >= {CEDH_TUTOR_MIN}"
        )

    def test_missing_low_curve_leg_drops_candidacy(self) -> None:
        deck = _cedh_deck() + [make_deck_card(_vanilla(name="Big Beater", cmc=8.0), quantity=20)]
        signal = _floor(deck, (make_combo_record(bucket="included"),))
        assert signal.floor == 4, f"fixture must still floor at 4, got {signal.floor}"
        assert signal.cedh_candidate is False, (
            "cedh_candidate requires a low average mana value (dense fast mana)"
        )


# ---------------------------------------------------------------------------
# AC8 — monotone SWAP directions (deck size constant; the 2.9 down-payment)
# ---------------------------------------------------------------------------


class TestMonotoneDirections:
    """Each documented direction, isolated by swapping a vanilla filler card."""

    def test_adding_game_changer_never_lowers_floor(self) -> None:
        for base_gc in (0, 3):
            base = _gc_rows(base_gc, True) + _filler_rows(4)
            grown = base + _gc_rows(1, True)
            before = _floor(base).floor
            after = _floor(grown).floor
            assert after >= before, (
                f"adding a Game Changer must never lower the floor (max-based): "
                f"{base_gc} GC -> {before}, +1 GC -> {after}"
            )

    def test_swap_filler_for_tutor_never_lowers_consistency(self, profile: FormatProfile) -> None:
        lands = [make_deck_card(_land(), quantity=10)]
        base = _filler_rows(20) + lands
        swapped = _filler_rows(19) + [make_deck_card(_tutor(cmc=2.0))] + lands
        before = dimension_vector(base, matched_combos=(), profile=profile).consistency
        after = dimension_vector(swapped, matched_combos=(), profile=profile).consistency
        assert after >= before, (
            f"swapping filler for a tutor must never lower consistency: {before} -> {after}"
        )

    def test_swap_filler_for_interaction_never_lowers_interaction(
        self, profile: FormatProfile
    ) -> None:
        base = _filler_rows(10)
        swapped = _filler_rows(9) + [make_deck_card(_interaction(cmc=2.0))]
        before = dimension_vector(base, matched_combos=(), profile=profile).interaction
        after = dimension_vector(swapped, matched_combos=(), profile=profile).interaction
        assert after >= before, (
            f"swapping filler for interaction must never lower interaction: {before} -> {after}"
        )

    def test_sorcery_interaction_into_instant_deck_never_lowers_interaction(
        self, profile: FormatProfile
    ) -> None:
        # The dilution edge the ratio model fails: one instant-speed interaction spell,
        # then a SORCERY-speed one swapped in for filler.
        base = [make_deck_card(_interaction(name="Instant Answer"))] + _filler_rows(9)
        swapped = [
            make_deck_card(_interaction(name="Instant Answer")),
            make_deck_card(_interaction(name="Sorcery Answer", type_line="Sorcery")),
        ] + _filler_rows(8)
        before = dimension_vector(base, matched_combos=(), profile=profile).interaction
        after = dimension_vector(swapped, matched_combos=(), profile=profile).interaction
        assert after >= before, (
            f"a sorcery-speed interaction swap must not lower interaction via instant-share "
            f"dilution: {before} -> {after}"
        )

    def test_zero_interaction_scores_at_most_with_interaction(self, profile: FormatProfile) -> None:
        none = dimension_vector(_filler_rows(10), matched_combos=(), profile=profile).interaction
        some = dimension_vector(
            _filler_rows(9) + [make_deck_card(_interaction())], matched_combos=(), profile=profile
        ).interaction
        assert none <= some, (
            f"a zero-interaction deck must score <= the same deck with interaction swapped in: "
            f"{none} vs {some}"
        )
        assert none == 0, f"zero interaction must map to interaction == 0, got {none}"

    def test_swap_filler_for_cheap_ramp_never_lowers_speed(self, profile: FormatProfile) -> None:
        lands = [make_deck_card(_land(), quantity=15)]
        base = _filler_rows(20) + lands
        swapped = _filler_rows(19) + [make_deck_card(_ramp(cmc=2.0))] + lands
        before = dimension_vector(base, matched_combos=(), profile=profile).speed
        after = dimension_vector(swapped, matched_combos=(), profile=profile).speed
        assert after >= before, (
            f"swapping filler for a cheap (cmc<=2) ramp spell must never lower speed: "
            f"{before} -> {after}"
        )

    def test_earlier_included_combo_never_lowers_speed_or_combo_potential(
        self, profile: FormatProfile
    ) -> None:
        combo = make_combo_record(bucket="included")
        late = _piece_rows(4.0) + _filler_rows(10)
        early = _piece_rows(1.0) + _filler_rows(10)
        late_vector = dimension_vector(late, matched_combos=(combo,), profile=profile)
        early_vector = dimension_vector(early, matched_combos=(combo,), profile=profile)
        assert early_vector.speed >= late_vector.speed, (
            f"an earlier included combo (cheaper pieces) must never lower speed: "
            f"{late_vector.speed} -> {early_vector.speed}"
        )
        assert early_vector.combo_potential >= late_vector.combo_potential, (
            f"an earlier included combo must never lower combo_potential: "
            f"{late_vector.combo_potential} -> {early_vector.combo_potential}"
        )

    def test_included_scores_at_least_almost_included(self, profile: FormatProfile) -> None:
        deck = _piece_rows(1.0) + _filler_rows(10)
        included = dimension_vector(
            deck, matched_combos=(make_combo_record(bucket="included"),), profile=profile
        ).combo_potential
        almost = dimension_vector(
            deck, matched_combos=(make_combo_record(bucket="almost_included"),), profile=profile
        ).combo_potential
        assert included >= almost, (
            f"an included combo must score combo_potential >= the same combo almost_included: "
            f"{included} vs {almost}"
        )


# ---------------------------------------------------------------------------
# AC8 — verify-by-shape anchors for the provisional curves
# ---------------------------------------------------------------------------


class TestProvisionalCurveAnchors:
    """Clamp/anchor checks only — no mid-curve pins (the curves are 5.9-owned)."""

    def test_empty_deck_combo_potential_zero(self, profile: FormatProfile) -> None:
        vector = dimension_vector((), matched_combos=(), profile=profile)
        assert vector.combo_potential == 0, (
            f"no contributing combo records must anchor combo_potential at 0, "
            f"got {vector.combo_potential}"
        )

    def test_bucket_none_records_contribute_nothing_to_vector(self, profile: FormatProfile) -> None:
        deck = _piece_rows(1.0) + _filler_rows(5)
        with_none = dimension_vector(
            deck, matched_combos=(make_combo_record(bucket=None),), profile=profile
        )
        without = dimension_vector(deck, matched_combos=(), profile=profile)
        assert with_none == without, "a bucket=None record must contribute nothing to any dimension"


# ---------------------------------------------------------------------------
# AC8 — determinism & input hygiene
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Identical input -> identical output; order-independent; inputs never mutated."""

    def _deck_and_combos(self) -> tuple[list[DeckCard], list[ComboRecord]]:
        deck = (
            _piece_rows(1.0)
            + _gc_rows(2, True)
            + _filler_rows(4)
            + [make_deck_card(_land(), quantity=8), make_deck_card(_tutor())]
        )
        combos = [
            make_combo_record(bucket="included"),
            make_combo_record(
                spellbook_id="2000-3000", bucket="almost_included", produces=("Card advantage",)
            ),
        ]
        return deck, combos

    def test_repeat_calls_identical(self, profile: FormatProfile) -> None:
        deck, combos = self._deck_and_combos()
        first = dimension_vector(deck, matched_combos=combos, profile=profile)
        second = dimension_vector(deck, matched_combos=combos, profile=profile)
        assert first == second, "two calls on equal input must yield equal DimensionVector"
        assert bracket_floor(deck, matched_combos=combos) == bracket_floor(
            deck, matched_combos=combos
        ), "two calls on equal input must yield equal BracketFloorSignal"

    def test_input_order_irrelevant(self, profile: FormatProfile) -> None:
        deck, combos = self._deck_and_combos()
        shuffled_deck = list(reversed(deck))
        shuffled_combos = list(reversed(combos))
        assert dimension_vector(deck, matched_combos=combos, profile=profile) == dimension_vector(
            shuffled_deck, matched_combos=shuffled_combos, profile=profile
        ), "shuffled deck_cards / matched_combos order must yield an identical vector"
        assert bracket_floor(deck, matched_combos=combos) == bracket_floor(
            shuffled_deck, matched_combos=shuffled_combos
        ), "shuffled input order must yield an identical BracketFloorSignal"

    def test_inputs_not_mutated(self, profile: FormatProfile) -> None:
        deck, combos = self._deck_and_combos()
        deck_snapshot = list(deck)
        combos_snapshot = list(combos)
        dimension_vector(deck, matched_combos=combos, profile=profile)
        bracket_floor(deck, matched_combos=combos)
        game_changer_signal(deck)
        assert deck == deck_snapshot, "deck_cards must never be mutated"
        assert combos == combos_snapshot, "matched_combos must never be mutated"
        assert all(record.bucket == snap.bucket for record, snap in zip(combos, combos_snapshot)), (
            "combo record buckets must never be rewritten in place"
        )


# ---------------------------------------------------------------------------
# AC8 — sideboard pin (standing 5.3-5.6 policy)
# ---------------------------------------------------------------------------


class TestSideboardPin:
    """Sideboard rows are NOT filtered — deck-composition policy belongs to the caller."""

    def test_sideboard_gc_counts(self) -> None:
        deck = [make_deck_card(_gc("Sideboard GC", True), sideboard=True)]
        signal = game_changer_signal(deck)
        assert signal.known_count == 1, (
            f"a sideboard=True game_changer row must still count, got {signal.known_count}"
        )

    def test_sideboard_rows_reach_the_floor(self) -> None:
        deck = [make_deck_card(_gc(f"SB GC {i}", True), sideboard=True) for i in range(4)]
        signal = _floor(deck)
        assert signal.floor == 4, (
            f"sideboard=True rows must reach the Bracket floor (standing policy), "
            f"got {signal.floor}"
        )

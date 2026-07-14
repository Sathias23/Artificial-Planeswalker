"""Offline shape/invariant tests for the ``FormatProfile`` frozen-data module (Story 5.2).

Verifies by *shape*, never by magic number (the 5.1 AC6 lesson): Story 5.9 owns hand-tuning
the provisional values against the calibration benchmark, so no test here asserts a specific
weight or parameter number — only domains, invariants, and immutability.
"""

import dataclasses

import pytest

from src.logic.assessment import (
    COMMANDER_PROFILE,
    DIMENSIONS,
    STANDARD_PROFILE,
    DimensionWeights,
    FormatProfile,
)

#: Weight-sum tolerance: weights are documented to sum to exactly 1.0.
_WEIGHT_SUM_TOLERANCE = 1e-9

#: The AD-7 closed 7-dimension key set the profiles must cover exactly.
_CANONICAL_DIMENSIONS = {
    "speed",
    "consistency",
    "resilience",
    "interaction",
    "mana_efficiency",
    "card_advantage",
    "combo_potential",
}

_PROFILES: dict[str, FormatProfile] = {
    "COMMANDER_PROFILE": COMMANDER_PROFILE,
    "STANDARD_PROFILE": STANDARD_PROFILE,
}


@pytest.fixture(params=sorted(_PROFILES), ids=sorted(_PROFILES))
def profile_name(request: pytest.FixtureRequest) -> str:
    """Parametrize over both module-level profile constants by name."""
    return str(request.param)


class TestProfileShape:
    """Both profiles exist and are instances of the frozen ``FormatProfile`` shape."""

    def test_profile_is_format_profile(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        assert isinstance(profile, FormatProfile), (
            f"{profile_name} must be a FormatProfile instance, got {type(profile).__name__}"
        )

    def test_dimensions_constant_matches_canonical_set(self) -> None:
        assert set(DIMENSIONS) == _CANONICAL_DIMENSIONS, (
            f"DIMENSIONS must equal the AD-7 closed key set exactly; got {DIMENSIONS!r}"
        )
        assert len(DIMENSIONS) == 7, (
            f"DIMENSIONS must have exactly 7 entries, got {len(DIMENSIONS)}"
        )


class TestImmutability:
    """Every profile and its nested containers are deeply immutable (AC4)."""

    def test_profile_fields_are_frozen(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        for field in dataclasses.fields(FormatProfile):
            with pytest.raises(dataclasses.FrozenInstanceError):
                setattr(profile, field.name, object())

    def test_weights_are_frozen(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        for field in dataclasses.fields(DimensionWeights):
            with pytest.raises(dataclasses.FrozenInstanceError):
                setattr(profile.weights, field.name, 0.5)

    def test_win_turn_band_is_tuple(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        assert isinstance(profile.win_turn_band, tuple), (
            f"{profile_name}.win_turn_band must be an immutable tuple, "
            f"got {type(profile.win_turn_band).__name__}"
        )


class TestWeights:
    """Aggregate weights cover exactly the closed key set and normalize to 1.0 (AC2/AC6)."""

    def test_weight_keys_equal_dimensions(self) -> None:
        weight_keys = {field.name for field in dataclasses.fields(DimensionWeights)}
        assert weight_keys == set(DIMENSIONS), (
            "DimensionWeights fields must equal DIMENSIONS exactly — "
            f"missing: {set(DIMENSIONS) - weight_keys}, extra: {weight_keys - set(DIMENSIONS)}"
        )

    def test_weights_non_negative(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        for dimension in DIMENSIONS:
            weight = getattr(profile.weights, dimension)
            assert weight >= 0.0, (
                f"{profile_name}.weights.{dimension} must be non-negative, got {weight}"
            )

    def test_weights_sum_to_documented_total(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        total = sum(getattr(profile.weights, dimension) for dimension in DIMENSIONS)
        assert abs(total - 1.0) < _WEIGHT_SUM_TOLERANCE, (
            f"{profile_name} weights must sum to 1.0 (documented total), got {total!r}"
        )


class TestFieldDomains:
    """Rubric, band, version, and caveat fields sit in their allowed domains (AC2/AC6)."""

    def test_rubric_in_allowed_domain(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        assert profile.rubric in {"brackets", "heuristic_only"}, (
            f"{profile_name}.rubric must be 'brackets' or 'heuristic_only', got {profile.rubric!r}"
        )

    def test_rubric_per_format(self) -> None:
        assert COMMANDER_PROFILE.rubric == "brackets", (
            f"COMMANDER_PROFILE.rubric must be 'brackets' (FR18), got {COMMANDER_PROFILE.rubric!r}"
        )
        assert STANDARD_PROFILE.rubric == "heuristic_only", (
            "STANDARD_PROFILE.rubric must be 'heuristic_only' (FR20), "
            f"got {STANDARD_PROFILE.rubric!r}"
        )

    def test_win_turn_band_ordered(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        lo, hi = profile.win_turn_band
        assert isinstance(lo, int) and isinstance(hi, int), (
            f"{profile_name}.win_turn_band must hold ints, got ({type(lo).__name__}, "
            f"{type(hi).__name__})"
        )
        assert 0 < lo <= hi, (
            f"{profile_name}.win_turn_band must satisfy 0 < lo <= hi, got ({lo}, {hi})"
        )

    def test_version_non_empty_string(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        assert isinstance(profile.format_profile_version, str), (
            f"{profile_name}.format_profile_version must be a str, "
            f"got {type(profile.format_profile_version).__name__}"
        )
        assert profile.format_profile_version, (
            f"{profile_name}.format_profile_version must be non-empty"
        )

    def test_versions_differ_per_format(self) -> None:
        assert (
            COMMANDER_PROFILE.format_profile_version != STANDARD_PROFILE.format_profile_version
        ), "format_profile_version is per-format and must not be shared across profiles"

    def test_multiplayer_variance_caveat_per_format(self) -> None:
        assert COMMANDER_PROFILE.multiplayer_variance_caveat is True, (
            "COMMANDER_PROFILE.multiplayer_variance_caveat must be True (AD-6 multiplayer caveat)"
        )
        assert STANDARD_PROFILE.multiplayer_variance_caveat is False, (
            "STANDARD_PROFILE.multiplayer_variance_caveat must be False (1v1 format)"
        )

    def test_combos_enabled_is_bool(self, profile_name: str) -> None:
        # The exact value is a tunable data edit (Story 5.9 / Epic 7 own flips), but the
        # *current* documented value (True for both formats, per FR20) is pinned below so an
        # accidental flip doesn't ship silently.
        profile = _PROFILES[profile_name]
        assert isinstance(profile.combos_enabled, bool), (
            f"{profile_name}.combos_enabled must be a bool, "
            f"got {type(profile.combos_enabled).__name__}"
        )

    def test_combos_enabled_per_format(self) -> None:
        assert COMMANDER_PROFILE.combos_enabled is True, (
            "COMMANDER_PROFILE.combos_enabled must be True (Spellbook combo data is "
            "Commander-centric)"
        )
        assert STANDARD_PROFILE.combos_enabled is True, (
            "STANDARD_PROFILE.combos_enabled must be True (FR20's heuristic inputs literally "
            "include combos)"
        )

    def test_karsten_formula_per_format(self) -> None:
        # Story 5.7 (AC6): the profile-driven Karsten formula selector — how
        # dimension_vector picks 5.4/5.5 math without a rubric branch.
        assert COMMANDER_PROFILE.karsten_formula == "commander", (
            "COMMANDER_PROFILE.karsten_formula must be 'commander' (99-card regression), "
            f"got {COMMANDER_PROFILE.karsten_formula!r}"
        )
        assert STANDARD_PROFILE.karsten_formula == "sixty_card", (
            "STANDARD_PROFILE.karsten_formula must be 'sixty_card' (60-card regression), "
            f"got {STANDARD_PROFILE.karsten_formula!r}"
        )

    def test_versions_bumped_for_karsten_formula_addition(self) -> None:
        # AD-3 bump rule: the Story 5.7 additive field change bumps BOTH profile versions
        # in the same edit (v1 -> v2).
        assert COMMANDER_PROFILE.format_profile_version == "commander-v2", (
            "COMMANDER_PROFILE.format_profile_version must be 'commander-v2' after the "
            f"karsten_formula addition (AD-3 bump rule), got "
            f"{COMMANDER_PROFILE.format_profile_version!r}"
        )
        assert STANDARD_PROFILE.format_profile_version == "standard-v2", (
            "STANDARD_PROFILE.format_profile_version must be 'standard-v2' after the "
            f"karsten_formula addition (AD-3 bump rule), got "
            f"{STANDARD_PROFILE.format_profile_version!r}"
        )

"""Offline tests for the Story 5.8 aggregate/label/vocabulary module (AC8).

Covers the for-format aggregate (domain, anchors, rounding, per-dimension monotonicity),
the FR24 tier label (totality, inclusive-lower-cut boundaries, monotone bands), the FR20
rubric-swap invariance proof, the closed AD-6 confidence vocabulary, the AC4 profile
additions, and determinism. Threshold and weight VALUES are provisional (Story 5.9 owns
tuning) — tests here verify shape, domains, and directions; exact pins are reserved for
the closed vocabularies and the decide-once rounding/boundary policies.
"""

import dataclasses
import string
import typing

import pytest

from src.logic.assessment import (
    CARDS_UNRESOLVED,
    COMBO_DATA_UNAVAILABLE,
    COMMANDER_PROFILE,
    COMMANDER_UNIDENTIFIED,
    CONFIDENCE_LEVELS,
    CONFIDENCE_REASON_TOKENS,
    DIMENSIONS,
    GAME_CHANGER_DATA_UNAVAILABLE,
    STANDARD_PROFILE,
    TIER_LABELS,
    ConfidenceLevel,
    DimensionVector,
    DimensionWeights,
    FormatProfile,
    TierLabel,
    aggregate_score,
    tier_label,
)

# The two private `_to_score` helpers are imported by their qualified module paths (they
# are private-by-convention, so not re-exported) purely to pin that this story's restated
# copy stays byte-for-byte faithful to the dimensions original it documents itself as
# restating — the review-added guard for the "shared decide-once policy" docstring claim.
from src.logic.assessment.aggregate import _to_score as _aggregate_to_score
from src.logic.assessment.dimensions import _to_score as _dimensions_to_score

_PROFILES: dict[str, FormatProfile] = {
    "COMMANDER_PROFILE": COMMANDER_PROFILE,
    "STANDARD_PROFILE": STANDARD_PROFILE,
}

#: Deterministic "arbitrary valid vector" sample points for domain checks (no randomness —
#: the suite itself must be deterministic).
_SAMPLE_VALUE_SETS: tuple[tuple[int, ...], ...] = (
    (0, 100, 37, 62, 5, 98, 50),
    (1, 1, 1, 1, 1, 1, 1),
    (99, 0, 100, 13, 77, 42, 88),
    (50, 50, 50, 50, 50, 50, 50),
)


def make_vector(**overrides: int) -> DimensionVector:
    """Build a ``DimensionVector`` defaulting every dimension to a mid value of 50."""
    values: dict[str, int] = {dimension: 50 for dimension in DIMENSIONS}
    values.update(overrides)
    return DimensionVector(**values)


def _vector_from(values: tuple[int, ...]) -> DimensionVector:
    """Zip a 7-value tuple onto ``DIMENSIONS`` in canonical order."""
    return DimensionVector(**dict(zip(DIMENSIONS, values, strict=True)))


@pytest.fixture(params=sorted(_PROFILES), ids=sorted(_PROFILES))
def profile_name(request: pytest.FixtureRequest) -> str:
    """Parametrize over both shipped profile constants by name."""
    return str(request.param)


class TestAggregateDomainAndAnchors:
    """AC2/AC8: integer 0-100 for any valid vector; exact anchors at the extremes."""

    @pytest.mark.parametrize("values", _SAMPLE_VALUE_SETS)
    def test_aggregate_is_int_in_domain(self, profile_name: str, values: tuple[int, ...]) -> None:
        profile = _PROFILES[profile_name]
        score = aggregate_score(_vector_from(values), profile=profile)
        assert isinstance(score, int), (
            f"aggregate_score must return int (AD-8 integer discipline), "
            f"got {type(score).__name__} under {profile_name}"
        )
        assert 0 <= score <= 100, (
            f"aggregate_score must land in [0, 100], got {score} for {values!r} "
            f"under {profile_name}"
        )

    def test_all_zero_vector_scores_exactly_zero(self, profile_name: str) -> None:
        # The float-dust clamp proof, low end: weights sum to 1.0, so an all-zero
        # vector must hit the boundary exactly, not approximately.
        profile = _PROFILES[profile_name]
        score = aggregate_score(_vector_from((0,) * 7), profile=profile)
        assert score == 0, (
            f"aggregate_score(all-zero vector) must be exactly 0 under {profile_name}, got {score}"
        )

    def test_all_hundred_vector_scores_exactly_hundred(self, profile_name: str) -> None:
        # The float-dust clamp proof, high end.
        profile = _PROFILES[profile_name]
        score = aggregate_score(_vector_from((100,) * 7), profile=profile)
        assert score == 100, (
            f"aggregate_score(all-100 vector) must be exactly 100 under {profile_name}, got {score}"
        )


class TestRoundingPolicy:
    """AC2/AC8: the decide-once policy is clamp then round HALF-UP, not ``round()``."""

    def test_half_sum_rounds_up(self) -> None:
        # Synthetic weights isolate a .5 weighted sum: 50 * 0.5 + 51 * 0.5 = 50.5
        # (both products exact in binary floating point). Half-up gives 51; Python's
        # round() would give 50 (banker's rounding sends .5 to the nearest EVEN
        # integer) — this pin documents why the module does not use round().
        half_split = dataclasses.replace(
            STANDARD_PROFILE,
            weights=DimensionWeights(
                speed=0.5,
                consistency=0.5,
                resilience=0.0,
                interaction=0.0,
                mana_efficiency=0.0,
                card_advantage=0.0,
                combo_potential=0.0,
            ),
        )
        vector = make_vector(speed=50, consistency=51)
        assert round(50.5) == 50  # the banker's-rounding trap the policy avoids
        score = aggregate_score(vector, profile=half_split)
        assert score == 51, (
            f"aggregate_score must round a x.5 weighted sum half-UP (50.5 -> 51), got {score}"
        )


class TestToScorePolicyParity:
    """The restated `_to_score` must stay faithful to `dimensions._to_score`.

    `aggregate._to_score` is a hand-copy of `dimensions._to_score` (private-by-convention,
    so restated rather than imported — see the aggregate module docstring). Each copy's own
    behaviour is pinned elsewhere, but nothing guarded the *seam*: a future edit to one copy
    would silently diverge while the docstring still claims a single "shared decide-once
    policy". This pins the two implementations agree across the rounding-critical and
    clamp-boundary values, so the divergence surfaces as a failing test, not a lie in prose.
    (Story 5.9 owns hoisting the two into one home; until then this is the guard.)
    """

    #: Values chosen to exercise both round-half-up behaviour (the `.5` points) and the
    #: clamp edges (below 0, exactly 0/100, above 100, plus float-dust either side).
    _POLICY_INPUTS: tuple[float, ...] = (
        -10.0,
        -0.0001,
        0.0,
        0.4999,
        0.5,
        0.5001,
        49.5,
        50.4999,
        50.5,
        62.3,
        99.5,
        99.9999999,
        100.0,
        100.5,
        250.0,
    )

    @pytest.mark.parametrize("value", _POLICY_INPUTS)
    def test_restated_to_score_matches_dimensions(self, value: float) -> None:
        expected = _dimensions_to_score(value)
        actual = _aggregate_to_score(value)
        assert actual == expected, (
            f"aggregate._to_score must restate dimensions._to_score exactly (shared "
            f"decide-once clamp + half-up policy): the two diverged on {value!r} "
            f"({actual} != {expected}) — hoist to one home or re-sync the copies"
        )


class TestMonotonicity:
    """AC8: raising any single dimension (others fixed) never lowers the aggregate."""

    @pytest.mark.parametrize("dimension", DIMENSIONS)
    def test_raising_one_dimension_never_lowers_score(
        self, profile_name: str, dimension: str
    ) -> None:
        profile = _PROFILES[profile_name]
        low = aggregate_score(make_vector(**{dimension: 10}), profile=profile)
        high = aggregate_score(make_vector(**{dimension: 90}), profile=profile)
        assert high >= low, (
            f"aggregate_score must be monotone in {dimension} under fixed "
            f"{profile_name} weights: raising {dimension} 10 -> 90 lowered the "
            f"aggregate {low} -> {high}"
        )


class TestRubricSwapInvariance:
    """AC5/AC8: neither function reads ``rubric`` — the Standard fork is no fork."""

    def test_aggregate_ignores_rubric(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        other = "heuristic_only" if profile.rubric == "brackets" else "brackets"
        swapped = dataclasses.replace(profile, rubric=other)
        for values in _SAMPLE_VALUE_SETS:
            vector = _vector_from(values)
            assert aggregate_score(vector, profile=profile) == aggregate_score(
                vector, profile=swapped
            ), (
                f"aggregate_score must be rubric-blind (reads only weights): "
                f"{profile_name} with rubric={other!r} diverged on {values!r}"
            )

    def test_tier_label_ignores_rubric(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        other = "heuristic_only" if profile.rubric == "brackets" else "brackets"
        swapped = dataclasses.replace(profile, rubric=other)
        for score in range(101):
            assert tier_label(score, profile=profile) == tier_label(score, profile=swapped), (
                f"tier_label must be rubric-blind (reads only tier_thresholds): "
                f"{profile_name} with rubric={other!r} diverged at score {score}"
            )


class TestTierLabel:
    """AC3/AC8: total over [0, 100], inclusive lower cuts, monotone, defensive outside."""

    def test_total_over_domain(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        for score in range(101):
            label = tier_label(score, profile=profile)
            assert label in TIER_LABELS, (
                f"tier_label({score}) under {profile_name} must be a TIER_LABELS "
                f"member, got {label!r}"
            )

    def test_domain_endpoints(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        assert tier_label(0, profile=profile) == TIER_LABELS[0], (
            f"tier_label(0) must map to the first band ({TIER_LABELS[0]!r}) under "
            f"{profile_name}, got {tier_label(0, profile=profile)!r}"
        )
        assert tier_label(100, profile=profile) == TIER_LABELS[-1], (
            f"tier_label(100) must map to the last band ({TIER_LABELS[-1]!r}) under "
            f"{profile_name} (top cut <= 100 pinned by the profile tests), got "
            f"{tier_label(100, profile=profile)!r}"
        )

    def test_thresholds_are_inclusive_lower_cuts(self, profile_name: str) -> None:
        # The decide-once boundary policy: score >= tier_thresholds[i] promotes into
        # band i+1, so the exact cut value belongs to the upper band and cut-1 to the
        # band below. Pinning both sides keeps a 5.9 re-cut from silently flipping
        # the convention.
        profile = _PROFILES[profile_name]
        for band_index, cut in enumerate(profile.tier_thresholds, start=1):
            at_cut = tier_label(cut, profile=profile)
            below_cut = tier_label(cut - 1, profile=profile)
            assert at_cut == TIER_LABELS[band_index], (
                f"tier_label({cut}) must promote into band {band_index} "
                f"({TIER_LABELS[band_index]!r}) under {profile_name} (inclusive lower "
                f"cut), got {at_cut!r}"
            )
            assert below_cut == TIER_LABELS[band_index - 1], (
                f"tier_label({cut - 1}) must stay in band {band_index - 1} "
                f"({TIER_LABELS[band_index - 1]!r}) under {profile_name}, got "
                f"{below_cut!r}"
            )

    def test_band_monotone_in_score(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        previous_band = -1
        for score in range(101):
            band = TIER_LABELS.index(tier_label(score, profile=profile))
            assert band >= previous_band, (
                f"tier_label must never map a higher score to a lower-power band: "
                f"score {score} fell to band {band} after band {previous_band} "
                f"under {profile_name}"
            )
            previous_band = band

    def test_out_of_domain_degrades_to_nearest_band(self, profile_name: str) -> None:
        # 5.6-lesson defense-in-depth: a future caller bug produces a clamped label,
        # never an exception from inside the pure core.
        profile = _PROFILES[profile_name]
        assert tier_label(-5, profile=profile) == TIER_LABELS[0], (
            f"tier_label(-5) must degrade to the first band under {profile_name}, "
            f"got {tier_label(-5, profile=profile)!r}"
        )
        assert tier_label(999, profile=profile) == TIER_LABELS[-1], (
            f"tier_label(999) must degrade to the last band under {profile_name}, "
            f"got {tier_label(999, profile=profile)!r}"
        )


class TestConfidenceVocabulary:
    """AC6/AC8: the closed AD-6 token set — exact, sorted, count-free, clock-free."""

    def test_reason_tokens_exact_set(self) -> None:
        assert CONFIDENCE_REASON_TOKENS == (
            CARDS_UNRESOLVED,
            COMBO_DATA_UNAVAILABLE,
            COMMANDER_UNIDENTIFIED,
            GAME_CHANGER_DATA_UNAVAILABLE,
        ), (
            "CONFIDENCE_REASON_TOKENS must contain exactly the four AD-6 constants, "
            f"got {CONFIDENCE_REASON_TOKENS!r}"
        )
        assert CONFIDENCE_REASON_TOKENS == (
            "cards_unresolved",
            "combo_data_unavailable",
            "commander_unidentified",
            "game_changer_data_unavailable",
        ), (
            "CONFIDENCE_REASON_TOKENS string values must be exactly the closed AD-6 "
            f"vocabulary — no clock/staleness token can be added — got "
            f"{CONFIDENCE_REASON_TOKENS!r}"
        )

    def test_reason_tokens_bytewise_sorted(self) -> None:
        assert CONFIDENCE_REASON_TOKENS == tuple(sorted(CONFIDENCE_REASON_TOKENS)), (
            "CONFIDENCE_REASON_TOKENS must be defined already bytewise-sorted so the "
            "documented order and the AD-8 emission order coincide, got "
            f"{CONFIDENCE_REASON_TOKENS!r}"
        )

    def test_reason_tokens_snake_case_no_digits(self) -> None:
        allowed = set(string.ascii_lowercase) | {"_"}
        for token in CONFIDENCE_REASON_TOKENS:
            assert set(token) <= allowed, (
                f"confidence token {token!r} must be snake_case with no digits — "
                "counts live in separate structured fields, phrasing only in summary"
            )

    def test_confidence_levels_match_literal(self) -> None:
        assert typing.get_args(ConfidenceLevel) == ("low", "medium", "high"), (
            "ConfidenceLevel must be Literal['low', 'medium', 'high'] in semantic "
            f"ascending order, got {typing.get_args(ConfidenceLevel)!r}"
        )
        assert CONFIDENCE_LEVELS == ("low", "medium", "high"), (
            f"CONFIDENCE_LEVELS must be ('low', 'medium', 'high'), got {CONFIDENCE_LEVELS!r}"
        )

    def test_tier_labels_match_literal(self) -> None:
        assert len(TIER_LABELS) == 5, (
            f"TIER_LABELS must have exactly 5 bands, got {len(TIER_LABELS)}"
        )
        assert tuple(typing.get_args(TierLabel)) == TIER_LABELS, (
            "TIER_LABELS must match the TierLabel Literal members in order, got "
            f"{TIER_LABELS!r} vs {typing.get_args(TierLabel)!r}"
        )


class TestProfileAdditions:
    """AC4/AC8: the tier_thresholds field and the v3 version bumps."""

    def test_tier_thresholds_shape_and_domain(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        cuts = profile.tier_thresholds
        assert isinstance(cuts, tuple) and len(cuts) == 4, (
            f"{profile_name}.tier_thresholds must be a 4-tuple (bands 2-5 lower cuts), got {cuts!r}"
        )
        for lower, upper in zip(cuts, cuts[1:], strict=False):
            assert lower < upper, (
                f"{profile_name}.tier_thresholds must be strictly ascending, got {cuts!r}"
            )
        for cut in cuts:
            assert isinstance(cut, int) and 0 < cut <= 100, (
                f"{profile_name}.tier_thresholds cuts must be ints in (0, 100], got {cut!r}"
            )

    def test_versions_read_v3(self) -> None:
        assert COMMANDER_PROFILE.format_profile_version == "commander-v3", (
            "COMMANDER_PROFILE.format_profile_version must read 'commander-v3' after "
            f"the Story 5.8 tier_thresholds addition, got "
            f"{COMMANDER_PROFILE.format_profile_version!r}"
        )
        assert STANDARD_PROFILE.format_profile_version == "standard-v3", (
            "STANDARD_PROFILE.format_profile_version must read 'standard-v3' after "
            f"the Story 5.8 tier_thresholds addition, got "
            f"{STANDARD_PROFILE.format_profile_version!r}"
        )


class TestDeterminism:
    """AC2/AC8: identical inputs yield identical outputs; inputs are never mutated."""

    def test_repeated_calls_equal(self, profile_name: str) -> None:
        profile = _PROFILES[profile_name]
        vector = _vector_from(_SAMPLE_VALUE_SETS[0])
        first = aggregate_score(vector, profile=profile)
        second = aggregate_score(vector, profile=profile)
        assert first == second, (
            f"aggregate_score must be deterministic under {profile_name}: {first} != {second}"
        )
        assert tier_label(first, profile=profile) == tier_label(first, profile=profile), (
            f"tier_label must be deterministic under {profile_name}"
        )

    def test_inputs_not_mutated(self, profile_name: str) -> None:
        # Frozen dataclasses make mutation impossible in practice; equality against a
        # freshly built twin makes the claim explicit and cheap.
        profile = _PROFILES[profile_name]
        vector = _vector_from(_SAMPLE_VALUE_SETS[0])
        twin = _vector_from(_SAMPLE_VALUE_SETS[0])
        aggregate_score(vector, profile=profile)
        tier_label(50, profile=profile)
        assert vector == twin, (
            f"aggregate_score/tier_label must not mutate the input vector under {profile_name}"
        )

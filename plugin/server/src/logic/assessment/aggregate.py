"""For-format aggregate score, descriptive tier label & AD-6 confidence vocabulary (5.8).

The first consumer of the Story 5.7 dimension vector: collapses it into the **for-format
0-100 integer score** (FR19) via the profile's ``weights``, attaches the **FR24 tier
label** from the profile's ``tier_thresholds``, and defines the **closed AD-6
confidence-reason vocabulary** (FR21's vocabulary half). Pure and deterministic (AD-2):
no network, no DB, no clock, no randomness, no logging — inputs are the already-computed
``DimensionVector`` and a ``FormatProfile``; this module consumes the VECTOR, never raw
signals.

**Decide-once policies (restated here, pinned by tests):**

- *Rounding:* clamp to ``[0.0, 100.0]`` then round half-up — the same policy as
  :func:`src.logic.assessment.dimensions._to_score`, restated locally in
  :func:`_to_score` (see its docstring for why it is a copy, not an import).
- *Label boundary:* inclusive lower cut — ``score >= tier_thresholds[i]`` promotes into
  band ``i + 1``; band 1 implicitly starts at 0 (:func:`tier_label`).
- *No rubric branch:* neither function reads any profile field except ``weights``
  (aggregate) / ``tier_thresholds`` (label). The FR20 "Standard fork" is the ABSENCE of
  a fork here: the Commander and Standard paths are the same code.

**Composition contract (Story 5.9 / Epic 7):** 5.9's ``score()`` composes matcher →
``dimension_vector`` / ``bracket_floor`` → :func:`aggregate_score` + :func:`tier_label`.
Under a ``heuristic_only`` profile the composer never consults ``bracket_floor`` and the
edge emits ``bracket: null`` (AD-7 fixed shape) — the fork lives in what is COMPOSED,
never inside this module. No 1-10 projection, no absolute cross-format score, no
percentile, and no meta-tier exist anywhere here (FR19/FR20).

**Vocabulary, not policy (FR21/AD-6):** this module ships the closed confidence-reason
tokens and level vocabulary only — exactly like 5.5's ``STRUCTURAL_GAP_TOKENS``. The
degradation ladder that maps run-context facts to a level and assembles ``reasons[]`` is
Epic 7 edge code; the Commander profile's multiplayer-variance caveat is ``summary`` text
driven by ``FormatProfile.multiplayer_variance_caveat``, NEVER a member of this enum.
"""

import math
from bisect import bisect_right
from typing import Final, Literal

from src.logic.assessment.dimensions import DimensionVector
from src.logic.assessment.profiles import DIMENSIONS, TIER_LABELS, FormatProfile, TierLabel

# ---------------------------------------------------------------------------
# AD-6 confidence vocabulary (AC6) — tokens only, no assignment policy
# ---------------------------------------------------------------------------

#: AD-6 reason token: one or more decklist entries did not resolve to known cards.
CARDS_UNRESOLVED: Final = "cards_unresolved"
#: AD-6 reason token: no combo snapshot was available for combo provisioning.
COMBO_DATA_UNAVAILABLE: Final = "combo_data_unavailable"
#: AD-6 reason token: the deck's commander could not be identified.
COMMANDER_UNIDENTIFIED: Final = "commander_unidentified"
#: AD-6 reason token: Game Changer status was unknown for one or more cards.
GAME_CHANGER_DATA_UNAVAILABLE: Final = "game_changer_data_unavailable"

#: The closed AD-6 reason-token set, defined already bytewise-sorted so the documented
#: order and the AD-8 ``reasons[]`` emission order coincide (the ``STRUCTURAL_GAP_TOKENS``
#: precedent). Tokens are count-free snake_case (counts live in separate structured
#: fields; phrasing only in ``summary``) and clock-free — this exact four-token set is
#: pinned by tests, so a "staleness" token cannot be added silently.
CONFIDENCE_REASON_TOKENS: Final[tuple[str, ...]] = (
    CARDS_UNRESOLVED,
    COMBO_DATA_UNAVAILABLE,
    COMMANDER_UNIDENTIFIED,
    GAME_CHANGER_DATA_UNAVAILABLE,
)

#: The AD-6 confidence level vocabulary (FR21). The level is a scalar, so this is a
#: SEMANTIC ascending order (low → high), not an AD-8 emission list — only ``reasons[]``
#: lists get bytewise-sorted at the edge.
ConfidenceLevel = Literal["low", "medium", "high"]

#: The three levels in semantic ascending order (see :data:`ConfidenceLevel`).
CONFIDENCE_LEVELS: Final[tuple[ConfidenceLevel, ...]] = ("low", "medium", "high")


# ---------------------------------------------------------------------------
# The for-format aggregate (AC2)
# ---------------------------------------------------------------------------


def _to_score(value: float) -> int:
    """Clamp to ``[0.0, 100.0]`` then round half-up — the shared decide-once policy.

    Restates :func:`src.logic.assessment.dimensions._to_score` verbatim: the sibling
    helper is private by convention and this story's diff stays additive-only, so the
    documented 2-line policy is copied rather than imported or promoted (if a third
    copy ever threatens, hoisting to one public home is Story 5.9's call).
    ``int(x + 0.5)`` rather than ``round()``: banker's rounding sends ``.5`` to the
    nearest EVEN integer. The clamp is float-dust defense only for the aggregate:
    weights are non-negative and sum to 1.0 (pinned by the profile tests), so the true
    weighted-sum range is already ``[0, 100]``.
    """
    clamped = min(100.0, max(0.0, value))
    return int(clamped + 0.5)


def aggregate_score(vector: DimensionVector, *, profile: FormatProfile) -> int:
    """Collapse the 7-dimension vector into the for-format 0-100 integer score (FR19).

    A weighted sum over :data:`~src.logic.assessment.profiles.DIMENSIONS` in its fixed
    canonical order (never dataclass field order), reading each dimension from both the
    vector and ``profile.weights`` — the only profile field this function touches (no
    ``rubric`` branch: Commander and Standard run the same code). Deterministic:
    identical inputs yield identical output. Monotone per-dimension under fixed
    weights: raising one dimension (others held equal) never lowers the result. The
    score is format-relative — there is deliberately no 1-10 projection and no
    absolute cross-format scale.

    Args:
        vector: The Story 5.7 ``DimensionVector`` (seven ints in ``[0, 100]``).
        profile: The format's frozen constants; only ``weights`` is read.

    Raises:
        ValueError: If any weight is negative or non-finite — the 5.9 guard (the 5.6
            lesson: malformed input must not masquerade as signal; a negative weight
            silently inverts a dimension's monotone direction). The shipped profiles
            are pinned valid by test; this protects hand-tuning workflows.

    Returns:
        The weighted aggregate as an integer in ``[0, 100]`` (AD-8 discipline).
    """
    for dimension in DIMENSIONS:
        weight = getattr(profile.weights, dimension)
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError(f"malformed weight for {dimension!r}: {weight!r}")
    weighted = sum(
        getattr(vector, dimension) * getattr(profile.weights, dimension) for dimension in DIMENSIONS
    )
    return _to_score(weighted)


# ---------------------------------------------------------------------------
# The FR24 tier label (AC3)
# ---------------------------------------------------------------------------


def tier_label(score: int, *, profile: FormatProfile) -> TierLabel:
    """Map a for-format score to its descriptive tier label (FR24).

    Boundary policy (decide once): **inclusive lower cut** — the highest band whose
    lower cut ``<=`` score wins, i.e. ``score >= profile.tier_thresholds[i]`` promotes
    into band ``i + 1``; band 1 (``TIER_LABELS[0]``) implicitly starts at 0.
    Implemented as :func:`bisect.bisect_right` over the strictly ascending cut tuple
    (pinned by the profile tests). Total over ``[0, 100]`` and defensive outside it: an
    out-of-domain input degrades to the nearest band (below 0 → first, above the top
    cut → last), never raises. Monotone by construction: a higher score never maps to
    a lower-power label. Reads no profile field except ``tier_thresholds``.

    Args:
        score: A for-format aggregate score, normally in ``[0, 100]``.
        profile: The format's frozen constants; only ``tier_thresholds`` is read.

    Raises:
        ValueError: If the cuts are not strictly ascending within ``(0, 100)`` — the
            5.9 guard: a cut at 0 shadows band 1 entirely and a cut at 100 makes its
            band a single-score degenerate sliver (the 5.8-deferred domain item); both
            are tuning mistakes, not meaningful configurations.

    Returns:
        The band's :data:`~src.logic.assessment.profiles.TierLabel` word.
    """
    cuts = profile.tier_thresholds
    if any(cut <= 0 or cut >= 100 for cut in cuts) or any(
        low >= high for low, high in zip(cuts, cuts[1:], strict=False)
    ):
        raise ValueError(f"malformed tier_thresholds (need strictly ascending in (0, 100)): {cuts}")
    return TIER_LABELS[bisect_right(cuts, score)]

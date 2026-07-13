"""FR17/FR7/FR9 consistency, interaction-detail & structural-coverage signals (Story 5.5).

Raw signals only: exact hypergeometric access probabilities (FR17), interaction
instant-speed/CMC detail (FR7), and rule-of-8 redundancy plus the closed
``structural_gaps`` token enum (FR9). Downstream stories map these onto scores — the
signal→0–100 ``consistency``/``interaction`` mapping is Story 5.7's, the aggregate
weighting Story 5.8's, and combo matching (earliest-turn math, Spellbook records) Story
5.6's. Everything here is a pure function over already-loaded Pydantic schemas
(:class:`Card` / :class:`DeckCard`) — no network, DB, clock, file I/O, or randomness
(AD-2); FR17 is analytic by requirement (no Monte Carlo). Every result is a frozen slots
dataclass or plain tuple with deterministically ordered contents (AD-8): identical input
always yields identical output.

One vocabulary (AD-10): category membership comes from
:mod:`src.logic.assessment.classifiers` (``classify_card`` / ``classify_deck``) and
land/spell counts from :func:`src.logic.assessment.mana_base.compute_curve` — this module
never re-implements oracle-text patterns, land detection, or CMC bucketing. The board-wipe
sub-tag 5.3 deferred "to 5.5 if its 8×8 math needs one" is NOT needed: the v1 baselines
operate on the coarse ``INTERACTION`` count, so the existing taxonomy suffices.

Sideboard rows are NOT filtered — deck-composition policy belongs to the caller: filter
``sideboard=False`` first if you want played-cards-only signals (the 5.3/5.4 precedent).
Consequence: sideboard rows inflate deck size and category counts symmetrically; the edge
(Epic 7) passes mainboard-only rows.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from src.data.schemas.card import Card
from src.data.schemas.deck import DeckCard
from src.logic.assessment.classifiers import (
    CARD_DRAW,
    CATEGORIES,
    INTERACTION,
    RAMP,
    WINCON_COMBO_PIECE,
    WINCON_EXPLICIT,
    WINCON_FINISHER,
    classify_card,
    classify_deck,
)
from src.logic.assessment.mana_base import KarstenFormula, compute_curve

# ---------------------------------------------------------------------------
# FR17 hypergeometric access (Task 2)
# ---------------------------------------------------------------------------

#: The v1 cards-seen convention: ``cards_seen(turn) = OPENING_HAND_SIZE + turn`` with
#: turn 0 = the opening hand (the on-the-draw reading). Derived from the research doc's
#: own worked example — "1 copy in 99 cards ≈ 12% by turn 5" is exactly 12 seen cards,
#: ``12/99`` (docs/deck-assess.md:154). No mulligan modeling in v1; an on-the-play
#: variant is a Story 5.9 refinement.
OPENING_HAND_SIZE: Final = 7


def probability_at_least(*, deck_size: int, copies: int, drawn: int, min_count: int = 1) -> float:
    """Exact hypergeometric P(at least ``min_count`` of ``copies`` among ``drawn``).

    The FR17 primitive: analytic, never Monte Carlo. ``math.comb`` is exact integer
    arithmetic and the single final division makes results bit-identical for identical
    inputs across runs and platforms (AD-2/NFR1 determinism). Downstream key-piece
    recipes parameterize this directly — e.g. "P(≥1 of k functional copies by turn N)"
    is ``probability_at_least(deck_size=size, copies=k, drawn=cards_seen_by_turn(n))``.

    Degradation precedence (checked in this order, never raises):

    1. ``min_count <= 0`` → ``1.0`` (trivially satisfied — checked FIRST, so an empty
       deck at turn 0 still reads 1.0);
    2. ``deck_size <= 0`` or ``copies <= 0`` or ``drawn <= 0`` → ``0.0``;
    3. ``copies``/``drawn`` above ``deck_size`` clamp to ``deck_size``;
    4. ``min_count > min(copies, drawn)`` → ``0.0`` (unreachable success count).

    Args:
        deck_size: Total cards in the deck (population size).
        copies: Number of success cards in the deck.
        drawn: Number of cards seen (sample size).
        min_count: Minimum successes required (default 1).

    Returns:
        The exact probability as a float in ``[0.0, 1.0]``.
    """
    if min_count <= 0:
        return 1.0
    if deck_size <= 0 or copies <= 0 or drawn <= 0:
        return 0.0
    copies = min(copies, deck_size)
    drawn = min(drawn, deck_size)
    reachable = min(copies, drawn)
    if min_count > reachable:
        return 0.0
    favorable = sum(
        math.comb(copies, successes) * math.comb(deck_size - copies, drawn - successes)
        for successes in range(min_count, reachable + 1)
    )
    return favorable / math.comb(deck_size, drawn)


def cards_seen_by_turn(turn: int) -> int:
    """Return the cards seen by turn ``turn`` under the v1 convention.

    ``OPENING_HAND_SIZE + turn``, turn 0 = the opening hand — see the convention note on
    :data:`OPENING_HAND_SIZE` (the 12/99 worked example fixes it).

    Args:
        turn: The turn number (0 = opening hand).

    Returns:
        The number of cards seen.
    """
    return OPENING_HAND_SIZE + turn


def land_access_by_turn(deck_cards: Sequence[DeckCard], turn: int) -> float:
    """P(at least ``turn`` lands among the cards seen by turn ``turn``) — FR17 mana access.

    "Made every land drop through turn N": ``min_count = turn``, so ``turn <= 0`` is
    trivially ``1.0`` via the primitive's precedence rule (no special case). Land count
    and deck size come from :func:`compute_curve` (quantity-aware; the land-detection
    policy has one owner). An empty deck reads ``0.0`` for positive turns — never raises.
    Sideboard rows are included — filter first if unwanted.

    Args:
        deck_cards: The deck's card associations.
        turn: The turn number (0 = opening hand).

    Returns:
        The exact probability of having made every land drop through ``turn``.
    """
    curve = compute_curve(deck_cards)
    return probability_at_least(
        deck_size=curve.land_count + curve.spell_count,
        copies=curve.land_count,
        drawn=cards_seen_by_turn(turn),
        min_count=turn,
    )


# ---------------------------------------------------------------------------
# FR9 rule-of-8 redundancy signals (Task 4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RedundancySignal:
    """One category's FR9 functional-redundancy read: count + opening-hand access.

    Attributes:
        category: A :data:`~src.logic.assessment.classifiers.CATEGORIES` token.
        count: Quantity-aware count of cards holding the tag (``classify_deck``'s count).
        opener_probability: P(≥1 in the opening :data:`OPENING_HAND_SIZE`) against the
            actual deck size — ``0.0`` when the deck has no copies.
    """

    category: str
    count: int
    opener_probability: float


def redundancy_signals(deck_cards: Sequence[DeckCard]) -> tuple[RedundancySignal, ...]:
    """Compute the FR9 redundancy signal for every category — fixed nine-tuple.

    Always all nine categories in :data:`CATEGORIES` order (the AD-7 fixed-shape
    discipline: no categories-present-conditional output). The published rule-of-8
    anchors (60-card opener: 4 copies → 39.9%, 8 → 65.4%, 12 → 80.9%) fall out of the
    primitive — they are not stored constants. An empty deck yields zero counts and
    ``0.0`` probabilities — never raises. Sideboard rows are included — filter first if
    unwanted.

    Args:
        deck_cards: The deck's card associations.

    Returns:
        A frozen nine-tuple of :class:`RedundancySignal`, one per category, in
        :data:`CATEGORIES` order.
    """
    counts = classify_deck(deck_cards)
    curve = compute_curve(deck_cards)
    deck_size = curve.land_count + curve.spell_count
    return tuple(
        RedundancySignal(
            category=category,
            count=counts[category].count,
            opener_probability=probability_at_least(
                deck_size=deck_size,
                copies=counts[category].count,
                drawn=OPENING_HAND_SIZE,
            ),
        )
        for category in CATEGORIES
    )


# ---------------------------------------------------------------------------
# FR7 interaction detail (Task 5)
# ---------------------------------------------------------------------------

#: Instant-speed policy (decide-once, v1): a card is instant-speed when ``"instant"``
#: appears in its lowercased ``type_line`` OR ``"flash"`` is among its lowercased
#: ``keywords``. Multi-face type lines are ``//``-joined at top level, so an
#: "Instant // Sorcery" split counts instant-speed — conservative, accepted v1.
#: Text-granted flash ("as though it had flash") is an accepted v1 undercount. A third
#: gap in the same direction: a permanent (land/artifact/creature) whose activated
#: ability is ``INTERACTION``-tagged reads as sorcery-speed here even though MTG's own
#: timing rules make any activated ability instant-speed unless the card says otherwise
#: — also an accepted v1 undercount, not modeled until a card-level activated-ability
#: timing signal exists.
_INSTANT_TYPE: Final = "instant"
_FLASH_KEYWORD: Final = "flash"


def _is_instant_speed(card: Card) -> bool:
    """True under the documented v1 instant-speed policy (type line or Flash keyword)."""
    if _INSTANT_TYPE in card.type_line.lower():
        return True
    return _FLASH_KEYWORD in {keyword.lower() for keyword in card.keywords or ()}


@dataclass(frozen=True, slots=True)
class InteractionSignals:
    """The FR7 interaction-detail read of a deck.

    Attributes:
        count: Quantity-aware total of ``INTERACTION``-tagged cards (equals
            ``classify_deck``'s count for the token).
        instant_speed_count: Quantity-aware subtotal that is instant-speed under the
            documented policy (see the module's instant-speed constants).
        instant_speed_ratio: ``instant_speed_count / count``; ``0.0`` when the deck has
            no interaction (documented convention — never NaN, never raises).
        cmc_distribution: ``(cmc_bucket, quantity-aware count)`` pairs over interaction
            cards, sorted ascending by bucket. Buckets are ``int(cmc)`` (floor —
            fractional ``cmc`` exists only on un-set cards; multi-face ``cmc`` is
            Scryfall's front-face value) — the same bucketing policy as 5.4's
            :class:`~src.logic.assessment.mana_base.CurveSignals`.
    """

    count: int
    instant_speed_count: int
    instant_speed_ratio: float
    cmc_distribution: tuple[tuple[int, int], ...]


def interaction_signals(deck_cards: Sequence[DeckCard]) -> InteractionSignals:
    """Compute the FR7 interaction-detail signals, quantity-aware and zero-safe.

    Joins :func:`classify_card`'s ``INTERACTION`` tag back to each card's type line,
    keywords, and ``cmc`` (the per-card join the 5.3 docstring promises 5.5). An empty
    or interaction-free deck yields zeroed signals — never raises. Sideboard rows are
    included — filter first if unwanted.

    Args:
        deck_cards: The deck's card associations.

    Returns:
        The frozen :class:`InteractionSignals`.
    """
    count = 0
    instant_speed_count = 0
    buckets: dict[int, int] = {}

    for deck_card in deck_cards:
        card = deck_card.card
        if INTERACTION not in classify_card(card):
            continue
        count += deck_card.quantity
        if _is_instant_speed(card):
            instant_speed_count += deck_card.quantity
        bucket = int(card.cmc)
        buckets[bucket] = buckets.get(bucket, 0) + deck_card.quantity

    return InteractionSignals(
        count=count,
        instant_speed_count=instant_speed_count,
        instant_speed_ratio=instant_speed_count / count if count else 0.0,
        cmc_distribution=tuple(sorted(buckets.items())),
    )


# ---------------------------------------------------------------------------
# FR9 structural-coverage gaps (Task 6)
# ---------------------------------------------------------------------------

# The closed structural_gaps token vocabulary (AD-6) — this module owns it; Epic 7's
# flags.structural_gaps serializes exactly these tokens, sorted bytewise (AD-8). Tokens
# are count-free snake_case: counts already live in the redundancy/classify_deck signals.
# Land adequacy is deliberately NOT a gap token — 5.4's Karsten flood/screw flags already
# own land-count adequacy, and two sources for one fact would let them disagree.

#: FR9 gap token: card-draw count below the formula baseline.
CARD_DRAW_BELOW_BASELINE: Final = "card_draw_below_baseline"
#: FR9 gap token: interaction count below the formula baseline.
INTERACTION_BELOW_BASELINE: Final = "interaction_below_baseline"
#: FR9 gap token: ramp count below the formula baseline.
RAMP_BELOW_BASELINE: Final = "ramp_below_baseline"
#: FR9 gap token: no card tagged with any ``WINCON_*`` category.
WINCON_MISSING: Final = "wincon_missing"

#: The closed token set in fixed documented order — defined already bytewise-sorted so
#: the documented order and the AD-8 emission order coincide.
STRUCTURAL_GAP_TOKENS: Final[tuple[str, ...]] = (
    CARD_DRAW_BELOW_BASELINE,
    INTERACTION_BELOW_BASELINE,
    RAMP_BELOW_BASELINE,
    WINCON_MISSING,
)

#: PROVISIONAL per-formula gap baselines (Story 5.9's benchmark pass owns tuning) —
#: "below baseline" means ``count < baseline`` (strictly less), quantity-aware counts.
#: Commander: the documented "<6 ramp or <6 interaction is a weakness signal" line
#: (docs/deck-assess.md:123); the Command Zone template (~10/10/10) is the aspirational
#: reference, the 6-line is the *gap* threshold — 8×8 theory. Sixty-card: ramp is not a
#: structural requirement (baseline 0 → the token simply never fires); draw 4 /
#: interaction 6 are honest provisional guesses that 5.9's Standard anchors calibrate.
#: Consequence: :data:`RAMP_BELOW_BASELINE` is permanently unreachable for every
#: ``sixty_card`` deck (a quantity-aware count can never be negative) — intentional, not
#: a bug; ramp simply isn't part of the 60-card structural-coverage read.
STRUCTURAL_GAP_BASELINES: Final[dict[KarstenFormula, dict[str, int]]] = {
    "commander": {RAMP: 6, CARD_DRAW: 6, INTERACTION: 6},
    "sixty_card": {RAMP: 0, CARD_DRAW: 4, INTERACTION: 6},
}

#: The below-baseline checks: (category token, gap token) pairs.
_BELOW_BASELINE_CHECKS: Final[tuple[tuple[str, str], ...]] = (
    (CARD_DRAW, CARD_DRAW_BELOW_BASELINE),
    (INTERACTION, INTERACTION_BELOW_BASELINE),
    (RAMP, RAMP_BELOW_BASELINE),
)

#: The three win-condition tags whose union feeds :data:`WINCON_MISSING`.
_WINCON_TAGS: Final[tuple[str, ...]] = (
    WINCON_COMBO_PIECE,
    WINCON_EXPLICIT,
    WINCON_FINISHER,
)


def structural_gaps(deck_cards: Sequence[DeckCard], *, formula: KarstenFormula) -> tuple[str, ...]:
    """Compute the FR9 8×8 structural-coverage gap tokens for a deck.

    Evaluates :func:`classify_deck` counts against the provisional per-formula baseline
    table (:data:`STRUCTURAL_GAP_BASELINES`); :data:`WINCON_MISSING` fires when the union
    of the three ``WINCON_*`` tags is empty. An empty deck simply falls below every
    baseline — tokens are emitted, nothing raises. Sideboard rows are included — filter
    first if unwanted.

    Args:
        deck_cards: The deck's card associations.
        formula: The format fork — ``"commander"`` or ``"sixty_card"`` — as an explicit
            parameter so this module stays profile-independent (the
            :data:`KarstenFormula` selector 5.4 established; the 5.7/5.8 caller picks
            per format).

    Returns:
        A tuple of :data:`STRUCTURAL_GAP_TOKENS` members, sorted ascending bytewise
        (AD-8), deterministic for identical input.
    """
    counts = classify_deck(deck_cards)
    baselines = STRUCTURAL_GAP_BASELINES[formula]
    gaps = [
        gap_token
        for category, gap_token in _BELOW_BASELINE_CHECKS
        if counts[category].count < baselines[category]
    ]
    if all(counts[tag].count == 0 for tag in _WINCON_TAGS):
        gaps.append(WINCON_MISSING)
    return tuple(sorted(gaps))

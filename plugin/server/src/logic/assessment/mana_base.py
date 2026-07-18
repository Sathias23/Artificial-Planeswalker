"""FR5/FR8 mana-base & curve signals for deck-power assessment (Story 5.4).

Raw numeric mana signals only: the curve distribution, average mana value, Karsten
land-count recommendations, and per-color pip/source consistency. Downstream stories map
these onto scores — the signal→0–100 ``mana_efficiency`` mapping is Story 5.7/5.8's, and
the hypergeometric consistency math over the land count is Story 5.5's. Everything here is
a pure function over already-loaded Pydantic schemas (:class:`Card` / :class:`DeckCard`) —
no network, DB, clock, or file I/O (AD-2) — and every result is a frozen dataclass with
deterministically ordered contents (AD-8 spirit).

Deliberately independent of :mod:`src.logic.mana_curve` (the Epic-1 ``analyze_mana_curve``
tool's engine): that module takes duplicate-expanded ``list[Card]``, raises ``ValueError``
on an empty deck, and returns prose coaching output — all wrong for the assessment core,
whose input is quantity-aware ``Sequence[DeckCard]`` and whose outputs must degrade (never
raise) and stay prose-free (AD-8: phrasing happens at the edge). The legacy module keeps
serving its own tool; do not import it here (AC1).

Sideboard rows are NOT filtered — deck-composition policy belongs to the caller: filter
``sideboard=False`` first if you want played-cards-only signals (the 5.3 precedent).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from src.data.schemas.card import Card
from src.data.schemas.deck import DeckCard
from src.logic.assessment.classifiers import CARD_DRAW, RAMP, classify_card

#: The five colors in canonical WUBRG order (project convention) — the fixed closed
#: shape of :func:`compute_pip_signals` (AD-7 spirit: no colors-present-conditional keys).
WUBRG: Final[tuple[str, ...]] = ("W", "U", "B", "R", "G")

# ---------------------------------------------------------------------------
# Karsten constants (Task 3) — published coefficients are exact; tolerances are
# provisional (Story 5.9's benchmark pass owns tuning them).
# ---------------------------------------------------------------------------

#: Karsten's "cheap" cutoff for the card-draw/ramp land-count reduction: MV <= 2
#: (addendum §C / docs/deck-assess.md:125). 5.3 deliberately did not pre-filter by cost —
#: this module owns the cutoff.
CHEAP_DRAW_RAMP_CMC_MAX: Final = 2

#: Karsten 99-card Commander regression: lands ≈ 31.42 + 3.13·avgMV − 0.28·(cheap draw+ramp)
#: (addendum §C, verbatim — published constants, asserted exactly in tests).
KARSTEN_COMMANDER_COEFFICIENTS: Final[tuple[float, float, float]] = (31.42, 3.13, 0.28)
#: Karsten 60-card regression: lands ≈ 19.59 + 1.90·avgMV − 0.28·(cheap draw+ramp)
#: (addendum §C, verbatim).
KARSTEN_SIXTY_CARD_COEFFICIENTS: Final[tuple[float, float, float]] = (19.59, 1.90, 0.28)

#: Flood/screw band: |actual − recommended| beyond this many lands raises the risk flag.
#: PROVISIONAL v1 value — Story 5.9's benchmark pass owns tuning; tests reference this
#: constant rather than hard-coding it.
KARSTEN_TOLERANCE_LANDS: Final = 2.0

#: The AC3/AC4 formula selector type — format choice enters as an explicit parameter so
#: this module stays profile-independent (the 5.7/5.8 caller picks per format, AC5).
KarstenFormula = Literal["commander", "sixty_card"]

_FORMULA_COEFFICIENTS: Final[dict[KarstenFormula, tuple[float, float, float]]] = {
    "commander": KARSTEN_COMMANDER_COEFFICIENTS,
    "sixty_card": KARSTEN_SIXTY_CARD_COEFFICIENTS,
}

# ---------------------------------------------------------------------------
# Land detection — one helper owns the policy (Task 1)
# ---------------------------------------------------------------------------


def _is_land(type_line: str) -> bool:
    """True when the type line marks a land — the shared substring policy.

    Matches ``classifiers.py`` / ``mana_curve.py``: ``"land" in type_line.lower()``.
    Consequence (documented v1 policy): a multi-face card whose ``//``-joined top-level
    type line contains a Land face (an MDFC "Creature // Land") counts as a land and is
    excluded from the curve and average mana value — the conservative "land-slot material"
    reading 5.3 established for ramp exclusion.
    """
    return "land" in type_line.lower()


# ---------------------------------------------------------------------------
# FR5 curve signals (Task 2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CurveSignals:
    """The FR5 curve read of a deck: distribution, average MV, land/spell counts.

    Attributes:
        distribution: ``(cmc_bucket, quantity-aware count)`` pairs for non-land cards,
            sorted ascending by bucket. Buckets are ``int(cmc)`` (floor — fractional
            ``cmc`` exists only on un-set cards; multi-face ``cmc`` is Scryfall's
            front-face value). Empty when the deck has no non-land cards.
        average_mana_value: Quantity-weighted mean ``cmc`` over non-land cards;
            ``0.0`` when there are no spells (never raises on empty input).
        land_count: Quantity-aware count of Land-typed cards.
        spell_count: Quantity-aware count of non-land cards.
    """

    distribution: tuple[tuple[int, int], ...]
    average_mana_value: float
    land_count: int
    spell_count: int


def compute_curve(deck_cards: Sequence[DeckCard]) -> CurveSignals:
    """Compute the FR5 curve signals over a deck, quantity-aware and zero-safe.

    Args:
        deck_cards: The deck's card associations (each carries ``quantity`` and the
            nested ``Card``). Sideboard rows are included — filter first if unwanted.

    Returns:
        The frozen :class:`CurveSignals`; an empty or all-land input yields zeroed
        signals rather than raising.
    """
    buckets: dict[int, int] = {}
    land_count = 0
    spell_count = 0
    cmc_total = 0.0

    for deck_card in deck_cards:
        card = deck_card.card
        if _is_land(card.type_line):
            land_count += deck_card.quantity
            continue
        spell_count += deck_card.quantity
        cmc_total += card.cmc * deck_card.quantity
        bucket = int(card.cmc)
        buckets[bucket] = buckets.get(bucket, 0) + deck_card.quantity

    return CurveSignals(
        distribution=tuple(sorted(buckets.items())),
        average_mana_value=cmc_total / spell_count if spell_count else 0.0,
        land_count=land_count,
        spell_count=spell_count,
    )


# ---------------------------------------------------------------------------
# FR8 Karsten land-count delta (Task 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KarstenLandSignal:
    """The FR8 Karsten land-count read: recommendation, actuals, and risk flags.

    Attributes:
        recommended_lands: The formula's recommended land count (float, unrounded).
        actual_lands: Quantity-aware count of Land-typed cards in the input.
        delta: ``actual_lands - recommended_lands`` (negative = fewer lands than
            recommended).
        cheap_draw_ramp_count: The 0.28-term input — quantity-aware count of non-land
            cards tagged ``RAMP`` or ``CARD_DRAW`` with ``cmc <=``
            :data:`CHEAP_DRAW_RAMP_CMC_MAX`; surfaced for explainability (NFR2).
        mana_screw_risk: ``delta < -``:data:`KARSTEN_TOLERANCE_LANDS` — too few lands.
        mana_flood_risk: ``delta > +``:data:`KARSTEN_TOLERANCE_LANDS` — too many lands.
    """

    recommended_lands: float
    actual_lands: int
    delta: float
    cheap_draw_ramp_count: int
    mana_screw_risk: bool
    mana_flood_risk: bool


def _cheap_draw_ramp_count(deck_cards: Sequence[DeckCard]) -> int:
    """Count cheap card-draw/ramp spells (the Karsten 0.28-term), quantity-aware.

    Joins 5.3's classifier tags back to ``cmc`` (the intended ``classify_card`` join):
    a non-land card tagged ``RAMP`` or ``CARD_DRAW`` with ``cmc`` at most
    :data:`CHEAP_DRAW_RAMP_CMC_MAX` counts once per copy — a card holding both tags is
    still one spell slot (AC3). Land-typed cards are never spell slots.
    """
    cheap = 0
    for deck_card in deck_cards:
        card = deck_card.card
        if _is_land(card.type_line):
            continue
        if card.cmc <= CHEAP_DRAW_RAMP_CMC_MAX and classify_card(card) & {RAMP, CARD_DRAW}:
            cheap += deck_card.quantity
    return cheap


def karsten_land_delta(
    deck_cards: Sequence[DeckCard], *, formula: KarstenFormula
) -> KarstenLandSignal:
    """Compute the FR8 Karsten recommended-land delta and flood/screw risk flags.

    Args:
        deck_cards: The deck's card associations. Sideboard rows are included — filter
            first if unwanted.
        formula: Which published regression to apply — ``"commander"`` (99-card) or
            ``"sixty_card"``. An explicit parameter so this module stays
            profile-independent (AC5); the 5.7/5.8 caller selects per format.

    Returns:
        The frozen :class:`KarstenLandSignal`; an empty deck degrades to the formula
        intercept rather than raising.
    """
    curve = compute_curve(deck_cards)
    intercept, mv_coefficient, cheap_coefficient = _FORMULA_COEFFICIENTS[formula]
    cheap = _cheap_draw_ramp_count(deck_cards)
    recommended = intercept + mv_coefficient * curve.average_mana_value - cheap_coefficient * cheap
    delta = curve.land_count - recommended
    return KarstenLandSignal(
        recommended_lands=recommended,
        actual_lands=curve.land_count,
        delta=delta,
        cheap_draw_ramp_count=cheap,
        mana_screw_risk=delta < -KARSTEN_TOLERANCE_LANDS,
        mana_flood_risk=delta > KARSTEN_TOLERANCE_LANDS,
    )


# ---------------------------------------------------------------------------
# FR8 pip demand & colored sources (Task 4)
# ---------------------------------------------------------------------------

# Mana-cost symbols: the {...} tokens of a cost string. Only bare monocolor symbols
# ({W}..{G}) count as hard pip demand — hybrid {G/U}, Phyrexian {G/P}, and twobrid {2/W}
# are each payable without that color's source, so counting them would overstate the
# requirement (documented v1 policy; Story 5.9 may weight them). Split cards store a
# "{1}{G} // {2}{U}" joined cost, which parses as written (mild double-count, accepted v1).
_MANA_SYMBOL_RE: Final = re.compile(r"\{([^}]+)\}")

# Colored-source detection over Land-typed cards. No produced-mana field exists in the
# schema/DB, so sources are derived from two signals plus the any-color phrase:
#   1. basic land types in the type line (basics, snow basics, typed duals like
#      "Land — Island Mountain");
#   2. "add {w}"-style symbols in the RAW lowercased oracle text (pain lands, duals
#      without basic types). Deliberately NOT reminder-stripped, unlike 5.3's
#      classifier text: a basic's whole mana ability is reminder text, and for nonbasic
#      lands reminder text about mana production is accurate, not a false positive.
# Accepted v1 undercounts (5.9 calibration options): fetchlands (produce nothing
# themselves), unusual production wordings, and non-land sources (dorks/rocks —
# Karsten's primary tables count lands).
_BASIC_LAND_TYPE_RES: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"\bplains\b"), "W"),
    (re.compile(r"\bisland\b"), "U"),
    (re.compile(r"\bswamp\b"), "B"),
    (re.compile(r"\bmountain\b"), "R"),
    (re.compile(r"\bforest\b"), "G"),
)
_ADD_SYMBOL_RES: Final[tuple[tuple[re.Pattern[str], str], ...]] = tuple(
    (re.compile(r"\badd\b[^.\n]*\{" + color.lower() + r"\}"), color) for color in WUBRG
)
# "Add one mana of any color" -> a source for all five colors, UNLESS the grant is
# conditional (e.g. Reflecting Pool "...that a land you control could produce", Exotic
# Orchard "...that a land your opponents control could produce"): a trailing "that"
# clause narrows the color to something other than "any", so it is excluded. Command
# Tower's "...in your commander's color identity" is not narrowed by a "that" clause and
# stays an accepted v1 false positive (unconditional in practice for most decks).
_ANY_COLOR_UNCONDITIONAL_RE: Final = re.compile(r"add one mana of any color(?!\s+that\b)")

#: Karsten colored-source anchors, 60-card: max pip intensity -> recommended sources.
#: 1 pip ≈ 14 and 2 pips ≈ 18 are published values (docs/deck-assess.md:155); the
#: 3+-pip anchor of 20 is a PROVISIONAL extrapolation — Story 5.9 owns tuning it.
PIP_SOURCE_ANCHORS_SIXTY_CARD: Final[dict[int, int]] = {1: 14, 2: 18, 3: 20}
#: PROVISIONAL Commander anchors: the 60-card values linearly scaled by deck size
#: (99/60 ≈ 1.65 -> 23/30/33). Karsten's real Commander tables differ — this documented
#: linear scale is an honest v1 that Story 5.9's benchmark pass can replace.
PIP_SOURCE_ANCHORS_COMMANDER: Final[dict[int, int]] = {1: 23, 2: 30, 3: 33}

_FORMULA_ANCHORS: Final[dict[KarstenFormula, dict[int, int]]] = {
    "commander": PIP_SOURCE_ANCHORS_COMMANDER,
    "sixty_card": PIP_SOURCE_ANCHORS_SIXTY_CARD,
}
#: Pip intensities above this use the top anchor (the tables stop at 3+).
_MAX_ANCHORED_PIPS: Final = 3


@dataclass(frozen=True, slots=True)
class ColorPipSignal:
    """One color's FR8 pip-demand vs colored-source read.

    Attributes:
        color: ``"W" | "U" | "B" | "R" | "G"`` — results always cover all five, in
            WUBRG order (fixed closed shape).
        pip_count: Quantity-aware total of this color's bare pips across non-land mana
            costs.
        max_pips_single_card: The largest pip count of this color in any single card's
            cost — the Karsten source-requirement determinant.
        source_count: Quantity-aware count of Land-typed cards that can produce this
            color (detection policy documented on the module constants).
        recommended_sources: The anchor value for ``max_pips_single_card`` (``0`` when
            the deck has no demand for this color).
        deficit: ``max(0, recommended_sources - source_count)`` — a color with zero
            demand has no deficit.
    """

    color: str
    pip_count: int
    max_pips_single_card: int
    source_count: int
    recommended_sources: int
    deficit: int


def _pip_cost(card: Card) -> str:
    """Return the cost string to parse for pips.

    Top-level ``mana_cost`` is never ``None`` (schema coercion) but is ``""`` for most
    multi-face cards — fall back to the FRONT face's cost, consistent with Scryfall
    keeping the front face's ``cmc`` at top level. Face fields can be an explicit
    ``None`` (the 5.3 null-face lesson), hence ``or ""``.
    """
    if card.mana_cost or not card.card_faces:
        return card.mana_cost
    return card.card_faces[0].get("mana_cost") or ""


def _source_text(card: Card) -> str:
    """Return the raw lowercased oracle text for source detection (faces joined).

    Mirrors 5.3's empty-top-level fallback but deliberately without reminder-stripping
    (see the detection-policy comment on the module constants).
    """
    text = card.oracle_text
    if not text and card.card_faces:
        text = "\n".join(face.get("oracle_text") or "" for face in card.card_faces)
    return text.lower()


def _land_source_colors(card: Card) -> frozenset[str]:
    """Return the colors a Land-typed card can produce, per the documented v1 policy."""
    type_line = card.type_line.lower()
    text = _source_text(card)
    if _ANY_COLOR_UNCONDITIONAL_RE.search(text):
        return frozenset(WUBRG)
    colors = {color for pattern, color in _BASIC_LAND_TYPE_RES if pattern.search(type_line)}
    colors.update(color for pattern, color in _ADD_SYMBOL_RES if pattern.search(text))
    return frozenset(colors)


def compute_pip_signals(
    deck_cards: Sequence[DeckCard], *, formula: KarstenFormula
) -> tuple[ColorPipSignal, ...]:
    """Compute the FR8 per-color pip-demand and colored-source adequacy signals.

    Args:
        deck_cards: The deck's card associations. Sideboard rows are included — filter
            first if unwanted.
        formula: Selects the source-anchor table — ``"sixty_card"`` uses the published
            Karsten anchors, ``"commander"`` the provisional deck-size-scaled ones —
            exactly like :func:`karsten_land_delta`'s selector (AC4/AC5).

    Returns:
        A frozen five-tuple, always all colors in WUBRG order; empty or colorless-only
        input yields zeroed signals rather than raising.
    """
    anchors = _FORMULA_ANCHORS[formula]
    pip_counts = dict.fromkeys(WUBRG, 0)
    max_pips = dict.fromkeys(WUBRG, 0)
    source_counts = dict.fromkeys(WUBRG, 0)

    for deck_card in deck_cards:
        card = deck_card.card
        if _is_land(card.type_line):
            for color in _land_source_colors(card):
                source_counts[color] += deck_card.quantity
            continue
        symbols = _MANA_SYMBOL_RE.findall(_pip_cost(card))
        for color in WUBRG:
            pips = sum(1 for symbol in symbols if symbol == color)
            if pips:
                pip_counts[color] += pips * deck_card.quantity
                max_pips[color] = max(max_pips[color], pips)

    signals = []
    for color in WUBRG:
        recommended = anchors[min(max_pips[color], _MAX_ANCHORED_PIPS)] if max_pips[color] else 0
        signals.append(
            ColorPipSignal(
                color=color,
                pip_count=pip_counts[color],
                max_pips_single_card=max_pips[color],
                source_count=source_counts[color],
                recommended_sources=recommended,
                deficit=max(0, recommended - source_counts[color]),
            )
        )
    return tuple(signals)

"""FR16/FR18 dimension vector, Commander Bracket floor & cEDH candidacy (Story 5.7).

The seam where raw signals become scores: this module consumes the 5.3-5.6 signal
emitters (:mod:`classifiers`, :mod:`mana_base`, :mod:`consistency`, :mod:`combos`) plus
the :class:`~src.logic.assessment.profiles.FormatProfile` and produces the fixed
7-dimension integer vector (FR16, AD-7), the WotC Bracket decision-tree floor (FR18),
and the cEDH candidacy flag — candidacy only, never an asserted Bracket 5. Everything is
a pure function over already-loaded schemas — no network, DB, clock, randomness, or
logging (AD-2); identical input always yields identical output (AD-8 spirit).

Decide-once policies (each documented at its code site):

- **Rounding:** every dimension passes through :func:`_to_score` — clamp to
  ``[0.0, 100.0]`` then round half-up via ``int(x + 0.5)`` (never ``round()``, whose
  banker's rounding at ``.5`` is a reviewer surprise).
- **Baseline floor 2, cap 4:** Brackets 1 and 5 are intent-declared, so the computed
  floor range is ``{2, 3, 4}`` (see :data:`BASELINE_BRACKET_FLOOR`).
- **Chain refinement:** the extra-turn refinement 5.3 deferred here — a quantity-aware
  count of :data:`~src.logic.assessment.classifiers.EXTRA_TURN` cards at or above
  :data:`EXTRA_TURN_CHAIN_MIN` is chain-capable; a single extra-turn card never raises
  the floor (WotC's "low quantities, not chained" language).
- **Included-only floor raises:** only ``bucket == "included"`` combo records ever raise
  the floor — an ``almost_included`` combo is not in the deck, and a ``bucket=None``
  record (never matched) contributes nothing anywhere, treated explicitly rather than
  falling through an ``if/elif`` (the 5.6 defense-in-depth lesson).
- **Tutors never feed the floor:** WotC removed tutor restrictions from Brackets in
  Oct 2025 (docs/deck-assess.md:119; the ``classifiers.TUTOR`` docstring warning) —
  tutor counts inform cEDH candidacy and the soft dimensions only.
- **Sideboard rows are NOT filtered** (standing 5.3-5.6 policy): deck-composition
  belongs to the caller; Epic 7 passes mainboard-only rows.
- **One ``classify_deck`` per entry point** (the logged 5.3 deferred-work item): each
  public function classifies the deck exactly once and feeds every gate from those locals
  — never ``detect_mass_land_denial`` + ``detect_extra_turn_cards`` back-to-back, and
  opener/land-access probabilities are computed from the locals via
  :func:`~src.logic.assessment.consistency.probability_at_least` rather than through
  ``redundancy_signals``/``land_access_by_turn`` (which would re-classify / re-curve
  internally). ``compute_curve`` is likewise called once directly, but some sanctioned
  sibling signal APIs re-derive shared data internally (``karsten_land_delta`` re-runs
  ``compute_curve``; ``earliest_turn_estimate`` rebuilds its name→cmc index per call), so
  the deck may be scanned more than once per public call — cheap and correctness-neutral;
  not worth threading pre-computed arguments through their signatures.

All mapping curves and gate constants are PROVISIONAL v1 values — Story 5.9 hand-tunes
them against the calibration benchmark (NFR8). Tests verify shape, clamps, and monotone
directions, never exact curve outputs.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from src.data.schemas.combo import ComboRecord
from src.data.schemas.deck import DeckCard
from src.logic.assessment.classifiers import (
    CARD_DRAW,
    EXTRA_TURN,
    MASS_LAND_DENIAL,
    RAMP,
    TUTOR,
    WINCON_COMBO_PIECE,
    WINCON_EXPLICIT,
    WINCON_FINISHER,
    classify_deck,
)
from src.logic.assessment.combos import (
    BRACKET_TAG_TO_BRACKET,
    MULTI_CARD_INFINITE,
    NON_INFINITE,
    TWO_CARD_INFINITE,
    combo_type,
    earliest_turn_estimate,
)
from src.logic.assessment.consistency import (
    OPENING_HAND_SIZE,
    STRUCTURAL_GAP_BASELINES,
    InteractionSignals,
    cards_seen_by_turn,
    interaction_signals,
    probability_at_least,
)
from src.logic.assessment.mana_base import (
    KARSTEN_TOLERANCE_LANDS,
    CurveSignals,
    KarstenFormula,
    compute_curve,
    compute_pip_signals,
    karsten_land_delta,
)
from src.logic.assessment.profiles import FormatProfile

# ---------------------------------------------------------------------------
# Bracket-floor gate constants (AC4/AC5) — PROVISIONAL v1, Story 5.9 owns tuning
# ---------------------------------------------------------------------------

#: The computed floor's baseline (decide-once): Bracket 1 (Exhibition) is intent-declared
#: exactly like Bracket 5 — card data cannot distinguish a deliberate theme build from a
#: core deck, and WotC's own guidance is "bracket up when in doubt" — so the computed
#: floor never claims B1 (effective range ``{2, 3, 4}``). FR18's "1-5" is the scale
#: domain, not an emission requirement. This also anchors the 5.1 benchmark (precons
#: expected ~B2; 5.9 tolerance ``[expected, expected+1]``).
BASELINE_BRACKET_FLOOR: Final = 2

#: The computed floor's cap: Bracket 5 is never asserted — :attr:`BracketFloorSignal.cedh_candidate`
#: is the only Bracket-5 surface (FR18).
BRACKET_FLOOR_MAX: Final = 4

#: Game Changer gate (addendum §C): ``1-3`` confirmed Game Changers floor at Bracket 3.
GC_BRACKET_THREE_MIN: Final = 1

#: Game Changer gate (addendum §C): ``>= 4`` confirmed Game Changers floor at Bracket 4.
GC_BRACKET_FOUR_MIN: Final = 4

#: Extra-turn chain threshold (the 5.3-deferred chain refinement, provisional): a deck
#: with this many extra-turn effects (quantity-aware) is chain-capable -> floor 4. A
#: single Time Warp is a B2/B3-legal quantity per WotC's "low quantities, not chained".
EXTRA_TURN_CHAIN_MIN: Final = 2

#: Early-combo gate (provisional): an included two-card infinite deployable by this turn
#: (per :func:`~src.logic.assessment.combos.earliest_turn_estimate`) floors at Bracket 4.
EARLY_COMBO_TURN_MAX: Final = 6

#: cEDH candidacy leg (provisional): an included infinite combo deployable by this turn.
CEDH_COMBO_TURN_MAX: Final = 4

#: cEDH candidacy leg (5.9 benchmark-tuned): quantity-aware ``TUTOR`` count at or above
#: this. Tutors inform candidacy only — never the floor (see the module docstring).
#: Tuned 4 -> 3 by the Story 5.9 benchmark: the classifier's FR6 tutor definition
#: (search to hand/top of library) deliberately excludes battlefield tutors (Green Sun's
#: Zenith class) and library-exile effects (Demonic Consultation class), so real cEDH
#: lists undercount — the committed Kinnan list carries exactly 3 tagged tutors (Gamble,
#: Mystical Tutor, Worldly Tutor) and failed candidacy on this leg alone at 4. A shared
#: tuning constant: this change bumped BOTH format_profile_versions (v3 -> v4, AC9).
CEDH_TUTOR_MIN: Final = 3

#: cEDH candidacy leg (provisional): average mana value at or below this (dense fast
#: mana + compact early combo — docs/deck-assess.md:186).
CEDH_AVG_MV_MAX: Final = 2.5

# ---------------------------------------------------------------------------
# Dimension-curve constants — PROVISIONAL v1 (5.9 owns the numbers). Per-format
# parameters are Final dicts keyed by KarstenFormula (the 5.4 _FORMULA_ANCHORS /
# 5.5 STRUCTURAL_GAP_BASELINES precedent) rather than new profile fields (AC6).
# ---------------------------------------------------------------------------

#: ``speed``: avgMV pivot — each point of average mana value above/below this shifts the
#: win-turn estimate a turn later/earlier.
_SPEED_AVG_MV_PIVOT: Final = 3.0
#: ``speed``: ramp acceleration — this many ramp spells buy one turn (Commander rule of
#: thumb: ~5 ramp ≈ one turn faster), capped at :data:`_SPEED_RAMP_TURN_CAP` turns.
_SPEED_RAMP_PER_TURN: Final = 5.0
_SPEED_RAMP_TURN_CAP: Final = 2.0
#: ``speed``: an included infinite combo shortcuts the estimate to its earliest turn
#: plus this pad (assembling is not winning on the spot).
_SPEED_COMBO_TURN_PAD: Final = 1.0
#: ``speed``: linear-map padding around the profile's ``win_turn_band`` — the estimate
#: maps ``[band hi + pad -> 0, band lo - pad -> 100]``.
_SPEED_BAND_PAD: Final = 2.0

#: ``consistency``: opener-probability blend weights (each opener already ``[0, 1]``).
_CONSISTENCY_DRAW_WEIGHT: Final = 0.35
_CONSISTENCY_RAMP_WEIGHT: Final = 0.25
_CONSISTENCY_WINCON_WEIGHT: Final = 0.25
_CONSISTENCY_LAND_WEIGHT: Final = 0.15
#: ``consistency``: the land-access blend term reads P(made every land drop) by this turn.
_CONSISTENCY_LAND_ACCESS_TURN: Final = 4
#: Tutor bonuses are additive-only (never part of a ratio) so "adding a tutor never
#: lowers the score" — a 5.9 monotonicity property — holds by construction; capped so
#: tutel density cannot dominate a curve.
_TUTOR_BONUS_COUNT_CAP: Final = 6
_TUTOR_CONSISTENCY_BONUS: Final = 2.0
_TUTOR_CARD_ADVANTAGE_BONUS: Final = 3.0

#: ``resilience`` blend weights (documented proxy — see :func:`dimension_vector`).
_RESILIENCE_WIN_ROUTE_WEIGHT: Final = 40.0
_RESILIENCE_INSTANT_WEIGHT: Final = 30.0
_RESILIENCE_DRAW_WEIGHT: Final = 30.0
#: The three win-route categories whose non-zero count feeds the resilience blend.
_WIN_ROUTE_CATEGORIES: Final[tuple[str, ...]] = (
    WINCON_COMBO_PIECE,
    WINCON_EXPLICIT,
    WINCON_FINISHER,
)

#: ``interaction`` targets: total interaction count that maxes the count term.
#: Commander 10 = the Command Zone template (docs/deck-assess.md:123-125); sixty-card 8
#: is an honest provisional guess for 1v1.
_INTERACTION_TARGETS: Final[dict[KarstenFormula, int]] = {"commander": 10, "sixty_card": 8}
#: ``interaction`` sub-targets: instant-speed and cheap (cmc <= 2) interaction counts
#: that max their terms — counts, deliberately NOT the recommended ratio blend: a ratio
#: term lets one sorcery-speed (or expensive) addition dilute the share faster than the
#: count term compensates, inverting the AC8 "swapping filler for interaction never
#: lowers interaction" direction; count-based sub-terms are monotone under any
#: interaction swap by construction.
_INSTANT_INTERACTION_TARGETS: Final[dict[KarstenFormula, int]] = {"commander": 5, "sixty_card": 4}
_CHEAP_INTERACTION_TARGETS: Final[dict[KarstenFormula, int]] = {"commander": 5, "sixty_card": 4}
#: ``interaction``: the cheap-interaction cmc cutoff (mirrors Karsten's cheap cutoff).
_CHEAP_INTERACTION_CMC_MAX: Final = 2
#: ``interaction`` term weights (sum 100).
_INTERACTION_COUNT_WEIGHT: Final = 70.0
_INTERACTION_INSTANT_WEIGHT: Final = 20.0
_INTERACTION_CHEAP_WEIGHT: Final = 10.0

#: ``mana_efficiency`` penalties: points per land beyond the Karsten tolerance band and
#: points per missing colored source (the 5.4 pip deficit).
_LAND_DELTA_PENALTY: Final = 6.0
_PIP_DEFICIT_PENALTY: Final = 3.0

#: ``card_advantage`` targets: draw count that maxes the count term (Commander 10 = the
#: Command Zone template; sixty-card 6 provisional).
_DRAW_TARGETS: Final[dict[KarstenFormula, int]] = {"commander": 10, "sixty_card": 6}
_CARD_ADVANTAGE_COUNT_WEIGHT: Final = 80.0

#: ``combo_potential`` credit per record by derived combo type; an ``almost_included``
#: record earns half its included credit (partial credit — it never touches the floor).
_COMBO_TYPE_CREDIT: Final[dict[str, float]] = {
    TWO_CARD_INFINITE: 50.0,
    MULTI_CARD_INFINITE: 30.0,
    NON_INFINITE: 15.0,
}
#: ``combo_potential`` earliness bonus per included infinite record:
#: ``max(0, (anchor - earliest_turn) * per_turn)``.
_COMBO_EARLINESS_TURN_ANCHOR: Final = 10
_COMBO_EARLINESS_PER_TURN: Final = 2.0


# ---------------------------------------------------------------------------
# Shared rounding policy (AC2)
# ---------------------------------------------------------------------------


def _to_score(value: float) -> int:
    """Clamp to ``[0.0, 100.0]`` then round half-up — the one shared rounding policy.

    ``int(x + 0.5)`` rather than ``round()``: Python's banker's rounding sends ``.5``
    cases to the nearest EVEN integer (``round(2.5) == 2``), a reviewer surprise;
    determinism holds either way, clarity wins. Every dimension passes through here.
    """
    clamped = min(100.0, max(0.0, value))
    return int(clamped + 0.5)


# ---------------------------------------------------------------------------
# Game Changer signal (AC3) — the AD-4 read side
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GameChangerSignal:
    """The deck-level Game Changer read — three states kept distinct (AD-4, FR11).

    ``Card.game_changer`` is ``bool | None`` and ``None`` is NEVER coalesced: a card
    with unknown status counts in ``unknown_count`` only, never ``known_count`` (in
    either direction). The edge derives the ``game_changer_data_unavailable`` confidence
    token from ``unknown_count`` — emitting AD-6 vocabulary is not this module's job.

    Attributes:
        known_count: Quantity-aware count of cards whose ``game_changer is True``.
        card_names: Unique contributing (True-only) names, sorted ascending bytewise —
            Epic 7's ``flags.game_changers`` explainability payload.
        unknown_count: Quantity-aware count of cards whose ``game_changer is None``.
    """

    known_count: int
    card_names: tuple[str, ...]
    unknown_count: int


def game_changer_signal(deck_cards: Sequence[DeckCard]) -> GameChangerSignal:
    """Count confirmed and unknown Game Changers across a deck (AC3).

    Identity checks (``is True`` / ``is None``) keep the three states distinct — no bool
    coercion anywhere. Sideboard rows are NOT filtered (standing 5.3-5.6 policy); an
    empty deck yields a zeroed signal, never raises.

    Args:
        deck_cards: The deck's card associations (quantity-aware).

    Returns:
        The frozen :class:`GameChangerSignal`.
    """
    known = 0
    unknown = 0
    names: set[str] = set()
    for deck_card in deck_cards:
        if deck_card.card.game_changer is True:
            known += deck_card.quantity
            names.add(deck_card.card.name)
        elif deck_card.card.game_changer is None:
            unknown += deck_card.quantity
    return GameChangerSignal(
        known_count=known, card_names=tuple(sorted(names)), unknown_count=unknown
    )


# ---------------------------------------------------------------------------
# Bracket floor + cEDH candidacy (AC4/AC5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BracketFloorSignal:
    """The FR18 Bracket-floor result plus its NFR2 explainability payload.

    Attributes:
        floor: The computed Bracket floor, always in ``{2, 3, 4}`` (baseline 2, cap 4 —
            Brackets 1 and 5 are intent-declared, never computed).
        game_changers: The AC3 Game Changer read that fed the GC gate.
        mass_land_denial: Whether any ``MASS_LAND_DENIAL``-tagged card is present.
        mass_land_denial_names: Unique tagged card names, sorted ascending bytewise.
        extra_turn_chain: Whether the quantity-aware ``EXTRA_TURN`` count reaches
            :data:`EXTRA_TURN_CHAIN_MIN` (chain-capable).
        extra_turn_names: Unique ``EXTRA_TURN``-tagged card names, sorted — reported
            even below the chain threshold (a single Time Warp is worth explaining).
        early_two_card_infinite: Whether an included two-card infinite combo is
            deployable by :data:`EARLY_COMBO_TURN_MAX`.
        early_two_card_infinite_ids: The driving ``spellbook_id``s, sorted ascending
            bytewise.
        cedh_candidate: The AC5 candidacy flag — the ONLY Bracket-5 surface; candidacy,
            never an assertion.
    """

    floor: int
    game_changers: GameChangerSignal
    mass_land_denial: bool
    mass_land_denial_names: tuple[str, ...]
    extra_turn_chain: bool
    extra_turn_names: tuple[str, ...]
    early_two_card_infinite: bool
    early_two_card_infinite_ids: tuple[str, ...]
    cedh_candidate: bool


def bracket_floor(
    deck_cards: Sequence[DeckCard], *, matched_combos: Sequence[ComboRecord]
) -> BracketFloorSignal:
    """Walk the WotC Bracket decision tree to a floor — deterministic, capped at 4 (AC4).

    The floor is the ``max()`` of the gate contributions, clamped to
    :data:`BRACKET_FLOOR_MAX`:

    - baseline :data:`BASELINE_BRACKET_FLOOR` (2 — see the constant's rationale);
    - Game Changers from :func:`game_changer_signal`'s ``known_count`` ONLY —
      ``unknown_count`` never contributes (AD-4: an absent count must neither raise nor
      lower the floor): ``1-3 -> 3``, ``>= 4 -> 4``;
    - any mass-land-denial card ``-> 4``;
    - an extra-turn CHAIN (count ``>= 2``, quantity-aware) ``-> 4``; a single extra-turn
      card never raises the floor;
    - included combos only: an early two-card infinite ``-> 4``; any other included
      infinite ``-> 3``; every included combo also contributes its
      ``BRACKET_TAG_TO_BRACKET`` value. ``almost_included`` and ``bucket=None`` records
      never raise the floor — you cannot trigger a Bracket rule with a card you don't
      play.

    cEDH candidacy (AC5) is folded into the signal — see the field docs. Tutors and the
    average mana value are read for candidacy only, never the floor. Sideboard rows are
    NOT filtered; an empty deck with no combos yields floor 2 with all flags False.

    Args:
        deck_cards: The deck's card associations (quantity-aware).
        matched_combos: The OUTPUT of :func:`~src.logic.assessment.combos.match_combos`
            — records with ``bucket`` assigned. Records with ``bucket=None`` contribute
            nothing.

    Returns:
        The frozen :class:`BracketFloorSignal`; identical input yields identical output.
    """
    counts = classify_deck(deck_cards)  # the ONE classify_deck call (5.3 deferred item)
    curve = compute_curve(deck_cards)  # the ONE compute_curve call (cEDH avgMV leg)
    game_changers = game_changer_signal(deck_cards)

    floor = BASELINE_BRACKET_FLOOR
    if game_changers.known_count >= GC_BRACKET_FOUR_MIN:
        floor = max(floor, 4)
    elif game_changers.known_count >= GC_BRACKET_THREE_MIN:
        floor = max(floor, 3)

    mld_bucket = counts[MASS_LAND_DENIAL]
    mass_land_denial = mld_bucket.count > 0
    if mass_land_denial:
        floor = max(floor, 4)

    extra_bucket = counts[EXTRA_TURN]
    extra_turn_chain = extra_bucket.count >= EXTRA_TURN_CHAIN_MIN
    if extra_turn_chain:
        floor = max(floor, 4)

    early_ids: list[str] = []
    fast_infinite = False
    for record in matched_combos:
        if record.bucket != "included":
            # almost_included / bucket=None: explicitly no floor contribution (AC4).
            continue
        floor = max(floor, BRACKET_TAG_TO_BRACKET[record.bracket_tag])
        kind = combo_type(record)
        if kind == NON_INFINITE:
            continue
        earliest = earliest_turn_estimate(record, deck_cards)
        if kind == TWO_CARD_INFINITE and earliest <= EARLY_COMBO_TURN_MAX:
            floor = max(floor, 4)
            early_ids.append(record.spellbook_id)
        else:
            floor = max(floor, 3)
        if earliest <= CEDH_COMBO_TURN_MAX:
            fast_infinite = True

    floor = min(floor, BRACKET_FLOOR_MAX)

    # AC5 candidacy (provisional v1 rule; 5.9 may retune or relax to a k-of-n vote):
    # dense fast mana + tutors + compact early combo (docs/deck-assess.md:186). The
    # tutor count and average mana value inform THIS flag only, never the floor.
    cedh_candidate = (
        floor == BRACKET_FLOOR_MAX
        and fast_infinite
        and counts[TUTOR].count >= CEDH_TUTOR_MIN
        and curve.average_mana_value <= CEDH_AVG_MV_MAX
    )

    return BracketFloorSignal(
        floor=floor,
        game_changers=game_changers,
        mass_land_denial=mass_land_denial,
        mass_land_denial_names=mld_bucket.card_names,
        extra_turn_chain=extra_turn_chain,
        extra_turn_names=extra_bucket.card_names,
        early_two_card_infinite=bool(early_ids),
        early_two_card_infinite_ids=tuple(sorted(set(early_ids))),
        cedh_candidate=cedh_candidate,
    )


# ---------------------------------------------------------------------------
# The 7-dimension vector (AC2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DimensionVector:
    """The FR16 fixed-shape power vector — exactly one ``int`` per AD-7 dimension.

    One field per entry in :data:`~src.logic.assessment.profiles.DIMENSIONS`, in that
    order (the ``DimensionWeights`` precedent — mypy makes a missing or extra dimension
    a type error; a test pins the field names against ``DIMENSIONS``). All seven are
    always present for any format, each an integer in ``[0, 100]``.

    Attributes:
        speed: Expected-win-turn read (curve + ramp density + combo earliest turn — no
            goldfish simulation, FR16).
        consistency: Opener/land-access probability blend plus tutor bonus.
        resilience: Documented PROXY (see :func:`dimension_vector`).
        interaction: Interaction density, instant-speed and cheap-answer coverage.
        mana_efficiency: Karsten land delta + per-color pip deficits, penalty-mapped.
        card_advantage: Draw-engine density plus tutor bonus.
        combo_potential: Matched-combo credit (included > almost_included) + earliness.
    """

    speed: int
    consistency: int
    resilience: int
    interaction: int
    mana_efficiency: int
    card_advantage: int
    combo_potential: int


def _opener_probability(count: int, deck_size: int) -> float:
    """P(at least one of ``count`` copies in the opening hand) against ``deck_size``."""
    return probability_at_least(deck_size=deck_size, copies=count, drawn=OPENING_HAND_SIZE)


def _speed_score(
    curve: CurveSignals,
    ramp_count: int,
    earliest_infinite_turn: int | None,
    win_turn_band: tuple[int, int],
) -> int:
    """Map an estimated win turn inversely onto the profile band (PROVISIONAL, 5.9-owned).

    ``estimate = mid(band) + (avgMV - pivot) - min(cap, ramp / per_turn)``, shortcut to
    ``earliest included infinite combo turn + 1`` when one exists, then linearly mapped
    ``[band hi + 2 -> 0, band lo - 2 -> 100]``. A deck with no spells cannot win at all
    -> 0 (degrade-not-raise; also keeps the empty-deck vector all-zero). Monotone under
    the AC8 SWAP directions (deck size held constant): swapping filler for a CHEAP
    (cmc <= 2) ramp spell, lowering avgMV, or an earlier included combo never lowers the
    score. (Adding an EXPENSIVE ramp spell raises avgMV and can net-lower it — the
    literal "adding X" monotonicity properties are Story 5.9's, asserted on calibrated
    curves.)
    """
    if curve.spell_count == 0:
        return 0
    band_lo, band_hi = win_turn_band
    # 5.9 guard (the 5.6 lesson: malformed input must not masquerade as signal): an
    # inverted band would flip the linear map's sign and quietly score fast decks slow.
    if band_lo > band_hi:
        raise ValueError(f"malformed win_turn_band: lo {band_lo} > hi {band_hi}")
    estimate = (
        (band_lo + band_hi) / 2.0
        + (curve.average_mana_value - _SPEED_AVG_MV_PIVOT)
        - min(_SPEED_RAMP_TURN_CAP, ramp_count / _SPEED_RAMP_PER_TURN)
    )
    if earliest_infinite_turn is not None:
        estimate = min(estimate, earliest_infinite_turn + _SPEED_COMBO_TURN_PAD)
    slowest = band_hi + _SPEED_BAND_PAD
    fastest = band_lo - _SPEED_BAND_PAD
    return _to_score(100.0 * (slowest - estimate) / (slowest - fastest))


def _consistency_score(
    opener: dict[str, float],
    land_access_turn4: float,
    tutor_count: int,
) -> int:
    """Blend opener/land-access probabilities plus an additive tutor bonus (PROVISIONAL).

    The tutor bonus is additive-only (never a ratio denominator) so adding a tutor can
    never lower the score. Monotone: swapping filler for a tutor never lowers this.
    """
    wincon_opener = max(opener[category] for category in _WIN_ROUTE_CATEGORIES)
    blended = (
        _CONSISTENCY_DRAW_WEIGHT * opener[CARD_DRAW]
        + _CONSISTENCY_RAMP_WEIGHT * opener[RAMP]
        + _CONSISTENCY_WINCON_WEIGHT * wincon_opener
        + _CONSISTENCY_LAND_WEIGHT * land_access_turn4
    )
    bonus = min(tutor_count, _TUTOR_BONUS_COUNT_CAP) * _TUTOR_CONSISTENCY_BONUS
    return _to_score(blended * 100.0 + bonus)


def _resilience_score(
    win_route_count: int, instant_speed_ratio: float, draw_count: int, formula: KarstenFormula
) -> int:
    """Blend win-route redundancy, instant-speed share, and draw density (PROVISIONAL).

    This is the documented resilience PROXY — see :func:`dimension_vector`'s docstring.
    The draw baseline is 5.5's ``STRUCTURAL_GAP_BASELINES`` value (imported, not
    restated).
    """
    draw_baseline = STRUCTURAL_GAP_BASELINES[formula][CARD_DRAW]
    draw_term = min(draw_count / draw_baseline, 1.0) if draw_baseline else 1.0
    return _to_score(
        _RESILIENCE_WIN_ROUTE_WEIGHT * (win_route_count / len(_WIN_ROUTE_CATEGORIES))
        + _RESILIENCE_INSTANT_WEIGHT * instant_speed_ratio
        + _RESILIENCE_DRAW_WEIGHT * draw_term
    )


def _interaction_score(interaction: InteractionSignals, formula: KarstenFormula) -> int:
    """Map interaction density and quality onto 0-100 (PROVISIONAL, 5.9-owned).

    Count-based sub-terms (total / instant-speed / cheap counts against per-formula
    targets) — see the deviation note on :data:`_INSTANT_INTERACTION_TARGETS`: the
    recommended ratio blend inverts under the AC8 swap direction; counts are monotone
    under any interaction swap by construction. Zero interaction -> 0.
    """
    if interaction.count == 0:
        return 0
    cheap_count = sum(
        count
        for bucket, count in interaction.cmc_distribution
        if bucket <= _CHEAP_INTERACTION_CMC_MAX
    )
    return _to_score(
        _INTERACTION_COUNT_WEIGHT * min(interaction.count / _INTERACTION_TARGETS[formula], 1.0)
        + _INTERACTION_INSTANT_WEIGHT
        * min(interaction.instant_speed_count / _INSTANT_INTERACTION_TARGETS[formula], 1.0)
        + _INTERACTION_CHEAP_WEIGHT * min(cheap_count / _CHEAP_INTERACTION_TARGETS[formula], 1.0)
    )


def _mana_efficiency_score(land_delta: float, total_pip_deficit: int) -> int:
    """Start at 100, subtract Karsten-delta and pip-deficit penalties (PROVISIONAL).

    Reuses 5.4's :data:`~src.logic.assessment.mana_base.KARSTEN_TOLERANCE_LANDS` band —
    a deck inside the tolerance with no color deficits scores 100.
    """
    penalty = _LAND_DELTA_PENALTY * max(0.0, abs(land_delta) - KARSTEN_TOLERANCE_LANDS)
    penalty += _PIP_DEFICIT_PENALTY * total_pip_deficit
    return _to_score(100.0 - penalty)


def _card_advantage_score(draw_count: int, tutor_count: int, formula: KarstenFormula) -> int:
    """Draw density against the per-formula target plus the additive tutor bonus.

    Structural cap: the count term maxes at 80 and the tutor bonus at 18, so the
    dimension tops out at 98, never 100 — kept deliberately after the 5.9 calibration
    pass (the 5.8-deferred disposition): the 2-point headroom is invisible under the
    aggregate weights and benchmark cuts, and re-normalizing the two terms to sum to
    100 would change every deck's score for zero benchmark benefit.
    """
    density = _CARD_ADVANTAGE_COUNT_WEIGHT * min(draw_count / _DRAW_TARGETS[formula], 1.0)
    bonus = min(tutor_count, _TUTOR_BONUS_COUNT_CAP) * _TUTOR_CARD_ADVANTAGE_BONUS
    return _to_score(density + bonus)


def _combo_potential_score(
    matched_combos: Sequence[ComboRecord], deck_cards: Sequence[DeckCard]
) -> int:
    """Sum per-record credit + earliness bonuses, clamp at 100 (PROVISIONAL, 5.9-owned).

    Credit by derived type (:data:`_COMBO_TYPE_CREDIT`); ``almost_included`` earns half
    its included credit (partial credit — the floor never sees it); ``bucket=None``
    records are explicitly skipped (never matched -> not evidence). Included infinite
    records add ``max(0, (10 - earliest_turn) * 2)``. By construction: included >=
    almost_included for the same record, and an earlier combo never lowers the score.
    All credits are multiples of 0.5, so summation order cannot change the result.
    """
    total = 0.0
    for record in matched_combos:
        if record.bucket is None:
            continue
        kind = combo_type(record)
        credit = _COMBO_TYPE_CREDIT[kind]
        if record.bucket == "included":
            total += credit
            if kind != NON_INFINITE:
                earliest = earliest_turn_estimate(record, deck_cards)
                total += max(
                    0.0, (_COMBO_EARLINESS_TURN_ANCHOR - earliest) * _COMBO_EARLINESS_PER_TURN
                )
        else:  # almost_included
            total += credit / 2.0
    return _to_score(total)


def dimension_vector(
    deck_cards: Sequence[DeckCard],
    *,
    matched_combos: Sequence[ComboRecord],
    profile: FormatProfile,
) -> DimensionVector:
    """Produce the FR16 7-dimension vector for a deck under a format profile (AC2).

    Works identically under both profiles — the only format fork is the
    ``profile.karsten_formula`` selector (no ``rubric`` branch) feeding the Karsten
    formula, structural baselines, and per-formula curve targets. Shared signals are
    gathered once per call (one :func:`~src.logic.assessment.classifiers.classify_deck`
    and one direct :func:`~src.logic.assessment.mana_base.compute_curve` — the 5.3
    deferred-work rule; ``karsten_land_delta`` below re-derives the curve internally, a
    cheap correctness-neutral second scan) and every dimension helper reads those locals.
    Every dimension is clamped and rounded through the one shared policy
    (:func:`_to_score`).

    **Resilience is a documented proxy.** No protection/recursion classifier category
    exists (adding one is an AD-10 vocabulary change owned by Story 5.9's tuning pass),
    so v1 resilience blends win-route redundancy (how many of the three ``WINCON_*``
    categories are non-zero), draw-engine access (rebuilding after a wipe), and the
    instant-speed interaction share (holding up answers). It does NOT measure hexproof,
    counterspell protection, or recursion loops.

    An empty deck yields a full (all-zero) vector — degrade, never raise. Sideboard rows
    are NOT filtered (standing 5.3-5.6 policy). All mapping curves are PROVISIONAL v1
    models (5.9 owns the numbers); tests verify shape, clamps, and the AC8 monotone
    directions only.

    Args:
        deck_cards: The deck's card associations (quantity-aware).
        matched_combos: The OUTPUT of :func:`~src.logic.assessment.combos.match_combos`
            — records with ``bucket`` set. A ``bucket=None`` record contributes nothing.
        profile: The format's frozen scoring constants (win-turn band + Karsten formula).

    Returns:
        The frozen :class:`DimensionVector`; identical input yields identical output.
    """
    formula = profile.karsten_formula
    counts = classify_deck(deck_cards)  # the ONE classify_deck call (5.3 deferred item)
    curve = compute_curve(deck_cards)  # the one direct compute_curve (karsten re-curves internally)
    karsten = karsten_land_delta(deck_cards, formula=formula)
    pip_signals = compute_pip_signals(deck_cards, formula=formula)
    interaction = interaction_signals(deck_cards)
    deck_size = curve.land_count + curve.spell_count

    # Opener/land-access probabilities via the primitive, fed from the locals above —
    # redundancy_signals/land_access_by_turn would re-run classify_deck/compute_curve
    # internally (the one-call rule; same math either way).
    opener = {
        category: _opener_probability(counts[category].count, deck_size)
        for category in (CARD_DRAW, RAMP, *_WIN_ROUTE_CATEGORIES)
    }
    land_access_turn4 = probability_at_least(
        deck_size=deck_size,
        copies=curve.land_count,
        drawn=cards_seen_by_turn(_CONSISTENCY_LAND_ACCESS_TURN),
        min_count=_CONSISTENCY_LAND_ACCESS_TURN,
    )

    earliest_infinite: int | None = None
    for record in matched_combos:
        if record.bucket != "included" or combo_type(record) == NON_INFINITE:
            continue
        turn = earliest_turn_estimate(record, deck_cards)
        earliest_infinite = turn if earliest_infinite is None else min(earliest_infinite, turn)

    win_route_count = sum(1 for category in _WIN_ROUTE_CATEGORIES if counts[category].count > 0)

    return DimensionVector(
        speed=_speed_score(curve, counts[RAMP].count, earliest_infinite, profile.win_turn_band),
        consistency=_consistency_score(opener, land_access_turn4, counts[TUTOR].count),
        resilience=_resilience_score(
            win_route_count, interaction.instant_speed_ratio, counts[CARD_DRAW].count, formula
        ),
        interaction=_interaction_score(interaction, formula),
        mana_efficiency=_mana_efficiency_score(
            karsten.delta, sum(signal.deficit for signal in pip_signals)
        ),
        card_advantage=_card_advantage_score(counts[CARD_DRAW].count, counts[TUTOR].count, formula),
        combo_potential=_combo_potential_score(matched_combos, deck_cards),
    )

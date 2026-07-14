"""The pure ``score()`` entry point composing the Epic-5 core (Story 5.9, AD-2).

The composition contract everyone already wrote down (``aggregate.py``): ``score()``
runs :func:`~src.logic.assessment.combos.match_combos` →
:func:`~src.logic.assessment.dimensions.dimension_vector` /
:func:`~src.logic.assessment.dimensions.bracket_floor` →
:func:`~src.logic.assessment.aggregate.aggregate_score` +
:func:`~src.logic.assessment.aggregate.tier_label`, exactly once each, and packages the
results as the frozen :class:`CoreAssessment`. Pure and deterministic (AD-2): no
network, DB, clock, randomness, or logging — identical ``(deck_cards, commanders,
variants, profile)`` input yields an equal ``CoreAssessment``.

**The rubric fork lives in what is COMPOSED, never inside any module:** under a
``heuristic_only`` profile the composer never calls ``bracket_floor()`` at all —
``bracket_floor=None`` / ``cedh_candidate=False`` — and the edge emits ``bracket:
null`` (AD-7 fixed shape). No scoring math branches on ``rubric``.

**Decide-once trigger semantics (AC3):** ``mass_land_denial`` (any tagged card present)
and ``extra_turn_chains`` (quantity-aware ``EXTRA_TURN`` count at or above
:data:`~src.logic.assessment.dimensions.EXTRA_TURN_CHAIN_MIN` — the same rule
``bracket_floor`` gates on) are computed format-agnostically for BOTH rubrics from one
:func:`~src.logic.assessment.classifiers.classify_deck` read. A Standard deck running
Armageddon factually HAS mass land denial — the flag is explainability, not a bracket
verdict; ``bracket_floor=None`` is what says "no bracket". Commander parity with
``BracketFloorSignal.mass_land_denial`` / ``.extra_turn_chain`` is pinned by test.

**Honest internal re-derivations (the 5.7 lesson):** the composed public functions
re-derive shared signals internally — ``dimension_vector`` and ``bracket_floor`` each
run their own ``classify_deck``/``compute_curve``, and ``bracket_floor`` re-derives its
own :class:`~src.logic.assessment.dimensions.GameChangerSignal` — so ``score()`` makes
no single-classification claim. The deck is scanned more than once per call: cheap and
correctness-neutral (the 5.3 rationale).

**Epic-7 consumer map:** 7.2 / feature 4.2 passes snapshot variants + resolved
commanders in and maps ``game_changers.unknown_count > 0`` →
``game_changer_data_unavailable``; 7.3 serializes ``CoreAssessment`` into
``AssessDeckPowerResult`` (``bracket_floor=None`` → ``bracket: null``,
``game_changers.card_names`` → ``flags.game_changers``); 7.5 diffs two of these — the
field names here are its delta keys. No confidence level, ``reasons[]``, summary,
``data_vintage``, or serialization here — Epic 7 edge policy (AD-6/AD-7/AD-8).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from src.data.schemas.combo import ComboRecord
from src.data.schemas.deck import DeckCard
from src.logic.assessment.aggregate import aggregate_score, tier_label
from src.logic.assessment.classifiers import EXTRA_TURN, MASS_LAND_DENIAL, classify_deck
from src.logic.assessment.combos import match_combos
from src.logic.assessment.consistency import structural_gaps
from src.logic.assessment.dimensions import (
    EXTRA_TURN_CHAIN_MIN,
    DimensionVector,
    GameChangerSignal,
    bracket_floor,
    dimension_vector,
    game_changer_signal,
)
from src.logic.assessment.profiles import FormatProfile, TierLabel


@dataclass(frozen=True, slots=True)
class CoreAssessment:
    """The fixed-shape result of one ``score()`` call (AD-7 discipline starts here).

    Every field is always present for any format — Standard holds
    ``bracket_floor=None`` plus ``False`` Bracket booleans, never a missing key. All
    collection fields are tuples that arrive pre-sorted from their producers
    (``combos`` by ``spellbook_id``, ``structural_gaps`` and
    ``game_changers.card_names`` bytewise) — nothing is re-sorted here.

    Attributes:
        vector: The FR16 7-dimension integer vector — all seven dimensions, any format.
        for_format_score: The FR19 0-100 for-format aggregate (no 1-10 scale anywhere).
        tier: The FR24 descriptive tier label — never a bare number.
        bracket_floor: The FR18 computed Bracket floor (``{2, 3, 4}``) under
            ``rubric == "brackets"``; ``None`` under ``heuristic_only`` (the composer
            never calls ``bracket_floor()`` on that path).
        cedh_candidate: The FR18 candidacy flag under ``brackets`` — candidacy only,
            never an asserted Bracket 5; ``False`` under ``heuristic_only``.
        game_changers: The AD-4 three-state Game Changer read, computed for BOTH
            rubrics: ``card_names`` feeds Epic 7's ``flags.game_changers``,
            ``unknown_count`` is the edge's ``game_changer_data_unavailable`` input —
            the core emits the VALUE, never the confidence token or level.
        combos: The matched records (buckets set, sorted by ``spellbook_id``, exactly
            as ``match_combos`` returns them).
        structural_gaps: The FR9 closed gap tokens under the profile's Karsten
            formula, bytewise-sorted.
        mass_land_denial: Whether any mass-land-denial card is present — one
            decide-once semantic for both formats (see the module docstring).
        extra_turn_chains: Whether the quantity-aware extra-turn count reaches the
            chain threshold — the same rule ``bracket_floor`` gates on, computed for
            both formats.
    """

    vector: DimensionVector
    for_format_score: int
    tier: TierLabel
    bracket_floor: int | None
    cedh_candidate: bool
    game_changers: GameChangerSignal
    combos: tuple[ComboRecord, ...]
    structural_gaps: tuple[str, ...]
    mass_land_denial: bool
    extra_turn_chains: bool


def score(
    deck_cards: Sequence[DeckCard],
    *,
    commanders: Sequence[str],
    variants: Sequence[ComboRecord],
    profile: FormatProfile,
) -> CoreAssessment:
    """Score a resolved deck under a format profile — the one pure entry point (AD-2).

    The AD-2 four-input signature: ``commanders`` is the already-resolved commander
    name list (AD-13 — the core never resolves or queries), ``variants`` are UNMATCHED
    snapshot records (``bucket=None``) — matching happens here via ``match_combos``
    (AD-9). Inputs are never mutated; identical input yields an equal
    :class:`CoreAssessment`. Empty inputs (``variants=()``, ``commanders=()``, an
    empty deck) score without raising — zero-safe like every composed primitive.
    Sideboard rows are NOT filtered (standing 5.3-5.8 policy); Epic 7 passes
    mainboard-only rows.

    Args:
        deck_cards: The deck's card associations (quantity-aware, already loaded).
        commanders: Resolved commander names, passed in as data (AD-13).
        variants: Candidate combo records from the snapshot (``bucket=None``).
        profile: The format's frozen scoring constants (AD-3).

    Returns:
        The frozen :class:`CoreAssessment` — see its field docs for the rubric fork.
    """
    matched = match_combos(deck_cards, commanders=commanders, variants=variants)
    vector = dimension_vector(deck_cards, matched_combos=matched, profile=profile)
    for_format_score = aggregate_score(vector, profile=profile)

    # The AC3 decide-once trigger booleans, format-agnostic for both rubrics (one
    # classify_deck read here; the composed functions re-derive their own — see the
    # module docstring's honesty note).
    counts = classify_deck(deck_cards)
    mass_land_denial = counts[MASS_LAND_DENIAL].count > 0
    extra_turn_chains = counts[EXTRA_TURN].count >= EXTRA_TURN_CHAIN_MIN

    # The ONLY rubric branch: what is composed, never how anything is scored.
    if profile.rubric == "brackets":
        floor_signal = bracket_floor(deck_cards, matched_combos=matched)
        floor: int | None = floor_signal.floor
        cedh_candidate = floor_signal.cedh_candidate
    else:
        floor = None
        cedh_candidate = False

    return CoreAssessment(
        vector=vector,
        for_format_score=for_format_score,
        tier=tier_label(for_format_score, profile=profile),
        bracket_floor=floor,
        cedh_candidate=cedh_candidate,
        game_changers=game_changer_signal(deck_cards),
        combos=matched,
        structural_gaps=structural_gaps(deck_cards, formula=profile.karsten_formula),
        mass_land_denial=mass_land_denial,
        extra_turn_chains=extra_turn_chains,
    )

"""The ``compare_deck_power`` edge tool (Story 7.5 — the final Epic-7 slice).

Answers "did my edit make the deck stronger, and what changed?" server-side
(FR26): two sequential runs of the existing :func:`~src.mcp_server.tools.
assess_deck_power.assess_deck_power` helper on the same session, followed by
pure subtraction / set-difference over the two returned frozen
:class:`~src.mcp_server.tools.assess_deck_power.Assessment` blocks. This
module contains **zero scoring, resolution, or serialization logic of its
own** (AD-1/AD-2): format resolution, commander resolution, combo
provisioning, ``score()``, and block assembly all happen inside the composed
assess pipeline — compare only arranges two of its outputs into deltas.

Delta direction (decide-once #2): every signed delta is **b − a**.
``deck_id_a`` is the baseline ("before"), ``deck_id_b`` the candidate
("after") — matching the PRD §3 walkthrough ``compare_deck_power(old_id,
new_id)``. Bracket "change" is the endpoint pair, never signed arithmetic
(decide-once #3: ``None − 2`` is meaningless; Standard sides are ``None``).

Deterministic per AD-8/NFR1: every diff list is computed via set difference
then ``sorted()`` (bytewise ascending — never insertion order), all deltas
are ``int``, no call-time clock anywhere ("as of" facts live only inside the
two pass-through ``data_vintage`` blocks), and pass-through blocks
(``DataVintage``, ``Confidence``, vector endpoints) are never re-sorted or
recomputed. Stateless (FR26/NFR7): nothing is written, nothing stored.
"""

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.schemas.combo import ComboBucket
from src.logic.assessment import TierLabel
from src.mcp_server.tools.assess_deck_power import (
    Assessment,
    Confidence,
    DataVintage,
    assess_deck_power,
)
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

#: AD-7 sibling: the compare result-schema version, independent of the assess
#: tool's ``SCHEMA_VERSION`` — the two contracts evolve separately.
COMPARE_SCHEMA_VERSION: Final = "1"


class VectorDelta(BaseModel):
    """Field-wise **b − a** deltas over the FR16 7-dimension vector (AC 3).

    Mirrors :class:`~src.mcp_server.tools.assess_deck_power.AssessmentVector`
    exactly — same seven fields, same declaration order (declaration order IS
    emission order, AD-8). Each field is an ``int`` in ``[-100, 100]`` by
    construction (the difference of two ``[0, 100]`` ints); positive means
    deck_b (the candidate) is higher than deck_a (the baseline).

    Attributes:
        speed: ``b.vector.speed − a.vector.speed``.
        consistency: ``b − a`` on the consistency dimension.
        resilience: ``b − a`` on the resilience dimension.
        interaction: ``b − a`` on the interaction dimension.
        mana_efficiency: ``b − a`` on the mana-efficiency dimension.
        card_advantage: ``b − a`` on the card-advantage dimension.
        combo_potential: ``b − a`` on the combo-potential dimension.
    """

    model_config = ConfigDict(frozen=True)

    speed: int
    consistency: int
    resilience: int
    interaction: int
    mana_efficiency: int
    card_advantage: int
    combo_potential: int


class ComboBucketChange(BaseModel):
    """One combo variant present on both sides whose bucket flipped (AC 3).

    A plain ``spellbook_id`` set-difference would report "no change" for the
    headline almost_included → included completion flip — this record makes
    it visible (decide-once #4). ``bucket_a`` is the baseline bucket,
    ``bucket_b`` the candidate's.

    Attributes:
        spellbook_id: The variant's Spellbook id (the combo diff identity).
        bucket_a: The variant's bucket in deck_a (the baseline).
        bucket_b: The variant's bucket in deck_b (the candidate).
    """

    model_config = ConfigDict(frozen=True)

    spellbook_id: str
    bucket_a: ComboBucket
    bucket_b: ComboBucket


class Comparison(BaseModel):
    """The fixed-shape comparison block — all keys always present (AC 3, AD-7).

    Every signed delta is **b − a** (deck_a is the baseline, decide-once #2).
    Diff lists are bytewise-sorted ascending (set difference then ``sorted()``,
    AD-8). Per-side facts (``bracket``, booleans, ``data_vintage``,
    ``confidence``) are carried verbatim from the two assessments — a delta
    consumer must see whether either side was degraded. A Standard comparison
    carries the same shape with ``bracket_a = bracket_b = None`` — never a
    missing key.

    Attributes:
        format: The shared resolved format of both assessments.
        vector_delta: Field-wise ``b − a`` over the 7-dimension vector.
        for_format_score_delta: ``b.for_format_score − a.for_format_score``.
        for_format_score_a: Deck_a's for-format score (delta endpoint).
        for_format_score_b: Deck_b's for-format score (delta endpoint).
        tier_a: Deck_a's tier label, verbatim.
        tier_b: Deck_b's tier label, verbatim.
        bracket_a: Deck_a's Commander bracket floor, verbatim (pair, not
            arithmetic — decide-once #3); ``None`` for Standard.
        bracket_b: Deck_b's Commander bracket floor, verbatim; ``None`` for
            Standard.
        game_changers_added: GC names in deck_b only, sorted ascending.
        game_changers_removed: GC names in deck_a only, sorted ascending.
        structural_gaps_added: Gap tokens in deck_b only, sorted ascending.
        structural_gaps_removed: Gap tokens in deck_a only, sorted ascending.
        combos_added: ``spellbook_id``s matched in deck_b only, sorted.
        combos_removed: ``spellbook_id``s matched in deck_a only, sorted.
        combos_bucket_changed: Variants on both sides whose bucket differs,
            sorted by ``spellbook_id``.
        mass_land_denial_a: Deck_a's mass-land-denial flag, verbatim.
        mass_land_denial_b: Deck_b's mass-land-denial flag, verbatim.
        extra_turn_chains_a: Deck_a's extra-turn-chain flag, verbatim.
        extra_turn_chains_b: Deck_b's extra-turn-chain flag, verbatim.
        cedh_candidate_a: Deck_a's cEDH candidacy, verbatim.
        cedh_candidate_b: Deck_b's cEDH candidacy, verbatim.
        data_vintage_a: Deck_a's "as of" block, verbatim (the only clock-derived
            facts anywhere in the result, AD-8).
        data_vintage_b: Deck_b's "as of" block, verbatim.
        confidence_a: Deck_a's confidence block, verbatim.
        confidence_b: Deck_b's confidence block, verbatim.
    """

    model_config = ConfigDict(frozen=True)

    format: Literal["commander", "standard"]
    vector_delta: VectorDelta
    for_format_score_delta: int
    for_format_score_a: int
    for_format_score_b: int
    tier_a: TierLabel
    tier_b: TierLabel
    bracket_a: Literal[2, 3, 4] | None
    bracket_b: Literal[2, 3, 4] | None
    game_changers_added: tuple[str, ...]
    game_changers_removed: tuple[str, ...]
    structural_gaps_added: tuple[str, ...]
    structural_gaps_removed: tuple[str, ...]
    combos_added: tuple[str, ...]
    combos_removed: tuple[str, ...]
    combos_bucket_changed: tuple[ComboBucketChange, ...]
    mass_land_denial_a: bool
    mass_land_denial_b: bool
    extra_turn_chains_a: bool
    extra_turn_chains_b: bool
    cedh_candidate_a: bool
    cedh_candidate_b: bool
    data_vintage_a: DataVintage
    data_vintage_b: DataVintage
    confidence_a: Confidence
    confidence_b: Confidence


class CompareDeckPowerResult(BaseModel):
    """Structured result of ``compare_deck_power`` — the versioned AD-7 sibling.

    Status vocabulary (decide-once #1): ``ok`` only when both sides assessed
    ``ok`` AND their resolved formats agree; the failing side is nameable from
    the status alone (``deck_a_failed`` / ``deck_b_failed`` /
    ``both_decks_failed``), with the underlying per-side assess status
    token(s) named in ``summary``. ``database_not_initialized`` is its own
    global status (both sides fail identically — it's not a side fault).
    ``format_mismatch`` fires when ``format`` was omitted and the two decks
    resolved to different formats (AC 5). An assess-side ``error`` triages as
    the side-failure status, so top-level ``error`` is reserved-but-defensive
    (an ``ok`` assess result missing its assessment block — structurally
    unreachable). None of these ever surface as ``isError=True`` at the wire.

    Attributes:
        status: The closed comparison outcome (see above).
        schema_version: Result-schema version, always present (AD-7);
            independent of the assess tool's version.
        summary: Human-facing projection of the comparison (or of the non-ok
            outcome, naming the failing deck id(s) and underlying status
            token(s)).
        deck_id_a: The baseline deck id, reflected back.
        deck_id_b: The candidate deck id, reflected back.
        comparison: The full comparison block on ``status="ok"``; ``None`` on
            every non-ok status.
    """

    status: Literal[
        "ok",
        "deck_a_failed",
        "deck_b_failed",
        "both_decks_failed",
        "format_mismatch",
        "database_not_initialized",
        "error",
    ]
    schema_version: str = COMPARE_SCHEMA_VERSION
    summary: str
    deck_id_a: str
    deck_id_b: str
    comparison: Comparison | None = None


def _build_comparison(a: Assessment, b: Assessment) -> Comparison:
    """Pure delta assembly over two Assessment blocks — subtraction only (AC 2).

    No I/O, no recomputation: field-wise ``b − a`` on the numbers, set
    difference then ``sorted()`` on the list flags (AD-8 — never insertion
    order), and verbatim pass-through of the per-side blocks. Combos are
    diffed on ``spellbook_id``; ids present on both sides with a different
    bucket become :class:`ComboBucketChange` entries (decide-once #4 — a
    plain id set-difference would hide the almost_included → included flip).

    Args:
        a: The baseline deck's assessment block.
        b: The candidate deck's assessment block.

    Returns:
        The frozen, fixed-shape comparison block.
    """
    gc_a, gc_b = set(a.flags.game_changers), set(b.flags.game_changers)
    gaps_a, gaps_b = set(a.flags.structural_gaps), set(b.flags.structural_gaps)
    # Matched combo records always carry a bucket (the matcher assigns it);
    # the is-not-None filter states that invariant rather than casting past it.
    buckets_a = {c.spellbook_id: c.bucket for c in a.flags.combos if c.bucket is not None}
    buckets_b = {c.spellbook_id: c.bucket for c in b.flags.combos if c.bucket is not None}
    return Comparison(
        format=a.format,
        vector_delta=VectorDelta(
            speed=b.vector.speed - a.vector.speed,
            consistency=b.vector.consistency - a.vector.consistency,
            resilience=b.vector.resilience - a.vector.resilience,
            interaction=b.vector.interaction - a.vector.interaction,
            mana_efficiency=b.vector.mana_efficiency - a.vector.mana_efficiency,
            card_advantage=b.vector.card_advantage - a.vector.card_advantage,
            combo_potential=b.vector.combo_potential - a.vector.combo_potential,
        ),
        for_format_score_delta=b.for_format_score - a.for_format_score,
        for_format_score_a=a.for_format_score,
        for_format_score_b=b.for_format_score,
        tier_a=a.tier,
        tier_b=b.tier,
        bracket_a=a.bracket,
        bracket_b=b.bracket,
        game_changers_added=tuple(sorted(gc_b - gc_a)),
        game_changers_removed=tuple(sorted(gc_a - gc_b)),
        structural_gaps_added=tuple(sorted(gaps_b - gaps_a)),
        structural_gaps_removed=tuple(sorted(gaps_a - gaps_b)),
        combos_added=tuple(sorted(buckets_b.keys() - buckets_a.keys())),
        combos_removed=tuple(sorted(buckets_a.keys() - buckets_b.keys())),
        combos_bucket_changed=tuple(
            ComboBucketChange(
                spellbook_id=spellbook_id,
                bucket_a=buckets_a[spellbook_id],
                bucket_b=buckets_b[spellbook_id],
            )
            for spellbook_id in sorted(buckets_a.keys() & buckets_b.keys())
            if buckets_a[spellbook_id] != buckets_b[spellbook_id]
        ),
        mass_land_denial_a=a.flags.mass_land_denial,
        mass_land_denial_b=b.flags.mass_land_denial,
        extra_turn_chains_a=a.flags.extra_turn_chains,
        extra_turn_chains_b=b.flags.extra_turn_chains,
        cedh_candidate_a=a.flags.cedh_candidate,
        cedh_candidate_b=b.flags.cedh_candidate,
        data_vintage_a=a.data_vintage,
        data_vintage_b=b.data_vintage,
        confidence_a=a.confidence,
        confidence_b=b.confidence,
    )


def _build_summary(comparison: Comparison, *, deck_id_a: str, deck_id_b: str) -> str:
    """Project the human summary from the comparison block alone (decide-once #5).

    Ids only — deck names are not on ``Assessment`` and threading them in
    would add a second derivation path. Deterministic: score movement with
    endpoints and tiers, the bracket endpoint pair (Commander only — both
    sides are ``None`` under Standard), headline diff counts, and the
    per-side confidence levels. The assess summary's multiplayer-variance
    caveat is deliberately NOT re-appended: a diff is not a strength read.

    Args:
        comparison: The assembled comparison block being projected.
        deck_id_a: The baseline deck id.
        deck_id_b: The candidate deck id.

    Returns:
        The deterministic human-facing summary.
    """
    bracket_text = (
        f"; Bracket floor {comparison.bracket_a} → {comparison.bracket_b}"
        if comparison.bracket_a is not None and comparison.bracket_b is not None
        else ""
    )
    changed = len(comparison.combos_bucket_changed)
    changed_noun = "bucket change" if changed == 1 else "bucket changes"
    return (
        f"Compared '{deck_id_a}' (baseline) → '{deck_id_b}' as {comparison.format}: "
        f"score {comparison.for_format_score_a} → {comparison.for_format_score_b} "
        f"({comparison.for_format_score_delta:+d}), "
        f"tier {comparison.tier_a} → {comparison.tier_b}"
        f"{bracket_text}"
        f"; Game Changers +{len(comparison.game_changers_added)}"
        f"/-{len(comparison.game_changers_removed)}"
        f"; combos +{len(comparison.combos_added)}/-{len(comparison.combos_removed)}, "
        f"{changed} {changed_noun}"
        f"; confidence {comparison.confidence_a.level} → {comparison.confidence_b.level}."
    )


async def compare_deck_power(
    session: AsyncSession, *, deck_id_a: str, deck_id_b: str, format: str | None = None
) -> CompareDeckPowerResult:
    """Compare two decks' power assessments server-side — pure b − a deltas (FR26).

    Runs the existing ``assess_deck_power`` helper twice on the same session
    (sequential awaits — one ``AsyncSession`` is never used concurrently) and
    subtracts the two returned blocks. Status triage (decide-once #1):
    ``database_not_initialized`` from either side is global; otherwise a
    non-ok side yields the side-naming failure status with the underlying
    assess token(s) in ``summary``; with ``format`` omitted, differing
    resolved formats yield ``format_mismatch`` — cross-format comparison
    never proceeds implicitly. An explicit ``format`` is passed verbatim to
    both calls, forcing both sides (an unsupported value fails both sides via
    the underlying ``unsupported_format``).

    Args:
        session: Async database session shared by both assessments.
        deck_id_a: The baseline ("before") deck id.
        deck_id_b: The candidate ("after") deck id; may equal ``deck_id_a``
            (a legal self-compare yielding all-zero deltas).
        format: Optional format override (``commander`` | ``standard``),
            applied to both sides; omit to let each deck resolve itself.

    Returns:
        A ``CompareDeckPowerResult`` whose ``status`` is ``ok`` (``comparison``
        populated), ``deck_a_failed``, ``deck_b_failed``, ``both_decks_failed``,
        ``format_mismatch``, ``database_not_initialized``, or ``error``.
    """
    deck_id_a = deck_id_a.strip()
    deck_id_b = deck_id_b.strip()

    result_a = await assess_deck_power(session, deck_id=deck_id_a, format=format)
    result_b = await assess_deck_power(session, deck_id=deck_id_b, format=format)

    # Global before side-fault: an un-imported DB fails both sides identically,
    # so naming a side would misattribute a global condition (AC 4).
    if "database_not_initialized" in (result_a.status, result_b.status):
        return CompareDeckPowerResult(
            status="database_not_initialized",
            deck_id_a=deck_id_a,
            deck_id_b=deck_id_b,
            summary=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    a_failed = result_a.status != "ok"
    b_failed = result_b.status != "ok"
    if a_failed and b_failed:
        return CompareDeckPowerResult(
            status="both_decks_failed",
            deck_id_a=deck_id_a,
            deck_id_b=deck_id_b,
            summary=(
                f"Both decks failed — deck A ('{deck_id_a}'): {result_a.status}; "
                f"deck B ('{deck_id_b}'): {result_b.status}."
            ),
        )
    if a_failed:
        return CompareDeckPowerResult(
            status="deck_a_failed",
            deck_id_a=deck_id_a,
            deck_id_b=deck_id_b,
            summary=f"Deck A ('{deck_id_a}') failed: {result_a.status}.",
        )
    if b_failed:
        return CompareDeckPowerResult(
            status="deck_b_failed",
            deck_id_a=deck_id_a,
            deck_id_b=deck_id_b,
            summary=f"Deck B ('{deck_id_b}') failed: {result_b.status}.",
        )

    assessment_a = result_a.assessment
    assessment_b = result_b.assessment
    if assessment_a is None or assessment_b is None:
        # Reserved-but-defensive (decide-once #1): status="ok" always carries
        # its block, so this branch is structurally unreachable through the
        # real assess helper — but a silent None here would crash the diff.
        return CompareDeckPowerResult(
            status="error",
            deck_id_a=deck_id_a,
            deck_id_b=deck_id_b,
            summary="An internal error occurred comparing the decks.",
        )

    if assessment_a.format != assessment_b.format:
        return CompareDeckPowerResult(
            status="format_mismatch",
            deck_id_a=deck_id_a,
            deck_id_b=deck_id_b,
            summary=(
                f"Deck A ('{deck_id_a}') resolved as {assessment_a.format} but deck B "
                f"('{deck_id_b}') resolved as {assessment_b.format} — cross-format "
                "comparison never proceeds implicitly. Pass "
                'format="commander" or format="standard" explicitly to force both sides.'
            ),
        )

    comparison = _build_comparison(assessment_a, assessment_b)
    summary = _build_summary(comparison, deck_id_a=deck_id_a, deck_id_b=deck_id_b)
    return CompareDeckPowerResult(
        status="ok",
        deck_id_a=deck_id_a,
        deck_id_b=deck_id_b,
        summary=summary,
        comparison=comparison,
    )

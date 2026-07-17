"""The ``assess_deck_power`` edge tool (Stories 7.1/7.2/7.3 — the full slice).

Loads a deck via ``DeckRepository.get_deck_with_cards`` (full nested ``Card``
rows — assessment needs ``type_line``/``cmc``/``oracle_text``/``legalities``/
``game_changer``, so the lightweight projections are unusable here), resolves
the scoring format to a profile, resolves commanders per AD-13, and assembles
the frozen :class:`ResolvedDeckInputs` seam. Story 7.2 adds snapshot-backed
combo provisioning (read-only, AD-5), the single ``score()`` invocation (AD-2),
and the AD-6 degradation ladder — level + reasons carried with the
:class:`CoreAssessment` on the frozen :class:`ScoredAssessment` seam. Story 7.3
completes the output contract: the ``status="ok"`` path serializes that seam
into the fixed-shape AD-7 ``assessment`` block (:class:`Assessment` — pure
field-for-field assembly, zero recomputation), deterministically per AD-8
(pre-sorted lists, integer scores, no call-time clock — "as of" facts come only
from ``data_vintage``), and projects the human ``summary`` from the assembled
block alone (including the profile-driven multiplayer-variance caveat).
Assessment is **mainboard-only** (sideboard excluded), matching the benchmark
wiring. Stateless (FR1 / NFR7): the deck is the client-supplied ``deck_id`` and
``format`` is a per-call parameter — no server-side session state.
"""

import logging
from dataclasses import dataclass
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.combo_snapshot import ComboSnapshotRepository
from src.data.repositories.deck import DeckRepository
from src.data.schemas.combo import ComboRecord, ComboSnapshotMeta
from src.data.schemas.deck import Deck, DeckCard
from src.logic.assessment import (
    CARDS_UNRESOLVED,
    COMBO_DATA_UNAVAILABLE,
    COMMANDER_PROFILE,
    COMMANDER_UNIDENTIFIED,
    GAME_CHANGER_DATA_UNAVAILABLE,
    STANDARD_PROFILE,
    ConfidenceLevel,
    CoreAssessment,
    FormatProfile,
    TierLabel,
    score,
)
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

logger = logging.getLogger(__name__)

#: AD-7: every result carries the result-schema version, independent of status.
SCHEMA_VERSION: Final = "1"

#: The first format→profile map in the codebase (decide-once). v1 keeps the
#: epic's closed ``commander | standard`` contract — see :func:`_resolve_format`
#: for the brawl-family rationale.
_FORMAT_PROFILES: Final[dict[str, FormatProfile]] = {
    "commander": COMMANDER_PROFILE,
    "standard": STANDARD_PROFILE,
}

_SUPPORTED_FORMATS_HINT: Final = (
    "Supported formats: commander, standard. "
    'Pass format="commander" or format="standard" to choose a profile explicitly.'
)

#: How the commanders tuple was resolved (AD-13); plain data on the seam so 7.2
#: can emit ``commander_unidentified`` without re-deriving anything.
CommanderResolution = Literal["flagged", "inferred", "unidentified"]

#: The fixed FR21/AD-3 multiplayer-variance caveat sentence, appended to the
#: ``summary`` iff ``profile.multiplayer_variance_caveat`` — profile-driven
#: prose, NEVER a confidence reason, never a token (AD-6). Module ``Final`` so
#: Stories 7.4/7.5 can assert against the exact sentence.
MULTIPLAYER_VARIANCE_CAVEAT: Final = (
    "Note: multiplayer Commander outcomes vary widely with politics, seat order, "
    "and table power — treat this score as a deck-strength read, not a win-rate "
    "prediction."
)


class AssessmentVector(BaseModel):
    """The FR16 7-dimension integer vector, serialized field-for-field (AD-7).

    Mirrors :class:`~src.logic.assessment.dimensions.DimensionVector` exactly —
    same seven fields, same declaration order (declaration order IS emission
    order, AD-8). All seven are always present for any format, each an ``int``
    in ``[0, 100]``.

    Attributes:
        speed: Expected-win-turn read.
        consistency: Opener/land-access probability blend plus tutor bonus.
        resilience: Protection/recursion proxy.
        interaction: Interaction density and cheap-answer coverage.
        mana_efficiency: Karsten land delta + pip deficits, penalty-mapped.
        card_advantage: Draw-engine density plus tutor bonus.
        combo_potential: Matched-combo credit + earliness.
    """

    model_config = ConfigDict(frozen=True)

    speed: int
    consistency: int
    resilience: int
    interaction: int
    mana_efficiency: int
    card_advantage: int
    combo_potential: int


class DataVintage(BaseModel):
    """ "As of" facts from stored input metadata ONLY — never a call-time clock (FR22/AD-8).

    An absent combo snapshot renders as ``null``-valued fixed keys, never a
    missing key or conditional sub-object (decide-once #2: AD-7 bans
    format-conditional keys; flat scalar keys diff cleanest). The vintage and
    the ``combo_data_unavailable`` reason are independent facts — a meta row
    with zero variants serializes verbatim even though the token fired.
    ``export_timestamp`` and ``variant_count`` are deliberately NOT emitted
    (AD-7 names exactly these two combo keys; additive later if wanted).

    Attributes:
        combo_snapshot_imported_at: The snapshot's stored ``imported_at``
            ISO-8601 string, verbatim — no datetime parsing; ``None`` when no
            meta row exists.
        combo_snapshot_export_version: The snapshot's stored bulk-file version,
            verbatim; ``None`` when no meta row exists.
        format_profile_version: The resolved profile's version string (FR4).
    """

    model_config = ConfigDict(frozen=True)

    combo_snapshot_imported_at: str | None
    combo_snapshot_export_version: str | None
    format_profile_version: str


class Confidence(BaseModel):
    """The AD-6 confidence read: categorical level + closed-enum reasons (FR21).

    Emitted exactly as the edge ladder assembled it — the reasons arrive
    bytewise-sorted from :func:`_derive_confidence` (AD-8) and are never
    re-sorted here.

    Attributes:
        level: The categorical confidence level.
        reasons: The active degradation tokens, bytewise ascending; empty when
            nothing degraded.
    """

    model_config = ConfigDict(frozen=True)

    level: ConfidenceLevel
    reasons: tuple[str, ...]


class AssessmentFlags(BaseModel):
    """The NFR2 explainability flags — exact cards, combos, and gaps (AD-7).

    ``cedh_candidate`` is homed HERE and only here: candidacy only, never an
    asserted Bracket 5 (FR18). Standard decks carry the same fixed shape with
    ``False`` booleans and empty collections — never a missing key.

    Attributes:
        game_changers: Unique confirmed Game Changer names, bytewise ascending
            (``GameChangerSignal.card_names`` verbatim; counts stay off the
            output per AD-6 — no token here needs one).
        combos: The matched :class:`~src.data.schemas.combo.ComboRecord` rows
            verbatim (AD-11), buckets populated, sorted by ``spellbook_id``.
            Derived heuristics (``type``, ``earliest_turn_estimate``) are
            deliberately NOT emitted (decide-once #3: they are PROVISIONAL
            core-internal values; freezing them into the diff surface would
            ossify 5.9-owned tuning). ``bucket`` per record already gives
            callers the included/almost_included split (FR13).
        structural_gaps: The closed FR9 gap tokens, bytewise ascending.
        mass_land_denial: Whether any mass-land-denial card is present.
        extra_turn_chains: Whether the extra-turn count reaches the chain
            threshold.
        cedh_candidate: The FR18 candidacy flag; always ``False`` for Standard.
    """

    model_config = ConfigDict(frozen=True)

    game_changers: tuple[str, ...]
    combos: tuple[ComboRecord, ...]
    structural_gaps: tuple[str, ...]
    mass_land_denial: bool
    extra_turn_chains: bool
    cedh_candidate: bool


class Assessment(BaseModel):
    """The full AD-7 assessment block — one fixed closed shape, any format (FR23).

    Every field is always present: Standard holds ``bracket=None`` plus
    ``False`` flag booleans, never a missing or conditional key. Serialization
    is AD-8-deterministic — all collections arrive pre-sorted from their
    producers (re-sorting here would mask a producer regression 7.4 wants to
    catch), every dimension score is an ``int``, and no field is
    datetime-derived. Story 7.5 diffs two of these — the field names are its
    delta keys.

    Attributes:
        format: The resolved profile key (``"commander"`` | ``"standard"``) —
            7.5 reads it for the ``format_mismatch`` check (decide-once #4).
        vector: The 7-dimension integer vector.
        for_format_score: The FR19 0-100 for-format aggregate (no 1-10 scale
            anywhere).
        tier: The FR24 descriptive label — no score without its label.
        bracket: ``CoreAssessment.bracket_floor`` renamed at the boundary (the
            scorer docstring pins the mapping); ``{2, 3, 4}`` under Commander,
            always ``None`` for Standard — never omitted. Phrased as a floor
            in the summary (decide-once #5).
        data_vintage: "As of" facts from stored input metadata (FR22/AD-8).
        confidence: The AD-6 level + reasons.
        flags: The NFR2 explainability payload.
    """

    model_config = ConfigDict(frozen=True)

    format: Literal["commander", "standard"]
    vector: AssessmentVector
    for_format_score: int
    tier: TierLabel
    bracket: Literal[2, 3, 4] | None
    data_vintage: DataVintage
    confidence: Confidence
    flags: AssessmentFlags


class AssessDeckPowerResult(BaseModel):
    """Structured result of ``assess_deck_power`` — the versioned AD-7 contract.

    Uses ``summary`` (AD-7's field name) rather than the siblings' ``message`` —
    a deliberate divergence: the human summary is a pure deterministic
    projection of the ``assessment`` block into this field (FR22).
    ``schema_version`` stays ``"1"``: the block was documented as pending from
    7.1, so completing it IS v1, not a bump (decide-once #1) — the first
    post-release shape change bumps it.

    Attributes:
        status: ``ok`` (deck scored — ``assessment`` populated),
            ``deck_not_found`` (no such deck), ``unsupported_format`` (neither
            the param nor the stored format resolves to a supported profile),
            ``database_not_initialized`` (first-run import has not happened),
            or ``error`` (database failure).
        schema_version: Result-schema version, always present (AD-7).
        summary: Human-facing projection of the assessment (or of the non-ok
            outcome).
        deck_id: The deck id reflected back to the caller.
        assessment: The full assessment block on ``status="ok"``; ``None`` on
            every non-ok status.
    """

    status: Literal[
        "ok",
        "deck_not_found",
        "unsupported_format",
        "database_not_initialized",
        "error",
    ]
    schema_version: str = SCHEMA_VERSION
    summary: str
    deck_id: str | None = None
    assessment: Assessment | None = None


@dataclass(frozen=True)
class ResolvedDeckInputs:
    """Frozen carrier of the resolved assessment inputs — the 7.2/7.3 seam.

    Carries exactly what ``score()`` needs (mainboard ``DeckCard`` rows +
    resolved commander names + profile) plus the resolution facts 7.2 turns
    into confidence tokens (``commander_resolution``, ``unresolved_count``).

    Attributes:
        deck: The loaded deck (metadata + all rows, boards included).
        mainboard: The ``sideboard=False`` rows assessment consumes.
        format: The resolved format key (``commander`` | ``standard``).
        profile: The frozen scoring profile the format selected.
        commanders: Resolved commander names (sorted for determinism), or
            ``()`` when unidentified.
        commander_resolution: How ``commanders`` was resolved (AD-13).
        unresolved_count: Mainboard rows whose nested card failed to resolve
            (structural FK join — normally 0), for 7.2's ``cards_unresolved``.
    """

    deck: Deck
    mainboard: tuple[DeckCard, ...]
    format: str
    profile: FormatProfile
    commanders: tuple[str, ...]
    commander_resolution: CommanderResolution
    unresolved_count: int


@dataclass(frozen=True)
class ScoredAssessment:
    """Frozen carrier of the scored assessment — the Story 7.3 seam (AD-2).

    Bundles the resolved inputs, the pure core result, the snapshot vintage, and
    the edge-assembled confidence so 7.3 can serialize the full assessment block
    without re-deriving anything.

    Attributes:
        inputs: The resolved-inputs seam this scoring run consumed.
        core: The frozen ``score()`` result (dimensions, tier, combos, signals).
        vintage: The combo-snapshot metadata row for 7.3's ``data_vintage``, or
            ``None`` when combos are disabled or the meta row is absent — may be
            ``None`` even when no degradation token fired (a profile choice is
            not a degradation, AD-6).
        confidence_level: The categorical AD-6 level from the reasons ladder.
        confidence_reasons: The bytewise-sorted closed-enum reason tokens (AD-8).
    """

    inputs: ResolvedDeckInputs
    core: CoreAssessment
    vintage: ComboSnapshotMeta | None
    confidence_level: ConfidenceLevel
    confidence_reasons: tuple[str, ...]


async def _provision_combos(
    session: AsyncSession, mainboard: tuple[DeckCard, ...], profile: FormatProfile
) -> tuple[tuple[ComboRecord, ...], ComboSnapshotMeta | None, bool]:
    """Provision combo variants from the local snapshot, gated on the profile (AD-2/AD-5).

    Read-only against the same session — never a live fetch, never a write. When
    ``profile.combos_enabled`` is ``False`` the gate short-circuits before any repo
    construction: a profile that disables combos is configuration, not a run-specific
    degradation, so no ``combo_data_unavailable`` token may fire from this path (AD-6).

    Unavailability is probed via ``snapshot_is_available()`` (meta row present AND ≥1
    variant row) — never inferred from an empty ``get_variants_for_names`` result: a
    healthy snapshot with zero overlapping variants is a legitimate no-combos outcome
    (G-R2 proved this on real decks), not a degradation.

    Args:
        session: The request's async session (shared with the deck load).
        mainboard: The deck's mainboard rows — their card names drive the lookup.
        profile: The resolved format profile carrying the ``combos_enabled`` gate.

    Returns:
        ``(variants, vintage, combo_data_unavailable)``: the unmatched snapshot
        records for ``score()``, the metadata row (may be ``None``), and whether
        the ``combo_data_unavailable`` token applies.

    Raises:
        pydantic.ValidationError: On a corrupt stored snapshot row — loud by design
            (Story 6.3 contract); catching it here would hide data corruption behind
            a fake degradation token.
    """
    if not profile.combos_enabled:
        return (), None, False

    combo_repo = ComboSnapshotRepository(session)
    available = await combo_repo.snapshot_is_available()
    vintage = await combo_repo.get_metadata()
    if not available:
        return (), vintage, True

    variants = await combo_repo.get_variants_for_names([dc.card.name for dc in mainboard])
    return variants, vintage, False


def _derive_confidence(
    *,
    unresolved_count: int,
    combo_data_unavailable: bool,
    gc_unknown_count: int,
    commander_unidentified: bool,
) -> tuple[ConfidenceLevel, tuple[str, ...]]:
    """Map run-specific degradation facts to the AD-6 confidence level + reasons (FR21).

    Pure and deterministic: plain facts in, level + reasons out — no I/O, no profile,
    no clock. Reasons come exclusively from the closed AD-6 enum (imported constants,
    never re-declared) and are emitted bytewise-sorted (AD-8) — the assembly order
    below IS the sorted order (``CONFIDENCE_REASON_TOKENS`` is defined pre-sorted).
    Tokens never embed counts; the counts stay separate structured facts on the seam.

    The reasons→level ladder — the first edge confidence policy in the codebase
    (decide-once, Story 7.2): **0 reasons → ``"high"``, exactly 1 → ``"medium"``,
    ≥2 → ``"low"``.** Count-based and symmetric by deliberate v1 choice: no
    calibration data justifies per-token severity weights yet. Hand-tuned and
    adjustable (NFR8); Stories 7.3/7.4 pin it in the output contract.

    Args:
        unresolved_count: Mainboard rows whose card failed to resolve (FR3).
        combo_data_unavailable: Whether the combo snapshot probe failed (AD-5/AD-6).
        gc_unknown_count: The core's quantity-aware ``game_changers.unknown_count``
            (AD-4) — never re-derived at the edge.
        commander_unidentified: Whether an unidentified commander degrades THIS run
            (Commander-format decks only — the caller applies the FR25/AD-13 scoping).

    Returns:
        The categorical :data:`ConfidenceLevel` and the bytewise-sorted reasons tuple.
    """
    reasons = tuple(
        token
        for token, active in (
            (CARDS_UNRESOLVED, unresolved_count > 0),
            (COMBO_DATA_UNAVAILABLE, combo_data_unavailable),
            (COMMANDER_UNIDENTIFIED, commander_unidentified),
            (GAME_CHANGER_DATA_UNAVAILABLE, gc_unknown_count > 0),
        )
        if active
    )
    if not reasons:
        level: ConfidenceLevel = "high"
    elif len(reasons) == 1:
        level = "medium"
    else:
        level = "low"
    return level, reasons


def _resolve_format(
    format: str | None, stored: str | None, *, has_flagged_commander: bool
) -> str | None:
    """Resolve the scoring format via the decide-once ladder (FR2).

    The ladder, deterministic and crash-free:

    1. **Explicit ``format`` param** (stripped/lowercased): in the profile map →
       use it; non-empty but unsupported → unresolved (``None``) — it never
       falls through, so the caller's explicit choice is honored or rejected,
       never silently replaced.
    2. **Stored ``Deck.format``** (stripped/lowercased — it is free text):
       ``commander`` or ``standard`` → use it.
    3. **Structural commander signal:** any flagged mainboard commander row →
       ``commander`` (an explicitly flagged deck is a Commander-family deck;
       this also gives flagged Brawl decks a sensible default).
    4. Anything else (brawl-family, ``historic``, unknown, ``None``) →
       unresolved (``None``); the tool returns ``unsupported_format``.

    Brawl-family decision (G-R2 calibration input, owned here): G-R2's throwaway
    harness provisionally mapped ``brawl``/``standardbrawl`` → the Commander
    profile and flagged the mapping itself as provisional; the same run showed
    ``mana_efficiency = 0`` on every real Brawl deck under the Commander
    Karsten/pip math — auto-mapping Brawl would bake that distortion in
    silently. v1 therefore keeps the epic's closed ``commander | standard``
    contract: brawl-family resolves to ``unsupported_format`` with the
    explicit-override hint, so forcing ``format="commander"`` is the caller's
    visible choice, never a silent guess.

    Args:
        format: The explicit per-call format param, or ``None`` when omitted.
        stored: The deck's stored free-text format, or ``None``.
        has_flagged_commander: Whether any mainboard row is flagged
            ``commander=True`` (the structural signal).

    Returns:
        The resolved profile key (``"commander"`` | ``"standard"``), or ``None``
        when no rung resolves (→ ``unsupported_format``).
    """
    explicit = format.strip().lower() if format else ""
    if explicit:
        return explicit if explicit in _FORMAT_PROFILES else None

    stored_key = stored.strip().lower() if stored else ""
    if stored_key in _FORMAT_PROFILES:
        return stored_key

    if has_flagged_commander:
        return "commander"

    return None


def _is_legendary_creature(type_line: str) -> bool:
    """Return whether the FRONT face of ``type_line`` is a legendary creature.

    DFC/split type lines join faces with ``" // "``; only face 0 qualifies — a
    back-face-only legendary creature is not castable from the command zone
    opener, so it never supports sole-legendary inference (FR25).

    Args:
        type_line: The card's full type line (may contain ``" // "``).

    Returns:
        ``True`` when the front face contains both ``legendary`` and
        ``creature`` (case-insensitive).
    """
    front_face = type_line.split(" // ")[0].lower()
    return "legendary" in front_face and "creature" in front_face


def _resolve_commanders(
    mainboard: tuple[DeckCard, ...],
    all_rows: list[DeckCard],
    resolved_format: str,
) -> tuple[tuple[str, ...], CommanderResolution]:
    """Resolve commanders per AD-13: flagged → inferred → unidentified.

    Degenerate flag states (the 6.1 review deferral, handled read-side only)
    resolve honestly: more than two flagged mainboard rows, or flags present
    only in the sideboard, yield ``unidentified`` with a warning — never a
    silently picked subset, never an inference over a degenerate state.

    Args:
        mainboard: The deck's ``sideboard=False`` rows.
        all_rows: Every deck row (used to detect sideboard-only flag states).
        resolved_format: The ladder's outcome; inference is Commander-only.

    Returns:
        The resolved commander names (sorted for deterministic output) and the
        resolution outcome for the seam.
    """
    flagged = [dc.card.name for dc in mainboard if dc.commander]
    if len(flagged) in (1, 2):
        return tuple(sorted(flagged)), "flagged"
    if len(flagged) > 2:
        logger.warning(
            "Deck has %s flagged commander rows (max 2, partners); resolving as unidentified",
            len(flagged),
        )
        return (), "unidentified"

    sideboard_flagged = sum(1 for dc in all_rows if dc.commander and dc.sideboard)
    if sideboard_flagged:
        logger.warning(
            "Deck's only commander flags are on %s sideboard row(s); sideboard rows are "
            "never commanders — resolving as unidentified",
            sideboard_flagged,
        )
        return (), "unidentified"

    if resolved_format == "commander":
        legendary_names = {
            dc.card.name for dc in mainboard if _is_legendary_creature(dc.card.type_line)
        }
        if len(legendary_names) == 1:
            return (next(iter(legendary_names)),), "inferred"

    return (), "unidentified"


def _commander_text(commanders: tuple[str, ...], resolution: CommanderResolution) -> str:
    """Render the commander-resolution facts for the ok-path summary."""
    if resolution == "unidentified":
        return "commander unidentified"
    names = " + ".join(commanders)
    label = "commander" if len(commanders) == 1 else "partner commanders"
    return f"{label} {names} ({resolution})"


def _build_assessment(scored: ScoredAssessment) -> Assessment:
    """Serialize the :class:`ScoredAssessment` seam into the AD-7 block (AC 1/2).

    A pure field-for-field mapping — zero recomputation, zero I/O (the seam was
    built so this story re-derives nothing). The only renames happen at this
    boundary, exactly as the scorer docstring pins them: ``bracket_floor`` →
    ``bracket`` and ``game_changers.card_names`` → ``flags.game_changers``.

    Args:
        scored: The frozen carrier from the single ``score()`` invocation.

    Returns:
        The frozen, deterministic-serializing assessment block.
    """
    core = scored.core
    vintage = scored.vintage
    # The seam carries ``format``/``bracket_floor`` as ``str``/``int | None``; the
    # closed field types are the boundary's job. The casts are static-only —
    # Pydantic still validates the ``Literal`` at construction, so a stray value
    # (e.g. an out-of-domain bracket) raises rather than serializing bad prose.
    return Assessment(
        format=cast('Literal["commander", "standard"]', scored.inputs.format),
        vector=AssessmentVector(
            speed=core.vector.speed,
            consistency=core.vector.consistency,
            resilience=core.vector.resilience,
            interaction=core.vector.interaction,
            mana_efficiency=core.vector.mana_efficiency,
            card_advantage=core.vector.card_advantage,
            combo_potential=core.vector.combo_potential,
        ),
        for_format_score=core.for_format_score,
        tier=core.tier,
        bracket=cast("Literal[2, 3, 4] | None", core.bracket_floor),
        data_vintage=DataVintage(
            combo_snapshot_imported_at=vintage.imported_at if vintage else None,
            combo_snapshot_export_version=vintage.export_version if vintage else None,
            format_profile_version=scored.inputs.profile.format_profile_version,
        ),
        confidence=Confidence(
            level=scored.confidence_level,
            reasons=scored.confidence_reasons,
        ),
        flags=AssessmentFlags(
            game_changers=core.game_changers.card_names,
            combos=core.combos,
            structural_gaps=core.structural_gaps,
            mass_land_denial=core.mass_land_denial,
            extra_turn_chains=core.extra_turn_chains,
            cedh_candidate=core.cedh_candidate,
        ),
    )


def _build_summary(
    assessment: Assessment,
    *,
    deck_name: str,
    commander_text: str,
    mainboard_total: int,
    unresolved_count: int,
    multiplayer_variance_caveat: bool,
) -> str:
    """Project the human ``summary`` from the assembled assessment (FR22/FR24/AD-8).

    Pure and deterministic: assembled facts plus stable deck-identity inputs
    in, prose out — no clock, no randomness, no iteration over unsorted
    sources (decide-once #6: one derivation path, nothing recomputed from raw
    cards). Combo counts are bucket-split so a shortfall-1 variant never reads
    as a live combo (AC 5); the Bracket is phrased as a *floor* (Commander
    only) so nobody reads it as an exact rating, and cEDH candidacy stays
    candidacy — never "Bracket 5" (decide-once #5). The multiplayer-variance
    caveat is appended iff the profile says so — prose, never a reason (AD-6).

    Args:
        assessment: The assembled AD-7 block being projected.
        deck_name: The deck's stored name (stable input).
        commander_text: The rendered commander-resolution facts.
        mainboard_total: Quantity-expanded mainboard card count.
        unresolved_count: Mainboard rows whose card failed to resolve.
        multiplayer_variance_caveat: The resolved profile's caveat gate.

    Returns:
        The deterministic human-facing summary.
    """
    flags = assessment.flags
    included = sum(1 for c in flags.combos if c.bucket == "included")
    almost = sum(1 for c in flags.combos if c.bucket == "almost_included")
    included_noun = "combo variant" if included == 1 else "combo variants"
    almost_noun = "combo variant" if almost == 1 else "combo variants"
    gc_count = len(flags.game_changers)
    gc_noun = "Game Changer" if gc_count == 1 else "Game Changers"

    bracket_text = f", Bracket {assessment.bracket} floor" if assessment.bracket is not None else ""
    cedh_text = ", cEDH candidate" if flags.cedh_candidate else ""
    gaps_text = (
        f"; structural gaps: {', '.join(flags.structural_gaps)}" if flags.structural_gaps else ""
    )
    reasons_text = (
        f"reasons: {', '.join(assessment.confidence.reasons)}"
        if assessment.confidence.reasons
        else "no degradations"
    )
    summary = (
        f"Resolved deck '{deck_name}' as {assessment.format} "
        f"(profile {assessment.data_vintage.format_profile_version}): "
        f"{commander_text}; "
        f"{mainboard_total} mainboard cards, {unresolved_count} unresolved. "
        f"Scored {assessment.for_format_score}/100 ({assessment.tier})"
        f"{bracket_text}{cedh_text}; "
        f"{included} {included_noun} included, {almost} {almost_noun} one card away; "
        f"{gc_count} {gc_noun}{gaps_text}; "
        f"confidence {assessment.confidence.level} ({reasons_text})."
    )
    if multiplayer_variance_caveat:
        summary = f"{summary} {MULTIPLAYER_VARIANCE_CAVEAT}"
    return summary


async def assess_deck_power(
    session: AsyncSession, *, deck_id: str, format: str | None = None
) -> AssessDeckPowerResult:
    """Assess a deck's power level: load, resolve, score, serialize (FR1/FR2/FR3/FR25).

    Loads the full-card deck, resolves the scoring format via the ladder
    (explicit param → stored ``Deck.format`` → commander-flag signal), resolves
    commanders per AD-13, provisions combo variants from the local snapshot,
    runs the single pure ``score()`` invocation, and serializes the result into
    the fixed-shape AD-7 ``assessment`` block with its deterministic human
    ``summary``. Degradations (absent snapshot, unidentified commander, unknown
    Game Changer data, unresolved cards) lower ``confidence`` and are named in
    ``reasons`` — the deck is still scored (AD-6).

    Args:
        session: Async database session to load the deck from.
        deck_id: The deck id (from ``create_deck`` / ``list_decks``).
        format: Optional format override (``commander`` | ``standard``,
            case-insensitive); omit to infer from the deck's stored format.

    Returns:
        An ``AssessDeckPowerResult`` whose ``status`` is ``ok`` (``assessment``
        populated), ``deck_not_found``, ``unsupported_format``,
        ``database_not_initialized``, or ``error``.
    """
    deck_id = deck_id.strip()
    format = format.strip().lower() if format else None

    # Param validation before any DB touch: an explicit unsupported format can
    # never resolve, whatever the deck holds.
    if format and format not in _FORMAT_PROFILES:
        return AssessDeckPowerResult(
            status="unsupported_format",
            deck_id=deck_id,
            summary=(
                f"Format '{format}' isn't supported for power assessment. {_SUPPORTED_FORMATS_HINT}"
            ),
        )

    if not await is_database_initialized(session):
        return AssessDeckPowerResult(
            status="database_not_initialized",
            deck_id=deck_id,
            summary=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    repo = DeckRepository(session)
    try:
        deck = await repo.get_deck_with_cards(deck_id)
    except DatabaseError:
        logger.exception("assess_deck_power failed for deck_id=%s", deck_id)
        return AssessDeckPowerResult(
            status="error",
            deck_id=deck_id,
            summary="A database error occurred assessing the deck.",
        )
    if deck is None:
        return AssessDeckPowerResult(
            status="deck_not_found",
            deck_id=deck_id,
            summary=f"No deck found with id '{deck_id}'.",
        )

    mainboard = tuple(dc for dc in deck.deck_cards if not dc.sideboard)
    has_flagged_commander = any(dc.commander for dc in mainboard)

    resolved_format = _resolve_format(
        format, deck.format, has_flagged_commander=has_flagged_commander
    )
    if resolved_format is None:
        stored_text = f"stored format '{deck.format}'" if deck.format else "no stored format"
        return AssessDeckPowerResult(
            status="unsupported_format",
            deck_id=deck_id,
            summary=(
                f"Deck '{deck.name}' has {stored_text}, which isn't supported for "
                f"power assessment. {_SUPPORTED_FORMATS_HINT}"
            ),
        )
    profile = _FORMAT_PROFILES[resolved_format]

    # Structural resolution count (FR3): the FK join makes a missing nested card
    # abnormal, but 7.2's cards_unresolved token needs the fact captured.
    # NOTE: this is structurally 0 today — DeckCard.card is a required (non-optional)
    # field, so an orphaned deck_cards row fails Deck.model_validate inside
    # get_deck_with_cards before it ever reaches here; dc.card is never None. Kept per
    # AC5 ("structural, FK join => normally 0"). Story 7.2 must NOT treat this as a live
    # cards_unresolved source until the shared load path tolerates a null nested card.
    unresolved_count = sum(1 for dc in mainboard if dc.card is None)

    commanders, commander_resolution = _resolve_commanders(
        mainboard, deck.deck_cards, resolved_format
    )

    inputs = ResolvedDeckInputs(
        deck=deck,
        mainboard=mainboard,
        format=resolved_format,
        profile=profile,
        commanders=commanders,
        commander_resolution=commander_resolution,
        unresolved_count=unresolved_count,
    )

    # The new combo reads sit under the same DatabaseError → error contract as the
    # deck load (7.1 AC6/NFR3): they run outside the guard above, and the snapshot
    # repo swallows only OperationalError, so a sibling DatabaseError here would
    # otherwise escape uncaught to the client. ValidationError on a corrupt stored
    # row stays loud by design (decide-once #5) — corruption surfaces, not degrades.
    try:
        variants, vintage, combo_data_unavailable = await _provision_combos(
            session, inputs.mainboard, inputs.profile
        )
    except DatabaseError:
        logger.exception("assess_deck_power combo provisioning failed for deck_id=%s", deck_id)
        return AssessDeckPowerResult(
            status="error",
            deck_id=deck_id,
            summary="A database error occurred assessing the deck.",
        )

    # The single pure-core invocation (AD-2/AD-9): matching runs INSIDE score() —
    # the edge never calls match_combos directly. Zero-safe on an empty mainboard.
    core = score(
        inputs.mainboard,
        commanders=inputs.commanders,
        variants=variants,
        profile=inputs.profile,
    )

    # commander_unidentified is scoped to Commander-format decks (FR25/AD-13): a
    # Standard deck resolves "unidentified" by construction and must not carry a
    # permanent degradation for a format that has no commanders.
    commander_unidentified = (
        inputs.commander_resolution == "unidentified" and inputs.profile.rubric == "brackets"
    )
    confidence_level, confidence_reasons = _derive_confidence(
        unresolved_count=inputs.unresolved_count,
        combo_data_unavailable=combo_data_unavailable,
        gc_unknown_count=core.game_changers.unknown_count,
        commander_unidentified=commander_unidentified,
    )

    scored = ScoredAssessment(
        inputs=inputs,
        core=core,
        vintage=vintage,
        confidence_level=confidence_level,
        confidence_reasons=confidence_reasons,
    )

    assessment = _build_assessment(scored)
    summary = _build_summary(
        assessment,
        deck_name=deck.name,
        commander_text=_commander_text(commanders, commander_resolution),
        mainboard_total=sum(dc.quantity for dc in inputs.mainboard),
        unresolved_count=inputs.unresolved_count,
        multiplayer_variance_caveat=inputs.profile.multiplayer_variance_caveat,
    )
    return AssessDeckPowerResult(
        status="ok", deck_id=deck_id, summary=summary, assessment=assessment
    )

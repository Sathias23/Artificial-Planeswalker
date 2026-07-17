"""Ingest/resolve/score slice of the ``assess_deck_power`` edge tool (Stories 7.1/7.2).

Loads a deck via ``DeckRepository.get_deck_with_cards`` (full nested ``Card``
rows — assessment needs ``type_line``/``cmc``/``oracle_text``/``legalities``/
``game_changer``, so the lightweight projections are unusable here), resolves
the scoring format to a profile, resolves commanders per AD-13, and assembles
the frozen :class:`ResolvedDeckInputs` seam. Story 7.2 adds snapshot-backed
combo provisioning (read-only, AD-5), the single ``score()`` invocation (AD-2),
and the AD-6 degradation ladder — level + reasons carried with the
:class:`CoreAssessment` on the frozen :class:`ScoredAssessment` seam for Story
7.3. Assessment is **mainboard-only** (sideboard excluded), matching the
benchmark wiring. Stateless (FR1 / NFR7): the deck is the client-supplied
``deck_id`` and ``format`` is a per-call parameter — no server-side session
state.

Result widening is still pending: the ``assessment`` block, deterministic
serialization, and the full human summary are Story 7.3. The ``status="ok"``
``summary`` is a deterministic projection of the resolution + scoring facts.
"""

import logging
from dataclasses import dataclass
from typing import Final, Literal

from pydantic import BaseModel
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


class AssessDeckPowerResult(BaseModel):
    """Structured result of ``assess_deck_power`` (Story 7.1 provisional shape).

    Uses ``summary`` (AD-7's field name) rather than the siblings' ``message`` —
    a deliberate divergence: 7.3 projects the human summary of the full
    assessment into this same field. ``assessment`` is a ``None`` placeholder
    until Story 7.3 widens it to the full assessment block.

    Attributes:
        status: ``ok`` (inputs resolved — scoring pending 7.2/7.3),
            ``deck_not_found`` (no such deck), ``unsupported_format`` (neither
            the param nor the stored format resolves to a supported profile),
            ``database_not_initialized`` (first-run import has not happened),
            or ``error`` (database failure).
        schema_version: Result-schema version, always present (AD-7).
        summary: Human-facing summary of the resolution outcome.
        deck_id: The deck id reflected back to the caller.
        assessment: Always ``None`` in this story — Story 7.3 widens it.
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
    assessment: None = None


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


async def assess_deck_power(
    session: AsyncSession, *, deck_id: str, format: str | None = None
) -> AssessDeckPowerResult:
    """Resolve a deck's assessment inputs: load, format→profile, commanders (FR1/FR2/FR3/FR25).

    Story 7.1 slice: loads the full-card deck, resolves the scoring format via
    the ladder (explicit param → stored ``Deck.format`` → commander-flag
    signal), resolves commanders per AD-13, counts unresolved rows, and
    assembles the :class:`ResolvedDeckInputs` seam. Scoring is pending Stories
    7.2/7.3 — the ``ok`` summary states the resolution facts only.

    Args:
        session: Async database session to load the deck from.
        deck_id: The deck id (from ``create_deck`` / ``list_decks``).
        format: Optional format override (``commander`` | ``standard``,
            case-insensitive); omit to infer from the deck's stored format.

    Returns:
        An ``AssessDeckPowerResult`` whose ``status`` is ``ok``,
        ``deck_not_found``, ``unsupported_format``,
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

    mainboard_total = sum(dc.quantity for dc in inputs.mainboard)
    reasons_text = (
        f"reasons: {', '.join(scored.confidence_reasons)}"
        if scored.confidence_reasons
        else "no degradations"
    )
    combos_matched = len(scored.core.combos)
    combos_noun = "combo variant" if combos_matched == 1 else "combo variants"
    summary = (
        f"Resolved deck '{deck.name}' as {resolved_format} "
        f"(profile {profile.format_profile_version}): "
        f"{_commander_text(commanders, commander_resolution)}; "
        f"{mainboard_total} mainboard cards, {unresolved_count} unresolved. "
        f"Scored {scored.core.for_format_score}/100 ({scored.core.tier}), "
        f"{combos_matched} {combos_noun} matched; "
        f"confidence {scored.confidence_level} ({reasons_text}). "
        "The structured assessment block lands in Story 7.3."
    )
    return AssessDeckPowerResult(status="ok", deck_id=deck_id, summary=summary)

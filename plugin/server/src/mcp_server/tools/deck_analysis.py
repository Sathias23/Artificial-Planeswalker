"""Structured deck-analysis logic for the Epic-1 analysis tools (Story 1.6).

Wraps the existing ``src/logic`` curve/synergy/validator over a full deck loaded
via ``DeckRepository.get_deck_with_cards`` (eager full ``Card`` rows — analysis
needs ``oracle_text``/``type_line``/``cmc``/``legalities``, so the lightweight
projections are unusable here). The three helpers back the ``analyze_mana_curve``
/ ``detect_synergies`` / ``validate_deck`` tools.

Stateless (FR3 / D5 / D-1.6d): the deck is the client-supplied ``deck_id`` on
every call, and ``format``/``games`` are per-call parameters — there is no
server-side active-deck, format-filter, or session state. Analysis is
**mainboard-only** (sideboard excluded). The tool layer holds no domain logic:
it loads the deck, shapes the inputs each logic function expects, and projects
the result into a structured ``*Result``. The legacy ``RunContext``/active-deck/
HTML-report/auto-feedback machinery is dropped (D-1.6g).
"""

import logging
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.deck import DeckRepository
from src.data.schemas.card import Card
from src.logic.deck_validator import DeckValidationReport
from src.logic.deck_validator import validate_deck as _logic_validate_deck
from src.logic.mana_curve import analyze_mana_curve as _logic_analyze_mana_curve
from src.logic.synergy import SynergyPattern
from src.logic.synergy import detect_synergies as _logic_detect_synergies
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

logger = logging.getLogger(__name__)

# Game-availability vocabulary, mirroring card_search._VALID_GAMES (D-1.6c).
_VALID_GAMES = frozenset({"paper", "arena", "mtgo"})


class ManaCurveResult(BaseModel):
    """Structured result of ``analyze_mana_curve``.

    The eight analysis fields are flattened from the logic's ``ManaCurveAnalysis``
    dataclass (D-1.6e) rather than nested. ``distribution`` and
    ``playable_cards_by_turn`` map CMC/turn to a count — note JSON serializes
    their integer keys as strings at the MCP client boundary.

    Attributes:
        status: ``ok`` (curve analyzed), ``empty`` (no mainboard cards),
            ``deck_not_found`` (no such deck), or ``error`` (database failure).
        deck_id: The deck id reflected back to the caller.
        deck_name: The deck's name when it was found, else ``None``.
        distribution: CMC -> spell count.
        total_lands: Number of land cards (mainboard, by quantity).
        total_spells: Number of non-land spells (mainboard, by quantity).
        average_cmc: Mean CMC of non-land spells.
        playable_cards_by_turn: Turn -> count of cards playable by that turn.
        land_ratio: Percentage of the deck that is lands.
        issues: Detected curve issues (flood/screw risk, gaps).
        recommendations: Suggested improvements.
        message: Human-facing summary of the analysis.
    """

    status: Literal["ok", "empty", "deck_not_found", "error", "database_not_initialized"]
    deck_id: str | None = None
    deck_name: str | None = None
    distribution: dict[int, int] = {}
    total_lands: int = 0
    total_spells: int = 0
    average_cmc: float = 0.0
    playable_cards_by_turn: dict[int, int] = {}
    land_ratio: float = 0.0
    issues: list[str] = []
    recommendations: list[str] = []
    message: str


class SynergyResult(BaseModel):
    """Structured result of ``detect_synergies``.

    Reuses the logic's ``SynergyPattern`` models directly. ``synergy_count`` is
    surfaced explicitly because the logic's ``SynergyAnalysis.total_count`` is a
    ``@property`` and would not appear in ``structuredContent`` (D-1.6e).

    Attributes:
        status: ``ok`` (synergies computed), ``empty`` (no mainboard cards),
            ``deck_not_found`` (no such deck), or ``error`` (database failure).
        deck_id: The deck id reflected back to the caller.
        deck_name: The deck's name when it was found, else ``None``.
        synergies: Detected synergy patterns (tribal / keyword / mechanic combo);
            each carries ``affected_cards`` as card names (strings).
        synergy_count: Number of detected synergy patterns.
        deck_cohesion: Overall cohesion assessment (``low``/``moderate``/``high``).
        message: Human-facing summary of the analysis.
    """

    status: Literal["ok", "empty", "deck_not_found", "error", "database_not_initialized"]
    deck_id: str | None = None
    deck_name: str | None = None
    synergies: list[SynergyPattern] = []
    synergy_count: int = 0
    deck_cohesion: Literal["low", "moderate", "high"] = "low"
    message: str


class ValidateDeckResult(BaseModel):
    """Structured result of ``validate_deck``.

    Nests the logic's ``DeckValidationReport`` directly (already Pydantic).

    Attributes:
        status: ``ok`` (validated — see ``report.is_legal`` for the verdict),
            ``deck_not_found`` (no such deck), ``invalid`` (a bad ``games`` value),
            or ``error`` (database failure).
        deck_id: The deck id reflected back to the caller.
        report: The whole-deck legality report when ``status == "ok"``, else
            ``None``.
        message: Human-facing summary of the verdict.
    """

    status: Literal["ok", "deck_not_found", "invalid", "error", "database_not_initialized"]
    deck_id: str | None = None
    report: DeckValidationReport | None = None
    message: str


async def analyze_mana_curve(session: AsyncSession, *, deck_id: str) -> ManaCurveResult:
    """Analyze a deck's mana curve (CMC distribution, lands/spells, issues, advice).

    Loads the deck by ``deck_id`` and analyzes its **mainboard only** (sideboard
    excluded), expanding cards by quantity. Returns a structured curve analysis —
    distribution, land/spell counts, average CMC, turn-by-turn playability, land
    ratio, and any detected issues with recommendations. Use ``load_deck`` for the
    deck's card list, or ``lookup_card_by_name`` for full detail on a card.

    Args:
        session: Async database session to load the deck from.
        deck_id: The deck id (from ``create_deck`` / ``list_decks``).

    Returns:
        A ``ManaCurveResult`` whose ``status`` is ``ok`` (analysis populated),
        ``empty`` (no mainboard cards), ``deck_not_found``, ``error``, or
        ``database_not_initialized`` (the card database hasn't been set up — run
        ``initialize_database``).
    """
    deck_id = deck_id.strip()
    if not await is_database_initialized(session):
        return ManaCurveResult(
            status="database_not_initialized",
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )
    repo = DeckRepository(session)
    try:
        deck = await repo.get_deck_with_cards(deck_id)
    except DatabaseError:
        logger.exception("analyze_mana_curve failed for deck_id=%s", deck_id)
        return ManaCurveResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred analyzing the deck's mana curve.",
        )
    if deck is None:
        return ManaCurveResult(
            status="deck_not_found",
            deck_id=deck_id,
            message=f"No deck found with id '{deck_id}'.",
        )

    # Mainboard expanded by quantity into list[Card] (sideboard excluded).
    all_cards: list[Card] = [
        dc.card for dc in deck.deck_cards if not dc.sideboard for _ in range(dc.quantity)
    ]
    if not all_cards:
        # analyze_mana_curve raises ValueError on []; pre-check and report empty.
        return ManaCurveResult(
            status="empty",
            deck_id=deck_id,
            deck_name=deck.name,
            message=f"Deck '{deck.name}' has no mainboard cards to analyze.",
        )

    analysis = _logic_analyze_mana_curve(all_cards)
    return ManaCurveResult(
        status="ok",
        deck_id=deck_id,
        deck_name=deck.name,
        distribution=analysis.distribution,
        total_lands=analysis.total_lands,
        total_spells=analysis.total_spells,
        average_cmc=analysis.average_cmc,
        playable_cards_by_turn=analysis.playable_cards_by_turn,
        land_ratio=analysis.land_ratio,
        issues=analysis.issues,
        recommendations=analysis.recommendations,
        message=(
            f"Curve analyzed: {analysis.total_spells} spells / {analysis.total_lands} lands, "
            f"avg CMC {analysis.average_cmc:.2f}."
        ),
    )


async def detect_synergies(session: AsyncSession, *, deck_id: str) -> SynergyResult:
    """Detect synergy patterns in a deck (tribal, keyword, and mechanic combos).

    Loads the deck by ``deck_id`` and analyzes its **mainboard only** (sideboard
    excluded), weighting by card quantity. Returns the detected synergy patterns
    (each naming its ``affected_cards``), a count, and an overall cohesion rating.
    Observational only — it never modifies the deck. Use ``load_deck`` for the
    deck's card list, or ``lookup_card_by_name`` for full detail on a card.

    Args:
        session: Async database session to load the deck from.
        deck_id: The deck id (from ``create_deck`` / ``list_decks``).

    Returns:
        A ``SynergyResult`` whose ``status`` is ``ok`` (synergies populated),
        ``empty`` (no mainboard cards), ``deck_not_found``, ``error``, or
        ``database_not_initialized`` (the card database hasn't been set up — run
        ``initialize_database``).
    """
    deck_id = deck_id.strip()
    if not await is_database_initialized(session):
        return SynergyResult(
            status="database_not_initialized",
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )
    repo = DeckRepository(session)
    try:
        deck = await repo.get_deck_with_cards(deck_id)
    except DatabaseError:
        logger.exception("detect_synergies failed for deck_id=%s", deck_id)
        return SynergyResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred detecting deck synergies.",
        )
    if deck is None:
        return SynergyResult(
            status="deck_not_found",
            deck_id=deck_id,
            message=f"No deck found with id '{deck_id}'.",
        )

    # Mainboard list[DeckCard], NOT expanded (the logic weights by quantity itself).
    mainboard = [dc for dc in deck.deck_cards if not dc.sideboard]
    if not mainboard:
        return SynergyResult(
            status="empty",
            deck_id=deck_id,
            deck_name=deck.name,
            message=f"Deck '{deck.name}' has no mainboard cards to analyze.",
        )

    analysis = _logic_detect_synergies(mainboard)
    return SynergyResult(
        status="ok",
        deck_id=deck_id,
        deck_name=deck.name,
        synergies=analysis.synergies,
        synergy_count=analysis.total_count,
        deck_cohesion=analysis.deck_cohesion,
        message=(
            f"Detected {analysis.total_count} synergy pattern(s); "
            f"deck cohesion: {analysis.deck_cohesion}."
        ),
    )


async def validate_deck(
    session: AsyncSession,
    *,
    deck_id: str,
    format: str = "standard",
    games: list[str] | None = None,
) -> ValidateDeckResult:
    """Validate a deck's construction legality for a format (size, copies, legality).

    Loads the deck by ``deck_id`` and checks the constructed rules: mainboard
    size, sideboard size, the copy limit (counted across both boards, basics
    exempt — 4 copies normally, **1 copy in singleton formats**: brawl,
    standardbrawl, commander, gladiator, competitivebrawl, duel, oathbreaker,
    paupercommander, predh — reported as
    ``singleton``), per-card legality in ``format``, and — when ``games`` is
    given — card availability on those platforms (based on the union of games
    across all printings). ``format`` is case-insensitive (lowercased here) and,
    like ``games``, a per-call parameter (no server-side state). Returns a
    structured report listing every violation; ``report.is_legal`` is the
    overall verdict.

    Args:
        session: Async database session to load the deck from.
        deck_id: The deck id (from ``create_deck`` / ``list_decks``).
        format: The MTG format to validate against (default ``"standard"``);
            case-insensitive — it is lowercased before use.
        games: Optional platforms (``paper``/``arena``/``mtgo``) the deck must be
            playable on; omit to skip the availability check.

    Returns:
        A ``ValidateDeckResult`` whose ``status`` is ``ok`` (``report`` populated),
        ``deck_not_found``, ``invalid`` (a bad ``games`` value), ``error``, or
        ``database_not_initialized`` (the card database hasn't been set up — run
        ``initialize_database``).
    """
    deck_id = deck_id.strip()
    format = format.strip().lower() or "standard"

    if games:
        for game in games:
            if game.strip() not in _VALID_GAMES:
                return ValidateDeckResult(
                    status="invalid",
                    deck_id=deck_id,
                    message=f"Invalid game '{game}'. Valid games are: paper, arena, mtgo.",
                )

    if not await is_database_initialized(session):
        return ValidateDeckResult(
            status="database_not_initialized",
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    repo = DeckRepository(session)
    try:
        deck = await repo.get_deck_with_cards(deck_id)
    except DatabaseError:
        logger.exception("validate_deck failed for deck_id=%s", deck_id)
        return ValidateDeckResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred validating the deck.",
        )
    if deck is None:
        return ValidateDeckResult(
            status="deck_not_found",
            deck_id=deck_id,
            message=f"No deck found with id '{deck_id}'.",
        )

    report = _logic_validate_deck(deck, format=format, games=games)
    if report.is_legal:
        message = f"Deck is legal in {format} ({report.mainboard_count}-card mainboard)."
    else:
        count = len(report.violations)
        noun = "issue" if count == 1 else "issues"
        message = f"Deck has {count} {noun} for {format} legality."

    return ValidateDeckResult(status="ok", deck_id=deck_id, report=report, message=message)

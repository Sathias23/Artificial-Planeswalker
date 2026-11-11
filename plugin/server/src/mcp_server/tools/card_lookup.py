"""Structured card-lookup logic for the ``lookup_card_by_name`` MCP tool.

Resolves the name through the shared resolver (``CardRepository.resolve_name``) and words the
disambiguation buckets (0 / 1 / 2-5 / 6-10 / more than 10) ported from the original PydanticAI
agent's card-lookup tool, while dropping all presentation concerns (HTML formatting, Chainlit UI
elements, RunContext, and session-state filtering). Returns a structured Pydantic result so
FastMCP can serialize machine-readable fields plus a human-facing message.
"""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.card import CardRepository
from src.data.schemas.card import Card
from src.mcp_server.tools.messages import (
    DATABASE_NOT_INITIALIZED_MESSAGE,
    ambiguous_lookup_message,
)


class CardLookupResult(BaseModel):
    """Structured result of a card lookup.

    Attributes:
        status: ``found`` (``card`` populated), ``not_found`` (no match),
            ``ambiguous`` (multiple candidates in ``matches``, in name order, at most 10; the
            message says "more than 10" when more matched), ``database_not_initialized`` (no
            card data yet — run ``initialize_database``), or ``error`` (the card database could not
            be read — corrupt, unreadable or locked; ``message`` names the cause. Answered by the
            tool edge in ``tools/failures.py``).
        card: The matched card when ``status == "found"``, else ``None``.
        matches: Candidate cards when ``status == "ambiguous"``, else empty.
        message: Human-facing summary suitable for surfacing to the user.
    """

    status: Literal["found", "not_found", "ambiguous", "database_not_initialized", "error"]
    card: Card | None = None
    matches: list[Card] = []
    message: str


async def lookup_card(
    session: AsyncSession,
    card_name: str,
    format: str | None = None,
    games: list[str] | None = None,
) -> CardLookupResult:
    """Look up a card by exact-or-fuzzy name and return a structured result.

    Tries an exact (case-insensitive) match on the name or printed name first, then falls back to
    a literal substring match, bucketing the outcome: no match, single match, a small set to
    disambiguate (2-5), or a large set that warrants refining (6 or more; past 10 the message says
    "more than 10" and ``matches`` holds the first 10 by name).

    Args:
        session: Async database session to query against.
        card_name: Exact or partial card name to search for.
        format: Optional MTG format to restrict results to legal cards
            (e.g. ``"standard"``); ``None`` applies no format filter.
        games: Optional list of game platforms (e.g. ``["arena"]``) to filter by;
            ``None`` applies no games filter.

    Returns:
        A ``CardLookupResult``. No-match returns a graceful ``not_found`` result
        with a friendly message rather than raising.
    """
    if not card_name or not card_name.strip():
        return CardLookupResult(
            status="not_found",
            message="Card name must not be empty. Please provide a name to look up.",
        )

    if not await is_database_initialized(session):
        return CardLookupResult(
            status="database_not_initialized", message=DATABASE_NOT_INITIALIZED_MESSAGE
        )

    card_name = card_name.strip()
    resolution = await CardRepository(session).resolve_name(
        card_name, format_filter=format, games=games
    )
    if resolution.card is not None:
        found = resolution.card
        return CardLookupResult(status="found", card=found, message=f"Found '{found.name}'.")
    if not resolution.matches:
        return CardLookupResult(
            status="not_found",
            message=(
                f"No card found matching '{card_name}'. "
                "Check the spelling or try a different search term."
            ),
        )
    return CardLookupResult(
        status="ambiguous",
        matches=resolution.matches,
        message=ambiguous_lookup_message(card_name, resolution, card_id_hint=False),
    )

"""Structured card-lookup logic for the ``lookup_card_by_name`` MCP tool.

Ports the legacy exact-then-partial matching and disambiguation buckets
(0 / 1 / 2-5 / 6+) from the original PydanticAI agent's card-lookup tool while dropping all
presentation concerns (HTML formatting, Chainlit UI elements, RunContext, and
session-state filtering). Returns a structured Pydantic result so FastMCP can
serialize machine-readable fields plus a human-facing message.
"""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.card import CardRepository
from src.data.schemas.card import Card
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

# Maximum number of candidate cards returned for an ambiguous query.
_MAX_MATCHES = 10
# Above this many partial matches, ask the user to refine rather than choose.
_REFINE_THRESHOLD = 5


class CardLookupResult(BaseModel):
    """Structured result of a card lookup.

    Attributes:
        status: ``found`` (``card`` populated), ``not_found`` (no match), or
            ``ambiguous`` (multiple candidates in ``matches``).
        card: The matched card when ``status == "found"``, else ``None``.
        matches: Candidate cards when ``status == "ambiguous"``, else empty.
        message: Human-facing summary suitable for surfacing to the user.
    """

    status: Literal["found", "not_found", "ambiguous", "database_not_initialized"]
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

    Tries an exact (case-insensitive) match first, then falls back to a partial
    substring match, bucketing the outcome: no match, single match, a small set
    to disambiguate (2-5), or a large set that warrants refining (6+).

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

    repo = CardRepository(session)

    exact = await repo.find_by_name_exact(card_name, format_filter=format, games=games)
    if exact is not None:
        return CardLookupResult(status="found", card=exact, message=f"Found '{exact.name}'.")

    matches = await repo.find_by_name_partial(card_name, format_filter=format, games=games)

    if not matches:
        return CardLookupResult(
            status="not_found",
            message=(
                f"No card found matching '{card_name}'. "
                "Check the spelling or try a different search term."
            ),
        )

    if len(matches) == 1:
        only = matches[0]
        return CardLookupResult(status="found", card=only, message=f"Found '{only.name}'.")

    shown = matches[:_MAX_MATCHES]
    if len(matches) > _REFINE_THRESHOLD:
        if len(shown) < len(matches):
            message = (
                f"Found {len(matches)} cards matching '{card_name}'. "
                f"Please refine your search; showing the first {len(shown)}."
            )
        else:
            message = (
                f"Found {len(matches)} cards matching '{card_name}'. Please refine your search."
            )
    else:
        message = f"Found {len(matches)} cards matching '{card_name}'. Which one did you mean?"
    return CardLookupResult(status="ambiguous", matches=shown, message=message)

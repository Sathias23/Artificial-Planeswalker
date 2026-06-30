"""Structured card-search logic for the ``search_cards`` MCP tool.

Wraps the existing ``CardRepository.search_advanced`` 1:1 (D-1.4a): the tool holds
no SQL — it validates inputs gracefully, awaits the async repository, and projects
each result to a lightweight ``CardSummary`` (D-1.4e) so a single page stays small
for the LLM client. Stateless (D-1.4d): ``format``/``games``/``page`` are per-call
parameters; no search context is retained between calls. Ports the filter set and
the four ``color_mode`` semantics from the original PydanticAI agent's card-search tool while
dropping all presentation/session concerns (HTML, RunContext, session cursors,
the ``max_results`` alias).
"""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.card import CardRepository
from src.data.schemas.card import CardSummary
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

# Validation vocabularies (AC4). Colors are the WUBRG codes as stored on cards;
# rarity/games are matched case-insensitively against these canonical values.
_VALID_COLORS = frozenset({"W", "U", "B", "R", "G"})
_VALID_RARITIES = frozenset({"common", "uncommon", "rare", "mythic", "special", "bonus"})
_VALID_GAMES = frozenset({"paper", "arena", "mtgo"})


class CardSearchResult(BaseModel):
    """Structured result of an advanced card search.

    Attributes:
        status: ``ok`` (``cards`` populated), ``empty`` (a valid query with no
            matches), or ``invalid`` (a filter value failed validation).
        cards: The matching cards on this page as lightweight ``CardSummary``
            rows (empty unless ``status == "ok"``).
        total_count: Total number of matches across all pages.
        page: The 1-based page number reflected back to the caller.
        page_size: The effective page size (``search_advanced`` caps it at 50).
        total_pages: Total number of pages for the query.
        message: Human-facing summary — reports the bound and how to page, an
            adjust-your-filters hint when empty, or the bad value when invalid.
    """

    status: Literal["ok", "empty", "invalid", "database_not_initialized"]
    cards: list[CardSummary] = []
    total_count: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    message: str


def _validation_error(
    *,
    colors: list[str] | None,
    rarity: str | list[str] | None,
    games: list[str] | None,
    mana_value_min: float | None,
    mana_value_max: float | None,
    page: int,
    page_size: int,
) -> str | None:
    """Return a specific error message for the first invalid filter value, else ``None``.

    Validates the free-form filters that the MCP boundary cannot type-check
    (``color_mode`` is a ``Literal`` validated by FastMCP). Keeps the failure
    graceful and unit-testable: callers surface the message as ``status="invalid"``.
    """
    if colors:
        for color in colors:
            if color not in _VALID_COLORS:
                return f"Invalid color '{color}'. Valid colors are W, U, B, R, G."

    if rarity is not None:
        rarity_list = [rarity] if isinstance(rarity, str) else rarity
        for value in rarity_list:
            if value.lower() not in _VALID_RARITIES:
                return (
                    f"Invalid rarity '{value}'. Valid rarities are: "
                    "common, uncommon, rare, mythic, special, bonus."
                )

    if games:
        for game in games:
            if game not in _VALID_GAMES:
                return f"Invalid game '{game}'. Valid games are: paper, arena, mtgo."

    if mana_value_min is not None and mana_value_min < 0:
        return f"mana_value_min must be >= 0 (got {mana_value_min})."
    if mana_value_max is not None and mana_value_max < 0:
        return f"mana_value_max must be >= 0 (got {mana_value_max})."
    if (
        mana_value_min is not None
        and mana_value_max is not None
        and mana_value_min > mana_value_max
    ):
        return (
            f"mana_value_min ({mana_value_min}) must not exceed mana_value_max ({mana_value_max})."
        )

    if page < 1:
        return f"page must be >= 1 (got {page})."
    if page_size < 1:
        return f"page_size must be >= 1 (got {page_size})."

    return None


async def search_cards(
    session: AsyncSession,
    *,
    colors: list[str] | None = None,
    color_mode: Literal["any", "all", "exact", "at_most"] = "any",
    types: list[str] | None = None,
    keywords: list[str] | None = None,
    oracle_text: list[str] | None = None,
    mana_value_min: float | None = None,
    mana_value_max: float | None = None,
    rarity: str | list[str] | None = None,
    format: str | None = None,
    games: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> CardSearchResult:
    """Search cards by relational filters and return a structured, paginated result.

    Validates inputs first (returning ``status="invalid"`` rather than raising),
    then delegates to ``CardRepository.search_advanced`` and projects each match
    to a lightweight ``CardSummary``. Stateless: every call is self-contained.

    Args:
        session: Async database session to query against.
        colors: Color codes (W/U/B/R/G) interpreted per ``color_mode``.
        color_mode: How ``colors`` is matched — ``any`` (has any), ``all`` (has
            all), ``exact`` (exactly these), ``at_most`` (subset of these).
        types: Type substrings to match in ``type_line`` (AND logic).
        keywords: Keywords to match in oracle text / keyword array (AND logic).
        oracle_text: Oracle-text phrases that must all appear (AND logic).
        mana_value_min: Inclusive minimum mana value (CMC).
        mana_value_max: Inclusive maximum mana value (CMC).
        rarity: A rarity, or list of rarities (OR logic), case-insensitive.
        format: Optional MTG format to restrict to legal cards (e.g. ``"standard"``).
        games: Optional platforms to filter by (``paper``/``arena``/``mtgo``).
        page: 1-based page number.
        page_size: Items per page (default 20, capped at 50 by the repository).

    Returns:
        A ``CardSearchResult`` with ``status`` of ``ok`` / ``empty`` / ``invalid`` /
        ``database_not_initialized`` (the card database hasn't been set up — run
        ``initialize_database``).
    """
    # Normalize degenerate inputs: empty rarity list would produce or_() with no args in the repo
    # (SQLAlchemy renders it as a false clause, silently filtering every row). Empty/whitespace
    # format bypasses the None guard in _apply_format_filter and fires a malformed JSON path.
    if isinstance(rarity, list) and not rarity:
        rarity = None
    if format is not None and not format.strip():
        format = None

    error = _validation_error(
        colors=colors,
        rarity=rarity,
        games=games,
        mana_value_min=mana_value_min,
        mana_value_max=mana_value_max,
        page=page,
        page_size=page_size,
    )
    if error is not None:
        return CardSearchResult(status="invalid", page=page, page_size=page_size, message=error)

    if not await is_database_initialized(session):
        return CardSearchResult(
            status="database_not_initialized",
            page=page,
            page_size=page_size,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    repo = CardRepository(session)
    result = await repo.search_advanced(
        colors=colors,
        types=types,
        keywords=keywords,
        oracle_text_phrases=oracle_text,
        mana_value_min=mana_value_min,
        mana_value_max=mana_value_max,
        rarity=rarity,
        page=page,
        page_size=page_size,
        format_filter=format,
        games=games,
        color_mode=color_mode,
    )

    if not result.items:
        return CardSearchResult(
            status="empty",
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
            total_pages=result.total_pages,
            message=(
                "No cards matched the given filters. Try relaxing or adjusting them "
                "(e.g. widen the mana range, drop a color, or remove the format filter)."
            ),
        )

    cards = [CardSummary.model_validate(card) for card in result.items]
    start = (result.page - 1) * result.page_size + 1
    end = start + len(cards) - 1
    message = (
        f"Showing cards {start}-{end} of {result.total_count} "
        f"(page {result.page}/{result.total_pages})."
    )
    if result.page < result.total_pages:
        message += f" Call again with page={result.page + 1} for more."

    return CardSearchResult(
        status="ok",
        cards=cards,
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        message=message,
    )

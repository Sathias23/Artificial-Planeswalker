"""FastMCP server builder for Artificial-Planeswalker (Story 1.3).

Constructs the ``FastMCP`` server and registers the Epic-1 tools. Tools are
``async def`` and ``await`` the async ``src/data`` repositories directly on the
FastMCP event loop (D-1.3a). Each tool closes over a ``session_factory`` so the
server is test-injectable; the default factory reuses the data-layer engine.

Registration is transport-agnostic: the transport string is selected only at the
entry point (``src/mcp_server/__main__.py``), never here (AC2 / D7).
"""

from typing import Literal

from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.database import create_engine, create_session_factory
from src.mcp_server.tools.bug_report import BugReportResult, file_bug_report
from src.mcp_server.tools.card_lookup import CardLookupResult, lookup_card
from src.mcp_server.tools.card_search import CardSearchResult
from src.mcp_server.tools.card_search import search_cards as _search_cards_helper


def build_server(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastMCP:
    """Build the FastMCP server with the card-lookup and bug-report tools.

    Args:
        session_factory: Async session factory the tools use for DB access. If
            ``None``, a default factory is built from the data-layer engine
            (reusing ``create_engine`` / ``create_session_factory``).

    Returns:
        A configured ``FastMCP`` instance with both tools registered.
    """
    if session_factory is None:
        session_factory = create_session_factory(create_engine())

    mcp = FastMCP("artificial-planeswalker")

    @mcp.tool()
    async def lookup_card_by_name(
        card_name: str,
        format: str | None = None,
        games: list[str] | None = None,
    ) -> CardLookupResult:
        """Look up a Magic: The Gathering card by exact or fuzzy name.

        Tries an exact (case-insensitive) name match first, then falls back to a
        partial substring match. Returns structured data the caller can act on.

        Args:
            card_name: Exact or partial card name (e.g. "Lightning Bolt" or "bolt").
            format: Optional MTG format (e.g. "standard") to restrict to legal cards.
            games: Optional platforms to filter by (e.g. ["arena", "paper"]).

        Returns:
            A result whose ``status`` is ``found`` (single ``card``),
            ``ambiguous`` (multiple ``matches`` to choose from), or ``not_found``.
        """
        async with session_factory() as session:
            return await lookup_card(session, card_name, format=format, games=games)

    @mcp.tool()
    async def report_bug(
        description: str = "User reported an issue (no details provided).",
    ) -> BugReportResult:
        """File a bug report about unexpected behavior.

        Persists the report and returns a confirmation including its id. Only
        invoke this when the user explicitly asks to report a bug.

        Args:
            description: The user's description of the bug or issue.

        Returns:
            A result with the new report ``id`` and a confirmation ``message``.
        """
        async with session_factory() as session:
            return await file_bug_report(session, description)

    @mcp.tool()
    async def search_cards(
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
        """Search Magic: The Gathering cards by relational filters.

        All supplied filters combine with AND logic. Results are bounded to one
        page of lightweight summaries — use ``lookup_card_by_name`` for full
        detail on a chosen card. The tool is stateless: pass ``format``/``games``
        and ``page`` on every call (nothing is remembered between calls).

        Args:
            colors: Color codes (W/U/B/R/G), interpreted by ``color_mode``.
            color_mode: How ``colors`` is matched — ``any`` (has any of them),
                ``all`` (has all of them), ``exact`` (exactly these and no others),
                ``at_most`` (only these colors or fewer, i.e. a subset).
            types: Type substrings to match in the type line (e.g. ["Creature"]).
            keywords: Keyword abilities to match (e.g. ["flying"]).
            oracle_text: Oracle-text phrases that must all appear.
            mana_value_min: Inclusive minimum mana value (CMC).
            mana_value_max: Inclusive maximum mana value (CMC).
            rarity: A rarity or list of rarities (common/uncommon/rare/mythic/...).
            format: Restrict to cards legal in this format (e.g. "standard").
            games: Restrict to platforms (any of "paper", "arena", "mtgo").
            page: 1-based page number (default 1).
            page_size: Results per page (default 20, max 50).

        Returns:
            A result whose ``status`` is ``ok`` (``cards`` plus pagination
            metadata), ``empty`` (no matches — a graceful hint), or ``invalid``
            (a filter value failed validation, with a message naming it).
        """
        async with session_factory() as session:
            return await _search_cards_helper(
                session,
                colors=colors,
                color_mode=color_mode,
                types=types,
                keywords=keywords,
                oracle_text=oracle_text,
                mana_value_min=mana_value_min,
                mana_value_max=mana_value_max,
                rarity=rarity,
                format=format,
                games=games,
                page=page,
                page_size=page_size,
            )

    return mcp

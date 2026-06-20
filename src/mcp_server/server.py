"""FastMCP server builder for Artificial-Planeswalker (Story 1.3).

Constructs the ``FastMCP`` server and registers the Epic-1 tools. Tools are
``async def`` and ``await`` the async ``src/data`` repositories directly on the
FastMCP event loop (D-1.3a). Each tool closes over a ``session_factory`` so the
server is test-injectable; the default factory reuses the data-layer engine.

Registration is transport-agnostic: the transport string is selected only at the
entry point (``src/mcp_server/__main__.py``), never here (AC2 / D7).
"""

from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.database import create_engine, create_session_factory
from src.mcp_server.tools.bug_report import BugReportResult, file_bug_report
from src.mcp_server.tools.card_lookup import CardLookupResult, lookup_card


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

    return mcp

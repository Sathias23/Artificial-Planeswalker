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
from src.mcp_server.tools.deck_management import (
    DeckCardResult,
    DeckDeleteResult,
    DeckListResult,
    DeckResult,
)
from src.mcp_server.tools.deck_management import add_card_to_deck as _add_card_to_deck_helper
from src.mcp_server.tools.deck_management import create_deck as _create_deck_helper
from src.mcp_server.tools.deck_management import delete_deck as _delete_deck_helper
from src.mcp_server.tools.deck_management import list_decks as _list_decks_helper
from src.mcp_server.tools.deck_management import load_deck as _load_deck_helper
from src.mcp_server.tools.deck_management import (
    remove_card_from_deck as _remove_card_from_deck_helper,
)


def build_server(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastMCP:
    """Build the FastMCP server with the Epic-1 card, deck, and bug-report tools.

    Args:
        session_factory: Async session factory the tools use for DB access. If
            ``None``, a default factory is built from the data-layer engine
            (reusing ``create_engine`` / ``create_session_factory``).

    Returns:
        A configured ``FastMCP`` instance with all Epic-1 tools registered.
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

    @mcp.tool()
    async def list_decks(format: str | None = None) -> DeckListResult:
        """List saved decks, optionally filtered by format.

        Returns lightweight deck summaries (metadata plus mainboard/sideboard/
        distinct-card counts) — no card lists. Use ``load_deck`` for a deck's full
        contents. Stateless: pass ``format`` on every call.

        Args:
            format: Optional MTG format to filter by (e.g. "standard").

        Returns:
            A result whose ``status`` is ``ok`` (``decks`` populated) or ``empty``.
        """
        async with session_factory() as session:
            return await _list_decks_helper(session, format=format)

    @mcp.tool()
    async def create_deck(
        name: str,
        format: str = "standard",
        strategy: str | None = None,
        tags: list[str] | None = None,
    ) -> DeckResult:
        """Create a new deck and return its details (including its new ``id``).

        Track the returned ``id`` to act on the deck later (add cards, load,
        delete) — the server keeps no "active deck" state. Deck names need not be
        unique. This does not add any cards.

        Args:
            name: Deck name (must be non-blank).
            format: Deck format (default "standard").
            strategy: Optional free-text strategy description.
            tags: Optional list of tags / win conditions.

        Returns:
            A result whose ``status`` is ``ok`` (``deck`` populated) or ``invalid``.
        """
        async with session_factory() as session:
            return await _create_deck_helper(
                session, name=name, format=format, strategy=strategy, tags=tags
            )

    @mcp.tool()
    async def load_deck(deck_id: str) -> DeckResult:
        """Load a deck and its cards by id.

        Cards are returned as lightweight summaries (quantity, sideboard flag, and
        a card summary) — use ``lookup_card_by_name`` for full card detail. Get the
        ``deck_id`` from ``create_deck`` or ``list_decks``.

        Args:
            deck_id: The deck id to load.

        Returns:
            A result whose ``status`` is ``ok`` (``deck`` populated) or ``not_found``.
        """
        async with session_factory() as session:
            return await _load_deck_helper(session, deck_id=deck_id)

    @mcp.tool()
    async def delete_deck(deck_id: str) -> DeckDeleteResult:
        """Delete a deck by id.

        This is destructive and irreversible — confirm with the user before
        calling. Get the ``deck_id`` from ``create_deck`` or ``list_decks``.

        Args:
            deck_id: The deck id to delete.

        Returns:
            A result whose ``status`` is ``ok`` (deleted) or ``not_found``.
        """
        async with session_factory() as session:
            return await _delete_deck_helper(session, deck_id=deck_id)

    @mcp.tool()
    async def add_card_to_deck(
        deck_id: str,
        card_id: str | None = None,
        name: str | None = None,
        quantity: int = 1,
        sideboard: bool = False,
    ) -> DeckCardResult:
        """Add a card to a deck, identified by ``card_id`` OR ``name`` (exactly one).

        Pure persistence — no legality, 4-copy-limit, or deck-size checking (use
        ``validate_deck`` for that). Adding a card already in that exact location
        returns ``status="exists"`` (quantities are not merged). A ``name`` that
        matches multiple cards returns ``status="ambiguous"`` with candidate
        ``matches`` — re-call with a specific ``card_id``. Stateless: pass
        ``deck_id`` every call.

        Args:
            deck_id: The target deck id.
            card_id: The card id to add (provide this OR ``name``, not both).
            name: A card name to resolve and add (provide this OR ``card_id``).
            quantity: Number of copies to add (must be >= 1; default 1).
            sideboard: Add to the sideboard instead of the mainboard (default False).

        Returns:
            A result whose ``status`` reports the outcome (``ok``/``exists``/
            ``deck_not_found``/``card_not_found``/``ambiguous``/``invalid``).
        """
        async with session_factory() as session:
            return await _add_card_to_deck_helper(
                session,
                deck_id=deck_id,
                card_id=card_id,
                name=name,
                quantity=quantity,
                sideboard=sideboard,
            )

    @mcp.tool()
    async def remove_card_from_deck(
        deck_id: str,
        card_id: str | None = None,
        name: str | None = None,
        sideboard: bool = False,
    ) -> DeckCardResult:
        """Remove a card from a deck, identified by ``card_id`` OR ``name`` (exactly one).

        A ``name`` matching multiple cards returns ``status="ambiguous"``;
        removing a card not present in that location returns
        ``status="not_in_deck"``. Stateless: pass ``deck_id`` every call.

        Args:
            deck_id: The target deck id.
            card_id: The card id to remove (provide this OR ``name``, not both).
            name: A card name to resolve and remove (provide this OR ``card_id``).
            sideboard: Remove from the sideboard instead of the mainboard (default False).

        Returns:
            A result whose ``status`` reports the outcome (``ok``/``not_in_deck``/
            ``deck_not_found``/``card_not_found``/``ambiguous``/``invalid``).
        """
        async with session_factory() as session:
            return await _remove_card_from_deck_helper(
                session,
                deck_id=deck_id,
                card_id=card_id,
                name=name,
                sideboard=sideboard,
            )

    return mcp

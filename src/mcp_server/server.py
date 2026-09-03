"""FastMCP server builder for Artificial-Planeswalker (Story 1.3; sync RAG tools added 2.4/2.5).

Constructs the ``FastMCP`` server and registers the tool surface. The Epic-1 tools are
``async def`` and ``await`` the async ``src/data`` repositories directly on the
FastMCP event loop (D-1.3a), closing over a ``session_factory`` so the server is
test-injectable; the default factory reuses the data-layer engine.

The Epic-2 search tools are fundamentally different: they are **sync** ``def`` tools (FastMCP runs
them in its anyio worker threadpool) because the vector index is reachable only on the sync
``sqlite-vec`` ``ConnectionFactory`` connection — the async aiosqlite engine never loads the
extension. ``semantic_search_cards`` (Story 2.4) embeds a natural-language query, so it also closes
over an optional ``embedder`` (a test seam; the production embedder is resolved lazily inside the
tool via :func:`get_embedder`, never at build time). ``find_similar_cards`` (Story 2.5) is seeded by
a card's **stored** vector and **never embeds**, so it uses only the ``connection_factory`` seam —
no embedder. Both close over the injected ``connection_factory`` (per-thread sqlite-vec connection,
NFR6).

Two first-run tools sit alongside these: ``initialize_database`` (async — the one-time in-client
Scryfall card import that build-on-first-run depends on, since a packaged install ships no data) and
``build_search_index`` (sync — builds the ``card_vec`` index). Every card/deck tool guards an
un-imported database with a graceful ``database_not_initialized`` status that points at
``initialize_database`` rather than leaking a raw "no such table" error.

The read-only ``view_deck`` tool renders a saved deck to a self-contained HTML page and
best-effort opens it in the host's default browser (a local-bundle side effect; the file
path is always returned, so a headless host degrades gracefully). **It is deprecated
(AD-15)**: the companion app superseded it, ``src/viewer`` is frozen, and its removal is
deferred to the next minor release once the companion is proven. It still registers and
behaves exactly as before — nothing new is built on it.

``companion_set_active_deck`` is the first tool that talks to something other than the local data
files: it validates the deck against the database here and then calls the companion backend's
``PUT /api/active-deck`` through the leaf client (``src/companion/client.py``). The leaf is
importable from this package by design (AD-3) — it reaches only ``httpx`` and ``pydantic``, so a
stdio session never transitively loads a web framework. Like every other tool it never raises: a
companion that is closed, restarting or wedged is a ``status``, not an exception (FR-12).

Registration is transport-agnostic: the transport string is selected only at the
entry point (``src/mcp_server/__main__.py``), never here (AC2 / D7).
"""

import logging
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.companion.client import notify_deck_changed as _notify_deck_changed
from src.companion.contracts import (
    GroupsPayload,
    SuggestionsPayload,
    SwapsPayload,
    TierListPayload,
)
from src.data.database import create_engine, create_session_factory
from src.mcp_server.tools.assess_deck_power import AssessDeckPowerResult
from src.mcp_server.tools.assess_deck_power import (
    assess_deck_power as _assess_deck_power_helper,
)
from src.mcp_server.tools.build_search_index import BuildSearchIndexResult
from src.mcp_server.tools.build_search_index import build_search_index as _build_search_index_helper
from src.mcp_server.tools.card_lookup import CardLookupResult, lookup_card
from src.mcp_server.tools.card_search import CardSearchResult
from src.mcp_server.tools.card_search import search_cards as _search_cards_helper
from src.mcp_server.tools.companion import (
    CompanionStatusResult,
    SetActiveDeckResult,
    ShowGroupsResult,
    ShowSuggestionsResult,
    ShowSwapsResult,
    ShowTierListResult,
)
from src.mcp_server.tools.companion import companion_status as _companion_status_helper
from src.mcp_server.tools.companion import set_active_deck as _set_active_deck_helper
from src.mcp_server.tools.companion import show_groups as _show_groups_helper
from src.mcp_server.tools.companion import show_suggestions as _show_suggestions_helper
from src.mcp_server.tools.companion import show_swaps as _show_swaps_helper
from src.mcp_server.tools.companion import show_tier_list as _show_tier_list_helper
from src.mcp_server.tools.compare_deck_power import CompareDeckPowerResult
from src.mcp_server.tools.compare_deck_power import (
    compare_deck_power as _compare_deck_power_helper,
)
from src.mcp_server.tools.deck_analysis import (
    ManaCurveResult,
    SynergyResult,
    ValidateDeckResult,
)
from src.mcp_server.tools.deck_analysis import analyze_mana_curve as _analyze_mana_curve_helper
from src.mcp_server.tools.deck_analysis import detect_synergies as _detect_synergies_helper
from src.mcp_server.tools.deck_analysis import validate_deck as _validate_deck_helper
from src.mcp_server.tools.deck_import import DeckImportResult
from src.mcp_server.tools.deck_import import import_decklist as _import_decklist_helper
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
from src.mcp_server.tools.find_similar import SimilarCardsResult
from src.mcp_server.tools.find_similar import find_similar_cards as _find_similar_helper
from src.mcp_server.tools.initialize_database import InitializeDatabaseResult
from src.mcp_server.tools.initialize_database import (
    initialize_database as _initialize_database_helper,
)
from src.mcp_server.tools.semantic_search import SemanticSearchResult
from src.mcp_server.tools.semantic_search import semantic_search_cards as _semantic_search_helper
from src.mcp_server.tools.view_deck import ViewDeckResult
from src.mcp_server.tools.view_deck import view_deck as _view_deck_helper
from src.search import ConnectionFactory, Embedder, get_embedder

logger = logging.getLogger(__name__)


async def _emit_deck_changed(deck_id: str | None) -> None:
    """Tell the companion a deck's contents changed — after the commit, never inside it (c7-2).

    The one wire between the five deck-mutation tools and c7-1's shared notifier
    (:func:`src.companion.client.notify_deck_changed`). Each mutation wrapper awaits this *after*
    its ``async with session_factory()`` block has exited — every commit has landed and the pooled
    connection is released before the up-to-~1 s notify window opens — and only when its result
    proves a write actually happened. A plain bounded await, deliberately never a detached task
    (``create_task``/``ensure_future``/``TaskGroup``/``gather`` are banned on this path — a task
    outliving the tool call can be torn down before it runs, silently losing the event).

    The outcome never alters the tool's own result: the notifier never raises (AD-9), and all this
    function does with the :class:`~src.companion.client.PushOutcome` is debug-log it.

    **The accepted staleness window, stated where it is created (c7-7).** The ruling is AD-9
    (``ARCHITECTURE-SPINE.md:211``), and its twin copy lives on
    :func:`src.companion.client.notify_deck_changed`, the function this one awaits — same rule,
    stated at both sites that swallow so a reader arrives at it from either. **An amendment starts
    at the spine and changes both.** When this emit does
    not land — the companion is closed, the POST is refused, the backend answers 500, the one-second
    budget expires — the database has already changed and the glass has not heard about it. The deck
    view is then **stale until the next event or a WebSocket reconnect**, and *that is expected
    behaviour, not a defect to repair here*: out-of-band change detection is a later phase (FR-16),
    and until it ships the UI shows **no staleness warning of any kind** — the silence is
    deliberate, ruled at AD-9 and written into ``EXPERIENCE.md``'s Flow 1 failure path (*"the deck
    view is stale until the next event or reconnect; no error surfaces"*). Nothing in this function
    may grow a retry loop, a queue, a status field or a user-visible warning to close that window;
    the mutation's own result stays byte-identical to the no-companion baseline either way.
    """
    outcome = await _notify_deck_changed(deck_id)
    logger.debug(
        "deck_changed emit for deck_id=%s -> %s (clients=%s)",
        deck_id,
        outcome.outcome,
        outcome.clients,
    )


def build_server(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    connection_factory: ConnectionFactory | None = None,
    embedder: Embedder | None = None,
) -> FastMCP:
    """Build the FastMCP server with the Epic-1 tools plus the Story 2.4/2.5 sync search tools.

    Args:
        session_factory: Async session factory the ``async`` Epic-1 tools use for DB access. If
            ``None``, a default factory is built from the data-layer engine
            (reusing ``create_engine`` / ``create_session_factory``).
        connection_factory: Sync :class:`~src.search.connection.ConnectionFactory` the
            ``semantic_search_cards`` and ``find_similar_cards`` tools use to reach the
            ``sqlite-vec`` index. If ``None``, a default is constructed — it resolves the **same**
            DB file as the async engine via ``CARDS_DATABASE_URL`` / the central
            ``src.paths.database_path()`` (single-file topology, D2).
        embedder: Optional :class:`~src.search.embedder.Embedder` override (a **test seam**) used
            only by ``semantic_search_cards`` (``find_similar_cards`` never embeds). In production
            this stays ``None`` and the tool resolves the process-lifetime singleton lazily via
            :func:`~src.search.embedder.get_embedder` on first call — the model is never loaded at
            build time.

    Returns:
        A configured ``FastMCP`` instance with every tool registered (async Epic-1 tools plus the
        sync ``semantic_search_cards`` and ``find_similar_cards``).
    """
    if session_factory is None:
        session_factory = create_session_factory(create_engine())
    if connection_factory is None:
        connection_factory = ConnectionFactory()

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
            page_size: Results per page (default 20, max 100; the repository clamps to 50).

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
            result = await _create_deck_helper(
                session, name=name, format=format, strategy=strategy, tags=tags
            )
        if result.status == "ok" and result.deck is not None:
            await _emit_deck_changed(result.deck.id)
        return result

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
            result = await _delete_deck_helper(session, deck_id=deck_id)
        if result.status == "ok":
            await _emit_deck_changed(result.deck_id)
        return result

    @mcp.tool()
    async def add_card_to_deck(
        deck_id: str,
        card_id: str | None = None,
        name: str | None = None,
        quantity: int = 1,
        sideboard: bool = False,
        commander: bool = False,
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
            quantity: Number of copies to add (1 to 250; default 1).
            sideboard: Add to the sideboard instead of the mainboard (default False).
            commander: Mark this card as the deck's commander (default False;
                flag two cards for partners).

        Returns:
            A result whose ``status`` reports the outcome (``ok``/``exists``/
            ``deck_not_found``/``card_not_found``/``ambiguous``/``invalid``).
        """
        async with session_factory() as session:
            result = await _add_card_to_deck_helper(
                session,
                deck_id=deck_id,
                card_id=card_id,
                name=name,
                quantity=quantity,
                sideboard=sideboard,
                commander=commander,
            )
        if result.status == "ok":
            await _emit_deck_changed(result.deck_id)
        return result

    @mcp.tool()
    async def import_decklist(deck_id: str, arena_export: str) -> DeckImportResult:
        """Bulk-add an MTG Arena export to an existing saved deck.

        Accepts Arena's ``Commander`` / ``Deck`` / ``Sideboard`` / ``Companion``
        sections with card lines shaped like ``1 Card Name (SET) 123``; the
        optional ``About`` / ``Name`` metadata block is skipped. Commander
        entries become mainboard cards **flagged as commanders**; Deck entries
        become unflagged mainboard cards; Sideboard and Companion entries
        become sideboard cards.
        The import is additive: it never clears the deck or silently merges an
        existing quantity. Each nonblank card line gets an ordered result such as
        ``ok``, ``ambiguous``, ``not_found``, ``invalid``, or ``exists``. Valid
        lines remain persisted when another line fails.

        Args:
            deck_id: Existing saved deck id from ``create_deck`` or ``list_decks``.
            arena_export: The complete Arena export text to parse and import.

        Returns:
            A structured summary with imported line/copy totals and per-line outcomes.
        """
        async with session_factory() as session:
            result = await _import_decklist_helper(
                session, deck_id=deck_id, arena_export=arena_export
            )
        # One emit per tool call, not per imported line — the helper's per-line delegation to
        # add_card_to_deck commits N times, and the glass needs to hear "changed" exactly once.
        if result.imported_lines > 0:
            await _emit_deck_changed(result.deck_id)
        return result

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
            result = await _remove_card_from_deck_helper(
                session,
                deck_id=deck_id,
                card_id=card_id,
                name=name,
                sideboard=sideboard,
            )
        if result.status == "ok":
            await _emit_deck_changed(result.deck_id)
        return result

    @mcp.tool()
    async def view_deck(deck_id: str, open_browser: bool = True) -> ViewDeckResult:
        """DEPRECATED — renders a saved deck as static HTML; superseded by the companion app.

        Prefer ``companion_set_active_deck``: it puts the deck on a running companion
        window that follows the conversation, instead of writing a one-shot HTML file.
        This tool keeps working unchanged for anyone not running the companion, and
        nothing about it will change before it is removed.

        Loads the deck by id, renders the read-only HTML deck viewer, writes it to a
        temp file, and (by default) opens it in this machine's default browser — the
        server runs locally, so the page opens on the user's own desktop. Opening is
        best-effort: ``file_path`` is always returned, so the page is reachable even
        when no browser can be launched (set ``open_browser=False`` to render only).
        Read-only and stateless — pass ``deck_id`` (from ``create_deck`` /
        ``list_decks``) every call.

        Args:
            deck_id: The deck id to view.
            open_browser: Open the rendered page in the default browser (default
                True); set False to render the file without opening it.

        Returns:
            A result whose ``status`` is ``ok`` (``file_path`` set,
            ``opened_in_browser`` reports whether a browser launched), ``not_found``,
            ``error``, or ``database_not_initialized``.
        """
        async with session_factory() as session:
            return await _view_deck_helper(session, deck_id=deck_id, open_browser=open_browser)

    @mcp.tool()
    async def companion_status() -> CompanionStatusResult:
        """Report whether the companion app is running, and how to open it if not.

        Use this when the user asks to open or see the companion, or when a
        companion tool answered ``app_not_running`` and you want to offer to
        start it. Read-only: it sends nothing to the companion and changes
        nothing. To actually open it, run the returned ``launch_command`` in a
        background shell (the ``companion`` skill walks through it): the
        companion starts in the foreground, prints its URL, and opens a browser
        tab on it itself. Run the command as returned — add ``--port N`` only
        when the user asked for a specific port — and never in the foreground:
        it serves until interrupted.

        Returns:
            A result whose ``status`` is ``running`` (``url`` is the companion's
            address and ``clients`` counts the open browser tabs — with one or
            more, there is nothing to do; with zero, run ``launch_command``,
            whose ``--open`` opens a tab on the running instance, and give the
            user ``url`` only if no browser could open) or ``not_running`` (run
            ``launch_command``). ``launch_command`` is set on every status.
        """
        return await _companion_status_helper()

    @mcp.tool()
    async def companion_set_active_deck(deck_id: str) -> SetActiveDeckResult:
        """Show a saved deck in the companion app's live browser view.

        Use this when the user says which deck they want to look at, or when the
        conversation moves to a different deck — the companion follows the
        conversation instead of the user switching it by hand. It changes only what
        is displayed: nothing about the deck is modified. Get the ``deck_id`` from
        ``create_deck`` or ``list_decks``.

        The companion app has to be running; if it is not, this reports that and
        nothing else happens — ``companion_status`` tells you how to open it.
        Stateless — pass ``deck_id`` every call.

        Args:
            deck_id: The deck id to display.

        Returns:
            A result whose ``status`` is ``displayed`` (showing now — ``clients``
            counts the browser tabs that updated), ``no_clients_connected`` (set, but
            no tab is open to see it), ``deck_not_found`` (no such deck; the
            companion was not contacted), ``app_not_running`` (the companion isn't
            running), ``payload_rejected``, ``backend_error``,
            ``database_not_initialized``, or ``error``.
        """
        async with session_factory() as session:
            return await _set_active_deck_helper(session, deck_id=deck_id)

    @mcp.tool()
    async def companion_show_suggestions(payload: SuggestionsPayload) -> ShowSuggestionsResult:
        """Show a list of suggested cards in the companion app's live browser view.

        Use this when you have card suggestions for the user — cards to add,
        consider, or look at — so they can see the actual cards instead of
        reading a list of names. Send the suggestions here **and** give your
        normal answer in the conversation as you always would; this adds a
        visual channel, it does not replace the reply.

        Name each card by its Scryfall printing id, which ``lookup_card_by_name``
        or any of this server's search tools returns as the card's ``id``. A
        card name in ``card_id`` will not render. An empty ``items`` list is a
        legitimate push meaning "I looked and found nothing" — send it rather
        than skipping the call.

        The companion app has to be running; if it is not, this reports that,
        nothing is sent, and your written answer still stands on its own
        (``companion_status`` tells you how to open it).
        Stateless and cumulative in nothing — each call carries its whole
        payload, and the companion shows what the latest call sent.

        Args:
            payload: The suggestions to display. ``payload.items`` is a list of
                at most 60 suggestions, shown in the order you send them, each
                with ``card_id`` (the Scryfall printing id, required),
                ``reason`` (one short line saying why, required, up to 200
                characters), ``category`` (an optional short badge such as
                "Curve" or "Removal" — a label on the row, not a heading that
                groups anything, up to 80 characters), and ``confidence``
                (optional, one of ``low``, ``medium``, ``high``).
                ``payload.title`` is an optional header for the list, up to 80
                characters; omit it to let the companion use its own.

        Returns:
            A result whose ``status`` is ``displayed`` (delivered to at least
            one connected browser tab now — ``clients`` counts how many;
            whether that tab currently renders suggestions on screen is its
            own concern, not this tool's), ``no_clients_connected`` (the
            companion took it but no tab is open to see it — do not send it
            again), ``app_not_running`` (the companion isn't running, and
            nothing was sent), ``payload_rejected`` (the companion refused the
            suggestions themselves), or ``backend_error`` (the companion is
            running and the push did not land). ``items_pushed`` reports how
            many suggestions the call attempted to push, on every status —
            including the ones where nothing actually reached the wire.
        """
        return await _show_suggestions_helper(payload=payload)

    @mcp.tool()
    async def companion_show_swaps(payload: SwapsPayload) -> ShowSwapsResult:
        """Show a list of proposed card swaps in the companion app's live browser view.

        Use this when you propose trading cards out of a deck for cards into it —
        "cut X for Y" — so the user sees both actual cards side by side instead of
        reading a list of names. Send the swaps here **and** give your normal
        answer in the conversation as you always would; this adds a visual
        channel, it does not replace the reply.

        Name each card by its Scryfall printing id, which ``lookup_card_by_name``
        or any of this server's search tools returns as the card's ``id``. A card
        name in ``out_card_id`` or ``in_card_id`` will not render. An empty
        ``items`` list is a legitimate push meaning "I looked and found no trade
        worth proposing" — send it rather than skipping the call.

        The companion app has to be running; if it is not, this reports that,
        nothing is sent, and your written answer still stands on its own
        (``companion_status`` tells you how to open it).
        Stateless and cumulative in nothing — each call carries its whole
        payload, and the companion shows what the latest call sent.

        Args:
            payload: The swaps to display. ``payload.items`` is a list of at
                most 60 swaps, shown in the order you send them, each with
                ``out_card_id`` (the Scryfall printing id of the card leaving
                the deck, required), ``in_card_id`` (the Scryfall printing id
                of the card entering it, required), ``rationale`` (why the
                trade is worth making, required, non-blank, up to 600
                characters),
                ``out_qty`` and ``in_qty`` (how many copies leave and enter,
                required, zero or more — zero is legal), and ``confidence``
                (optional, one of ``low``, ``medium``, ``high``).
                ``payload.title`` is an optional header for the list, up to 80
                characters; omit it to let the companion use its own. Note the
                total envelope is capped at 64 KB: a payload that maxes every
                field cap at once (60 swaps, each with a full 600-character
                rationale) exceeds it and comes back ``payload_rejected``, so
                keep large pushes comfortably inside the caps rather than at
                them.

        Returns:
            A result whose ``status`` is ``displayed`` (delivered to at least
            one connected browser tab now — ``clients`` counts how many),
            ``no_clients_connected`` (the companion took it but no tab is open
            to see it — do not send it again), ``app_not_running`` (the
            companion isn't running, and nothing was sent), ``payload_rejected``
            (the companion refused the envelope itself), or ``backend_error``
            (the companion is running and the push did not land).
            ``items_pushed`` counts the swap pairs the call attempted to push,
            on every status — including the ones where nothing reached the wire.
        """
        return await _show_swaps_helper(payload=payload)

    @mcp.tool()
    async def companion_show_tier_list(payload: TierListPayload) -> ShowTierListResult:
        """Show a tier list — cards ranked into named tiers — in the companion app's
        live browser view.

        Use this when you rank cards into tiers — "which creatures earn their slot",
        "how do these removal spells stack up" — so the user sees the actual cards
        grouped under each rank instead of reading a list of names. Send the tier
        list here **and** give your normal answer in the conversation as you always
        would; this adds a visual channel, it does not replace the reply.

        Name each card by its Scryfall printing id, which ``lookup_card_by_name``
        or any of this server's search tools returns as the card's ``id``. A card
        name in ``card_ids`` will not render. An empty ``items`` list is a
        legitimate push meaning "I found nothing worth tiering" — send it rather
        than skipping the call.

        The companion app has to be running; if it is not, this reports that,
        nothing is sent, and your written answer still stands on its own
        (``companion_status`` tells you how to open it).
        Stateless and cumulative in nothing — each call carries its whole
        payload, and the companion shows what the latest call sent.

        Args:
            payload: The tiers to display. ``payload.items`` is a list of at most
                12 tiers, shown in the order you send them, each with ``letter``
                (one of ``S``, ``A``, ``B``, ``C``, ``D`` — a closed set), ``name``
                (what the tier means in MTG terms, such as "Auto-include" or
                "Filler" — required, non-blank, up to 40 characters; the letter
                never stands alone), ``note`` (an optional line of commentary, up
                to 200 characters), and ``card_ids`` (the Scryfall printing ids in
                that tier, up to 60, shown in the order you send them — may be
                empty). Repeating a letter under a different name is legal: the
                12-tier cap and the 5-letter vocabulary are different quantities.
                ``payload.title`` is an optional header for the list, up to 80
                characters; omit it to let the companion use its own. Note the
                total envelope is capped at 64 KB: a payload that maxes every
                field cap at once (12 tiers of 60 ids with full names and
                notes) exceeds it and comes back ``payload_rejected``, so keep
                large pushes comfortably inside the caps rather than at them.

        Returns:
            A result whose ``status`` is ``displayed`` (delivered to at least one
            connected browser tab now — ``clients`` counts how many),
            ``no_clients_connected`` (the companion took it but no tab is open to
            see it — do not send it again), ``app_not_running`` (the companion
            isn't running, and nothing was sent), ``payload_rejected`` (the
            companion refused the envelope itself), or ``backend_error`` (the
            companion is running and the push did not land). ``items_pushed``
            counts the **tiers** the call attempted to push — never the cards
            inside them — on every status, including the ones where nothing
            reached the wire.
        """
        return await _show_tier_list_helper(payload=payload)

    @mcp.tool()
    async def companion_show_groups(payload: GroupsPayload) -> ShowGroupsResult:
        """Show titled card groups — cards gathered under named headings, each with a
        paragraph of reasoning — in the companion app's live browser view.

        Use this when you organise cards into themed groups — "the ramp package",
        "budget substitutes", "answers you are not running" — so the user sees the
        actual cards under each heading instead of reading a list of names. Send
        the groups here **and** give your normal answer in the conversation as you
        always would; this adds a visual channel, it does not replace the reply.

        Name each card by its Scryfall printing id, which ``lookup_card_by_name``
        or any of this server's search tools returns as the card's ``id``. A card
        name in ``card_ids`` will not render. A group may legitimately name cards
        the active deck does not run — grouping is an argument about cards, not an
        inventory of the deck. An empty ``card_ids`` list is legal (the group is
        not displayed at all), and an empty ``items`` list is a legitimate
        push meaning "I found no grouping worth drawing" — send it rather than
        skipping the call.

        The companion app has to be running; if it is not, this reports that,
        nothing is sent, and your written answer still stands on its own
        (``companion_status`` tells you how to open it).
        Stateless and cumulative in nothing — each call carries its whole
        payload, and the companion shows what the latest call sent.

        Args:
            payload: The groups to display. ``payload.items`` is a list of at most
                12 groups, shown in the order you send them, each with ``title``
                (the group's own heading — required, non-blank, up to 80
                characters; this is the per-group heading, distinct from the
                optional ``payload.title`` below), ``rationale`` (the paragraph
                explaining the group — required, non-blank, up to 600 characters),
                and ``card_ids`` (the Scryfall printing ids in that group, up to
                60, each up to 128 characters, shown in the order you send them —
                may be empty). ``payload.title`` is an optional header for the
                whole view, up to 80 characters; omit it to let the companion use
                its own. Note the total envelope is capped at 64 KB: a payload
                that maxes every field cap at once (12 groups of 60 ids with full
                titles and rationales) exceeds it and comes back
                ``payload_rejected``, so keep large pushes comfortably inside the
                caps rather than at them.

        Returns:
            A result whose ``status`` is ``displayed`` (delivered to at least one
            connected browser tab now — ``clients`` counts how many),
            ``no_clients_connected`` (the companion took it but no tab is open to
            see it — do not send it again), ``app_not_running`` (the companion
            isn't running, and nothing was sent), ``payload_rejected`` (the
            companion refused the envelope itself), or ``backend_error`` (the
            companion is running and the push did not land). ``items_pushed``
            counts the **groups** the call attempted to push — never the cards
            inside them — on every status, including the ones where nothing
            reached the wire.
        """
        return await _show_groups_helper(payload=payload)

    @mcp.tool()
    async def analyze_mana_curve(deck_id: str) -> ManaCurveResult:
        """Analyze a deck's mana curve by id.

        Loads the deck and analyzes its mainboard only (sideboard excluded),
        returning the CMC distribution, land/spell counts, average CMC,
        turn-by-turn playability, land ratio, and any detected issues with
        recommendations. Observational — it does not modify the deck. Use
        ``load_deck`` for the card list. Stateless: pass ``deck_id`` every call.

        Args:
            deck_id: The deck id (from ``create_deck`` or ``list_decks``).

        Returns:
            A result whose ``status`` is ``ok`` (analysis populated), ``empty``
            (no mainboard cards), ``deck_not_found``, or ``error``.
        """
        async with session_factory() as session:
            return await _analyze_mana_curve_helper(session, deck_id=deck_id)

    @mcp.tool()
    async def detect_synergies(deck_id: str) -> SynergyResult:
        """Detect synergy patterns in a deck by id.

        Loads the deck and analyzes its mainboard only (sideboard excluded),
        returning detected tribal/keyword/mechanic synergies (each naming the
        cards involved), a count, and an overall cohesion rating. Observational —
        it does not modify the deck. Stateless: pass ``deck_id`` every call.

        Args:
            deck_id: The deck id (from ``create_deck`` or ``list_decks``).

        Returns:
            A result whose ``status`` is ``ok`` (synergies populated), ``empty``
            (no mainboard cards), ``deck_not_found``, or ``error``.
        """
        async with session_factory() as session:
            return await _detect_synergies_helper(session, deck_id=deck_id)

    @mcp.tool()
    async def validate_deck(
        deck_id: str, format: str = "standard", games: list[str] | None = None
    ) -> ValidateDeckResult:
        """Validate a deck's construction legality (size, copy limits, format legality).

        Loads the deck and checks the constructed rules: mainboard size, sideboard
        size, the copy limit (combined across both boards, basics exempt — 4
        copies normally, 1 copy in the singleton formats brawl / standardbrawl /
        commander / gladiator / competitivebrawl / duel / oathbreaker /
        paupercommander / predh, reported as a
        ``singleton`` violation), per-card legality in ``format``, and — when
        ``games`` is given — card availability on those platforms (union of games
        across all printings). ``format`` is case-insensitive (lowercased before
        use); ``format``/``games`` are per-call parameters (no server-side
        state). Returns a report listing every violation; ``report.is_legal`` is
        the overall verdict.

        Args:
            deck_id: The deck id (from ``create_deck`` or ``list_decks``).
            format: The MTG format to validate against (default "standard");
                case-insensitive.
            games: Optional platforms ("paper"/"arena"/"mtgo") the deck must be
                playable on; omit to skip the availability check.

        Returns:
            A result whose ``status`` is ``ok`` (``report`` populated),
            ``deck_not_found``, ``invalid`` (a bad ``games`` value), or ``error``.
        """
        async with session_factory() as session:
            return await _validate_deck_helper(session, deck_id=deck_id, format=format, games=games)

    @mcp.tool()
    async def assess_deck_power(deck_id: str, format: str | None = None) -> AssessDeckPowerResult:
        """Assess a saved deck's power level by id — deterministic 0-100 score with evidence.

        Loads the deck (mainboard only), resolves the scoring format (explicit
        ``format`` param first, else the deck's stored format, else a flagged
        commander implies commander) and the commander(s) (flagged rows first,
        else a sole legendary creature in a commander deck, else
        unidentified), then scores the deck and returns a structured
        ``assessment`` block: a 7-dimension integer vector (speed, consistency,
        resilience, interaction, mana_efficiency, card_advantage,
        combo_potential), a ``for_format_score`` (0-100) with its descriptive
        ``tier`` label, the Commander ``bracket`` floor (``null`` for
        standard), ``data_vintage`` (combo-snapshot age + profile version — the
        only "as of" facts), a ``confidence`` level with named reasons, and
        explainability ``flags`` (Game Changer names, matched combos with
        included/almost_included buckets, structural gaps, cEDH candidacy).
        Deterministic: the same deck against the same card + combo data
        serializes byte-identically, so two results can be diffed. Missing
        inputs (no combo snapshot, unidentified commander, unknown Game Changer
        data) degrade ``confidence`` with named reasons — the deck is still
        scored. Supported formats: ``commander`` and ``standard``; anything
        else (e.g. brawl) returns ``unsupported_format`` — pass ``format``
        explicitly to force a profile. Observational — it does not modify the
        deck. Stateless: pass ``deck_id`` every call.

        Args:
            deck_id: The deck id (from ``create_deck`` or ``list_decks``).
            format: Optional format override ("commander" or "standard",
                case-insensitive); omit to infer from the deck.

        Returns:
            A result whose ``status`` is ``ok`` (``assessment`` populated,
            ``summary`` its human projection), ``deck_not_found``,
            ``unsupported_format``, ``database_not_initialized``, or
            ``error``.
        """
        async with session_factory() as session:
            return await _assess_deck_power_helper(session, deck_id=deck_id, format=format)

    @mcp.tool()
    async def compare_deck_power(
        deck_id_a: str, deck_id_b: str, format: str | None = None
    ) -> CompareDeckPowerResult:
        """Compare two saved decks' power assessments — deterministic server-side deltas.

        Runs the same assessment pipeline as ``assess_deck_power`` on both
        decks and returns a structured ``comparison`` block of every
        difference, so no caller ever re-derives the arithmetic. Delta
        direction is **b − a**: ``deck_id_a`` is the baseline ("before"),
        ``deck_id_b`` the candidate ("after") — a positive delta means the
        candidate is higher. The block carries the 7-dimension
        ``vector_delta``, the ``for_format_score`` delta with both endpoints
        and tiers, the Commander bracket pair (``bracket_a``/``bracket_b`` —
        endpoints, never subtracted; ``null`` for standard), sorted
        added/removed lists for Game Changers, structural gaps, and combos
        (plus ``combos_bucket_changed`` for variants whose
        included/almost_included bucket flipped), per-side booleans, and both
        sides' ``data_vintage`` and ``confidence`` blocks verbatim.
        Deterministic: identical inputs serialize byte-identically; comparing
        a deck with itself (legal) yields all-zero deltas and empty lists. To
        compare two versions of ONE deck, snapshot it first — export via
        ``view_deck``/``load_deck``, then ``create_deck`` +
        ``import_decklist`` (or re-add the rows) to freeze the "before" copy,
        edit the original, and compare the two ids. If the two decks resolve
        to different formats the result is ``format_mismatch`` — pass
        ``format`` explicitly to force both sides. A side that fails to
        assess yields ``deck_a_failed`` / ``deck_b_failed`` /
        ``both_decks_failed`` with the underlying reason in ``summary``.
        Observational — modifies nothing. Stateless: pass both deck ids every
        call.

        Args:
            deck_id_a: The baseline deck id (from ``create_deck`` or
                ``list_decks``).
            deck_id_b: The candidate deck id; may equal ``deck_id_a``.
            format: Optional format override ("commander" or "standard",
                case-insensitive) applied to BOTH decks; omit to let each
                deck resolve its own format.

        Returns:
            A result whose ``status`` is ``ok`` (``comparison`` populated,
            ``summary`` its human projection), ``deck_a_failed``,
            ``deck_b_failed``, ``both_decks_failed``, ``format_mismatch``,
            ``database_not_initialized``, or ``error``.
        """
        async with session_factory() as session:
            return await _compare_deck_power_helper(
                session, deck_id_a=deck_id_a, deck_id_b=deck_id_b, format=format
            )

    @mcp.tool()
    def semantic_search_cards(
        query: str,
        colors: list[str] | None = None,
        color_mode: Literal["any", "all", "exact", "at_most"] = "any",
        mana_value_min: float | None = None,
        mana_value_max: float | None = None,
        format: str | None = None,
        games: list[str] | None = None,
        limit: int = 10,
    ) -> SemanticSearchResult:
        """Search Magic: The Gathering cards by *meaning* (semantic similarity), with filters.

        Embeds your natural-language ``query`` and finds the nearest cards by vector similarity,
        then composes any optional relational filters into the **same hybrid query** — so one call
        answers things like *"semantically like Glorybringer, Standard-legal red 4-drops"*. Results
        are ranked nearest-first, de-duplicated to one entry per card, and returned as lightweight
        summaries (each with a ``distance`` relevance signal) — use ``lookup_card_by_name`` for full
        detail. Prefer this over ``search_cards`` when the intent is conceptual ("aggressive red
        one-drops", "graveyard recursion") rather than exact keyword/type filters. Stateless: pass
        ``format``/``games`` and every filter on each call (nothing is remembered between calls).

        Args:
            query: Natural-language description of what to search for (must be non-empty).
            colors: Color codes (W/U/B/R/G), interpreted by ``color_mode``.
            color_mode: How ``colors`` is matched — ``any`` (has any), ``all`` (has all),
                ``exact`` (exactly these and no others), ``at_most`` (only these or fewer).
            mana_value_min: Inclusive minimum mana value (CMC).
            mana_value_max: Inclusive maximum mana value (CMC).
            format: Restrict to cards legal in this format (e.g. "standard").
            games: Restrict to platforms (any of "paper", "arena", "mtgo").
            limit: Maximum number of cards to return (default 10).

        Returns:
            A result whose ``status`` is ``ok`` (``cards`` ranked nearest-first, each with a
            ``distance``), ``empty`` (a valid query with no surviving matches — a graceful hint),
            ``invalid`` (a query/filter value failed validation, with a message naming it),
            ``index_unavailable`` (the semantic index has not been built yet — run the
            ``build_search_index`` tool), or ``database_not_initialized`` (no card data yet — run
            the ``initialize_database`` tool).
        """
        # Sync tool: FastMCP threadpools it. Per-thread sqlite-vec connection (NFR6); the embedder
        # is the injected test seam or the lazily-built process singleton (never loaded at build).
        conn = connection_factory.get_connection()
        emb = embedder if embedder is not None else get_embedder()
        return _semantic_search_helper(
            conn,
            emb,
            query,
            colors=colors,
            color_mode=color_mode,
            mana_value_min=mana_value_min,
            mana_value_max=mana_value_max,
            format=format,
            games=games,
            limit=limit,
        )

    @mcp.tool()
    def find_similar_cards(
        card_name: str | None = None,
        card_id: str | None = None,
        colors: list[str] | None = None,
        color_mode: Literal["any", "all", "exact", "at_most"] = "any",
        mana_value_min: float | None = None,
        mana_value_max: float | None = None,
        format: str | None = None,
        games: list[str] | None = None,
        limit: int = 10,
    ) -> SimilarCardsResult:
        """Find Magic: The Gathering cards similar to a *seed card* you already have.

        Give a concrete card by ``card_name`` OR ``card_id`` (exactly one); this reads that card's
        stored semantic vector and returns the nearest *other* cards by meaning, then composes any
        optional relational filters into the **same hybrid query**. The seed itself — and every
        other printing of it — is excluded, so results are genuine **alternatives, not the seed
        echoed back**: use it for "more cards like this", replacements, or synergy pieces. Results
        are ranked nearest-first, de-duplicated to one entry per card, and returned as lightweight
        summaries (each with a ``distance`` relevance signal) — use ``lookup_card_by_name`` for full
        detail. Prefer this over ``semantic_search_cards`` when you have a specific card in hand
        rather than a natural-language description. Stateless: pass ``format``/``games`` and every
        filter on each call (nothing is remembered between calls).

        Args:
            card_name: The seed card's name (exact or fuzzy) — provide this OR ``card_id``, not
                both.
            card_id: The seed card's id — provide this OR ``card_name``, not both.
            colors: Color codes (W/U/B/R/G), interpreted by ``color_mode``.
            color_mode: How ``colors`` is matched — ``any`` (has any), ``all`` (has all),
                ``exact`` (exactly these and no others), ``at_most`` (only these or fewer).
            mana_value_min: Inclusive minimum mana value (CMC).
            mana_value_max: Inclusive maximum mana value (CMC).
            format: Restrict to cards legal in this format (e.g. "standard").
            games: Restrict to platforms (any of "paper", "arena", "mtgo").
            limit: Maximum number of alternatives to return (default 10).

        Returns:
            A result whose ``status`` is ``ok`` (``cards`` ranked nearest-first, each with a
            ``distance``, plus the resolved ``seed``), ``empty`` (seed found but no alternatives
            survived the filters), ``not_found`` (no such card, or the card isn't in the semantic
            index yet), ``ambiguous`` (the name matched multiple cards — see ``matches``, re-call
            with a ``card_id``), ``invalid`` (a parameter failed validation),
            ``index_unavailable`` (the semantic index has not been built yet — run the
            ``build_search_index`` tool), or ``database_not_initialized`` (no card data yet — run
            the ``initialize_database`` tool).
        """
        # Sync tool: FastMCP threadpools it. Per-thread sqlite-vec connection (NFR6). This tool
        # never embeds — it reads the seed's stored vector — so it needs no embedder.
        conn = connection_factory.get_connection()
        return _find_similar_helper(
            conn,
            card_name=card_name,
            card_id=card_id,
            colors=colors,
            color_mode=color_mode,
            mana_value_min=mana_value_min,
            mana_value_max=mana_value_max,
            format=format,
            games=games,
            limit=limit,
        )

    # Both tools below wipe-and-rebuild local state (the card tables / the embedding index), so
    # they carry an honest destructive hint for clients that gate such tools behind confirmation.
    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def initialize_database(update: bool = False) -> InitializeDatabaseResult:
        """Download the Magic card data and set up — or update — the local database.

        Run this once on a fresh install before using the card/deck tools: a packaged install ships
        with **no card data**, so the first card or deck call returns ``database_not_initialized``
        until this has run. It downloads the latest Scryfall ``default_cards`` set (a **~500 MB**
        download; allow a few minutes) into this machine's local data directory and creates the
        schema. The import deduplicates to one row per card (oracle identity) and stores each
        card's ``games`` as the union across all printings, so Arena/MTGO availability is accurate
        even when a card's newest printing is paper-only. Idempotent — if the cards are already
        present it returns ``already_initialized`` and downloads nothing.

        When a **new set releases**, run it again with ``update=true`` to refresh the database: it
        re-downloads the latest set and upserts it, adding new cards, refreshing existing ones
        (errata, banlist/legality changes), and reconciling older rows' ``games`` to the
        cross-printing union, without dropping anything. This imports the cards only; to enable
        (or refresh) semantic search, follow up with ``build_search_index``.

        Args:
            update: When ``true``, refresh an already-populated database with the latest card data
                (use this after a new set comes out). Default ``false`` — a one-time first-run
                import that does nothing if cards are already present.

        Returns:
            A result whose ``status`` is ``ok`` (first-run import — see ``cards_imported`` /
            ``cards_total``), ``updated`` (an ``update=true`` run — ``cards_imported`` is the count
            of new cards added), ``already_initialized`` (cards were already present and ``update``
            was not requested), or ``error`` (the import failed; ``message`` explains).
        """
        return await _initialize_database_helper(update=update)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    def build_search_index(rebuild: bool = False) -> BuildSearchIndexResult:
        """Build the semantic search index (one-time step that enables semantic_search_cards).

        Run this after ``initialize_database`` to enable ``semantic_search_cards`` and
        ``find_similar_cards``: it downloads a small embedding model (~80 MB) on first run and
        indexes every card (~5 minutes). Until it has run, those two tools return
        ``index_unavailable``. Idempotent and incremental — re-running only re-embeds cards that
        changed, so it is cheap to repeat. If the card data hasn't been imported yet it returns
        ``database_not_initialized`` (run ``initialize_database`` first).

        Args:
            rebuild: Drop and fully rebuild the index from scratch (use after the embedding model
                changes; normally leave ``False`` for a fast incremental update).

        Returns:
            A result whose ``status`` is ``ok`` (index built — see ``cards_indexed`` /
            ``cards_skipped``), ``database_not_initialized`` (import the cards first), or ``error``.
        """
        # Sync tool: FastMCP threadpools it. Reuses the injected sqlite-vec connection factory and
        # the lazily-built embedder singleton (``embedder`` is the build_server test seam).
        return _build_search_index_helper(connection_factory, embedder=embedder, rebuild=rebuild)

    return mcp

"""The companion tools — what the agent tells the glass to do (FR-07, FR-08, AD-8, AD-16).

The MCP side of the companion feature: a tool here delegates the wire work to the leaf client
(:mod:`src.companion.client`) and turns the client's closed outcome vocabulary into the ``status``
convention every other tool in this package already uses.

**Two shapes live here, and the difference is the database.** A *control* tool tells the companion
to change what it is showing out of data the companion can fetch for itself, so it validates its
argument against the database first — :func:`set_active_deck` is the one. A *push* tool carries the
content itself and validates nothing against the corpus (AD-7: card ids are deliberately not
checked), so it holds no session at all — :func:`show_suggestions` is the one. That is why only the
first carries ``deck_not_found`` / ``database_not_initialized`` / ``error``: the second has no
database to be wrong about, and its ``status`` set is the client's five tokens verbatim (AD-8).

**Why the deck lookup lives here and not in the backend.** ``PUT /api/active-deck`` has no database
and no ``404`` — it stores whatever it is given, deliberately (AD-16). The party that can tell an
agent "there is no such deck" is the party holding a session, which is this one. So the existence
check happens *before* any HTTP, and a missing deck never reaches the network.

**Nothing here is cached, and nothing is remembered between calls** (CM-3). The active deck lives in
the companion backend's memory, so two agent sessions talking to one companion see one active deck
rather than two disagreeing ones. A module-level "last deck we set" would be exactly the drift this
design avoids.

Importing the leaf is allowed and importing the app is not (AD-3): ``src.companion.client`` pulls in
``httpx`` and ``pydantic`` and stops there, so a stdio MCP session never transitively loads FastAPI
or uvicorn. ``tests/unit/companion/test_import_boundary.py`` enforces the difference.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from src.companion.client import base_url as _client_base_url
from src.companion.client import live_instance as _client_live_instance
from src.companion.client import probe_health as _client_probe_health
from src.companion.client import push_event as _client_push_event
from src.companion.client import set_active_deck as _client_set_active_deck
from src.companion.contracts import (
    ActiveDeckRequest,
    GroupsEvent,
    GroupsPayload,
    SuggestionsEvent,
    SuggestionsPayload,
    SwapsEvent,
    SwapsPayload,
    TierListEvent,
    TierListPayload,
)
from src.data.database import is_database_initialized
from src.data.repositories.deck import DeckRepository
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

logger = logging.getLogger(__name__)

_ECHO_LIMIT = 48
"""Bounds any caller- or database-sourced string echoed into a result — a *display* bound, distinct
from ``ActiveDeckRequest``'s 256-char *storage* bound on ``deck_id`` (``contracts.py``). It covers
two different unbounded sources: the tool's own ``deck_id`` parameter, which nothing validates
before the database lookup (unlike the wire's own request body); and ``deck.name``, which
``create_deck`` only refuses when blank and never caps in length. A result can echo one of these
twice (a miss puts ``deck_id`` in both the field and the message sentence; a success does the same
for ``deck_name``), and the ``database_not_initialized`` path pairs one echo with
``DATABASE_NOT_INITIALIZED_MESSAGE`` (225 chars on its own) — so even the wire's own 256-char cap
on ``deck_id`` would blow the ~200-token budget doubled, and this needs a smaller number than that.
All 40 ids in the shipped database are 36-character uuids (measured 2026-08-01, the same measurement
``_MAX_DECK_ID_LENGTH`` cites); 48 is headroom above that without threatening the budget in the
message that already carries the most fixed text (measured: 378 of the 400-char test convention
used throughout this file, itself half of AC 5's ~200-token/~800-character estimate).
"""


def _truncate_for_echo(value: str) -> str:
    """Bound a caller- or database-sourced string before it is echoed into a result (CM-1, AC 5)."""
    return value if len(value) <= _ECHO_LIMIT else value[:_ECHO_LIMIT] + "…"


class SetActiveDeckResult(BaseModel):
    """Structured result of ``companion_set_active_deck``.

    The ``status`` values are the leaf client's five wire outcomes plus three this layer owns:
    ``deck_not_found`` (the database read, before any HTTP) and the ``database_not_initialized`` /
    ``error`` pair every tool in this package carries. Layering rather than widening is the ruling
    (AD-16): the client's set stays closed at five because five is what the *wire* can tell it.

    Attributes:
        status: ``displayed`` (the companion switched and at least one tab saw it),
            ``no_clients_connected`` (switched, but no tab is open — a success, not a failure),
            ``deck_not_found`` (no such deck; nothing was sent), ``app_not_running`` (no companion
            could be proven live; no credential left the process), ``payload_rejected`` (the
            companion refused the request itself), ``backend_error`` (the companion is there and
            the change did not land), ``database_not_initialized`` or ``error``.
        deck_id: The deck asked for, echoed on every status so a caller can pair result to request.
            Before the deck is found, this is the caller's own argument, bounded to
            :data:`_ECHO_LIMIT` (nothing validates it beforehand); once found it is ``deck.id``,
            already bounded by the wire's own cap.
        deck_name: The deck's name, when the deck was found — lets the agent confirm by name rather
            than by uuid. Bounded to :data:`_ECHO_LIMIT`; ``create_deck`` refuses a blank name but
            never caps its length.
        clients: How many connected browsers received the change, when the companion said. ``None``
            on every status that never reached a receipt, which is deliberately distinguishable
            from ``0``: "nobody told us" and "nobody was watching" are different facts.
        message: One short human-facing sentence. Never echoes the deck's contents (CM-1).
    """

    status: Literal[
        "displayed",
        "no_clients_connected",
        "deck_not_found",
        "app_not_running",
        "payload_rejected",
        "backend_error",
        "database_not_initialized",
        "error",
    ]
    deck_id: str | None = None
    deck_name: str | None = None
    clients: int | None = None
    message: str


_MESSAGES = {
    "no_clients_connected": (
        "The companion switched decks, but no browser tab is open to see it — open the URL the "
        "companion printed when it started."
    ),
    "app_not_running": (
        "The companion app isn't running, so there is nothing to display on. You can open it "
        "for the user: call companion_status and run the launch command it returns (the "
        "companion skill walks through it), then ask again."
    ),
    "payload_rejected": "The companion refused the request, so the display did not change.",
    "backend_error": "The companion is running but the change didn't land. Try again.",
}
"""The wording for every outcome that is not a plain success, keyed by the client's own token.

A dict rather than a chain of branches because these are four independent sentences with no shared
structure; ``displayed`` is absent because it is the one message that interpolates the deck's name
and the count.
"""


async def set_active_deck(session: AsyncSession, *, deck_id: str) -> SetActiveDeckResult:
    """Point the companion's display at a saved deck.

    The order is load-bearing: the database read happens **first**, and a deck that does not exist
    returns ``deck_not_found`` without the companion being contacted at all (AD-16). The cheap
    :meth:`~src.data.repositories.deck.DeckRepository.get_deck` is used rather than
    ``get_deck_with_cards`` — the only facts needed here are that the deck exists and what it is
    called; the companion fetches the contents itself.

    Never raises. A ``DatabaseError`` becomes ``error`` and everything the companion, the network or
    the discovery file can do is already one of the client's five tokens (FR-12). An unexpected
    exception is deliberately **not** caught: that is a bug, and crashing loudly is this package's
    convention for one.

    Args:
        session: Async database session to read the deck through.
        deck_id: The id of the deck to display (from ``create_deck`` / ``list_decks``).

    Returns:
        A :class:`SetActiveDeckResult`.
    """
    if not await is_database_initialized(session):
        return SetActiveDeckResult(
            status="database_not_initialized",
            deck_id=_truncate_for_echo(deck_id),
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    repo = DeckRepository(session)
    try:
        deck = await repo.get_deck(deck_id)
    except DatabaseError:
        logger.exception("companion_set_active_deck failed reading deck_id=%s", deck_id)
        return SetActiveDeckResult(
            status="error",
            deck_id=_truncate_for_echo(deck_id),
            message="A database error occurred looking up the deck.",
        )

    if deck is None:
        shown_id = _truncate_for_echo(deck_id)
        return SetActiveDeckResult(
            status="deck_not_found",
            deck_id=shown_id,
            message=f"No deck found with id '{shown_id}'. Use `list_decks` to see saved decks.",
        )

    # `deck` is already a detached schema (Deck.model_validate), so nothing below this line
    # touches the session. Release the connection before the outbound HTTP call, which can run
    # up to the leaf's whole-call deadline (10s) — this is the first companion tool whose helper
    # does I/O other than the database, and holding a pooled connection for that long is needless.
    # Closing early is safe: AsyncSession.close() is idempotent, so the caller's own
    # `async with session_factory()` still exits cleanly.
    await session.close()

    shown_name = _truncate_for_echo(deck.name)
    outcome = await _client_set_active_deck(ActiveDeckRequest(deck_id=deck.id))
    if outcome.outcome == "displayed":
        tabs = "tab" if outcome.clients == 1 else "tabs"
        return SetActiveDeckResult(
            status="displayed",
            deck_id=deck.id,
            deck_name=shown_name,
            clients=outcome.clients,
            message=f"The companion is now showing '{shown_name}' in {outcome.clients} {tabs}.",
        )
    return SetActiveDeckResult(
        status=outcome.outcome,
        deck_id=deck.id,
        deck_name=shown_name,
        clients=outcome.clients,
        message=_MESSAGES[outcome.outcome],
    )


class ShowSuggestionsResult(BaseModel):
    """Structured result of ``companion_show_suggestions``.

    The ``status`` values are the leaf client's five wire outcomes and **nothing else**, which is
    the difference between a push tool and the control tool above. ``set_active_deck`` layers three
    more because it reads the deck table before it sends; this one reads nothing — card ids are
    deliberately unvalidated (AD-7) and deck existence is the control tool's business (AD-16) — so
    there is no database to report a fourth kind of failure about. AD-8's set, verbatim.

    **Counts, never contents.** Both numeric fields are facts *about* the push rather than pieces of
    it, which is what lets the result confirm scope without repeating a single card id or reason
    back into the conversation the agent is already holding them in (CM-1, AC 5).

    Attributes:
        status: ``displayed`` (the companion delivered the push to at least one connected browser),
            ``no_clients_connected`` (the companion took it and no tab was listening — a success on
            the wire, not a failure, and never something to re-send), ``app_not_running`` (no
            companion could be proven live; no credential left the process), ``payload_rejected``
            (the companion refused the envelope itself), or ``backend_error`` (the companion is
            there and the push did not land).
        clients: How many connected browsers received the push, when the companion said. ``None`` on
            every status that never reached a receipt, which is deliberately distinguishable from
            ``0``: "nobody told us" and "nobody was watching" are different facts.
        items_pushed: How many suggestions the envelope carried. Reported on **every** status,
            including the ones that never reached the wire, because it describes what was attempted
            rather than what arrived. Zero is a legitimate value, not an error (AD-7).
        message: One short human-facing sentence. Never echoes the payload (CM-1).
    """

    status: Literal[
        "displayed",
        "no_clients_connected",
        "app_not_running",
        "payload_rejected",
        "backend_error",
    ]
    clients: int | None = None
    items_pushed: int
    message: str


def _push_messages(noun: str) -> dict[str, str]:
    """Build the four push-failure sentences for one content noun (16.2's consolidation).

    The four sentences were measured to be pure "…the {noun}…" templates before this builder
    existed: the shipped suggestions and swaps tables differed **only** in the word naming the
    content, so one parameterized builder replaces two verbatim clones without changing a byte of
    either — ``TestEveryPushToolSpeaksItsOwnNoun`` in ``test_companion_tool.py`` pins the
    sentences as literals and each table to its own noun. A kind whose sentences ever needed a
    different *shape* would stop calling this and write its own table, which is exactly what the
    pre-consolidation docstrings said about sharing.

    None of these tells the agent what to do about its *reply* — only what happened to the glass.
    The companion is a second channel and never a replacement for the conversational one (NG5), so
    a sentence here that said "present them in chat instead" would be describing a fallback rather
    than the normal behaviour it never stopped being.

    ``displayed`` is absent because it is the one message that interpolates the counts — the
    success sentence varies per kind and is passed to :func:`_execute_push` by its caller.

    Args:
        noun: The plural word for the pushed content — "suggestions", "swaps", "tiers", "groups".

    Returns:
        The wording for every push outcome that is not a plain success, keyed by the client's own
        token.
    """
    return {
        "no_clients_connected": (
            f"The companion took the {noun}, but no browser tab is open to see them — open the "
            "URL the companion printed when it started."
        ),
        "app_not_running": (
            f"The companion app isn't running, so the {noun} have nowhere to appear. Offer to "
            "open it — companion_status returns the launch command, and the companion skill "
            "walks through it — the content is in chat regardless."
        ),
        "payload_rejected": (
            f"The companion refused the {noun}, so none of them were displayed. The content is in "
            "chat regardless."
        ),
        "backend_error": (
            f"The companion is running but the {noun} didn't land. Try again — the content is in "
            "chat regardless."
        ),
    }


_PUSH_MESSAGES = _push_messages("suggestions")
"""The suggestions wording — :func:`_push_messages` with the noun the shipped table carried.

Kept as a module-level table rather than rebuilt per call so the sentences stay inspectable where
the pre-consolidation dict lived — ``TestEveryPushToolSpeaksItsOwnNoun`` in
``test_companion_tool.py`` reads all three tables by name and pins this one's four sentences
byte-for-byte, so a builder edit that moved a shipped byte fails there rather than shipping.
"""


async def show_suggestions(*, payload: SuggestionsPayload) -> ShowSuggestionsResult:
    """Put a list of suggested cards on the companion's glass (FR-08, AD-8).

    Mints the envelope and hands it to :func:`~src.companion.client.push_event`, and that is the
    whole of it. There is no database read, no id resolution and no cap enforcement here: the caps
    are the payload model's (AD-7, and FastMCP applies them at the tool boundary before this
    function is entered), and the ids are Scryfall's, which this layer has no business second-
    guessing. What arrives is what is sent — **order included**, because payload order is render
    order and nothing here sorts, dedupes or trims.

    **An empty ``items`` list is posted, not short-circuited.** "I looked and found nothing" is a
    thing the agent is allowed to say on the glass (AD-7), and a helper that quietly skipped the
    push would make the honest answer unexpressible.

    The envelope's ``id`` is a fresh UUID4 per call — opaque identity and dedupe, never ordering
    (AD-6) — and ``ts`` is timezone-aware because the wire refuses a naive one. No title is
    injected when the payload omits one: the fallback header belongs to the reader, and a
    tool-supplied title would make "agent-authored" false.

    Never raises. Everything the discovery file, the network or the companion can do is already one
    of the client's five tokens (FR-12), and there is no database call to convert. An unexpected
    exception is deliberately **not** caught: that is a bug, and crashing loudly is this package's
    convention for one.

    Args:
        payload: The suggestions to display, already validated by the contract model.

    Returns:
        A :class:`ShowSuggestionsResult`.
    """
    event = SuggestionsEvent(
        kind="suggestions",
        id=str(uuid4()),
        ts=datetime.now(UTC),
        payload=payload,
    )
    items_pushed = len(payload.items)
    cards = "card" if items_pushed == 1 else "cards"
    return await _execute_push(
        event,
        items_pushed=items_pushed,
        result_cls=ShowSuggestionsResult,
        messages=_PUSH_MESSAGES,
        shown=f"{items_pushed} suggested {cards}",
    )


class ShowSwapsResult(BaseModel):
    """Structured result of ``companion_show_swaps``.

    A structural clone of :class:`ShowSuggestionsResult`, and the sameness is the contract: this
    is the second *push* tool, so its ``status`` values are the leaf client's five wire outcomes
    and **nothing else** (AD-8). It reads no database — card ids are deliberately unvalidated
    (AD-7) and deck existence is the control tool's business (AD-16) — so there is no fourth kind
    of failure to layer on top.

    **Counts, never contents** (CM-1, AC 5): both numeric fields describe the push without
    repeating one card id or rationale back into the conversation the agent is already holding.

    Attributes:
        status: ``displayed`` (the companion delivered the push to at least one connected
            browser), ``no_clients_connected`` (the companion took it and no tab was listening — a
            wire success, never something to re-send), ``app_not_running`` (no companion could be
            proven live; no credential left the process), ``payload_rejected`` (the companion
            refused the envelope itself), or ``backend_error`` (the companion is there and the
            push did not land).
        clients: How many connected browsers received the push, when the companion said. ``None``
            on every status that never reached a receipt — distinguishable from ``0`` on purpose.
        items_pushed: How many **swap pairs** the envelope carried — one out-card/in-card trade is
            one item, never two. Reported on every status, because it describes what was attempted
            rather than what arrived. Zero is a legitimate value, not an error (AD-7).
        message: One short human-facing sentence. Never echoes the payload (CM-1).
    """

    status: Literal[
        "displayed",
        "no_clients_connected",
        "app_not_running",
        "payload_rejected",
        "backend_error",
    ]
    clients: int | None = None
    items_pushed: int
    message: str


_SWAPS_PUSH_MESSAGES = _push_messages("swaps")
"""The swaps wording — :func:`_push_messages` with this tool's noun.

Before 16.2 this was a verbatim clone of the suggestions table with one word changed, and its
docstring predicted a shared table "would either misname this tool's content or force both tools
through a blander sentence neither asked for". The builder answers both horns: each kind still
names its own content, and no sentence got blander — the templates are the shipped sentences,
byte for byte, with the noun as the one slot they ever differed in.
"""


async def show_swaps(*, payload: SwapsPayload) -> ShowSwapsResult:
    """Put a list of proposed card swaps on the companion's glass (FR-08, AD-8).

    The push-tool shape, second application — :func:`show_suggestions` is the pattern source and
    every ruling there carries over unchanged: no database read, no id resolution, no cap
    enforcement here (the caps are the payload model's, applied by FastMCP at the tool boundary),
    and what arrives is what is sent — **order included**, because payload order is render order
    and nothing here sorts, dedupes or trims.

    **An empty ``items`` list is posted, not short-circuited** (AD-7): "I looked and found no
    trade worth proposing" is a thing the agent is allowed to say on the glass.

    The envelope's ``id`` is a fresh UUID4 per call — opaque identity and dedupe, never ordering
    (AD-6) — and ``ts`` is timezone-aware because the wire refuses a naive one. No title is
    injected when the payload omits one: the fallback header belongs to the reader.

    Never raises. Everything the discovery file, the network or the companion can do is already
    one of the client's five tokens (FR-12). An unexpected exception is deliberately **not**
    caught: that is a bug, and crashing loudly is this package's convention for one.

    Args:
        payload: The swaps to display, already validated by the contract model.

    Returns:
        A :class:`ShowSwapsResult`.
    """
    event = SwapsEvent(
        kind="swaps",
        id=str(uuid4()),
        ts=datetime.now(UTC),
        payload=payload,
    )
    items_pushed = len(payload.items)
    swaps = "swap" if items_pushed == 1 else "swaps"
    return await _execute_push(
        event,
        items_pushed=items_pushed,
        result_cls=ShowSwapsResult,
        messages=_SWAPS_PUSH_MESSAGES,
        shown=f"{items_pushed} proposed {swaps}",
    )


class ShowTierListResult(BaseModel):
    """Structured result of ``companion_show_tier_list``.

    The third *push* tool result, field-identical to :class:`ShowSuggestionsResult` and
    :class:`ShowSwapsResult` on purpose: its ``status`` values are the leaf client's five wire
    outcomes and **nothing else** (AD-8). It reads no database — card ids are deliberately
    unvalidated (AD-7) and deck existence is the control tool's business (AD-16) — so there is no
    fourth kind of failure to layer on top. Four distinct classes rather than one shared model
    because these docstrings are wire-visible: each tool's result documents its own count noun.

    **Counts, never contents** (CM-1, AC 5): both numeric fields describe the push without
    repeating one card id, tier name or note back into the conversation the agent is already
    holding.

    Attributes:
        status: ``displayed`` (the companion delivered the push to at least one connected
            browser), ``no_clients_connected`` (the companion took it and no tab was listening — a
            wire success, never something to re-send), ``app_not_running`` (no companion could be
            proven live; no credential left the process), ``payload_rejected`` (the companion
            refused the envelope itself), or ``backend_error`` (the companion is there and the
            push did not land).
        clients: How many connected browsers received the push, when the companion said. ``None``
            on every status that never reached a receipt — distinguishable from ``0`` on purpose.
        items_pushed: How many **tiers** the envelope carried — ``len(payload.items)``, never a
            count of the cards inside them: a tier holding sixty cards is one item. Reported on
            every status, because it describes what was attempted rather than what arrived. Zero
            is a legitimate value, not an error (AD-7).
        message: One short human-facing sentence. Never echoes the payload (CM-1).
    """

    status: Literal[
        "displayed",
        "no_clients_connected",
        "app_not_running",
        "payload_rejected",
        "backend_error",
    ]
    clients: int | None = None
    items_pushed: int
    message: str


_TIER_LIST_PUSH_MESSAGES = _push_messages("tiers")
"""The tier-list wording — :func:`_push_messages` with this tool's noun.

"Tiers" rather than "tier list" because the templates conjugate plural ("…have nowhere to
appear", "…none of them were displayed"), and the tiers are what the push carries — the same
grain ``items_pushed`` counts.
"""


async def _execute_push[
    ResultT: (ShowSuggestionsResult, ShowSwapsResult, ShowTierListResult, ShowGroupsResult)
](
    event: SuggestionsEvent | SwapsEvent | TierListEvent | GroupsEvent,
    *,
    items_pushed: int,
    result_cls: type[ResultT],
    messages: dict[str, str],
    shown: str,
) -> ResultT:
    """Hand one already-minted envelope to the leaf and fold the outcome into a result (16.2).

    The shared back half of every push tool — extracted because the helpers' bodies (three at
    the extraction, four since 16.3) differed in exactly five tokens (event class and kind,
    payload type, result class, count-noun pluralizer, success sentence), and the first four
    arrive here as arguments while the fifth is ``shown``, preformatted by the caller because
    ``items_pushed`` is caller-computed: what an "item" is (a suggestion, a pair, a tier, a
    group) is the one real semantic difference between kinds.

    Everything the pre-consolidation bodies guaranteed still holds, structurally: one call is one
    push (nothing here retries), the envelope crosses to the leaf untouched, and never raising is
    inherited from the client's own closed outcome vocabulary (FR-12). An unexpected exception is
    deliberately **not** caught: that is a bug, and crashing loudly is this package's convention
    for one.

    Args:
        event: The envelope, already minted by the caller — id, ts and payload included.
        items_pushed: How many items the caller counted in its own grain.
        result_cls: Which of the four field-identical result models to mint.
        messages: The kind's failure sentences, from :func:`_push_messages`.
        shown: The success sentence's subject — e.g. ``"2 suggested cards"``, ``"3 tiers"``.

    Returns:
        An instance of *result_cls*.
    """
    outcome = await _client_push_event(event)
    if outcome.outcome == "displayed":
        tabs = "tab" if outcome.clients == 1 else "tabs"
        return result_cls(
            status="displayed",
            clients=outcome.clients,
            items_pushed=items_pushed,
            message=f"The companion is showing {shown} in {outcome.clients} {tabs}.",
        )
    return result_cls(
        status=outcome.outcome,
        clients=outcome.clients,
        items_pushed=items_pushed,
        message=messages[outcome.outcome],
    )


async def show_tier_list(*, payload: TierListPayload) -> ShowTierListResult:
    """Put a tier list on the companion's glass (FR-08, AD-8).

    The push-tool shape, third application, on the shared path 16.2 consolidated — every ruling
    from :func:`show_suggestions` carries over unchanged: no database read, no id resolution, no
    cap enforcement here (the caps are the payload model's, applied by FastMCP at the tool
    boundary), and what arrives is what is sent — **order included**, because payload order is
    render order and nothing here sorts, dedupes or trims. Two tiers sharing a letter are a legal
    payload; the agent's ordering is the agent's argument.

    **``items_pushed`` counts tiers, never cards** — ``len(payload.items)``, the same grain the
    payload's own cap (12) is written in. A tier carrying sixty card ids is one item, exactly as
    one out/in trade is one swap.

    **An empty ``items`` list is posted, not short-circuited** (AD-7): "I ranked and found
    nothing worth tiering" is a thing the agent is allowed to say on the glass.

    The envelope's ``id`` is a fresh UUID4 per call — opaque identity and dedupe, never ordering
    (AD-6) — and ``ts`` is timezone-aware because the wire refuses a naive one. No title is
    injected when the payload omits one: the fallback header belongs to the reader
    (``DEFAULT_TITLE_BY_KIND`` gives it "Tier list"), and a tool-supplied title would make
    "agent-authored" false.

    Never raises. Everything the discovery file, the network or the companion can do is already
    one of the client's five tokens (FR-12). An unexpected exception is deliberately **not**
    caught: that is a bug, and crashing loudly is this package's convention for one.

    Args:
        payload: The tiers to display, already validated by the contract model.

    Returns:
        A :class:`ShowTierListResult`.
    """
    event = TierListEvent(
        kind="tier_list",
        id=str(uuid4()),
        ts=datetime.now(UTC),
        payload=payload,
    )
    items_pushed = len(payload.items)
    tiers = "tier" if items_pushed == 1 else "tiers"
    return await _execute_push(
        event,
        items_pushed=items_pushed,
        result_cls=ShowTierListResult,
        messages=_TIER_LIST_PUSH_MESSAGES,
        shown=f"{items_pushed} {tiers}",
    )


class ShowGroupsResult(BaseModel):
    """Structured result of ``companion_show_groups``.

    The fourth *push* tool result, field-identical to :class:`ShowSuggestionsResult`,
    :class:`ShowSwapsResult` and :class:`ShowTierListResult` on purpose: its ``status`` values
    are the leaf client's five wire outcomes and **nothing else** (AD-8). It reads no database —
    card ids are deliberately unvalidated (AD-7) and deck existence is the control tool's
    business (AD-16) — so there is no fourth kind of failure to layer on top. Four distinct
    classes rather than one shared model because these docstrings are wire-visible: each tool's
    result documents its own count noun.

    **Counts, never contents** (CM-1, AC 5): both numeric fields describe the push without
    repeating one card id, group title or rationale back into the conversation the agent is
    already holding.

    Attributes:
        status: ``displayed`` (the companion delivered the push to at least one connected
            browser), ``no_clients_connected`` (the companion took it and no tab was listening — a
            wire success, never something to re-send), ``app_not_running`` (no companion could be
            proven live; no credential left the process), ``payload_rejected`` (the companion
            refused the envelope itself), or ``backend_error`` (the companion is there and the
            push did not land).
        clients: How many connected browsers received the push, when the companion said. ``None``
            on every status that never reached a receipt — distinguishable from ``0`` on purpose.
        items_pushed: How many **groups** the envelope carried — ``len(payload.items)``, never a
            count of the cards inside them: a group holding sixty cards is one item. Reported on
            every status, because it describes what was attempted rather than what arrived. Zero
            is a legitimate value, not an error (AD-7).
        message: One short human-facing sentence. Never echoes the payload (CM-1).
    """

    status: Literal[
        "displayed",
        "no_clients_connected",
        "app_not_running",
        "payload_rejected",
        "backend_error",
    ]
    clients: int | None = None
    items_pushed: int
    message: str


_GROUPS_PUSH_MESSAGES = _push_messages("groups")
"""The groups wording — :func:`_push_messages` with this tool's noun.

"Groups" rather than "card groups" because the templates conjugate plural ("…have nowhere to
appear", "…none of them were displayed"), and the groups are what the push carries — the same
grain ``items_pushed`` counts.
"""


async def show_groups(*, payload: GroupsPayload) -> ShowGroupsResult:
    """Put titled card groups on the companion's glass (FR-08, AD-8).

    The push-tool shape, fourth application, on the shared path 16.2 consolidated — every
    ruling from :func:`show_suggestions` carries over unchanged: no database read, no id
    resolution, no cap enforcement here (the caps are the payload model's, applied by FastMCP
    at the tool boundary), and what arrives is what is sent — **order included**, because
    payload order is render order and nothing here sorts, dedupes or merges. A group may name
    cards the active deck does not run; grouping is an argument about cards, not an inventory
    of the deck.

    **``items_pushed`` counts groups, never cards** — ``len(payload.items)``, the same grain
    the payload's own cap (12) is written in. A group carrying sixty card ids is one item,
    exactly as one tier carrying sixty is.

    **An empty ``items`` list is posted, not short-circuited** (AD-7): "I looked and found no
    grouping worth drawing" is a thing the agent is allowed to say on the glass. An empty
    ``card_ids`` list inside a group is legal too — the view skips it.

    The envelope's ``id`` is a fresh UUID4 per call — opaque identity and dedupe, never
    ordering (AD-6) — and ``ts`` is timezone-aware because the wire refuses a naive one. No
    title is injected when the payload omits one: the fallback header belongs to the reader
    (``DEFAULT_TITLE_BY_KIND`` gives it "Groups"), and a tool-supplied title would make
    "agent-authored" false.

    Never raises. Everything the discovery file, the network or the companion can do is already
    one of the client's five tokens (FR-12). An unexpected exception is deliberately **not**
    caught: that is a bug, and crashing loudly is this package's convention for one.

    Args:
        payload: The groups to display, already validated by the contract model.

    Returns:
        A :class:`ShowGroupsResult`.
    """
    event = GroupsEvent(
        kind="groups",
        id=str(uuid4()),
        ts=datetime.now(UTC),
        payload=payload,
    )
    items_pushed = len(payload.items)
    groups = "group" if items_pushed == 1 else "groups"
    return await _execute_push(
        event,
        items_pushed=items_pushed,
        result_cls=ShowGroupsResult,
        messages=_GROUPS_PUSH_MESSAGES,
        shown=f"{items_pushed} {groups}",
    )


_INSTALL_ROOT = Path(__file__).resolve().parents[3]
"""The uv project directory the companion is launched from, derived from this file's own location.

``src/mcp_server/tools/companion.py`` is three packages below the project root, so ``parents[3]``
is the directory holding ``pyproject.toml`` — the repo checkout for a clone, and
``<plugin>/server`` for a plugin install, where the README's ``--directory`` anchor already
points. Derived from ``__file__`` rather than ``${CLAUDE_PLUGIN_ROOT}`` because nothing inside
``src/`` may depend on the host's environment (17.4, Never), and the file's own path is the one
fact true on both install shapes.
"""


def launch_command() -> str:
    """The exact shell command that starts the companion and opens a browser tab on it (17.4).

    The ``--directory`` form so the same string works from any working directory and for a plugin
    install (deferred-work.md:6516); ``--open`` so the page appears without a second step. The
    companion's own process opens the browser — the MCP server never spawns it (AD-15); the agent
    runs this in a background shell it owns.

    Returns:
        One command line, quoted for a shell.
    """
    return f'uv run --directory "{_INSTALL_ROOT}" artificial-planeswalker companion --open'


class CompanionStatusResult(BaseModel):
    """Structured result of ``companion_status`` — read-only, and the agent's route to the glass.

    The one companion tool that carries no content and sends no token: it answers "is a companion
    running, is anyone looking at it, and how do I start one?" so the agent can *open* the
    companion rather than telling the user to. Liveness is proven the same way every push tool
    proves it — :func:`~src.companion.client.live_instance`'s instance-id match against the
    discovery file — and nothing weaker: a stale file, a foreign server on the port, or a
    mismatched id all read as ``not_running``. The token the discovery file carries is never read
    into this result.

    Attributes:
        status: ``running`` (a companion matching the discovery file is answering) or
            ``not_running`` (nothing provable is). ``error`` is reserved and never minted today —
            every way the probe can fail is ``not_running`` by the client's own contract.
        url: The running companion's base URL, or ``None`` when there is none to name.
        clients: How many browser tabs are connected, when the companion said (17.4's ``/health``
            field). ``None`` when not running, or when an older companion answered without it.
        launch_command: The exact command that starts the companion and opens a tab on it. Set on
            **every** status — on ``running`` with no tab open, the same command's already-running
            branch opens a tab on the live instance and exits ``0``, which is the first thing to
            try; handing the user ``url`` is the fallback when no browser can open. The agent may
            add ``--port N`` when the user asked for a specific port; nothing else about it should
            change.
        message: One short sentence telling the agent what to do next.
    """

    status: Literal["running", "not_running", "error"]
    url: str | None = None
    clients: int | None = None
    launch_command: str
    message: str


async def companion_status() -> CompanionStatusResult:
    """Report whether the companion is running, who is watching, and how to start it (17.4).

    Read-only. :func:`~src.companion.client.live_instance` does the whole proof — discovery file,
    probe, identity match — and its record is used only for the *port*; the token beside it is
    never read here. One more :func:`~src.companion.client.probe_health` then reads the tab count,
    because ``live_instance`` hands back the record rather than the health body. Two probes rather
    than a widened client return shape: the client's contract is "a proven record", and changing
    it for one reader would ripple into every caller the push path has.

    The second probe is held to the same proof as the first: no body, or a body whose
    ``instance_id`` is not the proven record's, is ``not_running`` — a companion that died between
    the two probes, or a foreign server that took the port in that window, is never reported as
    running. The tab count is three-valued and the message never lies about which case it is in:
    a positive count names the tabs, an honest ``0`` says no tab is open, and an absent or
    negative ``clients`` (an older companion, or a malformed body) reads as ``None`` — "count
    unknown", never "no browser tab is open" and never a negative number.

    Never raises. Both client calls promise the same, and a stale discovery file is the ordinary
    ``not_running`` outcome, not an error (FR-12).

    Returns:
        A :class:`CompanionStatusResult`.
    """
    command = launch_command()
    not_running = CompanionStatusResult(
        status="not_running",
        launch_command=command,
        message=(
            "The companion isn't running. Offer to open it for the user: run launch_command in "
            "a background shell, wait for its URL line, and a browser tab opens on it."
        ),
    )
    live = await _client_live_instance()
    if live is None:
        return not_running
    health = await _client_probe_health(live.port)
    if health is None or health.instance_id != live.instance_id:
        logger.debug(
            "Port %d stopped answering as instance %s between probes; treating as app not running",
            live.port,
            live.instance_id,
        )
        return not_running
    url = _client_base_url(live.port)
    clients = health.clients if health.clients is not None and health.clients >= 0 else None
    if clients is not None and clients > 0:
        tabs = "tab" if clients == 1 else "tabs"
        message = f"The companion is running at {url} with {clients} {tabs} open — nothing to do."
    elif clients == 0:
        message = (
            f"The companion is running at {url} but no browser tab is open. Run launch_command — "
            f"its --open opens a tab on the running instance; give the user {url} only if the "
            "browser can't open."
        )
    else:
        message = (
            f"The companion is running at {url}, but this companion is too old to report its "
            f"tab count — a tab may already be open. Give the user {url} rather than opening a "
            "possibly-duplicate tab."
        )
    return CompanionStatusResult(
        status="running",
        url=url,
        clients=clients,
        launch_command=command,
        message=message,
    )

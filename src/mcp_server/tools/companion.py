"""The companion control tools — what the agent tells the glass to do (FR-07, AD-8, AD-16).

The MCP side of the companion feature: a tool here validates against the database, delegates the
wire work to the leaf client (:mod:`src.companion.client`), and turns the client's closed outcome
vocabulary into the ``status`` convention every other tool in this package already uses.

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
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from src.companion.client import set_active_deck as _client_set_active_deck
from src.companion.contracts import ActiveDeckRequest
from src.data.database import is_database_initialized
from src.data.repositories.deck import DeckRepository
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

logger = logging.getLogger(__name__)

_DECK_ID_ECHO_LIMIT = 100
"""Bounds the ``deck_id`` echoed back on a miss — a *display* bound, distinct from
``ActiveDeckRequest``'s 256-char *storage* bound (``contracts.py``), because a miss echoes the id
twice (the ``deck_id`` field and the ``message`` sentence): 256 chars doubled would already blow the
~200-token budget on its own. All 40 ids in the shipped database are 36-character uuids (measured
2026-08-01, same measurement ``_MAX_DECK_ID_LENGTH`` cites); 100 is roughly 3x that, wide enough for
a future id scheme, narrow enough that a caller-supplied id beyond it — which can never match a real
deck anyway — cannot make a ``deck_not_found`` result blow the CM-1 budget (AC 5).
"""


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
        deck_name: The deck's name, when the deck was found — lets the agent confirm by name rather
            than by uuid.
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
        "The companion app isn't running, so there is nothing to display on. Start it, then ask "
        "me again."
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
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    repo = DeckRepository(session)
    try:
        deck = await repo.get_deck(deck_id)
    except DatabaseError:
        logger.exception("companion_set_active_deck failed reading deck_id=%s", deck_id)
        return SetActiveDeckResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred looking up the deck.",
        )

    if deck is None:
        shown_id = (
            deck_id if len(deck_id) <= _DECK_ID_ECHO_LIMIT else deck_id[:_DECK_ID_ECHO_LIMIT] + "…"
        )
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

    outcome = await _client_set_active_deck(ActiveDeckRequest(deck_id=deck.id))
    if outcome.outcome == "displayed":
        tabs = "tab" if outcome.clients == 1 else "tabs"
        return SetActiveDeckResult(
            status="displayed",
            deck_id=deck.id,
            deck_name=deck.name,
            clients=outcome.clients,
            message=f"The companion is now showing '{deck.name}' in {outcome.clients} {tabs}.",
        )
    return SetActiveDeckResult(
        status=outcome.outcome,
        deck_id=deck.id,
        deck_name=deck.name,
        clients=outcome.clients,
        message=_MESSAGES[outcome.outcome],
    )

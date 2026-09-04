"""The companion's ephemeral in-memory state: active deck, WebSocket tickets, connections.

Everything here is ephemeral by contract (CM-3, FR-07): a restart reports no active deck, no tickets
and no connections, so nothing reaches disk, a cache or the discovery file. The backend owns this
state, not the MCP server (AD-5): the MCP tools are stateless and call the HTTP endpoints, so two
agent sessions talking to one companion see one active deck. The ticket store lives here rather than
in :mod:`~src.companion.app.security` because a single-use consume is a compare-and-set over the
storage, and ``security.py``'s proven structural property is that it stores nothing.

No holder takes a lock: setting the slot is one assignment, :meth:`TicketStore.consume` is one
synchronous ``dict.pop`` with no ``await`` between read and delete, and every registry operation is
one synchronous container mutation, so no second caller can observe a half-applied change. Splitting
a pop into ``get`` plus ``del``, awaiting inside a method, or a thread pool would break that.
"""

import math
import secrets
import time
from collections.abc import Callable
from typing import Protocol

from fastapi import FastAPI


class ActiveDeckSlot:
    """The in-memory slot naming the deck the UI is currently showing (FR-07).

    A "slot" because the wire model :class:`~src.companion.contracts.ActiveDeck` owns the other
    name. Nothing validates that the deck exists (AD-16): the MCP tool reports ``deck_not_found``.
    """

    def __init__(self) -> None:
        self._deck_id: str | None = None

    @property
    def deck_id(self) -> str | None:
        """The deck currently displayed, or ``None``; :meth:`set` is the single write site."""
        return self._deck_id

    def set(self, deck_id: str) -> None:
        """Point the display at *deck_id*, replacing whatever was there (idempotent, hence ``PUT``).

        Args:
            deck_id: Stored verbatim: a deck id has no declared shape and is reported back as given.
        """
        self._deck_id = deck_id


def active_deck(app: FastAPI) -> ActiveDeckSlot | None:
    """Return the :class:`ActiveDeckSlot` for *app*, or ``None`` if the lifespan never ran."""
    holder: ActiveDeckSlot | None = getattr(app.state, "active_deck", None)
    return holder


TICKET_TTL_SECONDS = 30.0
"""How long a minted ticket stays consumable, in seconds: AD-5's "single-use with a 30 s TTL".

It covers the milliseconds between ``GET /api/session`` and the browser's next upgrade, with ample
room for a stalled tab, and is short enough that a leaked ticket is worthless.
"""

MAX_TICKETS = 256
"""The hard bound on resident tickets, evicted earliest-expiry-first.

The mint is unauthenticated, so unbounded-callable; a browser mints at most six tickets per
30 s reconnect window, so 256 caps the map at a few tens of kilobytes. Eviction costs a legitimate
browser one failed upgrade and a re-mint; refusing to mint would hand a flooding page a permanent
denial. Not ``60`` or ``15``: ``test_routes_format_check.py`` bans those literals in the package.
"""

_TICKET_ENTROPY_BYTES = 32
"""Random bytes per ticket; its own minter call, as AD-5 bars sharing code with the agent token."""


class TicketStore:
    """The map of live WebSocket tickets, and the single-use consume over it (AD-5, NFR-01).

    CORS does not protect a WebSocket upgrade, so the browser must first read a ticket from
    same-origin ``GET /api/session``; a page on another origin can burn tickets but never learn one.
    A ticket is destroyed at :meth:`consume` whether or not the handshake succeeds; the TTL only
    clears tickets never presented. Nothing is persisted (CM-3) and the store shares no code path
    with the agent token (``test_routes_active_deck.py`` asserts it).

    Args:
        ttl: How long a minted ticket stays consumable, in seconds.
        max_tickets: The hard bound on resident tickets.
        clock: Monotonic time source, injected so the TTL is tested at zero wall clock.

    Raises:
        ValueError: ``ttl`` is not positive and finite, or ``max_tickets`` is below one.

    Example:
        >>> store = TicketStore()
        >>> issued = store.mint()
        >>> store.consume(issued), store.consume(issued)
        (True, False)
    """

    def __init__(
        self,
        *,
        ttl: float = TICKET_TTL_SECONDS,
        max_tickets: int = MAX_TICKETS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # nan compares False against everything, so a sign check alone would let it through.
        if not math.isfinite(ttl) or ttl <= 0:
            raise ValueError(f"ttl must be positive and finite, got {ttl}")
        if max_tickets < 1:
            raise ValueError(f"max_tickets must be at least 1, got {max_tickets}")
        self._ttl = ttl
        self._max_tickets = max_tickets
        self._clock = clock
        # Value is the deadline, not the issue time, so `consume` compares one number against one.
        self._deadlines: dict[str, float] = {}

    @property
    def resident_count(self) -> int:
        """Tickets resident now, including expired ones not yet pruned by :meth:`mint`."""
        return len(self._deadlines)

    def mint(self) -> str:
        """Issue a fresh, distinct ticket, valid for the TTL and consumable exactly once.

        Expired tickets are pruned here, not on read, or the map would fill with dead ones.
        """
        now = self._clock()
        self._forget_expired(now)
        if len(self._deadlines) >= self._max_tickets:
            self._evict_earliest_deadline()
        # Never `discovery.mint_token()`: AD-5 requires the ticket and the token to share no code.
        issued = secrets.token_urlsafe(_TICKET_ENTROPY_BYTES)
        self._deadlines[issued] = now + self._ttl
        return issued

    def consume(self, ticket: str) -> bool:
        """Destroy *ticket* and report whether it was live at the moment it was destroyed.

        Every path pops, so a rejected ticket cannot be retried into a different answer; unknown,
        consumed and expired tickets are refused identically. No lock: see the module docstring.
        """
        now = self._clock()
        deadline = self._deadlines.pop(ticket, None)
        return deadline is not None and now < deadline

    def _forget_expired(self, now: float) -> None:
        """Drop every ticket whose deadline has passed; a ticket has no history worth retaining."""
        expired = [issued for issued, deadline in self._deadlines.items() if now >= deadline]
        for issued in expired:
            del self._deadlines[issued]

    def _evict_earliest_deadline(self) -> None:
        """Drop the ticket closest to expiring, keyed on deadline so mixed lifetimes stay right."""
        earliest = min(self._deadlines, key=lambda issued: self._deadlines[issued])
        del self._deadlines[earliest]


def ticket_store(app: FastAPI) -> TicketStore | None:
    """Return the :class:`TicketStore` for *app*, or ``None`` if the lifespan never ran."""
    holder: TicketStore | None = getattr(app.state, "ticket_store", None)
    return holder


class Connection(Protocol):
    """What the fan-out needs a client to be; structural so this module imports no web framework."""

    @property
    def client_state(self) -> object:
        """The transport's connection state, uninterpreted here (hence ``object``)."""

    async def send_text(self, data: str) -> None:
        """Write one text frame."""

    async def close(self, code: int = 1000) -> None:
        """Close the connection with *code*."""


class ConnectionRegistry:
    """The set of accepted WebSockets a broadcast fans out to (FR-06, AD-8, CM-3).

    Membership only: :mod:`src.companion.app.ws` accepts, sends and closes. Unbounded, because every
    entry cost a ticket minted under :data:`MAX_TICKETS` and evicting one would close a legitimate
    tab. Nothing is persisted (CM-3) and nothing here identifies a client.
    """

    def __init__(self) -> None:
        # A set: `discard` must be idempotent and connections are hashable by identity.
        self._connections: set[Connection] = set()

    @property
    def connected_count(self) -> int:
        """Registered clients, not necessarily reachable; the ingest route reports delivered."""
        return len(self._connections)

    def add(self, connection: Connection) -> None:
        """Register *connection*, idempotently, once ``accept()`` has succeeded."""
        self._connections.add(connection)

    def discard(self, connection: Connection) -> None:
        """Unregister *connection*, silently on a miss: a dying tab is dropped twice by design."""
        self._connections.discard(connection)

    def snapshot(self) -> tuple[Connection, ...]:
        """Return an unordered tuple copy: the fan-out discards failed sockets while walking it."""
        return tuple(self._connections)


def connection_registry(app: FastAPI) -> ConnectionRegistry | None:
    """Return the :class:`ConnectionRegistry` for *app*, or ``None`` if the lifespan never ran."""
    holder: ConnectionRegistry | None = getattr(app.state, "connections", None)
    return holder

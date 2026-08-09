"""The companion's ephemeral in-memory state — the display, and the tickets (CM-3, FR-07, AD-5).

**The first state this backend owns.** Everything served before c3-4 was a projection of
``cards.db`` — ask twice, get the same answer, because the answer was never ours. The active deck is
different: it is a slot in *this process's* memory, and its whole contract is that it is
**ephemeral**. A restart reports none (FR-07). That is not a limitation to work around; it is the
specified behaviour, and it is why nothing here is written to disk, cached, or published in the
discovery file.

**Why the state lives here and not in the MCP server.** The spine's inherited-constraints table and
PRD CM-3 both rule that the *backend* owns the active deck. The MCP tools are stateless and
self-contained (project-context D5): ``companion_set_active_deck`` (c6-2) calls the HTTP endpoint
and keeps nothing, so two agent sessions talking to one companion see one active deck rather than
two disagreeing ones. ``tests/unit/companion/test_routes_active_deck.py`` asserts the MCP side
stays clean rather than trusting this paragraph.

**Why this module rather than a bare ``app.state.active_deck_id``.** The Structural Seed names it:
``app/state.py # active deck, connections, tickets — in memory (AD-5)``. c5-2's WebSocket tickets
landed here (:class:`TicketStore`) and c5-4's connection registry joined them
(:class:`ConnectionRegistry`), rather than inventing a third home, and keeping display state out of
``main.py`` leaves that module about identity and wiring. All three holders follow the shipped
convention exactly — an inert object the lifespan creates, reached through one accessor
(:func:`active_deck`, :func:`ticket_store`, :func:`connection_registry`, mirroring
:func:`src.companion.app.deps.database` and :func:`src.companion.app.main.bound_port`). The seed's
three nouns are now three objects in this file, and the module map's prediction is spent.

**The ticket store is here rather than in** :mod:`~src.companion.app.security` **(c5-2, Q3, Brad
2026-08-08), and the two modules disagreed in shipped prose until this story.** The spine's module
map splits storage from mint/consume — ``state.py # … tickets — in memory`` beside
``security.py # Host validation, token, ticket mint/consume`` — and a single-use ``consume`` is a
compare-and-set **over the storage**, so the split cannot survive contact: whichever module holds
the dict holds the consume. ``security.py``'s single *proven* structural property is that it stores
nothing (``test_routes_active_deck.py`` AST-walks it for any module-level mutable container, probed
against four planted violations), and that is the strongest evidence AD-5 has in the package.
Putting a mutable ticket map behind it — even as an instance — would spend it. So the store lives
here, and ``security.py``'s claim to it was corrected in the same commit.

**No lock, deliberately — do not cargo-cult** :class:`~src.companion.app.deps.Database`'s. That
class holds one because engine creation is a multi-step check-then-assign whose next ``await`` would
reintroduce silent double-creation. Setting a ``str | None`` is a **single assignment with no
read-modify-write and no interleaving point** on single-threaded asyncio: two concurrent writes
produce one of the two values, which is exactly what any lock would also produce. A lock here would
be defence against nothing, and would read to the next author as though a race existed.

**c5-2 is the story that was supposed to earn one, and it does not — the reason is stated rather
than omitted (AC 18).** The paragraph above named "a compare-and-set, a write that consults the old
value" as the change that earns a lock, and :meth:`TicketStore.consume` is exactly that: it must
read a ticket and destroy it, and two callers presenting the same ticket must not both win. The
lock is still unnecessary, because the compare-and-set is spelled as **one** ``dict.pop`` inside a
**synchronous** method on the single-threaded event loop: there is no ``await`` between the read
and the delete and therefore no interleaving point at which a second caller could observe the
ticket still present. That — the absence of a suspension point, not any bytecode-atomicity claim
about ``pop`` itself — is the whole argument, and it is the one that stays checkable against a
future change rather than against an interpreter version. Two concurrent
consumes of one ticket are two ``pop`` calls: the first returns the expiry, the second returns
``None``. That is precisely what a lock would produce, at the cost of making :meth:`consume`
awaitable and pulling ``async`` into c5-3's handshake path for nothing.

**c5-3 made the call and the argument survived contact with it.** The consume's one production
caller is :func:`src.companion.app.ws._handshake_is_authorised`, which is a **plain** ``def``
holding the entire handshake decision — read ``Origin``, evaluate it, reach the store, pop. A
plain ``def`` cannot contain an ``await``, so the no-suspension-point property is enforced by the
language rather than by the paragraph below, and reintroducing one means changing that ``def`` to
``async def`` — which is the second of the three breakers named next. ``test_ws.py`` asserts both.

**What would break that argument**, stated so the next author can check it against their change
rather than against this sentence: splitting the pop into a ``get`` plus a ``del``; making
:meth:`consume` ``async`` and awaiting anything between the two; or moving the store off the event
loop into a thread pool, where the GIL — not the absence of a suspension point — becomes the only
thing serialising the two operations.
"""

import math
import secrets
import time
from collections.abc import Callable
from typing import Protocol

from fastapi import FastAPI


class ActiveDeckSlot:
    """The in-memory slot naming the deck the UI is currently showing (FR-07).

    **Named a "slot", not an "ActiveDeck", on purpose.** The *wire* model
    :class:`~src.companion.contracts.ActiveDeck` already owns that name, and
    :mod:`src.companion.app.routes.active_deck` imports both — one to store, one to answer with.
    Two classes called ``ActiveDeck`` in one route module is an ``as`` alias waiting to be written
    and a reader waiting to be confused about which layer they are in.

    Constructing one is free and cannot fail — no I/O, no path resolution, no configuration — which
    is what lets the lifespan create it beside :class:`~src.companion.app.deps.Database` without
    widening the startup surface AD-10 keeps deliberately narrow.

    **Nothing here validates that the deck exists.** That is AD-16's ruling, not an omission: the
    MCP tool has database access and is the party that must report ``deck_not_found`` to the agent,
    so the backend stores what it is given. A slot holding an id no ``GET /api/deck/{id}`` can
    resolve is a legitimate state, and the UI's answer to it is the ordinary ``deck_not_found``
    path it already handles.

    Example:
        >>> ActiveDeckSlot().deck_id is None
        True
    """

    def __init__(self) -> None:
        self._deck_id: str | None = None

    @property
    def deck_id(self) -> str | None:
        """The deck currently being displayed, or ``None`` if none has been set this process.

        Read-only through the property so :meth:`set` is the single write site — the same reason
        :attr:`~src.companion.app.deps.Database.engine` is read-only.
        """
        return self._deck_id

    def set(self, deck_id: str) -> None:
        """Point the display at *deck_id*, replacing whatever was there.

        Idempotent by construction, which is why the wire verb is ``PUT`` and not ``POST``: setting
        the same deck twice is the same state.

        Args:
            deck_id: The deck to display. Stored verbatim — never trimmed, normalised or
                case-folded, because the value has to be *reported* back byte-for-byte and c3-1
                ruled a deck id has no declared shape, so there is no canonical form to normalise
                toward. (A reader handing it to ``GET /api/deck/{deck_id}`` still URL-encodes it
                like any path segment — verbatim storage is not a promise that every storable id
                is a valid raw path fragment.)
        """
        self._deck_id = deck_id


def active_deck(app: FastAPI) -> ActiveDeckSlot | None:
    """Return the :class:`ActiveDeckSlot` for *app*, or ``None`` if the lifespan never ran.

    The single reader of ``app.state.active_deck``, mirroring
    :func:`src.companion.app.deps.database` and :func:`src.companion.app.main.bound_port` so the
    state key has one construction site and one accessor. ``None`` means **the lifespan never ran**
    — a constructed-but-never-started app, which on a supported path only happens in a test.

    Args:
        app: The application to read.

    Returns:
        The holder, or ``None`` before startup.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    holder: ActiveDeckSlot | None = getattr(app.state, "active_deck", None)
    return holder


# ---------------------------------------------------------------------------------------------
# The WebSocket ticket store (AD-5, NFR-01) — c5-2 mints and expires, c5-3 consumes.
# Both halves are shipped as of c5-3: `src.companion.app.ws._handshake_is_authorised` is the
# consume's one production caller, and it is a plain `def`, which is what makes the no-lock
# argument below checkable rather than merely asserted.
# ---------------------------------------------------------------------------------------------


TICKET_TTL_SECONDS = 30.0
"""How long a minted ticket stays consumable, in seconds (AD-5, c5-2).

**AD-5 states the number, so this constant does not get to justify it** — *"single-use with a 30 s
TTL"* is the spine's wording. What is worth writing down is why the number is *comfortable*: the
ticket exists to cover the gap between ``GET /api/session`` returning and the browser's very next
``WebSocket`` upgrade, which on loopback is a handful of milliseconds. 30 s is three orders of
magnitude of headroom for a stalled tab, and still short enough that a leaked ticket is worthless
by the time anyone could act on it.

Not a rate limit and not a session lifetime: **c5-6 shipped, and mints a fresh ticket per
reconnect attempt** — ``createAgentSocket`` holds no ticket variable at all, so there is nothing
for it to inspect this value with, which is why it is deliberately not published on the wire (Q4).
The client's backoff ceiling is *also* 30 s, and its ordering is ``delay -> mint -> open`` for that
reason: at the ceiling the two windows are equal and a pre-delay mint would present an expired
ticket every time.
"""

MAX_TICKETS = 256
"""The hard bound on resident tickets, evicted earliest-expiry-first (c5-2, Q2, Brad 2026-08-08).

**The bound exists because the mint is unauthenticated and therefore unbounded-callable.** No
artefact specifies a number, so the reasoning is the specification: a legitimate browser holds *one*
outstanding ticket — it mints, upgrades, and the upgrade consumes — and even a pathological
reconnect storm at c5-6's backoff cannot keep hundreds alive inside a 30 s window — measured now
that it ships: one mint per attempt on a 2/4/8/16/30 s schedule is **at most six inside any 30 s
window, per tab**, and each is consumed or expired before the next. 256 is therefore
two-and-a-half orders of magnitude above the real workload while capping the map at a few tens of
kilobytes, which is the shape :class:`~src.companion.app.images.NegativeCache` already ships under.

**What eviction costs, stated rather than glossed.** At the cap the *earliest-expiring* entry is
dropped, mirroring :meth:`~src.companion.app.images.NegativeCache._evict_earliest_expiry`. Since
every ticket carries the same TTL that is the oldest one, so a local page that spams this endpoint
can push a legitimate browser's ticket out and cost it one failed upgrade and one re-mint (c5-6
ships that retry, and cannot tell this case from any other: ``ws.py`` refuses every failure with
the same bodyless ``1008``, so the loop's answer to an eviction is the same as its answer to a
restart). The alternative — refusing to mint at the cap — hands that same attacker a
**permanent** denial instead of a recoverable one, and would need an ``ErrorReason`` token AC 12
declines to add. A recoverable eviction beats an unrecoverable refusal.

Deliberately not ``60`` or ``15``: ``test_routes_format_check.py``'s AD-1 construction-limit family
bans those literals anywhere under ``src/companion``, and ``_LIMIT_FAMILY_EXEMPT`` names only
``contracts.py``.
"""

_TICKET_ENTROPY_BYTES = 32
"""How many random bytes back one ticket — ~43 URL-safe characters (c5-2, Q7).

**The same strength as** :func:`src.companion.discovery.mint_token`'s, under this module's own
constant and its own :func:`secrets.token_urlsafe` call site. That duplication is the requirement,
not an oversight: AD-5 rules that the ticket and the agent token share **no storage and no code
path**, and importing the token minter to save one line would breach it in the most literal way
available. Matching its *strength* while sharing none of its *code* is the whole shape.
"""


class TicketStore:
    """The map of live WebSocket tickets, and the single-use consume over it (AD-5, NFR-01).

    **What a ticket is for.** ``CORS`` does not protect a WebSocket upgrade — the browser sends no
    preflight and the handshake is not a fetch — so an upgrade authenticated by nothing but its
    ``Host`` is authenticated by nothing a page cannot also present. The ticket closes that: the
    browser must first read one from same-origin ``GET /api/session``, and a page on another origin
    cannot read that response (there is no ``Access-Control-Allow-Origin``, deliberately and
    permanently — c1-5). It can *issue* the mint and burn tickets; it cannot *learn* one.

    **Single-use is the property, and expiry is only the backstop.** A ticket is destroyed at
    :meth:`consume` whether or not the handshake that presented it goes on to succeed, so a replay
    fails even inside the TTL. :data:`TICKET_TTL_SECONDS` exists for the ticket that is minted and
    never presented — the tab the user closed — which single-use alone would leave resident forever.

    **It is** :class:`~src.companion.app.images.NegativeCache`**-shaped, and that is not decoration
    — it is what makes both hard parts testable.** Constructing it cannot fail (a dict and a clock),
    so the lifespan creates it beside :class:`ActiveDeckSlot` with no ``build_*`` factory and
    nothing in ``main._shutdown``, and AD-15's ruling that publishing the discovery file is the
    *only* startup step which may fail a launch stays literally true. And the clock is
    **injected**, so the 30-second TTL is proven at zero wall clock: a test that sleeps is a defect.

    **Bounded, and at the cap the earliest-expiring resident is evicted** (AC 10). Every ticket
    carries the same TTL, so earliest-expiring is also oldest-minted. The cost of an eviction: the
    client whose ticket was dropped loses its next upgrade and re-mints — recoverable, where
    refusing the mint at the cap would be a permanent denial under the same flood; see
    :data:`MAX_TICKETS` for the full argument and the bound's sizing.

    **Nothing is persisted, and that is CM-3 rather than an omission.** A ticket outliving the
    process it authenticates would be a credential for a socket that no longer exists; a restart
    begins with an empty store and every client re-mints. So nothing here reaches disk,
    ``companion.json`` or any cache.

    **This store shares no code path with the agent token (AD-5).** It does not import
    :mod:`src.companion.discovery`, does not read ``app.state.agent_token``, and routes no
    validation through ``presented_credential`` / ``agent_token_is_valid`` /
    ``require_agent_token``. ``test_routes_active_deck.py`` asserts that structurally rather than
    trusting this paragraph.

    Args:
        ttl: How long a minted ticket stays consumable, in seconds. Defaults to
            :data:`TICKET_TTL_SECONDS`.
        max_tickets: The hard bound on resident tickets. Defaults to :data:`MAX_TICKETS`.
        clock: The monotonic time source, in seconds. Injected for exactly the reason
            :class:`~src.companion.app.images.NegativeCache`'s is. **Monotonic, never**
            ``time.time``: a wall clock steps backwards on an NTP correction and across a DST
            boundary, which would either expire every live ticket at once or keep one consumable
            for an hour. The route never passes this; only tests do.

    Raises:
        ValueError: ``ttl`` is not a positive finite number (non-positive, every ticket would be
            born expired, so no handshake could ever succeed; ``nan`` or ``inf``, every deadline
            comparison would quietly answer ``False`` and expiry would never fire) or
            ``max_tickets`` is below one (the eviction would ``min()`` over
            an empty map on the first mint). A guard against a mis-injected test parameter, not a
            startup risk: the lifespan constructs with the module constants and no arguments, so
            the accessor's "construction cannot fail" claim stays true on every production path.

    Example:
        >>> store = TicketStore()
        >>> issued = store.mint()
        >>> store.consume(issued)
        True
        >>> store.consume(issued)
        False
    """

    def __init__(
        self,
        *,
        ttl: float = TICKET_TTL_SECONDS,
        max_tickets: int = MAX_TICKETS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # `not isfinite` rather than trusting `<= 0`: nan compares False against everything, so it
        # would sail through a sign check and then disarm every deadline comparison downstream.
        if not math.isfinite(ttl) or ttl <= 0:
            raise ValueError(f"ttl must be positive and finite, got {ttl}")
        if max_tickets < 1:
            raise ValueError(f"max_tickets must be at least 1, got {max_tickets}")
        self._ttl = ttl
        self._max_tickets = max_tickets
        self._clock = clock
        # Value is the deadline, not the issue time: `consume` then compares one number against
        # one reading instead of recomputing the sum on every handshake.
        self._deadlines: dict[str, float] = {}

    @property
    def resident_count(self) -> int:
        """How many tickets are resident right now — the bound AC 9 and AC 10 assert against.

        Exposed for the same single reason
        :attr:`~src.companion.app.images.NegativeCache.entry_count` is: it is the **only** thing
        that can distinguish *pruning* an expired ticket from merely *ignoring* it on read. Every
        behavioural assertion in the suite is identical under both, and a map that only ignores
        expiry reaches its cap on garbage and then evicts live tickets to make room for it.

        **Resident is not live.** Expired tickets are pruned at :meth:`mint`, not by time, so
        between mints this count includes tickets already past their deadline. A future metrics or
        dashboard reader wanting "live tickets right now" must not read this as that.
        """
        return len(self._deadlines)

    def mint(self) -> str:
        """Issue a fresh ticket, and return it.

        Every call returns a **distinct** value — there is no reuse, no caching and no
        one-per-client memo, because a ticket is consumed by the very next handshake and c5-6 mints
        a new one per reconnect attempt — which it now does: the browser's loop keeps no ticket
        field, so a ticket cannot outlive the attempt that minted it.

        Expired tickets are pruned here rather than on read, mirroring
        :meth:`~src.companion.app.images.NegativeCache.record_failure`: otherwise the map fills with
        tickets nobody will ever present, hits :data:`MAX_TICKETS`, and starts evicting live ones to
        make room for dead ones.

        Returns:
            The ticket, valid for :data:`TICKET_TTL_SECONDS` and consumable exactly once.
        """
        # One reading per public call, passed down, so a single mint cannot straddle two — the
        # rule `NegativeCache.record_failure` states at its own clock call.
        now = self._clock()
        self._forget_expired(now)
        if len(self._deadlines) >= self._max_tickets:
            self._evict_earliest_deadline()
        # This story's OWN `secrets.token_urlsafe` call, never `discovery.mint_token()`: AD-5
        # requires the ticket and the agent token to share no code path, and reusing the minter
        # would be the most literal possible breach of it.
        issued = secrets.token_urlsafe(_TICKET_ENTROPY_BYTES)
        self._deadlines[issued] = now + self._ttl
        return issued

    def consume(self, ticket: str) -> bool:
        """Destroy *ticket* and report whether it was live at the moment it was destroyed.

        **Destruction happens here, not at some later sweep, and it happens on every path** —
        an expired ticket and an already-consumed one are both removed by the same ``pop`` that
        rejects them. That is what makes "single-use" true rather than "single-successful-use":
        a caller cannot retry a rejected ticket into a different answer.

        The expiry boundary is **half-open, and the pick is that a ticket at exactly its deadline
        is already expired** — ``now < deadline``, the same operator and the same rounding as
        :meth:`~src.companion.app.images.NegativeCache.is_backing_off`. Both sides of that line are
        asserted rather than left to the reader.

        No lock, and the reasoning is in this module's docstring rather than repeated here: the
        compare-and-set is one synchronous ``dict.pop`` with no ``await`` inside it, so there is no
        interleaving point at which a second caller could observe the ticket still present.

        Args:
            ticket: The value a handshake presented. An unknown value — never minted, already
                consumed, or invented — is refused the same way an expired one is, and no
                distinction between those cases is reported: a caller that could tell them apart
                could probe the store.

        Returns:
            True when the caller may proceed with the upgrade.
        """
        now = self._clock()
        deadline = self._deadlines.pop(ticket, None)
        return deadline is not None and now < deadline

    def _forget_expired(self, now: float) -> None:
        """Drop every ticket whose deadline has passed.

        **The horizon is the deadline itself, with no retention beyond it** — and that is the one
        place this class deliberately diverges from
        :meth:`~src.companion.app.images.NegativeCache._forget_stale`, which keeps an entry a full
        ceiling past its window because a backoff *escalates* and needs its own history. A ticket
        has no history: it is live or it is worthless, and there is no next state for a remembered
        expiry to inform.

        Args:
            now: The current clock reading, passed in so one :meth:`mint` takes exactly one reading
                and cannot straddle two.
        """
        expired = [issued for issued, deadline in self._deadlines.items() if now >= deadline]
        for issued in expired:
            del self._deadlines[issued]

    def _evict_earliest_deadline(self) -> None:
        """Make room for one new ticket by dropping the one closest to expiring anyway.

        Reached only when :data:`MAX_TICKETS` live tickets exist at once, which the pruning above
        makes hard to arrive at honestly — see that constant for what an eviction costs the client
        whose ticket is dropped, and why a recoverable eviction was chosen over refusing the mint.

        Every ticket carries the same TTL, so earliest deadline is also oldest mint; the tiebreak is
        written against the deadline rather than insertion order so it stays correct if a future
        story ever issues a ticket with a different lifetime.
        """
        earliest = min(self._deadlines, key=lambda issued: self._deadlines[issued])
        del self._deadlines[earliest]


def ticket_store(app: FastAPI) -> TicketStore | None:
    """Return the :class:`TicketStore` for *app*, or ``None`` if the lifespan never ran.

    The single reader of ``app.state.ticket_store``, mirroring :func:`active_deck` so the state key
    has one construction site and one accessor. ``None`` means **the lifespan never ran** — a
    constructed-but-never-started app, which on a supported path only happens in a test.

    Args:
        app: The application to read.

    Returns:
        The store, or ``None`` before startup.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    holder: TicketStore | None = getattr(app.state, "ticket_store", None)
    return holder


# ---------------------------------------------------------------------------------------------
# The connection registry (CM-3, FR-06, AD-8) — c5-4 registers and fans out. c5-5 was scheduled to
# read `connected_count` and ruled otherwise (Q1): its receipt carries `broadcast()`'s DELIVERED
# count instead.
#
# ⚠️ THE FOLLOW-ON PREDICTION WAS FALSIFIED, and is recorded rather than quietly worked around
# (c5-7, Q6, 2026-08-08). This comment used to end "and this property waits for c5-7's connection
# pill, which wants a live gauge". The pill shipped, and it wants no such thing: FR-15 and UX-DR29
# specify a client-side status (live / reconnecting / backend gone) plus the active deck's name,
# and a connected-client count appears in neither. The pill reads its own socket through the
# browser's store and makes no backend call at all.
#
# `connected_count` is still consumed — see its own docstring — and the honest statement of who
# might want it is "a future status surface", with c10-1 the nearest candidate; note that c10-1
# reads `GET /health` for a port and an instance id, still not this count.
# The third and last of the Structural Seed's three nouns for this module.
# ---------------------------------------------------------------------------------------------


class Connection(Protocol):
    """What the fan-out needs a registered client to be — write to it, and close it (c5-4, Q1).

    **Structural, so this module keeps importing no web framework.** ``state.py`` is a dict, a slot
    and a clock; naming :class:`starlette.websockets.WebSocket` here would make the package's
    innermost state holder depend on the ASGI layer that happens to be the only current caller, and
    would force every registry unit test to build a scope and a ``receive``/``send`` pair to
    register anything. A protocol costs nothing and buys the fakes.

    **Three members rather than the one "an object with** ``send_text`` **" the story recommended**,
    and the third is why: Q2 ruled that a send failure closes that socket best-effort, so the
    fan-out's containment path needs :meth:`close` as well as :meth:`send_text`, and
    :func:`src.companion.app.ws._close_quietly` consults the connection state before spending a
    frame on a peer that has already gone. The recommendation predated the ruling; the ruling is
    what the type has to serve.

    :attr:`client_state` is typed ``object`` **deliberately**, and it is the one place this protocol
    declines to be precise. This module never interprets the value — it is compared by identity
    against a sentinel owned by the caller (``WebSocketState.DISCONNECTED``) — so naming
    Starlette's enum here would import the framework for a value this file has no opinion about.
    ``object`` is the honest type for "a token we pass through and never read".
    """

    @property
    def client_state(self) -> object:
        """Whatever the transport says about this connection, passed through uninterpreted."""

    async def send_text(self, data: str) -> None:
        """Write one text frame."""

    async def close(self, code: int = 1000) -> None:
        """Close the connection with *code*."""


class ConnectionRegistry:
    """The set of accepted WebSockets a broadcast fans out to (FR-06, AD-8, CM-3).

    **A container, and deliberately nothing more.** It does not accept sockets, does not send, does
    not close and does not know what an event is — :mod:`src.companion.app.ws` owns all four. What
    lives here is the membership, for the same reason the ticket map does: the Structural Seed
    homes ``connections`` in this module, and a registry that also fanned out would put the wire
    format in the state file.

    **No lock, and here is the argument** — the shape :class:`TicketStore` uses, re-made for this
    class rather than inherited by assertion. Every operation is a **single synchronous container
    mutation**: :meth:`add` is one ``set.add``, :meth:`discard` is one ``set.discard``,
    :meth:`snapshot` is one ``tuple()`` and :attr:`connected_count` is one ``len``. None of them
    reads a value and then writes a value derived from it, and none of them contains an ``await``,
    so on the single-threaded event loop there is no point at which a second caller can observe a
    half-applied change. Two concurrent registrations produce a set containing both; two concurrent
    discards of one connection produce a set containing neither. That is exactly what a lock would
    also produce, at the cost of making every one of these methods awaitable — including the
    ``finally`` that must run while a socket is being torn down.

    **What would break that argument**, stated so the next author can check it against their change
    rather than against this sentence: a method that consults membership and then acts on it (a
    ``add_if_absent``, a "broadcast only to clients that have not seen this id", any eviction
    policy that picks a victim by reading the set first — the read-modify-write
    :class:`TicketStore`'s docstring names in its own vocabulary); making any method ``async`` and
    awaiting inside it; or iterating ``self._connections`` directly instead of a
    :meth:`snapshot`, which would put the fan-out's own ``await`` inside a live iteration and turn
    a disconnect into ``RuntimeError: Set changed size during iteration``.

    **Unbounded, and that is a ruling rather than an oversight** (c5-4, Q7, Brad 2026-08-08). The
    ticket store is capped because its mint is unauthenticated and therefore unbounded-callable; a
    registration is not — every entry here cost the caller a same-origin ticket that was minted
    under :data:`MAX_TICKETS` and destroyed on use, so the ticket cap already bounds the rate at
    which this set can grow, and the process's own file-descriptor limit bounds the rest. A cap
    here would need an eviction policy, and evicting a connection means closing a legitimate tab
    that did nothing wrong — a permanent, visible failure to defend against a flood the layer above
    has already metered.

    **Nothing is persisted (CM-3).** A connection cannot outlive the process holding its socket, so
    a restart begins with an empty set and every client reconnects — the same shape, and the same
    reasoning, as the ticket store and the active-deck slot above.

    **This registry shares no code path with the agent credential (AD-5)**, and holds nothing that
    identifies a client beyond the connection object itself: no address, no ticket, no headers.
    There is nothing here to leak into a log line.

    Example:
        >>> ConnectionRegistry().connected_count
        0
    """

    def __init__(self) -> None:
        # A set rather than a list: `discard` must be idempotent (AC 5) and membership is the whole
        # contract, so the container that gives both for free is the right one. Connections are
        # hashable by identity — nothing here defines `__eq__` — which is exactly the identity two
        # tabs on one page need to be distinguishable by.
        self._connections: set[Connection] = set()

    @property
    def connected_count(self) -> int:
        """How many clients are registered right now — **not** the number ``POST /agent/events``
        answers with.

        **Corrected at c5-5 (Q1, Brad 2026-08-08), which is the story that had to choose.** This
        docstring used to open "the number story 5.5 answers with" while its own second paragraph
        said the endpoint "reports the delivery count it achieved" — two different numbers, stated
        one line apart. The ruling went to the delivery count:
        :func:`~src.companion.app.ws.broadcast`'s return value, which counts clients that actually
        took the frame and drops any that failed mid-fan-out. The two agree except in that failure
        race, and in exactly that window this property over-reports a tab that is already gone —
        so "how many browsers saw it", which is the question the endpoint exists to answer, is
        answerable only by the other one.

        **Kept — and the reason given for keeping it was wrong** (c5-7, Q6, Brad 2026-08-08).
        This paragraph used to read "c5-7's connection pill asks the question this property
        actually answers". It does not. The shipped pill reports *this browser's own* socket
        status and the active deck's name (FR-15, UX-DR29); it makes no request to this backend,
        and a count of other clients appears nowhere in its specification. Recorded as a falsified
        prediction in the c5-6 mould rather than silently dropped.

        What the property IS for is unchanged and real: it is consumed by this module's own test
        suite (:mod:`tests.unit.companion.test_ws`) and by
        :mod:`tests.unit.companion.test_routes_active_deck`. :mod:`~src.companion.app.ws`'s
        ``broadcast`` reads only :meth:`snapshot`, :meth:`add` and :meth:`discard` — never this
        property. The question it answers — *is anything listening right now* — is a live gauge a
        future STATUS SURFACE could want.
        c10-1 is the nearest candidate and is not a user of it either: it reads ``GET /health``
        for a port and an instance id. So it stays **queryable, cheap and free of I/O**: one
        ``len`` over an in-memory set, no database (AD-7), no failure mode.

        **Registered is not reachable.** A tab that vanished without a disconnect frame stays
        counted until the next broadcast fails to write to it (or its handler's ``finally`` runs),
        so this is the count of connections this process *believes* it holds, which is the only
        count anything can honestly report without spending a frame to find out.
        """
        return len(self._connections)

    def add(self, connection: Connection) -> None:
        """Register *connection* as a client broadcasts must reach.

        Called once per socket, immediately after ``accept()`` succeeds and never before — an
        unaccepted handshake has no channel to write to, so registering earlier would put a
        connection in the fan-out's path that the fan-out cannot use.

        Idempotent: registering the same connection twice leaves one entry, so a re-entrant caller
        cannot make :attr:`connected_count` over-report the tabs that exist.

        Args:
            connection: The accepted socket.
        """
        self._connections.add(connection)

    def discard(self, connection: Connection) -> None:
        """Unregister *connection*, whether or not it was ever registered.

        **The silence on a miss is load-bearing, not defensive** (AC 5). One dying tab is dropped
        twice on the ordinary path: the fan-out drops it when a send raises, and the handler's own
        ``finally`` drops it when the drain returns — in either order, and both certainly run. A
        method that raised on the second would convert a routine disconnect into the ``1011`` the
        handler reserves for genuine faults.

        Args:
            connection: The socket to forget.
        """
        self._connections.discard(connection)

    def snapshot(self) -> tuple[Connection, ...]:
        """Return the registered connections as a tuple the caller may safely outlive.

        **A copy, because the fan-out mutates this registry while walking it.** Sending is
        asynchronous and a failed send discards its socket, so iterating the live set directly
        would be a mutation during iteration; a tuple taken up front makes the broadcast operate on
        a stable membership and lets a connection that disconnects mid-fan-out simply fail its own
        send rather than corrupt everyone else's.

        **No ordering is promised**, and none should be read into it — a set has none, and AD-6
        puts event ordering on the envelope's ``ts`` rather than on the transport. A caller that
        needs "in registration order" is describing a different data structure and should say so.

        Returns:
            Every currently registered connection, in unspecified order.
        """
        return tuple(self._connections)


def connection_registry(app: FastAPI) -> ConnectionRegistry | None:
    """Return the :class:`ConnectionRegistry` for *app*, or ``None`` if the lifespan never ran.

    The single reader of ``app.state.connections``, mirroring :func:`active_deck` and
    :func:`ticket_store` so the state key has one construction site and one accessor. ``None``
    means **the lifespan never ran** — a constructed-but-never-started app, which on a supported
    path only happens in a test.

    Args:
        app: The application to read.

    Returns:
        The registry, or ``None`` before startup.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    holder: ConnectionRegistry | None = getattr(app.state, "connections", None)
    return holder

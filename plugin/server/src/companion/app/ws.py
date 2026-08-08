"""The authenticated WebSocket upgrade — ``Origin``, then the ticket, then accept (AD-5, NFR-01).

**Half of this story's security was already shipped, and this module deliberately does not repeat
it.** :class:`~src.companion.app.security.HostValidationMiddleware` is pure ASGI *specifically* so
it sees ``websocket`` scopes, and a handshake naming a disallowed authority is closed ``1008``
before it ever reaches this router. There is no ``Host`` check below, and there must never be one:
a second copy is a second thing to keep in sync, and the middleware's copy is the one that runs
first. What this module adds is the two things a ``Host`` check structurally cannot do — decide
**which page** is calling, and **spend** the ticket that page presented.

**Why ``Origin`` has to be checked here and nowhere else.** A WebSocket upgrade is not a fetch. The
browser sends no preflight, and ``Access-Control-Allow-Origin`` has no say in whether the handshake
proceeds — so the whole CORS apparatus that protects ``GET /api/session`` protects nothing here.
Meanwhile ``Host`` is honest for a hostile local tab: a page on ``evil.example.com`` that opens
``ws://127.0.0.1:<port>/ws`` addresses this process by exactly the authority it means to. ``Origin``
is what separates them, it is set by the browser, and the page cannot forge it. c5-2's mint declines
the same check on purpose (a cross-origin page can *issue* that ``GET`` but cannot *read* it, so it
can burn tickets and never learn one); AD-5 and review finding S-6 both home the check on this
upgrade, and this is that home.

**The order is ``Origin`` before consume, and the order is load-bearing.** A ticket is destroyed by
the mere act of presenting it — :meth:`~src.companion.app.state.TicketStore.consume` pops on every
path, which is what makes "single-use" true rather than "single-successful-use". So a foreign page
that somehow held a valid ticket and were checked ticket-first would *burn* it, costing the real
browser a failed upgrade per attempt. Burning is the residual exposure c5-2's Q1 knowingly accepted
at the mint; the upgrade declines to add a second burner. The rejection is therefore free of side
effects, and ``test_ws.py`` pins that by consuming the ticket successfully afterwards.

**Every rejection looks identical on the wire, and that is a requirement rather than laziness.**
No ticket, an unknown ticket, an expired ticket, a replayed ticket and a foreign ``Origin`` all
produce one ``websocket.close`` with code ``1008`` and nothing else. The store already refuses to
distinguish its own three cases — *"a caller that could tell them apart could probe the store"* —
and an upgrade that leaked the fourth distinction would hand back exactly what the store withheld.
The *log* may distinguish, and does: it is not the wire, and "the origin was wrong" versus "the
ticket was not live" is the difference between two entirely different c5-6 debugging sessions.

**No new ``ErrorReason`` token, and no JSON anywhere.** A closed WebSocket has no body to carry one,
the token set is closed at ten, and AD-16's rule is that a token exists to drive a UI state — ticket
churn is designed to be invisible (c5-6 re-mints and retries). ``1008`` is the shipped precedent
from the ``Host`` middleware; ``1011`` appears only on the fail-closed internal-error path below.

**What is deliberately absent: the connection registry and the broadcast.** The spine's module map
lists this file as ``ws.py # upgrade + ticket consume + broadcast``, and only the first two are
here. c5-4 owns the registry (:mod:`src.companion.app.state` already reserves its home) and the
fan-out; scaffolding either now would ship an empty holder for a story that has not been designed.
"""

import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketState

from src.companion.app.security import origin_is_allowed
from src.companion.app.state import TicketStore, ticket_store

logger = logging.getLogger(__name__)

WS_PATH = "/ws"
"""The path the upgrade answers on (c5-3, Q1, Brad 2026-08-08).

No artefact specified one — the spine names the *module* (``ws.py``) and the epic's ACs say only
"the upgrade is rejected". ``/ws`` takes the module's own name and stays out of ``/api``, which is
the REST namespace: this endpoint has no OpenAPI surface at all (OpenAPI does not model WebSockets),
so filing it under the documented REST prefix would put an undocumentable thing in the one namespace
whose contract is that it is documented.

**A plain HTTP ``GET`` of this path gets the typed 404, not the SPA index** — which is *not* what
Q1 predicted, and the difference is worth knowing. :func:`~src.companion.app.spa._reserved_prefixes`
derives its reservations from the live route table, and it descends into ``WebSocketRoute`` exactly
as it does into ``Route``, so registering this router reserves the first segment ``ws`` for the API
and the SPA mount declines it. The prediction assumed the fall-through; the measurement says
otherwise, and the better answer is the one that fell out. ``test_ws.py`` pins it deliberately.
"""

_TICKET_PARAM = "ticket"
"""The query parameter the ticket rides in (c5-3, Q2, Brad 2026-08-08).

**A query parameter because the browser's ``WebSocket`` constructor cannot set headers**, and it is
the only place left. The alternative considered was ``Sec-WebSocket-Protocol``, which browsers *do*
let a page set — but that field exists to negotiate a subprotocol, the server must echo the selected
value back in the handshake response, and abusing it means the ticket travels in both directions to
avoid travelling in one.

The residual is uvicorn's access log, which records path and query. It is argued acceptable rather
than waved away: the ticket is single-use and destroyed at the moment it is presented, so **a logged
ticket is by construction a spent one**. That reasoning is specific to this credential and does not
generalise — AD-5's no-logging rule is about the agent token, which is long-lived and would be a
real leak.
"""

_ORIGIN_HEADER = "origin"
"""The header naming the page that opened the socket. Read from ``websocket.headers`` by hand.

Never an ``Annotated[str, Header()]`` parameter and never a FastAPI security class, for the reasons
:data:`~src.companion.app.security._AUTHORIZATION_HEADER` records: a declared header lands in
``app.openapi()`` and a security class adds a ``securitySchemes`` component. Neither applies to a
WebSocket route today — it has no OpenAPI surface to pollute — but the habit is the guard, and
``test_committed_schema.py``'s 8-paths/13-components pins are what it protects.
"""

_POLICY_VIOLATION = 1008
"""The close code for **every** refused handshake, sent before ``accept``.

Exactly what :class:`~src.companion.app.security.HostValidationMiddleware` already sends on a
disallowed ``Host`` (``security.py``'s close-before-accept, which uvicorn renders as an HTTP 403
handshake failure). One code for one meaning — *you may not have this socket* — with no attempt to
say why. See the module docstring for why the reasons stay indistinguishable.
"""

_INTERNAL_ERROR = 1011
"""The close code for a fault in this handler, and the only place this module deviates from 1008.

**This is the disposition of the gap the shipped code homed on this story** (c5-3, Q6, Brad
2026-08-08). :class:`~src.companion.app.errors.UnhandledErrorMiddleware` covers ``http`` scopes only
— there is no JSON body to send on a ``websocket`` scope — so before this module existed a fault
while validating a handshake would have escaped raw. The fix is local: the handler catches its own
faults and closes ``1011``, and the error middleware **stays http-only**. Extending it to websocket
scopes would give one middleware a second shape for exactly one caller, and that shape would have to
duplicate this handler's pre-accept/post-accept distinction anyway.

Distinguishable from :data:`_POLICY_VIOLATION` on the wire, deliberately: a caller cannot *cause*
this branch, so it leaks nothing about the ticket store — and a client that could not tell "you are
not allowed" from "we broke" would retry the wrong one.
"""

_MAX_LOGGED_ORIGIN = 100
"""Precision cap on the attacker-controlled ``Origin`` written to the rejection log.

The same value and the same reasoning as ``security.py``'s cap on ``Host``: the header is truncated
rather than echoed in full, so a rejected handshake cannot write an arbitrarily long string into an
operator's console. The cap bounds the ``%r`` output, whose opening quote counts toward it.
"""

router = APIRouter()


def _store(websocket: WebSocket) -> TicketStore:
    """Return the ticket store for the app serving *websocket*.

    Args:
        websocket: The handshake being validated.

    Returns:
        The store the lifespan created.

    Raises:
        AttributeError: Raised by hand when the store is missing, matching
            :func:`src.companion.app.routes.session._store` exactly — the accessor's ``getattr``
            already swallowed the attribute miss, so this restores the loud failure. A missing store
            can only mean the lifespan never ran, which is a wiring bug rather than a policy
            rejection, and it must not be answered with the ``1008`` that means "you may not have
            this socket". :func:`websocket_upgrade`'s fail-closed handler turns it into ``1011``.
    """
    store = ticket_store(websocket.app)
    if store is None:
        raise AttributeError("no ticket store on this app; the lifespan did not run")
    return store


def _handshake_is_authorised(websocket: WebSocket) -> bool:
    """Decide the whole handshake — ``Origin`` then ticket — without ever suspending.

    **This function is synchronous, and that is the deliverable rather than a style choice**
    (``deferred-work.md``'s consume-atomicity entry, homed here).
    :meth:`~src.companion.app.state.TicketStore.consume` carries no lock, and ``state.py``'s module
    docstring argues it needs none because the compare-and-set is one ``dict.pop`` with no ``await``
    between the read and the delete, so there is no interleaving point at which a second caller
    could observe the ticket still present. That argument had **zero production callers** until this
    line; the ledger asked that the story making the call *show* the call sits in synchronous code.

    Here is the showing. The entire decision — read ``Origin``, evaluate it, reach the store, pop —
    lives in one plain ``def``. A plain ``def`` cannot contain an ``await``, so the property is
    enforced by the language rather than by review: there is no edit to this function that
    reintroduces a suspension point without also changing its ``def`` to ``async def``, which is one
    of the three changes ``state.py`` names as breaking the no-lock argument (the others being
    splitting the pop, and moving the store off the event loop). ``test_ws.py``'s AST guard asserts
    both halves — no ``Await`` node anywhere in this module's consume path, and ``consume`` itself
    still a plain function.

    **``Origin`` is evaluated first and returns early**, so a rejected foreign handshake never
    reaches the pop and cannot burn the ticket it happened to carry. See the module docstring.

    Args:
        websocket: The handshake being validated. Read-only here: nothing is accepted, closed or
            sent from this function, because a predicate that could answer the client would be a
            second place the rejection shape is decided.

    Returns:
        ``True`` only when the calling page is our own **and** it presented a live ticket, which is
        now spent. ``False`` for every other case, with no report of which — see the module
        docstring on indistinguishability.

    Raises:
        AttributeError: When the lifespan never ran; see :func:`_store`.
    """
    # More than one `Origin` is ambiguous by construction, mirroring `security.py`'s own
    # `_host_headers` treatment of `Host`: a reader taking the first and a reader taking the last
    # would disagree about which page is calling. Refuse rather than pick.
    origins = websocket.headers.getlist(_ORIGIN_HEADER)
    origin = origins[0] if len(origins) == 1 else None
    # Function-local, and for the reason `security.py` states at its own two: `main.py` imports
    # this module's router in its top-level block, so a module-level import of anything from
    # `main` is a genuine circular-import failure in both directions. `bound_port` is the accessor
    # c1-3 built for exactly this caller.
    from src.companion.app.main import bound_port

    if not origin_is_allowed(origin, bound_port(websocket.app)):
        logger.warning(
            "Refusing WebSocket upgrade: Origin %.*r is not this application's own origin",
            _MAX_LOGGED_ORIGIN,
            origin,
        )
        return False

    # `or ""` rather than a branch on absence: an omitted ticket must reduce to the same rejection
    # as a wrong one, and `consume("")` pops a key that was never minted. Collapsing it here is what
    # keeps the decision below down to one comparison and the wire down to one close.
    presented = websocket.query_params.get(_TICKET_PARAM) or ""
    if not _store(websocket).consume(presented):
        # No value logged, at any level. The ticket is a credential (AD-5), and the store refuses to
        # say whether it was unknown, expired or already spent — so there is nothing here to report
        # beyond the fact, and echoing the presented value would write an attacker-chosen string
        # into an operator's console for the privilege of saying it was wrong.
        logger.warning("Refusing WebSocket upgrade: no live ticket was presented")
        return False
    return True


async def _drain_until_disconnect(websocket: WebSocket) -> None:
    """Read and discard client frames until the client goes away (c5-3, Q5, Brad 2026-08-08).

    **The channel is one-way (AD-6): the backend broadcasts, the browser listens.** Nothing in the
    contract gives a client frame a meaning, so there are only two honest things to do with one, and
    closing on chatter is the worse of them — it would turn an innocent client bug, a stray
    keep-alive or a browser extension into a close, which c5-6's reconnect loop would answer with a
    re-mint and a fresh handshake, converting one harmless frame into a storm.

    Reading is not optional even though the content is ignored. The receive channel is how a
    disconnect *arrives*: a handler that returned immediately after ``accept`` would close a socket
    the client believes is open, which is precisely the connection c5-4 is about to want.

    Args:
        websocket: The accepted socket.
    """
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return


async def _close_quietly(websocket: WebSocket, code: int) -> None:
    """Close *websocket* with *code*, tolerating a peer that has already gone.

    Used for every pre-accept close this module sends — the ordinary policy rejection as well as
    the fail-closed paths — because a peer that vanished mid-handshake can make the close frame
    itself raise, on either kind of close. For the fail-closed paths the exception being handled
    may well *be* the connection dying, in which case a secondary failure inside error handling
    must not replace the log line that explains the primary one; for the ordinary rejection there
    is no primary error to protect, but the same peer-already-gone failure is just as reachable, so
    the same tolerance applies. Swallowed at ``DEBUG`` either way.

    Args:
        websocket: The socket to close.
        code: The close code to send.
    """
    if websocket.client_state is WebSocketState.DISCONNECTED:
        return
    try:
        await websocket.close(code=code)
    except Exception:  # pragma: no cover - defensive; the peer is already gone
        logger.debug("Could not send close frame %d; the peer is already gone", code)


@router.websocket(WS_PATH)
async def websocket_upgrade(websocket: WebSocket) -> None:
    """Accept one authenticated WebSocket, or refuse it before it is ever established.

    ``Host`` has already been validated by the time this runs —
    :class:`~src.companion.app.security.HostValidationMiddleware` closed the handshake ``1008``
    without calling the router if it was addressed wrongly. This handler decides the other two
    questions, in this order and no other: is the calling page ours, and did it bring a live ticket.

    **Rejection is pre-accept, and that is the ASGI-legal denial.** Sending ``websocket.close``
    while the connection is still in its handshake makes uvicorn answer the HTTP upgrade with 403
    — the socket is never established, so there is no accepted connection to tear down and nothing
    the client can read. Accepting first and closing after would be a different and worse protocol:
    the page would briefly hold an open socket to a session it is not entitled to.

    **Fail-closed on an unexpected fault** (Q6): the error middleware covers ``http`` scopes only,
    so a fault here would otherwise escape raw. Every phase is wrapped — a fault while validating
    the handshake, or while accepting it, closes ``1011`` pre-accept; a fault after accept closes
    ``1011`` on the live socket — and the traceback is logged once, exactly as the http net does.
    The ordinary policy rejection (line 2 below) is not a fault, but it shares the same
    peer-already-gone tolerance via :func:`_close_quietly` rather than a raw ``websocket.close``.

    Args:
        websocket: The handshake, injected by FastAPI. Its query string carries the ticket and its
            headers carry the ``Origin``; nothing else about it is read.
    """
    try:
        authorised = _handshake_is_authorised(websocket)
    except Exception:
        # The websocket half of what `UnhandledErrorMiddleware` does for http, and the reason it
        # stays http-only: there is no JSON body to send here, so the answer is a close code.
        logger.exception("Unhandled error validating a WebSocket handshake")
        await _close_quietly(websocket, _INTERNAL_ERROR)
        return

    if not authorised:
        await _close_quietly(websocket, _POLICY_VIOLATION)
        return

    try:
        await websocket.accept()
    except Exception:
        # `accept()` sends the first frame on a socket that may already be gone (the peer closed
        # the TCP connection between `_handshake_is_authorised` returning and this line) — the same
        # fault class as validation, just one line later, and it gets the same disposition.
        logger.exception("Unhandled error accepting a WebSocket handshake")
        await _close_quietly(websocket, _INTERNAL_ERROR)
        return

    try:
        await _drain_until_disconnect(websocket)
    except Exception:
        logger.exception("Unhandled error on an accepted WebSocket")
        await _close_quietly(websocket, _INTERNAL_ERROR)

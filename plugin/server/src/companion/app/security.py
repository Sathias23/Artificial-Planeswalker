"""The localhost-only security envelope: what may address this process, and who may write (AD-5).

Two independent checks live here, and they are independent on purpose.

* **The ``Host`` check** (:class:`HostValidationMiddleware`) — envelope-wide, applied to every
  request and every WebSocket handshake, and about *which authority the caller believed it was
  addressing*. It is installed as middleware by :func:`install_security`.
* **The agent credential** (:data:`AgentToken`) — per-route, applied only to the endpoints that
  *write*, and about *who the caller is*. It is a dependency rather than middleware, because a
  route-by-route decision is what the routes themselves should declare: c3-4's ``GET
  /api/active-deck`` is credential-free and its ``PUT`` is not, in the same module, and a
  middleware would have to re-derive that from a path list.

Both fail **closed** on a missing input, and that shared rule is the point rather than a
coincidence — see :func:`host_is_allowed` and :func:`agent_token_is_valid`, whose ``None`` handling
is deliberately identical.

**The WebSocket ticket is the third member, and it does NOT live here — corrected at c5-2
(2026-08-08).** The previous version of this paragraph said it "joins here"; the spine's module map
disagreed with itself (``state.py # … tickets — in memory`` beside ``security.py # Host validation,
token, ticket mint/consume``), and a single-use consume is a compare-and-set **over the storage**,
so whichever module holds the dict holds the consume. It holds neither here:
:class:`~src.companion.app.state.TicketStore` lives in :mod:`src.companion.app.state`, ruled at
c5-2's Q3 on the ground that **this module's one proven structural property is that it stores
nothing** — ``test_routes_active_deck.py`` AST-walks it for any module-level mutable container,
probed against four planted violations — and that property is the strongest evidence AD-5 has in
the package. What remains true, and is the part that mattered: AD-5 requires the ticket to share
**no storage and no code path** with the agent token, which is why the credential check below
stores nothing and reads exactly one accessor. c5-3 imports the store's accessor to gate the
upgrade; it does not move the store.

**What the check defends against.** Binding the socket to ``127.0.0.1`` stops a request from
*another machine* and nothing else. The attack this module exists to close comes from the machine
itself: a page on ``evil.example.com`` whose DNS is rebound to ``127.0.0.1`` reaches a
loopback-bound port perfectly well, and the browser will happily send it credentials it already
holds. The only thing distinguishing that request from a legitimate one is the ``Host`` header —
the authority the client *believed* it was addressing — which the browser sets and the page cannot
forge.

**Why the match is exact, not parsed.** ``127.1``, ``127.0.0.001``, ``0x7f.1``, ``localhost.`` and
``[::1]`` are all ways of writing something loopback-adjacent, and every parser that tries to
normalise them is a source of bypasses. Comparing the lowercased header against a small literal set
of authorities kills the entire class without a parser: an unrecognised spelling is simply not in
the set. The set is built from the port the runner *actually* bound (read from application state at
request time), because a request naming a different port was aimed at a different server.

**Why this layer sends rather than raises.** Starlette's stack is ``ServerErrorMiddleware`` →
user middleware → ``ExceptionMiddleware`` → router, so a handler registered with
``add_exception_handler`` sits *inside* every user middleware and can never see what one of them
raises. A ``CompanionError`` raised here reaches the caller as ``500 internal_error`` plus a false
``ERROR`` traceback — a routine security rejection reported as a backend bug. So the middleware
calls :func:`~src.companion.app.errors.error_response` and sends the body itself; that keeps the
wire shape byte-identical to every other typed 400 in the app, since it is the same construction
site.
"""

import logging
import secrets
from collections.abc import Iterable
from typing import Annotated

from fastapi import Depends, FastAPI
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from src.companion.app.errors import CompanionError, error_response

logger = logging.getLogger(__name__)

ALLOWED_HOSTNAMES: frozenset[str] = frozenset({"127.0.0.1", "localhost"})
"""The only two host names a legitimate caller can have addressed this process by.

``127.0.0.1`` is what :data:`~src.companion.app.server.HOST` binds and what the launch line prints;
``localhost`` is what a human types. Nothing else resolves to a socket this process owns.
"""

_DEFAULT_HTTP_PORT = 80
"""The port an HTTP client omits from ``Host`` — the one case where a bare authority is honest."""

_MAX_LOGGED_HOST = 100
"""Precision cap on the attacker-controlled values (``Host``, path) written to the rejection log;
they are truncated rather than echoed in full. The cap bounds the ``%r`` output, whose opening
quote counts toward it, so at most 99 characters of the value itself survive."""

_VALIDATED_SCOPE_TYPES = frozenset({"http", "websocket"})
"""The scope types that carry a ``Host``. Everything else (``lifespan``) passes through untouched —
a ``lifespan`` scope has no ``headers`` key at all, and failing on it would fail during startup,
where the error is least legible."""


def allowed_authorities(port: int) -> frozenset[str]:
    """Return every authority string that legitimately addresses this process on *port*.

    Args:
        port: The port the runner actually bound.

    Returns:
        ``{"127.0.0.1:<port>", "localhost:<port>"}``, plus the bare host names when *port* is 80,
        because an HTTP client omits the default port from ``Host``.

    Example:
        >>> sorted(allowed_authorities(8765))
        ['127.0.0.1:8765', 'localhost:8765']
    """
    authorities = {f"{hostname}:{port}" for hostname in ALLOWED_HOSTNAMES}
    if port == _DEFAULT_HTTP_PORT:
        authorities |= ALLOWED_HOSTNAMES
    return frozenset(authorities)


def host_is_allowed(host: str | None, port: int | None) -> bool:
    """Report whether *host* is an authority this process may answer on *port*.

    The whole accept/reject decision, as a pure function, so the matrix is testable without an ASGI
    stack. The header is compared after ``.strip().lower()`` and by exact string match; nothing is
    resolved, parsed or otherwise normalised (see the module docstring).

    Args:
        host: The ``Host`` header value, or ``None`` when it was absent or ambiguous.
        port: The port from application state, or ``None`` if the runner never bound one.

    Returns:
        ``True`` only for an exact match against :func:`allowed_authorities`. A missing header and a
        missing port both reject: HTTP/1.1 requires ``Host``, and an unbound port means the envelope
        cannot be evaluated — which is a reason to refuse, not to wave the request through.

    Example:
        >>> host_is_allowed("LOCALHOST:8765", 8765)
        True
        >>> host_is_allowed("evil.example.com:8765", 8765)
        False
    """
    if host is None or port is None:
        return False
    return host.strip().lower() in allowed_authorities(port)


_ORIGIN_SCHEME = "http://"
"""The only scheme a page served by this backend can have been loaded over.

c1-3 binds a plain HTTP socket and there is no TLS anywhere in the companion, so an ``https``
origin naming our own authority is *by construction* some other page — a service worker, a proxy,
or an attacker who noticed that allow-lists often forget the scheme. Prefixing the authority set
rather than comparing authorities alone is what keeps the scheme part of the decision.
"""


def allowed_origins(port: int) -> frozenset[str]:
    """Return every origin a page legitimately served by this process can present on *port*.

    **Derived from** :func:`allowed_authorities` **rather than written out again**, and that is the
    whole design: ``Host`` and ``Origin`` are answering two different questions (*what did you
    address* versus *what page is calling*) about the **same** two loopback spellings on the
    **same** bound port. Two hand-written literal sets would be two things to keep in sync, and the
    first divergence would be a silent one — an origin the Host check accepts and this one refuses,
    or worse. Deriving makes agreement a fact rather than a convention, and
    ``test_security.py::TestTheAllowedOrigins`` asserts the derivation from both directions.

    It also inherits the port-80 carve-out for free, which is correct rather than merely
    convenient: RFC 6454's ASCII serialisation omits the default port exactly as an HTTP client
    omits it from ``Host``, so ``http://localhost`` is the *right* spelling on :80 and a wrong one
    everywhere else.

    Args:
        port: The port the runner actually bound.

    Returns:
        ``{"http://127.0.0.1:<port>", "http://localhost:<port>"}``, plus the bare-authority forms
        when *port* is 80.

    Example:
        >>> sorted(allowed_origins(8765))
        ['http://127.0.0.1:8765', 'http://localhost:8765']
    """
    return frozenset(f"{_ORIGIN_SCHEME}{authority}" for authority in allowed_authorities(port))


def origin_is_allowed(origin: str | None, port: int | None) -> bool:
    """Report whether *origin* is a page this process may open a WebSocket for (c5-3, AD-5).

    The upgrade half of the ``Origin`` ruling AD-5 and review finding S-6 both home here. The mint
    (``GET /api/session``) deliberately does **not** check ``Origin`` — c5-2's Q1 — because a
    cross-origin page can issue that ``GET`` but cannot read its response, so it can burn tickets
    and never learn one. The handshake is the other half, and it is the half that matters: a
    WebSocket upgrade is not a fetch, so no preflight and no ``Access-Control-Allow-Origin`` stands
    between a hostile local page and this socket. ``Origin`` is what the browser sets and the page
    cannot forge, so it is the only thing that distinguishes them.

    **Independent of** :func:`host_is_allowed`, **and both are required.** ``Host`` says which
    authority the caller believed it was addressing — it catches DNS rebinding. ``Origin`` says
    which page is doing the calling — it catches the ordinary hostile tab, which addresses
    ``127.0.0.1`` perfectly honestly. Neither implies the other, and the handshake asks both.

    The header is compared after ``.strip().lower()`` and by exact string match against
    :func:`allowed_origins`; nothing is parsed or normalised, for the reason the module docstring
    gives about ``Host``.

    Args:
        origin: The ``Origin`` header value, or ``None`` when it was absent or ambiguous.
        port: The port from application state, or ``None`` if the runner never bound one.

    Returns:
        ``True`` only for an exact match. A missing header rejects (Q4, Brad 2026-08-08): browsers
        always send ``Origin`` on a WebSocket handshake, c5-8's real client sets it explicitly, and
        the fail-closed shape is the one :func:`host_is_allowed` and :func:`agent_token_is_valid`
        already share. A missing port rejects for the same reason it does there — an envelope that
        cannot be evaluated is a reason to refuse.

    Example:
        >>> origin_is_allowed("HTTP://LOCALHOST:8765", 8765)
        True
        >>> origin_is_allowed("http://evil.example.com:8765", 8765)
        False
        >>> origin_is_allowed(None, 8765)
        False
    """
    if origin is None or port is None:
        return False
    return origin.strip().lower() in allowed_origins(port)


def _host_headers(scope: Scope) -> list[str]:
    """Return every ``Host`` header value on *scope*, in arrival order.

    Args:
        scope: An ``http`` or ``websocket`` connection scope.

    Returns:
        The decoded values. ASGI header names are lowercased bytes, so the match is on ``b"host"``;
        values are decoded as latin-1, which is what the ASGI spec and Starlette use.
    """
    raw: Iterable[tuple[bytes, bytes]] = scope["headers"]
    return [value.decode("latin-1") for name, value in raw if name == b"host"]


class HostValidationMiddleware:
    """Refuse any request that did not address this process as loopback on the bound port.

    Pure ASGI rather than ``BaseHTTPMiddleware`` for two reasons: it must see ``websocket`` scopes
    (c5-3's upgrade reuses this check rather than duplicating it, AD-5), and it must be able to send
    the typed body itself rather than raise (see the module docstring).

    Args:
        app: The next application in the ASGI stack.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Validate one connection's ``Host`` and either pass it on or refuse it.

        Args:
            scope: The connection scope. Only ``http`` and ``websocket`` are checked; anything else
                is forwarded untouched.
            receive: The ASGI receive channel.
            send: The ASGI send channel. On refusal the response is written here directly and the
                inner app is **never** called — on ``http`` that would send a second response, and
                on ``websocket`` it would hand a denied connection to a route expecting to accept
                it.
        """
        if scope["type"] not in _VALIDATED_SCOPE_TYPES:
            await self.app(scope, receive, send)
            return

        # Function-local: main.py imports install_security in its top-level import block, above
        # where bound_port is defined, so the module-level form of this import is a genuine
        # circular-import failure in both directions. bound_port is the accessor c1-3 built for
        # exactly this caller; re-reading app.state here instead would be a second construction
        # site for the same value.
        from src.companion.app.main import bound_port

        port = bound_port(scope["app"])
        hosts = _host_headers(scope)
        # More than one Host is ambiguous by construction: a reader taking the first and a reader
        # taking the last would disagree about what was addressed. Refuse rather than pick. No
        # claim is made about whether uvicorn's parser would have rejected it first.
        host = hosts[0] if len(hosts) == 1 else None

        if host_is_allowed(host, port):
            await self.app(scope, receive, send)
            return

        # WARNING because a refused authority is the one event here an operator needs to see, and
        # that judgement is what fixes the level — c1-9's entry point now configures the root
        # logger at INFO on stderr, so an INFO line would reach the user too, just alongside
        # ordinary chatter. The precision on the %r conversions truncates both attacker-controlled
        # values while keeping the arguments lazy.
        logger.warning(
            "Rejecting %s request for %.*r: Host %.*r (%d header(s)) is not an allowed authority "
            "for bound port %r",
            scope["type"],
            _MAX_LOGGED_HOST,
            scope.get("path"),
            _MAX_LOGGED_HOST,
            hosts[0] if hosts else None,
            len(hosts),
            port,
        )

        if scope["type"] == "websocket":
            # Closing before accepting is the ASGI-legal denial; uvicorn renders it as an HTTP 403
            # handshake failure (uvicorn/protocols/websockets/websockets_impl.py).
            await send({"type": "websocket.close", "code": 1008})
            return
        await error_response("invalid_request")(scope, receive, send)


_AUTHORIZATION_HEADER = "authorization"
"""The header the agent presents its credential in.

Read from ``request.headers`` inside the dependency rather than declared as an
``Annotated[str, Header()]`` parameter or via a FastAPI security class, and both halves of that are
deliberate (Q4, Brad 2026-08-01):

* **Not a declared parameter**, because a declared header lands in ``app.openapi()`` and therefore
  in ``ui/src/api/types.d.ts`` and ``/docs`` — teaching a browser-facing document the name of a
  credential the browser must never hold (AD-5). It would also route a *missing* header through
  parameter validation, answering ``invalid_request`` where the honest answer is ``forbidden``.
* **Not** ``HTTPBearer``/``APIKeyHeader``, because those raise their own ``HTTPException``, which
  lands in :func:`~src.companion.app.errors.http_exception_handler` and becomes ``invalid_request``
  at *their* chosen status — silently bypassing the one rejection vocabulary AD-16 exists to keep.
  They also add a ``securitySchemes`` component and a per-operation ``security`` block to the
  artifact.
"""

_BEARER_SCHEME = "bearer"
"""The auth-scheme half of ``Authorization: Bearer <token>``, matched case-insensitively per
RFC 9110 §11.1. Standard spelling, so c6-1 sends what every HTTP client already knows how to
send."""


def presented_credential(header_value: str | None) -> str | None:
    """Extract the bearer credential from an ``Authorization`` header value.

    Pure and total, so the parsing matrix is testable without an ASGI stack — and separate from
    :func:`agent_token_is_valid` so that "what did they send" and "is it right" cannot be confused
    for one another.

    Args:
        header_value: The raw header, or ``None`` when it was absent.

    Returns:
        The credential, or ``None`` when there was nothing usable to compare: no header, a
        non-bearer scheme, or a bearer scheme with an empty credential. Every one of those is
        equivalent as far as the *comparison* is concerned, and collapsing them here is what keeps
        the comparison site down to one branch. (The rejection *log* distinguishes a header that
        failed to parse from no header at all — it reads the raw header separately, because that
        distinction is diagnostic even though the verdict is the same.)

    Example:
        >>> presented_credential("Bearer abc123")
        'abc123'
        >>> presented_credential("Basic abc123") is None
        True
    """
    if header_value is None:
        return None
    scheme, separator, credential = header_value.partition(" ")
    if not separator or scheme.lower() != _BEARER_SCHEME:
        return None
    # Strip before testing for emptiness: "Bearer   " is a present header carrying no credential,
    # and must reduce to the same None as no header at all rather than to a whitespace "token".
    return credential.strip() or None


def agent_token_is_valid(presented: str | None, expected: str | None) -> bool:
    """Report whether *presented* is the credential this process minted.

    The whole accept/reject decision as a pure function, mirroring :func:`host_is_allowed` — which
    is not a stylistic echo but the same safety property stated twice.

    **Fails closed on either side being absent**, and that is the load-bearing line in this module.
    :func:`~src.companion.app.main.agent_token` returns ``None`` before the lifespan has run, and a
    caller can present no header — which is also naturally ``None``. Any implementation that
    compared the two directly would evaluate ``None == None`` as ``True`` and **authenticate every
    request against an unstarted app**. The guard below is what stops that, and
    ``test_routes_active_deck.py`` drives a real ``build_app()`` whose lifespan never ran to prove
    it rather than unit-testing this function alone.

    **Empty counts as absent**, for the same reason and not merely for tidiness. ``""`` and
    ``""`` are equal, so a length-only guard would let two empty credentials authenticate each
    other — the same fail-open shape as ``None``/``None`` wearing a different spelling. It is
    unreachable through the shipped route (:func:`presented_credential` collapses an empty
    credential to ``None``, and a minted token is never empty), which is exactly why it was worth
    closing here: an unreachable hole is one refactor away from being reachable. **c5-5 arrived as
    that next caller and added no comparison at all** — ``POST /agent/events`` annotates
    :data:`AgentToken` and reads nothing about credentials itself, so this function still has
    exactly one call site and the hole stayed closed by construction rather than by review.

    **Compared as bytes, deliberately.** ``secrets.compare_digest`` accepts ``str`` only when *both*
    arguments are ASCII-only and raises ``TypeError`` otherwise. Header values decode as latin-1, so
    a credential containing ``ü`` is trivially reachable — and under a ``str`` comparison it would
    raise, be caught by :class:`~src.companion.app.errors.UnhandledErrorMiddleware`, and report a
    caller-controlled input as ``500 internal_error``: a false backend-bug report anyone could
    trigger. Encoding both sides first makes a non-ASCII credential an ordinary non-match. (The
    encoding cannot cause a false *accept*: the minted token is
    ``secrets.token_urlsafe``, always ASCII, where UTF-8 and latin-1 agree byte-for-byte.)

    ``compare_digest`` rather than ``==`` for the constant-time comparison. The exposure is small —
    a loopback port behind the ``Host`` envelope — but it costs nothing and the alternative is
    justifying ``==`` in a review.

    Args:
        presented: The credential the caller sent, from :func:`presented_credential`.
        expected: The credential this process minted, from
            :func:`~src.companion.app.main.agent_token`.

    Returns:
        ``True`` only when both are present and equal.

    Example:
        >>> agent_token_is_valid(None, None)
        False
        >>> agent_token_is_valid("", "")
        False
        >>> agent_token_is_valid("abc", "abc")
        True
    """
    if not presented or not expected:
        return False
    return secrets.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


async def require_agent_token(request: Request) -> None:
    """Refuse the request unless it presents this process's agent credential (NFR-01, AD-5).

    Raising is correct here and does not contradict c1-5's send-don't-raise ruling: a dependency is
    solved inside the router, which is *inside* Starlette's ``ExceptionMiddleware``, so a
    :class:`~src.companion.app.errors.CompanionError` raised from here reaches its handler and
    answers with its own token. The middleware above sits on the other side of that boundary — the
    difference is position in the stack, not the exception (the same reasoning
    :func:`~src.companion.app.deps.get_session` records).

    **What the rejection log may say.** The path and the fact, and nothing else. Neither the
    presented value nor the expected one is logged, at any level: the expected value is the
    credential itself (AD-5 bans it from logs outright) and the presented value is attacker
    controlled — logging it would write an arbitrary string into an operator's console and, if the
    caller guessed nearly right, park a near-miss credential in a file. *How* the credential failed
    — never sent, sent but unparseable, or parsed and wrong — is safe and genuinely diagnostic: it
    separates "the tool never sent one" from "the tool's header is malformed" from "the tool sent a
    stale one", which are three different c6-1 debugging sessions — so that one word is logged and
    no more.

    Args:
        request: The request being served; the header and the app are both read from it.

    Returns:
        ``None``. The dependency is used for its effect — no value is injected, because a route
        that has been authorised has nothing further to learn from the credential.

    Raises:
        CompanionError: ``forbidden`` when the credential is missing, malformed or wrong, and
            equally when this app has minted no token at all.
    """
    # Function-local, matching the bound_port import above and for the same reason: main.py imports
    # this module at its top level, so a module-level import here is a genuine circular-import
    # failure in both directions.
    from src.companion.app.main import agent_token

    header = request.headers.get(_AUTHORIZATION_HEADER)
    presented = presented_credential(header)
    if agent_token_is_valid(presented, agent_token(request.app)):
        return
    # Three words, still no values: "invalid" (a bearer credential that failed the comparison),
    # "malformed" (a header that did not parse to one — wrong scheme, empty credential), "no"
    # (no header at all). Collapsing "malformed" into "no" mislabels exactly the c6-1 case the
    # docstring promises to serve: a client with a header-construction bug *is* presenting
    # something (c3-4 review).
    logger.warning(
        "Refusing %s %s: %s agent credential",
        request.method,
        request.url.path,
        "invalid" if presented is not None else ("malformed" if header is not None else "no"),
    )
    raise CompanionError("forbidden")


AgentToken = Annotated[None, Depends(require_agent_token)]
"""The annotation every agent-authenticated handler writes, and the only one it should.

Story c3-4 (``PUT /api/active-deck``) is the first caller; c5-5's ``POST /agent/events`` is the
second and **inherited the whole contract** — the header spelling, the fail-closed comparison and
the ``forbidden`` token — rather than writing a second check. A route annotates a parameter with
this and reads nothing about credentials itself.

Measured at c5-5, because "inherits the whole contract" is the kind of claim that decays quietly:
``test_routes_agent_events.py`` AST-scans that route module and fails if it so much as names
``presented_credential``, ``agent_token_is_valid``, ``require_agent_token``, ``agent_token``,
``compare_digest`` or ``Header``. Two callers, still one comparison site.

Injects ``None`` on purpose: the dependency exists for its **effect**, and a route that has been
authorised has nothing further to learn from the credential. Handing the token to the endpoint
would put the credential in a local variable one careless f-string away from a log line or a
response body — the exact leak AD-5 exists to prevent.

Example:
    >>> from typing import get_args
    >>> get_args(AgentToken)[0] is type(None)
    True
"""


def install_security(app: FastAPI) -> None:
    """Install the security envelope on *app*, in one call.

    Call this **before** ``install_error_handling(app)`` in ``build_app()``. ``user_middleware[0]``
    is the most recently added middleware, so installing security first leaves
    :class:`~src.companion.app.errors.UnhandledErrorMiddleware` outermost — which is what makes a
    fault in the ``Host`` check itself answer as a typed ``500 internal_error`` rather than an
    untyped traceback. That net covers ``http`` scopes only: the error middleware passes
    ``websocket`` scopes straight through, because there is no JSON body to send on those.

    **c5-3 ruled the gap that left, and ruled it closed locally (Q6, Brad 2026-08-08).** The
    previous version of this paragraph said a fault while validating a handshake "escapes raw —
    acceptable while nothing on the ws path can raise, and c5-3 owns the question when it adds the
    upgrade". Something on the ws path can raise now, and nothing escapes:
    :func:`~src.companion.app.ws.websocket_upgrade` catches its own faults on both sides of
    ``accept`` and closes ``1011``. The error middleware **stays http-only** — extending it to
    websocket scopes would give one middleware a second shape for exactly one caller, and that
    shape would have to duplicate the handler's own pre-accept/post-accept distinction anyway.

    **Installs the middleware half only.** The agent credential (:data:`AgentToken`) is a
    per-route dependency and is wired by the routes that want it, not from here — c3-4's ``GET
    /api/active-deck`` and its ``PUT`` sit in one module with different answers, which is a
    decision a route declares rather than one a middleware re-derives from a path list. The
    previous version of this paragraph promised the token would land "here beside it"; c3-4 built
    it and ruled otherwise, two stories ahead of the c5-5 that was scheduled to. **c5-5 confirmed
    the ruling by using it**: its route annotates :data:`AgentToken` and this function gained not
    one line.

    **A prediction this docstring made twice, and got wrong twice — now settled by measurement.**
    The original said c5-2's WebSocket ticket "is still to come and is genuinely middleware-shaped
    (it gates a handshake, not an endpoint), so this remains the one wiring call and ``build_app()``
    never grows a second security line." c5-2 falsified half of it: its **mint** is an ordinary
    credential-free endpoint, so it grew ``build_app()`` by an ``include_router`` and put its store
    on the lifespan. c5-2's replacement text kept the other half — that the **consume** "does gate a
    handshake and is c5-3's" — and c5-3 falsified that too: the upgrade is a plain
    ``@router.websocket`` route (:mod:`src.companion.app.ws`), added by a third
    ``include_router``.

    The lesson, stated so c5-5 does not inherit the same mistake: *gating a handshake* describes
    what a check does, and *middleware* describes where it has to live. They are independent. A
    WebSocket route reads its own headers and closes its own connection, so it needs no middleware
    position to gate from — only the ``Host`` check, which must see **every** scope including ones
    no route claims, genuinely needs one.

    **c5-5 is in, and it split both ways — which is the lesson above paying out.** Its ``POST
    /agent/events`` is an ordinary route with an ``AgentToken`` dependency, so it grew
    ``build_app()`` by a fourth ``include_router`` and touched nothing here. Its **body cap** is
    genuinely middleware-shaped and for exactly the reason this paragraph gives: the cap must see
    every ``http`` scope before anything parses it, which is a position no route can occupy. So
    ``build_app()`` did grow a second middleware line — but it is ``install_body_cap``, not a
    security line, because a resource ceiling is not a statement about who the caller is. What
    survives unbroken across all three corrections: **this is still the one *security* wiring
    call**, and the store it does not hold is in :mod:`src.companion.app.state` (c5-2, Q3).

    Args:
        app: The application to install onto.
    """
    app.add_middleware(HostValidationMiddleware)

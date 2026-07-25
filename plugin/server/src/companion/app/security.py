"""The localhost-only security envelope: what is allowed to address this process (AD-5, NFR-01).

This module is the ``Host`` third of the envelope. Stories c5-2 and c5-5 add the WebSocket ticket
and the agent token here beside it, and :func:`install_security` is the one wiring call all three
share, so ``build_app()`` never grows a second security line.

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
from collections.abc import Iterable

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from src.companion.app.errors import error_response

logger = logging.getLogger(__name__)

ALLOWED_HOSTNAMES: frozenset[str] = frozenset({"127.0.0.1", "localhost"})
"""The only two host names a legitimate caller can have addressed this process by.

``127.0.0.1`` is what :data:`~src.companion.app.server.HOST` binds and what the launch line prints;
``localhost`` is what a human types. Nothing else resolves to a socket this process owns.
"""

_DEFAULT_HTTP_PORT = 80
"""The port an HTTP client omits from ``Host`` — the one case where a bare authority is honest."""

_MAX_LOGGED_HOST = 100
"""Cap on the ``Host`` value written to the log; it is attacker-controlled input on its way into
a file, so it is truncated rather than echoed in full."""

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

        # WARNING because no story has configured a root logger yet (c1-9 owns that) and
        # logging.lastResort surfaces WARNING+ to stderr — an INFO line would vanish in every real
        # run, and this is the one event an operator needs to see. The precision on %r truncates
        # the attacker-controlled value while keeping the argument lazy.
        logger.warning(
            "Rejecting %s request for %r: Host %.*r (%d header(s)) is not an allowed authority "
            "for bound port %r",
            scope["type"],
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


def install_security(app: FastAPI) -> None:
    """Install the security envelope on *app*, in one call.

    Call this **before** ``install_error_handling(app)`` in ``build_app()``. ``user_middleware[0]``
    is the most recently added middleware, so installing security first leaves
    :class:`~src.companion.app.errors.UnhandledErrorMiddleware` outermost — which is what makes a
    fault in the ``Host`` check itself answer as a typed ``500 internal_error`` rather than an
    untyped traceback.

    Stories c5-2 (ticket mint) and c5-5 (agent token) add their pieces here, so the wiring in
    ``build_app()`` never grows a second security line.

    Args:
        app: The application to install onto.
    """
    app.add_middleware(HostValidationMiddleware)

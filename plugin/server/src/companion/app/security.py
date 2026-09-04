"""The localhost-only security envelope: what may address this process, and who may write (AD-5).

Two independent checks. The ``Host`` check (:class:`HostValidationMiddleware`) is envelope-wide,
applied to every request and WebSocket handshake, and answers *which authority the caller believed
it was addressing*. The agent credential (:data:`AgentToken`) is a per-route dependency on the
endpoints that write and answers *who the caller is*; a route declares it, because a credential-free
``GET`` and a guarded ``PUT`` share one module. Both fail closed on a missing input. The WebSocket
ticket store is deliberately not here: AD-5 requires the ticket to share no storage and no code path
with the agent token, and this module's proven structural property is that it stores nothing
(``test_routes_active_deck.py`` AST-walks it for module-level mutable containers).

Binding to ``127.0.0.1`` stops requests from another machine and nothing else; a DNS-rebound page
reaches a loopback port, and the ``Host`` header the browser sets and the page cannot forge is the
only thing distinguishing it. The match is exact and never parsed: ``127.1``, ``0x7f.1`` and
``[::1]`` are loopback-adjacent spellings, every normaliser is a source of bypasses, and an
unrecognised spelling is simply not in the set built from the port the runner actually bound. The
middleware sends rather than raises, because Starlette's ``ExceptionMiddleware`` sits inside every
user middleware and an exception here would surface as ``500 internal_error``.
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
"""The only two host names a legitimate caller can have addressed this process by."""

_DEFAULT_HTTP_PORT = 80
"""The port an HTTP client omits from ``Host``, the one case where a bare authority is honest."""

_MAX_LOGGED_HOST = 100
"""Precision cap on attacker-controlled values in the rejection log (``%r``'s quote counts)."""

_VALIDATED_SCOPE_TYPES = frozenset({"http", "websocket"})
"""Scope types carrying a ``Host``; a ``lifespan`` scope has no ``headers`` key and passes."""


def allowed_authorities(port: int) -> frozenset[str]:
    """Return ``{"127.0.0.1:<port>", "localhost:<port>"}``, plus the bare names on port 80."""
    authorities = {f"{hostname}:{port}" for hostname in ALLOWED_HOSTNAMES}
    if port == _DEFAULT_HTTP_PORT:
        authorities |= ALLOWED_HOSTNAMES
    return frozenset(authorities)


def host_is_allowed(host: str | None, port: int | None) -> bool:
    """Report whether *host* is an authority this process may answer on *port*.

    Pure, so the matrix is testable without an ASGI stack. The header is compared after
    ``.strip().lower()`` by exact string match; nothing is resolved or normalised. A missing header
    and a missing port both reject: an envelope that cannot be evaluated is a reason to refuse.
    """
    if host is None or port is None:
        return False
    return host.strip().lower() in allowed_authorities(port)


_ORIGIN_SCHEME = "http://"
"""The only scheme a served page can have: there is no TLS, so an ``https`` origin is foreign."""


def allowed_origins(port: int) -> frozenset[str]:
    """Return every origin a page legitimately served by this process can present on *port*.

    Derived from :func:`allowed_authorities` so ``Host`` and ``Origin`` cannot silently diverge
    (``test_security.py::TestTheAllowedOrigins``); the port-80 carve-out matches RFC 6454.
    """
    return frozenset(f"{_ORIGIN_SCHEME}{authority}" for authority in allowed_authorities(port))


def origin_is_allowed(origin: str | None, port: int | None) -> bool:
    """Report whether *origin* is a page this process may open a WebSocket for (AD-5).

    A WebSocket upgrade is not a fetch, so no preflight stands between a hostile local page and this
    socket; ``Origin`` is what the browser sets and the page cannot forge. Independent of
    :func:`host_is_allowed` and both are required: ``Host`` catches DNS rebinding, ``Origin`` the
    hostile tab addressing ``127.0.0.1`` honestly. Exact match; a missing header or port rejects.
    """
    if origin is None or port is None:
        return False
    return origin.strip().lower() in allowed_origins(port)


def _host_headers(scope: Scope) -> list[str]:
    """Return every ``Host`` value on *scope* in arrival order, decoded as latin-1 per ASGI."""
    raw: Iterable[tuple[bytes, bytes]] = scope["headers"]
    return [value.decode("latin-1") for name, value in raw if name == b"host"]


class HostValidationMiddleware:
    """Refuse any request that did not address this process as loopback on the bound port.

    Pure ASGI rather than ``BaseHTTPMiddleware``: it must see ``websocket`` scopes and must send
    the typed body itself rather than raise (see the module docstring).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Validate one connection's ``Host``; on refusal the inner app is never called."""
        if scope["type"] not in _VALIDATED_SCOPE_TYPES:
            await self.app(scope, receive, send)
            return

        # Function-local: main.py imports install_security at its top level, so a module-level
        # import here is a circular-import failure in both directions.
        from src.companion.app.main import bound_port

        port = bound_port(scope["app"])
        hosts = _host_headers(scope)
        # More than one Host is ambiguous by construction: refuse rather than pick.
        host = hosts[0] if len(hosts) == 1 else None

        if host_is_allowed(host, port):
            await self.app(scope, receive, send)
            return

        # WARNING: a refused authority is the one event an operator needs to see. %.*r truncates.
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
            # Closing before accepting is the ASGI-legal denial; uvicorn renders it as HTTP 403.
            await send({"type": "websocket.close", "code": 1008})
            return
        await error_response("invalid_request")(scope, receive, send)


_AUTHORIZATION_HEADER = "authorization"
"""The header the agent presents its credential in.

Read inside the dependency, never declared as a ``Header()`` parameter or a FastAPI security class:
a declared header lands in ``app.openapi()`` and so in the browser-facing ``types.d.ts`` (AD-5).
"""

_BEARER_SCHEME = "bearer"
"""The scheme in ``Authorization: Bearer <token>``, matched case-insensitively per RFC 9110."""


def presented_credential(header_value: str | None) -> str | None:
    """Extract the bearer credential from an ``Authorization`` header value, or ``None``.

    Separate from :func:`agent_token_is_valid` so "what did they send" and "is it right" cannot be
    confused. No header, a non-bearer scheme and an empty credential all collapse to ``None``.
    """
    if header_value is None:
        return None
    scheme, separator, credential = header_value.partition(" ")
    if not separator or scheme.lower() != _BEARER_SCHEME:
        return None
    # "Bearer   " is a present header carrying no credential and must reduce to None.
    return credential.strip() or None


def agent_token_is_valid(presented: str | None, expected: str | None) -> bool:
    """Report whether *presented* is the credential this process minted.

    Fails closed when either side is absent or empty, the load-bearing line in this module: the
    token is ``None`` before the lifespan has run and a caller can present no header, so a direct
    comparison would authenticate every request against an unstarted app
    (``test_routes_active_deck.py`` drives one). Compared as bytes because ``compare_digest`` raises
    ``TypeError`` on non-ASCII ``str``, reachable through a latin-1 header; the minted token is
    ASCII, so encoding cannot cause a false accept. ``compare_digest``, not ``==``: constant time.
    """
    if not presented or not expected:
        return False
    return secrets.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


async def require_agent_token(request: Request) -> None:
    """Refuse the request unless it presents this process's agent credential (NFR-01, AD-5).

    Raising is correct here: a dependency is solved inside Starlette's ``ExceptionMiddleware``, so
    the error reaches its handler. The log names the path and how the credential failed, never the
    presented or expected value (AD-5).

    Raises:
        CompanionError: ``forbidden`` when the credential is missing, malformed or wrong, and
            equally when this app has minted no token at all.
    """
    # Function-local for the same circular-import reason as bound_port above.
    from src.companion.app.main import agent_token

    header = request.headers.get(_AUTHORIZATION_HEADER)
    presented = presented_credential(header)
    if agent_token_is_valid(presented, agent_token(request.app)):
        return
    # "invalid" (failed the comparison), "malformed" (did not parse), "no" (no header): still no
    # values, but three distinct leaf-client debugging sessions.
    logger.warning(
        "Refusing %s %s: %s agent credential",
        request.method,
        request.url.path,
        "invalid" if presented is not None else ("malformed" if header is not None else "no"),
    )
    raise CompanionError("forbidden")


AgentToken = Annotated[None, Depends(require_agent_token)]
"""The annotation every agent-authenticated handler writes, and the only one it should.

A route annotates a parameter with this and reads nothing about credentials itself, so there is one
comparison site (``test_routes_agent_events.py`` AST-scans the ingest route for any other). It
injects ``None`` on purpose: a token in a local variable is one f-string away from a log (AD-5).
"""


def install_security(app: FastAPI) -> None:
    """Install the ``Host`` middleware on *app*: the one security wiring call.

    Call it before ``install_error_handling(app)`` so the error middleware ends up outermost and a
    fault in the ``Host`` check answers as a typed ``500`` on ``http`` scopes. The agent credential
    is a per-route dependency wired by the routes that want it, not from here.
    """
    app.add_middleware(HostValidationMiddleware)

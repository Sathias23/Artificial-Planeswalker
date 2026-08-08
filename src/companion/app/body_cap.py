"""The pre-parse request-body ceiling — one mechanism, every body route (AD-7, c5-5).

``payload_too_large`` was declared at c1-4 and had **no producer** until this module existed;
:data:`~src.companion.contracts._MAX_ENVELOPE_BYTES` was a constant nothing read. This is what
makes both real, and the shape it takes was ruled at c5-5's Q2 (Brad, 2026-08-08).

**Why it cannot be a pydantic validator.** A model validator runs *after* the body has been read
and parsed, so it could reject an oversized envelope but could not stop an unauthenticated caller
from making the process buffer it first — and how much an unauthenticated caller can make this
process buffer is the entire property AD-7's ceiling exists to bound. The check has to happen
before parsing, which means before FastAPI is involved at all, which means here.

**Why it cannot be a dependency either.** A dependency is solved inside the router, one route at a
time, so a cap shaped that way would be duplicated per endpoint and — worse — would leave the hole
*open by default* on every body route a later story adds. ``deferred-work.md``'s entry (from c3-4's
Q4) asks for one mechanism covering ``POST /agent/events`` **and** ``PUT /api/active-deck``, and
one mechanism is what this is: neither route contains a line about size.

**Why it sends rather than raises** (c1-5's ruling, restated in ``errors.py``). Starlette's stack is
``ServerErrorMiddleware`` → user middleware → ``ExceptionMiddleware`` → router, so a handler
registered with ``add_exception_handler`` sits *inside* every user middleware and can never see what
one of them raises. A :class:`~src.companion.app.errors.CompanionError` raised here would reach the
caller as ``500 internal_error`` with a false traceback — a routine, caller-triggered refusal
reported as a backend bug. So this calls :func:`~src.companion.app.errors.error_response` and writes
the body itself, through the same construction site every other typed failure uses, which is what
keeps the wire shape (including ``Cache-Control: no-store``) byte-identical to the rest of the app.

**Two bounds, and the second is the one that holds.** ``Content-Length`` is checked first because
it lets an honest client be refused without transferring anything — but a caller controls its own
headers, so a declared length is a claim, not a fact. The counted-bytes bound is what actually
enforces the ceiling: bytes are accumulated as they arrive and the refusal fires the moment the
running total crosses the cap, so a body that lies about its size is refused on the strength of what
it actually sent.

**Rejected, never truncated.** An over-cap request's body is discarded and the inner application is
**never called** — there is no path here that hands a partial body to a route. A truncated payload
is a payload that renders wrong without saying so (``_MAX_ENVELOPE_BYTES``'s own docstring), and a
half-delivered event list would be exactly that.

**What it does not touch.** ``websocket`` and ``lifespan`` scopes pass straight through: the cap is
a statement about request bodies, and a WebSocket frame is not one (frame-level bounds, if they are
ever wanted, are a different decision on a different wire). So does any ``http`` request that
announces no body at all — the six body-less ``GET``s in this app never notice this middleware
exists, which is the same distinction the ``413`` schema curation makes in ``build_app()``.

**Where it sits.** Installed by :func:`install_body_cap` *before* the ``Host`` check and the error
middleware, so it ends up **inside** both: a fault here is still typed as a ``500`` by the outermost
middleware, and a request that never legitimately addressed this process is refused by ``Host``
before its body is read at all. Inside the routers, so no route declares or configures it.
"""

import logging

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.companion.app.errors import error_response
from src.companion.contracts import _MAX_ENVELOPE_BYTES

logger = logging.getLogger(__name__)

_CONTENT_LENGTH = b"content-length"
"""The declared body size, as an ASGI header name. Lowercased bytes, per the ASGI spec."""

_TRANSFER_ENCODING = b"transfer-encoding"
"""Read only to recognise a chunked body, which announces its size nowhere."""

_CHUNKED = "chunked"
"""The transfer coding that means "a body is coming and its length is not declared"."""


def _header(scope: Scope, name: bytes) -> bytes | None:
    """Return the last value of header *name* on *scope*, or ``None`` when it is absent.

    Args:
        scope: An ``http`` connection scope.
        name: The lowercased header name to look for.

    Returns:
        The raw value, or ``None``. The **last** occurrence wins rather than the first, which is
        the conservative reading for a size claim: a caller that sent two ``Content-Length``
        headers gets no say in which one this believes, and the counted-bytes bound below is
        authoritative either way.
    """
    found: bytes | None = None
    for header_name, value in scope["headers"]:
        if header_name == name:
            found = value
    return found


def _declared_length(scope: Scope) -> int | None:
    """Return the body size *scope* declares, or ``None`` when it declares none intelligibly.

    Args:
        scope: An ``http`` connection scope.

    Returns:
        The parsed ``Content-Length``, or ``None`` when the header is absent or unparseable. An
        unparseable value is deliberately **not** a refusal: it is not this middleware's job to
        police header syntax, and treating it as "size unknown" routes the request to the
        counted-bytes bound, which is the check that cannot be lied to.
    """
    raw = _header(scope, _CONTENT_LENGTH)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _announces_a_body(scope: Scope) -> bool:
    """Report whether *scope* says a request body is coming.

    Args:
        scope: An ``http`` connection scope.

    Returns:
        ``True`` if a ``Content-Length`` header is present at all — zero, negative, or
        unparseable included, since any of those routes to the counted-bytes bound rather than
        being trusted — or a chunked transfer coding is declared. ``False`` only when neither
        signal is present, which is what lets a body-less ``GET`` skip this middleware's
        machinery entirely rather than waiting on a ``receive`` it was never going to read.
    """
    if _header(scope, _CONTENT_LENGTH) is not None:
        return True
    encoding = _header(scope, _TRANSFER_ENCODING)
    return encoding is not None and _CHUNKED in encoding.decode("latin-1").lower()


class BodyCapMiddleware:
    """Refuse any request whose body exceeds the envelope ceiling, before anything parses it.

    Args:
        app: The next application in the ASGI stack.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Bound one request's body, then either pass it on or refuse it.

        Args:
            scope: The connection scope. Only ``http`` scopes that announce a body are bounded;
                ``websocket``, ``lifespan`` and body-less requests are forwarded untouched.
            receive: The ASGI receive channel, drained here and replayed to the inner application.
            send: The ASGI send channel. On refusal the typed body is written here directly and the
                inner application is **never** called — calling it would either send a second
                response or hand a route a body this middleware has already decided is illegal.
        """
        if scope["type"] != "http" or not _announces_a_body(scope):
            await self.app(scope, receive, send)
            return

        declared = _declared_length(scope)
        if declared is not None and declared > _MAX_ENVELOPE_BYTES:
            # The courtesy bound: an honest client is refused without transferring the body at all.
            await self._refuse(scope, receive, send, declared, "declared")
            return

        buffered: list[Message] = []
        counted = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                # A disconnect (or anything else) mid-body: nothing to cap, and nothing this
                # middleware should decide. Hand it on with what has been read so far.
                buffered.append(message)
                break
            counted += len(message.get("body", b""))
            if counted > _MAX_ENVELOPE_BYTES:
                # The bound that holds. Fires on bytes actually received, so a caller that
                # understated its Content-Length is refused on the strength of what it sent —
                # and the buffer is dropped rather than passed on, because a truncated payload is
                # a payload that renders wrong without saying so.
                await self._refuse(scope, receive, send, counted, "received")
                return
            buffered.append(message)
            if not message.get("more_body", False):
                break

        await self.app(scope, self._replay(buffered, receive), send)

    @staticmethod
    def _replay(buffered: list[Message], receive: Receive) -> Receive:
        """Return a ``receive`` that hands back *buffered* first, then defers to *receive*.

        The inner application must see the body exactly as it was sent — same messages, same
        ``more_body`` flags, same order — because this middleware read it only to measure it.

        Args:
            buffered: The messages already drained, in arrival order.
            receive: The original channel, for anything that arrives afterwards (a disconnect,
                most often).

        Returns:
            An ASGI receive callable.
        """
        pending = iter(buffered)

        async def replayed() -> Message:
            message = next(pending, None)
            if message is None:
                return await receive()
            return message

        return replayed

    @staticmethod
    async def _refuse(scope: Scope, receive: Receive, send: Send, size: int, basis: str) -> None:
        """Answer ``413`` and stop, without raising and without reading any more of the body.

        Args:
            scope: The connection scope being refused.
            receive: The ASGI receive channel, handed to the response.
            send: The ASGI send channel the typed body is written to.
            size: The size that breached the cap.
            basis: Which bound fired — ``"declared"`` or ``"received"``.
        """
        # INFO rather than WARNING: an over-cap push is a caller sending too much, not an attack on
        # the envelope the way a refused `Host` is — the `Host` check's WARNING is calibrated for
        # an operator who needs to see it. The path is included because it separates the two body
        # endpoints; no header, credential or body content is logged, at any level.
        logger.info(
            "Refusing %s %s: %s body of %d bytes exceeds the envelope cap",
            scope.get("method"),
            scope.get("path"),
            basis,
            size,
        )
        await error_response("payload_too_large")(scope, receive, send)


def install_body_cap(app: FastAPI) -> None:
    """Install the request-body ceiling on *app*, in one call.

    Call this **before** :func:`~src.companion.app.security.install_security`, so the ``Host`` check
    and the error middleware both end up outside it: a request that never legitimately addressed
    this process is refused before its body is read, and a fault in the counting itself is still
    typed as a ``500`` rather than escaping as a traceback.

    Args:
        app: The application to install onto.
    """
    app.add_middleware(BodyCapMiddleware)

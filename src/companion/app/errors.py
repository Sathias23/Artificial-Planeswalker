"""Every non-2xx the companion can produce, funnelled into one typed body (AD-16).

Three rules hold this module together, and each of them is a decision a later story inherits rather
than re-makes:

* **The status is derived from the token, never chosen at the call site.** :data:`STATUS_BY_REASON`
  is the single place in the codebase where a reason meets a status code. An endpoint raises
  :class:`CompanionError` with a token and is done; it cannot pick a status, so it cannot pick a
  *different* status than the one the UI was built against.

* **The unhandled-exception path is middleware, not** ``add_exception_handler(Exception, …)``.
  Starlette's ``ServerErrorMiddleware`` writes its response and then **always re-raises**
  (``starlette/middleware/errors.py``: "We always continue to raise the exception"), so a 500
  handler gives the caller the original exception instead of a body — and, under uvicorn, the
  traceback AD-16 forbids reaching the client. :class:`UnhandledErrorMiddleware` sits *inside*
  ``ServerErrorMiddleware`` and *outside* ``ExceptionMiddleware``, catches the same exceptions and
  returns without re-raising. ``ServerErrorMiddleware`` stays as the outermost net for anything
  this middleware itself fails on — defence in depth, not the contract.

* **The body never carries prose.** Only the token; see :class:`~src.companion.contracts.
  ErrorResponse`. Whatever a human needs — the validation detail, the traceback — is logged here
  and stops here, because the companion is one ``fetch`` away from any page in the browser.

Handlers are annotated ``(request: Request, exc: Exception)`` and narrow with ``isinstance``
inside: ``add_exception_handler`` is typed against that exact signature, and a narrower ``exc``
annotation is an ``arg-type`` failure under ``mypy --strict``.
"""

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.companion.contracts import ErrorReason, ErrorResponse

logger = logging.getLogger(__name__)

STATUS_BY_REASON: dict[ErrorReason, int] = {
    "deck_not_found": 404,
    "database_not_initialized": 503,
    "database_unavailable": 503,
    "invalid_request": 400,
    "payload_too_large": 422,
}
"""The one pairing of reason token to HTTP status (AD-16).

Every token in :data:`~src.companion.contracts.ErrorReason` appears exactly once; a test pins the
two sets equal, so a future token without a status fails loudly instead of defaulting.
"""


class CompanionError(Exception):
    """A modelled failure: one of the closed reason tokens, on its way to a typed response.

    Endpoints raise this instead of building a response, so the status, the body shape and the
    serialisation all stay in one place. Nothing in ``src/`` raises it yet — stories c1-5 (bad
    ``Host``), c1-6 (missing database), c3-1 (missing deck) and c5-5 (oversized push) are the first
    callers.

    Args:
        reason: The token this failure reports; its status comes from :data:`STATUS_BY_REASON`.

    Example:
        >>> str(CompanionError("deck_not_found"))
        'deck_not_found'
    """

    def __init__(self, reason: ErrorReason) -> None:
        # Pass the reason up so the default string form — which is what a log line or a pytest
        # failure prints — names the token rather than showing an empty exception.
        super().__init__(reason)
        self.reason: ErrorReason = reason


def error_response(reason: ErrorReason, *, status: int | None = None) -> JSONResponse:
    """Render *reason* as the typed error body.

    Args:
        reason: The token to report.
        status: Override for the status code. Exists **only** for the ``HTTPException`` path, where
            the framework's own status (404 for an unknown path, 405 for a wrong method) is more
            accurate than anything the token could imply. Modelled failures always take the
            mapping — do not pass this from an endpoint.

    Returns:
        A ``JSONResponse`` whose body is exactly ``{"reason": "<token>"}``.
    """
    return JSONResponse(
        status_code=STATUS_BY_REASON[reason] if status is None else status,
        content=ErrorResponse(reason=reason).model_dump(),
    )


def error_responses(*reasons: ErrorReason) -> dict[int | str, dict[str, Any]]:
    """Declare *reasons* to OpenAPI, so the generated TypeScript knows the shape (AD-12, NFR-03).

    A Pydantic model that no route references never enters ``components.schemas``, and ``c2-3``'s
    generator would emit nothing for it. This is the one construction site for that declaration:
    ``build_app()`` uses it app-wide, and c3-1 / c3-2 / c5-5 use it per-route for the tokens only
    their own endpoints can produce.

    Tokens sharing a status (both database tokens are 503) collapse into a single entry whose
    description names each of them, rather than one silently overwriting the other.

    Args:
        *reasons: The tokens the annotated routes may answer with.

    Returns:
        A mapping in FastAPI's ``responses=`` shape: status code to ``{"model", "description"}``.

    Example:
        >>> sorted(error_responses("invalid_request", "deck_not_found"))
        [400, 404]
    """
    grouped: dict[int, list[ErrorReason]] = {}
    for reason in reasons:
        grouped.setdefault(STATUS_BY_REASON[reason], []).append(reason)
    return {
        status: {
            "model": ErrorResponse,
            "description": "reason: " + " | ".join(tokens),
        }
        for status, tokens in grouped.items()
    }


async def companion_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert a raised :class:`CompanionError` into its typed response.

    Args:
        request: The request being served; unused, but part of the handler signature.
        exc: The exception Starlette dispatched here.

    Returns:
        The typed body at the token's mapped status.

    Raises:
        Exception: Re-raises anything that is not a :class:`CompanionError`, which can only happen
            if the handler is registered against the wrong class.
    """
    if not isinstance(exc, CompanionError):
        raise exc
    logger.debug("Companion error %s serving %s %s", exc.reason, request.method, request.url.path)
    return error_response(exc.reason)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer a request-validation failure with ``400 invalid_request``.

    Replaces FastAPI's default ``422 {"detail": [...]}`` for two reasons: 422 belongs to
    ``payload_too_large`` under AD-16, and the default body is a second error shape the UI would
    have to parse. The detail itself is **logged, never returned** — it echoes the caller's own
    input straight back over a port any page in the browser can reach.

    Args:
        request: The request whose parameters or body failed validation.
        exc: The exception Starlette dispatched here.

    Returns:
        The typed body at 400.

    Raises:
        Exception: Re-raises anything that is not a ``RequestValidationError``.
    """
    if not isinstance(exc, RequestValidationError):
        raise exc
    logger.warning(
        "Request validation failed for %s %s: %s", request.method, request.url.path, exc.errors()
    )
    return error_response("invalid_request")


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer an ``HTTPException`` with the typed body, keeping the framework's status.

    An unknown path's 404, a 405, and any ``HTTPException`` a later story raises are *framework
    misses*, not modelled UX states — there is no token for "you asked for a path that does not
    exist", and inventing one would breach the closed set. So the status is preserved and the token
    says only which half of the world the failure came from: ``invalid_request`` for 4xx (the
    caller), ``database_unavailable`` for 5xx (us). The property AD-16 actually needs — token to UX
    state, 1:1 — is untouched, because nothing in the SPA keys off a bare status code.

    Registered against **Starlette's** ``HTTPException``, which ``fastapi.HTTPException``
    subclasses, so one registration covers both and overrides FastAPI's own default handler.

    Args:
        request: The request being served; unused, but part of the handler signature.
        exc: The exception Starlette dispatched here.

    Returns:
        The typed body at the exception's own status.

    Raises:
        Exception: Re-raises anything that is not a Starlette ``HTTPException``.
    """
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    reason: ErrorReason = "invalid_request" if exc.status_code < 500 else "database_unavailable"
    return error_response(reason, status=exc.status_code)


class UnhandledErrorMiddleware:
    """Turn any unhandled exception into a typed ``503 database_unavailable``, logged once.

    Pure ASGI rather than an ``Exception`` exception-handler: Starlette's handler path always
    re-raises after writing (see the module docstring), which would give the caller a traceback
    instead of a body. Catches ``Exception`` and never ``BaseException``, so ``CancelledError``
    still propagates and shutdown and client disconnects keep working.

    Args:
        app: The next application in the ASGI stack.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve one ASGI event stream, converting an escaping exception into a typed response.

        Args:
            scope: The connection scope. Non-``http`` scopes (``lifespan``, and c5-3's
                ``websocket``) pass straight through — there is no JSON body to send on those.
            receive: The ASGI receive channel.
            send: The ASGI send channel, wrapped so we know whether the response already started.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Reaches stderr via logging.lastResort even though no story has configured a root
            # logger yet (c1-9 owns that); the client still gets only the token.
            logger.exception(
                "Unhandled error serving %s %s", scope.get("method"), scope.get("path")
            )
            if response_started:
                # Headers are already on the wire; a second response would corrupt the stream, so
                # let it go up to ServerErrorMiddleware and die honestly.
                raise
            response = error_response("database_unavailable")
            await response(scope, receive, send)


def install_error_handling(app: FastAPI) -> None:
    """Register every error path on *app*, in one call.

    Kept as a single function so c1-5 and c1-6 wire nothing new — they raise
    :class:`CompanionError` and the plumbing is already there.

    Call this **last** in ``build_app()``: ``app.user_middleware[0]`` is the most recently added
    middleware, so adding :class:`UnhandledErrorMiddleware` last is what puts it outermost, where it
    can type the failures of every middleware added before it. ``add_middleware`` also raises once
    the app has started, so this belongs in construction and nowhere else.

    Args:
        app: The application to install onto.
    """
    app.add_exception_handler(CompanionError, companion_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_middleware(UnhandledErrorMiddleware)

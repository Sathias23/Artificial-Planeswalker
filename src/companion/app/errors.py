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
from collections.abc import Mapping
from typing import Any, get_args

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import DatabaseError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.companion.contracts import ErrorReason, ErrorResponse

logger = logging.getLogger(__name__)

STATUS_BY_REASON: dict[ErrorReason, int] = {
    "deck_not_found": 404,
    "database_not_initialized": 503,
    "database_unavailable": 503,
    "invalid_request": 400,
    "payload_too_large": 413,
    "internal_error": 500,
}
"""The one pairing of reason token to HTTP status (AD-16).

Every token in :data:`~src.companion.contracts.ErrorReason` appears exactly once; a test pins the
two sets equal, so a future token without a status fails loudly instead of defaulting.
"""


class CompanionError(Exception):
    """A modelled failure: one of the closed reason tokens, on its way to a typed response.

    Endpoints raise this instead of building a response, so the status, the body shape and the
    serialisation all stay in one place. The callers so far are c1-6 (``get_session``, for a missing
    or unpopulated database) and c3-1 (``read_deck``, for a missing deck); c5-5's oversized push is
    still to come.

    **Middleware does not raise this.** A user middleware sits *outside* Starlette's
    ``ExceptionMiddleware``, so a handler registered with ``add_exception_handler`` can never see
    what one of them raises — the caller would get ``500 internal_error`` and a false traceback
    instead of the intended token. c1-5's ``Host`` check therefore calls :func:`error_response` and
    sends the body itself; any later middleware must do the same.

    Args:
        reason: The token this failure reports; its status comes from :data:`STATUS_BY_REASON`.

    Example:
        >>> str(CompanionError("deck_not_found"))
        'deck_not_found'
    """

    def __init__(self, reason: ErrorReason) -> None:
        # mypy checks the Literal at typed call sites, but a runtime string from anywhere else
        # would otherwise surface as a KeyError inside the handler, masked by the middleware as a
        # misleading internal_error. Fail loudly at the raise site instead.
        if reason not in get_args(ErrorReason):
            raise ValueError(f"unknown error reason: {reason!r}")
        # Pass the reason up so the default string form — which is what a log line or a pytest
        # failure prints — names the token rather than showing an empty exception.
        super().__init__(reason)
        self.reason: ErrorReason = reason


def error_response(
    reason: ErrorReason,
    *,
    status: int | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Render *reason* as the typed error body.

    Args:
        reason: The token to report.
        status: Override for the status code. Exists **only** for the ``HTTPException`` path, where
            the framework's own status (404 for an unknown path, 405 for a wrong method) is more
            accurate than anything the token could imply. Modelled failures always take the
            mapping — do not pass this from an endpoint.
        headers: Headers to carry on the response. Also only for the ``HTTPException`` path:
            Starlette's route-miss 405 arrives with the RFC-mandated ``Allow``, and a later
            story's exception may carry ``WWW-Authenticate`` or ``Retry-After`` — dropping them
            would make the typed body a downgrade.

    Returns:
        A ``JSONResponse`` whose body is exactly ``{"reason": "<token>"}``.
    """
    return JSONResponse(
        status_code=STATUS_BY_REASON[reason] if status is None else status,
        content=ErrorResponse(reason=reason).model_dump(),
        headers=dict(headers) if headers else None,
    )


def error_responses(*reasons: ErrorReason) -> dict[int | str, dict[str, Any]]:
    """Declare *reasons* to OpenAPI, so the generated TypeScript knows the shape (AD-12, NFR-03).

    A Pydantic model that no route references never enters ``components.schemas``, and ``c2-3``'s
    generator would emit nothing for it. This is the one construction site for that declaration:
    ``build_app()`` uses it app-wide, and the per-route callers declare only the tokens their own
    endpoints can produce: c3-1's ``GET /api/deck/{deck_id}`` declares ``deck_not_found`` (and its
    sibling ``GET /api/decks`` deliberately declares nothing, having no 404 to give); c3-2 and c5-5
    follow.

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
    # dict.fromkeys: dedupe while keeping declaration order, so a repeated token cannot ship a
    # "reason: x | x" description into the generated docs.
    for reason in dict.fromkeys(reasons):
        grouped.setdefault(STATUS_BY_REASON[reason], []).append(reason)
    return {
        status: {
            "model": ErrorResponse,
            "description": "reason: " + " | ".join(tokens),
        }
        for status, tokens in grouped.items()
    }


_AUTO_VALIDATION_COMPONENTS = ("HTTPValidationError", "ValidationError")


def without_auto_validation_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip FastAPI's auto-generated 422 validation response from an OpenAPI *schema*.

    The ``invalid_request`` handler makes that response permanently unreachable — validation
    failures answer ``400`` — but FastAPI re-documents it on every route with validated input,
    which would put a shape the API never emits into c2-3's generated TypeScript. Declaring an
    explicit 422 used to displace it as a side effect; the 413 ruling freed 422 entirely, so the
    displacement now happens here, at schema-build time, for every current and future route
    (caught by Greptile on PR #12: the first validated route silently resurrected the auto-422).

    Only entries referencing the auto-generated component are removed — a deliberate, explicitly
    declared 422 would survive untouched.

    Args:
        schema: The schema produced by ``FastAPI.openapi()``; modified in place.

    Returns:
        The same schema, without the auto-generated validation response or its components.
    """
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses", {})
            declared = responses.get("422", {})
            ref = (
                declared.get("content", {})
                .get("application/json", {})
                .get("schema", {})
                .get("$ref", "")
            )
            if str(ref).endswith("/HTTPValidationError"):
                del responses["422"]
    components = schema.get("components", {}).get("schemas", {})
    for name in _AUTO_VALIDATION_COMPONENTS:
        components.pop(name, None)
    return schema


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


async def http_exception_handler(request: Request, exc: Exception) -> Response:
    """Answer an ``HTTPException`` with the typed body, keeping the framework's status and headers.

    An unknown path's 404, a 405, and any ``HTTPException`` a later story raises are *framework
    misses*, not modelled UX states — there is no token for "you asked for a path that does not
    exist", and inventing one would breach the closed set. So the status is preserved and the token
    says only which half of the world the failure came from: ``invalid_request`` for 4xx (the
    caller), ``internal_error`` for 5xx (us, unmodelled — a *modelled* database outage raises
    :class:`CompanionError` and never lands here). The property AD-16 actually needs — token to UX
    state, 1:1 — is untouched, because nothing in the SPA keys off a bare status code.

    Headers ride along: Starlette's route-miss 405 carries the RFC-mandated ``Allow``, and dropping
    a ``WWW-Authenticate`` or ``Retry-After`` would make the typed body a downgrade. A sub-400 or
    bodiless (204/304) status is not an error at all, so it passes through with no body rather
    than being stamped with a token it cannot honestly carry.

    Registered against **Starlette's** ``HTTPException``, which ``fastapi.HTTPException``
    subclasses, so one registration covers both and overrides FastAPI's own default handler.

    Args:
        request: The request being served; unused, but part of the handler signature.
        exc: The exception Starlette dispatched here.

    Returns:
        The typed body at the exception's own status, or a bodiless response for a status that
        forbids or predates a body.

    Raises:
        Exception: Re-raises anything that is not a Starlette ``HTTPException``.
    """
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    if exc.status_code < 400 or exc.status_code in {204, 304}:
        return Response(status_code=exc.status_code, headers=exc.headers)
    reason: ErrorReason = "invalid_request" if exc.status_code < 500 else "internal_error"
    return error_response(reason, status=exc.status_code, headers=exc.headers)


async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer a transient database failure with ``503 database_unavailable``.

    **Why ``DatabaseError`` and not the wider ``SQLAlchemyError``.** ``sqlalchemy.exc`` splits
    cleanly along the line AD-16 cares about. ``DatabaseError`` — and its ``OperationalError`` /
    ``IntegrityError`` / ``DataError`` children — is the database telling us something went wrong
    *now*: "database is locked", "unable to open database file", "file is not a database". That is
    the **"Database updating"** state, which the UI retries quietly. ``ArgumentError``,
    ``InvalidRequestError`` and ``CompileError`` are us telling ourselves we wrote bad code; they
    are deterministic, retrying them is pointless, and they must fall through to
    :class:`UnhandledErrorMiddleware`'s ``500 internal_error`` — the distinction the c1-4 review
    added ``internal_error`` for. The MCP side catches ``DatabaseError`` in every tool, so a reader
    moving between the two shells meets one rule (AD-1).

    Registering it here rather than in :mod:`src.companion.app.deps` is what makes every data-backed
    route inherit the mapping with no per-route ceremony — the dependency's own readiness probe as
    much as the route bodies c3-1 onward will add.

    **Why the parameters are never logged.** ``str(exc)`` carries the failing statement *and its
    bound parameters* (verified: ``[parameters: (...)]``), which on this path can be anything a
    caller passed in. So the log names the exception class and ``exc.orig`` — the DBAPI error, the
    part an operator actually needs — and stops there.

    Args:
        request: The request whose database read failed.
        exc: The exception Starlette dispatched here.

    Returns:
        The typed body at 503.

    Raises:
        Exception: Re-raises anything that is not a ``DatabaseError``.
    """
    if not isinstance(exc, DatabaseError):
        raise exc
    logger.warning(
        "Database read failed serving %s %s: %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc.orig,
    )
    return error_response("database_unavailable")


class UnhandledErrorMiddleware:
    """Turn any unhandled exception into a typed ``500 internal_error``, logged once.

    Pure ASGI rather than an ``Exception`` exception-handler: Starlette's handler path always
    re-raises after writing (see the module docstring), which would give the caller a traceback
    instead of a body. Catches ``Exception`` and never ``BaseException``, so ``CancelledError``
    still propagates and shutdown keeps working. ``ClientDisconnect`` — an ``Exception`` subclass —
    is carved out separately: a client dropping mid-read is routine, not a bug, so it must not
    produce a false-alarm ``ERROR`` record or a response into a dead stream.

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
        except ClientDisconnect:
            # Routine, not a bug: the caller closed the connection mid-request. Re-raising is
            # byte-identical to not having this middleware at all — no ERROR record, no attempt
            # to answer a client that is gone.
            logger.debug("Client disconnected during %s %s", scope.get("method"), scope.get("path"))
            raise
        except Exception:
            if response_started:
                # Headers are already on the wire; a second response would corrupt the stream, so
                # let it go up to ServerErrorMiddleware and die honestly — and let that outer
                # layer do the logging, so every failure is logged exactly once by exactly one net.
                raise
            # Reaches stderr through the root handler c1-9's entry point configures (and via
            # logging.lastResort in any process that configures none); the client still gets only
            # the token.
            logger.exception(
                "Unhandled error serving %s %s", scope.get("method"), scope.get("path")
            )
            response = error_response("internal_error")
            await response(scope, receive, send)


def install_error_handling(app: FastAPI) -> None:
    """Register every error path on *app*, in one call.

    Which exception becomes which token, in one place — the enumeration a new route should read
    instead of adding a handler of its own:

    * :class:`CompanionError` — a *modelled* failure; the token it carries, at its mapped status.
    * ``RequestValidationError`` — ``400 invalid_request``.
    * ``sqlalchemy.exc.DatabaseError`` — ``503 database_unavailable``; transient, and deliberately
      narrower than ``SQLAlchemyError`` (see :func:`database_error_handler`).
    * Starlette's ``HTTPException`` — the framework's own status, with ``invalid_request`` for 4xx
      and ``internal_error`` for 5xx.
    * anything else — ``500 internal_error`` from :class:`UnhandledErrorMiddleware`, which is where
      a deterministic ``ArgumentError`` or ``InvalidRequestError`` correctly lands.

    Kept as a single function so the endpoint stories (c1-6, c3-1, c5-5) wire nothing new — they
    raise :class:`CompanionError` and the plumbing is already there. c1-5's middleware is the
    deliberate exception: it *sends* its typed body rather than raising (see
    :class:`CompanionError`'s docstring) and installs through ``install_security``, not here.

    Call this **last** in ``build_app()``: ``app.user_middleware[0]`` is the most recently added
    middleware, so adding :class:`UnhandledErrorMiddleware` last is what puts it outermost, where it
    can type the failures of every middleware added before it. ``add_middleware`` also raises once
    the app has started, so this belongs in construction and nowhere else.

    Args:
        app: The application to install onto.
    """
    app.add_exception_handler(CompanionError, companion_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(DatabaseError, database_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_middleware(UnhandledErrorMiddleware)

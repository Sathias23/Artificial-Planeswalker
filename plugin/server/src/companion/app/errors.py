"""Every non-2xx the companion can produce, funnelled into one typed body (AD-16).

Three rules hold this module together, and each of them is a decision later code inherits rather
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
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, get_args

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import DatabaseError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.companion.contracts import ErrorReason, ErrorResponse

logger = logging.getLogger(__name__)

STATUS_BY_REASON: dict[ErrorReason, int] = {
    "deck_not_found": 404,
    "card_not_found": 404,
    "no_image_data": 404,
    "image_fetch_failed": 502,
    "database_not_initialized": 503,
    "database_unavailable": 503,
    "invalid_request": 400,
    "forbidden": 403,
    "payload_too_large": 413,
    "internal_error": 500,
}
"""The one pairing of reason token to HTTP status (AD-16).

Every token in :data:`~src.companion.contracts.ErrorReason` appears exactly once; a test pins the
two sets equal, so a future token without a status fails loudly instead of defaulting.

**Why ``forbidden`` is 403 and not 401.** RFC 9110 §15.5.2 requires a ``401`` to carry a
``WWW-Authenticate`` challenge, and this app's raise path structurally **cannot**:
:func:`companion_error_handler` calls :func:`error_response` with no ``headers=``, and the parameter
exists for the ``HTTPException`` path alone. A ``401`` here would therefore either ship
non-conformant or force :class:`CompanionError` to grow a header channel that exactly one token
would ever use. ``403`` carries no such requirement and is the honest status for *a credential was
presented and refused* when there is no challenge-response scheme to advertise — the companion
mints one token per process and publishes it in the discovery file; there is nothing to negotiate.

**Why the two image tokens split across 404 and 502.** ``no_image_data`` is a statement about the
*resource*: this card, at this face, has no artwork — a permanent fact of the local row, and 404
is the status for "the thing you addressed is not there". ``image_fetch_failed`` is a statement
about an *upstream*: the URL was known and the CDN did not deliver. RFC 9110 §15.6.3 defines 502
as exactly that — a gateway received an invalid response from the server it was proxying — and it
is what makes the two distinguishable to a client that reads only the status, on top of the two
tokens that make them distinguishable to one that reads the body. Deliberately **not** 503: a 503
in this app means *the local database is unusable*, the UI retries it quietly, and a CDN blip
must not put up the "Card database is updating" panel.
"""


class CompanionError(Exception):
    """A modelled failure: one of the closed reason tokens, on its way to a typed response.

    Endpoints raise this instead of building a response, so the status, the body shape and the
    serialisation all stay in one place. Callers include route bodies (a missing deck or card) and
    dependencies (``get_session`` for a missing or unpopulated database,
    :func:`~src.companion.app.security.require_agent_token` for a refused credential). A
    dependency may raise it for the same reason a route body may — dependencies are solved inside
    Starlette's ``ExceptionMiddleware``, so what they raise reaches a handler. Position in the
    stack is the rule, not "only route bodies may raise".

    **Middleware does not raise this.** A user middleware sits *outside* Starlette's
    ``ExceptionMiddleware``, so a handler registered with ``add_exception_handler`` can never see
    what one of them raises — the caller would get ``500 internal_error`` and a false traceback
    instead of the intended token. The ``Host`` check and the body cap
    (:class:`~src.companion.app.body_cap.BodyCapMiddleware`) therefore call :func:`error_response`
    and send the body themselves; any later middleware must do the same.

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
            exception may carry ``WWW-Authenticate`` or ``Retry-After`` — dropping them
            would make the typed body a downgrade. A caller's own ``Cache-Control`` overrides the
            ``no-store`` default below; nothing sends one today.

    Returns:
        A ``JSONResponse`` whose body is exactly ``{"reason": "<token>"}``, marked ``no-store``.
    """
    # `no-store` on EVERY typed error, feature-wide, and it is load-bearing rather than hygiene.
    # A route cannot attach headers — the whole point of deriving the status from the token is
    # that a call site cannot shape the response — so the only place this can be said is here. It
    # has to be said: RFC 9111 §4.2.2 lists 404 among the statuses a cache may store
    # *heuristically*, with no explicit freshness at all, and a 404 from this app can describe a
    # card the next database import will add. Cached, one bad minute would leave a permanently
    # broken tile in that tab. No modelled failure in this app is worth re-serving from a cache:
    # every one of them is either about right now (503, 502) or about a request that will be
    # answered the same way anyway (400, 403, 404).
    #
    # The override is honoured by HEADER semantics, not dict semantics: HTTP names are
    # case-insensitive and dict keys are not, so a plain `**` merge over a caller's
    # `cache-control` would put TWO conflicting Cache-Control headers on the wire.
    merged: dict[str, str] = {"Cache-Control": "no-store"}
    for name, value in dict(headers or {}).items():
        merged["Cache-Control" if name.lower() == "cache-control" else name] = value
    return JSONResponse(
        status_code=STATUS_BY_REASON[reason] if status is None else status,
        content=ErrorResponse(reason=reason).model_dump(),
        headers=merged,
    )


def error_responses(*reasons: ErrorReason) -> dict[int | str, dict[str, Any]]:
    """Declare *reasons* to OpenAPI, so the generated TypeScript knows the shape (AD-12, NFR-03).

    A Pydantic model that no route references never enters ``components.schemas``, and the
    TypeScript generator would emit nothing for it. This is the one construction site for that
    declaration. ``build_app()`` uses it per **include** for the tokens every route in a router
    shares, and the per-route callers declare only the tokens their own endpoints can produce:
    ``GET /api/deck/{deck_id}`` declares ``deck_not_found`` while its sibling ``GET /api/decks``
    declares nothing, having no 404 to give; ``PUT /api/active-deck`` declares ``forbidden`` and
    ``payload_too_large`` while the credential-free, body-less ``GET`` beside it declares nothing;
    ``GET /api/card-image/{scryfall_id}`` declares three. The declaration is about what the
    *operation* can answer — a body-less ``GET`` never publishes a 413 — and not about which frame
    raised it: ``forbidden`` comes from a dependency, so a reader looking for the raise will not
    find it in the route function. A route whose **success** body is not JSON merges this mapping
    into a hand-written ``200`` entry rather than passing it as ``responses=`` wholesale; the
    declarations this builds are per status and describe the error bodies, so nothing here
    changes.

    Tokens sharing a status (both database tokens are 503; ``deck_not_found`` and
    ``card_not_found`` are both 404 without being interchangeable) collapse into a single entry
    whose description names each of them, rather than one silently overwriting the other.

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
    which would put a shape the API never emits into the generated TypeScript. No route declares a
    422 of its own (over-cap answers 413), so nothing displaces the auto-422 as a side effect; the
    removal happens here, at schema-build time, for every current and future route — a per-route
    displacement silently resurrects it on the first validated route that forgets.

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

    Replaces FastAPI's default ``422 {"detail": [...]}`` for two reasons: 422 is not a status any
    token carries under AD-16, and the default body is a second error shape the UI would have to
    parse. The detail itself is **logged, never returned** — it echoes the caller's own
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


_METHOD_NOT_ALLOWED = 405


def _leaf_routes(routes: Iterable[Any]) -> Iterator[Any]:
    """Yield the individual routes reachable from *routes*, flattening nested routers.

    FastAPI 0.140 does **not** flatten an included router into ``app.routes``: it stores a lazy
    ``_IncludedRouter`` wrapper whose ``matches()`` answers for the whole branch and which carries
    no ``methods`` of its own (measured — a naive one-level walk over this app finds four such
    wrappers and zero real routes). Starlette ``Mount``s nest the same way through ``.routes``.

    Written against attributes rather than against either framework's private classes, so a
    structural change upstream degrades this to "found nothing" — which the one caller treats as
    *keep the framework's own header* — instead of raising inside an error handler, which is the
    worst possible place to introduce a new failure.

    Args:
        routes: A route list, from ``app.routes`` or a nested router.

    Yields:
        Every leaf route, depth-first.
    """
    for route in routes:
        included = getattr(route, "original_router", None)
        nested = getattr(included, "routes", None) if included is not None else None
        if nested is None:
            nested = getattr(route, "routes", None)
        if nested:
            yield from _leaf_routes(nested)
            continue
        yield route


def supported_methods(request: Request) -> frozenset[str]:
    """Return every HTTP method the routes matching *request*'s path collectively support.

    **Why this has to exist, measured against Starlette 0.48.0.** ``Router.app`` keeps only the
    **first** partially-matching route (``routing.py:738``: ``elif match == Match.PARTIAL and
    partial is None``) and then lets it answer, and ``Route.handle`` builds the header from *that
    one route's* method set (``routing.py:283``: ``headers = {"Allow": ", ".join(self.methods)}``).
    One path served by two single-method routes therefore advertises only the first of them.

    ``/api/active-deck`` is served by two single-method routes, and a ``POST`` to it measured
    ``Allow: GET`` — omitting the ``PUT`` that is the whole point of the
    resource. RFC 9110 §15.5.6 requires the field to list *the target resource's* supported methods,
    so that answer is not merely unhelpful, it is wrong: a client reading it concludes the resource
    cannot be written.

    Recomputed here rather than worked around by merging the two operations into one route, because
    they are genuinely two operations — different bodies, different credentials, different declared
    errors — and collapsing them would trade a correct schema for a correct header.

    Args:
        request: The request that missed. Its scope is re-matched against the app's route table.

    Returns:
        The union of the methods of every route whose path matches but whose method did not.
        Empty when nothing matched partially — including if the route-table walk ever stops finding
        leaves, which the caller treats as "leave the framework's header alone".

    .. warning::
        The flattened children are matched against the **un-stripped** request scope. Starlette
        strips a mount's prefix into ``child_scope`` before children match, so this is correct
        only while every mount sits at ``/`` — true of this app today (the SPA mount) and asserted
        by nothing. A future non-root ``Mount`` would have children that silently never match here
        (degrading to Starlette's incomplete header) or, for a child at ``/``, match paths it does
        not serve. This is a *different* hole from the attribute-walk soft failure above: that one
        finds no leaves; this one finds them and asks them the wrong question. Whatever adds a
        non-root mount owns the prefix-stripping walk.
    """
    methods: set[str] = set()
    for route in _leaf_routes(request.app.routes):
        match, _ = route.matches(request.scope)
        if match is not Match.PARTIAL:
            continue
        # Mounts and routers have no `methods` at all, so they contribute nothing rather than
        # raising.
        methods |= set(getattr(route, "methods", None) or ())
    return frozenset(methods)


async def http_exception_handler(request: Request, exc: Exception) -> Response:
    """Answer an ``HTTPException`` with the typed body, keeping the framework's status and headers.

    An unknown path's 404, a 405, and any ``HTTPException`` later code raises are *framework
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

    The ``Allow`` on a 405 is **recomputed rather than forwarded**, and that is a repair rather than
    a refinement: Starlette derives it from the first partially-matching route alone, which
    under-reports the moment a path is served by more than one (see :func:`supported_methods` for
    the measurement). Forwarded unchanged, ``POST /api/active-deck`` would answer ``Allow: GET`` and
    tell the leaf client that the endpoint it calls does not accept writes. Every other header on
    the exception is passed through untouched.

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
    headers = exc.headers
    if exc.status_code == _METHOD_NOT_ALLOWED:
        allowed = supported_methods(request)
        # Guarded on truthiness: an empty union means nothing matched partially, which should not
        # happen on a 405 — and replacing a real header with an empty one would be strictly worse
        # than leaving Starlette's incomplete one in place.
        if allowed:
            headers = {**(headers or {}), "Allow": ", ".join(sorted(allowed))}
    reason: ErrorReason = "invalid_request" if exc.status_code < 500 else "internal_error"
    return error_response(reason, status=exc.status_code, headers=headers)


async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer a transient database failure with ``503 database_unavailable``.

    **Why ``DatabaseError`` and not the wider ``SQLAlchemyError``.** ``sqlalchemy.exc`` splits
    cleanly along the line AD-16 cares about. ``DatabaseError`` — and its ``OperationalError`` /
    ``IntegrityError`` / ``DataError`` children — is the database telling us something went wrong
    *now*: "database is locked", "unable to open database file", "file is not a database". That is
    the **"Database updating"** state, which the UI retries quietly. ``ArgumentError``,
    ``InvalidRequestError`` and ``CompileError`` are us telling ourselves we wrote bad code; they
    are deterministic, retrying them is pointless, and they must fall through to
    :class:`UnhandledErrorMiddleware`'s ``500 internal_error`` — the distinction ``internal_error``
    exists for. The MCP side catches ``DatabaseError`` in every tool, so a reader moving between
    the two shells meets one rule (AD-1).

    Registering it here rather than in :mod:`src.companion.app.deps` is what makes every data-backed
    route inherit the mapping with no per-route ceremony — the dependency's own readiness probe as
    much as the route bodies.

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
            scope: The connection scope. Non-``http`` scopes (``lifespan`` and ``websocket``) pass
                straight through — there is no JSON body to send on those. That is **permanent**
                rather than a gap: the WebSocket upgrade catches its own faults and answers with a
                close code (``1011``), so this middleware keeps one shape instead of growing a
                second for one caller. See
                :func:`src.companion.app.ws.websocket_upgrade`.
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
            # Reaches stderr through the root handler the entry point configures (and via
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

    Kept as a single function so endpoints wire nothing new — they raise :class:`CompanionError`
    and the plumbing is already there. Middleware is the deliberate exception, and there are two
    instances of it: the ``Host`` check and :class:`~src.companion.app.body_cap.BodyCapMiddleware`.
    Both *send* their typed body rather than raising (see :class:`CompanionError`'s docstring), and
    both install through their own ``install_*`` call in ``build_app()``, not here.

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

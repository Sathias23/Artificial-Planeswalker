"""The companion's ASGI application: a side-effect-free constructor and a lifespan (AD-10).

``build_app()`` is inert. It binds no port, opens no database, writes no file and resolves no data
path, because :func:`src.paths.data_dir` ends in ``mkdir`` and would create the data directory just
by being called. Everything with an effect outside this process belongs to the lifespan, which is
what makes the backend testable in-process with one real-port test (AD-10) and lets a missing
database be a served UI state rather than a startup crash (FR-22). The lifespan is a module-level
function so tests can enter it directly (``tests/unit/companion/conftest.py``).
"""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from src.companion import discovery
from src.companion.app import deps, images, state
from src.companion.app.body_cap import install_body_cap
from src.companion.app.errors import (
    error_responses,
    install_error_handling,
    without_auto_validation_schema,
)
from src.companion.app.routes import active_deck, agent_events, cards, decks, health, session
from src.companion.app.security import install_security
from src.companion.app.spa import install_spa
from src.companion.app.ws import router as ws_router

logger = logging.getLogger(__name__)

_TITLE = "Artificial Planeswalker Companion"


def _publish_discovery(app: FastAPI) -> None:
    """Publish where this process is and how to authenticate to it (AD-4).

    The record names :func:`bound_port`, the port the runner actually bound. ``None`` means nobody
    bound a socket and there is nothing truthful to publish, so the write is skipped at WARNING: a
    companion nobody can find is a problem the user should see. The token is never logged (AD-5).

    Args:
        app: The application being started, with its identity and token already on ``app.state``.

    Raises:
        OSError: Propagated from :func:`~src.companion.discovery.write_discovery`; not caught.
    """
    port = bound_port(app)
    if port is None:
        logger.warning(
            "Companion instance %s bound no port; skipping the discovery file, so agent tools "
            "will report the app as not running",
            app.state.instance_id,
        )
        return
    record = discovery.DiscoveryRecord(
        port=port,
        token=app.state.agent_token,
        instance_id=app.state.instance_id,
    )
    path = discovery.write_discovery(record)
    logger.info("Published discovery file %s for port %d", path, port)


async def _shutdown(app: FastAPI) -> None:
    """Release everything the lifespan acquired, in reverse order of acquisition.

    The discovery file goes first, so the process stops advertising itself as early as possible
    (``remove_discovery`` is ownership-guarded and never raises); the image client is closed before
    the engine, mirroring creation order, so its pool is released rather than left to the garbage
    collector; the engine's pool is disposed last, a no-op if no request ever created one.

    Args:
        app: The application whose startup resources are being released.
    """
    instance_id = getattr(app.state, "instance_id", None)
    logger.debug("Companion instance %s shutting down", instance_id)
    # None means the lifespan never ran (a test driving _shutdown directly): nothing to retract.
    if instance_id is not None:
        discovery.remove_discovery(instance_id)
    # try/finally: `aclose` may raise, and a failing close must not strand the engine dispose.
    try:
        client = images.image_client(app)
        if client is not None:
            await client.aclose()
    finally:
        holder = deps.database(app)
        if holder is not None:
            await holder.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Mint this process's identity on startup and tear down cleanly on exit.

    ``instance_id`` and the agent token are minted here rather than in :func:`build_app` so a
    constructed-but-never-started app has no identity or credential to leak, and fresh per process,
    so a caller can tell a restarted companion from the one it was talking to (AD-4, FR-14) and a
    restart invalidates the token a tool was holding. The token reaches only ``app.state`` and the
    discovery file (AD-5).

    The in-process holders are inert objects that cannot fail to construct, created here so
    ``build_app()`` keeps its zero-side-effect property (AD-10) and a restart begins empty (CM-3,
    FR-07). The image client lives here because only the lifespan has a teardown to close its pool
    in; the pacer because ~100 tiles must share one queue; the disk cache returns ``None`` on
    ``OSError`` rather than raising, since the app is fully functional without one.

    Publishing the discovery file is therefore the one startup step that can fail, and it sits
    before the ``try`` so an ``OSError`` propagates and uvicorn exits loudly (AD-15): without the
    file every agent tool reports ``app_not_running`` while the app is visibly running.
    ``test_app.py::test_startup_failure_propagates`` pins the asymmetry. Teardown swallows its own
    failures, since a shutdown that raises would mask the real reason the process is stopping.

    Args:
        app: The application being started; startup values are attached to ``app.state``.

    Yields:
        None. The application is serving for the duration of the ``yield``.

    Raises:
        OSError: The discovery file could not be published, which fails the launch.
    """
    app.state.instance_id = str(uuid.uuid4())
    app.state.agent_token = discovery.mint_token()
    app.state.database = deps.Database()
    app.state.active_deck = state.ActiveDeckSlot()
    app.state.ticket_store = state.TicketStore()
    # Not torn down: closing every socket on shutdown would race uvicorn's own close path.
    app.state.connections = state.ConnectionRegistry()
    app.state.image_client = images.build_image_client()
    app.state.image_pacer = images.Pacer()
    app.state.image_cache = images.build_image_cache()
    app.state.negative_cache = images.NegativeCache()
    _publish_discovery(app)
    logger.info("Companion instance %s started", app.state.instance_id)
    try:
        yield
    finally:
        try:
            await _shutdown(app)
        except Exception:
            logger.exception("Companion shutdown step failed; shutting down anyway")


def bound_port(app: FastAPI) -> int | None:
    """Return the port the runner bound for *app*, or ``None`` if it never bound one.

    The runner binds the socket before uvicorn starts and writes the port it really got here, so the
    value reflects the ephemeral fallback. Presence is not a liveness signal: the value is never
    cleared. The accessor lives here so the ``Host`` middleware and the discovery writer reach the
    port without importing uvicorn from inside a request path.

    Args:
        app: The application to read.

    Returns:
        The bound port, or ``None`` before any bind.
    """
    # Annotated local: app.state is Any, and warn_return_any would flag returning getattr directly.
    port: int | None = getattr(app.state, "bound_port", None)
    return port


def agent_token(app: FastAPI) -> str | None:
    """Return the agent credential minted for *app*, or ``None`` if the lifespan never ran.

    The one comparison site is :func:`~src.companion.app.security.agent_token_is_valid`, reached
    through the :data:`~src.companion.app.security.AgentToken` dependency; nothing else may read
    this accessor to authenticate. Never serialise it: it must not enter a response body, a header,
    a log line, a model that reaches ``app.openapi()`` or a WebSocket frame (AD-5), and it lives on
    ``app.state`` rather than in any declared shape so there is no schema for it to leak through.
    ``None`` is a rejection, never a wildcard: the comparison fails closed when either side is
    missing, otherwise an app whose lifespan never ran would authenticate every request.

    Args:
        app: The application to read.

    Returns:
        The minted token, or ``None`` before startup.
    """
    # Annotated local: app.state is Any, and warn_return_any would flag returning getattr directly.
    token: str | None = getattr(app.state, "agent_token", None)
    return token


_DOCSTRING_SECTIONS = frozenset(
    {
        "Args:",
        "Arguments:",
        "Attributes:",
        "Example:",
        "Examples:",
        "Keyword Args:",
        "Keyword Arguments:",
        "Raises:",
        "Returns:",
        "Todo:",
        "Warns:",
        "Yields:",
    }
)
"""The Google-style section headers that end a wire description.

``Note:`` and ``Warning:`` are deliberately absent: they are prose a reader of the generated types
wants, where the twelve above name parameters, exceptions and doctests that mean nothing there.
"""

_DATA_KEYS = frozenset({"example", "examples", "default", "const", "enum"})
"""Schema keys whose subtrees are payload data, not documentation.

An example payload may carry a field named ``description`` that the schema must reproduce verbatim,
so the walk does not descend past these keys (inside ``properties`` the same words are names).
"""


def _summary_before_sections(description: str) -> str:
    """Return *description* up to its first Google-style section header.

    Args:
        description: A docstring-derived description, already dedented by FastAPI.

    Returns:
        The leading prose, trailing whitespace stripped; empty if it opens with a section header.
    """
    lines = description.split("\n")
    for index, line in enumerate(lines):
        # .strip(): FastAPI dedents by the common prefix, so an unevenly indented header can stay
        # indented and should still terminate the summary.
        if line.strip() in _DOCSTRING_SECTIONS:
            lines = lines[:index]
            break
    return "\n".join(lines).rstrip()


def without_python_docstring_sections(schema: dict[str, Any]) -> dict[str, Any]:
    """Truncate every ``description`` in *schema* at its first Google-style section header.

    FastAPI uses route and model docstrings as OpenAPI descriptions and ``openapi-typescript``
    emits them verbatim as JSDoc: measured on one endpoint and two models, 186 generated lines,
    roughly 130 of them prose naming parameters a TypeScript caller cannot pass. So descriptions
    that cross the wire are summaries: the leading paragraphs are what the frontend and ``/docs``
    see. Applies at any depth except inside payload data (:data:`_DATA_KEYS`); a description that
    is only a section header loses the key rather than emitting a bare ``@description``.

    Args:
        schema: The schema produced by ``FastAPI.openapi()``; modified in place.

    Returns:
        The same schema, with every description reduced to its summary.
    """
    _truncate_descriptions(schema)
    return schema


def _truncate_descriptions(node: Any, *, in_properties: bool = False) -> None:
    """Walk *node* and truncate every documentation ``description`` string it contains.

    Subtrees under :data:`_DATA_KEYS` are left byte-identical. A ``properties`` map needs the
    inverse care: its keys are property names, so a property called ``example`` is still a schema.

    Args:
        node: Any part of a decoded JSON document; non-container values are ignored.
        in_properties: Whether *node* is a ``properties`` map, whose keys are property names.
    """
    if isinstance(node, dict):
        description = node.get("description")
        if isinstance(description, str) and not in_properties:
            summary = _summary_before_sections(description)
            if summary:
                node["description"] = summary
            else:
                del node["description"]
        for key, value in list(node.items()):
            if key in _DATA_KEYS and not in_properties:
                continue
            _truncate_descriptions(value, in_properties=key == "properties" and not in_properties)
    elif isinstance(node, list):
        for item in node:
            _truncate_descriptions(item)


class _CompanionFastAPI(FastAPI):
    """A ``FastAPI`` whose schema carries neither the auto-422 nor Python's docstring internals.

    Validation failures answer ``400 invalid_request``, so FastAPI's per-route auto-422 would
    document a shape the API never emits. Both normalisers run on the one schema-build path, so
    ``/docs``, ``/openapi.json`` and the committed ``ui/src/api/openapi.json`` cannot disagree.
    """

    def openapi(self) -> dict[str, Any]:
        """Build (and cache) the schema, normalised for the generated TypeScript.

        Returns:
            The OpenAPI schema with FastAPI's auto-generated validation response removed and every
            description reduced to its summary.
        """
        if self.openapi_schema is None:
            self.openapi_schema = without_python_docstring_sections(
                without_auto_validation_schema(super().openapi())
            )
        return self.openapi_schema


def build_app() -> FastAPI:
    """Construct the companion ASGI application without touching anything outside the process.

    The per-include ``responses`` put the typed error body into ``app.openapi()`` (AD-12, NFR-03);
    a model no route references never reaches ``components.schemas``. They are declared per include
    rather than app-wide because the declaration is about what the operation can answer: a
    body-less, database-free ``GET`` structurally cannot answer ``503`` or ``413``.

    Returns:
        A configured ``FastAPI`` instance whose startup work has not yet run. Enter its lifespan
        (serving it, or ``async with lifespan(app)`` in tests) before expecting ``app.state`` to
        hold anything.
    """
    app = _CompanionFastAPI(title=_TITLE, lifespan=lifespan)
    # `/health` takes no session, so it can answer neither 503 token. `payload_too_large` is
    # declared only at the two operations that can answer it, never in a shared set.
    health_responses = error_responses("invalid_request", "database_unavailable", "internal_error")
    # `database_not_initialized` is a property of `deps.get_session`, so every data route inherits
    # it; both 503 tokens share a status and `error_responses` collapses them into one entry.
    database_responses = error_responses(
        "invalid_request",
        "database_not_initialized",
        "database_unavailable",
        "internal_error",
    )
    app.include_router(health.router, responses=health_responses)
    app.include_router(decks.router, responses=database_responses)
    app.include_router(cards.router, responses=database_responses)
    # No database dependency, so no 503; the PUT's 413 and `forbidden` are declared at the route,
    # because the sibling GET carries no body and cannot answer them.
    app.include_router(
        active_deck.router, responses=error_responses("invalid_request", "internal_error")
    )
    # Same pair for the same reasons; `/api/session` adds no `ErrorReason` token (AD-16).
    app.include_router(
        session.router, responses=error_responses("invalid_request", "internal_error")
    )
    # No `responses=`: OpenAPI does not model WebSockets and a closed handshake carries only a close
    # code. Still registered above `install_spa` (`test_spa.py` checks the mount declines ws).
    app.include_router(ws_router)
    # Takes no session, so no 503. `/agent` is protected from the SPA catch-all by this line's
    # position and nothing else: spa.py's `_RESERVED_SEED` covers `/api` only.
    app.include_router(
        agent_events.router,
        responses=error_responses(
            "invalid_request", "forbidden", "payload_too_large", "internal_error"
        ),
    )
    # user_middleware[0] is the most recently added, so the error middleware is installed last to
    # end up outermost, typing the failures of every middleware before it (http scopes only). The
    # body cap goes first so `Host` refuses a wrongly-addressed request before its body is read; it
    # is its own call because a resource ceiling is not a statement about who the caller is.
    install_body_cap(app)
    install_security(app)
    install_error_handling(app)
    # MUST STAY LAST. install_spa mounts the SPA bundle at "/", and Starlette matches routes in list
    # order, so a mount at "/" would silently shadow every route registered after it. `/api` is also
    # covered by spa.py's `_RESERVED_SEED`, but a router on a novel prefix (`/agent`) has only this
    # ordering between it and the catch-all, and the mount reads the route table to decide which
    # prefixes never fall back to the index. `test_spa.py::TestMountOrdering` fails if it moves.
    install_spa(app)
    return app

"""The companion's ASGI application: a side-effect-free constructor and a lifespan (AD-10).

``build_app()`` is **inert**. It binds no port, opens no database, writes no file and — the easy
one to get wrong — resolves no data path, because :func:`src.paths.data_dir` ends in
``mkdir(parents=True, exist_ok=True)`` and would therefore *create* the data directory just by
being called. Everything with an effect outside this process belongs to the lifespan instead.

Two things follow from that, and both are the point:

* the whole backend is testable in-process (``httpx.ASGITransport``) without a socket, so only one
  test in the entire feature needs a real port (AD-10);
* a missing database can be a *served UI state* rather than a crash on startup (FR-22) — only
  possible because construction never went looking for it.

The lifespan is a **module-level** function so tests can enter it directly; see Decide-once #2 in
the story record and ``tests/unit/companion/conftest.py``.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from src.companion import discovery
from src.companion.app import deps
from src.companion.app.errors import (
    error_responses,
    install_error_handling,
    without_auto_validation_schema,
)
from src.companion.app.routes import health
from src.companion.app.security import install_security

logger = logging.getLogger(__name__)

_TITLE = "Artificial Planeswalker Companion"


def _publish_discovery(app: FastAPI) -> None:
    """Publish where this process is and how to authenticate to it (AD-4).

    The record names :func:`bound_port` — the port the runner *actually* bound — so an ephemeral
    fallback is what lands in the file rather than whatever was preferred. ``None`` means nobody
    bound a socket (a ``build_app()`` served directly, or a test entering the lifespan without a
    port), and there is nothing truthful to publish: the write is skipped and startup continues.
    That skip logs at WARNING rather than INFO because no root handler is configured until c1-9 and
    ``logging.lastResort`` only surfaces WARNING and above to stderr — the same reasoning as
    ``server.py``'s bind fallback.

    The resulting path and port are logged; the token never is (AD-5).

    Args:
        app: The application being started, with its identity and token already on ``app.state``.

    Raises:
        OSError: Propagated from :func:`~src.companion.discovery.write_discovery`. The caller does
            not catch it — see the lifespan.
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

    Two things, in this order:

    1. **The discovery file** (c1-7). Retracted first, so the process stops advertising itself as
       early as possible — a tool that reads the file during teardown gets *app not running*
       rather than a port whose socket is about to close.
       :func:`~src.companion.discovery.remove_discovery` is ownership-guarded and never raises, so
       a foreign entry survives and an unlink failure cannot strand the dispose below it.
    2. **The database engine's connection pool**, if a data-backed request ever caused one to be
       created (c1-6). :meth:`~src.companion.app.deps.Database.dispose` is a no-op when it was not,
       which is the ordinary case for a companion that only ever answered ``/health`` — so there is
       one unconditional call rather than a condition per resource.

    Args:
        app: The application whose startup resources are being released.
    """
    instance_id = getattr(app.state, "instance_id", None)
    logger.debug("Companion instance %s shutting down", instance_id)
    # Guarded on the value, not on hasattr: None means the lifespan never ran, which is possible
    # when a test drives _shutdown directly — and there is then nothing of ours to retract.
    if instance_id is not None:
        discovery.remove_discovery(instance_id)
    holder = deps.database(app)
    if holder is not None:
        await holder.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Mint this process's identity on startup and tear down cleanly on exit.

    ``instance_id`` is minted **here** rather than in :func:`build_app` so a constructed-but-never
    -started app has no identity to leak, and so every fresh start is distinguishable — that is
    what lets a caller tell a restarted companion from the one it was talking to (AD-4, FR-14).

    The agent token is minted beside it and for the same reason — a constructed-but-never-started
    app holds no credential — and it is minted **fresh per process**, so two starts never share one
    and a restarted backend invalidates the token a tool was holding (c6-1's retry-once absorbs
    exactly that). It reaches only two places: ``app.state`` and the discovery file (AD-5).

    The :class:`~src.companion.app.deps.Database` holder is created beside them, and for the same
    reason it is safe to do so: like the identity mint it is an inert in-process object that cannot
    fail. The **engine** inside it is not created here — a fresh install has no card database yet,
    and AD-10 makes that a served UI state rather than a startup crash (FR-22).

    Publishing the discovery file is the **one** startup step that can fail, and it sits
    deliberately **before** the ``try`` so an ``OSError`` propagates and uvicorn exits loudly with
    the traceback (AD-15). That is a ruling, not an oversight (Decide-once #3): without the file
    the app is reachable only by a human reading the printed URL, so every agent tool reports
    ``app_not_running`` while the app is visibly running, and nothing on either surface explains
    the contradiction. An unwritable data directory is narrow and actionable; a half-launched
    rendezvous is not. Nothing else moves into the ``try``
    (``test_app.py::test_startup_failure_propagates`` pins the asymmetry).

    Teardown runs under ``try/finally`` and swallows its own failures: a shutdown that raises would
    mask the real reason the process is stopping and could strand later teardown steps. The failure
    is logged in full and the context manager exits normally.

    Args:
        app: The application being started; startup values are attached to ``app.state``.

    Yields:
        None — the application is serving for the duration of the ``yield``.

    Raises:
        OSError: The discovery file could not be published, which fails the launch.
    """
    app.state.instance_id = str(uuid.uuid4())
    app.state.agent_token = discovery.mint_token()
    app.state.database = deps.Database()
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

    The runner (:mod:`src.companion.app.server`) binds the socket *before* uvicorn starts and writes
    the port it really got here, so the value reflects the ephemeral fallback rather than whatever
    was preferred. Absence means *never bound*, exactly as absence of ``instance_id`` means *not
    started* — a constructed-but-never-run app cannot masquerade as a serving one. Presence is
    **not** a liveness signal: the value is never cleared, so after shutdown (or a serve failure)
    it still names a port whose socket is gone. Within a running process the distinction is moot —
    the app object dies with :func:`~src.companion.app.server.run` — but do not read this accessor
    as "the server is up".

    This accessor lives in ``main.py`` rather than in the runner so its callers — c1-5's ``Host``
    middleware and c1-7's discovery-file writer — reach the port without importing the process
    runner (and with it uvicorn) from inside a request path.

    Args:
        app: The application to read.

    Returns:
        The bound port, or ``None`` before any bind.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    port: int | None = getattr(app.state, "bound_port", None)
    return port


def agent_token(app: FastAPI) -> str | None:
    """Return the agent credential minted for *app*, or ``None`` if the lifespan never ran.

    The token is minted once per process by :func:`lifespan` and published in the discovery file so
    an agent-side caller can present it. Story c5-5 is the production consumer: ``POST
    /agent/events`` compares the presented credential against this value, and nothing else may.

    **Never serialize it.** It must not enter a response body, a header, a log line, a pydantic
    model that reaches ``app.openapi()``, or a WebSocket frame (AD-5). It lives behind this
    accessor — on ``app.state`` rather than in any declared shape — precisely so there is no schema
    for it to leak through; ``test_discovery.py`` pins the four surfaces that exist today (body,
    headers, logs, schema). The WebSocket frame is c5-3's to pin when the socket exists — nothing
    guards it yet.

    Args:
        app: The application to read.

    Returns:
        The minted token, or ``None`` before startup.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    token: str | None = getattr(app.state, "agent_token", None)
    return token


class _CompanionFastAPI(FastAPI):
    """A ``FastAPI`` whose schema never carries the auto-generated 422 validation response.

    Validation failures answer ``400 invalid_request`` (AC 5), so FastAPI's per-route auto-422
    would document a shape the API never emits — straight into c2-3's generated TypeScript. The
    explicit 422 declaration that used to displace it went away with the 413 ruling, so the
    displacement now lives here, on the schema-build path itself, covering every future validated
    route (c3-1 onward) with no per-route ceremony.
    """

    def openapi(self) -> dict[str, Any]:
        """Build (and cache) the schema, stripped of the unreachable auto-422.

        Returns:
            The OpenAPI schema with FastAPI's auto-generated validation response removed.
        """
        if self.openapi_schema is None:
            self.openapi_schema = without_auto_validation_schema(super().openapi())
        return self.openapi_schema


def build_app() -> FastAPI:
    """Construct the companion ASGI application without touching anything outside the process.

    The app-level ``responses`` is what puts the typed error body into ``app.openapi()`` (AD-12,
    NFR-03): a Pydantic model no route references never reaches ``components.schemas``, so c2-3's
    generator would have nothing to emit and the UI's state panels nothing to switch on. The
    :class:`_CompanionFastAPI` schema hook keeps FastAPI's auto-generated ``HTTPValidationError``
    — a shape the ``invalid_request`` handler makes permanently unreachable — out of it.

    Returns:
        A configured ``FastAPI`` instance whose startup work has **not** yet run. Enter its
        lifespan (serving it, or ``async with lifespan(app)`` in tests) before expecting
        ``app.state`` to hold anything.
    """
    app = _CompanionFastAPI(
        title=_TITLE,
        lifespan=lifespan,
        responses=error_responses(
            "invalid_request", "payload_too_large", "database_unavailable", "internal_error"
        ),
    )
    app.include_router(health.router)
    # Ordering, and it is the whole point: user_middleware[0] is the most recently added
    # middleware, so the error middleware must be installed *last* to end up outermost — where it
    # can type the failures of every middleware added before it. The Host check goes above this
    # line so that a fault in the security envelope itself answers as a typed 500 rather than an
    # untyped traceback (on http scopes — the error middleware passes websocket scopes through,
    # a gap c5-3 owns); c5-2 and c5-5 add their pieces inside install_security, not here.
    install_security(app)
    install_error_handling(app)
    return app

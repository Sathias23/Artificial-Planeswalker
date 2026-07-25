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


async def _shutdown(app: FastAPI) -> None:
    """Release everything the lifespan acquired, in reverse order of acquisition.

    Today that is the database engine's connection pool, if a data-backed request ever caused one to
    be created (c1-6). :meth:`~src.companion.app.deps.Database.dispose` is a no-op when it was not,
    which is the ordinary case for a companion that only ever answered ``/health`` — so there is one
    unconditional call rather than a condition per resource. Story c1-7 removes the discovery file
    here too.

    Args:
        app: The application whose startup resources are being released.
    """
    logger.debug("Companion instance %s shutting down", getattr(app.state, "instance_id", None))
    holder = deps.database(app)
    # Guarded on the accessor, not on hasattr: None means the lifespan never ran, which is possible
    # when a test drives _shutdown directly.
    if holder is not None:
        await holder.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Mint this process's identity on startup and tear down cleanly on exit.

    ``instance_id`` is minted **here** rather than in :func:`build_app` so a constructed-but-never
    -started app has no identity to leak, and so every fresh start is distinguishable — that is
    what lets a caller tell a restarted companion from the one it was talking to (AD-4, FR-14).

    The :class:`~src.companion.app.deps.Database` holder is created beside it, and for the same
    reason it is safe to do so: like the identity mint it is an inert in-process object that cannot
    fail. The **engine** inside it is not created here — a fresh install has no card database yet,
    and AD-10 makes that a served UI state rather than a startup crash (FR-22). Startup therefore
    still has no failure path, which is why nothing needs to move into the ``try``
    (``test_app.py::test_startup_failure_propagates`` pins that).

    Teardown runs under ``try/finally`` and swallows its own failures: a shutdown that raises would
    mask the real reason the process is stopping and could strand later teardown steps. The failure
    is logged in full and the context manager exits normally.

    Args:
        app: The application being started; startup values are attached to ``app.state``.

    Yields:
        None — the application is serving for the duration of the ``yield``.
    """
    app.state.instance_id = str(uuid.uuid4())
    app.state.database = deps.Database()
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

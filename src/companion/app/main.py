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

from fastapi import FastAPI

from src.companion.app.routes import health

logger = logging.getLogger(__name__)

_TITLE = "Artificial Planeswalker Companion"


async def _shutdown(app: FastAPI) -> None:
    """Release everything the lifespan acquired, in reverse order of acquisition.

    Nothing is acquired yet — this story's startup only mints an identity, which needs no release.
    The helper exists so the teardown that stories c1-6 (engine dispose) and c1-7 (discovery-file
    removal) hang their work on is already correct and already covered by a test, rather than being
    retrofitted onto a bare ``yield``.

    Args:
        app: The application whose startup resources are being released.
    """
    logger.debug("Companion instance %s shutting down", getattr(app.state, "instance_id", None))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Mint this process's identity on startup and tear down cleanly on exit.

    ``instance_id`` is minted **here** rather than in :func:`build_app` so a constructed-but-never
    -started app has no identity to leak, and so every fresh start is distinguishable — that is
    what lets a caller tell a restarted companion from the one it was talking to (AD-4, FR-14).

    Teardown runs under ``try/finally`` and swallows its own failures: a shutdown that raises would
    mask the real reason the process is stopping and could strand later teardown steps. The failure
    is logged in full and the context manager exits normally.

    Args:
        app: The application being started; startup values are attached to ``app.state``.

    Yields:
        None — the application is serving for the duration of the ``yield``.
    """
    app.state.instance_id = str(uuid.uuid4())
    logger.info("Companion instance %s started", app.state.instance_id)
    try:
        yield
    finally:
        try:
            await _shutdown(app)
        except Exception:
            logger.exception("Companion shutdown step failed; shutting down anyway")


def build_app() -> FastAPI:
    """Construct the companion ASGI application without touching anything outside the process.

    Returns:
        A configured ``FastAPI`` instance whose startup work has **not** yet run. Enter its
        lifespan (serving it, or ``async with lifespan(app)`` in tests) before expecting
        ``app.state`` to hold anything.
    """
    app = FastAPI(title=_TITLE, lifespan=lifespan)
    app.include_router(health.router)
    return app

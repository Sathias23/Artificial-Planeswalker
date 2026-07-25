"""The in-process seam every Epic C1 story drives the companion backend through (AD-10).

**Why this exists:** ``httpx.ASGITransport`` speaks the ASGI *request* protocol only — it never
sends the ``lifespan`` startup/shutdown messages. A test that "starts the app" by simply making a
request through it would find no ``instance_id``, no engine and no discovery file, because none of
the startup code ever ran. FastAPI's own async-test guidance solves this with the ``asgi-lifespan``
package; story c1-2 decided against a new dependency (Decide-once #2) and instead keeps
:func:`src.companion.app.main.lifespan` a **module-level** function, so a test can enter it directly
with ``async with lifespan(app)``. That also keeps the seam off Starlette internals such as
``app.router.lifespan_context``.

Consequence, and it is load-bearing: startup values must live on ``app.state``, never on a state
dict yielded from the lifespan. Starlette's ``yield {...}`` populates ``scope["state"]`` only under
a real ASGI lifespan handshake, which driving the context manager directly deliberately skips.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from src.companion.app.main import lifespan

BASE_URL = "http://testserver"


@asynccontextmanager
async def _lifespan_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Run *app*'s lifespan and yield a client wired straight into it — no socket, no port.

    Args:
        app: A freshly constructed application, normally from ``build_app()``.

    Yields:
        An ``httpx.AsyncClient`` whose requests are dispatched in-process via ``ASGITransport``,
        with startup already completed and shutdown guaranteed on exit.
    """
    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
            yield client


@pytest.fixture
def lifespan_client():
    """Return the :func:`_lifespan_client` context manager.

    Exposed as a fixture rather than imported directly so every companion test reaches the seam the
    same way, without depending on the conftest module's import path.

    Returns:
        The async context-manager factory, called as ``async with lifespan_client(app) as client``.
    """
    return _lifespan_client

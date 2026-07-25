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

**Why the seam stamps a port (c1-5).** The ``Host`` middleware refuses any request that did not
address the app as loopback on the port the runner actually bound, and it fails *closed* when no
port was bound at all (Decide-once #2 of c1-5). A seam that left ``app.state.bound_port`` unset —
or addressed the app as ``http://testserver`` — would therefore get a typed ``400`` on every
request. So it stamps a port and derives a matching ``base_url`` from it, which httpx turns into a
valid ``Host`` automatically. The upshot is deliberate: **every** companion test now flows through
the real security envelope rather than around it.
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from src.companion.app import main
from src.companion.app.main import lifespan

BASE_URL = "http://testserver"
"""Fallback base URL for an app with no bound port. Not a valid ``Host`` for the companion — which
is the point: a test that asks for no port is asking to be refused."""

_TEST_BOUND_PORT = 54321
"""The port the seam pretends the runner bound.

Deliberately **not** :data:`src.companion.app.server.DEFAULT_PORT` (8765), so no test in the suite
can pass by accidentally agreeing with the production default instead of reading the port the app
was actually given.
"""


@asynccontextmanager
async def _lifespan_client(
    app: FastAPI,
    *,
    base_url: str | None = None,
    headers: Mapping[str, str] | None = None,
    bound_port: int | None = _TEST_BOUND_PORT,
) -> AsyncIterator[httpx.AsyncClient]:
    """Run *app*'s lifespan and yield a client wired straight into it — no socket, no port.

    Args:
        app: A freshly constructed application, normally from ``build_app()``.
        base_url: The URL requests are addressed to, and therefore the ``Host`` httpx sends.
            Defaults to loopback on whatever port the app ends up with, so the security envelope
            accepts it. Pass one explicitly to address the app as something else.
        headers: Headers sent on every request, for a test that needs to override ``Host`` (or
            anything else) per client.
        bound_port: Stamped onto ``app.state.bound_port`` **only if the app has none**, so an app
            that arrives with its own port keeps it. Pass ``None`` to leave the state unset, which
            is how the never-bound case is driven.

    Yields:
        An ``httpx.AsyncClient`` whose requests are dispatched in-process via ``ASGITransport``,
        with startup already completed and shutdown guaranteed on exit.
    """
    if bound_port is not None and main.bound_port(app) is None:
        app.state.bound_port = bound_port
    if base_url is None:
        port = main.bound_port(app)
        base_url = BASE_URL if port is None else f"http://127.0.0.1:{port}"
    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url=base_url, headers=headers
        ) as client:
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

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
from starlette.routing import Mount

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


def keep_spa_mount_last(app: FastAPI) -> FastAPI:
    """Move the SPA mount back to the end of *app*'s route table, and return *app*.

    **Why any test needs this.** ``build_app()`` finishes with ``install_spa(app)``, which mounts
    the committed SPA bundle at ``/`` (c2-2). A mount at ``/`` matches every path and Starlette
    matches routes in list order, so **anything appended afterwards is shadowed** — the endpoint
    never runs and the caller gets ``200`` plus ``index.html``. Production code never hits this
    because every router is registered *above* the ``install_spa(app)`` line, exactly as
    ``main.py`` says.

    Test modules that attach throwaway routes to a real ``build_app()`` instance — the
    raise-on-demand routes in ``test_errors.py``, the database-touching routes in
    ``test_deps.py`` — are the one place that ordering is genuinely inverted, because a decorator
    can only append. This helper restores the production shape after the fact rather than making
    each test reason about route indices.

    Args:
        app: An application whose test routes have just been attached.

    Returns:
        The same application, with the SPA mount once again the final route.
    """
    routes = app.router.routes
    for index, route in enumerate(routes):
        if isinstance(route, Mount) and route.name == "spa":
            routes.append(routes.pop(index))
            return app
    raise AssertionError(
        "No SPA mount found on this app. build_app() is expected to end with install_spa(app); "
        "if that changed, this helper (and tests/unit/companion/test_spa.py::TestMountOrdering) "
        "need updating together."
    )


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point ``PLANESWALKER_DATA_DIR`` at this test's own ``tmp_path``, for every test here.

    **Why this is autouse, and why it is a deliverable rather than hygiene (c1-7 AC 12).** From
    c1-7 onward the lifespan writes a real ``companion.json`` into ``src.paths.data_dir()``, so
    every one of the ~94 ``lifespan_client`` / ``async with lifespan(app)`` entries already in this
    package acquires a filesystem effect on the *developer's* machine. Unisolated, they would race
    each other over one path in ``%LOCALAPPDATA%\\artificial-planeswalker`` and — the damage that
    matters — clobber the discovery file of a companion the user actually has running. The
    ownership guard in ``remove_discovery`` saves the deletion but not the overwrite.

    Only ``PLANESWALKER_DATA_DIR`` is set. Deliberately **not** ``CARDS_DATABASE_URL``: discovery
    never reads it, and c1-6's tests manage that variable per-test. A test that sets
    ``PLANESWALKER_DATA_DIR`` itself still wins, because its ``monkeypatch.setenv`` runs after
    fixture setup.

    ``test_discovery.py::test_the_isolation_fixture_is_active`` pins this, so deleting the fixture
    turns a test red rather than quietly polluting a machine.
    """
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))


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
            that arrives with its own port keeps it. Pass ``None`` to skip stamping — which drives
            the never-bound case on a fresh ``build_app()``, but does **not** unset a port the app
            already carries. The stamp lands on ``app.state`` and therefore outlives this context
            manager: re-entering the seam with the same app reuses the same port, which is what
            lets a test address one app through two consecutive clients.

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

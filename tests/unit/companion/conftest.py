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

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from starlette.routing import Mount
from starlette.websockets import WebSocketState

from src.companion.app import main
from src.companion.app.main import lifespan
from src.companion.app.spa import install_spa
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel

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

    The old mount is **removed and the SPA re-installed**, not merely moved to the end. The
    mount's reserved-prefix set is frozen at install time from the then-current route table, so a
    moved mount would keep a set that predates the throwaway routes — order restored, semantics
    not: a wrong-method request to a test route would get the mount's generic ``405 Allow: GET,
    HEAD`` instead of the route's real ``Allow``, and an extension-less subpath under a test
    route would fall back to the index instead of a typed 404. Re-installing re-derives the set
    from the now-complete table, which is exactly what production does.

    Args:
        app: An application whose test routes have just been attached.

    Returns:
        The same application, with the SPA mount once again the final route and its reservations
        re-derived.
    """
    routes = app.router.routes
    for index, route in enumerate(routes):
        if isinstance(route, Mount) and route.name == "spa":
            del routes[index]
            install_spa(app)
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


_OMIT = object()
"""Sentinel for :func:`drive_handshake`'s header arguments: ``None`` means *send no header*, so
"caller said nothing" needs a value of its own. Without it a test could not ask for the
missing-``Origin`` case at all, which is the case c5-3's Q4 exists to rule."""

_NORMAL_CLOSURE = 1000
"""The close code the client reports when it goes away tidily. Only the *type* of the disconnect
message matters to the drain loop; this is here so the fake is not silently sending ``None``."""


def _websocket_scope(app, *, path, ticket, origin, host):
    """Build the ASGI ``websocket`` scope a handshake against *app* would arrive in.

    Factored out of :func:`drive_handshake` by c5-4, which needed the identical scope for sockets
    that stay **open** — two helpers hand-building one scope is two things to keep in step, and the
    ``Host``/``Origin`` derivation below is exactly the part a divergence would silently break (the
    c5-3 review already caught one bug in it).

    Args:
        app: A companion application whose lifespan is already running.
        path: The path to hand shake at.
        ticket: The ``ticket`` query parameter, or :data:`_OMIT` for no query string.
        origin: The ``Origin`` header; :data:`_OMIT` for this app's own, ``None`` to send none.
        host: The ``Host`` header; :data:`_OMIT` for this app's own authority.

    Returns:
        The scope dict.
    """
    port = main.bound_port(app)
    assert port is not None, (
        "app.state.bound_port is unset — stamp it (directly, or via lifespan_client's default) "
        "before driving a handshake, or this helper silently builds a '127.0.0.1:None' host/"
        "origin header instead of the test-setup failure that actually happened"
    )
    headers = []
    if host is _OMIT:
        headers.append((b"host", f"127.0.0.1:{port}".encode("latin-1")))
    elif host is not None:
        headers.append((b"host", host.encode("latin-1")))
    if origin is _OMIT:
        headers.append((b"origin", f"http://127.0.0.1:{port}".encode("latin-1")))
    elif origin is not None:
        headers.append((b"origin", origin.encode("latin-1")))

    query_string = b"" if ticket is _OMIT else f"ticket={ticket}".encode("latin-1")
    return {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": query_string,
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 51234),
        "server": ("127.0.0.1", port),
        "subprotocols": [],
        "state": {},
    }


class FakeConnection:
    """A registered client with no ASGI machinery behind it (c5-4, Q1/Q5).

    **This is what the structural** :class:`~src.companion.app.state.Connection` **protocol buys.**
    The registry stores anything that can be written to and closed, so every delivery, containment
    and accounting assertion in the suite is driven against an object that records calls — no
    scope, no ``receive``/``send`` pair, no task. The proofs that need the real router are the
    two-tab wire tests, and they use :func:`open_socket` instead.

    Lives here rather than in ``test_ws.py`` because two test modules need it — the fan-out's own
    tests and the route's — and this package already learned at c3-7 what two hand-synchronised
    copies of one fake cost.

    Args:
        fails: Make :meth:`send_text` raise, modelling the tab that went away between the registry
            snapshot and the write.
        client_state: What :func:`~src.companion.app.ws._close_quietly` reads to decide whether a
            close frame is worth attempting. Defaults to connected, the case that exercises it.

    Attributes:
        sent: Every text frame written to this client, in order.
        closed: Every close code this client was closed with.
    """

    def __init__(self, *, fails=False, client_state=WebSocketState.CONNECTED):
        self.sent = []
        self.closed = []
        self.client_state = client_state
        self._fails = fails

    async def send_text(self, data):
        """Record *data*, or raise if this fake was built to fail."""
        if self._fails:
            raise RuntimeError("this client is gone")
        self.sent.append(data)

    async def close(self, code=1000):
        """Record the close code rather than tearing anything down."""
        self.closed.append(code)


class OpenSocket:
    """A handle on a socket that is still open, and everything the app has sent it so far.

    Yielded by :func:`open_socket`. The message list is the *live* one the ASGI ``send`` callable
    appends to, so a frame pushed by a broadcast is visible the moment the broadcast's ``await``
    returns — there is nothing to poll and nothing to wait for, which is what keeps this helper
    inside the package's "a test that sleeps is a defect" rule.

    Attributes:
        sent: Every ASGI message the application has sent on this socket, in order.
    """

    def __init__(self):
        self.sent = []

    @property
    def frames(self):
        """The text frames the application pushed, as strings, in order.

        Server-to-client text arrives as ``{"type": "websocket.send", "text": ...}``; the
        ``websocket.accept`` that opened the socket is deliberately not one of these, so an empty
        list means *nothing was broadcast to this client*.
        """
        return [
            message["text"]
            for message in self.sent
            if message["type"] == "websocket.send" and "text" in message
        ]

    @property
    def was_accepted(self):
        """Whether the handshake was accepted rather than refused."""
        return any(message["type"] == "websocket.accept" for message in self.sent)


@asynccontextmanager
async def open_socket(app, *, ticket, path="/ws", origin=_OMIT, host=_OMIT):
    """Hold one accepted WebSocket open for the body of the block, and hand back what it receives.

    **Why this exists alongside** :func:`drive_handshake` **(c5-4, Q5, Brad 2026-08-08).** That
    helper runs one handshake *to completion*: its ``receive`` exhausts the caller's frames and then
    repeats ``websocket.disconnect`` forever, so the handler always returns before the call does and
    **no socket is ever open at the same time as anything else**. That is the right shape for
    proving what a handshake answers, and it structurally cannot prove what a *broadcast* reaches:
    FR-06's requirement is that **every** connected client receives an event, which needs two
    sockets open concurrently while a third party pushes.

    So this runs the app as a task with a controllable receive queue. The block body executes with
    the handler parked in its drain loop and the connection registered, exactly as it is while a
    real browser sits idle; on exit the queue is fed a ``websocket.disconnect`` and the task is
    awaited, so the handler's ``finally`` runs and the registry is left clean.

    **Still not a real socket.** There is no server, no port and no TCP anywhere — this drives the
    same in-process ASGI callable ``drive_handshake`` does. AD-10 homes the one genuine
    end-to-end proof on **c5-8**, which shipped it at
    ``tests/integration/companion/test_live_backend.py`` (2026-08-09) — and this file still must
    not grow one. The rule reads the same after the story as before it: the one real socket lives
    over there, deselected by ``-m "not integration"``, and everything here stays in-process.

    Args:
        app: A companion application whose lifespan is already running.
        ticket: The ticket to present. Required — an unauthenticated handshake is refused and never
            reaches the open state this helper exists to hold.
        path: The path to hand shake at.
        origin: The ``Origin`` header; omit for this app's own.
        host: The ``Host`` header; omit for this app's own authority.

    Yields:
        An :class:`OpenSocket` whose :attr:`~OpenSocket.frames` grow as the application pushes.
    """
    scope = _websocket_scope(app, path=path, ticket=ticket, origin=origin, host=host)
    handle = OpenSocket()
    incoming = asyncio.Queue()
    incoming.put_nowait({"type": "websocket.connect"})
    settled = asyncio.Event()

    async def receive():
        return await incoming.get()

    async def send(message):
        handle.sent.append(message)
        # Either answer settles the handshake: an accept means the socket is open (and by the time
        # this waiter is resumed the handler has run on to its first real suspension, which is the
        # drain's `receive` — so registration has already happened), a close means it was refused
        # and the block below should not pretend otherwise.
        if message["type"] in {"websocket.accept", "websocket.close"}:
            settled.set()

    served = asyncio.create_task(app(scope, receive, send))
    waiter = asyncio.create_task(settled.wait())
    try:
        # Wait on BOTH, so a handler that raises before sending anything fails the test with its
        # own traceback instead of hanging the suite on an event nobody will ever set.
        await asyncio.wait({served, waiter}, return_when=asyncio.FIRST_COMPLETED)
        if served.done():
            served.result()  # re-raise whatever killed it, rather than reporting a silent absence
        assert handle.was_accepted, (
            f"the handshake was refused, so no socket is open: {handle.sent}"
        )
        yield handle
    finally:
        # Cancelled once, here, and awaited before this context manager returns — cancelling twice
        # without collecting the result (review finding, 2026-08-08) risked a "Task was destroyed
        # but it is pending" warning if teardown outran the cancellation.
        waiter.cancel()
        with suppress(asyncio.CancelledError):
            await waiter
        incoming.put_nowait({"type": "websocket.disconnect", "code": _NORMAL_CLOSURE})
        await served


async def drive_handshake(
    app,
    *,
    path="/ws",
    ticket=_OMIT,
    origin=_OMIT,
    host=_OMIT,
    frames=(),
):
    """Run one WebSocket handshake against *app* at the ASGI level and return everything it sent.

    **Why this shape (c5-3, Q7, Brad 2026-08-08).** ``httpx.ASGITransport`` — the seam every other
    companion test uses — speaks the ASGI *request* protocol only and cannot drive a ``websocket``
    scope at all. Starlette's ``TestClient.websocket_connect`` can, but it runs the app on a thread
    portal with its own lifespan handling, which would put a second lifespan-entry idiom into a
    package that deliberately has exactly one (see this module's docstring). So this generalises
    what ``test_security.py`` already does against the middleware — build a scope, drive it with
    real async ``receive``/``send`` stubs, collect the messages — through the **real** router, and
    leaves the lifespan to the caller's ``async with lifespan_client(app)``.

    That division is what makes the interesting tests possible: the caller mints a ticket over HTTP
    through the ordinary seam and then presents it here, against the same running app, which is the
    actual sequence a browser performs.

    Args:
        app: A companion application whose lifespan is already running.
        path: The path to hand shake at.
        ticket: The value of the ``ticket`` query parameter. Omit for no query string at all;
            pass ``""`` for a present-but-empty parameter.
        origin: The ``Origin`` header. Omit for this app's own origin (the accepted case), or pass
            ``None`` to send no ``Origin`` header at all.
        host: The ``Host`` header. Omit for this app's own authority, which is what the shipped
            :class:`~src.companion.app.security.HostValidationMiddleware` requires.
        frames: Client-to-server messages delivered after the handshake, before the disconnect.

    Returns:
        Every ASGI message the application sent, in order — ``[{"type": "websocket.close", ...}]``
        for a refusal, ``[{"type": "websocket.accept", ...}, ...]`` for an accepted socket.
    """
    scope = _websocket_scope(app, path=path, ticket=ticket, origin=origin, host=host)

    # The connect, then whatever the test wants to say, then a disconnect that repeats forever: a
    # handler that keeps reading past the disconnect must not hang the suite waiting for a message
    # the fake was never going to send.
    incoming = iter([{"type": "websocket.connect"}, *frames])
    sent = []

    async def receive():
        return next(incoming, {"type": "websocket.disconnect", "code": _NORMAL_CLOSURE})

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return sent


@pytest.fixture
def lifespan_client():
    """Return the :func:`_lifespan_client` context manager.

    Exposed as a fixture rather than imported directly so every companion test reaches the seam the
    same way, without depending on the conftest module's import path.

    Returns:
        The async context-manager factory, called as ``async with lifespan_client(app) as client``.
    """
    return _lifespan_client


# =============================================================================================
# The card corpus every card-addressed route is driven against.
#
# Written by c3-2 for ``test_routes_cards.py`` and MOVED here by c3-5, which needs the same six
# cards for ``GET /api/card-image/…``. That is the whole reason for the move: the alternative was
# a second hand-seeded set, and two fixtures claiming to model the same measured corpus drift the
# moment one of them is corrected — which this one already has been, once, by a code review.
# Nothing about the seeded data changed in the move.
# =============================================================================================


def _uuid(suffix: str) -> str:
    """Mint a canonical lowercase hyphenated uuid ending in *suffix*.

    Canonical because the card routes' shape constraint refuses anything else — ``_card()``-style
    ids like ``"card-anchor"`` (which ``test_routes_decks.py`` mints) are rejected with ``400``
    before the handler runs. ``suffix`` must be hex; it is what makes each seeded card
    individually addressable and each id readable in a failure message.

    Args:
        suffix: Up to 12 hex characters identifying this card.

    Returns:
        A uuid of the exact shape ``cards.id`` holds.
    """
    tail = suffix.rjust(12, "0")
    assert len(tail) == 12 and all(c in "0123456789abcdef" for c in tail), suffix
    return f"00000000-0000-4000-8000-{tail}"


# Every card the fixtures seed, by role. Distinguishable on several fields each — c3-1's review
# found 28 green tests over identical fixtures, where a mis-paired projection was invisible.
ANCHOR_ID = _uuid("a0")
SINGLE_FACE_ID = _uuid("b1")
MULTI_FACE_ID = _uuid("c2")
NO_IMAGE_ID = _uuid("d3")
MANY_FACE_ID = _uuid("e4")
SPLIT_FACE_ID = _uuid("e5")
SCHEMA_ONLY_ID = _uuid("e6")
ABSENT_ID = _uuid("ff")

_TOP_LEVEL_IMAGES = {
    "small": "https://cards.scryfall.io/small/split.jpg?1700000001",
    "normal": "https://cards.scryfall.io/normal/split.jpg?1700000002",
    "large": "https://cards.scryfall.io/large/split.jpg?1700000003",
    "png": "https://cards.scryfall.io/png/split.png?1700000004",
    "art_crop": "https://cards.scryfall.io/art_crop/split.jpg?1700000005",
    "border_crop": "https://cards.scryfall.io/border_crop/split.jpg?1700000006",
}
"""The six size keys the real corpus carries, measured 2026-07-31 and re-verified at c3-5.

**Every value is distinct**, which c3-5 made load-bearing: its image route selects one of these
six by name, so identical URLs would let a route that ignored ``size`` entirely pass every test.
The host is a real allowed origin (``cards.scryfall.io``) because that route refuses to fetch from
anywhere else — a fixture on ``cards.example`` would answer ``image_fetch_failed`` for the wrong
reason and hide whatever the test was actually about. The ``?<timestamp>`` suffix is Scryfall's
cache-buster, carried by 245,742 of 245,742 stored URLs.
"""


def _card(card_id: str, name: str, **overrides: object) -> CardModel:
    """Build a complete card row: every non-nullable column, so the insert is realistic.

    Args:
        card_id: The canonical uuid this card is addressed by.
        name: The card's name; also seeds several other fields so the row is distinguishable.
        **overrides: Column values replacing the defaults built here.

    Returns:
        An unsaved ``CardModel``.
    """
    fields: dict[str, object] = {
        "id": card_id,
        "name": name,
        "printed_name": None,
        "oracle_id": f"oracle-{card_id}",
        "mana_cost": f"{{{card_id[-1].upper()}}}",
        "cmc": float(len(name)),
        "type_line": f"Instant — {name}",
        "oracle_text": f"{name} does something.",
        "rarity": "common",
        "set_code": "TST",
        "set_name": "Test Set",
        "collector_number": "1",
        "colors": ["R"],
        "color_identity": ["R"],
        "legalities": {"standard": "legal", "commander": "legal"},
        "games": ["paper", "arena", "mtgo"],
    }
    fields.update(overrides)
    return CardModel(**fields)  # type: ignore[arg-type]


def _point_at(monkeypatch, path: Path) -> Path:
    """Steer ``src.paths.database_url()`` at *path* via ``CARDS_DATABASE_URL``.

    The ``test_routes_decks.py`` pattern: an explicit ``CARDS_DATABASE_URL`` wins over everything,
    so resolution cannot be hijacked by a developer's own environment.
    """
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{path.as_posix()}")
    return path


async def _seed(path: Path, seeder) -> None:
    """Open a session against *path*, hand it to *seeder*, then dispose the engine.

    The engine is disposed before the app is built so the fixture never holds a connection the
    routes then contend with.
    """
    engine = create_engine(f"sqlite+aiosqlite:///{path.as_posix()}")
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            await seeder(session)
    finally:
        await engine.dispose()


async def _ready_database(path: Path) -> None:
    """Create the full schema at *path* and seed the anchor card.

    ``is_database_initialized`` requires a **populated** ``cards`` table, not merely the file, so a
    schema-only database still reads as ``database_not_initialized``.
    """
    engine = create_engine(f"sqlite+aiosqlite:///{path.as_posix()}")
    try:
        await init_database(engine)
        factory = create_session_factory(engine)
        async with factory() as session:
            session.add(_card(ANCHOR_ID, "Anchor Card", image_uris=_TOP_LEVEL_IMAGES))
            await session.commit()
    finally:
        await engine.dispose()


@pytest.fixture
async def ready_db(tmp_path, monkeypatch):
    """A real database file with the full schema and the anchor card, already pointed at.

    The fixture **builds** the database rather than only setting the environment variable: a test
    that forgot would get ``503 database_not_initialized``, which — for the several tests asserting
    on 503 or 404 bodies — is a plausible false green rather than a loud failure (c3-1 review,
    2026-07-31).
    """
    path = _point_at(monkeypatch, tmp_path / "cards.db")
    await _ready_database(path)
    return path


@pytest.fixture
async def image_shapes(ready_db):
    """Seed every image shape the real corpus actually contains.

    **RE-MEASURED after the code review of 2026-07-31, because the first version of this fixture
    was built on a true count read as a false rule.** c3-2 measured "cards carrying BOTH top-level
    and per-face ``image_uris``: 0" — which is true — and generalised it to "a card with a
    top-level image has no ``card_faces``", which is false for 368 real printings. Both review
    layers caught it independently. The corrected census, over 38,261 rows (re-verified
    independently at c3-5, read-only, same numbers):

        image_uris + card_faces NULL ................................. 35,036   (SINGLE_FACE_ID)
        image_uris + card_faces present, faces WITHOUT image_uris .....   368   (SPLIT_FACE_ID)
        image_uris NULL + faces WITH per-face image_uris ..............  2,778   (MULTI_FACE_ID)
        image_uris NULL + faces present, faces WITHOUT image_uris .....    79   (NO_IMAGE_ID)
        image_uris NULL + card_faces NULL .............................     0   (SCHEMA_ONLY_ID)
        face-count histogram ....................... 2 -> 3,222 · 3 -> 2 · 5 -> 1

    Two consequences the first version got wrong, and they are the reason the docstrings on
    ``Card`` and ``read_card`` were rewritten:

    * **``card_faces`` is not the discriminator — per-face ``image_uris`` is.** A split card
      (``Adventurous Eater // Have a Bite``) has two faces *and* a top-level image, because the
      halves share one piece of artwork. A consumer branching on ``card_faces !== null`` renders
      nothing for 368 cards that have a perfectly good image.
    * **"No image anywhere" does not mean "no faces".** All 79 such cards carry a ``card_faces``
      array whose entries have no images; the shape the first fixture seeded for that case
      (``image_uris`` null *and* ``card_faces`` null) matches **zero** rows in the corpus. It is
      still permitted by the schema, so ``SCHEMA_ONLY_ID`` keeps it — labelled as what it is.

    Every URL is on an origin ``src/companion/app/images.py`` will actually fetch from, and every
    one is distinct, so c3-5's route cannot pass a size or face assertion by accident.
    """

    async def seeder(session):
        # 35,036 rows: the ordinary case.
        session.add(
            _card(
                SINGLE_FACE_ID,
                "Single Face",
                type_line="Creature — Human Wizard",
                rarity="rare",
                power="2",
                toughness="3",
                keywords=["Flying"],
                image_uris=_TOP_LEVEL_IMAGES,
                card_faces=None,
            )
        )
        # 368 rows: THE SHAPE THE FIRST VERSION OF THIS FIXTURE DENIED EXISTED. Faces and a
        # top-level image together; no face carries an image of its own.
        session.add(
            _card(
                SPLIT_FACE_ID,
                "Split Halves",
                type_line="Sorcery — Adventure // Sorcery",
                rarity="uncommon",
                image_uris=_TOP_LEVEL_IMAGES,
                card_faces=[
                    {"name": "Split Halves", "mana_cost": "{R}", "type_line": "Sorcery"},
                    {"name": "Other Half", "mana_cost": "{2}{G}", "type_line": "Sorcery"},
                ],
            )
        )
        # 2,778 rows: the DFC case — per-face images, no top-level image. The two faces carry
        # DIFFERENT hosts-paths AND different size key-sets, so c3-5's face selection cannot pass
        # by returning whichever map came first (c3-1's R3 finding).
        session.add(
            _card(
                MULTI_FACE_ID,
                "Two Faced",
                type_line="Creature — Werewolf // Creature — Werewolf",
                rarity="mythic",
                image_uris=None,
                card_faces=[
                    {
                        "name": "Two Faced",
                        "mana_cost": "{1}{R}",
                        "image_uris": {
                            "normal": "https://cards.scryfall.io/normal/front/f.jpg?1700000101",
                            "large": "https://cards.scryfall.io/large/front/f.jpg?1700000102",
                        },
                    },
                    {
                        "name": "Two Faced, Unleashed",
                        "mana_cost": "",
                        "image_uris": {
                            "normal": "https://cards.scryfall.io/normal/back/b.jpg?1700000201",
                            "large": "https://cards.scryfall.io/large/back/b.jpg?1700000202",
                        },
                    },
                ],
            )
        )
        # 79 rows: genuinely no image anywhere — but faces ARE present. This is the real shape.
        session.add(
            _card(
                NO_IMAGE_ID,
                "No Image At All",
                type_line="Token Creature — Zombie // Token Creature — Zombie",
                rarity="uncommon",
                image_uris=None,
                card_faces=[
                    {"name": "No Image At All", "mana_cost": ""},
                    {"name": "No Image Either", "mana_cost": ""},
                ],
            )
        )
        # 0 rows: permitted by the schema, absent from the corpus. Seeded so the wire behaviour of
        # a shape the importer has never produced is known rather than assumed.
        session.add(
            _card(
                SCHEMA_ONLY_ID,
                "Neither Field",
                type_line="Artifact",
                rarity="common",
                image_uris=None,
                card_faces=None,
            )
        )
        session.add(
            _card(
                MANY_FACE_ID,
                "Five Faced",
                type_line="Card // Card // Card // Card // Card",
                rarity="special",
                image_uris=None,
                card_faces=[
                    {
                        "name": f"Face {n}",
                        "image_uris": {
                            "normal": f"https://cards.scryfall.io/normal/{n}/f.jpg?17000003{n:02d}"
                        },
                    }
                    for n in range(5)
                ],
            )
        )
        await session.commit()

    await _seed(ready_db, seeder)
    return ready_db


# =============================================================================================
# The virtual clock and the stall-able upstream — ONE of each, for the whole package.
#
# CONSOLIDATED HERE BY c3-7 (2026-08-01), which `deferred-work.md` named as the trigger: c3-6
# shipped `Upstream` in `test_images.py` and `StallableCdn` in `test_routes_card_image.py`, two
# hand-synchronised fakes modelling the same arbitrarily-slow CDN, and the ledger entry said the
# third consumer should merge them rather than add a third. c3-7 is the third consumer.
#
# They were never quite the same, which is exactly how two fakes of one thing drift: one recorded
# start times off a virtual clock and had no `completed` counter, the other counted completions
# and had no clock. The merged class carries the union, and the clock is optional so a test that
# does not care about time does not have to build one.
# =============================================================================================


class FakeClock:
    """Virtual time: the clock moves only when the pacer sleeps on it (c3-6 AC 9, Q3).

    **This is the whole answer to "how do you test a rate without spending one".** The pacer takes
    its clock and its sleep as constructor parameters, so a test can hand it a pair that advances a
    counter instead of waiting. Start offsets are then asserted **exactly** — ``0.0``, ``0.1``,
    ``0.2`` — at zero wall-clock cost, where a real-time proof would be both slow and flaky on a
    loaded box.

    ``await asyncio.sleep(0)`` inside :meth:`sleep` is a bare yield to the event loop, not a wait:
    it costs no wall clock and it is what keeps the *concurrency* real while the *time* is fake.
    Other tasks genuinely run at that point, so an ordering bug is still visible.

    **The re-entrancy assertion is load-bearing and is the fake checking its own premise.**
    ``now += delay`` is only exact while at most one task sleeps at a time, which holds because the
    pacer sleeps inside its turnstile lock. If a redesign ever sleeps outside that lock, two
    concurrent sleepers would double-advance the clock and every pacing assertion in the package
    would quietly start measuring fiction — so the fake refuses instead.

    Attributes:
        now: The current virtual time, in seconds.
        slept: Every delay the pacer asked for, in order. A pacer that never sleeps leaves this
            empty, which several tests assert directly — including c3-7's proof that a WARM deck
            paint never enters the pacer at all.
    """

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []
        self._sleeping = False

    def time(self) -> float:
        """Return the current virtual time, in the shape ``time.monotonic`` has."""
        return self.now

    async def sleep(self, delay: float) -> None:
        """Advance virtual time by *delay* and yield to the loop.

        Args:
            delay: Seconds to wait for, as the pacer computed them.
        """
        assert not self._sleeping, (
            "two tasks slept on this clock at once — `now += delay` is only exact while the "
            "pacer sleeps inside its turnstile, so this fake would be lying about the numbers"
        )
        self._sleeping = True
        try:
            self.slept.append(delay)
            self.now += delay
            await asyncio.sleep(0)
        finally:
            self._sleeping = False


class StallableUpstream:
    """A stand-in CDN that records every request and can be held open indefinitely.

    An arbitrarily slow upstream expressed as an ``asyncio.Event`` rather than a duration: every
    request parks until a test releases it. That is what lets an interleaving *count* and a permit
    accounting be exact rather than probabilistic — with no wall-clock time involved at all.

    Four things it exists to measure, none of which a response body can show:

    * **that a fetch began at all**, so "zero outbound requests" is a positive observation and not
      an absence of evidence — which is what c3-7's CM-2 assertion rests on;
    * **when** each fetch began, on the pacer's own virtual clock, when one is supplied — c3-6's
      AC 4 is about start times, and c3-5's review theme was a check that ran after the thing it
      was meant to prevent;
    * **how many** requests are open at once, from the transport's own accounting (entered minus
      completed) rather than inferred from timing;
    * **how many finished**, so "nothing is actually queued" can be refuted.

    Args:
        clock: The virtual clock to read start times from. ``None`` — the default — means this
            test does not care about time, and :attr:`started_at` stays empty rather than filling
            with meaningless wall-clock values.
        hold: Start with every request parked. ``False`` — the default — releases immediately, so
            the same class serves an ordinary fast CDN.
        body: The response body. Distinct-by-default is *not* assumed here: a test that needs two
            responses to be distinguishable should say so (c3-1's R3 finding — identical fixtures
            prove nothing).
        content_type: The ``Content-Type`` served back.

    Attributes:
        requested: Every URL asked for, in order.
        started_at: The virtual time each request began, in start order; empty without a *clock*.
        in_flight: How many upstream requests are open right now.
        peak_in_flight: The high-water mark of :attr:`in_flight`.
        completed: How many have finished.
        release: Set it to let parked requests through.
    """

    def __init__(
        self,
        clock: FakeClock | None = None,
        *,
        hold: bool = False,
        body: bytes = b"\xff\xd8body",
        content_type: str = "image/jpeg",
    ) -> None:
        self._clock = clock
        self._body = body
        self._content_type = content_type
        self.requested: list[str] = []
        self.started_at: list[float] = []
        self.in_flight = 0
        self.peak_in_flight = 0
        self.completed = 0
        self.release = asyncio.Event()
        if not hold:
            self.release.set()

    async def handle(self, request: httpx.Request) -> httpx.Response:
        """Answer one request, parking until :attr:`release` is set."""
        if self._clock is not None:
            self.started_at.append(self._clock.time())
        self.requested.append(str(request.url))
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await self.release.wait()
        finally:
            self.in_flight -= 1
        self.completed += 1
        return httpx.Response(200, content=self._body, headers={"content-type": self._content_type})

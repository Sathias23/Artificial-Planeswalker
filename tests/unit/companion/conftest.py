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
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from starlette.routing import Mount

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

"""Story c1-6: the lazy database engine, and what a fresh install is served instead of a crash.

Every test drives a **real** ``build_app()`` through the ``lifespan_client`` seam. The dependency
has no production route yet (c3-1 is its first consumer), so each test that needs a data-backed
request mounts a **test-local** route on the app before entering its lifespan — the same technique
c1-4 and c1-5 used for their otherwise-unreachable paths.

Two disciplines run through the file and both are deliberate:

* **Observable state, not mock arithmetic.** Laziness is asserted as ``engine is None`` and *the
  file still does not exist*; reuse is asserted by object identity (``is``).
* **Non-vacuity.** Every 503 assertion is paired with a request against a *ready* database that
  answers ``200`` from the same route, so the suite cannot pass by a guard that refuses everything
  (the lesson from Greptile's PR #12 catch).

Fixture databases are built with plain ``sqlite3`` rather than the async engine: a fixture built
through the code under test proves nothing.
"""

import asyncio
import logging
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import ArgumentError, DatabaseError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from src.companion.app import deps
from src.companion.app.deps import Database, DbSession, database, database_file
from src.companion.app.errors import CompanionError
from src.companion.app.main import build_app

_DEPS_MODULE = "src.companion.app.deps"
_ERRORS_MODULE = "src.companion.app.errors"


# ---------------------------------------------------------------------------------------------
# Fixture databases — the four readiness shapes, built with plain sqlite3 (Testing standards).
# ---------------------------------------------------------------------------------------------


def _create_cards_table(path: Path) -> None:
    """Create a minimal ``cards`` table at *path* — enough for the readiness probe, nothing more."""
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, name TEXT)")


def _insert_card(path: Path, card_id: str = "c1") -> None:
    """Put one row in ``cards`` at *path*, which is what ``is_database_initialized`` reads."""
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cards (id, name) VALUES (?, ?)", (card_id, "Ancestral")
        )


def _mark_import_in_progress(path: Path, flag: int = 1) -> None:
    """Write the ``import_state`` marker at *path* — the killed-mid-import shape."""
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS import_state "
            "(id INTEGER PRIMARY KEY CHECK (id = 1), in_progress INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO import_state (id, in_progress) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET in_progress = excluded.in_progress",
            (flag,),
        )


def _ready_database(path: Path) -> Path:
    """Build a database at *path* that ``is_database_initialized`` calls ready, and return it."""
    _create_cards_table(path)
    _insert_card(path)
    return path


_DATA_PATH = "/_test/data"
"""Where the test-local route is mounted.

**Decide-once #1: this story ships the seam, not an endpoint.** ``src/`` gains no route — c3-1 owns
``GET /api/decks`` and its own AC says it "uses the shared lazy engine from Story 1.6". A
placeholder data route here would either duplicate c3-1's endpoint or leave a route in ``src/`` that
no UX state consumes, and AD-16's token↔state mapping is 1:1. So the dependency is driven through a
route mounted **in the test**, exactly as c1-4 and c1-5 drove their own otherwise-unreachable paths.
The dead-guard standard is met by exercising every branch, not by shipping a consumer.
"""


_FAIL_PATH = "/_test/fail"
"""A test-local route whose *body* fails against a perfectly good session — the second of AC 9's two
raise sites. Both are inside ``ExceptionMiddleware``, so both reach the registered handler."""

_BOUND_SECRET = "bound-parameter-that-must-not-be-logged"
"""A distinctive value bound into the failing statement. ``str(exc)`` carries the statement *and its
bound parameters* (verified), which is why the handler logs ``exc.orig`` instead — this string is
what proves it."""


def _data_app() -> FastAPI:
    """Return a real ``build_app()`` with the two test-local routes this story is driven through.

    ``/_test/data`` reads through the session it was handed rather than merely accepting it, so a
    dependency that yielded something unusable would fail here instead of passing silently.
    ``/_test/fail`` gets a healthy session and fails inside its own body.

    Returns:
        The application, with its lifespan **not** yet entered.
    """
    app = build_app()

    @app.get(_DATA_PATH)
    async def read_data(session: DbSession) -> dict[str, int]:
        return {"value": (await session.execute(text("SELECT 1"))).scalar_one()}

    @app.get(_FAIL_PATH)
    async def fail_in_the_body(session: DbSession) -> dict[str, int]:
        await session.execute(
            text("SELECT 1 FROM no_such_table WHERE name = :name"), {"name": _BOUND_SECRET}
        )
        raise AssertionError("unreachable: the statement above always raises")

    return app


def _corrupt(path: Path) -> Path:
    """Make *path* a file SQLite refuses to read, and return it.

    The realistic transient shape: the file is present (so the existence check passes and the engine
    is built) but the first read raises ``DatabaseError: file is not a database``.
    """
    path.write_bytes(b"this is definitely not a sqlite database" * 8)
    return path


def _point_at(monkeypatch, path: Path) -> Path:
    """Steer ``src.paths.database_url()`` at *path* via ``CARDS_DATABASE_URL``.

    The precedent is ``tests/integration/mcp_server/test_first_run_data_init.py``: an explicit
    ``CARDS_DATABASE_URL`` wins over everything, so the resolution cannot be hijacked by a
    developer's own environment.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        path: The SQLite file the app should resolve, whether or not it exists.

    Returns:
        *path*, so callers can use this inline.
    """
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{path.as_posix()}")
    return path


# ---------------------------------------------------------------------------------------------
# AC 3: the pure URL -> path function. The table *is* the test.
# ---------------------------------------------------------------------------------------------

_URL_MATRIX = [
    pytest.param(
        "sqlite+aiosqlite:///C:/Users/x/AppData/cards.db",
        "C:/Users/x/AppData/cards.db",
        id="absolute-sqlite-path",
    ),
    pytest.param(
        "sqlite+aiosqlite:///./data/cards.db",
        "./data/cards.db",
        id="relative-sqlite-path",
    ),
    pytest.param("sqlite+aiosqlite:///:memory:", None, id="in-memory-named"),
    pytest.param("sqlite+aiosqlite://", None, id="in-memory-empty-database"),
    pytest.param("postgresql+asyncpg://user@host/cardsdb", None, id="non-sqlite-backend"),
]


class TestDatabaseFile:
    """AC 3: what "the file" is, for every URL shape the resolver can produce."""

    @pytest.mark.parametrize(("url", "expected"), _URL_MATRIX)
    def test_matrix(self, url, expected):
        resolved = database_file(url)

        if expected is None:
            assert resolved is None, (
                f"{url!r} names no file, so the existence check must be skipped — None never means "
                "'not initialized'"
            )
        else:
            assert resolved == Path(expected)

    def test_a_non_sqlite_database_name_is_never_treated_as_a_path(self):
        """``.database`` on a Postgres URL is a database *name*; a file check on it would fire on a
        perfectly valid URL and report a fresh install that is not one."""
        assert database_file("postgresql+asyncpg://user@host/cardsdb") is None


# ---------------------------------------------------------------------------------------------
# AC 1 / 2 / 3 / 6 / 7 / 10: the holder itself, driven directly — no route, no request.
# ---------------------------------------------------------------------------------------------


class TestHolderIsInertUntilUsed:
    """AC 2: a fresh holder has done nothing, and creating one cannot fail."""

    def test_a_new_holder_has_no_engine(self):
        assert Database().engine is None

    def test_constructing_a_holder_touches_no_data_path(self, tmp_path, monkeypatch):
        # data_dir() ends in mkdir(parents=True), so a single resolution in __init__ would create
        # this directory — the same trap test_app.py's inertness test guards construction against.
        never = tmp_path / "never-created"
        monkeypatch.delenv("CARDS_DATABASE_URL", raising=False)
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(never))

        holder = Database()

        assert holder.engine is None
        assert not never.exists()


class TestFirstUseCreatesExactlyOneEngine:
    """AC 2 + AC 6: the engine appears on first use, is reused, and comes from the shared recipe."""

    async def test_first_call_creates_and_second_call_reuses(self, tmp_path, monkeypatch):
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        holder = Database()

        first = await holder.session_factory()
        engine = holder.engine
        second = await holder.session_factory()

        assert isinstance(engine, AsyncEngine)
        # Identity, not a call count: an orphaned second engine would hold a second pool silently.
        assert holder.engine is engine
        assert second is first
        await holder.dispose()

    async def test_the_engine_carries_the_shared_recipe(self, tmp_path, monkeypatch):
        """AC 6: ``create_engine`` is what supplies the busy timeout, so a local
        ``create_async_engine`` call here would drift from ``src/mcp_server/server.py``."""
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        holder = Database()

        factory = await holder.session_factory()

        assert holder.engine is not None
        assert holder.engine.dialect.name == "sqlite"
        # expire_on_commit=False is the half of the recipe a route can actually observe.
        assert factory.kw["expire_on_commit"] is False
        await holder.dispose()

    async def test_concurrent_first_uses_create_one_engine(self, tmp_path, monkeypatch):
        """AC 7: N racing first uses build exactly one engine.

        The count is the assertion, not the successes: a second engine is orphaned *silently*,
        holding a second connection pool nobody disposes.

        Measured caveat, recorded so nobody mistakes this test for the lock's proof: ``_create`` is
        fully synchronous, so on single-threaded asyncio this passes with the lock removed too. The
        two assertions with real teeth are in :class:`TestTheCreationLock` below.
        """
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        calls = []
        real_create_engine = deps.create_engine

        def counting_create_engine(url):
            calls.append(url)
            return real_create_engine(url)

        # Patch where it is looked up (Gotcha 13), not src.data.database's own reference.
        monkeypatch.setattr(deps, "create_engine", counting_create_engine)
        holder = Database()

        factories = await asyncio.gather(*(holder.session_factory() for _ in range(8)))

        assert len(calls) == 1, f"expected one engine creation, got {len(calls)}"
        assert all(factory is factories[0] for factory in factories)
        await holder.dispose()


class TestTheCreationLock:
    """AC 7 + Gotcha 3, pinned by the two claims a removed lock actually breaks.

    A ``gather`` test cannot fail while the creation body has no await in it (verified by removing
    the lock: the concurrency tests stayed green). These two can, and they are what keeps the lock
    from being a dead guard: it belongs to the *instance*, and it is *held* during creation. The
    hazard they guard is the next await added to the creation path silently reintroducing
    double-creation.
    """

    def test_the_lock_belongs_to_the_instance_not_the_module(self):
        """A module-level lock would serialise every app a test run builds and hide a real
        double-creation bug behind a global."""
        first, second = Database(), Database()

        assert first._lock is not second._lock

    async def test_the_lock_is_held_while_the_engine_is_created(self, tmp_path, monkeypatch):
        """Fails if the lock is removed, or if the creation call is moved outside it — which is the
        double-check-inside-the-lock half of AC 7."""
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        holder = Database()
        held = []
        real_create_engine = deps.create_engine

        def observing_create_engine(url):
            held.append(holder._lock.locked())
            return real_create_engine(url)

        monkeypatch.setattr(deps, "create_engine", observing_create_engine)

        await holder.session_factory()

        assert held == [True], "the engine was created outside the holder's lock"
        await holder.dispose()


class TestMissingFileIsServedNotCreated:
    """AC 3: the existence check runs *before* the engine, so nothing is planted on disk."""

    async def test_missing_file_raises_the_token_and_plants_nothing(self, tmp_path, monkeypatch):
        absent = _point_at(monkeypatch, tmp_path / "cards.db")
        holder = Database()

        with pytest.raises(CompanionError) as raised:
            await holder.session_factory()

        assert raised.value.reason == "database_not_initialized"
        # Observable filesystem state, in the style of c1-2's inertness tests: the first connection
        # would have created this file at zero bytes.
        assert not absent.exists(), "a zero-byte cards.db was planted on a fresh install"
        assert holder.engine is None

    async def test_an_in_memory_url_skips_the_check(self, monkeypatch):
        """``None`` from :func:`database_file` means *create the engine* — never *not
        initialized*."""
        monkeypatch.setenv("CARDS_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        holder = Database()

        await holder.session_factory()

        assert holder.engine is not None
        await holder.dispose()

    async def test_the_default_resolution_path_is_used_when_no_url_is_set(
        self, tmp_path, monkeypatch
    ):
        """Gotcha 4: a developer's own ``CARDS_DATABASE_URL`` wins over ``PLANESWALKER_DATA_DIR``,
        so it must be deleted for this to prove anything (precedent: tests/unit/test_paths.py)."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _ready_database(data_dir / "cards.db")
        monkeypatch.delenv("CARDS_DATABASE_URL", raising=False)
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(data_dir))
        holder = Database()

        await holder.session_factory()

        assert holder.engine is not None
        assert holder.engine.url.database == (data_dir / "cards.db").as_posix()
        await holder.dispose()


class TestDispose:
    """AC 10: shutdown releases the pool, and tolerates never having had one."""

    async def test_dispose_without_an_engine_is_a_no_op(self):
        holder = Database()

        await holder.dispose()

        assert holder.engine is None

    async def test_dispose_releases_the_engine_and_leaves_the_holder_honest(
        self, tmp_path, monkeypatch
    ):
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        holder = Database()
        await holder.session_factory()

        await holder.dispose()

        assert holder.engine is None
        # And the holder is usable again — the cached factory was reset with the engine, so a
        # post-dispose call cannot hand out sessions bound to a disposed engine.
        factory = await holder.session_factory()
        assert holder.engine is not None
        assert factory is not None
        await holder.dispose()


class TestAccessor:
    """AC 1: ``app.state.database`` has exactly one reader, shaped like ``main.bound_port``."""

    def test_a_constructed_app_has_no_holder(self):
        assert database(build_app()) is None

    async def test_the_lifespan_creates_an_inert_holder(self, lifespan_client):
        app = build_app()

        async with lifespan_client(app):
            holder = database(app)

            assert isinstance(holder, Database)
            # AD-10: startup creates the holder and nothing else — no engine, no path, no I/O.
            assert holder.engine is None


# ---------------------------------------------------------------------------------------------
# AC 4 / 5 / 12: the dependency, driven through a real request on the test-local route.
# ---------------------------------------------------------------------------------------------


class TestReadinessIsTheProjectsExistingDefinition:
    """AC 4: readiness is ``src.data.database.is_database_initialized`` — not a second rule.

    All four not-ready shapes answer the same token here as they answer on the MCP side, which is
    what stops the two shells disagreeing about the same file (AD-1). Each is paired with the ready
    case below, so none of these can pass by the route refusing everything (non-vacuity).
    """

    async def test_a_ready_database_answers_200(self, tmp_path, monkeypatch, lifespan_client):
        """The non-vacuity anchor for every 503 in this class."""
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        app = _data_app()

        async with lifespan_client(app) as client:
            response = await client.get(_DATA_PATH)

        assert response.status_code == 200
        assert response.json() == {"value": 1}

    async def test_a_missing_file_answers_503(self, tmp_path, monkeypatch, lifespan_client):
        absent = _point_at(monkeypatch, tmp_path / "cards.db")
        app = _data_app()

        async with lifespan_client(app) as client:
            response = await client.get(_DATA_PATH)
            # Read inside the lifespan: _shutdown disposes, which would make this pass trivially.
            holder = database(app)
            assert holder is not None
            assert holder.engine is None, "the engine was created before the file check"

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}
        assert not absent.exists(), "the 503 path planted a zero-byte cards.db"

    async def test_a_present_but_empty_file_answers_503(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        """No ``cards`` table at all — the file exists, so the engine *is* created and the probe is
        what refuses."""
        empty = _point_at(monkeypatch, tmp_path / "cards.db")
        empty.touch()
        app = _data_app()

        async with lifespan_client(app) as client:
            response = await client.get(_DATA_PATH)
            # The counterpart to the missing-file case: here the file *did* exist, so the check
            # passed and the engine was built — the readiness probe is what refused.
            holder = database(app)
            assert holder is not None
            assert holder.engine is not None

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_an_empty_cards_table_answers_503(self, tmp_path, monkeypatch, lifespan_client):
        path = _point_at(monkeypatch, tmp_path / "cards.db")
        _create_cards_table(path)
        app = _data_app()

        async with lifespan_client(app) as client:
            response = await client.get(_DATA_PATH)

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_an_import_killed_midway_answers_503(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        """Rows present but ``import_state.in_progress = 1`` — the fourth not-ready shape
        (:mod:`src.data.import_state`), and the reason readiness is not "the table has rows"."""
        path = _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        _mark_import_in_progress(path)
        app = _data_app()

        async with lifespan_client(app) as client:
            partial = await client.get(_DATA_PATH)
            # Clearing the marker through a *separate* sqlite3 connection makes this its own
            # non-vacuity pairing: the same request, the same engine, one flag apart.
            _mark_import_in_progress(path, flag=0)
            complete = await client.get(_DATA_PATH)

        assert partial.status_code == 503
        assert partial.json() == {"reason": "database_not_initialized"}
        assert complete.status_code == 200


class TestHealthIsUnaffectedByMissingData:
    """AC 5: the process is healthy; only its data is missing."""

    async def test_health_is_200_while_data_is_503(self, tmp_path, monkeypatch, lifespan_client):
        """Both endpoints, the same app, the same lifespan — so this cannot pass by ``/health``
        having been broken into a different shape somewhere else."""
        _point_at(monkeypatch, tmp_path / "cards.db")
        app = _data_app()

        async with lifespan_client(app) as client:
            health = await client.get("/health")
            data = await client.get(_DATA_PATH)

        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert data.status_code == 503
        assert data.json() == {"reason": "database_not_initialized"}


class TestNoHolder:
    """AC 1 + AC 14: the accessor's ``None`` branch, driven rather than left as a dead guard."""

    async def test_a_request_without_a_lifespan_answers_500(self, tmp_path, monkeypatch, caplog):
        """``None`` from the accessor means *the lifespan never ran*, which is a bug in the wiring —
        not a missing database. It must not be laundered into ``database_not_initialized``.

        This is the one test that builds its own client, because the whole point is to **not** enter
        the lifespan (the ``lifespan_client`` seam always does). The port is stamped and the base
        URL matched so the request still passes c1-5's ``Host`` envelope rather than dying at a 400.
        """
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        app = _data_app()
        app.state.bound_port = 54321

        transport = httpx.ASGITransport(app=app)
        with caplog.at_level(logging.ERROR):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://127.0.0.1:54321"
            ) as client:
                response = await client.get(_DATA_PATH)

        assert response.status_code == 500
        assert response.json() == {"reason": "internal_error"}
        assert database(app) is None
        assert any(record.name == _DEPS_MODULE for record in caplog.records), (
            "the unreachable branch must say why it fired"
        )


# ---------------------------------------------------------------------------------------------
# AC 9: a transient database failure is database_unavailable, mapped in exactly one place.
# ---------------------------------------------------------------------------------------------


class TestTransientFailureIsDatabaseUnavailable:
    """AC 9: ``DatabaseError`` — and only ``DatabaseError`` — is the transient net.

    Both raise sites are driven end-to-end, because they fail differently: one from inside the
    dependency (the readiness probe), one from inside a route body. Every 503 here is paired with a
    ``200`` from the same app, so the handler cannot pass by refusing everything.
    """

    async def test_a_failure_inside_the_dependency_answers_503(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        """The file exists, so the engine is built; the readiness probe is what fails."""
        _point_at(monkeypatch, _corrupt(tmp_path / "cards.db"))
        app = _data_app()

        async with lifespan_client(app) as client:
            response = await client.get(_DATA_PATH)

        assert response.status_code == 503
        assert response.json() == {"reason": "database_unavailable"}

    async def test_a_failure_inside_a_route_body_answers_503(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        app = _data_app()

        async with lifespan_client(app) as client:
            # Non-vacuity, in one lifespan: the same session machinery answers 200 next door.
            ok = await client.get(_DATA_PATH)
            response = await client.get(_FAIL_PATH)

        assert ok.status_code == 200
        assert response.status_code == 503
        assert response.json() == {"reason": "database_unavailable"}

    async def test_the_rejection_is_logged_once_without_the_bound_parameters(
        self, tmp_path, monkeypatch, lifespan_client, caplog
    ):
        """``str(exc)`` carries the statement *and its bound parameters* (verified), and the
        companion is one ``fetch`` away from any page in the browser. So the log names the exception
        class and ``exc.orig`` — the DBAPI error — and never the exception's own string form."""
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        app = _data_app()

        with caplog.at_level(logging.WARNING):
            async with lifespan_client(app) as client:
                response = await client.get(_FAIL_PATH)

        assert response.status_code == 503
        records = [
            record
            for record in caplog.records
            if record.name == _ERRORS_MODULE and record.levelno >= logging.WARNING
        ]
        assert len(records) == 1, f"expected exactly one WARNING, got {records}"
        record = records[0]
        assert record.levelno == logging.WARNING
        message = record.getMessage()
        assert "GET" in message
        assert _FAIL_PATH in message
        # The exception class and the DBAPI error, which is what an operator actually needs.
        assert "OperationalError" in message
        assert "no such table: no_such_table" in message
        assert _BOUND_SECRET not in message, (
            "the log leaked the statement's bound parameters — log exc.orig, never str(exc)"
        )
        # Lazy %-style args (project-context.md), not a pre-formatted f-string.
        assert record.args, "the log line must pass its values as lazy % args"

    async def test_a_deterministic_argument_error_is_internal_error_not_unavailable(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        """AD-16's whole reason for ``internal_error``: an ``ArgumentError`` is a bug in *us*, not
        the database saying something went wrong now, so the UI must not quietly retry it.

        A ``CARDS_DATABASE_URL`` with no ``sqlite+aiosqlite:///`` prefix is the live example — the
        long-standing bare-path item in ``deferred-work.md``, which this story gives a defined
        behaviour rather than fixing.
        """
        monkeypatch.setenv("CARDS_DATABASE_URL", str(tmp_path / "cards.db"))
        app = _data_app()

        async with lifespan_client(app) as client:
            response = await client.get(_DATA_PATH)

        assert response.status_code == 500
        assert response.json() == {"reason": "internal_error"}

    def test_the_net_is_database_error_not_the_wider_sqlalchemy_error(self):
        """The ruling, as an executable assertion: ``OperationalError`` is caught (transient),
        ``ArgumentError`` is not (deterministic)."""
        assert issubclass(OperationalError, DatabaseError)
        assert not issubclass(ArgumentError, DatabaseError)
        assert issubclass(DatabaseError, SQLAlchemyError)


# ---------------------------------------------------------------------------------------------
# AC 7: concurrent first requests create exactly one engine.
# ---------------------------------------------------------------------------------------------


class TestConcurrentFirstRequests:
    """AC 7, through real requests rather than the holder alone."""

    async def test_racing_first_requests_create_one_engine(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        """The count is the assertion, not the response codes: a second engine would be orphaned
        silently, holding a second connection pool.

        See :class:`TestTheCreationLock` for why this test alone does not prove the lock works.
        """
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        engines = []
        real_create_engine = deps.create_engine

        def counting_create_engine(url):
            engine = real_create_engine(url)
            engines.append(engine)
            return engine

        # Patch the *lookup* site (Gotcha 13): deps imports create_engine by name.
        monkeypatch.setattr(deps, "create_engine", counting_create_engine)
        app = _data_app()

        async with lifespan_client(app) as client:
            responses = await asyncio.gather(
                *(client.get(_DATA_PATH) for _ in range(6)),
            )
            holder = database(app)
            assert holder is not None
            assert holder.engine is engines[0]

        assert len(engines) == 1, f"expected one engine creation, got {len(engines)}"
        assert [response.status_code for response in responses] == [200] * 6


# ---------------------------------------------------------------------------------------------
# AC 8: a database that appears while the backend runs is picked up with no restart (FR-22).
# ---------------------------------------------------------------------------------------------


class TestDatabaseAppearingAtRuntime:
    """Both paths, because they fail differently — one has no engine yet, one already has one."""

    async def test_no_engine_yet_then_the_file_appears(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        path = _point_at(monkeypatch, tmp_path / "cards.db")
        app = _data_app()

        async with lifespan_client(app) as client:
            missing = await client.get(_DATA_PATH)
            holder = database(app)
            assert holder is not None
            assert holder.engine is None, "nothing may be created while the file is absent"

            # The user asks their agent to run initialize_database; here, plain sqlite3 stands in.
            _ready_database(path)
            appeared = await client.get(_DATA_PATH)
            assert holder.engine is not None, "the engine is created on the request that needs it"

        assert missing.status_code == 503
        assert missing.json() == {"reason": "database_not_initialized"}
        assert appeared.status_code == 200
        assert appeared.json() == {"value": 1}

    async def test_a_cached_engine_sees_a_schema_created_underneath_it(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        """The engine is already cached against a present-but-empty file. SQLite re-reads the schema
        per statement, so no engine invalidation is needed — and adding one would be machinery with
        no failing test behind it (Gotcha 11)."""
        path = _point_at(monkeypatch, tmp_path / "cards.db")
        path.touch()
        app = _data_app()

        async with lifespan_client(app) as client:
            not_ready = await client.get(_DATA_PATH)
            holder = database(app)
            assert holder is not None
            cached = holder.engine
            assert cached is not None, "a present file means the engine was built"

            # A *separate* sqlite3 connection writes the schema and a row.
            _ready_database(path)
            ready = await client.get(_DATA_PATH)
            assert holder.engine is cached, "the same cached engine served both requests"

        assert not_ready.status_code == 503
        assert not_ready.json() == {"reason": "database_not_initialized"}
        assert ready.status_code == 200


# ---------------------------------------------------------------------------------------------
# AC 10: shutdown disposes the engine, and tolerates never having had one.
# ---------------------------------------------------------------------------------------------


class TestShutdownDisposesTheEngine:
    """Two cases, because the interesting one is the app that never took a data request."""

    async def test_dispose_is_reached_after_an_engine_was_created(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        _point_at(monkeypatch, _ready_database(tmp_path / "cards.db"))
        app = _data_app()

        async with lifespan_client(app) as client:
            assert (await client.get(_DATA_PATH)).status_code == 200
            holder = database(app)
            assert holder is not None
            engine = holder.engine
            assert engine is not None
            pool_before = engine.sync_engine.pool

        # Observable state rather than a mock: dispose() releases the pool and recreates it, so a
        # different pool object is proof the disposal really happened.
        assert engine.sync_engine.pool is not pool_before
        assert holder.engine is None

    async def test_shutdown_is_clean_on_an_app_that_never_took_a_data_request(
        self, tmp_path, monkeypatch, lifespan_client, caplog
    ):
        """The ordinary case: a companion that only ever answered ``/health`` has nothing to
        release, and ``dispose()`` must not turn that into a logged teardown failure."""
        absent = _point_at(monkeypatch, tmp_path / "cards.db")
        app = _data_app()

        with caplog.at_level(logging.WARNING):
            async with lifespan_client(app) as client:
                assert (await client.get("/health")).status_code == 200

        holder = database(app)
        assert holder is not None
        assert holder.engine is None
        assert not absent.exists(), "a health-only run touched the database file"
        # main.lifespan swallows-and-logs a failing teardown, so a raising dispose() would show up
        # here as an ERROR rather than as a test failure. Scoped to this package's loggers so a
        # third-party warning emitted during the lifespan cannot fail the test as a false positive.
        assert not [
            record
            for record in caplog.records
            if record.levelno >= logging.WARNING and record.name.startswith("src.companion")
        ], "teardown logged a failure on an app that never created an engine"

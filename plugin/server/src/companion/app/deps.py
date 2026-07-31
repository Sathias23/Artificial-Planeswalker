"""The lazy database engine and the session dependency every data-backed route shares (AD-2, AD-10).

**Why the engine is lazy.** A fresh install ships no card database — the Scryfall set is excluded by
licence, so ``cards.db`` does not exist until the user asks their agent to run
``initialize_database``. Building the engine in ``build_app()`` or in the lifespan would therefore
turn that entirely normal first run into a startup crash, and would make every future test need a
database on disk. AD-10 rules the other way: *the database engine is created lazily and its absence
is a served UI state, not a startup failure* — which is what makes FR-22 hold. So construction stays
inert, the lifespan creates only an empty :class:`Database` holder (an in-process object, no I/O),
and the engine appears on the **first** request that actually needs a session.

**Why the file check precedes engine creation.** ``create_async_engine(...)`` touches no disk, but
the **first connection creates a zero-byte SQLite file** (verified in this environment). Letting the
readiness probe discover the absence would mean the *read-only* read model plants an empty
``cards.db`` in the user's data directory on every fresh-install request — an artefact that outlives
the request and that the next reader has to reason about. The check also keeps the missing-directory
case honest: a URL under a directory that does not exist raises ``OperationalError: unable to open
database file``, a ``DatabaseError``, which
:func:`~src.companion.app.errors.database_error_handler` would otherwise report as the *transient*
``database_unavailable`` when the truth is "there is no database".

**Why the recipe is shared with the MCP side.** The engine comes from
:func:`src.data.database.create_engine` and the factory from
:func:`src.data.database.create_session_factory` — never a local ``create_async_engine`` call — so
the busy-timeout (``connect_args={"timeout": 5}``) and ``expire_on_commit=False`` recipe cannot
drift from ``src/mcp_server/server.py``. Readiness is likewise
:func:`src.data.database.is_database_initialized`, the same function every MCP tool uses: a second
definition here would let the two shells disagree about the same file (AD-1). The verdict is
re-probed on every request and never cached — that is what lets a database created while the backend
runs be picked up with no restart, at a cost of a few tiny SELECTs against local SQLite (noted for
c10-3, which owns latency hardening).

**Why there is no ``mode=ro``.** PRD NFR-02 names it; AD-2 deliberately overrides it. ``mode=ro``
drags in the WAL ``-shm`` Windows landmine and ``immutable`` would foreclose FR-16. Read-only is
enforced structurally instead, by ``tests/unit/companion/test_import_boundary.py`` — nothing under
``src/companion`` can reach a write path. The PRD amendment is c8-3's.

The exception→token mapping lives next door in :mod:`src.companion.app.errors`
(:func:`~src.companion.app.errors.install_error_handling`), not here: that module is already the one
answer to "which exception becomes which token". This module keeps the engine; that one keeps the
mapping.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.requests import Request

from src.companion.app.errors import CompanionError
from src.data.database import create_engine, create_session_factory, is_database_initialized
from src.paths import database_url

logger = logging.getLogger(__name__)

_MEMORY = ":memory:"
"""SQLite's in-memory database name. Names no file, so there is nothing to check for."""

_SQLITE_BACKEND = "sqlite"
"""The only backend whose ``.database`` component is a filesystem path. On every other backend it is
a database *name*, and an existence check on it would refuse a perfectly valid URL."""


def database_file(url: str) -> Path | None:
    """Return the SQLite file *url* addresses, or ``None`` when it addresses no file.

    Pure and total, so AC 3's matrix is testable without an engine. ``None`` means **skip the
    existence check and create the engine**; it never means "not initialized".

    Args:
        url: A SQLAlchemy URL string, normally from :func:`src.paths.database_url`.

    Returns:
        The ``Path`` the URL names, or ``None`` for an in-memory SQLite database (``:memory:`` or an
        empty database component) and for any non-sqlite backend.

    Example:
        >>> database_file("sqlite+aiosqlite:///:memory:") is None
        True
    """
    parsed = make_url(url)
    if parsed.get_backend_name() != _SQLITE_BACKEND:
        return None
    if not parsed.database or parsed.database == _MEMORY:
        return None
    return Path(parsed.database)


class Database:
    """The per-app holder for the lazily created engine and its session factory (AD-10).

    Constructing one is free and cannot fail: no URL is resolved, no path is touched, no engine is
    built. That is what lets the lifespan create it beside the ``instance_id`` mint without widening
    the startup surface (``test_app.py::test_startup_failure_propagates`` pins that asymmetry).

    The engine is created by the **first** :meth:`session_factory` call, behind a lock this instance
    owns — never a module-level one, which would serialise unrelated apps in a test run and hide a
    real double-creation bug behind a global. The lock is created here rather than in the running
    loop because ``asyncio.Lock`` no longer binds a loop at construction on Python 3.10+.

    A note on what the lock currently buys, so a later reader does not mistake defence for
    necessity: :meth:`_create` is **fully synchronous**, so on single-threaded asyncio the
    check-then-assign in :meth:`session_factory` cannot actually be interleaved today, and a
    ``gather`` of concurrent first requests creates one engine with or without the lock (measured —
    see the story's Debug Log). The lock is kept because it is free and because the *next* await
    added to the creation path — an async pre-check, a migration probe — would otherwise reintroduce
    silent double-creation, whose symptom is an orphaned second connection pool that nothing
    disposes. ``test_deps.py`` pins the two properties that do have teeth: the lock is per-instance,
    and it is **held** while the engine is being created.

    Example:
        >>> Database().engine is None
        True
    """

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._lock = asyncio.Lock()

    @property
    def engine(self) -> AsyncEngine | None:
        """The engine, or ``None`` until the first data-backed request creates it.

        Read-only on purpose: the creation path is :meth:`session_factory`, so there is exactly one
        place an engine can come into existence and exactly one place the lock is held.
        """
        return self._engine

    async def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Return the session factory, creating the engine on the first call.

        Returns:
            The cached ``async_sessionmaker``. The same object on every call, so a route cannot end
            up bound to a second engine.

        Raises:
            CompanionError: ``database_not_initialized`` when the URL names a SQLite file that does
                not exist. Raised *before* any engine is created, because the first connection would
                otherwise create that file at zero bytes — the read-only read model writing to the
                user's data directory on a fresh install.
        """
        if self._session_factory is not None:
            return self._session_factory
        async with self._lock:
            # Double-check *inside* the lock: N racing first requests must produce one engine, and
            # without this the loser of the race silently orphans a second connection pool.
            if self._session_factory is not None:
                return self._session_factory
            self._session_factory = self._create()
            return self._session_factory

    def _create(self) -> async_sessionmaker[AsyncSession]:
        """Resolve the URL once, check the file, then build the engine and its factory.

        One resolution is the point: the existence check and the engine are handed the *same*
        string, so they can never disagree about which file they mean.

        Returns:
            A factory bound to the newly created engine, which is also cached on the instance.

        Raises:
            CompanionError: ``database_not_initialized`` when the resolved SQLite file is absent.
        """
        # Resolved here and never at import, module or construction time: database_url() reaches
        # data_dir(), which mkdirs (Gotcha 2). First-request time is acceptable; earlier is not.
        url = database_url()
        path = database_file(url)
        if path is not None and not path.exists():
            logger.info("Card database not found at %s; serving database_not_initialized", path)
            raise CompanionError("database_not_initialized")
        engine = create_engine(url)
        # Factory first, engine published second: if the factory construction ever raised, a
        # half-initialized holder would re-enter _create and orphan this engine's pool.
        factory = create_session_factory(engine)
        self._engine = engine
        # The one line an operator reads to confirm which database the companion actually found.
        # Rendered with the password hidden: the URL can be user-supplied via CARDS_DATABASE_URL,
        # and a non-SQLite URL may carry credentials.
        logger.info(
            "Card database engine created for %s",
            make_url(url).render_as_string(hide_password=True),
        )
        return factory

    async def dispose(self) -> None:
        """Release the engine's connection pool, if one was ever created.

        Safe to call when no engine exists, which is the common case: a companion that served no
        data request has nothing to release. The cached factory is dropped along with the engine so
        the holder stays honest — a post-dispose caller gets a fresh engine rather than sessions
        bound to a disposed one.

        Runs under the same lock as creation, so a first request racing shutdown cannot re-create
        an engine in the window where dispose has cleared the cache but not yet released the pool.
        """
        async with self._lock:
            engine = self._engine
            if engine is None:
                return
            await engine.dispose()
            # Cleared only after the dispose succeeds: a raising dispose leaves the holder still
            # pointing at the engine, rather than stranding an undisposed pool behind a None that
            # no retry could ever reach.
            self._engine = None
            self._session_factory = None
            logger.debug("Card database engine disposed")


def database(app: FastAPI) -> Database | None:
    """Return the :class:`Database` holder for *app*, or ``None`` if the lifespan never ran.

    The single reader of ``app.state.database``, mirroring
    :func:`src.companion.app.main.bound_port` so the state key has one construction site and one
    accessor. ``None`` means **the lifespan never ran** — a constructed-but-never-started app, which
    on a supported path only happens in a test; a request served against one answers
    ``500 internal_error`` rather than pretending the database is merely missing.

    Args:
        app: The application to read.

    Returns:
        The holder, or ``None`` before startup.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    holder: Database | None = getattr(app.state, "database", None)
    return holder


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a session for one request, refusing early if the database is not ready.

    Raising here is correct and is the opposite of c1-5's send-don't-raise ruling: a dependency is
    solved inside the router, which is *inside* Starlette's ``ExceptionMiddleware``, so a
    :class:`~src.companion.app.errors.CompanionError` raised from here does reach its handler and
    does answer with its own token (verified). c1-5's middleware sits on the other side of that
    boundary — the difference is position in the stack, not the exception.

    Readiness is re-probed on **every** request and never cached. That is deliberate: a database
    created while the backend is running must be picked up with no restart (FR-22), which a
    remembered ``True`` would break as surely as a remembered ``False``.

    Nothing runs after the ``yield`` beyond letting the ``async with`` close the session. An
    exception raised *after* the response has been sent escapes every handler and every middleware
    (verified), so no cleanup that can throw may be added here.

    Args:
        request: The request being served; the holder is read from ``request.app``.

    Yields:
        An ``AsyncSession`` from the shared factory, against a database confirmed ready.

    Raises:
        CompanionError: ``database_not_initialized`` when the file is absent or the database is not
            yet populated (the same verdict every MCP tool reads), or ``internal_error`` when the
            lifespan never ran and there is therefore no holder to use.
    """
    holder = database(request.app)
    if holder is None:
        # Unreachable on every supported path — the lifespan always runs before a request is served
        # — but a missing holder is a wiring bug, not a missing database, and must not be laundered
        # into database_not_initialized. AD-16 added internal_error for exactly this distinction.
        logger.error(
            "No database holder on the app serving %s %s; the lifespan did not run",
            request.method,
            request.url.path,
        )
        raise CompanionError("internal_error")
    factory = await holder.session_factory()
    async with factory() as session:
        if not await is_database_initialized(session):
            raise CompanionError("database_not_initialized")
        yield session


DbSession = Annotated[AsyncSession, Depends(get_session)]
"""The annotation every data-backed handler writes, and the only one it should.

Stories c3-1 (``GET /api/decks``, ``GET /api/deck/{deck_id}``), c3-2
(``GET /api/cards/{card_id}``) and c3-3 (``GET /api/deck/{deck_id}/format-check``) annotate a
parameter with this and inherit the whole contract: the lazy engine, the readiness probe, the
``503`` tokens and the shared recipe. None of them re-derives any of it. **All three are shipped
and did exactly that** — none constructs an engine, calls ``is_database_initialized``, reads
``request.app.state`` or writes a ``try/except DatabaseError``, and each proves the two ``503``
answers through its real routes.

Mind the two spellings, which are not a typo: the deck detail route is **singular**
``/api/deck/{deck_id}`` and the card route is **plural** ``/api/cards/{card_id}``. Each matches
the PRD, the spine, the epic split — and c3-3's format check hangs off the singular one as
``/api/deck/{deck_id}/format-check``, so the deck spelling now has two routes behind it.

Example:
    >>> from typing import get_args
    >>> get_args(DbSession)[0].__name__
    'AsyncSession'
"""

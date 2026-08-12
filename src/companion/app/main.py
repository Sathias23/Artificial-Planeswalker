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
from src.companion.app import deps, images, state
from src.companion.app.body_cap import install_body_cap
from src.companion.app.errors import (
    error_responses,
    install_error_handling,
    without_auto_validation_schema,
)
from src.companion.app.routes import active_deck, agent_events, cards, decks, health, session
from src.companion.app.security import install_security
from src.companion.app.spa import install_spa
from src.companion.app.ws import router as ws_router

logger = logging.getLogger(__name__)

_TITLE = "Artificial Planeswalker Companion"


def _publish_discovery(app: FastAPI) -> None:
    """Publish where this process is and how to authenticate to it (AD-4).

    The record names :func:`bound_port` — the port the runner *actually* bound — so an ephemeral
    fallback is what lands in the file rather than whatever was preferred. ``None`` means nobody
    bound a socket (a ``build_app()`` served directly, or a test entering the lifespan without a
    port), and there is nothing truthful to publish: the write is skipped and startup continues.
    That skip logs at WARNING rather than INFO because a companion nobody can find is a real
    problem for the user to see, not ordinary news — the same reasoning as ``server.py``'s bind
    fallback. (Until c1-9 configured the root logger it was also the only level that surfaced at
    all, via ``logging.lastResort``; the level stands on its own merits now that both do.)

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

    Three things, in this order:

    1. **The discovery file** (c1-7). Retracted first, so the process stops advertising itself as
       early as possible — a tool that reads the file during teardown gets *app not running*
       rather than a port whose socket is about to close.
       :func:`~src.companion.discovery.remove_discovery` is ownership-guarded and never raises, so
       a foreign entry survives and an unlink failure cannot strand the dispose below it.
    2. **The outbound image client** (c3-5). Closed before the engine, mirroring the order it was
       created in, so its connection pool is released rather than left to the garbage collector —
       which on an unclosed ``httpx.AsyncClient`` produces a ``ResourceWarning`` and, under a
       hostile upstream, a socket that outlives the request that opened it.
    3. **The database engine's connection pool**, if a data-backed request ever caused one to be
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
    # try/finally, not sequence: step 1 is certified never to raise, but `aclose` carries no such
    # guarantee, and a failing close must not strand the engine dispose below it — the exact
    # stranding this docstring credits step 1 with avoiding (review 2026-08-01).
    try:
        client = images.image_client(app)
        if client is not None:
            await client.aclose()
    finally:
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
    and a restarted backend invalidates the token a tool was holding
    (:func:`~src.companion.client.push_event`'s retry-once absorbs exactly that). It reaches only
    two places: ``app.state`` and the discovery file (AD-5).

    The :class:`~src.companion.app.deps.Database` holder is created beside them, and for the same
    reason it is safe to do so: like the identity mint it is an inert in-process object that cannot
    fail. The **engine** inside it is not created here — a fresh install has no card database yet,
    and AD-10 makes that a served UI state rather than a startup crash (FR-22).

    c3-5's outbound image client is created here for a *different* reason, and the difference is
    worth stating: constructing an ``httpx.AsyncClient`` opens no socket, so ``build_app()`` could
    hold one without breaking AD-10's no-side-effects rule. What it could not do is **close** it.
    A client per process is what gives ~100 tiles of a deck view one TLS handshake instead of a
    hundred, and only the lifespan has a teardown to release the pool in — so the thing that needs
    closing is created where the closing happens (Q5, Brad 2026-08-01).

    c3-6's :class:`~src.companion.app.images.Pacer` is created on the line after it, and for a
    *third* reason worth distinguishing from both: it needs no teardown at all, so nothing about
    :func:`_shutdown` changes for it. What puts it here rather than in ``build_app()`` is that
    ~100 tiles must be **one** queue, and the lifespan is where this process's shared things are
    made — the same reasoning as the client, minus the closing. Constructing one is free and
    cannot fail (``asyncio`` primitives no longer bind a loop at construction), so the startup
    asymmetry ``test_app.py::test_startup_failure_propagates`` pins is untouched: publishing the
    discovery file is still the only step that can fail. The pacer is created **after** the client
    it paces, mirroring the order they are used in, and AC 2 gates that this is the one and only
    place in ``src/companion`` where one is constructed (Q1, Brad 2026-08-01).

    c3-7's :class:`~src.companion.app.images.DiskCache` follows on the next line, and it is the
    **first thing created here that can fail** — which is why it is created through
    :func:`~src.companion.app.images.build_image_cache` rather than by a constructor call. That
    function resolves the cache root and creates it, and on an ``OSError`` logs at WARNING and
    returns ``None``, so ``app.state.image_cache`` is always set and the value itself carries
    "there is no cache this run". **This is what keeps the startup asymmetry above literally
    true** (Q6, Brad 2026-08-01): the app is *fully functional* without a cache — every request
    simply fetches, exactly as it did at c3-6 — so failing the launch would be disproportionate in
    a way a half-launched rendezvous is not, and it would mean editing the ruling
    ``test_startup_failure_propagates`` exists to protect. It is created **here and not in**
    ``build_app()`` for the reason that module docstring gives above: ``src.paths.data_dir()``
    ``mkdir``\\ s, and AD-11 says the lifespan creates the cache root. Like the pacer it needs no
    teardown, so :func:`_shutdown` is untouched by it.

    c3-4's :class:`~src.companion.app.state.ActiveDeckSlot` is created on the same line of reasoning
    and is the first state this process *owns* rather than projects. Creating it here rather than in
    ``build_app()`` is what makes FR-07's restart behaviour structural: the slot is reachable only
    through ``app.state``, a fresh process gets a fresh app, and the previous process's active deck
    has nowhere to have survived. Nothing persists it, and nothing should.

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
    app.state.active_deck = state.ActiveDeckSlot()
    # Same shape and the same reason as the negative cache below: a dict and a clock, so there is
    # no `build_*` factory, nothing lands in `_shutdown`, and AD-15's "publishing the discovery
    # file is the ONLY startup step that may fail a launch" stays literally true (c5-2). Created
    # here rather than in `build_app()` so that function keeps its zero-side-effect property
    # (AD-10) — and so a restart genuinely begins with an empty store (CM-3).
    app.state.ticket_store = state.TicketStore()
    # The third holder from `state.py`, and the same shape for the third time: a set, so no
    # `build_*` factory and nothing in `_shutdown` (c5-4). Deliberately NOT torn down — closing
    # every registered socket on shutdown would be a second close path racing uvicorn's own, and
    # the process is ending anyway; the registry dies with it, which is CM-3's whole point.
    app.state.connections = state.ConnectionRegistry()
    app.state.image_client = images.build_image_client()
    app.state.image_pacer = images.Pacer()
    app.state.image_cache = images.build_image_cache()
    # No `build_*` factory and nothing in `_shutdown`, unlike the disk cache on the line above:
    # constructing a negative cache is a dict and a clock, so it cannot fail. That is what keeps
    # AD-15's ruling literally true — publishing the discovery file below stays the ONLY startup
    # step that may fail a launch — and it is why `test_app.py::test_startup_failure_propagates`
    # needed no edit for this story. Predicted at context time and confirmed by measurement (c3-8).
    app.state.negative_cache = images.NegativeCache()
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
    an agent-side caller can present it.

    **The one comparison site is** :func:`~src.companion.app.security.agent_token_is_valid`, reached
    through the :data:`~src.companion.app.security.AgentToken` dependency — nothing else may read
    this accessor to authenticate. c3-4 is the first consumer (``PUT /api/active-deck``), two
    stories ahead of the c5-5 that was scheduled to build the seam; c5-5's ``POST /agent/events``
    inherits the same dependency rather than writing a second check. (The previous version of this
    paragraph named c5-5 as the *only* consumer, which c3-4 made false — see AC 20 row 1 of its
    story record.)

    **Never serialize it.** It must not enter a response body, a header, a log line, a pydantic
    model that reaches ``app.openapi()``, or a WebSocket frame (AD-5). That rule is unchanged by
    gaining a consumer: the credential check reads the value and answers a *boolean*, so the token
    itself never reaches a response or a log — the rejection log names the path and the fact, never
    the presented value or the expected one. It lives behind this accessor — on ``app.state`` rather
    than in any declared shape — precisely so there is no schema for it to leak through;
    ``test_discovery.py`` pins the four surfaces that exist today (body, headers, logs, schema),
    and c3-4 extended each of them to cover the first route that reads it. The WebSocket frame is
    c5-3's to pin when the socket exists — nothing guards it yet.

    **``None`` is a rejection, never a wildcard.** Returning ``None`` before startup is why the
    comparison must fail closed: an implementation that compared a missing header against a missing
    token would authenticate every request on an app whose lifespan never ran.
    :func:`~src.companion.app.security.agent_token_is_valid` refuses when *either* side is missing,
    matching :func:`~src.companion.app.security.host_is_allowed`.

    Args:
        app: The application to read.

    Returns:
        The minted token, or ``None`` before startup.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    token: str | None = getattr(app.state, "agent_token", None)
    return token


_DOCSTRING_SECTIONS = frozenset(
    {
        "Args:",
        "Arguments:",
        "Attributes:",
        "Example:",
        "Examples:",
        "Keyword Args:",
        "Keyword Arguments:",
        "Raises:",
        "Returns:",
        "Todo:",
        "Warns:",
        "Yields:",
    }
)
"""The Google-style section headers that end a description (c2-3, Q1).

``Note:`` and ``Warning:`` are deliberately **absent**: they are ordinary prose a reader of the
generated types or ``/docs`` genuinely wants, where the twelve above are Python-internal —
parameter names, exception classes and doctests mean nothing to a TypeScript consumer.
"""

_DATA_KEYS = frozenset({"example", "examples", "default", "const", "enum"})
"""Schema keys whose subtrees are payload data, not documentation (c2-3 review, 2026-07-27).

An example payload is free to carry a field named ``description`` — c3-1's decks have one — and
its value is data the schema must reproduce byte-for-byte, never a docstring to truncate. The
walk therefore does not descend past these keys. (Inside a ``properties`` map the same words are
property *names*, not data markers, so the skip does not apply there.)
"""


def _summary_before_sections(description: str) -> str:
    """Return *description* up to its first Google-style section header.

    Args:
        description: A docstring-derived description, already dedented by FastAPI.

    Returns:
        The leading prose, trailing whitespace stripped. Empty if the description opens with a
        section header.
    """
    lines = description.split("\n")
    for index, line in enumerate(lines):
        # .strip() rather than an exact match: FastAPI dedents by the common prefix, so a header
        # sits at column 0 today — but a docstring whose first line is indented differently would
        # leave one indented, and it should still terminate the summary.
        if line.strip() in _DOCSTRING_SECTIONS:
            lines = lines[:index]
            break
    return "\n".join(lines).rstrip()


def without_python_docstring_sections(schema: dict[str, Any]) -> dict[str, Any]:
    """Truncate every ``description`` in *schema* at its first Google-style section header.

    FastAPI uses a route's docstring as the operation ``description`` and a Pydantic class's
    docstring as the schema ``description``, and ``openapi-typescript`` emits both verbatim as
    JSDoc. Measured at the c2-3 baseline, for one endpoint and two models: **186 generated lines,
    roughly 130 of them prose**, including ``Args:\\n    request: The incoming request, used only
    to reach app.state.instance_id`` and ``>>> ErrorResponse(reason="deck_not_found")
    .model_dump()``. Those sections are Python's business — they name parameters a TypeScript
    caller cannot pass and exceptions it cannot catch — and every docstring edit anywhere on a wire
    model would redden both drift gates until the artifacts were regenerated.

    So the boundary is here: **descriptions that cross the wire are summaries, not docstrings.**
    Write route and model docstrings normally; the leading paragraphs are what the frontend and
    ``/docs`` see. The useful half survives — ``ErrorResponse``'s enumeration of what each token
    means on the glass is exactly what c2-9 needs on hover.

    Applies to every documentation ``description`` at any depth, so a ``Field(description=...)``
    on a c3-1 model is covered with no further work — but **not** inside example/default payload
    data (:data:`_DATA_KEYS`), where the same key is a field of the payload and is reproduced
    byte-for-byte. A description consisting *only* of a section header loses the key entirely
    rather than becoming an empty string, which would emit a bare ``@description`` in the
    generated TypeScript.

    Args:
        schema: The schema produced by ``FastAPI.openapi()``; modified in place.

    Returns:
        The same schema, with every description reduced to its summary.
    """
    _truncate_descriptions(schema)
    return schema


def _truncate_descriptions(node: Any, *, in_properties: bool = False) -> None:
    """Walk *node* and truncate every documentation ``description`` string it contains.

    Subtrees under the :data:`_DATA_KEYS` (``example``, ``default``, …) are left byte-identical:
    a ``description`` key there is payload data, not documentation. A ``properties`` map needs the
    inverse care — its keys are property *names*, so a property that happens to be called
    ``example`` or ``default`` is still a schema whose own description must be truncated.

    Args:
        node: Any part of a decoded JSON document; non-container values are ignored.
        in_properties: Whether *node* is a ``properties`` map, whose keys are property names.
    """
    if isinstance(node, dict):
        description = node.get("description")
        if isinstance(description, str) and not in_properties:
            summary = _summary_before_sections(description)
            if summary:
                node["description"] = summary
            else:
                del node["description"]
        for key, value in list(node.items()):
            if key in _DATA_KEYS and not in_properties:
                continue
            _truncate_descriptions(value, in_properties=key == "properties" and not in_properties)
    elif isinstance(node, list):
        for item in node:
            _truncate_descriptions(item)


class _CompanionFastAPI(FastAPI):
    """A ``FastAPI`` whose schema carries neither the auto-422 nor Python's docstring internals.

    Validation failures answer ``400 invalid_request`` (AC 5), so FastAPI's per-route auto-422
    would document a shape the API never emits — straight into c2-3's generated TypeScript. The
    explicit 422 declaration that used to displace it went away with the 413 ruling, so the
    displacement now lives here, on the schema-build path itself, covering every future validated
    route (c3-1 onward) with no per-route ceremony.

    The second normaliser is c2-3's (Q1, Brad 2026-07-27): a description stops at the first
    Google-style section header, so ``Args:``, ``Attributes:`` and doctests stay on the Python side
    of the wire. Both run on this one path, so there is still exactly one schema — ``/docs``,
    ``/openapi.json`` and the committed ``ui/src/api/openapi.json`` cannot disagree.
    """

    def openapi(self) -> dict[str, Any]:
        """Build (and cache) the schema, normalised for the generated TypeScript.

        Returns:
            The OpenAPI schema with FastAPI's auto-generated validation response removed and every
            description reduced to its summary.
        """
        if self.openapi_schema is None:
            self.openapi_schema = without_python_docstring_sections(
                without_auto_validation_schema(super().openapi())
            )
        return self.openapi_schema


def build_app() -> FastAPI:
    """Construct the companion ASGI application without touching anything outside the process.

    The per-include ``responses`` are what put the typed error body into ``app.openapi()`` (AD-12,
    NFR-03): a Pydantic model no route references never reaches ``components.schemas``, so c2-3's
    generator would have nothing to emit and the UI's state panels nothing to switch on. They are
    declared **per include rather than app-wide** (c3-4 review, Brad 2026-08-01): the active-deck
    routes are the first with no database dependency and no request-body ceiling, and an app-wide
    declaration would tell every ``types.d.ts`` consumer they can answer ``503`` and ``413`` when
    they structurally cannot — the declaration is about what the *operation* can answer. The
    database-backed routers carry a fifth token as of c3-9 — ``database_not_initialized``, which
    they have answered since c1-6 and never declared; ``/health`` keeps the historical four
    unchanged, because narrowing a c1-2 route's committed schema is not this story's call and
    widening one it structurally cannot answer would be worse. The
    :class:`_CompanionFastAPI` schema hook keeps FastAPI's auto-generated ``HTTPValidationError``
    — a shape the ``invalid_request`` handler makes permanently unreachable — out of it.

    Returns:
        A configured ``FastAPI`` instance whose startup work has **not** yet run. Enter its
        lifespan (serving it, or ``async with lifespan(app)`` in tests) before expecting
        ``app.state`` to hold anything.
    """
    app = _CompanionFastAPI(title=_TITLE, lifespan=lifespan)
    # `/health` keeps the historical four EXACTLY as c1-2 declared them. It takes no session, so
    # it can answer neither 503 token; narrowing a c1-2 route's committed schema is not this
    # story's call, and WIDENING it would be worse — an inherited over-declaration is a wart, a
    # freshly-added one is a lie.
    #
    # AND `payload_too_large` IS GONE FROM BOTH SHARED SETS AS OF c5-5 (Q4, Brad 2026-08-08),
    # which is the ledgered wart `deferred-work.md` homed on this story by name closing exactly as
    # its own fix-shape described. Until c5-5 the token had no producer anywhere, so every
    # operation declaring it — six body-less GETs — promised a `types.d.ts` consumer a branch that
    # could never arrive, and each new GET route doubled the wart. c5-5 makes 413 real, and the
    # curation is what keeps "makes it real" from meaning "makes six lies true-shaped": the two
    # operations that can actually answer it declare it AT THE ROUTE, and nothing else declares it
    # at all. c5-2 and c3-4 both declined to EXTEND the wart, which made per-include narrowing a
    # two-instance pattern before this story; this is the story that unwinds it.
    health_responses = error_responses("invalid_request", "database_unavailable", "internal_error")
    # …and the database-backed routers declare the token they have been answering since c1-6
    # (c3-9, Q4). `database_not_initialized` was undocumented on three routes and rising —
    # `TestDatabaseStates` asserts it by name in three test modules while the committed schema
    # said only `database_unavailable` — and on a fresh install it is the MOST COMMON 503 the UI
    # will ever see, the one whole state c3-9 exists to render. It is a property of
    # `deps.get_session`, not of any route, so every data route inherits it by construction and
    # the gap could only ever widen.
    #
    # This is also the first call that exercises `error_responses`' documented collapse: both
    # tokens share status 503, so they land in ONE entry whose description names each of them
    # ("reason: database_not_initialized | database_unavailable"). That behaviour has been
    # advertised in the helper's docstring since c1-4 and had never fired.
    database_responses = error_responses(
        "invalid_request",
        "database_not_initialized",
        "database_unavailable",
        "internal_error",
    )
    app.include_router(health.router, responses=health_responses)
    app.include_router(decks.router, responses=database_responses)
    app.include_router(cards.router, responses=database_responses)
    # No 503 (no database dependency). The 413 half of this comment used to read "nothing enforces
    # a body ceiling until c5-5's cap"; c5-5 built the cap, so the PUT can now genuinely answer
    # 413 — but it is declared AT THE ROUTE beside its existing `forbidden`, not here, because the
    # sibling `GET /api/active-deck` carries no body and still cannot answer it. Per-operation is
    # the whole point of the curation above.
    app.include_router(
        active_deck.router, responses=error_responses("invalid_request", "internal_error")
    )
    # Exactly the same pair, for exactly the same two reasons, and c5-2 confirmed both rather than
    # inheriting them: no database dependency means no 503 to promise, and a body-less GET means no
    # 413. The second one is the wart `deferred-work.md` homes on c5-5 — every new GET route
    # doubles an unreachable 413 wherever one is declared — and declaring it here would have been
    # the first time this feature added to it deliberately. `/api/session` also adds NO new
    # `ErrorReason` token: the set stays closed at ten, because AD-16's rule is that a token exists
    # to drive a UI state and ticket churn is designed to be invisible.
    app.include_router(
        session.router, responses=error_responses("invalid_request", "internal_error")
    )
    # No `responses=` at all, and that is not an omission: `responses` describes an OPERATION in
    # `app.openapi()`, and a WebSocket route has no operation there — OpenAPI does not model
    # WebSockets, so c5-3 adds zero paths and zero components (proven, not assumed, by
    # `test_committed_schema.py`'s untouched 8/13 pins and a byte-identical `gen:api`). A closed
    # handshake carries no JSON body either, so there is no typed error to declare: the whole
    # vocabulary on that wire is a close code. It still MUST be registered above `install_spa`,
    # for the reason the block below states and one more that is specific to it — see
    # `test_spa.py::test_the_mount_declines_non_http_scopes`.
    app.include_router(ws_router)
    # c5-5's ingest, and the first router on a NOVEL first path segment since c3-1's /api. Four
    # tokens and deliberately no 503: the route takes no session, so it must NOT join
    # `TestTheDatabaseTokensAreDeclared.DATABASE_BACKED`. `payload_too_large` is declared here
    # rather than inherited, because after the curation above this operation is one of exactly two
    # in the app that can answer it — the other being `PUT /api/active-deck`, which declares its
    # own at the route for the same reason.
    #
    # `/agent` is protected from the SPA catch-all by THIS LINE'S POSITION and nothing else: the
    # `_RESERVED_SEED` belt-and-braces covers `/api` only (see the block below install_spa).
    app.include_router(
        agent_events.router,
        responses=error_responses(
            "invalid_request", "forbidden", "payload_too_large", "internal_error"
        ),
    )
    # Ordering, and it is the whole point: user_middleware[0] is the most recently added
    # middleware, so the error middleware must be installed *last* to end up outermost — where it
    # can type the failures of every middleware added before it. The Host check goes above this
    # line so that a fault in the security envelope itself answers as a typed 500 rather than an
    # untyped traceback (on http scopes — the error middleware passes websocket scopes through,
    # which c5-3's Q6 ruled PERMANENT: the upgrade handler catches its own faults and closes 1011,
    # so the middleware keeps one shape). c5-5's pre-parse body ceiling is installed here too, as
    # its own call — see the third correction below.
    #
    # CORRECTED AT c5-2, which falsified the previous version of that clause ("c5-2 and c5-5 add
    # their pieces inside install_security, not here"). c5-2 adds neither a middleware nor a
    # security line: its mint is an ORDINARY ENDPOINT, so it adds an include_router above, and its
    # store is created by the lifespan.
    #
    # AND CORRECTED AGAIN AT c5-3, which falsified c5-2's replacement for it. That version said
    # "c5-3 — the handshake gate — is the story that sentence was really describing", predicting a
    # security line here. IT IS NOT. The upgrade is an ordinary FastAPI route on an APIRouter, so
    # c5-3 added an include_router above this block exactly as c5-2 did, and install_security is
    # STILL the one security wiring call — now two stories past the one that was supposed to grow
    # it. What made the prediction wrong is worth keeping: "gates a handshake" describes what the
    # check DOES, and middleware-versus-route is about WHERE the check can be expressed. A
    # websocket route can read its own headers and close its own connection, so it needs no
    # middleware position to do the gating from. c5-5 was the only story still holding that
    # prediction going into this commit.
    #
    # AND CORRECTED A THIRD TIME AT c5-5, which falsifies its own replacement for it ("c5-5 adds
    # its piece inside install_security, not here"). HALF right: it genuinely is a middleware, but
    # genuinely NOT a security wiring line — `install_security` stays the one security call, and
    # the body ceiling is its own call, `install_body_cap`, because the cap is about resource
    # bounds rather than about who the caller is. Added FIRST so it ends up innermost of the three
    # — `Host` refuses a wrongly-addressed request before its body is read, and a fault in the
    # counting is still typed by the error middleware. Same commit as the code that falsifies it
    # (c3-9's rule); a `#` comment in a non-wire position, so no regeneration diff.
    install_body_cap(app)
    install_security(app)
    install_error_handling(app)
    # MUST STAY LAST. install_spa mounts the SPA bundle at "/", and Starlette matches routes in
    # list order, so a mount at "/" matches every path and shadows everything registered after it
    # — silently: a route would answer 200 with index.html instead of running the endpoint.
    # c3-1's decks router, c3-2's cards router, c3-4's active-deck router and c5-2's session router
    # are registered above this line; c5-5 adds its /agent router there too. (c3-3 added a route
    # and edited nothing here,
    # by design: its format-check endpoint is a deck sub-resource that joined the decks router,
    # which is already above this line. A story adding a route to an EXISTING router inherits the
    # ordering; only a story adding a router has to touch this block. c3-5 is the second instance
    # of that: its /api/card-image/{scryfall_id} joined the cards router — same identifier, same
    # corpus, same repository call — so this block and test_spa.py's differential list were both
    # verified unchanged rather than edited. Note what it therefore also inherits: the `shared`
    # includes' 413, which no body-less GET can answer. That wart is ledgered and homed on c3-9.)
    #
    # c3-4 is the second instance of the OTHER kind, and it paid the full tax deliberately: a new
    # router here AND the differential list in test_spa.py::test_the_schema_is_unchanged_by_
    # installing_the_mount. It could have joined decks.router for free, but every route there takes
    # a DbSession and that module's docstring is written about deck reads — an authenticated
    # in-memory write with no database at all would have made it false (Q1, Brad 2026-08-01).
    #
    # Note that /api specifically is ALSO protected by spa.py's _RESERVED_SEED, so c3-1's two
    # routes survive being registered late (measured: they still answer). That belt-and-braces
    # does NOT generalise — a router on a NOVEL prefix (c5-5's /agent) has only this ordering
    # between it and the catch-all, which is why the rule is stated for every router rather than
    # for the ones that happen to be covered twice.
    #
    # The mount also reads the route table to decide which prefixes never fall back to the index,
    # so it needs that table complete regardless.
    # test_spa.py::TestMountOrdering fails with these instructions if the line ever moves.
    install_spa(app)
    return app

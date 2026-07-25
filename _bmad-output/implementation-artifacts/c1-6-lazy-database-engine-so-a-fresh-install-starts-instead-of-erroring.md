---
baseline_commit: 13a8a10
epic: c1
story: c1-6
work_branch: feat/companion-app
story_branch: feat/companion-c1-6-lazy-database-engine
---

# Story C1.6: Lazy database engine so a fresh install starts instead of erroring

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad on a brand-new machine,
I want the companion to start before the card database exists,
so that a fresh install is a guided next step rather than a crash on first run.

**Why this story is sixth.** Everything before it was about the process: c1-2 made construction
inert, c1-3 got it a port, c1-4 gave failures a vocabulary, c1-5 decided who may address it. This is
the first story that gives the backend a *data* surface — and the first that can undo AD-10, because
the obvious implementation (build the engine in `build_app()` or in the lifespan) turns a fresh
install into a startup crash and makes every future test need a database on disk. Three of c1-4's
six reason tokens exist only for this story: `database_not_initialized`, `database_unavailable` and
— by elimination — the `internal_error` that a *deterministic* database fault must not be confused
with. c3-1 (`GET /api/decks`) says in its own AC that it "uses the shared lazy engine from Story
1.6", so the seam built here is consumed unchanged by c3-1, c3-2 and c3-3, and never re-derived.

## Acceptance Criteria

1. **One module owns the engine: `src/companion/app/deps.py`.** The spine's Structural Seed names
   it (`deps.py # lazy engine + session dependency (AD-2, AD-10)`). It exports exactly:

   - `Database` — the per-app holder: `engine` (read-only property, `None` until first use),
     `session_factory()` (async; creates the engine on first call, then returns the cached
     factory), `dispose()` (async; releases the engine if one was ever created, and is safe to call
     when none was);
   - `database(app: FastAPI) -> Database | None` — the accessor, mirroring `main.bound_port`, so
     `app.state.database` has exactly one reader;
   - `database_file(url: str) -> Path | None` — the pure URL→path function, so AC 3's matrix is
     testable without an engine;
   - `get_session(request: Request) -> AsyncIterator[AsyncSession]` — the FastAPI dependency;
   - `DbSession = Annotated[AsyncSession, Depends(get_session)]` — the one annotation c3-1/c3-2/c3-3
     write on their handlers.

2. **Nothing is created until a data-backed request arrives (AD-10).** `build_app()` still creates
   no engine, no holder and no path (`test_app.py::TestConstructionIsInert` stays green
   **unedited**). The **lifespan** creates the holder — an inert in-process object, no I/O — and
   `database(app).engine is None` after startup. The engine appears on the **first** `get_session`
   call and is reused: a second request returns the *same* `AsyncEngine` object, pinned by identity
   (`is`), not by a call count alone.

3. **A missing database file answers `503 database_not_initialized` and plants nothing on disk.**
   The file-existence check runs **before** the engine is created, because
   `create_async_engine(...)` touches no disk but the **first connection creates a zero-byte file**
   (verified here — see Latest technical information). Planting an empty `cards.db` in the user's
   data directory would be the read-only read model writing to disk on a fresh install, and would
   leave a file the next reader has to reason about. The test asserts **observable filesystem
   state** — the file still does not exist after the 503 — in the style of c1-2's inertness tests,
   and that `database(app).engine is None` afterwards. `database_file` decides what "the file" is:

   | URL | `database_file` | Why |
   | --- | --- | --- |
   | `sqlite+aiosqlite:///C:/…/cards.db` | that `Path` | the normal case |
   | `sqlite+aiosqlite:///./data/cards.db` | that relative `Path` | an explicit `CARDS_DATABASE_URL` |
   | `sqlite+aiosqlite:///:memory:` | `None` | no file to check |
   | `sqlite+aiosqlite://` (`.database is None`) | `None` | in-memory, no file to check |
   | any non-sqlite backend (e.g. `postgresql+asyncpg://…`) | `None` | `.database` is a database *name*, not a path — the existence check must not fire on it |

   `None` means **skip the check and create the engine**; it never means "not initialized".

4. **"Not initialized" is the project's existing definition, not a second one.** After a session is
   opened, readiness is `src.data.database.is_database_initialized(session)` — the same function
   every MCP tool uses, so "file exists but the `cards` table does not", "table exists but is
   empty" and "an import was killed mid-way" (`src.data.import_state`) all answer
   `503 database_not_initialized` exactly as they answer `database_not_initialized` on the MCP
   side. Defining a second readiness rule here would let the two shells disagree about the same
   file (AD-1). The verdict is **re-probed on every request and never cached** — that is what makes
   AC 8 work without a restart; the cost (≤ 4 tiny SELECTs against local SQLite) is accepted and
   noted for c10-3, which owns latency hardening.

5. **`GET /health` still returns `200` while data endpoints answer `503`.** The process is healthy;
   only its data is missing. Pinned in **one** test that drives both endpoints against the same app
   in the same lifespan, so it cannot pass by the health route having been broken into a different
   shape.

6. **One engine, one session-factory recipe, shared with the MCP side (AD-2).** The engine comes
   from `src.data.database.create_engine(url)` and the factory from
   `create_session_factory(engine)` — **not** a local `create_async_engine` call, so the busy-timeout
   (`connect_args={"timeout": 5}`) and `expire_on_commit=False` recipe cannot drift from
   `src/mcp_server/server.py:115`. The URL is resolved **once** per engine creation via
   `src.paths.database_url()`, the path is derived from that same string with
   `sqlalchemy.engine.make_url`, and that same string is passed to `create_engine` — one resolution,
   so the existence check and the engine can never disagree about which file they mean.
   **No `mode=ro`, no `immutable`, no `?uri=true`**: PRD NFR-02 names `mode=ro` and AD-2
   deliberately overrides it (the WAL `-shm` Windows landmine, and `immutable` would foreclose
   FR-16). Read-only is enforced by `test_import_boundary.py`, and the PRD amendment is c8-3's.

7. **Concurrent first requests create exactly one engine.** Creation sits behind an
   `asyncio.Lock` held by the `Database` instance, with the double-check *inside* the lock. Test:
   `asyncio.gather` of N (≥ 5) concurrent first requests against a ready database, with
   `create_engine` wrapped by a counting spy — exactly **one** call, one engine object, N successful
   responses. Without the lock the failure is silent (an orphaned second engine holding a second
   connection pool), so the count is the assertion, not the response codes.

8. **A database that appears while the backend is running is picked up with no restart.** Both
   paths are pinned, because they fail differently:
   - **no engine yet** — file absent → `503`; the file is then created and populated → the next
     request succeeds and the engine is created then;
   - **engine already cached against a not-yet-ready file** — an empty-but-present `cards.db` is
     probed (`503 database_not_initialized`, engine now cached), the schema and a row are then
     written by another connection → the next request through the **same cached engine** succeeds
     (verified — SQLite re-reads the schema per statement).

9. **A transient database failure is `503 database_unavailable`, mapped in exactly one place.**
   `install_error_handling` registers a handler for **`sqlalchemy.exc.DatabaseError`** returning
   `error_response("database_unavailable")`, so every data-backed route — the ones c3-1 onward will
   add as much as the dependency's own readiness probe — inherits it with no per-route ceremony
   (the epic-7 *error-contract enumeration* item, applied before the routes exist rather than after).
   The net is `DatabaseError`, **not** the wider `SQLAlchemyError`, and that is the ruling:
   `OperationalError` ("database is locked", "unable to open database file", "disk I/O error") is a
   `DatabaseError` and is transient; an `ArgumentError` or `InvalidRequestError` is a deterministic
   bug and must fall through to `UnhandledErrorMiddleware`'s `500 internal_error`, which is the
   distinction AD-16 added `internal_error` for. Matches the MCP side, which catches `DatabaseError`
   in every tool. Both raise sites are tested end-to-end: one from inside the dependency, one from
   inside a route body (verified reachable — both are inside `ExceptionMiddleware`).
   The rejection is logged **once** at `WARNING` with `%`-style lazy args, naming the method, the
   path, the exception class and `exc.orig` (the DBAPI error) — **never** `str(exc)`, which carries
   the statement and its bound parameters.

10. **Shutdown disposes the engine, and tolerates never having had one.** `main._shutdown` awaits
    `database(app).dispose()` (guarded on the accessor's `None`), so the pool is released on a clean
    exit. Two tests: dispose is reached after an engine was created, and shutdown is clean on an app
    that never took a data request. `_shutdown`'s existing docstring already names this story as its
    first real client — update it to say what it now releases.

11. **The startup/teardown asymmetry is preserved.**
    `test_app.py::test_startup_failure_propagates` exists to catch exactly this story widening the
    lifespan's `try` to cover startup; it must stay green **unedited**. Creating the holder is
    the only new startup work and it cannot fail, so nothing needs to move.

12. **No production route ships (Decide-once #1).** `src/` gains no endpoint: c3-1 is the first real
    consumer and its AC already says so. The dependency is driven through a **test-local** route
    mounted on a real `build_app()` before its lifespan is entered — the same technique c1-4 and
    c1-5 used to exercise otherwise-unreachable paths, and the reason the guard is not a dead one.
    A helper in the new test module builds `app = build_app()` + `@app.get("/_test/data")` returning
    something derived from the session (e.g. a `SELECT 1` scalar, or `is_database_initialized`'s own
    read), so the route genuinely uses what it was handed.

13. **The import boundaries stay green, unedited.** `deps.py` sits under `src/companion/app/`, so
    the leaf/app guard classifies it automatically; the write guard must find nothing — no
    `init_database`, no `create_all`, no `session.add/commit/flush/delete/merge`, no
    `sqlalchemy.insert/update/delete`, no `src.data.importers`. `tests/unit/companion/
    test_import_boundary.py` is **not** edited.

14. **Tests: `tests/unit/companion/test_deps.py`**, unmarked unit tests, no network and no server
    boot, driving a real `build_app()` through the `lifespan_client` seam. Databases are real SQLite
    files under `tmp_path`, addressed by monkeypatching **`CARDS_DATABASE_URL`** (the precedent in
    `tests/integration/mcp_server/test_first_run_data_init.py`), plus **at least one** test that
    instead sets `PLANESWALKER_DATA_DIR` and `monkeypatch.delenv("CARDS_DATABASE_URL",
    raising=False)` to prove the default resolution path — see Gotcha 4, a developer's own shell
    variable would otherwise silently win. Cover: AC 3's `database_file` matrix and the
    no-file-planted assertion; AC 2's laziness and reuse; AC 4's three not-ready shapes (no table,
    empty table, import-in-progress); AC 5's health-stays-200; AC 7's concurrency count; AC 8's two
    appearance paths; AC 9's two raise sites, its single `WARNING` record from
    `src.companion.app.errors` (asserted on the record, including that the message does **not**
    carry the statement's bound parameters), and the "`ArgumentError` is `internal_error`, not
    `database_unavailable`" negative; AC 10's two shutdown cases; and the unreachable
    no-holder branch of AC 1 (a `build_app()` served **without** its lifespan → `500
    internal_error`), driven directly rather than left as a dead guard.
    **Non-vacuity:** every 503 assertion is paired with a request against a *ready* database that
    returns `200` from the same route, so the suite cannot pass by refusing everything.

15. **Quality gates green (NFR-07).** `uv run ruff check .`, `uv run ruff format --check .`,
    `uv run mypy src/`, `uv run mypy src/ --platform linux` (what CI runs) and
    `uv run pytest -m "not integration"` all pass with **no new failures** against the
    **1,495 passed / 45 deselected** baseline (verified at `13a8a10` on 2026-07-25). Actual output
    pasted into the Debug Log.

16. **Plugin mirror rebuilt and committed.** `uv run python -m scripts.build_plugin`, then commit
    `plugin/`; `git status --porcelain -- plugin/` clean afterwards.

17. **Scope boundary — what this story must NOT do.** No REST route in `src/` (c3-1/c3-2/c3-3/c3-5).
    No repository call, no deck or card schema, no `deck_not_found` (c3-1 owns the token's first
    raise). No discovery file (c1-7), no single-instance check (c1-8), no CLI or root-logger
    configuration (c1-9). No WebSocket, ticket or agent token (c5-2/c5-3/c5-5). No new reason token
    — all three this story uses already exist. No new dependency and no `pyproject.toml` /
    `uv.lock` / `.pre-commit-config.yaml` change (SQLAlchemy, aiosqlite and `src.paths` are all
    already dependencies of the app side). No edit to `tests/unit/companion/test_app.py`,
    `test_security.py`, `test_server.py`, `test_import_boundary.py` or `.github/workflows/ci.yml`.
    No change to `src/data/**` or `src/mcp_server/**` — if the shared recipe needs a change, that is
    a finding, not an edit.
    Checked rather than assumed: `test_errors.py` needs no edit even though `errors.py` grows a
    fourth handler, because what it pins is the token↔status table (`STATUS_BY_REASON` vs the six
    `_REASONS`) and `user_middleware[0]` — neither of which this story touches. It registers no
    assertion over the set of exception handlers. If `test_errors.py` goes red, the change went
    further than AC 9 allows.

## Tasks / Subtasks

- [x] **Task 0 — State verification** (standing team agreement since the epic-6 retro: any story
      whose notes assert repository state opens with the cheap check that proves it)
  - [x] Create `feat/companion-c1-6-lazy-database-engine` **off `feat/companion-app`** (currently at
        `13a8a10`); the story PR targets `feat/companion-app`.
  - [x] Confirm `src/companion/app/deps.py` and `tests/unit/companion/test_deps.py` do **not** exist,
        and that `build_app()` ends with `install_security(app)` then `install_error_handling(app)`.
  - [x] Baseline the suite: `uv run pytest -m "not integration" -q` → expected **1,495 passed, 45
        deselected**. Record any delta rather than chasing it.
  - [x] Re-confirm the two findings this story is built on, in five lines each (they are the reason
        AC 3 and AC 9 are shaped as they are): a first connection to a missing SQLite file
        **creates a zero-byte file**, and `sqlalchemy.exc.OperationalError` is a subclass of
        `DatabaseError`.

- [x] **Task 1 — The pure URL→path function, test-first** (AC: 1, 3)
  - [x] Write AC 3's matrix as a parametrized test against `database_file` first; watch it fail on
        the missing module (red-phase evidence for the Debug Log).
  - [x] `src/companion/app/deps.py` — module docstring covering: why the engine is lazy (AD-10 /
        FR-22 — a fresh install is a served state, not a crash), why the file check precedes engine
        creation (the zero-byte-file finding), why the recipe is shared with the MCP side (AD-2),
        and why `mode=ro` is **not** used. Module-level `logger = logging.getLogger(__name__)`.
  - [x] `database_file(url)` with a Google docstring: `make_url(url)`, `None` unless the backend is
        sqlite and `.database` is a real path (`None` / `":memory:"` both yield `None`).

- [x] **Task 2 — The holder** (AC: 1, 2, 3, 6, 7, 10)
  - [x] `Database` — `_engine`, `_session_factory`, `_lock: asyncio.Lock`; `engine` as a read-only
        property; `session_factory()` async with the double-check **inside** the lock;
        `dispose()` async, no-op when `_engine is None`, and resetting the cached factory so the
        holder is honest after disposal.
  - [x] Creation path, in order: resolve the URL once (`src.paths.database_url()`) →
        `database_file(url)` → if it is a `Path` that does not exist, log once at `INFO` and raise
        `CompanionError("database_not_initialized")` → else `create_engine(url)` +
        `create_session_factory(engine)` → cache both. Log the engine creation once at `INFO` with
        `%`-style args (this is the one line an operator uses to confirm the database was found).
  - [x] `database(app)` accessor with the same shape and docstring discipline as
        `main.bound_port` — annotated local, returns `Database | None`, and its docstring says
        `None` means *the lifespan never ran*.

- [x] **Task 3 — The dependency** (AC: 1, 4, 5, 12)
  - [x] `get_session(request)` — async generator: read the holder through the accessor (a `None`
        logs and raises `CompanionError("internal_error")`, the unreachable-on-supported-paths
        branch of AC 14); `factory = await db.session_factory()`; `async with factory() as session`;
        `if not await is_database_initialized(session): raise
        CompanionError("database_not_initialized")`; `yield session`.
  - [x] `DbSession = Annotated[AsyncSession, Depends(get_session)]`, with a docstring naming
        c3-1/c3-2/c3-3 as the callers so the next story annotates rather than re-derives.
  - [x] Nothing in the teardown path may raise — see Gotcha 6.

- [x] **Task 4 — Wire the lifespan** (AC: 2, 10, 11)
  - [x] `src/companion/app/main.py` — the lifespan creates `app.state.database = Database()` beside
        the `instance_id` mint (both are inert; neither can fail), and `_shutdown` awaits
        `dispose()` through the accessor. Update `_shutdown`'s docstring: it now releases something.
  - [x] Change nothing else in `main.py` — `build_app`, `bound_port`, `_CompanionFastAPI`, the
        middleware ordering and the app-level `responses=` are untouched.
  - [x] Re-run `tests/unit/companion/test_app.py` **unedited** — especially
        `TestConstructionIsInert` and `test_startup_failure_propagates`.

- [x] **Task 5 — The transient-failure handler** (AC: 9)
  - [x] `src/companion/app/errors.py` — `database_error_handler`, registered inside
        `install_error_handling` alongside the existing three. Docstring: why `DatabaseError` and
        not `SQLAlchemyError`, and why the parameters are never logged.
  - [x] Extend the module docstring's rule list (or `install_error_handling`'s) so the enumeration
        "which exception becomes which token" stays readable in one place.

- [x] **Task 6 — Tests** (AC: 3, 4, 5, 7, 8, 9, 10, 12, 14)
  - [x] `tests/unit/companion/test_deps.py` per AC 14, with the test-local-route helper and the
        non-vacuity pairing called out in comments.
  - [x] Add fixtures for the three not-ready database shapes (absent / empty file / schema with no
        rows / `import_state.in_progress = 1`) built with plain `sqlite3`, not the async engine —
        a test that builds its fixture through the code under test proves nothing.
  - [x] Confirm no pre-existing companion test needed an edit; if one did, stop and say why.

- [x] **Task 7 — Gates, mirror, deferred-work and scope** (AC: 13, 15, 16, 17)
  - [x] `uv run ruff check . --fix` · `uv run ruff format .` · `uv run mypy src/` ·
        `uv run mypy src/ --platform linux` · `uv run pytest -m "not integration"` — paste actual
        counts into the Debug Log.
  - [x] `_bmad-output/implementation-artifacts/deferred-work.md`: record how this story now surfaces
        the long-standing **bare-path `CARDS_DATABASE_URL`** item (line 268) — a URL with no
        `sqlite+aiosqlite:///` prefix makes `create_engine` raise `ArgumentError`, which under AC 9
        answers `500 internal_error` rather than crashing the process. Not fixed here; homed, per the
        epic-7 gate-output rule.
  - [x] `uv run python -m scripts.build_plugin`, `git add plugin/`, verify
        `git status --porcelain -- plugin/` is clean after the commit.
  - [x] Confirm by command that the AC 17 forbidden files are untouched:
        `git status --porcelain -- tests/unit/companion/test_app.py tests/unit/companion/test_security.py tests/unit/companion/test_server.py tests/unit/companion/test_import_boundary.py .github/workflows/ci.yml pyproject.toml uv.lock .pre-commit-config.yaml src/data src/mcp_server`
        returns empty.

## Dev Notes

### Decide-once rulings (made here so four later stories inherit them)

**#1 — This story ships the seam, not an endpoint.** The epic's ACs are written against "any
data-backed endpoint", and none exists yet: c3-1 owns `GET /api/decks` and its AC says it "uses the
shared lazy engine from Story 1.6". Shipping a placeholder data route here would either duplicate
c3-1's endpoint or leave a route in `src/` that no UX state consumes — and AD-16's token-to-state
mapping is 1:1, so a route with no state is a contract violation waiting to happen. The dependency
is therefore exercised through a **test-local route on a real `build_app()`**, exactly as c1-4 and
c1-5 drove their own unreachable paths. The dead-guard standard is met by exercising every branch,
not by shipping a consumer.

**#2 — The file-existence check precedes engine creation, and it is not paranoia.**
`create_async_engine(...)` opens nothing, but the **first connection creates a zero-byte database
file** (verified: `1a engine created; file exists? False` → `1b after connect+select; file exists?
True size 0`). Without the check, the *read-only* read model would write a file into the user's data
directory on every fresh-install request, and the artefact would outlive the request. The check is
also what keeps the missing-directory case honest: a URL under a directory that does not exist
raises `OperationalError: unable to open database file` — a `DatabaseError`, which AC 9 would
otherwise report as the transient `database_unavailable` when the truth is "there is no database".

**#3 — Readiness is `src.data.database.is_database_initialized`, re-probed every request.** Two
alternatives were available and both are worse. *A second definition* (e.g. "the file exists,
therefore ready") lets the two shells disagree about the same file: the MCP side would answer
`database_not_initialized` for an empty or half-imported database while the companion served a
`200` with zero decks, and AD-1 exists to prevent exactly that second truth. *Caching the verdict*
(probe once, remember `True`) saves ~4 SELECTs against a local SQLite file and breaks AC 8, whose
whole point is that the app comes alive on its own while a page is open. The cost is real but tiny
and it is stated rather than discovered; c10-3 owns latency hardening and may revisit with a
measurement in hand.

**#4 — `DatabaseError`, not `SQLAlchemyError`, is the transient net.** `sqlalchemy.exc` splits
cleanly along the line AD-16 cares about: `DatabaseError` (and its `OperationalError` /
`IntegrityError` / `DataError` children) is the database telling us something went wrong *now* —
locked, unreadable, malformed — which is the "Database updating" retry state. `ArgumentError`,
`InvalidRequestError` and `CompileError` are us telling ourselves we wrote bad code; they are
deterministic, retrying them is pointless, and AD-16 added `internal_error` precisely so the UI can
stop retrying. This also matches the MCP side, which catches `DatabaseError` in every tool
(`deck_management.py`, `deck_analysis.py`, `view_deck.py`, `assess_deck_power.py`), so a reader
moving between the two shells meets one rule.

**#5 — The handler is registered in `errors.py`, not in `deps.py`.** `install_error_handling` is
already the single answer to "which exception becomes which token", and it is already called last
in `build_app()`; adding the fourth registration there keeps the enumeration greppable in one file
and keeps `build_app()` at two install lines. The cost — `errors.py` now imports
`sqlalchemy.exc` — is acceptable: `errors.py` is app-side, not leaf, and it already imports
FastAPI and Starlette. `deps.py` keeps the engine; `errors.py` keeps the mapping; each docstring
names the other.

### Architecture rules this story implements

- **AD-10** — the sentence this story exists for: *"the database engine is created lazily and its
  absence is a served UI state, not a startup failure — this is what makes FR-22 hold."*
  Construction stays inert; the lifespan owns the holder; the engine is first touched by a request.
- **AD-2** — one engine, one session-factory recipe, shared with the MCP side, and read-only
  enforced by the CI import boundary rather than `mode=ro`. This story is the first real test of
  that: it is the first companion module that could plausibly reach a write path, and it must not.
- **AD-16** — three tokens, each mapped 1:1 onto a UX state c2-9 will build:
  `database_not_initialized` (503) → the fresh-install panel, `database_unavailable` (503) → "Database
  updating", `internal_error` (500) → the unhandled-bug panel. No new token is added.
- **AD-1** — the companion consumes the existing core. `is_database_initialized`, `create_engine`
  and `create_session_factory` are used as they are; nothing is copied into `src/companion`.
- **FR-22** — the backend half. c3-9 closes the loop in the UI ("comes alive on its own"); AC 8 here
  is what makes that possible without a restart.

### Source tree — what exists, what this story adds

```text
src/
  companion/
    app/
      deps.py                  # NEW — Database, database(), database_file(), get_session, DbSession
      main.py                  # UPDATE — lifespan creates the holder; _shutdown disposes it
      errors.py                # UPDATE — database_error_handler + its registration
      security.py              # EXISTS — untouched
      server.py                # EXISTS — untouched
      routes/health.py         # EXISTS — untouched (AC 5 proves it stays 200)
    contracts.py               # EXISTS — untouched (all three tokens already exist)
tests/
  unit/companion/
    test_deps.py               # NEW
    conftest.py                # EXISTS — untouched; the c1-5 seam already does what this needs
    test_app.py                # EXISTS — NOT edited (AC 17)
    test_errors.py             # EXISTS — NOT edited (AC 17)
    test_security.py           # EXISTS — NOT edited (AC 17)
    test_import_boundary.py    # EXISTS — NOT edited (AC 17)
```

**Current state of the files being modified** (read before editing):

- `src/companion/app/main.py` — `_TITLE`; `_shutdown(app)` (today a single `logger.debug`, whose
  docstring already says *"the teardown that stories c1-6 (engine dispose) and c1-7 (discovery-file
  removal) hang their work on"*); `lifespan` (mints `instance_id`, then `try/yield/finally` with the
  teardown wrapped in its own swallow-and-log); `bound_port(app)`; `_CompanionFastAPI` (the
  `openapi()` hook that strips FastAPI's auto-422); `build_app()` = `_CompanionFastAPI(...)` +
  `include_router(health.router)` + `install_security(app)` + `install_error_handling(app)`.
  **What must be preserved:** no module-level side effect and **no module-level `src.paths` call**
  (the inertness test fresh-imports this module with `PLANESWALKER_DATA_DIR` pointed at a
  non-existent directory and asserts it is never created — a module-level `database_url()` anywhere
  on the import chain fails it); the swallow-wraps-teardown-only asymmetry; `bound_port`'s
  semantics; the middleware install order.
- `src/companion/app/errors.py` — `STATUS_BY_REASON` (six tokens), `CompanionError`,
  `error_response`, `error_responses`, `without_auto_validation_schema`, three handlers
  (`companion_error_handler`, `validation_error_handler`, `http_exception_handler`),
  `UnhandledErrorMiddleware`, `install_error_handling`. **What must be preserved:** the handler
  signature convention (`(request: Request, exc: Exception)` with an `isinstance` narrowing and a
  re-raise on mismatch — a narrower `exc` annotation is an `arg-type` failure under `mypy --strict`);
  `install_error_handling` staying the **last** call in `build_app()`; the body-carries-no-prose rule.
- `src/data/database.py` — `create_engine(url=None)`, `create_session_factory(engine)`,
  `get_session(session_factory)` (a *different* helper — see Gotcha 5), `init_database` (**banned
  here**), `is_database_initialized(session)`, `health_check` (writes — never call it).
  **Read, not modified.**
- `src/paths.py` — `data_dir()` (mkdirs), `database_path()`, `database_url()` (an explicit
  `CARDS_DATABASE_URL` wins, else `data_dir()/cards.db` as a posix URL). **Read, not modified.**
- `tests/unit/companion/conftest.py` — the `lifespan_client` seam with `base_url=` / `headers=` /
  `bound_port=`. **No change is needed:** it stamps a port and derives a matching loopback
  `base_url`, so requests pass the Host envelope automatically. If a c1-6 test finds itself wanting
  to change the seam, that is a signal to re-read it, not to edit it.

**Deviation from the spine's Structural Seed:** none. `deps.py` is on the seed's list by name with
exactly this responsibility.

### Gotchas specific to this story

1. **A first connection creates the file.** `create_async_engine` is inert; the first `connect()`
   materialises a zero-byte SQLite file (verified). This is the single fact AC 3 is built on — do
   not "simplify" by letting the readiness probe discover the absence.

2. **`src.paths.database_url()` mkdirs the data directory.** It calls `database_path()` →
   `data_dir()`, which ends in `mkdir(parents=True, exist_ok=True)` (verified: resolving the URL
   created a directory that did not exist). That is acceptable at *first-request* time and matches
   what the MCP side does anyway — but it is **not** acceptable at import or construction time, and
   `test_app.py::test_import_and_construction_create_no_directory` will catch it. Never call it at
   module level, in a default argument, or in `build_app()`.

3. **`asyncio.Lock()` must belong to the `Database` instance, not the module.** A module-level lock
   is shared across every app a test builds, which serialises unrelated tests and hides a real
   double-creation bug behind a global. Constructing it inside the lifespan means it is bound in the
   running loop, which is where it will be used.

4. **A developer's own `CARDS_DATABASE_URL` can hijack the tests.** `src.paths.database_url()` reads
   the process environment directly and an explicit `CARDS_DATABASE_URL` **wins over**
   `PLANESWALKER_DATA_DIR`. Any test that steers via `PLANESWALKER_DATA_DIR` must first
   `monkeypatch.delenv("CARDS_DATABASE_URL", raising=False)` — the precedent is
   `tests/unit/test_paths.py:79`. Otherwise the test would read a real database on one machine and
   a tmp one on another.

5. **`src.data.database.get_session` is not this story's `get_session`.** The data-layer helper takes
   a session factory; the dependency here takes a `Request`. Do not import the former into `deps.py`
   by reflex — the `async with factory() as session` form is what the dependency needs, and having
   two same-named symbols in one file is how the wrong one gets called.

6. **A dependency's teardown raising is unrecoverable.** After the response has been sent, an
   exception from the code *after* `yield` escapes every handler and every middleware — verified:
   `4a teardown raise escaped as RuntimeError`. So the teardown does nothing but let the
   `async with` close the session. Never add cleanup that can throw.

7. **`CompanionError` from a dependency *does* reach the handler** — unlike from middleware.
   Dependencies are solved inside the router, which is inside `ExceptionMiddleware` (verified:
   `/dep -> 503 {"reason":"database_not_initialized"}`). This is the opposite of c1-5's Decide-once
   #1, and the difference is position in the stack, not the exception. Do not copy c1-5's
   send-don't-raise pattern here.

8. **The write guard reads names, not intent.** `_SESSION_RECEIVERS` includes `database`, `db`,
   `conn`, `session` and `_SESSION_MUTATORS` includes `add`, `delete`, `merge`, `commit`, `flush`.
   The accessor in this story is literally called `database` and its result will usually be bound to
   `db` — so `db.merge(...)` or `database.add(...)` on *anything*, even a non-session object, turns
   `test_import_boundary.py` red. `dispose()`, `close()` and `session_factory()` are all fine.

9. **`init_database` and `create_all` are banned by name**, including in an import. The companion
   never creates the schema — that is `initialize_database`'s job on the MCP side, and it is what
   the fresh-install panel tells the user to ask their agent to run.

10. **`health_check` in `src/data/database.py` writes** (it inserts, selects and deletes a probe
    card). It is not a readiness check for this story and calling it would breach AD-2 —
    `is_database_initialized` is the read-only one.

11. **A cached engine survives the database being created underneath it** (verified: `5a before:
    False` → schema written by a separate `sqlite3` connection → `5b after (same cached engine):
    True`). So AC 8's second path needs no engine invalidation, and adding one would be extra
    machinery with no failing test behind it.

12. **`mypy --strict` details.** `Database.engine` returns `AsyncEngine | None`;
    `get_session` is `async def get_session(request: Request) -> AsyncIterator[AsyncSession]`
    (`collections.abc.AsyncIterator`, not `AsyncGenerator`, matching `main.lifespan`'s style);
    `database(app)` needs the annotated-local trick `bound_port` uses (`app.state` is `Any`, and
    `warn_return_any` flags returning it directly); `make_url(...).database` is `str | None`.

13. **`asyncio.gather` on `httpx.AsyncClient` shares one transport** — that is fine for AC 7 (in-process
    ASGI, no connection pool contention), but the counting spy must wrap
    `src.companion.app.deps`'s *reference* to `create_engine`, not `src.data.database.create_engine`,
    unless the module imports it lazily. Patch where it is looked up.

### Testing standards

- New tests live in `tests/unit/companion/test_deps.py` — unmarked, fast, no network, no server
  boot. `--strict-markers` is on: do not invent a marker.
- `asyncio_mode = "auto"` — write `async def test_…` directly; no `@pytest.mark.asyncio`.
- Reuse the `lifespan_client` fixture unchanged; build the app with a test-local route *before*
  entering the seam.
- Fixture databases are built with plain `sqlite3` (schema + a row, or the `import_state` marker) so
  the fixture never depends on the code under test.
- Parametrize AC 3's URL matrix as data (the table *is* the test).
- Assert **observable state** for the inertness-flavoured claims — the file does not exist, the
  engine attribute is `None`, the same engine object came back — never that a mock went uncalled.
- **Verification before completion:** paste actual ruff / mypy / pytest output into the Debug Log.
  "Tests pass" without output is not acceptance — standing agreement from the epic-5/6 retros.

### Previous story intelligence (c1-5, done 2026-07-25, merged as PR #13 — Greptile 5/5 zero findings)

- **The Host envelope is live on every request the suite makes.** The conftest seam stamps
  `app.state.bound_port` and derives a matching loopback `base_url`, so a new test file needs no
  Host awareness at all — but a test that invents its own `httpx.AsyncClient` with
  `base_url="http://testserver"` will get a typed `400`, not a `503`, and the diagnosis will look
  like a c1-6 bug. Use the fixture.
- **Send-don't-raise was a *middleware* ruling, not a general one** (Gotcha 7). c1-5's own module
  docstring explains the position argument; this story sits on the other side of
  `ExceptionMiddleware` and raises normally.
- **c1-5 corrected `errors.py`'s docstrings to name c1-6 as a first `CompanionError` caller** — that
  becomes true in this story. Check `CompanionError`'s docstring and `install_error_handling`'s
  docstring still read correctly once c1-6 lands (they should; they were written for it).
- **Three deferrals were closed by c1-5 and one opened** (`test_list_decks_with_strategy_field`
  same-tick ordering flake, needing a `src/data` home). It is unrelated to this story but lives in
  the same suite — if the full run shows that one test red, it is the known flake, not a regression.
- **The non-vacuity lesson from Greptile's PR #12 catch** is why AC 14 pairs every 503 with a 200
  from the same route: a guard that rejects everything passes a rejection test perfectly.
- **Gate-output homing** (open epic-7 action item): this story closes no deferral but **homes** one —
  the bare-path `CARDS_DATABASE_URL` item (deferred-work.md:268) now has a defined behaviour
  (`internal_error`) instead of an undefined crash. Record that against the existing item rather
  than opening a new one.
- **The mypy-hook `additional_dependencies` floor-vs-lock drift stays deferred** (Brad, 2026-07-25).
  This story adds no dependency, so it neither extends nor resolves that item.

### Git intelligence

`HEAD = 13a8a10` on `feat/companion-app` (the PR #13 merge). The per-story rhythm across c1-1 → c1-5
is: one focused `feat(companion): …` commit implementing the story, review fixes as separate
follow-up commits on the same branch, then a PR into `feat/companion-app` (Greptile reviews per
story). c1-4 needed a `feat(companion)!:` for a breaking wire-contract change; this story changes no
wire contract and needs no `!` — the three tokens it uses were all frozen by c1-4.

Suggested commit: `feat(companion): lazy database engine so a fresh install starts instead of erroring`.

### Latest technical information

Verified in this environment on 2026-07-25: **Python 3.12.13 · FastAPI 0.140.0 · Starlette 0.48.0 ·
SQLAlchemy 2.0.44 · aiosqlite 0.21.0 · httpx 0.28.1 · uvicorn 0.51.0 · pydantic 2.12.0** — all at or
above the spine's floors. No upgrade is part of this story and no dependency is added.

Probe results this story is built on (each re-runnable in a few lines):

- `create_async_engine(...)` leaves the file absent; the first `connect()` + `SELECT` creates it at
  **0 bytes**. `engine.dispose()` is safe to call twice.
- `make_url("sqlite+aiosqlite:///C:/x/y/cards.db").database` → `C:/x/y/cards.db`;
  `sqlite+aiosqlite://` → `None`; `sqlite+aiosqlite:///:memory:` → `:memory:`.
- A `CompanionError` raised **inside a dependency** answers `503 {"reason":
  "database_not_initialized"}`; raised inside a route body it answers its own token likewise.
- A registered handler for `SQLAlchemyError`/`DatabaseError` types both a route-raised and a
  dependency-raised failure (`503 {"reason": "database_unavailable"}`); a `yield` dependency's
  `except` block does see the route's exception on its way past.
- `issubclass(OperationalError, DatabaseError)` and `issubclass(DatabaseError, SQLAlchemyError)` are
  both `True`; the full MRO is `OperationalError → DatabaseError → DBAPIError → StatementError`.
- A URL under a **missing directory** raises `OperationalError: unable to open database file` — a
  `DatabaseError`, which is why the file check has to come first (Decide-once #2).
- A present-but-**empty** file answers `is_database_initialized → False` without raising.
- An exception raised **after** a dependency's `yield` escapes every handler (`RuntimeError` reached
  the caller).
- A cached engine sees a schema created underneath it by another connection (`False` → `True`).
- `src.paths.database_url()` **creates** the data directory as a side effect of resolving.

### Project Structure Notes

- `deps.py` under `src/companion/app/` is classified automatically by
  `test_import_boundary.py::test_every_companion_file_sits_in_a_guarded_category` (the `app/`
  branch), so **no boundary-test edit is required**. It may import `fastapi`, `starlette`,
  `sqlalchemy` and `src.data` / `src.paths` freely — it is app-side, not leaf.
- Pre-existing tracked files modified: `src/companion/app/main.py`, `src/companion/app/errors.py`,
  `_bmad-output/implementation-artifacts/deferred-work.md`,
  `_bmad-output/implementation-artifacts/sprint-status.yaml`, and the generated `plugin/` mirror.
  **Not** `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `src/data/**` or `src/mcp_server/**`.
- Naming follows the project conventions: `snake_case` functions, `PascalCase` class, Google
  docstrings on every public symbol, a module docstring at the top, `%`-style lazy log args, and
  guard clauses over nesting.

### References

- [epics-companion-app.md — Story 1.6](_bmad-output/planning-artifacts/epics-companion-app.md#L1044-L1073) — the source acceptance criteria · [Epic 1 framing](_bmad-output/planning-artifacts/epics-companion-app.md#L882-L888)
- Consumers: [Story 3.1 — "uses the shared lazy engine from Story 1.6"](_bmad-output/planning-artifacts/epics-companion-app.md#L1537-L1544) · [Story 3.9 — the fresh-install loop this closes in the UI](_bmad-output/planning-artifacts/epics-companion-app.md#L1773-L1801)
- ARCHITECTURE-SPINE.md — [AD-10](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L227-L240) · [AD-2](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L101-L112) · [AD-16](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L329-L352) · [Structural Seed — `deps.py`](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L438-L462)
- [prd.md — FR-22](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L104) · [NFR-02, the `mode=ro` line AD-2 overrides](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L161)
- [src/data/database.py](src/data/database.py#L32-L103) — `create_engine` / `create_session_factory`, the shared recipe · [`is_database_initialized`](src/data/database.py#L125-L163) — the readiness definition, and why it returns `False` rather than raising
- [src/mcp_server/server.py](src/mcp_server/server.py#L114-L118) — the MCP side's one-line construction of the same recipe
- [src/paths.py](src/paths.py#L23-L78) — `data_dir()` mkdirs; `database_url()` precedence
- [src/companion/app/main.py](src/companion/app/main.py#L40-L81) — `_shutdown` and the lifespan this story extends · [src/companion/app/errors.py](src/companion/app/errors.py#L343-L362) — `install_error_handling`, where the fourth handler lands
- [src/companion/contracts.py](src/companion/contracts.py#L46-L113) — what each of the three tokens means on the glass
- [tests/unit/companion/test_app.py](tests/unit/companion/test_app.py#L63-L101) — the inertness tests that must stay green unedited · [`test_startup_failure_propagates`](tests/unit/companion/test_app.py#L203-L220) — written to catch this story widening the lifespan `try`
- [tests/unit/companion/test_import_boundary.py](tests/unit/companion/test_import_boundary.py#L70-L106) — the banned surface, name by name
- [tests/unit/test_paths.py](tests/unit/test_paths.py#L71-L81) — the `CARDS_DATABASE_URL` / `PLANESWALKER_DATA_DIR` precedence, and the `delenv` precedent
- [c1-5 story record](_bmad-output/implementation-artifacts/c1-5-localhost-only-security-envelope-host-validation-and-cors.md) — the seam, the envelope and the send-don't-raise ruling this story deliberately does not copy · [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md#L268-L273) — the bare-path `CARDS_DATABASE_URL` item this story homes
- [project-context.md](_bmad-output/project-context.md) — `%`-style lazy logging, async-everywhere in `src/data`, ruff/mypy, Google docstrings

## Open questions for Brad

Neither blocks implementation.

1. **Is the per-request readiness probe worth pinning as a decision, or as a measurement?**
   Decide-once #3 chooses correctness over ~4 SELECTs per data request, which is right for a local
   SQLite file and for AC 8. If it later shows up in c10-3's latency work, the cheap fix is a short
   TTL on the *positive* verdict only (never on the negative one, which AC 8 depends on). Recording
   it now so the option is inherited rather than rediscovered.
2. **A `CARDS_DATABASE_URL` pointing at a non-SQLite backend is now silently permitted.**
   `database_file` returns `None` for, say, `postgresql+asyncpg://…`, so the existence check is
   skipped and the engine is created — which is the correct behaviour for a check about *files*, but
   it means an obviously-unsupported URL reaches SQLAlchemy rather than being refused early.
   Nothing in the product supports Postgres today (`asyncpg` is listed as a future dependency), so
   this is a deliberate non-decision; say the word if it should be an explicit refusal instead.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`

### Debug Log References

**Task 0 — state verification (2026-07-25).** `HEAD = 13a8a104643396928d969a6dfd4ef87c7fd08c8f` on
`feat/companion-app`, matching the story's `baseline_commit`. Branch created:
`Switched to a new branch 'feat/companion-c1-6-lazy-database-engine'`.
`Test-Path src/companion/app/deps.py` → `False`; `Test-Path tests/unit/companion/test_deps.py` →
`False`. `build_app()` read at `main.py:160-161`: `install_security(app)` then
`install_error_handling(app)`. Baseline:

```
==================== 1495 passed, 45 deselected in 47.52s =====================
```

Exactly the expected 1,495 / 45 — no delta. The two load-bearing findings re-confirmed by probe,
plus the URL matrix as a bonus:

```
1a engine created; file exists? False
1b after connect+select; file exists? True size 0
2a issubclass(OperationalError, DatabaseError) = True
2b issubclass(DatabaseError, SQLAlchemyError) = True
2c MRO = ['OperationalError', 'DatabaseError', 'DBAPIError', 'StatementError', 'SQLAlchemyError']
3 'sqlite+aiosqlite:///C:/x/y/cards.db' -> backend='sqlite' database='C:/x/y/cards.db'
3 'sqlite+aiosqlite:///./data/cards.db' -> backend='sqlite' database='./data/cards.db'
3 'sqlite+aiosqlite:///:memory:'        -> backend='sqlite' database=':memory:'
3 'sqlite+aiosqlite://'                 -> backend='sqlite' database=None
3 'postgresql+asyncpg://user@host/cardsdb' -> backend='postgresql' database='cardsdb'
```

**Red-phase evidence.** Task 1 (AC 3 matrix written before the module):

```
tests\unit\companion\test_deps.py:29: in <module>
    from src.companion.app import deps
E   ImportError: cannot import name 'deps' from 'src.companion.app'
```

Then green: `6 passed in 0.26s`. Task 2 red: `ImportError: cannot import name 'Database'`; green
`17 passed` with the single remaining failure being Task 4's own red
(`assert isinstance(None, Database)`). Task 3 red: `ImportError: cannot import name 'DbSession'`;
green left 7 failures, all one root cause (`No database holder on the app ... the lifespan did not
run`), cleared by Task 4. Task 5 red: three `database_unavailable` tests failing with the raw
`OperationalError` escaping; green after registering the handler.

**Task 5 probes — the two raise sites, measured rather than assumed.**

```
A corrupt file -> DatabaseError            (raised from inside the dependency's readiness probe)
A is DatabaseError? True
A orig = DatabaseError('file is not a database')
B bad statement -> OperationalError        (raised from inside a route body)
B is DatabaseError? True
B orig = OperationalError('no such table: no_such_table')
B str(exc) leaks bound param? True         <-- why AC 9 forbids str(exc)
C make_url(bare path) -> ArgumentError; ArgumentError? True; DatabaseError? False
```

The `str(exc)` leak is visible in the raw traceback too:
`[SQL: SELECT 1 FROM no_such_table WHERE name = ?]` /
`[parameters: ('bound-parameter-that-must-not-be-logged',)]`. The handler logs `exc.orig`, and
`test_the_rejection_is_logged_once_without_the_bound_parameters` asserts that string is **absent**
from the record.

**Mutation check on AC 7 — a finding, see Completion Notes.** With
`async with self._lock:` replaced by `if True:`, both concurrency tests **stayed green**
(`2 passed, 33 deselected`). The creation body is fully synchronous, so single-threaded asyncio never
interleaves the check-then-assign and no `gather` can force the race AC 7 describes. Two replacement
assertions were added; re-running the same mutation against them:

```
tests\unit\companion\test_deps.py .F
____ TestTheCreationLock.test_the_lock_is_held_while_the_engine_is_created ____
E   AssertionError: the engine was created outside the holder's lock
E   assert [False] == [True]
================= 1 failed, 1 passed, 35 deselected in 0.17s ==================
```

The lock was then restored and the suite re-verified green.

**Task 7 — quality gates (AC 15), actual output.**

```
$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
271 files already formatted

$ uv run mypy src/
Success: no issues found in 80 source files

$ uv run mypy src/ --platform linux
Success: no issues found in 80 source files

$ uv run pytest -m "not integration" -q
==================== 1532 passed, 45 deselected in 45.80s =====================
```

1,532 vs the 1,495 baseline = **+37, zero regressions**. `tests/unit/companion/test_deps.py` alone
reports `37 passed`, so every new test is in the new file and no existing file's count moved. The
companion suite is `222 passed`, with `test_app.py` (13), `test_errors.py`, `test_security.py`,
`test_server.py` and `test_import_boundary.py` (50) all green **unedited**.

**Task 7 — scope boundary (AC 17), by command.**
`git status --porcelain --` over `test_app.py`, `test_security.py`, `test_server.py`,
`test_import_boundary.py`, `test_errors.py`, `conftest.py`, `.github/workflows/ci.yml`,
`pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `src/data`, `src/mcp_server` returned
**empty**. Plugin mirror rebuilt (`Plugin assembled at ...\plugin (v0.4.0, 4 skills)`) and mirrors
exactly the three changed app files.

### Completion Notes List

- **AC 1** — `src/companion/app/deps.py` exports exactly the five named symbols: `Database`,
  `database(app)`, `database_file(url)`, `get_session(request)` and `DbSession`. Nothing else is
  public.
- **AC 2** — `build_app()` still creates no engine, holder or path (`TestConstructionIsInert` green
  unedited). The lifespan creates the holder beside the `instance_id` mint;
  `database(app).engine is None` after startup, pinned by
  `TestAccessor::test_the_lifespan_creates_an_inert_holder`. Reuse is pinned by identity (`is`), not
  a call count.
- **AC 3** — the five-row URL matrix is parametrized data. The existence check precedes engine
  creation, and `test_a_missing_file_answers_503` asserts the **observable filesystem state** (the
  file still does not exist) plus `engine is None` — read *inside* the lifespan, because `_shutdown`
  now disposes and would otherwise make that second assertion pass trivially.
- **AC 4** — readiness is `src.data.database.is_database_initialized`, re-probed every request. All
  **four** not-ready shapes are covered: file absent, file present but no `cards` table, table
  present but empty, and `import_state.in_progress = 1`.
- **AC 5** — one test drives `/health` and the data route against the same app in the same lifespan:
  200 and 503 respectively.
- **AC 6** — engine from `src.data.database.create_engine`, factory from `create_session_factory`;
  the URL is resolved **once** per creation and the same string feeds both the path derivation and
  the engine. No `mode=ro`, no `immutable`, no `?uri=true`.
- **AC 7 — implemented as specified, but the specified test is vacuous; two replacements added.**
  The lock, the double-check inside it and the `gather` count test are all in place. The mutation
  check above shows the count test **cannot fail**: `_create()` contains no `await`, so on
  single-threaded asyncio the check-then-assign is already atomic and the race AC 7 describes is not
  reachable today. Rather than ship a dead guard, two assertions with real teeth were added
  (`TestTheCreationLock`): the lock is **per-instance** (Gotcha 3's actual hazard) and it is **held
  while the engine is created** (which also fails if the creation call moves outside the lock). The
  second one is verified to go red under the mutation. The lock is kept — it is free, and the next
  `await` added to the creation path would otherwise silently reintroduce double-creation, whose
  symptom is an orphaned second pool nobody disposes. The caveat is written into both the
  `Database` docstring and the test docstrings so nobody later mistakes the `gather` test for proof.
  **Flagged for Brad** — no AC text was changed.
- **AC 8** — both appearance paths pass. No-engine-yet: 503, then the file is created and the next
  request succeeds *and* creates the engine. Engine-already-cached: an empty-but-present `cards.db`
  probes 503 with the engine cached, then a separate `sqlite3` connection writes the schema and a
  row, and the next request through the **same cached engine** (asserted by identity) returns 200.
  No invalidation machinery was added — Gotcha 11 holds.
- **AC 9** — one handler in `errors.py` for `sqlalchemy.exc.DatabaseError`, registered inside
  `install_error_handling`. Both raise sites are driven end-to-end. The rejection logs once at
  `WARNING` with `%`-style lazy args naming method, path, exception class and `exc.orig`; the test
  asserts the bound parameter is **absent** from the record. The `ArgumentError`-is-`internal_error`
  negative is pinned, and the subclass relationships are asserted directly.
- **AC 10** — `_shutdown` awaits `dispose()` through the accessor, guarded on `None`. Disposal is
  asserted as observable state (the pool object is replaced), not via a mock. The never-took-a-data-
  request case additionally asserts no `WARNING`+ record was logged, which is how a raising
  `dispose()` would surface given the lifespan's swallow-and-log.
- **AC 11** — nothing moved into the lifespan's `try`. Creating the holder cannot fail, so
  `test_startup_failure_propagates` stays green unedited.
- **AC 12 / Decide-once #1** — no route ships in `src/`. Two test-local routes on a real
  `build_app()`: `/_test/data` reads through its session (`SELECT 1`), `/_test/fail` fails inside its
  own body.
- **AC 13** — `test_import_boundary.py` green unedited; `deps.py` is classified automatically by the
  `app/` branch. Gotcha 8 was respected: no `_SESSION_MUTATORS` name is called on a `database`- or
  `db`-shaped receiver anywhere in the new code.
- **AC 14** — 37 unmarked unit tests, no network, no server boot, all through the `lifespan_client`
  seam (the sole exception is the no-holder test, which must *not* enter the lifespan and therefore
  builds its own client with a matching loopback `base_url` so it still passes c1-5's envelope).
  Fixtures are plain `sqlite3`. One test steers via `PLANESWALKER_DATA_DIR` with
  `monkeypatch.delenv("CARDS_DATABASE_URL", raising=False)`, per Gotcha 4. Every 503 is paired with a
  200 from the same route.
- **AC 15 / 16 / 17** — all green; see the Debug Log for actual output and the by-command scope
  check.
- **Open question 2 is now live behaviour, not theory.** A non-SQLite `CARDS_DATABASE_URL` is
  silently permitted (`database_file` returns `None`, the check is skipped, the engine is created and
  SQLAlchemy decides). Left as the story's deliberate non-decision; say the word if it should be an
  explicit refusal.
- **Deferred-work homing** — the bare-path `CARDS_DATABASE_URL` item was annotated in place rather
  than reopened. One correction to its original wording: the raise site is
  `sqlalchemy.engine.make_url` inside `database_file`, one step earlier than `create_async_engine`,
  because the companion parses the URL to derive the path before building an engine. The outcome
  (`500 internal_error`, process survives) is what the story predicted.

### File List

**New**

- `src/companion/app/deps.py`
- `tests/unit/companion/test_deps.py`
- `plugin/server/src/companion/app/deps.py` (generated mirror)

**Modified**

- `src/companion/app/main.py` — lifespan creates the holder; `_shutdown` disposes it; both
  docstrings updated
- `src/companion/app/errors.py` — `database_error_handler` + its registration; the
  which-exception-becomes-which-token enumeration added to `install_error_handling`'s docstring
- `plugin/server/src/companion/app/main.py` (generated mirror)
- `plugin/server/src/companion/app/errors.py` (generated mirror)
- `_bmad-output/implementation-artifacts/deferred-work.md` — bare-path `CARDS_DATABASE_URL` item
  homed
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — c1-6 → in-progress → review
- `_bmad-output/implementation-artifacts/c1-6-lazy-database-engine-so-a-fresh-install-starts-instead-of-erroring.md`

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-25 | Story c1-6 implemented on `feat/companion-c1-6-lazy-database-engine` off `13a8a10`. `deps.py` ships the lazy engine seam (`Database` holder, `database()` accessor, pure `database_file()`, `get_session` dependency, `DbSession`); the lifespan creates the inert holder and `_shutdown` disposes it; `errors.py` gains the single `DatabaseError` → `503 database_unavailable` mapping. No route ships in `src/` (Decide-once #1) — the dependency is driven through two test-local routes on a real `build_app()`. 37 new tests; suite 1,495 → **1,532 passed / 45 deselected**, zero regressions; ruff, `mypy src/` and `mypy src/ --platform linux` all clean. `test_app.py`, `test_errors.py`, `test_security.py`, `test_server.py`, `test_import_boundary.py` and `conftest.py` all green **unedited**, verified by command. Plugin mirror rebuilt. Homes (does not fix) the bare-path `CARDS_DATABASE_URL` deferral, correcting its raise site to `make_url`. **One finding for review:** AC 7's `gather` count test is vacuous — measured, it stays green with the lock removed, because the creation body has no `await` — so two assertions that do fail under that mutation were added (per-instance lock, lock held during creation) and the caveat documented in code. Status → review. |
| 2026-07-25 | Story c1-6 created from epics Story 1.6 + AD-10/AD-2/AD-16, with every load-bearing claim verified against the installed FastAPI 0.140.0 / SQLAlchemy 2.0.44 / aiosqlite 0.21.0 rather than assumed: a first connection creates a zero-byte SQLite file (the reason the existence check precedes engine creation), `make_url(...).database` across five URL shapes, `CompanionError` raised from a dependency reaching the registered handler (unlike from middleware), a `DatabaseError` handler typing both dependency- and route-raised failures, the `OperationalError → DatabaseError → DBAPIError` MRO, a missing directory raising `OperationalError` not a file error, an empty file probing `False` without raising, a post-`yield` teardown exception escaping every handler, a cached engine seeing a schema created underneath it, and `database_url()` creating the data directory as a side effect. Baseline re-measured at `13a8a10`: 1,495 passed / 45 deselected. Homes (does not fix) the bare-path `CARDS_DATABASE_URL` deferral. Status → ready-for-dev. |

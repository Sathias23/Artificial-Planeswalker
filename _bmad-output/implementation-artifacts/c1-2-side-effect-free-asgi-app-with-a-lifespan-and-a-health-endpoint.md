---
baseline_commit: ce13f5f
epic: c1
story: c1-2
work_branch: feat/companion-app
story_branch: feat/companion-c1-2-asgi-app-lifespan-health
---

# Story C1.2: Side-effect-free ASGI app with a lifespan and a health endpoint

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want `build_app()` to construct the ASGI application without touching anything outside the process,
so that the whole backend is testable in-process without binding a port or overwriting real files on disk.

**Why this story is second.** c1-1 landed the guards; this is the first companion code born under
them. It creates the app object, the lifespan and the one endpoint that has no prerequisites — and
it fixes the **testing seam** (`httpx.ASGITransport` + a lifespan driver) that stories c1-3 through
c1-9 all reuse. AD-10 exists so this seam is possible: everything with an external effect belongs to
the lifespan, so construction stays inert and the bulk of the backend never needs a socket.

## Acceptance Criteria

1. **`build_app()` is inert (AD-10).** `src/companion/app/main.py` exposes
   `build_app() -> FastAPI`. Calling it binds no port, writes no file, **creates no directory**, and
   creates no database engine. In particular it must not call `src.paths.data_dir()` (or
   `database_path()` / `fastembed_cache_dir()`, which call it) at import time or during
   construction — **`data_dir()` does `mkdir(parents=True, exist_ok=True)`, so merely calling it is a
   filesystem side effect** and fails this AC.

2. **Construction is proven inert, not asserted.** A test points `PLANESWALKER_DATA_DIR` at a
   **non-existent** subdirectory of `tmp_path`, imports `src.companion.app.main` and calls
   `build_app()`, then asserts that directory still does not exist and that `tmp_path` gained no
   entries. A second test asserts no socket is bound during construction (monkeypatch
   `socket.socket.bind` to raise, then call `build_app()`).

3. **The lifespan mints and holds `instance_id`.** Startup sets a per-process `instance_id` on
   application state (`app.state.instance_id`), a `str(uuid.uuid4())`. It is stable for the lifetime
   of the running app and different on every fresh `build_app()` + lifespan entry. It is **not**
   assigned in `build_app()` — minting belongs to the lifespan, so a constructed-but-never-started
   app has no identity to leak.

4. **`GET /health` returns `200` with a typed body (FR-14).** The body carries at least
   `{status, instance_id}` and is declared as the route's `response_model`, so it lands in
   `app.openapi()` for the c2-3 TypeScript generation (AD-12). `status` is `Literal["ok"]` — a
   closed token, extendable only by adding a member. The endpoint requires **no authentication**: it
   is what callers use *before* deciding to send a token (AD-4's identity probe).

5. **The health response model lives in the leaf.** It is defined in `src/companion/contracts.py`
   as `HealthResponse` (pydantic import only — leaf-legal under AD-3), because the AD-4 identity
   probe in story c1-8 lives in the leaf and **cannot import `src.companion.app`**. See Decide-once
   #1. This story creates `contracts.py` containing `HealthResponse` and nothing else; the c4
   envelope (AD-6/AD-7) is added to the same file later.

6. **Clean shutdown releases everything and swallows nothing upward.** The lifespan is written
   `try: yield finally: <teardown>` from the first commit, and the teardown body is wrapped so that
   **no exception escapes the shutdown path** — a failure is logged (`logger.exception`, or
   `logger.warning` with `%`-style lazy args) and the context manager exits normally. A test
   monkeypatches a teardown step to raise and asserts `async with lifespan(app)` exits cleanly and
   the failure was logged. This story acquires no external resource yet; the structure exists so
   c1-6's engine dispose and c1-7's discovery-file removal land in an already-correct teardown.

7. **The app is drivable in-process with no network.** Tests reach it through
   `httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")`.
   **`ASGITransport` does not run lifespan events** — a shared async helper in
   `tests/unit/companion/conftest.py` enters the lifespan and yields a client, so every later story
   in Epic C1 drives startup the same way. See Decide-once #2. No new dependency is added for this
   (no `asgi-lifespan`, no `TestClient`).

8. **Dependencies added, everywhere they must be declared.** `fastapi>=0.139.2` and
   `uvicorn[standard]>=0.51.0` are added to `pyproject.toml` `[project].dependencies` via
   `uv add` (never a hand-edit), and `uv.lock` is regenerated and committed — CI runs
   `uv sync --locked`. `fastapi` is **also** added to `.pre-commit-config.yaml`'s mypy
   `additional_dependencies`, because that hook runs in an isolated env over `^src/` and
   `src/companion/app/main.py` now imports FastAPI. (uvicorn is declared here per c1-1's homing note
   but is not yet imported by `src/`; c1-3 adds it to the mypy hook when it does.)

9. **The c1-1 guards still pass, unmodified.** `tests/unit/companion/test_import_boundary.py` is
   **not edited by this story**. The new files must satisfy it as written:
   - `src/companion/contracts.py` is already in `_LEAF_MODULES`, so it is now scanned with
     `role="leaf"` — it may import only the stdlib, `pydantic`, `httpx`, `src.paths` and its sibling
     leaf modules. **No `fastapi` import, not even under `if TYPE_CHECKING:`** (there is no
     TYPE_CHECKING exemption in any role).
   - Everything under `src/companion/app/` is exempt from the leaf rule and from the
     outside-app import rule, and satisfies the enumeration pin automatically.
   - The write guard scans `src/companion/**` including `app/` — no session mutator on a
     session-shaped receiver, no SQLAlchemy DML, no `init_database` / `create_all`, no
     `src.data.importers`.
   - **Nothing outside `src/companion/app/` may import it at module level** — so
     `src/companion/app/__init__.py` must stay a docstring-only file and must **not** re-export
     `build_app`.

10. **Quality gates green (NFR-07).** `uv run ruff check .`, `uv run ruff format --check .`,
    `uv run mypy src/` and `uv run pytest -m "not integration"` all pass, with **no new failures**
    against the 1,359-test baseline. New tests are unmarked unit tests in `tests/unit/companion/`
    (no `integration` marker — AD-10 reserves the single real-socket test for later).

11. **Plugin mirror rebuilt and committed.** `uv run python -m scripts.build_plugin`, then commit
    `plugin/`. This story changes `src/`, `pyproject.toml` **and** `uv.lock` — all three are
    `build_plugin` inputs and all three are watched by the `build-plugin-sync` pre-commit hook and
    the CI *"Plugin tree in sync with src/"* step.

12. **Scope boundary — what this story must NOT do.** No port bind, no `uvicorn.run`, no CLI wiring
    (c1-3, c1-9). No discovery file (c1-7). No `Host` middleware, no CORS, no token, no ticket
    (c1-5). No database engine, session dependency or `deps.py` (c1-6). No typed error contract or
    reason-token enum (c1-4) — `/health` has no failure path to model. No `state.py`, `security.py`,
    `ws.py`, `images.py`, `static/`, no `ui/`, no other route. No edit to
    `tests/unit/companion/test_import_boundary.py` or `.github/workflows/ci.yml`.

## Tasks / Subtasks

- [x] **Task 0 — State verification** (standing team agreement since the epic-6 retro: any story
      whose notes assert repository state opens with the cheap check that proves it)
  - [x] Create `feat/companion-c1-2-asgi-app-lifespan-health` **off `feat/companion-app`** (not off
        `master`); the story PR targets `feat/companion-app`.
  - [x] Confirm `src/companion/__init__.py` and `src/companion/app/__init__.py` exist and are
        docstring-only, and that `src/companion/contracts.py` does **not** yet exist.
  - [x] Confirm `fastapi` is not importable (`uv run python -c "import fastapi"` fails) — this
        story is what installs it.
  - [x] Baseline the suite: `uv run pytest -m "not integration" -q` → record the count (expected
        1,359 passed, 45 deselected). *Actual: **1,360** passed, 45 deselected — see Debug Log.*

- [x] **Task 1 — Dependencies** (AC: 8, 11)
  - [x] `uv add "fastapi>=0.139.2" "uvicorn[standard]>=0.51.0"` — regenerates `uv.lock`.
  - [x] Add `fastapi>=0.139.2` to `.pre-commit-config.yaml` → mypy hook `additional_dependencies`.
  - [x] Sanity-check the resolution: `uv run python -c "import fastapi, uvicorn; print(fastapi.__version__, uvicorn.__version__)"`. *→ `0.140.0 0.51.0`.*

- [x] **Task 2 — The leaf contract** (AC: 5, 9)
  - [x] `src/companion/contracts.py` — module docstring naming it the leaf wire contract (AD-3,
        AD-12) and stating that it may import only pydantic/httpx/stdlib/`src.paths`/sibling leaves.
  - [x] `class HealthResponse(BaseModel)` with `status: Literal["ok"]` and `instance_id: str`,
        Google-style docstring.
  - [x] Immediately run `uv run pytest tests/unit/companion/test_import_boundary.py -q` — this file
        is now scanned as a leaf for the first time. *→ 50 passed, before `main.py` existed.*

- [x] **Task 3 — App, lifespan and health route** (AC: 1, 3, 4, 6)
  - [x] `src/companion/app/main.py` — module docstring; module-level
        `logger = logging.getLogger(__name__)`; a module-level
        `@asynccontextmanager async def lifespan(app: FastAPI) -> AsyncIterator[None]` (module-level
        so tests can drive it directly — Decide-once #2); `build_app() -> FastAPI`.
  - [x] Lifespan startup: `app.state.instance_id = str(uuid.uuid4())`. Nothing else — no path
        resolution, no engine, no file.
  - [x] Lifespan teardown: `finally:` → call a `_shutdown(app)` helper inside `try/except Exception`
        with a logged failure, so AC 6's "no exception escapes" is structural.
  - [x] `src/companion/app/routes/__init__.py` (docstring only) + `src/companion/app/routes/health.py`
        with an `APIRouter` and `@router.get("/health", response_model=HealthResponse)` reading
        `request.app.state.instance_id`.
  - [x] `build_app()` constructs `FastAPI(title=..., lifespan=lifespan)` and includes the health
        router. Do not touch `src/companion/app/__init__.py` (AC 9).

- [x] **Task 4 — The in-process test seam** (AC: 2, 7)
  - [x] `tests/unit/companion/conftest.py` with an async context-manager helper (e.g.
        `lifespan_client(app)`) that enters `lifespan(app)` and yields a configured
        `httpx.AsyncClient` over `ASGITransport`. Docstring must state *why* it exists:
        `ASGITransport` does not run lifespan events.
  - [x] `tests/unit/companion/test_app.py` — `async def test_...` (project pytest is
        `asyncio_mode = "auto"`; no `@pytest.mark.asyncio`, and do **not** invent a marker,
        `--strict-markers` is on).

- [x] **Task 5 — Tests** (AC: 1–7)
  - [x] Inertness: no directory created under a non-existent `PLANESWALKER_DATA_DIR`; no socket
        bound during construction; `build_app()` leaves `app.state` without `instance_id`.
  - [x] Identity: `instance_id` present after startup, stable across two requests in one lifespan,
        and different between two separate `build_app()` + lifespan entries.
  - [x] `GET /health` → `200`, body validates against `HealthResponse`, `status == "ok"`,
        `instance_id` matches `app.state.instance_id`. No auth header sent.
  - [x] Shutdown: teardown runs on clean exit; a raising teardown step does not propagate and is
        logged (`caplog`).
  - [x] OpenAPI: `build_app().openapi()` contains the `HealthResponse` component and the `/health`
        path — the c2-3 generator's input exists from day one (AD-12).

- [x] **Task 6 — Quality gates and plugin mirror** (AC: 10, 11, 12)
  - [x] `uv run ruff check . --fix` · `uv run ruff format .` · `uv run mypy src/` ·
        `uv run pytest -m "not integration"` — paste actual counts into Completion Notes.
  - [x] `uv run python -m scripts.build_plugin`, `git add plugin/`, then verify
        `git status --porcelain -- plugin/` is clean after the commit (that is exactly what CI
        checks) and that `plugin/server/pyproject.toml` + `plugin/server/uv.lock` picked up the new
        dependencies.
  - [x] Confirm `tests/unit/companion/test_import_boundary.py` and `.github/workflows/ci.yml` are
        untouched (AC 9, 12).

### Review Findings

Code review 2026-07-25 (Blind Hunter + Edge Case Hunter + Acceptance Auditor; diff
`ce13f5f...ab0657b`). Auditor verdict: **Accept** — no AC violations, no scope breaches, all four
gates independently re-run green. Findings below are hardening and record-accuracy items.

- [x] [Review][Patch] Story doc Gotcha 6's failure mode is factually wrong — the pre-commit mypy
      hook runs `--ignore-missing-imports`, so a missing `additional_dependencies` entry does not
      fail the hook; it silently types FastAPI as `Any` and passes with degraded checking. Correct
      the gotcha and record the real hazard (green hook ≠ typed FastAPI when the list drifts).
      [_bmad-output/implementation-artifacts/c1-2-side-effect-free-asgi-app-with-a-lifespan-and-a-health-endpoint.md — Gotchas #6] (Severity: Medium)
- [x] [Review][Patch] `/health` docstring overclaims "always 200 / no failure path" — the claim is
      contingent on the lifespan having run; served without it (`--lifespan off`, bare
      `ASGITransport`, future mounting), `request.app.state.instance_id` raises `AttributeError`
      → bare 500. Soften the docstring to state the precondition. (A 503 guard was considered and
      dismissed: AC 12 forbids the error contract, and Dev Note #3's design is "a companion that
      cannot answer does not answer" — c1-4 owns failure modelling.)
      [src/companion/app/routes/health.py:16-17] (Severity: Low)
- [x] [Review][Patch] Import-time socket bind is never proven absent — `test_construction_binds_no_socket`
      monkeypatches `bind` but calls `build_app()` on the long-cached module; a module-level bind
      in `main.py` would pass. Route the test through `_fresh_main` so the import path is covered
      too (AC 1 says "at import time or during construction"). [tests/unit/companion/test_app.py:75-81] (Severity: Low)
- [x] [Review][Patch] `_fresh_main` eviction scope is narrower than the inertness claim —
      only `src.companion.app*` is evicted, so an import-time `data_dir()` call added later to
      `src.companion.contracts` or `src.paths` would go undetected (both stay cached); the
      `startswith` prefix also lacks a dot boundary. Widen eviction to `src.companion` +
      `src.paths` with a dot-boundary match — c1-3..c1-9 inherit this helper.
      [tests/unit/companion/test_app.py:34-36] (Severity: Low)
- [x] [Review][Patch] Startup-failure asymmetry is untested — nothing pins that a failure *before*
      `yield` propagates (only teardown is swallowed). A later refactor that widens the `try` when
      c1-6's engine startup lands would silently convert startup failures into swallowed ones. Add
      a test that a raising startup step propagates out of lifespan entry.
      [src/companion/app/main.py:65-73] (Severity: Low)
- [x] [Review][Patch] Teardown-logging test asserts the message only incidentally — the string
      reaches `caplog` via the traceback `logger.exception` attaches; the record's level, logger
      name and `exc_info` are unasserted. Assert the record directly (ERROR level, exc_info set).
      [tests/unit/companion/test_app.py:164-177] (Severity: Low)
- [x] [Review][Patch] Debug Log names the wrong sixth new lock package — the six new `[[package]]`
      entries are `annotated-doc`, `fastapi`, `httptools`, **`uvloop`**, `watchfiles`,
      `websockets`; `uvicorn` was a pre-existing transitive upgraded 0.37.0 → 0.51.0 (the same
      paragraph already says so). [story Debug Log — Task 1] (Severity: Low)
- [x] [Review][Patch] Baseline delta 1,359 → 1,360 is now identified — the +1 is c1-1's final
      review commit `57b19c9` (dml-star-import negative test; its commit message records "1360
      passed"), which landed after this story's notes were written. Record the identification in
      the Debug Log so the delta is explained, not just observed. [story Debug Log — Task 0] (Severity: Low)
- [x] [Review][Patch] Dev Notes "Project Structure Notes" omits `sprint-status.yaml` from the
      modified-files prose ("the only pre-existing tracked files this story modifies are…") while
      the diff and File List both include it. Align the prose. [story Dev Notes — Project Structure Notes] (Severity: Low)
- [x] [Review][Patch] `sprint-status.yaml` duplicated header out of sync — the line-2 *comment*
      copy of `last_updated` still says "story c1-2 created" while the real field (line 49) says
      "implemented → review"; this commit updated one copy of the hand-maintained pair.
      [_bmad-output/implementation-artifacts/sprint-status.yaml:2] (Severity: Low)
- [x] [Review][Defer] The `lifespan_client` seam is not parameterizable for its named inheritors —
      `BASE_URL` is hardcoded and the helper takes no headers/base-url kwargs, but c1-5's
      Host-validation tests must vary exactly those. Extending the signature with optional kwargs
      is backward-compatible, so it belongs to c1-5 when the need is concrete.
      [tests/unit/companion/conftest.py:26-43] — deferred to c1-5
- [x] [Review][Defer] mypy hook `additional_dependencies` resolve independently of `uv.lock`, so
      pre-commit may type-check a different FastAPI than the locked 0.140.0 — pre-existing pattern
      (pydantic, sqlalchemy already listed) extended here, not introduced.
      [.pre-commit-config.yaml:9] — deferred, pre-existing

Dismissed as noise (4): teardown `except Exception` not catching `BaseException` (correct asyncio
semantics — swallowing `CancelledError`/`KeyboardInterrupt` would break cancellation; AC 6's intent
is teardown *failures*); companion conftest requiring FastAPI to collect the guard suite (fastapi
is a hard runtime dep in every supported env, root and plugin, and the guard is AST-based);
`uvicorn[standard]` shipped with zero imports (spec-mandated — AC 8 + c1-1's homing note);
`instance_id` typed as unconstrained `str` (the spec pins `instance_id: str`; a UUID wire type
would deviate from the AC).

## Dev Notes

### Decide-once rulings (made here so later stories inherit them)

**#1 — `HealthResponse` lives in `src/companion/contracts.py`, not in `app/`.** The forcing
function is AD-3 plus story c1-8: the identity probe ("`GET /health`, match the echoed
`instance_id`, then send the token") **lives in the leaf so both the startup check and the companion
tools share one implementation**, and the leaf may not import `src.companion.app`. A health model
defined under `app/` would therefore be duplicated or parsed as raw JSON by the leaf — exactly the
"second shape drifting from the first" that AD-1 and AD-12 exist to prevent. EPIC-SPLIT gives E4 the
**envelope**, not exclusive ownership of the file; this story creates the file with one model and
c4 adds the envelope to it. *(Flagged for Brad below.)*

**#2 — Tests drive the lifespan by calling `lifespan(app)` directly, via a shared conftest helper.**
`httpx.ASGITransport` does not run lifespan events — this is documented FastAPI behaviour, and the
official async-test guidance is to add `asgi-lifespan`'s `LifespanManager`. Three options were
weighed: (a) add `asgi-lifespan` as a dev dependency; (b) use `fastapi.testclient.TestClient` as a
context manager (sync, spins a portal thread, and pulls the test suite away from the
`asyncio_mode = "auto"` async style used everywhere else); (c) keep `lifespan` a **module-level**
function in `main.py` and have the helper do `async with lifespan(app):` before yielding the client.
**(c) wins**: no new dependency, stays async, and it depends only on this project's own public
surface — not on Starlette internals such as `app.router.lifespan_context`. The cost is that the
raw ASGI `lifespan` *scope* messages are never exercised in unit tests; AD-10's single
`integration`-marked real-backend test is where that is covered.

**Consequence of #2, and it is load-bearing: startup values go on `app.state`, never on a state dict
yielded from the lifespan.** Starlette supports `yield {...}` to populate `scope["state"]`, but that
path only runs under a real ASGI lifespan handshake — driving the context manager directly would
silently skip it and every later story's state would read as missing under test. Use
`app.state.<name>` throughout Epic C1.

**#3 — `/health`'s `status` field is not the MCP envelope.** AD-16 bans the project's
`{"status": "ok", ...}` *result envelope* from REST: success bodies are the resource itself,
unwrapped. `/health` is not an exception to that rule — its body **is** the health resource, and
`status` is a field of it, typed `Literal["ok"]` so it stays a closed token in the project's
convention. Do not read this as licence to wrap any other endpoint.

### Architecture rules this story implements

- **AD-10** — `build_app()` has zero side effects; the lifespan owns everything external; the
  engine is lazy. This story is the AD's first half. The rule is what makes FR-22 reachable: a
  missing database must be a *served UI state*, which is only possible if startup never touches it.
- **AD-3** — the leaf/app split. `contracts.py` (leaf, pydantic-only) vs `app/` (FastAPI).
- **AD-12** — Pydantic is the single source of truth and TS is generated from `app.openapi()`.
  Declaring `response_model=HealthResponse` is what puts the shape into OpenAPI; a hand-built
  `dict` return would leave c2-3's generator with nothing to emit.
- **AD-16** — REST is HTTP-native. `/health` returns `200` + the resource; no envelope.
- **AD-4 / FR-14** — `instance_id` is the identity a caller verifies before sending the token.
  `/health` is deliberately unauthenticated for that reason.
- **AD-15** — the companion process owns its stdout/stderr, unlike the MCP process. Module-level
  `logging` with `%`-style lazy args is still the rule; no `print()` in `src/`.

### Source tree — what exists, what this story adds

```text
src/
  paths.py                     # EXISTS — data_dir() MKDIRS on call; do not call it in build_app()
  companion/
    __init__.py                # EXISTS — docstring only, leaf-constrained by the guard
    contracts.py               # NEW — HealthResponse only (leaf: pydantic import)
    app/
      __init__.py              # EXISTS — docstring only; DO NOT add re-exports (AC 9)
      main.py                  # NEW — build_app() + module-level lifespan
      routes/
        __init__.py            # NEW — docstring only
        health.py              # NEW — APIRouter with GET /health
tests/
  unit/companion/
    __init__.py                # EXISTS
    test_import_boundary.py    # EXISTS — NOT edited by this story
    conftest.py                # NEW — lifespan_client helper (the seam for c1-3..c1-9)
    test_app.py                # NEW
```

`discovery.py`, `client.py`, `app/deps.py`, `app/state.py`, `app/security.py`, `app/ws.py`,
`app/images.py`, `app/static/` and `ui/` all belong to later stories — creating a stub for any of
them here puts a file under a guard no story yet owns.

### Gotchas specific to this story

1. **`src.paths.data_dir()` creates a directory as a side effect.** It ends
   `base.mkdir(parents=True, exist_ok=True)`. `database_path()`, `fastembed_cache_dir()` and
   `database_url()` all call it. AC 1 is violated by a single such call anywhere on the
   construction path — including at module import time in `main.py`. Defer all path resolution to
   the lifespan (c1-7) or to first use (c1-6).
2. **`src/companion/contracts.py` is scanned as a leaf the moment it exists.** Before this story the
   leaf scan ran over `src/companion/__init__.py` only. A stray `from fastapi import ...` — even
   inside `if TYPE_CHECKING:` — fails `test_leaf_modules_import_only_their_allowed_surface`
   immediately. Run that test file first, before writing `main.py`.
3. **Do not re-export `build_app` from `src/companion/app/__init__.py`.** It stays docstring-only.
   The guard's `outside_app` scan is what makes this matter later: c1-9's dispatcher may only do a
   *function-local* import of `src.companion.app.*`, and a convenience re-export invites the
   module-level form.
4. **`--strict-markers` is on.** Do not invent a marker for the new tests. They are plain unmarked
   unit tests and must pass under both `uv run pytest` and `uv run pytest -m "not integration"`.
5. **`asyncio_mode = "auto"`** — write `async def test_...` directly; adding
   `@pytest.mark.asyncio` is redundant and inconsistent with the rest of the suite.
6. **The pre-commit mypy hook runs in its own isolated environment, with
   `--ignore-missing-imports`.** *(Corrected in review — the original note claimed the hook would
   fail without the entry.)* Without `fastapi` in `additional_dependencies` the hook does **not**
   fail: `--ignore-missing-imports` makes it silently type all of FastAPI as `Any` and pass with
   degraded checking. That is the real hazard — a green hook proves FastAPI-typed code only while
   `additional_dependencies` tracks the third-party imports `^src/` actually makes. AC 8's third
   declaration site exists to keep that check honest, not to un-break a red hook.
7. **`uv.lock` is a `build_plugin` input** (`SERVER_FILES = ["pyproject.toml", "uv.lock", ...]`), so
   a dependency change makes the plugin mirror stale in two places, not one. An epic-4 retro action
   item records a local checkout where `.git/hooks/pre-commit` was missing and the sync silently did
   not run — run the build explicitly and check `git status --porcelain -- plugin/`.
8. **The write guard scans `app/` too.** FastAPI's `@router.delete(...)` / `app.delete(...)` are
   safe (`router` / `app` are not in `_SESSION_RECEIVERS`, and `_DML_RECEIVERS` is
   `{sqlalchemy, sa, sql}`), but keep it in mind when routes grow in c1-4 and c1-6.

### Testing standards

- New tests live in `tests/unit/companion/` — unit layer, fast, no I/O beyond `tmp_path` and
  `monkeypatch`. AD-10 reserves the single `integration`-marked real-socket test for a later story;
  do not add one here.
- Iterate with `uv run pytest tests/unit/companion/ -v`, then run the full
  `uv run pytest -m "not integration"` before claiming done.
- **Verification before completion:** paste actual ruff / mypy / pytest output into the Completion
  Notes. "Tests pass" without output is not acceptance — this is a standing agreement from the
  epic-5/6 retros and c1-1 was corrected for it.
- The AC-2 inertness tests are the ones that will catch a regression years from now. Make them
  assert *observable filesystem state*, not that a mock was not called.

### Previous story intelligence (c1-1, done 2026-07-25)

- **The guards are the acceptance surface for everything in `src/companion/`.** c1-1's review added
  an **enumeration pin**: every `*.py` under `src/companion/**` must be under `app/`, be an
  `__init__.py`, or be a member of `_LEAF_MODULES`. `contracts.py` is already a member and
  everything else this story adds is under `app/` — so no guard edit is needed. If you find yourself
  wanting to edit the guard file, stop: it means a file is in the wrong place.
- **TYPE_CHECKING imports count as module-level in every role** (Brad's ruling on c1-1's review).
  There is no typing escape hatch for the leaf.
- **c1-1 homed FastAPI/uvicorn on this story explicitly** — "FastAPI >=0.139.2 and
  uvicorn[standard] >=0.51.0 are the spine's pinned floors; they belong to story c1-2."
- **Construction-site enumeration** (standing agreement from the epic-7 retro): when a concept
  threads through multiple sites, enumerate every site before claiming end-to-end. For this story
  that is AC 8's *three* declaration sites for one dependency — `pyproject.toml`, `uv.lock`, and
  the pre-commit mypy hook — plus the plugin mirror.
- **Gate-output homing** (open epic-7 action item): the two decide-once rulings above are homed on
  **c1-8** (leaf probe consuming `HealthResponse`) and **c1-3/c1-5/c1-6/c1-7** (the conftest
  lifespan helper) rather than left as prose.

### Git intelligence

`HEAD = ce13f5f` on `feat/companion-app` — the merge of PR #9 (c1-1). The three code commits before
it are all c1-1: `dee555e` (skeleton + guards), `931cdc2` (11 review patches), `57b19c9` (Greptile
P1, star-import DML bypass). Pattern to match: one focused `feat(companion): …` commit, with review
fixes as separate follow-up commits on the same branch.

Suggested commit: `feat(companion): side-effect-free ASGI app with lifespan and health endpoint`.

### Latest technical information

- **FastAPI** latest is **0.140.0** (PyPI, checked 2026-07-25); the spine's `>=0.139.2` floor
  resolves to it. **uvicorn** latest is **0.51.0**, exactly the spine's floor. Both require
  Python `>=3.10`, satisfied by this project's `>=3.12`. Bind as `>=` floors, matching the existing
  `pyproject.toml` convention — do not pin exact versions.
- **`httpx.ASGITransport` does not run lifespan events.** This is stated in FastAPI's own async-test
  documentation, which recommends `asgi-lifespan`'s `LifespanManager` as the fix. Decide-once #2
  takes the dependency-free route instead; the important thing is that a test which "starts the app"
  by making a request through `ASGITransport` alone would see **no** `instance_id` and is wrong.
- **Lifespan shape:** `@asynccontextmanager async def lifespan(app: FastAPI) -> AsyncIterator[None]`
  passed as `FastAPI(lifespan=lifespan)`. Startup code before `yield`, teardown after. `on_event`
  (`@app.on_event("startup")`) is the deprecated predecessor — do not use it.
- `httpx>=0.28.1` is already a project dependency; `ASGITransport(app=app)` is the current keyword
  form.

### Project Structure Notes

- Purely additive under `src/companion/`. The only pre-existing tracked files this story modifies
  are `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, the story-tracking
  `sprint-status.yaml` and the generated `plugin/` mirror.
- `src/companion/app/__init__.py` is deliberately left unchanged — see AC 9 and gotcha 3.
- No existing module imports the new code, so there is no regression surface beyond the dependency
  addition itself (a new transitive dependency set entering `uv.lock`).

### References

- [epics-companion-app.md — Story 1.2](_bmad-output/planning-artifacts/epics-companion-app.md#L924-L950) — the source acceptance criteria
- [epics-companion-app.md — Epic 1 framing](_bmad-output/planning-artifacts/epics-companion-app.md#L879-L886) and [stories 1.3–1.9](_bmad-output/planning-artifacts/epics-companion-app.md#L952-L1166) — what must remain buildable on this seam
- ARCHITECTURE-SPINE.md — [AD-3](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L114-L125) · [AD-4](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L127-L141) · [AD-10](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L227-L240) · [AD-12](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L272-L290) · [AD-16](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L329-L347) · [Stack](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L357-L383) · [Structural Seed](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L433-L457)
- [EPIC-SPLIT.md — E1 ownership](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/EPIC-SPLIT.md#L58-L69) and [the one serialisation worth respecting](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/EPIC-SPLIT.md#L81-L85)
- [prd.md — FR-14, FR-22, NFR-07](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L102-L104)
- [c1-1 story record](_bmad-output/implementation-artifacts/c1-1-companion-package-skeleton-with-ci-enforced-import-boundaries.md) — decide-once rulings, guard limitations, gate-output discipline
- [tests/unit/companion/test_import_boundary.py](tests/unit/companion/test_import_boundary.py) — the guards this story must satisfy without editing
- [src/paths.py](src/paths.py#L23-L45) — `data_dir()` mkdirs; the AC-1 landmine
- [project-context.md](_bmad-output/project-context.md) — layer boundaries, logging, ruff/mypy/docstring conventions
- [pyproject.toml](pyproject.toml#L22-L33) — dependency block · [.pre-commit-config.yaml](.pre-commit-config.yaml#L11-L22) — mypy `additional_dependencies` · [ci.yml](.github/workflows/ci.yml#L41-L67) — gates + plugin drift check
- [scripts/build_plugin.py](scripts/build_plugin.py#L62) — `SERVER_FILES` includes `pyproject.toml` and `uv.lock`
- [sprint-status.yaml — companion key scheme + branch workflow](_bmad-output/implementation-artifacts/sprint-status.yaml#L187-L237)

## Open questions for Brad

Neither blocks implementation.

1. **`contracts.py` created here (Decide-once #1).** EPIC-SPLIT homes `contracts.py`'s envelope on
   E4, but the leaf/app boundary means c1-8's identity probe cannot see a health model defined under
   `app/`. This story creates the file with `HealthResponse` only. The alternative — define it under
   `app/` and have the leaf parse raw JSON in c1-8 — costs a duplicated shape. Confirm the
   early-create is the one you want.
2. **`/docs` and `/openapi.json` left at FastAPI defaults.** Nothing requires them (c2-3 calls
   `app.openapi()` in-process), and nothing forbids them on a localhost-only app. Left enabled as a
   non-decision; worth a second look when c1-5 draws the security envelope.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Amelia, bmad-dev-story)

### Debug Log References

**Task 0 — state verification.** Branch `feat/companion-c1-2-asgi-app-lifespan-health` created off
`feat/companion-app` at `ce13f5f`. `src/companion/__init__.py` and `src/companion/app/__init__.py`
confirmed present and docstring-only; `src/companion/contracts.py` confirmed absent.
`uv run python -c "import fastapi"` → `ModuleNotFoundError: No module named 'fastapi'` (expected —
this story installs it). **Baseline deviation:** the suite baselined at **1,360 passed, 45
deselected**, not the 1,359 the story notes predicted. One extra test exists on
`feat/companion-app` versus the count recorded when the story was written; no failures either way,
so the delta is recorded rather than chased. All later counts are measured against 1,360.
*(Identified in review: the +1 is c1-1's final review commit `57b19c9` — the dml-star-import
negative test — which landed after these notes were written; its own commit message records the
same "1360 passed, 45 deselected".)*

**Task 1 — dependency resolution.** `uv add` resolved `fastapi==0.140.0` (the `>=0.139.2` floor)
and `uvicorn==0.51.0`, which **replaced an existing transitive `uvicorn==0.37.0`** pulled in by
`mcp` — the first-party `>=0.51.0` floor now governs it. Six new packages entered `uv.lock`
(`annotated-doc`, `fastapi`, `httptools`, `uvloop`, `watchfiles`, `websockets` — review corrected
`uvloop` here: `uvicorn` was not *new*, it was the pre-existing transitive entry upgraded as just
described); the full suite was re-run afterwards specifically to cover that transitive change.

**Red-green evidence.** Both cycles were driven test-first and observed failing:
- Task 2 RED: `ModuleNotFoundError: No module named 'src.companion.contracts'` (collection error).
- Tasks 4/5 RED: `ImportError while loading conftest … No module named 'src.companion.app.main'`.

**Mutation check on the AC-2 inertness test** (it must still bite years from now, so it was proven
to bite today). A temporary `paths.data_dir()` call was inserted into `build_app()`:

```
FAILED tests/unit/companion/test_app.py::TestConstructionIsInert::test_import_and_construction_create_no_directory
E   AssertionError: build_app() (or importing main) resolved a data path — data_dir() mkdirs, so
    the companion would create state on a fresh install before the UI could report it (AD-10)
E   assert not True +  where True = exists() … 'never-created'.exists
```

The mutation was reverted immediately; the final tree contains no such call.

**Fresh-import hazard found while writing the AC-2 test.** `conftest.py` imports
`src.companion.app.main` at module level, so by the time the inertness test runs the module is
already cached — a plain `import` inside the test would prove nothing about *import-time* side
effects. `importlib.reload` was rejected: it swaps the `sys.modules` entry for a new module object
permanently, which would silently break `TestShutdown`'s `monkeypatch.setattr(main, "_shutdown", …)`
(conftest's `lifespan` closes over the *old* module globals) in an order-dependent way. The test
instead uses `monkeypatch.delitem(sys.modules, …)` over the `src.companion.app*` entries before
re-importing, so the fresh import is real **and** monkeypatch restores the original modules at
teardown. Recorded because c1-3…c1-9 inherit this conftest and will hit the same hazard.

**Gate outputs** — pasted verbatim per the standing epic-5/6 verification agreement:

```
> uv run ruff check .
All checks passed!

> uv run ruff format --check .
256 files already formatted

> uv run mypy src/
Success: no issues found in 76 source files

> uv run pytest -m "not integration" -q
1372 passed, 45 deselected in 64.47s (0:01:04)
```

`uv run ruff format .` reformatted one file en route (`tests/unit/companion/test_app.py`, a
101-char assertion message); the check above is the post-format state.

### Completion Notes List

- **AC 1 — inert construction.** `build_app()` constructs `FastAPI(title=…, lifespan=lifespan)` and
  includes the health router; nothing else. Neither `main.py` nor `routes/health.py` imports
  `src.paths` at all, so the `data_dir()` mkdir landmine cannot fire on the construction path.
- **AC 2 — proven, not asserted.** Three tests: a non-existent `PLANESWALKER_DATA_DIR` under
  `tmp_path` survives a fresh import + `build_app()` **and** `tmp_path` gains no entries;
  `socket.socket.bind` monkeypatched to raise, then `build_app()`; and `app.state` carries no
  `instance_id` after construction. The first was mutation-tested (see Debug Log).
- **AC 3 — identity in the lifespan.** `app.state.instance_id = str(uuid.uuid4())` on startup only.
  Covered by: parses as a UUID, identical across two requests in one lifespan and equal to
  `app.state.instance_id`, and different between two separate `build_app()` + lifespan entries.
- **AC 4 — `/health`.** `@router.get("/health", response_model=HealthResponse)`, unauthenticated,
  returns `200` with `{status, instance_id}`. The test sends no auth header and validates the body
  through `HealthResponse.model_validate`.
- **AC 5 — the model lives in the leaf.** `src/companion/contracts.py` contains `HealthResponse`
  and nothing else, importing only `typing.Literal` and `pydantic.BaseModel`. Its docstring names
  the AD-3 constraint so c4's envelope lands beside it under the same rule.
- **AC 6 — clean shutdown.** `try: yield finally:` wrapping `await _shutdown(app)` in
  `try/except Exception` + `logger.exception`. `_shutdown` is a module-level **async** helper (it is
  a no-op that logs today) precisely so c1-6's `await engine.dispose()` and c1-7's discovery-file
  removal drop into an already-correct, already-tested teardown. Two tests: teardown runs on clean
  exit, and a raising teardown neither propagates nor goes unlogged (`caplog`).
- **AC 7 — in-process seam.** `tests/unit/companion/conftest.py` exposes `lifespan_client` as a
  **fixture returning the context-manager factory**, so later stories reach the seam without
  depending on the conftest module's import path. No new dependency: no `asgi-lifespan`, no
  `TestClient`. Its docstring states why it exists (`ASGITransport` runs no lifespan events) and
  restates the `app.state`-not-yielded-dict consequence.
- **AC 8 — construction-site enumeration for one dependency, three declaration sites + mirror.**
  (1) `pyproject.toml` `[project].dependencies` via `uv add`, never hand-edited; (2) `uv.lock`
  regenerated by that same command; (3) `.pre-commit-config.yaml` mypy `additional_dependencies`
  gained `fastapi>=0.139.2` (uvicorn deliberately **not** added — no `src/` module imports it yet;
  c1-3 owns that); (4) the plugin mirror re-derived both `plugin/server/pyproject.toml` and
  `plugin/server/uv.lock`, verified by grep for each name.
- **AC 9 — guards satisfied unmodified.** `tests/unit/companion/test_import_boundary.py` was not
  edited (`git diff --stat` empty). `contracts.py` is now scanned as a leaf for the first time and
  passes; it was written and run against the leaf guard *before* `main.py` existed, per the story's
  sequencing. `src/companion/app/__init__.py` is byte-identical — no `build_app` re-export. All 50
  guard tests green throughout.
- **AC 10 — no new failures.** 1,372 passed = the 1,360 baseline + 12 new tests, 45 deselected.
- **AC 11 — plugin mirror.** Rebuilt with `uv run python -m scripts.build_plugin` and committed;
  `git status --porcelain -- plugin/` verified clean after the commit, which is exactly the CI
  *"Plugin tree in sync with src/"* check.
- **AC 12 — scope held.** No port bind, no `uvicorn.run`, no CLI wiring, no discovery file, no
  middleware/CORS/token/ticket, no engine or `deps.py`, no error contract, no second route, no
  `ui/`, no `integration`-marked test. `.github/workflows/ci.yml` untouched.
- **Open question 1 (`contracts.py` created here) stands as implemented** per Decide-once #1 — the
  file exists with `HealthResponse` only, leaving the c4 envelope to land beside it. Open question 2
  (`/docs`, `/openapi.json` at FastAPI defaults) was left as a non-decision, unchanged; it is
  reachable on the localhost-only app and worth revisiting when c1-5 draws the security envelope.

### File List

**New**

- `src/companion/contracts.py`
- `src/companion/app/main.py`
- `src/companion/app/routes/__init__.py`
- `src/companion/app/routes/health.py`
- `tests/unit/companion/conftest.py`
- `tests/unit/companion/test_app.py`

**Modified**

- `pyproject.toml` — `fastapi>=0.139.2`, `uvicorn[standard]>=0.51.0` added via `uv add`
- `uv.lock` — regenerated
- `.pre-commit-config.yaml` — `fastapi>=0.139.2` added to the mypy hook's `additional_dependencies`
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — c1-2 status transitions

**Generated (committed mirror)**

- `plugin/server/pyproject.toml`, `plugin/server/uv.lock`
- `plugin/server/src/companion/contracts.py`
- `plugin/server/src/companion/app/main.py`
- `plugin/server/src/companion/app/routes/__init__.py`, `plugin/server/src/companion/app/routes/health.py`

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-25 | Story c1-2 created from epics Story 1.2 + AD-3/4/10/12/16, with c1-1's guard surface as the acceptance constraint. Status → ready-for-dev. |
| 2026-07-25 | Implemented: `HealthResponse` leaf contract, side-effect-free `build_app()`, module-level lifespan minting `instance_id` with a swallow-and-log teardown, unauthenticated `GET /health`, and the shared `lifespan_client` in-process test seam. FastAPI + uvicorn added across all three declaration sites; plugin mirror rebuilt. 12 new tests; 1,372 passed / 45 deselected; ruff + mypy clean. Status → review. |
| 2026-07-25 | Code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor): Accept — no AC violations. 10 patches applied (test hardening: fresh-import socket test, widened `_fresh_main` eviction, startup-propagation test, direct log-record assertion; `/health` docstring precision; 5 record corrections incl. the Gotcha 6 `--ignore-missing-imports` fix), 2 deferred (seam kwargs → c1-5; mypy-hook version drift, pre-existing), 4 dismissed. 1,373 passed / 45 deselected; all gates green; mirror rebuilt. Status → done. |

---
baseline_commit: 4a5695c
epic: c1
story: c1-4
work_branch: feat/companion-app
story_branch: feat/companion-c1-4-typed-rest-error-contract
---

# Story C1.4: Typed REST error contract with closed reason tokens

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a UI developer,
I want every non-2xx response to carry one token from a closed set,
so that each backend failure maps 1:1 onto a defined user-facing state instead of a guess.

**Why this story is fourth.** c1-2 gave the app a body, c1-3 gave it a port. This story gives it a
**vocabulary of failure** — and it is the last purely-additive story before the consumers arrive:
c1-5 rejects a bad `Host` with `invalid_request`, c1-6 answers a missing database with
`database_not_initialized`, c3-1 answers a deleted deck with `deck_not_found`, c3-2 *extends* the
set with `card_not_found`, and c5-5 rejects an over-cap push with `payload_too_large`. Five stories
raise into this module; none of them may invent a shape. Epic 2 then generates the TypeScript from
it (`openapi-typescript` "stands itself up against the endpoints that exist after Epic 1 —
`/health` + the typed error body"), so if the error model is not in `app.openapi()` when this story
ends, c2-3 has nothing to generate and the UI's state-panel switch has no types to switch on.

## Acceptance Criteria

1. **The reason token type is a closed set of exactly five (AD-16).** `src/companion/contracts.py`
   gains

   ```python
   ErrorReason = Literal[
       "deck_not_found",
       "database_not_initialized",
       "database_unavailable",
       "invalid_request",
       "payload_too_large",
   ]
   ```

   It lives in the **leaf**, next to `HealthResponse`, so the MCP-side client (c6-1) and the
   OpenAPI→TypeScript generator (c2-3) read one definition. A test asserts
   `set(get_args(ErrorReason))` equals that five-member set **exactly**, so adding a sixth token is
   a deliberate act with a failing test attached. c3-2 adds `card_not_found` under AD-16's own
   extension rule ("adding a UI state means adding a token here first"); nothing else may.

2. **One typed error body, carrying nothing but the token.** `ErrorResponse(BaseModel)` in the same
   leaf module, with the single field `reason: ErrorReason`. **No `message`, no `detail`, no
   `status`** — see Decide-once #3. The serialised body is exactly `{"reason": "<token>"}`, pinned
   by a test asserting the JSON keys are `{"reason"}` and nothing more.

3. **The status code is derived from the token, never chosen at the call site.**
   `src/companion/app/errors.py` holds the single mapping

   | reason | status |
   | --- | --- |
   | `deck_not_found` | 404 |
   | `database_not_initialized` | 503 |
   | `database_unavailable` | 503 |
   | `invalid_request` | 400 |
   | `payload_too_large` | 422 |

   as `STATUS_BY_REASON: dict[ErrorReason, int]`, and it is the **only** place in the codebase a
   status is paired with a token. An enumeration-pin test asserts
   `set(STATUS_BY_REASON) == set(get_args(ErrorReason))` — a future token with no status fails
   rather than defaulting.

4. **Endpoints raise; they never hand-build a response.** `CompanionError(Exception)` carries a
   `reason: ErrorReason`; a registered handler converts it to the typed body at its mapped status.
   Nothing in `src/` raises it yet — c1-5, c1-6, c3-1 and c5-5 are the first callers — so this
   story ships the mechanism and proves it through **test-only routes attached to a real
   `build_app()` instance** (AC 11). No debug/boom route ships in `src/`.

5. **Framework failures are typed too — including the ones FastAPI answers by default.**
   - `RequestValidationError` → **400 `invalid_request`**, replacing FastAPI's default
     `422 {"detail": [...]}`. 422 is reserved for `payload_too_large` by AD-16, and the default
     body is a second error shape the UI would have to parse. The validation detail goes to the
     **log**, never to the client (it echoes caller input — see Decide-once #3).
   - `StarletteHTTPException` (an unknown path's 404, a 405, and any `HTTPException` a later story
     raises) → the typed body with the **status preserved**, reason `invalid_request` for 4xx and
     `database_unavailable` for 5xx. Registering on the **Starlette** class also covers
     `fastapi.HTTPException`, which subclasses it.

6. **An unhandled exception yields a typed `503 database_unavailable`, logged, never a traceback.**
   Implemented as a pure-ASGI `UnhandledErrorMiddleware` in `errors.py` — **not**
   `add_exception_handler(Exception, …)`, which Starlette always re-raises from (Decide-once #1,
   with verified evidence). The exception is logged once with `logger.exception(...)` using
   `%`-style lazy args, which reaches **stderr** through `logging.lastResort` even though no story
   has configured a root logger yet (Gotcha 7). If the response has already started, the middleware
   re-raises rather than sending a second response. `except Exception` — never `BaseException`, so
   `CancelledError` still propagates.

7. **The error middleware is the outermost application middleware.** `app.user_middleware[0]` is
   the last-added one (verified), so `install_error_handling(app)` is called **last** in
   `build_app()` and a test pins `app.user_middleware[0].cls is UnhandledErrorMiddleware`. This is
   what makes c1-5's `Host` middleware fail *typed* if it ever raises, and the pin is the thing
   that tells c1-5 where to insert itself.

8. **The error body is in `app.openapi()` from this commit (AD-12, NFR-03).** `build_app()` passes
   app-level `responses=error_responses("invalid_request", "payload_too_large",
   "database_unavailable")`, where `error_responses(*reasons)` is a helper in `errors.py` that maps
   tokens to `{status: {"model": ErrorResponse, …}}` through `STATUS_BY_REASON` (one construction
   site; c3-1/c3-2 reuse it per-route for `deck_not_found` / `card_not_found`). Two verified
   consequences, both asserted:
   - `ErrorResponse` appears in `schema["components"]["schemas"]`;
   - the explicit 422 **displaces** FastAPI's auto-generated `HTTPValidationError`, which AC 5
     makes permanently unreachable — `"HTTPValidationError" not in components` is the assertion
     that keeps a shape we never emit out of the generated TypeScript.

9. **Success bodies stay unwrapped, and the MCP `status`-envelope never crosses into REST
   (AD-16).** A test walks `build_app().openapi()` and asserts that for every path/method, every
   2xx response whose content includes `application/json` has a schema that is a **`$ref` to a
   component** — never an inline object. That bans `{"status": "ok", "deck": {…}}` structurally
   while leaving c3-5's binary image route (which declares `image/*`, not JSON) free. `/health`'s
   body keys stay exactly `{status, instance_id}` — `HealthResponse.status` is a **field of the
   health resource**, not an envelope, as its docstring already records.

10. **c1-2's and c1-3's regression surfaces stay green, untouched.** `build_app()` remains inert
    (AD-10): registering handlers and middleware is pure in-process construction — no port, no
    file, no directory, no engine. `tests/unit/companion/test_app.py` and
    `tests/unit/companion/test_server.py` are **not edited**, and
    `TestConstructionIsInert` + `test_openapi_carries_the_health_contract` pass unmodified.

11. **Tests drive the real app through the real stack.** `tests/unit/companion/test_errors.py`,
    unmarked unit tests, using the existing `lifespan_client` fixture. Every response assertion
    goes through a `build_app()` instance with **test-local routes attached in the test**
    (`@app.get("/_boom")` etc. added to that instance before the first request) — so the middleware
    order, the handler registration and the JSON serialisation are all exercised as shipped. Cover:
    each of the five tokens through `CompanionError`; a validation failure; an unknown path; a 405;
    an unhandled `RuntimeError` (body **and** the logged record: level `ERROR`, `exc_info` set,
    logger name `src.companion.app.errors` — c1-2's `caplog` pattern); and that the raised
    exception does **not** escape to the client.

12. **Quality gates green (NFR-07).** `uv run ruff check .`, `uv run ruff format --check .`,
    `uv run mypy src/` and `uv run pytest -m "not integration"` all pass with **no new failures**
    against the **1,405 passed / 45 deselected** baseline (verified at `4a5695c` on 2026-07-25).
    Actual output pasted into the Debug Log.

13. **Plugin mirror rebuilt and committed.** `uv run python -m scripts.build_plugin`, then commit
    `plugin/`; `git status --porcelain -- plugin/` clean afterwards.

14. **Scope boundary — what this story must NOT do.** No `Host` middleware, no CORS (c1-5). No
    database engine, no `deps.py`, no `database_not_initialized` **raise site** (c1-6) — only the
    token and its wiring. No discovery file (c1-7), no single-instance check (c1-8), no CLI (c1-9).
    No deck/card routes and no `card_not_found` (c3-1, c3-2). No payload caps and no
    `/agent/events` (c5-5). No root-logger configuration (c1-9 owns it — Gotcha 7). No new
    dependency, no `pyproject.toml` / `uv.lock` / `.pre-commit-config.yaml` change. No edit to
    `tests/unit/companion/test_app.py`, `test_server.py`, `test_import_boundary.py` or
    `.github/workflows/ci.yml`.

## Tasks / Subtasks

- [x] **Task 0 — State verification** (standing team agreement since the epic-6 retro: any story
      whose notes assert repository state opens with the cheap check that proves it)
  - [x] Create `feat/companion-c1-4-typed-rest-error-contract` **off `feat/companion-app`**
        (currently at `4a5695c`); the story PR targets `feat/companion-app`.
  - [x] Confirm `src/companion/app/errors.py` and `tests/unit/companion/test_errors.py` do **not**
        exist, and that `src/companion/contracts.py` contains `HealthResponse` and nothing else.
  - [x] Baseline the suite: `uv run pytest -m "not integration" -q` → expected **1,405 passed, 45
        deselected**. Record any delta rather than chasing it.

- [x] **Task 1 — The leaf contract** (AC: 1, 2)
  - [x] `src/companion/contracts.py` — add `ErrorReason` (the five-member `Literal`) and
        `ErrorResponse` with the single `reason` field. Google docstrings; the class docstring must
        state *why* there is no message field (Decide-once #3) and name the five UX states each
        token maps to, because this docstring is what c2-9's panel copy and c6-1's client read.
  - [x] Keep the module's leaf discipline: `typing` + `pydantic` only. No `fastapi`, no
        `status`-code constants (those are the app's business, AC 3).

- [x] **Task 2 — The app-side machinery** (AC: 3, 4, 5, 6, 8)
  - [x] `src/companion/app/errors.py` — module docstring covering: status is derived from the
        token; the unhandled path is middleware **because** the `Exception` handler re-raises
        (Decide-once #1); and the body never carries prose (Decide-once #3). Module-level
        `logger = logging.getLogger(__name__)`.
  - [x] `STATUS_BY_REASON: dict[ErrorReason, int]` per AC 3, plus
        `error_response(reason, *, status=None) -> JSONResponse` (status defaults to the mapping;
        the override exists solely for AC 5's status-preserving `HTTPException` path) and
        `error_responses(*reasons) -> dict[int | str, dict[str, Any]]` for OpenAPI declaration.
  - [x] `CompanionError(Exception)` — `__init__(self, reason: ErrorReason)` calls `super().__init__`
        with the reason so the string form is useful in a log, and stores `self.reason`.
  - [x] Three handlers, each annotated `(request: Request, exc: Exception) -> JSONResponse` —
        **not** the narrow exception type (Gotcha 2, verified mypy failure) — narrowing with
        `if not isinstance(exc, X): raise exc` before use:
        `companion_error_handler`, `validation_error_handler` (logs the validation detail at
        `warning`, returns `invalid_request`), `http_exception_handler` (status preserved; reason
        by 4xx/5xx).
  - [x] `UnhandledErrorMiddleware` — pure ASGI class (`__init__(self, app: ASGIApp)`,
        `async def __call__(self, scope, receive, send)`): pass non-`http` scopes straight through,
        track `http.response.start` via a wrapped `send`, catch `Exception`, `logger.exception`
        with `%`-style args, re-raise if the response already started, else send
        `error_response("database_unavailable")`.
  - [x] `install_error_handling(app: FastAPI) -> None` — registers the three handlers (on
        `CompanionError`, `RequestValidationError` and **`starlette.exceptions.HTTPException`**)
        and adds the middleware. One function so c1-5/c1-6 wire nothing new.

- [x] **Task 3 — Wire it into the app** (AC: 7, 8, 9, 10)
  - [x] `src/companion/app/main.py` — `build_app()` passes
        `responses=error_responses("invalid_request", "payload_too_large", "database_unavailable")`
        to `FastAPI(...)`, includes the health router as today, and calls `install_error_handling(app)`
        **last**, with a comment saying why last (AC 7) so c1-5 does not insert itself after it.
  - [x] Change nothing else in `main.py`: `lifespan`, `_shutdown`, `bound_port` and the inertness
        contract are untouched.

- [x] **Task 4 — Tests** (AC: 1–11)
  - [x] `tests/unit/companion/test_errors.py`, unmarked; a small helper that builds an app and
        attaches the test-only routes it needs, then drives it with `lifespan_client`.
  - [x] Contract: `get_args(ErrorReason)` is exactly the five tokens; `ErrorResponse` rejects an
        unknown token (`ValidationError`, mirroring c1-2's `test_status_is_a_closed_token`); the
        serialised body's keys are exactly `{"reason"}`.
  - [x] Mapping: `set(STATUS_BY_REASON) == set(get_args(ErrorReason))`; each token's status matches
        AC 3's table (parametrized, so the table is the test).
  - [x] Raise path: a route raising `CompanionError(token)` returns that status and
        `{"reason": token}` — parametrized over all five.
  - [x] Framework paths: `/_typed/{n}` with `n: int` called as `xx` → **400** `invalid_request`
        (explicitly assert it is *not* 422 and carries no `detail` key); unknown path → 404
        `invalid_request`; wrong method on `/health` → 405 `invalid_request`; a route raising
        `HTTPException(503)` → 503 `database_unavailable`.
  - [x] Unhandled path: a route raising `RuntimeError("kaboom")` → **503** `database_unavailable`;
        the exception does not escape the client call; exactly one `ERROR` record from
        `src.companion.app.errors` with `exc_info` set and `"kaboom"` in it.
  - [x] Structure pins: `app.user_middleware[0].cls is UnhandledErrorMiddleware`; `ErrorResponse` in
        `openapi()["components"]["schemas"]`; `"HTTPValidationError"` absent; every 2xx
        `application/json` schema is a `$ref` (assert the walk was **non-vacuous** — it must have
        visited at least `/health`'s 200; c1-1's dead-guard lesson).
  - [x] Inertness: constructing the app with the handlers installed still creates no directory —
        one cheap re-assertion here, without touching `test_app.py` (AC 10).

- [x] **Task 5 — Gates, mirror and scope** (AC: 12, 13, 14)
  - [x] `uv run ruff check . --fix` · `uv run ruff format .` · `uv run mypy src/` ·
        `uv run pytest -m "not integration"` — paste actual counts into the Debug Log.
  - [x] `uv run python -m scripts.build_plugin`, `git add plugin/`, verify
        `git status --porcelain -- plugin/` is clean after the commit.
  - [x] Confirm by command, not assertion, that the AC 14 forbidden files are untouched:
        `git status --porcelain -- tests/unit/companion/test_app.py tests/unit/companion/test_server.py tests/unit/companion/test_import_boundary.py .github/workflows/ci.yml pyproject.toml uv.lock .pre-commit-config.yaml`
        returns empty.

### Review Findings

Code review 2026-07-25 (Blind Hunter + Edge Case Hunter + Acceptance Auditor; diff
`4a5695c...4bc5b7a`). Auditor verdict: **all 14 ACs satisfied** — gates reproduced at the review
commit (1,443 passed / 45 deselected), mirror byte-identical, zero raise sites in `src/` confirmed,
forbidden-edit list untouched. 26 raw findings deduplicated to 16. The review also credits three
implementation catches: the shared-status grouping in `error_responses`, the verified
middleware-vs-`Exception`-handler ruling, and the mid-stream re-raise dead-guard test.

- [x] [Review][Decision] **Unhandled bugs → `internal_error` (500), RESOLVED (Brad, 2026-07-25).**
      The sixth token was added before Epic 2 freezes the TypeScript union: `ErrorReason` is now
      closed at six, `STATUS_BY_REASON["internal_error"] = 500`, the unhandled middleware and the
      5xx branch of `http_exception_handler` return it (a stray 5xx `HTTPException` is "us,
      unmodelled" — `database_unavailable` now strictly means the modelled transient-DB state),
      `build_app()` declares it app-wide, and the state panel is homed on Story 2.9 in the epics
      doc. Resolves the story's Open Question 1.
- [x] [Review][Decision] **`payload_too_large` → 413, RESOLVED (Brad, 2026-07-25).** Moved from
      422 to HTTP's native status in `STATUS_BY_REASON`, the test table, AD-16's spine table and
      the epics REST-semantics table + c5-5 references — all annotated with the ruling. 422 is now
      unused, and `invalid_request` (400) keeps semantic-validation failures.
- [x] [Review][Patch] `http_exception_handler` drops `exc.headers` — Starlette's route-miss 405
      carries `Allow` (RFC 9110 MUST) and its default handler forwards it; the typed replacement
      loses it, and any future `WWW-Authenticate`/`Retry-After` too. Also: a sub-400 or 204/304
      `HTTPException` (latent — nothing raises one today) would get an error body on a non-error
      or bodiless status. Forward headers; pass sub-400/204/304 through bodiless with status +
      headers preserved. [src/companion/app/errors.py:178-204] (Severity: Medium)
- [x] [Review][Patch] `ClientDisconnect` is an `Exception` subclass, so a client dropping mid-read
      would be ERROR-logged as an unhandled bug and answered into a dead stream — false-alarm
      ERRORs poison the log contract this story establishes (first reachable when c5-5 reads
      bodies). Carve it out: debug log + re-raise (identical to today's no-middleware behaviour).
      [src/companion/app/errors.py:243-256] (Severity: Low)
- [x] [Review][Patch] Mid-stream failures are logged twice — `logger.exception` fires before the
      `response_started` check, then the re-raise gets logged again by the outer net (uvicorn).
      Move the log into the not-started branch so every failure is logged exactly once, by exactly
      one layer. [src/companion/app/errors.py:245-254] (Severity: Low)
- [x] [Review][Patch] `CompanionError` accepts any string at runtime — mypy guards `src/` only, and
      a typo'd token from an un-typechecked call site surfaces as a `KeyError` inside the handler,
      masked by the middleware as a misleading `503 database_unavailable`. Validate in `__init__`
      (`ValueError` naming the bad token) + a test. [src/companion/app/errors.py:73-77] (Severity: Low)
- [x] [Review][Patch] `error_responses()` does not dedupe repeated tokens —
      `error_responses("invalid_request", "invalid_request")` ships "reason: invalid_request |
      invalid_request" into the OpenAPI description c2-3 generates docs from, and c3-1/c3-2/c5-5
      reuse this helper. `dict.fromkeys(reasons)`. [src/companion/app/errors.py:120-129] (Severity: Low)
- [x] [Review][Patch] AC 5's "the validation detail goes to the log" is asserted nowhere — the
      `logger.warning` with `exc.errors()` can be deleted without a red test (the claim-without-a-
      pin pattern c1-1's dead-guard lesson warns about). Add a `caplog` assertion to the validation
      test. [tests/unit/companion/test_errors.py — TestFrameworkFailures] (Severity: Low)
- [x] [Review][Patch] The AC 9 OpenAPI walk assumes every path-item value is an operation dict and
      every JSON content entry has a `schema` — a path-level `parameters` list or a schemaless
      content block turns the structural pin into an `AttributeError`/`KeyError` crash instead of a
      diagnostic failure. Skip non-dict values; assert `schema` presence with a message.
      [tests/unit/companion/test_errors.py:298-310] (Severity: Low)
- [x] [Review][Patch] The non-http passthrough test hands the middleware `None` for
      `receive`/`send` — the test itself violates the ASGI contract, and any future middleware
      change touching those channels on non-http scopes fails with `TypeError` instead of a
      readable assertion. Pass proper async stubs. [tests/unit/companion/test_errors.py:252-261] (Severity: Low)
- [x] [Review][Patch] Debug Log stale figures — "tests/unit/companion/ is 131 green" (actual at the
      review commit: 133; the figure predates the two extra ASGI dead-guard tests) and "265 files
      already formatted" (actual: 266; the paste predates the plugin rebuild). [story Debug Log] (Severity: Low)
- [x] [Review][Defer] The outermost error middleware means c1-5's future CORS middleware (inner,
      per the install-last pin) never stamps headers onto an unhandled-503 — a cross-origin caller
      would see an opaque network error for exactly the failure class this story types. The
      ordering trade (typed failures *of* the security middleware vs CORS-visible unhandled
      errors) is real and only c1-5 can weigh it with the actual CORS scope in hand.
      [src/companion/app/main.py:120-124] — deferred to c1-5

Dismissed as noise (4): double-`install_error_handling` idempotence guard (speculative — one call
site, and c1-5/c1-6 are told to wire nothing); the "weak" inertness re-assertion (it is exactly the
cheap re-assertion the spec's Task 4 prescribed, and the strong fresh-import inertness coverage in
`test_app.py` now traverses `errors.py` via the import chain anyway); decorative doctest examples
(project-wide Google-docstring convention; no `--doctest-modules` runner is configured anywhere);
the app-wide 422 on `/health` documenting an impossible response (the story's Open Question 2,
explicitly ruled "displace globally" with the trade acknowledged).

## Dev Notes

### Decide-once rulings (made here so five later stories inherit them)

**#1 — The unhandled-exception path is middleware, not `add_exception_handler(Exception, …)`.
Verified, not assumed.** `.venv/Lib/site-packages/starlette/middleware/errors.py:151-185`:

```python
try:
    await self.app(scope, receive, _send)
except Exception as exc:
    ...
    if not response_started:
        await response(scope, receive, send)
    # We always continue to raise the exception.
    raise exc
```

Probed against the installed FastAPI 0.140.0 / Starlette 0.48.0: with a `500` handler registered,
a route raising `RuntimeError` through `httpx.ASGITransport` gives the caller
`RuntimeError: kaboom`, **not** a response — the body is written to the transport and then the
exception is re-raised through it. Two consequences: the AC 6 test could not assert on a body at
all, and under uvicorn the re-raise is what produces the traceback AD-16 forbids reaching the
client. A pure-ASGI middleware sits *inside* `ServerErrorMiddleware` and *outside*
`ExceptionMiddleware`, catches the same exceptions, and returns without re-raising. Same probe with
the middleware: `503 {"reason":"database_unavailable"}` plus the traceback on stderr from our own
`logger.exception`. `ServerErrorMiddleware` remains the outermost net for anything our middleware
itself fails on — that is defence in depth, not the contract.

**#2 — `reason` is a `Literal`, not a `StrEnum`.** It matches `HealthResponse.status`
(`Literal["ok"]`), it generates a plain TypeScript string union from `openapi-typescript`, and
`get_args()` makes the closed set testable in one line. A `StrEnum` would additionally require
every raise site to import the enum; a bare string literal is what c1-5/c1-6/c3-1 will actually
write, and mypy checks it at the call site either way.

**#3 — The error body carries the token and nothing else.** No `message`, no `detail`, no
`errors[]`. Three reasons, in order of weight: (a) **the copy lives in the UI** — EXPERIENCE.md
fixes the verbatim wording of every state panel ("Card database is updating." / "Reads will resume
automatically — nothing to do here.") and UX-DR33 bans "something went wrong"; a server-side prose
field would become a second source of user-facing copy that no UX review covers; (b) **it would
leak input back** — FastAPI's validation detail echoes the offending value, and the companion is
one `fetch` away from any page in the browser; (c) the token *is* the contract — AD-16's whole
point is a 1:1 token→state map, and anything a human needs beyond that belongs in the log, which
this story writes. If a later story genuinely needs machine-readable specifics (a field name, a
byte count), it adds a **typed** optional field with a UX consumer, not a free-text bucket.

**#4 — Framework misses keep their status; defined failures derive theirs.** A `CompanionError`
is a *modelled* outcome, so its status comes from `STATUS_BY_REASON` and the 1:1 table holds
exactly. A route-miss 404, a 405, or a stray `HTTPException` is not a modelled UX state — there is
no token for "you asked for a path that does not exist" and inventing one would breach AC 1. Those
keep their own status and carry `invalid_request` (4xx) or `database_unavailable` (5xx), so the
body is always parseable. The 1:1 property that matters is **token → UX state**, and it is
preserved: nothing in the SPA keys off "404" alone, it keys off `reason`.

### Architecture rules this story implements

- **AD-16** — the whole story. Closed snake_case tokens, HTTP-native status codes, unwrapped
  success bodies, and the MCP `status`-envelope stopping at the MCP boundary. AC 9 turns the last
  of those from a convention into a test.
- **AD-12 / NFR-03** — `contracts.py` is the single source of truth and the TS is generated from
  `app.openapi()`. AC 8 is what makes c2-3 possible; without the app-level `responses`, a Pydantic
  model no route references never enters `components.schemas`, and the generator emits nothing.
- **AD-10** — construction stays inert. Handlers and middleware are in-process objects; this story
  adds no external effect at all, which is why it needs no lifespan work.
- **AD-3** — `ErrorReason`/`ErrorResponse` in the leaf (importable by `src/mcp_server` for c6-1's
  outcome mapping); every `fastapi`/`starlette` import stays under `app/`.

### Source tree — what exists, what this story adds

```text
src/
  companion/
    contracts.py               # UPDATE — add ErrorReason + ErrorResponse (leaf: typing + pydantic only)
    app/
      main.py                  # UPDATE — responses= on FastAPI(...) + install_error_handling(app) last
      errors.py                # NEW — STATUS_BY_REASON, CompanionError, handlers, middleware
      server.py                # EXISTS — untouched
      routes/health.py         # EXISTS — untouched
tests/
  unit/companion/
    conftest.py                # EXISTS — lifespan_client; reused, not edited
    test_errors.py             # NEW
    test_app.py                # EXISTS — NOT edited (AC 10, 14)
    test_server.py             # EXISTS — NOT edited
    test_import_boundary.py    # EXISTS — NOT edited
```

**Current state of the files being modified** (read before editing):

- `src/companion/contracts.py` — module docstring stating the leaf rule (only stdlib, `pydantic`,
  `httpx`, `src.paths`, sibling leaves — *not even under `if TYPE_CHECKING:`*), then
  `from typing import Literal`, `from pydantic import BaseModel`, and `HealthResponse`
  (`status: Literal["ok"]`, `instance_id: str`). **What must be preserved:** the leaf import
  surface, and `HealthResponse.status` as-is — its docstring already explains why a *field* called
  `status` is not the banned envelope, and AC 9 depends on that distinction holding.
- `src/companion/app/main.py` — `_TITLE`, `async _shutdown(app)`, `@asynccontextmanager lifespan`
  (mints `app.state.instance_id`, `try/yield/finally` with swallow-and-log teardown),
  `bound_port(app)` (c1-3), and `build_app()` = `FastAPI(title=_TITLE, lifespan=lifespan)` +
  `include_router(health.router)`. **What must be preserved:** no module-level side effect and no
  `src.paths` import — `test_app.py::TestConstructionIsInert` fresh-imports this module with
  `socket.socket.bind` monkeypatched to raise and with `PLANESWALKER_DATA_DIR` pointed at a
  non-existent directory. Importing `errors.py` (which imports fastapi/starlette, already on the
  chain) is safe; importing anything that resolves a path is not.

**Deviation from the spine's Structural Seed, stated deliberately** (same shape as c1-3's
`server.py`): the seed lists `main.py`, `deps.py`, `state.py`, `security.py`, `routes/`, `ws.py`,
`images.py`, `static/` and names no error module. `errors.py` is an addition, not a contradiction —
five later stories import it, and folding it into `main.py` would put the exception vocabulary
behind the one module whose defining property is that it does nothing.

### Gotchas specific to this story

1. **`add_exception_handler(Exception, …)` always re-raises** — Decide-once #1. If you find
   yourself registering a 500 handler, the AC 6 test will fail with the original exception.

2. **A narrow `exc` annotation fails `mypy --strict`.** Verified:

   ```text
   error: Argument 2 to "add_exception_handler" of "Starlette" has incompatible type
   "Callable[[Request, CompanionError], Coroutine[Any, Any, JSONResponse]]"; expected
   "Callable[[Request, Exception], Response | Awaitable[Response]] | ..."  [arg-type]
   ```

   Annotate every handler `(request: Request, exc: Exception)` and narrow inside with
   `if not isinstance(exc, CompanionError): raise exc`. Do not `# type: ignore` it.

3. **FastAPI auto-documents a 422 `HTTPValidationError` on any route with validated params.**
   Since AC 5 makes that response unreachable, the schema would advertise a shape we never emit —
   straight into c2-3's generated TypeScript. Declaring 422 explicitly (AC 8) **replaces** it, and
   `HTTPValidationError`/`ValidationError` then vanish from `components.schemas` entirely
   (verified both ways against FastAPI 0.140.0).

4. **`app.user_middleware[0]` is the *last* middleware added** (verified: adding `B` then `A`
   yields `[A, B]`). Hence "install last" in AC 7. Related: `add_middleware` raises
   `RuntimeError` once the app has started, so all of this belongs in `build_app()`.

5. **Catch `Exception`, never `BaseException`.** `asyncio.CancelledError` is a `BaseException` on
   3.12 and swallowing it would break shutdown and client-disconnect handling.

6. **Never send twice.** If `http.response.start` already went out, the middleware must re-raise —
   a second `await response(scope, receive, send)` corrupts the ASGI stream.

7. **Nothing configures the root logger yet** (c1-3 Open Question 2, still open, owned by c1-9).
   Consequence, and it works *in our favour* here: `logging.lastResort` emits `WARNING`+ to
   **stderr**, so `logger.exception(...)` (ERROR) genuinely reaches stderr as AC 6 requires, while
   c1-2's `logger.info` lines are still dropped. Do **not** add `logging.basicConfig` to fix that —
   it is c1-9's call, and adding it here changes behaviour for every module at once.

8. **No boom route in `src/`.** Attach test routes to the `build_app()` instance inside the test
   (routes may be added after construction, before the first request). A shipped debug route would
   be a permanent unauthenticated 500 generator on a localhost port.

9. **`caplog` needs the right target.** Assert on `caplog.records` filtered to
   `record.name == "src.companion.app.errors"` with `levelno == logging.ERROR` and
   `exc_info is not None` — exactly c1-2's
   `test_failing_teardown_is_logged_and_swallowed` pattern. Asserting on `caplog.text` alone
   passes for the wrong reasons.

10. **`httpx.ASGITransport` propagates exceptions to the caller** (that is how Decide-once #1 was
    caught). A test that expects a response but gets a raised error is telling you the middleware
    is missing or mis-ordered, not that the test is wrong.

11. **Register the handler on `starlette.exceptions.HTTPException`,** not `fastapi.HTTPException`.
    FastAPI's subclasses Starlette's and installs its own default handler on the Starlette class;
    registering there overrides it and covers both.

12. **The write guard scans `app/` too.** Nothing here goes near a session, but keep the habit:
    `_SESSION_MUTATORS` fires on `add`/`delete`/`commit`/`flush` **on a session-shaped receiver**
    (`session`, `db`, `conn`, …). Name a local `db` and call `.add(...)` on it and the boundary
    test goes red.

13. **`_` -prefixed helpers stay private, public ones get Google docstrings** — `mypy --strict`
    requires full annotations on every function in `src/`, including the middleware's
    `__call__(self, scope: Scope, receive: Receive, send: Send) -> None` (import the ASGI types
    from `starlette.types`).

### Testing standards

- New tests live in `tests/unit/companion/test_errors.py` — unmarked, fast, no network, no server
  boot. `--strict-markers` is on: do not invent a marker.
- `asyncio_mode = "auto"` — write `async def test_…` directly; no `@pytest.mark.asyncio`.
- Reuse the `lifespan_client` fixture from `tests/unit/companion/conftest.py`. Do not build a
  second client seam and do not add `asgi-lifespan` (c1-2 ruled against the dependency).
- **Verification before completion:** paste actual ruff / mypy / pytest output into the Debug Log.
  "Tests pass" without output is not acceptance — standing agreement from the epic-5/6 retros.
- Any structural scan (AC 9's OpenAPI walk) must assert its own **non-vacuity**: c1-1's dead-guard
  lesson, re-learned in c1-3's review where a per-directory non-vacuity assertion was added.
- Parametrize over `get_args(ErrorReason)` rather than a hand-copied list where the assertion is
  per-token — that way c3-2's `card_not_found` automatically inherits the coverage.

### Previous story intelligence (c1-3, done 2026-07-25, merged as PR #11)

- **The story-record → review → patch rhythm is established.** c1-3 took 29 raw review findings to
  16, applied 9 patches, deferred 2, dismissed 5. Expect the same treatment; write the record so a
  reviewer can verify claims by command.
- **Baseline discipline:** c1-2 found the recorded baseline off by one and *recorded the delta*
  rather than chasing it. The 1,405 figure above was re-measured at `4a5695c` for this story.
- **Gate-output homing** (open epic-7 action item): this story's rulings are homed as — #1 and #4
  on **c1-5** (its `Host` rejection is the first `invalid_request` producer, and it must know the
  middleware-order pin), #2 and #3 on **c2-3 / c2-9** (generated types and panel copy), the
  `error_responses(...)` helper on **c3-1 / c3-2 / c5-5** (per-route declaration).
- **Construction-site enumeration** (standing agreement): the concept here is *the reason token*
  and its sites are exactly four — the `Literal`, `STATUS_BY_REASON`, the OpenAPI `responses`
  declaration, and the raise sites (**deliberately zero in `src/` today**). AC 3's enumeration pin
  and AC 8's schema assertions keep the first three from drifting apart.
- **Deferred items already homed on c1-5, not on this story:** `SO_EXCLUSIVEADDRUSE` on the Windows
  bind, and `free_port()`'s TOCTOU in `test_server.py` (act on first flake). See
  `_bmad-output/implementation-artifacts/deferred-work.md`.
- **The mypy-hook `additional_dependencies` floor-vs-lock drift is a known, ruled-on deferral**
  (Brad, 2026-07-25: leave deferred — CI's `uv sync --locked` + `mypy src/` is the authoritative
  gate). This story adds **no** dependency, so it neither extends nor resolves that item.

### Git intelligence

`HEAD = 4a5695c` on `feat/companion-app` (PR #11 merge plus a docs-only commit to
`deferred-work.md`). The per-story pattern across c1-1 → c1-3 is: one focused
`feat(companion): …` commit implementing the story, review fixes as separate follow-up commits on
the same branch, then a PR into `feat/companion-app` (Greptile reviews per story).

Suggested commit: `feat(companion): typed REST error contract with closed reason tokens`.

### Latest technical information

Verified in this environment on 2026-07-25 (`uv run python -c "import fastapi, pydantic, starlette"`):
**FastAPI 0.140.0 · Starlette 0.48.0 · pydantic 2.12.0 · uvicorn 0.51.0** — all at or above the
spine's floors; no upgrade is part of this story.

- `FastAPI(responses={...})` applies to **every** route and is the mechanism AC 8 relies on
  (verified: `ErrorResponse` lands in `components.schemas`, and `/health` gains `400/422/503`).
- An explicitly declared 422 **overrides** FastAPI's auto-generated validation response; with it
  declared app-wide, `HTTPValidationError` and `ValidationError` disappear from the schema
  (verified).
- `add_exception_handler` is untyped-narrow-hostile under `mypy --strict` (Gotcha 2) and is the
  correct registration API for non-500 handlers — those go through `ExceptionMiddleware` and do
  **not** re-raise (verified: `CompanionError` → `404 {"reason":"deck_not_found"}` through
  `ASGITransport`).
- Starlette's `ServerErrorMiddleware` is installed outermost by Starlette itself and always
  re-raises after writing its response (`starlette/middleware/errors.py:184-185`).
- Pure-ASGI middleware added via `app.add_middleware(SomeClass)` needs only
  `__init__(self, app)` + `async __call__(self, scope, receive, send)`; type it with
  `starlette.types.{ASGIApp, Scope, Receive, Send}`.
- AC 9's pin holds on today's app: `/health`'s 200 JSON schema is already
  `{"$ref": "#/components/schemas/HealthResponse"}` (verified against the real `build_app()`), so
  the walk has a non-vacuous case from the first commit.
- AC 11's approach works: a route decorated onto an app **after** `add_middleware` and before the
  first request is served normally (verified) — Starlette builds the middleware stack lazily on
  first call.

### Project Structure Notes

- `errors.py` lives under `src/companion/app/`, which the AD-3 enumeration pin classifies
  automatically — **no edit to `test_import_boundary.py` is needed**. If you find yourself wanting
  to edit that file, a file is in the wrong place. The `contracts.py` additions must keep the leaf
  import surface (`typing`, `pydantic`) or the leaf guard goes red.
- Pre-existing tracked files modified: `src/companion/contracts.py`, `src/companion/app/main.py`,
  `_bmad-output/implementation-artifacts/sprint-status.yaml`, and the generated `plugin/` mirror.
  **Not** `pyproject.toml`, `uv.lock` or `.pre-commit-config.yaml` — no new dependency exists.
- Docs nit worth a one-line fix if you are already in the file: `epics-companion-app.md:1559`
  refers to "the closed reason-token set from Story 1.5" when it means **Story 1.4** (this one).
  Optional, and outside AC 14's forbidden list.

### References

- [epics-companion-app.md — Story 1.4](_bmad-output/planning-artifacts/epics-companion-app.md#L984-L1010) — the source acceptance criteria · [Epic 1 framing](_bmad-output/planning-artifacts/epics-companion-app.md#L879-L886)
- [epics-companion-app.md — REST semantics](_bmad-output/planning-artifacts/epics-companion-app.md#L255-L264) — the token table incl. c3-2's `card_not_found` extension · [Epic 2 deviation #2](_bmad-output/planning-artifacts/epics-companion-app.md#L713-L716) — why the error body must be in OpenAPI at the end of Epic 1
- Consumers: [Story 1.5 — Host rejection](_bmad-output/planning-artifacts/epics-companion-app.md#L1027) · [Story 1.6 — DB tokens](_bmad-output/planning-artifacts/epics-companion-app.md#L1054-L1066) · [Story 3.1/3.2](_bmad-output/planning-artifacts/epics-companion-app.md#L1528-L1563) · [Story 5.5 — `payload_too_large`](_bmad-output/planning-artifacts/epics-companion-app.md#L2432) · [Story 2.9 — the state panels](_bmad-output/planning-artifacts/epics-companion-app.md#L1432-L1466)
- ARCHITECTURE-SPINE.md — [AD-16](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L329-L348) · [AD-12](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L272-L291) · [AD-10](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L227-L240) · [AD-3](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L114-L125) · [Consistency Conventions](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L349-L356)
- [EXPERIENCE.md — verbatim state-panel copy](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L57-L65) · [degradation table](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L112-L113) — what each token has to mean on screen
- [prd.md — FR-22](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L104) · [FR-11](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L139) · [NFR-03](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L162)
- [src/companion/contracts.py](src/companion/contracts.py) — the leaf this story extends · [src/companion/app/main.py](src/companion/app/main.py#L104-L114) — `build_app()`
- [tests/unit/companion/test_app.py](tests/unit/companion/test_app.py#L63-L101) — the inertness tests that must stay green · [#L178-L201](tests/unit/companion/test_app.py#L178-L201) — the `caplog` assertion pattern to copy · [conftest.py](tests/unit/companion/conftest.py) — `lifespan_client`
- [c1-3 story record](_bmad-output/implementation-artifacts/c1-3-port-selection-with-ephemeral-fallback-and-a-printed-launch-url.md) — the print-vs-log ruling, the no-root-logger finding, and the review rhythm · [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — what is already homed on c1-5
- [.venv/Lib/site-packages/starlette/middleware/errors.py](.venv/Lib/site-packages/starlette/middleware/errors.py#L151-L185) — "We always continue to raise the exception", verified
- [project-context.md](_bmad-output/project-context.md) — logging (`%`-style lazy args), ruff/mypy, Google docstrings

## Open questions for Brad

Neither blocks implementation.

1. **An unhandled bug is served as `503 database_unavailable`, i.e. the "Card database is updating"
   panel.** That is the only retry-shaped surface in a token set AC 1 closes at five, and the
   alternative — an untyped 500 — is banned outright. The honest alternative is a sixth token
   (`internal_error`, 500) plus a new state panel with EXPERIENCE.md copy, since AD-16 requires the
   token *and* the UI state to be added together. Worth deciding before Epic 2 writes the panels.
2. **The app-level `responses` declares 422 on every route** (including `/health`, which has no
   body to reject) purely so FastAPI's `HTTPValidationError` never enters the generated
   TypeScript. The alternative is per-route declaration and living with a documented-but-impossible
   422 shape in the schema. Current ruling: displace it globally.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the `bmad-dev-story` workflow.

### Debug Log References

**Task 0 — state verification** (branch `feat/companion-c1-4-typed-rest-error-contract` off
`feat/companion-app` @ `4a5695c`):

```text
$ Test-Path src/companion/app/errors.py          -> False
$ Test-Path tests/unit/companion/test_errors.py  -> False
src/companion/contracts.py: module docstring + HealthResponse only (read in full) ✓

$ uv run pytest -m "not integration" -q
==================== 1405 passed, 45 deselected in 54.66s =====================
```

Baseline matched the recorded 1,405 / 45 **exactly** — no delta to record.

**Red-phase evidence** (each task's tests were written and observed failing before the code):

```text
Task 1: ImportError: cannot import name 'ErrorReason' from 'src.companion.contracts'
Task 2: ModuleNotFoundError: No module named 'src.companion.app.errors'
Task 3: 15 failed, 21 passed   (every response assertion + all three schema pins red
        against an unwired build_app(); the 21 green ones were the pure-contract tests)
```

**Task 5 — gates (AC 12), actual output:**

```text
$ uv run ruff check . --fix
All checks passed!
$ uv run ruff format .
265 files left unchanged
$ uv run ruff check .
All checks passed!
$ uv run ruff format --check .
265 files already formatted   (review-corrected: 266 at the review commit — the paste predates
                               the plugin rebuild adding plugin/server/.../errors.py)

$ uv run mypy src/
Success: no issues found in 78 source files

$ uv run pytest -m "not integration" -q
==================== 1443 passed, 45 deselected in 50.25s =====================
```

1,443 − 1,405 = **38 new tests, zero regressions.** `tests/unit/companion/` is 133 green
*(review-corrected: the original paste said 131, captured before the two extra ASGI-level
dead-guard tests were added)*, including `test_app.py`, `test_server.py` and
`test_import_boundary.py` run unmodified (AC 10).

**Task 5 — scope check (AC 14), by command:**

```text
$ git status --porcelain -- tests/unit/companion/test_app.py tests/unit/companion/test_server.py \
    tests/unit/companion/test_import_boundary.py .github/workflows/ci.yml pyproject.toml \
    uv.lock .pre-commit-config.yaml
(empty)
```

**Task 5 — plugin mirror (AC 13):**

```text
$ uv run python -m scripts.build_plugin
... Plugin assembled at .../plugin (v0.4.0, 4 skills)
$ git status --porcelain -- plugin/      # after commit
(empty)
```

### Completion Notes List

- **All 14 ACs met.** Implemented exactly as specified; no AC required a deviation, and the story's
  four Decide-once rulings were implemented as written rather than re-litigated.
- **Two extra tests beyond AC 11's list, both closing dead guards.** AC 6 requires the middleware to
  re-raise once `http.response.start` has gone out (Gotcha 6) and to pass non-`http` scopes
  through, but neither branch is reachable from a route — an unexercised guard is exactly c1-1's
  dead-guard lesson. Both are driven at the ASGI level (`UnhandledErrorMiddleware(app)(scope, …)`
  directly): the first asserts the exception propagates **and** that only one message
  (`http.response.start`) ever reached `send`; the second asserts a `lifespan` scope reaches the
  inner app untouched. Every branch in the middleware is now covered.
- **`error_responses()` groups by status rather than comprehending over tokens.** The naive
  `{STATUS_BY_REASON[r]: {...} for r in reasons}` silently drops one of the two 503 tokens, since
  `database_not_initialized` and `database_unavailable` share a status. It now collects tokens per
  status and names each in the description, with a test pinning that (`test_two_tokens_sharing_a_
  status_collapse_into_one_documented_entry`). This is the helper c3-1 / c3-2 / c5-5 reuse, so the
  collision would have shipped into their generated docs, not just ours.
- **Verified in this environment, not assumed:** the app-level `responses` does put `ErrorResponse`
  into `components.schemas` **and** displaces `HTTPValidationError` (both asserted, and
  `ValidationError` is gone too); `user_middleware[0]` is the last-added middleware, so
  `install_error_handling(app)` last makes it outermost; routes decorated onto the app after
  `add_middleware` are served normally; and the narrow-`exc` mypy failure is real — every handler
  is `(request: Request, exc: Exception)` narrowing with `isinstance`, no `type: ignore` anywhere.
- **Nothing in `src/` raises `CompanionError` yet**, by design (AC 4). The construction-site
  enumeration for *the reason token* stands at four sites, three of them live: the `Literal`
  (`contracts.py`), `STATUS_BY_REASON` (`errors.py`), the OpenAPI `responses=` declaration
  (`main.py`), and raise sites — deliberately zero, first filled by c1-5.
- **Docs nit fixed while in the file** (explicitly sanctioned by the story notes, outside AC 14's
  forbidden list): `epics-companion-app.md:1559` said "the closed reason-token set from Story 1.5"
  where it means Story **1.4**.
- **Open questions for Brad are unchanged and still unblocking** — see that section. Question 1
  (an unhandled bug is served as the "Card database is updating" panel) is the one worth a ruling
  before Epic 2 writes the panels; the current behaviour is what shipped.

### File List

| File | Change |
| --- | --- |
| `src/companion/contracts.py` | MODIFIED — `ErrorReason` (five-member `Literal`) + `ErrorResponse` |
| `src/companion/app/errors.py` | NEW — `STATUS_BY_REASON`, `CompanionError`, `error_response`, `error_responses`, three handlers, `UnhandledErrorMiddleware`, `install_error_handling` |
| `src/companion/app/main.py` | MODIFIED — app-level `responses=` + `install_error_handling(app)` last |
| `tests/unit/companion/test_errors.py` | NEW — 38 tests |
| `plugin/server/src/companion/contracts.py` | REGENERATED — plugin mirror |
| `plugin/server/src/companion/app/errors.py` | REGENERATED — plugin mirror |
| `plugin/server/src/companion/app/main.py` | REGENERATED — plugin mirror |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | MODIFIED — c1-4 → in-progress → review |
| `_bmad-output/implementation-artifacts/c1-4-typed-rest-error-contract-with-closed-reason-tokens.md` | MODIFIED — this record |
| `_bmad-output/planning-artifacts/epics-companion-app.md` | MODIFIED — one-word fix: "Story 1.5" → "Story 1.4" at line 1559 |

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-25 | Story c1-4 created from epics Story 1.4 + AD-16/AD-12/AD-10, with the Starlette re-raise behaviour, the `mypy --strict` handler-signature failure, the app-level `responses` schema effect and the middleware ordering all verified against the installed FastAPI 0.140.0 / Starlette 0.48.0 rather than assumed. Baseline re-measured at `4a5695c`: 1,405 passed / 45 deselected. Status → ready-for-dev. |
| 2026-07-25 | Implemented all 14 ACs across Tasks 0–5. `ErrorReason`/`ErrorResponse` in the leaf; `errors.py` with the single status mapping, `CompanionError`, three `(request, exc: Exception)` handlers and the pure-ASGI `UnhandledErrorMiddleware`; `build_app()` declares the error body app-wide and installs the handling last. 38 new tests (1,405 → 1,443 passed, 45 deselected); ruff, `ruff format --check` and `mypy src/` all clean; plugin mirror rebuilt. Status → review. |
| 2026-07-25 | Code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor): all 14 ACs verified; 26 raw findings → 16 unique. **Two wire-contract rulings by Brad, applied before Epic 2 freezes the TS union:** `internal_error` (500) added as the sixth token (unhandled bugs + stray 5xx `HTTPException`s no longer masquerade as the retry-forever `database_unavailable`; panel homed on Story 2.9) and `payload_too_large` moved 422 → 413 — spine AD-16 table + epics tables annotated. 9 hardening patches: `http_exception_handler` forwards `exc.headers` (405 keeps RFC-mandated `Allow`) and passes sub-400/204/304 through bodiless; `ClientDisconnect` carved out of the unhandled path (debug + re-raise, no false-alarm ERROR); log-once ordering on mid-stream failures; `CompanionError` validates its token at runtime; `error_responses` dedupes; validation-detail log pinned by caplog; OpenAPI walk hardened; non-http test uses real ASGI channels; Debug Log figures corrected. 1 deferred (CORS-ordering tension → c1-5), 4 dismissed. 1,452 passed / 45 deselected; all gates green; mirror rebuilt. Status → done. |

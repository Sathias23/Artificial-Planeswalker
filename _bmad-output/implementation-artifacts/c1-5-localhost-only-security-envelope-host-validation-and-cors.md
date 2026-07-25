---
baseline_commit: 5779c80
epic: c1
story: c1-5
work_branch: feat/companion-app
story_branch: feat/companion-c1-5-localhost-security-envelope
---

# Story C1.5: Localhost-only security envelope — Host validation and CORS

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad running the companion beside a browser,
I want the backend to refuse requests that did not address it as localhost,
so that a malicious web page I happen to have open cannot reach into the app through DNS rebinding.

**Why this story is fifth.** c1-3 bound the socket to `127.0.0.1` — which stops a request from
*another machine*, and nothing else. The attack this story exists to close comes from the machine
itself: a page on `evil.example.com` whose DNS is rebound to `127.0.0.1` reaches a loopback-bound
port perfectly well, and the only thing distinguishing it from a legitimate request is the `Host`
header the browser sends. c1-4 gave the vocabulary for the refusal (`invalid_request`), so this is
the first story that *produces* a typed rejection rather than defining one. It is also the last
structural story before the app grows a data surface: c1-6 adds the first data-backed endpoints,
c3-1/c3-2/c3-5 add deck, card and image routes, c5-3 adds the WebSocket upgrade — every one of
them is protected by what lands here, and c5-3's AC explicitly says the upgrade "reuses that check
rather than duplicating it (AD-5)". If the check is not middleware, or if it does not see
`websocket` scopes, c5-3 has nothing to reuse.

## Acceptance Criteria

1. **One module owns the envelope: `src/companion/app/security.py`.** The spine's Structural Seed
   names it (`security.py # Host validation, token, ticket mint/consume (AD-5)`); this story fills
   only the Host-validation third, and c5-2/c5-5 add the ticket and the agent token to the same
   module. It exports exactly:

   - `ALLOWED_HOSTNAMES: frozenset[str]` — `{"127.0.0.1", "localhost"}`;
   - `allowed_authorities(port: int) -> frozenset[str]` — the authority strings valid for *port*;
   - `host_is_allowed(host: str | None, port: int | None) -> bool` — the whole decision as a pure
     function, so the accept/reject matrix is testable without an ASGI stack;
   - `HostValidationMiddleware` — pure ASGI, the only caller of the predicate;
   - `install_security(app: FastAPI) -> None` — one wiring call, mirroring
     `install_error_handling`, so c5-2/c5-3 add their pieces here and `build_app()` never grows a
     second security line.

2. **The accepted set is exactly the two loopback authorities at the actual bound port.** With a
   bound port `P`, `allowed_authorities(P)` is `{f"127.0.0.1:{P}", f"localhost:{P}"}` — plus the
   bare `127.0.0.1` / `localhost` **only when `P == 80`**, because an HTTP client omits the default
   port from `Host`. The header is compared after `.strip().lower()` and by **exact string match**
   against that set. Nothing is parsed, resolved or normalised further; that is the point. A
   parametrized test pins the matrix:

   | `Host` | Verdict | Why |
   | --- | --- | --- |
   | `127.0.0.1:P` / `localhost:P` | accept | the two supported spellings |
   | `LOCALHOST:P` | accept | host names are case-insensitive |
   | `127.0.0.1` / `localhost` (bare), `P != 80` | reject | implies port 80, not the bound one |
   | `127.0.0.1:Q`, `localhost:Q` (`Q != P`) | reject | AC 3 — a mismatched port is a different server |
   | `evil.example.com:P` | reject | the DNS-rebinding case NFR-01 names |
   | `[::1]:P` | reject | the socket is IPv4-only (`server.HOST`), so `::1` never reaches us |
   | `localhost.:P` | reject | trailing-dot FQDN — a classic allow-list bypass |
   | `127.1:P`, `127.0.0.001:P`, `0x7f.1:P` | reject | alternate loopback spellings; exact matching kills the whole class without parsing |
   | *(absent)* or `""` | reject | HTTP/1.1 requires `Host`; absence is not a pass |

3. **The port is read from application state at request time, never from a constant.** The
   middleware reaches it through `main.bound_port(app)` with `app` taken from `scope["app"]`
   (verified present on **both** `http` and `websocket` scopes, and set by Starlette *before* the
   middleware stack runs). So an ephemeral fallback validates against the port actually bound, and
   `server.DEFAULT_PORT` is never named here — c1-3's `TestNothingElseHardcodesThePort` stays
   green.

4. **No bound port means reject, not skip (Decide-once #2).** `bound_port(app) is None` →
   the same typed 400. `run()` sets `app.state.bound_port` before `_serve` (c1-3, pinned by
   `test_server.py::test_state_carries_the_real_bound_port`), so no supported path is affected;
   fail-open would mean a future runner that forgot the state assignment silently disables the
   envelope, and nothing would go red.

5. **The rejection is c1-4's typed body, *sent* by the middleware — never raised.** The middleware
   returns `error_response("invalid_request")` from `errors.py` (the single construction site for
   the body), giving exactly `400 {"reason": "invalid_request"}`, and the route handler **never
   runs** — pinned by a test-local route that flips a flag and asserting the flag stays `False`.
   Raising `CompanionError` here is wrong and the story must not do it: user middleware sits
   *outside* Starlette's `ExceptionMiddleware`, so the registered handler never sees it. Verified
   at c1-5's exact position (inner user middleware): the client gets
   `500 {"reason": "internal_error"}` plus a false `ERROR` traceback from `UnhandledErrorMiddleware`
   — wrong token, wrong status, and log noise on a routine rejection.

6. **A rejected `websocket` scope is denied at the handshake, by the same code path (AD-5).** For
   `scope["type"] == "websocket"` with a disallowed `Host`, the middleware sends
   `{"type": "websocket.close", "code": 1008}` and does **not** call the inner app; uvicorn turns a
   close-before-accept into an HTTP **403** handshake denial
   (`uvicorn/protocols/websockets/websockets_impl.py:286-293`, verified). Every other scope type
   (`lifespan`) passes straight through untouched — a `lifespan` scope has no `headers` key and
   would raise if it reached the check. No WebSocket route exists yet, so both branches are driven
   **at the ASGI level** (`HostValidationMiddleware(app)(scope, receive, send)` directly), exactly
   as c1-4 drove its own unreachable branches — an unexercised guard is c1-1's dead-guard lesson.

7. **More than one `Host` header is a rejection.** `Headers(scope=scope).get("host")` returns the
   *first* of several (verified with a two-`host` scope), which is precisely the ambiguity where
   our check and a later reader could disagree about what was addressed. Count the `b"host"`
   entries in `scope["headers"]`; more than one → reject. Defence in depth — no claim is made about
   whether uvicorn's parser would have rejected it first.

8. **The security middleware is installed *inside* the error middleware.** `build_app()` calls
   `install_security(app)` **before** `install_error_handling(app)`, so
   `[m.cls for m in app.user_middleware] == [UnhandledErrorMiddleware, HostValidationMiddleware]`
   (index 0 is the *last* added, i.e. outermost — verified). A test pins that exact list, not just
   index 0. This is what c1-4's install-last comment in `main.py` was written for: a fault in the
   Host check itself answers as a typed `500 internal_error` instead of an untyped traceback.
   Corollary worth checking rather than assuming: c1-4's own pin
   (`test_errors.py`: `app.user_middleware[0].cls is UnhandledErrorMiddleware`) stays green
   **unedited** precisely because the insertion goes *before* `install_error_handling` — if that
   test goes red, the wiring is upside down, not the test.

9. **CORS: none is installed, and that *is* "restricted to the app's own origin" (Decide-once #3).**
   Guarded by three assertions rather than by a comment:
   - a preflight `OPTIONS /health` carrying `Origin: http://evil.example.com` +
     `Access-Control-Request-Method: GET` comes back with **no** `access-control-allow-origin`
     header (today: `405` typed `invalid_request`, `Allow: GET` preserved by c1-4's header
     forwarding — verified);
   - a *simple* cross-origin `GET /health` likewise carries no `access-control-allow-origin`;
   - no middleware in `app.user_middleware` is Starlette's `CORSMiddleware`, so a later story that
     wants one has to come back to this ruling first.

   This also resolves the ordering tension c1-4 deferred here (an inner `CORSMiddleware` would
   never stamp headers on an outer-middleware 503): with no CORS middleware, there is no trade
   left to make. Record that in the story's Completion Notes and strike the item from
   `deferred-work.md`.

10. **`SO_EXCLUSIVEADDRUSE` on the Windows bind (closes the c1-3 deferral).** `server._new_socket()`
    sets `SO_EXCLUSIVEADDRUSE` when `os.name == "nt"`, alongside — and mutually exclusive with —
    the existing POSIX-only `SO_REUSEADDR`. The option exists only on Windows (verified here:
    `socket.SO_EXCLUSIVEADDRUSE == -5`, `os.name == "nt"`), so the test guards with
    `getattr(socket, "SO_EXCLUSIVEADDRUSE", None)` and asserts *set on Windows / absent elsewhere*,
    mirroring `test_reuseaddr_follows_asyncios_own_platform_policy`. Without it another local
    process using `SO_REUSEADDR` can bind over the companion's held port, weakening the
    single-instance premise c1-8 is built on. The existing fallback already absorbs a harder-to-get
    bind, so no other behaviour changes. This is an edit to `src/companion/app/server.py` and
    `tests/unit/companion/test_server.py` — in scope **only** for this option.

11. **The test seam grows the kwargs its named inheritors need (closes the c1-2 deferral).**
    `tests/unit/companion/conftest.py::_lifespan_client(app, *, base_url=None, headers=None,
    bound_port=_TEST_BOUND_PORT)`:
    - by default it stamps `app.state.bound_port = bound_port` **only if the app has none**, and
      derives `base_url = f"http://127.0.0.1:{port}"` from whatever port the app ends up with — so
      httpx sends a valid `Host` automatically (verified: httpx derives `Host` from `base_url`,
      port included);
    - `bound_port=None` leaves state unset, which is how AC 4's never-bound case is driven;
    - `base_url=` / `headers=` let a test address the app as anything it likes.

    `_TEST_BOUND_PORT` is a distinctive constant (**not** 8765) so nothing in the suite can pass by
    accidentally agreeing with the production default. The acceptance signal for this AC is that
    **every existing companion test passes unedited** — which also means the whole existing suite
    now exercises the Host path on every request it makes.

12. **Tests: `tests/unit/companion/test_security.py`**, unmarked unit tests, driving a real
    `build_app()` through `lifespan_client` (plus direct ASGI calls for AC 6's two branches).
    Cover: AC 2's full matrix through `host_is_allowed` **and** at least one accept + one reject
    end-to-end through the stack; the ephemeral case (state says `P`, a `Host` naming 8765 is
    rejected); never-bound; route-not-reached; duplicate `Host`; websocket close; lifespan
    passthrough; the middleware-order list; AC 9's three CORS pins; and that a rejection logs
    exactly one `WARNING` from `src.companion.app.security` whose message carries the offending
    host **truncated** (AC 13). Non-vacuity: the accept case must return a real `200` from
    `/health`, so the guard cannot pass by rejecting everything.

13. **The rejection is logged once, at `WARNING`, with the offending value truncated.** `WARNING`
    because no story has configured a root logger yet (c1-9 owns that) and `logging.lastResort`
    surfaces `WARNING`+ to stderr — an `INFO` line would vanish in every real run, and this is the
    one event an operator needs to see. The `Host` value is attacker-controlled input on its way
    into a log file, so it is truncated (≤ 100 chars) and `%`-style lazy args are used, per
    project-context.

14. **Quality gates green (NFR-07).** `uv run ruff check .`, `uv run ruff format --check .`,
    `uv run mypy src/` and `uv run pytest -m "not integration"` all pass with **no new failures**
    against the **1,452 passed / 45 deselected** baseline (verified at `5779c80` on 2026-07-25).
    Actual output pasted into the Debug Log.

15. **Plugin mirror rebuilt and committed.** `uv run python -m scripts.build_plugin`, then commit
    `plugin/`; `git status --porcelain -- plugin/` clean afterwards.

16. **Scope boundary — what this story must NOT do.** No agent token, no WS ticket, no
    `GET /api/session`, no `Origin` validation on HTTP requests (c5-2/c5-3 own all four — see
    Decide-once #5). No database engine or `deps.py` (c1-6). No discovery file (c1-7), no
    single-instance check (c1-8), no CLI (c1-9). No new route in `src/`. No behavioural change to
    `errors.py` or `contracts.py` — the `invalid_request` token already exists (a **docstring-only**
    accuracy fix in `errors.py` is permitted, see Task 6). No root-logger configuration. No new
    dependency, no `pyproject.toml` / `uv.lock` / `.pre-commit-config.yaml` change. No edit to
    `tests/unit/companion/test_app.py`, `test_errors.py`, `test_import_boundary.py` or
    `.github/workflows/ci.yml`.

## Tasks / Subtasks

- [x] **Task 0 — State verification** (standing team agreement since the epic-6 retro: any story
      whose notes assert repository state opens with the cheap check that proves it)
  - [x] Create `feat/companion-c1-5-localhost-security-envelope` **off `feat/companion-app`**
        (currently at `5779c80`); the story PR targets `feat/companion-app`.
  - [x] Confirm `src/companion/app/security.py` and `tests/unit/companion/test_security.py` do
        **not** exist, and that `src/companion/app/main.py::build_app` ends with
        `install_error_handling(app)`.
  - [x] Baseline the suite: `uv run pytest -m "not integration" -q` → expected **1,452 passed, 45
        deselected**. Record any delta rather than chasing it.

- [x] **Task 1 — The predicate, test-first** (AC: 1, 2)
  - [x] Write the AC 2 matrix as a parametrized test against `host_is_allowed` first, and watch it
        fail on the missing module (red-phase evidence for the Debug Log).
  - [x] `src/companion/app/security.py` — module docstring covering: what `Host` defends against
        (DNS rebinding from a page on the same machine, which the loopback bind does *not* stop);
        why the match is exact rather than parsed; and why the module sends the response instead of
        raising (Decide-once #1). Module-level `logger = logging.getLogger(__name__)`.
  - [x] `ALLOWED_HOSTNAMES`, `allowed_authorities(port)`, `host_is_allowed(host, port)` — Google
        docstrings; `host_is_allowed` returns `False` for `host is None`, `""` and `port is None`.

- [x] **Task 2 — The middleware** (AC: 3, 5, 6, 7, 13)
  - [x] `HostValidationMiddleware` — `__init__(self, app: ASGIApp)`,
        `async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None`.
        Pass through any scope whose type is neither `http` nor `websocket`. Read the port with a
        **function-local** `from src.companion.app.main import bound_port` (Gotcha 3 — the
        module-level form is a verified `ImportError`), counting and reading the `host` header from
        `scope["headers"]`.
  - [x] Reject path: log once at `WARNING` with `%`-style args and a truncated host; then
        `await error_response("invalid_request")(scope, receive, send)` for `http`, or
        `await send({"type": "websocket.close", "code": 1008})` for `websocket`. Do not call the
        inner app on either.
  - [x] `install_security(app: FastAPI) -> None` — adds the middleware; docstring states it must be
        called **before** `install_error_handling(app)` and why (AC 8).

- [x] **Task 3 — Wire it into the app** (AC: 8)
  - [x] `src/companion/app/main.py` — `install_security(app)` immediately above
        `install_error_handling(app)`, extending (not replacing) the existing install-last comment
        so the ordering rule reads as one thought.
  - [x] Change nothing else in `main.py`: `lifespan`, `_shutdown`, `bound_port`,
        `_CompanionFastAPI` and the app-level `responses=` are untouched.

- [x] **Task 4 — Repair and extend the test seam** (AC: 11)
  - [x] At this point the companion suite is red (`testserver` is not an allowed authority) —
        capture that output as red-phase evidence, it is the proof the middleware is live.
  - [x] Extend `tests/unit/companion/conftest.py` per AC 11: `_TEST_BOUND_PORT`, the three kwargs,
        the stamp-if-absent rule, the derived `base_url`. Update the module docstring to say why
        the seam now stamps a port.
  - [x] Re-run `uv run pytest tests/unit/companion -q` and confirm every pre-existing test is green
        **without editing it**.

- [x] **Task 5 — `SO_EXCLUSIVEADDRUSE`** (AC: 10)
  - [x] `server._new_socket()` — add the Windows branch and extend the docstring with what the
        option buys (nobody binds over a held port) and why it pairs with the `SO_REUSEADDR`
        omission rather than contradicting it.
  - [x] Add `test_exclusiveaddruse_is_set_on_windows_only` next to the existing reuse-policy test.
  - [x] Re-run `tests/unit/companion/test_server.py` in full: the fallback tests must still pass on
        this machine, since a *harder* bind is exactly what they exercise.

- [x] **Task 6 — Tests and the docstring fix** (AC: 5, 6, 7, 9, 12, 13)
  - [x] `tests/unit/companion/test_security.py` per AC 12, with the accept-case non-vacuity
        assertion called out in a comment.
  - [x] Docstring-only accuracy fix in `errors.py`: `CompanionError`'s docstring names "c1-5 (bad
        `Host`)" as a first caller, which this story's Decide-once #1 makes false — c1-5 *sends*
        the body, it does not raise. Correct the list to c1-6 / c3-1 / c5-5 and note that the
        middleware layer sends directly. **No behaviour change** (the c1-4 precedent: fix the docs
        nit while you are in the file).

- [x] **Task 7 — Gates, mirror, deferred-work and scope** (AC: 9, 14, 15, 16)
  - [x] `uv run ruff check . --fix` · `uv run ruff format .` · `uv run mypy src/` ·
        `uv run pytest -m "not integration"` — paste actual counts into the Debug Log.
  - [x] `_bmad-output/implementation-artifacts/deferred-work.md`: mark the three items this story
        closes — the c1-2 `lifespan_client` seam item, the c1-3 `SO_EXCLUSIVEADDRUSE` item, and the
        c1-4 CORS-ordering item (resolved by the no-CORS ruling, not by an ordering change).
  - [x] `uv run python -m scripts.build_plugin`, `git add plugin/`, verify
        `git status --porcelain -- plugin/` is clean after the commit.
  - [x] Confirm by command that the AC 16 forbidden files are untouched:
        `git status --porcelain -- tests/unit/companion/test_app.py tests/unit/companion/test_errors.py tests/unit/companion/test_import_boundary.py .github/workflows/ci.yml pyproject.toml uv.lock .pre-commit-config.yaml`
        returns empty.

## Dev Notes

### Decide-once rulings (made here so four later stories inherit them)

**#1 — The middleware *sends* the typed response; it never raises.** Verified at c1-5's exact
position. Starlette's stack is `ServerErrorMiddleware → user middleware → ExceptionMiddleware →
router`, so a handler registered with `add_exception_handler` is *inside* every user middleware and
can never see what one of them raises. Probed with a `CompanionError("invalid_request")` raised
from an inner user middleware against the real `build_app()`:

```text
order (outermost first): ['UnhandledErrorMiddleware', 'Raiser']
raise from INNER user middleware -> 500 {'reason': 'internal_error'}
# plus: ERROR "Unhandled error serving GET /health" with a full traceback
```

Wrong status, wrong token, and a security *rejection* logged as a backend *bug*. Raised from an
**outer** user middleware it is worse still — `ServerErrorMiddleware` re-raises and the caller gets
the exception itself, no response at all (the same behaviour c1-4's Decide-once #1 documented).
`error_response(...)` is a plain `JSONResponse` factory and is callable directly on a scope, so the
wire shape stays byte-identical to every other 400 in the app.

**#2 — No bound port means reject.** The alternative — skip validation when
`app.state.bound_port` is unset — is fail-open, and its failure mode is invisible: some later
runner (c1-9's CLI, a Tauri wrapper, a test harness) serves an app without stamping the port and
the entire envelope silently evaporates with every test still green. Rejecting makes that
mis-wiring a loud `400` on the first request. The cost is that the in-process test seam must supply
a port, which AC 11 turns into a benefit: every companion test now flows through the real check.

**#3 — CORS is implemented by installing no CORS.** Four reasons, in order of weight:

1. **The app's own origin is the only origin.** AD-13 commits the SPA to being served from
   `src/companion/app/static/` by this same backend, so every legitimate browser request is
   same-origin and needs no CORS grant at all. "Restricted to the app's own origin" *is* the empty
   grant.
2. **A browser refuses by default.** With no `Access-Control-Allow-Origin` on the response, the
   cross-origin fetch fails in the browser — the AC's "refused" is satisfied by omission, and
   verified today: preflight `405` (typed, `Allow: GET` intact), simple `GET` `200`, neither
   carrying `ACAO`.
3. **`CORSMiddleware` would breach AD-16.** Its own preflight refusal is
   `400 'Disallowed CORS origin'` as `text/plain` (verified) — a second, untyped error shape on the
   wire, which is exactly the thing c1-4 exists to prevent. And it does **not** block a simple
   cross-origin request either (verified: `200`, no `ACAO`), so it buys nothing here.
4. **It cannot know the port.** `allow_origins` is fixed at construction time, and under an
   ephemeral fallback the app's own origin is not known until the socket is bound. An
   `allow_origin_regex` loose enough to cover any port would grant *every* local app an origin —
   worse than nothing.

What actually protects the state-changing surface is **not** CORS and later stories must not
assume otherwise: `POST /agent/events` requires the agent token, which never reaches the browser
(AD-5), and the WebSocket upgrade requires a single-use ticket minted at a same-origin endpoint a
cross-origin page cannot read. This ruling also closes c1-4's deferred CORS-ordering item — with no
CORS middleware, the "inner CORS never stamps an outer 503" trade does not arise.

**#4 — Not Starlette's `TrustedHostMiddleware`.** Three disqualifying facts, all in
`starlette/middleware/trustedhost.py`:

- it discards the port outright (`host = headers.get("host", "").split(":")[0]`), and AC 3's whole
  point is that the port must match the *bound* one;
- its rejection is `PlainTextResponse("Invalid host header", status_code=400)` — untyped, breaching
  AD-16;
- `allowed_hosts` is fixed at construction, before the ephemeral port exists.

The one idea worth borrowing is its scope handling: it validates `http` **and** `websocket` and
passes everything else through, which is the shape AC 6 requires.

**#5 — `Host` is this story's job; `Origin` is not.** They answer different questions: `Host` is
*what authority was addressed* (the rebinding defence), `Origin` is *which page is calling*. AD-5
homes `Origin` on the WebSocket upgrade specifically, because CORS never applies to WebSockets and
the upgrade is the one place a browser-originated connection can be checked. Adding an `Origin`
check to every REST request now would duplicate that decision, and would break any future
Vite-dev-server proxy workflow without a UX ruling. Homed on c5-2 (same-origin ticket mint) and
c5-3 (upgrade `Origin` check) — flagged in the Open Questions rather than silently dropped.

### Architecture rules this story implements

- **AD-5** — the Host half of the envelope, and the middleware placement that lets c5-3 inherit it
  for the upgrade without duplication. The token and ticket halves stay in c5-2/c5-5, in this same
  module.
- **AD-16** — a rejection is `invalid_request` from the closed set, with the status derived from
  `STATUS_BY_REASON`, and the body built by the single `error_response` construction site. This
  story adds **no** token: `invalid_request`'s `ErrorResponse` docstring already covers "aimed at a
  path/method/`Host` the companion does not serve".
- **AD-10** — construction stays inert. Adding middleware is in-process object graph work; no port,
  no file, no engine. `test_app.py::TestConstructionIsInert` must stay green untouched.
- **AD-3** — `security.py` lives under `src/companion/app/`, which the boundary test classifies
  automatically. No `test_import_boundary.py` edit is needed; if you want one, a file is in the
  wrong place.
- **NFR-01** — the socket-layer half (`127.0.0.1` bind) already exists; this story adds the
  request-layer half and hardens the bind itself (AC 10).

### Source tree — what exists, what this story adds

```text
src/
  companion/
    app/
      security.py              # NEW — ALLOWED_HOSTNAMES, allowed_authorities, host_is_allowed,
                               #       HostValidationMiddleware, install_security
      main.py                  # UPDATE — install_security(app) immediately above install_error_handling(app)
      server.py                # UPDATE — SO_EXCLUSIVEADDRUSE on Windows (AC 10), nothing else
      errors.py                # UPDATE — docstring accuracy only (Task 6); no behaviour change
      routes/health.py         # EXISTS — untouched
    contracts.py               # EXISTS — untouched (invalid_request already in ErrorReason)
tests/
  unit/companion/
    conftest.py                # UPDATE — the three kwargs + the stamped bound port (AC 11)
    test_security.py           # NEW
    test_server.py             # UPDATE — one new test for AC 10
    test_app.py                # EXISTS — NOT edited (AC 16)
    test_errors.py             # EXISTS — NOT edited (AC 16)
    test_import_boundary.py    # EXISTS — NOT edited (AC 16)
```

**Current state of the files being modified** (read before editing):

- `src/companion/app/main.py` — `_TITLE`, `_shutdown`, `lifespan` (mints `instance_id`,
  swallow-and-log teardown), `bound_port(app)` (annotated local, returns `None` before any bind),
  `_CompanionFastAPI` (the `openapi()` hook that strips FastAPI's auto-422 — Greptile's PR #12
  catch), and `build_app()` = `_CompanionFastAPI(...)` + `include_router(health.router)` +
  `install_error_handling(app)` last, under a comment that already says *"c1-5's Host middleware
  belongs above this line, not below."* **What must be preserved:** no module-level side effect and
  no `src.paths` import (the inertness tests fresh-import this module with `socket.socket.bind`
  patched to raise and `PLANESWALKER_DATA_DIR` pointed at a non-existent directory);
  `bound_port`'s exact semantics; the `_CompanionFastAPI` hook.
- `src/companion/app/server.py` — `HOST = "127.0.0.1"`, `DEFAULT_PORT = 8765`,
  `resolve_preferred_port`, `_new_socket()` (sets `SO_REUSEADDR` on POSIX only),
  `bind_localhost_socket` (any-`OSError` fallback to an ephemeral port), `_serve` (uvicorn with
  `sockets=[sock]`), `run()` (stdout `print`, sets `app.state.bound_port = actual` **before**
  `_serve`). **What must be preserved:** the POSIX-only `SO_REUSEADDR` line and its rationale — the
  new option is an addition on the other branch, not a replacement; the "the returned socket holds
  exactly *preferred* on success" invariant; the fallback-on-any-`OSError` behaviour.
- `src/companion/app/errors.py` — `STATUS_BY_REASON` (six tokens), `CompanionError`,
  `error_response(reason, *, status=None, headers=None)`, `error_responses(*reasons)`,
  `without_auto_validation_schema`, three handlers, `UnhandledErrorMiddleware`,
  `install_error_handling`. **What must be preserved:** everything except the one docstring line in
  Task 6. `error_response` is the function this story calls; note it already accepts `headers=`,
  which the rejection path does not need.
- `tests/unit/companion/conftest.py` — `BASE_URL = "http://testserver"`, `_lifespan_client(app)`
  (enters `lifespan(app)` directly, then wraps `httpx.ASGITransport`), and the `lifespan_client`
  fixture that returns the context manager. **What must be preserved:** the "enter the module-level
  `lifespan` directly rather than adding `asgi-lifespan`" decision (c1-2 Decide-once #2), and the
  consequence recorded in its docstring — startup values live on `app.state`, never on a state dict
  yielded from the lifespan.

**Deviation from the spine's Structural Seed:** none. `security.py` is on the seed's list by name;
this story fills a third of it and says so in the module docstring, so c5-2/c5-5 extend rather than
wonder.

### Gotchas specific to this story

1. **`testserver` is not an allowed authority.** The moment the middleware is wired, every
   companion test that requests through the existing seam gets `400`. That is expected and is the
   proof the wiring works — fix it once, in the conftest (Task 4), not by exempting anything in
   `src/`.

2. **A raise from user middleware bypasses the exception handlers** — Decide-once #1, verified.
   If you find yourself writing `raise CompanionError(...)` in `security.py`, the AC 5 test will
   fail with `500 internal_error`.

3. **`from src.companion.app.main import bound_port` at module level in `security.py` is a real
   `ImportError`** — verified in both directions with a minimal reproduction:

   ```text
   ImportError: cannot import name 'bound_port' from partially initialized module
   'cyc.main' (most likely due to a circular import)
   ImportError: cannot import name 'install_security' from partially initialized module
   'cyc.security' (most likely due to a circular import)
   ```

   `main.py` imports `install_security` in its top import block, above where `bound_port` is
   defined. Use a **function-local** import inside `__call__` with a comment naming the cycle —
   project-context explicitly sanctions that for real cycles. Do **not** solve it by re-deriving
   `getattr(app.state, "bound_port", None)` in `security.py`: `bound_port` is the accessor c1-3
   built *for this caller* (its docstring says so), and a second reader of the same state is a
   second construction site.

4. **`scope["app"]` is set by Starlette before the middleware stack runs, on `websocket` scopes
   too** (both verified). That is how the middleware reaches the live port without importing
   `server.py` — which would drag uvicorn onto every request path.

5. **`app.user_middleware[0]` is the *last* middleware added.** Hence "install security *before*
   error handling". Pin the whole list, not just index 0, so a future insertion between them is
   visible.

6. **Never call the inner app after rejecting.** On `http` that would send two responses; on
   `websocket` it would hand a denied connection to a route that expects to `accept()` it.

7. **`websocket.close` before `websocket.accept` is the ASGI-legal denial** and uvicorn renders it
   as HTTP `403` (`websockets_impl.py:286-293`). Do not try to send an HTTP response on a
   `websocket` scope.

8. **`lifespan` scopes have no `headers` key.** Guard on `scope["type"]` *first*; a bare
   `Headers(scope=scope)` on a lifespan scope raises, and it would raise during startup, where the
   failure is least legible.

9. **Header names in the ASGI scope are lowercased bytes**, so the duplicate count is over
   `b"host"`. Values are bytes — decode with `latin-1` (what the ASGI spec and Starlette use) and
   only then `.strip().lower()`.

10. **Uvicorn's proxy-headers middleware never rewrites `Host`.** It touches only `scope["client"]`
    and `scope["scheme"]` from `X-Forwarded-For` / `X-Forwarded-Proto`
    (`uvicorn/middleware/proxy_headers.py`), so there is no `X-Forwarded-Host` laundering path to
    defend against — and no reason to read anything but the `Host` header itself.

11. **Do not exempt `/health`.** It is unauthenticated by design (it is what a caller reads before
    sending a token), but "unauthenticated" is not "unprotected" — NFR-01 says *all* endpoints
    validate `Host`, and `/health` is precisely what a rebound page would probe first.

12. **`mypy --strict` needs the ASGI types**: `__init__(self, app: ASGIApp) -> None`,
    `__call__(self, scope: Scope, receive: Receive, send: Send) -> None`, imported from
    `starlette.types`. `_`-prefixed helpers stay private; everything public gets a Google docstring.

13. **The write guard scans `app/` too.** Nothing here goes near a session, but do not name a local
    `db`, `conn` or `session` and call `.add(...)` / `.update(...)` on it — `_SESSION_MUTATORS` on a
    session-shaped receiver turns the boundary test red.

14. **`SO_EXCLUSIVEADDRUSE` exists only on Windows.** Reference it through the `os.name == "nt"`
    branch (and `getattr` in the test), or the module fails to import on CI's Linux runners.

### Testing standards

- New tests live in `tests/unit/companion/test_security.py` — unmarked, fast, no network, no server
  boot. `--strict-markers` is on: do not invent a marker.
- `asyncio_mode = "auto"` — write `async def test_…` directly; no `@pytest.mark.asyncio`.
- Reuse the `lifespan_client` fixture; extend it per AC 11 rather than building a second client
  seam, and do not add `asgi-lifespan` (c1-2 ruled against the dependency).
- Drive AC 6's two branches at the ASGI level with **real async stubs** for `receive`/`send` — c1-4's
  review had to fix a test that passed `None` for both, which violates the ASGI contract and turns a
  future failure into a `TypeError` instead of an assertion.
- Parametrize AC 2's matrix as data (the table *is* the test), and assert the accept case
  end-to-end so the suite cannot pass by rejecting everything.
- **Verification before completion:** paste actual ruff / mypy / pytest output into the Debug Log.
  "Tests pass" without output is not acceptance — standing agreement from the epic-5/6 retros.

### Previous story intelligence (c1-4, done 2026-07-25, merged as PR #12)

- **Two wire-contract rulings landed late and are now load-bearing:** the token set is closed at
  **six** (`internal_error`, 500) and `payload_too_large` is **413**. `invalid_request` is
  unchanged at 400 — this story needs no token work at all.
- **Greptile's PR #12 catch is the pattern to fear:** a change that removed the explicit 422
  silently resurrected FastAPI's auto-generated `HTTPValidationError`, and the displacement test
  passed *vacuously* because no shipped route had validated input. The lesson this story inherits:
  a structural assertion must be shown to be non-vacuous (AC 12's accept case, AC 9's real preflight).
- **`_CompanionFastAPI.openapi()` is a schema-build hook.** Do not disturb it; adding middleware
  does not touch the schema, and no new OpenAPI declaration is needed for the rejection — the
  app-level `responses=` already documents `400 invalid_request` on every route.
- **The story-record → review → patch rhythm is established**: c1-4 took 26 raw findings to 16,
  applied 9 patches + 1 Greptile fix, deferred 1, dismissed 4. Write the record so a reviewer can
  verify each claim by command.
- **Gate-output homing** (open epic-7 action item) — this story closes three named deferrals rather
  than passing them on: the c1-2 seam item (AC 11), the c1-3 `SO_EXCLUSIVEADDRUSE` item (AC 10) and
  the c1-4 CORS-ordering item (AC 9's ruling). Its own rulings are homed as: #1 and #4 on
  **c5-3** (the upgrade reuses this middleware and must not re-implement the check), #3 on **c2-1 /
  c2-2** (the SPA is same-origin; a dev-server proxy is the only thing that could change that), and
  #5 on **c5-2 / c5-3** (`Origin`).
- **Construction-site enumeration** (standing agreement): the concept here is *the allowed
  authority*, and its sites are exactly three — `ALLOWED_HOSTNAMES`, `allowed_authorities(port)`
  (the only place a port is formatted into an authority) and the middleware's read of
  `bound_port`. `server.HOST`/`DEFAULT_PORT` are deliberately **not** among them; c1-3's
  `TestNothingElseHardcodesThePort` fails if this story names 8765 anywhere in `src/`.
- **The mypy-hook `additional_dependencies` floor-vs-lock drift stays deferred** (Brad, 2026-07-25).
  This story adds no dependency, so it neither extends nor resolves that item.

### Git intelligence

`HEAD = 5779c80` on `feat/companion-app` (the PR #12 merge). The per-story pattern across
c1-1 → c1-4 is: one focused `feat(companion): …` commit implementing the story, review fixes as
separate follow-up commits on the same branch, then a PR into `feat/companion-app` (Greptile
reviews per story). c1-4 needed a `feat(companion)!:` commit for its breaking contract change —
this story has no wire-contract change and needs no `!`.

Suggested commit: `feat(companion): localhost-only security envelope — Host validation and the CORS ruling`.

### Latest technical information

Verified in this environment on 2026-07-25: **FastAPI 0.140.0 · Starlette 0.48.0 · httpx 0.28.1 ·
uvicorn 0.51.0 · pydantic 2.12.0**, all at or above the spine's floors. No upgrade is part of this
story and no dependency is added — `starlette.datastructures.Headers`, `starlette.types` and the
existing `error_response` cover everything.

Probe results this story is built on (each re-runnable in five lines):

- `scope["app"]` is present and is the app object in a user middleware, on `http` **and**
  `websocket` scopes.
- httpx derives `Host` from `base_url`, port included (`http://127.0.0.1:8765` → `127.0.0.1:8765`),
  and a per-request `headers={"Host": ...}` override reaches the scope verbatim — so the test seam
  can address the app as anything.
- A middleware can send a `JSONResponse` directly onto a scope: `400 {"reason": "invalid_request"}`,
  `content-type: application/json`.
- A `CompanionError` raised from an inner user middleware yields `500 internal_error` + a false
  `ERROR` traceback (Decide-once #1).
- Two `host` headers in a scope → `Headers.get("host")` returns the first (AC 7).
- On the shipped app today: preflight `OPTIONS /health` with a cross origin → `405`
  `{"reason": "invalid_request"}`, `Allow: GET`, **no** `ACAO`; simple cross-origin `GET` → `200`,
  **no** `ACAO`.
- `CORSMiddleware` with a restricted `allow_origins`: preflight refusal is
  `400 'Disallowed CORS origin'`, `text/plain`; a simple cross-origin `GET` still returns `200` with
  no `ACAO` (Decide-once #3).
- `socket.SO_EXCLUSIVEADDRUSE == -5` on this Windows box; the constant is absent on POSIX.
- The `main` ↔ `security` module-level import cycle fails in both directions (Gotcha 3).

### Project Structure Notes

- `security.py` under `src/companion/app/` is classified automatically by
  `test_import_boundary.py::test_every_companion_file_sits_in_a_guarded_category` (the `app/`
  branch), so **no boundary-test edit is required**. It may import `fastapi` and `starlette`
  freely — it is app-side, not leaf.
- Pre-existing tracked files modified: `src/companion/app/main.py`, `src/companion/app/server.py`,
  `src/companion/app/errors.py` (docstring only), `tests/unit/companion/conftest.py`,
  `tests/unit/companion/test_server.py`, `_bmad-output/implementation-artifacts/deferred-work.md`,
  `_bmad-output/implementation-artifacts/sprint-status.yaml`, and the generated `plugin/` mirror.
  **Not** `pyproject.toml`, `uv.lock` or `.pre-commit-config.yaml`.
- Docs nit worth a one-line fix if you are already in the file: `epics-companion-app.md:2381` says
  "the Host middleware from Story 1.4" where it means **Story 1.5** (this one) — the same class of
  off-by-one c1-4 fixed at line 1559. Optional, and outside AC 16's forbidden list.

### References

- [epics-companion-app.md — Story 1.5](_bmad-output/planning-artifacts/epics-companion-app.md#L1015-L1042) — the source acceptance criteria · [Epic 1 framing](_bmad-output/planning-artifacts/epics-companion-app.md#L882-L888)
- Consumers and neighbours: [Story 5.3 — the upgrade reuses this check](_bmad-output/planning-artifacts/epics-companion-app.md#L2378-L2387) · [Story 5.2 / 5.5 — ticket + token, same module](_bmad-output/planning-artifacts/epics-companion-app.md#L2421-L2453) · [Story 1.6 — the first data endpoints behind this envelope](_bmad-output/planning-artifacts/epics-companion-app.md#L1044-L1073)
- ARCHITECTURE-SPINE.md — [AD-5](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L143-L157) · [AD-16](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L329-L348) · [AD-10](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L227-L240) · [Structural Seed — `security.py`](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L438-L462) · [Capability map — security envelope](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L475)
- [prd.md — NFR-01](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L160) — the whole envelope in one line · [epics-companion-app.md — NFR-01 as inventoried](_bmad-output/planning-artifacts/epics-companion-app.md#L137-L142)
- [src/companion/app/main.py](src/companion/app/main.py#L131-L157) — `build_app()` and the install-last comment written for this story · [`bound_port`](src/companion/app/main.py#L82-L107) — the accessor c1-3 built for this caller
- [src/companion/app/errors.py](src/companion/app/errors.py#L87-L113) — `error_response`, the body this story sends · [`install_error_handling`](src/companion/app/errors.py#L338-L355) — the ordering contract
- [src/companion/app/server.py](src/companion/app/server.py#L111-L126) — `_new_socket`, the AC 10 edit · [tests/unit/companion/test_server.py](tests/unit/companion/test_server.py#L228-L233) — the reuse-policy test to mirror
- [tests/unit/companion/conftest.py](tests/unit/companion/conftest.py) — the seam to extend (AC 11)
- [.venv/Lib/site-packages/starlette/middleware/trustedhost.py](.venv/Lib/site-packages/starlette/middleware/trustedhost.py) — why not this (Decide-once #4) · [cors.py](.venv/Lib/site-packages/starlette/middleware/cors.py) — the untyped `Disallowed CORS origin` body
- [.venv/Lib/site-packages/uvicorn/protocols/websockets/websockets_impl.py](.venv/Lib/site-packages/uvicorn/protocols/websockets/websockets_impl.py#L286-L293) — close-before-accept renders as 403
- [c1-4 story record](_bmad-output/implementation-artifacts/c1-4-typed-rest-error-contract-with-closed-reason-tokens.md) — the four Decide-once rulings this story builds on · [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md#L614-L659) — the three items this story closes
- [project-context.md](_bmad-output/project-context.md) — `%`-style lazy logging, ruff/mypy, Google docstrings, function-local imports for real cycles

## Open questions for Brad

Neither blocks implementation.

1. **`Origin` is not validated on REST requests** — only `Host` is, and (per AD-5) `Origin` is
   checked at the WebSocket upgrade. A malicious local page can therefore *issue* simple
   cross-origin GETs to the companion; it cannot read the responses (no `ACAO`), and every
   state-changing endpoint is token- or ticket-authenticated, so the envelope holds. Confirming
   that is the intended line — rather than rejecting any cross-`Origin` REST request outright —
   would let c5-2/c5-3 stop treating it as open.
2. **The Epic 2 dev workflow.** If c2-1 runs the Vite dev server on `:5173` and proxies `/api` to
   the backend, the proxy must rewrite `Host` (`changeOrigin: true`) or every proxied call gets a
   `400`. Nothing in the epics or the spine commits to a dev-proxy today (AD-13 makes the SPA a
   committed same-origin artifact), so this is a c2-1 decision, not a hole here — worth knowing
   before that story starts rather than during it.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the `bmad-dev-story` workflow.

### Debug Log References

**Task 0 — baseline (`5779c80`, branch created off `feat/companion-app`)**

```text
$ git rev-parse HEAD            -> 5779c803083df4b81fe7b6477cc2c437f3689c8c
$ Test-Path src/companion/app/security.py        -> False
$ Test-Path tests/unit/companion/test_security.py -> False
$ uv run pytest -m "not integration" -q
1452 passed, 45 deselected in 98.87s (0:01:38)
```

Exactly the expected 1,452 / 45. No delta to record.

**Task 1 — red phase (the predicate before the module)**

```text
$ uv run pytest tests/unit/companion/test_security.py -q
tests\unit\companion\test_security.py:12: in <module>
    from src.companion.app.security import ALLOWED_HOSTNAMES, allowed_authorities, host_is_allowed
E   ModuleNotFoundError: No module named 'src.companion.app.security'
1 error in 0.11s
```

Green after the module landed: `22 passed in 0.02s`.

**Task 4 — red phase (proof the middleware is live)**

With `install_security(app)` wired and the seam not yet repaired, 15 pre-existing companion tests
went red because `http://testserver` is not an allowed authority — the expected outcome, and the
evidence the guard is actually in the request path rather than merely defined:

```text
$ uv run pytest tests/unit/companion -q
15 failed, 149 passed in 0.82s
FAILED tests/unit/companion/test_app.py::TestHealthEndpoint::test_health_returns_the_typed_body
FAILED tests/unit/companion/test_errors.py::TestRaisedErrorsReachTheWire::…[deck_not_found]
FAILED tests/unit/companion/test_errors.py::TestFrameworkFailuresAreTypedToo::…404 / 405 / 5xx
… (11 more, all in test_app.py / test_errors.py)
```

After the conftest change, and with **no edit to any of those 15 tests**:

```text
$ uv run pytest tests/unit/companion -q
164 passed in 0.72s      # then 183 passed once test_security.py was complete
```

**Task 5 — the `os.name` → `sys.platform` finding**

AC 10 specifies the branch as `os.name == "nt"`. That form is runtime-correct but fails the AC 14
type gate on CI, which runs `mypy src/` on `ubuntu-latest`, because mypy narrows on `sys.platform`
and **not** on `os.name`, so it type-checks a branch typeshed has no constant for. Verified in both
directions by temporarily swapping the line:

```text
# with `elif os.name == "nt":`
$ uv run mypy src/companion/app/server.py --platform linux
src\companion\app\server.py:139: error: Module has no attribute "SO_EXCLUSIVEADDRUSE"  [attr-defined]

# with `elif sys.platform == "win32":`   (shipped)
$ uv run mypy src/companion/app/server.py --platform linux
Success: no issues found in 1 source file
```

The two conditions are identical at runtime here; only the shipped form survives a Linux checker.
Recorded as a deliberate, behaviour-identical deviation from the AC's literal wording, and
explained in `_new_socket`'s docstring so the next reader does not "correct" it back.

**Task 7 — quality gates (AC 14)**

```text
$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
268 files already formatted

$ uv run mypy src/
Success: no issues found in 79 source files

$ uv run mypy src/ --platform linux          # what CI actually runs
Success: no issues found in 79 source files

$ uv run pytest -m "not integration" -q
1493 passed, 45 deselected in 47.85s
```

1,452 baseline + 41 new (40 in `test_security.py`, 1 in `test_server.py`) = 1,493. No pre-existing
test was edited, deleted or skipped.

**One flaky failure, diagnosed and dismissed as pre-existing.** The first full-suite run showed
`1 failed, 1492 passed` at
`tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` — a test that
touches nothing this story changed. It passes in isolation (`56 passed` for its whole file) and
passed on two subsequent full runs (`1493 passed` twice). Root cause: the test creates three decks
back-to-back and asserts strict newest-first ordering, while `list_decks` orders by
`DeckModel.created_at.desc(), DeckModel.id` (`src/data/repositories/deck.py:262`) — so a same-tick
`created_at` tie falls through to a **random UUID**, which does not correlate with insertion order.
Out of AC 16's scope boundary (`src/data`), so it is characterised in `deferred-work.md` rather
than fixed here.

**Plugin mirror (AC 15)**

```text
$ uv run python -m scripts.build_plugin
Plugin assembled at …\plugin (v0.4.0, 4 skills)
$ git status --porcelain -- plugin/
 M plugin/server/src/companion/app/errors.py
 M plugin/server/src/companion/app/main.py
 M plugin/server/src/companion/app/server.py
?? plugin/server/src/companion/app/security.py     # staged and committed; clean afterwards
```

**Scope boundary (AC 16)**

```text
$ git status --porcelain -- tests/unit/companion/test_app.py tests/unit/companion/test_errors.py \
    tests/unit/companion/test_import_boundary.py .github/workflows/ci.yml pyproject.toml \
    uv.lock .pre-commit-config.yaml
(empty)
```

### Completion Notes List

- **The envelope is one module and one wiring call.** `security.py` exports exactly the five names
  AC 1 lists. `install_security(app)` sits immediately above `install_error_handling(app)` in
  `build_app()`, so `[m.cls for m in app.user_middleware] == [UnhandledErrorMiddleware,
  HostValidationMiddleware]` — pinned as a whole list, not just index 0. c1-4's own pin
  (`test_errors.py`: `user_middleware[0].cls is UnhandledErrorMiddleware`) stayed green **unedited**,
  which is the corollary AC 8 asked to be checked rather than assumed.
- **Decide-once #1 held: the middleware sends, never raises.** `error_response("invalid_request")`
  is called directly on the scope, so the rejection is byte-identical to every other typed 400 —
  same construction site, same body. No `CompanionError` is raised anywhere in `security.py`.
- **Decide-once #2 held: no bound port rejects.** Driven by `bound_port=None` through the seam, with
  an otherwise-perfect `Host`, and answered `400 invalid_request`.
- **AC 9 / Decide-once #3 — CORS is implemented by installing no CORS, and this closes c1-4's
  deferred ordering item.** Three assertions pin it: a cross-origin preflight `OPTIONS /health`
  comes back `405 {"reason": "invalid_request"}` with `Allow: GET` intact and **no**
  `access-control-allow-origin`; a simple cross-origin `GET /health` returns `200`, likewise with no
  `ACAO`; and no `CORSMiddleware` appears in `app.user_middleware`. Because there is no inner CORS
  middleware, the tension c1-4 recorded ("an outer-middleware 503 never passes back through inner
  CORS") **cannot arise** — the item is resolved by the ruling, not by an ordering change. Struck
  from `deferred-work.md` accordingly.
- **Three deferrals closed, one opened.** Closed: the c1-2 `lifespan_client` seam item (AC 11), the
  c1-3 `SO_EXCLUSIVEADDRUSE` item (AC 10), and the c1-4 CORS-ordering item (AC 9). Opened, per the
  epic-7 gate-output-homing rule rather than left floating: the `test_list_decks_with_strategy_field`
  same-tick ordering flake, with a suggested home on `data-layer-orphan-handling` (the other open
  `src/data` item).
- **Every guard is exercised, and every structural assertion is non-vacuous** (the lesson from
  Greptile's PR #12 catch). The accept case returns a real `200` from `/health`; the duplicate-`Host`
  refusal is paired with a test proving that *same* header alone is accepted; the websocket close is
  paired with an allowed-websocket passthrough; the ephemeral-port rejection is paired with the
  ephemeral port itself being accepted; the "route never ran" flag is paired with a run where it
  does. The `websocket` and `lifespan` branches are driven at the ASGI level with **real async**
  `receive`/`send` stubs, never `None`.
- **The `lifespan` passthrough test is built to fail loudly if the guard regresses**: the scope it
  passes has no `headers` and no `app` key at all, so a middleware that reached for either would
  raise during startup rather than silently pass.
- **AC 11's acceptance signal was met exactly**: all 149 pre-existing companion tests pass
  **unedited**, which means the entire companion suite now flows through the real `Host` envelope on
  every request it makes, rather than around it.
- **One deviation from the AC's literal wording**, behaviour-identical and documented in code:
  AC 10 says `os.name == "nt"`; the shipped branch is `sys.platform == "win32"` because only the
  latter is narrowed by mypy, and AC 14's type gate runs on Linux in CI. Evidence in the Debug Log.
- **One test assertion of mine was wrong and got fixed, not the code**: the truncation test first
  bounded the *whole* log message at 200 chars, which failed at 206 — the fixed prose is ~106 chars
  on top of the 100-char host cap. Replaced with an assertion on the run of characters from the host
  itself (`"e" * 101 not in message`), which pins the truncation rather than the surrounding prose.
- **Open questions for Brad are unchanged and still non-blocking** — the `Origin`-on-REST line
  (homed on c5-2/c5-3) and the Epic 2 Vite-dev-proxy `changeOrigin` consequence (homed on c2-1).
  Worth an answer before c2-1 starts rather than during it.
- **Scope was held.** No token, ticket, session endpoint, `Origin` check, engine, discovery file,
  CLI or new route. No new dependency, and `pyproject.toml` / `uv.lock` / `.pre-commit-config.yaml`
  are untouched, so the deferred mypy-hook floor-vs-lock drift is neither extended nor resolved.

### File List

| File | Change |
| --- | --- |
| `src/companion/app/security.py` | **NEW** — `ALLOWED_HOSTNAMES`, `allowed_authorities`, `host_is_allowed`, `HostValidationMiddleware`, `install_security` |
| `src/companion/app/main.py` | `install_security(app)` above `install_error_handling(app)`; ordering comment extended |
| `src/companion/app/server.py` | `SO_EXCLUSIVEADDRUSE` on the Windows bind (AC 10) + docstring |
| `src/companion/app/errors.py` | Docstring-only accuracy fix on `CompanionError` (no behaviour change) |
| `tests/unit/companion/test_security.py` | **NEW** — 40 tests (matrix, wire, duplicates, ws/lifespan, order, CORS, logging) |
| `tests/unit/companion/conftest.py` | `_TEST_BOUND_PORT` + `base_url=` / `headers=` / `bound_port=` kwargs (AC 11) |
| `tests/unit/companion/test_server.py` | `test_exclusiveaddruse_is_set_on_windows_only` |
| `_bmad-output/implementation-artifacts/deferred-work.md` | Three items closed; one new flake item recorded |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | `c1-5` → `review` |
| `_bmad-output/implementation-artifacts/c1-5-…-cors.md` | This record |
| `_bmad-output/planning-artifacts/epics-companion-app.md` | One-word docs nit: "Story 1.4" → "Story 1.5" at the c5-3 reuse clause |
| `plugin/server/src/companion/app/{security,main,server,errors}.py` | Generated mirror rebuilt (AC 15) |

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-25 | Story c1-5 created from epics Story 1.5 + AD-5/AD-16/AD-10, with every load-bearing claim verified against the installed FastAPI 0.140.0 / Starlette 0.48.0 / uvicorn 0.51.0 rather than assumed: `scope["app"]` on http and websocket scopes, the `500 internal_error` outcome of raising from an inner user middleware, `Headers.get("host")` returning the first of duplicates, the shipped app's cross-origin behaviour with and without `CORSMiddleware`, `TrustedHostMiddleware`'s port-dropping and untyped refusal, uvicorn's close-before-accept 403, the absence of `X-Forwarded-Host` handling, `SO_EXCLUSIVEADDRUSE == -5` on Windows, and the `main` ↔ `security` import cycle. Baseline re-measured at `5779c80`: 1,452 passed / 45 deselected. Closes three named deferrals (c1-2 seam, c1-3 `SO_EXCLUSIVEADDRUSE`, c1-4 CORS ordering). Status → ready-for-dev. |
| 2026-07-25 | Implemented on `feat/companion-c1-5-localhost-security-envelope`. New `security.py` (Host predicate + pure-ASGI middleware + `install_security`), wired inside the error middleware; `SO_EXCLUSIVEADDRUSE` on the Windows bind; the `lifespan_client` seam extended with `base_url` / `headers` / `bound_port` so all 149 pre-existing companion tests pass **unedited** while now flowing through the real envelope; 40 new security tests + 1 new server test. Three deferrals closed (c1-2 seam, c1-3 socket option, c1-4 CORS ordering — the last by the no-CORS ruling, not an ordering change); one new pre-existing flake characterised and recorded (`test_list_decks_with_strategy_field`, same-tick `created_at` tie broken by a random UUID). One documented, behaviour-identical deviation: the Windows branch is `sys.platform == "win32"` rather than AC 10's literal `os.name == "nt"`, because only the former is narrowed by mypy and CI type-checks on Linux. Gates green: ruff clean, `mypy src/` clean on both win32 and linux platforms, 1,493 passed / 45 deselected. Status → review. |

---
baseline_commit: b498ac5fb070d11ec3ab7c5fcfb25bf0097f796e
---

# Story c5-8: The one real-socket integration test

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created. -->

## Story

As a developer,
I want exactly one test that boots a real backend on a real port,
So that the seams which only fail in a real process are proven in a real process, and nothing else pays for sockets.

## The story in one paragraph

Seven stories built the channel entirely in-process; eight in-source comments and one sprint-status
line all point at this story as the place where it finally meets a real socket. c5-8 creates
`tests/integration/companion/test_live_backend.py` (the exact path SPINE:461 fixed), the ONE
`integration`-marked test in the whole feature that boots a real backend subprocess: ephemeral port,
real discovery file under an isolated `PLANESWALKER_DATA_DIR`, real `/health` identity match, real
ticket mint, real WebSocket upgrade (with the explicit `Origin` that `security.py:204` promised on
this story's behalf), a token-authenticated POST whose envelope arrives over the open socket, and a
mid-test restart where a caller holding a stale token gets `403`, re-reads `companion.json`, and
succeeds on the retry — the FR-12 shape, hand-rolled, because c6-1's client helper does not exist
yet and must not be anticipated. **This story writes no production code.** It also pays the three
deferred-work debts homed on it (explicit socket teardown, explicit `Origin`, and the vitest
`ephemeralPort()` TOCTOU fix — the one frontend touch, per the Q4 ruling). CI never runs this test
(`ci.yml` is `-m "not integration"` on ubuntu); the "passes on Windows" AC is discharged by the
local run on this machine, recorded in the Dev Agent Record.

## Acceptance Criteria

1. `tests/integration/companion/test_live_backend.py` exists — the exact path ARCHITECTURE-SPINE.md:461
   names — with module-level `pytestmark = pytest.mark.integration`, and it is the **only**
   integration-marked companion test and the only test anywhere that boots a real backend process
   (AD-10). `uv run pytest -m "not integration"` deselects it and still passes at the baseline
   count (2,770 passed / 1 skipped — verify at Task 0), proving the rest of the suite covers the
   channel logic without it.
2. The test boots the real backend as a **direct child process** per the Q1 ruling —
   `[sys.executable, "-m", "src.mcp_server", "companion", "--port", "0"]`, `cwd` = repo root —
   with `PLANESWALKER_DATA_DIR` set to a per-test temp directory in the **child's env** (and via
   `monkeypatch.setenv` in the test process itself, so `src.paths.data_dir()` and the leaf client
   resolve the same isolated dir). `--port 0` is a legal direct ephemeral request
   (server.py:167 binds it exactly once, no fallback retry). Child stdout+stderr go to a **file**
   in the temp dir, never a pipe (a filled pipe buffer blocks the child).
3. Readiness and the real discovery file are proven together per the Q2 ruling: the test polls
   (bounded deadline, ~30 s; poll interval ≤ 0.25 s; no bare sleeps as proof of anything) until
   `companion.json` exists and parses via `discovery.read_discovery()` — which never raises;
   `None` just means "not yet" — then asserts the record carries `{port, token, instance_id}`
   with a nonzero port (AD-4; the ephemeral port is *read from the file*, never parsed from
   stdout).
4. Real identity verification reuses the shipped leaf: `src.companion.client.live_instance()`
   (async, env already pointing at the isolated dir) returns a live record whose `instance_id`
   matches the file — the same one-implementation-both-callers path AD-3/story c1-8 built. No
   hand-rolled health probe.
5. Real ticket mint: `GET http://127.0.0.1:{port}/api/session` (httpx, `trust_env=False`,
   literal `127.0.0.1` — never `localhost`, which resolves `::1` first on Windows against an
   IPv4-only bind) returns `200 {"ticket": "<str>"}` with `Cache-Control: no-store`.
6. Real WebSocket upgrade with ticket consume: `websockets.connect` (dev dep, installed 16.1.1 —
   no new dependency) to `ws://127.0.0.1:{port}/ws?ticket={t}` with an **explicit
   `origin="http://127.0.0.1:{port}"`** — missing `Origin` is refused fail-closed (Q4 ruling of
   c5-3; security.py:204 names this story; dw:5459 paid). The connection is accepted.
7. Consume is proven with the acceptance/rejection pair the unit suite's discipline requires:
   presenting the **same** ticket on a second connect fails the handshake — every refusal is a
   byte-identical pre-accept 1008 that uvicorn renders as **HTTP 403 with no body**, so the
   assertion is `websockets.exceptions.InvalidStatus` with `exc.response.status_code == 403`,
   never a reason string — and a **fresh** ticket from a second mint succeeds (non-vacuity).
8. Real token-authenticated push: with the socket open, `POST /agent/events` carrying
   `Authorization: Bearer {token-from-companion.json}` and a minimal valid envelope
   (`{"kind": "active_deck_changed", "id": <hex>, "ts": <aware ISO>, "payload": {"deck_id": null}}`
   — `ts` must be timezone-aware, naive datetimes are refused) returns `200 {"clients": 1}`, and
   the same envelope arrives over the open socket within a bounded `recv` (kind and id
   round-trip). Delivered count, not connected count — they are the same thing here by c5-5's
   ruling.
9. The restart-mints-new-token retry case (FR-12, AD-8 shape, AD-10): the first backend is
   stopped (`terminate()` + `wait()` — a hard kill on Windows, which deliberately leaves the
   stale `companion.json` behind so the second boot exercises c1-8's reclaim path); a second
   backend boots in the **same** data dir and publishes a new `{port, token, instance_id}`; a
   caller holding the **stale** token POSTs to the **new** backend's port and receives
   `403 {"reason": "forbidden"}`; it re-reads `companion.json`, retries once with the fresh
   token, and receives `200`. The retry logic lives **inside the test** — c6-1's leaf-client
   push half does not exist and must not be started here (grep-verified: no retry/ingest code
   under `src/mcp_server/`).
10. Teardown is explicit and total (dw:5451's pattern inherited): the websocket client is closed
    by hand before the server is stopped; every subprocess is terminated **and waited** in
    fixture teardown/`finally` (an un-waited child holds the port and breaks Windows `tmp_path`
    cleanup); every await carries a bounded timeout; the fixture is safe to tear down at any
    failure point mid-test.
11. The test passes on **Windows** — this machine — and the run is recorded in the Dev Agent
    Record with its actual pass count. CI is explicitly out of scope: `ci.yml` runs
    `-m "not integration"` on ubuntu, so no CI change is made and none is claimed (noted for the
    C5 retro instead). The run command is scoped
    `uv run pytest tests/integration/companion/ -v` — a bare `-m integration` would also collect
    `test_list_decks_with_strategy_field`, the known twice-sighted flake homed on the retro.
12. Per the Q4 ruling, dw:5470 is paid: `ui/tests/devProxyRoundTrip.test.ts`'s `ephemeralPort()`
    probe-then-bind TOCTOU is removed. The ledger's proposed shape (`port: 0` + read the real port
    back off `vite.httpServer.address()`) does **not** work in the installed Vite — measured
    directly, `0` is treated as falsy/unset and every server falls back to the 5173 default. What
    shipped instead: a monotonic per-test port counter feeding `strictPort: false`, so Vite
    bind-and-retries on collision with no TOCTOU window, and the real bound port is still read
    back off `vite.httpServer.address()` (the file already did that for its return value) —
    **while keeping ports distinct per test**, now *asserted* via `recordOrigin()` rather than
    left as a property of a comment, which is load-bearing for the unrelated undici keep-alive
    ECONNRESET flake the file's own warning documents. Test-only change: no `ui/src` change, no
    bundle rebuild, no plugin mirror change.
13. The three c5-8-homed ledger entries are dispositioned in `deferred-work.md`: dw:5451
    (teardown pattern — paid by AC 10), dw:5459 (explicit Origin — paid by AC 6), dw:5470 (paid
    by AC 12 or re-homed per the ruling, with the reason written). The ledger's standing
    prediction that c5-8 "adds more real-socket tests to `devProxyRoundTrip.test.ts`" is
    corrected where dispositioned — c5-8's real-socket test is Python-side; that prediction is
    recorded as falsified, not silently fulfilled.
14. Task 0 greps `c5-8` across `src/ tests/ ui/ scripts/ _bmad-output/` and the Dev Agent Record
    enumerates every hit with a disposition. Fulfilled predictions are rewritten as shipped truth
    (prose-only, behaviour byte-identical): `security.py:204` ("c5-8's real client sets it
    explicitly" → it did), `tests/unit/companion/conftest.py:319-320` and `test_ws.py:15-16`
    ("no `tests/integration/companion/` exists" → it does now), `test_routes_agent_events.py:22`,
    `test_routes_active_deck.py:1126-1127`, `test_import_boundary.py:14-15` (boundary
    deliberately skips `tests/**` so this story may boot the real app — verify, don't touch).
    If backend prose changes, the plugin mirror is rebuilt and sha256-verified and the Python
    suite count is unchanged.
15. Gates all green: ruff + `ruff format`, mypy strict untouched (tests are mypy-exempt but
    ruff-covered), `uv run pytest -m "not integration"` at baseline, the new integration test
    green locally, `pre-commit run --all-files` clean; frontend `npm test` strictly ≥ baseline
    (1,868 / 69 files — verify at Task 0) if dw:5470 is paid, untouched otherwise; no new
    dependency in any group; `npm run gen:api` a no-op (no wire change).

## Tasks / Subtasks

- [x] Task 0 — Baseline and reconnaissance (AC: 1, 14, 15)
  - [x] Branch `feat/companion-c5-8-live-backend` off `feat/companion-c5` at `b498ac5`
  - [x] Verify baselines: Python `uv run pytest -m "not integration"` (expect 2,770 / 1 skipped);
        frontend `npm test` (expect 1,868 / 69 files); record both
  - [x] `grep -rn "c5-8" src tests ui scripts _bmad-output` — enumerate every hit with a
        disposition (Dev Notes carries the expected starting set)
  - [x] Read end-to-end before writing any code: `src/companion/app/server.py` (run sequence,
        `--port 0`, launch line), `src/companion/discovery.py` (record shape, never-raises
        reader), `src/companion/client.py` (`live_instance`, probe timeouts),
        `src/companion/app/ws.py` (ticket param, 1008 pre-accept), `src/companion/app/security.py`
        (Bearer parse, Origin rules), `scripts/cdp_harness.py::Companion` (the boot/teardown
        pattern to port — and the `uv run` grandchild trap it exists to solve),
        `tests/unit/companion/conftest.py` (the in-process seam this test deliberately leaves)
- [x] Task 1 — The process harness (AC: 2, 3, 10)
  - [x] `tests/integration/companion/` with an `__init__.py` (every sibling integration dir has
        one — verified), plus `test_live_backend.py` with `pytestmark = pytest.mark.integration`
        and a module docstring naming AD-10 and the exactly-one rule
  - [x] A boot helper/fixture: temp data dir, child env, `sys.executable -m src.mcp_server
        companion --port 0`, output to a log file, poll `read_discovery()` until a record appears
        (bounded ~30 s deadline; a dead-port probe takes ~2 s on Windows — budget for it),
        teardown = close sockets, `terminate()`, `wait()`, always, at any failure point
- [x] Task 2 — The channel walk (AC: 4–8; single test function per the Q3 ruling)
  - [x] `live_instance()` identity match (AC 4); ticket mint (AC 5); `websockets.connect` with
        explicit origin (AC 6); same-ticket refusal as `InvalidStatus` 403 + fresh-ticket
        acceptance (AC 7); Bearer POST → `{"clients": 1}` + bounded `recv` round-trip (AC 8)
- [x] Task 3 — Restart and the FR-12 retry (AC: 9)
  - [x] Stop backend one (terminate + wait); boot backend two in the same data dir; await its
        discovery record (new token, new instance_id); stale-token POST → 403 `forbidden`;
        re-read `companion.json`; retry once → 200. All inside the same single test function
- [x] Task 4 — Pay the ledger and reconcile prose (AC: 12, 13, 14)
  - [x] dw:5470 per the Q4 ruling: bind-then-read in `devProxyRoundTrip.test.ts`, ports stay
        distinct, full `npm test` green; record the before/after shape
  - [x] Disposition dw:5451, dw:5459, dw:5470 in `deferred-work.md`; correct the "adds tests to
        this exact file" prediction as falsified
  - [x] Rewrite the fulfilled c5-8 predictions as shipped truth (prose-only); rebuild + verify
        the plugin mirror only if backend files changed
- [x] Task 5 — Verification and gates (AC: 1, 11, 15)
  - [x] `uv run pytest tests/integration/companion/ -v` green on this Windows machine — paste the
        actual output into the Dev Agent Record (this is the AC-11 evidence; CI will never run it)
  - [x] `uv run pytest -m "not integration"` at baseline; ruff, mypy, `pre-commit run
        --all-files`; frontend suite if touched
  - [x] Set story status to `review` and STOP — Brad runs the three-layer review and raises the
        PR (standing rule; overrides any Task-7-style completion step)

### Review Findings

- [x] [Review][Patch] Fixture teardown swallows all but the first backend-stop exception [tests/integration/companion/test_live_backend.py:249-257]
- [x] [Review][Patch] `websockets.connect()`/`.close()` calls carry no explicit timeout, contradicting the module's "every await carries a bound" comment [tests/integration/companion/test_live_backend.py:92,310-312,318-321,359-362,367]
- [x] [Review][Patch] Phase 9 comment misattributes why `clients == 0` on the restarted backend [tests/integration/companion/test_live_backend.py:416-417]
- [x] [Review][Patch] AC 12's literal text doesn't match the shipped dw:5470 fix mechanism [c5-8-the-one-real-socket-integration-test.md, Acceptance Criteria #12]
- [x] [Review][Patch] Restart phase asserts token/instance_id changed but never that the port differed, while reusing the phase-3 httpx client across the restart [tests/integration/companion/test_live_backend.py:292,376-383]

## Dev Notes

### The wire contract you are exercising (all shipped — modify nothing)

| Thing | Value | Where |
|---|---|---|
| Boot | `python -m src.mcp_server companion --port 0`; `--port 0` binds ephemeral once, no retry | `src/mcp_server/__main__.py:192`, `src/companion/app/server.py:167` |
| Launch line (stdout) | `[planeswalker] companion running at http://127.0.0.1:{port} — …` — do **not** parse it; read the port from `companion.json` | `server.py:352-356` |
| Discovery | `{data_dir}/companion.json`, `{"port", "token", "instance_id"}`, atomic write, `read_discovery()` never raises | `src/companion/discovery.py:54,114,178` |
| Health | `GET /health` → `200 {"status":"ok","instance_id":…}`, unauthenticated | `app/routes/health.py` |
| Identity | `client.live_instance()` = read discovery → probe → instance_id must match; `trust_env=False`; ~5 s whole-probe deadline | `src/companion/client.py:167` |
| Ticket | `GET /api/session` → `200 {"ticket": …}`, `no-store`; TTL 30 s; single-use; popped on every presentation | `app/routes/session.py:73`, `app/state.py:163,351` |
| WS | `ws://127.0.0.1:{port}/ws?ticket={t}`; Origin validated in-route, **missing → reject**; every refusal = pre-accept 1008 → HTTP 403, no body, no reason | `app/ws.py:90,107,133,214`, `app/security.py:178` |
| Ingest | `POST /agent/events`, `Authorization: Bearer {token}`; wrong/missing → `403 {"reason":"forbidden"}` (the status FR-12's "auth rejection" means on the wire); success → `200 {"clients": N}` (delivered count; 0 is a success) | `app/routes/agent_events.py:64`, `app/security.py:309-479`, `app/errors.py:54` |
| Envelope | `{kind,id,ts,payload}`, `extra="forbid"`, `ts` **AwareDatetime**, ≤ 64 KB; simplest valid kind is `active_deck_changed` with `{"deck_id": null}` | `src/companion/contracts.py:500,1227` |
| Singleton | held advisory lock on `{data_dir}/companion.lock` (`msvcrt` on win32); isolated per `PLANESWALKER_DATA_DIR`, so the test never contends with a real companion | `app/singleton.py:65,97` |

### Scope boundary — what this story is NOT

- **No production code.** `src/` changes are prose-comment reconciliation only (AC 14). If you
  find yourself editing behaviour in `src/companion/`, stop — the channel is done.
- **Not c6-1.** The leaf client's push half (POST helper, retry-once, outcome vocabulary) is the
  next story. The FR-12 retry here is a hand-rolled sequence *inside the test function*.
  Grep-verified: nothing under `src/mcp_server/` does discovery-retry today. Do not create a
  helper module for it.
- **Not a fix for accepted residuals.** The broadcast overlap race (no per-connection lock) and
  the slow-client stall (no per-send timeout) were ruled acceptable in c5-4. If the real socket
  surfaces them, record — don't fix.
- **No CI change.** No Windows runner, no integration job. The AC-11 evidence is the local run.
- **No Playwright.** Browser E2E is explicitly deferred (SPINE, Deferred riders).
- **No new dependency.** `websockets` 16.1.1 is already in the dev group (declared for
  `scripts/cdp_harness.py`); `httpx` is a runtime dep.

### The pattern to copy (solved problems — do not invent)

- **`scripts/cdp_harness.py::Companion` (:242-307)** is the only existing boot-a-real-companion
  code: env with `PLANESWALKER_DATA_DIR`, output to a log file, poll `/health` until up, teardown
  that kills and then polls until down. Port its shape, with one deliberate difference (Q1
  ruling): the harness launches via `uv run`, which makes the server a **grandchild** and forces
  `taskkill /F /T` on Windows; this test launches `sys.executable -m src.mcp_server` so the child
  *is* the server and `terminate()`/`wait()` suffice cross-platform.
- **Readiness = the discovery file**, not stdout parsing and not a fixed sleep: poll
  `discovery.read_discovery()` (never raises) under a deadline, then `live_instance()` for the
  identity half. This makes AC 3 and AC 4 fall out of the wait itself.
- **The unit suite's pairing discipline** (`tests/unit/companion/` throughout): every rejection
  assertion pairs with an acceptance from the same call site. AC 7 is written that way — keep it.
- **`_Loopback`/`StubFleet`** (`tests/unit/companion/test_server.py:32`, `test_client.py:129`)
  show the house style for real sockets in fixtures: track everything opened, close everything at
  teardown, a leaked listener surfaces as a *later* test's failure.

### Landmines specific to this story

1. **`uv run` spawns a grandchild** that survives `terminate()`, holds the port *and* `cards.db`,
   and breaks the next run's temp-dir cleanup. Avoided entirely by Q1's `sys.executable -m`.
2. **Windows `tmp_path` cleanup fails if the child is alive** (or if AV/indexer holds a file) —
   `wait()` after every `terminate()`, no exceptions. `remove_discovery` and the discovery
   writer already swallow/raise the right things; your teardown must be equally paranoid.
3. **A TCP connect to a dead loopback port takes ~2 s to refuse on Windows** (measured, c1-8);
   a live `/health` answers in ~15 ms. Budget poll deadlines accordingly (30 s boot deadline is
   generous, not paranoid); never tighten a timeout to make a test faster.
4. **`localhost` resolves `::1` first on Windows** and the bind is IPv4-only — the literal
   `127.0.0.1` everywhere, matching `client.base_url()`.
5. **`websockets` ≥ 14 raises `InvalidStatus`** (with `.response.status_code`), not the legacy
   `InvalidStatusCode`. Installed: 16.1.1. Also: its `connect()` sends **no Origin by default** —
   pass `origin=` explicitly (the whole point of AC 6).
6. **Proactor loop is load-bearing**: `asyncio_mode = "auto"`, no loop policy is set anywhere in
   the repo, and Windows subprocess-with-pipes needs Proactor (the default). Don't set a
   Selector policy; also prefer sync `subprocess.Popen` (the cdp-harness shape) over asyncio
   subprocess to sidestep loop coupling entirely.
7. **The child's stdout must not be a pipe you never drain** — the launch line plus uvicorn/log
   lines can fill the buffer and block the server. Log file in the temp dir (cdp-harness shape),
   and on failure include its tail in the assertion message.
8. **A hard kill leaves `companion.json` behind — deliberately.** The second boot must reclaim
   it (dead-port probe → stale → reclaim, c1-8's path). Don't "helpfully" delete the stale file
   between boots; its survival is what makes the restart case honest.
9. **`--strict-markers` is on**: the `integration` marker is already registered in
   `pyproject.toml:100-102` — use it exactly, no new markers.
10. **Bare `-m integration` collects the known flake** `test_list_decks_with_strategy_field`
    (two sightings, homed on the C5 retro) plus Scryfall live-contract tests. All local runs in
    this story are scoped to `tests/integration/companion/`.
11. **jsdom/vitest side (only if paying dw:5470):** distinct ports per test in
    `devProxyRoundTrip.test.ts` are load-bearing for the undici keep-alive ECONNRESET flake —
    the fix removes the probe, not the distinctness. That file is "the only place a real
    listener is sanctioned" in the frontend; keep it that way.

### Grep-own-key: expected `c5-8` hits and their dispositions (verify at Task 0)

| Location | Claim | Disposition after this story |
|---|---|---|
| `src/companion/app/security.py:204` | "c5-8's real client sets it explicitly" | Fulfilled — rewrite as shipped truth |
| `tests/unit/companion/conftest.py:319-320` | "this file must not grow one" | Still true — reconcile tense ("the one genuine proof lives in tests/integration/companion/") |
| `tests/unit/companion/test_ws.py:15-16, :306` | "no `tests/integration/companion/` exists" | Now false — rewrite |
| `tests/unit/companion/test_routes_agent_events.py:22` | "The one real-socket proof is c5-8's" | Fulfilled — rewrite |
| `tests/unit/companion/test_routes_active_deck.py:1126-1127` | "real-socket version is c5-8's" | Fulfilled — rewrite |
| `tests/unit/companion/test_import_boundary.py:14-15` | "`tests/**` not scanned so c5-8 may boot the app" | Verify it held; do not touch |
| `ui/tests/devProxyRoundTrip.test.ts` | TOCTOU home + "c5-8 works in this file" | Per Q4 ruling; prediction corrected |
| `deferred-work.md:5451,5459,5470` | three homes | Dispositioned (AC 13) |
| `sprint-status.yaml:605,614` | tracking | Status flip at story end |

### Previous-story intelligence (c5-5 → c5-7, reviewed + merged)

- **The standing review theme across three stories: defects live in the guard layer.** c5-5's
  byte-identical-refusal test passed under the exact planted failure it was written to catch;
  c5-7's P15 planted a wrong-token swap and 1,866 tests stayed green because jsdom evaluates no
  stylesheet. For THIS story that means: before trusting the restart case green, plant one
  falsification by hand (e.g. retry with the stale token instead of the fresh one) and watch it
  actually go red. A real-socket test that cannot fail is worse than none.
- **c5-6's review bug** was an ordering gap (`fail()` skipping `schedule()` when a callback
  threw) — the reconnect loop could silently halt. The lesson generalises to teardown code:
  every step of your `finally` must run even when the previous one raised.
- **c5-7's Greptile P1**: a positional claim verified only by bounding box; fixed after checking
  in a real browser. This story is the backend twin of that lesson — the whole point of AD-10 is
  that some claims are only true in a real process.
- **Baselines c5-7 left**: frontend 1,868 / 69 files; Python 2,770 / 1 skipped
  (`-m "not integration"`); bundle `index-4i3k0aJS.js` / `index-D0jCbtgu.css`; `gen:api` no-op.
  This story should move the Python integration count by exactly the new test and nothing else.
- **The subprocess-from-lowercase-drive-letter trap** (c5-6, dw:5079 still open): an `npm test`
  child launched from `c:\…` resolves no vitest config on Windows and every probe reads RED for
  the wrong reason. Normalise `C:` before scoring any frontend probe run in Task 4.

### Project structure notes

- New: `tests/integration/companion/test_live_backend.py` (SPINE-fixed name; new directory —
  sibling dirs `data/`, `logic/`, `mcp_server/`, `search/` each carry an `__init__.py`, match
  them).
- `tests/integration/conftest.py` has DB fixtures only and **no data-dir isolation** — the
  autouse `PLANESWALKER_DATA_DIR` fixture is scoped to `tests/unit/companion/` and does NOT
  cover this test. Own your isolation locally (fixture in the new file, or a tiny local
  conftest); do not widen the unit conftest and do not add companion fixtures to the shared
  integration conftest (nothing else there needs them).
- Modified (test/prose only): `tests/unit/companion/{test_ws,test_routes_agent_events,test_routes_active_deck,conftest}.py`
  comment reconciliation, `src/companion/app/security.py` docstring line,
  `ui/tests/devProxyRoundTrip.test.ts` (Q4), `deferred-work.md`, `sprint-status.yaml`,
  `epics-companion-app.md` only if a prediction there needs the shipped-truth treatment.
- Tests are mypy-exempt but ruff-covered (line length 100, isort, pep8-naming). Google-style
  docstring on the test module; the module docstring is the right home for the AD-10
  exactly-one rule.

### References

- Epic ACs: `_bmad-output/planning-artifacts/epics-companion-app.md:2628-2659` (Story 5.8);
  Epic 5 header `:2374-2379`
- AD-10: `_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md:227-240`;
  target path `:461`; Playwright deferred `:494`
- AD-4 (discovery/rendezvous): SPINE `:127-141`; AD-5 (two credentials): `:143-157`;
  AD-2 (why "passes on Windows" is the AC): `:101-112`; AD-8 (retry-once shape): `:197-209`
- FR-12 / FR-14 / FR-06: `_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md:146,103,126`
- Deferred debts: `_bmad-output/implementation-artifacts/deferred-work.md:5451-5498`
- Boot pattern: `scripts/cdp_harness.py:242-307`; marker config: `pyproject.toml:96-107`;
  CI scope: `.github/workflows/ci.yml:71`

## Open questions for Brad (recommendations first — rule before code)

1. **Boot mechanism.** Recommend `[sys.executable, "-m", "src.mcp_server", "companion",
   "--port", "0"]` as a direct child (terminate/wait works everywhere), NOT the cdp-harness's
   `uv run artificial-planeswalker …` (grandchild → `taskkill /F /T` → fragile teardown in a
   test that must never leak a process). The console-script dispatch path loses one layer of
   coverage (`[project.scripts]` wiring), which `test_server.py` already covers in-process.
2. **Readiness signal.** Recommend polling `discovery.read_discovery()` + `live_instance()`
   (readiness IS two of the ACs), never stdout parsing — the launch line's em dash and cp437
   consoles are exactly the kind of Windows papercut this story shouldn't re-litigate.
3. **One test function or several?** Recommend ONE `async def test_…` walking boot → channel →
   restart → retry sequentially. AC 1's "exactly one" count stays unambiguous (a module of five
   functions each booting processes reads as five), and the restart case needs the first
   backend's corpse anyway. Cost: a long function; mitigate with phase comments, not splitting.
4. **dw:5470 (vitest `ephemeralPort` TOCTOU) — pay here or re-home?** Recommend pay here: the
   ledger homes it here, the fix shape is fully specified, it is test-only, and the alternative
   is a fourth home for a twice-fired intermittent. But note the homing rested on a falsified
   premise (that c5-8 would add tests to that file) — re-homing to the C5 retro with that reason
   written is a legitimate ruling if you'd rather keep this story pure-Python.
5. **Identity check via the leaf.** Recommend reusing `src.companion.client.live_instance()`
   verbatim (AD-3's one-implementation rule; it is also what c6-1 will build on) rather than a
   hand-rolled httpx probe. Cost: the test's env must be set in-process too (monkeypatch), which
   Task 1 does anyway.
6. **Windows evidence.** Recommend: the AC-11 "passes on Windows" evidence is the pasted local
   run in the Dev Agent Record, no CI change this story, and a one-line note filed for the C5
   retro on whether a Windows integration lane is ever worth its minutes.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context), via Claude Code / BMad `dev-story`.

### Debug Log References

**All six open questions ruled by Brad AS RECOMMENDED, before any code** (2026-08-09) — the fourth
story running with a clean pre-code sweep. Q4 was the only genuinely open one and was ruled *pay
dw:5470 here*.

**Baselines verified at Task 0**, both matching the story's stated figures: Python **2,770 passed /
1 skipped** (`-m "not integration"`, 54 deselected); frontend **1,868 passed / 69 files**.

#### AC 11 — the Windows evidence (CI will never produce this)

```
$ uv run pytest tests/integration/companion/ -v
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\brads\Projects\Artificial-Planeswalker
configfile: pyproject.toml
plugins: anyio-4.11.0, asyncio-1.2.0, cov-7.0.0
asyncio: mode=Mode.AUTO
collecting ... collected 1 item

tests/integration/companion/test_live_backend.py::test_the_real_channel_end_to_end PASSED [100%]

============================== 1 passed in 5.09s ==============================
```

Two real backend processes, an ephemeral port each, a real WebSocket handshake and a real restart,
in **5.09 s**. Scoped to `tests/integration/companion/` deliberately: a bare `-m integration` also
collects the twice-sighted `test_list_decks_with_strategy_field` flake and the live Scryfall
contract tests.

#### AC 1 — the deselection proof, and the number that moved

`uv run pytest -m "not integration"` → **2,770 passed / 1 skipped / 55 deselected**. The passed
count is byte-identical to the baseline and **deselected moved 54 → 55**: exactly this test and
nothing else. That is the claim AC 1 actually makes — the rest of the suite covers the channel
logic without this test, and this test did not quietly become load-bearing for anything.

#### Grep-own-key: every `c5-8` hit, dispositioned

| Location | Claim before | Disposition |
| --- | --- | --- |
| `src/companion/app/security.py:204` | "c5-8's real client sets it explicitly" | **Fulfilled and MEASURED** — rewritten; probe F2 confirmed the rule fires over a real socket |
| `tests/unit/companion/test_ws.py:16` | "no `tests/integration/companion/` exists" | **Now false** — rewritten; the directory exists and holds exactly one test |
| `tests/unit/companion/test_ws.py:306` | "c5-8's client sets it explicitly" | Fulfilled — rewritten with the probe result |
| `tests/unit/companion/conftest.py:320` | "the one proof is c5-8's, and this file must not grow one" | Tense reconciled; **the rule is unchanged** and says so |
| `tests/unit/companion/test_routes_agent_events.py:22` | "The one real-socket proof is c5-8's" | Fulfilled — rewritten, naming what the real socket adds (the FR-12 restart no in-process test can stage) |
| `tests/unit/companion/test_routes_active_deck.py:1126` | "the real-socket version is c5-8's" | Fulfilled — rewritten **with a narrowing recorded**: c5-8 drives ONE socket, not two; the two-tab claim stays in-process |
| `tests/unit/companion/test_import_boundary.py:15` | "`tests/**` not scanned so c5-8 may boot the app" | **Verified, not touched** — the exemption held with no edit, and the file now says so |
| `ui/tests/devProxyRoundTrip.test.ts:272` | "what c5-8's real client will have to do" | Fulfilled — rewritten |
| `deferred-work.md:5451 / 5459 / 5470` | three homes | All three **PAID** (AC 13) |

#### Falsification probes — 7 planted, 7 RED

The story's own Dev Notes demanded at least one: *"a real-socket test that cannot fail is worse
than none."* Each probe planted one change, ran the real test against real backends, and was
reverted from the staged file.

| # | Planted | RED | What it proves |
| --- | --- | --- | --- |
| F1 | Phase 9 retries with the **stale** token | ✓ | The FR-12 retry is really the re-read token; got `403 {"reason":"forbidden"}` |
| F2 | Drop the explicit `origin=` from the first upgrade | ✓ | **dw:5459 is load-bearing** — real handshake refused `HTTP 403` |
| F3 | Phase 7 reuses the **spent** ticket | ✓ | The fresh-ticket acceptance is not vacuous |
| F4 | Compare the delivered id against a different id | ✓ | The socket round-trip is really compared |
| F5 | Phase 8 waits on file **presence** alone | ✓ | **The most valuable one** — see below |
| F6 | Boot a module that does not exist | ✓ | Dead-child detection fires in 0.45 s instead of burning the 30 s deadline |
| F7 | Assert the same ticket is accepted twice | ✓ | The ticket really is consumed on presentation |

**F5 is the finding worth keeping.** Removing `replacing=record_one.instance_id` from the second
boot's wait made `_await_record` return the **corpse's** record — same `instance_id` *and the same
port* (`53623` both times) — and the run went red on the next assertion. That is the proof that a
hard kill genuinely leaves `companion.json` behind, that the second backend really does walk
c1-8's reclaim path, and that waiting on file presence alone would have made the entire restart
case vacuous while still passing.

#### dw:5470 — the fix shape in the ledger was wrong, and was re-measured

The ledger proposed *"let Vite bind port 0 and read the real port back off
`vite.httpServer.address()`"*. **That does not work in the installed Vite**, measured directly by
starting two servers with `{ port: 0, strictPort: true }`: the falsy `0` is treated as unset, both
fall back to the 5173 default, and the second died with *"Port 5173 is already in use"*. The
file's own original comment was right and the ledger's suggested fix was wrong.

What shipped instead is the ledger's *other* suggestion — retry the bind: a monotonic counter
supplies a distinct starting port and `strictPort: false` lets Vite bind-and-retry on EADDRINUSE,
one atomic step with no window. Distinctness (load-bearing for the unrelated undici keep-alive
ECONNRESET flake) is preserved **and is now asserted** by `recordOrigin()` — it had been a property
of a comment. Verified: that file green **5/5 consecutive runs**, full frontend suite green.

#### Not done, and why

- **No CI change**, and this is now a recorded gap rather than a silence: `ci.yml` is
  `-m "not integration"` on ubuntu, so the only test covering the process boundary has no
  automated home and will rot silently if it ever breaks. Filed for the C5 retro (severity
  medium) rather than fixed here, per the Q6 ruling.
- **No production code.** `src/companion/app/security.py` is a docstring edit; the Python count is
  byte-identical and the plugin mirror is sha256-verified.
- **No new dependency**: `websockets` 16.1.1 was already in the dev group, `httpx` is a runtime dep.

### Completion Notes List

- **`tests/integration/companion/test_live_backend.py`** — the ONE `integration`-marked test that
  boots a real backend, at the exact path `ARCHITECTURE-SPINE.md:461` fixed. One `async def`
  walking nine phases (Q3): boot → identity → ticket → upgrade → consume → push → fresh-ticket →
  restart → FR-12 retry.
- **Boot is a direct child** (Q1): `sys.executable -m src.mcp_server companion --port 0`, so
  `terminate()` + `wait()` is sufficient on every platform. The `cdp_harness` `uv run` shape makes
  the server a *grandchild* and needs `taskkill /F /T`; that trap is documented in the module
  header rather than inherited.
- **Readiness is the discovery file** (Q2), never stdout: `read_discovery()` never raises, so the
  wait is a plain poll under a bounded deadline, and AC 3 + AC 4 fall out of the wait itself.
- **Identity reuses the shipped leaf** (Q5): `client.live_instance()`, not a hand-rolled probe —
  AD-3's one-implementation rule, and the path c6-1 builds on.
- **The FR-12 retry is hand-rolled inside the test**, deliberately: c6-1 owns the leaf-client push
  half, and building it here would be building it twice. Grep-verified that nothing under
  `src/mcp_server/` does discovery-retry today.
- **Teardown is total**: handles are detached before `terminate()`/`wait()` so a raising `wait()`
  cannot skip the log close (c5-6's review lesson applied to teardown), every backend is stopped
  even if an earlier stop raised, and the websocket is closed by hand before the server dies.
- **AC 8's `clients == 1` is ordering-safe on purpose**: the fresh-ticket acceptance half of AC 7
  is deferred to *after* the POST, so a second socket opened-and-closed cannot race its own
  disconnect against the delivered count.
- **Gates all green**: integration test green on Windows (evidence above); Python 2,770 / 1 skipped
  (55 deselected); frontend 1,868 / 69 files; ruff + `ruff format`, mypy strict, eslint, stylelint,
  prettier, `tsc -b --force`, `pre-commit run --all-files` all clean; `npm run gen:api` a genuine
  no-op (zero diff under `ui/src/api`); no bundle rebuild and no `ui/src` change, as AC 12 requires.

### File List

**New**

- `tests/integration/companion/__init__.py`
- `tests/integration/companion/test_live_backend.py`

**Modified — test-only (dw:5470)**

- `ui/tests/devProxyRoundTrip.test.ts`

**Modified — prose only (comments/docstrings)**

- `src/companion/app/security.py`
- `tests/unit/companion/conftest.py`
- `tests/unit/companion/test_ws.py`
- `tests/unit/companion/test_routes_agent_events.py`
- `tests/unit/companion/test_routes_active_deck.py`
- `tests/unit/companion/test_import_boundary.py`

**Modified — artefacts and tracking**

- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/c5-8-the-one-real-socket-integration-test.md`

**Rebuilt (mechanical)**

- `plugin/server/src/companion/app/security.py` (mirror, sha256-verified against `src/`)

## Change Log

| Date | Change |
| --- | --- |
| 2026-08-09 | Story implemented. All 6 open questions ruled as recommended before code. The one real-socket integration test ships at `tests/integration/companion/test_live_backend.py` — two real backends, ephemeral ports, real WS handshake, real restart, FR-12 retry — passing on Windows in 5.09 s. No production code. dw:5451, dw:5459 and dw:5470 all PAID, with two falsified premises recorded (c5-8 adds no tests to `devProxyRoundTrip.test.ts`; the ledger's `port: 0` fix shape does not work in the installed Vite). 7 falsification probes, all RED — F5 proved the restart wait would have been vacuous without its `replacing=` guard. Python 2,770 / 1 skipped unchanged, deselected 54 → 55; frontend 1,868 / 69 unchanged. Status → `review`. |

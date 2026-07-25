---
baseline_commit: a7e1355
epic: c1
story: c1-3
work_branch: feat/companion-app
story_branch: feat/companion-c1-3-port-selection-ephemeral-fallback
---

# Story C1.3: Port selection with ephemeral fallback and a printed launch URL

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad launching the companion,
I want the backend to take port 8765 when it is free and quietly pick another when it is not,
so that a port conflict never blocks me and I always know from the terminal where to point my browser.

**Why this story is third.** c1-2 built an app object that cannot serve itself. This story is the
first code with a real external effect: it opens a socket. It also settles the single fact four
later stories all depend on — **where the bound port is readable from** — because c1-5 validates
`Host` against it, c1-7 writes it into the discovery file, c1-8 probes it, and c1-9 launches
through it. Get the seam wrong here and four stories inherit the mistake.

## Acceptance Criteria

1. **The default bind attempt is `127.0.0.1:8765` (FR-01, NFR-01).** `src/companion/app/server.py`
   holds `HOST = "127.0.0.1"` and `DEFAULT_PORT = 8765` and binds an `AF_INET` socket to that pair
   when the port is free. The host is a **module constant, never a parameter** — a configurable
   bind address would make NFR-01 a suggestion. `0.0.0.0`, `::`, `""` and `localhost` appear
   nowhere as a bind target.

2. **A conflict falls back to an ephemeral port, never an exit (FR-01).** When the preferred port
   cannot be bound, the code binds `("127.0.0.1", 0)` instead and continues. The fallback triggers
   on **any** `OSError`, not only `EADDRINUSE` — see Gotcha 3 (Windows reserves port ranges and
   raises `WSAEACCES`, a different errno). Only a failure of the *ephemeral* bind propagates.

3. **An explicitly configured port is attempted first, with the same fallback.** Precedence:
   `run(port=…)` argument → `PLANESWALKER_COMPANION_PORT` env var → `DEFAULT_PORT`. A value from
   **either** source that is not an integer in `0..65535` is **ignored with a logged warning** and
   the default is used — a typo'd env var must not stop the launch, and c1-9 will feed a
   user-supplied `--port` through the same argument, so the two must validate identically. `0` is a
   legal configured value meaning "go straight to ephemeral".

4. **The actual bound port is readable from application state (AD-4).** After the bind,
   `app.state.bound_port` holds the integer the socket actually got, and
   `src.companion.app.main.bound_port(app) -> int | None` returns it (`None` before any bind). This
   is the single accessor c1-5 and c1-7 use; see Decide-once #2.

5. **Nothing else in the codebase hardcodes 8765 (AD-4).** A test scans every `*.py` under `src/`
   and `scripts/` for the literal `8765` and fails on any occurrence outside
   `src/companion/app/server.py`. (`tests/` and the generated `plugin/` mirror are out of scope —
   the test itself must name the number, and `plugin/` is a verbatim copy of `src/`.)

6. **The reachable URL is printed to stdout (AD-15).** Before serving, the runner prints, to
   **stdout** and flushed:

   ```text
   [planeswalker] companion running at http://127.0.0.1:{port} — open this URL in your browser (Ctrl-C to stop)
   ```

   and, **only when the preferred port was unavailable**, an additional preceding line:

   ```text
   [planeswalker] port {preferred} is unavailable — falling back to an ephemeral port
   ```

   The URL always carries the **actual** bound port and the literal host `127.0.0.1` (not
   `localhost` — see Gotcha 5). `print()` is correct here and `logger.info` is not; see
   Decide-once #3.

7. **The socket is bound by the runner, before uvicorn serves it.** `run()` binds the socket
   itself and hands it to uvicorn as `uvicorn.Server(...).run(sockets=[sock])`. Letting uvicorn
   bind is **wrong and must not be done**: `Server.startup()` calls `await self.lifespan.startup()`
   *before* it creates any listener, so a lifespan that needs the port — c1-7's discovery-file
   write — would run before the port exists. See Decide-once #1, which carries the verified
   evidence.

8. **`build_app()` stays inert (AD-10).** The socket work lives in `server.py`, never in `main.py`,
   and importing `src.companion.app.main` still imports no uvicorn and binds nothing. c1-2's
   `TestConstructionIsInert` (which monkeypatches `socket.socket.bind` to raise, then fresh-imports
   `main`) passes **unmodified**. `main.py`'s only change is the `bound_port` accessor from AC 4.

9. **The socket is never leaked.** If anything between the bind and the return of `run()` raises,
   the socket is closed (`try/finally`). Double-close is harmless — uvicorn's `shutdown()` already
   closes the sockets it was handed.

10. **uvicorn is configured for exactly this process.** `workers` stays at the default `1` (in-memory
    state under AD-5 cannot be fragmented across processes, and uvicorn's multi-worker path
    re-shares the socket on Windows), and `lifespan="on"` is set explicitly so a lifespan failure is
    loud rather than silently skipped — c1-7's discovery-file write must never be quietly bypassed.

11. **Tests bind real loopback sockets, and never port 8765.** The conflict and fallback cases are
    proven against genuinely occupied ports (a helper binds `("127.0.0.1", 0)` and passes that port
    in as the preferred one), because mocking `bind` to raise would prove only that an exception is
    caught. Tests **never bind `DEFAULT_PORT`** — a dev or a parallel CI job with 8765 in use would
    otherwise get flakes. Every test socket is closed by a fixture. These are **unmarked unit
    tests**: AD-10 reserves the one `integration`-marked test that *boots a backend* for a later
    story, and opening a loopback socket is not booting a backend.

12. **uvicorn is declared where mypy needs it.** `uvicorn>=0.51.0` is added to
    `.pre-commit-config.yaml`'s mypy `additional_dependencies` — c1-2 deliberately left it out
    because no `src/` module imported uvicorn yet, and homed the addition on this story. No
    `pyproject.toml` or `uv.lock` change: `uvicorn[standard]>=0.51.0` is already a dependency.

13. **Quality gates green (NFR-07).** `uv run ruff check .`, `uv run ruff format --check .`,
    `uv run mypy src/` and `uv run pytest -m "not integration"` all pass with **no new failures**
    against the 1,373-test baseline. Actual output pasted into the Debug Log.

14. **Plugin mirror rebuilt and committed.** `uv run python -m scripts.build_plugin`, then commit
    `plugin/`; `git status --porcelain -- plugin/` clean afterwards. `src/` is copied wholesale, so
    the new `server.py` and the `main.py` edit both land in `plugin/server/src/`.

15. **Manual smoke, recorded not committed.** Start the backend for real
    (`uv run python -c "from src.companion.app.server import run; run()"`), confirm the printed URL,
    `GET /health` against it, then Ctrl-C. Repeat with that port occupied to observe the fallback
    line. Paste the observed stdout into the Debug Log. **Do not commit this as a test** — AD-10's
    single real-backend integration test belongs to a later story.

16. **Scope boundary — what this story must NOT do.** No CLI wiring, no `[project.scripts]` change,
    no subcommand dispatcher (c1-9). No discovery file, no token, no `instance_id` verification
    (c1-7, c1-8). No `Host` middleware, no CORS (c1-5). No database engine or `deps.py` (c1-6). No
    error contract (c1-4). No root-logger configuration (see Open question 2). No edit to
    `tests/unit/companion/test_import_boundary.py`, `tests/unit/companion/test_app.py`,
    `.github/workflows/ci.yml`, `pyproject.toml` or `uv.lock`.

## Tasks / Subtasks

- [x] **Task 0 — State verification** (standing team agreement since the epic-6 retro: any story
      whose notes assert repository state opens with the cheap check that proves it)
  - [x] Create `feat/companion-c1-3-port-selection-ephemeral-fallback` **off `feat/companion-app`**
        (currently at `a7e1355`, the merge of PR #10); the story PR targets `feat/companion-app`.
  - [x] Confirm `src/companion/app/server.py` does **not** exist and `src/companion/app/main.py`
        does.
  - [x] Confirm `uvicorn` is importable but unused by `src/`:
        `uv run python -c "import uvicorn; print(uvicorn.__version__)"` → `0.51.0`, and
        `grep -rn "uvicorn" src/` returns nothing.
  - [x] Baseline the suite: `uv run pytest -m "not integration" -q` → expected **1,373 passed, 45
        deselected**. Record any delta rather than chasing it.

- [x] **Task 1 — Port resolution** (AC: 1, 3)
  - [x] `src/companion/app/server.py` — module docstring covering: this is the process runner
        (AD-15), the bind happens **here** and not in uvicorn (AD-10 + Decide-once #1), and the host
        is fixed at `127.0.0.1` (NFR-01). Module-level `logger = logging.getLogger(__name__)`.
  - [x] Constants `HOST = "127.0.0.1"`, `DEFAULT_PORT = 8765`,
        `PORT_ENV_VAR = "PLANESWALKER_COMPANION_PORT"`.
  - [x] `resolve_preferred_port(explicit: int | None = None) -> int` — argument, then env var, then
        default; a non-integer or out-of-range env value logs a warning (`%`-style lazy args) and
        returns the default.

- [x] **Task 2 — The bind** (AC: 1, 2, 9)
  - [x] `bind_localhost_socket(preferred: int) -> socket.socket` — tries `(HOST, preferred)`, and on
        **any** `OSError` closes that socket and binds `(HOST, 0)`. Never calls `listen()` —
        `loop.create_server(sock=…)` does that (matching uvicorn's own `bind_socket`).
  - [x] `SO_REUSEADDR` is set **on POSIX only** — never on Windows. Mirror asyncio's own policy
        (`base_events.create_server` sets it only when `os.name == "posix"`); see Gotcha 2 for why
        setting it on Windows would silently break AC 2.
  - [x] Every failed bind closes its socket before the next attempt.

- [x] **Task 3 — State accessor** (AC: 4, 8)
  - [x] `src/companion/app/main.py` — add `bound_port(app: FastAPI) -> int | None` reading
        `app.state.bound_port` with a `getattr(..., None)` default, matching c1-2's
        absence-means-not-started convention for `instance_id`. Google docstring naming c1-5 and
        c1-7 as the callers.
  - [x] mypy: `app.state` reads as `Any` and `warn_return_any = true` is on — assign to an
        annotated local (`port: int | None = getattr(...)`) and return that, or `cast`. Do **not**
        `return getattr(...)` directly.
  - [x] Do not touch `build_app()` beyond nothing at all — it must stay byte-identical in behaviour.

- [x] **Task 4 — The runner** (AC: 6, 7, 9, 10)
  - [x] `run(port: int | None = None) -> None` — resolve → bind → read `sock.getsockname()[1]` →
        `build_app()` → set `app.state.bound_port` → print (AC 6) → serve, all inside
        `try/finally: sock.close()`.
  - [x] Serving goes through a small module-level `_serve(app, sock, port) -> None` seam that builds
        `uvicorn.Config(app, host=HOST, port=port, lifespan="on")` and calls
        `uvicorn.Server(config).run(sockets=[sock])`. Tests monkeypatch `_serve`; nothing in the
        unit suite starts a server.
  - [x] `build_app()` is imported at module level here — `server.py` lives under
        `src/companion/app/`, so the AD-3 outside-app rule does not apply to it.

- [x] **Task 5 — Tests** (AC: 1–11)
  - [x] `tests/unit/companion/test_server.py`, with a fixture that yields a helper for binding
        throwaway loopback sockets and closes them all at teardown.
  - [x] Resolution: default when unset; env var honoured; `run(port=…)` beats the env var;
        non-integer, negative and `>65535` env values fall back to the default **and log a warning**.
  - [x] Bind: free port → that exact port; **occupied** port (bound by the fixture) → a *different*,
        non-zero port; `preferred=0` → an ephemeral port with no fallback message; bound address is
        `127.0.0.1`; the returned socket is `AF_INET`/`SOCK_STREAM`.
  - [x] `run()` with `_serve` monkeypatched: `app.state.bound_port` equals the socket's real port,
        `main.bound_port(app)` returns the same, the URL line lands on **stdout** (`capsys`) with
        the actual port, the fallback line appears only in the conflict case, and the socket is
        closed after `run()` returns (`sock.fileno() == -1`).
  - [x] Failure path: `_serve` raising still closes the socket.
  - [x] AC 5 guard: scan `src/**/*.py` + `scripts/**/*.py` for `8765`; only `server.py` may contain
        it. Assert the scan is non-vacuous (it must find at least the one legal occurrence) —
        c1-1's dead-guard lesson.
  - [x] AC 1 guard: no `0.0.0.0` / `::` bind target anywhere under `src/companion/`.
  - [x] `main.bound_port()` returns `None` for a freshly constructed app.

- [x] **Task 6 — Declaration sites, gates and mirror** (AC: 12, 13, 14, 15, 16)
  - [x] Add `uvicorn>=0.51.0` to `.pre-commit-config.yaml` mypy `additional_dependencies`.
  - [x] `uv run ruff check . --fix` · `uv run ruff format .` · `uv run mypy src/` ·
        `uv run pytest -m "not integration"` — paste actual counts into the Debug Log.
  - [x] `uv run pre-commit run mypy --all-files` once, to prove the hook resolves uvicorn now.
  - [x] Manual smoke per AC 15; paste the observed stdout.
  - [x] `uv run python -m scripts.build_plugin`, `git add plugin/`, verify
        `git status --porcelain -- plugin/` is clean after the commit.
  - [x] Confirm `test_import_boundary.py`, `test_app.py`, `ci.yml`, `pyproject.toml` and `uv.lock`
        are untouched (AC 16).

## Dev Notes

### Decide-once rulings (made here so later stories inherit them)

**#1 — The runner binds the socket; uvicorn is handed it. This is not a style choice.**
Verified against the installed uvicorn 0.51.0 (`.venv/Lib/site-packages/uvicorn/server.py:103-144`):

```python
async def startup(self, sockets: list[socket.socket] | None = None) -> None:
    await self.lifespan.startup()          # line 104 — lifespan FIRST
    ...
    if sockets is not None:                # line 123 — listeners created SECOND
        for sock in sockets: ...
```

If uvicorn binds (the `host`/`port` path), the port is not knowable until *after* lifespan startup
has already run — so c1-7's discovery-file write, which the spine explicitly homes in the lifespan
(AD-4, AD-10), would have no port to write. Pre-binding and passing `sockets=[sock]` inverts the
order and is the only arrangement in which AD-4 and AD-10 are simultaneously satisfiable. Two
consequences worth knowing: uvicorn skips its own *"Uvicorn running on …"* banner when it is handed
sockets (`server.py:186-191`), which is why AC 6's print is the only launch line; and
`Server.shutdown(sockets=…)` closes what it was given, so AC 9's `finally` is belt-and-braces, not
a double-free.

**#2 — `app.state.bound_port`, read through `main.bound_port(app)`.** Absence means *not bound*,
exactly as c1-2 made absence of `instance_id` mean *not started* — no sentinel is written by
`build_app()`, so a constructed-but-never-run app cannot masquerade as a serving one. The accessor
lives in `main.py`, **not** `server.py`, so c1-5's `Host` middleware and c1-7's discovery writer
reach the port without importing the process runner (and with it uvicorn) from inside a request
path. In unit tests, later stories set `app.state.bound_port = <int>` by hand; that is the intended
seam and needs no helper.

**#3 — The launch URL is `print()`ed, not logged.** Two reasons, and the second is the load-bearing
one. (a) AC 6 says stdout; Python's `logging` writes to **stderr** by default. (b) Nothing
configures a root handler in this process — uvicorn's `LOGGING_CONFIG` configures only the
`uvicorn*` loggers — so a `logger.info("…")` from `src.companion.app.server` would propagate to a
handler-less root and be **dropped entirely** (`logging.lastResort` only surfaces `WARNING`+). The
URL is the single thing the user must see; it cannot depend on logging configuration that no story
has yet written. Precedent: `src/mcp_server/__main__.py` prints its diagnostics directly, and ruff's
selected rule sets (`E, F, I, N, W, UP`) do not include `T20`, so `print` is not lint-banned. The
`[planeswalker]` prefix matches that file's convention. Everything *else* in `src/companion` stays
on module-level `logging` with `%`-style lazy args.

**#4 — `127.0.0.1` in the printed URL, never `localhost`.** The socket is `AF_INET`-only by NFR-01,
so `::1` is not served; `localhost` resolves to `::1` first on Windows and modern Linux, leaving the
browser to Happy-Eyeballs its way back to IPv4 after a refused connection. Printing the literal IP
removes a failure mode that would present as "the URL doesn't work" with no diagnosable cause. The
UX docs' prose `localhost:8765` (EXPERIENCE.md:19) describes where Brad *is*, not what the terminal
must emit; c1-5 will accept **both** `Host` values, which is where the equivalence belongs.

### Architecture rules this story implements

- **FR-01 / AD-4** — default 8765, ephemeral fallback, and the pin that *nothing* else hardcodes
  the number. AC 5 turns that pin into an executable test rather than a convention.
- **NFR-01** — `127.0.0.1` only. Bound as a constant, not a parameter, and guarded by a source scan.
- **AD-10** — construction stays inert; the socket is the first external effect and it lives in the
  runner. c1-2's inertness tests are the regression surface: they must pass untouched.
- **AD-15** — the companion process owns its stdout, unlike the MCP process, which must keep stdout
  clean for JSON-RPC. This story is where that inversion first becomes visible.
- **AD-5 (forward-looking)** — `workers=1` is not a default to leave to chance: active deck,
  connections and tickets live in backend memory, and a second worker would silently halve them.

### Source tree — what exists, what this story adds

```text
src/
  companion/
    contracts.py               # EXISTS — leaf; untouched
    app/
      __init__.py              # EXISTS — docstring only; DO NOT add re-exports
      main.py                  # UPDATE — add bound_port(app); build_app()/lifespan unchanged
      server.py                # NEW — HOST/DEFAULT_PORT, resolve, bind, run  (the only 8765)
      routes/health.py         # EXISTS — untouched
tests/
  unit/companion/
    conftest.py                # EXISTS — lifespan_client; untouched
    test_app.py                # EXISTS — NOT edited by this story
    test_import_boundary.py    # EXISTS — NOT edited by this story
    test_server.py             # NEW
```

**Current state of the files being modified** (read before editing):

- `src/companion/app/main.py` — module docstring, `logger`, `_TITLE`, `async _shutdown(app)`,
  `@asynccontextmanager lifespan(app)` (mints `app.state.instance_id`, `try/yield/finally` with a
  swallow-and-log teardown), and `build_app()` returning `FastAPI(title=_TITLE, lifespan=lifespan)`
  with the health router included. **What must be preserved:** it imports no uvicorn, no
  `src.paths`, and nothing at module level with a side effect — c1-2's
  `test_construction_binds_no_socket` fresh-imports this module with `socket.socket.bind`
  monkeypatched to raise. Adding a *function* is safe; adding an import of `server.py` would create
  a cycle and drag uvicorn back in. Don't.
- `.pre-commit-config.yaml` — the mypy hook's `additional_dependencies` currently lists fastapi,
  pydantic, sqlalchemy, numpy, mcp, platformdirs. Append uvicorn; change nothing else.

### Gotchas specific to this story

1. **Lifespan runs before the listener exists** — the whole reason for Decide-once #1. If you find
   yourself writing `uvicorn.run(app, host=…, port=…)`, stop: that form cannot satisfy c1-7.

2. **`SO_REUSEADDR` means opposite things on Windows and POSIX.** On Windows it permits binding a
   port another socket is *actively listening on* — the bind would silently succeed and two
   processes would fight over 8765, making AC 2 untestable and AD-4's single-instance premise
   false. On POSIX it does the opposite and is genuinely wanted: without it, restarting the
   companion while `TIME_WAIT` connections linger on 8765 raises `EADDRINUSE` and drops you onto a
   pointless ephemeral port. Hence: set it on POSIX, never on Windows — the same rule asyncio
   applies to its own `create_server`. Note that uvicorn's `config.bind_socket()` sets it
   unconditionally, which is a second reason not to let uvicorn bind.

3. **A busy port is not the only bind failure.** Windows (WinNAT / Hyper-V / WSL2) reserves dynamic
   port ranges that can swallow 8765 and raises `WSAEACCES` (10013), not `WSAEADDRINUSE` (10048).
   Catch `OSError`, not `errno`-specific cases — otherwise the machine most likely to hit it is
   Brad's.

4. **The bound socket must not be `listen()`ed here.** `loop.create_server(sock=…)` calls `listen()`
   itself; uvicorn's own `bind_socket` likewise only binds. Bind reserves the port, which is all
   this story needs.

5. **`localhost` ≠ `127.0.0.1` for a v4-only socket** — Decide-once #4. Applies to the printed URL,
   and it is why c1-5 must accept both spellings in `Host`.

6. **`app.state` is `Any` to mypy and `warn_return_any = true` is on.** `return getattr(app.state,
   "bound_port", None)` fails `mypy --strict`. Assign to an annotated local first.

7. **The pre-commit mypy hook runs `--ignore-missing-imports` in an isolated env.** A missing
   `additional_dependencies` entry does **not** turn the hook red — it silently types uvicorn as
   `Any` and passes with degraded checking (the correction applied to c1-2's notes in review). AC 12
   exists to keep the check honest, not to un-break a red hook. Prove it with
   `uv run pre-commit run mypy --all-files`.

8. **Do not bind `DEFAULT_PORT` in a test.** Occupy an ephemeral port and pass it as the *preferred*
   one; the code path is identical and the test cannot collide with a real companion, another dev
   process, or a parallel CI job.

9. **CI is Linux-only** (`ubuntu-latest`, py3.12 + py3.13) while Brad develops on Windows. Any
   platform-conditional line — the `SO_REUSEADDR` branch above — is exercised on only one side of
   that split per run. Keep the branch trivial and assert the *observable* outcome (a conflicting
   bind falls back), which holds identically on both platforms.

10. **The write guard scans `app/` too.** Nothing here goes near a session, but `sock.close()` and
    `file.flush()`-shaped calls are worth remembering: `_SESSION_MUTATORS` fires only on a
    session-shaped receiver, so `sock` is safe.

### Testing standards

- New tests live in `tests/unit/companion/test_server.py` — unmarked, fast, no network, no server
  boot. `--strict-markers` is on: do not invent a marker.
- `asyncio_mode = "auto"` — write `async def test_…` directly where needed; most of this story's
  tests are synchronous.
- **Verification before completion:** paste actual ruff / mypy / pytest output into the Debug Log.
  "Tests pass" without output is not acceptance — standing agreement from the epic-5/6 retros.
- The AC 5 and AC 1 source-scan guards must be **proven non-vacuous** (assert the scan visited files
  and found the one legal `8765`); c1-1's `collect_python_files` raises on an empty walk for exactly
  this reason and is a good model.
- Close every socket a test opens, via a fixture, not `try/finally` in each test — a leaked listener
  on Windows produces failures in *later* tests, which is the worst kind of flake to diagnose.

### Previous story intelligence (c1-2, done 2026-07-25)

- **The `lifespan_client` seam exists** in `tests/unit/companion/conftest.py` as a fixture returning
  a context-manager factory. This story barely needs it (no request goes through the runner), but do
  not duplicate it.
- **`uvicorn` was deliberately left out of the mypy hook by c1-2**, with the addition explicitly
  homed on this story ("c1-3 adds it to the mypy hook when it does"). AC 12 is that debt.
- **Construction-site enumeration** (epic-7 retro standing agreement): when a concept threads
  through multiple sites, enumerate them before claiming end-to-end. Here the concept is *the port*
  and the sites are: the constant, `app.state`, the printed URL, and — deliberately **not yet** —
  the discovery file (c1-7) and `Host` validation (c1-5). Naming what this story does *not* wire is
  part of the enumeration.
- **Gate-output homing** (open epic-7 action item): Decide-once #1 is homed on **c1-7** (lifespan
  needs the port), #2 on **c1-5 and c1-7** (both read `bound_port`), #3 and #4 on **c1-9** (README
  and launch copy).
- **Baseline discipline:** c1-2 found the recorded baseline off by one and *recorded* the delta
  rather than chasing it. Do the same.

### Git intelligence

`HEAD = a7e1355` on `feat/companion-app` — the merge of PR #10 (c1-2). The pattern across c1-1 and
c1-2 is identical and should be matched: one focused `feat(companion): …` commit implementing the
story, then review fixes as separate follow-up commits on the same branch, then a PR into
`feat/companion-app` (Greptile reviews per story).

Suggested commit: `feat(companion): port selection with ephemeral fallback and a printed launch URL`.

### Latest technical information

- **uvicorn 0.51.0** is installed and locked; `Server.run(sockets=[...])` and
  `Config(app, host=…, port=…, lifespan="on")` are the current API. `on_event`-era helpers are
  irrelevant here. `uvicorn.run(...)` (the module-level convenience) does **not** accept a
  pre-bound socket — use `Config` + `Server` directly.
- The `[standard]` extra brings `uvloop` (POSIX), `httptools`, `watchfiles` and `websockets`. None
  of it changes the binding story; `websockets` is what c4 will need for the WS upgrade.
- **`socket.socket.getsockname()` after `bind(("127.0.0.1", 0))`** returns the kernel-assigned port
  immediately — no `listen()` required. That is what makes the pre-bind design possible at all.
- **asyncio's own reuse policy** (`asyncio/base_events.py`, `create_server`): `reuse_address`
  defaults to `os.name == "posix" and sys.platform != "cygwin"`. Mirroring it is not a
  micro-optimisation; it is the standard library's ruling on the exact Windows hazard in Gotcha 2.

### Project Structure Notes

- One new module under `src/companion/app/`, which the AD-3 enumeration pin classifies
  automatically (everything under `app/` is exempt from the leaf rule and the outside-app rule), so
  **no guard edit is needed**. If you find yourself wanting to edit
  `tests/unit/companion/test_import_boundary.py`, a file is in the wrong place.
- **Deviation from the spine's Structural Seed, stated deliberately:** the seed lists `main.py`,
  `deps.py`, `state.py`, `security.py`, `routes/`, `ws.py`, `images.py`, `static/` and names no
  runner module. `server.py` is an addition, not a contradiction — the seed's `main.py` line is
  *"build_app() — zero side effects; lifespan owns effects"*, and putting a socket bind and a
  uvicorn import in that same file would work against the description. Keeping them apart also
  keeps c1-2's fresh-import inertness tests cheap and c1-5's middleware free of a uvicorn import.
- Pre-existing tracked files modified: `src/companion/app/main.py`, `.pre-commit-config.yaml`,
  `_bmad-output/implementation-artifacts/sprint-status.yaml` and the generated `plugin/` mirror.
  **Not** `pyproject.toml` and **not** `uv.lock` — uvicorn is already a declared dependency.
- Nothing imports `server.py` yet; c1-9 will be its first caller. Its regression surface today is
  the `main.py` addition and the mypy-hook line.

### References

- [epics-companion-app.md — Story 1.3](_bmad-output/planning-artifacts/epics-companion-app.md#L952-L982) — the source acceptance criteria
- [epics-companion-app.md — Epic 1 framing](_bmad-output/planning-artifacts/epics-companion-app.md#L879-L886) · [stories 1.5–1.9](_bmad-output/planning-artifacts/epics-companion-app.md#L1012-L1166) — the four consumers of `bound_port`
- ARCHITECTURE-SPINE.md — [AD-3](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L114-L125) · [AD-4](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L127-L141) · [AD-5](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L143-L157) · [AD-10](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L227-L240) · [AD-14](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L304-L313) · [AD-15](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L315-L327) · [Structural Seed](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L433-L457)
- [prd.md — FR-01](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L102) · [NFR-01](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L160)
- [EXPERIENCE.md — the terminal URL as the recovery path](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L202)
- [c1-2 story record](_bmad-output/implementation-artifacts/c1-2-side-effect-free-asgi-app-with-a-lifespan-and-a-health-endpoint.md) — the inertness contract, the test seam, and the homed uvicorn/mypy debt
- [src/companion/app/main.py](src/companion/app/main.py) — the module this story extends · [tests/unit/companion/test_app.py](tests/unit/companion/test_app.py#L63-L101) — the inertness tests that must stay green
- [.venv/Lib/site-packages/uvicorn/server.py](.venv/Lib/site-packages/uvicorn/server.py#L103-L144) — lifespan-before-listener, verified · [uvicorn/config.py](.venv/Lib/site-packages/uvicorn/config.py#L550-L590) — `bind_socket`'s unconditional `SO_REUSEADDR`
- [src/mcp_server/__main__.py](src/mcp_server/__main__.py#L21-L61) — the `[planeswalker]` print convention (stderr there, stdout here — AD-15)
- [.pre-commit-config.yaml](.pre-commit-config.yaml#L11-L22) — mypy `additional_dependencies` · [ci.yml](.github/workflows/ci.yml#L41-L67) — gates + plugin drift check
- [project-context.md](_bmad-output/project-context.md) — logging, ruff/mypy, docstring conventions

## Open questions for Brad

Neither blocks implementation.

1. **Env-var name `PLANESWALKER_COMPANION_PORT`.** Chosen for symmetry with `PLANESWALKER_DATA_DIR`.
   FR-01 says "configurable" without naming a mechanism, and c1-9 may later add a `--port` flag that
   feeds the same `run(port=…)` argument. Confirm the name before it reaches the README.
2. **Nothing configures the root logger yet.** Consequently every `logger.info` in `src/companion`
   (including c1-2's "Companion instance %s started") is currently dropped on the floor, while
   uvicorn's own logs appear because uvicorn configures its own loggers. That is why AC 6 uses
   `print`. Wiring `logging.basicConfig` belongs to the process entry point — c1-9 — and is flagged
   here rather than silently absorbed.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Amelia / bmad-dev-story)

### Debug Log References

**Task 0 — state verification (all four assertions held).**

```text
$ git rev-parse HEAD                       → a7e13557e75d3912e9bceaa4b96ab61702dbf3a6
$ git branch --show-current                → feat/companion-c1-3-port-selection-ephemeral-fallback (off feat/companion-app)
$ Test-Path src/companion/app/server.py    → False
$ Test-Path src/companion/app/main.py      → True
$ uv run python -c "import uvicorn; print(uvicorn.__version__)"  → 0.51.0
$ grep -rn "uvicorn" src/                  → 1 hit, src/companion/app/__init__.py:3 (docstring prose, not an import)
$ uv run pytest -m "not integration" -q    → 1373 passed, 45 deselected in 41.53s
```

Baseline matched the recorded 1,373 exactly — **no delta to record** this time (c1-2's off-by-one
did not recur).

**Decide-once #1 re-verified against the installed source** (not taken on trust from the notes):
`.venv/Lib/site-packages/uvicorn/server.py:104` is `await self.lifespan.startup()`; the
`if sockets is not None:` listener loop is at `:123`; the banner suppression is at `:186-191`. The
story's claim is accurate — lifespan genuinely precedes the listener, so the pre-bind design is
required, not preferred.

**Task 6 — quality gates (AC 13).**

```text
$ uv run ruff check .            → All checks passed!
$ uv run ruff format --check .   → 262 files already formatted
$ uv run mypy src/               → Success: no issues found in 77 source files
$ uv run pytest -m "not integration" -q
                                 → 1405 passed, 45 deselected in 41.65s
```

1,405 = 1,373 baseline + 32 new tests. **Zero regressions**; c1-2's `TestConstructionIsInert`
passes unmodified (AC 8).

**AC 12 — the mypy hook proven honest, not merely green.** Gotcha 7 warns that a *missing*
`additional_dependencies` entry also passes (uvicorn silently becomes `Any`), so "Passed" alone is
not evidence. Two findings:

1. `pre-commit run` **stashes unstaged changes** — a probe left unstaged is not what the hook sees.
   The first probe run passed spuriously for this reason.
2. With `port="PROBE-NOT-AN-INT"` staged, the hook failed with
   `src\companion\app\server.py:182: error: Argument "port" to "Config" has incompatible type "str"; expected "int"  [arg-type]`
   — proving the hook now resolves uvicorn's **real** signatures. Probe reverted; hook green again.

**AC 15 — manual smoke on Windows (recorded, not committed).**

Run 1, port free — stdout exactly as AC 6 specifies, and `/health` live on it:

```text
[planeswalker] companion running at http://127.0.0.1:8765 — open this URL in your browser (Ctrl-C to stop)
$ GET http://127.0.0.1:8765/health
{"status":"ok","instance_id":"39f7c367-237c-4e82-a28e-3e6fc1e8e7da"}
```

stderr carried only uvicorn's own `Started server process` / `Application startup complete` — **no
"Uvicorn running on …" banner**, exactly as Decide-once #1 predicts when uvicorn is handed sockets.
Confirms the printed line is the sole launch line.

Run 2, port 8765 occupied — both lines, in order, and the fallback port genuinely serving:

```text
[planeswalker] port 8765 is unavailable — falling back to an ephemeral port
[planeswalker] companion running at http://127.0.0.1:49589 — open this URL in your browser (Ctrl-C to stop)
$ GET http://127.0.0.1:49589/health
{"status":"ok","instance_id":"494e69cb-744d-4faf-a9c2-6480bf4c7d8c"}
```

**Worth recording precisely:** the occupant was *not* the throwaway hog script written for the
purpose — that script itself died with
`OSError: [WinError 10048] Only one usage of each socket address … is normally permitted`, because
run 1's companion was still holding 8765 (killing the `uv` wrapper leaves the python child alive).
So the conflict exercised was **a second companion launching while a real one is already running** —
a truer version of the scenario than the one intended, and the exact case AD-4's single-instance
premise and c1-8 will formalise. Orphaned processes cleaned up afterwards; 8765 confirmed free.

**AC 14 — plugin mirror.** `uv run python -m scripts.build_plugin` picked up both source changes
(`plugin/server/src/companion/app/server.py` new, `.../main.py` modified) and both were committed.

**AC 16 — scope boundary verified by command, not by assertion:**
`git status --porcelain -- tests/unit/companion/test_import_boundary.py tests/unit/companion/test_app.py .github/workflows/ci.yml pyproject.toml uv.lock`
returned empty. All five untouched.

### Completion Notes List

- **All 16 ACs met.** The socket is bound by `run()` and handed to uvicorn as `sockets=[sock]`;
  `app.state.bound_port` carries the *actual* port; the URL is `print`ed to stdout with the literal
  `127.0.0.1`.
- **Construction-site enumeration** (standing agreement) — the concept is *the port*, and its sites
  in this story are exactly four: the `DEFAULT_PORT` constant, `app.state.bound_port`, the printed
  URL, and `uvicorn.Config(port=…)`. Deliberately **not** wired yet, per the story: the discovery
  file (c1-7) and `Host` validation (c1-5). AC 5's scan is what keeps the enumeration honest —
  it asserts `8765` occurs in `src/companion/app/server.py` and **nowhere else** under `src/` or
  `scripts/`.
- **Both source-scan guards assert their own non-vacuity** (c1-1's dead-guard lesson): the AC 5 scan
  fails if it does *not* find the one legal `8765`, and the AC 1 scan fails if it finds no `bind()`
  call at all. A guard that silently stops visiting files would go red, not green.
- **The AC 1 guard is AST-based, not a string search.** It walks every `bind()` call under
  `src/companion/` and asserts the address tuple's host element is the `HOST` **constant** — a
  direct proof of "no other bind target" rather than an approximation via banned substrings. It also
  avoids a trap: a blanket ban on the literal `"localhost"` would wrongly fire on c1-5, which must
  accept both spellings in `Host`.
- **Test-design correction made during implementation.** The first `run()` tests read the port back
  off the socket *after* `run()` returned — but `run()` closes it, so they failed with
  `WinError 10038`. Fixed by having the `_serve` stub record `sock.getsockname()[1]` **during** the
  call. This is strictly stronger: `app.state.bound_port` is now compared against the socket's own
  port rather than against a number the runner passed itself, so the assertion is no longer a
  tautology.
- **The occupied-port fixture calls `listen()`, deliberately.** On Linux a merely-*bound* socket can
  be re-bound by a second socket when both set `SO_REUSEADDR` — which is exactly what this module
  does on POSIX. A *listening* socket is refused on every platform, so the "occupied" premise holds
  identically on Windows and on CI's Linux runners (Gotcha 9's split). Our own socket is still never
  `listen()`ed (Gotcha 4).
- **`preferred == 0` is not a conflict.** `run()` suppresses the fallback line when `0` was asked
  for, since receiving an ephemeral port is the requested outcome, not a degradation.
- No test binds `DEFAULT_PORT` (Gotcha 8); every socket a test opens is closed by the `loopback`
  fixture at teardown.
- **Open question 1 still stands for Brad:** the env-var name `PLANESWALKER_COMPANION_PORT` is
  implemented as specified but has not been confirmed — worth settling before c1-9 puts it in the
  README. Open question 2 (no root logger configured, hence `print`) is unchanged and belongs to
  c1-9.

### File List

| File | Change |
| --- | --- |
| `src/companion/app/server.py` | **NEW** — `HOST`/`DEFAULT_PORT`/`PORT_ENV_VAR`, `resolve_preferred_port`, `_new_socket`, `bind_localhost_socket`, `_serve`, `run` |
| `src/companion/app/main.py` | Modified — added `bound_port(app)`; `build_app()`/`lifespan` unchanged |
| `tests/unit/companion/test_server.py` | **NEW** — 32 unmarked unit tests |
| `.pre-commit-config.yaml` | Modified — `uvicorn>=0.51.0` added to mypy `additional_dependencies` |
| `plugin/server/src/companion/app/server.py` | **NEW** — generated mirror |
| `plugin/server/src/companion/app/main.py` | Modified — generated mirror |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | Modified — c1-3 → in-progress → review |
| `_bmad-output/implementation-artifacts/c1-3-…-launch-url.md` | Modified — this record |

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-25 | Story c1-3 created from epics Story 1.3 + AD-4/AD-10/AD-15/NFR-01, with c1-2's inertness contract as the standing constraint and uvicorn 0.51.0's startup ordering verified against the installed source. Status → ready-for-dev. |
| 2026-07-25 | Implemented all 6 tasks. New `src/companion/app/server.py` (port resolution → loopback bind with ephemeral fallback → pre-bound socket handed to uvicorn → stdout launch URL); `main.bound_port(app)` accessor added. 32 new tests, incl. two non-vacuous source-scan guards (AC 5 port literal, AC 1 AST bind-target). uvicorn added to the mypy hook and the hook *proven* to resolve it via a staged type-error probe. Gates green (ruff/mypy clean, 1405 passed / 45 deselected, zero regressions); manual smoke recorded for both the free-port and occupied-port paths. Status → review. |

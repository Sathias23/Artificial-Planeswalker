---
baseline_commit: a82c032
epic: c1
story: c1-8
work_branch: feat/companion-app
story_branch: feat/companion-c1-7-discovery-file-rendezvous (continued — see Task 0)
---

# Story C1.8: Single-instance enforcement with verified identity

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad who forgot the backend was already running,
I want a second launch to tell me so and exit,
so that I never end up with two instances fighting over one discovery file and a browser pointed at
the wrong one.

**Why this story is eighth, and what it costs today.** c1-7 made the app *findable*; it also made the
app *clobberable*, because its lifespan overwrites whatever `companion.json` it finds. That is not a
theory — it was measured on this machine at the baseline commit (see Latest technical information,
probe C):

```
1  discovery file written    : {'port': 64474, 'instance_id': 'd337280a-…'}
6  second launch started too : True
7  rendezvous now points at  : 64481 | same instance as first? False
8  first instance still up   : 200 {'status': 'ok', 'instance_id': 'd337280a-…'}
```

Two companions, one rendezvous, and the browser tab Brad already has open is pointed at the instance
that no agent tool can find any more. This story closes that with the check AD-4 has specified since
the spine was written: read the file, ask the port who it is, and believe only an `instance_id` that
matches. It also lands the **second half of the leaf's answer to "where is the app?"** —
`src/companion/client.py`, whose identity probe c6-1 then reuses before every push (its AC says so in
as many words), which is why AC 1 puts the probe in the leaf rather than in the runner.

## Acceptance Criteria

1. **The identity probe lives in the leaf, in `src/companion/client.py` (AD-3, AD-4).** The spine's
   Structural Seed names the module and its job: `client.py # LEAF — /health + /agent/events,
   notifier (AD-8, AD-9)`. This story builds the **`/health` half only**; c6-1 adds the POST, the
   retry-once and the outcome vocabulary into the same file. It exports exactly:

   - `LOOPBACK_HOST = "127.0.0.1"` — the address a caller dials. It is deliberately *not* imported
     from `server.HOST` (a leaf may not import the app), and the duplication is one literal with a
     comment naming its twin;
   - `HEALTH_PATH = "/health"`;
   - `PROBE_TIMEOUT` — the `httpx.Timeout` of AC 3;
   - `base_url(port: int) -> str` — `f"http://{LOOPBACK_HOST}:{port}"`, the one place the URL is
     assembled (c6-1 posts to it, `server.py` prints it);
   - `probe_health(port: int, *, timeout: httpx.Timeout | None = None) -> HealthResponse | None`;
   - `live_instance(*, timeout: httpx.Timeout | None = None) -> DiscoveryRecord | None`.

   **Leaf constraints (AD-3), already enforced without a test edit:** `src/companion/client.py` is
   listed in `test_import_boundary._LEAF_MODULES`, so it is classified the moment it exists. It may
   import the stdlib, `pydantic`, **`httpx`**, `src.paths` and its sibling leaves
   (`src.companion.contracts`, `src.companion.discovery`) — never `fastapi`, `uvicorn`,
   `sqlalchemy` or `src.companion.app`, **not even under `if TYPE_CHECKING:`**. Reuse
   `contracts.HealthResponse` to parse the body: it is the shape the endpoint already declares, and
   a second local model would be the drift AD-12 exists to prevent.

2. **The probe is `async`, and the runner reaches it through `asyncio.run` (AD-8).** One
   implementation serves both callers, and the shape is fixed by the *other* caller: c6-1's tools are
   `async def` and will post with the same client, so a sync probe would force `asyncio.to_thread`
   around a network call in an async tool. `run()` is sync and calls
   `asyncio.run(client.live_instance())` **before** uvicorn ever exists; a second `asyncio.run` (the
   one uvicorn performs) on the same thread afterwards is legal and was verified (probe B2). Do not
   add a sync mirror of the probe "for the runner" — two implementations is the thing AD-3's shared
   leaf exists to prevent.

3. **The timeout is split — a short connect, a longer read — and the split is measured, not
   guessed.** `PROBE_TIMEOUT = httpx.Timeout(connect=1.0, read=2.0, write=2.0, pool=2.0)`.

   - **Why connect is short:** on this machine a TCP connect to a *dead* loopback port takes **~2.03
     s** to report `ConnectionRefused` (verified: raw socket, `asyncio.open_connection` and httpx all
     agree — probe B). A stale discovery file is the *ordinary* post-crash state (AD-15), so without
     a short connect deadline every launch after a crash would stall two seconds before starting. A
     live listener completes the loopback handshake in the kernel, in microseconds, whether or not it
     is busy — so a 1 s connect deadline cannot make a live instance look dead.
   - **Why read is longer:** the read is the one that *can* be slow on a live app (a large deck
     refetch, a burst of image work). A live instance answered `/health` in **~15 ms** here (probe C),
     and 2 s is the margin. Calling a live-but-busy app dead is the expensive mistake — it starts a
     second instance, which is exactly what this story exists to prevent — so read is deliberately
     generous where connect is deliberately tight.

   The `timeout=` parameter exists so a test can drive the dead-port and never-answers cases in
   milliseconds instead of seconds; production callers pass nothing.

4. **`probe_health` never raises — anything that is not this companion answering is `None`.** One
   `try`, and every outcome below returns `None` after a **DEBUG** log (the c1-7 reasoning: for
   c6-1's client the expected case is that nothing is there, and a WARNING per push would be noise):

   | What is on the port | What httpx does | Verified |
   | --- | --- | --- |
   | nothing listening | `ConnectTimeout` (short deadline) / `ConnectError` (long) | probe A1, B–D |
   | accepts but never answers | `ReadTimeout` | probe A6 |
   | a foreign server returning HTML `200` | body fails `model_validate_json` | probe A3 |
   | JSON of the wrong shape (`{"status":"ok"}`) | `ValidationError` | probe A4, A4b |
   | any non-2xx (e.g. a `400 invalid_request` from another companion-shaped server) | status checked before parse | probe A7 |
   | bytes that are not UTF-8 / not JSON | `ValidationError` via `model_validate_json` | c1-7 probe 15 |

   The net is `except (httpx.HTTPError, ValueError)`, and both halves are verified here (probe D):
   `ConnectTimeout`, `ReadTimeout` and `ConnectError` are all `httpx.HTTPError` subclasses,
   `httpx.HTTPError` is **not** a `ValueError` (so both members of the tuple earn their place), and
   `pydantic.ValidationError` is a `ValueError`. Do **not** widen it to
   `except Exception`: a `MemoryError` mid-probe is not "app not running". Status is checked
   explicitly (`response.status_code != 200 → None`) rather than via `raise_for_status`, so the
   non-2xx path never travels through an exception.

5. **`live_instance()` is the whole question in one call, and it short-circuits.** In order:
   `discovery.read_discovery()` → if `None`, return `None` **without touching the network**; probe
   `record.port`; return the record **only** when the echoed `instance_id` equals the recorded one;
   otherwise `None`. Returning the *record* rather than a bool is deliberate — its `port` is what the
   refusal message prints, and its `token` is what c6-1 needs the moment identity is proven. It
   **never raises** (both halves already never raise). The no-file short-circuit is an assertable
   behaviour, not an optimisation: a launch on a clean machine must make **no** network call at all
   (AC 16 pins it with a stub server that recorded zero requests).

6. **No token ever leaves the process on this path (AD-4, AD-5).** `/health` is unauthenticated by
   design — it is what a caller reads *before* deciding to trust the port. The probe therefore sends
   no `Authorization` header, no token in the query string and no body, and **nothing in
   `client.py` reads `record.token` in this story** (c6-1 introduces the first read, after identity
   is proven). Pinned by a test that stands up a *foreign* stub server on the recorded port,
   captures every byte it receives, and asserts the token substring appears in no request line, no
   header and no body — the scenario the AC is written for is precisely the one where a token must
   not be handed over.

7. **The check runs in `run()`, before anything is claimed.** `src/companion/app/server.py::run()`
   calls `asyncio.run(client.live_instance())` **before** `resolve_preferred_port`,
   `bind_localhost_socket` and `build_app()`. Ordering is behaviour, not tidiness: a refusing launch
   must not momentarily hold a port another process might want, and must not construct an app it
   will never serve.

8. **The refusal is one line on stdout naming the live URL, and the process exits 0.** Printed, not
   logged, for c1-3's reason (this process owns stdout under AD-15, and no root handler exists until
   c1-9), and printed **after** `run()`'s existing `sys.stdout.reconfigure(errors="replace")` guard,
   because the message carries an em dash like every other launch line:

   ```
   [planeswalker] companion is already running at http://127.0.0.1:64474 — open that URL, or stop the other instance before starting a new one
   ```

   `run()` then **returns** — no `sys.exit`, no exception — so the process exits `0`. The rationale
   is Decide-once #3; the reverse (a non-zero status) is Open Question 1.

9. **A refusal touches nothing.** After `run()` refuses: no socket was bound (assertable — the
   preferred port is still free afterwards), `_serve` was never called, no app was built, and the
   discovery file is **byte-identical** to what it was before (AC's "does not overwrite or delete the
   existing discovery file"). The last one is not automatic: it is a consequence of returning before
   the lifespan, and it needs its own assertion because a future refactor that moved the check into
   the lifespan would break it silently.

10. **A stale entry is reclaimed silently and automatically (AD-15).** File present, nothing
    answering → `run()` proceeds exactly as it does today. The stale file is **not** deleted: c1-7's
    lifespan publishes atomically over it, so a delete would add a window in which no rendezvous
    exists for no benefit, and a crash between delete and publish would leave the machine worse off.
    The reclaim logs at **INFO**, not WARNING — a stale file after a crash is the expected state AD-15
    describes, and warning about the ordinary case trains a user to ignore warnings. (It is therefore
    invisible until c1-9 configures a root handler; that is accepted and stated in the code comment,
    which distinguishes it from c1-3's and c1-7's deliberate WARNINGs.)

11. **A foreign process on a recycled port is treated as dead (AD-4).** Something answers, its
    `instance_id` does not match the file, or its body is not a `HealthResponse` at all → reclaim and
    start normally, having sent it nothing. If that port happens to be the one this launch prefers,
    c1-3's ephemeral fallback already handles the bind conflict — this story adds no port logic and
    must not.

12. **The rendezvous is the singleton, not the port.** An explicit port (argument or
    `PLANESWALKER_COMPANION_PORT`) does **not** bypass the check: a second instance on a different
    port is exactly the failure mode measured at baseline, because the discovery file can only name
    one of them. One test passes a port that differs from the live instance's and asserts the launch
    still refuses.

13. **`httpx` joins the pre-commit mypy hook's `additional_dependencies`.**
    `.pre-commit-config.yaml`'s mypy hook runs in an isolated environment with
    `--ignore-missing-imports`, and it lists `fastapi`, `pydantic`, `sqlalchemy`, `numpy`, `mcp`,
    `platformdirs`, `uvicorn` — **not `httpx`**. Every `httpx` call in the new leaf would therefore
    be silently `Any` in the hook while `uv run mypy src/` (which sees the real, `py.typed` package —
    verified) checks it properly: the c1-2 silent-Any gotcha, in the one story that makes it bite.
    Add `httpx>=0.28.1` and run `uv run pre-commit run mypy --all-files` to prove the hook still
    passes. **If — and only if — that surfaces pre-existing errors in `src/data/importers/
    scryfall_api.py` or `spellbook_api.py`** (the two existing httpx importers), revert the line,
    keep the story green, and home the finding in `deferred-work.md`; fixing unrelated importer
    typing is not this story's job.

14. **The two deferrals homed against this story get a ruling, not a re-defer by silence.**
    `deferred-work.md`'s c1-7 section homes both here; each gets an explicit outcome recorded in that
    file (per the epic-7 gate-output rule), and neither is "fixed" by default:

    - **Windows `os.replace`-while-open on publish.** Ruling: **still accepted, re-homed to c6-1**.
      This story does not make it more likely — the only concurrent reader of `companion.json` in
      production arrives with c6-1's client, which reads before every push. Note in the entry that
      c1-8 read the file itself at startup and closed it before the lifespan publishes, so a process
      cannot collide with itself.
    - **TOCTOU in `remove_discovery`'s ownership guard.** Ruling: **accepted and materially
      narrowed** — the second live instance the window needs is now the case this story refuses. Keep
      the entry, record the narrowing, and (AC 15) make the docstring that points at it truthful.

15. **New residual, homed rather than hidden: two simultaneous launches.** The check is
    check-then-act. Two processes started within the same few hundred milliseconds can both read
    "no file / dead file" and both start, the second publishing over the first — the baseline
    failure, in a window narrowed from *forever* to *startup*. A real fix needs an OS-level mutex (an
    `O_EXCL` lock file, or treating the bound port as the lock), which is a design decision, not a
    tweak. Record it in `deferred-work.md` under a new c1-8 section with that framing; do **not**
    build a lock file in this story. Also record there — in the same entry — that a live instance
    whose event loop is blocked for longer than the read timeout will be judged dead.

16. **A one-line documentation repair in `discovery.py`, and no behaviour change.**
    `remove_discovery`'s docstring currently says the TOCTOU trade is *"recorded in `deferred-work.md`
    against c1-8, the story that first makes two instances contend for this file."* Once this story
    lands, that sentence is stale in both halves. Reword it to state the accepted trade and that
    single-instance enforcement now prevents the ordinary second instance. **This is the only edit
    `src/companion/discovery.py` may receive** — no signature, no behaviour, no logic.

17. **Tests: `tests/unit/companion/test_client.py` (new) and `tests/unit/companion/test_server.py`
    (updated).** Unmarked unit tests — `--strict-markers` is on, and AD-10's *one* `integration` test
    is c5-8's, not this one. **Use real loopback sockets, not mocked transports**, following c1-3's
    precedent in `test_server.py`: a `http.server.HTTPServer` on port 0 in a daemon thread, in a
    fixture that shuts it down and joins the thread at teardown (a leaked listener surfaces as a
    failure in some *later* test — c1-3's stated reason for centralising teardown). Cover:

    - **AC 4's matrix**, one stub per row, each asserting `None`;
    - **AC 5**: no file → `None`, and the stub recorded **zero** requests; matching identity → the
      record; the record returned is the one from disk, field for field;
    - **AC 6**: the foreign stub captured no token, in any position;
    - **AC 8/9**: a refusing `run()` prints the message with the live port, does not call `_serve`,
      leaves the preferred port free, and leaves the file's bytes unchanged;
    - **AC 10/11**: stale file and foreign-identity file both serve normally, with the file left
      alone;
    - **AC 12**: an explicit non-matching port still refuses.

    **Non-vacuity (c1-6's rule, restated by c1-7 AC 15):** every "returns `None`" case sits beside
    the well-formed stub that returns a populated `HealthResponse` from the same call, and the
    `run()`-refuses assertions sit beside a `run()`-proceeds case, so neither test can pass by
    refusing everything or by never refusing. Discovery-file fixtures are written with plain
    `Path.write_text(json.dumps(...))`, **never** through `write_discovery` — a fixture built by the
    code under test proves nothing.

18. **Quality gates green (NFR-07).** `uv run ruff check .`, `uv run ruff format --check .`,
    `uv run mypy src/`, `uv run mypy src/ --platform linux`,
    `uv run pre-commit run mypy --all-files` and `uv run pytest -m "not integration"` all pass with
    no new failures against the **1,588 passed / 1 skipped / 45 deselected** baseline (measured at
    `a82c032` on 2026-07-26; `tests/unit/companion` is **275 passed / 1 skipped**). Actual output
    pasted into the Debug Log.

19. **Plugin mirror rebuilt and committed.** `uv run python -m scripts.build_plugin`, then commit
    `plugin/`; `git status --porcelain -- plugin/` clean afterwards. `client.py` is new source, so
    the mirror gains a file.

20. **Scope boundary — what this story must NOT do.**
    - **No push path** (c6-1): no `post_event`, no `POST /agent/events` call, no outcome-token
      vocabulary (`displayed | app_not_running | …`), no retry-once, no `deck_changed` notifier. The
      module docstring says which half is missing and which story brings it.
    - **No MCP tool and no `src/mcp_server/**` edit of any kind.**
    - **No CLI, no subcommand, no root-logger configuration** (c1-9). `run()` keeps its current
      signature.
    - **No new endpoint and no change to `/health`**, `contracts.py`, `errors.py`, `security.py`,
      `deps.py`, `main.py`, `routes/`, `src/data/**` or `src/paths.py`. No new reason token.
    - **No new dependency** — `httpx>=0.28.1` is already a project dependency; the only config edit
      is AC 13's one line in `.pre-commit-config.yaml`. No `pyproject.toml` / `uv.lock` edit.
    - **No lock file, no retry loop, no port-based mutex** (AC 15 homes the residual instead).
    - No edit to `tests/unit/companion/test_import_boundary.py` (AC 1 — `client.py` is already
      classified), `test_app.py`, `test_deps.py`, `test_errors.py`, `test_security.py`,
      `test_discovery.py` or `conftest.py`. If any of those needs a change, that is a **finding**,
      not an edit.

## Tasks / Subtasks

- [x] **Task 0 — State verification** (standing team agreement since the epic-6 retro: any story
      whose notes assert repository state opens with the cheap check that proves it)
  - [x] **Branching, and it is not the usual rhythm.** Brad's ruling (2026-07-26): because PR #15
        (`feat/companion-c1-7-discovery-file-rendezvous` → `feat/companion-app`) is **held open** —
        Greptile flagged the `remove_discovery` ownership-guard TOCTOU that c1-7 homed here — c1-8 is
        built **on c1-7's branch**, once off, and #15 becomes a two-story PR. So: **do not create a
        new branch.** Confirm `git branch --show-current` is
        `feat/companion-c1-7-discovery-file-rendezvous` at `a82c032` with a clean tree, and that PR
        #15 is still open (`gh pr view 15 --json state,baseRefName`).
  - [x] Confirm `src/companion/client.py` and `tests/unit/companion/test_client.py` do **not** exist,
        and that `test_import_boundary._LEAF_MODULES` already lists `src/companion/client.py`.
  - [x] Baseline the suite: `uv run pytest -m "not integration" -q` → expected **1,588 passed, 1
        skipped, 45 deselected**; `uv run pytest tests/unit/companion -q` → **275 passed, 1
        skipped**. Record any delta rather than chasing it.
  - [x] Re-confirm probe D in one line (it is what AC 4's single `except` rests on, and it is cheap):
        `issubclass(httpx.ConnectTimeout, httpx.HTTPError)`,
        `issubclass(httpx.ReadTimeout, httpx.HTTPError)`,
        `issubclass(httpx.ConnectError, httpx.HTTPError)`,
        `issubclass(httpx.HTTPError, ValueError)` (expected **False** — the tuple needs both members)
        and `issubclass(pydantic.ValidationError, ValueError)`. If any differs, match reality and say
        so in the Debug Log.

- [x] **Task 1 — The leaf probe, test-first** (AC: 1, 2, 3, 4, 5, 6)
  - [x] Write the AC 4 matrix in `tests/unit/companion/test_client.py` against the stub-server
        fixture first, and watch it fail on the missing module (red-phase evidence for the Debug Log).
  - [x] `src/companion/client.py` — module docstring covering: what half of the leaf client this is
        and what c6-1 adds; why the probe exists at all (AD-4 — never send a token to a process that
        has not proven it is this app); why it is a leaf and what that forbids (AD-3); why the
        timeout is split, with the ~2 s dead-port measurement; and that `/health` is unauthenticated
        because it is read *before* trust. Module-level `logger = logging.getLogger(__name__)`.
  - [x] `LOOPBACK_HOST`, `HEALTH_PATH`, `PROBE_TIMEOUT`, `base_url()`, `probe_health()`,
        `live_instance()` — Google docstrings on each, with an explicit "never raises" line on both
        async functions.
  - [x] Keep every local name clear of `_SESSION_RECEIVERS` (`session`, `sess`, `db`, `db_session`,
        `database`, `conn`, `connection`) — the write guard reads names, not intent (c1-7 Gotcha 5).
        Name the client `client`, the response `response`, the parsed body `health`.

- [x] **Task 2 — The startup check** (AC: 7, 8, 9, 10, 11, 12)
  - [x] `src/companion/app/server.py::run()` — the probe call and the refusal print, above
        `resolve_preferred_port`, below the stdout reconfigure. Extend `run()`'s docstring: it now
        has two outcomes, and the refusal is one of them.
  - [x] Update the module docstring's list of deliberate, load-bearing decisions with a fourth entry:
        the single-instance check runs before the bind, so a refusing launch never holds a port.
  - [x] Change nothing else in `server.py` — `resolve_preferred_port`, `_new_socket`,
        `bind_localhost_socket`, `_serve`, `HOST` and `DEFAULT_PORT` are untouched.

- [x] **Task 3 — Tests** (AC: 17)
  - [x] The stub-server fixture (bind port 0, daemon thread, teardown shuts down **and** joins), plus
        a `free_port()` helper. `test_server.py` already has `_Loopback` for the socket half — reuse
        the pattern rather than inventing a second one; do not import across test modules if that
        means editing `test_server.py`'s helper (a small duplication in `test_client.py` is cheaper
        than a shared-fixture refactor this story did not budget for).
  - [x] The `run()` cases go in `test_server.py` beside `TestRun`, using its existing
        `recorded_serve` fixture — this is the story that is allowed to edit that file.
  - [x] Every dead/never-answers case passes a **small** explicit `timeout=` so the suite does not
        pay seconds; one test asserts the *production* `PROBE_TIMEOUT` constant's connect and read
        values, so the measured trade is pinned somewhere.
  - [x] Assert observable state throughout — the file's bytes, the port's availability, what the stub
        recorded — never that a mock went uncalled.

- [x] **Task 4 — Config, deferrals and docs** (AC: 13, 14, 15, 16)
  - [x] `.pre-commit-config.yaml`: add `httpx>=0.28.1`; run `uv run pre-commit run mypy --all-files`
        and paste the output. Apply AC 13's revert-and-home rule if it goes red on pre-existing files.
  - [x] `deferred-work.md`: rule on the two c1-7-homed items in place (AC 14) and add the new c1-8
        section for the simultaneous-launch residual and the wedged-instance case (AC 15).
  - [x] `src/companion/discovery.py`: the one docstring sentence (AC 16). Diff it before committing —
        if `git diff --stat` shows anything but that file's docstring, back it out.

- [x] **Task 5 — Gates, mirror and scope** (AC: 18, 19, 20)
  - [x] `uv run ruff check . --fix` · `uv run ruff format .` · `uv run mypy src/` ·
        `uv run mypy src/ --platform linux` · `uv run pre-commit run mypy --all-files` ·
        `uv run pytest -m "not integration"` — paste actual counts into the Debug Log.
  - [x] `uv run python -m scripts.build_plugin`, `git add plugin/`, verify
        `git status --porcelain -- plugin/` is clean after the commit.
  - [x] Confirm by command that the AC 20 forbidden paths are untouched:
        `git status --porcelain -- tests/unit/companion/test_app.py tests/unit/companion/test_deps.py tests/unit/companion/test_errors.py tests/unit/companion/test_security.py tests/unit/companion/test_discovery.py tests/unit/companion/test_import_boundary.py tests/unit/companion/conftest.py .github/workflows/ci.yml pyproject.toml uv.lock src/data src/mcp_server src/paths.py src/companion/contracts.py src/companion/app/deps.py src/companion/app/errors.py src/companion/app/security.py src/companion/app/main.py src/companion/app/routes`
        returns empty.
  - [x] **Live check, since this story's whole subject is two processes** (the probe recipe is in
        Latest technical information — re-run it after the change): launch a companion with
        `PLANESWALKER_DATA_DIR` pointed at a temp directory, launch a second one, and confirm the
        second prints the "already running" line, exits, and leaves the first instance's
        `companion.json` byte-identical. Paste the two stdout lines into the Debug Log. This is the
        AC that a unit suite can only approximate.

### Review Findings

- [x] [Review][Decision] `test_server.py` imports `StubFleet`/`health_bytes`/`plant_discovery`
      from sibling test module `test_client.py` — **Brad's ruling (2026-07-26): accepted as-is.**
      The documented deviation stands (F811 on fixture import, `conftest.py` out of bounds under
      AC 20); revisit with a `_stubs.py` extraction only if a third module ever needs the stubs.
      [tests/unit/companion/test_server.py:26]
- [x] [Review][Patch] The probe has no overall deadline (**Brad's ruling 2026-07-26: patch**) — a
      drip-feeding or huge-body listener on the recorded port stalls `run()` indefinitely;
      `httpx.Timeout(read=2.0)` bounds the gap *between chunks*, not the whole exchange, and
      `response.content` buffers an unbounded body. Fix: `asyncio.timeout(...)` total deadline
      inside `probe_health` with `TimeoutError` folded into the `None` net — a sanctioned widening
      of AC 4's `except (httpx.HTTPError, ValueError)`, to be noted in the story record.
      [src/companion/client.py:64,127]
- [x] [Review][Patch] Probe follows `HTTP_PROXY`/`ALL_PROXY` env vars to 127.0.0.1 — missing
      `trust_env=False` on the `AsyncClient`; with a proxy configured (verified in this venv), the
      loopback probe dials the proxy, a live companion looks dead, and a duplicate instance starts —
      the exact baseline failure. Also stops `.netrc` from injecting an `Authorization` header
      (AC 6). [src/companion/client.py:124]
- [x] [Review][Patch] `probe_health` docstring says "any non-2xx status" but the code rejects
      anything `!= 200` (a 201/204 is treated as app-not-running — correct, but undocumented).
      [src/companion/client.py:95]
- [x] [Review][Patch] Reclaim INFO message over-claims — "is not answering; reclaiming it" also
      fires on the AC 11 foreign-identity path (which *is* answering), and no reclaim happens at
      that point (the overwrite is the lifespan's, later, maybe never).
      [src/companion/app/server.py:240]
- [x] [Review][Patch] `deferred-work.md` wording drift — the AC 14 ruling says the startup check
      "does one `read_bytes()`" (the reclaim path reads twice via `_note_reclaimed_entry`), and
      "same few hundred milliseconds" understates the check-then-act window (probe up to ~3 s at
      production timeouts, publish later still, at the lifespan).
      [_bmad-output/implementation-artifacts/deferred-work.md]
- [x] [Review][Patch] Test robustness — live-stub happy-path tests pass the 0.25 s `FAST` timeout
      (its own docstring scopes it to dead-or-silent cases; a starved CI thread flakes the matrix's
      non-vacuity anchor), and the reclaim-log test's WARNING sweep filters no logger name.
      [tests/unit/companion/test_client.py:32, tests/unit/companion/test_server.py:572]

## Dev Notes

### Decide-once rulings (made here so c6-1 and c1-9 inherit them)

**#1 — The probe goes in `client.py`, not `discovery.py`.** Both are leaves, so the boundary test is
indifferent; the seed is not. `discovery.py` owns *the file* — it is the module a caller imports to
learn a path, and c1-7 deliberately kept `httpx` out of it so a stdio MCP session pays nothing for
reading a port. `client.py` owns *talking to the backend*, which is what the seed says
(`/health + /agent/events, notifier`) and what c6-1's first AC re-states. Splitting them this way also
means the two stories touch disjoint files: c6-1 extends `client.py` and never reopens `discovery.py`.

**#2 — The leaf is async-only; the runner adapts.** The alternative — a sync probe with an async
wrapper — puts the fork inside the shared implementation to spare `run()` one `asyncio.run` call, and
c6-1 would then be posting through `asyncio.to_thread` from inside an async tool. `asyncio.run` before
uvicorn's own `asyncio.run` is verified legal (probe B2) and costs an event-loop construction on a
path that runs once per process.

**#3 — Refusing is a success, so the exit status is 0.** The user's intent — "have the companion
running" — is satisfied when the process exits, and the terminal line tells them where it is. AD-15
rules out the reader for whom a non-zero status would matter: there is no daemon, no supervisor and no
auto-restart, so nothing consumes the exit code except a human and, later, c1-9's dispatcher (which
reserves non-zero for an *unknown subcommand* — a genuine usage error). Returning rather than raising
also keeps the tests plain function calls. Recorded as Open Question 1 in case Brad wants the opposite.

**#4 — A reclaim deletes nothing.** The temptation is to `unlink` the stale file before starting;
resist it. c1-7's publish is atomic, so an overwrite is already indivisible, and a delete opens a
window in which the rendezvous does not exist at all — with a crash inside that window leaving the
machine worse off than the stale file it was cleaning. `remove_discovery`'s ownership guard also means
the delete would have to be unguarded to work here, which is precisely the primitive c1-7 declined to
build.

**#5 — Identity is compared, not merely fetched.** "Something answered on that port" is not evidence:
the port may have been recycled to an unrelated local dev server that returns `200` to everything
(probe A3 is exactly that server). Only an `instance_id` that matches the file proves the answering
process is the one the file describes — which is why `/health` echoes it (c1-2) and why the file
records it (c1-7). A mismatch is *dead*, never *ambiguous*, and never a reason to send a credential.

### Architecture rules this story implements

- **AD-4** — the half c1-7 deliberately left: *"Before sending the token, a caller calls `GET /health`
  and matches the echoed `instance_id`; a mismatch or failure is app not running. **Exactly one
  instance runs:** at startup a verified-live entry makes the new process exit with 'already running';
  a stale or dead entry is reclaimed."* Both sentences are this story, and nothing else is.
- **AD-3** — the leaf gains its third and final module. The probe must be importable by
  `src/mcp_server/tools/companion.py` (c6-1) without dragging FastAPI into a stdio session; that is
  the whole reason it is not a private helper inside `server.py`.
- **AD-5** — two credentials that never touch. This story is the *no-credential* path: it proves
  identity before anything is sent, which is what makes c6-1's token send safe.
- **AD-15** — the operational envelope, verbatim: a foreground, user-launched, **single-instance**
  local process, whose crash *"leaves a stale discovery file that the next start reclaims"*. AC 10 is
  that sentence.
- **AD-10** — untouched, and worth checking you have not broken: the probe lives in `run()`, not in
  the lifespan and not in `build_app()`, so construction stays inert and `test_app.py`'s
  `TestConstructionIsInert` keeps passing without an edit.
- **FR-01** — its second sentence (*"Exactly one instance runs at a time…"*) closes here; the port and
  fallback halves closed in c1-3.

### Source tree — what exists, what this story adds

```text
src/
  companion/
    client.py                  # NEW — LOOPBACK_HOST, HEALTH_PATH, PROBE_TIMEOUT, base_url,
                               #       probe_health, live_instance   (the /health half; c6-1 adds POST)
    discovery.py               # UPDATE — one docstring sentence only (AC 16)
    contracts.py               # EXISTS — untouched (HealthResponse is reused as-is)
    app/
      server.py                # UPDATE — run() refuses a live instance before binding
      main.py                  # EXISTS — untouched
      deps.py / errors.py / security.py / routes/  # EXISTS — untouched
tests/
  unit/companion/
    test_client.py             # NEW — the probe matrix over real loopback stub servers
    test_server.py             # UPDATE — the run() refuse/reclaim cases beside TestRun
    conftest.py                # EXISTS — NOT edited (its autouse isolation already covers this)
    test_import_boundary.py    # EXISTS — NOT edited (client.py is pre-classified)
.pre-commit-config.yaml        # UPDATE — httpx in the mypy hook's additional_dependencies (AC 13)
```

**Current state of the files being modified** (read before editing):

- `src/companion/app/server.py` — `run(port: int | None = None)` currently: reconfigures stdout for
  the em dash, `resolve_preferred_port(port)`, `bind_localhost_socket(preferred)`, then inside a
  `try/finally` reads `getsockname()[1]`, builds the app, stamps `app.state.bound_port`, prints the
  fallback line (when `preferred != 0 and actual != preferred`) and the URL line, and calls `_serve`;
  the `finally` closes the socket. **What must be preserved:** the stdout reconfigure runs first (the
  refusal line has an em dash too); the `finally`-closes-the-socket invariant; `_serve` isolated so
  tests can replace it; `DEFAULT_PORT` remaining the only place in `src/` that names 8765 —
  `client.py` must name **no** port number.
- `src/companion/discovery.py` — `read_discovery()` (never raises, `None` means app not running) is
  consumed as-is; `remove_discovery()`'s docstring is the one edit. Read `DiscoveryRecord`'s field
  constraints: `port` is already validated `1..65535`, so `live_instance` needs no port sanity check
  of its own.
- `src/companion/contracts.py` — `HealthResponse(status: Literal["ok"], instance_id: str)`. Its
  module docstring already says *"the AD-4 identity probe lives in the leaf and is shared by the
  startup check and the companion tools"* — this story makes that sentence true. Unknown keys are
  ignored by pydantic default, so a future backend that adds a health field stays parseable.
- `tests/unit/companion/test_server.py` — `_Loopback` (real sockets, teardown-owned), `_RecordingServe`
  + the `recorded_serve` fixture (replaces `server._serve`, records `app`, `sock`, `port`), and
  `TestRun`. Note `recorded_serve` means **the lifespan never runs** in this file, so no discovery
  file is written by these tests — which is why the refusal tests must plant their own file.
- `tests/unit/companion/conftest.py` — the autouse `isolated_data_dir` fixture points
  `PLANESWALKER_DATA_DIR` at each test's `tmp_path`. It already covers `test_server.py`, which matters
  more than it did yesterday: `run()` now **reads the discovery file**, so without that fixture these
  tests would consult (and be steered by) the developer's real `companion.json`. No edit needed —
  but understand why it is load-bearing here before touching anything near it.
- `tests/unit/companion/test_import_boundary.py` — `_LEAF_MODULES` lists `client.py`;
  `_LEAF_ALLOWED_THIRD_PARTY` is `{pydantic, httpx}`; `_LEAF_ALLOWED_SRC` includes the sibling leaves.
  There is even a committed clean-case fixture (`_SRC_LEAF_ALLOWED_SURFACE`) whose path is
  `src/companion/client.py` and whose imports are `json` + `httpx` + `pydantic` + `src.paths`.
  **Read, not modified.**

**Deviation from the spine's Structural Seed:** none. `client.py` is on the seed by name; this story
lands the AD-4 half of its stated responsibility and c6-1 lands the AD-8/AD-9 half.

### Gotchas specific to this story

1. **A dead loopback port does not refuse instantly on Windows.** It takes ~2.03 s (measured three
   ways). Every timeout shorter than that turns the dead case into a `ConnectTimeout` rather than a
   `ConnectError` — which is why AC 4's `except` must catch the timeout family, and why AC 3 sets a
   short connect deadline instead of accepting a 2 s stall on every post-crash launch.

2. **`httpx.ConnectTimeout` is *not* an `asyncio.TimeoutError`, and `ReadTimeout` is not `ConnectTimeout`.**
   Catch `httpx.HTTPError` (the family root) rather than enumerating leaves; Task 0 verifies the
   hierarchy rather than trusting it.

3. **Do not use `raise_for_status()`.** It converts a perfectly ordinary "that is not our app" into an
   exception you then catch — and it makes the non-2xx path indistinguishable from a transport
   failure in the log. Check `status_code` and return `None`.

4. **`asyncio.run` inside `run()` runs *before* uvicorn creates its loop.** Verified safe. But do not
   move the probe below `_serve` or inside any coroutine — `uvicorn.Server.run()` calls
   `asyncio.run` itself, and calling `asyncio.run` from inside a running loop raises.

5. **The refusal line must be printed after `sys.stdout.reconfigure(errors="replace")`.** It carries
   an em dash exactly like the launch line, and the reconfigure exists because a redirected stdout
   under a non-UTF-8 locale would otherwise raise `UnicodeEncodeError` on the one line that must
   never fail.

6. **`client.py` must name no port number** — not 8765, not an example port in a docstring. AD-4 puts
   the single mention in `server.DEFAULT_PORT`, and `test_server.py::TestNothingElseHardcodesThePort`
   AST-scans `src/` for it. (This is the exact trap that produced a c1-7 review finding: a docstring
   example carrying `port=8765`.)

7. **The write guard reads names, not intent.** No local in `client.py` may be called `session`,
   `sess`, `db`, `db_session`, `database`, `conn` or `connection` — a `conn.close()` would fail
   `test_import_boundary.py` for reasons that have nothing to do with databases.

8. **A stub `http.server` in a thread must be shut down *and* joined.** `shutdown()` returns before
   the thread has necessarily exited; a leaked listener on Windows surfaces as a failure in some later
   test. Put it in the fixture's teardown, not in each test.

9. **`asyncio_mode = "auto"`** — write `async def test_…` directly, with no `@pytest.mark.asyncio`.
   The probe functions are awaitable, so most of `test_client.py` is async; the `run()` cases in
   `test_server.py` stay sync (they call `asyncio.run` through `run()` itself — do **not** make those
   tests async, or you will be calling `asyncio.run` inside a running loop, Gotcha 4's failure mode
   inside the test).

10. **`mypy --strict` details.** `probe_health` returns `HealthResponse | None`; `live_instance`
    returns `DiscoveryRecord | None`; `httpx.Timeout` is a concrete class, so the `timeout: httpx.Timeout
    | None = None` parameter needs no cast; `response.status_code` is `int`;
    `HealthResponse.model_validate_json(response.content)` takes `bytes` and is fully typed. CI runs
    `mypy src/` on Linux — run `uv run mypy src/ --platform linux` locally too.

11. **The one behaviour a unit test cannot prove is the one the story is named for.** Two real
    processes contending is Task 5's live check; do not skip it because the suite is green.

### Testing standards

- New tests in `tests/unit/companion/test_client.py`; the `run()` cases join
  `tests/unit/companion/test_server.py`. Unmarked, fast, no `integration` marker — `--strict-markers`
  is on, do not invent one.
- Real loopback sockets over mocked transports (c1-3's ruling, restated): mocking `httpx` would prove
  only that a mock was called, and the failures this story catches — a connect that hangs, a body that
  is not our shape — live in the transport.
- **Assert observable state**: the file's bytes before and after, whether the preferred port is still
  bindable, what the stub server recorded. Never "a mock went uncalled".
- Discovery-file fixtures use `Path.write_text` / `write_bytes`, never `write_discovery` (c1-6's rule,
  restated by c1-7).
- **Verification before completion:** paste actual ruff / mypy / pre-commit / pytest output into the
  Debug Log. "Tests pass" without output is not acceptance — standing agreement from the epic-5/6
  retros.

### Previous story intelligence (c1-7, done 2026-07-26, PR #15 held open)

- **PR #15 is deliberately still open, and this story rides its branch.** Greptile flagged the
  `remove_discovery` TOCTOU that c1-7 had already homed here; Brad's ruling was to build c1-8 on the
  same branch and let #15 become a two-story PR. Task 0 encodes it — this is the one story in the epic
  that does **not** cut a fresh branch.
- **c1-7's review produced seven patch findings, and three of them are patterns to repeat here.**
  (a) *"Never raises" must be true of the whole function, not the happy path* — `read_discovery` and
  `remove_discovery` both had `discovery_path()` sitting outside their `except`. `probe_health` and
  `live_instance` make the same promise; make sure nothing (including
  `httpx.AsyncClient(...)` construction) sits outside the net. (b) *A test that asserts "some WARNING
  exists" pins nothing* — assert message substrings. (c) *A docstring that miscounts or misdescribes
  its own guarantees is a finding* — AC 16 exists because c1-7's docstring will otherwise be stale the
  moment this lands.
- **The vacuous-test lesson (c1-6, re-stated by c1-7 AC 15).** Where an AC names a mechanism, add an
  assertion that goes red when the mechanism is removed. Here that is: delete the `instance_id`
  comparison and `test_a_foreign_identity_is_treated_as_dead` must fail; delete the probe entirely and
  the refuse-and-proceed pair must disagree.
- **Log hygiene was a c1-6 finding and a c1-7 AC.** The token is not on this story's path at all —
  keep it that way, and do not log the `DiscoveryRecord` (its `repr` hides the token, but an
  `f"{record.token}"` would not).
- **Known pre-existing flake:** `test_list_decks_with_strategy_field`'s same-tick ordering. If a full
  run shows that one test red, it is the known flake, not a regression.

### Git intelligence

`HEAD = a82c032` on `feat/companion-c1-7-discovery-file-rendezvous`, working tree clean. Recent
rhythm on this branch: `3ea6732 feat(companion): discovery file as the sole rendezvous` → `ccaafb7
docs(companion): c1-7 story record` → `4781496 fix(companion): c1-7 code-review patches`. This story
adds its own `feat(companion): …` commit on the same branch; it changes no wire contract, adds no
reason token and needs no `!`.

Suggested commit: `feat(companion): single-instance enforcement with verified identity`.

### Latest technical information

Verified in this environment on 2026-07-26 — Python 3.12.13 · httpx 0.28.1 · pydantic 2.12.0 ·
FastAPI 0.140.0 · uvicorn 0.51.0, all at or above the spine's floors. No dependency is added,
upgraded or pinned by this story (`httpx>=0.28.1` is already in `pyproject.toml`; AC 13 only teaches
the mypy *hook* about it).

**Probe A — what answers, and how httpx reports it** (each row re-runnable in a few lines):

```
A1 nothing listening (timeout=1.0)      -> ConnectTimeout           after 1.11 s
A3 foreign server, HTML 200             -> 200 '<html>not the companion</html>'   in 0.015 s
A4 JSON 200 but {"status":"ok"} only    -> 200, and HealthResponse.model_validate_json -> ValidationError
A5 well-formed health + an extra key    -> 200 {'status':'ok','instance_id':'abc-123','extra':1}  (extra ignored)
A6 accepts but never answers (t=0.75)   -> ReadTimeout              after 0.77 s
A7 400 {"reason":"invalid_request"}     -> 400                      in 0.014 s
A8 request Host header httpx sends      -> '127.0.0.1:<port>'       (so a live companion's c1-5 Host check passes)
```

**Probe B — why the connect deadline is short.** A TCP connect to a *dead* loopback port on this
machine does not refuse promptly:

```
B1 raw socket.create_connection(timeout=2.0) -> TimeoutError              at 2.01 s
B1b asyncio.open_connection                  -> ConnectionRefusedError    at 2.05 s
B1c anyio.connect_tcp                        -> OSError                   at 2.05 s
B1d httpx timeout=0.25 / 1.0 / 3.0           -> ConnectTimeout 0.30 s / ConnectTimeout 1.03 s / ConnectError 2.03 s
B2 two consecutive asyncio.run() calls       -> OK   (run() probes, then uvicorn runs its own loop)
    default loop on Windows                  -> ProactorEventLoop
```

**Probe D — the exception hierarchy AC 4's single `except (httpx.HTTPError, ValueError)` rests on:**

```
issubclass(httpx.ConnectTimeout, httpx.HTTPError)   = True
issubclass(httpx.ReadTimeout,    httpx.HTTPError)   = True
issubclass(httpx.ConnectError,   httpx.HTTPError)   = True
issubclass(httpx.HTTPError,      ValueError)        = False   <- both tuple members are load-bearing
issubclass(pydantic.ValidationError, ValueError)    = True    (c1-7 probe 1, re-confirmed)
```

**Probe C — the baseline failure this story fixes, with two real processes.** Two
`src.companion.app.server.run(0)` launches against one `PLANESWALKER_DATA_DIR`:

```
1  discovery file written    : {'port': 64474, 'token': 'fqF7tA…', 'instance_id': 'd337280a-…'}
2  GET /health on live port  : 200 {'status': 'ok', 'instance_id': 'd337280a-…'}
3  identity matches record   : True
4  request headers sent      : {'host': '127.0.0.1:64474', 'accept': '*/*', …}   (no Authorization)
5  token in request headers  : False
6  second launch started too : True          <-- what this story changes
7  rendezvous now points at  : 64481 | same instance as first? False
8  first instance still up   : 200 {'status':'ok','instance_id':'d337280a-…'}   (live, unreachable via the file)
9  discovery file after stop : True          <-- a hard-killed instance leaves the stale file AC 10 reclaims
10 first stdout              : [planeswalker] companion running at http://127.0.0.1:64474 — open this URL…
```

Line 9 is worth keeping: killing the processes (no clean shutdown) left the file behind, which is the
crash case AD-15 describes and AC 10 handles — reproduced here without arranging for it.

**Baseline measured at `a82c032`:** **1,588 passed / 1 skipped / 45 deselected** (full suite,
`-m "not integration"`), **275 passed / 1 skipped** in `tests/unit/companion`, `uv run mypy src/` →
*Success: no issues found in 81 source files*. `httpx` ships `py.typed` (verified), so AC 13's hook
entry gives the hook the same view local mypy already has.

### Project Structure Notes

- `client.py` sits directly under `src/companion/`, is already enumerated in
  `test_import_boundary._LEAF_MODULES`, and is therefore classified with **no boundary-test edit**. It
  may import the stdlib, `pydantic`, `httpx`, `src.paths` and its sibling leaves — nothing else, in
  any role, including under `if TYPE_CHECKING:`.
- Pre-existing tracked files modified: `src/companion/app/server.py`, `src/companion/discovery.py`
  (docstring only), `.pre-commit-config.yaml`, `tests/unit/companion/test_server.py`,
  `_bmad-output/implementation-artifacts/deferred-work.md`,
  `_bmad-output/implementation-artifacts/sprint-status.yaml`, and the generated `plugin/` mirror.
  **Not** `pyproject.toml`, `uv.lock`, `src/paths.py`, `src/data/**`, `src/mcp_server/**` or any other
  file under `src/companion/app/`.
- Naming follows project conventions: `snake_case` functions, `UPPER_SNAKE` constants, Google
  docstrings on every public symbol, a module docstring at the top, `%`-style lazy log args, guard
  clauses over nesting, ruff line-length 100.

### References

- [epics-companion-app.md — Story 1.8](_bmad-output/planning-artifacts/epics-companion-app.md#L1110-L1138) — the source acceptance criteria · [Epic 1 framing](_bmad-output/planning-artifacts/epics-companion-app.md#L882-L888) · [FR-01](_bmad-output/planning-artifacts/epics-companion-app.md#L36-L39)
- The two consumers this story is shaped by: [Story 6.1 — the leaf client that probes before every push](_bmad-output/planning-artifacts/epics-companion-app.md#L2563-L2604) · [Story 1.9 — the dispatcher that will call `run()`](_bmad-output/planning-artifacts/epics-companion-app.md#L1140-L1168)
- ARCHITECTURE-SPINE.md — [AD-4](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L127-L141) · [AD-3](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L114-L125) · [AD-5](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L143-L157) · [AD-8](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L197-L209) · [AD-10](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L227-L240) · [AD-15](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L315-L327) · [Structural Seed](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L438-L462)
- [src/companion/app/server.py — `run()`](src/companion/app/server.py#L211-L254) — where the check lands, and the stdout reconfigure it must follow · [`bind_localhost_socket`](src/companion/app/server.py#L143-L187) — the fallback that already handles a foreign process on our preferred port
- [src/companion/discovery.py — `read_discovery`](src/companion/discovery.py#L178-L207) — the never-raising reader this story consumes · [`remove_discovery`](src/companion/discovery.py#L210-L260) — the docstring sentence AC 16 repairs, and the ownership guard AC 14 rules on
- [src/companion/contracts.py — `HealthResponse`](src/companion/contracts.py#L22-L44) — the shape the probe parses · [the module docstring that already promises this story](src/companion/contracts.py#L9-L14)
- [src/companion/app/routes/health.py](src/companion/app/routes/health.py#L1-L28) — why `/health` is unauthenticated
- [tests/unit/companion/test_import_boundary.py](tests/unit/companion/test_import_boundary.py#L113-L131) — `_LEAF_MODULES` already lists `client.py`, and the leaf's allowed surface · [the session-receiver names to avoid](tests/unit/companion/test_import_boundary.py#L86-L92)
- [tests/unit/companion/test_server.py](tests/unit/companion/test_server.py#L276-L330) — `_RecordingServe` + `recorded_serve` + `TestRun`, where the `run()` cases go · [`_Loopback`](tests/unit/companion/test_server.py#L26-L105) — the real-socket helper pattern to mirror
- [tests/unit/companion/conftest.py](tests/unit/companion/conftest.py#L48-L68) — the autouse data-dir isolation that now also protects `test_server.py`
- [deferred-work.md — the two items homed here](_bmad-output/implementation-artifacts/deferred-work.md#L736-L762)
- [c1-7 story record](_bmad-output/implementation-artifacts/c1-7-discovery-file-as-the-sole-rendezvous.md) — the reader/writer contract, the five decide-once rulings and the review findings
- [project-context.md](_bmad-output/project-context.md) — `%`-style lazy logging, ruff/mypy, Google docstrings, module docstrings

## Open questions for Brad

Neither blocks implementation.

1. **Should a refused launch exit `0` or non-zero?** Decide-once #3 chooses `0`: nothing failed, the
   app is running, and AD-15 rules out the supervisor for whom a status code would matter. The
   alternative — `raise SystemExit(1)` so a script can tell "I started it" from "it was already up" —
   is a one-line change. Recording it now so c1-9 inherits the choice rather than re-litigating it.
2. **Is an escape hatch wanted for the rare "I really do want a second one"?** None is built (scope,
   and `PLANESWALKER_DATA_DIR` already gives a clean second instance its own rendezvous, which is how
   the tests and probes here run two companions side by side). If a `--force` flag is ever wanted it
   belongs to c1-9, with the discovery file left alone.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the BMad `dev-story` workflow.

### Debug Log References

**Task 0 — state verification (all green, one recorded delta).**

```
git branch --show-current   -> feat/companion-c1-7-discovery-file-rendezvous
git rev-parse --short HEAD  -> a82c032
git status --porcelain      -> only sprint-status.yaml (M) + this story file (??)
gh pr view 15               -> {"baseRefName":"feat/companion-app","state":"OPEN",
                                "headRefName":"feat/companion-c1-7-discovery-file-rendezvous"}
src/companion/client.py            -> absent (only __init__/app/contracts/discovery present)
tests/unit/companion/test_client.py-> absent
_LEAF_MODULES                      -> lists "src/companion/client.py" at line 116 (no edit needed)
```

Probe D re-confirmed exactly as the story recorded it — **no deviation**, so AC 4's single
`except (httpx.HTTPError, ValueError)` stands as specified:

```
ConnectTimeout<=HTTPError  : True
ReadTimeout<=HTTPError     : True
ConnectError<=HTTPError    : True
HTTPError<=ValueError      : False   <- both tuple members are load-bearing
ValidationError<=ValueError: True
httpx 0.28.1  pydantic 2.12.0
```

Baseline suite:

```
uv run pytest -m "not integration" -q  -> 1588 passed, 1 skipped, 45 deselected in 68.77s   [MATCHES]
uv run pytest tests/unit/companion -q  -> 278 passed, 1 skipped in 4.62s                    [DELTA]
```

**Recorded delta, not chased:** the story's per-directory figure of *275 passed* is stale by 3;
the actual baseline is **278 passed / 1 skipped**. The full-suite number matches to the test, so
this is a stale note in the story rather than drift in the repo (c1-7's review patches added the
three). Every later count in this log is quoted against 278.

**Task 1 — red phase, then green.** The AC 4 matrix was written first and failed on the missing
module, which is the intended red:

```
tests\unit\companion\test_client.py:29: in <module>
    from src.companion import client, discovery
E   ImportError: cannot import name 'client' from 'src.companion'
=========================== 1 error in 0.15s ===========================
```

After `src/companion/client.py` landed: `24 passed in 9.58s`. The 9.58 s was almost entirely
teardown — `--durations=10` showed **thirteen** teardowns at 0.51 s each, which is
`BaseServer.shutdown()` waiting out `serve_forever`'s default 0.5 s poll interval. Passing
`poll_interval=0.01` took the module to **`24 passed in 1.67s`**.

**Non-vacuity mutation check (c1-7 AC 15's rule, run rather than asserted).** The `instance_id`
comparison in `live_instance` was temporarily replaced with `if False:`:

```
tests\unit\companion\test_client.py:415: in test_a_foreign_identity_is_treated_as_dead
    assert await client.live_instance(timeout=FAST) is None
E   AssertionError: assert DiscoveryRecord(port=52096, instance_id='inst-alpha') is None
====================== 1 failed, 23 deselected in 0.17s ======================
```

The mechanism is genuinely pinned, and the failure output doubles as evidence that
`DiscoveryRecord.token` really is `repr=False` — the token is absent from the rendered record.
Reverted immediately; `24 passed in 1.64s`.

**Tasks 2/3 — red phase for the runner half.** With the tests written and `run()` untouched:

```
8 failed, 6 passed, 33 deselected in 0.38s
```

The 6 that passed are the *proceeds* cases (stale file, foreign identity, clean machine) — they
already proceed today, which is exactly the non-vacuity pairing AC 17 asks for. After the `run()`
change: `tests/unit/companion/test_server.py -> 47 passed in 1.25s`.

**Task 4 — the pre-commit mypy hook (AC 13).** Added `httpx>=0.28.1`; the hook rebuilt its isolated
environment and passed, so **AC 13's revert-and-home rule did not fire** — no pre-existing errors
surfaced in `scryfall_api.py` or `spellbook_api.py`:

```
[INFO] Initializing environment for https://github.com/pre-commit/mirrors-mypy:fastapi>=0.139.2,
       pydantic>=2.12.0,sqlalchemy>=2.0.44,numpy>=2.0.0,mcp>=1.27.0,platformdirs>=4.0.0,
       uvicorn>=0.51.0,httpx>=0.28.1.
mypy.....................................................................Passed
```

**Task 5 — quality gates (AC 18), actual output.**

```
uv run ruff check .                 -> All checks passed!
uv run ruff format --check .        -> 277 files already formatted
uv run mypy src/                    -> Success: no issues found in 82 source files
uv run mypy src/ --platform linux   -> Success: no issues found in 82 source files
uv run pre-commit run mypy --all-files -> mypy...Passed
uv run pytest -m "not integration" -q  -> 1626 passed, 1 skipped, 45 deselected in 49.27s
uv run pytest tests/unit/companion -q  -> 316 passed, 1 skipped in 5.21s
```

1626 − 1588 = **+38**, exactly the 24 new `test_client.py` cases plus the 14 new
`TestSingleInstanceCheck` cases. No pre-existing test changed behaviour; the known
`test_list_decks_with_strategy_field` flake did not appear. mypy's file count rose 81 → 82 with
`client.py`.

**Task 5 — live check with two real processes (AC 8/9/12).** Two `run(0)` launches against one
`PLANESWALKER_DATA_DIR` in a temp directory:

```
1  discovery file written    : port=60317 instance=df2f52f5
2  GET /health on live port  : 200 {'status': 'ok', 'instance_id': 'df2f52f5-…'}
3  identity matches record   : True
4  second launch exit status : 0   (after 0.73s)
5  discovery file unchanged  : True
6  first instance still up   : True
7  and still answering       : 200 {'status': 'ok', 'instance_id': 'df2f52f5-…'}
RESULT: PASS
```

The two stdout lines the AC asks for (`?` is the cp1252 console rendering the em dash, not a
missing character — the reconfigure guard is doing its job in the capture harness too):

```
--- first process stdout ---
[planeswalker] companion running at http://127.0.0.1:60317 ? open this URL in your browser (Ctrl-C to stop)
--- second process stdout ---
[planeswalker] companion is already running at http://127.0.0.1:60317 ? open that URL, or stop the other instance before starting a new one
```

Compare against the baseline probe C in the story notes, where line 6 read *"second launch started
too : True"* and line 7 showed the rendezvous hijacked to a different port. Both are now closed.
The first instance's uvicorn access log recorded exactly **one** `GET /health` attributable to the
second launch — it asked once and sent nothing else.

**Task 5 — live reclaim check (AC 10), added because it is the other half of the behaviour.** The
first instance was hard-killed (no clean shutdown, so `remove_discovery` never ran) and a second
launched against the stale file:

```
1  first instance published  : port=60399 instance=25748c92
2  stale file left behind    : True  (121 bytes)
3  second start took         : 1.72s  (no multi-second stall on the dead port)
4  new instance took over    : True
5  new instance id           : b451bec5  port=60407
--- second (reclaiming) process stdout ---
[planeswalker] companion running at http://127.0.0.1:60407 ? open this URL in your browser (Ctrl-C to stop)
RESULT: PASS
```

Line 3 is the point of AC 3's split timeout: the whole reclaiming launch — interpreter start,
probe against a dead port, bind, lifespan, publish — took 1.72 s, well under the ~2 s that a
*single* undivided connect would have burned before even reporting refusal.

**One harness bug worth recording, because its failure output is misleading.** The first attempt at
the reclaim check reported `RESULT: FAIL` with the second launch refusing. That was correct
behaviour meeting a broken harness: it spawned via `uv run … shell=True`, so `Popen.kill()` reaped
the shell wrapper and left the real companion running and answering. Spawning
`.venv/Scripts/python.exe` directly fixed it. Noted because anyone re-running these probes will hit
the same trap, and because the "failure" was itself an unplanned confirmation that the refusal
works against a genuinely live process.

**Scope confirmation (AC 20).** The forbidden-path command returned empty:

```
git status --porcelain -- tests/unit/companion/test_app.py … src/companion/app/routes
(no output)
```

### Completion Notes List

- **All 20 acceptance criteria are met.** The leaf gained its third and final module,
  `src/companion/client.py`, exporting exactly the six names AC 1 specifies; `run()` now refuses a
  verified-live instance before it resolves a port, binds a socket or builds an app.
- **AC 4's matrix is covered row for row against real loopback listeners**, in three flavours
  because httpx reports them three different ways: an HTTP stub returning arbitrary
  status/bytes/content-type, a bare listening socket that completes the handshake and never answers
  (`ReadTimeout`), and a port with nothing on it (`ConnectTimeout`). Every "returns `None`" case
  sits beside the well-formed stub returning a populated `HealthResponse` from the same call.
- **The `except Exception` prohibition is tested, not just documented** —
  `test_a_memory_error_is_not_app_not_running` monkeypatches `model_validate_json` to raise
  `MemoryError` and asserts it propagates.
- **The non-2xx path is proven not to travel through an exception** by asserting the DEBUG record
  names the status code, which `raise_for_status()` could not produce.
- **AC 6 is pinned in the scenario it exists for:** a *foreign* stub on the recorded port, with the
  planted token searched for across the request line, every header and the body — plus an explicit
  `authorization` header check and an empty-body assertion.
- **Deviation to flag, small and deliberate: `run()` reads the discovery file a second time on the
  reclaim path only.** AC 7 names `asyncio.run(client.live_instance())` as the decision call and AC
  5 makes that "the whole question in one call", so `live_instance` returns `None` for both *no
  file* and *dead file* — but AC 10 wants an INFO reclaim log that must **not** fire on a clean
  first start. Rather than widen the leaf's return type for a log line (which would also push the
  message into c6-1's per-push path, the noise AC 4 exists to avoid), a private
  `server._note_reclaimed_entry()` re-reads the file purely to decide whether there is anything to
  say. The cost lands where it should: a clean machine and a live instance each pay one read, and
  only the post-crash path pays a second. Nothing about `run()`'s behaviour depends on it, and
  `test_a_clean_machine_logs_no_reclaim` is the non-vacuity guard.
- **Both c1-7 deferrals were ruled on in place (AC 14), neither by silence.** The Windows
  `os.replace`-while-open item is **still accepted and re-homed to c6-1**, with the note AC 14 asks
  for: c1-8 reads the file through `read_discovery`, which closes its handle before the probe is
  dialled, in a launch that either returns without publishing or publishes much later from the
  lifespan — so a process cannot collide with itself. The `remove_discovery` TOCTOU is **accepted
  and materially narrowed**, entry kept: the second live instance the window needs is now the case
  this story refuses, so its reachability depends on the simultaneous-launch race below rather than
  on ordinary use.
- **The new residual is homed, not hidden (AC 15).** A new c1-8 section in `deferred-work.md`
  records that the check is check-then-act — two launches inside the same few hundred milliseconds
  can still both start — with the framing AC 15 requires (an OS-level mutex is a design decision,
  and the port-as-lock option would invert this story's own ordering). The wedged-instance case is
  recorded in the same section: a companion whose event loop is blocked past the 2 s read is judged
  dead, accepted as the right side of a ~130× margin against a measured ~15 ms response.
- **`client.py` names no port number anywhere**, including its docstrings — Gotcha 6, and the exact
  trap that produced a c1-7 review finding. `test_server.py::TestNothingElseHardcodesThePort` still
  passes untouched.
- **No local in `client.py` is named `session`/`sess`/`db`/`db_session`/`database`/`conn`/
  `connection`** (Gotcha 7): the client is `client`, the response `response`, the parsed body
  `health`.
- **One structural choice worth reviewing:** the stub-server machinery lives in `test_client.py` as
  a `StubFleet` helper class with a four-line fixture in each of the two modules, mirroring the
  existing `_Loopback`/`loopback` pair. Importing the *fixture* into `test_server.py` was tried
  first and rejected — a module-level `stub_server` binding plus a test parameter of the same name
  is a ruff **F811** redefinition, nineteen times over — and `conftest.py`, the usual home for a
  shared fixture, is out of bounds under AC 20.
- **Open Question 1 is unchanged and still open for Brad:** a refused launch exits `0` per
  Decide-once #3, and `test_a_refusal_returns_rather_than_raising` pins it. Flipping it to a
  non-zero status is a one-line change plus one test edit.
- The `deferred-work.md` c1-8 section names **c1-9** as the natural revisit point for a launch-time
  lock, since that story owns the console-script entry point.

### File List

**New**

- `src/companion/client.py` — the leaf identity probe: `LOOPBACK_HOST`, `HEALTH_PATH`,
  `PROBE_TIMEOUT`, `base_url()`, `probe_health()`, `live_instance()`
- `tests/unit/companion/test_client.py` — 24 tests: AC 4's matrix over real loopback stubs, AC 5's
  short-circuit and identity comparison, AC 6's no-token proof, AC 1/3's exported surface
- `_bmad-output/implementation-artifacts/c1-8-single-instance-enforcement-with-verified-identity.md`
  — this story record

**Modified**

- `src/companion/app/server.py` — `run()` refuses a verified-live instance before the bind; new
  private `_note_reclaimed_entry()`; module docstring gains its fourth load-bearing decision;
  `asyncio` and the two leaf imports added
- `src/companion/discovery.py` — one docstring sentence in `remove_discovery` (AC 16); no
  signature, behaviour or logic change (verified by `git diff`)
- `tests/unit/companion/test_server.py` — new `TestSingleInstanceCheck` (14 tests) and a
  `stub_server` fixture; imports `StubFleet`/`health_bytes`/`plant_discovery` from `test_client.py`
- `.pre-commit-config.yaml` — `httpx>=0.28.1` in the mypy hook's `additional_dependencies` (AC 13)
- `_bmad-output/implementation-artifacts/deferred-work.md` — rulings on both c1-7-homed items
  (AC 14) and a new c1-8 section with two entries (AC 15)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `c1-8` → `in-progress` → `review`
- `plugin/server/src/companion/client.py` (new), `plugin/server/src/companion/app/server.py`,
  `plugin/server/src/companion/discovery.py` — generated mirror, rebuilt via
  `uv run python -m scripts.build_plugin` (AC 19)

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-26 | Code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor): 2 decisions, 6 patches, 8 dismissed. Brad's rulings: patch the missing whole-probe deadline (a **sanctioned widening of AC 4's net** — `asyncio.timeout(_PROBE_TOTAL_SECONDS = 5.0)` around the probe body, `TimeoutError` folded into the `None` outcome, private so AC 1's six exports stand); accept the `StubFleet` cross-test-module share as documented. Patches applied: `trust_env=False` on the probe's `AsyncClient` (the review's one high — httpx grants loopback no proxy exemption, so `HTTP_PROXY` would have routed the probe to the proxy, judged the live companion dead and resurrected the baseline duplicate-instance failure; also keeps `.netrc` from attaching an `Authorization` header, AC 6); `probe_health` docstring now says what the code does (anything other than 200 is foreign, not merely "non-2xx"); the reclaim INFO reworded to cover the foreign-identity case and to say *will* reclaim (the publish is the lifespan's, later, maybe never); `deferred-work.md` wording repaired (the reclaim path reads the file twice, and the simultaneous-launch window is a couple of seconds, not "a few hundred milliseconds" — a human double-launch can hit it); live-stub tests dropped the 0.25 s `FAST` deadline (scoped now to dead-or-silent cases only, per its own docstring); the reclaim-log WARNING sweep scoped to `src.*` loggers. Both new guards mutation-checked red→green (`trust_env` removed → proxy test fails; `asyncio.timeout` removed → drip test crawls 30 s and fails its elapsed assertion). Gates: ruff clean, mypy clean both platforms (82 files), **1,629 passed / 1 skipped / 45 deselected** (+3: total-deadline pin, proxy-ignored, drip cut-off), companion dir 319/1. Plugin mirror rebuilt. Status → done. |
| 2026-07-26 | Story c1-8 implemented. `src/companion/client.py` lands the leaf's AD-4 half — `probe_health` (never raises; one `except (httpx.HTTPError, ValueError)` around the whole body, status checked rather than `raise_for_status`d) and `live_instance` (no file → no network call at all; a record returned only when the echoed `instance_id` matches). `run()` now asks that question before it resolves a port, binds a socket or builds an app, printing the "already running" line and returning `0` when a companion is verified live, and reclaiming a stale or foreign entry silently otherwise — deleting nothing, since c1-7's publish is already atomic. Verified with two real processes: the second launch exits 0 in 0.73 s leaving the first instance's `companion.json` byte-identical and still serving, closing the baseline failure probe C measured; and a hard-killed instance's stale file is reclaimed by the next start in 1.72 s end to end, which is the measured payoff of AC 3's short connect deadline. Both c1-7 deferrals ruled on in place (replace-while-open → still accepted, re-homed to c6-1, with the note that a process cannot collide with itself; `remove_discovery` TOCTOU → accepted and materially narrowed, entry kept) and the new check-then-act residual homed in a fresh c1-8 section alongside the wedged-instance case. `httpx` added to the pre-commit mypy hook, which passed without surfacing pre-existing importer errors. One deliberate deviation: `run()` re-reads the discovery file on the reclaim path only, so AC 10's INFO log can fire on a reclaim without firing on a clean first start — rather than widening the leaf's return type and pushing that message into c6-1's per-push path. Gates green: ruff clean, mypy clean on both platforms (82 files), **1,626 passed / 1 skipped / 45 deselected** (+38 = 24 new client tests + 14 new `run()` tests) against the 1,588 baseline. Plugin mirror rebuilt. Status → review. |
| 2026-07-26 | Story c1-8 created from epics Story 1.8 + AD-4/AD-3/AD-5/AD-15, with every load-bearing claim measured in this environment rather than assumed: a dead loopback port takes ~2.03 s to report refusal on Windows (raw socket, asyncio and httpx agree) — which is why the probe splits its timeout into a short connect and a longer read; two consecutive `asyncio.run` calls are legal, so the sync runner can drive the async leaf probe; and, most importantly, two real companion launches at the baseline commit were shown to produce two live instances with the second hijacking the rendezvous while the first stays up and unreachable. Five decide-once rulings: the probe lives in `client.py` (the seed's module) not `discovery.py`; the leaf is async-only and the runner adapts; a refusal exits `0`; a reclaim deletes nothing (c1-7's publish is already atomic); and identity is *compared*, never merely fetched. Rules on both deferrals homed here by c1-7 (replace-while-open → re-homed to c6-1; `remove_discovery` TOCTOU → accepted, materially narrowed) and homes one new residual (two simultaneous launches remain a check-then-act race; an OS-level mutex is a design decision, not a tweak). Also catches that the pre-commit mypy hook has no `httpx`, so the new leaf's httpx calls would be silently `Any` in the hook while local mypy checks them. Baseline re-measured at `a82c032`: 1,588 passed / 1 skipped / 45 deselected (275 passed / 1 skipped in `tests/unit/companion`). Per Brad's 2026-07-26 ruling the story is built **on c1-7's branch** and PR #15 becomes a two-story PR. Status → ready-for-dev. |

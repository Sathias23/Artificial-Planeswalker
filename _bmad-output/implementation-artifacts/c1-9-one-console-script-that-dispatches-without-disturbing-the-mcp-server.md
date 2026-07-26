---
baseline_commit: 8bfc909
epic: c1
story: c1-9
work_branch: feat/companion-app
story_branch: feat/companion-c1-9-console-script-dispatcher
---

# Story C1.9: One console script that dispatches, without disturbing the MCP server

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad following the README,
I want `uv run artificial-planeswalker companion` to start the backend while the bare command still
runs the MCP server,
so that there is a single documented entry point and no existing MCP client configuration breaks.

**Why this story is last in the epic, and what it is really closing.** The dispatcher itself is the
small half: `main()` grows a branch, and AD-14 has already verified that no MCP client configuration
touches the console script. The large half is everything eight stories deliberately left owing to
this one, and all of it is measurable at the baseline commit:

- **Five comments in `src/companion/app/` say "no root handler exists until c1-9."** They are not
  asides — c1-3's port-fallback WARNING, c1-7's discovery-skip WARNING, c1-8's reclaim INFO and
  c1-5's security WARNING each chose their *level* around the fact that nothing surfaces a log record
  today. This story is the one that makes the companion process actually log (AD-15), and those
  sentences become false the moment it does.
- **`resolve_preferred_port`'s docstring already promises `--port`**: *"c1-9 feeds a user-supplied
  `--port` through *explicit*, so both must validate identically"*
  ([server.py:76](src/companion/app/server.py#L76)).
- **The launch race is real, and it reproduces on this machine in 6 ms.** Two `run(0)` launches
  spawned back to back against one `PLANESWALKER_DATA_DIR` at `8bfc909`:

  ```
  both spawned within 6 ms
  process 1 stdout: [planeswalker] companion running at http://127.0.0.1:58448 ...
  process 2 stdout: [planeswalker] companion running at http://127.0.0.1:58453 ...
  discovery file: 58453
  processes still alive: 2      <- the race reproduced
  ```

  Two live companions, one rendezvous, and the instance on 58448 is unreachable by every agent tool
  — the *baseline* failure c1-8 was written to fix, surviving in the window c1-8 narrowed from
  forever to startup. Brad's ruling of 2026-07-26 (commit `8bfc909`) added the fix to this story's
  ACs in the epic file and to `deferred-work.md`: a **process-lifetime held OS advisory lock**, which
  also collapses to zero the reachability of the `remove_discovery` TOCTOU that Greptile held PR #15
  at 3/5 over.

## Acceptance Criteria

1. **The dispatcher is `main()` in `src/mcp_server/__main__.py`, and its return value is the exit
   status (AD-14).** The signature becomes `main(argv: Sequence[str] | None = None) -> int`; `argv`
   defaults to `sys.argv[1:]` and exists so tests never mutate `sys.argv`. The console-script wrapper
   installed in `.venv/Scripts/artificial-planeswalker.exe` is **`sys.exit(main())`** — read out of
   the wrapper, not assumed:

   ```python
   from src.mcp_server.__main__ import main
   if __name__ == "__main__":
       ...
       sys.exit(main())
   ```

   so returning `0` exits `0` and returning `2` exits `2` with no `sys.exit` call of our own. The
   module footer becomes `raise SystemExit(main())` so `python -m src.mcp_server` propagates the same
   status. The entry point named in `pyproject.toml` (`src.mcp_server.__main__:main`) is **not**
   changed — the `.exe` wrapper imports `main` by name and would otherwise need a re-sync.

2. **No arguments runs the MCP server exactly as today, and stdout still carries only the JSON-RPC
   stream (AD-14, AD-15).** The current body of `main()` moves verbatim into a private
   `_run_mcp_server() -> int`: transport read from `MCP_TRANSPORT` (default `stdio`),
   `_log_startup_diagnostics()`, then `build_server().run(transport=transport)`, in that order, then
   `return 0`. Nothing is added to that path — no logging configuration, no import of anything under
   `src/companion/`, no `print`. The measured baseline this protects (real subprocess, one MCP
   `initialize` handshake, `PLANESWALKER_DATA_DIR` pointed at a temp dir):

   ```
   === STDOUT lines: 1
     JSON-RPC ok: keys= ['id', 'jsonrpc', 'result'] | id= 1
   === STDERR lines: 5
      [planeswalker] data_dir=...    [planeswalker] database=... exists=False size=0
      [planeswalker] env PLANESWALKER_DATA_DIR=...  CARDS_DATABASE_URL=None  LOCALAPPDATA=...
   ```

3. **`companion` starts the backend in the foreground, and accepts `--port` (AD-14, AD-15).**
   `_run_companion(args: list[str]) -> int` accepts `--port N` and `--port=N`, in that one form pair
   only, and passes the parsed integer straight to `run(port)`.

   - **A non-integer `--port` is a usage error** (AC 4's exit `2` and usage text): unlike a stale
     environment variable it is something the user typed in *this* invocation, with the command still
     on screen to fix.
   - **An out-of-range integer is not.** It flows through to
     [`resolve_preferred_port`](src/companion/app/server.py#L71-L117), which logs a warning and uses
     the default — identical treatment to `PLANESWALKER_COMPANION_PORT`, which is exactly what that
     function's docstring promises and is now finally true.
   - Any other argument after `companion` — including a bare `--port` with no value — is a usage
     error. `run()`'s signature is unchanged.

4. **An unknown subcommand exits non-zero with usage text naming the valid subcommands.** Unknown
   subcommand or malformed option → usage on **stderr**, exit **2** (the conventional usage-error
   status, and what `argparse` would have used); `-h` / `--help` → the same usage text on **stdout**,
   exit **0**, because a user asking for help has not made an error. The usage text names the bare
   invocation, `companion`, `--port` and `--help`, and **must not name a port number** —
   `test_server.py::TestNothingElseHardcodesThePort` AST-scans `src/` and `scripts/` for the numeric
   literal, `__main__.py` is inside that scan, and `DEFAULT_PORT` cannot be imported here at module
   level (AC 5). Say "the default port" in words.

5. **The companion import is function-local, and it is the only such exemption in the codebase
   (AD-3).** `from src.companion.app.server import run` sits **inside** `_run_companion`, never at
   module level, and **never** under `if TYPE_CHECKING:` — the boundary test counts a
   `TYPE_CHECKING` import as module-level in every role, so no annotation in this file may name a
   companion-app type (use no annotation, or a string). This needs **no edit** to
   `tests/unit/companion/test_import_boundary.py`: `_APP_IMPORT_EXEMPT` already contains
   `src/mcp_server/__main__.py`, there is already a committed clean-case fixture named
   `dispatcher-function-local-exemption`, and there are already two violation fixtures proving the
   module-level and `TYPE_CHECKING` forms still fail. If that file needs a change, that is a
   **finding**, not an edit. The reason the exemption is function-local: a bare
   `artificial-planeswalker` invocation must never import FastAPI or uvicorn, which is the whole
   point of AD-3 and is the property AC 2 preserves.

6. **The companion process configures the root logger; the MCP process never does (AD-15).**
   `logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=…)` is called in
   `_run_companion` **before** `run()` is called — the first records worth seeing (c1-8's reclaim
   INFO, c1-3's fallback WARNING) are emitted inside `run()` before uvicorn exists, so configuring it
   any later loses them. It lives in the entry point rather than in `run()` because library code does
   not configure logging (project-context.md) and because `run()` must stay callable from tests
   without a global side effect.

   - **INFO, not DEBUG.** `read_discovery` and `probe_health` log their ordinary "nothing there"
     outcomes at DEBUG deliberately; a DEBUG root would put that chatter on every c6-1 push.
   - **stderr, not stdout.** The deliberate user-facing lines are already `print`ed to stdout by
     `run()`; AD-15's "logs freely to stdout and stderr" is satisfied by uvicorn's own access log
     (stdout) plus this handler (stderr) — verified below.
   - **Verified to survive uvicorn (uvicorn 0.51.0, this environment).** `uvicorn.Config(...)`
     applies `LOGGING_CONFIG` via `dictConfig`, and that config has
     `disable_existing_loggers: False` with **no `root` key**, so the handler installed here stays:

     ```
     INFO src.companion.app.server: INFO from a src.* logger AFTER uvicorn.Config applied its dictConfig
     root level: INFO handlers: [<StreamHandler <stderr> (NOTSET)>]
     uvicorn logger propagate: False   (uvicorn's own records do not double-print through root)
     ```

7. **The comments that say a root handler does not exist are repaired — levels are not changed.**
   Six sentences across four files become false with AC 6, and this project treats a docstring that
   misdescribes its own guarantees as a finding. Repair each in place, changing **no behaviour and no
   log level**: the WARNING choices stand on their own merits (a bind fallback and an unwritable
   rendezvous *are* warnings), and c1-8's reclaim INFO simply becomes visible, which is the payoff.

   | File | What is now stale |
   | --- | --- |
   | [server.py:187-188](src/companion/app/server.py#L187-L188) | "no root handler is configured yet (see run())… an INFO record here would be dropped" |
   | [server.py:239-242](src/companion/app/server.py#L239-L242) | "no root handler exists until c1-9 … this record is invisible in a real run today" |
   | [server.py:270-272](src/companion/app/server.py#L270-L272) | `run()`'s docstring: "no story has yet configured a root handler, so an INFO record … would be dropped entirely" |
   | [main.py:49-51](src/companion/app/main.py#L49-L51) | "because no root handler is configured until c1-9 and `logging.lastResort` only surfaces WARNING and above" |
   | [security.py:172-174](src/companion/app/security.py#L172-L174) | "no story has configured a root logger yet (c1-9 owns that)" |
   | [errors.py:380-381](src/companion/app/errors.py#L380-L381) | "even though no story has configured a root logger yet (c1-9 owns that)" |

   `run()`'s docstring keeps its *other* reason for `print` over `logging` — logging writes to stderr
   and AD-15 puts the launch line on stdout — which remains true and is now the whole reason.
   [server.py:76](src/companion/app/server.py#L76)'s forward reference to c1-9's `--port` becomes
   present tense. Note in the [server.py:187](src/companion/app/server.py#L187) repair that the bind
   fallback is now announced twice (a WARNING record *and* the stdout line `run()` prints); that
   duplication is accepted, not fixed here.

8. **The single-instance lock is a new app-layer module, `src/companion/app/singleton.py`.** It
   exports exactly:

   - `LOCK_FILENAME = "companion.lock"`;
   - `lock_path() -> Path` — `src.paths.data_dir() / LOCK_FILENAME`, resolved **at call time** for
     c1-7's reason (`data_dir()` ends in a `mkdir`, so a module-level call would create the user's
     data directory at import and break AD-10's inertness);
   - `acquire_instance_lock() -> int | None` — the open file descriptor when the lock was taken,
     `None` when **another process (or another descriptor) already holds it**;
   - `release_instance_lock(fd: int) -> None` — closes the descriptor, which is what releases the
     lock; never raises.

   It is **app-layer, not a leaf**, and that is a decision: taking this lock is the process runner's
   job and no agent-side caller may ever take it, so putting it in the leaf would both imply
   MCP-side use and force an edit to `_LEAF_MODULES`. Living under `src/companion/app/` means the
   enumeration pin skips it with no boundary-test edit at all.

   The platform split is a module-level `sys.platform` branch, because that is the form mypy
   narrows on both platforms:

   ```python
   if sys.platform == "win32":
       import msvcrt
   else:
       import fcntl
   ```

9. **Non-blocking, and the right primitive on each platform.**

   - Windows: `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)` — **`LK_NBLCK`, never `LK_LOCK`**, which
     blocks and retries ten times over ten seconds.
   - POSIX: `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` — **`flock`, never `lockf`/`F_SETLK`.**
     Record locks are owned by the *process*, not the descriptor: a second `lockf` in the same
     process would succeed (silently defeating the test strategy of AC 15) and closing *any*
     descriptor to the file would drop the lock. `flock` is per open-file-description, which is the
     semantics this design needs and the primitive the epic AC names.

   One byte at offset 0 is locked; the file's contents are irrelevant and it stays zero-length.

10. **Held for the process's lifetime, and never deleted (AD-15).** The descriptor is acquired in
    `run()` and closed only in `run()`'s outermost `finally` — so the lock is held across the whole
    `_serve` call, and on any death (Ctrl-C, kill, crash, blue screen) the kernel releases it. This
    is why the design is a *held* lock rather than an `O_EXCL` create-and-delete file: there is no
    stale-lock state to recover from and no PID-liveness heuristic to get wrong, which is what makes
    it compatible with AD-15's stance that a crash is ordinary.

    **The lock file itself is never unlinked** — not on clean shutdown, not on reclaim. Deleting it
    is a correctness bug, not untidiness: on POSIX `flock` binds to the inode, so unlink + recreate
    hands a second process a *different* file to lock and both would think they own the machine. It
    is a **separate file** from `companion.json` (the rendezvous stays c1-7's atomic publish; the
    lock is never read for data, never parsed, and carries no port, token or identity), and it lives
    under `src.paths.data_dir()` so `PLANESWALKER_DATA_DIR` isolates it exactly as it isolates the
    rendezvous — which is what keeps the autouse `isolated_data_dir` fixture contention-free and what
    lets two deliberate instances coexist under different data directories.

11. **Exactly one failure is swallowed, and it is the one that means "someone else has it".** Only
    the lock call sits inside `except OSError` → close the descriptor we opened (**no fd leak on the
    contention path**) → log at DEBUG → `return None`. The `os.open` deliberately sits **outside**
    that guard: a data directory we cannot even open a file in will fail c1-7's discovery publish
    moments later anyway, and c1-7's Decide-once #3 already rules that a launch which cannot claim
    its rendezvous should fail loudly rather than half-start. `release_instance_lock` wraps its
    `os.close` in `except OSError` with a WARNING and never raises, because it runs in a `finally`.

    Measured on this machine (Python 3.12.13, win32) — contention reports as `PermissionError`
    (`errno 13`), which is indistinguishable from a real permission problem, and that is precisely
    why the `os.open` is outside the guard:

    ```
    1 first open ok
    2 second open of the same file in one process: allowed (Python's open does not deny sharing)
    3 first acquire: OK
    4 second acquire, same process, other fd: FAILED as wanted -> PermissionError errno=13 (EACCES)
    5 after closing the holder, re-acquire on the other fd: OK  (close releases)
    6 acquire while another PROCESS holds it: FAILED as wanted -> PermissionError errno=13
    7 after HARD KILL of the holder, acquire: OK — kernel released, no stale-lock state
    8 lock file still present afterwards: True, size 0
    ```

12. **`run()`'s ordering: probe first, then lock — and the lock is released last.** The c1-8 identity
    probe stays exactly where it is and keeps its behaviour; the acquire goes **below** the refusal
    and **above** `_note_reclaimed_entry`, `resolve_preferred_port` and the bind:

    ```
    reconfigure stdout                      (unchanged — the refusal lines carry em dashes)
    live = asyncio.run(client.live_instance())
    if live is not None: print "already running at <url>"; return      (c1-8, unchanged)
    lock = singleton.acquire_instance_lock()
    if lock is None: print the contention line; return                 (new)
    try:
        _note_reclaimed_entry() / resolve_preferred_port / bind / build_app / print / _serve
        (the existing inner try/finally that closes the socket is untouched)
    finally:
        singleton.release_instance_lock(lock)
    ```

    Probe-before-lock is a decision with a reason: the probe is the branch that can name *where* the
    other instance is, it keeps every c1-8 assertion true unedited (a refusing launch still never
    opens a file descriptor, binds a port or builds an app), and it leaves the lock as exactly what
    the epic AC calls it — the atomic *whether*, not the informative *who*. The release is in the
    **outer** `finally`, after the socket close, so the lock outlives every other resource.

13. **The contention refusal is one line, and it does not re-probe.** When `acquire_instance_lock()`
    returns `None`:

    ```
    [planeswalker] another companion is already starting up — wait for it to print its URL, or stop it before starting a new one
    ```

    printed (not logged) after the stdout reconfigure, then `run()` **returns** — exit `0`, matching
    c1-8's Decide-once #3, and leaving non-zero reserved for AC 4's usage errors. There is
    deliberately **no second probe** to try to name a URL: reaching this branch means the probe has
    already answered "nothing findable is running", so no URL can be named honestly, and a second
    probe would add up to five seconds to a path whose whole purpose is to get out of the way fast.
    A refusal here touches nothing else — no `_note_reclaimed_entry`, no port resolution, no bind, no
    app, and the discovery file is left byte-identical.

14. **Neither `.mcp.json` needs changing, and a test says so (AD-14).** Both files invoke
    `python -m src.mcp_server` directly — the repo root's
    `{"command": "uv", "args": ["run", "python", "-m", "src.mcp_server"]}` and `plugin/.mcp.json`'s
    `["run", "--directory", "${CLAUDE_PLUGIN_ROOT}/server", "python", "-m", "src.mcp_server"]` — so
    no MCP client configuration passes through the console script at all. Extend
    `tests/integration/mcp_server/test_entry_point.py`'s existing `test_mcp_json_registers_server`
    with a sibling for the **committed** `plugin/.mcp.json`, each asserting the args end with
    `python -m src.mcp_server` and that **no subcommand follows** — the assertion that would go red
    if a future story "helpfully" rewrote them to `artificial-planeswalker companion`. Do not touch
    `scripts/build_plugin.py`'s generators or `tests/integration/test_build_plugin.py`, which already
    pins the generated forms.

15. **Tests, and where each lands.** All unmarked (`--strict-markers` is on; AD-10's one `integration`
    test is c5-8's, not this one).

    - **`tests/unit/companion/test_singleton.py` (new).** Real descriptors, no mocks: acquire returns
      an int; a second acquire from another descriptor in the same process returns `None` (the AC 9
      primitive choice is what makes this true — it is the cheap, honest contention test, and it is
      why `lockf` is banned); release then acquire succeeds; the file is created under
      `PLANESWALKER_DATA_DIR` with the name `LOCK_FILENAME` and is **still present** after a release;
      `lock_path()` follows a `monkeypatch.setenv` of the data dir; an unopenable path (monkeypatch
      `lock_path` to a file inside a directory that does not exist) **propagates** `OSError` rather
      than returning `None` — the AC 11 split, which is otherwise the easiest thing in the story to
      get silently wrong; `release_instance_lock` on an already-closed descriptor does not raise.
    - **`tests/unit/companion/test_server.py` (updated).** Beside `TestSingleInstanceCheck`: with the
      test itself holding the lock, `run()` prints the contention line, never calls `_serve` (the
      existing `recorded_serve` fixture), leaves the preferred port free and leaves `companion.json`
      byte-identical; **paired with** the existing proceeds-case so neither can pass by refusing
      everything. Plus: after a normal `run()` the lock is released (a fresh acquire succeeds) and
      the lock file still exists; the release happens even when `_serve` raises.
    - **`tests/integration/mcp_server/test_entry_point.py` (updated).** The dispatcher matrix —
      `main([])` runs the MCP path (fake `build_server`) and writes **nothing** to stdout while the
      diagnostics reach stderr; `main(["companion"])` calls a patched
      `src.companion.app.server.run` with `None`; `--port 1234` and `--port=1234` both arrive as the
      integer `1234`; `--port abc`, a bare `--port`, `--bogus` and an unknown subcommand each return
      `2` with usage on stderr and never call `run`; `--help` returns `0` with usage on stdout; the
      usage text names `companion`; the root logger gains a handler on the companion path and gains
      **none** on the MCP path. This file is the one that already owns `__main__.py` and `.mcp.json`;
      keep the tests together there rather than opening a second home for one module.

    **Two hazards that must be handled in the tests, not discovered by them.** (a) `basicConfig`
    mutates global state — every dispatcher test that reaches the companion branch must run under a
    fixture that snapshots `logging.root.handlers` and `logging.root.level` and restores both at
    teardown, or the rest of the session inherits a stderr handler. (b) The dispatcher tests must
    point `PLANESWALKER_DATA_DIR` at `tmp_path`: `_log_startup_diagnostics` opens the real card
    database otherwise (the two pre-existing tests in that file already do — leave them alone, but do
    not copy the habit).

    **Non-vacuity, restated from c1-6/c1-7/c1-8:** delete the `acquire_instance_lock` call from
    `run()` and the contention test must fail; swap `flock` for `lockf` (or `LK_NBLCK` for `LK_LOCK`)
    and a test must fail rather than hang. Run both mutations and record them in the Debug Log.

16. **The two deferred entries this story closes get rulings, in place.** Per the epic-7 gate-output
    rule, and neither by silence:

    - **`deferred-work.md`'s c1-8 entry, "Two launches started within the same startup window can
      both start"** — Brad's ruling already says *"Close this entry when c1-9 lands."* Close it, and
      record what actually shipped (held lock, the release-on-death property, and the measured
      contention behaviour) rather than restating the plan.
    - **`deferred-work.md`'s c1-7 entry, "TOCTOU in `remove_discovery`'s ownership guard"** — its
      harm scenario needs a second *live* instance, which the held lock now makes impossible within
      one data directory. Rule it **closed by unreachability** (not by a code change), and say
      plainly what would reopen it: two instances deliberately run under different
      `PLANESWALKER_DATA_DIR` values, which is a supported configuration that gives each its own
      lock, its own rendezvous, and no shared state to race over.
    - Consequently, [`remove_discovery`'s docstring](src/companion/discovery.py#L226-L230) — which
      c1-8 reworded to *"reaching this race now takes two launches colliding within the same fraction
      of a second"* — is stale again and must be corrected to state that single-instance mutual
      exclusion is now enforced by the held lock. **That sentence is the only edit
      `src/companion/discovery.py` may receive**: no signature, no behaviour, no logic.
    - Record any genuinely new residual in a c1-9 section rather than leaving it in the story record.

17. **Quality gates green (NFR-07).** `uv run ruff check .`, `uv run ruff format --check .`,
    `uv run mypy src/`, `uv run mypy src/ --platform linux`,
    `uv run pre-commit run mypy --all-files` and `uv run pytest -m "not integration"` all pass with
    no new failures against the **1,629 passed / 1 skipped / 45 deselected** baseline (measured at
    `8bfc909` on 2026-07-26; `tests/unit/companion` is **319 passed / 1 skipped**). Actual output
    pasted into the Debug Log. **Both mypy runs are mandatory and neither is redundant**: each
    platform's run type-checks only its own half of AC 8's `sys.platform` branch, so a bug in the
    `msvcrt` half is invisible to the Linux run and vice versa — and CI runs on **ubuntu-latest**
    (py3.12 + py3.13), so the POSIX half is the one CI exercises while Windows is only ever covered
    by the local run.

18. **Plugin mirror rebuilt and committed.** `uv run python -m scripts.build_plugin`, then commit
    `plugin/`; `git status --porcelain -- plugin/` clean afterwards. `singleton.py` is new source, so
    the mirror gains a file, and `__main__.py` changes in it too.

19. **Scope boundary — what this story must NOT do.**
    - **No README, no CHANGELOG, no `EXPERIENCE.md`.** Story c8-4 owns every word of the release
      documentation, including the launch command, the port behaviour and the "already running"
      message. The README has no companion section today and must not grow one here.
    - **No new MCP tool, no `src/mcp_server/tools/**` edit, and no change to `build_server()`.** The
      only file touched under `src/mcp_server/` is `__main__.py`.
    - **No change to `pyproject.toml`** (the console-script entry point stays
      `src.mcp_server.__main__:main`), `uv.lock`, `.mcp.json`, `plugin/.mcp.json`,
      `scripts/build_plugin.py`, `.github/workflows/ci.yml` or `.pre-commit-config.yaml` — the new
      module imports stdlib only, so the mypy hook needs nothing added.
    - **No new dependency and no argparse migration.** A hand-rolled dispatch of two shapes is
      smaller than the `argparse` surface it would otherwise have to be tested against, and it keeps
      the bare invocation provably free of any parser side effect.
    - **No change to the identity probe, `client.py`, `contracts.py`, `deps.py`, `errors.py`'s
      behaviour, `security.py`'s behaviour, `main.py`'s behaviour, `routes/`, `src/data/**` or
      `src/paths.py`.** The `errors.py` / `security.py` / `main.py` edits are AC 7 comment repairs
      only; if a diff there shows anything but a comment, back it out.
    - **No change to any log level**, no new reason token, no new endpoint.
    - **No `O_EXCL` lock file, no PID file, no port-as-lock, no retry loop, no `--force` flag.** The
      held lock is the design; the alternatives were considered and rejected in `deferred-work.md`.
    - **No edit to `tests/unit/companion/test_import_boundary.py`, `conftest.py`, `test_app.py`,
      `test_client.py`, `test_deps.py`, `test_discovery.py`, `test_errors.py`, `test_security.py`, or
      `tests/integration/test_build_plugin.py`.** If any of those needs a change, that is a
      **finding**, not an edit.

## Tasks / Subtasks

- [x] **Task 0 — State verification** (standing team agreement since the epic-6 retro: any story whose
      notes assert repository state opens with the cheap check that proves it)
  - [x] Branch: `git switch -c feat/companion-c1-9-console-script-dispatcher` off `feat/companion-app`
        at `8bfc909` with a clean tree (PR #15 is **merged** — `gh pr view 15` → `MERGED`,
        2026-07-26 — so the c1-8 exception is over and the usual per-story branch rhythm resumes).
  - [x] Confirm `src/companion/app/singleton.py` and `tests/unit/companion/test_singleton.py` do
        **not** exist, and that `test_import_boundary._APP_IMPORT_EXEMPT` already contains
        `src/mcp_server/__main__.py`.
  - [x] Baseline the suite: `uv run pytest -m "not integration" -q` → expected **1,629 passed, 1
        skipped, 45 deselected**; `uv run pytest tests/unit/companion -q` → **319 passed, 1 skipped**.
        Record any delta rather than chasing it.
  - [x] Re-confirm the lock semantics on this machine in one script (AC 11's table is what the whole
        design rests on): two descriptors on one file in one process, acquire on the first, acquire
        on the second → must fail; close the first → second succeeds; a child process holding it →
        parent fails; hard-kill the child → parent succeeds. If any row differs, stop and say so.
  - [x] Re-confirm the console wrapper really is `sys.exit(main())` (AC 1) by reading the zip payload
        embedded in `.venv/Scripts/artificial-planeswalker.exe`, and re-confirm uvicorn's
        `LOGGING_CONFIG` still has `disable_existing_loggers: False` and no `root` key (AC 6).

- [x] **Task 1 — The lock module, test-first** (AC: 8, 9, 10, 11)
  - [x] Write `tests/unit/companion/test_singleton.py` first and watch it fail on the missing module
        (red-phase evidence for the Debug Log).
  - [x] `src/companion/app/singleton.py` — module docstring covering: what the lock is for (the
        measured 6 ms launch race), why it is *held* rather than created-and-deleted (the kernel
        releases it on any death, so AD-15's crash-is-ordinary stance needs no stale-lock recovery),
        why the file is never unlinked (POSIX `flock` binds to the inode), why it is separate from
        `companion.json`, and why `flock`/`LK_NBLCK` and not `lockf`/`LK_LOCK`. Module-level
        `logger = logging.getLogger(__name__)`.
  - [x] The four public symbols with Google docstrings; an explicit "never raises" line on
        `release_instance_lock` and an explicit "raises `OSError` if the file cannot be opened at
        all" line on `acquire_instance_lock`.
  - [x] Keep every local name clear of `_SESSION_RECEIVERS` (`session`, `sess`, `db`, `db_session`,
        `database`, `conn`, `connection`) — the write guard reads names, not intent. `fd`, `handle`
        and `lock` are all fine.

- [x] **Task 2 — Wiring the lock into `run()`** (AC: 12, 13)
  - [x] `src/companion/app/server.py::run()` — the acquire below the c1-8 refusal, the contention
        print, and the outer `try/finally` that releases. The inner socket `try/finally` is not
        restructured.
  - [x] Extend `run()`'s docstring: it now has **three** outcomes, all of them exits with status 0.
  - [x] Add a fifth entry to the module docstring's list of deliberate, load-bearing decisions: the
        held lock, and why the probe still runs first.
  - [x] Change nothing else in `server.py` beyond AC 7's comment repairs —
        `resolve_preferred_port`, `_new_socket`, `bind_localhost_socket`, `_serve`,
        `_note_reclaimed_entry`, `HOST` and `DEFAULT_PORT` keep their behaviour.

- [x] **Task 3 — The dispatcher** (AC: 1, 2, 3, 4, 5, 6)
  - [x] `src/mcp_server/__main__.py`: `_run_mcp_server()` (the current body, verbatim),
        `_run_companion(args)`, `_usage()`, `main(argv)` and the `raise SystemExit(main())` footer.
  - [x] Extend the module docstring: it is now a dispatcher, the bare invocation is unchanged and why
        that matters (AD-14), stdout still belongs to JSON-RPC on that path (AD-15's inversion), and
        the companion import is function-local by AD-3 with the boundary test named.
  - [x] `logging.basicConfig` on the companion path only, with a comment naming AD-15 and the fact
        that it is what finally surfaces c1-3/c1-7/c1-8's records.
  - [x] Catch `KeyboardInterrupt` around `run()` and return `0`: under uvicorn Ctrl-C is handled
        internally, but an interrupt during the probe or the bind would otherwise print a traceback
        for what is a deliberate user action on a foreground process.

- [x] **Task 4 — The stale-comment repairs** (AC: 7)
  - [x] Repair all six sentences in the AC 7 table plus
        [server.py:76](src/companion/app/server.py#L76)'s forward reference. Re-run
        `grep -rn "root handler\|root logger\|lastResort" src/` afterwards and confirm every
        surviving hit is true.
  - [x] Diff `errors.py`, `security.py` and `main.py` before committing — if `git diff` shows
        anything but comment/docstring text in those three, back it out (AC 19).

- [x] **Task 5 — Tests** (AC: 15, 14)
  - [x] `test_singleton.py`, the `test_server.py` additions and the `test_entry_point.py` matrix, per
        AC 15's list, including the logging save/restore fixture and the `PLANESWALKER_DATA_DIR`
        pin on the dispatcher tests.
  - [x] The two `.mcp.json` resolution tests (AC 14), asserting no subcommand follows the module
        path.
  - [x] Run the two mutations AC 15 names (`acquire` removed; `flock` → `lockf` **or**
        `LK_NBLCK` → `LK_LOCK`) and paste the red output, then revert.

- [x] **Task 6 — Deferrals and the discovery docstring** (AC: 16)
  - [x] `deferred-work.md`: close the c1-8 launch-race entry and the c1-7 `remove_discovery` TOCTOU
        entry with the rulings AC 16 specifies; open a c1-9 section only if something genuinely new
        is found.
  - [x] `src/companion/discovery.py`: the one docstring sentence. `git diff --stat` must show that
        file with a docstring-only change.

- [x] **Task 7 — Gates, mirror, scope and the live checks** (AC: 17, 18, 19)
  - [x] `uv run ruff check . --fix` · `uv run ruff format .` · `uv run mypy src/` ·
        `uv run mypy src/ --platform linux` · `uv run pre-commit run mypy --all-files` ·
        `uv run pytest -m "not integration"` — paste actual counts.
  - [x] `uv run python -m scripts.build_plugin`, `git add plugin/`, verify
        `git status --porcelain -- plugin/` is clean after the commit.
  - [x] Confirm by command that the AC 19 forbidden paths are untouched:
        `git status --porcelain -- pyproject.toml uv.lock .mcp.json plugin/.mcp.json scripts/build_plugin.py .github/workflows/ci.yml .pre-commit-config.yaml README.md CHANGELOG.md src/data src/paths.py src/companion/client.py src/companion/contracts.py src/companion/app/routes src/companion/app/deps.py tests/unit/companion/test_import_boundary.py tests/unit/companion/conftest.py tests/integration/test_build_plugin.py`
        returns empty.
  - [x] **Live check 1 — the race is closed.** Re-run the baseline race probe (two `run(0)` launches
        spawned back to back against one temp `PLANESWALKER_DATA_DIR`) and confirm exactly **one**
        process survives, the survivor's port is what `companion.json` names, and the loser printed
        one of the two refusal lines. Paste the before/after side by side.
  - [x] **Live check 2 — the entry point.** `uv run artificial-planeswalker` with one real MCP
        `initialize` handshake → exactly one stdout line, and it parses as JSON-RPC;
        `uv run artificial-planeswalker companion` → the launch line plus, for the first time,
        visible log records on stderr; `uv run artificial-planeswalker nonsense` → usage and exit
        status **2** (check `$LASTEXITCODE`); `uv run artificial-planeswalker --help` → usage and
        exit **0**.
  - [x] **Live check 3 — Ctrl-C.** Start the companion in its own process group, send a real
        interrupt (`signal.CTRL_BREAK_EVENT` on Windows), and confirm the process exits without a
        traceback, `companion.json` is **gone** and `companion.lock` **remains**. This is the AC 2
        half of the epic's Ctrl-C criterion that no unit test can prove.

### Review Findings

- [x] [Review][Decision] Non-contention lock failures are swallowed as "someone else has it" —
      `acquire_instance_lock`'s bare `except OSError` around the lock call treats *every* lock-call
      failure as contention, not only `EACCES`/`EWOULDBLOCK`. On a `PLANESWALKER_DATA_DIR` whose
      filesystem cannot lock at all (`ENOLCK`/`ENOTSUP` — NFS without lockd, some SMB/FUSE mounts),
      every launch prints "another companion is already starting up — wait for it to print its URL"
      and exits 0, forever, with no companion anywhere and the only diagnostic at DEBUG (invisible
      under the INFO root this story installs). Options: (a) keep the blanket swallow (AC 11's
      letter as written); (b) narrow to contention errnos (`EACCES`, `EAGAIN`/`EWOULDBLOCK`,
      `EDEADLK`) and let anything else propagate loudly, matching AC 11's *title* ("exactly one
      failure is swallowed, and it is the one that means someone else has it").
      [src/companion/app/singleton.py:120]
- [x] [Review][Decision] `artificial-planeswalker companion --help` is a usage error: it falls into
      `_parse_companion_port`, prints an error banner + usage on **stderr** and exits **2**. AC 3's
      letter rules this ("any other argument after `companion` … is a usage error"), but it sits
      askew of AC 4 / Decide-once #5's principle that a user asking for help has made no error, and
      the synopsis `[-h] [companion [--port PORT]]` is ambiguous about the flag's position. Options:
      (a) keep as-is (AC 3 letter); (b) recognise `-h`/`--help` after `companion` too → usage on
      stdout, exit 0. RULED (Brad, 2026-07-26): option (b) — applied, with a paired test.
      [src/mcp_server/__main__.py:179]
- [x] [Review][Patch] `remove_discovery`'s new docstring over-claims — "that second instance cannot
      exist" is broader than the enforcement point: the lock is acquired only in `server.run()`, so
      a `build_app()` served directly (a path `main.py`'s own docstring treats as supported) takes
      no lock. Scope the sentence to instances launched through `run()`.
      [src/companion/discovery.py:227]
- [x] [Review][Patch] Windows release relies on close-time unlock, which Microsoft documents as
      potentially deferred under load — add `msvcrt.locking(fd, LK_UNLCK, _LOCK_BYTES)` before
      `os.close` (inside the same never-raises guard) so a stop-then-immediate-relaunch cannot be
      spuriously refused. [src/companion/app/singleton.py:147]
- [x] [Review][Patch] `release_instance_lock`'s docstring blesses double release ("closing one that
      is already closed … is logged and otherwise ignored") — but after fd-number reuse a second
      call silently closes an unrelated descriptor and *succeeds*. Reword to "call at most once;
      a second call after the number is reused would close an unrelated descriptor".
      [src/companion/app/singleton.py:143]
- [x] [Review][Patch] Ctrl-C during the function-local companion import (FastAPI + uvicorn, ~1 s
      cold) escapes the `try` that only wraps `run(parsed)` — a deliberate interrupt in that window
      prints a `KeyboardInterrupt` traceback and exits 1. Widen the `try` to cover the import.
      [src/mcp_server/__main__.py:217]
- [x] [Review][Patch] `test_the_refused_path_leaks_no_descriptor`'s proxy (a fresh acquire succeeds
      after release) passes identically whether the refusal path leaked 0 or 64 descriptors —
      deleting `os.close(fd)` from the contention branch stays green on the CI platform. Assert
      fd-number reuse instead (probe fd before/after the refusals and compare).
      [tests/unit/companion/test_singleton.py]
- [x] [Review][Patch] AC 16 residual mis-homed: the "Worth Brad's eye" note (Windows
      `CTRL_BREAK_EVENT` exits 3 imposed by the console-control path; interactive `CTRL_C_EVENT`
      unverified) lives only in the story record's deviation 3 — AC 16 requires genuinely new
      residuals in a c1-9 section of `deferred-work.md`. Add the section; also note there the
      autouse `isolated_data_dir` fixture's reach onto the two pre-existing transport tests
      (undocumented second departure from "leave them alone").
      [_bmad-output/implementation-artifacts/deferred-work.md]
- [x] [Review][Patch] `sprint-status.yaml`'s two `last_updated` strings still read "story c1-9 →
      ready-for-dev" while `development_status` says `review` — the header is two transitions
      stale. [_bmad-output/implementation-artifacts/sprint-status.yaml]
- [x] [Review][Defer] The "both mypy runs are mandatory" comment is wired into no gate — no
      pre-commit hook or CI step passes `--platform linux`; the POSIX half is strict-checked only
      because CI happens to run on ubuntu, and the Windows half only on Brad's machine. Real, but
      AC 19 forbids touching `.github/workflows/ci.yml` and `.pre-commit-config.yaml` this story.
      [src/companion/app/singleton.py:55] — deferred, out of this story's scope

## Dev Notes

### Decide-once rulings (made here so c6-1 and the Phase-2 stories inherit them)

**#1 — The lock is app-layer, not a leaf.** Both would satisfy the boundary test; only one is
truthful. `client.py` and `discovery.py` exist so an agent-side caller can *find and talk to* the
app; nothing agent-side may ever take this lock, and a leaf module named `singleton` would invite
exactly that. Putting it under `src/companion/app/` also means the enumeration pin skips it and
`_LEAF_MODULES` needs no edit — the boundary tests stay untouched, which AC 19 requires.

**#2 — Probe first, lock second.** The reverse ordering is defensible on paper (fail fast, no network
call on the contended path) and was rejected for two reasons. First, it would rewrite the fourteen
`TestSingleInstanceCheck` cases c1-8 just landed: those plant a live stub and a discovery file with
nobody holding the lock, so under lock-first they would all *proceed* instead of refusing. Second,
the informative refusal — the one naming a URL Brad can actually open — is the common case, and the
lock cannot name anything. The epic AC frames it exactly this way: the probe supplies the *who and
where*, the lock supplies the atomic *whether*.

**#3 — No second probe on the contention path.** Reaching that branch means the probe has already
said "nothing findable is running", so there is no honest URL to print, and re-probing would spend up
to five seconds on the one path whose job is to get out of the way. The message says what is true —
another launch is starting up — and points at the terminal that will print the URL. Recorded as Open
Question 2 in case Brad prefers a URL-naming variant.

**#4 — The lock file is never deleted, and that is load-bearing rather than lazy.** On POSIX `flock`
attaches to the inode behind the open descriptor; unlink-and-recreate would hand the next launch a
different inode and both processes would hold "the lock". A zero-byte file that outlives every run is
the correct artifact, and c8-2 (image-cache stewardship) is where its existence gets documented for
users, not here.

**#5 — Exit status vocabulary is now fixed for the whole feature.** `0` = the user's intent is
satisfied, including both refusals (c1-8's Decide-once #3, extended). `2` = the user typed something
this program does not understand. Nothing else is minted; a crash still exits via its traceback.

**#6 — The root logger is configured by the entry point, at INFO, on stderr.** Not in `run()` (a
library-shaped function that tests call), not in `build_app()` (AD-10 inertness), not at DEBUG (that
would put `read_discovery`'s per-push chatter in the user's terminal from c6-1 onward), and not on
stdout (the deliberate lines are already `print`ed there; mixing log records in would make the
launch URL harder to find, and uvicorn already puts its access log on stdout).

### Architecture rules this story implements

- **AD-14**, in full: *"`artificial-planeswalker` becomes a subcommand dispatcher: no arguments runs
  the MCP server exactly as today; `companion` runs the backend. Verified safe — both `.mcp.json` and
  `plugin/.mcp.json` invoke `python -m src.mcp_server` directly."* AC 2 and AC 14 are those two
  sentences, made executable.
- **AD-15**, the half that has been owed since c1-2: *"Unlike the MCP process it logs freely to
  stdout/stderr, because it owns them."* AC 6 is that sentence; AC 7 is the cleanup it forces. AD-15
  also supplies the crash model the held lock is designed against — *"a crash leaves a stale
  discovery file that the next start reclaims"* — which is exactly why a create-and-delete lock file
  would have been wrong.
- **AD-3** — the exemption the guard was built with in mind. `src/mcp_server/__main__.py` may import
  `src.companion.app` **function-locally and nowhere else**, so a stdio MCP session still never
  imports FastAPI. The guard, its exemption and both its violation fixtures already exist; this story
  is the first code to use them.
- **AD-4** — untouched but depended on: the discovery file remains the sole rendezvous, the lock is
  never read for data, and the identity probe still decides the informative refusal.
- **AD-10** — check you have not broken it: `singleton.lock_path()` must resolve at call time, and
  nothing in the new module may run at import.
- **FR-01** — its "exactly one instance" sentence stops being *nearly* true here.

### Source tree — what exists, what this story adds

```text
src/
  mcp_server/
    __main__.py              # UPDATE — main() becomes the dispatcher; _run_mcp_server /
                             #          _run_companion / _usage; logging config on the companion path
  companion/
    app/
      singleton.py           # NEW — LOCK_FILENAME, lock_path, acquire_instance_lock,
                             #       release_instance_lock  (the held advisory lock)
      server.py              # UPDATE — run() takes the lock before it claims anything else;
                             #          docstrings + three stale log comments repaired
      main.py                # UPDATE — one stale comment (AC 7); no behaviour change
      security.py            # UPDATE — one stale comment (AC 7); no behaviour change
      errors.py              # UPDATE — one stale comment (AC 7); no behaviour change
    discovery.py             # UPDATE — one docstring sentence (AC 16); no behaviour change
    client.py                # EXISTS — untouched
tests/
  unit/companion/
    test_singleton.py        # NEW — the lock's real-descriptor contract
    test_server.py           # UPDATE — the contention refusal + release-on-exit cases
  integration/mcp_server/
    test_entry_point.py      # UPDATE — the dispatcher matrix + both .mcp.json resolution pins
_bmad-output/implementation-artifacts/
  deferred-work.md           # UPDATE — close the c1-8 race entry and the c1-7 TOCTOU entry
```

**Current state of the files being modified** (read before editing):

- [`src/mcp_server/__main__.py`](src/mcp_server/__main__.py) — 73 lines. `_log_startup_diagnostics()`
  prints five `[planeswalker] …` lines to **stderr** (with a blanket `except Exception` so
  diagnostics can never break startup) and `main()` reads `MCP_TRANSPORT`, calls the diagnostics and
  then `build_server().run(transport=transport)`. **What must be preserved:** every one of those
  writes stays on stderr; the diagnostics run *before* the server starts; `main` keeps its name and
  module path (`pyproject.toml`'s `[project.scripts]` and the installed `.exe` both point at it); the
  `_Transport` `Literal` and the `cast` stay as they are.
- [`src/companion/app/server.py`](src/companion/app/server.py) — `run()` currently: reconfigures
  stdout, probes `client.live_instance()` and returns on a match, calls `_note_reclaimed_entry()`,
  resolves the preferred port, binds, and inside a `try/finally` builds the app, stamps
  `app.state.bound_port`, prints the fallback and launch lines and calls `_serve`; the `finally`
  closes the socket. **What must be preserved:** the stdout reconfigure stays first (the new refusal
  line carries an em dash too); the probe stays above everything that claims a resource; the
  `finally`-closes-the-socket invariant; `_serve` isolated so tests can replace it; `DEFAULT_PORT`
  remaining the only place in `src/` that names 8765 — `singleton.py` and `__main__.py` must name
  **no** port number.
- [`src/companion/discovery.py`](src/companion/discovery.py) — `discovery_path()` is the pattern
  `lock_path()` copies (call-time resolution, and why). `remove_discovery`'s TOCTOU paragraph is the
  one edit (AC 16).
- [`tests/unit/companion/test_server.py`](tests/unit/companion/test_server.py) — `_Loopback`,
  `_RecordingServe` + the `recorded_serve` fixture, `TestRun`, `TestSingleInstanceCheck`,
  `TestNothingElseHardcodesThePort` (the AST scan for `8765` across `src/` **and** `scripts/`) and
  `TestNothingBindsBeyondLoopback`. `recorded_serve` means the lifespan never runs in this file, so
  no discovery file is written by these tests — the refusal tests plant their own.
- [`tests/unit/companion/conftest.py`](tests/unit/companion/conftest.py) — the autouse
  `isolated_data_dir` fixture points `PLANESWALKER_DATA_DIR` at each test's `tmp_path`. It is what
  keeps the new lock file out of the developer's real data directory and keeps the lock tests
  contention-free. **Read it, do not edit it.**
- [`tests/integration/mcp_server/test_entry_point.py`](tests/integration/mcp_server/test_entry_point.py)
  — 51 lines: a `_FakeServer` recording the transport, two `main()` tests that monkeypatch
  `main_mod.build_server`, and `test_mcp_json_registers_server`. The two existing `main()` tests call
  `main()` with no arguments, so they keep working unchanged **only if** `argv` defaults to
  `sys.argv[1:]` and pytest's own argv is not mistaken for a subcommand — pass `[]` explicitly in the
  new tests and leave the two old ones alone; if either goes red, that is the signal that `main()`
  is reading `sys.argv` when it should be reading its parameter.

**Deviation from the spine's Structural Seed:** one addition. The seed lists
`__main__.py  # subcommand dispatcher (AD-14)` but names no lock module; `app/singleton.py` is new
surface introduced by Brad's 2026-07-26 ruling, and it sits inside the `app/` package the seed
already defines. Nothing is moved or renamed.

### Gotchas specific to this story

1. **`fcntl.lockf` would pass a naive test and be wrong.** POSIX record locks are owned by the
   *process*: a second `lockf` on another descriptor in the same process succeeds, and closing *any*
   descriptor to the file releases every lock the process holds on it. `flock` is per open-file
   description, which is both what the design needs and what makes AC 15's cheap same-process
   contention test meaningful. The epic AC names `flock` for this reason.

2. **`msvcrt.LK_LOCK` blocks for ten seconds.** It retries ten times at one-second intervals before
   raising. `LK_NBLCK` fails immediately. A launch that hangs for ten seconds behind another launch
   is indistinguishable from a hung app.

3. **CI never runs the Windows half.** `.github/workflows/ci.yml` is `ubuntu-latest` on py3.12 and
   py3.13, so `msvcrt` is exercised only on Brad's machine and `mypy --platform linux` is the only
   thing that type-checks the POSIX branch locally (and `mypy src/` the only thing that checks the
   Windows one). Run both, every time; a green local run alone proves half the module.

4. **The dispatcher must not import the companion app at module level — including for a type.** The
   boundary guard counts `if TYPE_CHECKING:` as module-level in every role. There is a committed test
   fixture (`type-checking-app-import-is-still-module-level`) that exists purely to catch this
   story doing it.

5. **`logging.basicConfig` is a no-op if the root logger already has a handler.** In a test session
   pytest may have configured logging already, so a dispatcher test asserting "a handler was added"
   must snapshot and clear root's handlers first, then restore them at teardown — otherwise the test
   passes vacuously *and* leaks a stderr handler into the rest of the suite.

6. **Do not let `main()` read `sys.argv` when it was handed an `argv`.** Under pytest, `sys.argv[1:]`
   is full of pytest's own flags; a dispatcher that falls back to `sys.argv` inside a test would try
   to dispatch `-q` and return 2. The default must be resolved once, at the top of `main`.

7. **`singleton.py` must name no port number** — not 8765, not an example port in a docstring — and
   neither must `__main__.py`'s usage text. `TestNothingElseHardcodesThePort` AST-scans `src/` and
   `scripts/` for the numeric literal and asserts exactly one legal occurrence. (A *string* "8765"
   would slip past the scan and still be a duplication — write "the default port" in words.)

8. **The write guard reads names, not intent.** No local in `singleton.py` may be called `session`,
   `sess`, `db`, `db_session`, `database`, `conn` or `connection`; a `conn.close()` would fail
   `test_import_boundary.py` for reasons that have nothing to do with databases.

9. **Close the descriptor on the contention path.** `acquire_instance_lock` opens before it locks, so
   the `except OSError` branch owns an open descriptor it must close before returning `None`. A leak
   here is invisible in one test run and pins a file handle open for the process's life.

10. **Ctrl-C during the probe is not the same as Ctrl-C during `serve`.** uvicorn installs its own
    signal handling and shuts down gracefully (running the lifespan's `remove_discovery`); an
    interrupt before uvicorn exists propagates as `KeyboardInterrupt` through `run()` — where the
    outer `finally` still releases the lock — and out to the dispatcher, which is why Task 3 catches
    it there rather than in `run()`.

11. **`asyncio_mode = "auto"`** — write `async def test_…` directly, with no marker. The lock tests
    are all sync; the dispatcher tests are sync (they call `main()`, which calls `asyncio.run`
    through `run()`; making them async would call `asyncio.run` inside a running loop).

12. **The one behaviour a unit test cannot prove is the one the story is named for.** Two real
    processes racing is Task 7's live check 1; do not skip it because the suite is green.

### Testing standards

- New tests in `tests/unit/companion/test_singleton.py`; the `run()` cases join
  `tests/unit/companion/test_server.py`; the dispatcher cases join
  `tests/integration/mcp_server/test_entry_point.py`. Unmarked, fast, no `integration` marker.
- **Real descriptors and real files over mocks** (c1-3's ruling, restated by c1-7 and c1-8): mocking
  `msvcrt`/`fcntl` would prove only that a mock was called, and the failure this story exists to
  catch — a second process getting the lock — lives in the kernel.
- **Assert observable state**: whether a second acquire succeeds, whether the lock file exists,
  whether the port is still bindable, what the process actually wrote to stdout versus stderr. Never
  "a mock went uncalled".
- Discovery-file fixtures use `Path.write_text` / `write_bytes`, never `write_discovery` (c1-6's
  rule, restated by c1-7 and c1-8).
- **Verification before completion:** paste actual ruff / mypy / pre-commit / pytest output into the
  Debug Log. "Tests pass" without output is not acceptance — standing agreement from the epic-5/6
  retros.

### Previous story intelligence (c1-8, done 2026-07-26; PR #15 merged)

- **The branch exception is over.** c1-8 was built on c1-7's branch because PR #15 was held open;
  #15 merged at 2026-07-26T01:51Z, so c1-9 cuts a fresh branch off `feat/companion-app` in the
  normal rhythm.
- **c1-8's review produced one high and five patches, and three of its lessons apply directly.**
  (a) *A "never raises" promise must cover the whole function, not the happy path* — check that
  nothing in `acquire_instance_lock` (including the `os.open`) sits in the wrong place relative to
  its guard, and be explicit about which failures are meant to escape. (b) *An unbounded wait is a
  finding* — the review's total-deadline patch existed because a read timeout bounds the gap between
  chunks, not the whole exchange; the analogue here is `LK_LOCK` versus `LK_NBLCK`. (c) *Environment
  can defeat a guard* — `trust_env=False` was the review's one high because `HTTP_PROXY` would have
  routed the loopback probe away and resurrected the duplicate-instance failure; the analogue here is
  `PLANESWALKER_DATA_DIR`, which legitimately gives two instances separate locks, and AC 16 requires
  that to be *stated* rather than discovered.
- **The vacuous-test lesson (c1-6, restated by c1-7 and c1-8).** Where an AC names a mechanism, add
  an assertion that goes red when the mechanism is removed, and *run* the mutation — c1-8 ran two and
  pasted both.
- **c1-8's deliberate deviation to be aware of:** `run()` re-reads the discovery file on the reclaim
  path only, via `_note_reclaimed_entry()`. It now sits *below* the lock acquire, which is correct —
  a launch that is about to refuse should not log about reclaiming anything.
- **Known pre-existing flake:** `test_list_decks_with_strategy_field`'s same-tick ordering. If a full
  run shows that one test red, it is the known flake, not a regression.

### Git intelligence

`HEAD = 8bfc909` on `feat/companion-app`, working tree clean. Recent rhythm: `431bd6e feat(companion):
single-instance enforcement with verified identity` → `cc0b5d5 Merge pull request #15` → `8bfc909
docs(companion): rule the c1-8 launch-race fix into c1-9`. That last commit is this story's charter —
it is the ruling that added the sixth acceptance criterion to Story 1.9 in the epic file and rewrote
the `deferred-work.md` entry from "candidate fix" to "c1-9 builds it".

This story changes no wire contract, adds no reason token, adds no dependency and needs no `!`.
Suggested commit: `feat(companion): one console script that dispatches, plus a held single-instance lock`.

### Latest technical information

Verified in this environment on 2026-07-26 — Python 3.12.13 · uvicorn 0.51.0 · httpx 0.28.1 ·
pydantic 2.12.0 · FastAPI 0.140.0, all at or above the spine's floors. No dependency is added,
upgraded or pinned by this story; the new module imports stdlib only.

**Probe 1 — the launch race, at `8bfc909`, before the fix** (two `run(0)` launches spawned back to
back against one temp `PLANESWALKER_DATA_DIR`):

```
both spawned within 6 ms
process 1 stdout: [planeswalker] companion running at http://127.0.0.1:58448 - open this URL ...
process 2 stdout: [planeswalker] companion running at http://127.0.0.1:58453 - open this URL ...
discovery file : 58453
processes alive: 2        <- the race reproduced; 58448 is live and unfindable
```

**Probe 2 — the lock's semantics** (win32, py3.12.13; `os.open(path, os.O_RDWR | os.O_CREAT, 0o600)`
then `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)`):

```
1 first open ok
2 second open of the same file in one process        -> allowed (Python's open does not deny sharing)
3 first acquire                                      -> OK
4 second acquire, same process, other descriptor     -> PermissionError errno=13 (EACCES)
5 after closing the holder, acquire on the other fd  -> OK   (close is what releases)
6 acquire while another PROCESS holds it             -> PermissionError errno=13
7 after HARD KILL of that process, acquire           -> OK   (kernel released it; no stale state)
8 lock file after all of the above                   -> present, 0 bytes
```

Row 4 is what makes AC 15's cheap contention test possible; row 7 is what makes the held-lock design
correct under AD-15. The POSIX equivalents are **reasoned, not measured here** — `flock` is
per-open-file-description, so rows 4 and 6 hold and row 7 follows from the kernel dropping locks when
the last descriptor closes. CI (ubuntu-latest, py3.12 + py3.13) is what proves it; if the Linux run
disagrees with row 4, say so rather than working around it.

**Probe 3 — the console-script wrapper** (read out of the zip payload embedded in
`.venv/Scripts/artificial-planeswalker.exe`):

```python
from src.mcp_server.__main__ import main
if __name__ == "__main__":
    ...
    sys.exit(main())
```

So `main()`'s return value **is** the exit status, `None` exits 0, and the wrapper imports `main` by
name — which is why `pyproject.toml`'s entry point must not move.

**Probe 4 — stdout purity at baseline** (a real `artificial-planeswalker` subprocess, one MCP
`initialize` request on stdin):

```
=== STDOUT lines: 1
  JSON-RPC ok: keys= ['id', 'jsonrpc', 'result'] | id= 1
=== STDERR lines: 5   ([planeswalker] data_dir / database / three env lines)
```

**Probe 5 — logging survives uvicorn's dictConfig** (uvicorn 0.51.0): `LOGGING_CONFIG` has
`disable_existing_loggers: False` and **no `root` key**; its `default` handler writes to **stderr**
and its `access` handler to **stdout**, and both its loggers set `propagate: False`. After
`basicConfig(level=INFO, stream=sys.stderr)` and then `uvicorn.Config(...)`:

```
INFO src.companion.app.server: INFO from a src.* logger AFTER uvicorn.Config applied its dictConfig
root level: INFO handlers: [<StreamHandler <stderr> (NOTSET)>]
```

**Baseline measured at `8bfc909`:** **1,629 passed / 1 skipped / 45 deselected** (full suite,
`-m "not integration"`, 84 s), **319 passed / 1 skipped** in `tests/unit/companion`.

### Project Structure Notes

- `singleton.py` sits under `src/companion/app/`, so `test_import_boundary`'s enumeration pin skips it
  and `_LEAF_MODULES` needs no entry. It may import FastAPI-adjacent things in principle but imports
  only stdlib plus `src.paths` in practice — keep it that way; a leaf-clean lock module is one less
  thing for a future refactor to trip over.
- `src/mcp_server/__main__.py` is the **only** file in the repository permitted a function-local
  `src.companion.app` import, and only function-local.
- Pre-existing tracked files modified: `src/mcp_server/__main__.py`, `src/companion/app/server.py`,
  `src/companion/app/main.py`, `src/companion/app/security.py`, `src/companion/app/errors.py`
  (the last three comment-only), `src/companion/discovery.py` (docstring only),
  `tests/unit/companion/test_server.py`, `tests/integration/mcp_server/test_entry_point.py`,
  `_bmad-output/implementation-artifacts/deferred-work.md`,
  `_bmad-output/implementation-artifacts/sprint-status.yaml`, and the generated `plugin/` mirror.
  **Not** `pyproject.toml`, `uv.lock`, `.mcp.json`, `plugin/.mcp.json`, `README.md`,
  `.pre-commit-config.yaml`, `src/paths.py`, `src/data/**` or any other `src/mcp_server/` file.
- Naming follows project conventions: `snake_case` functions, `UPPER_SNAKE` constants, Google
  docstrings on every public symbol, a module docstring at the top, `%`-style lazy log args, guard
  clauses over nesting, ruff line-length 100.

### References

- [epics-companion-app.md — Story 1.9](_bmad-output/planning-artifacts/epics-companion-app.md#L1140-L1182) — the source acceptance criteria, including Brad's 2026-07-26 held-lock addition · [Epic 1 framing](_bmad-output/planning-artifacts/epics-companion-app.md#L882-L888)
- ARCHITECTURE-SPINE.md — [AD-14](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L304-L313) · [AD-15](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L315-L327) · [AD-3 and the leaf/app split](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L114-L125) · [Structural Seed](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L438-L462) · [the inherited stdout invariant this story inverts](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L55)
- [deferred-work.md — the c1-8 launch-race entry and Brad's ruling](_bmad-output/implementation-artifacts/deferred-work.md#L790-L819) · [the c1-7 `remove_discovery` TOCTOU entry](_bmad-output/implementation-artifacts/deferred-work.md#L765-L788)
- [src/mcp_server/__main__.py](src/mcp_server/__main__.py#L1-L73) — the entry point that becomes the dispatcher, and the stderr-only diagnostics that must stay stderr-only
- [src/companion/app/server.py — `run()`](src/companion/app/server.py#L254-L327) — where the lock lands · [`resolve_preferred_port`](src/companion/app/server.py#L71-L117) — the `--port` receiver, and the docstring that already promises this story · [`_note_reclaimed_entry`](src/companion/app/server.py#L220-L251) — the INFO line this story finally makes visible
- [src/companion/discovery.py — `discovery_path`](src/companion/discovery.py#L85-L98) — the call-time-resolution pattern `lock_path()` copies · [`remove_discovery`](src/companion/discovery.py#L210-L262) — the docstring sentence AC 16 repairs
- [src/companion/app/__init__.py](src/companion/app/__init__.py) — the package docstring that already names this story's exemption
- [tests/unit/companion/test_import_boundary.py](tests/unit/companion/test_import_boundary.py#L133-L138) — `_APP_IMPORT_EXEMPT`, and [the committed fixtures for both the legal and illegal forms](tests/unit/companion/test_import_boundary.py#L785-L936) · [the enumeration pin](tests/unit/companion/test_import_boundary.py#L536-L552) · [the session-receiver names to avoid](tests/unit/companion/test_import_boundary.py#L86-L92)
- [tests/unit/companion/test_server.py — `TestNothingElseHardcodesThePort`](tests/unit/companion/test_server.py) — the AST scan that constrains the usage text
- [tests/integration/mcp_server/test_entry_point.py](tests/integration/mcp_server/test_entry_point.py#L1-L51) — the file the dispatcher tests extend
- [c1-8 story record](_bmad-output/implementation-artifacts/c1-8-single-instance-enforcement-with-verified-identity.md) — the probe, its five decide-once rulings, and the review findings this story inherits
- [project-context.md](_bmad-output/project-context.md) — `%`-style lazy logging, ruff/mypy, Google docstrings, module docstrings

## Open questions for Brad

Neither blocks implementation.

1. **Should `--port` exist at all in this story?** The epic's ACs do not name it;
   `resolve_preferred_port`'s docstring does, in as many words, and leaving it out means editing that
   docstring to remove a promise instead. It is built (AC 3). If you would rather the CLI stayed at
   exactly two shapes, the removal is a few lines plus that docstring.
2. **Should a lock-contention refusal try to name a URL?** It does not (Decide-once #3): the probe
   has already said nothing is findable, and a second probe costs up to five seconds. The alternative
   is one extra `live_instance()` call on that path, printing c1-8's exact "already running at …"
   line when it happens to succeed.
3. **Is `2` the right status for a usage error?** It matches `argparse` and Unix convention, and AC 4
   pins it in a test. `1` is a one-character change if you prefer it.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the bmad-dev-story workflow.

### Debug Log References

**Task 0 — state verification (all assertions in the story notes reproduced).**

- `gh pr view 15` → `{"mergedAt":"2026-07-26T01:51:32Z","state":"MERGED"}`; branch cut off
  `feat/companion-app` at `8bfc909` with only the story file + sprint-status pending.
- `src/companion/app/singleton.py` and `tests/unit/companion/test_singleton.py` both absent;
  `_APP_IMPORT_EXEMPT = frozenset({"src/mcp_server/__main__.py"})` already present
  ([test_import_boundary.py:138](tests/unit/companion/test_import_boundary.py#L138)).
- Baselines matched exactly: `1629 passed, 1 skipped, 45 deselected in 53.16s`;
  `tests/unit/companion` → `319 passed, 1 skipped in 6.12s`.
- Lock semantics, all eight rows of AC 11's table reproduced (win32, py3.12.13):

  ```
  1 first open ok
  2 second open of the same file in one process: allowed
  3 first acquire: OK
  4 second acquire, same process, other fd: refused as wanted -> PermissionError errno=13
  5 after closing the holder, re-acquire on the other fd: OK
  6 acquire while another PROCESS holds it: refused as wanted -> PermissionError errno=13
  7 after HARD KILL of the holder, acquire: OK
  8 lock file still present afterwards: True, size 0
  ```

- Console wrapper re-read out of the `.exe` zip payload — it is `sys.exit(main())`, confirming
  `main()`'s return value is the exit status. uvicorn 0.51.0 `LOGGING_CONFIG`:
  `disable_existing_loggers = False`, `'root' in config = False`, `default` handler → stderr,
  `access` handler → stdout, both loggers `propagate: False`.

**Red-phase evidence (Task 1).** `test_singleton.py` written first:
`ImportError: cannot import name 'singleton' from 'src.companion.app'` → 1 collection error.
After `singleton.py` landed: `14 passed in 0.06s`.

**Non-vacuity mutations (AC 15) — both run, both recorded.**

- *Mutation 1 — `acquire_instance_lock()` call removed from `run()`* (replaced with `lock = 0`):
  **4 failed, 7 passed** in `TestHeldInstanceLock` —
  `test_a_contended_launch_prints_the_refusal_line`, `..._never_serves`,
  `test_the_lock_file_survives_a_normal_run`, `test_the_lock_is_held_while_serving`
  (`AssertionError: run() must hold the lock for the whole serve; assert [0] == [None]`). Reverted.
- *Mutation 2 — `LK_NBLCK` → `LK_LOCK`*: **the tests still passed**, but
  `test_singleton.py` went from **0.06 s to 591.52 s** — the blocking primitive raises after ten
  one-second retries, which `acquire_instance_lock` then reports as ordinary contention. It **hung
  rather than failed**, so the primitive choice was *not* actually guarded. Added
  `test_a_refused_acquire_returns_immediately` (a 2.0 s deadline on a contended acquire); re-running
  mutation 2 against it now gives
  `AssertionError: a contended acquire took 9.1s — it must never block and retry` in **9.18 s**.
  Reverted. See Completion Notes deviation 2.

**Quality gates (AC 17), actual output.**

```
uv run ruff check .            -> All checks passed!
uv run ruff format --check .   -> 280 files already formatted
uv run mypy src/               -> Success: no issues found in 83 source files
uv run mypy src/ --platform linux -> Success: no issues found in 83 source files
uv run pre-commit run mypy --all-files -> mypy...Passed
uv run pytest -m "not integration" -q
   -> 1681 passed, 1 skipped, 45 deselected in 63.47s (0:01:03)
```

Baseline was 1,629 → **+52 tests**, no regressions, no skips added
(15 `test_singleton.py`, +11 `test_server.py`, +26 `test_entry_point.py`).

**AC 18 — plugin mirror.** `uv run python -m scripts.build_plugin` →
`Plugin assembled at …\plugin (v0.4.0, 4 skills)`; mirror picked up exactly the six modified files
plus the new `singleton.py`, and nothing else.

**AC 19 — scope boundary, by command.** `git status --porcelain --` over all seventeen forbidden
paths returned **empty**.

**Live check 1 — the race is closed.** Before (at `8bfc909`, from the story notes) vs after:

```
BEFORE                                   AFTER
both spawned within 6 ms                 both spawned within 16 ms
process 1: companion running at :58448   process 1 SURVIVED: companion running at :61215
process 2: companion running at :58453   process 2 (exited 0): another companion is already
                                                    starting up — wait for it to print its URL…
discovery file: 58453                    discovery file: port 61215   <- names the survivor
processes still alive: 2  <- RACE        processes still alive: 1     <- RACE CLOSED
                                         lock file: exists=True size=0
```

**Live check 2 — the entry point**, all four shapes against the real
`.venv/Scripts/artificial-planeswalker.exe`:

```
A. bare + one MCP initialize handshake
     STDOUT lines: 1   -> JSON-RPC ok: keys=['id','jsonrpc','result'] id=1
     STDERR lines: 5   (the diagnostics, unchanged)
B. companion --port 0
     STDOUT: [planeswalker] companion running at http://127.0.0.1:57061 — open this URL …
     STDERR: INFO:     Started server process [38988]
             INFO:     Waiting for application startup.
             INFO src.companion.app.main: Published discovery file …\companion.json for port 57061
             INFO src.companion.app.main: Companion instance 7b1ea073-… started
             INFO:     Application startup complete.
C. nonsense   -> exit status: 2   stdout empty: True
                 stderr: artificial-planeswalker: error: unknown subcommand: nonsense
D. --help     -> exit status: 0   stderr empty: True
                 stdout: usage: artificial-planeswalker [-h] [companion [--port PORT]]
```

The two `INFO src.companion.app.main:` lines are AC 6's payoff observed live — the first time in the
feature's history that a `src.*` log record reaches a user.

**Live check 3 — Ctrl-C** (own process group, real `signal.CTRL_BREAK_EVENT`), plus a relaunch:

```
running:      companion.json=True  companion.lock=True
after Ctrl-C: exit=3  traceback=False  companion.json=False  companion.lock=True (size 0)
              graceful shutdown ran: True   ("Application shutdown complete")
next launch:  [planeswalker] companion running at http://127.0.0.1:56078 — open this URL …
              -> unblocked: True  (no stale-lock recovery needed)
```

All three conditions the task names hold: no traceback, `companion.json` gone, `companion.lock`
retained at 0 bytes — and the follow-up launch proves the kernel released the lock with no stale
state. **The observed exit status is `3`, not `0`** — see Completion Notes deviation 3; it is not
produced by the dispatcher.

### Completion Notes List

**What shipped.** `main()` is now a subcommand dispatcher returning the process's exit status; the
bare invocation is byte-for-byte the old behaviour (`_run_mcp_server`, the pre-dispatcher body moved
verbatim). `companion` runs the backend, accepts `--port N` / `--port=N`, and is the only path that
configures the root logger (INFO, stderr) — which is what finally surfaces the records c1-3, c1-7 and
c1-8 have been emitting into nothing. A new app-layer module `src/companion/app/singleton.py` holds a
process-lifetime OS advisory lock (`msvcrt.LK_NBLCK` / `fcntl.flock(LOCK_EX|LOCK_NB)`), acquired in
`run()` below c1-8's identity refusal and released in `run()`'s outermost `finally`. The measured
6 ms launch race is closed; all fourteen of c1-8's `TestSingleInstanceCheck` cases pass **unedited**,
which was the point of probe-before-lock.

**Three deviations / findings, none of which changed an AC's intent.**

1. **AC 15's "leave the two old `test_entry_point.py` tests alone" was not satisfiable — a genuine
   finding, resolved with a two-character edit.** The Dev Notes predicted those tests "keep working
   unchanged only if `argv` defaults to `sys.argv[1:]` and pytest's own argv is not mistaken for a
   subcommand". Those two conditions are in direct conflict: AC 1 *mandates* the `sys.argv[1:]`
   default, and under pytest `sys.argv[1:]` is pytest's own argument list, so a bare `main()` call
   inside a test dispatches the test file path as a subcommand. Observed exactly that:
   `artificial-planeswalker: error: unknown subcommand: tests/integration/mcp_server/test_entry_point.py`,
   2 failed. The notes' fallback reading — "that is the signal that `main()` is reading `sys.argv`
   when it should be reading its parameter" — does not apply, because `main()` *is* reading its
   parameter; the parameter simply was not passed. Fixed by passing `[]` in those two calls.
   `test_entry_point.py` is designated UPDATE by AC 15 and is **not** on AC 19's forbidden-edit list,
   so this is in scope; flagging it because the story asserted the opposite. `TestArgvHandling`
   now pins both halves (an explicit `argv` wins; `sys.argv` is genuinely the default).

2. **Mutation 2 exposed a real gap in the tests as specified, and it was closed.** AC 15 asks that
   swapping `LK_NBLCK` for `LK_LOCK` make "a test fail rather than hang". As written, the suite did
   neither — it **passed**, 10,000× slower (591 s vs 0.06 s), because `LK_LOCK` raises after its ten
   retries and that raise is indistinguishable from contention at the `except OSError`. Added
   `TestAcquireAndRelease::test_a_refused_acquire_returns_immediately`, a 2.0 s deadline chosen to
   sit far above the real refusal (microseconds) and far below the mutation (~9-10 s). The mutation
   now fails in 9 s. Without this the AC 9 primitive choice was documented but unguarded.

3. **Ctrl-C exits `3` on Windows, and it is not the dispatcher's `0`.** Traced rather than assumed:
   uvicorn's `Server.run()` completes its graceful shutdown ("Finished server process" is logged,
   the lifespan teardown runs, `companion.json` is removed) and then the process is terminated
   before `main()` can return — instrumenting the child to print `main()`'s return value shows
   **`MAIN RETURNED` never prints**. So the `3` is imposed by the Windows console-control path at
   the point uvicorn's loop unwinds; neither `sys.exit(STARTUP_FAILURE)` site in uvicorn fired
   (startup succeeded). Everything Task 7 asks to confirm holds, and the `KeyboardInterrupt` catch
   Task 3 specifies still covers the case it was written for — an interrupt *before* uvicorn exists,
   during the probe or the bind — which is pinned by
   `test_a_keyboard_interrupt_during_run_exits_zero`. **Not verified:** what an interactive Ctrl-C
   (`CTRL_C_EVENT`) yields, because it cannot be delivered to a detached child in this harness
   without also signalling the driver; `CTRL_BREAK_EVENT` is the proxy the story itself specifies.
   Worth Brad's eye during manual testing, and deliberately not "fixed" by trapping a signal, which
   would be new behaviour outside this story's ACs.

**Two smaller notes.** (a) A test hazard the story flagged proved real and sharper than described:
pytest installs four handlers on the root logger *after* fixture setup, so a snapshot-and-clear
fixture is undone before the test body runs and `basicConfig` no-ops — the logging assertions would
have passed **vacuously**. The `root_logger_guard` fixture therefore exposes an explicit
`make_pristine()` the test body calls, with the restore still at teardown. (b) The `os.open` sitting
outside the `except OSError` (AC 11) is covered by
`TestFailureSplit::test_an_unopenable_path_propagates_oserror` — the easiest thing in the story to
get silently wrong, since contention and a real permission failure are the same exception on Windows.

**Deferrals (AC 16).** Both entries closed in place in `deferred-work.md` with what actually shipped
rather than the plan: the c1-8 launch race (**CLOSED**, with the primitive, the ordering, the
measured release-on-hard-kill and the before/after race probe) and the c1-7 `remove_discovery`
TOCTOU (**CLOSED by unreachability**, stating plainly that two instances under *different*
`PLANESWALKER_DATA_DIR` values is a supported configuration that reopens nothing — the c1-8
`trust_env` lesson applied in advance). `remove_discovery`'s docstring was corrected to match; that
sentence is the only change `src/companion/discovery.py` received. **No new residual** was found, so
no c1-9 section was opened.

**Open questions 1-3 were left as the story built them** (`--port` exists; no second probe on the
contention path; `2` for usage errors), since all three are implemented and reversible cheaply.

### File List

**New**

- `src/companion/app/singleton.py`
- `tests/unit/companion/test_singleton.py`
- `plugin/server/src/companion/app/singleton.py` _(generated mirror)_

**Modified**

- `src/mcp_server/__main__.py`
- `src/companion/app/server.py`
- `src/companion/app/main.py` _(comment only)_
- `src/companion/app/security.py` _(comment only)_
- `src/companion/app/errors.py` _(comment only)_
- `src/companion/discovery.py` _(docstring only)_
- `tests/unit/companion/test_server.py`
- `tests/integration/mcp_server/test_entry_point.py`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/c1-9-one-console-script-that-dispatches-without-disturbing-the-mcp-server.md`
- `plugin/server/src/mcp_server/__main__.py`, `plugin/server/src/companion/app/server.py`,
  `plugin/server/src/companion/app/main.py`, `plugin/server/src/companion/app/security.py`,
  `plugin/server/src/companion/app/errors.py`, `plugin/server/src/companion/discovery.py`
  _(generated mirror)_

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-26 | **Implemented — all 19 ACs met; Status → review.** `main()` became the subcommand dispatcher (`_run_mcp_server` carrying the old body verbatim, `_run_companion`, `_usage`, `_usage_error`, `_parse_companion_port`, `raise SystemExit(main())` footer); new app-layer `src/companion/app/singleton.py` holds a process-lifetime OS advisory lock wired into `run()` below c1-8's refusal and released in the outermost `finally`; the root logger is configured on the companion path only (INFO, stderr), and the six now-false "no root handler exists until c1-9" sentences across four files were repaired with no level or behaviour change. Both `deferred-work.md` entries closed — the c1-8 launch race outright, the c1-7 `remove_discovery` TOCTOU by unreachability with the different-data-dir caveat stated. Suite 1,629 → **1,681 passed / 1 skipped / 45 deselected**; ruff, `mypy src/`, `mypy src/ --platform linux` and the pre-commit mypy hook all clean; plugin mirror rebuilt; the seventeen AC 19 forbidden paths verified untouched by command. Live: the 6 ms race now leaves **one** survivor whose port is the one `companion.json` names, the bare entry point still emits exactly one JSON-RPC stdout line, and `src.*` log records reach a user's terminal for the first time. Three findings recorded in the Completion Notes — AC 15's "leave the two old entry-point tests alone" was unsatisfiable against AC 1's `sys.argv[1:]` default (fixed by passing `[]`); mutation 2 (`LK_NBLCK`→`LK_LOCK`) *hung* rather than failed, so a deadline assertion was added to guard the AC 9 primitive choice; and Ctrl-C exits `3` on Windows from the console-control path after uvicorn's graceful shutdown, not from the dispatcher (`main()` demonstrably never returns), with interactive `CTRL_C_EVENT` left unverified. |
| 2026-07-26 | Story c1-9 created from epics Story 1.9 (including Brad's 2026-07-26 held-lock amendment, commit `8bfc909`) + AD-14/AD-15/AD-3, with every load-bearing claim measured in this environment rather than assumed: the launch race reproduces with two processes spawned **6 ms** apart, both surviving while the rendezvous names only one; an OS advisory lock taken with `msvcrt.locking(LK_NBLCK)` is refused for a second descriptor **in the same process** (which is what makes a cheap real contention test possible) and is released by the kernel on a hard kill (which is what makes the held-lock design correct under AD-15); the installed console wrapper really is `sys.exit(main())`, so `main()`'s return value is the exit status; the bare entry point today emits exactly one stdout line (JSON-RPC) and five stderr diagnostics; and uvicorn 0.51.0's `LOGGING_CONFIG` leaves an already-configured root handler in place, so the companion can finally log. Six decide-once rulings: the lock is app-layer not leaf; the probe runs before the lock (so every c1-8 test stands unedited); no second probe on the contention path; the lock file is never deleted (POSIX `flock` binds to the inode); exit `0` for both refusals and `2` for usage errors; the root logger is configured by the entry point at INFO on stderr. Also catches the six now-stale "no root handler exists until c1-9" comments across four files, the `--port` promise sitting in `resolve_preferred_port`'s docstring, and the two `deferred-work.md` entries (the c1-8 launch race, and the c1-7 `remove_discovery` TOCTOU whose reachability the lock collapses to zero — the substance of Greptile's 3/5 hold on PR #15) that this story must close rather than re-defer. Baseline measured at `8bfc909`: 1,629 passed / 1 skipped / 45 deselected (319 passed / 1 skipped in `tests/unit/companion`). Status → ready-for-dev. |

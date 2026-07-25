---
baseline_commit: 2461ade
epic: c1
story: c1-7
work_branch: feat/companion-app
story_branch: feat/companion-c1-7-discovery-file-rendezvous
---

# Story C1.7: Discovery file as the sole rendezvous

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a companion MCP tool,
I want the backend to publish where it is and how to authenticate in one atomically written file,
so that I can find a running app without hardcoding a port and without ever reading a half-written file.

**Why this story is seventh.** Six stories built a process that can be *addressed*; this is the one
that makes it *findable*. c1-3 pre-binds the socket precisely so the lifespan knows the real port
before it runs (`server.py`'s module docstring names this story as the reason), c1-2 left the
lifespan a place to hang startup effects, and `_shutdown`'s docstring already says "Story c1-7
removes the discovery file here too". It is also the first story to create a **second leaf module**
— `discovery.py` has been named in `test_import_boundary._LEAF_MODULES` since c1-1, and one of that
file's *clean-case* fixtures is literally a comment about "discovery.py's atomic temp+rename write".
Everything downstream rendezvouses through this file: c1-8's single-instance check reads it, c6-1's
leaf client reads it before every push, and c5-5 authenticates `POST /agent/events` against the
token minted here. It is also the first story whose lifespan writes to the user's real data
directory, which is why **test isolation is an AC rather than a side effect** (AC 12).

## Acceptance Criteria

1. **One leaf module owns the file: `src/companion/discovery.py`.** The spine's Structural Seed
   names it (`discovery.py # LEAF — atomic companion.json r/w (AD-4)`). It exports exactly:

   - `COMPANION_FILENAME = "companion.json"` — the one place the name is written;
   - `DiscoveryRecord` — the pydantic model of the file's contents (`port`, `token`, `instance_id`);
   - `discovery_path() -> Path` — `src.paths.data_dir() / COMPANION_FILENAME`, resolved **at call
     time**, so writer and reader can never disagree about the location and no caller invents one;
   - `mint_token() -> str` — the credential mint;
   - `write_discovery(record: DiscoveryRecord) -> Path` — the atomic publish, returning the path;
   - `read_discovery() -> DiscoveryRecord | None` — `None` means *app not running*;
   - `remove_discovery(instance_id: str) -> bool` — ownership-guarded removal (AC 11).

   **Leaf constraints (AD-3):** stdlib + `pydantic` + `src.paths` only. Not `fastapi`, not
   `sqlalchemy`, not `src.companion.app.*`, **not even under `if TYPE_CHECKING:`** (the guard has no
   `TYPE_CHECKING` exemption for the leaf). `httpx` is permitted but **not used here** — the HTTP
   identity probe is c1-8's, and importing httpx for nothing would be dead weight in a module a
   stdio MCP session imports.

2. **The location honours `PLANESWALKER_DATA_DIR` (AD-4).** `discovery_path()` calls
   `src.paths.data_dir()` — never `platformdirs` directly, never a hardcoded `~/…`. Because
   `data_dir()` ends in `mkdir(parents=True, exist_ok=True)`, it must be called **inside the
   function**, never at module level, in a default argument, or in a class body: an import-time
   resolution would create the data directory just by importing the leaf and would turn
   `test_app.py::test_import_and_construction_create_no_directory` red. One test asserts the
   resolved path sits under an overridden `PLANESWALKER_DATA_DIR`, and one asserts importing
   `src.companion.discovery` creates no directory.

3. **The write is atomic: temp file in the same directory, then `os.replace`.** In order: resolve
   the directory, `tempfile.mkstemp(dir=<that directory>)`, write the serialized record, `flush()`
   + `os.fsync(fileno())`, `os.chmod(temp, 0o600)`, `os.replace(temp, target)`. Four details are
   load-bearing and each was verified in this environment (see Latest technical information):

   - **`os.replace`, never `os.rename`.** `os.rename` over an existing file raises `FileExistsError`
     on Windows — so a second launch after a stale file was left behind would fail on the rename,
     on Brad's platform only. Test with teeth: `monkeypatch.setattr(os, "rename", boom)` and the
     write still succeeds, plus a write **over an existing file** succeeds.
   - **The temp file lives in the target's own directory**, because `os.replace` is only atomic
     within one filesystem, and the system temp dir may be on another volume.
   - **`mkstemp`, not a fixed `companion.json.tmp`**, so two processes starting at once cannot
     write the same temp file and hand each other a spliced record.
   - **The temp file is removed on any failure** (`try/except/finally`), so a failed write leaves no
     `.tmp` litter beside the real file and — the actual claim — **no reader can observe a partially
     written file**: the target is only ever moved into place whole. Test: make `os.replace` raise,
     then assert the target still holds the *previous* content (or still does not exist) and the
     directory contains no leftover temp file.

   `os.chmod(…, 0o600)` is **POSIX-effective only** — verified to leave `0o666` on Windows, where
   the per-user `%LOCALAPPDATA%` directory is the protection. It is applied to the temp file
   *before* the replace so the file is never briefly world-readable at its real name.

4. **The token is a per-process secret, minted fresh on every start.**
   `mint_token()` returns `secrets.token_urlsafe(32)` — 256 bits of entropy, 43 URL-safe characters,
   verified. The lifespan mints it once per process, so two starts never share a token and a
   restarted backend invalidates the one a tool was holding (which is exactly what c6-1's
   retry-once exists to absorb). `DiscoveryRecord.token` carries **`Field(repr=False)`** so an
   accidental `logger.info("%s", record)`, an f-string, or a traceback frame cannot print it
   (verified: the token is absent from both `repr()` and `str()`). It is **not** a `SecretStr` — that
   would serialize to `"**********"` and write a file no tool could authenticate with, a bug that
   only shows up at runtime.

5. **The token appears in no log line, no REST response and no schema (AD-5).** One test drives a
   full lifespan with `caplog.set_level(logging.DEBUG)` on the **root** logger and asserts the token
   substring is absent from every captured record's formatted message *and* its `args`; the same
   test asserts it is absent from the `GET /health` body, from every response header, and from
   `json.dumps(app.openapi())`. The token reaches exactly two places: the discovery file, and
   `app.state.agent_token` in memory. The AC's other two surfaces — HTML and WebSocket frames — do
   not exist yet (c2-1 serves the SPA, c5-3 opens the socket); what this story owes them is that the
   token never enters a shape either could serialize, which is why it lives on `app.state` behind an
   accessor and in no pydantic model that reaches `app.openapi()`.

6. **The reader never raises — every unusable file is *app not running* (AD-4).**
   `read_discovery()` returns `None`, never an exception, for each of:

   | File state | Raises | Caught as |
   | --- | --- | --- |
   | absent | `FileNotFoundError` | `OSError` |
   | a directory at that path | `PermissionError` (Windows) / `IsADirectoryError` | `OSError` |
   | unreadable (permissions) | `PermissionError` | `OSError` |
   | not JSON at all | `ValidationError` | `ValueError` |
   | truncated mid-write | `ValidationError` | `ValueError` |
   | valid JSON, wrong shape (`{}`, missing key, wrong type) | `ValidationError` | `ValueError` |
   | not valid UTF-8 | `ValidationError` (via `model_validate_json`) | `ValueError` |

   So the whole net is **`except (OSError, ValueError)`** — verified: `pydantic.ValidationError`,
   `json.JSONDecodeError` and `UnicodeDecodeError` are all `ValueError` subclasses. Read with
   `path.read_bytes()` + `DiscoveryRecord.model_validate_json(...)`: one read, one parse, one
   `except`. Do **not** add a bare `except Exception` — a `MemoryError` or a `KeyboardInterrupt`
   during a read is not "app not running". A rejected read logs at **DEBUG**, not WARNING: for
   c6-1's client the ordinary, expected case is that no file exists at all, and a WARNING per push
   would be noise in the user's terminal.

7. **The reader validates shape, and ignores unknown keys.** `port` is `int` constrained
   `ge=1, le=65535` (a record naming port 0 or -1 points at nothing reachable), `token` and
   `instance_id` are `str` with `min_length=1` — so a zero-length credential is *app not running*
   rather than an auth attempt with an empty string. Extra keys are **ignored** (pydantic's default,
   verified), which is deliberate: a newer backend that adds a field must not make an older reader
   report "not running". One parametrized test per rejected shape, paired with a valid record that
   round-trips, so the suite cannot pass by rejecting everything.

8. **The lifespan publishes the rendezvous, and is the only writer (AD-10, AD-4).** `main.lifespan`
   gains, in this order: mint `instance_id` (unchanged) → `app.state.agent_token =
   discovery.mint_token()` → create the `Database` holder (unchanged) → publish. Publishing records
   **`bound_port(app)`** — the port the runner actually bound, so an ephemeral fallback is what
   lands in the file, never the 8765 default. A test that stamps a non-default port through the seam
   and reads the file back pins this; nothing in `discovery.py` may name 8765 (AD-4: the default bind
   attempt in `server.py` is the only place that number appears in `src/`).

9. **No bound port, no file.** `bound_port(app) is None` means nobody bound a socket — a
   `build_app()` served directly, or a test entering the lifespan with `bound_port=None`. There is
   nothing truthful to publish, so the publish is **skipped with a `WARNING`** (not an INFO: no root
   handler is configured until c1-9, and `logging.lastResort` surfaces WARNING+ to stderr — the same
   reasoning as `server.py:178`) and startup continues. Driven directly through the seam's existing
   `bound_port=None` argument, asserting no file was created.

10. **A failed publish fails the launch.** The publish sits **before** the lifespan's `try`, so an
    `OSError` from it propagates and uvicorn exits loudly with the traceback on stderr (AD-15 — this
    process owns them). This is the ruling, not an accident: without the file the app is reachable
    only by a human reading the printed URL, every agent tool reports `app_not_running` while the app
    is visibly running, and the user has no way to connect the two. A loud failure at the moment the
    data directory is unwritable is diagnosable; a half-launched rendezvous is not.
    `test_app.py::test_startup_failure_propagates` — written to catch a story widening that `try` —
    stays green **unedited**, and this story deliberately keeps it accurate. Test: patch
    `write_discovery` to raise `OSError`, assert it escapes `async with lifespan(app)`.

11. **Clean shutdown removes our own entry — and only ours.** `_shutdown` calls
    `discovery.remove_discovery(app.state.instance_id)`, which reads the file back and unlinks it
    **only when the recorded `instance_id` matches**. A foreign entry, an absent file, or an
    unparseable one is left exactly as found and the function returns `False`. The epic AC says "the
    discovery file is removed"; this is that, plus the guard that stops a second dev instance (or a
    test) from deleting a live instance's rendezvous — and it is the same ownership question c1-8's
    reclaim rule answers from the other side. Removal happens **first** in `_shutdown`, before the
    engine dispose: reverse order of acquisition, and it stops the process advertising itself as
    early as possible. It never raises — an `OSError` (Windows: another process holds the file open)
    is logged at `WARNING` and swallowed. Four tests: ours is removed; a foreign entry survives byte
    -for-byte; no file is a clean no-op; an unlink failure is logged and does not escape.

12. **Test isolation is a deliverable of this story (the one pre-existing test file that changes).**
    `tests/unit/companion/conftest.py` gains an **autouse** fixture pointing `PLANESWALKER_DATA_DIR`
    at each test's own `tmp_path`. Without it, the **~94** `lifespan_client` / `lifespan(app)` entries
    already in `test_app.py`, `test_deps.py`, `test_errors.py` and `test_security.py` would each
    write a real `companion.json` into the developer's `%LOCALAPPDATA%\artificial-planeswalker`
    (verified: no `companion.json` is there today), race each other, and leave the machine's own
    running companion clobbered by a test run. The fixture sets **only** `PLANESWALKER_DATA_DIR` —
    not `CARDS_DATABASE_URL`, because discovery never reads it and c1-6's tests manage that variable
    per-test (its Gotcha 4). Tests that set `PLANESWALKER_DATA_DIR` themselves keep winning, since
    a per-test `monkeypatch.setenv` runs after fixture setup. Pin it with
    `test_the_isolation_fixture_is_active`, asserting `discovery_path()` resolves under pytest's tmp
    root — so deleting the fixture turns a test red rather than quietly polluting a machine.

13. **The import boundaries stay green, unedited.** `discovery.py` is already listed in
    `_LEAF_MODULES`, so `test_every_companion_file_sits_in_a_guarded_category` classifies it with no
    edit. The write guard must find nothing: no `session.add/commit/flush/delete/merge` on a
    `session`/`db`/`database`/`conn` receiver, no `sqlalchemy` DML, no `init_database`/`create_all`.
    `handle.flush()` inside the atomic write is explicitly a *clean case* in that file
    (`_SRC_FILE_FLUSH`) — but only because the receiver is not session-shaped, so **do not name a
    local `db`, `conn`, `session` or `database`** in this module. `tests/unit/companion/
    test_import_boundary.py` is **not** edited.

14. **`agent_token(app)` joins `bound_port(app)` in `main.py`.** Same shape, same docstring
    discipline, same annotated-local trick (`app.state` is `Any`; `warn_return_any` flags returning
    it directly): `def agent_token(app: FastAPI) -> str | None`. `app.state` gets exactly one reader
    per value, `None` means *the lifespan never ran*, and the docstring names c5-5 (`POST
    /agent/events` compares the presented credential against this) as the production consumer and
    forbids serializing it. Today's consumer is AC 5's leak test, which needs to know the string it
    is searching for.

15. **Tests: `tests/unit/companion/test_discovery.py`**, unmarked unit tests, no network and no
    server boot. The leaf functions are driven **directly** (they need no app at all — that is the
    point of a leaf), and the lifespan behaviours through the existing `lifespan_client` seam on a
    real `build_app()`. Cover: AC 2's location + import-inertness; AC 3's atomicity (the `os.rename`
    mutation, over-write, interrupted-write leaves target and directory clean); AC 4's entropy,
    uniqueness across mints and `repr` suppression; AC 5's four leak surfaces; AC 6's seven reader
    cases; AC 7's shape matrix plus the extra-key round-trip; AC 8's real-port record and a
    write→read round-trip; AC 9's skip; AC 10's propagation; AC 11's four removal cases; AC 12's
    fixture pin.
    **Non-vacuity:** every "returns `None`" assertion is paired with a well-formed file that returns
    a populated record from the same call, so the reader cannot pass by refusing everything — the
    lesson from Greptile's PR #12 catch, restated by c1-6's AC 14.

16. **Quality gates green (NFR-07).** `uv run ruff check .`, `uv run ruff format --check .`,
    `uv run mypy src/`, `uv run mypy src/ --platform linux` and `uv run pytest -m "not integration"`
    all pass with **no new failures** against the **1,532 passed / 45 deselected** baseline (verified
    at `2461ade` on 2026-07-26; the companion sub-suite is **222 passed**). Actual output pasted into
    the Debug Log.

17. **Plugin mirror rebuilt and committed.** `uv run python -m scripts.build_plugin`, then commit
    `plugin/`; `git status --porcelain -- plugin/` clean afterwards.

18. **Scope boundary — what this story must NOT do.**
    - **No single-instance check** (c1-8). This story *overwrites* whatever `companion.json` it
      finds; c1-8 inserts the "is it live?" probe **before** this write. Do not add a liveness test,
      an "already running" message, or a `sys.exit`.
    - **No HTTP identity probe** (c1-8's own AC puts it in the leaf, and it is c1-8's to put there).
      No `httpx` import in `discovery.py`.
    - **No `client.py`** (c6-1), no companion MCP tool, no `src/mcp_server/**` change of any kind.
    - **No token *authentication*** — nothing checks a presented token yet (c5-5). No new endpoint,
      no new route, no `/agent/events`.
    - No CLI or root-logger configuration (c1-9). No new reason token, no `contracts.py` change, no
      new dependency, no `pyproject.toml` / `uv.lock` / `.pre-commit-config.yaml` edit (`secrets`,
      `tempfile`, `os`, `json` are stdlib; `pydantic` and `src.paths` are already leaf-legal).
    - No edit to `test_app.py`, `test_errors.py`, `test_security.py`, `test_server.py`,
      `test_deps.py`, `test_import_boundary.py`, `.github/workflows/ci.yml`, `src/companion/app/
      deps.py`, `errors.py`, `security.py`, `server.py`, `routes/`, `src/data/**` or `src/paths.py`.
      `tests/unit/companion/conftest.py` **is** edited (AC 12) — it is the single exception, and if
      any *other* file on this list needs a change, that is a finding, not an edit.
    - Checked rather than assumed: `test_server.py` needs no edit even though `run()` now leads to a
      discovery write, because its `recorded_serve` fixture replaces `server._serve` — the lifespan
      never runs in that file (0 lifespan entries, verified).

## Tasks / Subtasks

- [ ] **Task 0 — State verification** (standing team agreement since the epic-6 retro: any story
      whose notes assert repository state opens with the cheap check that proves it)
  - [ ] Create `feat/companion-c1-7-discovery-file-rendezvous` **off `feat/companion-app`**
        (currently at `2461ade`); the story PR targets `feat/companion-app`.
  - [ ] Confirm `src/companion/discovery.py` and `tests/unit/companion/test_discovery.py` do **not**
        exist, and that `main.lifespan` today mints `instance_id`, creates `deps.Database()`, logs,
        then `try/yield/finally`.
  - [ ] Baseline the suite: `uv run pytest -m "not integration" -q` → expected **1,532 passed, 45
        deselected**; `uv run pytest tests/unit/companion -q` → **222 passed**. Record any delta
        rather than chasing it.
  - [ ] Re-confirm the three findings the ACs are shaped around, in a few lines each: `os.rename`
        over an existing file raises `FileExistsError` on Windows while `os.replace` succeeds;
        `pydantic.ValidationError` is a `ValueError`; and the real data dir
        (`src.paths.data_dir()`) currently holds **no** `companion.json`.

- [ ] **Task 1 — Isolate the tests first** (AC: 12)
  - [ ] Add the autouse `PLANESWALKER_DATA_DIR` fixture to `tests/unit/companion/conftest.py`,
        with a docstring saying *why* (the lifespan is about to acquire a real filesystem effect and
        ~94 lifespan entries would land it in the developer's data directory).
  - [ ] Run the companion suite **before** writing any production code: still **222 passed**. This
        ordering is deliberate — the fixture must be proven inert against today's behaviour, so a
        later failure is attributable to the feature and not to the fixture.

- [ ] **Task 2 — The leaf, test-first** (AC: 1, 2, 3, 4, 6, 7)
  - [ ] Write AC 6's reader matrix and AC 7's shape matrix as parametrized tests against
        `read_discovery` first; watch them fail on the missing module (red-phase evidence for the
        Debug Log).
  - [ ] `src/companion/discovery.py` — module docstring covering: why this file is the *sole*
        rendezvous (AD-4), why it is a leaf and what that forbids (AD-3 — a stdio MCP session must
        not import FastAPI to learn a port), why the write is temp + `os.replace` and why
        `os.rename` is wrong on Windows, why a parse failure is *app not running* rather than an
        error, and that the token must never be logged. Module-level
        `logger = logging.getLogger(__name__)`.
  - [ ] `COMPANION_FILENAME`, `discovery_path()`, `DiscoveryRecord` (with `Field(repr=False)` on
        `token` and the constraints from AC 7), `mint_token()`, `write_discovery()`,
        `read_discovery()`, `remove_discovery()` — Google docstrings on each, `Raises:` on
        `write_discovery` (the only one that may raise) and an explicit "never raises" line on the
        other two.
  - [ ] Keep every local name clear of `_SESSION_RECEIVERS` (Gotcha 5).

- [ ] **Task 3 — Publish from the lifespan** (AC: 8, 9, 10, 14)
  - [ ] `src/companion/app/main.py` — `app.state.agent_token = discovery.mint_token()` beside the
        identity mint; a module-level `_publish_discovery(app)` helper that reads `bound_port(app)`,
        skips with a `WARNING` when it is `None`, otherwise builds the record and writes it, logging
        the resulting **path and port** at `INFO` (never the token).
  - [ ] `agent_token(app)` accessor, mirroring `bound_port` line for line.
  - [ ] Change nothing else in `main.py` — `build_app`, `_CompanionFastAPI`, the middleware ordering
        and the app-level `responses=` are untouched, and no new work moves inside the lifespan's
        `try`.
  - [ ] Re-run `test_app.py` **unedited** — especially `TestConstructionIsInert` and
        `test_startup_failure_propagates`.

- [ ] **Task 4 — Retract on shutdown** (AC: 11)
  - [ ] `_shutdown` — `remove_discovery(instance_id)` **before** the engine dispose, guarded on the
        `instance_id` being present at all (a test may drive `_shutdown` on an app whose lifespan
        never ran). Update the docstring: it now releases two things, and says which order and why.
  - [ ] Verify by test that a foreign entry survives byte-for-byte.

- [ ] **Task 5 — Tests** (AC: 3, 5, 8, 9, 10, 11, 15)
  - [ ] `tests/unit/companion/test_discovery.py` per AC 15, with the non-vacuity pairings called out
        in comments.
  - [ ] The AC 3 atomicity tests must have teeth: the `os.rename`-explodes mutation, and the
        interrupted-write assertion on **observable filesystem state** (target content unchanged,
        no leftover temp file) — never "a mock went uncalled".
  - [ ] AC 5's leak test captures the **root** logger at DEBUG for the whole lifespan, and checks
        `record.getMessage()` *and* `record.args` (a `%`-style record hides its arguments from the
        unformatted `msg`).

- [ ] **Task 6 — Gates, mirror, deferred-work and scope** (AC: 13, 16, 17, 18)
  - [ ] `uv run ruff check . --fix` · `uv run ruff format .` · `uv run mypy src/` ·
        `uv run mypy src/ --platform linux` · `uv run pytest -m "not integration"` — paste actual
        counts into the Debug Log.
  - [ ] `_bmad-output/implementation-artifacts/deferred-work.md`: record the **Windows
        replace-while-open** hazard (Gotcha 2) — measured here, no failing user story behind it,
        natural home is c1-8, which is the story that makes startup contend with an existing file.
        Per the epic-7 gate-output rule, home it rather than fix it.
  - [ ] `uv run python -m scripts.build_plugin`, `git add plugin/`, verify
        `git status --porcelain -- plugin/` is clean after the commit.
  - [ ] Confirm by command that the AC 18 forbidden files are untouched:
        `git status --porcelain -- tests/unit/companion/test_app.py tests/unit/companion/test_deps.py tests/unit/companion/test_errors.py tests/unit/companion/test_security.py tests/unit/companion/test_server.py tests/unit/companion/test_import_boundary.py .github/workflows/ci.yml pyproject.toml uv.lock .pre-commit-config.yaml src/data src/mcp_server src/paths.py src/companion/contracts.py src/companion/app/deps.py src/companion/app/errors.py src/companion/app/security.py src/companion/app/server.py`
        returns empty.

## Dev Notes

### Decide-once rulings (made here so four later stories inherit them)

**#1 — The record's model lives in `discovery.py`, not `contracts.py`.** `contracts.py`'s own
docstring scopes it to "every shape that crosses the companion's **HTTP and WebSocket** boundary",
and AD-12 generates the SPA's TypeScript from `app.openapi()`. The discovery record crosses a
*filesystem* boundary between two backend-side processes and must never reach the browser at all —
putting it in `contracts.py` would either emit a TS type for a shape no SPA code can use, or, worse,
invite a future story to hand it back over HTTP. The two leaf modules split cleanly: `contracts.py`
is what goes on the wire, `discovery.py` is what goes on disk.

**#2 — Removal is ownership-guarded.** The epic AC reads "the discovery file is removed"; taken
literally that is `unlink()`, and it is wrong the moment two processes exist — which they do, because
c1-8's *entire* subject is a second launch meeting a file it did not write. Reading the file back and
matching `instance_id` costs one small read on a path that runs once per process lifetime, and it
makes the shutdown correct under exactly the condition the next story introduces. It also composes
with AC 9: a process that never published removes nothing, with no special case.

**#3 — A failed publish fails the launch; it does not degrade.** The alternative — log the failure
and serve anyway — was rejected. The observable result of that choice is an app the user can see in
the browser while every agent tool reports `app_not_running`, with nothing in either surface
explaining the contradiction. AD-4 calls the file "the sole rendezvous"; a companion that cannot
publish it is not a degraded companion, it is a browser page. And the failure mode is narrow and
actionable (an unwritable data directory), so failing at startup puts the traceback in front of the
person who can fix it. Recorded as Open Question 1 in case Brad wants the opposite trade.

**#4 — `Field(repr=False)`, not `SecretStr`.** `SecretStr` protects `repr` *and* serialization —
which sounds strictly better until `model_dump_json()` writes `{"token": "**********"}` into
`companion.json` and every tool fails to authenticate against a backend that is running perfectly.
The failure would be invisible to the unit suite (which would compare a `SecretStr` to a `SecretStr`)
and would surface only in c5-8's one real-socket test, or on Brad's machine. `repr=False` covers the
realistic leak — a stray `logger.info("%s", record)` or an exception frame — without touching
serialization. AC 5's leak test is the belt to that suspender.

**#5 — Test isolation is production-relevant, not test hygiene.** This is the first lifespan effect
that lands on the *user's* disk rather than in process memory, so it is the first time an unisolated
test suite could destroy real state — specifically, a test run while Brad has the companion open
would overwrite the live `companion.json` and then, at teardown, decline to remove it (AC 11's
ownership guard saves the deletion but not the overwrite). The fixture is the fix; AC 11 is why the
damage is bounded even without it.

### Architecture rules this story implements

- **AD-4** — the sentence this story exists for: `src.paths.data_dir()/companion.json`, contents
  `{port, token, instance_id}`, **written atomically (temp + rename) by the lifespan and removed on
  clean shutdown**, and *"a parse failure is treated as app not running, never an error."* The other
  half of AD-4 — verify `instance_id` over `GET /health` before sending the token, and the
  single-instance rule — is **c1-8's**, deliberately not here.
- **AD-3** — the leaf grows its second module. The whole point of the split is that
  `src/mcp_server/tools/companion.py` can read a port and a token without a stdio session importing
  FastAPI and uvicorn; `discovery.py` is the module that makes that concrete.
- **AD-10** — construction stays inert, the lifespan owns the effect. The discovery write is the
  clearest example in the codebase of the rule: it is exactly the file AD-10 says a test must never
  overwrite by merely constructing an app.
- **AD-5** — two credentials that never touch. This story mints and publishes the **agent token**
  only. The WS ticket (c5-3) shares no storage and no code path with it, and this story adds no
  shared "credentials" module for a later one to hang the ticket on.
- **AD-15** — a crash leaves a stale file that the next start reclaims (c1-8) and that tools read as
  *app not running* (c6-1). That is why the reader's tolerance in AC 6 is a product behaviour, not
  defensive programming.
- **FR-14** — this story is its first half; `GET /health`'s `instance_id` echo (already shipped in
  c1-2) is what makes the file verifiable.

### Source tree — what exists, what this story adds

```text
src/
  companion/
    discovery.py               # NEW — COMPANION_FILENAME, DiscoveryRecord, discovery_path,
                               #       mint_token, write_discovery, read_discovery, remove_discovery
    contracts.py               # EXISTS — untouched (Decide-once #1)
    app/
      main.py                  # UPDATE — token mint, publish, agent_token(), _shutdown retracts
      deps.py                  # EXISTS — untouched
      errors.py                # EXISTS — untouched
      security.py              # EXISTS — untouched
      server.py                # EXISTS — untouched (its docstrings already name this story)
tests/
  unit/companion/
    test_discovery.py          # NEW
    conftest.py                # UPDATE — autouse PLANESWALKER_DATA_DIR isolation (AC 12)
    test_app.py                # EXISTS — NOT edited (AC 18)
    test_deps.py               # EXISTS — NOT edited (AC 18)
    test_errors.py             # EXISTS — NOT edited (AC 18)
    test_security.py           # EXISTS — NOT edited (AC 18)
    test_server.py             # EXISTS — NOT edited (AC 18)
    test_import_boundary.py    # EXISTS — NOT edited (AC 18)
```

**Current state of the files being modified** (read before editing):

- `src/companion/app/main.py` — `_TITLE`; `_shutdown(app)` (logs at DEBUG, then disposes the c1-6
  holder through `deps.database(app)`, guarded on `None`; its docstring **already promises** *"Story
  c1-7 removes the discovery file here too"* — make that true and update the wording); `lifespan`
  (mints `instance_id`, creates `deps.Database()`, logs "started", then `try/yield/finally` with the
  teardown wrapped in its own swallow-and-log); `bound_port(app)` (whose docstring already names
  *"c1-7's discovery-file writer"* as a caller); `_CompanionFastAPI`; `build_app()`.
  **What must be preserved:** no module-level side effect and **no module-level `src.paths` call**
  anywhere on the import chain — `test_app.py::test_import_and_construction_create_no_directory`
  fresh-imports this module with `PLANESWALKER_DATA_DIR` pointing at a non-existent directory and
  asserts it is never created, and `_FRESH_PREFIXES` includes `src.paths` *specifically* so a new
  import-time `data_dir()` call is caught; the swallow-wraps-teardown-only asymmetry
  (`test_startup_failure_propagates`); `bound_port`'s semantics; the middleware install order.
- `src/companion/app/server.py` — `run()` binds the socket, sets `app.state.bound_port = actual`,
  **then** serves, so the lifespan already finds the real port on `app.state`. Its module docstring
  explains that this inversion exists *for this story*. **Read, not modified.**
- `src/paths.py` — `data_dir()` mkdirs (that is the only side effect this story leans on),
  `database_path()`, `database_url()`. **Read, not modified.**
- `src/companion/contracts.py` — the leaf's existing member; read its docstring for the leaf rules
  and the house style for a leaf module. **Not modified.**
- `tests/unit/companion/conftest.py` — the `lifespan_client` seam. It stamps
  `app.state.bound_port = 54321` **only if the app has none**, and supports `bound_port=None` to
  drive the never-bound case (AC 9 uses exactly that). The seam itself needs **no change**; the only
  addition is the autouse isolation fixture beside it.
- `tests/unit/companion/test_import_boundary.py` — `_LEAF_MODULES` already lists
  `src/companion/discovery.py`; `_SESSION_MUTATORS`/`_SESSION_RECEIVERS` are the names to avoid;
  `_SRC_FILE_FLUSH` is a committed *clean case* written in anticipation of this story's atomic write.
  **Read, not modified.**

**Deviation from the spine's Structural Seed:** none. `discovery.py` is on the seed's list by name
with exactly this responsibility.

### Gotchas specific to this story

1. **`os.rename` over an existing file raises `FileExistsError` on Windows** (verified) — POSIX
   silently replaces. Use `os.replace`. This is the single most likely way for this story to ship a
   bug that only Brad sees, and only on the *second* launch after a crash.

2. **`os.replace` fails with `PermissionError [WinError 5]` while another process holds the target
   open for reading** (verified on this machine). The window is microseconds — a reader does
   `read_bytes()` and closes — and the write happens once per process start, so no retry machinery is
   added. But it means a publish failure is not *necessarily* a permissions problem, and under AC 10
   it aborts the launch. Home it in `deferred-work.md` against c1-8; do not build a retry loop here.

3. **`src.paths.data_dir()` mkdirs.** Calling it resolves *and creates* the directory. That is
   correct at lifespan time and forbidden at import time. Never call it at module level, in a
   default argument, or in a dataclass/pydantic field default.

4. **A `%`-style log record hides its arguments from `record.msg`.** `logger.info("port %d", port)`
   leaves `record.msg == "port %d"`. AC 5's leak test must call `record.getMessage()` **and** inspect
   `record.args`, or a `logger.debug("record=%s", record)` carrying the token would pass a naive
   substring check on `caplog.text`... which it would not, since caplog formats — but a test that
   iterates `records` and checks `.msg` would. Check both; belt and braces on a credential.

5. **The write guard reads names, not intent.** `_SESSION_RECEIVERS` includes `database`, `db`,
   `conn`, `session`; `_SESSION_MUTATORS` includes `add`, `delete`, `merge`, `commit`, `flush`. A
   local named `db` calling `.flush()` — entirely plausible in a file-writing module — turns
   `test_import_boundary.py` red for a reason that has nothing to do with databases. Name the file
   handle `handle` (the committed clean case uses `file`), the directory `directory`, the model
   `record`.

6. **`pydantic.ValidationError`, `json.JSONDecodeError` and `UnicodeDecodeError` are all
   `ValueError`s** (verified), which is what makes `except (OSError, ValueError)` a complete net and
   `except Exception` unnecessary. `model_validate_json` accepts `bytes`, so one `read_bytes()` +
   one `model_validate_json()` covers decode *and* parse *and* shape in a single `try`.

7. **Extra keys are ignored by default in pydantic v2** (verified) — do not set
   `model_config = ConfigDict(extra="forbid")`. A stricter reader would make a *newer* backend
   invisible to an *older* tool, which is the wrong direction for a file two independently-versioned
   halves share.

8. **`os.chmod(path, 0o600)` is a no-op for the permission bits on Windows** (verified: the file
   stays `0o666`). Apply it anyway for POSIX, and say so in the docstring rather than implying a
   protection the primary dev platform does not have.

9. **Directory `fsync` is not attempted.** On POSIX, full durability of a rename needs an `fsync` on
   the containing directory; on Windows a directory cannot be opened for `fsync` at all. It is
   deliberately skipped: the file is rewritten on every start, and a crash that loses it leaves
   *app not running* — which is true. Do not add a platform-branching durability dance.

10. **`_shutdown` runs inside the lifespan's swallow-and-log `finally`**, so a raise there is logged
    rather than fatal. That is not a licence to let `remove_discovery` raise: a raise would skip the
    engine dispose that follows it (`test_failing_teardown_is_logged_and_swallowed` proves the
    swallow, not the completion). Order matters, and so does never raising.

11. **The seam stamps a port on every companion test**, so *every* lifespan entry publishes a file
    once this story lands. That is why AC 12 comes first in the task order, and why AC 9's
    "no port, no file" case must be driven with the seam's explicit `bound_port=None`.

12. **`mypy --strict` details.** `discovery_path() -> Path`; `read_discovery() -> DiscoveryRecord |
    None`; `tempfile.mkstemp(dir=…)` returns `tuple[int, str]` (a `str`, not a `Path` — wrap it);
    `os.replace` accepts `StrPath` so a `Path` is fine; `agent_token(app)` needs the annotated-local
    trick `bound_port` uses. CI runs `mypy src/` on Linux, so also run
    `uv run mypy src/ --platform linux` locally — `server.py`'s `sys.platform == "win32"` branch is
    the precedent for why the two differ.

### Testing standards

- New tests live in `tests/unit/companion/test_discovery.py` — unmarked, fast, no network, no server
  boot. `--strict-markers` is on: do not invent a marker.
- `asyncio_mode = "auto"` — write `async def test_…` directly; no `@pytest.mark.asyncio`.
- Reuse the `lifespan_client` fixture unchanged for anything request- or lifespan-shaped; drive the
  leaf functions directly for everything else (a leaf that needs an app to be tested is not a leaf).
- Assert **observable filesystem state** — the file exists / does not / holds exactly these bytes /
  the directory has no leftovers — never that a mock went uncalled. This is the house style
  established by c1-2's inertness tests and c1-6's no-plant assertion.
- Fixtures write `companion.json` variants with plain `Path.write_text` / `write_bytes`, never
  through `write_discovery` — a test whose fixture is built by the code under test proves nothing
  (c1-6's rule, restated).
- **Verification before completion:** paste actual ruff / mypy / pytest output into the Debug Log.
  "Tests pass" without output is not acceptance — standing agreement from the epic-5/6 retros.

### Previous story intelligence (c1-6, done 2026-07-25, merged as PR #14)

- **The review found a vacuous concurrency test and Brad signed off the deviation rather than
  amending the AC.** The lesson carried into this story: where an AC names a *mechanism*, add at
  least one assertion that fails when the mechanism is removed. AC 3's `os.rename`-explodes mutation
  is that assertion here — it goes red the instant someone "simplifies" `os.replace` to `os.rename`.
- **c1-6's review produced four `[Review][Patch]` items on the same theme:** state published before
  it was fully built, and locks not held across mutation. The analogue here is the temp file — do not
  `os.replace` before `fsync`, and do not leave the temp path dangling on the failure branch.
- **Log hygiene was a review finding** (`hide_password` on the engine URL). This story's equivalent
  is the token, and AC 5 is the test that stops it recurring.
- **Four deferrals were homed by c1-6, none closed.** This story homes one (Gotcha 2) and closes
  none; record it against a new c1-7 section in `deferred-work.md`, per the epic-7 gate-output rule.
- **The `test_list_decks_with_strategy_field` same-tick ordering flake is still open** and lives in
  the same suite. If a full run shows that one test red, it is the known flake, not a regression.
- **`_shutdown` and `bound_port` already carry docstrings written for this story.** Read them before
  editing: c1-6 and c1-3 wrote forward-references to c1-7 deliberately, and leaving a promise
  unfulfilled ("Story c1-7 removes the discovery file here too") in a file that now does exactly
  that would be a documentation regression.

### Git intelligence

`HEAD = 2461ade` on `feat/companion-app` (the PR #14 merge), working tree clean. The per-story rhythm
across c1-1 → c1-6 is: one focused `feat(companion): …` commit implementing the story, review fixes
as separate `fix(companion): …` commits on the same branch, then a PR into `feat/companion-app`
(Greptile per story). c1-4 needed a `feat(companion)!:` for a breaking wire-contract change; this
story changes no wire contract, adds no reason token and needs no `!`.

Suggested commit: `feat(companion): discovery file as the sole rendezvous`.

### Latest technical information

Verified in this environment on 2026-07-26 — Python 3.12.13 · pydantic 2.12.0 · FastAPI 0.140.0 ·
Starlette 0.48.0 · httpx 0.28.1 · uvicorn 0.51.0, all at or above the spine's floors. No dependency is
added, upgraded or pinned by this story.

Probe results the ACs are built on (each re-runnable in a few lines):

```
1  issubclass(ValidationError, ValueError)      = True
1b issubclass(json.JSONDecodeError, ValueError) = True
1c issubclass(UnicodeDecodeError, ValueError)   = True
2  os.replace over an existing file             -> OK
3  os.replace while a reader holds it open      -> PermissionError [WinError 5]
4  len(secrets.token_urlsafe(32))               = 43
5  Field(repr=False) hides the token from repr() and str()
6  model_dump_json() still carries the token    = True
7  an unknown extra key is ignored              -> OK
8  port 0 / empty token / truncated JSON / non-JSON / {}  -> all ValidationError
9  flush() + os.fsync(fileno()) on a text-mode file       -> OK
10 os.chmod(path, 0o600) on Windows             -> 0o666 (no-op)
11 Path.unlink(missing_ok=True) on an absent file         -> OK
12 read_bytes() on a directory                  -> PermissionError (an OSError)
13 os.rename over an existing file (win32)      -> FileExistsError
14 mkstemp(dir=…) + fdopen + os.replace         -> OK, no leftovers
15 invalid UTF-8 bytes into model_validate_json -> ValidationError
```

Baseline measured at `2461ade`: **1,532 passed / 45 deselected** (full suite, `-m "not integration"`)
and **222 passed** (`tests/unit/companion`). The real data directory
(`C:\Users\brads\AppData\Local\artificial-planeswalker`) holds `cards.db`, its `-shm`/`-wal`
siblings and `fastembed_cache` — **no `companion.json`**, which is the state AC 12 exists to
preserve.

### Project Structure Notes

- `discovery.py` sits directly under `src/companion/`, is already enumerated in
  `test_import_boundary._LEAF_MODULES`, and is therefore classified with **no boundary-test edit**.
  It may import the stdlib, `pydantic`, `httpx` and `src.paths` — and nothing else, in any role,
  including under `if TYPE_CHECKING:`.
- Pre-existing tracked files modified: `src/companion/app/main.py`,
  `tests/unit/companion/conftest.py`, `_bmad-output/implementation-artifacts/deferred-work.md`,
  `_bmad-output/implementation-artifacts/sprint-status.yaml`, and the generated `plugin/` mirror.
  **Not** `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `src/paths.py`, `src/data/**` or
  `src/mcp_server/**`.
- Naming follows the project conventions: `snake_case` functions, `PascalCase` model, `UPPER_SNAKE`
  constant, Google docstrings on every public symbol, a module docstring at the top, `%`-style lazy
  log args, and guard clauses over nesting.

### References

- [epics-companion-app.md — Story 1.7](_bmad-output/planning-artifacts/epics-companion-app.md#L1075-L1108) — the source acceptance criteria · [Epic 1 framing](_bmad-output/planning-artifacts/epics-companion-app.md#L882-L888) · [FR-14](_bmad-output/planning-artifacts/epics-companion-app.md#L93-L97)
- Consumers, and the scope line between them and this story: [Story 1.8 — single-instance + the leaf identity probe](_bmad-output/planning-artifacts/epics-companion-app.md#L1110-L1138) · [Story 6.1 — the leaf client that reads this file before every push](_bmad-output/planning-artifacts/epics-companion-app.md#L2563-L2604) · [Story 5.8 — the one real-socket test, which writes a real discovery file under an isolated data dir](_bmad-output/planning-artifacts/epics-companion-app.md#L2521-L2552) · [Story 8.2 — the uninstall note about a leftover file](_bmad-output/planning-artifacts/epics-companion-app.md#L3174-L3176)
- ARCHITECTURE-SPINE.md — [AD-4](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L127-L141) · [AD-3](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L114-L125) · [AD-5](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L143-L157) · [AD-10](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L227-L240) · [AD-15](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L315-L327) · [Structural Seed](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L438-L462)
- [prd.md — FR-14](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L103) · [FR-01, the single-instance half c1-8 owns](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L102) · [the stale-file risk row](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L203)
- [src/companion/app/main.py](src/companion/app/main.py#L41-L96) — `_shutdown` and the lifespan this story extends · [`bound_port`](src/companion/app/main.py#L98-L123) — the accessor pattern `agent_token` copies, and its docstring naming this story
- [src/companion/app/server.py](src/companion/app/server.py#L1-L19) — why the socket is pre-bound *for this story* · [`_serve`](src/companion/app/server.py#L190-L208) — `lifespan="on"` so this write is never bypassed
- [src/companion/contracts.py](src/companion/contracts.py#L1-L15) — the leaf rules and house style, restated in the sibling module
- [src/paths.py](src/paths.py#L23-L50) — `data_dir()` mkdirs; `PLANESWALKER_DATA_DIR` precedence
- [tests/unit/companion/conftest.py](tests/unit/companion/conftest.py#L16-L23) — why the seam stamps a port, and therefore why every lifespan entry will publish · [the seam](tests/unit/companion/conftest.py#L48-L86) — including the `bound_port=None` argument AC 9 uses
- [tests/unit/companion/test_import_boundary.py](tests/unit/companion/test_import_boundary.py#L113-L131) — `_LEAF_MODULES` already lists `discovery.py`, and the leaf's allowed surface · [the session-receiver names to avoid](tests/unit/companion/test_import_boundary.py#L86-L92) · [`_SRC_FILE_FLUSH`](tests/unit/companion/test_import_boundary.py#L670-L676) — the clean case written in anticipation of this write
- [tests/unit/companion/test_app.py](tests/unit/companion/test_app.py#L63-L101) — the inertness tests that must stay green unedited · [`test_startup_failure_propagates`](tests/unit/companion/test_app.py#L203-L220) — the asymmetry AC 10 leans on
- [c1-6 story record](_bmad-output/implementation-artifacts/c1-6-lazy-database-engine-so-a-fresh-install-starts-instead-of-erroring.md) — the lifespan/teardown seam, the vacuous-test lesson and the log-hygiene finding · [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md)
- [project-context.md](_bmad-output/project-context.md) — `%`-style lazy logging, ruff/mypy, Google docstrings, module docstrings

## Open questions for Brad

Neither blocks implementation.

1. **Should an unwritable data directory abort the launch, or degrade to browser-only?**
   Decide-once #3 chooses abort: the rendezvous is the product, and the degraded mode is an app that
   is visibly running while every tool says it is not. The reverse trade — log an ERROR and serve the
   UI anyway — is a two-line change if you would rather never lose the deck view to a filesystem
   problem. Recording it now so the choice is inherited rather than rediscovered in c1-8.
2. **The token is never rotated within a process.** It is minted once at startup and lives until the
   process exits, so a token captured from the file stays valid for the session. That is the right
   floor for a loopback-only, single-user, foreground process, and rotation would break c6-1's
   retry-once contract (a tool would see auth failures it could not attribute to a restart). Noted
   rather than proposed — say the word if the file should be re-minted on some interval.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-26 | Story c1-7 created from epics Story 1.7 + AD-4/AD-3/AD-5/AD-10/AD-15, with every load-bearing claim verified against the installed pydantic 2.12.0 / Python 3.12.13 on Windows rather than assumed: `os.rename` over an existing file raises `FileExistsError` while `os.replace` succeeds, `os.replace` fails with `PermissionError` while a reader holds the target open, `ValidationError`/`JSONDecodeError`/`UnicodeDecodeError` are all `ValueError`s, `Field(repr=False)` hides the token from `repr` and `str` while `model_dump_json` still writes it, pydantic ignores unknown keys by default, `os.chmod(0o600)` is a no-op on Windows, and `mkstemp(dir=…)` + `fdopen` + `os.replace` leaves no litter. Baseline re-measured at `2461ade`: 1,532 passed / 45 deselected (222 in `tests/unit/companion`), and the real data dir confirmed to hold no `companion.json` today. Five decide-once rulings: the record's model lives in `discovery.py` not `contracts.py`; shutdown removal is ownership-guarded by `instance_id`; a failed publish fails the launch; `Field(repr=False)` over `SecretStr`; and test isolation (the autouse `PLANESWALKER_DATA_DIR` fixture) is a first-class AC because ~94 existing lifespan entries would otherwise write into the developer's real data directory. Homes (does not fix) the Windows replace-while-open hazard against c1-8. Status → ready-for-dev. |

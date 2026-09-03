---
baseline_commit: e73fa7bf2331e59b8912785bbdc3bcc84cc036f7
---

# Story 1.2: SQLite ConnectionFactory with WAL & Extension Loading

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want all **synchronous** SQLite access routed through one connection factory that enables loadable extensions and WAL,
so that the MCP tools and the future RAG layer are driver-agnostic and the `sqlite-vec` vector extension can load without any module hardcoding `sqlite3.connect`.

## Acceptance Criteria

> Source: [epics.md#Story-1.2](../planning-artifacts/epics.md) (BDD as authored), with implementation-critical clarifications folded in from analysis. **All five must hold simultaneously.**

**AC1 — All sync SQLite access goes through the factory; no direct `sqlite3.connect`**
- **Given** any data-layer or tool code that needs a **synchronous** SQLite connection
- **When** it needs a connection
- **Then** it obtains one from `ConnectionFactory`
- **And** no module under `src/` calls `sqlite3.connect(...)` directly (the factory is the single seam).
- **Scope clarification:** This governs the **new sync `sqlite3` path** (MCP tools, the `sqlite-vec` index builder). The existing **async SQLAlchemy/aiosqlite** path in `src/data/database.py` is a *separate* connection mechanism and stays **unchanged** in this story — do **not** rewrite `create_engine`/`async_sessionmaker` to use the factory. There are currently **zero** direct `sqlite3.connect` calls in `src/` (verified), so AC1 is a forward-looking convention + the new factory, not a refactor of existing code.

**AC2 — A new connection loads the extension and enables WAL**
- **Given** a new connection produced by the factory
- **When** the factory creates it
- **Then** `enable_load_extension(True)` is set, `sqlite_vec.load(conn)` is applied, `enable_load_extension(False)` is restored, and `conn.execute("select vec_version()").fetchone()[0]` returns a value (e.g. `v0.1.9`)
- **And** WAL journal mode is enabled (`PRAGMA journal_mode=WAL` returns `wal` for a **file-backed** DB).

**AC3 — Connection per worker thread (no cross-thread sharing)**
- **Given** concurrent worker threads (FastMCP threadpools sync tools — NFR6)
- **When** tools run
- **Then** each thread receives its **own** connection object; a connection is never shared across threads (use a thread-local store; keep the stdlib default `check_same_thread=True`).

**AC4 — Documented `apsw` substitution seam, defaulting to stdlib `sqlite3`**
- **Given** a future environment whose driver lacks `enable_load_extension`
- **When** the factory is configured
- **Then** an `apsw` substitution seam **exists and is documented** (a clean extension point — e.g. an abstract/Protocol interface or a `driver` selector that raises a clear `NotImplementedError` with guidance)
- **And** it **defaults to stdlib `sqlite3`** (apsw is **not implemented** in Phase 1 — contingency only).

**AC5 — Unit-tested probe**
- **Given** the factory
- **When** unit-tested
- **Then** a probe asserts: (a) the extension loads (`vec_version()` truthy), (b) WAL is active on a file-backed DB, (c) a **relational** query round-trips (CREATE/INSERT/SELECT), and (d) two threads receive distinct connection objects.

## Tasks / Subtasks

- [x] **Task 1 — Create `ConnectionFactory` in `src/search/connection.py`** (AC: 1, 2, 4)
  - [x] Add module docstring (one-line purpose) — required by project convention.
  - [x] Implement the connection-build sequence in this exact order: `conn = sqlite3.connect(db_path)` → `conn.enable_load_extension(True)` → `sqlite_vec.load(conn)` → `conn.enable_load_extension(False)` → `conn.execute("PRAGMA journal_mode=WAL")`. (Disabling extension loading after `sqlite_vec.load` is a deliberate hardening step — see Dev Notes.)
  - [x] Resolve the DB **file path** (not the SQLAlchemy URL): accept an explicit `db_path: str | None`, else derive from `CARDS_DATABASE_URL` by stripping the `sqlite+aiosqlite:///` prefix, else default `./data/cards.db`. (See Dev Notes → "DB path resolution".)
  - [x] Provide the **apsw seam**: a minimal, documented extension point that defaults to `sqlite3`. Keep it lean — do **not** build the apsw adapter (AC4 is "exists + documented", not "implemented").
  - [x] Full type hints (`mypy --strict`); Google-style docstring on the public class/methods; guard clauses over deep nesting.
- [x] **Task 2 — Per-thread connection management** (AC: 3)
  - [x] Hand each worker thread its own connection via a `threading.local()` store (lazily create on first `get_connection()` per thread); keep stdlib default `check_same_thread=True`. Do **not** pass `check_same_thread=False` (see Anti-Patterns).
  - [x] Provide a clear public entry point (e.g. `get_connection()` returning the thread-local connection) and a `close()`/teardown path usable by tests.
- [x] **Task 3 — Unit test the factory** (AC: 5)
  - [x] Create `tests/unit/search/__init__.py` and `tests/unit/search/test_connection.py` (mirror `src/` layout under `tests/unit/`).
  - [x] Sync `def test_...` functions (the factory is sync; **no** `async`/`@pytest.mark.asyncio`). Use pytest's `tmp_path` for the file-backed DB needed to assert WAL.
  - [x] Assert: `vec_version()` truthy; `PRAGMA journal_mode` == `wal` (file DB); a relational CREATE/INSERT/SELECT round-trips through a factory connection; two `threading.Thread`s receive distinct connection objects.
- [x] **Task 4 — Export & guard the convention** (AC: 1)
  - [x] Re-export `ConnectionFactory` from `src/search/__init__.py` (replace the placeholder docstring's "implementation lands in Epic 2" only as far as this port — keep the package docstring accurate) so consumers import `from src.search import ConnectionFactory`.
  - [x] Confirm by grep that no `src/` module calls `sqlite3.connect` directly except inside `connection.py`.
- [x] **Task 5 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/unit/search/ -v` → new probe tests pass.
  - [x] `uv run pytest tests/` → full active suite still green (no regressions; 300+ passing).
  - [x] `uv run ruff check .` and `uv run ruff format --check .` → clean.
  - [x] `uv run mypy src/` → clean (see Dev Notes if `sqlite_vec` types trip mypy).

### Review Findings

- [x] [Review][Decision] AC2 runtime probe — dismissed; test assertion (AC5a) is sufficient; `_build_connection` need not call vec_version() on every connection.
- [x] [Review][Patch] Connection leak if sqlite_vec.load raises — no try/finally in `_build_connection` [`src/search/connection.py:128-132`]
- [x] [Review][Patch] `close()` stale reference if conn.close() raises — self._local.conn not cleared on exception [`src/search/connection.py:142-145`]
- [x] [Review][Patch] WAL pragma result silently discarded — cursor from PRAGMA journal_mode=WAL never fetched; silent failure undetected [`src/search/connection.py:132`]
- [x] [Review][Patch] Test uses Unix /tmp/ path in Windows project — test_resolve_db_path_explicit_wins uses "/tmp/explicit.db" [`tests/unit/search/test_connection.py:101`]
- [x] [Review][Patch] self._driver is dead state — always "sqlite3" after the guard clause; never read again [`src/search/connection.py:93`]
- [x] [Review][Patch] No test for sqlite_vec.load failure path — _build_connection error handling has zero test coverage; most critical failure mode on Windows
- [x] [Review][Defer] Empty string CARDS_DATABASE_URL not guarded [`src/search/connection.py:38-45`] — deferred, operator config error; fails loudly with OperationalError

## Dev Notes

### What this story IS — and is NOT

- **IS:** a single, thin **infrastructure port** — `ConnectionFactory` — that yields a **sync** stdlib `sqlite3` connection with `sqlite-vec` loaded, WAL on, one-per-thread, plus its unit test and a documented apsw seam. This is research design-delta #1 [Source: [research §6 deltas](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); [epics.md "ConnectionFactory port"](../planning-artifacts/epics.md)].
- **IS NOT:** the `Embedder` (Story 2.1), the `card_vec` schema/virtual table (Story 2.2), the index builder (Story 2.3), any MCP tool or `.mcp.json` (Story 1.3), or any change to the async SQLAlchemy engine. **Do not** create `card_vec`, serialize vectors, or run a KNN query here — `vec_version()` is the *only* `sqlite-vec` call this story makes (proof-of-load). Resist scaffolding ahead; later stories own those.

### Why a *new* sync seam (the async-vs-sync split)

The existing core (`src/data`, `src/logic`) is **async everywhere** on SQLAlchemy + aiosqlite [Source: [project-context.md](../project-context.md) "Async everywhere"]. The MCP pivot makes **tools plain sync `def`** (FastMCP threadpools them) with a **per-thread `sqlite3` connection + WAL**, and the embedding model a process singleton [Source: [project-context.md](../project-context.md) "MCP server"; [research §Concurrency](../planning-artifacts/research/...)]. `sqlite-vec` is a C extension loaded **into a `sqlite3` connection** — it cannot ride the aiosqlite engine cleanly. So this story introduces the **sync** connection path that Stories 1.3–1.6 and Epic 2 build on. The two paths (async SQLAlchemy for legacy/data tests; sync factory for MCP tools + vectors) **coexist**; reconciling which tools use which is a Story 1.3 concern, explicitly **out of scope here**.

### File location decision (where `ConnectionFactory` lives)

**Decision: `src/search/connection.py`.** Rationale:
1. The research §6 design deltas and [project-context.md](../project-context.md) both group the `ConnectionFactory` under the **`src/search` RAG deltas** ("RAG / semantic search (Phase-1 target — `src/search`) … Carry the six de-risk deltas: (1) a `ConnectionFactory` port…").
2. Its reason to exist is loading the **`sqlite-vec`** extension — a search-stack concern.
3. `src/data` is **async-everywhere** by local convention; dropping a **sync** `sqlite3` factory there would muddy that boundary. `src/search` is the new, sync-oriented package and already exists as a scaffold.
- **Layering check:** import direction is `data → logic → (mcp_server) → ui` with `search` a sibling infra package that `mcp_server` consumes. `src/search/connection.py` is imported *downward* by `src/mcp_server` (Story 1.3) and by `scripts/` (Epic 2) — no upward import, no cycle. ✅
- **Alternative (if you/architect prefer):** `src/data/connection.py`. Functionally equivalent; rejected per points 1–3 above. *(Flagged as the one open question — see end of story.)*

### The canonical load sequence (copy this; it is verified on THIS machine)

The project's RAG de-risk spike ran exactly this on CPython 3.12.13 / SQLite 3.50.4 / Windows and got `enable_load_extension: True`, `vec_version: v0.1.9`, and a working hybrid KNN — **no fallback driver needed** [Source: [research §Empirical spike](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md)].

```python
import sqlite3
import sqlite_vec

conn = sqlite3.connect(db_path)          # default check_same_thread=True — keep it
conn.enable_load_extension(True)
sqlite_vec.load(conn)                     # bundled helper loads the vec0 extension
conn.enable_load_extension(False)         # re-disable: hardening (only sqlite-vec needs it)
conn.execute("PRAGMA journal_mode=WAL")   # persisted on the file; idempotent per-conn
# proof-of-load (AC2): conn.execute("select vec_version()").fetchone()[0]  -> "v0.1.9"
```

- **Extension load is per-connection** (not persisted to the file) → every connection the factory returns must run `enable_load_extension`+`sqlite_vec.load`.
- **WAL is per-file** (persisted once, reported per-connection) → setting it on each connection is harmless and idempotent.

### DB path resolution (sync factory needs a FILE PATH, not the SQLAlchemy URL)

There is **no central settings module** — `src/data/database.py` reads the env var directly: `DATABASE_URL = os.getenv("CARDS_DATABASE_URL", "sqlite+aiosqlite:///./data/cards.db")` [Source: [src/data/database.py:26](../../src/data/database.py#L26)]. The factory needs the **filesystem path** `./data/cards.db`, so:
- Accept an explicit `db_path` (tests pass `tmp_path / "x.db"`).
- Else read `CARDS_DATABASE_URL` and strip the `sqlite+aiosqlite:///` (and bare `sqlite:///`) prefix to recover the file path.
- Else default to `./data/cards.db` (matches the existing default; data files live in `./data/` — [project-context.md](../project-context.md)).
- Remember the env var is **`CARDS_DATABASE_URL`, not `DATABASE_URL`** (Chainlit hijacks `DATABASE_URL`) — do not rename. [Source: [project-context.md](../project-context.md) "DB URL env var"]

### apsw seam (AC4) — keep it minimal

AC4 needs the seam to *exist and be documented*, not to be built. Cleanest lean options:
- A small abstract interface (ABC or `typing.Protocol`) `ConnectionFactory` with one concrete `SQLiteConnectionFactory`, plus a docstring/comment marking where an `ApswConnectionFactory` would slot in; **or**
- A single class with a `driver: Literal["sqlite3", "apsw"] = "sqlite3"` param that raises `NotImplementedError("apsw seam is a documented Phase-1 contingency; default is stdlib sqlite3")` for `"apsw"`.

Either satisfies AC4. Do not add `apsw` to dependencies. Note from research: apsw is *not* a 100% DB-API drop-in for `sqlite3`, which is precisely why the seam is centralized here. [Source: [research §Technology Stack Component 2](../planning-artifacts/research/...)]

### Concurrency model (AC3, NFR6)

- FastMCP dispatches **sync `def` tools to a threadpool**; SQLite connections are **not freely thread-shareable**. The clean pattern is **WAL + one connection per worker thread** — the factory hands each thread its own connection via `threading.local()`. WAL gives concurrent readers during a write (ideal for a read-heavy card server; the only serve-time writers are deck CRUD — single-writer is fine). [Source: [research §Concurrency & Threading Model](../planning-artifacts/research/...); [project-context.md](../project-context.md) "MCP server"]
- **Do not** set `check_same_thread=False` to "share" a connection — that disables Python's guard and risks corruption. Thread-local connections keep the safe default. [Source: research §Concurrency]

### Testing standards (from project-context.md + repo conventions)

- pytest config is in `pyproject.toml`: `asyncio_mode = "auto"`, `--strict-markers`, `--tb=short`, verbose; `testpaths = ["tests"]`. Test layout **mirrors `src/`** → new tests go in **`tests/unit/search/`** (create `__init__.py`). [Source: [project-context.md](../project-context.md) "Testing Rules"; [pyproject.toml](../../pyproject.toml)]
- These are **unit** tests (fast, sync, `tmp_path` file DB) — **not** `integration`-marked (no network/API). Naming: `test_*.py`, `test_*` functions. `tests.*` is exempt from `mypy --strict` but still ruff-clean. Follow the existing sync style in [tests/unit/data/test_database.py](../../tests/unit/data/test_database.py).
- **WAL caveat for tests:** an in-memory (`:memory:`) DB ignores WAL (reports `memory`). Assert WAL only against a **file-backed** DB (`tmp_path`). Extension-load + relational-query assertions can use either, but prefer `tmp_path` for realism.

### mypy / pre-commit notes

- `mypy --strict` runs over `^src/` via pre-commit and `uv run mypy src/`. `[tool.mypy] ignore_missing_imports = true` is already set, so the **stub-less `sqlite_vec`** import won't error. `sqlite3` is stdlib (typed). You likely need **no** change to `.pre-commit-config.yaml` mypy `additional_dependencies` — but if a strict run complains about `sqlite_vec` symbols, add `sqlite-vec` there (Story 1.1 established this rule: "if you add a runtime dep that mypy needs to resolve types, also add it to `.pre-commit-config.yaml`'s mypy `additional_dependencies`"). [Source: [project-context.md](../project-context.md) "Code Quality"; [Story 1.1 Task 4](./1-1-repository-restructure-dependency-reshape.md)]
- Don't bypass hooks; fix issues. Conventional Commits on branch `feat/mcp-server-architecture`. Suggested commit: `feat: add sqlite ConnectionFactory (WAL + sqlite-vec load, per-thread)`.

### Anti-patterns (do NOT do these)

- ❌ Hardcode `sqlite3.connect` anywhere except inside `connection.py` (defeats AC1's whole purpose).
- ❌ `check_same_thread=False` + share one connection across threads (corruption). Use thread-local.
- ❌ Assert WAL on a `:memory:` DB (it reports `memory`, test will flake/fail).
- ❌ Make the factory `async` / `await` anything — this is the **sync** path; the async SQLAlchemy engine is untouched.
- ❌ Rewrite `src/data/database.py` to route through the factory (out of scope; the aiosqlite engine is a different mechanism).
- ❌ Build `card_vec`, serialize vectors, run KNN, add `apsw`, or pin `FASTEMBED_CACHE_DIR` here (later stories).
- ❌ `print()` in library code — use module-level `logger = logging.getLogger(__name__)` with `%`-style lazy args. Module docstring required.

### Previous Story Intelligence (Story 1.1 — done)

- Story 1.1 archived `src/agent`+`src/ui` → `legacy/`, reshaped deps to a lean core, and **already added `sqlite-vec>=0.1.9`, `fastembed>=0.7.1`, `mcp>=1.27.0` to core `[project.dependencies]`** and scaffolded `src/search/__init__.py` + `src/mcp_server/__init__.py` (docstring-only). So `sqlite_vec` is **already installed** — just import it. [Source: [Story 1.1 File List](./1-1-repository-restructure-dependency-reshape.md); [pyproject.toml](../../pyproject.toml)]
- Core suite is green at **300 passed, 0 collection errors** on the lean install — keep it that way (NFR7). `legacy/` is excluded from the active suite.
- 1.1 fixed real pre-existing defects (`.gitignore` `data/`→`/data/` so `src/data` isn't ignored; recreated `pagination.py`; `CardModel.printed_name` default). Heads-up: the `/data/` gitignore rule means the **runtime `./data/cards.db` is correctly ignored** — your `tmp_path` test DBs are unaffected.
- Established pattern: thorough Dev Notes, run-and-capture verification, scope discipline ("resist scaffolding ahead").

### Git Intelligence

- HEAD `e73fa7b` "refactor: archive agent+ui to legacy, reshape deps for MCP pivot (Story 1.1)" is the baseline. Recent history is all planning/restructure; **this is the first feature code of the MCP pivot's data seam.** No prior `ConnectionFactory` exists — green field within `src/search`.
- Working tree has minor uncommitted edits to `1-1-*.md`, `sprint-status.yaml`, `test_format_filtering.py`, and an untracked `deferred-work.md` — unrelated to this story; leave them.

### Latest Tech / Versions (verified for THIS project)

| Item | Value | Source |
|---|---|---|
| `sqlite-vec` | **v0.1.9** (already in core deps; Windows wheel `sqlite_vec-0.1.9-...win_amd64.whl` present in `uv.lock`) | [pyproject.toml](../../pyproject.toml); [uv.lock] |
| Load helper | `sqlite_vec.load(conn)` after `enable_load_extension(True)` | [research §Component 1](../planning-artifacts/research/...) |
| Proof-of-load | `select vec_version()` → `v0.1.9` | research empirical spike (this machine) |
| Driver | **stdlib `sqlite3`** — `enable_load_extension` confirmed `True` on the target build; **no apsw needed** | research empirical spike |
| Python / SQLite | CPython 3.12.13 / SQLite 3.50.4 / Windows / uv 0.11.7 | [project-context.md](../project-context.md) "Verified platform envelope" |

### Project Structure Notes

Target additions (everything else unchanged):

```
src/
  search/
    __init__.py        # re-export ConnectionFactory
    connection.py      # NEW — ConnectionFactory (sync sqlite3 + sqlite_vec.load + WAL + per-thread; apsw seam)
tests/
  unit/
    search/
      __init__.py      # NEW
      test_connection.py  # NEW — probe: vec_version, WAL(file), relational round-trip, per-thread distinct
```

- **Alignment:** matches the spec §4 restructure (`src/search` = embedder wrapper + sqlite-vec integration) and the research roadmap step 2 ("Search core — ConnectionFactory …"). [Source: [design spec §4](../../docs/architecture.md); [research §8](../planning-artifacts/research/...)]
- **Variance to record:** the `ConnectionFactory` is placed in `src/search` (not `src/data`) deliberately — see "File location decision" above.

### References

- [epics.md — Epic 1 / Story 1.2](../planning-artifacts/epics.md) — user story, ACs, the "ConnectionFactory port" additional requirement (no hardcoded `sqlite3.connect`; WAL; apsw seam).
- [research — RAG de-risk](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md) — §Component 1/2 (load sequence, driver gate), §Integration E (driver seam), §Concurrency (WAL + per-thread), §Empirical spike (verified `vec_version v0.1.9`, `enable_load_extension: True`), §6 deltas (delta #1).
- [design spec §4 / §6](../../docs/architecture.md) — restructure (`src/search`), RAG storage in one SQLite file.
- [project-context.md](../project-context.md) — RAG/MCP rules, async-vs-sync boundary, `CARDS_DATABASE_URL`, testing layout, mypy/ruff gates, verified Windows envelope.
- [src/data/database.py](../../src/data/database.py) — existing async engine (the path this story does **not** touch) and the `CARDS_DATABASE_URL` default to mirror.
- [tests/unit/data/test_database.py](../../tests/unit/data/test_database.py) — sync test style to follow.
- [Story 1.1](./1-1-repository-restructure-dependency-reshape.md) — deps already include `sqlite-vec`; `src/search` scaffold; core suite baseline (300 passed).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context)

### Debug Log References

- **sqlite-vec load verified in env (pre-implementation):** `uv run python -c "import sqlite_vec; ..."` → `vec_version: v0.1.9`, `enable_load_extension` available — matches the RAG de-risk envelope, no apsw fallback needed.
- **AC1 baseline confirmed:** grep for `sqlite3.connect` across `src/` returned **zero** matches before implementation (the factory is a forward-looking convention, not a refactor). Post-implementation grep returns exactly one call — inside `connection.py:128`.
- **Test-cleanup bug found & fixed (not an implementation defect):** first run of `test_distinct_connection_per_thread` failed at teardown with `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread` — the **main** thread tried to `.close()` a connection created in a **worker** thread. This is the `check_same_thread=True` guard (AC3) working as intended; it actually *proves* connections are thread-bound. Fixed the test to close each worker connection from within its own thread and to compare only object identity (`is not`, no SQLite call) across threads.
- **Pre-existing flaky test (out of scope, recorded):** `tests/integration/data/test_deck_repository.py::test_list_decks` fails intermittently in the full-suite run (passes 5/5 in isolation). Root cause: `DeckRepository.list_decks` orders by `created_at.desc()` with no tie-breaker; three decks created in the same instant tie and order arbitrarily. Unrelated to this story's `src/search` additions. Logged in [deferred-work.md](./deferred-work.md).

### Completion Notes List

- Implemented `ConnectionFactory` (sync stdlib `sqlite3`) in `src/search/connection.py` as the **single seam** for synchronous SQLite access (AC1). The async SQLAlchemy/aiosqlite engine in `src/data` is deliberately left untouched (separate mechanism).
- Each new connection runs the verified load sequence (AC2): `connect` → `enable_load_extension(True)` → `sqlite_vec.load` → `enable_load_extension(False)` (hardening) → `PRAGMA journal_mode=WAL`. `vec_version()` is the only `sqlite-vec` call made (proof-of-load) — no `card_vec`, no KNN (those are Epic 2).
- Per-thread connections via `threading.local()`, lazily created on first `get_connection()`, with the stdlib default `check_same_thread=True` kept (AC3). Added a `close()` teardown path for tests/worker shutdown.
- Documented **apsw substitution seam** via a `driver: Literal["sqlite3", "apsw"]` param defaulting to `"sqlite3"`; selecting `"apsw"` raises `NotImplementedError` with guidance (AC4). apsw is **not** added to dependencies (contingency only).
- DB **file path** resolution (not the SQLAlchemy URL): explicit `db_path` → strip `sqlite+aiosqlite:///`/`sqlite:///` prefix off `CARDS_DATABASE_URL` → default `./data/cards.db`.
- Re-exported `ConnectionFactory` from `src/search/__init__.py` so consumers use `from src.search import ConnectionFactory` (AC1 convention seam).
- **11 unit tests** in `tests/unit/search/test_connection.py` cover AC5 (vec_version truthy, WAL on file DB, relational round-trip, distinct per-thread connections) plus the apsw seam, default driver, and the four path-resolution branches.
- **Verification:** new tests 11/11 pass; full suite 310 passed (1 pre-existing flaky `test_list_decks`, unrelated — see Debug Log); `mypy src/` clean (29 files); `ruff check`/`ruff format --check` clean for all new files. (Pre-existing `_bmad/scripts/` ruff issues are framework files, outside `src/` and this story's scope.)

### File List

- `src/search/connection.py` — NEW: `ConnectionFactory` (sync `sqlite3` + `sqlite_vec.load` + WAL + per-thread; apsw seam; path resolution).
- `src/search/__init__.py` — MODIFIED: re-export `ConnectionFactory` (`__all__`), updated package docstring.
- `tests/unit/search/__init__.py` — NEW: package marker for the mirrored test layout.
- `tests/unit/search/test_connection.py` — NEW: 11 probe/unit tests (AC5 + AC4 + path resolution).
- `_bmad-output/implementation-artifacts/deferred-work.md` — MODIFIED: recorded the pre-existing `test_list_decks` flaky-ordering item.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIED: story status `ready-for-dev` → `in-progress` → `review`.

## Change Log

| Date | Change |
|---|---|
| 2026-06-20 | Implemented Story 1.2 — `ConnectionFactory` (sync `sqlite3` + `sqlite-vec` load + WAL + per-thread, documented apsw seam) in `src/search`, with 11 unit tests. All 5 ACs satisfied; status set to `review`. |

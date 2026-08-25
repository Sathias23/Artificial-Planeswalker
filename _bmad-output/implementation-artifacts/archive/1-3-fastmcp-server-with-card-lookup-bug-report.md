---
baseline_commit: 02d8d40
---

# Story 1.3: FastMCP Server with Card Lookup & Bug Report

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player using Claude Code,
I want a running MCP server that exposes card lookup and bug reporting,
so that I can fetch a card by name conversationally and report issues — all served by a stateless FastMCP server over stdio.

## Decisions Locked (resolved with Brad, 2026-06-20)

> Two design forks were resolved before this story was finalized. They shape the ACs/Tasks below — **do not re-litigate**:
> - **D-1.3a — Repo-backed tools are `async def`.** Epic-1 tools `await` the existing async `src/data` repositories **directly** on the FastMCP event loop. The locked NFR6 "sync `def`" rule is **relaxed for repo-backed tools** and **reserved for Epic 2's `sqlite-vec`/embedder tools** (which use the sync `ConnectionFactory`). No background-loop bridge is built.
> - **D-1.3b — Bug reports persist to SQLite.** `report_bug` writes to a new `bug_reports` **table** in the same SQLite file (via a new async repository), **not** the legacy `data/bug_reports.jsonl`. This adds a small, additive data-layer slice (model + schema + repository + metadata registration + migration).

## Acceptance Criteria

> Source: [epics.md#Story-1.3](../planning-artifacts/epics.md) (BDD as authored), with the locked decisions above and implementation-critical clarifications folded in. **All seven must hold simultaneously.** This story **stands up the server skeleton + the async-tool data-access pattern** that Stories 1.4–1.6 reuse, so the foundational seams (server builder, transport entry point, injected session factory) are as load-bearing as the two tools.

**AC1 — A FastMCP server runs over stdio and is registered for Claude Code**
- **Given** the project
- **When** the server starts (`python -m src.mcp_server`)
- **Then** a **FastMCP** server (`mcp.server.fastmcp.FastMCP`) runs over **stdio**
- **And** a project `.mcp.json` at repo root registers it so Claude Code can consume it (FR1, FR2).

**AC2 — Transport is selected at the entry point (pluggable)**
- **Given** the transport
- **When** configured
- **Then** the transport string is chosen **only at the entry point** (`src/mcp_server/__main__.py`), defaulting to `stdio`, so HTTP/SSE can swap in later **without changing any tool definition** (FR2, D7). Tool functions contain **no** transport-specific code.

**AC3 — `lookup_card_by_name` returns structured card data via the existing repository**
- **Given** `lookup_card_by_name` with an exact or fuzzy name
- **When** invoked
- **Then** it returns **structured** card data (not legacy HTML-blob strings) by reusing the existing `src/data` `CardRepository` (`find_by_name_exact` → fall back to `find_by_name_partial`), awaited directly (D-1.3a) (FR4)
- **And** `format` and `games` are **tool parameters** (not server state); the legacy `auto_filter`/session-filter behavior is dropped (FR3, D5)
- **And** a no-match returns a **graceful structured message** with **no exception** surfaced to the client.

**AC4 — `report_bug` persists a report to SQLite and acknowledges it**
- **Given** `report_bug` with a description
- **When** invoked
- **Then** it inserts a row into the `bug_reports` table (via a new async `BugReportRepository`) with `id`, `description`, `status="open"`, UTC `created_at`/`updated_at`, and returns a confirmation string including the report id (FR12, D-1.3b)
- **And** on a DB error it returns a **graceful error message** rather than surfacing a raw exception to the client.

**AC5 — Repo-backed tools are `async def`, stateless per call**
- **Given** each tool in this story
- **When** defined
- **Then** it is an **`async def`** registered via `@mcp.tool()`, awaiting the async data layer, with **no per-call/per-session server state** (no `format_filter`/`games_filter`/`active_deck`/`session_id` retained between calls) (FR3, D5, D-1.3a).
- **And** the sync `def` + per-thread-WAL model (NFR6) is **not** used here — it remains reserved for Epic 2's `sqlite-vec` tools.

**AC6 — Existing core behavior unchanged; data-layer change is additive only**
- **Given** `src/data` and `src/logic`
- **When** this story lands
- **Then** existing card/deck/logic behavior is **unchanged** and the full active suite stays green (NFR7). The **only** data-layer change is the **additive** `bug_reports` model + schema + repository + its `Base.metadata` import registration + a migration script. **No** edits to existing models, `CardRepository`, `DeckRepository`, queries, or the async engine config.

**AC7 — In-memory MCP client harness drives the tools (no subprocess)**
- **Given** an in-process / in-memory MCP client harness against a **seeded test DB**
- **When** it drives the tools in-process
- **Then** `lookup_card_by_name` (exact hit, fuzzy/partial-ambiguous, and no-match) and `report_bug` (row inserted + confirmation) assertions pass **without spawning a subprocess** (spec §8).

## Tasks / Subtasks

- [x] **Task 1 — Bug-report data-layer slice** (AC: 4, 6) — *additive; mirror existing patterns exactly*
  - [x] `src/data/models/bug_report.py` — `BugReportModel(Base)`, `__tablename__ = "bug_reports"`. Mirror [DeckModel](../../src/data/models/deck.py) dataclass style (`MappedAsDataclass`): `id` PK `String` `default_factory=lambda: str(uuid4()), init=False`; `description: Mapped[str]` `Text, init=True`; `status: Mapped[str]` `String, default="open", index=True, init=True`; optional `context: Mapped[str | None]` `Text, default=None, init=True`; `created_at`/`updated_at` `DateTime` `default_factory=lambda: datetime.now(UTC), init=False` (`updated_at` adds `onupdate=lambda: datetime.now(UTC)`). Module docstring + full types.
  - [x] `src/data/schemas/bug_report.py` — `BugReport(BaseModel)` with `model_config = ConfigDict(from_attributes=True)` and a `BugReportStatus(str, Enum)` (`open/investigating/resolved/closed/archived`) reused from the legacy values. Fields: `id, description, status, created_at, updated_at, context`.
  - [x] `src/data/repositories/bug_report.py` — `BugReportRepository(BaseRepository)` with `async def create(self, description: str, context: str | None = None) -> BugReport`. Follow [DeckRepository.create_deck](../../src/data/repositories/deck.py#L53) transaction discipline: `session.add` → `commit` → `refresh` → `return BugReport.model_validate(model)`; on `IntegrityError`/`DatabaseError` → `await session.rollback()` then re-raise; module `logger`, `%`-style lazy log args.
  - [x] Register the model so `Base.metadata` knows it: add `from src.data.models.bug_report import BugReportModel  # noqa: F401` to [src/data/database.py](../../src/data/database.py#L18) alongside the other model imports. (This is the only edit to `database.py` — additive metadata registration, no behavior change.)
  - [x] `scripts/migrate_add_bug_reports.py` — idempotent: build the async engine from `CARDS_DATABASE_URL` and `await init_database(engine)` (create_all is idempotent — only the missing `bug_reports` table is created on the existing `./data/cards.db`). Runnable via `uv run python scripts/migrate_add_bug_reports.py`.
- [x] **Task 2 — `lookup_card_by_name` tool** (AC: 3, 5)
  - [x] `src/mcp_server/tools/__init__.py` + `src/mcp_server/tools/card_lookup.py`.
  - [x] **`async def`** `lookup_card_by_name(card_name, format=None, games=None)` taking a `session_factory` (provided by the server builder — see Task 4). `async with session_factory() as session:` → `CardRepository(session)` → port the legacy **logic** (exact → partial fallback, disambiguation buckets 0/1/2-5/6+) — **dropping** all Chainlit/`ui_elements`/HTML formatting, `RunContext`/`AgentDependencies`, and `auto_filter`/session state. *(Logic implemented as the `async def lookup_card(session, ...)` helper; the `@mcp.tool()` wrapper closing over `session_factory` is registered in Task 4.)*
  - [x] Return a **structured** Pydantic result `CardLookupResult{status, card, matches, message}` (`status` ∈ `found|not_found|ambiguous`); reuse the `Card` schema for card data. No-match → `status="not_found"` + friendly `message` (no exception). Google-style docstring (= the LLM-facing tool description).
- [x] **Task 3 — `report_bug` tool** (AC: 4, 5)
  - [x] `src/mcp_server/tools/bug_report.py` — **`async def`** `report_bug(description=...)` using `BugReportRepository` via the injected `session_factory`. Returns a structured confirmation (e.g. `BugReportResult{id, message}`). On DB error, return a graceful message (don't raise to the client). **Do not import `legacy.*`.** *(Implemented as the `async def file_bug_report(session, description)` helper; the `@mcp.tool()` wrapper closing over `session_factory` is registered in Task 4.)*
- [x] **Task 4 — Server builder + tool registration** (AC: 1, 2, 5, 6)
  - [x] `src/mcp_server/server.py` — `build_server(session_factory: async_sessionmaker[AsyncSession] | None = None) -> FastMCP`. If `None`, build the default engine+factory via `src.data.database.create_engine()` / `create_session_factory()` (reuse — don't re-implement). Instantiate `FastMCP("artificial-planeswalker")`; register both tools with `@mcp.tool()`, each **closing over `session_factory`** (see Dev Notes → "Providing the session factory to tools"). Keep registration transport-agnostic.
  - [x] Update `src/mcp_server/__init__.py` to export `build_server` (replace the "lands in Story 1.3" placeholder docstring).
- [x] **Task 5 — Entry point + `.mcp.json`** (AC: 1, 2)
  - [x] `src/mcp_server/__main__.py` — `main()`: `build_server().run(transport=os.getenv("MCP_TRANSPORT", "stdio"))`. Transport chosen **only here**.
  - [x] `.mcp.json` at repo root: `{"mcpServers": {"artificial-planeswalker": {"command": "uv", "args": ["run", "python", "-m", "src.mcp_server"]}}}`. *(User-approved creation — harness flagged it as a self-modification.)*
- [x] **Task 6 — In-memory integration test harness** (AC: 7)
  - [x] `tests/integration/test_mcp_tools.py`. Use a **file-backed temp DB** (`tmp_path`), `await init_database(engine)` (creates `cards` **and** `bug_reports`), seed `CardModel`s (mirror [test_deck_repository.py:37-90](../../tests/integration/data/test_deck_repository.py#L37); include ≥2 cards sharing a substring like "bolt" to exercise the ambiguous bucket). Build `create_session_factory(engine)` and pass it into `build_server(session_factory=...)`.
  - [x] Drive tools via an **in-process MCP client** (`mcp.shared.memory.create_connected_server_and_client_session` — verified present in installed `mcp` 1.28). Assert: exact hit, partial/ambiguous, no-match graceful message; `report_bug` returns a confirmation **and** a row exists in `bug_reports` (query via the same factory).
  - [x] Reusable `seeded_card_db` fixture added to `tests/integration/conftest.py` for Stories 1.4–1.6.
- [x] **Task 7 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/integration/test_mcp_tools.py -v` → new harness passes (4 passed).
  - [x] `uv run pytest tests/` → **331 passed, 1 failed**; the single failure is the known-flaky `test_list_decks` family (`test_list_decks_with_strategy_field`) — `created_at` ordering tie, **passes in isolation** (45/45), confirmed not a regression (no `DeckRepository` change). See Previous Story Intelligence.
  - [x] `uv run ruff check .` / `uv run ruff format --check .` → all Story-1.3 files clean; the only remaining findings are pre-existing in `_bmad/scripts/tests/test_resolve_customization.py` (out of scope, not in this changeset).
  - [x] `uv run mypy src/` → clean (37 source files).
  - [x] Smoke-start: `uv run python -m src.mcp_server < /dev/null` launches over stdio and shuts down cleanly on EOF (exit 0), confirming AC1.

### Review Findings

- [x] [Review][Patch] Post-commit ValidationError returns id='' while row is persisted [src/data/repositories/bug_report.py:55]
- [x] [Review][Patch] Empty/whitespace card_name hits find_by_name_partial with ilike('%%') — matches all cards [src/mcp_server/tools/card_lookup.py:67-71]
- [x] [Review][Patch] "Showing the first N" message fires even when no truncation occurred (6–9 matches, all returned) [src/mcp_server/tools/card_lookup.py:87-93]
- [x] [Review][Patch] Test uses relative Path('.mcp.json') — FileNotFoundError when pytest is run outside project root [tests/integration/mcp_server/test_entry_point.py:45]
- [x] [Review][Defer] updated_at onupdate lambda does not fire via SQLAlchemy ORM unit-of-work [src/data/models/bug_report.py:43-47] — deferred, matches DeckModel pre-existing pattern; only matters when a future update story is added
- [x] [Review][Defer] No CHECK constraint on status column; unknown string persists silently and causes ValidationError on read-back [src/data/models/bug_report.py:32-34] — deferred, only triggered by manual DB manipulation; address when update is implemented
- [x] [Review][Defer] CardLookupResult.matches=[] on found status is ambiguous for callers (vs None) [src/mcp_server/tools/card_lookup.py] — deferred, design preference; no functional bug
- [x] [Review][Defer] LIKE wildcard injection in card_name / games params [src/data/repositories/card.py] — deferred, pre-existing in CardRepository; out of scope for Story 1.3
- [x] [Review][Defer] Non-DatabaseError exceptions in BugReportRepository.create skip explicit rollback [src/data/repositories/bug_report.py:50-69] — deferred, session context manager handles rollback on exit; low practical risk
- [x] [Review][Defer] migrate_add_bug_reports.py CWD-sensitive relative path — deferred, project convention (run from root) guards this; add doc comment
- [x] [Review][Defer] Transport cast(_Transport, ...) is a runtime no-op; no validation before FastMCP.run() [src/mcp_server/__main__.py:20] — deferred, FastMCP raises on invalid transport anyway

## Dev Notes

### What this story IS — and is NOT

- **IS:** the **first running MCP server** — a `FastMCP` instance over **stdio**, a transport-pluggable **entry point**, a project `.mcp.json`, the **`async def` repo-backed tool pattern** (server builder injects a session factory; tools `await` the async core), the two tools (`lookup_card_by_name`, `report_bug`), the additive **`bug_reports` data slice**, and an **in-memory** integration harness. Establishes the patterns all of Epic 1 reuses.
- **IS NOT:** `search_cards` (1.4), deck tools (1.5), analysis tools (1.6), or **anything RAG** — no `Embedder`, no `card_vec`, no semantic/similar tools, **no use of the sync `ConnectionFactory`** here (Epic 2). **Do not** scaffold ahead. No changes to existing `src/data`/`src/logic` behavior beyond the additive bug-report slice (AC6).

### Async-def tools + data access (D-1.3a — the core pattern for Epic 1)

The reusable core (`src/data`) is **async** SQLAlchemy + `aiosqlite` ([card.py:126](../../src/data/repositories/card.py#L126)). Per **D-1.3a**, Epic-1 repo-backed tools are **`async def`** and `await` the repos **directly** on FastMCP's event loop — no bridge, no `asyncio.run()`, no background thread. FastMCP awaits `async def` tools on its own loop; the async engine (created in `build_server`) binds to that loop on first tool use. `aiosqlite` is non-blocking I/O, so it won't stall the loop.

- The sync `def` + per-thread-WAL model (NFR6) and the Story-1.2 `ConnectionFactory` are **reserved for Epic 2's `sqlite-vec`/embedder tools** (CPU-bound embedding + raw-`sqlite3` vector queries). The two models **coexist** in one server: `async def` for async-repo tools, sync `def` for vector tools. FastMCP supports mixing (it inspects each function).

### Providing the session factory to tools

Tools need a `session_factory`. Use **closure-based registration** inside `build_server` so each server instance binds its own factory (clean + test-injectable):

```python
# src/mcp_server/server.py  (skeleton)
from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.data.database import create_engine, create_session_factory
from src.data.repositories.card import CardRepository
from src.data.repositories.bug_report import BugReportRepository

def build_server(session_factory: async_sessionmaker[AsyncSession] | None = None) -> FastMCP:
    if session_factory is None:
        session_factory = create_session_factory(create_engine())   # reuse data-layer config
    mcp = FastMCP("artificial-planeswalker")

    @mcp.tool()
    async def lookup_card_by_name(card_name: str, format: str | None = None,
                                  games: list[str] | None = None) -> CardLookupResult:
        """Look up an MTG card by exact-or-fuzzy name. ... (LLM-facing description)"""
        async with session_factory() as session:
            repo = CardRepository(session)
            card = await repo.find_by_name_exact(card_name, format_filter=format, games=games)
            if card:
                return CardLookupResult(status="found", card=card, matches=[], message=...)
            cards = await repo.find_by_name_partial(card_name, format_filter=format, games=games)
            ...  # 0 → not_found ; 1 → found ; 2+ → ambiguous (return matches)

    @mcp.tool()
    async def report_bug(description: str = "User reported an issue (no details provided)") -> BugReportResult:
        """File a bug report. ... (LLM-facing description)"""
        async with session_factory() as session:
            try:
                report = await BugReportRepository(session).create(description=description)
            except Exception:
                return BugReportResult(id="", message="Couldn't save the report; please try again.")
            return BugReportResult(id=report.id, message=f"Bug report {report.id} submitted. Thank you!")

    return mcp
```

- Keep the actual tool bodies thin; the matching/disambiguation logic for `lookup_card_by_name` can live in a helper in `tools/card_lookup.py` that takes a `session` (easier to unit-test), with the registered tool a thin wrapper. Either is fine — closure registration is the only hard requirement so tests can inject a factory.

### `lookup_card_by_name` — port the logic, drop the UI

Legacy ([legacy/agent/tools/card_lookup.py](../../legacy/agent/tools/card_lookup.py)) returns trusted-HTML blobs and appends Chainlit images. The MCP version **keeps the matching logic, discards presentation**:
- **Keep:** exact-first (`find_by_name_exact`) → fallback partial (`find_by_name_partial`) → buckets (0 / 1 / 2-5 / 6+).
- **Drop:** `format_card_with_image`/`format_card_details`/`format_card_list`, `ui_elements`, `RunContext`/`AgentDependencies`, `auto_filter` + session `format_filter`/`games_filter` (now explicit `format`/`games` params, default `None` = no filter — FR3/D5).
- **Structured, not strings** ([project-context.md](../project-context.md)). FastMCP serializes a typed/Pydantic return into `structuredContent` automatically. Define `CardLookupResult` so the client gets machine-readable fields + a human `message`.
- **`format` as a param name is intentional/allowed** — ruff `N` is on but the project keeps `format` for MTG-domain clarity. Don't rename.
- Repo methods already return Pydantic `Card` (never ORM) — [card.py:172](../../src/data/repositories/card.py#L172). `Card` fields: [src/data/schemas/card.py](../../src/data/schemas/card.py).

### `report_bug` → SQLite (D-1.3b)

- New table `bug_reports` in the **same** SQLite file. Mirror [DeckModel](../../src/data/models/deck.py)/[DeckRepository.create_deck](../../src/data/repositories/deck.py#L53) **exactly** for style (dataclass-mapped model, `default_factory` PK/timestamps; repo transaction discipline: commit+refresh, rollback-on-error, return schema).
- **Stateless** (FR3): no `session_id`/conversation history. `context` is an optional free-text/JSON column for any client-supplied detail — default `None`.
- Models are registered in [database.py](../../src/data/database.py#L18) for `Base.metadata` (the additive import). `init_database`'s `create_all` then makes the table; tests get it automatically via the `init_database(engine)` call, and the existing prod `./data/cards.db` gets it via the one-time migration script.
- **Legacy JSONL is superseded** for new reports. [scripts/manage_bug_reports.py](../../scripts/manage_bug_reports.py) reads the old `data/bug_reports.jsonl` and imports `BugReportStatus` from `legacy.*`; it is **out of scope** here (a future story can repoint it at the table / migrate old JSONL). Don't touch it.

### FastMCP server, transport, structured output

- `from mcp.server.fastmcp import FastMCP`; register tools with `@mcp.tool()` — **`async def` tools are awaited on the server loop** (this is what D-1.3a relies on).
- **Transport at the entry point only** (AC2/D7): `server.run(transport="stdio")` in `__main__.py`, default from `MCP_TRANSPORT`. Tool defs stay transport-free.
- **Tool docstrings are the LLM-facing descriptions** — write crisp Google-style docstrings (purpose, args, returns).

### Testing — the `:memory:` multi-connection trap

- The existing tests use `:memory:` ([test_deck_repository.py:14](../../tests/integration/data/test_deck_repository.py#L14)) but share **one** session/connection. Here the **seeding** session and the **tool's** session are **separate** `async with session_factory()` blocks → with `:memory:` each connection gets its **own** empty DB. **Use a file-backed `tmp_path` DB**: `create_engine("sqlite+aiosqlite:///" + str(tmp_path / "test.db"))`, `await init_database(engine)`, seed cards, then `build_server(session_factory=create_session_factory(engine))`. All sessions hit the same file. (With `async def` tools everything runs on the one pytest event loop — no cross-loop concerns.)
- In-memory MCP client: prefer `mcp.shared.memory.create_connected_server_and_client_session` (no subprocess, AC7). **Verify the exact helper against installed `mcp` 1.27** (see Latest Tech) — the SDK client/test API has shifted across minor versions.
- pytest config ([pyproject.toml](../../pyproject.toml)): `asyncio_mode = "auto"` → write `async def test_...`, **no** `@pytest.mark.asyncio`. `tests.*` is exempt from `mypy --strict` but still ruff-clean. Layout mirrors `src/` → `tests/integration/test_mcp_tools.py`.

### Anti-patterns (do NOT do these)

- ❌ Build a sync→async bridge / background loop / `asyncio.run()` per call — D-1.3a makes tools `async def`; just `await` the repo.
- ❌ Use the sync `ConnectionFactory`/raw `sqlite3` for these tools (that's Epic 2's vector seam) or re-implement `CardRepository` SQL.
- ❌ Return HTML-blob strings or import `legacy.ui.formatters`/`legacy.agent.*` (MCP returns **structured** data; legacy pulls `pydantic_ai`, absent from the lean core).
- ❌ Reintroduce per-session server state — no `format_filter`/`games_filter`/`active_deck`/`session_id` between calls (FR3/D5).
- ❌ Edit existing models/queries or the async engine config. The bug-report slice is **additive only**; the sole `database.py` change is the model import (AC6).
- ❌ Write bug reports to JSONL (superseded by D-1.3b) or import `BugReportStatus` from `legacy.*` (define it in `src/data/schemas/bug_report.py`).
- ❌ Assert against a `:memory:` DB across separate sessions (different connection → different DB). Use a `tmp_path` file.
- ❌ Surface raw exceptions to the MCP client — no-match and DB errors return graceful structured messages (AC3, AC4).
- ❌ `print()` in library code; naive `datetime`. Use module `logger` + `datetime.now(UTC)`.

### Previous Story Intelligence (Stories 1.1 & 1.2 — done)

- **1.1** archived `src/agent`+`src/ui` → `legacy/`, moved `pydantic-ai`/`chainlit` to the optional `legacy` group, added `mcp>=1.27.0`/`sqlite-vec`/`fastembed` to the lean core, scaffolded `src/mcp_server/__init__.py` (docstring-only — this story fills it). Baseline: **300 passed**; `legacy/` excluded.
- **1.2** built `ConnectionFactory` in [src/search/connection.py](../../src/search/connection.py) (sync `sqlite3` + `sqlite_vec.load` + WAL + per-thread). **That is the Epic-2 vector seam — not used by this story.** Suite at **310 passed**.
- **Known-flaky (out of scope):** `tests/integration/data/test_deck_repository.py::test_list_decks` ties on `created_at` ordering (no tie-breaker) — intermittent in full-suite runs, passes in isolation ([deferred-work.md](./deferred-work.md)). If it flakes during verify, it's **not** your regression.
- Team patterns to match: thorough Dev Notes, **run-and-capture** verification, strict scope discipline.

### Git Intelligence

- HEAD **`02d8d40`** "fix: harden ConnectionFactory error handling; close Stories 1.1 + 1.2" is the baseline. Branch `feat/mcp-server-architecture`; Conventional Commits. Suggested message: `feat: stand up FastMCP server (lookup_card_by_name + report_bug, bug_reports table) (Story 1.3)`. Working tree clean.

### Latest Tech / Versions (verify against the installed SDK)

| Item | Value | Source / Action |
|---|---|---|
| MCP SDK | `mcp>=1.27.0` (core dep) | [pyproject.toml:18](../../pyproject.toml#L18) |
| Server class | `from mcp.server.fastmcp import FastMCP`; `@mcp.tool()`; `mcp.run(transport="stdio")` | **Probe:** `uv run python -c "from mcp.server.fastmcp import FastMCP; print('ok')"` |
| Async tools | `async def` tools awaited on the server loop; typed/Pydantic returns → `structuredContent` | SDK docs/tests |
| In-memory client | `mcp.shared.memory.create_connected_server_and_client_session` (or `create_client_server_memory_streams` + `ClientSession`) | **Probe:** `uv run python -c "import mcp.shared.memory as m; print([x for x in dir(m) if 'create' in x])"` then use what's present |
| DB / platform | CPython 3.12.13 / SQLite 3.50.4 / Windows / uv | [project-context.md](../project-context.md) "Verified platform envelope" |

> The `mcp` SDK's high-level client/test surface changes across minor versions. Treat the two probes as **required first steps** (matches the run-and-capture norm) and bind to whatever symbols installed 1.27 exposes.

### Project Structure Notes

Target additions (everything else unchanged):

```
.mcp.json                       # NEW — registers the server for Claude Code
src/
  data/
    database.py                 # MODIFIED — additive: import BugReportModel for metadata
    models/bug_report.py        # NEW — BugReportModel
    schemas/bug_report.py       # NEW — BugReport + BugReportStatus
    repositories/bug_report.py  # NEW — BugReportRepository.create (async)
  mcp_server/
    __init__.py                 # MODIFIED — export build_server
    __main__.py                 # NEW — entry point; selects transport (stdio default)
    server.py                   # NEW — build_server(session_factory) -> FastMCP; registers async tools
    tools/__init__.py           # NEW
    tools/card_lookup.py        # NEW — lookup_card_by_name (async, structured)
    tools/bug_report.py         # NEW — report_bug (async, SQLite)
scripts/
  migrate_add_bug_reports.py    # NEW — idempotent create of bug_reports table
tests/
  integration/
    conftest.py                 # MODIFIED (optional) — reusable seeded_card_db fixture
    test_mcp_tools.py           # NEW — in-memory MCP client harness (AC7)
```

- **Alignment:** matches spec §4 (`src/mcp_server` = server + transport entry point) and §5 (tools import core repositories directly). Import direction stays `data → logic → mcp_server` (no upward imports). [Source: [design spec §4/§5](../../docs/architecture.md)]
- **Variances to record (Dev Agent Record):** (a) D-1.3a relaxes NFR6's "sync `def`" for repo-backed tools (async `def`; sync reserved for Epic 2). (b) D-1.3b adds a `bug_reports` table, superseding the legacy JSONL store.

### References

- [epics.md — Epic 1 / Story 1.3](../planning-artifacts/epics.md) — user story, ACs (FR1–FR4, FR12, FR3).
- [design spec §4 / §5 / §8](../../docs/architecture.md) — restructure, tool catalog + statelessness (D5), stdio/pluggable transport (D7), in-process MCP test approach.
- [project-context.md](../project-context.md) — MCP rules, structured returns, port tools 1:1, `CARDS_DATABASE_URL`, model/repo conventions, testing layout, ruff/mypy gates, `format`-as-param convention, schema-change/migration rule.
- [legacy/agent/tools/card_lookup.py](../../legacy/agent/tools/card_lookup.py) / [bug_report.py](../../legacy/agent/tools/bug_report.py) — source logic + status enum values to port (logic/values only; drop UI/session/JSONL).
- [src/data/repositories/card.py](../../src/data/repositories/card.py) — `find_by_name_exact`/`find_by_name_partial` (async, return `Card`). [schemas/card.py](../../src/data/schemas/card.py) — `Card` fields.
- [src/data/models/deck.py](../../src/data/models/deck.py) / [repositories/deck.py](../../src/data/repositories/deck.py#L53) / [models/base.py](../../src/data/models/base.py) — exact ORM (`MappedAsDataclass`) + repo transaction patterns to mirror for `bug_reports`.
- [src/data/database.py](../../src/data/database.py) — `create_engine`/`create_session_factory`/`init_database` to reuse; the additive model-import site.
- [tests/integration/data/test_deck_repository.py](../../tests/integration/data/test_deck_repository.py) — engine/session/`test_cards` fixture pattern to mirror (use a **file** DB, not `:memory:`).
- [Story 1.1](./1-1-repository-restructure-dependency-reshape.md) / [Story 1.2](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md) — deps, scaffold, baselines; `ConnectionFactory` is the Epic-2 seam (not used here).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Claude Code, BMad dev-story workflow)

### Debug Log References

- **SDK probes (run-and-capture, as required by Dev Notes → Latest Tech):** installed `mcp 1.28.0`; `from mcp.server.fastmcp import FastMCP` imports OK; `mcp.shared.memory` exposes `create_connected_server_and_client_session` (accepts a `FastMCP` directly, extracts `_mcp_server` internally) and `create_client_server_memory_streams`; `FastMCP.run(transport: Literal['stdio','sse','streamable-http'] = 'stdio', ...)`.
- **Timestamp round-trip:** SQLite `DateTime` columns store tz-naive, so `BugReport.created_at`/`updated_at` come back naive after `commit`+`refresh` even though created via `datetime.now(UTC)` — identical to `DeckModel`. Test assertion relaxed accordingly (the model still mirrors `DeckModel` exactly).
- **Migration robustness:** `init_database` against `./data/cards.db` fails with "unable to open database file" on a fresh checkout where `./data/` is absent; added a parent-dir guard (`make_url` + `mkdir(parents=True, exist_ok=True)`) so the script is genuinely runnable. Verified idempotent (ran twice, tables `bug_reports, cards, deck_cards, decks`).
- **`structuredContent` shape:** FastMCP serializes a Pydantic tool return into `CallToolResult.structuredContent` as the model dict directly (e.g. `{"status","card","matches","message"}`), with `isError=False` for graceful not_found/DB-error paths.

### Completion Notes List

- **All 7 ACs satisfied.** First running FastMCP server over stdio (`python -m src.mcp_server`), repo-root `.mcp.json`, transport selected only at the entry point, two `async def` repo-backed tools (`lookup_card_by_name`, `report_bug`), additive `bug_reports` data slice, and an in-memory MCP-client harness (no subprocess).
- **D-1.3a honored:** tools are `async def` and `await` the async `src/data` repos directly on the FastMCP loop — no sync→async bridge, no `asyncio.run()`, no use of the Story-1.2 sync `ConnectionFactory` (reserved for Epic 2). Tool *logic* lives in thin testable helpers (`lookup_card(session, ...)`, `file_bug_report(session, ...)`); `build_server` registers `@mcp.tool()` wrappers that close over an injected `session_factory`.
- **D-1.3b honored:** `report_bug` persists to a new `bug_reports` SQLite table via a new async `BugReportRepository` (commit+refresh, rollback-on-error, returns Pydantic schema) — not the legacy JSONL store. `BugReportStatus` is defined in `src/data/schemas/bug_report.py` (values ported from legacy), not imported from `legacy.*`.
- **AC6 additive-only:** the sole edit to existing `src/data` is the additive `BugReportModel` import in `database.py` for `Base.metadata`. No changes to existing models, `CardRepository`, `DeckRepository`, queries, or the async engine config.
- **Variances recorded (per Project Structure Notes):** (a) D-1.3a relaxes NFR6's "sync `def`" for repo-backed tools (async `def`; sync reserved for Epic 2's vector tools); (b) D-1.3b adds the `bug_reports` table, superseding the legacy JSONL store.
- **`.mcp.json`:** the harness flagged creating it as a self-modification (registers an MCP server into Claude Code's config); created after explicit user approval.
- **Verification:** new MCP harness 4/4 green; full suite **331 passed, 1 known-flaky** (`test_list_decks` family `created_at` tie — passes 45/45 in isolation, not a regression); `mypy src/` clean (37 files); ruff/format clean across all Story-1.3 files (only pre-existing `_bmad/scripts/tests/...` findings remain, out of scope); stdio smoke-start exits 0 on EOF.

### File List

**New — source:**
- `src/mcp_server/server.py` — `build_server(session_factory) -> FastMCP`; registers both async tools.
- `src/mcp_server/__main__.py` — entry point; selects transport (stdio default) via `MCP_TRANSPORT`.
- `src/mcp_server/tools/__init__.py`
- `src/mcp_server/tools/card_lookup.py` — `lookup_card` helper + `CardLookupResult`.
- `src/mcp_server/tools/bug_report.py` — `file_bug_report` helper + `BugReportResult`.
- `src/data/models/bug_report.py` — `BugReportModel`.
- `src/data/schemas/bug_report.py` — `BugReport` + `BugReportStatus`.
- `src/data/repositories/bug_report.py` — `BugReportRepository.create` (async).
- `scripts/migrate_add_bug_reports.py` — idempotent `bug_reports` table migration.

**New — config / tests:**
- `.mcp.json` — registers the server for Claude Code (repo root).
- `tests/integration/test_mcp_tools.py` — in-memory MCP-client harness (AC7).
- `tests/integration/mcp_server/__init__.py`
- `tests/integration/mcp_server/test_card_lookup_tool.py`
- `tests/integration/mcp_server/test_bug_report_tool.py`
- `tests/integration/mcp_server/test_server_builder.py`
- `tests/integration/mcp_server/test_entry_point.py`
- `tests/integration/data/test_bug_report_repository.py`

**Modified:**
- `src/data/database.py` — additive: import `BugReportModel` for `Base.metadata` (sole `src/data` change).
- `src/mcp_server/__init__.py` — export `build_server`.
- `tests/integration/conftest.py` — added reusable `seeded_card_db` fixture (file-backed DB) for Stories 1.3–1.6.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status tracking (workflow artifact).

## Change Log

| Date | Change |
|---|---|
| 2026-06-20 | Story 1.3 implemented: stood up the FastMCP server (stdio + pluggable transport entry point, `.mcp.json`), the `async def` repo-backed tool pattern (`build_server` injects a session factory), the `lookup_card_by_name` and `report_bug` tools, the additive `bug_reports` data slice (model + schema + repository + metadata registration + idempotent migration), and an in-memory MCP-client integration harness. Status → review. |

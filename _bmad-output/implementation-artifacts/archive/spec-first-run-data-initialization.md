---
title: 'First-Run Data Initialization (in-client init tools + graceful not-initialized statuses)'
type: 'feature'
created: '2026-06-28'
status: 'done'
baseline_commit: 'd5e671a0bfaf0fddb242bc69384a88102927ec56'
context:
  - '{project-root}/_bmad-output/project-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A fresh MCPB / Claude Desktop install ships no card data by design (license). The server starts, but every relational tool then fails against the empty DB with an opaque "A database error occurred" (`no such table: cards`), and the semantic tools point users at terminal scripts a GUI client can't run. No in-client build path, no guidance — the gap tracked in `deferred-work.md` ("MCPB bundle has no first-run data bootstrap or guidance").

**Approach:** Ship build-on-first-run as two explicit, consent-gated MCP tools — `initialize_database` (imports Scryfall cards) and `build_search_index` (builds the embedding index) — and replace the opaque DB error across all existing tools with a graceful `database_not_initialized` status that tells the assistant to run `initialize_database`. Semantic tools get both states: `database_not_initialized` when cards are gone, and an updated "index not built" status pointing at `build_search_index`.

## Boundaries & Constraints

**Always:**
- Wrap the EXISTING import/build code — never reimplement: `import_scryfall_bulk_data(session, bulk_type="oracle_cards", …)` for cards, `build_card_embeddings(conn, embedder, …)` for the index.
- Detection (`is_database_initialized`) must return `False` — never throw — for a missing DB file, missing `cards` table, OR empty `cards` table.
- All not-initialized responses are graceful (`isError=False`) and their copy names the in-client TOOL (`initialize_database` / `build_search_index`), not a terminal command.
- `initialize_database` is idempotent (skip import if cards already populated → `already_initialized`); `build_search_index` stays hash-incremental.
- Match existing result-model + `status` Literal conventions; `mypy --strict` + `ruff` clean.

**Ask First:**
- If a multi-minute blocking tool call exceeds the MCP client's request timeout during live smoke (the import is ~2–3 min; a full index build ~5 min): HALT and decide whether background-execution/progress is pulled into scope (it is currently a Design-Note risk, not a deliverable).

**Never:**
- Never ship a prebuilt DB or bundle card data (Scryfall/WotC license).
- Never silently auto-build on server startup or inside an unrelated tool call — initialization is explicit, tool-triggered, consent-gated only.
- Never hit the Scryfall network or download the real embedding model in unit/CI tests — use injected seams/fakes; mark any real-network test `integration`.
- Don't reintroduce per-session server state; don't expose a stale-data "refresh/force re-import" path (out of scope — first-run only).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Any relational tool, uninitialized DB | `cards` missing/empty | result model `status="database_not_initialized"`, message → run `initialize_database`, `isError=False` | guard before repo call; no `OperationalError` leaks |
| `initialize_database`, fresh DB | no cards | creates schema + imports `oracle_cards`; `status="ok"` + counts + hint to build the index | network/import failure → `status="error"`, message |
| `initialize_database`, already populated | cards present | `status="already_initialized"` + card count; no re-download | N/A |
| `build_search_index`, cards present no index | `cards` populated, `card_vec` empty/missing | builds index; `status="ok"` + build stats | embed/build failure → `status="error"`, message |
| `build_search_index`, no cards | `cards` missing/empty | `status="database_not_initialized"` → run `initialize_database` first | guard before build |
| Semantic tools, cards present no index | `card_vec` empty | `status="index_unavailable"`, message → run `build_search_index` | graceful, `isError=False` |

</frozen-after-approval>

## Code Map

- `src/data/importers/scryfall.py::import_scryfall_bulk_data` -- async card import seam to wrap (reuse, don't touch)
- `src/search/index_builder.py::build_card_embeddings` -- sync index build seam to wrap
- `src/search/embedder.py::get_embedder`, `src/search/connection.py::ConnectionFactory` -- sync embedder singleton + sqlite-vec connection
- `src/data/database.py` -- add async `is_database_initialized(session)`; reuse `create_engine` / `init_database` / `create_session_factory`
- `src/search/query.py` -- add sync `is_database_initialized(conn)` alongside `index_is_populated`
- `src/mcp_server/server.py::build_server` -- register the two new tools; thread import-fn / embedder / connection seams
- `src/mcp_server/tools/{card_lookup,card_search,bug_report,deck_management,deck_analysis,semantic_search,find_similar}.py` -- add `database_not_initialized` guard + status literal
- `tests/integration/mcp_server/`, `tests/unit/{data,search}/` -- new + extended tests; `tests/fixtures/embedder.py::FakeEmbedder` for index test
- `README.md`, `deferred-work.md` -- accuracy fix + close coupled deferred items

## Tasks & Acceptance

**Execution:**
- [x] `src/data/database.py` -- add `async def is_database_initialized(session: AsyncSession) -> bool` (sqlite_master check for `cards` + `SELECT EXISTS(SELECT 1 FROM cards)`; never throws).
- [x] `src/search/query.py` -- add sync `def is_database_initialized(conn: sqlite3.Connection) -> bool`, mirroring `index_is_populated`.
- [x] `src/mcp_server/tools/messages.py` (NEW) -- `DATABASE_NOT_INITIALIZED_MESSAGE` + `INDEX_NOT_BUILT_MESSAGE` constants naming the in-client tools.
- [x] `src/mcp_server/tools/initialize_database.py` (NEW) -- `InitializeDatabaseResult` (`status: Literal["ok","already_initialized","error"]`) + async helper: guard already-initialized; else own engine → `init_database` → `import_scryfall_bulk_data(..., bulk_type="oracle_cards")` (importer passed as an injectable seam, default real) → dispose → `ok` with `ImportStatistics` summary + "now run build_search_index" hint; wrap failures as `error`.
- [x] `src/mcp_server/tools/build_search_index.py` (NEW) -- `BuildSearchIndexResult` (`status: Literal["ok","database_not_initialized","error"]`) + sync helper: guard `is_database_initialized(conn)`; else `get_embedder()` (or injected) + `build_card_embeddings(conn, embedder, limit=…, rebuild=…, prune=…)` → `ok` with `BuildStatistics`; wrap failures as `error`.
- [x] `src/mcp_server/tools/{card_lookup,card_search,bug_report,deck_management,deck_analysis}.py` -- each helper: early-return its result model with `status="database_not_initialized"` + shared message when `not await is_database_initialized(session)`; add the literal to every affected result model.
- [x] `src/mcp_server/tools/semantic_search.py` + `find_similar.py` -- add `database_not_initialized` guard (before the index check) + status literal; repoint the existing `index_unavailable` copy to `INDEX_NOT_BUILT_MESSAGE`.
- [x] `src/mcp_server/server.py` -- register `initialize_database` (async `@mcp.tool()`) and `build_search_index` (sync `@mcp.tool()`); reuse the injected `connection_factory`/`embedder` seams and a new optional import-fn seam; update module docstring.
- [ ] Tests -- unit: both `is_database_initialized` variants (missing/empty/populated). Integration: representative relational tool + each semantic tool return `database_not_initialized` on an empty DB; semantic returns `index_unavailable` when cards exist but index doesn't; `initialize_database` happy-path (fake importer inserts cards) + `already_initialized`; `build_search_index` happy-path (FakeEmbedder) + `database_not_initialized` with no cards.
- [x] `README.md` -- rewrite the first-run/Claude-Desktop section to describe the `initialize_database` → `build_search_index` flow; delete the false "setup.py builds the index" and "first launch prompts you" claims.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- mark the "MCPB bundle has no first-run data bootstrap" (High-for-UX) and the two README-overclaim items resolved, with a pointer to this spec.

**Acceptance Criteria:**
- Given a data dir with no `cards.db`, when any of the 14 existing tools is called, then it returns a graceful `database_not_initialized` (never `isError=True` / leaked `OperationalError`) naming `initialize_database`.
- Given `initialize_database` then `build_search_index` run on an empty data dir, when a card tool and `semantic_search_cards` are called afterward, then both return `status="ok"` (the end-to-end first-run loop works).
- Given the full suite, when `uv run pytest -m "not integration"`, `ruff`, and `mypy src/` run, then all pass and no test performs real network/model I/O.

## Spec Change Log

- **Dev deviation (2026-06-28): `report_bug` is intentionally NOT guarded.** AC1 said "any of the 14 existing tools"; the implementation guards 13. `report_bug` is excluded because (a) it is card-data-independent — it writes `bug_reports`, not `cards`, so a `database_not_initialized` ("set up the card DB") status is the wrong signal; (b) it is already graceful (a missing table is caught → friendly "could not be saved" message, no opaque error leak — the very thing this spec removes); and (c) it has no `status` field, so guarding would reshape its result model and block the legitimate "report that init failed" path. Net: the guard lands on the 13 card/deck tools where the opaque error actually occurred. Avoids the known-bad state of blocking pre-init bug reports.

## Design Notes

- **Two detection variants by layer:** the 12 async tools hold an `AsyncSession` (async helper in `src/data/database.py`); the 2 sync semantic tools + `build_search_index` hold a sqlite3 `conn` (sync helper in `src/search/query.py`). No shared call site exists, so guard each helper — a single choke point is impossible.
- **Semantic tools check both states, DB first:** `database_not_initialized` (cards gone) before `index_unavailable` (cards present, `card_vec` empty). Both graceful, both now point at tools not scripts.
- **`initialize_database` is self-contained** (own engine → `init_database` → import → `dispose`), mirroring `setup.py::initialize_database`; importer injectable for network-free tests; `oracle_cards` keeps it ~2–3 min.
- **Long-running risk:** blocking multi-minute calls. v1 ships blocking; progress/background execution is a mitigation gated behind live-smoke (Ask First), which is Brad's gate.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean
- `uv run mypy src/` -- expected: no errors
- `uv run pytest -m "not integration"` -- expected: all pass, zero real network/model I/O

**Manual checks:**
- Live smoke (Brad): point `PLANESWALKER_DATA_DIR` at an empty temp dir; in Claude Desktop call a card tool (expect `database_not_initialized`) → `initialize_database` → card tool works → `semantic_search_cards` (expect `index_unavailable`) → `build_search_index` → semantic search works. Confirm no client timeout aborts the long calls.

## Suggested Review Order

**The first-run tools (design intent)**

- Self-contained build-on-first-run: own engine, idempotent skip, partial-import rollback on failure.
  [`initialize_database.py:69`](../../src/mcp_server/tools/initialize_database.py#L69)

- Staged sibling: guards an un-imported DB, resolves the embedder before any destructive rebuild.
  [`build_search_index.py:48`](../../src/mcp_server/tools/build_search_index.py#L48)

- Both registered as explicit, consent-gated MCP tools (async + sync) — no startup auto-build.
  [`server.py:542`](../../src/mcp_server/server.py#L542)

**The detection guard (the foundation)**

- Async variant for the 12 relational tools — returns False (never raises) for missing/empty `cards`.
  [`database.py:115`](../../src/data/database.py#L115)

- Sync variant for the sqlite-vec tools, mirroring `index_is_populated`.
  [`query.py:219`](../../src/search/query.py#L219)

- Shared copy that names the in-client tool to run next, never a terminal command.
  [`messages.py:11`](../../src/mcp_server/tools/messages.py#L11)

**The guard rollout**

- Representative relational guard: early-return `database_not_initialized` before any repo call.
  [`card_lookup.py:73`](../../src/mcp_server/tools/card_lookup.py#L73)

- Semantic two-state contract: `database_not_initialized` checked before `index_unavailable`.
  [`semantic_search.py:203`](../../src/mcp_server/tools/semantic_search.py#L203)

**Tests & docs (supporting)**

- End-to-end offline loop: init → build → semantic `ok` (AC2).
  [`test_first_run_data_init.py:262`](../../tests/integration/mcp_server/test_first_run_data_init.py#L262)

- README first-run accuracy fix + closed deferred-work items.
  [`README.md`](../../README.md)

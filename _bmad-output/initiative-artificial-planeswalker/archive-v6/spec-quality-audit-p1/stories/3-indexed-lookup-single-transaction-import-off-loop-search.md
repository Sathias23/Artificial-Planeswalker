---
title: 'Indexed name lookup, single-transaction import, off-loop search tools'
type: 'refactor'
created: '2026-09-04'
status: 'done'
baseline_commit: 'edfaba13efaaa8fef6b455e3acec5ad9852b1196'
review_loop_iteration: 0
context: ['_bmad-output/specs/spec-quality-audit-p1/SPEC.md', '_bmad-output/specs/spec-quality-audit-p1/batches.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Batch 2 of SPEC-quality-audit-p1 (CAP-1, CAP-2, CAP-11). Exact card lookup runs `lower(name) LIKE` over 30k rows (70 ms, `SCAN cards`) and `import_decklist` repeats that scan plus an init check, a deck load, a commit and a reload per line (7–10 s per 100 lines). The three sync search tools run on the FastMCP event loop (mcp 1.28 calls sync tools inline, the `server.py` docstring's threadpool claim is false), so a five-minute `build_search_index` stalls every other call and the MCP ping. A companion push opens two `httpx.AsyncClient`s and makes two requests, and `import src.mcp_server.server` pulls in fastembed (~250 ms).

**Approach:** Add `COLLATE NOCASE` indexes on `cards.name` and `cards.printed_name`, query them with collated equality, and create them on existing databases from an engine-connect hook. Give `DeckRepository` a bulk add that commits once, and make the import resolve every line first, then write once. Turn the three sync tools into `async def` closures that run their helper (connection acquisition included) in `asyncio.to_thread`; offload the aggregate pass and the per-batch parse of the Scryfall import the same way. Share one lazily built `httpx.AsyncClient` in the companion client, drop the pre-push health probe, and map a refused connection to `app_not_running`. Import fastembed inside `Embedder.__init__`.

## Boundaries & Constraints

**Always:** Tool names, argument schemas, docstrings-as-descriptions, and every result `status` literal stay as they are. `find_by_name_exact` keeps its `format_filter`/`games` filters and its exact→partial bucketing in callers. Per-thread sqlite-vec connections (NFR6): `connection_factory.get_connection()` and `get_embedder()` are called inside the offloaded callable, never on the loop thread. `trust_env=False` on the shared client. `live_instance`/`probe_health` stay exported for `companion_status` and the app's singleton check. Import in-memory duplicate detection reproduces today's per-line `exists` result. Rebuild `plugin/` in the same PR. Run the full preflight gate in `batches.md` before the first push. Record EXPLAIN QUERY PLAN before/after and the 100-line import timing in the completion notes.

**Ask First:** Any change to a tool signature or to the `DeckImportResult`/`DeckImportLineResult` shape. Reintroducing any identity check before a push (the decision to drop it is recorded in Design Notes). Touching companion security invariants (loopback bind, Host/Origin, tickets, bearer compare, body cap).

**Never:** A migration script the operator must run. Sharing one sqlite-vec connection across threads. `except Exception` in the companion client. Pruning provenance comments beyond the sentences this story makes false (CAP-4 is story 5). Changing `search_cards`, FTS, or the partial-name path.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Exact lookup, mixed case | `find_by_name_exact("LIGHTNING bolt")` | the card; `EXPLAIN QUERY PLAN` shows `SEARCH cards USING INDEX ix_cards_name_nocase` | N/A |
| Wildcard chars in name | `find_by_name_exact("Light%")` | `None` (literal compare, no LIKE wildcards) | N/A |
| Existing DB lacks the index | file DB created with the old schema, new engine connects | both NOCASE indexes exist after the first connection | `OperationalError` (locked) is logged, connect succeeds, next connect retries |
| Fresh empty DB | no `cards` table at connect time | hook skips; `create_all` creates the indexes | N/A |
| 100 resolvable import lines | `import_decklist` on a seeded DB | `status="ok"`, one `commit()`, one deck reload, deck holds 100 rows | N/A |
| Same card twice in one board | lines `1 Bolt` and `2 Bolt` (mainboard) | first `ok`, second `exists`; one commit | N/A |
| One unresolvable line | 99 good, 1 unknown name | `status="partial"`, 99 rows committed, unknown line `card_not_found` | N/A |
| Commit fails | `DatabaseError` on the bulk write | `status="error"`, no rows added, session rolled back | rollback before return |
| Tool call during index build | `build_search_index` blocked on a stub embedder; concurrent `call_tool("list_decks")` | the concurrent call returns before the build is released | N/A |
| Push, app running | discovery record + stub answering 200 receipt | `displayed`; the stub saw exactly one request (POST, no GET) | N/A |
| Push, refused connection | discovery record pointing at a dead port | `app_not_running` | `ConnectError`/`ConnectTimeout` → `app_not_running` |
| Push, listener never answers | silent socket | `backend_error` (read timeout on the POST) | N/A |
| Push, 403 then 200 | token rotates mid-call | second POST succeeds; two POSTs, zero GETs | N/A |
| No discovery file | none on disk | `app_not_running`, zero requests | N/A |
| Server import | `python -c "import src.mcp_server.server"` | `fastembed` not in `sys.modules` | N/A |

</frozen-after-approval>

## Code Map

- `src/data/models/card.py:25-27` -- `name`/`printed_name` are `index=True` (binary collation). Add `__table_args__ = (Index("ix_cards_name_nocase", text("name COLLATE NOCASE")), Index("ix_cards_printed_name_nocase", text("printed_name COLLATE NOCASE")))`; pattern at `src/data/models/combo.py:101`.
- `src/data/database.py:32-58` -- `create_engine`; no connect listener exists. Add `@event.listens_for(engine.sync_engine, "connect")` that checks `sqlite_master` for `cards` and runs `CREATE INDEX IF NOT EXISTS` for both. `init_database:100` runs `create_all` (covers fresh DBs). `src/search/connection.py:136-140` shows the WAL pragma-on-connect style.
- `src/data/repositories/card.py:186-192` -- `find_by_name_exact` query: `or_(CardModel.name.ilike(name), CardModel.printed_name.ilike(name))` → `CardModel.name.collate("NOCASE") == name` (both columns; SQLite's OR optimisation needs an index per term). `:201` partial path untouched.
- `src/data/repositories/deck.py:294-365` -- `add_card_to_deck` commits then reloads per call. Add `add_cards_to_deck(deck_id, entries)` next to it: `add_all`, one commit, one `selectinload` reload of the new rows, rollback on `IntegrityError`/`DatabaseError`. Entry shape: a small pydantic input in `src/data/schemas/deck.py` (`card_id`, `quantity`, `sideboard`, `commander`). `DeckCardModel` PK is `(deck_id, card_id, sideboard)` (`deck_card.py:27-35`).
- `src/mcp_server/tools/deck_management.py:153-183` -- `_resolve_card` (reuse for per-line resolution); `:377-470` single-card tool, unchanged except it now hits the index.
- `src/mcp_server/tools/deck_import.py:330-460` -- the per-line `_add_card_to_deck` loop to replace: keep the parse/guard/deck-load prefix (`is_database_initialized` once, `get_deck` once), then resolve all, dedupe against `deck.deck_cards` + a seen set, one bulk write, then `_line_result`. Docstring `:333-341` says "successful lines remain committed when another line fails" — restate for one transaction.
- `src/mcp_server/server.py:8-10` -- the false threadpool sentence; inline copies at `:972`, `:1037`, `:1106`. `semantic_search_cards:931`, `find_similar_cards:989`, `build_search_index:1087` are the sync closures; `view_deck.py:97` is the existing `await asyncio.to_thread(...)` precedent. `FastMCP(name, lifespan=...)` accepts an async context manager (`mcp/server/fastmcp/server.py:123`) — use it to `aclose` the shared companion client.
- `src/data/importers/scryfall.py:427` -- `aggregates = build_oracle_aggregates(downloaded_file)` (sync CPU pass); `importer.py:76-130` `import_cards` consumes the parse generator inline — pull each batch with `await asyncio.to_thread(lambda: list(islice(it, batch_size)))`, keep counting/insert on the loop.
- `src/search/embedder.py:10,99` -- top-level `from fastembed import TextEmbedding`; move into `Embedder.__init__` (annotation via `TYPE_CHECKING`). Chain: `server.py:118` → `src/search/__init__.py:18` → embedder. `EMBEDDING_DIM`/`MODEL_NAME` stay module constants.
- `src/companion/client.py:236-300` `probe_health`, `:344-404` `_send`, `:451-473` `_attempt` (probe then POST), `:679-760` active-deck twins, `:580` `notify_deck_changed`. Each builds its own `httpx.AsyncClient`. Add `_shared_client()` (cached per running loop; `reset_shared_client()` for tests) and `aclose_shared_client()`. `_PUSH_TOTAL_SECONDS >= 2 * _PROBE_TOTAL_SECONDS` relation (`test_client.py:567`) loses its rationale.
- `src/mcp_server/tools/companion.py:40-44,812-815` -- aliases; `companion_status` keeps probing (tab count).
- Tests: `tests/unit/data/test_card_repository.py:141` case-insensitive lookup (in-memory, `create_all`); `tests/unit/data/test_database.py`; `tests/integration/data/test_deck_repository.py`; `tests/integration/mcp_server/test_deck_import_tool.py` (17 tests on `seeded_card_db`, `tests/integration/conftest.py:84`); `tests/integration/test_mcp_tools.py:1052` `_vec_server`, `ROUND_TRIPPED:1689`; `tests/unit/search/test_embedder.py`; `tests/unit/companion/test_client.py:1005-1070` `TestPushIdentityGate`, `:1099` probe-order test, `:546-583` `TestExportedSurface`, real-socket `stub_server:369` / `sockets:481`; `test_companion_degradation.py:58` `closed_companion` (no discovery file).
- Docs naming the probe: `docs/companion.md:12,158`, `docs/companion-app-feature-brief.md:126`, `README.md:225,260`.

## Tasks & Acceptance

**Execution:**
- [x] `src/data/models/card.py`, `src/data/database.py` -- NOCASE indexes in metadata + connect-time `CREATE INDEX IF NOT EXISTS` guarded on `cards` existing -- CAP-1, no manual migration
- [x] `src/data/repositories/card.py` -- collated equality in `find_by_name_exact` -- index search
- [x] `src/data/schemas/deck.py`, `src/data/repositories/deck.py` -- entry schema + `add_cards_to_deck` (one commit, one reload, rollback on error) -- single transaction
- [x] `src/mcp_server/tools/deck_import.py` -- resolve-all then bulk write; in-memory `exists`; `error` on commit failure; docstring -- CAP-1
- [x] `src/mcp_server/server.py` -- docstring/comment fix; three closures `async def` + `asyncio.to_thread`; `lifespan` closing the companion client -- CAP-2
- [x] `src/data/importers/scryfall.py`, `importer.py` -- aggregate pass and per-batch parse via `to_thread` -- CAP-2
- [x] `src/search/embedder.py` -- lazy fastembed import; fix the "import is free" docstring lines -- CAP-11
- [x] `src/companion/client.py` -- shared client, probe dropped from push/notify/active-deck, connect failure → `app_not_running`; docstrings that describe prove-then-send updated -- CAP-11
- [x] `docs/companion.md`, `docs/companion-app-feature-brief.md`, `README.md` -- probe sentences updated -- no drift
- [x] `tests/unit/data/test_card_repository.py`, `test_database.py`, `tests/integration/data/test_deck_repository.py`, `tests/integration/mcp_server/test_deck_import_tool.py`, `tests/integration/test_mcp_tools.py`, `tests/unit/search/test_embedder.py`, `tests/unit/companion/test_client.py` -- matrix rows; commit counted via a `session.commit` spy; concurrency test uses a `threading.Event` embedder stub -- proof
- [x] `CHANGELOG.md` `[Unreleased]` -- one line per CAP -- release notes
- [x] `uv run python -m scripts.build_plugin` -- commit `plugin/` -- CI drift check

**Acceptance Criteria:**
- Given the operator's `cards.db`, when `EXPLAIN QUERY PLAN` for the new exact-name query runs before and after, then before shows `SCAN cards` and after shows `SEARCH ... USING INDEX ix_cards_name_nocase`, both pasted in the completion notes.
- Given a 100-line Commander list against a copy of the operator's `cards.db`, when `import_decklist` runs, then it finishes in under 0.5 s, with the timing in the completion notes.
- Given `tests/integration/test_mcp_tools.py`, when compared with `ROUND_TRIPPED`, then all 25 tools still round-trip and the concurrency test passes.
- Given the preflight gate in `batches.md`, when run before the first push, then it is green and `git status --porcelain` is empty after `build_plugin`.

## Spec Change Log

## Design Notes

**Index and query.** SQLite uses an index only when the query's collation matches the index's; `name COLLATE NOCASE = ?` matches `ix_cards_name_nocase`, `lower(name) LIKE` matches nothing. The connect hook, not a script, is the migration path because the MCP server never calls `init_database` at startup. `CREATE INDEX IF NOT EXISTS` on a missing table raises, hence the `sqlite_master` guard.

**Dropping the probe (AD-4).** The probe proved the port's identity before the token moved. Its remaining protection is the case where the app died and a foreign loopback process took the port before the discovery file was removed; that process already runs as the same user, so the per-process push token is not worth a round trip per push. The discovery file stays the trust root: no file, or a corrupt one, is still `app_not_running` with zero network. `companion_status` keeps its two GETs on the shared client.

**to_thread shape.** Each closure becomes:
```python
@mcp.tool()
async def semantic_search_cards(...) -> SemanticSearchResult:
    def _run() -> SemanticSearchResult:
        conn = connection_factory.get_connection()
        emb = embedder if embedder is not None else get_embedder()
        return _semantic_search_helper(conn, emb, query, ...)
    return await asyncio.to_thread(_run)
```
The helper modules keep their sync signatures, so their direct-call tests stay untouched.

**Shared client.** Cache `(loop, client)`; a different or closed running loop builds a fresh client (pytest gives each async test its own loop). Per-request `timeout=` keeps the existing probe/push/notify deadlines.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy src/ --platform win32` -- expected: clean
- `uv run pytest -m "not integration" -q` -- expected: green
- `uv run python -c "import sys, src.mcp_server.server; assert 'fastembed' not in sys.modules"` -- expected: no output
- `cd ui && npm run lint && npm run format:check && npm run typecheck && npm test && npm run test:gates && npm run build && npm run gen:types && cd ..` -- expected: green (no ui change, so nothing moves)
- `uv run python -m scripts.build_plugin && git status --porcelain` -- expected: only the intended `plugin/` changes, then committed

## Completion Notes

Implemented 2026-09-04 on `chore/quality-audit-latency` (nothing committed or pushed by the implementer). All measurements ran against a **copy** of the operator's `cards.db` (with its `-wal`/`-shm` copied alongside) in the session scratchpad; the real file was never opened for writing.

### EXPLAIN QUERY PLAN — exact-name lookup (`find_by_name_exact("LIGHTNING bolt")`, SQL captured from the repository via `before_cursor_execute`)

**Before** (`lower(cards.name) LIKE lower(?) OR lower(cards.printed_name) LIKE lower(?)`):

```
(8, 0, 222, 'SCAN cards USING INDEX sqlite_autoindex_cards_1')
indexes on cards: ['sqlite_autoindex_cards_1', 'ix_cards_printed_name', 'ix_cards_name']
```

**After** (`(cards.name COLLATE "NOCASE") = ? OR (cards.printed_name COLLATE "NOCASE") = ?`):

```
(9, 0, 0, 'MULTI-INDEX OR')
(10, 9, 0, 'INDEX 1')
(18, 10, 61, 'SEARCH cards USING INDEX ix_cards_name_nocase (name=?)')
(23, 9, 0, 'INDEX 2')
(31, 23, 61, 'SEARCH cards USING INDEX ix_cards_printed_name_nocase (printed_name=?)')
(69, 0, 0, 'USE TEMP B-TREE FOR ORDER BY')
indexes on cards: ['sqlite_autoindex_cards_1', 'ix_cards_printed_name', 'ix_cards_name', 'ix_cards_name_nocase', 'ix_cards_printed_name_nocase']
```

The "after" run started from a pristine copy with no NOCASE indexes: the engine's `connect` hook created both on the first connection (that first connect cost **374 ms** once on the ~30k-row copy; 13 ms before the change, and ordinary again afterwards). `find_by_name_exact("Light%")` now returns `None` (was `Lightning Shrieker` via the LIKE wildcard).

### Timings (same DB copy, warm, single process)

| Measure | Before | After |
|---|---|---|
| `find_by_name_exact("LIGHTNING bolt")` (5 runs, ms) | 57.9 / 57.6 / 59.3 / 57.8 / 58.0 | 0.62 / 0.55 / 0.49 / 0.47 / 0.56 |
| `import_decklist`, 100-line Commander list (1 commander + 99 deck lines, all resolvable) | **2.032 s**, 100 commits, 100 rows | **0.091 s**, 1 commit, 100 rows, `status="ok"` |

(The pre-change import on this machine measured ~2 s rather than the 7–10 s the audit recorded; the audit's number was taken under different load. The target of < 0.5 s is met with room.)

### Verification (all run 2026-09-04, exact outcomes)

- `uv run ruff check .` — All checks passed. `uv run ruff format --check .` — 334 files already formatted.
- `uv run mypy src/` and `uv run mypy src/ --platform win32` — Success: no issues found in both.
- `uv run pytest -m "not integration" -q` — **3154 passed, 1 skipped, 27 deselected** in 126.8 s (first run surfaced one failure, `test_deck_changed_wiring.py::test_a_real_500_after_the_commit_leaves_the_result_byte_identical`, which asserted a `GET /health` before the notify POST; updated to assert the POST is the only request — the probe-drop ripple, see below).
- `uv run python -c "import sys, src.mcp_server.server; assert 'fastembed' not in sys.modules"` — no output (also pinned by the new subprocess test `test_importing_the_server_does_not_import_fastembed`).
- `cd ui && npm run lint && npm run format:check && npm run typecheck && npm test && npm run test:gates && npm run build && npm run gen:types` — lint clean, Prettier clean, tsc clean, **58 files / 1758 tests passed**, gates **2 files / 39 tests passed**, build ok (static assets byte-identical — no `ui/` or `src/companion/app/static` change in porcelain), gen:types ok.
- `uv run python -m scripts.build_plugin && git status --porcelain` — plugin assembled (v0.5.0, 5 skills); porcelain lists only the intended `src/`, `tests/`, `docs/`, `CHANGELOG.md` and `plugin/server/src/**` modifications plus this untracked story file. Left uncommitted for Brad's review/commit.
- `tests/integration/test_mcp_tools.py::test_every_registered_tool_has_a_round_trip` — passes: all 25 `ROUND_TRIPPED` tools still register and round-trip; the new `test_a_tool_call_is_answered_while_the_index_builds` passes (`list_decks` answered while `build_search_index` was parked inside a `threading.Event`-gated embedder stub).

### Matrix coverage

| Row | Test |
|---|---|
| Exact lookup, mixed case (+ plan) | `tests/unit/data/test_card_repository.py::TestFindByNameExact::test_mixed_case_lookup_is_an_index_search` |
| Wildcard chars literal | `…::test_wildcard_characters_are_compared_literally` |
| Existing DB lacks the index / locked | `tests/unit/data/test_database.py::test_an_existing_database_gains_the_nocase_indexes_on_connect`, `…::test_a_locked_database_is_logged_and_the_next_connect_retries` |
| Fresh empty DB | `…::test_a_fresh_database_gets_the_indexes_from_create_all` |
| 100 resolvable lines, one commit/reload | `tests/integration/mcp_server/test_deck_import_tool.py::test_import_decklist_hundred_lines_is_one_commit_and_one_reload` (spies on `AsyncSession.commit`, `get_deck_with_cards`, `add_cards_to_deck`) |
| Same card twice in one board | `…::test_import_decklist_same_card_twice_in_one_board_is_exists_on_the_second_line` |
| One unresolvable line | `…::test_import_decklist_one_unresolvable_line_commits_the_other_ninety_nine` |
| Commit fails | `…::test_import_decklist_failed_commit_is_error_with_nothing_added` (+ repository-level `test_add_cards_to_deck_duplicate_rolls_back_the_whole_batch`) |
| Tool call during index build | `tests/integration/test_mcp_tools.py::test_a_tool_call_is_answered_while_the_index_builds` |
| Push, app running (one POST, no GET) | `tests/unit/companion/test_client.py::TestPushDiscoveryGate::test_a_live_backend_sees_exactly_one_request_and_it_is_the_post` (and the PUT twin) |
| Push, refused connection | `…::TestPushDiscoveryGate::test_a_dead_port_is_app_not_running` |
| Push, listener never answers | `…::TestPushDiscoveryGate::test_a_silent_listener_is_backend_error` |
| Push, 403 then 200 | `…::TestPushRetriesOnceOnAForbiddenToken::test_the_retry_re_reads_discovery_and_probes_nothing` (`["POST", "POST"]`) |
| No discovery file | `…::TestPushDiscoveryGate::test_no_discovery_file_is_app_not_running_without_touching_the_network` |
| Server import | `tests/unit/search/test_embedder.py::test_importing_the_server_does_not_import_fastembed` |

### Ripples outside the files the Code Map listed

- `tests/integration/mcp_server/test_deck_changed_wiring.py` — the 500-after-commit row asserted the probe ran first; now asserts the POST is the only request. Its drip row's docstring/assert messages named `_PROBE_TOTAL_SECONDS` (5 s) as the no-budget fallback; that is now `_PUSH_TOTAL_SECONDS` (10 s). The elapsed-time bounds (0.9–3.0 s) are unchanged and still pass.
- `tests/unit/companion/test_import_boundary.py` — `add_cards_to_deck` added to `_REPO_WRITE_METHODS` (the surface pin fails on any unclassified repository method).
- `tests/unit/companion/test_client.py` — the stub now answers every response with `Connection: close` (the pooled client would otherwise hold a keep-alive socket open while the stub's `server_close()` joins its handler threads), and an autouse fixture resets/closes the shared client per test. The two "foreign identity → no token sent" tests (push and active-deck) were removed: with the probe gone that protection no longer exists, per the Design Notes ruling (AD-4 amended).
- `src/search/connection.py` docstring — the "FastMCP dispatches sync tools to a threadpool" sentence was false and is now "run on worker threads (`asyncio.to_thread`)". `src/search/embedder.py` had two similar "threadpool workers" comments, also corrected.
- The frozen "docstrings-as-descriptions … stay as they are" constraint was read as "no tool description changes beyond the sentences this change made false": the only tool docstring edited is `import_decklist`'s persistence sentence ("Valid lines remain persisted when another line fails" → one transaction), and its neighbouring "commits N times" comment.
- `docs/companion.md` and `README.md` — the spec cites probe sentences at `companion.md:12,158` and `README.md:225,260`; grep found no `/health`/probe wording at those lines (only `companion.md:197`, which is about DB readiness, not the push). The one doc sentence that did describe the pre-push probe was `docs/companion-app-feature-brief.md:126`, updated.

### Review pass (2026-09-04, same day)

Applied the coordinator's eleven findings: the connect hook now reads the two index names first and issues no DDL when both exist, catches `sqlite3.DatabaseError` (corrupt/non-SQLite file still connects), and is opt-out via `create_engine(ensure_indexes=False)`, which the companion's `deps.py` passes (AD-2 read-only shell); `import_decklist` separates a bulk-write `IntegrityError` ("the deck changed while importing; nothing was added — re-run the import", WARNING) from other `DatabaseError`s; the ambiguous / not-found / exists / added message builders and a public `resolve_card` live in `deck_management.py` and are used by both modules; the shared client sets `keepalive_expiry=2.0` (under uvicorn's 5 s idle close) and the runner resets it after its `asyncio.run` startup check; the per-test reset/close fixture moved to `tests/conftest.py`; new tests cover client reuse, lifespan close, existing-indexes-no-DDL, corrupt-file warn, the companion opt-out, both indexes in the plan, `not build.done()` mid-build, and a resolve-time `DatabaseError` line.

Re-verified after the pass: ruff check clean, ruff format --check 334 files clean, mypy `src/` and `--platform win32` both clean, `uv run pytest -m "not integration" -q` **3162 passed, 1 skipped, 27 deselected** (204 s), fastembed import check silent, UI chain green (lint, Prettier, tsc, 58 files / 1758 tests, gates 2 files / 39 tests, build, gen:types), `build_plugin` assembled and porcelain shows only the intended `src/`, `tests/`, docs, CHANGELOG, `project-context.md` (reviewer's edit) and `plugin/server/src/**` changes plus this story file.

### Incomplete or risky

- `_bmad-output/project-context.md` carried the same false "FastMCP runs sync tools in a threadpool" rule; it was updated (by the reviewer) so the coding rules no longer contradict `server.py`.
- **Firing proof for the concurrency test was reasoned, not run** through `scripts.probe_harness` against the old sync closure: on the old code the loop thread would block inside the gated embedder, `entered.wait` could not be observed, and the row fails by `wait_for` timeout after the 30 s gate expires. No planted-regression run was executed.
- The connect hook issues `CREATE INDEX IF NOT EXISTS` (two catalog checks) on every **new** pooled connection; existing databases pay one ~0.4 s index build on their first connection after upgrade. A competing writer's lock is logged at WARNING and retried on the next connection, never raised.
- Shared companion client: cached per running loop. The runner's `asyncio.run(client.live_instance())` startup check leaves a client bound to a closed loop; the next call on a live loop drops it (sockets close on GC) rather than `aclose()`-ing it, since a pool cannot be closed from another loop. Production close path is the FastMCP `lifespan` hook.
- The 27 `integration`-marked tests (network / real model) were not run.
- A timing assertion for the < 0.5 s import is recorded here, not as a test (fixture setup against the real DB is a non-goal).

## Suggested Review Order

**Entry point**

- Corrected docstring states the real FastMCP contract; everything else follows from it
  [`server.py:11`](../../../../src/mcp_server/server.py#L11)

**CAP-1: indexed lookup**

- Two NOCASE functional indexes in metadata; `create_all` covers fresh databases
  [`card.py:26`](../../../../src/data/models/card.py#L26)
- Connect hook migrates existing files: skips when both indexes exist, never fails the connection
  [`database.py:44`](../../../../src/data/database.py#L44)
- Hook gated by `ensure_indexes`; the companion stays a read-only shell (AD-2)
  [`database.py:86`](../../../../src/data/database.py#L86)
  [`deps.py:179`](../../../../src/companion/app/deps.py#L179)
- Collated equality replaces `ilike`; both OR terms indexed so SQLite uses MULTI-INDEX OR
  [`card.py:197`](../../../../src/data/repositories/card.py#L197)

**CAP-1: single-transaction import**

- Bulk add: `add_all`, one commit, one reload, rollback on error
  [`deck.py:387`](../../../../src/data/repositories/deck.py#L387)
- Resolve-all then one write; duplicates detected in memory to keep per-line `exists`
  [`deck_import.py:511`](../../../../src/mcp_server/tools/deck_import.py#L511)
- Concurrent-writer `IntegrityError` becomes a distinct whole-import error
  [`deck_import.py:512`](../../../../src/mcp_server/tools/deck_import.py#L512)
- Resolver and message builders made public so the two tools cannot drift
  [`deck_management.py:157`](../../../../src/mcp_server/tools/deck_management.py#L157)
  [`deck_management.py:185`](../../../../src/mcp_server/tools/deck_management.py#L185)
- Entry schema; the quantity ceiling stays the caller's job
  [`deck.py:40`](../../../../src/data/schemas/deck.py#L40)

**CAP-2: off the event loop**

- Search closure: connection and embedder acquired inside the worker (NFR6), then `to_thread`
  [`server.py:1010`](../../../../src/mcp_server/server.py#L1010)
- Index build offloaded the same way
  [`server.py:1078`](../../../../src/mcp_server/server.py#L1078)
- Aggregate pass off-loop; parse pulled per batch in a worker
  [`scryfall.py:431`](../../../../src/data/importers/scryfall.py#L431)
  [`importer.py:90`](../../../../src/data/importers/importer.py#L90)

**CAP-11: companion client and lazy embedder**

- One client per running loop; keep-alive expiry below uvicorn's idle timeout
  [`client.py:251`](../../../../src/companion/client.py#L251)
  [`client.py:262`](../../../../src/companion/client.py#L262)
- Push reads discovery and sends; no probe (AD-4 ruling in Design Notes)
  [`client.py:528`](../../../../src/companion/client.py#L528)
- Refused connection is `app_not_running`; any other transport failure is `backend_error`
  [`client.py:475`](../../../../src/companion/client.py#L475)
- Server lifespan closes the pool; the runner drops its pre-uvicorn client
  [`server.py:201`](../../../../src/mcp_server/server.py#L201)
  [`server.py:347`](../../../../src/companion/app/server.py#L347)
- fastembed imported on first `Embedder` construction, not at server import
  [`embedder.py:21`](../../../../src/search/embedder.py#L21)

**Tests and peripherals**

- Query plan asserts both NOCASE indexes and no scan
  [`test_card_repository.py:159`](../../../../tests/unit/data/test_card_repository.py#L159)
- Migration hook rows: existing, fresh, locked, corrupt, gated
  [`test_database.py:96`](../../../../tests/unit/data/test_database.py#L96)
- Commit/reload spies for the 100-line import
  [`test_deck_import_tool.py:98`](../../../../tests/integration/mcp_server/test_deck_import_tool.py#L98)
- Concurrency proof with a gated embedder; lifespan close
  [`test_mcp_tools.py:1559`](../../../../tests/integration/test_mcp_tools.py#L1559)
  [`test_mcp_tools.py:1590`](../../../../tests/integration/test_mcp_tools.py#L1590)
- Discovery-gate rows replace the identity-gate rows; client reuse pinned
  [`test_client.py:1018`](../../../../tests/unit/companion/test_client.py#L1018)
  [`test_client.py:1058`](../../../../tests/unit/companion/test_client.py#L1058)
- Shared-client reset fixture for every test that dials the companion
  [`conftest.py:15`](../../../../tests/conftest.py#L15)
- Subprocess import check
  [`test_embedder.py:54`](../../../../tests/unit/search/test_embedder.py#L54)
- Release notes
  [`CHANGELOG.md:13`](../../../../CHANGELOG.md#L13)

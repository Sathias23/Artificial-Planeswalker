---
title: 'Python tests are hermetic and share one fixture set'
type: 'refactor'
ticket: 2
created: '2026-11-10'
status: 'built'
baseline_revision: '9ce18db27d31a6d9d767a6ccdcb4d4f8205e9430'
route: 'full'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Most tests resolve the developer's real data directory: every MCP mutation's `deck_changed` emit reads the real `companion.json` (a stale one costs 1 s per mutation; 29 of the 30 slowest tests, about 146 s of a 287 s run), the subprocess tests inherit it, and the assessment benchmark opens the real `cards.db` read-write. Fixtures are copied instead of shared, the CardRepository ones bypass the production engine (no foreign-key pragma, `autoflush=True`), the search-index client tests give the server's two database handles different files, `FakeEmbedder` reuses vectors past 384 texts, 14 stray `asyncio` markers remain, and on Linux the singleton no-blocking test would hang instead of fail (M47, T1-1-P3/P7/P8/P9/P16, T1-2-P2/P3, T1-3-P1/P10/P15).

**Approach:** One root autouse fixture points `PLANESWALKER_DATA_DIR` at the test's `tmp_path`, drops `CARDS_DATABASE_URL`, and pins `FASTEMBED_CACHE_DIR` to the persistent model cache, so the per-file copies go. Shared fixtures and builders move into the conftests and `tests/fixtures/`, the index tests open one file through both seams, and the singleton contention runs in a thread with a bounded join.

## Boundaries & Constraints

**Always:** Test code only (`tests/**`); nothing under `src/`, `scripts/`, `ui/` or `plugin/` changes. Assertions keep their meaning: where a shared fixture's defaults differ from a deleted copy's, pass the override at the call site instead of weakening the assertion. Every new guard gets a probe-harness RED proof. Grep the whole tree for each pattern before calling it fixed. Wall time no worse than the 287 s baseline.

**Never:** Run any test, probe or command against the real data directory (a probe that removes the root fixture runs with `PLANESWALKER_DATA_DIR` set to a scratch dir). Commit (the orchestrator commits), use bare `git stash`, or run `git checkout HEAD --` over staged work (stage the tree before planting a probe; check each revert with `git diff --exit-code <file>`). Touch the CI workflow (story 4.4), the probe harness (4.5), `test_index_builder.py` / `test_query.py`'s hand-typed DDL (T1-1, not this story), T1-2-D1's assessment client duplication (deferred), or T1-3-P2/P16 (Q23 backlog).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Any test | developer has a stale `companion.json` and/or an exported `CARDS_DATABASE_URL` | the test sees `PLANESWALKER_DATA_DIR == tmp_path`, no URL, `FASTEMBED_CACHE_DIR` = the real model cache | — |
| Test sets its own data dir | fixture or body `setenv`s `PLANESWALKER_DATA_DIR` | its value wins (autouse runs first) | — |
| Benchmark | real `cards.db` present / absent | opened read-only and immutable, never written; absent → skip as today | — |
| FakeEmbedder | 384 distinct texts, then a 385th | 384 distinct vectors; the 385th raises `ValueError` naming the limit | raise |
| Singleton contention | lock already held in-process | refusal returns within 2 s; a blocking acquire fails the test at 2 s instead of hanging | `pytest.fail` |
| CardRepository unit fixture | session from the shared fixture | `PRAGMA foreign_keys` reads 1 | — |
| Index client tests | `seeded_card_db` + build | both seams open one file; `cards_indexed == 3`; a card lookup answers mid-build | — |

</frozen-after-approval>

## Code Map

- `tests/conftest.py` -- root; add autouse `isolated_data_dir(tmp_path, monkeypatch) -> Path` (setenv data dir, delenv URL, setenv cache) beside `_fresh_shared_companion_client`; add `sample_json_file` and `stub_server` fixtures.
- `tests/fixtures/real_data.py` (new) -- import-time, side-effect-free snapshot of the developer's env: `MODEL_CACHE_DIR` (`FASTEMBED_CACHE_DIR`, else real data dir / `fastembed_cache`) and `REAL_DATABASE_FILE` (URL file via `src.paths.sqlite_file_from_url`, else real data dir / `cards.db`). Real data dir = stripped `PLANESWALKER_DATA_DIR` or `platformdirs.user_data_dir("artificial-planeswalker", appauthor=False)`. Never call `src.paths.data_dir()` (it mkdirs).
- Copies to delete (M47): `tests/unit/companion/conftest.py:99-119` `isolated_data_dir`; `tests/integration/mcp_server/test_entry_point.py:107-116`; `test_deck_changed_wiring.py:897-900`, `:1003-1018`; `test_companion_tool.py:1229-1240`; `test_companion_degradation.py:~60-70`; `tests/integration/test_mcp_tools.py:2137-2143` `closed_companion`. Tests that used a returned path request `isolated_data_dir` (or `tmp_path`, same dir). `test_live_backend.py:271-290` `live_data_dir` just returns `tmp_path`. `test_discovery.py:76-82` docstring points at the root fixture. Keep `test_import_clis.py`'s own data-dir subfolder and the default-location tests that `delenv` on purpose (`test_paths.py`, `test_embedder.py`, `test_connection.py`, `test_cdp_harness.py`).
- `tests/integration/logic/test_assessment_benchmark.py:100-104` -- `_resolve_all` calls `create_engine()` from a module-scoped fixture (runs before the autouse patch, so it hits the real DB read-write). Open `REAL_DATABASE_FILE` as `sqlite+aiosqlite:///file:<posix>?mode=ro&immutable=1&uri=true` with `ensure_indexes=False`; missing file returns `None` (skip).
- `tests/integration/search/test_embedder.py:15-17` -- module-level `fastembed_cache_dir()`; use `MODEL_CACHE_DIR`.
- `tests/unit/data/test_card_repository.py:19-94`, `test_format_filtering.py:13-59` -- move `async_engine`, `async_session`, `mixed_format_session`, `mixed_format_repo` into new `tests/unit/data/conftest.py` built on `create_engine("sqlite+aiosqlite:///:memory:")` + `init_database` + `create_session_factory`. Add a test that the session reports `PRAGMA foreign_keys` = 1. Tests that relied on autoflush get an explicit `flush()`/`commit()`.
- `tests/integration/conftest.py` -- add `in_memory_engine`, `session`, `card_db_path` (`tmp_path / "test.db"`), `empty_card_db` (file-backed, schema, no rows), `uninitialized_session`; rebuild `seeded_card_db` on `empty_card_db`. Delete copies: `integration/data/test_database_integration.py:12-27`, `test_combo_snapshot_repository.py:23-38`, `test_deck_repository.py:53-73` (keep its local `session_factory` on the shared engine), `test_scryfall_import_e2e.py:26-46` and `test_spellbook_import_e2e.py:28-41` (`test_db` -> `empty_card_db`), `mcp_server/test_card_lookup_tool.py:37-44` and `test_card_search_tool.py:159-166` (their seeding `session` overrides request the parent `session`). Rename `test_cards` (`test_deck_repository.py:82`) to `seeded_cards`.
- `tests/unit/data/importers/test_parser.py:11-14`, `test_scryfall_import_e2e.py:42-45` -- `sample_json_file` copies; delete, root fixture serves both.
- `test_scryfall_import_e2e.py` -- delete all 14 `@pytest.mark.asyncio` (the only file with any).
- `tests/fixtures/embedder.py:32-38` -- raise `ValueError` once `len(self._assigned) == EMBEDDING_DIM` for a new text; test in `tests/unit/fixtures/test_fake_embedder.py` (new).
- New `tests/fixtures/assessment_db.py` (T1-2-P2): `assessment_card(card_id, name, *, type_line, cmc=2.0, oracle_text="Does a thing.", colors=None, game_changer=False) -> CardModel` (body of `test_assess_deck_power_tool.py:65`), `assessment_core_cards(prefix)` (Mountain, Krenko, Zada, Goblin Guide, Shock, then Bolas's Citadel before Aura Shards; ids `{prefix}mountain`, `{prefix}krenko`, `{prefix}zada`, `{prefix}goblin-guide`, `{prefix}shock`, `{prefix}gc-bolas`, `{prefix}gc-aura`), `null_game_changer_card(prefix)` (`{prefix}gc-null`, "Mystery Relic"), `make_deck(session, rows, *, name="Deck", format="commander") -> str`. Consumers: assess suite (`"card-"` core + its local DFC/Chandra extras + null), compare suite (`"card-"` core; drop its `_card`, `_seed_cards`, `_make_deck`, `uninitialized_session`), `test_mcp_tools.py:999-1100` (`"e2e-"` core + null; drop `_assessment_card`). Their `session` fixtures stay local (different seeds), sharing the builders.
- New `tests/fixtures/server_seams.py`: `RecordingNotifier` (from `test_mcp_tools.py:345` and `test_deck_changed_wiring.py:162`; unify on the superset if they differ) and `fake_importer` (+ its card builder) from `test_first_run_data_init.py:40-70`. `test_mcp_tools.py:62-65` stops importing from a test module.
- T1-2-P3: `test_mcp_tools.py:2058-2115` -- build with `ConnectionFactory(db_path=str(card_db_path))` over `seeded_card_db`, assert `cards_indexed == 3`; the concurrent call becomes `lookup_card_by_name` "Lightning Bolt" (status `found`), which reads the file being indexed. `test_first_run_data_init.py:72-106,309-425` -- delete `_sync_cards_factory`; the six sync tests become `async def` over `empty_card_db` / `seeded_card_db` + a factory on `card_db_path` (count 3; find_similar by "Lightning Bolt").
- T1-3-P1: `tests/unit/companion/test_routes_decks.py:42-149` and `test_routes_format_check.py:41-118` -- delete local `_point_at`, `_card`, `_ready_database`, `_seed`, `ready_db`; import `_card`, `_point_at`, `_seed` from `tests.unit.companion.conftest` (`:507-593`, already imported elsewhere). Decks: pass `type_line=f"Instant — {card_id}"` where `test_each_entry_nests_its_own_card:453` relies on it, and `cmc=` where asserted. Format-check may keep a thin `_legal_card` wrapper over conftest `_card` carrying its legalities / basic-land defaults. `test_deps.py:75` `_ready_database` (raw sqlite3) -> `_ready_sqlite_file`; its `_point_at` (`:143`) goes. Fix the circular docstrings.
- T1-3-P15: new `tests/fixtures/companion_stubs.py` takes from `tests/unit/companion/test_client.py:55-534`: `HANGUP`, `DRIP`, `RecordedRequest`, `StubHandler`, `StubServer`, `StubFleet`, one `drip_bytes(send)` loop shared by the handler's `_drip` (`:180-201`) and the socket drip (`:446-470`), `Loopback` (merges `test_server.py:31` `_Loopback` and `test_client.py:391` `_Sockets`: `occupy`, `track`, `free_port`, `silent`, `drip`, `close_all`; both hosts are `127.0.0.1`), `health_bytes`, `plant_discovery`. Fixtures: `stub_server` in root conftest (delete the four copies: `test_client.py:379`, `test_server.py:112`, `test_companion_tool.py:1205`, `test_deck_changed_wiring.py:925`); `loopback` in `tests/unit/companion/conftest.py` (`test_client.py`'s `sockets` callers switch, `dead()` -> `free_port()`). `bearer(token)` and `mint_ticket(client)` go to `tests/unit/companion/conftest.py` from `test_routes_active_deck.py:45,700`, `test_routes_agent_events.py:115,120`, `test_ws.py:61` (confirm the bodies match first). Importers updated: `test_server.py:26`, `test_companion_tool.py:79`, `test_deck_changed_wiring.py:99`.
- `tests/unit/companion/test_singleton.py:70-96` -- helper runs `acquire_instance_lock()` in a daemon thread, `join(timeout=2.0)`, `pytest.fail` if alive; used by both contention tests.
- New `tests/unit/test_isolation.py` -- pins the root fixture: data dir resolves to `tmp_path`, `CARDS_DATABASE_URL` unset, `FASTEMBED_CACHE_DIR == MODEL_CACHE_DIR` and not under `tmp_path`.

## Tasks & Acceptance

**Execution:**
- [ ] `tests/fixtures/real_data.py`, `tests/conftest.py`, `tests/unit/test_isolation.py` -- root isolation + its pin; then delete the M47 copies and retarget `live_data_dir`, `test_discovery`, the benchmark and `integration/search/test_embedder.py`.
- [ ] `tests/unit/data/conftest.py` + the two CardRepository files -- shared production-engine fixtures and the FK-pragma test.
- [ ] `tests/integration/conftest.py` + the data and mcp_server files listed -- shared empty/in-memory fixtures, renames, `sample_json_file`, `asyncio` markers.
- [ ] `tests/fixtures/assessment_db.py`, `tests/fixtures/server_seams.py` + assess, compare, `test_mcp_tools.py`, `test_deck_changed_wiring.py`, `test_first_run_data_init.py` -- shared builders, one-file index tests.
- [ ] `tests/fixtures/embedder.py` + `tests/unit/fixtures/test_fake_embedder.py` -- the limit and its test.
- [ ] companion: route suites, `test_deps.py`, `tests/fixtures/companion_stubs.py`, the stub/loopback/mint/bearer moves, `test_singleton.py`.

**Acceptance Criteria:**
- Given the full Python gate, when run, then ruff, ruff format, both mypy platforms and `uv run pytest` pass, and `--durations=30` is no longer dominated by `test_mcp_tools.py`.
- Given each pattern this story removes (`PLANESWALKER_DATA_DIR` setenv copies, `in_memory_engine`, `test_db`, `sample_json_file`, `mark.asyncio`, `_RecordingNotifier`, `_card` in the two route suites, `_point_at`, `stub_server`, `_mint`, `_bearer`, imports from `tests.unit.companion.test_client` and `test_first_run_data_init`), when grepped across `tests/`, then only the shared definition (or a deliberate, documented exception) remains.

## Design Notes

The root fixture's data dir is `tmp_path` itself, not a subfolder: the unit companion tests and `live_data_dir` already assume `discovery_path().parent == tmp_path`, so this keeps them and lets the shared fixture replace them. Module-scoped fixtures run before a function-scoped autouse one, so nothing module-scoped may resolve a default path; that is why the benchmark names `REAL_DATABASE_FILE` explicitly (the one sanctioned reader of operator data, read-only and immutable so SQLite creates no `-wal`/`-shm`) and why the model cache comes from the import-time snapshot. `FASTEMBED_CACHE_DIR` is pinned rather than isolated because the ~80 MB model is a download cache, not operator data, and AGENTS.md requires a persistent path.

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32` -- clean.
- `uv run pytest --durations=30 -p no:cacheprovider` -- passes, wall time recorded; baseline 3337 passed, 2 skipped in 287.34 s.
- Snapshot the real data dir (file list, sizes, mtimes, `companion.json` sha256, the directory's own mtime) before and after the run -- identical; the stale `companion.json` (2026-09-15) is already planted.
- `PLANESWALKER_DATA_DIR=<scratch> uv run python -m scripts.probe_harness --expect-red '<node id>' ...` with each guard's fix reverted in the working tree (index staged first; `git diff --exit-code` after restoring): the isolation pin, the FK-pragma test, the FakeEmbedder limit test, the singleton bound (plant `LK_LOCK`) -- proof line in Implementation Notes.

## Implementation Notes

All six execution tasks done; changes are under `tests/**` only (`src/`, `scripts/`, `ui/`, `plugin/` untouched; `git diff --exit-code src` clean after the probes).

**Gate (2026-11-10, Windows):** `ruff check .`, `ruff format --check .`, `mypy src/`, `mypy src/ --platform win32` clean. `uv run pytest --durations=30 -p no:cacheprovider`: **3345 passed, 2 skipped in 109.70 s** (baseline 3337 passed, 2 skipped in 287.34 s; +8 are the new pins). The slowest-30 list is no longer `test_mcp_tools.py`: its slowest test is now 0.32 s, and the top entries are deliberate timeouts (live backend 4.3 s, drip/wedge rows ~1 s).

**Real data dir:** snapshot (file list, sizes, mtimes, `companion.json` sha256, the directory's own mtime) identical before and after every run, including the benchmark run that opens the real `cards.db` read-only + immutable (no `-wal`/`-shm` created).

**Probe proofs** (each run with `PLANESWALKER_DATA_DIR=<scratch>`, tree staged first, each revert checked with `git diff --exit-code <file>`):

- Isolation pin (plant: root fixture's three env lines replaced by `setenv("PLANESWALKER_DATA_DIR", str(tmp_path / "elsewhere"))`; run with `CARDS_DATABASE_URL=<scratch>/url.db` exported): `full suite (-m 'not integration'): 3320 collected, 13 failed, 0 errored, exit 1`, RED includes `test_isolation.py::test_data_dir_resolves_to_this_tests_tmp_path`, `::test_no_database_url_reaches_a_test`, `::test_the_model_cache_is_pinned_to_the_persistent_one`; harness exit 0.
  - The literal plant (root fixture's env lines deleted outright) never finishes: the run, all tests sharing one scratch data dir, spun at 100% CPU for 30+ min after `test_routes_card_image.py::TestARepeatRequestMakesNoCdnRequest::test_the_second_request_is_served_from_a_file_that_actually_exists` (shared `image_cache`), so it was killed and the partial revert above used instead.
- FK pragma (plant: `tests/unit/data/conftest.py` back to bare `create_async_engine` + `create_all`): `full suite (-m 'not integration'): 3320 collected, 1 failed, 0 errored, exit 1`, RED `tests/unit/data/test_card_repository.py::test_the_shared_session_enforces_foreign_keys`.
- FakeEmbedder limit (plant: `% EMBEDDING_DIM` wrap restored, raise removed): `full suite (-m 'not integration'): 3320 collected, 1 failed, 0 errored, exit 1`, RED `tests/unit/fixtures/test_fake_embedder.py::test_one_text_too_many_raises_naming_the_limit`.
- Singleton bound (plant: `msvcrt.LK_NBLCK` -> `LK_LOCK` in `src/companion/app/singleton.py`, reverted): `full suite (-m 'not integration'): 3320 collected, 3 failed, 0 errored, exit 1`, RED `test_singleton.py::TestAcquireAndRelease::test_a_second_descriptor_in_this_process_is_refused`, `::test_a_refused_acquire_returns_immediately`, `::test_the_refused_path_leaks_no_descriptor`.

**Pattern greps (AC 2), across `tests/`:** one definition each of `isolated_data_dir`, `in_memory_engine`, `uninitialized_session`, `sample_json_file`, `stub_server`, `loopback`, `_point_at`, `RecordingNotifier`, `bearer`, `mint_ticket`; zero `mark.asyncio`, `def test_db`, `_RecordingNotifier`, `_mint`, `_bearer`, `_Sockets`, `_Loopback`, `closed_companion`; zero imports from `tests.unit.companion.test_client` or `test_first_run_data_init`; no `_card`/`_ready_database`/`_seed`/`ready_db` in the two route suites (format-check keeps the sanctioned `_legal_card` wrapper). Remaining `setenv("PLANESWALKER_DATA_DIR", ...)` sites are deliberate: the default-location tests (`test_paths.py`, unit `test_embedder.py`, `test_connection.py`, `test_cdp_harness.py`), `test_import_clis.py`'s subfolder, and tests that point the dir at a never-created / blocked / second path on purpose (`test_app.py`, `test_errors.py`, `test_deps.py`, `test_discovery.py`, `test_singleton.py`, `test_images.py:2303`).

**Findings outside this story's scope:**

- `build_card_embeddings` crashes (`TypeError: can only join an iterable` in `compose_card_text`) on a card written through the ORM with `keywords=None`, because the JSON column stores `null` and the builder joins it. Raw-SQL `NULL` keywords are handled. Surfaced when the index tests moved onto `seeded_card_db`; the sample cards now carry `keywords=[]` as real Scryfall data does. Production exposure is plausible: `src/data/importers/transformers.py:306-307` preserves `None` when a Scryfall object omits `keywords`, so one such card would abort an index build. Not verified against the live corpus and not fixed here (`src/` out of bounds); worth a ticket.
- An unisolated suite hangs rather than fails (above). The root fixture prevents it; a per-test timeout would turn any future regression into a failure (CI story 4.4 territory).

**After review (quick lens, three patches).** The benchmark's `_read_only_url` / `_resolve_all` docstrings now say the immutable open reads only the checkpointed main file (commits still in `cards.db-wal` are invisible; a concurrent checkpoint can yield wrong results or `SQLITE_CORRUPT`), behaviour unchanged. `test_companion_tool.py`'s stub-ownership comment names `tests/fixtures/companion_stubs.py`. `TestCompanionStatusOverARealSocket`'s two tests assert `read_discovery() is None` again before planting. Re-verified by the orchestrator on the patched tree: ruff check and format clean, mypy clean on both platforms, `uv run pytest --durations=30 -p no:cacheprovider -rs` **3345 passed, 2 skipped in 110.24 s** (skips: `test_discovery.py:129` chmod on Windows, `test_cdp_harness.py:369` symlink privilege; the benchmark ran), real data dir snapshot (directory mtime included) identical before and after.

## Plan Change Log

- `loopback` fixture lives in the root `tests/conftest.py` beside `stub_server`, not in `tests/unit/companion/conftest.py`: `tests/integration/mcp_server/test_deck_changed_wiring.py` also needs it (its `sockets` copy), and a companion-package fixture would not reach that file.
- Also deleted, as copies of the same patterns: the assess suite's local `uninitialized_session` (identical to the new shared one), `test_first_run_data_init.py`'s `empty_session_factory` (now `empty_card_db`), and `test_images.py`'s three redundant `setenv(PLANESWALKER_DATA_DIR, tmp_path)` lines (now `isolated_data_dir`).
- `test_rag_eval.py`'s module-scoped fixture pins `FASTEMBED_CACHE_DIR` to `MODEL_CACHE_DIR` around `get_embedder()`: module scope sets up before the root fixture, so it was the one other module-scoped default-path resolver.
- `test_singleton.py`'s fd-leak test (`test_the_refused_path_leaks_no_descriptor`, 64 contended acquires) also goes through `_bounded_acquire`, the third contention site the grep found.
- `tests/integration/conftest.py::_sample_cards` gained `keywords=[]` (see the index-builder finding above); no assertion depended on `None`.
- The isolation probe used a partial revert, because the literal one hangs the suite (see Implementation Notes).

## Review Triage Log

Pass 1 (quick lens): 5 findings. high 0, medium 0, low 4 (3 patched, 1 rejected), false 0, maybe-false 0; plus 1 pre-existing item deferred.

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | Benchmark's `immutable=1` open ignores the WAL of a WAL-mode `cards.db` | low | patch | Real: uncheckpointed commits are invisible, and a checkpoint inside the ~0.4 s module-scoped read could error; it never writes. Read-only + immutable is the frozen matrix's choice (a `mode=ro` open of a WAL file still creates `-wal`/`-shm`), so only the docstrings changed, stating the caveat. |
| 2 | Redundant `setenv(PLANESWALKER_DATA_DIR, tmp_path)` left in `test_paths.py`, `test_connection.py`, unit `test_embedder.py` | low | reject | Lines are real but each is the stated precondition of a test of the path resolvers themselves; no caller diverges. The Implementation Notes call them "default-location tests", which is loose: they are resolver tests that set the variable explicitly. The only fix is editing this build's plan. |
| 3 | Deleting the root fixture was never proven red; the literal plant hangs the suite | medium | defer | The pin itself goes red under deletion (data dir resolves elsewhere than `tmp_path`); the hang is pre-existing code in `test_routes_card_image.py` spinning on a shared `image_cache`, which the root fixture now prevents. Deferred to `deferred-work.md` (loop not located). The `test_discovery` docstring claim holds. |
| 4 | Stale "`test_client.py` owns the only real HTTP stubs" comment, `test_companion_tool.py:76-78` | low | patch | Confirmed; reworded to name `tests/fixtures/companion_stubs.py`. Grep found no other comment claiming ownership. |
| 5 | `TestCompanionStatusOverARealSocket` lost its `read_discovery() is None` precondition | low | patch | Confirmed against the deleted class fixture; restored at the top of both tests, as the sibling wiring suite kept it. |

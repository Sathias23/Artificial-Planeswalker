---
title: 'Filtered semantic searches come back full'
type: 'bugfix'
ticket: '11'
created: '2026-11-11'
status: 'review'
baseline_revision: '4321f054175cb1933180bb42129133ef7ad4b119'
route: 'full'
route_source: 'auto'
risk: 'high'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `hybrid_search` always takes the 200 nearest vectors and only then applies the format and games filters. On the real index a `standard` filter keeps 5–24 of the 200, so `limit=10` comes back short (Sol Ring 5, Llanowar Elves 6) and `limit=50` always does (M10). 14,472 orphan vectors (26.8%) whose card is gone take 41–79 of the 200 slots in each of 16 measured queries, because nothing prunes them by default (M9). `initialize_database` tells the agent to pass `prune=true` to a tool with no such parameter (M9, research F6). Dropping the `limit` or `color_mode` forward in either sync tool passes the suite (B9-P17).

**Approach:** Pin the forwards first (green on the old code). Then, when a filtered window comes back short and the KNN filled `k`, retry once at the cap (review option a). Prune orphans on every build. Drop the `prune` advice and parameters.

## Boundaries & Constraints

**Always:** Every KNN statement binds `k`, and `k` never exceeds `_MAX_OVER_FETCH_K = 4096`, the vec0 limit measured on sqlite-vec 0.1.9 (`k=4097` raises "k value in knn query too large"). The common path does not change: a window that fills `limit`, or a KNN that returned fewer than `k` rows, runs exactly one KNN. The work stays sync inside `asyncio.to_thread`. Pruning deletes only rows whose `card_id` is not in `cards`, and never runs while the first-run import marker is set (the precondition the review attached to option a). Docstrings for `semantic_search_cards`, `find_similar_cards`, `build_search_index` and `initialize_database`'s hint state the new behaviour. `plugin/` is rebuilt. CI tests use `tmp_path` databases built through `init_database`, with a fake embedder. Real-data checks open `cards.db` with `mode=ro&immutable=1` (no `-wal` exists, and nothing gets written beside it). The build proof runs on a backup-API copy in the scratchpad.

**Never:** No vec0 schema change or metadata-column legality filter (option c); no ranking or embedding change; no change to `_MAX_LIMIT` (50). No CLI bootstrap rewrite (B6-P3), `--rebuild` reorder (B6-P1), model fingerprint (B6-D3) or `ORDER BY` (M44); those stay in their backlog stories. No write to the real data directory.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First window fills | unfiltered, or a filter with ≥ `limit` matches in the nearest 200 | one KNN at k=200, results as today | none |
| Starved filter | `format="standard"`, `limit=10`, ≥ 10 legal cards inside the nearest 4,096 but < 10 in the nearest 200 | 10 results, nearest-first; a second KNN at k=4096 | none |
| Exhausted pre-filter | colour/mana filters leave < 200 vectors, result short | one KNN, short result, no retry | none |
| Beyond the cap | legal matches only past rank 4,096 | short or `empty` result; no KNN above k=4096; the tool `message` adds that only N matched among the nearest 4,096 cards and `search_cards` filters the whole database | none |
| Default build | `card_vec` rows whose card was deleted | rows gone from `card_vec` and `card_embedding_meta`; `cards_pruned` reported | per-chunk rollback as today |
| Import in progress | first-run marker set, orphans present | build runs, prune skipped and logged | none |

**Decisions (Brad, 2026-11-11):**
- Short at the cap: (b). `hybrid_search` reports when it stopped at the cap with the window full and the result short. `semantic_search_cards` and `find_similar_cards` then append one sentence to `message` on `ok` and `empty`, with no result-schema change.
- Plan size: keep the full plan (~2,800 tokens); no split.

</frozen-after-approval>

## Code Map

- `src/search/query.py:256-401` `hybrid_search` -- the only KNN call site (grepped `MATCH` across `src/` and `scripts/`). Switch the JOIN to `LEFT JOIN cards` and compute the outer filters as a bound `passes` column, so `len(rows)` is the KNN row count (it detects a filled `k`; NULL `c.id` counts orphans for the debug log). Python keeps passing rows, then dedups. Loop: run at `over_fetch_k` (now the initial window, default 200). If hits < `limit`, `len(rows) == k` and `k < cap`, run again at the cap. It returns `HybridHits`, a `list[CardHit]` subclass carrying `cap_reached: bool`. The flag is true when the cap query also filled `k` and the result is still short. Existing callers and tests that treat the result as a list keep working. Module docstring lines 3-15 and the args docstring change with it.
- `src/mcp_server/tools/semantic_search.py:44-46`, `find_similar.py:55-58` -- `_MAX_LIMIT` comments cite "over_fetch_k (200)"; reword. Calls at `semantic_search.py:239` and `find_similar.py:385` are unchanged. The `ok` and `empty` messages after them append the cap sentence when `hits.cap_reached`.
- `src/search/index_builder.py:247-350` -- drop the `prune` parameter. Always call `_prune_orphans` unless `is_import_in_progress_sync(conn)` is set (`src/data/import_state.py:69`, already imported by `query.py`). Fix the `BuildStatistics` docstring (line 77).
- `src/mcp_server/tools/build_search_index.py` -- drop `prune`. Add `cards_pruned: int = 0` to `BuildSearchIndexResult` (MCP-only, not served by the companion, so no `gen:api`). The message names the pruned count when it is non-zero.
- `scripts/build_card_embeddings.py:107-111,150` -- remove `--prune`; the summary already prints the pruned count.
- `src/mcp_server/server.py:1204-1400` -- the `semantic_search_cards` and `find_similar_cards` docstrings say filters are applied to the nearest cards, widened up to the nearest 4,096 when results run short. The `build_search_index` docstring says each build also removes the vectors of cards no longer in the database.
- `src/mcp_server/tools/initialize_database.py:18-20,253-262` -- the hint drops `prune=true`; a plain re-run now drops the removed rows' vectors.
- Skills: none mention prune, `k=` or server over-fetch (grepped). Add one line after each `limit` hard-cap bullet in `magic-deckbuilding`, `synergy-discovery`, `mana-curve-analysis` and `format-legality`: an `ok` can hold fewer than `limit` when a narrow filter runs out of matches among the nearest 4,096 cards. The `message` then says so; use `search_cards` for the full filtered set.
- Tests (pins): `tests/integration/mcp_server/test_semantic_search_tool.py` and `test_find_similar_tool.py` (hand-built schema, `FakeEmbedder`). `tests/unit/search/test_query.py:314` `test_over_fetch_k_bounds_candidate_pool` pins the old fixed window and is rewritten in commit 2. `tests/unit/search/test_index_builder.py:523` passes `prune=True`. `tests/integration/mcp_server/test_first_run_data_init.py:140-167` pins the `prune=true` advice and flips.
- Fixtures: `tests/integration/conftest.py` `empty_card_db` / `card_db_path` (real schema via `init_database`). `tests/fixtures/embedder.py` gains a `RankedEmbedder`: card text → a unit vector at a chosen rank from a fixed query vector, so orderings are strict, not one-hot ties.

## Tasks & Acceptance

**Execution:**
- [ ] Commit 1 (`test:`): `test_semantic_search_tool.py`, `test_find_similar_tool.py` -- `limit=2` over four surviving cards returns 2; `color_mode="all"` with `["W","U"]` excludes a mono-W card that `any` keeps. Green on the old code; probe-prove each with the forward dropped.
- [ ] Commit 2 (`fix:`): `src/search/query.py` widening; `tests/fixtures/embedder.py` `RankedEmbedder`; `tests/unit/search/test_query.py` -- starved filter fills (red on the old code), exhausted pre-filter and filled first window each issue one KNN (counted via `conn.set_trace_callback`), and a cap test over 4,100 nearer illegal cards that the old code also fails (`cap_reached` true; false when the first window fills or the KNN is exhausted). New `tests/integration/mcp_server/test_filtered_semantic_fill.py` on `empty_card_db` drives both helpers with `format="standard", limit=10` → 10, and each tool's message carries the cap sentence only when `cap_reached`.
- [ ] Commit 3 (`fix:`): builder, tool, CLI and initialize-database prune changes; tests in the new file: the default `build_search_index` and CLI `main()` (argv, `CARDS_DATABASE_URL` and `get_embedder` patched) leave no `card_vec` row without a card; the import marker skips the prune. Update the two existing prune tests.
- [ ] Commit 4 (`docs:`): docstrings, skills, `plugin/` rebuild.

**Acceptance Criteria:**
- Given the real index (read-only), when the 16 measured queries run with `format="standard", limit=10`, then every one returns 10.
- Given a backup copy of the real database, when the default build runs on it, then `card_vec` holds no row whose card is missing and `card_vec`/`card_embedding_meta` ids are equal.
- Given the recall selection with `FASTEMBED_CACHE_DIR` pinned, when it runs, then it passes with a hit-rate ≥ 0.9.
- Given each new guard, when its line is reverted, then the probe harness reports exactly that node red.

## Design Notes

Measured on the real index (read-only, sqlite 3.50.4, vec 0.1.9, 39,503 cards, 53,975 vectors, 5,164 standard-legal), median of one `hybrid_search`: k=200 66 ms, 800 93 ms, 3,200 121 ms, 4,096 128 ms. The vec0 scan dominates, so every extra tier costs roughly a full scan. One jump from 200 to 4,096 costs at most ~195 ms. The ×4 ladder (200→800→3,200→4,096) costs at most ~408 ms. Hence one retry at the cap.

Fill at fixed k (16 queries: 10 seed vectors, 6 embedded NL queries): standard `limit=50` minimum 38 at k=800, 50 at k=3,200. Filtered recall against a brute-force ground truth, today: standard limit=10 0.931 (149/160), limit=50 0.275 (220/800); pauper limit=50 0.882; oldschool limit=10 0.075. Oldschool still returns only 3–28 at k=3,200; that is the honest bound of option a.

Baseline recall eval (`uv run pytest -m integration tests/integration/search/ tests/integration/mcp_server/test_semantic_search_tool.py tests/unit/search/test_index_builder.py`): 5 passed; hit-rate 12/12 = 1.000 (target 0.9). It is unfiltered over 20 cards, so the filtered brute-force recall above is the change's real measure and is re-run after.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy src/ --platform win32 && uv run pytest` -- expected: all pass.
- `FASTEMBED_CACHE_DIR=<persistent cache> uv run pytest -m integration tests/integration/search/ tests/integration/mcp_server/test_semantic_search_tool.py tests/unit/search/test_index_builder.py` -- expected: passes, hit-rate ≥ 0.9.
- `uv run python -m scripts.probe_harness --expect-red '<node id>'` per new guard -- expected: that node red, the proof line pasted below.
- Scratch scripts (`measure_real.py`, `filtered_recall.py`) on the read-only real file, then the backup-copy build -- expected: standard limit=10 is 10 for all 16, timing at the cap recorded, 0 orphans on the copy.
- `uv run python -m scripts.build_plugin` -- expected: `plugin/` regenerated and committed.

## Implementation Notes

Commits on `fix/quality-6-11-filtered-semantic-search`: `5dfb50d` (commit 1, pins, green on the old code), `41d9310` (commit 2, widening + cap note), `f894d10` (commit 3, prune on every build), `841e501` (commit 4, docstrings, skills). `plugin/` is rebuilt in every commit that touches `src/` or a skill, because the pre-commit drift hook checks each commit, so it is not left to commit 4 alone.

- `query.py`: `_MAX_OVER_FETCH_K = 4096`. `HybridHits(list[CardHit])` takes `cap_reached` as a keyword. The SQL is `knn LEFT JOIN cards` with `CASE WHEN c.id IS NOT NULL AND <format/games> THEN 1 ELSE 0 END AS passes` and `c.id IS NULL AS orphan` (the debug log counts orphans). The ORDER BY is unchanged. The loop runs at `k = min(over_fetch_k, cap)` and stops when hits ≥ `limit`, the KNN returned < `k` rows, or `k` is already the cap; otherwise it runs once more at the cap. `cap_reached = short and window_full and k >= cap`. The `k >= cap` term is needed: without it, a short and full first window would report the cap even with the retry deleted. The de-dup moved into `_dedup_hits`, which skips rows that do not pass.
- Cap sentence: `messages.semantic_cap_note(n)` returns " Only n of the nearest 4,096 cards matched the filters; `search_cards` filters the whole database, so use it for the full filtered set." For n=0 it starts "None of the nearest…". Both tools append it to `ok` and `empty` when `hits.cap_reached`. `messages.py` imports the private `_MAX_OVER_FETCH_K` (precedent: `_UNSET` in `deck_management.py`).
- Fixtures: `tests/fixtures/embedder.py` gains `RankedEmbedder`. Rank r maps to `cos(r·step)·e0 + sin(r·step)·e1`, with step = (π/2)/8192 and rank 0 = the query vector, so the seed of a `find_similar` sits on it. It also gains `seed_ranked_cards`, a raw insert into the real `cards` schema that returns the embedder. `test_query.py` builds its widening DBs through `init_database` (via `asyncio.run`) and reads each KNN's bound `k` from `conn.set_trace_callback` (expanded SQL).
- Added beyond the plan's list: `test_orphan_vectors_filling_the_first_window_widen_it` (it is the guard for the `LEFT JOIN`) and `test_over_fetch_k_above_the_cap_binds_the_cap` (the clamp).
- Prune: `build_card_embeddings` has no `prune`. After the chunks it calls `_prune_orphans` unless `is_import_in_progress_sync(conn)`, in which case it logs "Skipped the orphan-vector prune: a first-run card import is in progress". `BuildSearchIndexResult.cards_pruned` is added; when it is non-zero the message adds " Removed N vectors of cards no longer in the database." `--prune` is gone from the CLI. `initialize_database`'s update hint is now "re-run `build_search_index` to index the new cards and drop the vectors of the removed rows."
- The 16 queries: the plan does not list its 16, so these were re-chosen. Ten seed vectors: Sol Ring, Llanowar Elves, Lightning Bolt, Counterspell, Dark Ritual, Swords to Plowshares, Birds of Paradise, Serra Angel, Shivan Dragon, Giant Growth. Six embedded queries: "flying red dragon that deals damage", "draw a card when a creature enters the battlefield", "return a creature card from your graveyard to the battlefield", "destroy target artifact or enchantment", "create treasure tokens", "counter target spell". Sol Ring (5) and Llanowar Elves (6) reproduce the plan's measured shortfall.

Real data (`cards.db` opened `mode=ro&immutable=1`: sqlite 3.50.4, vec v0.1.9, 39,503 cards, 53,975 vectors, 14,472 orphans; the file's mtime was unchanged afterwards). Recall is against a brute-force, oracle-deduplicated ground truth over the live vectors. "old" is `hybrid_search` from `5dfb50d`.

| Config | new fill (min–max) | old fill | recall new | recall old | cap_reached |
|---|---|---|---|---|---|
| standard limit=10 | 10–10 | 5–10 | 160/160 = 1.000 | 151/160 = 0.944 | 0/16 |
| standard limit=50 | 50–50 | 5–29 | 800/800 = 1.000 | 273/800 = 0.341 | 0/16 |
| pauper limit=50 | 50–50 | 23–50 | 800/800 = 1.000 | 717/800 = 0.896 | 0/16 |
| oldschool limit=10 | 5–10 | 0–3 | 151/160 = 0.944 | 11/160 = 0.069 | 2/16 |

Timing (Sol Ring seed, median of 7): unfiltered 74 ms; standard limit=10 new 222 ms (two KNNs) against old 72 ms; oldschool at the cap 221 ms. The retry costs about 150 ms, inside the plan's ~195 ms ceiling.

Backup copy (backup API from the read-only source into the scratchpad; then the CLI `scripts/build_card_embeddings.py` with `CARDS_DATABASE_URL` pointed at the copy): before, `cards=39503 card_vec=53975 card_embedding_meta=53975 orphan_vectors=14472`. The build reported "39,503 processed, 0 new, 0 changed, 39,503 skipped (0 metadata refreshed), 14,472 pruned, 17.7s". After, `cards=39503 card_vec=39503 card_embedding_meta=39503 orphan_vectors=0 vec_ids==meta_ids=True`. Re-measured on the pruned copy: standard limit=10 recall new 1.000 / old 0.988; standard limit=50 new 1.000 / old 0.449; pauper limit=50 new 1.000 / old 0.970; oldschool limit=10 new 0.988 (fill 8–10, cap 1/16) / old 0.100. Sol Ring standard limit=10 is back to one KNN, 73 ms.

Recall eval (`FASTEMBED_CACHE_DIR` pinned to a scratch copy of the model cache; the plan's command): 5 passed; the RAG hit-rate is 12/12 = 1.000, read through a scratch pytest plugin wrapping `evaluate_hit_rate`.

Probe proofs (full suite via `scripts.probe_harness`, each plant made in a detached probe worktree at the commit under test, reverted with `git checkout --` and checked with `git diff --exit-code`, 0 every time):

Commit 1 (on `5dfb50d`):
- `semantic_search.py` drops `limit=`: `full suite (-m 'not integration'): 3527 collected, 1 failed, 0 errored, exit 1`, RED `test_semantic_search_tool.py::test_limit_is_forwarded_to_the_search`.
- `semantic_search.py` drops `color_mode=`: `3527 collected, 1 failed, 0 errored, exit 1`, RED `test_semantic_search_tool.py::test_color_mode_is_forwarded_to_the_search`.
- `find_similar.py` drops `limit=`: `3527 collected, 1 failed, 0 errored, exit 1`, RED `test_find_similar_tool.py::test_limit_is_forwarded_to_the_search`.
- `find_similar.py` drops `color_mode=`: `3527 collected, 1 failed, 0 errored, exit 1`, RED `test_find_similar_tool.py::test_color_mode_is_forwarded_to_the_search`.

Commit 2 (on `41d9310`):
- A, the retry becomes `break` (the old fixed window): `full suite (-m 'not integration'): 3536 collected, 7 failed, 0 errored, exit 1`. RED `test_starved_format_filter_widens_once_and_fills_nearest_first` (expected), plus `test_over_fetch_k_is_the_first_window_and_a_short_full_one_widens_to_the_cap`, `test_orphan_vectors_filling_the_first_window_widen_it`, `test_matches_past_the_cap_stop_at_4096_and_report_cap_reached`, and all three `test_filtered_semantic_fill.py` search tests.
- B, the not-a-full-window stop removed: `3536 collected, 1 failed, 0 errored, exit 1`, RED `test_exhausted_prefilter_runs_one_knn_and_returns_short`.
- C, the filled-`limit` stop removed: `3536 collected, 1 failed, 0 errored, exit 1`, RED `test_first_window_that_fills_limit_runs_one_knn`.
- D, `k = over_fetch_k` (no clamp): `3536 collected, 1 failed, 0 errored, exit 1`, RED `test_over_fetch_k_above_the_cap_binds_the_cap`.
- E, `cap_reached=False`: `3536 collected, 3 failed, 0 errored, exit 1`, RED `test_matches_past_the_cap_stop_at_4096_and_report_cap_reached` plus the two cap-message tests.
- F, `LEFT JOIN` back to `JOIN`: `3536 collected, 1 failed, 0 errored, exit 1`, RED `test_orphan_vectors_filling_the_first_window_widen_it`.
- G1 / G2, the cap note never appended (semantic / similar): each `3536 collected, 2 failed, 0 errored, exit 1`, RED `test_short_at_the_cap_ok_message_names_search_cards` and `test_nothing_inside_the_cap_empty_message_names_search_cards`.
- G3 / G4, the cap note always appended (semantic / similar): each `3536 collected, 1 failed, 0 errored, exit 1`, RED `test_starved_standard_filter_fills_limit_in_both_tools`.

Commit 3 (on `841e501`):
- H, the default prune removed (`else: pass`): `full suite (-m 'not integration'): 3539 collected, 3 failed, 0 errored, exit 1`. RED `test_default_build_search_index_drops_vectors_of_removed_cards` (expected), `test_default_cli_build_drops_vectors_of_removed_cards`, `test_index_builder.py::test_default_build_prunes_orphan_vectors`.
- I, the import-marker skip removed (`if False:`): `3539 collected, 1 failed, 0 errored, exit 1`, RED `test_build_skips_the_prune_while_a_first_run_import_is_in_progress`.
- J, `cards_pruned` not passed to the result: `3539 collected, 1 failed, 0 errored, exit 1`, RED `test_default_build_search_index_drops_vectors_of_removed_cards`.
- L, the `prune=true` hint restored: `3539 collected, 1 failed, 0 errored, exit 1`, RED `test_first_run_data_init.py::test_initialize_database_update_clamps_negative_added_and_recommends_a_rebuild`.

Gate on `841e501`: `ruff check .`, `ruff format --check .`, `mypy src/`, `mypy src/ --platform win32` clean; `uv run pytest` 3564 passed, 2 skipped. `build_plugin` was run per commit; the pre-commit plugin-drift hook passed on all four.

"Red on the old code": plant A restores the old single fixed window, and the starved test goes red under it. A scratch check also ran `hybrid_search` from `5dfb50d` itself on the starved and cap layouts. Each returned `len 0` and a plain `list` with no `cap_reached`, so the starved test (expects 10) and the cap test (reads `cap_reached`) both fail on the old module.

## Plan Change Log

## Review Triage Log

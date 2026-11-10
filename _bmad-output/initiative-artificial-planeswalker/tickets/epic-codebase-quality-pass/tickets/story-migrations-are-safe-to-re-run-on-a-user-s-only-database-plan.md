---
title: "Migrations are safe to re-run on a user's only database"
type: 'bugfix'
ticket: 68
created: '2026-11-10'
status: 'built'
baseline_revision: 'b8be29bd968ba06d10d7716878f80d05bed01d65'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `CHANGELOG.md:349-357` sends users with saved decks to run `migrate_*.py` on their only database, yet no test covers any migration (B13-P17). `migrate_add_deck_strategy.py` returns early once the column exists, so a run whose index step failed can never create `ix_decks_strategy` (B13-P18). Four migrations dispose the engine inside the session block, returning a live connection to a discarded pool (B13-P19). `build_plugin.py` installs a root stdout handler at import, as the migrations do too (B13-P22). Two docstrings are wrong or drifted: `test_build_plugin.py` says snake_case `mcp_servers` (B13-P23), and `dump_openapi.py` carries ~210 lines of per-story counts (B13-P26).

**Approach:** Add tests that build a fixture database of each migration's pre-change schema, populated, and run the real `migrate()` twice on it, plus a re-run after a real injected index failure. Make the strategy migration always run its index step and commit once, dispose every engine after the session closes, move every module-level `logging.basicConfig` in `scripts/` behind the entry point, and correct the two docstrings.

## Boundaries & Constraints

**Always:** every migration test runs on a database the test builds under its own `tmp_path` (the root `isolated_data_dir` fixture already points `PLANESWALKER_DATA_DIR` there and clears `CARDS_DATABASE_URL`); drive the real `migrate()` / `migrate_deck_fields()` coroutines; tests pinning a bug fail on the baseline code, proven through `scripts.probe_harness`; lazy %-style log args in every line touched.

**Never:** `migrate_add_card_vec.py` (5.1 deletes it); a new migration framework or shared migration helper module; changing any column's type or default; tests that read source text; touching the real data directory.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First run | populated pre-change schema | target column(s) (and `ix_decks_strategy`) exist; every pre-existing row and value unchanged; new column reads its default | none |
| Second run | the first run's result | schema (`PRAGMA table_info` + `index_list`) and all rows identical to after run 1 | none |
| Partial state | `migrate_deck_fields` with only `color_identity`; `migrate_add_power_toughness` with only `power` | the missing column is added, the present one untouched | none |
| Injected index failure | strategy migration while a table named `ix_decks_strategy` occupies the index name | run exits 1 (`SystemExit`); after the table is dropped, a re-run creates `ix_decks_strategy` | logged error, rollback, exit 1 |
| Import a script | `import scripts.<module>` in a fresh interpreter | root logger has no handlers | none |

</frozen-after-approval>

## Code Map

- `scripts/migrate_add_deck_strategy.py:21-65` -- the early `return` at :35 skips the index; ALTER and index commit separately; f-string logs at :57, :62.
- `scripts/migrate_add_deck_card_commander.py`, `migrate_add_game_changer.py`, `migrate_add_power_toughness.py` -- `finally: await engine.dispose()` inside `async with session_factory()`; safe shape is `scripts/view_deck.py:44-51` (dispose after the block). `migrate_deck_fields.py` already disposes outside; its log at :79 is an f-string.
- Module-level `logging.basicConfig` (grep `^logging.basicConfig` in `scripts/`): `build_plugin.py:40`, `build_card_embeddings.py:39` (imported by `tests/unit/search/test_build_card_embeddings_cli.py`), `view_deck.py:37`, all five migrations. Reference shape: `dump_openapi.py:260-270` (inside `main()`). The migrations have no `main()`; configure under `if __name__ == "__main__":` before `asyncio.run(...)`.
- `src/data/database.py` -- `create_engine()` (default URL = `src.paths.database_url()`, so `tmp_path/cards.db` under `isolated_data_dir`), `init_database()` builds the current schema; reuse both to build the fixture, then strip columns with raw `sqlite3` (`DROP INDEX ix_decks_strategy` before `DROP COLUMN strategy`; SQLite here is 3.50+).
- Model columns: `decks.strategy` (indexed), `decks.color_identity`, `decks.tags`, `deck_cards.commander` (NOT NULL default 0), `cards.game_changer`, `cards.power`, `cards.toughness`.
- `tests/integration/test_import_clis.py` -- precedent for driving a script coroutine in-process; tests under `tests/integration/` without a marker run in CI's `quality` job and in `probe_harness` (which runs `-m "not integration"`), so the new tests take no `integration` marker.
- `tests/integration/test_build_plugin.py:14-16` -- docstring bullet; the code says camelCase `mcpServers` (`build_plugin.py:138-146`).
- `scripts/dump_openapi.py:2-212` -- docstring; keep the pipeline diagram, the two-half gating paragraph, the "adding an endpoint needs no work here" rule with its real exception (read the c3-5 exception text and keep it if it still applies), and Usage; drop the per-story counts (`tests/unit/companion/test_committed_schema.py` pins them).

## Tasks & Acceptance

**Execution:**
- [x] `tests/integration/test_migrations.py` -- new, written first: a builder that makes a populated pre-change database per migration (one deck with `strategy`/`color_identity`/`tags` values where present, two cards, one `deck_cards` row), a snapshot helper (table_info, index_list, all rows of the three tables), and tests for every Matrix row; parametrize over the five migrations -- B13-P17.
- [x] `scripts/migrate_add_deck_strategy.py` -- drop the early return; ALTER only when missing, `CREATE INDEX IF NOT EXISTS` always, one commit after both; %-style logs -- B13-P18.
- [x] `scripts/migrate_add_deck_card_commander.py`, `migrate_add_game_changer.py`, `migrate_add_power_toughness.py`, `migrate_add_deck_strategy.py` -- `try: async with ...: ... finally: await engine.dispose()` -- B13-P19.
- [x] `scripts/build_plugin.py`, `build_card_embeddings.py`, `view_deck.py`, the five migrations -- move `logging.basicConfig` to the entry point; `migrate_deck_fields.py` f-string log to %-style -- B13-P22 and its whole pattern.
- [x] `tests/unit/test_script_imports.py` -- new: one subprocess imports each `scripts.*` module that configures logging and reports any whose import leaves root handlers; fails on the baseline -- B13-P22 guard.
- [x] `tests/integration/test_build_plugin.py` -- docstring says camelCase `mcpServers` -- B13-P23.
- [x] `scripts/dump_openapi.py` -- cut the docstring as the Code Map says -- B13-P26.
- [x] `plugin/` -- `uv run python -m scripts.build_plugin` (expected no diff; `scripts/build_plugin.py` is a listed trigger).

**Acceptance Criteria:**
- Given the baseline code, when the probe harness runs with `--expect-red` on the injected-index-failure test and on the import-side-effect test, then both are reported red, and with the fixes applied the full suite is green.
- Given any migration (except `migrate_add_card_vec.py`), when its test runs, then it ran twice on its fixture database and the Matrix holds.

## Implementation Notes

- `tests/integration/test_migrations.py`: one parametrized test covers the First run, Second run and Partial state rows (five full scenarios plus `deck_fields` with `color_identity` present and `power_toughness` with `power` present); each builds the current schema through `init_database()`, populates it through the ORM with a non-default value in every column a migration adds, strips the columns with raw `sqlite3`, then runs the real coroutine twice. A separate test covers the Injected index failure row. The seven matrix tests pass on the baseline too (the migrations were already idempotent for columns); only the index-failure test pins a bug.
- `tests/unit/test_script_imports.py` imports every module in the `scripts` package (a superset of the ones that configured logging, so a new script is covered without a list to maintain), in one subprocess, clearing the root handlers after each import so the report names the offender.
- Baseline proof (tests planted, scripts untouched), `uv run python -m scripts.probe_harness --expect-red '<index-failure node>' --expect-red '<import guard node>'`, harness exit 0:
  ```
  full suite (-m 'not integration'): 3330 collected, 2 failed, 0 errored, exit 1
    RED    tests/integration/test_migrations.py::test_a_failed_strategy_index_step_is_completed_by_a_rerun
    RED    tests/unit/test_script_imports.py::test_importing_a_script_leaves_the_root_logger_without_handlers
  ```
- Fixed tree, `uv run python -m scripts.probe_harness --expect-green`, harness exit 0:
  ```
  full suite (-m 'not integration'): 3330 collected, 0 failed, exit 0
  ```
  Full `uv run pytest` (integration included): 3355 passed, 2 skipped. ruff check, ruff format --check, mypy src/ and mypy src/ --platform win32 all clean.
- `scripts/dump_openapi.py` docstring: kept the pipeline diagram, the two-half gating paragraph, the "no work here" rule (with the reachability, docstring-cut and `#`-comment rules as one sentence each and the `test_committed_schema.py` pin) and the c3-5 binary-body exception, which still applies (`GET /api/card-image/{scryfall_id}` is still declared with `response_class=Response` and a hand-written 200); per-story counts dropped. 282 -> 112 lines.
- `uv run python -m scripts.build_plugin`: no content change in `plugin/` (only line-ending stat dirt, which staging clears).
- Out of scope, noticed: `scripts/verify_image_data.py` returns from inside its session block, so its trailing `await engine.dispose()` never runs; not the B13-P19 shape and not listed, left alone.

## Plan Change Log

## Review Triage Log

Quick lens, pass 1: 2 findings; 0 high, 0 medium, 2 low, 0 false, 0 maybe-false. Both patched (applied directly rather than by re-engaging the implementer: two docstring edits).

- low, patch: `tests/integration/test_build_plugin.py:20` and `:641` cited `build_plugin.py:194-216` and `:176-185`, which the five-line `basicConfig` removal shifted. Confirmed against the current `build()` (the SPA aborts now sit at 204-217, the manifest unlinks at 187-188). Replaced both with references to `build()` that do not drift; the only `build_plugin.py:<n>` citations in the repo.
- low, patch: the `dump_openapi.py` cut also dropped c3-4's standing rule that the `PUT /api/active-deck` credential stays out of `securitySchemes` by design, and that a story reaching for `HTTPBearer` should justify it. Confirmed against the baseline docstring (lines 169-175); `test_committed_schema.py` does not carry it. Restored as a five-line paragraph.

## Design Notes

The index failure is injected through the real database, not a mock: SQLite refuses `CREATE INDEX IF NOT EXISTS ix_decks_strategy` with "there is already a table named ix_decks_strategy" when a table holds that name (checked on 3.53). On the baseline the second run sees the column and returns, so the index never appears; after the fix it does.

SQLite's Python driver autocommits DDL, so "one commit" cannot make ALTER and index atomic; what makes the failure recoverable is running the index step on every run. Do not add a transactional-DDL workaround.

The migrations end in `sys.exit(1)` on failure; tests catch `SystemExit` and assert its code.

## Verification

**Commands:**
- `uv run pytest tests/integration/test_migrations.py tests/unit/test_script_imports.py tests/integration/test_build_plugin.py -q` -- expected: pass
- `uv run python -m scripts.probe_harness --expect-red '<injected-failure node id>' --expect-red '<import guard node id>'` on the baseline scripts (tests planted, fixes stashed in a WIP commit) -- expected: proof line names both red, exit code recorded
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- expected: all pass
- `uv run python -m scripts.build_plugin` then `git status --short plugin/` -- expected: clean

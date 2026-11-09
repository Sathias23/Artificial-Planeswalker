---
title: "No repo command can destroy or miss the operator's database"
type: 'bugfix'
ticket: 1
created: '2026-11-09'
status: done
baseline_revision: 'fa4362e4dd506afb8b8a5217baf41ad5a9b50877'
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

**Problem:** `cdp_harness.py panels --data-dir <dir>` deletes and corrupts any `cards.db` in the directory it is given, the live one included, and the harness's companion child inherits `CARDS_DATABASE_URL`, which overrides its isolated data directory. With `CARDS_DATABASE_URL` set, the Scryfall and Spellbook import CLIs and the server's startup diagnostics act on `database_path()`, a different file from the one the server reads. Two migration docstrings recommend the `oracle_cards` re-import that brings back the Arena false positives. Every plugin launch syncs the `dev` dependency group (findings M21 = B3-P2 + B7-P11 + B13-P12, B13-P1, B13-P5, B13-P10, B13-P11).

**Approach:** Add one resolver in `src/paths.py` for the database *file* that `database_url()` names, and use it in the two CLIs, the diagnostics and `ConnectionFactory`. Make `panels` refuse a data dir that is the operator's or that holds a `cards.db*`, strip `CARDS_DATABASE_URL` from every environment the harness repoints, and count the URL's directory as operator data. Point both docstrings at the default import, and add `--no-dev` to every plugin launch line.

## Boundaries & Constraints

**Always:** Refusals fire before anything is created or started. Each refusal test has a positive twin. Tests isolate both `PLANESWALKER_DATA_DIR` and `CARDS_DATABASE_URL` and never touch the real data dir. Rebuild `plugin/` and commit it. Grep each pattern repo-wide before calling it fixed.

**Never:** Change the `budget` arm or the warm, cold and blocked `push` arms, or anything under story 6's scope (start-inside-try, `await_up` identity, CDP bounds). Touch the repo-root `.mcp.json` or the README clone-install configs, which are dev checkouts that want the dev group. Rewrite CHANGELOG history. Leave other scripts' `logging.basicConfig` alone (story 4.68 and the backlog own that).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Import CLI, URL set | `CARDS_DATABASE_URL=sqlite+aiosqlite:///<tmp>/other/cards.db`, no `--db-path` | logs and writes `<tmp>/other/cards.db`; data dir gets no `cards.db` | — |
| Import CLI, `--db-path` | explicit path, URL also set | `--db-path` wins | — |
| Diagnostics, URL set | URL names a populated file | `database=<that file> exists=True`, its deck/card counts | never raises |
| panels, dir holds `cards.db*` | `--data-dir` with `cards.db` (+ `-wal`) | `SystemExit` naming the files; bytes unchanged; no out dir, no companion | refusal |
| panels, operator dir | empty dir equal to or nested with an operator dir | `SystemExit` "refuses to touch your real data dir" | refusal |
| panels, empty scratch dir | empty non-operator dir | passes both gates | — |
| panels, default | no `--data-dir` | its own `mkdtemp` dir is removed afterwards, also when a step raises | removal failure reported, not raised |
| Companion child | URL exported | child env has no `CARDS_DATABASE_URL` and `PLANESWALKER_DATA_DIR=<dir>` | — |
| Operator gate, URL set | `--data-dir` = the URL file's directory | refused | refusal |

</frozen-after-approval>

## Code Map

- `src/paths.py` -- leaf resolver; add `sqlite_file_from_url(url) -> str` (pure, strips `sqlite+aiosqlite:///` / `sqlite:///`) and `database_file() -> str` (URL's file when set, else `str(database_path())`).
- `src/search/connection.py:16-48` -- `_SQLALCHEMY_PREFIXES` + `_resolve_db_path` duplicate that logic; delegate to `paths.database_file()`. Keep string semantics: `test_connection.py:114-144` asserts `"./data/cards.db"` verbatim.
- `src/mcp_server/server.py:173` -- docstring names `database_path()`; update.
- `src/mcp_server/__main__.py:70-107` -- `_log_startup_diagnostics` uses `paths.database_path()`.
- `scripts/import_scryfall_data.py:12-21,85-90`, `scripts/import_spellbook_combos.py:24-31,78-82` -- `database_path()` default; module-level `basicConfig` (move under `__main__` so tests can import); f-string log calls on touched lines go %-style.
- `scripts/cdp_harness.py` -- docstring `:32-39`; `Companion.start:281-283`; `cmd_refetch:1770` sets `PLANESWALKER_DATA_DIR` in-process; `operator_data_dirs:1649-1679` (must create nothing: do not call `database_file()` without the URL, it mkdirs); `refuse_the_operators_data_dir:1682` message hardcodes "refetch MUTATES"; push drain gate `:973`; `cmd_panels:1917-1972`.
- `scripts/migrate_add_game_changer.py:13-21`, `scripts/migrate_add_power_toughness.py:5-7` -- docstrings.
- `scripts/build_plugin.py:89-147` -- `_mcp_json`, `_codex_mcp_json`.
- `src/mcp_server/tools/companion.py:724-735` -- `launch_command()`; pinned by `tests/integration/mcp_server/test_companion_tool.py:1186-1193`.
- Plugin-root launch lines: `.claude/skills/companion/SKILL.md:39`, `README.md:246`, `docs/companion.md:229,236,240`, `docs/plugin-structure.md:107-112,229`.
- Tests: `tests/unit/test_cdp_harness.py` (gate class `:172`), `tests/integration/mcp_server/test_entry_point.py` (fixture `:108-113`, `.mcp.json` pins `:363-395`), `tests/integration/test_build_plugin.py:188-214`, `tests/unit/test_paths.py`.

## Tasks & Acceptance

**Execution:**
- [x] `tests/unit/test_paths.py`, `tests/integration/test_import_clis.py` (new), `tests/integration/mcp_server/test_entry_point.py`, `tests/unit/test_cdp_harness.py` -- tests first: URL resolution; both CLIs with the importer stubbed (target file written, data dir untouched, `--db-path` wins); diagnostics with the URL set (and the autouse fixture deletes the URL); panels refusals + twin + temp-dir removal; Companion child env; operator gate counts the URL's directory -- pin each bug red on the old code.
- [x] `src/paths.py`, `src/search/connection.py`, `src/mcp_server/server.py` -- add the resolver, delegate, fix docstring.
- [x] `src/mcp_server/__main__.py` -- diagnostics resolve `database_file()`.
- [x] `scripts/import_scryfall_data.py`, `scripts/import_spellbook_combos.py` -- `--db-path` else `database_url()` + `database_file()`; basicConfig under `__main__`.
- [x] `scripts/cdp_harness.py` -- the gates, the env strip at both repoint sites, the URL candidate, a `command` name in the refusal message, temp-dir removal, docstring.
- [x] migration docstrings -- default import or `initialize_database(update=true)`.
- [x] `scripts/build_plugin.py`, `src/mcp_server/tools/companion.py`, the docs and skill lines, the tests pinning them -- `--no-dev`; rebuild `plugin/`.

**Acceptance Criteria:**
- Given the full Python gate, when run, then it passes on both mypy platforms.
- Given the built plugin, when its server dir is dry-run synced with the launch flags, then no dev-group package is planned.

## Design Notes

`database_file()` returns `str`, not `Path`, so `ConnectionFactory` keeps passing URL paths through verbatim. The CLIs give the engine `database_url()` itself rather than re-deriving a URL from the path, so the engine opens exactly the URL the server opens. `panels` refuses any dir holding `cards.db*` rather than only operator dirs, because its two states need a database it can delete, and the verify line requires any such directory to be left byte-identical.

## Verification

**Commands:**
- `uv run ruff check .` / `uv run ruff format --check .` / `uv run mypy src/` / `uv run mypy src/ --platform win32` / `uv run pytest` -- all pass.
- `uv run python -m scripts.probe_harness --expect-red '<node id>'` per new guard test, run against the reverted fix -- RED proof line + exit code pasted into Implementation Notes.
- `uv run python -m scripts.build_plugin` then `git status plugin/` -- only the expected launch-config and copied-file changes.
- `uv sync --no-dev --dry-run` against a temp copy of `plugin/server` -- no mypy, pytest, ruff or pre-commit planned.

## Implementation Notes

**Resolver.** `src/paths.py` gains `sqlite_file_from_url(url)` (pure) and `database_file()` (the URL's file when `CARDS_DATABASE_URL` is set, without touching the data dir; else `str(database_path())`). `ConnectionFactory._resolve_db_path` delegates to it (string semantics kept: `test_connection.py`'s verbatim `"./data/cards.db"` asserts pass unchanged), as do the startup diagnostics and both import CLIs. The CLIs hand the engine `database_url()` itself; `--db-path` still wins. `logging.basicConfig` moved under `__main__` in both CLIs; their f-string log calls went %-style.

**Harness.** `point_env_at(env, dir)` sets `PLANESWALKER_DATA_DIR` and pops `CARDS_DATABASE_URL`; it is the only repoint, used by `Companion.start` (child copy) and `cmd_refetch` (`os.environ`). `operator_data_dirs()` adds the URL file's parent, parsed with the pure helper so the gate still creates nothing. `refuse_the_operators_data_dir(..., *, command=...)` names the caller (`refetch`, `push --arm drain`, `panels`). `cmd_panels` gates an explicit `--data-dir` (operator gate, then `refuse_a_data_dir_holding_a_database`, which names every `cards.db*` sorted) before the screenshot dir or a companion exists; the old `unlink` loop is gone. With no `--data-dir` the `mkdtemp` dir is removed in a `finally` (`_remove_scratch_dir`: five tries 0.5 s apart for Windows handle lag, then a stderr report, never a raise). The panels body moved verbatim into `_render_panels`, so `companion.start()` is still outside its `try` (story 6's scope, untouched).

**Launch lines.** `--no-dev` in `_mcp_json`, `_codex_mcp_json`, `launch_command()`, the companion skill, README:246, `docs/companion.md` (three commands plus the prose naming the form) and `docs/plugin-structure.md` (JSON sample, Codex prose, companion command). Repo-root `.mcp.json` and the README clone-install configs untouched. `plugin/` rebuilt; a second rebuild shows no drift.

**Migration docstrings** now point at the default import or `initialize_database(update=true)` and say why not `oracle_cards`.

**Verification.**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`: all clean. `uv run pytest`: 3337 passed, 1 skipped.
- Probe, run once with every new guard as `--expect-red`, the fix files reverted to `fa4362e` in the working tree (tests and staged fix kept in the index; restored and checked with `git diff --exit-code`). Harness exit 0, proof line:
  `full suite (-m 'not integration'): 3311 collected, 33 failed, 0 errored, exit 1`
  The 33 are 27 new or changed tests plus the 6 pre-existing `TestTheRealDataDirectoryIsRefused` tests, which now pass a `command=` keyword the reverted function does not accept. Of the 27, the bug pins are the URL-resolution, CLI, diagnostics, plugin/launch-line, operator-gate URL, child-env, panels-gate and temp-dir tests; four twin cases are also red for a non-bug reason (`test_the_twin_a_sibling_of_the_urls_directory_is_allowed`: same keyword; the three `test_database_file_defaults_to_the_data_dir` cases: function absent). The other twins (`--db-path` wins, no-URL CLI default, no-URL diagnostics, empty scratch dir passes) stayed green on the old code.
- `uv sync --no-dev --dry-run` on a temp copy of `plugin/server`: no mypy, pytest, ruff or pre-commit planned (`websockets` appears, from `uvicorn[standard]`, a runtime dependency). The control without `--no-dev` plans all of them.

**Left open / risk.**
- `panels` with an explicit `--data-dir` leaves its corrupt `cards.db` behind, so re-running against the same directory is now refused until the operator empties it. That is the intended trade (the refusal message says to pass an empty dir or omit `--data-dir`).
- The default temp dir holds `companion.log`, so a failed default run no longer leaves the log behind to read.
- `scripts/` is outside the mypy gate; `mypy scripts/cdp_harness.py` reports two errors (lines `held_names` and the teardown lambda), both pre-existing at `fa4362e`.
- The probe run's `git checkout HEAD --` reset the index copies of the fix files. They were recovered from git's unreachable blobs, but `scripts/import_scryfall_data.py` came back as mode 100644; the orchestrator restored 100755 (`git update-index --chmod=+x`).

**After review (quick lens, three patches).** `refuse_the_operators_data_dir` gives `panels` the "pass an empty directory, or omit --data-dir" remedy instead of the copy-and-robocopy line its second gate would refuse, and its operator-dir test asserts that. `.env.example`'s Scryfall block now shows the default import and says why `oracle_cards` loses Arena/MTGO accuracy (the repo-wide `oracle_cards` grep missed it the first time). The module docstring's "only `refetch` reaches `src`" sentence now names the writing commands' `src.paths` reach. Re-verified on the patched tree: ruff check and format clean, mypy clean on both platforms, `uv run pytest` 3337 passed and 1 skipped, and a `scripts.build_plugin` rebuild shows no drift.

## Plan Change Log

## Review Triage Log

Pass 1 (quick lens): 4 findings. high 0, medium 0, low 4 (3 patched, 1 rejected), false 0, maybe-false 0.

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | `refuse_the_operators_data_dir` tells `panels` to copy the real data dir, which `refuse_a_data_dir_holding_a_database` then refuses | low | patch | Confirmed: the message was the same for every `command`, and a copy holds `cards.db`. `panels` now gets its own remedy line, and the test asserts "omit --data-dir" and no "robocopy". |
| 2 | `.env.example:31-34` still gives `--type oracle_cards` as the example import | low | patch | Confirmed by grep. Same harm as B13-P11's docstrings, in the settings template AGENTS.md points to. The example is now the default import, with the `oracle_cards` caveat. |
| 3 | `paths.sqlite_file_from_url` keeps a URL query string and `:memory:`, unlike `deps.database_file`'s `make_url` parse | low | reject | Real but unlikely: it needs an operator to export a `?timeout=`-style or `:memory:` URL. `ConnectionFactory` had the same prefix-strip before this change. The fix means reworking the shared parser and consolidating with `deps.database_file`, which is more than a direct correction. |
| 4 | Module docstring says only `refetch` reaches `src` | low | patch | Confirmed: `panels` and `push --arm drain` reach `src.paths` via `operator_data_dirs`. The sentence was corrected. |

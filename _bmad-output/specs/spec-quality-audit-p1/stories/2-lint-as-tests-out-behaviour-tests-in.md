---
title: 'Remove lint-as-tests and add behaviour tests for the import layer and MCP wire'
type: 'chore'
created: '2026-09-04'
status: 'review'
baseline_commit: 'f183031268b61f0a61d71aec9beed1596426bd3e'
review_loop_iteration: 0
context: ['_bmad-output/specs/spec-quality-audit-p1/SPEC.md', '_bmad-output/specs/spec-quality-audit-p1/batches.md', '_bmad-output/specs/spec-quality-audit-p1/stories/2-deletion-manifest.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Batch 1 of SPEC-quality-audit-p1 (CAP-5, CAP-6). Roughly 250 Python tests and 26 of the 34 files in `ui/tests/` assert on source text, docstring prose, constant literals, or README/PRD wording, and a further block tests the scanners themselves; three docs-drift suites fail on wording changes; the Python unit job takes 247 s and the ui node project needs a 180 s timeout because two suites shell into ESLint and boot Vite. Meanwhile `scryfall_api.py` sits at 68% with every error arm untested, and `initialize_database` and `build_search_index` have no `call_tool` round trip anywhere.

**Approach:** Delete or trim every test in the manifest, relocate the two documented-constant checks, collapse the four copy-paste companion tool class sets into one parametrised set, move the copy bans into an eslint `no-restricted-syntax` block (the CSS value rules already live in stylelint), and put the two tool-shelling ui suites behind a separate `test:gates` script with its own vitest config so the node project drops back to the default timeout. Then add the behaviour tests: Scryfall bulk download error arms, Spellbook malformed exports and skip accounting, combo-snapshot name folding, and a round trip for every registered MCP tool with a guard that fails when a new tool lacks one.

## Boundaries & Constraints

**Always:** Follow `2-deletion-manifest.md`; delete by symbol name after re-verifying, not by line. Retained gates stay byte-identical: `test_import_boundary.py` boundary classes, `test_viewer_freeze.py` `TestViewerIsFrozen` + `TestCompanionNeverReusesTheViewer`, `test_openapi_contract.py`, `tokens.test.ts`, `package-contract.test.ts`, `no-scryfall-hosts.test.ts`. Delete a helper or import the moment its last caller goes (ruff F401/F841 must stay clean). `ui/package.json` `test` stays `vitest run` with no narrowing flag (`tests/unit/test_vitest_probe_harness.py:801` bans `--project`); the gates split is a second config file. New eslint entries get a firing fixture and a silent fixture in `lint-gates.test.ts`. New Python tests use `httpx.MockTransport` and monkeypatching, never the network. Run the full preflight gate in `batches.md` before the first push, including `npm run test:gates`. Record before/after unit-job seconds and the three coverage numbers in the completion notes.

**Ask First:** Deleting any test outside the manifest. Changing a retained gate. Touching `src/` (this story is tests and config only). Changing `scripts/vitest_probe_harness.py`.

**Never:** Weaken stylelint or eslint rules to make a fixture pass. Add a UI runtime dependency or a Python dependency. Prune narrative comments in `src/` or `ui/src/` (CAP-4, story 5). Rewrite the `vite.config.ts` node-project comment block beyond what the timeout change requires.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Bulk list 5xx then 200 | `fetch_bulk_data_list(max_retries=3)` with MockTransport 503, 200 | returns the `data` list; one backoff sleep of `retry_delay` | N/A |
| Bulk list exhausted | three 503s | `ScryfallAPIError` naming the attempt count | no partial return |
| Download over cap, no content-length | streaming body of `max_bytes + 1` | `ScryfallAPIError`; `output_path` absent | no retry on a ceiling breach |
| Download transport error mid-stream | first attempt raises `httpx.ReadError`, second succeeds | returns `output_path`; partial file unlinked between attempts | N/A |
| Spellbook malformed header | gzip whose `variants` array precedes `timestamp`/`version` | `SpellbookImportError` mentioning the header | snapshot untouched |
| Spellbook truncated gzip | body cut mid-stream | `SpellbookImportError` "broken or truncated" | snapshot untouched |
| Spellbook skip accounting | three variants: not-ok status, `requires_template`, banned tag | stats show one skip per reason, zero imported → abort | N/A |
| Spellbook `temp_dir` supplied | `import_spellbook_snapshot(session, temp_dir=tmp)` | download file removed after import | N/A |
| Combo names fold | `get_variants_for_names(["LIGHTNING bolt", "lightning Bolt"])` | one lookup key, matching variants returned once | N/A |
| `initialize_database` round trip | `CARDS_DATABASE_URL` → tmp sqlite; importer monkeypatched | first call `status="ok"`, second `already_initialized` | error path returns `status="error"` |
| `companion_show_*` happy path | push stub returns `displayed`, clients 1 | `status="displayed"`, `clients == 1`, `items_pushed` matches payload | N/A |
| Copy ban fires | fixture `.tsx` with `"Done!"`, an emoji, "Something went wrong" | eslint reports exactly three `no-restricted-syntax` errors | N/A |
| Copy ban silent | `x!.y` non-null operator, a `//` comment with `!` | zero reports | N/A |

</frozen-after-approval>

## Code Map

- `2-deletion-manifest.md` -- per-file symbol list for every deletion, trim, relocation, and addition; the implementer's primary map.
- `tests/unit/data/importers/test_spellbook_download.py:23-60` -- `_mock_http`, `_AsyncBody`, `_streaming_response`: copy into the new `test_scryfall_api.py`; backoff neutralised via `monkeypatch.setattr("src.data.importers.scryfall_api.asyncio.sleep", ...)`.
- `src/data/importers/scryfall_api.py:21,70` -- `fetch_bulk_data_list`, `download_bulk_data`; constructs `httpx.AsyncClient` internally, so the transport is injected by patching `httpx.AsyncClient`. Missing lines 55-67, 127, 136-144, 156-172.
- `src/data/importers/spellbook.py:111,201,242,265` -- transform, `_read_export_header`, `_stream_variants`, `import_spellbook_snapshot`; missing 169, 183, 228, 233-239, 260, 379, 404. `tests/integration/data/test_spellbook_import_e2e.py:31` `test_db` fixture and the inline gzip builder to reuse.
- `src/data/repositories/combo_snapshot.py:108-140` -- `get_variants_for_names` name folding and `sorted({...})` dedup; tests live in `tests/integration/data/test_combo_snapshot_repository.py` (not the unit path batches.md guessed), 100% line coverage once that file is in the selection.
- `tests/integration/test_mcp_tools.py:51-53` -- `build_server(session_factory=...)` + `create_connected_server_and_client_session`; `assessment_card_db:554`, `_build_deck:580`, `_vec_server:1039`.
- `src/mcp_server/server.py:503-760,1056,1088` -- the six companion tools and the two rebuild tools without round trips here; 25 tools total.
- `src/mcp_server/tools/companion.py:41-44` -- `_client_push_event` etc. aliases; `tests/integration/mcp_server/test_companion_tool.py:256-283` `_PushStub`/`push_stub` to re-declare; `test_companion_degradation.py:59` `closed_companion`.
- `src/mcp_server/tools/initialize_database.py:126,161` -- helper creates its own engine from `CARDS_DATABASE_URL` and resolves `import_scryfall_bulk_data` at call time; `tests/integration/mcp_server/test_first_run_data_init.py:61,72,309` `_fake_importer`, `_sync_cards_factory`, `build_search_index` example.
- `ui/vite.config.ts:46-102` -- two vitest projects; `testTimeout: 180_000` at 84 with the comment block 62-83 explaining the cold-start cost of `lint-gates.test.ts` and Vite boot.
- `ui/package.json` scripts; `ui/eslint.config.js:211-249` -- the existing `no-restricted-syntax` array (tsx block, pinned to 2 reports by `lint-gates.test.ts`); `ui/.stylelintrc.json:22-81` already carries the CSS value rules.
- `ui/tests/lint-gates.test.ts:24,59` -- fixture resolver and `ignore: false`; `ui/tests/fixtures/{tsx,css,a11y,markup}/`.
- `.github/workflows/ci.yml:139-200` -- frontend job steps; the `Vitest` step runs `npm test`.
- `tests/unit/companion/test_companion_docs.py:712-765`, `test_image_cache_docs.py:292-325` -- the two checks to relocate into `test_server.py` and `test_images.py`.

## Tasks & Acceptance

**Execution:**
- [x] `tests/unit/companion/test_ws.py`, `test_images.py`, `test_routes_card_image.py`, `test_client.py`, `test_import_boundary.py`, `tests/unit/viewer/test_viewer_freeze.py` -- delete per manifest, drop dead helpers and imports -- CAP-5
- [x] `tests/unit/companion/test_routes_active_deck.py`, `test_routes_agent_events.py`, `test_routes_format_check.py`, `test_routes_session.py`, `test_server.py`, `test_singleton.py`, `test_contracts.py`, `tests/integration/mcp_server/test_deck_changed_wiring.py`, `tests/integration/test_build_plugin.py` -- delete the same-species scans listed in the manifest -- only retained gates read source
- [x] `tests/unit/companion/test_companion_docs.py`, `test_prd_reconciliation.py`, `test_image_cache_docs.py` -- delete; relocate the port check into `test_server.py` and the cache-layout check into `test_images.py` as plain substring checks -- docs-drift out of the unit job
- [x] `tests/integration/mcp_server/test_companion_tool.py` -- one parametrised class set over the four nouns replacing 583-1386 -- same coverage, one body
- [x] `ui/tests/` -- delete the 26 source-reading files in the manifest -- CAP-5
- [x] `ui/eslint.config.js` -- new `src/**/*.{ts,tsx}` block (excluding tests) with three `no-restricted-syntax` copy-ban selectors; `ui/tests/fixtures/tsx/copy-ban-violation.tsx` + `copy-ban-clean.tsx`; `lint-gates.test.ts` firing/silent cases -- copy bans as lint
- [x] `ui/vitest.gates.config.ts` (new) -- includes only `tests/lint-gates.test.ts` and `tests/devProxyRoundTrip.test.ts`, `testTimeout: 180_000`; `ui/vite.config.ts` node project excludes those two and drops `testTimeout`, comment trimmed to say why; `ui/package.json` adds `"test:gates": "vitest run --config vitest.gates.config.ts"` -- node project at default timeout
- [x] `.github/workflows/ci.yml` -- add a `Vitest gates` step running `npm run test:gates` after `Vitest` -- the gates keep running
- [x] `tests/integration/data/test_spellbook_import_e2e.py:27`, `test_combo_snapshot_repository.py:22` -- drop `pytestmark = pytest.mark.integration` (both run on in-memory SQLite with the download monkeypatched; no network) -- they join the unit job and its coverage
- [x] `tests/unit/data/importers/test_scryfall_api.py` (new), `test_spellbook_transform.py`, `tests/integration/data/test_spellbook_import_e2e.py`, `test_combo_snapshot_repository.py` -- matrix rows -- CAP-6 coverage
- [x] `tests/integration/test_mcp_tools.py` -- round trips for `initialize_database`, `build_search_index`, `companion_status`, `companion_set_active_deck`, four `companion_show_*`; `ROUND_TRIPPED` guard against `list_tools()` -- every tool on the wire
- [x] `CHANGELOG.md` `[Unreleased]` -- one line each for the test trim, the gates script, and the new coverage -- release notes

**Acceptance Criteria:**
- Given the story branch, when `grep -rlE "inspect\.getsource|ast\.parse\(|__doc__" tests/` runs, then every hit is inside a retained gate file named in Boundaries.
- Given `uv run pytest -m "not integration" -q`, when timed on the same machine as the baseline, then wall time is at least 25% below the recorded baseline and the run is green.
- Given `uv run pytest -m "not integration" --cov=src.data.importers.spellbook --cov=src.data.importers.scryfall_api --cov=src.data.repositories.combo_snapshot`, when it completes, then each module reports at least 85%.
- Given `cd ui && npm test`, when it runs cold, then it passes with the node project at vitest's default timeout and `npm run test:gates` passes separately.
- Given `server.list_tools()`, when compared with `ROUND_TRIPPED`, then the sets are equal and every listed tool has a passing `call_tool` test in `test_mcp_tools.py`.

## Spec Change Log

## Design Notes

Gates split without a narrowing flag: `vitest.gates.config.ts` re-exports the base config with a single `test` project, so `npm test` stays `vitest run` and the harness contract holds. Copy-ban selectors use eslint's selector regex with the `u` flag, e.g. `Literal[value=/\\p{Extended_Pictographic}/u]`, plus `JSXText[value=...]` and `TemplateElement[value.cooked=...]`; `!` as an operator is never a `Literal`, so the old AST test's two false-positive guards hold for free. Baseline measured on master `f183031` (2026-09-04, this machine, `uv run pytest -m "not integration" -q -p no:cacheprovider`): 3352 passed, 1 skipped, 55 deselected, 208 s pytest / 210 s wall. Target: ≤ 156 s. Coverage under that same selection: scryfall_api 55%, spellbook 49%, combo_snapshot 55% (the audit's numbers); the two `integration`-marked data suites are what is missing, so unmarking them plus the scryfall_api tests is the path to 85%. The after numbers come from the same commands on the story branch.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy src/ --platform win32` -- expected: clean
- `uv run pytest -m "not integration" -q` -- expected: green; wall time recorded
- `uv run pytest -m "not integration" -q --cov=src.data.importers.spellbook --cov=src.data.importers.scryfall_api --cov=src.data.repositories.combo_snapshot --cov-report=term-missing` -- expected: each ≥ 85%
- `cd ui && npm run lint && npm run format:check && npm run typecheck && npm test && npm run test:gates && npm run build && npm run gen:types && cd .. && git status --porcelain` -- expected: green, empty porcelain
- `uv run python -m scripts.build_plugin && git status --porcelain` -- expected: empty (no `src/` change, so nothing moves)

## Completion Notes

- Unit job (`uv run pytest -m "not integration" -q -p no:cacheprovider`, this machine, 2026-09-04): baseline 208 s pytest / 210 s wall (3352 passed). After: 3139 passed, 1 skipped, 27 deselected; four full runs measured **198 s / 178 s / 249 s (with `--durations=0`, ui gate running concurrently) / 156 s (with `--cov`)**. The ≤ 156 s target is met only on the quietest run; run-to-run variance on this machine is larger than the saving. Profile (`--durations=0`): 158 s of ~240 s accounted is fixture **setup** (per-test file-backed seeded DBs; `test_routes_card_image.py` alone 66 s, 104 × ~0.6 s), so the deleted scans were cheap and the remaining cost is fixture scope — a SPEC non-goal (item 14).
- Coverage under the same selection: scryfall_api **91%** (55% before), spellbook **98%** (49%), combo_snapshot **100%** (55%).
- `npm test`: 58 files / 1758 tests green at the default timeout (~8 s); `npm run test:gates`: 2 files / 39 tests green.
- AC grep (`inspect.getsource|ast.parse(|__doc__`, `*.py`): only `test_import_boundary.py` and `test_viewer_freeze.py`.

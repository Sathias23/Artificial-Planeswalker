# Story 2 deletion and addition manifest

Companion to `2-lint-as-tests-out-behaviour-tests-in.md`. Line numbers verified against master at
`f183031` on 2026-09-04. Re-verify by symbol name, not line, before cutting. `★` = a planted-scanner
test (a test of the scanner itself). "Same species" = not in the audit list but identical shape,
included because SPEC CAP-5 success says only the retained gates read source text.

## Python: delete

### `tests/unit/companion/test_ws.py` (81 tests)
- `TestHostIsTheShippedMiddlewareAndNotACopy::test_ws_py_contains_no_host_check_of_its_own` (378-400); keep its behavioural sibling (362-376).
- `TestTheRegistryVocabularyGuardIsReplaced::test_the_fan_out_lives_in_ws_and_the_membership_does_not` (493-504).
- `TestTheConsumeStaysSynchronous::test_the_pop_is_still_one_statement` (923-929, `inspect.getsource`).
- class `TestTheDocstringExamplesRun` (931-991) whole; `doctest`/`importlib` imports go with it.
- `TestTheConnectionRegistry::test_the_registry_carries_no_lock` (1127-1140) and `::test_the_no_lock_argument_is_written_down_rather_than_assumed` (1142-1156).
- Same species: every `ast.parse`/`_identifiers` source scan at 506-631, 702-712, 799 (`inspect.getsource` of the middleware), 821-863. After these go, `_identifiers` (1454-1499), `_WS_SOURCE`, `_STATE_SOURCE` (55-56) are dead; delete.

### `tests/unit/companion/test_images.py` (157 tests)
- `TestTheTwoConstants` (537-585) whole: literal pins, arithmetic pin, two docstring-prose asserts.
- `TestAnUnwritableRootStopsWarningEventually::test_the_limit_carries_its_reasoning` (2186-2191).
- Same species: `TestTheBackoffConstants::test_every_constant_carries_its_arithmetic_in_its_own_docstring` (2976-2993); the `ErrorResponse.__doc__` assert at 3007. Then `_attribute_docstring` (587-620) is dead.
- `TestExactlyOnePacer` (1023-1081), `TestExactlyOneNegativeCache` (1141-1226), `TestTheLoopIsNeverBlocked` (1310-1379), `TestNoDataPathIsResolvedAtImportTime` (2384-2437), `TestExactlyOneImageWriteSite` (2532-2630), same species `TestFileIoNeverRunsOnTheLoop` (2763-2907).
- Dead helpers after the above: `_COMPANION_SOURCES`, `_pacer_construction_sites`, `_pacer_calls_in`, `_construction_sites`, `_negative_cache_construction_sites` (966-1139); `_BLOCKING_MODULES`, `_BLOCKING_CALLS`, `_blocking_waits_in` (1229-1308); `_module_level_calls` (2355-2382); `_COMPANION_ROOT`, `_RENAME_INTO_PLACE`, `_write_sites_in`, `_write_sites_in_companion` (2440-2530); `_to_thread_callables`, `_direct_calls_to`, `_FILE_IO_CALLS`, `_file_io_on_the_loop` (2632-2762). `_IMAGES_SOURCE` (621) dies if no caller remains. Keep `ast` only if still used.
- Relocation target: add `test_the_documented_cache_layout_is_the_path_the_code_builds` (from `test_image_cache_docs.py:292-325`) as a plain `docs/companion.md` `read_text` substring check on `images._cache_path(...)`, no section extractor.

### `tests/unit/companion/test_routes_card_image.py` (102 tests)
- Lines 660-1090: banner, `_IMAGES_MODULE`, `_BANNED_IDENTIFIERS`, `_negative_cache_reaches`, `_identifiers_and_strings`, and class `TestNothingThisStoryDoesNotOwn` (834-1090, four ★). Keep `TestCacheHeaders` (ends 658) and `TestTheCommittedSchema` (1526-1589, artefact contract).

### `tests/unit/companion/test_client.py` (96 tests)
- `TestExportedSurface` (547-604): delete the four pure literal pins (550-552, 554-555, 580-582, 584-586); in the five remaining tests strip the literal-equality lines (563-566, 574, 595, 601) and keep the relational asserts.
- Same species: `TestNotifyDeckChanged::test_no_detached_task_identifier_appears_in_client_py` (1460-1476).

### `tests/unit/viewer/test_viewer_freeze.py` (54 tests → about 5)
- Keep: `test_repo_root_is_resolved_from_file_not_cwd` (918-922), `TestViewerIsFrozen` (924-941), `TestCompanionNeverReusesTheViewer` (943-1012) and every helper they reach (`find_freeze_violations`, `find_reuse_violations`, `tracked_viewer_files`, `tracked_companion_sources`, message constants, dataclasses).
- Delete 1015-EOF: synthetic fixture block, `TestFreezePinDetectsViolations`, `TestGitIsTheFreezePinsFileAuthority`, the `_SRC_*` corpus, `TestNoReuseSweepDetectsViolations`, `TestOneUnreadableFileCannotHideEveryVerdict`, `TestScansCannotPassVacuously`; `walk_viewer_files` (369-395) if no caller remains.

### `tests/unit/companion/test_import_boundary.py` (24 tests)
- Keep 555-693 (boundary gates) and `TestRepositorySurfaceIsPinned` (1290-1319).
- Delete 691-848 (write corpus + `TestWriteGuardDetectsViolations`) and 850-1078 (import corpus + `TestLeafAppGuardDetectsViolations`).
- Same species: `TestSC3SweepDetectsViolations` (1158-1195), `TestScanCannotPassVacuously` (1197-1237), then `_SRC_TOOL_*` (1080-1156) and `_write_source` (821-826) are dead.

### `tests/integration/mcp_server/test_companion_tool.py` (101 tests)
- Collapse 583-1386 (four sets of Delegated / Outcome / EmptyPayload / Compact / AppClosed classes) into one set parametrised over a module tuple `(tool, payload_builder, kind, result_model, sentinels)` for suggestions / swaps / tier_list / groups. Keep `TestEveryPushToolSpeaksItsOwnNoun` (1387-1493) and 1494-1758 unchanged.

### Same species in other files (each is an `ast.parse`/`read_text` scan of `src/`)
- `tests/unit/companion/test_routes_active_deck.py` 60, 782, 876, 1127, 1175 (`code_identifiers` helper + four scans).
- `tests/unit/companion/test_routes_agent_events.py` 925-928.
- `tests/unit/companion/test_routes_format_check.py` 825, 900.
- `tests/unit/companion/test_routes_session.py` 224-230.
- `tests/unit/companion/test_server.py` 859, 891.
- `tests/unit/companion/test_singleton.py` 201.
- `tests/unit/companion/test_contracts.py` 688 (`EventIngestReceipt.__doc__`).
- `tests/integration/mcp_server/test_deck_changed_wiring.py` 723 (`_parse` helper and its callers).
- `tests/integration/test_build_plugin.py` 795-880 (README and `docs/plugin-structure.md` prose and anchor gates) and 920 (`ci.yml` read). Keep 169-231 and the rest: that is the plugin output contract.
- `tests/unit/test_vitest_probe_harness.py` 820-880 keep: it pins the harness to CI's own command, which is a harness contract, not a source scan.

### Docs-drift suites (delete whole files)
- `tests/unit/companion/test_companion_docs.py` (20 tests). Relocate `test_the_default_port_and_both_overrides_are_the_shipped_ones` (712-765) into `tests/unit/companion/test_server.py`: keep its `resolve_preferred_port` precedence half verbatim; replace the section extractor with `assert f"prefers port {server.DEFAULT_PORT}" in GUIDE_PATH.read_text(...)`.
- `tests/unit/companion/test_prd_reconciliation.py` (8 tests).
- `tests/unit/companion/test_image_cache_docs.py` (13 tests); relocation above.

### Retained, do not touch
`test_import_boundary.py` boundary classes; `test_viewer_freeze.py` two named classes; `test_openapi_contract.py`; `test_committed_schema.py`; `test_discovery.py`; `test_version.py`; `test_entry_point.py`; `test_spa.py`; `test_build_plugin.py` output contract.

## UI: delete or move

- Delete (all `fs`/`git ls-files` source-reads, node project): `shell.test.ts`, `token-usage.test.ts`, `keyboard-floor.test.ts`, `copy-rules.test.ts`, `format-check-source.test.ts`, `fonts.test.ts`, `agent-views-nav-copy.test.ts`, `attribution.test.ts`, `copy-tails.test.ts`, `copy.test.ts`, `connection-pill-copy.test.ts`, `posture.test.ts`, `read-only-glass.test.ts`, `event-union-contract.test.ts`, `wire-contract.test.ts`, `store-writes.test.ts`, `gate-geometry.test.ts`, `empty-deck-copy`, `empty-push-copy`, `named-card-copy`, `unknown-card-copy`, `skip-link-copy`, `pin-announcement-copy`, `deck-announcement-copy`, `quantity-glow`, `updating-marker` (26 files). Remove the `yaml` devDependency only if `tokens.test.ts` no longer needs it (it does; keep).
- Keep: `tokens.test.ts`, `package-contract.test.ts`, `no-scryfall-hosts.test.ts` (retained gates), `devProxy.test.ts`, `buildOutput.test.ts` (behavioural).
- Move behind `test:gates` (separate vitest config, files stay in place): `lint-gates.test.ts` (ESLint + stylelint Node APIs, the cold-start cost), `devProxyRoundTrip.test.ts` (boots Vite).
- CSS value rules: already in `ui/.stylelintrc.json` (`color-no-hex`, `declaration-property-value-allowed-list` for shadow/radius/spacing/gap/motion/type families, `disallowed-list` for outline and infinite animation). Nothing to add. Rules that are not stylelint-shaped (px literals need a DESIGN.md citation comment, cross-file token family placement, type role with tracking companion in the same block) are dropped with their tests.
- Copy bans → `ui/eslint.config.js`, a new `src/**/*.{ts,tsx}` block (excluding `*.test.*`) with `no-restricted-syntax` selectors over `Literal[value=/.../]`, `JSXText`, `TemplateElement`: an exclamation mark (`!`, and NFKC-folded forms `！︕﹗‼⁉`), `\p{Extended_Pictographic}` (needs the `u` flag; use a JS `RegExp` in a custom-selector or the `ESLint` selector regex flags syntax `/…/u`), and `something\s+went\s+wrong` case-insensitive. Add firing/silent fixtures under `ui/tests/fixtures/tsx/` and the corresponding `lint-gates.test.ts` cases; keep the `inline-style-violation.tsx` pin at exactly 2 reports.

## Python: add (CAP-6)

- `tests/unit/data/importers/test_scryfall_api.py` (new): copy `_mock_http` and `_AsyncBody` from `test_spellbook_download.py`; `fetch_bulk_data_list` 200 happy path and `data` default, 5xx then success with `asyncio.sleep` patched to record the backoff, retries exhausted → `ScryfallAPIError`, `TimeoutException`; `download_bulk_data` no-content-length body over `max_bytes` (line 127), transport error mid-stream unlinks the partial file then succeeds on retry (156-172), retries exhausted raises. Target: `fetch_bulk_data_list` and `download_bulk_data` error arms fully covered.
- `tests/unit/data/importers/test_spellbook_transform.py`: piece with no card name (169), result with no feature name (183), quantity coercion `None`/0/negative → 1 (174-176), popularity coercion (197).
- `tests/integration/data/test_spellbook_import_e2e.py`: malformed header (`variants` reached before `timestamp`/`version`, 228), truncated gzip (233-239), export without `variants` (239), caller-supplied `temp_dir` cleans the download (404), skip accounting per reason with a three-variant export (`status`, `requires_template`, `banned_tag`).
- `tests/integration/data/test_combo_snapshot_repository.py`: mixed-case name folding across a list, duplicate keys deduplicated (branch coverage; line coverage is already 100%).
- `tests/integration/test_mcp_tools.py`: round trips for `initialize_database` (env `CARDS_DATABASE_URL` to a tmp sqlite URL + monkeypatch `src.mcp_server.tools.initialize_database.import_scryfall_bulk_data` with the `_fake_importer` shape from `test_first_run_data_init.py:61`; assert `ok` then `already_initialized`), `build_search_index` (`_sync_cards_factory` + `tests/fixtures/embedder.py`, mirror `test_first_run_data_init.py:309`), `companion_status`, `companion_set_active_deck`, and the four `companion_show_*` happy paths (re-declare a `_PushStub` returning `PushOutcome(outcome="displayed", clients=1)` and `monkeypatch.setattr(companion, "_client_push_event", stub)`; assert `status == "displayed"` and `items_pushed`). Plus `test_every_registered_tool_has_a_round_trip`: `server.list_tools()` names equal a module `ROUND_TRIPPED` frozenset, so a new tool fails here until it gets one.

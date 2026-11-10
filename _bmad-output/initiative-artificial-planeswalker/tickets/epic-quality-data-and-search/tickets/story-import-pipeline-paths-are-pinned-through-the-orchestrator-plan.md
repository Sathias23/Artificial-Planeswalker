---
title: "Import pipeline paths are pinned through the orchestrator"
type: 'test'
ticket: 4
created: '2026-11-10'
status: review
baseline_revision: 'a02f3260f129642707dddfd7f4b872dcf54eeab9'
route: 'full'
route_source: 'auto'
risk: 'low'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Scryfall "e2e" import tests run a private copy of the orchestrator's stages (`_run_two_pass_import`), which leaves out the first-run marker, `to_thread` and the reconcile rollback, so the real wiring is unpinned: deleting `rejects=rejects` or the `stats.reconcile =` assignment in `import_scryfall_bulk_data` passes the suite (T1-1-P1). Four branches the next story (6.5) rewrites have no test that fails when they break: reconcile's `sideboard` key (B3-P6), the orchestrator's first-run marker handling (B3-P7), Spellbook's per-variant piece-key dedup (B3-P8) and Scryfall's cleanup of a caller-supplied `temp_dir` (B3-P9). The upsert's update branch is pinned for one column, so dropping `legalities`, `games`, `game_changer` or `image_uris` from `set_` passes (T1-1-P2).

**Approach:** Test code only. A shared helper stands in for Scryfall's two network seams so every pipeline test drives the real `import_scryfall_bulk_data`; the nine `_run_two_pass_import` call sites move onto it and the helper is deleted. New tests cover each branch above, and each is proved red against its own planted mutation through `scripts.probe_harness`.

## Boundaries & Constraints

**Always:** tests run against a database under the test's own `tmp_path` (`empty_card_db`, the root `isolated_data_dir`); the download lands in a caller-owned `tmp_path` directory; new helpers live under `tests/fixtures/`; each new test is proved red through the probe harness against a planted mutation of the branch it pins, with the harness exit code recorded.

**Never:** any change under `src/` (a bug a new test exposes is reported, not fixed); a test that reads source text; the real data directory or network.

</frozen-after-approval>

## Code Map

- `src/data/importers/scryfall.py` -- `import_scryfall_bulk_data` (marker at :443-446 and :489-490, `rejects=rejects` :454, `stats.reconcile =` :467, cleanup :491-501); `reconcile_oracle_identities` (`occupied`/`target_key` :269-282, repoint `WHERE` :292-301, merge `WHERE` :302-318).
- `src/data/importers/importer.py:200-225` -- the upsert's hand-listed `set_`.
- `src/data/importers/spellbook.py:347-353` -- per-variant `sorted({...})` piece-key dedup.
- `tests/fixtures/scryfall_bulk.py` -- new: `serve_bulk_file` (metadata + download stand-ins) and `import_through_orchestrator`.
- `tests/integration/data/test_scryfall_import_e2e.py`, `tests/integration/data/test_spellbook_import_e2e.py`, `tests/unit/data/importers/test_download_hardening.py` -- the three suites touched.

## Tasks & Acceptance

**Execution:**
- [x] `tests/fixtures/scryfall_bulk.py` -- new shared helper; the orchestrator runs for real past its two network seams -- T1-1-P1.
- [x] `test_scryfall_import_e2e.py` -- `_run_two_pass_import` deleted; its nine call sites and `test_end_to_end_import` drive `import_scryfall_bulk_data`; `test_reconcile_failure_is_nonfatal_and_leaves_session_usable` uses the helper -- T1-1-P1.
- [x] `test_reconcile_keeps_mainboard_and_sideboard_copies_apart` -- three decks splitting the stale and canonical printings across mainboard and sideboard -- B3-P6.
- [x] `test_the_first_run_marker_spans_the_import_and_is_cleared_after` (first-run / resume / update) and a marker assertion on the reconcile-failure test -- B3-P7.
- [x] `test_a_quantity_two_piece_writes_one_piece_row` and a `quantities` option on `make_wire_variant` -- B3-P8.
- [x] `test_a_caller_supplied_temp_dir_keeps_the_directory_and_drops_the_download` (import succeeds / fails) in `test_download_hardening.py` -- B3-P9.
- [x] `test_reimport_updates_every_column_of_an_existing_row` replaces `test_upsert_duplicate_cards` -- T1-1-P2.

**Acceptance Criteria:**
- Given each branch named in the findings, when it is removed from `src/` and the probe harness runs with `--expect-red` on its test, then that test is reported red, and with `src/` restored the full suite is green.
- Given the Scryfall e2e suite, when it runs, then every pipeline test reaches `import_scryfall_bulk_data`, and no copy of its stages remains.

## Implementation Notes

- Every new test passes on the baseline `src/`: these pin correct behaviour, and none exposed a bug. `src/` is untouched (`git diff --exit-code a02f326 -- src/` clean).
- `tests/fixtures/scryfall_bulk.py` replaces only `fetch_bulk_data_list` and `download_bulk_data`; `import_through_orchestrator` passes the test's `tmp_path` as `temp_dir`, so the download never touches the shared temp root. `test_end_to_end_import` now reads the sample file and runs it through the orchestrator (same counts: 6 processed, 5 inserted, 1 error). `test_batch_processing` and `test_empty_import` stay on `import_cards`: the first pins batching the orchestrator's fixed batch size cannot reach, and the second's orchestrator-level behaviour is what 6.6 (M41) changes.
- The first-run marker test reads the flag *during* the import through a pass-through spy on the real `reconcile_oracle_identities` (it runs after the upsert has committed). Checking only the end state would pass with `mark_import_started` deleted, which is the very bug the marker exists to prevent.
- The caller-`temp_dir` test went into `test_download_hardening.py` next to its private-directory sibling (the finding's cited site), parametrized over a succeeding and a failing import because the cleanup is a `finally`.
- Upsert column coverage: through the orchestrator, dropping `games` from `set_` is **masked**, because stage 6 rewrites every surviving row's `games` to the cross-printing union. So the every-column test is parametrized over `orchestrator` and `import_cards`; the `import_cards` case pins the upsert alone, `games` included, which matters for a run whose reconcile fails. Dropping `game_changer` or `image_uris` also turns both cases red (checked with a targeted run, not a harness run).
- `make_wire_variant` gains `quantities` (default 1 per piece, so every existing caller is unchanged).
- Probe proofs. One full-suite harness run per planted mutation, with `src/` restored by byte copy and checked with `git diff --exit-code src/` (0) after each. `uv run python -m scripts.probe_harness --expect-red '<node>'`, harness exit 0 every time:
  ```
  occupied-key (occupied/target_key without sideboard) -- B3-P6
  full suite (-m 'not integration'): 3338 collected, 1 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_keeps_mainboard_and_sideboard_copies_apart
  merge-where (merge UPDATE without sideboard) -- B3-P6
  full suite (-m 'not integration'): 3338 collected, 1 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_keeps_mainboard_and_sideboard_copies_apart
  repoint-where (repoint UPDATE without sideboard) -- B3-P6
  full suite (-m 'not integration'): 3338 collected, 1 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_keeps_mainboard_and_sideboard_copies_apart
  no-mark-started (mark_import_started deleted) -- B3-P7
  full suite (-m 'not integration'): 3338 collected, 1 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_the_first_run_marker_spans_the_import_and_is_cleared_after[first-run]
  no-resume-clause (manage_marker = existing == 0) -- B3-P7
  full suite (-m 'not integration'): 3338 collected, 1 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_the_first_run_marker_spans_the_import_and_is_cleared_after[resume]
  always-mark (manage_marker = True) -- B3-P7
  full suite (-m 'not integration'): 3338 collected, 1 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_the_first_run_marker_spans_the_import_and_is_cleared_after[update]
  finish-inside-reconcile-try (mark_import_finished moved into the reconcile try) -- B3-P7
  full suite (-m 'not integration'): 3338 collected, 1 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_failure_is_nonfatal_and_leaves_session_usable
  piece-key-list (per-variant set replaced by a list) -- B3-P8
  full suite (-m 'not integration'): 3338 collected, 1 failed, 0 errored, exit 1
    RED    tests/integration/data/test_spellbook_import_e2e.py::test_a_quantity_two_piece_writes_one_piece_row
  no-caller-dir-unlink (output_file.unlink replaced by pass) -- B3-P9
  full suite (-m 'not integration'): 3338 collected, 2 failed, 0 errored, exit 1
    RED    tests/unit/data/importers/test_download_hardening.py::test_a_caller_supplied_temp_dir_keeps_the_directory_and_drops_the_download[import-succeeds]
    RED    tests/unit/data/importers/test_download_hardening.py::test_a_caller_supplied_temp_dir_keeps_the_directory_and_drops_the_download[import-fails]
  no-rejects-wiring (rejects=rejects deleted from the import_cards call) -- T1-1-P1
  full suite (-m 'not integration'): 3338 collected, 2 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_leaves_identity_untouched_when_canonical_rejected
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_import_captures_reject_identity_and_reason
  no-reconcile-assignment (stats.reconcile = dropped) -- T1-1-P1
  full suite (-m 'not integration'): 3338 collected, 7 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_dedups_stale_preexisting_row
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reimport_with_shifted_canonical_collapses_to_one_row
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_repoints_deck_cards_to_canonical
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_merges_deck_quantities_when_deck_holds_both_printings
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_keeps_mainboard_and_sideboard_copies_apart
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_collapses_two_stale_printings_held_by_one_deck
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reconcile_leaves_identity_untouched_when_canonical_rejected
  upsert-drops-legalities ("legalities" removed from set_) -- T1-1-P2
  full suite (-m 'not integration'): 3338 collected, 2 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reimport_updates_every_column_of_an_existing_row[orchestrator]
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reimport_updates_every_column_of_an_existing_row[import_cards]
  upsert-drops-games ("games" removed from set_) -- T1-1-P2
  full suite (-m 'not integration'): 3338 collected, 1 failed, 0 errored, exit 1
    RED    tests/integration/data/test_scryfall_import_e2e.py::test_reimport_updates_every_column_of_an_existing_row[import_cards]
  ```
- Final tree, `uv run python -m scripts.probe_harness --expect-green`, harness exit 0:
  ```
  full suite (-m 'not integration'): 3338 collected, 0 failed, exit 0
  ```
  Full `uv run pytest` (integration included): 3363 passed, 2 skipped. `ruff check .`, `ruff format --check .`, `mypy src/` and `mypy src/ --platform win32` all clean. `uv run python -m scripts.build_plugin`: no content change in `plugin/`.
- Out of scope, noticed: of the three `sideboard` terms in the merge, the one in the merge `DELETE`'s `WHERE` cannot be observed. Without it the first merge also deletes a stale sideboard row that a later planned merge was due to delete, and the planned quantities land the same either way. It is left unpinned on purpose. The ticket's `width` puts `test_download_hardening.py` under `tests/integration/data/`; it lives at `tests/unit/data/importers/`.

## Plan Change Log

## Review Triage Log

## Design Notes

Mutations were planted by a scratch script (exact-string replacement, each asserting one match) and restored from a byte copy, never with `git checkout`; the test work was committed before the first plant.

## Verification

**Commands:**
- `uv run pytest tests/integration/data/test_scryfall_import_e2e.py tests/integration/data/test_spellbook_import_e2e.py tests/unit/data/importers/test_download_hardening.py -q` -- expected: pass
- `uv run python -m scripts.probe_harness --expect-red '<node id>'` once per planted mutation, `src/` restored and checked with `git diff --exit-code` after each -- expected: the named test red, harness exit 0
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- expected: all pass

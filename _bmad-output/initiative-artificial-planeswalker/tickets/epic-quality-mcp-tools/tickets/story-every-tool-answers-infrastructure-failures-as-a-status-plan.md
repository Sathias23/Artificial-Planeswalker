---
title: 'Every tool answers infrastructure failures as a status'
type: 'bugfix'
ticket: '2'
created: '2026-11-10'
status: 'review'
baseline_revision: '1d2ec06524d70378b4d29d96613d3a57a4aeecf2'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** "Never raise" is every tool's contract (`server.py:31-32`), but the readiness probe, the sqlite-vec connection, the embedder load and the card tools' pre-reads run outside each tool's guard, so a corrupt or locked `cards.db`, a missing sqlite-vec extension or an offline first model load reaches the agent as an MCP `isError`. In `compare_deck_power` a side-A probe failure means side B never runs; `semantic_search_cards` loads (and downloads) the model before its database and index guards; `add_card_to_deck` calls every `IntegrityError` `exists`; `initialize_database` blames "the connection" for every failure.

**Approach:** One shared guard at the tool edge in `server.py` turns infrastructure failures (and only those) into each tool's `status="error"`, the four card result models that lack `error` gain it, and the three behaviour bugs are fixed in their helpers. Tests that pin today's untested arms land first.

## Boundaries & Constraints

**Always:** The guard catches exactly the infrastructure set (Design Notes) and re-raises SQL `ProgrammingError`; every other exception still surfaces as an MCP error. Sync sqlite-vec and embedder work stays inside `asyncio.to_thread`. Failure tests build their state on temp-dir fixture databases and monkeypatched loaders; none reads, locks, corrupts or writes the real data directory, and none can reach the network (the Scryfall importer and the fastembed loader are stubbed in every scenario). New guards are proved through `scripts.probe_harness`. Docstrings, the five skills and `plugin/` move with the new token.

**Never:** No change to `src/viewer/` or `view_deck`'s display (its failure path is covered by the edge guard alone); no change to the companion push tools or `companion_status` (no database, AD-8); no new status token besides `error`; no catch-all `except Exception` at the edge; no fix to the combo-read degradation (5.3) or the docstring/skill drift that is not about `error` (5.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Corrupt file | `cards.db` is not a SQLite file | every database tool: `error`; `compare_deck_power`: `both_decks_failed`; companion push/status tools: their usual no-companion status | `isError` false on all 28 tools |
| Locked file | another connection holds an exclusive lock | same as corrupt | busy-timeout seam keeps the test fast |
| Missing vec extension | `sqlite_vec` load fails | `semantic_search_cards`, `find_similar_cards`, `build_search_index`: `error` naming the extension; relational tools unaffected | `isError` false |
| Offline first model load | fastembed cannot load the model | `semantic_search_cards` (built index), `build_search_index`: `error` naming the model; `find_similar_cards`: unaffected | `isError` false |
| Offline model, unbuilt index | cards, no `card_vec` | `semantic_search_cards`: `index_unavailable`; model never loaded | none |
| Programming error | a helper raises `TypeError` or SQL `ProgrammingError` | MCP `isError` (not swallowed) | propagates |
| Compare, side A fails | side A's probe raises `OperationalError` | `deck_a_failed`; side B assessed | rollback restores the shared session |
| Deck vanishes mid-add | deck passes the pre-check, gone at insert | `add_card_to_deck`: `deck_not_found` | a true duplicate still answers `exists` |
| Init fails | import fails for a non-network cause | message names the cause, no "Check the connection" | network causes keep a network hint |

</frozen-after-approval>

## Code Map

- `src/mcp_server/server.py` -- 28 tool wrappers. Guard applies to the 19 that open `session_factory()` (lookup, search, list/create/clone/load/update/delete deck, add/set/remove card, import, view, set_active_deck, curve, synergies, validate, assess, compare) and the 3 `asyncio.to_thread` search tools; each passes an error-result factory. `initialize_database` keeps its own `except Exception`; `companion_status` and the 4 push tools are untouched.
- `src/mcp_server/tools/failures.py` (new) -- the shared guard and message builder.
- `src/search/connection.py:_build_connection` -- wrap `enable_load_extension` + `sqlite_vec.load` as `VectorExtensionUnavailableError`; add a `busy_timeout_ms=5000` seam (connect timeout and pragma).
- `src/search/embedder.py:Embedder.__init__` -- wrap the cache `mkdir` and `TextEmbedding(...)` construction (`OSError`/`ValueError`/`RuntimeError`; fastembed raises `ValueError("Could not load model … from any source.")` offline) as `EmbeddingModelUnavailableError`. Keep the cache-is-a-file `ValueError`.
- `src/search/__init__.py` -- export the two errors and their base `SearchBackendUnavailableError(RuntimeError)`.
- `src/data/database.py:create_engine` -- add a `busy_timeout: float = 5` seam; correct the three connect-hook docstrings and `is_database_initialized`'s docstring: it raises on an unreadable file, and the tool edge maps that to `error`.
- `src/mcp_server/tools/assess_deck_power.py:700` -- move the probe inside a `DatabaseError` arm with the existing rollback, so compare's side B runs.
- `src/mcp_server/tools/semantic_search.py` -- accept `Embedder | Callable[[], Embedder]` and resolve it after both guards (23 test call sites pass instances; unchanged). Add `error` to `SemanticSearchResult`. The server passes `get_embedder` uncalled.
- `src/mcp_server/tools/find_similar.py`, `card_lookup.py`, `card_search.py` -- add `error` to `SimilarCardsResult`, `CardLookupResult`, `CardSearchResult` (needed for the verify line; none is served by the companion, so no `gen:api`).
- `src/mcp_server/tools/deck_management.py:675` -- on `IntegrityError`, re-read the deck; `None` means `deck_not_found`. `deck_import.py:511` already reports a race as `error`; leave it.
- `src/mcp_server/tools/initialize_database.py:237` -- network hint only when the cause chain holds `ScryfallAPIError` or `httpx.HTTPError`.
- Tests to extend: `test_companion_tool.py:229` `_ClientStub`, `test_deck_changed_wiring.py:654-719`, `test_deck_analysis_tool.py`, `test_first_run_data_init.py:258-357`, `test_compare_deck_power_tool.py`, `test_deck_management_tool.py`. Harness to mirror: `test_companion_degradation.py` (real in-memory MCP session, `isError`). Fixtures: `seeded_vec_db`, `empty_card_db`, `FakeEmbedder`.
- Skills to ripple: the rows and status lists in all five `.claude/skills/*/SKILL.md` that enumerate lookup, search, semantic or similar statuses.

## Tasks & Acceptance

**Execution:**
- [x] tests (commit 1, green on the old code) -- B8-P4: the stub records `session.in_transaction()` and asserts `False`; B8-P6: add add and remove to the write-failure parametrisation; B9-P18: one test over the 3 analysis helpers raising from `get_deck_with_cards`; T1-2-P5: one test over every guarded helper on an empty card table.
- [x] `src/search/*`, `src/data/database.py` -- named loader errors and timeout seams, as mapped.
- [x] `src/mcp_server/tools/failures.py`, `server.py` -- the guard on the 22 wrappers, each with its error factory.
- [x] `assess_deck_power.py`, `semantic_search.py`, `deck_management.py`, `initialize_database.py`, the 4 result models -- the fixes as mapped.
- [x] `tests/integration/mcp_server/test_infrastructure_failures.py` (new) -- 4 scenarios × 28 tools through a real MCP session, plus the programming-error pass-through; bug tests for compare side B, deck-vanishes, embedder ordering and the init message.
- [x] `server.py` docstrings, the 4 model docstrings, the skills -- name `error` and what it means where a tool can now return it; then `uv run python -m scripts.build_plugin`.

**Acceptance Criteria:**
- Given each injected failure, when every one of the 28 tools is called through a real MCP client session, then no result has `isError` and each status is one its result model declares.
- Given a helper that raises a non-infrastructure exception, when its tool is called, then the client sees `isError` (the guard did not swallow it).
- Given the guard, the loader wraps or the assess probe arm deleted in turn, when the probe harness runs the full suite, then the named tests go red.

## Design Notes

```python
INFRASTRUCTURE_ERRORS = (sqlalchemy.exc.DatabaseError, sqlite3.DatabaseError,
                         SearchBackendUnavailableError)
PROGRAMMING_ERRORS = (sqlalchemy.exc.ProgrammingError, sqlite3.ProgrammingError)

async def answer_infrastructure_failures(tool, call, on_error):
    try:
        return await call()
    except PROGRAMMING_ERRORS:
        raise
    except INFRASTRUCTURE_ERRORS as exc:
        logger.error("%s answered status=error", tool, exc_info=exc)
        return on_error(infrastructure_error_message(exc))
```

`MissingGreenlet`, `InvalidRequestError`, `ValidationError`, `TypeError` and similar are not in the set and still raise. Third-party loader errors are narrowed where they happen (two `src/search` wraps), so the edge never catches `ValueError` or `OSError`. The message uses the DB-API's own text (`exc.orig`, never SQLAlchemy's statement echo), truncated to 200 characters, with a wait-and-retry hint when the text says locked or busy. Known limit: SQLite reports SQL syntax errors as `OperationalError`, so a malformed query answers `error`, logged at error level with traceback on stderr. Compare keeps `both_decks_failed` when both sides answer `error` (no new semantics).

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- all green
- `uv run python -m scripts.probe_harness --expect-red …` (one run per planted removal, repeatable flag) -- proof lines pasted into Implementation Notes
- `uv run python -m scripts.build_plugin` then `git status --short plugin/` -- committed, no drift

## Implementation Notes

Commits on `fix/quality-5-2-infra-failures-as-status`: `f1a6105` (commit 1, tests green on the old
code: B8-P4, B8-P6, B9-P18, T1-2-P5) and `ad15adc` (the guard, the loader wraps, the three behaviour
fixes, the four models, docstrings, skills, `plugin/` rebuilt).

Deviations and choices the plan left open:

- Locked-file scenario runs with the busy-timeout seams at **0**, not a small positive value: on
  Windows even 10 ms cost ~0.2 s per tool (sleep granularity), 6 s for the sweep; 0 still answers
  "database is locked" and takes ~1 s. The locked fixture is built through the async engine only, so
  the file stays in rollback-journal mode (under WAL an exclusive writer does not block readers).
- `initialize_database` is not wrapped by the edge (it keeps its own `except Exception`); in the sweep
  its engine is built through a monkeypatched `create_engine` partial so the locked file fails fast.
  Its message now uses the DB-API text for a database cause anywhere in the chain, and the network
  hint only for `ScryfallAPIError` / `httpx.HTTPError` in the chain.
- `failure_detail` is public in `failures.py` so `initialize_database` reuses the same capped text.
- The connection wrap catches `(AttributeError, OSError, sqlite3.Error)` around
  `enable_load_extension` + `sqlite_vec.load`; the embedder wrap covers the fastembed import
  (`ImportError`, e.g. a Windows "DLL load failed"), the cache `mkdir` and the `TextEmbedding(...)`
  construction (review fix).
- `src/search/query.is_database_initialized` got the same one-sentence "raises on an unreadable file"
  docstring correction as its async twin (same pattern, not in the Code Map).
- The B8-P6 and B9-P18 tests also assert the helper's own message, so they still pin the helpers'
  `except DatabaseError` arms now that the edge would otherwise catch a deleted arm.
- Skills: `error` added to the lookup/search/semantic/similar rows in the four skills that list them
  (the companion skill lists none), plus a one-bullet `error` handling note where the degradation
  section lacked one or the semantic fallback was unstated.

Verification:

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`,
  `uv run mypy src/ --platform win32`: clean. `uv run pytest`: 3506 passed, 2 skipped.
- `uv run python -m scripts.build_plugin` then `git status --short plugin/`: no drift.

Probe-harness proofs (each plant applied to the committed tree, reverted with `git checkout`, revert
checked with `git diff --exit-code`; harness exit 0 = every `--expect-red` met):

guard deleted (`answer_infrastructure_failures` reduced to `return await call()`):
```
full suite (-m 'not integration'): 3481 collected, 5 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_corrupt_file_answers_error_from_every_database_tool
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_locked_file_answers_error_from_every_database_tool
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_missing_vector_extension_answers_error_from_the_three_vector_tools
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_an_offline_first_model_load_answers_error_from_the_two_embedding_tools
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_the_edge_message_is_the_driver_text_capped_with_a_lock_hint
```
sqlite-vec wrap deleted (`src/search/connection.py`, bare `raise`):
```
full suite (-m 'not integration'): 3481 collected, 1 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_missing_vector_extension_answers_error_from_the_three_vector_tools
```
model wrap deleted (`src/search/embedder.py`, bare `raise`):
```
full suite (-m 'not integration'): 3481 collected, 1 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_an_offline_first_model_load_answers_error_from_the_two_embedding_tools
```
assess probe arm deleted (probe moved back outside the `try`):
```
full suite (-m 'not integration'): 3481 collected, 3 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_corrupt_file_answers_error_from_every_database_tool
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_locked_file_answers_error_from_every_database_tool
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_side_a_probe_failure_still_assesses_side_b
```

Pins and bug fixes, proved after implementation (13 plants in one run: `session.close()` dropped in
`set_active_deck`; the add/remove card and the three analysis `except DatabaseError` arms narrowed to
`KeyError`; the `database_not_initialized` guard disabled in `load_deck`, `delete_deck`,
`remove_card_from_deck` and `detect_synergies`; the B8-P7 deck re-check disabled; the server resolving
`get_embedder()` before the helper; the old "Check the connection" init message restored). Tree staged
first; each file reverted with `git checkout` and checked with `git diff --exit-code`. All 14
`--expect-red` met; the 5 extra reds are knock-ons of the embedder and init-message plants (the model
loads early in the corrupt/locked sweeps and the `ValueError` pass-through row; the old message lacks
"network"):
```
full suite (-m 'not integration'): 3481 collected, 19 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_companion_tool.py::TestAnExistingDeckIsDelegated::test_the_read_transaction_is_released_before_the_companion_is_called
  RED    tests/integration/mcp_server/test_deck_analysis_tool.py::test_a_database_error_loading_the_deck_is_status_error[analyze_mana_curve]
  RED    tests/integration/mcp_server/test_deck_analysis_tool.py::test_a_database_error_loading_the_deck_is_status_error[detect_synergies]
  RED    tests/integration/mcp_server/test_deck_analysis_tool.py::test_a_database_error_loading_the_deck_is_status_error[validate_deck]
  RED    tests/integration/mcp_server/test_deck_changed_wiring.py::TestANoWriteOutcomeEmitsNothing::test_a_database_error_in_the_new_tools_is_silent_and_leaves_the_deck_alone[add_card_to_deck-args3-add_card_to_deck]
  RED    tests/integration/mcp_server/test_deck_changed_wiring.py::TestANoWriteOutcomeEmitsNothing::test_a_database_error_in_the_new_tools_is_silent_and_leaves_the_deck_alone[remove_card_from_deck-args4-remove_card_from_deck]
  RED    tests/integration/mcp_server/test_first_run_data_init.py::test_every_guarded_helper_answers_database_not_initialized_on_an_empty_card_table[load_deck]
  RED    tests/integration/mcp_server/test_first_run_data_init.py::test_every_guarded_helper_answers_database_not_initialized_on_an_empty_card_table[delete_deck]
  RED    tests/integration/mcp_server/test_first_run_data_init.py::test_every_guarded_helper_answers_database_not_initialized_on_an_empty_card_table[remove_card_from_deck]
  RED    tests/integration/mcp_server/test_first_run_data_init.py::test_every_guarded_helper_answers_database_not_initialized_on_an_empty_card_table[detect_synergies]
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_corrupt_file_answers_error_from_every_database_tool
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_locked_file_answers_error_from_every_database_tool
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_an_offline_model_with_an_unbuilt_index_is_index_unavailable_without_a_load
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_non_infrastructure_exception_still_surfaces_as_an_mcp_error[ValueError]
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_deck_deleted_between_the_check_and_the_write_is_deck_not_found
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_non_network_import_failure_names_its_cause_without_a_network_hint[bad-bulk-file]
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_non_network_import_failure_names_its_cause_without_a_network_hint[wrapped-bad-bulk-file]
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_network_import_failure_keeps_the_network_hint[httpx]
  RED    tests/integration/mcp_server/test_infrastructure_failures.py::test_a_network_import_failure_keeps_the_network_hint[api]
```

The three review-patch tests (vanished card, failed fastembed import, database error with network
context) were added in `ce9cdb9` and have no harness red proof.

After the review patches (`ce9cdb9`): ruff, ruff format, mypy (both platforms) clean; `uv run pytest`
3509 passed, 2 skipped; `scripts.build_plugin` leaves no drift.

## Plan Change Log

## Review Triage Log

**Pass 1 (quick lens):** 0 high / 1 medium / 3 low / 0 false / 0 maybe-false.

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | `add_card_to_deck` still reports a card removed between resolution and insert as `exists`; the comment named two constraints, `deck_cards` has three (`deck_card.py:30` FK to `cards.id`) | low | patch | Confirmed: the update reconcile deletes `cards` rows (`scryfall.py:345`), and the deck re-check alone then answers `exists`. Same root defect the intent names, and the fix mirrors the deck re-check. Implementer re-reads the card (`card_not_found`), corrected the comment, and added a test. |
| 2 | `Embedder.__init__` calls `_load_text_embedding()` (the fastembed / onnxruntime import) outside the wrap, so a Windows "DLL load failed" `ImportError` is still an MCP `isError` from `semantic_search_cards` | medium | patch | Confirmed: only `build_search_index` was covered, by its own `except Exception`. Moved the call inside the try and added `ImportError`, with a test. |
| 3 | `initialize_database._failure_message` scanned the whole chain for a network cause first, so a locked `_clear_cards` after a download failure read "database is locked. Check the network…"; the network branch also produced ".." | low | patch | Confirmed: the cleanup error carries the network error as `__context__`. A direct correction: the first classified link, outermost first, decides, and `.rstrip('.')`. Test added. |
| 4 | `server.py` module docstring and the skill `error` notes promise a message naming the cause, but helper-arm catches (analysis, deck writes, assess/compare) return generic text | low | patch | Confirmed for the arms. Wording only: the docstring distinguishes edge-caught from helper-caught failures, and two skills say the message "describes the failure". The conditional "locked → retry once" advice stands. `plugin/` rebuilt. |

Pass 1 outcome: four patches applied by the implementer in `ce9cdb9`, nothing rejected, nothing deferred, no loopback.

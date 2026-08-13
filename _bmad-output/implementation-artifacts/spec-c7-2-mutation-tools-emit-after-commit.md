---
title: 'c7-2: Every deck-mutation tool emits after its transaction commits'
type: 'feature'
created: '2026-08-13'
status: 'review'
review_loop_iteration: 0
baseline_revision: 'e5826d058b99fbca1b22a358d1e77da9a22217ca'
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-c7-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** The five deck-mutation tools persist changes but never tell the companion, so the glass silently goes stale after every agent edit — the epic's core loop (agent drives, app shows) is broken without this wire.

**Approach:** Each mutation tool's `server.py` wrapper awaits c7-1's `notify_deck_changed(deck_id)` after its `async with session_factory()` block exits (every commit already landed; connection released) and only when the result proves a write happened. One emit per tool call — `import_decklist` emits once, not per line. An enumeration guard makes a future mutation tool fail loudly until it is wired.

## Boundaries & Constraints

**Always:** Emit only on a persisted write: `status == "ok"` for create/delete/add/remove; `imported_lines > 0` for import — every other status emits nothing. Emit outside the session block, never inside it. The notify path is a plain awaited call. The notification outcome never alters the tool's own result — no new statuses, no message changes; debug-log the `PushOutcome` with `%`-style lazy args (`client.py:592` anticipates exactly this). All new companion references land in `server.py` only — the SC-3 allow-list stays at three entries and `test_import_boundary.py` passes unchanged. Rebuild and commit `plugin/` after the src change.

**Block If:** The emit turns out to require touching `deck_management.py`/`deck_import.py` or growing the SC-3 allow-list; the notifier's contract or budget needs changing; a sixth deck-write surface is discovered.

**Never:** `create_task`/`ensure_future`/`TaskGroup`/`gather` on the notify path. No helper-level wiring. No per-line emits from import. No UI work (c7-3+), no notifier changes (c7-1 shipped), no staleness warning (accepted until FR-16). Do not extend `test_ws.py`'s package-wide sweep to `src/mcp_server` — the local await-only guard covers the new sites.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Create/add/remove ok | Tool returns `status="ok"` | Exactly one emit; `deck_id` = `result.deck.id` (create) / `result.deck_id` | N/A |
| Delete ok | Deck deleted | One emit with the now-absent deck's id (UI refetch 404s → clears, by design) | N/A |
| Import, ≥1 line lands | `imported_lines > 0` (`ok`/`partial`) | Exactly one emit after the loop, `result.deck_id` | N/A |
| No write | `invalid`, `exists`, `not_in_deck`, `*_not_found`, `ambiguous`, `error`, `database_not_initialized`; import with `imported_lines == 0` | Zero emits | N/A |
| Companion closed | No discovery file | Mutation result byte-identical; notifier returns `app_not_running` cheaply | Client DEBUG-logs; wrapper debug-logs outcome |
| Notify failure | Stub returns `backend_error` etc. | Tool result unchanged; never raises (client guarantees) | Debug log only |
| After-commit proof | Observer reads DB at notify time | Create: row visible; delete: row gone | N/A |

</intent-contract>

## Code Map

- `src/mcp_server/server.py` -- THE file. Wrappers: `create_deck` :233, `delete_deck` :277, `add_card_to_deck` :293, `import_decklist` :335, `remove_card_from_deck` :362 — each is `async with session_factory() as session: return await _<x>_helper(...)`; restructure to capture-result → exit block → conditional emit → return. Imports :39-96 (alias style `as _x_helper`); **no logger exists yet** — add `logging.getLogger(__name__)`. Already on the SC-3 allow-list.
- `src/companion/client.py:580` -- `async def notify_deck_changed(deck_id: str | None = None, *, timeout=None) -> PushOutcome`; never raises, ~1 s budget (`_NOTIFY_TOTAL_SECONDS` :131), mints the envelope itself. Read-only.
- `src/mcp_server/tools/deck_management.py` -- read-only. Result models: `DeckResult` :59 (`deck.id`), `DeckDeleteResult` :75 (`deck_id`), `DeckCardResult` :89 (`deck_id`). Commits happen inside `src/data/repositories/deck.py` :91/:226/:347/:419 — so "after commit" = after the helper returns.
- `src/mcp_server/tools/deck_import.py` -- read-only. `DeckImportResult` :66 (`imported_lines`, `deck_id`); delegates per line to `add_card_to_deck` (import alias :16, call :420) — N commits; why emit lives in the wrapper.
- `src/mcp_server/tools/companion.py` -- precedents: patch-at-importer convention (docstring :25-29); release-connection-before-outbound-HTTP rationale :181-186.
- `tests/unit/companion/test_import_boundary.py` -- `_COMPANION_REFERENCE_ALLOWED` :162-171 already names `server.py`; `_REPO_WRITE_METHODS` :76-87 is the pinned deck-write vocabulary (cross-checked live by `TestRepositorySurfaceIsPinned` :1290) — source the guard's write-method names to match it. Must pass unchanged.
- `tests/integration/mcp_server/` -- test home (no `integration` marker — runs in the default gate, per `test_companion_tool.py:31`). Reuse: `_PushStub`/fixture shape (`test_companion_tool.py:119,:136`), `closed_companion` (`test_companion_degradation.py:58`), in-process client driver (`tests/integration/test_mcp_tools.py:31,:142`), set-equality precedent (`tests/integration/test_build_plugin.py:135`).
- `tests/unit/companion/test_routes_active_deck.py:754` -- existing sweep bans identifiers `ActiveDeckSlot`/`active_deck`/`ActiveDeck` in `src/mcp_server` — name nothing that trips it.
- `scripts/build_plugin.py` -- committed verbatim mirror of `src/`; rebuild + commit (`tests/integration/test_build_plugin.py` gates).

## Tasks & Acceptance

**Execution:**
- [x] `src/mcp_server/server.py` -- add module logger + `from src.companion.client import notify_deck_changed as _notify_deck_changed`; add module-level `async def _emit_deck_changed(deck_id: str | None) -> None` (await notifier, debug-log outcome); rewire the five wrappers per the matrix predicates.
- [x] `tests/integration/mcp_server/test_deck_changed_wiring.py` (new) -- behavioral half: in-process MCP client + recording stub monkeypatched as `server._notify_deck_changed` (injectable `PushOutcome`), covering the full matrix incl. exactly-one-emit per multi-line import, failure-outcome-leaves-result-unchanged, and the after-commit proofs (stub opens its own session from the same factory: create→row exists, delete→row gone at notify time); degradation: real client + `closed_companion`-style repointed `PLANESWALKER_DATA_DIR`, mutation still `ok`.
- [x] Same file, enumeration half -- AST guards with non-vacuity asserts: (a) derive mutating helper functions by sweeping `src/mcp_server/tools/*.py` for references to the deck-write method names, resolving import aliases (deck_import's `_add_card_to_deck` is the case that demands it), map through `server.py`'s import aliases to the wrappers that call them, assert set equality with the five tool names — a future unwired mutation tool fails by name; (b) each of the five wrappers awaits `_emit_deck_changed`; no other wrapper references it or `_notify_deck_changed`; (c) every reference to either name in `server.py` sits under an `ast.Await` call (local detached-task ban).
- [x] Firing proof (Task-0 discipline) -- stage the tree; plant (a) the emit deleted from one wrapper, (b) another wrapper's emit wrapped in `asyncio.create_task`; `uv run python -m scripts.probe_harness --expect-red '<node id>'` for the guard + behavioral ids; revert (`git diff --exit-code`); paste proof lines into this record.
- [x] `plugin/` -- `uv run python scripts/build_plugin.py`, commit the refreshed mirror.

**Firing proof (2026-08-13).** Plants: the `delete_deck` emit deleted outright; the `add_card_to_deck` emit wrapped in `asyncio.create_task(...)`. Staged tree first, plants unstaged:

```
full suite (-m 'not integration'): 3019 collected, 5 failed, 0 errored, exit 1
  RED    tests/integration/data/test_deck_repository.py::test_update_deck_strategy
  RED    tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field
  RED    tests/integration/mcp_server/test_deck_changed_wiring.py::TestEachPersistedWriteEmitsExactlyOnce::test_delete_deck_emits_the_now_absent_id_after_the_row_is_gone
  RED    tests/integration/mcp_server/test_deck_changed_wiring.py::TestEveryMutationToolIsWiredAndNoOtherToolIs::test_exactly_the_five_mutating_wrappers_reference_the_emit_path
  RED    tests/integration/mcp_server/test_deck_changed_wiring.py::TestEveryMutationToolIsWiredAndNoOtherToolIs::test_every_emit_reference_in_server_py_is_a_plain_awaited_call
```

All three `--expect-red` ids fired (the enumeration guard named the unwired wrapper; the await-only guard caught the detached task; the behavioural delete test caught the missing emit). The two `test_deck_repository` reds are the pre-existing flake pair recorded in Design Notes below — re-verified nondeterministic on the *unchanged baseline tree* during this story (fails ~1-in-2 runs of its own file, passes in isolation). Revert: `git restore src/mcp_server/server.py` then `git diff --exit-code` → clean (worktree == staged tree). Green run after revert:

```
full suite (-m 'not integration'): 3019 collected, 0 failed, exit 0
```

**Acceptance Criteria:**
- Given an in-process server with a stubbed notifier, when each of the five tools persists a change, then exactly one emit carries that deck's id, observed after the commit is visible (delete: after the row is gone).
- Given any no-write outcome on any of the five tools, when the tool returns, then zero emits occurred.
- Given a closed companion or a failure `PushOutcome`, when a mutation runs, then its structured result is identical to pre-story behaviour and nothing raises.
- Given a hypothetical new tool calling a deck-write repository method without the emit, when the enumeration guard runs, then it fails naming that tool.
- Given the full import-boundary and active-deck sweeps, when the suite runs, then they pass with zero allow-list changes.

## Spec Change Log

## Review Triage Log

## Design Notes

- Wrapper-level (not helper-level) emit is load-bearing: helpers would need two new SC-3 allow-list entries plus edits to fixtures that use `deck_management.py` as a *violation* case (`test_import_boundary.py:1104,:1188`), and `import_decklist`'s per-line delegation to `add_card_to_deck` would fire N emits for one import. The wrapper is the one place that sees exactly one call per tool invocation and is already companion-privileged.
- Emitting after the `async with` block exits gives both guarantees at once: the transaction is committed (repos commit internally) and no pooled connection is held across the ~1 s HTTP window (`companion.py:181-186` rationale, achieved structurally instead of via `session.close()`).
- `deck_id=None` from a result passes through unchanged — the contract reads it as "refetch whatever is active"; do not invent a guard.
- Known full-suite flake (pre-existing, recorded in c7-1): `tests/integration/data/test_deck_repository.py::test_update_deck_strategy` / `::test_list_decks_with_strategy_field` — not this story's regression if they appear in harness output.
- Branch process: story branch `feat/companion-c7-2-mutation-tools-emit` off umbrella `feat/companion-c7`; PR targets the umbrella.

## Verification

**Commands:**
- `uv run pytest tests/integration/mcp_server tests/unit/companion -q` -- expected: green incl. the new wiring file; boundary suites untouched and green.
- `uv run python -m scripts.probe_harness --expect-red '<planted node id>'` then `--expect-green` after revert -- expected: proof lines pasted above.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: clean.
- `uv run python scripts/build_plugin.py && git status --porcelain plugin/` -- expected: mirror rebuilt, diff committed.

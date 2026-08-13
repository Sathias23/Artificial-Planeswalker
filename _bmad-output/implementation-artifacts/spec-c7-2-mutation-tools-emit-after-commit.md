---
title: 'c7-2: Every deck-mutation tool emits after its transaction commits'
type: 'feature'
created: '2026-08-13'
status: 'done'
review_loop_iteration: 0
baseline_revision: 'e5826d058b99fbca1b22a358d1e77da9a22217ca'
followup_review_recommended: true
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

**Firing proof, review patches (2026-08-13, second entry).** The review added two guards (emit-outside-the-session-block; the hardened derivation resolving relative imports, module-object attribute delegation, and a recursive sweep incl. `__init__.py`, plus the server.py direct-write pin). Plants, staged tree first: (i) `create_deck`'s emit moved back *inside* its `async with` block; (ii) a temporary `src/mcp_server/tools/merge_tool.py` whose only path to a repository write is a **relative** from-import of `add_card_to_deck` — the delegation shape the pre-patch resolver could not see — plus an unwired `merge_tool` wrapper registered in server.py:

```
full suite (-m 'not integration'): 3021 collected, 3 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_deck_changed_wiring.py::TestEveryMutationToolIsWiredAndNoOtherToolIs::test_the_derived_mutating_tools_are_exactly_the_five_wired_ones
  RED    tests/integration/mcp_server/test_deck_changed_wiring.py::TestEveryMutationToolIsWiredAndNoOtherToolIs::test_no_emit_reference_sits_inside_a_session_block
  RED    tests/integration/test_build_plugin.py::test_server_registers_expected_tools
```

Both `--expect-red` ids fired; the derivation guard's failure message named the plant (`wire (or unwire) the difference: ['merge_tool']`), and the third red is the tool-catalogue set-equality guard seeing the planted tool — an expected side effect confirming the plant registered a real tool. Revert: `git restore src/mcp_server/server.py` + delete the temp module, `git diff --exit-code` → clean (worktree == staged tree). Green run after revert:

```
full suite (-m 'not integration'): 3021 collected, 0 failed, exit 0
```

(Collected count 3019 → 3021: the two review-patch guard tests.)

**Acceptance Criteria:**
- Given an in-process server with a stubbed notifier, when each of the five tools persists a change, then exactly one emit carries that deck's id, observed after the commit is visible (delete: after the row is gone).
- Given any no-write outcome on any of the five tools, when the tool returns, then zero emits occurred.
- Given a closed companion or a failure `PushOutcome`, when a mutation runs, then its structured result is identical to pre-story behaviour and nothing raises.
- Given a hypothetical new tool calling a deck-write repository method without the emit, when the enumeration guard runs, then it fails naming that tool.
- Given the full import-boundary and active-deck sweeps, when the suite runs, then they pass with zero allow-list changes.

## Spec Change Log

## Review Triage Log

### 2026-08-13 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 3: (high 0, medium 2, low 1)
- defer: 0
- reject: 17: (high 0, medium 1, low 16)
- addressed_findings:
  - `[medium]` `[patch]` The "emit outside the session block" Always-constraint had no test — a refactor moving the emit back inside the `async with` passed everything (the repos commit internally, so the after-commit observers see the row either way). Added `test_no_emit_reference_sits_inside_a_session_block`: no emit-path name may be a descendant of an `ast.AsyncWith` in a mutation wrapper, with non-vacuity asserts. Proven red via a planted inline emit.
  - `[medium]` `[patch]` The enumeration guard's import resolver only understood absolute `from src.mcp_server.tools.X import y` — relative imports (permitted by repo convention within a package), plain `import` forms, module-attribute delegation, `__init__.py`, and subpackages all escaped the "can't be forgotten" promise; nothing pinned server.py against inline repository writes either. Hardened the resolver (relative-import resolution shared with `test_import_boundary.py`, module-binding attribute edges, recursive module sweep) and added `test_server_py_reaches_no_repository_write_method_directly`. Proven red via a planted relative-import delegating tool, named by the guard.
  - `[low]` `[patch]` The epic's verb list names "update" but no update-shaped MCP tool exists; the record resolved that tension silently. Added a Design Notes bullet making the reconciliation explicit (four repository update/merge write methods have zero `src/mcp_server` references; the derivation guard forces wiring the day such a tool appears).

## Design Notes

- Wrapper-level (not helper-level) emit is load-bearing: helpers would need two new SC-3 allow-list entries plus edits to fixtures that use `deck_management.py` as a *violation* case (`test_import_boundary.py:1104,:1188`), and `import_decklist`'s per-line delegation to `add_card_to_deck` would fire N emits for one import. The wrapper is the one place that sees exactly one call per tool invocation and is already companion-privileged.
- Emitting after the `async with` block exits gives both guarantees at once: the transaction is committed (repos commit internally) and no pooled connection is held across the ~1 s HTTP window (`companion.py:181-186` rationale, achieved structurally instead of via `session.close()`).
- `deck_id=None` from a result passes through unchanged — the contract reads it as "refetch whatever is active"; do not invent a guard.
- Known full-suite flake (pre-existing, recorded in c7-1): `tests/integration/data/test_deck_repository.py::test_update_deck_strategy` / `::test_list_decks_with_strategy_field` — not this story's regression if they appear in harness output.
- Branch process: story branch `feat/companion-c7-2-mutation-tools-emit` off umbrella `feat/companion-c7`; PR targets the umbrella.
- Verb-list/tool-surface reconciliation (review patch 3, 2026-08-13): the epic's requirement names the verb "update" among the emitting mutations, but **no update-shaped MCP tool exists today** — `update_deck`, `update_card_quantity`, `update_deck_color_identity`, and `merge_decks` all exist on the repository layer with zero references anywhere in `src/mcp_server`. The five wired tools therefore cover the entire current mutation surface, and the derivation guard (which seeds from the pinned repository write-method vocabulary, those four names included) is what forces wiring the day an update-shaped tool appears: its helper would reference a pinned write method, join the derived set, and fail the enumeration guard by name until its wrapper emits.

## Verification

**Commands:**
- `uv run pytest tests/integration/mcp_server tests/unit/companion -q` -- expected: green incl. the new wiring file; boundary suites untouched and green.
- `uv run python -m scripts.probe_harness --expect-red '<planted node id>'` then `--expect-green` after revert -- expected: proof lines pasted above.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: clean.
- `uv run python scripts/build_plugin.py && git status --porcelain plugin/` -- expected: mirror rebuilt, diff committed.

## Auto Run Result

Status: done

**Summary.** All five deck-mutation MCP tools (`create_deck`, `delete_deck`, `add_card_to_deck`, `import_decklist`, `remove_card_from_deck`) now emit `deck_changed` through c7-1's shared notifier after their session block exits — commit landed, pooled connection released — and only when the result proves a persisted write (`status == "ok"`; `imported_lines > 0` for import, one emit per call, never per line). The notify outcome is debug-logged and never touches the tool's own result. A derivation-based enumeration guard makes any future deck-write tool fail by name until wired.

**Files changed** (commits `1995cc9` feat + `e7aede8` review fix, on `feat/companion-c7-2-mutation-tools-emit` off umbrella `feat/companion-c7`):
- `src/mcp_server/server.py` — module logger, leaf-notifier import, `_emit_deck_changed` helper, five wrappers rewired (capture result → exit session block → conditional emit → return).
- `plugin/server/src/mcp_server/server.py` — rebuilt verbatim mirror.
- `tests/integration/mcp_server/test_deck_changed_wiring.py` — new, 19 tests: behavioural matrix (exactly-one-emit, after-commit observer proofs, no-write silence, outcome-token indifference, real-client closed-companion degradation) + five AST guards (derived-writers==wired-emitters, only-the-five-reference-the-emit-path, await-only, emit-outside-session-block, no-inline-repo-writes-in-server.py).
- This spec file — record, firing proofs, triage log.

**Review findings breakdown.** 20 post-dedup findings across four layers (blind hunter, edge-case hunter, verification-gap, intent-alignment): 3 patched (2 medium — missing placement guard, resolver under-approximation; 1 low — verb-list reconciliation note), 0 deferred, 17 rejected (contrived evasion scenarios, defense-in-depth against c7-1's tested never-raises contract, crash-path lost events the epic's best-effort delivery model explicitly accepts, already-tracked flake noise, cosmetics). No intent gaps, no bad-spec loopbacks.

**Follow-up review recommendation: true** — patched severities: 0 high, 2 medium, 1 low → score 3×2 + 1 = 7 ≥ 5.

**Verification performed.** Firing proofs through the committed harness, both passes: feature plants (emit deleted / emit wrapped in `create_task`) → 3 expected reds fired, revert → green; patch plants (emit moved inside the session block / relative-import delegating unwired tool) → both new guards red naming their plants, revert → full suite green (`3021 collected, 0 failed, exit 0`). Post-patch re-verification: `pytest tests/integration/mcp_server tests/unit/companion` → 1767 passed, 1 skipped; wiring file 19/19; `ruff check` + `ruff format --check` + `mypy src/` clean; plugin mirror rebuild produces no diff; import-boundary and active-deck sweeps pass with zero allow-list changes.

**Residual risks.**
- Pre-existing full-suite flake pair (`test_deck_repository.py::test_update_deck_strategy` / `::test_list_decks_with_strategy_field`) still surfaces intermittently in harness runs; unrelated to this story, tracked as C7 prep item R3.
- Pre-existing tests that drive mutations through the in-process client now traverse the real notifier; on a machine with no companion discovery file this is a cheap `app_not_running`, but a dev machine running the suite with the companion open would send real `deck_changed` events and pay up to ~1 s per mutation test. Suite-wide `PLANESWALKER_DATA_DIR` isolation was deliberately left out of scope.
- The enumeration guard's detection surface ends at the repo's conventions: a mutation written via raw session DML, or in a module outside `src/mcp_server`, is invisible to it (the SC-3 allow-list and layer-boundary tests are the backstop).

---
title: 'c7-1: One shared notifier with a bounded await and no detached tasks'
type: 'feature'
created: '2026-08-13'
status: 'review'
review_loop_iteration: 0
baseline_commit: 'e39278879c98fc088b61610437ac81ad579de70b'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-c7-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Deck-mutation tools have no way to tell the companion the deck changed, and a detached task can be torn down before it runs — the event never leaves the process and the deck view silently goes stale (AD-9).

**Approach:** Add one shared async notifier to the companion leaf — `notify_deck_changed()` in `src/companion/client.py` (the spine's structural seed names client.py as the notifier's home). It mints a `deck_changed` envelope carrying the deck id and POSTs it through the existing push plumbing under a **~1 s whole-call deadline** (vs. the push tools' 10 s), catches and logs every exception, never raises. Wiring mutation tools is c7-2; UI handling is c7-3.

## Boundaries & Constraints

**Always:** Leaf import discipline (pydantic, httpx, `src.paths`, leaf siblings, stdlib). Bounded await via `asyncio.timeout` — the deadline caps the latency a notification can add to a mutation. Every exception caught and logged with `%`-style lazy args (DEBUG for expected absence, WARNING + `exc_info` for the unexpected); the bearer token never logged. Reuse the envelope contract and `PushOutcome` vocabulary unchanged. Rebuild and commit `plugin/` after the src change.

**Ask First:** Rehoming the notifier to a new module (touches import-boundary allow-lists); changing the contract, outcome vocabulary, or existing timeout constants.

**Never:** `asyncio.create_task`, `ensure_future`, `TaskGroup`, or `gather` on the notification path. No `src.companion.app.*` import. No mutation-tool wiring (c7-2), no UI work (c7-3+), no staleness warning (accepted until FR-16), no `DEFAULT_TITLE_BY_KIND` entry (signals pinned excluded).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | Backend live, clients connected | Valid `DeckChangedEvent{deck_id}` POSTed; `PushOutcome(displayed, clients=N)` | N/A |
| App closed | No discovery file / dead port | `app_not_running`, cheap, no raise | DEBUG log |
| Nobody listening | Receipt `clients=0` | `no_clients_connected` — still a successful emit | N/A |
| Slow backend | Server accepts then drips | Returns in ≈1 s (`_NOTIFY_TOTAL_SECONDS`), never 10 s | Expiry caught, DEBUG log, existing budget-expiry outcome |
| Stale token | First POST → 403 | Re-discover + retry once (existing semantics), inside the budget | N/A |
| Null deck id | `deck_id=None` | Valid envelope; `None` payload means "refetch whatever is active" | N/A |
| Unexpected bug | Any exception on the path | Error outcome returned | Caught, WARNING + `exc_info`, never propagates |

</frozen-after-approval>

## Code Map

- `src/companion/client.py` -- THE file. Reuse: `_send` :323 (bearer auth, never raises), `_attempt` :430 (POST `EVENTS_PATH`), `_once_then_retry` :454 (whole-call `asyncio.timeout` + retry-once-on-403; hard-codes `_PUSH_TOTAL_SECONDS` :104 — parametrize with `budget` kwarg), `push_event` :495 (shape to mirror), `PushOutcome` :173, `PROBE_TIMEOUT` :86. Docstring :117-120 already assigns AD-9's ~1 s bound to c7's notifier.
- `src/companion/contracts.py` -- construct-only, contract complete: `DeckChangedEvent` :1201, `DeckChangedPayload` :923 (nullable `deck_id`), union :1278. Mint `uuid4()` id + `now(UTC)` ts like `src/mcp_server/tools/companion.py:279`.
- `src/companion/app/routes/agent_events.py:64` -- ingest endpoint, read-only; already accepts `deck_changed`; responds `EventIngestReceipt{clients}`.
- `tests/unit/companion/test_client.py` -- extend. `StubFleet` :296, `stub_server` :367, `plant_discovery` :504, sentinels `FAST`/`HANGUP`/`DRIP`; mirror `TestPushEvent` :863 / retry :1080 / never-raises-never-leaks :1188. `TestExportedSurface` :545 pins constants — add the new one.
- `tests/unit/companion/test_ws.py:526` -- `test_the_push_path_creates_no_task`: AST sweep of `src/companion/*.py` for the four detached-task names — auto-covers the notifier; `_identifiers` helper :1454. `test_import_boundary.py` needs no list changes (no new module) and must stay green.
- `scripts/build_plugin.py` -- `plugin/` is a committed verbatim mirror of `src/`; rebuild + commit (`tests/integration/test_build_plugin.py` gates). Frontend types already enumerate `deck_changed`; untouched.

## Tasks & Acceptance

**Execution:**
- [x] `src/companion/client.py` -- add `_NOTIFY_TOTAL_SECONDS = 1.0`; give `_once_then_retry` a `budget: float = _PUSH_TOTAL_SECONDS` kwarg (call sites unchanged); add `async def notify_deck_changed(deck_id: str | None = None, *, timeout: httpx.Timeout = PROBE_TIMEOUT) -> PushOutcome` minting the envelope and delegating to the existing attempt path under the 1.0 s budget, with an outer defensive catch-all.
- [x] `tests/unit/companion/test_client.py` -- `TestNotifyDeckChanged` covering the I/O matrix (incl. elapsed-time assertion ≈1 s for the slow case; stub-side parse of the received body as `DeckChangedEvent` with the sent `deck_id`; token never in logs) + explicit AST ban assertion on `client.py`; update `TestExportedSurface`.
- [x] Firing proof (Task-0 discipline) -- stage the tree, plant violations (temporary `create_task` on the path; broken deadline), prove the new tests RED via `uv run python -m scripts.probe_harness --expect-red '<node id>'`, revert (`git diff --exit-code`), paste the proof lines into the story record.
- [x] `plugin/` -- `uv run python scripts/build_plugin.py`, commit the refreshed mirror.

**Acceptance Criteria:**
- Given the codebase, when the leaf is inspected, then exactly one notifier exists, in the leaf, and the import-boundary suite passes unchanged.
- Given the notification path, when the sweep and the new ban test run, then no detached-task identifier appears.
- Given a slow or unreachable backend, when a caller awaits `notify_deck_changed`, then it returns a `PushOutcome` within the ~1 s budget and no exception ever propagates.
- Given a live backend, when the notifier runs, then the ingest endpoint receives a schema-valid `deck_changed` envelope carrying the deck id.

## Design Notes

- Return `PushOutcome`, not `None`: c7-2 callers may debug-log it, tests observe it, the closed vocabulary is reused. Budget expiry maps to whatever the existing `_once_then_retry` expiry path produces — reuse, don't invent.
- Minting inside the notifier (caller passes only `deck_id`) is the point of "one place to tell the companion".
- Branch process: story branch `feat/companion-c7-1-shared-notifier` off umbrella `feat/companion-c7` (create umbrella off `master` — first story of the epic); PR targets the umbrella.

## Verification

**Commands:**
- `uv run pytest tests/unit/companion -q` -- expected: green incl. `TestNotifyDeckChanged`.
- `uv run python -m scripts.probe_harness --expect-red '<planted node id>'` -- expected: proof line, then green after revert.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: clean.
- `uv run python scripts/build_plugin.py && git status --porcelain plugin/` -- expected: mirror rebuilt, diff committed.

## Spec Change Log

- **Implementation, 2026-08-13.** `budget` on `_once_then_retry` is `budget: float | None = None` in the shipped code, not the literal `budget: float = _PUSH_TOTAL_SECONDS` this Task 0 line names. An ordinary parameter default is bound once, at import time, so a default of `_PUSH_TOTAL_SECONDS` would freeze in `10.0` and stop tracking the module attribute — and two existing tests (`test_a_drip_feeding_backend_is_cut_off_by_the_whole_push_deadline`, `test_a_drip_feeding_backend_is_cut_off_by_the_whole_call_deadline`) shrink that attribute via `monkeypatch.setattr(client, "_PUSH_TOTAL_SECONDS", 0.8)` specifically because there is no argument to pass it through. The literal signature broke both (proved red locally before the fix, not part of the pasted firing proof below — that was this story's own regression, not a planted violation). `None` read as `_PUSH_TOTAL_SECONDS` **inside the function body** keeps every existing call site's behaviour, including the monkeypatch path, identical to before this story. No constant value, outcome vocabulary, or contract changed — only how the existing constant's default is resolved.

### Firing proof (Task 0)

Planted together: (a) an unreachable `asyncio.create_task(asyncio.sleep(0))` inside `notify_deck_changed` (guarded by `if False:`, so only the AST identifier is planted — a package-wide sweep and this story's own local pin both key on the identifier's presence, not on execution), and (b) `_NOTIFY_TOTAL_SECONDS` widened from `1.0` to `100.0` (broken deadline).

```
uv run python -m scripts.probe_harness \
  --expect-red "tests/unit/companion/test_client.py::TestNotifyDeckChanged::test_no_detached_task_identifier_appears_in_client_py" \
  --expect-red "tests/unit/companion/test_ws.py::TestTheRegistryVocabularyGuardIsReplaced::test_the_push_path_creates_no_task" \
  --expect-red "tests/unit/companion/test_client.py::TestExportedSurface::test_the_notify_budget_is_ad_9s_one_second_not_the_pushs_ten"

full suite (-m 'not integration'): 3002 collected, 6 failed, 0 errored, exit 1
  RED    tests/integration/data/test_deck_repository.py::test_update_deck_strategy
  RED    tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field
  RED    tests/unit/companion/test_client.py::TestExportedSurface::test_the_notify_budget_is_ad_9s_one_second_not_the_pushs_ten
  RED    tests/unit/companion/test_client.py::TestNotifyDeckChanged::test_a_slow_backend_is_cut_off_by_the_one_second_notify_budget
  RED    tests/unit/companion/test_client.py::TestNotifyDeckChanged::test_no_detached_task_identifier_appears_in_client_py
  RED    tests/unit/companion/test_ws.py::TestTheRegistryVocabularyGuardIsReplaced::test_the_push_path_creates_no_task
```

All three expected node ids fired red, plus the budget plant also reddened the slow-backend elapsed-time test (expected — it asserts elapsed time under the same constant). The two `test_deck_repository.py` reds are a pre-existing, unrelated flake: that file touches no companion code, both tests pass in isolation, and they reproduce identically after the revert below (`--expect-green` run) — flagged for Brad, out of this story's scope.

Reverted (`git diff src/companion/client.py | grep -i planted` → clean). Post-revert:

```
uv run python -m scripts.probe_harness --expect-green

full suite (-m 'not integration'): 3002 collected, 2 failed, 0 errored, exit 1
  RED    tests/integration/data/test_deck_repository.py::test_update_deck_strategy
  RED    tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field
```

Only the pre-existing, unrelated flake remains — every c7-1 test is green.

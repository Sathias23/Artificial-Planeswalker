---
title: 'R3: kill the deck-repository timestamp flake at its root'
type: 'bugfix'
created: '2026-08-14'
status: 'in-review'
review_loop_iteration: 0
context: []
baseline_commit: 'e39278879c98fc088b61610437ac81ad579de70b'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Three tests in `tests/integration/data/test_deck_repository.py` fail nondeterministically (measured 22/30 runs red on master). Instrumentation proves the cause is the platform clock, not the code under test: `datetime.now(UTC)` advances in ~593 µs steps on this machine, which is coarser than a repository call, so consecutive `create_deck`/`update_deck` calls receive *identical* timestamps. Two tests then assert a strict increase in `updated_at` (impossible inside one tick) and one addresses `list_decks` output positionally in creation order when `created_at` has tied — at which point the already-deterministic `ORDER BY created_at DESC, id` tie-break returns rows in random-UUID order.

**Approach:** Fix the tests, not the production code. `list_decks`' ordering contract is already deterministic under ties and already documented as arbitrary-within-a-tie; `updated_at` is never compared by any consumer. Make each test's precondition deterministic — pin timestamps explicitly (the pattern this file already established with `_set_created_at`) and address decks by identity rather than position — so each test asserts the contract the code actually makes.

## Boundaries & Constraints

**Always:** Deterministic mechanisms only. Pin timestamps to explicit values; address rows by id. Every rewritten test must still go red when the behaviour it guards regresses, proven through `scripts/probe_harness` (`--expect-red`) against the FULL suite, not a hand-typed narrow run. Python 3.12, `uv run` for everything.

**Ask First:** Any change to `list_decks`' observable ordering, to `DeckModel`'s timestamp columns/defaults, or to `update_deck`/`merge_decks` timestamp behaviour. All three are believed correct; changing one is a contract change with consumers (`src/mcp_server/tools/deck_management.py`, `src/companion/app/routes/decks.py`) and, for a column default, a hand-written migration under the no-Alembic rule.

**Never:** No retries, reruns, sleeps, `pytest-rerunfailures`, or arbitrary waits. No widening an assertion to accept either value (`>=` on a strict-increase assertion, "one of these two strategies", sorting the result before comparing). No edits to `ui/`, `plugin/`, or `src/companion/`. No new dependency.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Update stamps the clock | Deck whose `updated_at` is pinned to a known-old value; `update_deck(name=...)` | Returned `updated_at` is strictly greater than the pinned value | N/A |
| Update leaves other fields | Same, updating only `strategy` | `name` unchanged, `strategy` replaced, `updated_at` advanced | N/A |
| Merge stamps the clock | Target deck with `updated_at` pinned old; merge a source deck in | Target's `updated_at` strictly greater than the pinned value | N/A |
| Strategy round-trips for every deck | Three decks created back-to-back (two with a strategy, one without), all tying on `created_at` | `list_decks` returns all three; each deck's strategy matches what it was created with, matched by id | N/A |
| Ordering under a tie | Decks sharing one `created_at` | Existing `test_list_decks_orders_deterministically_on_created_at_tie` continues to pass unchanged | N/A |

</frozen-after-approval>

## Code Map

- `tests/integration/data/test_deck_repository.py` -- the only file to change. `_set_created_at` (L16–22) is the existing pin helper to mirror. Targets: `test_update_deck_name` (L178, assert L189), `test_update_deck_strategy` (L199, assert L210), `test_list_decks_with_strategy_field` (L320, positional asserts L331–333), `test_merge_updates_timestamp` (L1078, assert L1095 — same mechanism, latent: 0/50 failures observed, fix pre-emptively).
- `src/data/models/deck.py:49-57` -- READ-ONLY. `created_at`/`updated_at` both `default_factory=lambda: datetime.now(UTC)`; `updated_at` also has `onupdate`. **Verified:** an explicitly assigned value survives the flush — `onupdate` does not clobber it — so an ORM-attribute pin is sufficient; no Core `update()` needed.
- `src/data/repositories/deck.py:239-267` -- READ-ONLY. `list_decks` already orders `created_at DESC, id` (L262) and the docstring already explains the tie-break. `update_deck` (L199) and `merge_decks` (L692) stamp `datetime.now(UTC)`. Nothing here changes.
- `src/companion/app/routes/decks.py:35-59` -- READ-ONLY evidence: the `/api/decks` docstring already states decks tying on `created_at` "fall back to id order, which is a UUID and therefore arbitrary — do not read a strict newest-first guarantee into a tie." The test asserted what this contract explicitly disclaims.
- `src/mcp_server/tools/deck_management.py:178-204` -- READ-ONLY evidence: forwards `repo.list_decks` order verbatim, no re-sort. With ordering unchanged, this consumer is untouched.
- `tests/integration/mcp_server/test_deck_management_tool.py:158,178` -- READ-ONLY evidence: the suite's only other positional `decks[0]` reads, both on single-deck result sets (`count == 1` asserted). Not flaky, out of scope.
- `scripts/probe_harness.py` -- the committed firing-proof harness. `--expect-red '<node id>'` / `--expect-green`; owns its own argv.

## Tasks & Acceptance

**Execution:**
- [x] `tests/integration/data/test_deck_repository.py` -- add a `_set_updated_at` helper mirroring `_set_created_at` (L16–22), with a docstring naming the ~593 µs clock granularity as the reason -- gives the three timestamp tests a deterministic precondition instead of racing the clock.
- [x] `tests/integration/data/test_deck_repository.py` -- in `test_update_deck_name` and `test_update_deck_strategy`, pin `updated_at` to a fixed old value before calling `update_deck`, then assert the returned value is strictly greater than that pin -- keeps the strict-increase assertion (no widening) while making it satisfiable.
- [x] `tests/integration/data/test_deck_repository.py` -- apply the same pin to `test_merge_updates_timestamp` -- same mechanism, currently latent; fixing it stops the family regrowing.
- [x] `tests/integration/data/test_deck_repository.py` -- rewrite `test_list_decks_with_strategy_field` to assert an id→strategy mapping instead of `decks[0..2]`, and update its docstring to say why order is not asserted here -- the test's purpose is strategy round-tripping; order is owned by `test_list_decks` and `test_list_decks_orders_deterministically_on_created_at_tie`, which already cover it deterministically.

**Results (measured 2026-08-14, branch `fix/r3-deck-list-flake`):**

- 30× loop, before: **22/30 runs red**. After: **0/30**, every run `56 passed` — same test count, nothing dropped or skipped.
- Full gate: `uv run pytest -m "not integration"` → **2988 passed, 1 skipped**; `ruff check` + `ruff format --check` + `mypy src/` → all clean.
- `git diff master --stat` → two files: `tests/integration/data/test_deck_repository.py` and this spec record. `git diff master --name-only -- src ui plugin` → **empty**: no production file changed, so the ordering contract is untouched and no consumer moved.

Firing proofs, all through `scripts/probe_harness` against the FULL suite (tree staged before each plant, `git diff --exit-code` after each revert):

```
plant: DeckModel.updated_at onupdate removed + both explicit stamps removed
full suite (-m 'not integration'): 2989 collected, 3 failed, 0 errored, exit 1
  RED    tests/.../test_deck_repository.py::test_update_deck_name
  RED    tests/.../test_deck_repository.py::test_update_deck_strategy
  RED    tests/.../test_deck_repository.py::test_merge_updates_timestamp

plant: list_decks drops strategy from its projection
full suite (-m 'not integration'): 2989 collected, 1 failed, 0 errored, exit 1
  RED    tests/.../test_deck_repository.py::test_list_decks_with_strategy_field

reverted:
full suite (-m 'not integration'): 2989 collected, 0 failed, exit 0
```

**Acceptance Criteria:**
- Given the fixed file, when `tests/integration/data/test_deck_repository.py` is run 30 times in a row, then 30/30 runs pass (baseline: 22/30 red).
- Given the fixed suite, when `uv run pytest -m "not integration"` runs, then it is green and the collected test count is unchanged from master (no test deleted or silently skipped).
- Given `update_deck` is regressed so it no longer stamps `updated_at`, when `scripts/probe_harness --expect-red` names `test_update_deck_name`, then the harness reports it red through a full-suite run — proving the rewritten assertion still fires.
- Given `test_list_decks_with_strategy_field` is regressed so one deck's strategy is wrong, when the probe harness names it, then it reports red — proving identity-addressing did not weaken the test.
- Given the change, when `git diff master --name-only -- src ui plugin` is run, then it outputs nothing — no production file changed, so `list_decks`' observable ordering is unchanged and no consumer (MCP `list_decks`, companion `/api/decks`, `skills/*/SKILL.md`) is affected. (The branch's full changeset is two files: the test file and this spec record.)
- Given the fixed file, when `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` runs, then all three are clean and pre-commit passes without `--no-verify`.

## Design Notes

Why no production change. The recorded hypothesis (a `created_at` tie making `ORDER BY` nondeterministic) is confirmed but incomplete: it explains only `test_list_decks_with_strategy_field`. The two `update_*` tests fail through a second, independent path — a strict `>` on a clock that has not ticked — which is why they fire even in a three-test isolated run, where no ordering is involved. Measured on master, 200 trials each:

```
datetime.now(UTC) min non-zero step : 593 us
A) create -> update SAME updated_at : 85/200  (42.5%)  -> test_update_deck_{name,strategy}
B) distinct created_at over 3 creates: 1 distinct: 115, 2: 77, 3: 8 -> tie 96% of runs
C) list_decks order != creation order: 140/200 (70%)   -> test_list_decks_with_strategy_field
```

The tie-break `ORDER BY created_at DESC, id` (added by 642cbc6) is correct and is what makes the third failure *deterministically arbitrary* rather than luck-of-the-scan: under a full tie the rows come back in UUID4 order, uncorrelated with creation order, so the positional test passes only ~1-in-6. The contract is right; the test was reading a guarantee out of it that `src/companion/app/routes/decks.py` explicitly documents as absent.

Pinning shape (the helper already in the file, extended):

```python
async def _set_updated_at(session: AsyncSession, deck_id: str, value: datetime) -> None:
    model = await session.get(DeckModel, deck_id)
    assert model is not None
    model.updated_at = value
    await session.commit()
```

An explicit assignment beats the column's `onupdate` (verified), so this pin survives the commit and the subsequent `update_deck` genuinely advances past it.

**Found while proving the fix:** the first planted regression — deleting `deck_model.updated_at = datetime.now(UTC)` from both `update_deck` (`deck.py:199`) and `merge_decks` (`deck.py:692`) — left the full suite **green**. Those two assignments are redundant: `DeckModel.updated_at` carries `onupdate=lambda: datetime.now(UTC)` (`models/deck.py:55`), which stamps the column on any UPDATE regardless. The harness caught what a hand-typed proof would have mis-scored as "my test fired". The real mechanism had to be disabled at the model before the tests went red. The redundancy is left alone — it is harmless, out of scope, and removing a belt-and-braces stamp is not this fix's call.

## Verification

**Commands:**
- `for i in $(seq 1 30); do uv run pytest tests/integration/data/test_deck_repository.py -q --tb=no | tail -1; done` -- expected: 30 lines, every one `56 passed` (or the post-change count), zero `failed`.
- `uv run pytest -m "not integration" -q` -- expected: green, collected count matching master's.
- `uv run python -m scripts.probe_harness --expect-red 'tests/integration/data/test_deck_repository.py::test_update_deck_name'` (with the `updated_at` stamp removed from `update_deck`, tree staged first) -- expected: harness proof line reporting it red; then `git diff --exit-code src/data/repositories/deck.py` to confirm the revert.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: all clean.
- `git diff master --name-only -- src ui plugin` -- expected: no output at all (the production tree is untouched). `git diff master --stat` for the record: two files, the test file and this spec.

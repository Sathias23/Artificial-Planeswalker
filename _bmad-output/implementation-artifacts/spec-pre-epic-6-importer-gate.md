---
title: 'Pre-Epic-6 Importer Gate — oracle-identity dedup + import diagnostics'
type: 'bugfix'
created: '2026-07-15'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'ca85129f081e96d45538891772f46c4c2790f5a0'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Re-running the Scryfall bulk import accumulates duplicate rows per oracle identity — the canonical printing (max `released_at`) shifts between snapshots, each refresh inserts the new printing id, and old rows persist untouched (observed 2026-07-14: 51,189 rows for ~38k cards; 12,992 stale rows with `game_changer` NULL; `find_by_name_exact` resolving 4,711 names to stale printings). Separately, transformer rejects are counted ("Errors: 36") with no card identity or reason surfaced anywhere, and the MCP result drops the count entirely.

**Approach:** Extend the post-import reconcile stage (precedent: `reconcile_games`) into an oracle-identity reconcile: per oracle_id in the current aggregates, repoint `deck_cards` to the canonical row and delete non-canonical duplicates. Capture per-card reject identity + reason into `ImportStatistics`, surfaced via CLI summary and MCP result plus a "stale rows remaining" warning. Pin with re-import integration tests over a persisted SQLite file. (Retro gate G-I1/G-I2/G-I3, epic-5-retro-2026-07-15.md.)

## Boundaries & Constraints

**Always:**
- Repoint `deck_cards.card_id` **before** deleting the stale row, in the same transaction (FK enforcement is OFF — a delete never errors, it silently dangles).
- On repoint collision with `deck_cards` composite PK `(deck_id, card_id, sideboard)` (deck holds both printings), merge by summing `quantity` into the canonical row, then remove the stale row.
- Survivor = the run's `aggregate.canonical_id` row. If that row is absent from the DB (its printing was rejected this run), touch nothing for that oracle_id and count it toward the stale-remaining warning.
- The reconcile stage keeps its non-fatal contract (`IntegrityError`/`DatabaseError` → warning, import still succeeds; next `update=true` retries).
- The pass must be idempotent and must repair an already-damaged DB (51k→~38k) on a plain re-import — no separate migration script.
- `mypy --strict` + ruff clean; repositories keep returning Pydantic, never ORM.

**Ask First:**
- If the 36 rejects turn out to be a transformer defect whose fix requires changing the transform contract (beyond capturing diagnostics), stop and ask — that may be its own spec.
- Any schema change to `cards` or `deck_cards` (none is anticipated).

**Never:**
- No unique index on `oracle_id` / no re-keying of the upsert arbiter (that strategy needs a dedup migration + touches every existing DB; the reconcile pass achieves the same end state with a smaller blast radius).
- No Alembic; no changes to `find_by_name_exact` ordering (dedup makes `ORDER BY id LIMIT 1` moot); no edits under `src/logic/assessment/**`.
- Rows whose oracle_id is absent from the current aggregates are left untouched (out-of-snapshot; not this gate's concern).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Canonical shift re-import | DB row `old-id`; snapshot's canonical is `new-id`, same oracle_id | One row per oracle_id survives (`new-id`) with current data (`game_changer` non-NULL); `find_by_name_exact` resolves to it | N/A |
| Deck references stale row | `deck_cards.card_id = old-id` (deck may also hold `new-id`) | Repointed to `new-id`; if both printings present, quantities summed onto `new-id` and stale deck_cards row removed | N/A |
| Canonical printing rejected (the 36) | Transformer returns `None` for the oracle's canonical printing | Existing rows untouched; oracle_id counted in "stale rows remaining" warning; reject listed with identity + reason | N/A |
| Transformer reject | Card JSON missing required field / raises | `ImportStatistics.rejects` gains (name-or-id, reason); CLI prints each; MCP message carries count + sample names | Reject never aborts the run |
| Reconcile-stage DB error | Lock/disk error mid-reconcile | Import reports success with warning; retry via `update=true` | Non-fatal (existing contract) |
| Already-clean DB | One row per oracle_id | No-op; zero deletes/repoints | N/A |

</frozen-after-approval>

## Code Map

- `src/data/importers/scryfall.py` -- orchestrator; `reconcile_games` (:95-137) = oracle-keyed reconcile precedent; non-fatal wrapper :247-253
- `src/data/importers/importer.py` -- `ImportStatistics` (:15, gains `rejects`); identity-less None-reject counter (:70-72); upsert keyed on `id` (:97, unchanged)
- `src/data/importers/transformers.py` -- reject sites discarding reason (:41-46, :140, :145); expose identity+reason without changing the None contract
- `src/data/importers/aggregate.py` -- `OracleAggregate.canonical_id` (max `released_at`, min-`id` tiebreak) = the survivor; unchanged
- `src/data/models/deck_card.py` -- composite PK `(deck_id, card_id, sideboard)`; FK to `cards.id`, no ondelete, enforcement OFF
- `scripts/import_scryfall_data.py` -- CLI summary (:110-118)
- `src/mcp_server/tools/initialize_database.py` -- `InitializeDatabaseResult` (:49-67) drops `total_errors` today
- `tests/integration/data/test_scryfall_import_e2e.py` -- e2e harness over tmp SQLite; `test_reconcile_updates_stale_preexisting_row` (:247) pins duplicate retention as EXPECTED — flip it
- `src/data/repositories/card.py` -- `find_by_name_exact` `ORDER BY id LIMIT 1` (:192); read-only reference

## Tasks & Acceptance

**Execution:**
- [x] `src/data/importers/scryfall.py` -- extend the reconcile stage into `reconcile_oracle_identities`: per aggregates oracle_id with >1 DB rows, repoint/merge `deck_cards`, delete non-canonical rows, keep games propagation; count skipped oracle_ids (canonical absent) and return reconcile stats to the orchestrator -- G-I1
- [x] `src/data/importers/transformers.py` + `src/data/importers/importer.py` -- capture reject identity (name, else id, else "unknown") + reason (missing field / exception class) into `ImportStatistics.rejects`; keep counting semantics -- G-I2
- [x] `scripts/import_scryfall_data.py` -- print per-reject lines + "stale rows remaining: N oracle identities" warning -- G-I2
- [x] `src/mcp_server/tools/initialize_database.py` -- surface error count + up to 5 sample names + stale warning in the result `message` (no result-schema field changes beyond message unless trivial and additive) -- G-I2
- [x] `tests/integration/data/test_scryfall_import_e2e.py` -- flip `test_reconcile_updates_stale_preexisting_row` to expect dedup; add: two-snapshot shifting-canonical re-import (persisted tmp DB) asserting one-row-per-oracle + `game_changer` survives + `find_by_name_exact` resolves canonical; deck repoint case; quantity-merge case; canonical-rejected untouched case; reject-capture case -- G-I3
- [x] `tests/unit/data/importers/` -- unit-cover `rejects` population and reconcile decision logic where testable without a DB -- G-I3

**Acceptance Criteria:**
- Given a persisted DB imported from snapshot A, when snapshot B with shifted canonical printings is imported, then exactly one row per aggregates oracle_id remains, carrying snapshot-B data, and no `deck_cards` row dangles.
- Given the damaged-DB shape (duplicate oracle_id rows, NULL `game_changer` on stale rows), when a plain import runs, then duplicates collapse and 0 `game_changer` NULLs remain for oracle_ids present in the snapshot.
- Given a run with transformer rejects, when the CLI or MCP import completes, then each reject's identity + reason is visible to the operator (CLI: every line; MCP: count + sample) and rejected-canonical oracle_ids are reported as stale-remaining.
- Given a clean DB, when the import re-runs unchanged, then reconcile performs zero deletes/repoints (idempotence).

## Verification

**Commands:**
- `uv run pytest` -- expected: full suite green (1,136+ baseline, new tests included)
- `uv run mypy src/` -- expected: clean (strict)
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean

**Manual checks (if no CLI):**
- Gate acceptance on the live DB (Sathias): run `uv run python scripts/import_scryfall_data.py`; expect row count ≈ one per oracle identity (~38k), `SELECT count(*) FROM cards WHERE game_changer IS NULL` = 0, and any errors listed by name in the summary.

## Suggested Review Order

**Dedup design — the plan/execute split**

- Entry point: pure, unit-testable planner — survivor selection + canonical-absent skip logic in one place.
  [`scryfall.py:100`](../../src/data/importers/scryfall.py#L100)

- The executor: repoints deck_cards before deleting stale rows, one transaction, FK-off safe.
  [`scryfall.py:145`](../../src/data/importers/scryfall.py#L145)

- Composite-PK collision path: merge-by-summing plus the `occupied`-set chain for sequential stale printings.
  [`scryfall.py:186`](../../src/data/importers/scryfall.py#L186)

**Failure containment (review's critical find)**

- Stage-6 rollback: a read-phase lock error no longer poisons the session (prevented first-run DB wipe).
  [`scryfall.py:417`](../../src/data/importers/scryfall.py#L417)

- `failed` flag keeps a failed reconcile from masquerading as a clean one.
  [`importer.py:18`](../../src/data/importers/importer.py#L18)

**Reject diagnostics**

- `TransformReject` + identity fallback (name → id → "unknown"); optional collector keeps the None contract.
  [`transformers.py:20`](../../src/data/importers/transformers.py#L20)

- Collector threading through the canonical-model iterator into `ImportStatistics.rejects`.
  [`scryfall.py:64`](../../src/data/importers/scryfall.py#L64)

**Operator surfaces**

- MCP message assembly: reject count + samples, stale warning, deletion note, `prune=true` guidance.
  [`initialize_database.py:77`](../../src/mcp_server/tools/initialize_database.py#L77)

- Negative-delta clamp now that reconcile deletes rows.
  [`initialize_database.py:197`](../../src/mcp_server/tools/initialize_database.py#L197)

- CLI summary: reconcile counters, capped reject listing (50), reworded stale-identity warning.
  [`import_scryfall_data.py:130`](../../scripts/import_scryfall_data.py#L130)

**Tests (peripherals)**

- The headline scenario: two snapshots, shifted canonical, one persisted DB → one row, correct resolution, idempotent re-run.
  [`test_scryfall_import_e2e.py:344`](../../tests/integration/data/test_scryfall_import_e2e.py#L344)

- Session-poisoning pin — proven to fail with the P1 rollback removed.
  [`test_scryfall_import_e2e.py:531`](../../tests/integration/data/test_scryfall_import_e2e.py#L531)

- Repoint→merge chain: deck holding two stale printings collapses to quantity 5.
  [`test_scryfall_import_e2e.py:488`](../../tests/integration/data/test_scryfall_import_e2e.py#L488)

- Flipped legacy test: duplicate retention was pinned as expected — now expects dedup.
  [`test_scryfall_import_e2e.py:260`](../../tests/integration/data/test_scryfall_import_e2e.py#L260)

- Pure planner unit coverage (remap/skip/no-op branches).
  [`test_reconcile_plan.py:1`](../../tests/unit/data/importers/test_reconcile_plan.py#L1)

- MCP diagnostics: clamp + prune guidance; reconcile-failure warning.
  [`test_first_run_data_init.py:200`](../../tests/integration/mcp_server/test_first_run_data_init.py#L200)

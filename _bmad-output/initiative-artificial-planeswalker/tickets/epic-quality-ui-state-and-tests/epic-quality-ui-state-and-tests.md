---
type: epic
title: "Quality pass, UI state and tests: the companion re-renders only what changed and never shows silent stale state"
parent: initiative-artificial-planeswalker
covers: []
sources:
  - _bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md
companions:
  - _bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md
  - _bmad-output/initiative-artificial-planeswalker/deferred-work.md
after: []
refined: true
risk: high
---

# Quality pass, UI state and tests: the companion re-renders only what changed and never shows silent stale state

## Description

The UI state and tests lane of the 2026-11 codebase review's fix list (themes Q5 UI, Q6, Q19, Q20 and the guard half of Q22): unused UI surface deleted, App.test.tsx on one shared harness and split into suites, two ESLint rules guarding the one network door and the no-persisted-state rule, a store write that re-renders only what changed, recovery that never leaves silent stale state, and agent-pushed values that cannot reach inherited keys. Split out of epic-codebase-quality-pass at the 2026-11-09 board review.

## Outcome

A user watching the companion while the agent edits a deck sees every change promptly, never a blank or stale panel without a marker; the signal is the closure check and the render-count tests.

## Requirements

1. R5 (review Summary Q5, part): The UI holds no unused props, exports or styles.
2. R6 (review Summary Q6): The root UI tests sit in a shared harness that routes every endpoint, resets every store and declares each helper once, so their outcome does not depend on file order, and `useDeckState` has direct tests.
3. R19 (review Summary Q19): A UI store write re-renders only what changed, the cold open meets its budget when re-measured, and no transient refusal, reconnect loop or agent edit leaves the companion showing stale or blank state without a marker.
4. R20 (review Summary Q20): Agent-pushed values cannot reach inherited object keys or unmount a view, and each guard and tile helper exists once.
5. R22 (review Summary Q22, part): Two ESLint rules hold the one network door and the no-persisted-state rule (D4).

## Constraints

- Each story is one PR off `master` that runs the full Python and UI gate (`AGENTS.md`, Running and verifying), regenerates what it touches (`plugin/` via `scripts.build_plugin`, `npm run gen:api`) and gets its Greptile review; refactors never ride with feature work (review step 6).
- A story's "Tests first" findings land first in its PR: a test pinning a refactor passes on the old code; a test pinning a bug fails on it (review Summary, How to read it, Order).
- Before a pattern fix is called done, every instance of the pattern is grepped, not only the cited lines (review step 6; `AGENTS.md` Known pitfalls).
- A new guard is proved through the committed probe harnesses, once R4's harness fixes have landed (`AGENTS.md` Running and verifying; Summary cross-theme order).
- Decisions D1-D11 bind as recorded, and the Summary's Dropped directions stay dropped (review Summary, Decisions and Dropped).
- A tool contract change updates the five shipped skills and rebuilds `plugin/` in the same PR; an OpenAPI change regenerates `openapi.json` and `types.d.ts`; a schema change ships a `scripts/migrate_*.py`, and a data repair needing no DDL rides the engine's connect hook (`AGENTS.md`).

## Done when

- Every story is done or dropped with a `Dropped:` line, and the closure check finds each fix finding named in a story's `findings` resolved on `master` by that story's PR.
- No story built an item that `deferred-work.md` records for the 2026-11 review or its board review.
- The render-count tests on `master` show a store write re-rendering only the tiles that changed, and the cold open, re-measured with the R4 harness, meets its budget (R19).
- CI on `master` is green, `plugin/`, `openapi.json`, `types.d.ts` and the five skills are in step with the code, and the lane's changes ship in a tagged release.

## Boundaries

- Not here: the other quality lanes (epic-codebase-quality-pass for groundwork, and the epic-quality-* lanes beside it); the deferred findings in `deferred-work.md`; the review Summary's Dropped directions (a bounded-backoff recovery timer above all); any new feature.
- Touch point: agent-view payloads — the inherited-keys and guard stories (was 50 and 51) edit `agentView.ts` and `SuggestionsView` after epic-quick-wins entry 5 adds `deck_id`; owner of the payload fields: epic-quick-wins.
- Must not change: `HISTORY_CAP` retention and revisit semantics beyond the unread fix (was story 49).

## References

- source — `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`, `## Summary` (Decisions, Themes in fix order, cross-theme order, Merged findings, Deferred, Dropped) and the finding stamps in `## Code Review`
- research — `_bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md`, findings F1-F10 cited by the merge groups
- deferred — `_bmad-output/initiative-artificial-planeswalker/deferred-work.md`, the 2026-11-09 entries
- decisions — `_bmad-output/initiative-artificial-planeswalker/tickets/epic-codebase-quality-pass/epic-codebase-quality-pass.md`, Notes (slicing, sequencing, `plan_checkpoint` rule, board review, story renumbering)
- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Constraints
- process — `AGENTS.md` and `CONTRIBUTING.md`, the gate and the generated-artifact table

## Notes

- Decision: 2026-11-09, board review, Brad: split out of epic-codebase-quality-pass, one of six lane epics beside it (groundwork stays there). Requirement ids keep the review's numbering (R<n> is theme Q<n>), so a line here may be one part of a theme another lane shares; story ids were renumbered on the move, and the old-to-new map is in epic-codebase-quality-pass's Notes. The slicing rule, the sequencing rule, the `plan_checkpoint` rule and the board-review rulings recorded there bind this lane. No Refactor sweep (board review batch 2).
- Decision: 2026-11-09, tracer bullet: the first entry (unused UI surface, was story 9). The lane adds no new path through the layers.
- Decision: 2026-11-09 (carried from epic-codebase-quality-pass): `M25` (D4) is split; the ESLint story (was 46) adds the two rules here, and the citation rewording in epic-quality-ui-accessibility-and-polish carries `M25` in its `findings`. `T1-5-D1` is split the same way: the harness story (was 70) builds the harness and the split story (was 11) carries `T1-5-D1`.
- Assumption: a `-D` finding that D1-D11 do not rule is fixed with the option its review run recommended; each story names the option where it shapes the work.

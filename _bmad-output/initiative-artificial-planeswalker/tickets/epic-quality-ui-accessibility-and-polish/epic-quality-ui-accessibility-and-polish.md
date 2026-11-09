---
type: epic
title: "Quality pass, UI accessibility and polish: the companion meets its design and accessibility rules, and its comments and tests mean what they say"
parent: initiative-artificial-planeswalker
covers: []
sources:
  - _bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md
companions:
  - _bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md
  - _bmad-output/initiative-artificial-planeswalker/deferred-work.md
after: []
refined: true
risk: medium
---

# Quality pass, UI accessibility and polish: the companion meets its design and accessibility rules, and its comments and tests mean what they say

## Description

The UI accessibility and polish lane of the 2026-11 codebase review's fix list (theme Q21, the comment half of Q22 and the UI half of Q23): the DESIGN.md, EXPERIENCE.md and NFR-06 rules hold in a real browser (D5-D9), motion, fonts and focus rings rest on enforced rules, UI comments name what enforces each rule today, and the UI tests that cannot fail are fixed. Split out of epic-codebase-quality-pass at the 2026-11-09 board review.

## Outcome

A keyboard, screen-reader or High Contrast user can use every companion panel as DESIGN.md and EXPERIENCE.md describe, and a maintainer can trust the UI's comments and tests; the signal is the closure check and a real-browser pass.

## Requirements

1. R21 (review Summary Q21): The DESIGN.md, EXPERIENCE.md and NFR-06 accessibility and interaction requirements hold in a real browser: focus stays where it belongs, every control and tile has a distinct accurate name, forced colours keep the data marks (best-effort, D7), the full Fan Content notice shows (D5), truncated reasons are recoverable (D6), and previews and announcements follow D8 and D9.
2. R22 (review Summary Q22, part): UI comments name what enforces each rule today, and no comment cites a drifted line number or count.
3. R23 (review Summary Q23, part): Every remaining UI test can fail on the regression it is named for.

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
- The D5-D9 behaviours (full Fan Content notice, recoverable reasons, forced-colours marks, in-view previews, the pill's announcement policy) hold in a real browser on `master` (R21).
- The cold open, re-measured with the R4 harness after the motion, fonts and focus-ring story (was 60), meets its release budget.
- CI on `master` is green, `plugin/`, `openapi.json`, `types.d.ts` and the five skills are in step with the code, and the lane's changes ship in a tagged release.

## Boundaries

- Not here: the other quality lanes (epic-codebase-quality-pass for groundwork, and the epic-quality-* lanes beside it); the deferred findings in `deferred-work.md`; the review Summary's Dropped directions (a generic slotted tile, `aria-pressed` on every control, an app-wide forced-colours pass); any new feature.
- Touch point: agent-view payloads — the suggestion-reasons and groups-and-swaps stories (was 56 and 58) edit `SuggestionsView` and `contracts.py` after epic-quick-wins entry 5 adds `deck_id`; owner of the payload fields: epic-quick-wins.

## References

- source — `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`, `## Summary` (Decisions, Themes in fix order, cross-theme order, Merged findings, Deferred, Dropped) and the finding stamps in `## Code Review`
- research — `_bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md`, findings F1-F10 cited by the merge groups
- deferred — `_bmad-output/initiative-artificial-planeswalker/deferred-work.md`, the 2026-11-09 entries
- decisions — `_bmad-output/initiative-artificial-planeswalker/tickets/epic-codebase-quality-pass/epic-codebase-quality-pass.md`, Notes (slicing, sequencing, `plan_checkpoint` rule, board review, story renumbering)
- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Constraints
- process — `AGENTS.md` and `CONTRIBUTING.md`, the gate and the generated-artifact table

## Notes

- Decision: 2026-11-09, board review, Brad: split out of epic-codebase-quality-pass, one of six lane epics beside it (groundwork stays there). Requirement ids keep the review's numbering (R<n> is theme Q<n>), so a line here may be one part of a theme another lane shares; story ids were renumbered on the move, and the old-to-new map is in epic-codebase-quality-pass's Notes. The slicing rule, the sequencing rule, the `plan_checkpoint` rule and the board-review rulings recorded there bind this lane. No Refactor sweep (board review batch 2).
- Decision: 2026-11-09, tracer bullet: the first entry (footer, state panel, badges and mana symbols, was story 52). The lane adds no new path through the layers.
- Assumption: a `-D` finding that D1-D11 do not rule is fixed with the option its review run recommended; each story names the option where it shapes the work.

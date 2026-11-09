---
type: epic
title: "Quality pass, analysis: legality, synergy, card statistics and power scores are right and agree with the companion"
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

# Quality pass, analysis: legality, synergy, card statistics and power scores are right and agree with the companion

## Description

The analysis lane of the 2026-11 codebase review's fix list (themes Q15-Q17): snow basics and restricted cards get the right verdict, synergy detection sees every card and scores monotonically, `src/logic` owns the card statistics the companion draws (D1), and the power assessment is pinned by tests before its classifiers and combo scoring change. Split out of epic-codebase-quality-pass at the 2026-11-09 board review.

## Outcome

A player gets legality, synergy and power verdicts that are right for their deck, and the agent and the companion report the same figures for it; the signal is the closure check and the re-run assessment benchmark.

## Requirements

1. R15 (review Summary Q15): Format verdicts are right for snow basics and restricted cards, synergy detection sees multi-face text, every keyword holder and real tribal types, cohesion rises with coverage, and analysis output is deterministic across processes.
2. R16 (review Summary Q16): Land count, mana-value buckets and colour counts are defined once in `src/logic` and the companion draws the figures the deck-detail payload carries (D1).
3. R17 (review Summary Q17): The power assessment scores deterministic two-card wins as infinite, credits a combo once, counts the common ramp, removal, draw and tutor wordings, keeps mass land denial for real land denial, names the cards behind each bracket flag, and is pinned by tests before it changes.

## Constraints

- Each story is one PR off `master` that runs the full Python and UI gate (`AGENTS.md`, Running and verifying), regenerates what it touches (`plugin/` via `scripts.build_plugin`, `npm run gen:api`) and gets its Greptile review; refactors never ride with feature work (review step 6).
- A story's "Tests first" findings land first in its PR: a test pinning a refactor passes on the old code; a test pinning a bug fails on it (review Summary, How to read it, Order).
- Before a pattern fix is called done, every instance of the pattern is grepped, not only the cited lines (review step 6; `AGENTS.md` Known pitfalls).
- A new guard is proved through the committed probe harnesses, once R4's harness fixes have landed (`AGENTS.md` Running and verifying; Summary cross-theme order).
- Decisions D1-D11 bind as recorded, and the Summary's Dropped directions stay dropped (review Summary, Decisions and Dropped).
- `src/companion/` writes nothing (AD-2); `src/mcp_server/` imports only the companion leaf (AD-3); `src/viewer/` and `view_deck` change only on a failure path, never in display (AD-15); analysis tools stay observational and MCP tools stateless (`AGENTS.md` Policy).
- A tool contract change updates the five shipped skills and rebuilds `plugin/` in the same PR; an OpenAPI change regenerates `openapi.json` and `types.d.ts`; a schema change ships a `scripts/migrate_*.py`, and a data repair needing no DDL rides the engine's connect hook (`AGENTS.md`).

## Done when

- Every story is done or dropped with a `Dropped:` line, and the closure check finds each fix finding named in a story's `findings` resolved on `master` by that story's PR.
- No story built an item that `deferred-work.md` records for the 2026-11 review or its board review.
- The assessment benchmark re-run on `master` records the score deltas the classifier, combo and bracket stories made, and for a benchmark deck the agent and the companion report the same land count, curve and colour counts (R16, R17).
- CI on `master` is green, `plugin/`, `openapi.json`, `types.d.ts` and the five skills are in step with the code, and the lane's changes ship in a tagged release.

## Boundaries

- Not here: the other quality lanes (epic-codebase-quality-pass for groundwork, and the epic-quality-* lanes beside it); the deferred findings and options in `deferred-work.md` (`B4-D3` option b, `B5-D3` option b, `B5-D5` option b, the mana-curve polish); the review Summary's Dropped directions; any new feature or tool; the frozen viewer's display.
- Touch point: legality coverage — the restricted-card story (was 32) lands before epic-quick-wins entry 4, so R6's coverage table lists no restricted line; owner of the coverage table: epic-quick-wins.
- Touch point: combo credit — the combo-scoring story (was 39) credits each Spellbook variant once; owner of the combo list: epic-trustworthy-assessment (R15).

## References

- source — `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`, `## Summary` (Decisions, Themes in fix order, cross-theme order, Merged findings, Deferred, Dropped) and the finding stamps in `## Code Review`
- research — `_bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md`, findings F1-F10 cited by the merge groups
- deferred — `_bmad-output/initiative-artificial-planeswalker/deferred-work.md`, the 2026-11-09 entries
- decisions — `_bmad-output/initiative-artificial-planeswalker/tickets/epic-codebase-quality-pass/epic-codebase-quality-pass.md`, Notes (slicing, sequencing, `plan_checkpoint` rule, board review, story renumbering)
- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Constraints
- process — `AGENTS.md` and `CONTRIBUTING.md`, the gate and the generated-artifact table

## Notes

- Decision: 2026-11-09, board review, Brad: split out of epic-codebase-quality-pass, one of six lane epics beside it (groundwork stays there). Requirement ids keep the review's numbering (R<n> is theme Q<n>), so a line here may be one part of a theme another lane shares; story ids were renumbered on the move, and the old-to-new map is in epic-codebase-quality-pass's Notes. The slicing rule, the sequencing rule, the `plan_checkpoint` rule and the board-review rulings recorded there bind this lane. No Refactor sweep (board review batch 2).
- Decision: 2026-11-09, tracer bullet: the first entry (snow basics and restricted cards, was story 32), which also unblocks epic-quick-wins entry 4.
- Decision: 2026-11-09, board review, Brad: initiative R16 binds only epic-trustworthy-assessment's own changes; the assessment pins (was story 37) land before that epic's first story, and that epic lands before the classifier story (was 38), so R16 is measured against today's baseline. The classifier, combo and bracket stories each re-run the benchmark and record their deltas in the PR.
- Assumption: whether the assessment profile version moves is settled in the classifier and combo stories' PRs (B5-D1).
- Assumption: a `-D` finding that D1-D11 do not rule is fixed with the option its review run recommended; each story names the option where it shapes the work.

---
type: epic
title: "Quality pass, MCP tools: every tool answers failures as a status and treats the same input the same way"
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

# Quality pass, MCP tools: every tool answers failures as a status and treats the same input the same way

## Description

The MCP tools lane of the 2026-11 codebase review's fix list (themes Q5 backend, Q7-Q11): dead backend surface deleted, every infrastructure failure answered as a status, one normaliser per parameter kind, one card-name resolver, tool descriptions and skills that list what the tools really return, and search filters that do what they say. Split out of epic-codebase-quality-pass at the 2026-11-09 board review; each entry states what it fixes, what that costs today, how wide it is and the finding ids it resolves.

## Outcome

An agent calling any MCP tool gets a status it can act on, never a raised error, and the same input means the same thing in every tool; the signal is the closure check against the review's finding stamps.

## Requirements

1. R5 (review Summary Q5, part): The backend holds no unused repository methods, unreachable analysis code, sentinel-writing health check, stale scripts or unused dev dependency.
2. R7 (review Summary Q7): Every MCP tool answers a corrupt or locked database, a missing sqlite-vec extension, an offline model load and a failed combo read with a status, never a raised error, and a failed combo read degrades the assessment instead of scoring it combo-free.
3. R8 (review Summary Q8): Each tool parameter kind (format, games, ids, names, colours, paging) is normalised once at the tool edge, so the same input means the same thing in every tool and an unbindable or unknown value answers `invalid`.
4. R9 (review Summary Q9): Every tool resolves card names through one indexed, bounded resolver that escapes wildcards and reports a capped count as capped.
5. R10 (review Summary Q10): Tool descriptions, result models and the five skills name every status a tool returns and document every tool; one fact has one token where D3 does not keep two; mixed-printing Arena imports and format defaults behave as an agent would expect; stdio is the only transport.
6. R11 (review Summary Q11): Colour, rarity and paging filters do what their docstrings say, the same way on the relational and semantic paths, and `at_most` is documented as filtering card colours (D2).

## Constraints

- Each story is one PR off `master` that runs the full Python and UI gate (`AGENTS.md`, Running and verifying), regenerates what it touches (`plugin/` via `scripts.build_plugin`, `npm run gen:api`) and gets its Greptile review; refactors never ride with feature work (review step 6).
- A story's "Tests first" findings land first in its PR: a test pinning a refactor passes on the old code; a test pinning a bug fails on it (review Summary, How to read it, Order).
- Before a pattern fix is called done, every instance of the pattern is grepped, not only the cited lines (review step 6; `AGENTS.md` Known pitfalls).
- Every semantic-search change carries its recall sanity eval; ranking changes wait for R3's recall job (review step 6; Summary cross-theme order).
- A new guard is proved through the committed probe harnesses, once R4's harness fixes have landed (`AGENTS.md` Running and verifying; Summary cross-theme order).
- Decisions D1-D11 bind as recorded, and the Summary's Dropped directions stay dropped (review Summary, Decisions and Dropped).
- `src/companion/` writes nothing (AD-2); `src/mcp_server/` imports only the companion leaf (AD-3); `src/viewer/` and `view_deck` change only on a failure path, never in display (AD-15); analysis tools stay observational and MCP tools stateless (`AGENTS.md` Policy).
- A tool contract change updates the five shipped skills and rebuilds `plugin/` in the same PR; an OpenAPI change regenerates `openapi.json` and `types.d.ts`; a schema change ships a `scripts/migrate_*.py`, and a data repair needing no DDL rides the engine's connect hook (`AGENTS.md`).

## Done when

- Every story is done or dropped with a `Dropped:` line, and the closure check finds each fix finding named in a story's `findings` resolved on `master` by that story's PR.
- No story built an item that `deferred-work.md` records for the 2026-11 review or its board review.
- Every MCP tool, driven through its entry point against a locked or corrupt database, a missing sqlite-vec extension and an offline model load, answers a status (R7).
- CI on `master` is green, `plugin/`, `openapi.json`, `types.d.ts` and the five skills are in step with the code, and the lane's changes ship in a tagged release.

## Boundaries

- Not here: the other quality lanes (epic-codebase-quality-pass for groundwork, and the epic-quality-* lanes beside it); the deferred findings in `deferred-work.md`; the review Summary's Dropped directions; any new feature or tool; the frozen viewer's display.
- Touch point: card-name resolution — the one-resolver story (was 16) lands before epic-reliable-deck-workflows entry 1, which builds on it; owner: epic-reliable-deck-workflows (initiative R10).
- Touch point: Arena import — the mixed-printing story (was 71) lands before epic-reliable-deck-workflows entry 4; owner of import results and round trips: epic-reliable-deck-workflows (R11, R13).

## References

- source — `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`, `## Summary` (Decisions, Themes in fix order, cross-theme order, Merged findings, Deferred, Dropped) and the finding stamps in `## Code Review`
- research — `_bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md`, findings F1-F10 cited by the merge groups
- deferred — `_bmad-output/initiative-artificial-planeswalker/deferred-work.md`, the 2026-11-09 entries
- decisions — `_bmad-output/initiative-artificial-planeswalker/tickets/epic-codebase-quality-pass/epic-codebase-quality-pass.md`, Notes (slicing, sequencing, `plan_checkpoint` rule, board review, story renumbering)
- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Constraints
- process — `AGENTS.md` and `CONTRIBUTING.md`, the gate and the generated-artifact table

## Notes

- Decision: 2026-11-09, board review, Brad: split out of epic-codebase-quality-pass, one of six lane epics beside it (groundwork stays there). Requirement ids keep the review's numbering (R<n> is theme Q<n>), so a line here may be one part of a theme another lane shares; story ids were renumbered on the move, and the old-to-new map is in epic-codebase-quality-pass's Notes. The slicing rule, the sequencing rule, the `plan_checkpoint` rule and the board-review rulings recorded there bind this lane. No Refactor sweep (board review batch 2).
- Decision: 2026-11-09, tracer bullet: the first entry (dead backend surface, was story 8). The lane adds no new path through the layers; deleting the dead surface first means no later story fixes code that is about to go.
- Assumption: a `-D` finding that D1-D11 do not rule is fixed with the option its review run recommended; each story names the option where it shapes the work.

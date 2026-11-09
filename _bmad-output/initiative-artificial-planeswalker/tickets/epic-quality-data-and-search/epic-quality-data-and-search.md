---
type: epic
title: "Quality pass, data and search: the repository, import and index follow one set of rules and report failure honestly"
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

# Quality pass, data and search: the repository, import and index follow one set of rules and report failure honestly

## Description

The data and search lane of the 2026-11 codebase review's fix list (themes Q12-Q14, the Python half of Q23 and the lint half of Q24): the model and repository follow the loading and transaction rules AGENTS.md states, the import is serialised, off the MCP loop and honest about failure, the semantic index fills filtered results and trusts no half-written build, and the Python tests that cannot fail are fixed or deleted. Split out of epic-codebase-quality-pass at the 2026-11-09 board review.

## Outcome

The maintainer refreshes the card database and the search index and gets an honest result every time, through repository code that follows its stated rules; the signal is the closure check against the review's finding stamps.

## Requirements

1. R12 (review Summary Q12): The data model and the deck repository follow the relationship-loading, transaction and reload rules `AGENTS.md` states (collections noload, scalar relations raise; one transaction rule; a reload that tolerates a vanished row), `list_decks` reads no card rows, and the published deck and card schemas match the database.
2. R13 (review Summary Q13): The import is serialised, runs off the MCP loop, reports an empty or degraded run as a failure, stores the English canonical printing and WUBRG colours, keeps deck commander flags through reconcile, and its downloader classifies failures honestly.
3. R14 (review Summary Q14): Filtered semantic searches return a full result where the index holds one, orphan vectors are pruned by default, the index trusts no half-written build, and both rebuild paths are one tested implementation.
4. R23 (review Summary Q23, part): Every remaining Python test can fail on the regression it is named for, and no test asserts documentation text or reads a planning artefact.
5. R24 (review Summary Q24, part): Eager log formatting and untyped scripts are caught by lint and type checks in CI and pre-commit.

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
- On `master`, `initialize_database(update=true)` and an index build on the real `cards.db` report honestly and leave no orphan vectors, and a filtered `limit=10` semantic query returns 10 results where the index holds them (R13, R14).
- CI on `master` is green, `plugin/`, `openapi.json`, `types.d.ts` and the five skills are in step with the code, and the lane's changes ship in a tagged release.

## Boundaries

- Not here: the other quality lanes (epic-codebase-quality-pass for groundwork, and the epic-quality-* lanes beside it); the deferred findings in `deferred-work.md` (`M15` and `B6-D3` above all); the review Summary's Dropped directions; any new feature or tool.

## References

- source — `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`, `## Summary` (Decisions, Themes in fix order, cross-theme order, Merged findings, Deferred, Dropped) and the finding stamps in `## Code Review`
- research — `_bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md`, findings F1-F10 cited by the merge groups
- deferred — `_bmad-output/initiative-artificial-planeswalker/deferred-work.md`, the 2026-11-09 entries
- decisions — `_bmad-output/initiative-artificial-planeswalker/tickets/epic-codebase-quality-pass/epic-codebase-quality-pass.md`, Notes (slicing, sequencing, `plan_checkpoint` rule, board review, story renumbering)
- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Constraints
- process — `AGENTS.md` and `CONTRIBUTING.md`, the gate and the generated-artifact table

## Notes

- Decision: 2026-11-09, board review, Brad: split out of epic-codebase-quality-pass, one of six lane epics beside it (groundwork stays there). Requirement ids keep the review's numbering (R<n> is theme Q<n>), so a line here may be one part of a theme another lane shares; story ids were renumbered on the move, and the old-to-new map is in epic-codebase-quality-pass's Notes. The slicing rule, the sequencing rule, the `plan_checkpoint` rule and the board-review rulings recorded there bind this lane. No Refactor sweep (board review batch 2).
- Decision: 2026-11-09, tracer bullet: the first entry (engine and model conventions, was story 21). The lane adds no new path through the layers.
- Assumption: the English-printing and WUBRG changes (was story 25) reach existing databases through the next `initialize_database(update=true)`, with no connect-hook repair.
- Assumption: a `-D` finding that D1-D11 do not rule is fixed with the option its review run recommended; each story names the option where it shapes the work.

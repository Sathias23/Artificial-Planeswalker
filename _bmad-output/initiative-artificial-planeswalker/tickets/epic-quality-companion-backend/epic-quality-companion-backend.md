---
type: epic
title: "Quality pass, companion backend: routes, discovery, push outcomes and the published contract say what the code does"
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

# Quality pass, companion backend: routes, discovery, push outcomes and the published contract say what the code does

## Description

The companion backend lane of the 2026-11 codebase review's fix list (theme Q18): the image route touches the database only on a cache miss, errors log safely and name the real failure, discovery publishes on Windows and stays private on POSIX, push and receipt outcomes name the real result, and the published contract carries only answerable responses and bounded fields. Split out of epic-codebase-quality-pass at the 2026-11-09 board review.

## Outcome

The companion serves images cheaply, starts on Windows while a reader holds its discovery file, and reports every push as what really happened; the signal is the closure check against the review's finding stamps.

## Requirements

1. R18 (review Summary Q18): The image route touches the database only on a cache miss and holds no session through the pacer wait, request and image size ceilings hold on wire bytes, logs carry no raw caller input, discovery publishes on Windows and stays private on POSIX, push and receipt outcomes name the real result, and the published contract carries only answerable responses and bounded fields.

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
- On Windows, the companion launches while another process holds `companion.json` open, and the regenerated `openapi.json` on `master` carries no response the code cannot answer (R18).
- CI on `master` is green, `plugin/`, `openapi.json`, `types.d.ts` and the five skills are in step with the code, and the lane's changes ship in a tagged release.

## Boundaries

- Not here: the other quality lanes (epic-codebase-quality-pass for groundwork, and the epic-quality-* lanes beside it); the deferred findings in `deferred-work.md`; the review Summary's Dropped directions; any new feature or tool.
- Touch point: agent-view payloads — the push-deadline and contract stories (8.4 and 8.5, was 44 and 45) edit `contracts.py` after epic-quick-wins entry 5 adds `deck_id` to the `companion_show_*` payloads; owner of the payload fields: epic-quick-wins.

## References

- source — `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`, `## Summary` (Decisions, Themes in fix order, cross-theme order, Merged findings, Deferred, Dropped) and the finding stamps in `## Code Review`
- research — `_bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md`, findings F1-F10 cited by the merge groups
- deferred — `_bmad-output/initiative-artificial-planeswalker/deferred-work.md`, the 2026-11-09 entries
- decisions — `_bmad-output/initiative-artificial-planeswalker/tickets/epic-codebase-quality-pass/epic-codebase-quality-pass.md`, Notes (slicing, sequencing, `plan_checkpoint` rule, board review, story renumbering)
- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Constraints
- process — `AGENTS.md` and `CONTRIBUTING.md`, the gate and the generated-artifact table

## Notes

- Decision: 2026-11-09, board review, Brad: split out of epic-codebase-quality-pass, one of six lane epics beside it (groundwork stays there). Requirement ids keep the review's numbering (R<n> is theme Q<n>), so a line here may be one part of a theme another lane shares; story ids were renumbered on the move, and the old-to-new map is in epic-codebase-quality-pass's Notes. The slicing rule, the sequencing rule, the `plan_checkpoint` rule and the board-review rulings recorded there bind this lane. No Refactor sweep (board review batch 2).
- Decision: 2026-11-09, tracer bullet: the first entry (the image route, 8.1, was story 41). The lane adds no new path through the layers.
- Assumption: a `-D` finding that D1-D11 do not rule is fixed with the option its review run recommended; each story names the option where it shapes the work.
- Decision: 2026-11-09, re-scope, Brad: build only the stories that fix something a user or the user's data would hit, then return to feature work. Every other live story stays on the board as backlog, pulled in when a feature touches the same files; nothing is dropped or deferred by this ruling. A backlog story's plan holds `status: draft` and a `blocked_reason` starting "backlog (re-scope 2026-11-09", so `tickets.py next` lists it as blocked; pulling one in is `tickets.py mark <ref> draft` (which clears the block) and a check of its `after`. The core list and its build order are under `### Re-scope (2026-11-09)` in the review plan's `## Summary`. Core here: 8.1, the lane's tracer bullet; its `after` (4.2, 4.4) is unchanged and both are core. The rest of the lane is backlog.

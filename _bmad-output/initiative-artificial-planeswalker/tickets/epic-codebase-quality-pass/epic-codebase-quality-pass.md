---
type: epic
title: "Codebase quality pass: the 2026-11 review's fix list is closed"
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

# Codebase quality pass: the 2026-11 review's fix list is closed

## Description

The 2026-11 full codebase review (an architecture pass, 21 group reviews, five targeted test runs and a configuration review, all at `ee0263d`) left 387 distinct findings in 25 themes: 385 fix, 2 deferred, none open after decisions D1-D11. This epic carries every fix finding to `master`, one PR per story, in the review's fix order: the data-loss traps first, then the test, CI and harness groundwork the later themes rely on, then the tool, data, analysis, companion and UI themes, and the comment, test-design and toolchain cleanup last. Brad's 2026-11-09 ruling takes all of it; he judges at board review which stories are worth building, so each entry states what it fixes, what that costs today, how wide it is and the finding ids it resolves.

## Outcome

The maintainer works on a codebase whose tools answer every failure as a status, whose agent and companion agree on every figure, whose guards and harnesses can go red, and whose comments and tests mean what they say; the signal is the closure check below, run against the review's finding stamps.

## Requirements

1. R1 (review Summary Q1): No command in the repository can destroy the operator's database or write a different database file from the one the server reads, and the shipped plugin installs no dev toolchain.
2. R2 (review Summary Q2): Python and UI tests run without touching the developer's data directory, share one set of fixtures and builders, fail on React warnings, and do not hang or poll where an awaited condition will do.
3. R3 (review Summary Q3): CI runs the semantic recall eval and the Windows halves of the companion unit suite, every job has a timeout, uv is pinned, and a delete-only commit triggers the plugin-sync check.
4. R4 (review Summary Q4): A probe-harness proof line and a cold-open budget verdict are each true of the run they report, every harness run is bounded in time, and a failed harness step leaves no browser or companion process behind.
5. R5 (review Summary Q5): The repository holds no unused repository methods, unreachable analysis code, sentinel-writing health check, stale scripts, unused UI props or exports, or unused dev dependency.
6. R6 (review Summary Q6): The root UI tests sit in a shared harness that routes every endpoint, resets every store and declares each helper once, so their outcome does not depend on file order, and `useDeckState` has direct tests.
7. R7 (review Summary Q7): Every MCP tool answers a corrupt or locked database, a missing sqlite-vec extension, an offline model load and a failed combo read with a status, never a raised error, and a failed combo read degrades the assessment instead of scoring it combo-free.
8. R8 (review Summary Q8): Each tool parameter kind (format, games, ids, names, colours, paging) is normalised once at the tool edge, so the same input means the same thing in every tool and an unbindable or unknown value answers `invalid`.
9. R9 (review Summary Q9): Every tool resolves card names through one indexed, bounded resolver that escapes wildcards and reports a capped count as capped.
10. R10 (review Summary Q10): Tool descriptions, result models and the five skills name every status a tool returns and document every tool; one fact has one token where D3 does not keep two; mixed-printing Arena imports and format defaults behave as an agent would expect; stdio is the only transport.
11. R11 (review Summary Q11): Colour, rarity and paging filters do what their docstrings say, the same way on the relational and semantic paths, and `at_most` is documented as filtering card colours (D2).
12. R12 (review Summary Q12): The data model and the deck repository follow the relationship-loading, transaction and reload rules `AGENTS.md` states (collections noload, scalar relations raise; one transaction rule; a reload that tolerates a vanished row), `list_decks` reads no card rows, and the published deck and card schemas match the database.
13. R13 (review Summary Q13): The import is serialised, runs off the MCP loop, reports an empty or degraded run as a failure, stores the English canonical printing and WUBRG colours, keeps deck commander flags through reconcile, and its downloader classifies failures honestly.
14. R14 (review Summary Q14): Filtered semantic searches return a full result where the index holds one, orphan vectors are pruned by default, a model change forces a re-embed, and both rebuild paths are one tested implementation.
15. R15 (review Summary Q15): Format verdicts are right for snow basics and restricted cards, synergy detection sees multi-face text, every keyword holder and real tribal types, cohesion rises with coverage, and analysis output is deterministic across processes.
16. R16 (review Summary Q16): Land count, mana-value buckets and colour counts are defined once in `src/logic` and the companion draws the figures the deck-detail payload carries (D1).
17. R17 (review Summary Q17): The power assessment scores deterministic two-card wins as infinite, credits a combo once, counts the common ramp, removal, draw and tutor wordings, keeps mass land denial for real land denial, names the cards behind each bracket flag, and is pinned by tests before it changes.
18. R18 (review Summary Q18): The image route touches the database only on a cache miss and holds no session through the pacer wait, request and image size ceilings hold on wire bytes, logs carry no raw caller input, discovery publishes on Windows and stays private on POSIX, push and receipt outcomes name the real result, and the published contract carries only answerable responses and bounded fields.
19. R19 (review Summary Q19): A UI store write re-renders only what changed, the cold open meets its budget when re-measured, and no transient refusal, reconnect loop or agent edit leaves the companion showing stale or blank state without a marker.
20. R20 (review Summary Q20): Agent-pushed values cannot reach inherited object keys or unmount a view, and each guard and tile helper exists once.
21. R21 (review Summary Q21): The DESIGN.md, EXPERIENCE.md and NFR-06 accessibility and interaction requirements hold in a real browser: focus stays where it belongs, every control and tile has a distinct accurate name, forced colours keep the data marks (best-effort, D7), the full Fan Content notice shows (D5), truncated reasons are recoverable (D6), and previews and announcements follow D8 and D9.
22. R22 (review Summary Q22): UI comments name what enforces each rule today, two ESLint rules hold the one network door and the no-persisted-state rule (D4), and no comment cites a drifted line number or count.
23. R23 (review Summary Q23): Every remaining test can fail on the regression it is named for, and no test asserts documentation text or reads a planning artefact.
24. R24 (review Summary Q24): Pre-commit and CI run the same locked toolchain (D10), the leak guard catches any user-profile path in CI (D11), eager log formatting and untyped scripts are caught, and CI covers the runtimes users run with a canary that can go red.
25. R25 (review Summary Q25): Every `migrate_*.py` is tested and safe to re-run on a user's only database, and the build scripts install no global logging on import.

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

- Every story is done or dropped with a `Dropped:` line, and the closure check finds each of the 385 fix findings resolved on `master` by the PR of the story whose `findings` name it.
- `deferred-work.md` still records `M15`, `T1-2-D1` and the four deferred options, and no story built one of them.
- CI on `master` is green, including the recall-eval job and the Windows companion unit files R3 adds.
- The cold open, re-measured with the R4 harness after the last UI story (story 60), meets its release budget.
- `plugin/`, `openapi.json`, `types.d.ts` and the five skills are in step with the tools, and the changes ship in a tagged release.

## Boundaries

- Not here: the deferred findings and options in `deferred-work.md` (`M15`, `T1-2-D1`, `B4-D3` option b, `B5-D5` option b, `B5-D3` option b, a colour-identity search filter); the Dropped directions in the review Summary; any new feature or tool; the frozen viewer's display.
- Touch point: card-name resolution — story 16 folds today's three resolvers into one; epic-reliable-deck-workflows R10 (bulk lookup and import resolution) builds on the same resolver; owner: epic-reliable-deck-workflows (initiative R10). Which lands first is an open question in the initiative's Notes.
- Touch point: legality coverage — story 32 models restricted cards, which epic-quick-wins R6 lists as an unchecked Vintage rule; owner of the coverage table: epic-quick-wins.
- Touch point: combo credit — story 39 credits each Spellbook variant once; epic-trustworthy-assessment R15 separates complete combos from suggestions; owner of the combo list: epic-trustworthy-assessment.
- Touch point: Arena import — story 71 sums mixed-printing lines; epic-reliable-deck-workflows R11 and R13 own import results and round trips; owner: epic-reliable-deck-workflows.
- Touch point: agent-view payloads — stories 44, 45, 50, 51, 56 and 58 edit `contracts.py`, `agentView.ts` and `SuggestionsView`, where epic-quick-wins entry 5 adds `deck_id` to the `companion_show_*` payloads; owner of the payload fields: epic-quick-wins.
- Must not change: `HISTORY_CAP` retention and revisit semantics beyond story 49's unread fix.

## References

- source — `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`, `## Summary` (Decisions, Themes in fix order, cross-theme order, Merged findings, Deferred, Dropped) and the finding stamps in `## Code Review`
- research — `_bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md`, findings F1-F10 cited by the merge groups
- deferred — `_bmad-output/initiative-artificial-planeswalker/deferred-work.md`, the 2026-11-09 entries
- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Constraints
- architecture — `docs/architecture.md`; `_bmad-output/initiative-artificial-planeswalker/architecture-Artificial-Planeswalker-2026-07-25/architecture-Artificial-Planeswalker-2026-07-25.md`, AD-2, AD-3, AD-4, AD-6, AD-12, AD-15
- process — `AGENTS.md` and `CONTRIBUTING.md`, the gate and the generated-artifact table

## Notes

- Decision: 2026-11-09, Brad: scope is all 25 themes and all 385 fix findings; nothing is cut now. He reviews the board afterwards to decide which stories are real.
- Decision: 2026-11-09, one epic, as the review's step 5 names it. The breakdown runs to 71 stories, past the usual 8-12; a split into lane epics (groundwork, tools and data, analysis, companion backend, UI, cleanup) is offered, not made (Open question below).
- Decision: 2026-11-09, the epic serves no initiative Requirements line, so `covers` is empty and each Requirements line cites its review theme.
- Decision: 2026-11-09, slicing rule: one story per theme, split where a theme spans code lanes that ship separately (Python and UI gates, tool, repository and backend layers, one file's distinct jobs) or would outrun one session. A story's tests-first findings ride in it. Each finding is in exactly one entry's `findings`.
- Decision: 2026-11-09, tracer bullet: story 1 (R1, the data-loss traps). The pass adds no new path through the layers; R1 goes first in the review's order and depends on nothing.
- Decision: 2026-11-09, sequencing follows the Summary's cross-theme order: R1 first; R2 before stories that add tests; R3 before the ranking changes and the Windows fixes; R4 before stories that prove guards through the harnesses and before the cold-open re-measure; R5 before R9, R12, R15 and R16; R6 before R19-R21; R7 before R8 and R10; R15's tests before R16; R19 before R20 and R21; R22's comment sweep after R19-R21. Two deviations from table order by theme number: story 3 (UI test setup, R2) is built after story 5 because its proof line needs the fixed vitest harness, and the App.test.tsx harness (70) and split (11) come before story 10, as T1-5-D1 advises. Other `after` keys mark stories that edit the same source, test or config files. Shared docs (`AGENTS.md`, DESIGN.md, EXPERIENCE.md, the skills) and generated artifacts (`plugin/`, `openapi.json`, `types.d.ts`, which each PR regenerates on its rebased branch) do not count as a collision.
- Decision: 2026-11-09, `M25` (D4) is split: story 46 adds its two ESLint rules at the start of the UI work, and story 61 rewords the citations and carries `M25` in its `findings`. Likewise `T1-5-D1`'s two changes: story 70 builds the harness and story 11, which carries `T1-5-D1`, does the move-only split.
- Decision: 2026-11-09, `plan_checkpoint = true` marks a story that changes a tool's parameters, statuses, defaults, annotations or caller-facing instructions, the transport the server is reached over, a model, field, bound, response or description published in the OpenAPI contract, or a stored schema. Corrections that make a description match unchanged behaviour, and score changes with no new vocabulary (story 39), do not count. Marked: 12, 14, 15, 17, 18, 71, 19, 20, 23, 31, 32, 36, 40, 44, 45, 56, 58.
- Decision: 2026-11-09, the epic closes with a "Refactor sweep" (story 69), proposed by default; Brad can drop it at board review.
- Decision: 2026-11-09, the stories Brad is likely least sure of are 31 (adaptive k with the recall eval) and 39 (assessment scoring); neither moves forward, because each needs its groundwork stories first.
- Decision: 2026-11-09, validation round 1 (fresh-context Set, Dependencies, Ticket and Tree checks): story 21 follows B1-D3 option (a), `lazy="raise"`; story 11 split into 70 (harness) and 11 (split); story 18 split into 18 (deck-tool tokens) and 71 (Arena import); story 39 unmarked as a checkpoint; `after` keys added for the Windows fix in 41, the harness proofs in 3 and 21, and shared files in 21, 37, 66, 49 and 59; the release-budget re-measure also runs in story 60. Round 2 added `after` keys for shared files (47 and 36 after 10, 71 and 32 after 18, 63 after 32, 64 after 62) and passed.
- Assumption: a `-D` finding that D1-D11 do not rule is fixed with the option its review run recommended; each story names the option where it shapes the work.
- Assumption: stories 38 and 39 re-run the assessment benchmark, and whether the profile version moves is settled in their PRs (B5-D1).
- Assumption: story 25's data changes (English printing, WUBRG colours) reach existing databases through the next `initialize_database(update=true)` (upsert plus reconcile), with no connect-hook repair.
- Open question: split the 71 stories into lane epics before building, or keep one epic? Brad, at board review.
- Open question: build order between this epic and epics 1-3 where they meet (stories 16, 32, 39, 71 and the agent-view payload stories against epic-reliable-deck-workflows entries 1 and 4, epic-quick-wins entries 4 and 5, epic-trustworthy-assessment R15); recorded in the initiative's Notes. Brad, at board review.
- Source conflict: stories 38-40 (review B5-D1 to D5, B5-P1 to P13) vs initiative R16 and epic-trustworthy-assessment R3 — they change supported Commander and Standard scores, which R16 says stay unchanged apart from the incomplete-combo correction. Settle before story 38 is built: does R16 bind only epic 3's own changes?
- Source conflict: story 32 (review B4-D1) vs epic-quick-wins R6 — B4-D1 makes restricted a checked Vintage rule, R6 reports restricted as unchecked. Settle before story 32 or epic-quick-wins entry 4 is built, whichever comes first.

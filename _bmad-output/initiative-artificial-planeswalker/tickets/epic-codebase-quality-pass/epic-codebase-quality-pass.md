---
type: epic
title: "Codebase quality pass, groundwork: no command can destroy the operator's data, and the tests, CI and harnesses can go red"
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

# Codebase quality pass, groundwork: no command can destroy the operator's data, and the tests, CI and harnesses can go red

## Description

The groundwork lane of the 2026-11 full codebase review's fix list (themes Q1-Q4, Q25 and the toolchain half of Q24). The review (an architecture pass, 21 group reviews, five targeted test runs and a configuration review, all at `ee0263d`) left 385 fix findings in 25 themes; this epic carried all of them until the 2026-11-09 board review dropped four stories, deferred five findings and split the rest into six lane epics beside this one (epic-quality-mcp-tools, epic-quality-data-and-search, epic-quality-analysis, epic-quality-companion-backend, epic-quality-ui-state-and-tests, epic-quality-ui-accessibility-and-polish). This lane goes first: the data-loss traps, then the test, CI, harness, toolchain and migration groundwork the other lanes rely on. Each entry states what it fixes, what that costs today, how wide it is and the finding ids it resolves.

## Outcome

The maintainer can run every repository command without risk to the operator's data, and trusts that the tests, CI and harnesses go red when they should; the signal is the closure check below, run against the review's finding stamps.

## Requirements

1. R1 (review Summary Q1): No command in the repository can destroy the operator's database or write a different database file from the one the server reads, and the shipped plugin installs no dev toolchain.
2. R2 (review Summary Q2): Python and UI tests run without touching the developer's data directory, share one set of fixtures and builders, fail on React warnings, and do not hang or poll where an awaited condition will do.
3. R3 (review Summary Q3): CI runs the semantic recall eval and the Windows halves of the companion unit suite, every job has a timeout, uv is pinned, and a delete-only commit triggers the plugin-sync check.
4. R4 (review Summary Q4): A probe-harness proof line and a cold-open budget verdict are each true of the run they report, every harness run is bounded in time, and a failed harness step leaves no browser or companion process behind.
5. R24 (review Summary Q24, part): Pre-commit and CI run the same locked toolchain (D10), the leak guard catches any user-profile path in CI (D11), and CI covers the runtimes users run with a canary that can go red.
6. R25 (review Summary Q25): Every `migrate_*.py` is tested and safe to re-run on a user's only database, and the build scripts install no global logging on import.

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
- `deferred-work.md` still records `M15`, `T1-2-D1`, the four deferred options and the board-review drops (story 33's findings, `B6-D3`), and no story in any quality lane built one of them.
- CI on `master` is green, including the recall-eval job and the Windows companion unit files R3 adds, and every job has a timeout.
- A probe-harness run and a cold-open budget run on `master` each report a verdict that is true of the run (R4).
- `plugin/` is in step with the code, and the lane's changes ship in a tagged release.

## Boundaries

- Not here: the six other quality lanes (epic-quality-mcp-tools, epic-quality-data-and-search, epic-quality-analysis, epic-quality-companion-backend, epic-quality-ui-state-and-tests, epic-quality-ui-accessibility-and-polish), which own every touch point with epics 1-3; the deferred findings and options in `deferred-work.md`; the Dropped directions in the review Summary; any new feature or tool.

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
- Decision: 2026-11-09, board review batch 1 (groundwork), Brad: stories 1-7, 65 and 68 kept as written; story 67 merged into 65 (both are CI and toolchain config in the same files, too small for their own PR and Greptile round). Story 65 now carries 67's nine findings, its verify and its width; 68 waits on 65 in 67's place.
- Dropped: story 67, 2026-11-09, merged into story 65 (board review batch 1); its findings moved to 65, none are deferred.
- Decision: 2026-11-09, board review, Brad: from batch 2 on, only Sofia's drop and merge picks are brought to him; every story not named is kept as written.
- Decision: 2026-11-09, board review batch 2 (stories 8-64, 69-71), Brad: four picks ruled; the other 56 stories kept as written. Story 35 merged into 34 (same file and tests, one PR); story 33 dropped; story 30 keeps seven findings and defers B6-D3; story 69 dropped, and the lane epics get no Refactor sweep (this epic is itself the cleanup pass; PR-review leftovers go to `deferred-work.md` as they do today). Supersedes the 2026-11-09 sweep decision above. R14 no longer promises that a model change forces a re-embed.
- Dropped: story 35, 2026-11-09, merged into story 34 (board review batch 2); its findings moved to 34, none are deferred.
- Dropped: story 33, 2026-11-09, board review batch 2: its one visible effect is "Add ~0 lands" for a deck under three cards; the rest (named thresholds, an exact-string test, a land/spell split quadratic over at most 100 cards, dead `cmc` arms) is cosmetic in a file story 36 rewrites. B4-P10, B4-P13, B4-P16 and B4-P18 are in `deferred-work.md`.
- Dropped: story 69 (Refactor sweep), 2026-11-09, board review batch 2: a sweep after a cleanup pass is cleanup of cleanup.
- Decision: 2026-11-09, board review batch 2: B6-D3 (a model fingerprint in the index hash) is deferred out of story 30. It forces one full re-embed on every user's machine to guard a model swap nobody has planned; the PR that changes the model adds it. In `deferred-work.md`.
- Decision: 2026-11-09, board review pass 3, Brad: the split is applied. This epic keeps the groundwork lane (1-7, 65, 68, with dropped 67 and 69) and Requirements R1-R4, R25 and the toolchain part of R24; R5-R23 and the lint part of R24 moved to the six lane epics, each line keeping its review number. The UI lane split in two (state and tests; accessibility and polish) by the same rule that split the tools lane. Order conflicts between the lanes are expected (initiative Notes).
- Decision: 2026-11-09, story ids renumbered by the lane split (old → new; the old ids appear in the Decisions above and in the review plan's step 5 note): epic-quality-mcp-tools 8→5.1, 12→5.2, 13→5.3, 14→5.4, 15→5.5, 16→5.6, 17→5.7, 18→5.8, 71→5.9, 19→5.10, 20→5.11; epic-quality-data-and-search 21→6.1, 22→6.2, 23→6.3, 24→6.4, 25→6.5, 26→6.6, 27→6.7, 28→6.8, 29→6.9, 30→6.10, 31→6.11, 63→6.12, 66→6.13; epic-quality-analysis 32→7.1, 33→7.2, 34→7.3, 35→7.4, 36→7.5, 37→7.6, 38→7.7, 39→7.8, 40→7.9; epic-quality-companion-backend 41→8.1, 42→8.2, 43→8.3, 44→8.4, 45→8.5; epic-quality-ui-state-and-tests 9→9.1, 70→9.2, 11→9.3, 10→9.4, 46→9.5, 47→9.6, 48→9.7, 49→9.8, 50→9.9, 51→9.10; epic-quality-ui-accessibility-and-polish 52→10.1, 53→10.2, 54→10.3, 55→10.4, 56→10.5, 57→10.6, 58→10.7, 59→10.8, 60→10.9, 61→10.10, 62→10.11, 64→10.12. Groundwork keeps its ids (1-7, 65, 68; 67 and 69 dropped).
- Decision: 2026-11-09, tracer bullet unchanged: story 1 (the data-loss traps).
- Assumption: a `-D` finding that D1-D11 do not rule is fixed with the option its review run recommended; each story names the option where it shapes the work.
- Assumption: stories 38 and 39 re-run the assessment benchmark, and whether the profile version moves is settled in their PRs (B5-D1).
- Assumption: story 25's data changes (English printing, WUBRG colours) reach existing databases through the next `initialize_database(update=true)` (upsert plus reconcile), with no connect-hook repair.
- Decision: 2026-11-09, board review, Brad: split into five lane epics, each with its own retro: groundwork (1-7, 65, 67, 68), MCP tools and data (8, 12-31, 71, 63, 66), analysis (32-40), companion backend (41-45) and UI (9, 70, 11, 10, 46-62, 64). The moves are applied after the story-by-story pass, so no dropped story is moved; if the tools lane still holds about 24 stories it splits again into tools (12-20, 71) and data and search (21-31).
- Decision: 2026-11-09, board review, Brad (build order against epics 1-3): story 16 before epic-reliable-deck-workflows entry 1, story 71 before its entry 4, epic-quick-wins entry 5 before story 44 (`after = [43, "1.5"]`; 45, 50, 51, 56 and 58 follow 44), story 32 before epic-quick-wins entry 4, story 37 before epic-trustworthy-assessment's first story and that epic before story 38.
- Decision: 2026-11-09, board review, Brad (settles the source conflict between stories 38-40 and initiative R16 / epic-trustworthy-assessment R3): R16 binds only epic-trustworthy-assessment's own changes. Stories 38-40 may move supported Commander and Standard scores on purpose; each re-runs the assessment benchmark and records the score deltas in its PR. Epic-trustworthy-assessment builds before story 38 (`after`), so R16 is measured against today's baseline.
- Decision: 2026-11-09, board review, Brad (settles the source conflict between story 32 and epic-quick-wins R6): B4-D1 wins. Story 32 makes restricted a checked rule and builds before epic-quick-wins entry 4, whose R6 drops the Vintage restricted line. Today `deck_validator.py:434-436` counts a restricted card as a violation, so reporting the rule as unchecked would mislead. Story 32 now waits on 2 and 8 only; stories 14 and 18, which it used to wait on for shared files, wait on it instead.

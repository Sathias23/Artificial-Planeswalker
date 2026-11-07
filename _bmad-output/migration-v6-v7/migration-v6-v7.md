---
type: migration
title: Artificial-Planeswalker v6 to v7 planning migration
status: done
created: 2026-11-07
---

# v6 to v7 planning migration

Migration `method` 1 (`from` 6, `to` 7). The rules are in `.claude/skills/bmod-method/migration-1.toml`. Approved by Brad 2026-11-07 and carried out on `chore/bmad-v7-migration`.

## Detect signals matched

- `epics.md` under the planning folder (`_bmad-output/planning-artifacts/`).
- Dated artifact folders: `prds/prd-*-<date>/prd.md`, `architecture/architecture-*-<date>/ARCHITECTURE-SPINE.md`, `ux-designs/ux-*-<date>/DESIGN.md`.
- `specs/spec-<slug>/SPEC.md` under the output folder (5 folders, 2 of them with `stories.yaml`).
- No `active_initiative` and no `initiative-*/` folder.

## Backup

`.v6-v7-migration-backup-20261107-1800/` holds `_bmad/` (made by `bmad setup`'s v6 cleanup) and `_bmad-output/`: 94 files, checked with `diff -rq`. Its own `.gitignore` is `*`, so git never stages it.

## Questions and answers

| Question | Answer | Reason |
|---|---|---|
| Source folders | Planning: `_bmad-output/planning-artifacts/` and `_bmad-output/specs/`. Implementation: none on disk. | Sprint status and story files live on the orphan `process` branch. Brad chose to migrate planning only and leave the `process` branch alone. |
| Workspace or a separate repo for the store? | No. The store stays in this repo. | Default. Single repo. |
| Shipped history in the ticket tree? | No. It is archived unchanged in `archive-v6/`. The live tree holds open work only. | Brad's choice. Almost all ~141 v6 stories have shipped and their status is on the `process` branch. A tree of "done" entries with no evidence beside it adds noise. |
| How many initiatives? | One: `initiative-artificial-planeswalker/`. | Brad's choice. One product. Future work becomes epics under it. |
| Where does it land? | Branch `chore/bmad-v7-migration`, then a PR to `master`. | Brad's choice. Two tests read UX files by path, so the move needs code edits in the same change (see "References outside the store"). |
| Superseded flat `prd.md` and `architecture.md` (Jan 2026, PydanticAI/Chainlit, pre-pivot) | `archive/`, unchanged. | Brad's choice. It keeps a superseded design from being read as current. |
| Dated versions sharing a name (`prd-…-2026-07-11` and `-07-22`, `architecture-…-2026-07-11` and `-07-25`) | Keep both, live. | They are not versions of one document. 07-11 is the deck power assessment, while 07-22 and 07-25 are the companion app. |
| Stories in progress | None to finish in v6. Quick-wins stories 1 and 2 are `done` (PRs #114 and #115). Stories 3 to 5 are not started. | — |
| Fold unstarted stories' files into entries? | Not applicable. No unstarted story has a file. | — |

## Target tree

```
_bmad-output/
  initiative-artificial-planeswalker/
    initiative-artificial-planeswalker.md         # the envelope (new)
    prd-Artificial-Planeswalker-2026-07-11/       # from prds/, whole; prd.md renamed to match the folder
    prd-Artificial-Planeswalker-2026-07-22/       # from prds/, whole; prd.md renamed to match the folder
    architecture-Artificial-Planeswalker-2026-07-11/   # from architecture/, whole; ARCHITECTURE-SPINE.md renamed
    architecture-Artificial-Planeswalker-2026-07-25/   # from architecture/, whole; ARCHITECTURE-SPINE.md renamed
    ux-Artificial-Planeswalker-2026-07-22/        # from ux-designs/, whole; new router ux-Artificial-Planeswalker-2026-07-22.md beside DESIGN.md and EXPERIENCE.md
    research-<stem>/research-<stem>.md            # one folder per file in research/ (5)
    sprint-change-proposal-2026-07-12/…           # flat file into a folder named after its stem
    sprint-change-proposal-2026-08-16/…
    implementation-readiness-report-2026-07-11/…
    tickets/
      tickets.toml                                # [[epic]] quick-wins, reliable-deck-workflows, trustworthy-assessment
      epic-quick-wins/
        epic-quick-wins.md                        # rendered from specs/spec-quick-wins/SPEC.md (CAP-1..6 to R1..R6)
        .memlog.md                                # the spec's memlog
        tickets/
          tickets.toml                            # entries 1..5 from stories.yaml
          story-deck-metadata-and-card-quantity-tools-plan.md   # stories/1-…md, status done
          story-clone-deck-tool-plan.md                         # stories/2-…md, status done
      epic-reliable-deck-workflows/
        epic-reliable-deck-workflows.md           # from epics-deck-workflow-reliability.md Epic 1 + spec CAPs
        acceptance.md                             # spec companion, a References line
        .memlog.md
        tickets/tickets.toml                      # entries 1..5 from Stories 1.1..1.5, no plans
      epic-trustworthy-assessment/
        epic-trustworthy-assessment.md            # Epic 2 goal only, refined: false, no entries yet
    archive-v6/
      epics.md, epics-companion-app.md, epics-deck-power-assessment.md, epics-deck-workflow-reliability.md
      spec-deck-power-assessment/, spec-quality-audit-p1/, spec-quality-review-fixes/   # whole, unchanged
      spec-quick-wins/SPEC.md + stories.yaml, spec-deck-workflow-reliability/SPEC.md   # sources rendered into the live epics
  archive/
    prd.md, architecture.md                       # Jan 2026 pre-pivot design, unchanged
  backlog/.gitkeep
  migration-v6-v7/migration-v6-v7.md              # this file
```

The emptied `planning-artifacts/`, `prds/`, `architecture/`, `ux-designs/`, `research/` and `specs/` folders are removed.

### The initiative envelope

The initiative has no single live PRD. Its Description and Outcome describe the product (an MCP server plus a read-only companion). Its Requirements are the open work's lines, numbered from R1:
- quick-wins CAP-1..6, as `R<n> (CAP-m, spec-quick-wins)`;
- deck workflow reliability FRs, as `R<n> (FR-m, spec-deck-workflow-reliability)`.

Constraints combine the two specs' constraints. `sources:` names the two archived specs. `companions:` names `docs/architecture.md` (the design of record), the 2026-07-25 architecture (AD-n) and the UX DESIGN and EXPERIENCE files. Shipped capabilities are noted in Notes as a pointer to `archive-v6/`, not as requirements.

### Statuses

- `epic-quick-wins`: `in-progress`. Entries 1 and 2 get plans with `status: done`, `type: feature`, and `baseline_revision` only if the story file records one. Entries 3 to 5 are entries only.
- `epic-reliable-deck-workflows`: no status line (backlog). Its v6 breakdown says "epic-1-stories-draft-awaiting-review", so the epic gets `refined: false`. Sofia should review it before building.
- `epic-trustworthy-assessment`: no status, `refined: false`, no entries.

### Prerequisites

The quick-wins `stories.yaml` declares none. Workflow reliability Story 1.5 (export) overlaps quick-wins entry 3 (decklist export). The migration records this as an open question in both epics' Notes for Sofia. It neither merges nor drops either entry.

## Files left in place

None. Every file under the two source folders moves to the initiative, `archive-v6/` or `archive/`.

## References outside the store

These are not edited by the migration itself. Because Brad chose a PR, the same branch updates them in a separate commit:

| File:line | Old path | Change |
|---|---|---|
| `ui/tests/tokens.test.ts:43` | `planning-artifacts/ux-designs/ux-…-2026-07-22/DESIGN.md` | new initiative path (would otherwise fail `npm test`) |
| `tests/unit/companion/test_openapi_contract.py:437-441` | `planning-artifacts/ux-designs/ux-…-2026-07-22/EXPERIENCE.md` | new initiative path (would otherwise fail `pytest`) |
| `.pre-commit-config.yaml:40` | `research/quality-audit-2026-09-03.md` and `specs/spec-quality-audit-p1/stories/1-…md` excludes | new paths |
| `AGENTS.md:6` | `ARCHITECTURE-SPINE.md` path and `_bmad-output/specs/` | new paths; also name the active initiative |

Mentions of the bare name `ARCHITECTURE-SPINE.md:211`/`:461` in `src/` docstrings and `tests/integration/companion/test_live_backend.py` cite a line, not a path. They are listed for Brad and left unchanged; regenerating `plugin/` would be needed if they changed. Historical mentions in `CHANGELOG.md` and `docs/release-readiness-review.md` stay as written.

## Configuration

- `_bmad/custom/config.user.toml`: `[core] active_initiative = "initiative-artificial-planeswalker"`.
- No module config key points inside the planning folder after setup's cleanup. No `_bmad/custom/` override names a moved path.

## Commits

On `chore/bmad-v7-migration`, `git mv` throughout so history follows; the backup is never staged; nothing pushed.

| Commit | Step |
|---|---|
| `34c3cb7` | State before the migration: the untracked deck-workflow-reliability breakdown and spec, and this plan |
| `d820810` | 7 Documents (plus the `.pre-commit-config.yaml` excludes, see Deviations) |
| `912c27f` | 8–9 Ticket tree and the two spec folders |
| `42422c9` | 13 Path rewrites |
| `58c4a29` | 14 Configuration and cleanup: `backlog/.gitkeep`, the two tests and `AGENTS.md` |

Steps 6, 10, 11 and 12 had nothing to do: no workspace change; `migrate_v6.py --fold-specs` reported no pre-release spec folders; no loose implementation files; nothing left in place.

## Deviations from the approved plan

- The `.pre-commit-config.yaml` excludes moved into the step 7 commit rather than the final one: the `no-local-machine-paths` hook fails on the moved files until its excludes follow them, and the hook is never bypassed.
- Research reports moved into folders named after their stems (for example `quality-audit-2026-09-03/`) as the rules say, not `research-<stem>/` as the target tree sketched; the prefixed form also pushed one path past the Windows length limit.
- `epic-trustworthy-assessment/` has no `tickets/` folder yet; it gets one when Sofia plans its stories.
- In `AGENTS.md` the "active specs" pointer became a pointer to the ticket tree and `archive-v6/`.

## Dead in v6, not broken by the migration

These live references already pointed at nothing before the migration and are unchanged:

- `_bmad-output/project-context.md` (deleted before the migration) in the 2026-07-11 and 2026-07-25 architecture spines and the 2026-07-25 memlog.
- `_bmad-output/implementation-artifacts/…` (moved to the `process` branch before the migration) in `sprint-change-proposal-2026-08-16.md` and `spike-mtga-collector-go-no-go-2026-07-20.md`.
- Thirteen `](src/…)` and `](scripts/…)` links in `technical-mtg-arena-deck-import-export-research-2026-06-27.md`, written relative to the repo root but resolved from the report's folder.
- The `_ds/planeswalker-companion-design-system-…/` asset paths in `imports/claude-design/Planeswalker Companion.dc.html`.

## For Brad to update (not edited)

- `src/companion/client.py:432`, `src/mcp_server/server.py:140` (and their `plugin/` copies), `tests/integration/companion/test_live_backend.py:6`: cite `ARCHITECTURE-SPINE.md:211` / `:461`, now `architecture-Artificial-Planeswalker-2026-07-25.md` at the same lines. Changing the `src/` docstrings needs a `plugin/` rebuild.
- `CHANGELOG.md:108`, `docs/release-readiness-review.md`, `docs/quality-review-2026-09-06.md`: historical mentions of old paths; left as written.

## Checklist results

| # | Item | Result |
|---|---|---|
| 1 | Every source file accounted for | Pass. `git diff -M 34c3cb7 HEAD`: all 94 files under `planning-artifacts/` and `specs/` are renames, none deleted; nothing is left in place. |
| 2 | Folders keep v6 names and every file; main file or router; `initiative-*/`, `backlog/`, `archive/` exist | Pass. The UX folder has a router; `backlog/` has a `.gitkeep`. |
| 3 | Dated versions all present | Pass. Both PRDs and both architectures are live under their own names. |
| 4 | `tickets.py status` exits 0; story counts match the archived sources | Pass, with a recorded exception. Exit 0, 10 tickets (2 done, 8 planned). Live counts match their sources: quick-wins 5 = `stories.yaml` 5, reliable-deck-workflows 5 = Stories 1.1–1.5. Brad chose to archive shipped Epics 1–17 instead of rebuilding them, and their tracking stays on `process`. |
| 5 | One entry per story, one plan per build record, no epic story files; `find` returns each plan | Pass. `find 1.1` and `find 1.2` return the two plans. |
| 6 | Plans have a build type and mapped status; baselines kept | Pass. Both are `type: feature`, `status: done`, with the story files' own `baseline_revision` (`26bccfd`, `598b2fc`). No retrospectives were in scope. |
| 7 | `covers` ids resolve; every requirement has an entry | Pass. Every epic and entry `covers` id is a Requirements line one level up; every initiative R has an epic. Every R in the two refined epics has an entry; epic-trustworthy-assessment has no entries yet, by design. |
| 8 | No pre-release `spec-<slug>/spec-<slug>.md` remains; no stray `CAP-` ids | Pass for the folds: there were none. `CAP-` ids remain in the two v6 build records (now plans), the reliability `acceptance.md` companion and `sprint-change-proposal-2026-07-12.md`. They are historical evidence, traceable through each epic's `(parent R<n>, CAP-<m>)` lines. The reliability `acceptance.md` CAP-1..3 are the reliability spec's own. |
| 9 | Every live path resolves | Pass. 80 live paths and links resolve; the ones listed under "Dead in v6" were already dead before the migration. |
| 10 | Active initiative set; `output_folder` resolves | Pass. `resolve_config.py`: `core.active_initiative = initiative-artificial-planeswalker`, `core.output_folder = {project-root}/_bmad-output`. |
| 11 | Moved module config keys name new locations | Pass. None pointed inside the planning folder after setup's v6 cleanup. |
| 12 | Store under git as answered; no double tracking | Pass. Single repo, no workspace. |
| 13 | Backup holds every source file and is never committed | Pass. The backup holds 94 files under `_bmad-output/`; `git log --all` shows no commit touching it. |
| 14 | Plan records questions, answers, backup, files, results | Pass. This file. |

Gates after step 14: `ruff check`, `ruff format --check`, `pytest -m "not integration"` (3280 passed), `npm test` (1786 passed), pre-commit hooks all green.

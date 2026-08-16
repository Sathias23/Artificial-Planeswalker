# Sprint Change Proposal — Companion Epic Renumbering (c1–c10 → 8–17)

**Date:** 2026-08-16
**Author:** Correct-course workflow (Sathias + agent)
**Mode:** Batch review
**Status:** APPROVED and IMPLEMENTED 2026-08-16 (Sathias). Replacement counts: yaml keys
10 epic / 10 retro / 76 story, 66 ledger epic fields, 11 retro-filename refs; epics file
113 "Epic N" + 97 "Story N.M" + 7 forward story ids; deferred-work 59 forward story ids;
retro file renamed with frontmatter `epic: 14`. Verification gate §4.6: all four checks passed
(`detect-epic` → epic 14, pending empty, `epic-14-retrospective: done`; grep gates zero).

---

## 1. Issue Summary

BMAD v6.11 (installed 2026-08-16) made the retrospective tooling integer-only. The companion
app's epics are tracked with a `c` prefix (`epic-c1`…`epic-c10`, story keys `c7-1-…`), which the
new tooling cannot see or address:

- `sprint_status.py` `STORY_RE = ^(\d+)-\d+[a-z]?-` — every `cN-M-…` story key is invisible to
  `detect-epic`, the dashboard, and the unfinished-story gate.
- `--epic` is `argparse type=int` — `--epic c8` is rejected before any logic runs.
- Legacy action-item addressing requires "an integer epic and a non-empty string action" — the
  **66 ledger items carrying `epic: c1`…`c7` (strings, no `id:`)** are unaddressable by
  `set-status`. (Only the 9 newest items, from the C7 retro, carry ids.)
- Previous-retro discovery globs `epic-{prev}-retro-*.md` with integer `prev` — the next epic's
  retro will look for `epic-14-retro-*.md`, which does not exist under the current naming.

**Discovery context:** surfaced at the Epic C7 retrospective (run 2026-08-16 under v6.11);
epics c8–c10 are still backlog, so the friction recurs at every future retro and sprint-status
operation unless resolved now.

## 2. Impact Analysis

**Epic impact.** No epic's scope, stories, ACs, or sequencing change. This is a pure
renumbering: the companion roadmap becomes a contiguous integer block continuing from the last
integer epic (7, deck-power roadmap).

| Old | New | Status | | Old | New | Status |
|-----|-----|--------|-|-----|-----|--------|
| c1 | **8** | done | | c6 | **13** | done |
| c2 | **9** | done | | c7 | **14** | done (retro'd) |
| c3 | **10** | done | | c8 | **15** | backlog |
| c4 | **11** | done | | c9 | **16** | backlog |
| c5 | **12** | done | | c10 | **17** | backlog |

**Collision check:** integer story keys `1-1`…`7-5` and retro keys `epic-1`…`epic-7` are taken by
the two earlier roadmaps; `8`–`17` are free. Ledger items `epic: 4`…`7` (17 items) do not collide
with converted companion items (`8`–`17`). Verified clean.

**Artifact conflicts.** PRD: none (superseded docs untouched; no requirement changes).
Architecture: none. UX: none — `EXPERIENCE.md`/`DESIGN.md` carry zero c8/c9/c10 references.
The conflicts are confined to the tracking/planning layer plus comment-level residue in code.

**Reference census** (pattern `c{8,9,10}-N` / `epic-c{8,9,10}` / "Epic C8" etc.): 405 hits in
87 files, splitting into:
- **Living planning/tracking artifacts** (must change): `sprint-status.yaml`,
  `epics-companion-app.md`, `deferred-work.md` (57 hits), the fresh
  `epic-c7-retro-2026-08-16.md`.
- **Historical record** (stays, per ruling): the ~60 `cN-M-*.md` story files, retro files
  c1–c6, prose in sprint-status header narrative — these name real merged PRs, branches, and
  commits.
- **Code-comment residue** (accepted, see §4.5): citation comments in `src/`, the `plugin/`
  mirror, `ui/tests/*.ts`, `ui/README.md` referencing future homes like `c8-6`/`c10-3`.

## 3. Recommended Approach — Direct Adjustment

Renumber in place (Option 1). Rollback is meaningless here (nothing to revert), and MVP scope is
untouched (Option 3 N/A). Effort: **Low** (mechanical, rule-driven — one mapping table, `+7`).
Risk: **Low**, concentrated in two spots: (a) missing a *forward* reference so a future story is
built under an id nothing points at — mitigated by the census above and a post-edit grep gate;
(b) breaking sprint-status YAML — mitigated by running the v6.11 `sprint_status.py` validator
after the edit.

Ruled by Sathias (2026-08-16): ordinal-preserving mapping (c1→8 … c10→17); rename keys + forward
references; historical prose and filenames stay with a mapping legend.

## 4. Detailed Change Proposals

### 4.1 `sprint-status.yaml` (tracking keys + ledger)

- **Epic keys** (10): `epic-c1:` → `epic-8:` … `epic-c10:` → `epic-17:` — values and trailing
  comments unchanged.
- **Retro keys** (10): `epic-c1-retrospective:` → `epic-8-retrospective:` … — values unchanged.
- **Story keys** (76): `cN-M-<slug>:` → `{N+7}-M-<slug>:` — slugs and statuses unchanged.
  Example: `c7-7-uj-1-end-to-end: done` → `14-7-uj-1-end-to-end: done`.
- **Action-item ledger** (66 items): `- epic: c1` → `- epic: 8` … `- epic: c7` → `- epic: 14`
  (YAML integer, unquoted). Action text, status, refs unchanged.
- **Ref pointer** (1): the `epic-c7-retrospective` entry's file reference follows the rename in
  §4.3.
- **Legend** (new comment block under the header):
  `# EPIC RENUMBERING 2026-08-16: companion epics c1..c10 renamed 8..17 (c1=8, c2=9, c3=10,`
  `# c4=11, c5=12, c6=13, c7=14, c8=15, c9=16, c10=17). Historical prose, story/retro filenames,`
  `# PR titles and branch names keep the cN-M ids. See sprint-change-proposal-2026-08-16.md.`
- Historical `cN-M` mentions inside header narrative and per-key comments: **unchanged**.

**Rationale:** makes every companion story visible to `STORY_RE`, `detect-epic` auto-detection
land on 14 (highest done), and all 66 legacy ledger items addressable by integer epic + action.

### 4.2 `epics-companion-app.md` (full internal renumber, +7)

All internal epic/story numbering shifts by +7 — inside this file "Epic N" always means a
companion epic, so the shift is total, not selective:

- Epic List and body headings: `## Epic 1: Launch the Companion` → `## Epic 8: Launch the
  Companion` … `## Epic 10: Session History…` → `## Epic 17: Session History…`.
- Story headings (~72): `### Story 1.1: …` → `### Story 8.1: …`; `### Story 7.4` → `### Story
  14.4`; etc.
- Prose references to epic/story numbers (FR/NFR mapping tables, "the formal gate is Epic 8" →
  "Epic 15", "Blocks the history story in Epic 10" → "Epic 17", cross-references like
  "Story 7.4's AC").
- Forward story ids (7 hits): `c8-6` → `15-6`, `c10-1` → `17-1`, `c10-3` → `17-3`, "Epic 8
  (c8-6)" → "Epic 15 (15-6)".
- Legend note added under the document title (same text as §4.1's).
- Historical `cN-M` citations of merged work (review rulings, "corrected at c6-7", PR
  references): **unchanged** — they name real branches/PRs.

**Rationale:** this file is what sprint-planning regenerates keys from; heading numbers must
equal the new integer keys or the next `sprint-planning` run recreates the mismatch.

### 4.3 `epic-c7-retro-2026-08-16.md` (rename + frontmatter)

- File rename: `epic-c7-retro-2026-08-16.md` → **`epic-14-retro-2026-08-16.md`** (file is
  currently untracked — a plain rename, no git history to preserve).
- Frontmatter: `epic: c7` → `epic: 14`.
- Title/body references to "Epic C7" gain a one-line note: "(epic c7, renumbered **14** on
  2026-08-16)". Body prose otherwise unchanged.
- Retro files c1–c6: **not renamed** — previous-retro discovery only ever looks back one epic,
  so only c7's file will ever be globbed again (as `epic-14-retro-*.md` by epic 15's retro).

**Rationale:** epic 15's retrospective looks for `epic-14-retro-*.md` and reads frontmatter
`epic` as an integer.

### 4.4 `deferred-work.md` (forward refs)

- All `c8-N`/`c9-N`/`c10-N` story-home references → `15-N`/`16-N`/`17-N` (57 candidate hits;
  each reviewed in place — only forward-pointing *homes* change; quoted historical text stays).
- Legend line added at the top of the ledger.

**Rationale:** the ledger's open items are homed on unbuilt stories; after renumbering, those
stories will only ever exist under integer ids.

### 4.5 Accepted residue (explicitly NOT changed)

- **Code comments** citing future homes — `src/companion/**` and its `plugin/` mirror
  (`ws.py`'s `c10-3` sentence, `images.py`, `state.py`, etc.), `ui/tests/*.ts` citation
  comments, `ui/README.md` (6 hits). Changing them means touching shipped code, the committed
  plugin mirror, and the bundle-drift chain for zero behavioral value. The legend covers them;
  if it ever grates, a one-line sweep can ride along with the next story that touches each file.
- **Historical story/retro/spec files** (`c1-1-*.md` … `c7-7-*.md`, `epic-c1-retro`…`epic-c6-retro`,
  `spec-c7-*`): filenames and content stay — they are the record of work merged under those names.
- **Memory/intake notes**: the agent's memory files will be updated separately after
  implementation (not a repo artifact).

### 4.6 Verification gate (after all edits)

1. `uv run python .claude/skills/bmad-retrospective/scripts/sprint_status.py detect-epic --file _bmad-output/implementation-artifacts/sprint-status.yaml` → must report `epic: 14`, empty `pending_stories`, `retro_key: epic-14-retrospective`, `retro_status: done`.
2. Grep gate: `\bc(8|9|10)-\d` returns zero hits in `sprint-status.yaml`, `epics-companion-app.md`, `deferred-work.md`.
3. Story-key census: 76 integer story keys `8-*`…`17-*` present; zero `c`-prefixed keys remain.
4. YAML parses (ruamel round-trip via any script `--file` load).

## 5. Implementation Handoff

**Scope classification: Minor** — direct implementation, no backlog reorganization or replan.
Content of no story changes; only identifiers.

- **Executor:** Developer agent (this session), per the edits in §4, in order 4.1 → 4.2 → 4.3 →
  4.4 → 4.6.
- **Branch/commit:** current branch `feat/companion-c7` already carries the retro artifacts;
  the renumbering commits ride with it into the C7→master integration PR. (Note: umbrella
  *branch names* keep their historical `cN` names; only tracking identifiers change. Future
  umbrellas use integer names, e.g. `feat/companion-15`.)
- **Success criteria:** all four checks in §4.6 pass; the next retro can be invoked as
  `--epic 15` with previous-retro discovery finding `epic-14-retro-2026-08-16.md`.
- **Follow-through:** agent memory (companion-app-intake) updated to the new numbering after
  implementation.

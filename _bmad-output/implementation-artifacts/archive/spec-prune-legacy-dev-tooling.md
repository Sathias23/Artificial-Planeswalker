---
title: 'Prune legacy stack + dev tooling for public release'
type: 'chore'
created: '2026-06-28'
status: 'done'
baseline_commit: 'a9eb68844e8713beb65a76d3d1cfe372d5a0032d'
context:
  - '{project-root}/RELEASE-STRATEGY.md'
  - '{project-root}/_bmad-output/implementation-artifacts/deferred-work.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repo is heading public (RELEASE-STRATEGY.md §7 step 2) but still tracks the superseded PydanticAI/Chainlit stack (`legacy/`, `public/`), scratch scripts, internal/process docs, and the BMAD dev framework + 43 `bmad-*` skills. The already-rewritten README links to `docs/architecture.md`, which does not exist yet (dangling link).

**Approach:** One `chore` commit on branch `chore/prune-legacy-dev-tooling`: hard-delete the superseded/private/scratch files; `git mv` the design spec to `docs/architecture.md` (fixing the README link) and re-point the references that survive; untrack-but-keep-on-disk (`git rm --cached`) the BMAD framework + `bmad-*` skills; and update `.gitignore`. Keep `_bmad-output/` and the 4 MTG product skills tracked.

## Boundaries & Constraints

**Always:**
- Hard `git rm` ONLY the superseded/private/scratch set. Untrack (`git rm --cached -r`, keep on disk) for `_bmad/` and `.claude/skills/bmad-*`. `git mv` (not delete+create) the spec to preserve history.
- The 4 product skills (`magic-deckbuilding`, `synergy-discovery`, `mana-curve-analysis`, `format-legality`) and ALL of `_bmad-output/` stay tracked.
- `uv run pytest -m "not integration"` and `uv run mypy src/` stay green after the prune.

**Ask First:**
- Reference-fix scope: rewrite the ~20 surviving `_bmad-output/**` refs + `project-context.md` from the old spec path to `docs/architecture.md` (recommended — keeps the public design record link-clean) vs. move-only. Surface at CHECKPOINT 1.

**Never:**
- Do NOT hard-delete anything bmad-related — untrack only (the running workflow + its resolver live there).
- Do NOT touch `pyproject.toml`, dependency groups, `.env.example`, or any `src/` logic — those are the separate §6 deferred run.
- Do NOT run the manual/outward-facing steps (secret scan, `git tag`, GitHub Release, flip public) — Brad's call.
- Do NOT delete `_bmad-output/`.

## I/O & Edge-Case Matrix

| Target | Treatment | Post-state |
|--------|-----------|------------|
| `legacy/` (68), `public/` (2), `examples/` (4); root docs `PROJECTIDEA/SATHIAS/SPIDER_MAN_INVESTIGATION/TODO-LIST/TOOL_PERFORMANCE_REPORT.md`; `scripts/test_{agent,api_connection,database_setup,mini_import,queries}.py`; internal `docs/*` (8 files) | `git rm` | gone from repo + disk |
| `docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md` | `git mv` → `docs/architecture.md` | README:139 link resolves; `docs/superpowers/` empties out |
| `_bmad/` (15), `.claude/skills/bmad-*` (43 dirs) | `git rm --cached -r` + gitignore | untracked, still on disk, workflow still runs |
| `.claude/skills/{4 product}`, `_bmad-output/` | untouched | stay tracked |

</frozen-after-approval>

## Code Map

- `RELEASE-STRATEGY.md` §1, §1c, §2 -- source of truth for the prune lists
- `.gitignore` -- remove `.github/` (un-ignore) + `PROJECTIDEA.md`; add `/_bmad/` and `.claude/skills/bmad-*/`
- `README.md:139` -- already links `docs/architecture.md`; the move makes it resolve
- `_bmad-output/project-context.md:23,203` -- prose refs to old spec path/dir; update
- `_bmad-output/implementation-artifacts/*.md` (~14 story files) -- relative `[design spec](../../docs/superpowers/specs/...)` links; update
- `docs/` -- after prune: `architecture.md`, `BUG_REPORT_MANAGEMENT.md` only

## Tasks & Acceptance

**Execution:**
- [x] Hard-delete: `git rm` the root docs, `legacy/`, `public/`, `examples/`, the 5 scratch `scripts/test_*.py`, and the 8 internal `docs/*` files (exact list in the Matrix) -- remove superseded/private/process files.
- [x] `git mv docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md docs/architecture.md` -- promote design of record; fixes the README link.
- [x] Reference fix: replace substring `docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md` → `docs/architecture.md` across `_bmad-output/**`; fix `project-context.md:203` `docs/superpowers/specs/` directory mention -- zero broken links in the kept design record. (Approved: fix all ~20 refs.)
- [x] `git rm --cached -r _bmad/` and `git rm --cached -r .claude/skills/bmad-*` -- untrack dev tooling, keep on disk.
- [x] `.gitignore` -- drop `.github/` and `PROJECTIDEA.md` lines; add `/_bmad/` and `.claude/skills/bmad-*/` (with a one-line "kept on disk" comment).
- [x] (local, not in commit) `rm -rf .chainlit/` -- untracked-on-disk Chainlit cache cleanup.
- [x] Commit `chore: remove legacy stack and dev tooling for public release`.

**Acceptance Criteria:**
- Given the prune commit, when `git ls-files _bmad/ ".claude/skills/bmad-*"` runs, then it returns empty AND `_bmad/` + `.claude/skills/bmad-quick-dev/` still exist on disk.
- Given the prune, when `git ls-files _bmad-output/ ".claude/skills/magic-deckbuilding"` runs, then both remain tracked.
- Given the move, when the README:139 `docs/architecture.md` link is followed it resolves; and `git grep -l "2026-06-20-mcp-server-architecture-design" -- _bmad-output README.md docs/` returns no matches (the old path survives only in `RELEASE-STRATEGY.md` as the migration record and in this spec's own descriptive text — both intended).
- Given the deletions, when `uv run pytest -m "not integration"` and `uv run mypy src/` run, then both pass.
- Given `git diff --staged --stat`, when reviewed, then only the intended deletes/rename/untracks appear — no stray files.

## Spec Change Log

### specLoopIteration 1 — step-04 review patches (2026-06-28)

Adversarial review (Blind / Edge-case / Acceptance) surfaced surviving dependents on `legacy/` the Code Map missed — all caused by the deletion, all fixed in-diff as **patches** (frozen intent unchanged → no loopback):
- **HIGH** `scripts/manage_bug_reports.py` imported `BugReportStatus` from `legacy.agent.tools.bug_report` → repointed to `src.data.schemas.bug_report` (compatible superset; adds `ARCHIVED`, which `--include-archived` already expects). Without this a fresh clone crashes the keeper script.
- **HIGH** `tests/test_setup.py` asserted `legacy/agent` + `legacy/ui` exist → removed those assertions + retitled. Was masked locally by untracked `legacy/` leftovers (since `rm`-ed from disk so local == fresh clone).
- **Brad decision (review-time):** `docs/performance.md` is 100% legacy streaming/agent/Chainlit content (0 MCP relevance) → **deleted** (reverses RELEASE-STRATEGY §1c "keep" — that call assumed it was a general perf doc).
- **Brad decision (review-time):** cleaned remaining `legacy/` *path* mentions in kept files — `docs/architecture.md` (one top public-release note + line-152 fix; narrative archive mentions kept by design), 2 `src/mcp_server/tools/*.py` provenance docstrings, 3 test-file docstrings. `pyproject.toml` + `uv.lock` `legacy` refs intentionally left for the §6 deps run.
- Dangling citations to deleted docs scrubbed from public product skills (`TOOL_PERFORMANCE_REPORT.md` ×3) and test docstrings (`SPIDER_MAN_INVESTIGATION.md` ×2).

KEEP: the core delete / untrack / move / ref-fix set was correct and verified (577 unit tests + mypy green) — do not re-derive it.

## Design Notes

- **Self-untrack is safe:** `bmad-quick-dev` runs from `.claude/skills/bmad-quick-dev/` and uses `_bmad/scripts/resolve_customization.py`; both are `git rm --cached` (kept on disk), so this workflow keeps running. Never `git rm -r` anything bmad.
- **Two `architecture.md` by design:** `docs/architecture.md` (public design of record) vs. the SUPERSEDED `_bmad-output/planning-artifacts/architecture.md` (already documented as superseded in project-context.md). Different dirs; no collision — `docs/architecture.md` does not currently exist.
- **`pyproject.toml` legacy group untouched:** its `[dependency-groups] legacy` names PyPI packages, not the `legacy/` dir, so deleting `legacy/` leaves it valid-but-unused; removing it is the §6 run. `testpaths=["tests"]` already excludes `legacy/`, so the active suite is unaffected.

## Verification

**Commands:**
- `uv run pytest -m "not integration"` -- expected: pass (deletions don't touch the active suite).
- `uv run mypy src/` -- expected: clean.
- `git grep -l "2026-06-20-mcp-server-architecture-design" -- _bmad-output README.md docs/` -- expected: no matches (the path survives only in `RELEASE-STRATEGY.md` migration record + this spec's own text, both intended).
- `git ls-files _bmad/ ".claude/skills/bmad-*"` -- expected: empty.

**Manual checks:**
- `ls _bmad/scripts/resolve_customization.py .claude/skills/bmad-quick-dev/` -- expected: still present on disk.
- Open README.md → follow `docs/architecture.md` link -- expected: resolves to the moved spec.
- `git diff --staged --stat` -- expected: only intended deletes (legacy/public/examples/docs/scratch), one rename (spec→architecture), `--cached` untracks (_bmad/ + bmad-* skills), and `.gitignore` edit.

## Suggested Review Order

**The prune policy (start here)**

- The forward-looking untrack rule — bmad framework + dev skills ignored, kept on disk.
  [`.gitignore:10`](../../.gitignore#L10)

**Functional fixes (highest risk — make a fresh clone build & test green)**

- Keeper script: repointed `BugReportStatus` off deleted `legacy/` to the data schema.
  [`manage_bug_reports.py:30`](../../scripts/manage_bug_reports.py#L30)

- Active-suite test: dropped the now-false `legacy/agent`+`legacy/ui` existence asserts.
  [`test_setup.py:12`](../../tests/test_setup.py#L12)

**Design-record move + link hygiene**

- One public-release note contextualizes the doc's historical `legacy/` mentions after the move.
  [`architecture.md:10`](../../docs/architecture.md#L10)

- Representative of the 20-file old-spec-path → `docs/architecture.md` rewrite.
  [`project-context.md:23`](../project-context.md#L23)

**Cleanup (peripheral)**

- Provenance docstring: dead `legacy/agent/tools/...` path swapped for prose (1 of 2 src docstrings).
  [`card_lookup.py:3`](../../src/mcp_server/tools/card_lookup.py#L3)

- Public product skill: dangling `TOOL_PERFORMANCE_REPORT.md` citation scrubbed (1 of 3 skills).
  [`format-legality/SKILL.md:323`](../../.claude/skills/format-legality/SKILL.md#L323)

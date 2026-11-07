---
type: review-plan
title: "Full codebase review: code quality, optimisation and architecture"
created: '2026-11-07'
status: draft
reviewer_model: claude-opus-5-5
reviewed_revision: ee0263d652a46f021515860bbc2a19e3dac60eed
context:
  - AGENTS.md
  - CONTRIBUTING.md
  - docs/architecture.md
  - _bmad-output/initiative-artificial-planeswalker/architecture-Artificial-Planeswalker-2026-07-25/architecture-Artificial-Planeswalker-2026-07-25.md
  - docs/quality-review-2026-09-06.md
  - _bmad-output/initiative-artificial-planeswalker/quality-audit-2026-09-03/quality-audit-2026-09-03.md
---

# Full codebase review: code quality, optimisation and architecture

A one-off review of the whole codebase with Claude Opus 5.5, run through BMad skills: an architecture pass, then group-by-group code reviews, then the findings become tickets that `bmad-build` fixes one at a time. This file is both the checklist and the plan handed to every `bmad-code-review` run, so each run reads the intent below and appends its findings to `## Code Review`.

## Intent (what every reviewer is told)

Review the code as it stands on `master`, not a change. Look for:

- **Correctness:** bugs, unhandled failure paths, race conditions, resource leaks, wrong or missing error handling.
- **Code quality:** duplication and near-copies, inconsistent patterns between modules doing the same job, dead code, oversized files or functions, unclear names, comments that no longer match the code.
- **Optimisation:** wasted queries (N+1, missing indexes, unbounded reads), blocking work on the event loop, repeated work that could be cached, needless re-renders and request storms in the UI, bundle weight.
- **Architecture:** drift from `docs/architecture.md` and the AD-n decisions; layer violations (data, then logic, then mcp_server; `src/data` and `src/logic` framework-free); AD-2 (nothing under `src/companion/` writes) and AD-3 (mcp_server never imports `src/companion/app/`); stateless tools; the frozen viewer (AD-15); boundaries that leak.
- **Test design:** behaviour tested through real entry points, gaps on risky paths, slow or brittle tests, tests that assert nothing.

Out of scope: style the linters already enforce (ruff, Prettier, mypy), the generated artifacts (`plugin/`, `src/companion/app/static/`, `ui/src/api/types.d.ts`, `ui/src/api/openapi.json`), and findings already fixed by the 2026-09-03 audit or the 2026-09-06 quality review. Read both first; do not re-raise what they closed.

## Steps

### 0. Prerequisites

- [x] PR #116 (v7 migration) merged, so this file and the ticket tree are on `master`.
- [x] Commit this file straight to `master` (planning artifact).
- [x] Record the reviewed revision: `ee0263d` (the PR #116 merge), in the frontmatter. All runs review that same commit.
- [ ] Database and semantic index built (`python setup.py`, `uv run python scripts/build_card_embeddings.py`), so reviewers can run integration tests and the search sanity eval if they need evidence.
- [ ] Budget: a thorough `bmad-code-review` run takes 30 minutes or more; the plan below is about 20 runs. Run groups in separate fresh sessions.

### 1. Architecture pass (`bmad-deep-recon`)

Do this first: it frames every group review and catches what no single group can see.

- [ ] Run `bmad-deep-recon` in "research the codebase" mode with this question: *"How far has the code drifted from `docs/architecture.md` and the AD-n decisions in the 2026-07-25 architecture spine? Where are the layer boundaries, the AD-2/AD-3 rules and the stateless-tool rule bent or worked around; where do the MCP tools, the companion backend and the UI duplicate logic that should live once; and what are the main performance risks (database access patterns, event-loop blocking, sqlite-vec usage, UI request patterns)?"*
- [ ] Its report lands in `research-codebase-architecture/` in the initiative. Approve any ADRs it proposes only when they record a real decision.
- [ ] Add the report path to this file's `context:` list so every group review reads it.

### 2. Group reviews (`bmad-code-review`)

One run per group, in a fresh session each. Say: *"run code review, no-code, on the file list for group <id> in `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`; this file is the plan."*

- **File list, not a diff.** Give the paths below; the review takes whole files.
- **This file is the plan.** It is read in full, its `context:` documents are loaded, and findings are appended to `## Code Review` as a dated block per run.
- **`no-code`.** The audit changes nothing; fixes come in step 5, one ticket at a time.
- **Thorough** (the default): four independent lenses. Use `quick` only for groups marked quick.
- **At triage, choose "leave as action items"** so findings stay in this file rather than being patched.
- Keep each group under about 3,000 lines; the review warns and offers to split above that.

| Id | Group | Paths | Lines | Extra focus | Done |
|---|---|---|---|---|---|
| B1 | Data model and database | `src/data/models/`, `src/data/schemas/`, `src/data/database.py`, `src/data/import_state.py` | ~1,500 | The connect-hook data repairs, JSON-in-Text `*_list` properties, `noload` relationships, the `# noqa: F401` model imports | [ ] |
| B2 | Repositories | `src/data/repositories/` | ~2,000 | `_UNSET` vs `None`, commit/refresh/rollback on every write method, Pydantic schemas out (never ORM models), N+1 loads, `deck.py` (1,184 lines) size | [ ] |
| B3 | Importers | `src/data/importers/`, `scripts/import_scryfall_data.py` | ~2,400 | Transaction scope, memory use on bulk data, idempotent re-import, WUBRG order | [ ] |
| B4 | Analysis logic: validator, curve, synergy | `src/logic/__init__.py`, `deck_validator.py`, `mana_curve.py`, `synergy.py` | ~2,000 | Observational only, framework-free, rule coverage | [ ] |
| B5 | Power assessment | `src/logic/assessment/` | ~2,850 | Scoring determinism, combo credit, duplication with the validator and synergy | [ ] |
| B6 | Semantic search | `src/search/`, `scripts/build_card_embeddings.py` | ~1,900 | `asyncio.to_thread` with its own connection, every KNN with `k`/`LIMIT` (over-fetch then JOIN-filter, `_MAX_LIMIT` 50), `index_unavailable` path; any suggested change needs a query-to-expected-card recall check | [ ] |
| B7 | MCP server core | `src/mcp_server/__init__.py`, `server.py`, `__main__.py`; `tools/messages.py`, `initialize_database.py`, `build_search_index.py`, `view_deck.py` | ~2,000 | Tool registration, stdio-only, stderr diagnostics, no per-session state, `server.py` (1,221 lines) size | [ ] |
| B8 | MCP deck and companion tools | `src/mcp_server/tools/deck_management.py`, `deck_import.py`, `companion.py` | ~2,350 | Status vocabulary consistency, `deck_changed` emitted only on `ok` and after the session closes, push payload bounds, tool docstrings (they are the LLM-facing descriptions) | [ ] |
| B9 | MCP card and analysis tools | `src/mcp_server/tools/assess_deck_power.py`, `compare_deck_power.py`, `deck_analysis.py`, `find_similar.py`, `semantic_search.py`, `card_search.py`, `card_lookup.py` | ~2,700 | Same status vocabulary, observational analysis, the five shipped skills match each tool's real parameters | [ ] |
| B10 | Companion contracts and client | `src/companion/contracts.py`, `client.py`, `discovery.py` | ~2,200 | `contracts.py` (1,361 lines) size, AD-9 staleness window, the import boundary (mcp_server may import only this leaf) | [ ] |
| B11 | Companion backend: routes and wiring | `src/companion/app/routes/`, `__init__.py`, `main.py`, `server.py`, `deps.py`, `state.py`, `spa.py` | ~2,560 | AD-2 read-only, route contracts vs OpenAPI, error responses | [ ] |
| B12 | Companion backend: images, socket, safety | `src/companion/app/images.py`, `errors.py`, `ws.py`, `body_cap.py`, `security.py`, `singleton.py` | ~2,680 | Image fetch and cache bounds, the per-platform `singleton.py` (`msvcrt` vs `fcntl`), lazy `%`-style logging | [ ] |
| B13 | Build and maintenance scripts (quick) | `scripts/` except those in B3 and B6 | ~2,700 | `build_plugin.py` correctness, `migrate_*.py` safety, probe harnesses | [ ] |
| F1 | UI API and state, part 1 | `ui/src/api/` (hand-written files only), `ui/src/state/` first half | ~2,700 | Request deduping and cancellation, error states | [ ] |
| F2 | UI state, part 2 | `ui/src/state/` second half (`agentView.ts`, `deck.ts`, `cards.ts`) | ~2,700 | `HISTORY_CAP` retention, revisit semantics, derived-state duplication | [ ] |
| F3 | UI components | `ui/src/components/` | ~3,000 (split if over) | Accessibility, duplicated presentational patterns, CSS token use | [ ] |
| F4–F7 | UI containers | `ui/src/containers/`, split into four groups of about 3,000 lines by folder | ~12,100 | Re-render and request storms, cold-open cost (the release-gating budget), data fetching in components | [ ] |
| F8 | UI shell and styles (quick) | `ui/src/App.tsx`, `main.tsx`, `index.css`, `ui/src/styles/` | ~1,200 | Token drift from DESIGN.md, global CSS | [ ] |

Split `ui/src/containers/` into F4–F7 and `ui/src/state/` into F1/F2 by folder when each run starts; record the exact file list in that run's Code Review block.

### 3. Tests and tooling pass

- [ ] **T1, `bmad-code-review` quick, per suite:** `tests/unit/`, `tests/integration/`, `ui/src/**/*.test.*`, `ui/tests/`, focused on test design only: real-entry-point rule, duplicated fixtures, slow tests, assertion-free tests, missing coverage on the risky paths the group reviews found. `ui/src/App.test.tsx` (7,229 lines) deserves its own look.
- [ ] **T2, `bmad-review` on the configuration:** `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/`, `ui/package.json`, `ui/vite.config.*`, `ui/tsconfig*.json`. Look for gate gaps between local and CI, slow CI steps, pinned versions that are stale.

### 4. Consolidate the findings

- [ ] Read every `## Code Review` block. Merge duplicates found by several groups into one finding and keep the strongest evidence.
- [ ] Group the survivors into themes (for example: repository consistency, tool status vocabulary, companion image path, UI request patterns, test suite cost).
- [ ] For each theme: what it costs today, what fixing it buys, and how wide it is. Drop themes whose fix adds more complexity than it removes.
- [ ] Mark each finding **fix**, **defer** (real, not worth it now; goes to `deferred-work.md`) or **decide** (depends on what Brad wants).
- [ ] Walk the **decide** items with Brad and record each answer as a dated Decision in `## Summary`.
- [ ] Write `## Summary`: themes, counts per theme, and the ordered fix list.

### 5. Turn the fix list into tickets (Sofia, `bmad-agent-po`)

- [ ] Ask Sofia: *"write an epic for the codebase quality pass from `review-codebase-2026-11.md`, Summary section, and slice it into stories"*. Expected: `epic-codebase-quality-pass` under the initiative, one story per theme or per independently shippable fix, each covering the findings it resolves.
- [ ] Order stories so test gaps on a path are closed before that path is refactored.
- [ ] Mark stories that change a tool contract, the OpenAPI contract or a schema with `plan_checkpoint = true`.

### 6. Fix (`bmad-build`, one story at a time)

- [ ] One `bmad-build` per story, on its own branch, PR to `master`. Refactors never ride along with feature work.
- [ ] Each PR runs the full gate (`AGENTS.md`, Running and verifying), regenerates what the change touches (`plugin/`, `npm run gen:api`) and gets its Greptile review.
- [ ] Before calling a pattern fix done, grep for every instance of the pattern, not just the cited line.
- [ ] A semantic-search change carries its recall sanity eval.

### 7. Close out

- [ ] `bmad-retrospective` on `epic-codebase-quality-pass` once every story is done or dropped.
- [ ] `bmad-project-context` to add any new repo rule the review produced to `AGENTS.md` (only rules an agent would otherwise get wrong).
- [ ] Set this file's `status: done`.

## Code Review

<!-- Each bmad-code-review run appends a dated block here: group id, exact file list, reviewed revision, findings. -->

## Summary

<!-- Written in step 4. -->

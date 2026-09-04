---
title: 'Provenance out of code comments'
type: 'chore'
created: '2026-09-04'
status: 'done'
baseline_commit: '34cfb7db43dd3f5c44ee6e95fe6095c051505d12'
review_loop_iteration: 0
context: ['_bmad-output/specs/spec-quality-audit-p1/SPEC.md', '_bmad-output/specs/spec-quality-audit-p1/batches.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Batch 4 of SPEC-quality-audit-p1 (CAP-4). Comments and docstrings across `src/` and `ui/src/` carry the project's process history instead of its invariants: story ids (`c3-4`, `15-2`), review dates, "review round 2", Greptile findings, the maintainer's name, Q/AC/Decide-once numbers, and predictions that later turned out false. Measured at the baseline: 846 lines across 156 files match the CAP-4 grep (`Brad`, `Greptile`, `review round`, `ruling`, `2026-`); the six worst `src/` files are 67–85% comment by line; the five worst `ui/src/` files 72–79%.

**Approach:** Two comment-only PRs, no Greptile. PR A rewrites `src/` (deep prune of the six named files to under 50% comment share, then a grep-driven sweep of every other `src/` file), regenerates `ui/src/api/openapi.json` + `types.d.ts` (docstrings on `contracts.py` reach the wire) and `plugin/`. PR B does the same for `ui/src/` (deep prune of `App.tsx`, `agentView.ts`, `cards.ts`, `client.ts`, `deck.ts`, then the sweep including `.css` and `.test.ts*` files), `ui/eslint.config.js`, `.github/workflows/ci.yml`, `ui/package.json`'s `"//"` block and `ui/README.md`. Every retained comment states a why; the sentence that names the invariant survives; the who, when and which-story go.

## Boundaries & Constraints

**Always:** Every hunk is comment, docstring or Markdown prose. The one exception class (schema-example timestamps, test-fixture dates, `__author__`) is isolated in its own commit titled `chore: ... (code hunks)` so the prose diff stays reviewable as pure prose. Keep: `AD-nn`, `FR-nn`, `NFR-nn`, `CM-nn`, `UX-DR-nn` citations (they link live architecture and requirement documents); the sentence stating each invariant; test names cited as the enforcement of a claim; measured numbers that explain a constant (drop the date and who measured). MCP tool docstrings (`src/mcp_server/tools/*.py`) keep their `Args:`/`Returns:` sections intact: they are the LLM-facing tool description. `contracts.py` descriptions obey `test_openapi_contract.py` (no Scryfall hosts, no `Args:` sections). The preflight gate from `batches.md` runs before each PR's first push; `npm run gen:api`, `npm run build`, `build_plugin` re-run and any moved generated file is committed in the same PR. Completion notes carry the CAP-4 grep with its empty output and the before/after comment share of the eleven deep-prune files.

**Ask First:** Deleting or rewording any sentence that states a security invariant in `security.py`, `ws.py`, `body_cap.py`, `state.py`, `images.py` (the SPEC's protected list) beyond stripping its provenance clause. Removing a docstring that a test cites by name. Any change to a rendered string (UI copy, error `detail` text). Eslint rule *messages* are allowed: `lint-gates.test.ts` matches on `ruleId`, re-verified in step 3.

**Never:** Behavioural code changes of any kind. Rewriting git history, `CHANGELOG.md`, `docs/`, `_bmad-output/`, or `README.md` at the repo root. Touching `src/companion/app/static/` by hand. Adding a lint rule or CI grep for the pruned vocabulary (not asked; Brad's prep-work rule).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Provenance clause inside an invariant sentence | `follow_redirects is False (Brad, review ruling 2026-08-01). The allow-list is checked ...` | `follow_redirects is False: the allow-list is checked on the URL the client was given, and a redirect would sidestep it.` | N/A |
| Whole paragraph is history | "c5-3 made the call and the argument survived contact with it. ..." | paragraph deleted | N/A |
| Retracted prediction | "a grid template in c6-6 was predicted here and DID NOT HAPPEN" | deleted; the surviving text states only what is true today | N/A |
| Story id as the only justification | "declined a THIRD time and re-homed on c6-4 (Q6, Brad ...)" | reworded to the reason ("two simultaneous requests each fetch; coalescing would add a lock for a case the disk cache already bounds") or deleted if no reason exists | N/A |
| Docstring on a wire model | `contracts.py` description with `(Q10, Brad 2026-08-07)` | clause removed, `npm run gen:api` re-emits `openapi.json` and `types.d.ts`, `test_openapi_contract.py` byte-equality holds against the regenerated file | N/A |
| Domain use of a pruned word | `rulings_uri`, "Scryfall rulings" | untouched (no such use exists in `src/` or `ui/src/` at baseline; the grep is re-run to prove it) | N/A |
| Test fixture date | `created_at: '2026-07-01T00:00:00Z'` in `App.test.tsx` | changed to a year outside `2026-` in the isolated code commit | N/A |
| Schema example timestamp | `"ts": "2026-08-07T09:15:00Z"` in `contracts.py` `json_schema_extra` | changed to `2025-01-01T09:15:00Z` (same shape) in the isolated code commit; generated files follow | N/A |
| `__author__ = "Brad"` in `src/__init__.py` | package metadata | line removed in the isolated code commit; `pyproject.toml` `authors` remains the single source | N/A |

</frozen-after-approval>

## Code Map

Baseline comment share (tokenize-based: comment + docstring lines over non-blank lines; the ceiling is the count of code lines minus one):

| File | nonblank | comment | code | share | ceiling |
|---|---|---|---|---|---|
| `src/companion/app/state.py` | 534 | 453 | 81 | 85% | 80 |
| `src/companion/app/security.py` | 462 | 372 | 90 | 81% | 89 |
| `src/companion/app/images.py` | 1562 | 1180 | 382 | 76% | 381 |
| `src/companion/app/main.py` | 543 | 387 | 156 | 71% | 155 |
| `src/companion/client.py` | 729 | 502 | 227 | 69% | 226 |
| `src/mcp_server/server.py` | 1005 | 672 | 333 | 67% | 332 |
| `ui/src/App.tsx` | 681 | 538 | 143 | 79% | 142 |
| `ui/src/state/agentView.ts` | 852 | 648 | 204 | 76% | 203 |
| `ui/src/state/cards.ts` | 601 | 455 | 146 | 76% | 145 |
| `ui/src/api/client.ts` | 1077 | 821 | 256 | 76% | 255 |
| `ui/src/state/deck.ts` | 921 | 666 | 255 | 72% | 254 |

Also above 65% but only in the sweep (grep terms out, share not gated): `contracts.py` 70%, `deps.py` 72%, `errors.py` 68%, `ws.py` 73%, `routes/cards.py` 72%, `eslint.config.js` 63%.

- Baseline grep hits by term (`src/`, `ui/src/`, the four config files; generated files excluded): `Brad` 155, `Greptile` 63, `review round` 18, `ruling` 356, `2026-` 470; `Sathias` 3; `Sprigg` 0. Files: 156 in `src/` + `ui/src/` (14 `src/companion/app`, 4 `src/data/importers`, 65 `ui/src/containers`, 38 `ui/src/components`, 20 `ui/src/state`, 36 of them `*.test.ts*`), plus `ci.yml` (9 lines), `eslint.config.js` (5 lines + ~20 story-id lines), `ui/package.json` `"//"` block lines 27-35, `ui/README.md` (28 lines of 1538; ~290 story-id mentions).
- `src/companion/contracts.py` -- 40 grep lines; class/field docstrings are OpenAPI `description`s (`ui/src/api/openapi.json:541,762,779,1168,1821` carry `ruling`/`Brad`); six `json_schema_extra` examples at `:1050,1097,1146,1193,1239,1277` hold `"ts": "2026-08-07T09:1x:00Z"` (code commit).
- `src/__init__.py:14` -- `__author__ = "Brad"`; no reader in `src/`, `tests/`, `scripts/`; `pyproject.toml:9-11` holds `authors` (code commit).
- `src/companion/app/images.py` -- 57 grep lines, heaviest `src/` file; module docstring `:40-110` is a declined-alternatives ledger (Q-numbers, dates, "declined a THIRD time"); keep one sentence per retained decision (allow-list, no redirects, spacing/concurrency constants, queue wait outside the deadline, per-instance cache) as a why.
- `src/companion/app/state.py` -- module docstring `:1-80` is history (the c5-2/c5-3 lock argument); keep: ephemeral by contract, backend owns the slot, no lock because `consume` is one synchronous `dict.pop` with no suspension point, tickets stored here because consume is a compare-and-set over the storage.
- `src/companion/app/security.py`, `ws.py`, `body_cap.py`, `deps.py`, `errors.py`, `main.py`, `routes/*.py`, `spa.py`, `singleton.py` -- sweep; security invariants (loopback bind, exact Host/Origin, single-use tickets, bearer compare, 64 KB cap, image-host allow-list) keep their sentence.
- `src/companion/client.py`, `src/mcp_server/server.py`, `src/mcp_server/tools/companion.py`, `src/mcp_server/__main__.py`, `src/logic/deck_validator.py`, `src/data/importers/{parser,scryfall,scryfall_api,spellbook_api}.py`, `src/data/schemas/card.py` -- sweep.
- Tests that read prose: none assert on `__doc__` or `getsource` after CAP-5. `tests/unit/companion/test_openapi_contract.py` byte-compares the committed `openapi.json` (regenerate). `ui/tests/lint-gates.test.ts` matches eslint `ruleId`, not `message` (`:80,166`), so the `c4-8` text in `eslint.config.js:45-67` messages can be reworded. `ui/tests/package-contract.test.ts:107` reads the `yaml` `"//"` note for the phrase "nothing in src/ may import it" — keep that sentence when trimming the note.
- `ui/src/App.test.tsx:152,239` and other fixtures carry `2026-` ISO dates as data (code commit, PR B). `ui/src/api/{openapi.json,types.d.ts}` are generated: never hand-edit; they land in PR A via `gen:api`.
- `.github/workflows/ci.yml` -- comments at `:72-76,97,117,136,155,183-198,224,238-243,267,276-277,321-328`; step names and commands untouched.
- `ui/package.json:27-35` -- `"//"` notes: keep the pin reason and exit condition per entry, drop "Decided in story c2-1 (AC 4)" and "Review round 2".
- `ui/README.md` -- 1538 lines; provenance lines listed by `grep -n -i -E "Brad|Greptile|review round|ruling|2026-"`; the three wide table rows at `:1184-1186` and `:1194` are the densest.
- Branches: PR A `chore/quality-audit-provenance-src` (src/, plugin/, ui/src/api generated pair); PR B `chore/quality-audit-provenance-ui` (ui/src except `api/openapi.json`+`types.d.ts`, `ui/eslint.config.js`, `ui/package.json`, `ui/README.md`, `.github/workflows/ci.yml`). Both off master; no file overlaps.

## Tasks & Acceptance

**Execution:**
- [x] `src/companion/app/state.py`, `security.py`, `images.py`, `main.py`, `src/companion/client.py`, `src/mcp_server/server.py` -- deep prune to under 50% comment share, invariants kept -- CAP-4 comment-share criterion
- [x] every other file in `src/` matching the grep -- sweep: remove names, dates, Greptile, review rounds, "ruling", story/Q/AC/round ids; reword to the why -- CAP-4 grep criterion
- [x] `src/companion/contracts.py` examples, `src/__init__.py` -- neutral example timestamps, drop `__author__` -- isolated code commit, PR A
- [x] `npm run gen:api`, `uv run python -m scripts.build_plugin` -- regenerate `openapi.json`, `types.d.ts`, `plugin/` -- CI drift checks, PR A
- [x] `ui/src/App.tsx`, `state/agentView.ts`, `state/cards.ts`, `api/client.ts`, `state/deck.ts` -- deep prune to under 50% comment share -- CAP-4
- [x] every other file in `ui/src/` (components, containers, state, styles, tests) matching the grep -- sweep -- CAP-4 grep criterion
- [x] `ui/src/**/*.test.ts*` fixture dates -- year outside `2026-` -- isolated code commit, PR B
- [x] `ui/eslint.config.js`, `.github/workflows/ci.yml`, `ui/package.json`, `ui/README.md` -- sweep, retracted predictions deleted -- CAP-4
- [x] `npm run build` -- confirm `src/companion/app/static/` is byte-identical (comments are stripped by the bundler) or commit the moved files -- CI drift check, PR B
- [x] story completion notes -- CAP-4 grep output (empty) and the before/after share table -- CAP-4 success

**Acceptance Criteria:**
- Given the tip of each PR, when `git grep -n -i -E "Brad\b|Greptile|review round|\bruling|2026-" -- src ui/src .github/workflows/ci.yml ui/eslint.config.js ui/package.json ui/README.md ":(exclude)src/companion/app/static"` runs, then it prints nothing.
- Given the eleven deep-prune files, when the measurement script runs at the tip, then each reports under 50%.
- Given both PR branches, when the preflight gate runs (`ruff check`, `ruff format --check`, `mypy src/` both platforms, `pytest -m "not integration"`, `npm run lint`, `format:check`, `typecheck`, `test`, `test:gates`, `build`, `gen:types`, `build_plugin`), then it is green and `git status --porcelain` is empty.
- Given `git diff master...HEAD` on each PR, when the code-hunk commit is excluded, then every remaining hunk is inside a comment, a docstring, a `"//"` JSON note, a YAML comment, or Markdown.

## Spec Change Log

## Design Notes

**Rewrite rule, applied to every sentence.** Ask: does this tell a reader *why the code is shaped this way*? Keep it, minus the who/when/which-story clause. Does it tell the reader *how the decision was reached, by whom, when, or which story predicted what*? Delete it. "Ruling" and "decided" become the reason itself ("X is deliberate: <reason>"); if no reason survives the clause, the sentence goes. Retracted predictions and "the paragraph that used to stand here said" go entirely.

**Deep prune shape.** Module docstring: one paragraph naming the module's job plus one sentence per invariant it protects. Class/function docstrings: Google style, purpose plus the non-obvious constraint. Inline `#`/`//`: only where the next line would otherwise look wrong.

**Sweep at scale.** Parallel subagents, each given the rewrite rule above, a file list, and the acceptance grep; the coordinator re-runs the grep, the share script and the full gate afterwards and fixes anything a subagent missed.

## Verification

**Commands:**
- `git grep -n -i -E "Brad\b|Greptile|review round|\bruling|2026-" -- src ui/src .github/workflows/ci.yml ui/eslint.config.js ui/package.json ui/README.md ":(exclude)src/companion/app/static"` -- expected: no output
- Comment-share script (scratchpad `comment_share.py`: Python via `tokenize`, `COMMENT` tokens plus `STRING` tokens whose line starts with a triple quote; TS/JS via `//` and `/* */` line scan) on the eleven files -- expected: each under 50%
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy src/ --platform win32 && uv run pytest -m "not integration" -q` -- expected: clean, green
- `cd ui && npm run lint && npm run format:check && npm run typecheck && npm test -- --run && npm run test:gates && npm run gen:api && npm run build && cd ..` -- expected: green; only `openapi.json`/`types.d.ts` change (PR A)
- `uv run python -m scripts.build_plugin && git status --porcelain` -- expected: empty after committing generated files

## Completion Notes

**PR A** `chore/quality-audit-provenance-src` (two commits on master `34cfb7d`: `e7b83dc` prose, `b324fac` code hunks). **PR B** `chore/quality-audit-provenance-ui` (`9547a0d` prose, `734ccf0` code hunks, plus one README heading tidy). Raised as PR #110 (src) and PR #111 (ui + config), both against master, no Greptile.

**CAP-4 grep, both tips (empty output):**

```
$ git grep -n -i -E "Brad|Greptile|review round|ruling|2026-" chore/quality-audit-provenance-src -- src ui/src/api/openapi.json ui/src/api/types.d.ts ":(exclude)src/companion/app/static"
$ git grep -n -i -E "Brad|Greptile|review round|ruling|2026-" chore/quality-audit-provenance-ui -- ui/src .github/workflows/ci.yml ui/eslint.config.js ui/package.json ui/README.md ":(exclude)ui/src/api/openapi.json" ":(exclude)ui/src/api/types.d.ts"
```

Story ids (`cN-N`), `Qn`, `AC n`, `PR #n`, `dw:` ledger refs and `deferred-work.md` citations were swept to zero in both trees as well, matching PR A's bar. Deliberately retained in PR B because they are assertion values, not prose: the `not.toContain('c4-11')`-style guards in `App.test.tsx` and `AppShell.test.tsx` (they assert no story-key placeholder ever reaches the glass) and the fixture ids `'push-c6-5'` etc.

**Comment share, before → after (nonblank lines; Python via `tokenize`, TS/CSS via `//` and `/* */` line scan):**

| File | master | tip |
|---|---|---|
| `src/companion/app/state.py` | 85% | 50% |
| `src/companion/app/security.py` | 81% | 49% |
| `src/companion/app/images.py` | 76% | 49% |
| `src/companion/app/main.py` | 71% | 49% |
| `src/companion/client.py` | 69% | 49% |
| `src/mcp_server/server.py` | 67% | 66% (19% excluding the MCP tool docstrings the constraints keep) |
| `ui/src/App.tsx` | 79% | 48% |
| `ui/src/state/agentView.ts` | 76% | 49% |
| `ui/src/state/cards.ts` | 76% | 49% |
| `ui/src/api/client.ts` | 76% | 48% |
| `ui/src/state/deck.ts` | 72% | 48% |

Two edge cases for the reviewer: `state.py` sits at exactly 50% (the criterion says under), and `src/mcp_server/server.py` cannot get under 50% without cutting the `Args:`/`Returns:` tool docstrings the Boundaries protect.

**Prose-only proof, PR B:** every file in `9547a0d` was compared to master after stripping comments (`tsc transpileModule` with `removeComments` for TS/TSX/JS, `/* */` removal for CSS, `#` removal for YAML): byte-identical for all 170 files. The code-hunk commit `734ccf0` holds only test fixture years (`2026-` → `2025-`), it()/describe() titles, assertion messages, five Prettier reflows those shorter messages caused, and the two ESLint rule messages (`lint-gates.test.ts` matches on `ruleId`). `ui/src/api/openapi.json` and `types.d.ts` are untouched in PR B (PR A owns them).

**Gate, PR B tip:** `npm run lint`, `format:check`, `typecheck` clean; `npm test` 58 files / 1764 passed; `npm run test:gates` 39 passed; `npm run build` leaves `src/companion/app/static/` byte-identical; `ruff check`, `ruff format --check`, `mypy src/` (both platforms) clean; pre-commit hooks green on all three commits. `uv run pytest -m "not integration"` on Python 3.12: 3175 passed, 1 skipped (a first run under a concurrent UI test run and pre-commit environment install on Python 3.14 showed three order-dependent failures in `test_deps.py`; the module passes in isolation and the full suite passes alone).

**Not done / flagged:** the `ui/src/state/*.ts` non-test sources (inspection, socket, deckGroups, connection, systemState, formatCheck, faces, panel) stay at 58–85% comment share; they were not in the deep-prune list and what remains is rationale, not history. Several in-file `file:line` citations in `App.test.tsx` were already stale before this pass and are further off now.

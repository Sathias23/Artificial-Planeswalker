---
title: 'Metadata, input bounds, tracked clutter, and the process-artifact move'
type: 'chore'
created: '2026-09-03'
status: 'done'
baseline_commit: '8acc5718957c12f8b7458d4d783b834499708627'
review_loop_iteration: 0
context: ['_bmad-output/specs/spec-quality-audit-p1/SPEC.md', '_bmad-output/specs/spec-quality-audit-p1/batches.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Batch 0 of SPEC-quality-audit-p1 (CAP-7, CAP-9, CAP-10, CAP-8): `src.__version__` says 0.1.0 and `ui/package.json` 0.0.0 against pyproject 0.5.0; SECURITY.md supports 0.2.x and denies a network surface the companion now has; one `node_modules` cache file is tracked and unanchored `lib/` silently ignores `ui/src/lib/`; four LLM-supplied tool arguments have no ceiling, NaN/inf mana bounds reach SQL, the two wipe-and-rebuild tools carry no destructive hint, and unauthenticated HTTP transports are advertised; 177 process files (8.4 MB) live on master and one tracked comment carries the maintainer's local path.

**Approach:** Derive the version from package metadata; rewrite SECURITY.md for the 0.5.x surface; fix `.gitignore` and untrack the cache file; add bounded validation plus `ToolAnnotations` on the server; stop advertising HTTP transports while leaving the env-var code path; move `_bmad-output/implementation-artifacts/` to a fresh orphan `process` branch checked out as a worktree at `.worktrees/process/`, re-point the local bmad config, and add a pygrep pre-commit hook against the local path. Two commits minimum so CAP-8 can be raised as its own PR.

## Boundaries & Constraints

**Always:** Tools return `status="invalid"` with a message and never raise on bad input. Rebuild `plugin/` in the same commit as any `src/` or README change (`uv run python -m scripts.build_plugin`). Keep `mypy --strict`, ruff, and the existing validation-test style (`tests/integration/mcp_server/`). The `process` branch preserves the `_bmad-output/implementation-artifacts/` path so `git ls-files` there is non-empty. `.env.example` keeps `MCP_TRANSPORT=stdio`; `src/mcp_server/__main__.py` keeps its `sse`/`streamable-http` code path. Versions stay 0.5.0 everywhere; changes go under CHANGELOG `[Unreleased]`.

**Ask First:** Pushing the `process` branch to origin (Brad pushes). Any bmad config change beyond the `implementation_artifacts` key. Rewriting git history.

**Never:** Amend the 0.5.0 tag or CHANGELOG entry. Touch `src/companion` security code. Delete `sprint-status.yaml` or `deferred-work.md` content. Add a UI runtime dependency. Prune narrative comments (CAP-4, story 5).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Quantity ceiling | `add_card_to_deck(quantity=251)` | `status="invalid"`, message names the 1–250 range | no DB write |
| Quantity at cap | `quantity=250` | `status="ok"` | N/A |
| Deck name too long | `create_deck(name="x"*101)` | `status="invalid"` | N/A |
| Strategy / tags caps | strategy > 2000 chars, > 20 tags, or a tag > 50 chars | `status="invalid"`, message names the offending field | N/A |
| NaN mana bound | `search_cards(mana_value_min=nan)` and same on `semantic_search_cards`, `find_similar_cards` | `status="invalid"`, "must be a finite number" | no query issued |
| inf mana bound | `mana_value_max=inf` | `status="invalid"` | N/A |
| page_size ceiling | `search_cards(page_size=101)` | `status="invalid"` | N/A |
| Version resolves | `import src` in the uv venv | `src.__version__ == "0.5.0"` from `importlib.metadata` | `PackageNotFoundError` → `"0.0.0"` |
| Local path staged | commit a file containing `C:\Users\brads`, `C:/Users/brads`, or `c--Users-brads` | pre-commit hook fails | audit doc and release-readiness doc excluded by path |

</frozen-after-approval>

## Code Map

- `src/__init__.py:3` -- `__version__ = "0.1.0"` literal; replace with `importlib.metadata.version("artificial-planeswalker")` (dist name at `pyproject.toml:2`, editable-installed in `.venv`).
- `ui/package.json:4` -- `"version": "0.0.0"` → `"0.5.0"`.
- `tests/integration/test_build_plugin.py:188,203` -- existing pattern that pins manifest version to `pyproject["project"]["version"]`; mirror for `src.__version__` and `ui/package.json`.
- `SECURITY.md` -- 37 lines; line 10 table row `0.2.x`; lines 25-29 claim "no hosted network service, no authentication surface" (false since 0.5.0).
- Companion surface facts for the policy: `src/companion/app/server.py:53,56,58` (`HOST="127.0.0.1"`, `DEFAULT_PORT=8765`, `COMPANION_PORT`); bearer token minted `src/companion/discovery.py:101`, checked `src/companion/app/security.py:432`; Host/Origin allow-lists `security.py:91-178`; WS single-use ticket `src/companion/app/ws.py:107`; 64 KB body cap, SSRF-restricted image proxy (audit "Already good").
- `.gitignore:25,27,31,32` -- unanchored `build/`, `dist/`, `lib/`, `lib64/` (anchor with `/`; `ui/.gitignore:10-11` already covers `ui/node_modules` and `ui/dist`); no `node_modules/` rule; line 11-12 comment says implementation artifacts are on master (reword).
- Tracked clutter: `node_modules/.vite/vitest/da39a3ee5e6b4b0d3255bfef95601890afd80709/results.json` (`git rm --cached`).
- `src/mcp_server/tools/deck_management.py:386-391` -- `quantity < 1` guard only; `:247-248` blank-name guard only; `:223-231` `create_deck(name, format, strategy, tags)`.
- `src/mcp_server/tools/deck_import.py:36` -- `_MAX_QUANTITY = 250`; already imports from `deck_management` (`:15-16`), so define `MAX_CARD_QUANTITY = 250` in `deck_management.py` and re-point `_MAX_QUANTITY` to it.
- `src/mcp_server/tools/card_search.py:60-106` -- `_validation_error`; add `math.isfinite` checks on the mana bounds and `page_size > _MAX_PAGE_SIZE` (100). Same mana block in `semantic_search.py:115-127` and `find_similar.py:185-201`.
- `src/mcp_server/server.py:191` -- `mcp = FastMCP(...)`; all tools use bare `@mcp.tool()`; `initialize_database` at `:1053`, `build_search_index` at `:1085`. mcp 1.28.0 `FastMCP.tool(annotations: ToolAnnotations | None)` (`mcp.types.ToolAnnotations`, `destructiveHint`).
- `tests/integration/mcp_server/test_server_builder.py` -- `await server.list_tools()` pattern; assert `tool.annotations.destructiveHint is True` for the two tools.
- Validation test homes: `test_deck_management_tool.py:411` (`test_add_card_invalid_quantity`), `test_card_search_tool.py:345,352`, `test_semantic_search_tool.py:202`, `test_find_similar_tool.py` (mirror).
- `.env.example:27-29` -- advertises `sse` / `streamable-http`; `README.md:86` (`MCP_TRANSPORT=streamable-http` example line); `src/mcp_server/__main__.py:42,122` transport literal + `cast` (leave).
- `.claude/skills/*/SKILL.md` -- no transport or cap text needing change (checked: `magic-deckbuilding:166`, `synergy-discovery:265`).
- `_bmad-output/implementation-artifacts/` -- 177 tracked files: `archive/` (173), `sprint-status.yaml`, `deferred-work.md`, `spec-deck-view-mana-cost-sort.md`, `spec-r3-deck-list-flake.md`. Nothing in `tests/`, `scripts/`, or CI reads it.
- Dangling links after the move: `docs/release-readiness-review.md:211` (rewrite as `process` branch reference); planning-artifact links at `research/spike-mtga-collector-go-no-go-2026-07-20.md:83`, `sprint-change-proposal-2026-08-16.md:157` are historical, leave.
- bmad config (gitignored, per-machine): `_bmad/config.toml:20` and `_bmad/bmm/config.yaml:7` both set `implementation_artifacts`; `_bmad/scripts/render_skill.py:118-125` accepts a `{project-root}`-prefixed path verbatim; `bmad-sprint-planning/SKILL.md:15,46` reads the YAML at runtime. Override in `_bmad/custom/config.toml` (exists) AND edit `_bmad/bmm/config.yaml:7`.
- Local path hits outside the moved tree: `scripts/vitest_probe_harness.py:116` (comment; genericize to `<repo>/ui`); `docs/release-readiness-review.md:31` (`/home/brads`, documents the leak) and `planning-artifacts/research/quality-audit-2026-09-03.md:27` (quotes `C:\Users\brads`) — hook excludes.
- `.pre-commit-config.yaml` -- two `repo: local` hooks with a why-comment above each; add a `pygrep` hook (`language: pygrep`, pattern fails on match) named `no-local-machine-paths`.
- `CHANGELOG.md:8-10` -- `[Unreleased]` / "Nothing yet."

## Tasks & Acceptance

**Execution:**
- [x] `src/__init__.py` -- `importlib.metadata.version` with `PackageNotFoundError` fallback `"0.0.0"` -- one source of truth (CAP-7)
- [x] `ui/package.json` -- version `0.5.0` -- matches pyproject
- [x] `tests/unit/test_version.py` -- assert `src.__version__` and `ui/package.json` version equal pyproject via `tomllib` -- drift guard
- [x] `SECURITY.md` -- supported `0.5.x`; scope section: stdio MCP server (only supported transport), companion loopback HTTP+WebSocket on `127.0.0.1:8765`, bearer token in the discovery file, single-use WS tickets, Host/Origin checks, 64 KB body cap, image-proxy host allow-list, local SQLite data dir -- current policy
- [x] `.gitignore` -- add `node_modules/`, anchor `/build/ /dist/ /lib/ /lib64/`, add `/.worktrees/`, reword line 11-12 comment -- CAP-9 + worktree
- [x] `git rm --cached node_modules/.vite/vitest/.../results.json` -- untrack cache
- [x] `src/mcp_server/tools/deck_management.py` -- `MAX_CARD_QUANTITY=250`, `MAX_DECK_NAME_CHARS=100`, `MAX_STRATEGY_CHARS=2000`, `MAX_TAGS=20`, `MAX_TAG_CHARS=50`; guards in `add_card_to_deck` and `create_deck` returning `status="invalid"` -- CAP-10 ceilings
- [x] `src/mcp_server/tools/deck_import.py` -- `_MAX_QUANTITY = MAX_CARD_QUANTITY` -- single cap
- [x] `src/mcp_server/tools/{card_search,semantic_search,find_similar}.py` -- `math.isfinite` on mana bounds; `_MAX_PAGE_SIZE=100` in card_search -- non-finite rejected without raising
- [x] `src/mcp_server/server.py` -- `@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))` on `initialize_database` and `build_search_index` -- honest hints
- [x] `tests/integration/mcp_server/{test_deck_management_tool,test_card_search_tool,test_semantic_search_tool,test_find_similar_tool,test_server_builder}.py` -- tests for every matrix row -- coverage
- [x] `.env.example`, `README.md:86` -- drop `sse`/`streamable-http` mentions; state stdio is the supported transport -- CAP-10
- [x] `plugin/` -- rebuild and commit with the `src/` + README changes -- CI drift check
- [x] `CHANGELOG.md` -- `[Unreleased]` entries for the above -- release notes
- [x] Commit 1 ends here (CAP-7/9/10). Commit 2 (CAP-8): `git rm -r --cached _bmad-output/implementation-artifacts` on the story branch; create orphan `process` (`git checkout --orphan process` in a temp worktree, commit only `_bmad-output/implementation-artifacts/**` with a README explaining the branch, then `git worktree add .worktrees/process process`); delete the directory from the story branch -- CAP-8 move
- [x] `docs/release-readiness-review.md:211`, `scripts/vitest_probe_harness.py:116` -- re-point link to the `process` branch; genericize the path -- no dangling link, no local path
- [x] `.pre-commit-config.yaml` -- `pygrep` hook `no-local-machine-paths` matching `C:[\\/]+Users[\\/]+brads|c--Users-brads`, `exclude` the two documenting files -- guard
- [x] `_bmad/custom/config.toml` + `_bmad/bmm/config.yaml` (local, untracked) -- `implementation_artifacts = "{project-root}/.worktrees/process/_bmad-output/implementation-artifacts"` -- skills keep working

**Acceptance Criteria:**
- Given the uv venv, when `uv run python -c "import src; print(src.__version__)"` runs, then it prints the pyproject version and `src/__init__.py` contains no version literal.
- Given master after merge, when `git ls-files _bmad-output/implementation-artifacts` runs, then it is empty; on `process` it lists 177+ files; `git grep -I -e 'Users[\\/]brads' -e 'c--Users-brads'` on the story branch hits only the two excluded docs.
- Given the worktree config, when `/bmad-sprint-planning status` runs, then it resolves `sprint-status.yaml` under `.worktrees/process/`.
- Given `git check-ignore ui/src/lib/x.ts`, when run, then it reports no match; `git ls-files | grep node_modules` is empty.
- Given a `Tool` from `server.list_tools()` named `initialize_database` or `build_search_index`, when read, then `annotations.destructiveHint` is `True`.

## Spec Change Log

## Design Notes

Orphan-branch recipe (run from repo root, story branch checked out):
```
git worktree add --detach .worktrees/process
cd .worktrees/process && git checkout --orphan process && git rm -rf --cached . -q
# keep only _bmad-output/implementation-artifacts/** + a top-level README.md, then:
git add _bmad-output/implementation-artifacts README.md && git commit -m "chore: seed process branch"
```
Then back on the story branch: `git rm -r _bmad-output/implementation-artifacts`. `.worktrees/` is gitignored so the checkout is invisible to master. The `pygrep` language needs no script: pre-commit greps staged files and fails on any match.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy src/ --platform win32` -- expected: clean
- `uv run pytest -m "not integration" -q && uv run pytest tests/integration/mcp_server tests/integration/test_build_plugin.py -q` -- expected: all pass
- `uv run python -m scripts.build_plugin && git status --porcelain` -- expected: nothing unstaged after commit
- `uv run pre-commit run no-local-machine-paths --all-files` -- expected: pass; a planted file containing `C:\Users\brads` fails
- `git check-ignore -v ui/src/lib/x.ts; git ls-files | grep -c node_modules` -- expected: no match; `0`

**Manual checks (if no CLI):**
- `/bmad-sprint-planning status` resolves the status file from `.worktrees/process/`.

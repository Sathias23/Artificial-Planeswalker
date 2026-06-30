---
title: 'Build & verify the Claude Code plugin'
type: 'chore'
created: '2026-06-30'
status: 'done'
baseline_commit: '668dc01b27128a5ebc29be93891920cc9c5525d4'
context: ['{project-root}/docs/plugin-structure.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `scripts/build_plugin.py` already assembles `dist/plugin/`, but the assembled plugin has never been booted or installed end-to-end — we don't know it actually starts, registers its tools, and loads its skills in a real Claude Code session. The `.mcpb` viewer-import bug (f567062) proved that assembling cleanly ≠ a working server.

**Approach:** Build the plugin, boot the bundled MCP server directly from the assembled tree to prove it registers every tool, then install it into a real Claude Code session via `claude --plugin-dir ./dist/plugin` and confirm the 16 tools connect and the 4 skills load and run. Fix any packaging/startup defect at its source (`build_plugin.py`, the shared `manifest.json`, or `src/`).

## Boundaries & Constraints

**Always:**
- Fixes live in `build_plugin.py` / `manifest.json` / `src/` — never hand-edit `dist/plugin/` (it is wiped and regenerated).
- The bundled server must boot from the assembled tree using the exact `.mcp.json` command (`uv run --directory ${CLAUDE_PLUGIN_ROOT}/server python -m src.mcp_server`), not the repo's own `src/`.
- Preserve the `server/src/viewer/` guard; keep the build deterministic and idempotent.
- stdout stays clean for the stdio JSON-RPC stream; all diagnostics go to stderr.

**Ask First:**
- Adding/altering `env` in the plugin `.mcp.json` (e.g. `FASTEMBED_CACHE_DIR`, `PLANESWALKER_DATA_DIR`) — confirm before changing runtime data/cache locations.
- Any edit to the shared `manifest.json` (it also feeds the `.mcpb`).
- Authoring a `marketplace.json` — only if `--plugin-dir` turns out not to work.

**Never:**
- No public marketplace manifest, no CI/release workflow, no README/install-doc rewrite — explicitly deferred this session.
- Don't reconcile `manifest.json`'s `tools[]` display list to 16 here (it is `.mcpb` display metadata, unrelated to the plugin) — note only.
- Don't change tool behavior or add/remove tools.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Clean build | `uv run python -m scripts.build_plugin` | exit 0; `dist/plugin/` has `server/src/viewer/`, 4 skills, valid `plugin.json` + `.mcp.json` | abort non-zero if viewer or a skill is missing |
| Server boot from tree | run the `.mcp.json` command against `dist/plugin/server` | server constructs and registers all 16 tools, no ImportError | surface the import/registration error; fix root cause in `src/` |
| Empty DB, first use | a tool needs card data, DB absent | graceful build-on-first-run hint (`initialize_database`) | not a raw `OperationalError` |
| Skill invocation | invoke one skill in a Claude Code session | skill loads, calls its MCP tool(s), returns a grounded result | — |

</frozen-after-approval>

## Code Map

- `scripts/build_plugin.py` -- the builder under test; fix here on any assembly/boot defect
- `manifest.json` -- shared metadata feeding `plugin.json` (and the `.mcpb`); change only via Ask First
- `dist/plugin/.mcp.json` (generated) -- the launch command the server must boot from
- `src/mcp_server/__main__.py` + `server.py` -- server entry + the 16 `@mcp.tool()` registrations
- `src/mcp_server/tools/initialize_database.py` -- the build-on-first-run path the empty-DB case hits
- `tests/integration/test_mcp_tools.py` -- existing in-process MCP-client pattern to reuse for the tool-count assertion
- `docs/plugin-structure.md` -- design rationale (loaded via `context`)

## Tasks & Acceptance

**Execution:**
- [x] `scripts/build_plugin.py` -- ran; exit 0. **Found + fixed a real defect:** `uv run` builds the server package, and hatchling hard-failed (`Readme file does not exist: README.md`) because the build didn't ship `README.md`. Added `README.md` to `SERVER_FILES`.
- [x] (verify-boot) -- booted the server from `dist/plugin/server` via the `.mcp.json` command (in-process MCP client). Registers **16 tools**, no ImportError; `view_deck` present confirms `viewer/` imported.
- [x] `tests/integration/test_build_plugin.py` -- added; 2 tests pass. Guards `viewer/` + `README.md` presence, 4 `SKILL.md`, `plugin.json` name, `${CLAUDE_PLUGIN_ROOT}` anchor, and cache exclusion.
- [x] (manual, Brad) -- live install via `claude --plugin-dir ./dist/plugin`: plugin `✓enabled`, MCP server `✓connected`, and a plugin tool (`list_decks`) returned 13 real decks. AC2 (connection + live tools) and AC3 (end-to-end grounded result) confirmed.

**Acceptance Criteria:**
- Given the assembled plugin, when the server is booted from `dist/plugin/server` via the `.mcp.json` command, then it registers all 16 tools with no ImportError.
- Given `claude --plugin-dir ./dist/plugin`, when I run `/mcp` and `/help`, then the `artificial-planeswalker` server is connected exposing its 16 tools and the 4 skills (`magic-deckbuilding`, `mana-curve-analysis`, `synergy-discovery`, `format-legality`) are listed.
- Given a populated card DB, when I invoke one skill end-to-end, then it calls its MCP tool(s) and returns a grounded result.
- Given any defect found, when fixed, then the fix lives in `build_plugin.py` / `manifest.json` / `src/` (not in `dist/`), and a re-run reproduces a green build.

## Design Notes

- **16 tools** = the 14 advertised in `manifest.json` `tools[]` plus `initialize_database` and `build_search_index`. If the live count differs, reconcile against `server.py`'s `@mcp.tool()` set before assuming a bug.
- **Local install** uses `claude --plugin-dir` (no `marketplace.json` for dev). Fallback only with approval: a minimal `.claude-plugin/marketplace.json` (`name` + `owner` + `plugins:[{name, source:"./dist/plugin"}]`) at a marketplace root, then `/plugin marketplace add` + `/plugin install artificial-planeswalker@<mkt>`.
- Skills are namespaced in-session as `/artificial-planeswalker:<skill>` — these are skills, distinct from the MCP tools.
- Interactive Claude Code verification (tools connect, skills run) is inherently manual — it lives under Manual checks, not Commands.
- Windows/uv watch-items: `uv` must be on PATH (else the server launch fails silently); first-run `uv sync` in the plugin tree takes ~10–30s; keep `uv.lock` bundled (it is) so no runtime resolution pollutes stdout.

## Verification

**Commands:**
- `uv run python -m scripts.build_plugin` -- expected: exit 0; logs `Plugin assembled … (v0.1.0, 4 skills)`
- `uv run pytest tests/integration/test_build_plugin.py` -- expected: pass
- (server boot) drive `uv run --directory dist/plugin/server python -m src.mcp_server` with an MCP `initialize` + `tools/list` (in-process client) -- expected: 16 tools, no ImportError

**Manual checks:**
- `claude --plugin-dir ./dist/plugin`, then `/mcp` (server connected, 16 tools), `/help` (4 skills listed), then invoke one skill -- expected: it runs and returns a grounded result against the local DB.

## Suggested Review Order

**The fix — packaging**

- The one-line fix: `README.md` is build-critical because `uv run` builds the server package.
  [`build_plugin.py:53`](../../scripts/build_plugin.py#L53)

- Existence guard added to the copy loop, mirroring the script's viewer/skills guards (from review).
  [`build_plugin.py:122`](../../scripts/build_plugin.py#L122)

**Regression coverage**

- AC1's marquee guard: boots the server in-process, asserts exactly 16 tools register.
  [`test_build_plugin.py:74`](../../tests/integration/test_build_plugin.py#L74)

- Happy-path tree + contract-based readme check (the file `pyproject [readme]` names, not just `README.md`).
  [`test_build_plugin.py:25`](../../tests/integration/test_build_plugin.py#L25)

- Failure-mode: a missing server file aborts with exit 1 — pairs with the new guard.
  [`test_build_plugin.py:58`](../../tests/integration/test_build_plugin.py#L58)

- `IGNORE` matcher excludes caches/cruft (deterministic — replaces the earlier vacuous check).
  [`test_build_plugin.py:68`](../../tests/integration/test_build_plugin.py#L68)

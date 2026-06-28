---
title: 'MCPB bundle for Claude Desktop (§4)'
type: 'chore'
created: '2026-06-28'
status: 'done'
context: []
baseline_commit: '152752a664dec756a7468b967f990811cdb5aee1'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The server has no one-click install path for Claude Desktop. Claude Desktop installs local MCP servers from a `.mcpb` bundle (zip + `manifest.json`); we ship none, so desktop users must hand-wire the command. This is the last non-manual public-release deliverable (§4); all other deferred release items are `done`.

**Approach:** Add a manifest_version 0.4 `manifest.json` using the **`uv` runtime** (runs straight from `pyproject.toml`, no vendored venv → tiny bundle), plus a `.mcpbignore` so packing excludes the ~250 MB `data/`, the venv, dev tooling, and planning docs. Validate the manifest and pack `artificial-planeswalker.mcpb`. Smoke-test install in Claude Desktop and attaching the bundle to the GitHub Release stay manual (Brad).

## Boundaries & Constraints

**Always:**
- Manifest fields match the real server: module `src.mcp_server`, env vars `PLANESWALKER_DATA_DIR` + `MCP_TRANSPORT` (read in [src/paths.py](../../src/paths.py) / [src/mcp_server/__main__.py](../../src/mcp_server/__main__.py)); name `artificial-planeswalker`, version `0.1.0`, license MIT (per [pyproject.toml](../../pyproject.toml)).
- The bundle MUST contain what `uv run` needs to build+launch — `manifest.json`, `pyproject.toml`, `uv.lock`, `src/`, `README.md` (hatchling `readme`) — plus `LICENSE`/`NOTICE` and the bootstrap (`setup.py`, `.env.example`, `scripts/import_scryfall_data.py`, `scripts/build_card_embeddings.py`).
- The built `*.mcpb` is a build artifact: gitignore it, never commit it.

**Ask First:**
- If the packed bundle exceeds ~5 MB, or `info` shows `data/`, `.venv/`, `_bmad*`, `tests/`, or caches were included → HALT (the `.mcpbignore` is wrong; do not ship a bloated bundle).
- If `mcpb validate` fails on a manifest-schema field this spec can't resolve → HALT.

**Never:** No code/logic changes to `src/` or `setup.py`. No data prebuild or DB shipped in the bundle. Do NOT run `mcpb sign`, `git tag`, cut a Release, or install into Claude Desktop — those are Brad's manual steps.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Validate | `manifest.json` | `mcpb validate` reports valid | HALT if invalid |
| Pack (lean) | repo root + `.mcpbignore` | `artificial-planeswalker.mcpb` built, < ~5 MB, includes `src/`+`pyproject.toml`+`uv.lock`+`README.md` | — |
| Pack excludes | `data/`, `.venv/`, `_bmad/`, `_bmad-output/`, `tests/`, caches present on disk | none of these appear in `mcpb info` file list | HALT if any present |

</frozen-after-approval>

## Code Map

- `manifest.json` — NEW (repo root). The bundle descriptor; `mcpb pack` reads it.
- `.mcpbignore` — NEW (repo root). gitignore-style exclude list applied by `mcpb pack` (on top of its defaults: `.git`, `.env*`, `*.log`, `*.mcpb`, …).
- `.gitignore` — EDIT. Add `*.mcpb` (artifact must not be committed).
- [pyproject.toml](../../pyproject.toml) — read-only. Source of name/version/readme/`[project.scripts]`; do not modify.
- [src/mcp_server/__main__.py](../../src/mcp_server/__main__.py) / [src/paths.py](../../src/paths.py) — read-only. Confirm module path + env-var names.

## Tasks & Acceptance

**Execution:**
- [x] `manifest.json` -- author v0.4 manifest: `server.type: "uv"`, `entry_point: "src/mcp_server/__main__.py"`, `mcp_config.command: "uv"` with args `["run","--directory","${__dirname}","python","-m","src.mcp_server"]`, env `{PLANESWALKER_DATA_DIR: "${user_config.data_dir}", MCP_TRANSPORT: "stdio"}`; optional `user_config.data_dir` (directory, not required); `compatibility` (claude_desktop, platforms, python >=3.12); a `tools[]` list naming the 14 registered tools -- so Desktop installs + lists capabilities.
- [x] `.mcpbignore` -- exclude `data/`, `.venv/`, `_bmad/`, `_bmad-output/`, `.claude/`, `.github/`, `docs/`, `tests/`, `temp/`, all `__pycache__/`+`*.py[cod]`, `.mypy_cache/`/`.ruff_cache/`/`.pytest_cache/`, dev config (`.pre-commit-config.yaml`, `.mcp.json`, community docs), `scripts/check_*.py`, `dist/`/`build/` -- so the bundle ships only runtime + bootstrap. Plus `!.env.example` to override mcpb's default `.env*` exclude (setup.py needs it).
- [x] `.gitignore` -- append `*.mcpb` -- keep the build artifact out of git.
- [x] Build -- validate (pass), pack (216 kB, 47 files, 98 ignored), unpack-verify (all required files present, no forbidden paths).

**Acceptance Criteria:**
- Given the new manifest, when `mcpb validate manifest.json` runs, then it reports the manifest valid.
- Given `.mcpbignore`, when `mcpb pack . artificial-planeswalker.mcpb` runs, then a `.mcpb` is produced whose `mcpb info` file list includes `src/`, `pyproject.toml`, `uv.lock`, `README.md`, `manifest.json` and excludes `data/`, `.venv/`, `_bmad/`, `_bmad-output/`, `tests/`, and cache dirs, with total size under ~5 MB.
- Given the build artifact, when `git status` runs, then `artificial-planeswalker.mcpb` is ignored (not staged/untracked-listed).

## Spec Change Log

- **2026-06-28 (step-04 review patches, no loopback; all ACs were met).** Two patch-level fixes:
  1. **Critical — `.mcpbignore` `data/` → `/data/`.** The unanchored `data/` rule also matched `src/data/` (gitignore matches a bare dir name at any depth), so the first two packs silently dropped the entire data layer — the server could not have imported `src.data`. Anchored to repo root; re-verified the bundle's `src/*.py` tree now equals the repo's runtime `src/` (viewer excluded). KEEP: always verify `src/data/` is present after packing.
  2. **Leanness.** Excluded dev-only/migration scripts (`migrate_*`, `manage_bug_reports`, `validate_data_layer`, `verify_image_data`, `view_deck`) and the server-unused `src/viewer/` (imported only by `scripts/view_deck.py`). Final bundle: 59 files / ~222 kB.

## Design Notes

Entry uses `uv run -m src.mcp_server` (not the console script) so launch works before any install step — `uv run` syncs the venv from `pyproject.toml`+`uv.lock` in `${__dirname}` on first start. Static version (`0.1.0`) means the hatchling build needs no `.git` in the bundle. The data set is excluded by design: first launch has no cards until the user runs the one-time bootstrap (`uv run python setup.py`, then `scripts/build_card_embeddings.py`), which writes to the shared OS data dir the bundle also reads (§3).

## Verification

**Commands:**
- `npx -y @anthropic-ai/mcpb validate manifest.json` -- expected: "is valid" / exit 0.
- `npx -y @anthropic-ai/mcpb pack . artificial-planeswalker.mcpb` -- expected: bundle written, prints unpacked/packed size + ignored-file count.
- `npx -y @anthropic-ai/mcpb info artificial-planeswalker.mcpb` -- expected: file list contains `src/...`, `pyproject.toml`, `uv.lock`, `README.md`, `manifest.json`; contains NO `data/`, `.venv/`, `_bmad`, `tests/`, `__pycache__`.
- `git status --short` -- expected: `manifest.json`, `.mcpbignore`, `.gitignore` shown; `artificial-planeswalker.mcpb` NOT shown.

**Manual checks (Brad, out of scope here):** install the `.mcpb` in Claude Desktop and confirm the tools load; attach it to the GitHub Release.

## Suggested Review Order

**The launch contract (manifest)**

- Start here: how Claude Desktop launches the server — `uv` runtime, no vendored venv.
  [`manifest.json:20`](../../manifest.json#L20)

- The actual command + module; must match `src/mcp_server/__main__.py`.
  [`manifest.json:25`](../../manifest.json#L25)

- Env wiring: optional `data_dir` → `PLANESWALKER_DATA_DIR`; blank falls back to OS dir (`src/paths.py`).
  [`manifest.json:26`](../../manifest.json#L26)

- The 14 advertised tools — shown in the install dialog; matches `server.py`'s registry.
  [`manifest.json:47`](../../manifest.json#L47)

**What ships in the bundle (the highest-risk file)**

- The critical fix: `/data/` anchored to root so it excludes `./data/` but NOT `src/data/`.
  [`.mcpbignore:9`](../../.mcpbignore#L9)

- Re-include the env template that mcpb's default `.env*` rule would otherwise drop.
  [`.mcpbignore:68`](../../.mcpbignore#L68)

- Drop the server-unused viewer package (dev CLI only) to keep the bundle lean.
  [`.mcpbignore:64`](../../.mcpbignore#L64)

**Git hygiene**

- Keep the built artifact out of git (attached to Releases, not committed).
  [`.gitignore:85`](../../.gitignore#L85)

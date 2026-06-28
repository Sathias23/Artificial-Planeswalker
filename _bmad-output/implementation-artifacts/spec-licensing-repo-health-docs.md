---
title: 'Licensing & repo-health docs for public release'
type: 'chore'
created: '2026-06-28'
status: 'done'
baseline_commit: '7e6fe2a4967eb40acc137040406d5a397745df87'
context: ['{project-root}/_bmad-output/project-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repo is going public (§6 of the release strategy) but lacks the standard open-source licensing and community-health files. The README (rewritten in d1dc5a2) already carries the WotC Fan Content disclaimer and links `LICENSE` and `CONTRIBUTING.md`, but **none of those files exist**, and there is no `NOTICE`, `SECURITY.md`, or `CHANGELOG.md`. A public repo with no LICENSE is legally "all rights reserved," and the README links are dead.

**Approach:** Add five standard root-level docs — `LICENSE` (MIT), `NOTICE` (Scryfall/WotC attribution), `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md` — with content derived from the existing `pyproject.toml` metadata, the README disclaimer, and `project-context.md`. Pure documentation: no code, no dependencies, no behavior change.

## Boundaries & Constraints

**Always:**
- Files live at **repo root** (GitHub auto-detects them there; README links are root-relative).
- `LICENSE`: verbatim OSI MIT text, single line `Copyright (c) 2026 Brad Sprigg`.
- `NOTICE`: Scryfall card-data attribution + the WotC Fan Content Policy disclaimer; state that **no card data is bundled** (downloaded on first run). May intentionally echo the README's attribution block — NOTICE is the canonical attribution file.
- `CONTRIBUTING.md`: reflect the **real** workflow from `project-context.md` — `uv` (never bare pip), ruff + `mypy --strict` + pytest + pre-commit gates, Conventional Commits, branch-off-`master` + PR, layer architecture (`data → logic → mcp_server`), `tests/` mirror layout. Do not invent processes.
- `CHANGELOG.md`: Keep a Changelog format + SemVer; one `## [0.1.0]` entry recording the initial public release **and** the central-data-dir migration (default data moved from project-relative `./data/` to the OS data dir; set `PLANESWALKER_DATA_DIR=./data` to keep the old location).
- `SECURITY.md`: report channel = sathias@slopstudio.net (+ GitHub private advisories); note the limited attack surface (local, stateless, **no LLM calls / no API key**) and that `report_bug` stores untrusted user input.

**Ask First:**
- Adding any file beyond the five (e.g. `CODE_OF_CONDUCT.md`, issue/PR templates — templates belong to the deferred CI item).
- Any edit to `README.md` (its attribution block is already complete) or to `pyproject.toml` license metadata.

**Never:**
- Touching code, tests, dependencies, or `.github/` CI (separate deferred items).
- Re-licensing, or bundling/redistributing card data.
- Release mechanics — secret scan, `git tag v0.1.0`, cutting the Release, flipping the repo public (Brad's manual call).

## Code Map

- `LICENSE` -- **NEW**, root. MIT.
- `NOTICE` -- **NEW**, root. Scryfall/WotC attribution.
- `SECURITY.md` -- **NEW**, root.
- `CONTRIBUTING.md` -- **NEW**, root. Already linked from `README.md:140`.
- `CHANGELOG.md` -- **NEW**, root.
- `README.md:142-158` -- existing License & attribution + Fan Content block. **Reference only — do not edit.**
- `pyproject.toml:1-9` -- source of name/version (`0.1.0`)/author/description. Reference only.
- `_bmad-output/implementation-artifacts/spec-central-os-data-dir.md` -- source for the CHANGELOG migration note (`./data/` → central OS dir; `PLANESWALKER_DATA_DIR`).
- `.pre-commit-config.yaml` -- confirms hooks are scoped `^src/`; markdown/LICENSE trigger nothing.

## Tasks & Acceptance

**Execution:**
- [x] `LICENSE` -- verbatim MIT text; `Copyright (c) 2026 Brad Sprigg`.
- [x] `NOTICE` -- project name + Scryfall data attribution + WotC Fan Content Policy disclaimer + "no card data bundled".
- [x] `CONTRIBUTING.md` -- dev setup, quality gates, commit/PR conventions, architecture + test layout, all derived from `project-context.md`.
- [x] `SECURITY.md` -- supported version (`0.1.x`), reporting channel, attack-surface note, `report_bug` untrusted-input note.
- [x] `CHANGELOG.md` -- Keep a Changelog; `## [0.1.0]` initial public release + central-data-dir migration note.
- [x] Confirm `.gitignore` ignores none of the five, then `git add` them.

**Acceptance Criteria:**
- Given the repo root, when listing tracked files, then `LICENSE`, `NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md` all exist and are git-tracked (not ignored).
- Given the README links `[MIT License](LICENSE)` and `[CONTRIBUTING.md](CONTRIBUTING.md)`, when followed, then both resolve to real files.
- Given `LICENSE`, then it is the standard MIT text with exactly one copyright line `Copyright (c) 2026 Brad Sprigg`.
- Given `CHANGELOG.md` `0.1.0`, then it records both the public release and the `./data/` → central-OS-dir migration including the `PLANESWALKER_DATA_DIR` workaround.
- Given `NOTICE`, then it credits Scryfall + Wizards of the Coast and includes the Fan Content Policy disclaimer.
- Given this is docs-only, when `git diff --stat` is inspected, then **no** file under `src/`, `tests/`, or `pyproject.toml` is modified.

## Spec Change Log

## Design Notes

CHANGELOG migration wording (the one non-obvious content piece) should convey: existing users who ran an older build had `cards.db` + the fastembed cache under the project's `./data/`; as of 0.1.0 the default is the OS data dir (`%LOCALAPPDATA%\artificial-planeswalker\` / `~/Library/Application Support/...` / `~/.local/share/...`). To keep the old location, set `PLANESWALKER_DATA_DIR=./data` (or move the existing `data/` contents to the new dir). New users are unaffected — `setup.py` builds into the central dir automatically.

## Verification

**Commands:**
- `git add -A && git status --short` -- expected: 5 new `A` entries (the docs) + this spec; nothing under `src/` or `tests/`.
- `git diff --cached --stat -- src tests pyproject.toml` -- expected: empty (proves docs-only).

**Manual checks:**
- Open `README.md` and confirm the `LICENSE` and `CONTRIBUTING.md` links now resolve.
- Skim `NOTICE` and `CHANGELOG.md` against the README disclaimer and the central-data-dir spec for consistency.

## Suggested Review Order

**Licensing & attribution (the legal core)**

- Start here — the grant and the one copyright line that defines the whole release.
  [`LICENSE:3`](../../LICENSE#L3)

- Canonical attribution: Scryfall data + "bundles NO card data" (downloaded on first run).
  [`NOTICE:7`](../../NOTICE#L7)

- WotC Fan Content Policy disclaimer — mirrors the already-shipped README block.
  [`NOTICE:18`](../../NOTICE#L18)

**Public-release accuracy (the review-patched content)**

- 0.1.0 entry; verify the tool/skill inventory matches what actually ships.
  [`CHANGELOG.md:12`](../../CHANGELOG.md#L12)

- Patched: index is built separately (not by `setup.py`); recommend an **absolute** `PLANESWALKER_DATA_DIR`.
  [`CHANGELOG.md:30`](../../CHANGELOG.md#L30)

- Patched: `setup.py` imports the DB only; the semantic index build is a separate, optional step.
  [`CONTRIBUTING.md:15`](../../CONTRIBUTING.md#L15)

- Patched: most MCP tools are `async def`; only the two semantic tools are sync `def`.
  [`CONTRIBUTING.md:49`](../../CONTRIBUTING.md#L49)

**Contributor & security policy**

- Branch-off-`master` + Conventional Commits + PR flow matches the project's real workflow.
  [`CONTRIBUTING.md:74`](../../CONTRIBUTING.md#L74)

- Private reporting channel (outlook + GitHub advisories) and the limited attack surface.
  [`SECURITY.md:12`](../../SECURITY.md#L12)

- `report_bug` stores untrusted user input — the one thing a security reviewer must know.
  [`SECURITY.md:33`](../../SECURITY.md#L33)

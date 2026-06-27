# Public Release Strategy — Artificial Planeswalker

**Date:** 2026-06-27 · **Author:** Brad Sprigg · **Goal:** take the repo from private dev workspace to a clean, public, easily-onboarded MCP server.

## Decisions locked (this session)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Legacy PydanticAI + Chainlit stack | **Delete entirely** (history preserved in git) |
| 2 | License | **MIT** + explicit note that card data is Scryfall / Wizards of the Coast |
| 3 | BMAD framework + 44 `bmad-*` dev skills (NOT the artifacts) | **Untrack (`git rm --cached` + gitignore, keep on disk) the `_bmad/` framework + `bmad-*` dev skills; KEEP `_bmad-output/` tracked** (planning + implementation artifacts = public design record). Keep only the 4 MTG product skills tracked. *(amended 2026-06-28 — keep `_bmad-output/`; gitignore the rest rather than delete, so the workflow still runs locally)* |
| 4 | Central card DB + embedding index | **Build on first run** into a shared OS data dir (no hosting) |

## Pre-flight safety check — PASSED

- `.env` **was never committed** to git history (verified `git log --all -- .env` → empty). The on-disk `.env` holds real keys but is gitignored and untracked — leave it that way.
- No `*.pem`, `id_rsa`, `secret`, or `credential` files in history.
- **Still do before flipping public:** one belt-and-braces secret scan over full history —
  `uvx gitleaks detect --source . --log-opts="--all"` (or `trufflehog git file://. --only-verified`). Cheap insurance.

---

## 1. File disposition

### 1a. DELETE — superseded / private / process noise

```bash
# Loose root docs (superseded vision, collaborator notes, internal reports)
git rm PROJECTIDEA.md SATHIAS.md SPIDER_MAN_INVESTIGATION.md TODO-LIST.md TOOL_PERFORMANCE_REPORT.md

# Legacy PydanticAI agent + Chainlit UI (decision #1)
git rm -r legacy/ public/
rm -rf .chainlit/                       # untracked on disk; delete locally

# BMAD framework + dev skills (decision #3). UNTRACK but KEEP ON DISK (--cached) so the workflow
# still runs locally; the .gitignore entries in §2 remove them from the public repo. KEEP
# _bmad-output/ tracked — the planning + implementation artifacts are the public design record.
git rm --cached -r _bmad/
git rm --cached -r .claude/skills/bmad-*   # 44 dev-tooling skills; keeps the 4 product skills tracked

# Manual scratch scripts (NOT the test suite in tests/)
git rm scripts/test_agent.py scripts/test_api_connection.py \
       scripts/test_database_setup.py scripts/test_mini_import.py scripts/test_queries.py

# Examples (decision: delete the whole folder)
git rm -r examples/

# Internal / legacy docs (curate docs/ — see 1c)
git rm docs/CONTEXT_DESIGN.md docs/SESSION_DEBUGGING_GUIDE.md docs/actions.md \
       docs/conversation-history-requirements.md docs/LOGFIRE.md \
       docs/project-scan-report.json docs/test-failure-analysis.md docs/project-index.md
```

> `PROJECTIDEA.md` is already in `.gitignore` **but still tracked** — `.gitignore` does not untrack. The `git rm` above is what actually removes it.

### 1b. KEEP — the product

- `src/` (data · logic · search · mcp_server) — the whole server
- `tests/` (unit + integration) — real suite, mirrors `src/`
- `.claude/skills/{magic-deckbuilding, synergy-discovery, mana-curve-analysis, format-legality}` — the 4 product skills that ride along with the tools
- `scripts/` keepers: `build_card_embeddings.py`, `import_scryfall_data.py`, `manage_bug_reports.py`, `migrate_*.py`, `validate_data_layer.py`, `view_deck.py`, `verify_image_data.py`
- `setup.py`, `pyproject.toml`, `uv.lock`, `.mcp.json`, `.pre-commit-config.yaml`, `.env.example`

### 1c. CURATE — `docs/` after pruning

Keep and lightly retitle:
- `docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md` → move to `docs/architecture.md` (this is the design of record)
- `docs/BUG_REPORT_MANAGEMENT.md` (the `report_bug` tool ships) and `docs/performance.md`

Result: `docs/` becomes a small, public-appropriate set (architecture, bug-report ops, performance) instead of 11 mixed internal files.

---

## 2. `.gitignore` changes

Remove these now-obsolete lines:
- `PROJECTIDEA.md` (file deleted)
- `.github/` — **un-ignore it**; a public repo wants CI, issue templates, and FUNDING tracked

Add:
```gitignore
# Dev process tooling — untracked here (via `git rm --cached` in §1a) but KEPT ON DISK locally so
# the workflow still runs. NOTE: _bmad-output/ is intentionally NOT ignored — its planning +
# implementation artifacts are kept and tracked in the public repo.
/_bmad/
.claude/skills/bmad-*/
.claude/settings.local.json   # (already present — keep)

# Central data dir, if a dev points it back into the tree
/data/                        # (already present — keep)
```
Keep the existing `*.db`, `.venv/`, `.env`, cache, and `temp/` ignores as-is.

---

## 3. Central SQLite storage (decision #4)

**Problem today:** the DB path is hard-coded to a project-relative `./data/cards.db` in **three** places, so every clone re-imports ~60k cards and rebuilds the index into its own tree. Touch points:

- `src/data/database.py:27` — `DATABASE_URL` default
- `src/search/connection.py:13` — `_DEFAULT_DB_PATH`
- `src/search/embedder.py:19` — `_DEFAULT_CACHE_DIR`

**Solution:** one shared, OS-correct data directory resolved by a new leaf module, reused by all three. Add `platformdirs` (tiny, standard) to dependencies.

`src/paths.py` (new — no internal imports, so it respects the `data → logic → mcp_server` layering):

```python
"""Central, OS-appropriate data paths shared by the DB engine, search layer, and embedder."""
from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir

_APP = "artificial-planeswalker"


def data_dir() -> Path:
    """Shared data directory. Override with PLANESWALKER_DATA_DIR. Created if missing.

    Windows: %LOCALAPPDATA%\\artificial-planeswalker
    macOS:   ~/Library/Application Support/artificial-planeswalker
    Linux:   ~/.local/share/artificial-planeswalker  (honours XDG_DATA_HOME)
    """
    override = (os.getenv("PLANESWALKER_DATA_DIR") or "").strip()
    base = Path(override).expanduser() if override else Path(user_data_dir(_APP, appauthor=False))
    base.mkdir(parents=True, exist_ok=True)
    return base


def database_path() -> Path:
    return data_dir() / "cards.db"


def fastembed_cache_dir() -> Path:
    d = data_dir() / "fastembed_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def database_url() -> str:
    """Async SQLAlchemy URL. Explicit CARDS_DATABASE_URL still wins (back-compat)."""
    explicit = (os.getenv("CARDS_DATABASE_URL") or "").strip()
    return explicit or f"sqlite+aiosqlite:///{database_path().as_posix()}"
```

**Resolution order (unchanged precedence, new default):**
1. Explicit env override (`CARDS_DATABASE_URL` / `FASTEMBED_CACHE_DIR` / `PLANESWALKER_DATA_DIR`) — keeps every current setup working.
2. **Central OS data dir** (new default) — shared across Claude Desktop, Claude Code, Cursor, VS Code, …
3. (Drop the bare `./data/cards.db` relative default.)

Then change the three touch points to import from `src.paths` (`database.py` → `database_url()`, `connection.py` → `database_path()`, `embedder.py` → `fastembed_cache_dir()`). Update the docstring examples that hard-code `./data/cards.db`.

**First-run bootstrap (build on first run):** an MCP server can't run a 5–10 min import during the protocol handshake. Reuse the existing graceful-status pattern (`index_unavailable`):

- On an empty/absent central DB, tools return `status="database_not_initialized"` with a one-line fix instead of an error.
- Provide a single bootstrap command — add a console script (`planeswalker-setup`, see §6) that runs the existing `setup.py` flow against the central path. First run: `uvx --from . planeswalker-setup` (or `uv run python -m setup`). It imports Scryfall + builds the index into the central dir once; every client thereafter is instant.
- `setup.py`'s "skip if already populated" check makes this idempotent and safe to re-run.

**Migration for existing users:** document one line in the README/CHANGELOG — either `move ./data/* → <central dir>`, or keep the old location by exporting `PLANESWALKER_DATA_DIR=$PWD/data`.

---

## 4. MCPB bundle for Claude Desktop

Claude Desktop installs local servers from a **`.mcpb`** bundle (the format formerly called `.dxt`): a zip of the server + a `manifest.json`. Manifest **v0.4** adds a **`uv` runtime type** that runs the server straight from `pyproject.toml` with no vendored `venv` — a ~100 KB bundle instead of 5–10 MB, and a perfect fit since this project already standardises on `uv`.

`manifest.json` (project root):

```json
{
  "manifest_version": "0.4",
  "name": "artificial-planeswalker",
  "display_name": "Artificial Planeswalker",
  "version": "0.1.0",
  "description": "MTG deck-building assistant: card lookup, deck validation, mana-curve & synergy analysis, and local semantic card search — over a local Scryfall database.",
  "author": { "name": "Brad Sprigg" },
  "license": "MIT",
  "keywords": ["mtg", "magic-the-gathering", "deckbuilding", "scryfall", "mcp"],
  "server": {
    "type": "uv",
    "entry_point": "src/mcp_server/__main__.py",
    "mcp_config": {
      "command": "uv",
      "args": ["run", "--directory", "${__dirname}", "python", "-m", "src.mcp_server"],
      "env": {
        "PLANESWALKER_DATA_DIR": "${user_config.data_dir}",
        "MCP_TRANSPORT": "stdio"
      }
    }
  },
  "user_config": {
    "data_dir": {
      "type": "directory",
      "title": "Card data directory (optional)",
      "description": "Where the ~250 MB card DB + embedding index live. Leave blank to use the shared OS location.",
      "required": false
    }
  },
  "compatibility": {
    "claude_desktop": ">=0.10.0",
    "platforms": ["darwin", "win32", "linux"],
    "runtimes": { "python": ">=3.12" }
  }
}
```

**Build & ship:**
```bash
npx @anthropic-ai/mcpb init     # scaffolds/validates a manifest interactively
npx @anthropic-ai/mcpb pack     # → artificial-planeswalker.mcpb
```
Attach the `.mcpb` to the GitHub Release; users double-click to install in Claude Desktop.

**Caveats to document:**
- The `uv` runtime requires `uv` on the user's PATH. If you want zero-prereq install, switch to `"type": "python"` with a bundled `server/lib` (larger bundle) — but given the audience, requiring `uv` is reasonable and matches the repo's own workflow.
- The 250 MB data set is **not** in the bundle. First launch reports `database_not_initialized`; the user runs the one-time bootstrap (§3). Optionally add a tiny `tools[]` list to the manifest so the capabilities show in the install dialog.

---

## 5. Other platforms it already supports

The server speaks standard MCP over **stdio** (default) and **streamable-http** (`MCP_TRANSPORT=streamable-http`). Any MCP client works — only the config wiring differs:

| Client | How to add it | Notes |
|--------|---------------|-------|
| **Claude Code** | `.mcp.json` (already present) | Zero-config in this directory |
| **Claude Desktop** | `.mcpb` bundle (§4) | One-click install |
| **Cursor** | `.cursor/mcp.json` or Settings → MCP | Same command/args as `.mcp.json` |
| **VS Code (Copilot agent mode)** | `.vscode/mcp.json` | Native MCP support |
| **Windsurf** | Cascade MCP settings | stdio command |
| **Cline / Roo** | MCP servers panel | stdio command |
| **Zed** | `context_servers` in settings | stdio command |
| **Goose, Continue, LibreChat, Witsy, …** | per-client MCP config | standard stdio/HTTP |
| **Remote / multi-user / web** | `MCP_TRANSPORT=streamable-http` | host once, many clients connect; pairs with the central DB |

**Recommendation:** ship a copy-paste config block per client in the README (stdio command is identical everywhere). PyPI publish (which would enable `uvx artificial-planeswalker` without cloning) is **deferred** — not at this stage.

---

## 6. Other recommendations

**Licensing & attribution (decision #2)**
- Add `LICENSE` (MIT, `Copyright (c) 2026 Brad Sprigg`).
- Add an **attribution / disclaimer** block to the README and a short `NOTICE`:
  - Card data © Wizards of the Coast, sourced from **Scryfall** bulk data under [Scryfall's terms](https://scryfall.com/docs/api); this project bundles **no** card data — users download it themselves.
  - **Wizards of the Coast Fan Content Policy:** *"Artificial Planeswalker is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast."* (important for any public MTG tool).

**`pyproject.toml` fixes**
- Description still says *"built with PydanticAI"* — rewrite to the MCP-server reality.
- `authors` email is `brad@example.com` — set a real/contact address.
- Remove the `[dependency-groups] legacy` block.
- Trim orphaned runtime deps (verified 0 imports in shipping `src/`): **`anthropic`, `openai`, `asyncpg`**. Move **`logfire`** to an optional `observability` group (1 optional import in `database.py`). Verify and likely drop **`tenacity`** and **`python-dotenv`** (pydantic-settings handles env). Add **`platformdirs`**.
- Add console entry points:
  ```toml
  [project.scripts]
  artificial-planeswalker = "src.mcp_server.__main__:main"
  planeswalker-setup = "setup:main"   # wrap setup.main() for sync entry
  ```
  (lets `uvx artificial-planeswalker` / `uvx --from . planeswalker-setup` work, and gives MCPB/other clients a stable launch command).

**`.env.example`** — delete the entire `LEGACY ONLY` section; add a commented `PLANESWALKER_DATA_DIR` override note. Without legacy, the file shrinks to ~3 settings.

**Repo health files**
- `.github/workflows/ci.yml` — `uv sync` → `ruff check` → `ruff format --check` → `mypy src/` → `pytest -m "not integration"` on push/PR (matrix on 3.12/3.13).
- `SECURITY.md` — note the server needs no secrets and that `report_bug` stores untrusted user input.
- `CONTRIBUTING.md` — the dev loop (uv, pre-commit, conventional commits) distilled from `project-context.md`.
- `CHANGELOG.md` — start at `0.1.0`; record the central-DB path change as a migration note.
- Issue/PR templates + a short repo description & topics on GitHub.

**Release mechanics**
- Tag `v0.1.0`, cut a **GitHub Release**, and attach the `.mcpb` bundle there (the canonical distribution channel for Claude Desktop install).
- **PyPI publish: deferred** (not at this stage). Revisit later if zero-clone `uvx` install becomes worth it.

---

## 7. Suggested execution order

1. **Safety:** run the secret scan (§ pre-flight). 
2. **Prune:** run §1a deletions + §1c curation + §2 `.gitignore` edits. Commit: `chore: remove legacy stack and dev tooling for public release`.
3. **Centralize DB:** add `platformdirs`, `src/paths.py`, rewire the 3 touch points + first-run status. Test a fresh-path bootstrap. Commit: `feat: store card DB + index in a central OS data dir`.
4. **Trim deps & metadata:** §6 `pyproject.toml` / `.env.example` fixes. Commit: `chore: trim orphaned deps, fix package metadata`.
5. **Docs:** rewrite `README.md` (done — see below), add `LICENSE`, `NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`.
6. **CI:** add `.github/workflows/ci.yml`; confirm green.
7. **Package:** add `manifest.json`, `mcpb pack`, smoke-test install in Claude Desktop.
8. **Release:** tag `v0.1.0`, cut a GitHub Release with the `.mcpb` attached, flip repo public.

## 8. Resolved follow-ups

- **No prebuilt DB — ever.** Build-on-first-run only. Shipping a prebuilt `cards.db` would mean redistributing Scryfall/WotC card data ourselves (license risk) and the asset would go stale against new sets. Keeping the data download user-side sidesteps both. (This is also why the `.mcpb` carries no data — §4.)
- **Delete `examples/`** entirely (done in §1a).
- **PyPI publish: deferred** — not at this stage.
- **Require `uv`** for the `.mcpb` (manifest `type: "uv"`), and **distribute the `.mcpb` via GitHub Releases**.

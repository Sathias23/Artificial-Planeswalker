# Packaging as a Claude Code Plugin

> **Why this exists:** the `.mcpb` bundle ships only the MCP *tools* to Claude Desktop.
> It cannot carry Claude **Skills** — that is not part of the MCPB manifest spec. A
> **Claude Code plugin** is the supported vehicle that bundles the MCP server *and* its
> four companion MTG skills as a single installable unit, so a user gets both the raw
> tools and the expert coaching layer in one install.

This document sketches that plugin. It is a design note, not a build script.

---

## What goes in the plugin

| Piece | Source today | Role in the plugin |
|-------|--------------|--------------------|
| MCP server | `src/` + `pyproject.toml` + `uv.lock` | Exposes the 14 tools (`lookup_card_by_name`, `analyze_mana_curve`, …) |
| `magic-deckbuilding` skill | `.claude/skills/magic-deckbuilding/SKILL.md` | Orchestrator: full "improve my deck" loop |
| `mana-curve-analysis` skill | `.claude/skills/mana-curve-analysis/SKILL.md` | Deep dive: curve / land count |
| `synergy-discovery` skill | `.claude/skills/synergy-discovery/SKILL.md` | Deep dive: interactions / combos |
| `format-legality` skill | `.claude/skills/format-legality/SKILL.md` | Deep dive: legality / banlist / sideboard |

The `bmad-*` skills are **dev tooling for this repo** and should *not* ship in the
end-user plugin — only the four MTG domain skills above.

---

## Directory layout

```
artificial-planeswalker-plugin/
├── .claude-plugin/
│   └── plugin.json              # plugin manifest (required, this exact path)
├── .mcp.json                    # MCP server definition (uses ${CLAUDE_PLUGIN_ROOT})
├── skills/                      # auto-discovered; one folder per skill
│   ├── magic-deckbuilding/
│   │   └── SKILL.md
│   ├── mana-curve-analysis/
│   │   └── SKILL.md
│   ├── synergy-discovery/
│   │   └── SKILL.md
│   └── format-legality/
│       └── SKILL.md
└── server/                      # the bundled Python MCP server
    ├── pyproject.toml
    ├── uv.lock
    └── src/                     # copied verbatim from this repo's src/
        ├── mcp_server/
        ├── data/
        ├── logic/
        ├── search/
        ├── viewer/              # NB: must be included — view_deck imports it
        └── paths.py
```

`commands/`, `agents/`, and `hooks/` directories are also supported by the plugin
format but aren't needed here.

---

## `.claude-plugin/plugin.json`

```json
{
  "name": "artificial-planeswalker",
  "description": "MTG deckbuilding assistant: card search, deck management, mana-curve, synergy, and format-legality tools plus an expert deckbuilding coach.",
  "version": "0.1.0",
  "author": {
    "name": "Sathias",
    "email": "sathias@slopstudio.net",
    "url": "https://github.com/Sathias23"
  },
  "homepage": "https://github.com/Sathias23/Artificial-Planeswalker",
  "repository": "https://github.com/Sathias23/Artificial-Planeswalker",
  "license": "MIT",
  "keywords": ["mtg", "magic-the-gathering", "deckbuilding", "scryfall", "mcp"]
}
```

Skills under `skills/` are discovered automatically from this manifest's location —
they do **not** need to be listed in `plugin.json`.

---

## `.mcp.json` (plugin root)

The plugin's MCP server config mirrors the repo's existing `.mcp.json`, but anchors
the working directory to the installed plugin via `${CLAUDE_PLUGIN_ROOT}` so it runs
no matter where Claude Code installs it:

```json
{
  "mcpServers": {
    "artificial-planeswalker": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "${CLAUDE_PLUGIN_ROOT}/server",
        "python", "-m", "src.mcp_server"
      ],
      "env": {
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

The skills call the server's tools by name, so the tool names must match exactly what
`src/mcp_server` registers (they do today).

---

## Open items before this is shippable

These are the same constraints the `.mcpb` already wrestles with — they don't go away
in plugin form:

1. **Python + uv must exist on the user's machine.** Unlike a self-contained binary,
   this server shells out to `uv`. The plugin should document that prerequisite (the
   MCPB declares `runtimes.python >=3.12`; the plugin has no equivalent manifest field,
   so it's a README note).
2. **The ~250 MB Scryfall card DB is not bundled** (correctly — `.mcpbignore` excludes
   `/data/`). The one-time bootstrap (`scripts/import_scryfall_data.py` →
   `scripts/build_card_embeddings.py`, run by `setup.py`) still has to happen on first
   use. Decide whether the plugin ships those two bootstrap scripts and a setup note, or
   whether a tool triggers the import on demand (the server already exposes
   `initialize_database` / `build_search_index`).
3. **`src/viewer/` must be copied in** — `src/mcp_server/tools/view_deck.py` imports it
   at module load. This is the exact bug that broke the first `.mcpb` build
   (commit `f567062`); the plugin's `server/` copy must not repeat it.
4. **Source duplication — solved by `scripts/build_plugin.py`.** The repo keeps a single
   `src/` and assembles the plugin's `server/` at build time rather than maintaining a
   second copy by hand. See "Building it" below.

---

## Building it

`scripts/build_plugin.py` assembles the whole `dist/plugin/` tree from this repo's single
source of truth, so there's no hand-maintained second copy of `src/` or the skills:

```bash
uv run python -m scripts.build_plugin            # build into dist/plugin/
uv run python -m scripts.build_plugin --out X    # build into X/ instead
```

What it does, deterministically and idempotently (wipes and rebuilds `dist/plugin/`):

1. **Copies the server** — `src/` (caches stripped) + `pyproject.toml` + `uv.lock` into
   `dist/plugin/server/`. It hard-fails if `src/viewer/` didn't make it across, guarding
   against repeating the `f567062` startup bug.
2. **Copies the four MTG skills** — `magic-deckbuilding`, `mana-curve-analysis`,
   `synergy-discovery`, `format-legality` — into `dist/plugin/skills/`. The `bmad-*`
   skills are deliberately left out (they're repo dev-tooling).
3. **Generates the manifests** — `.claude-plugin/plugin.json` is derived from
   `manifest.json` (one metadata source shared with the `.mcpb`, so they never drift),
   and `.mcp.json` is written with the `${CLAUDE_PLUGIN_ROOT}/server` anchor shown above.

`dist/` is already gitignored, so the assembled tree is a build artifact, not committed
source. The script does **not** solve open items 1 and 2 (the uv/Python prerequisite and
the one-time data bootstrap) — those remain runtime concerns documented for the end user.

## How a user would install it

```bash
# from a marketplace, or a local path during development:
/plugin install artificial-planeswalker@<marketplace>
# or point Claude Code at a local checkout for testing:
/plugin marketplace add ./artificial-planeswalker-plugin
```

After install, the user gets all 14 MCP tools **and** the four skills
(`magic-deckbuilding` and friends) auto-loaded — the coaching layer the bare `.mcpb`
can't provide.
```

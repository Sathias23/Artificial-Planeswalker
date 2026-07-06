# Packaging as a Claude Code Plugin

> **Status (2026-07-06):** implemented. `scripts/build_plugin.py` assembles the committed
> `plugin/` tree described here, and `.claude-plugin/marketplace.json` serves it as the
> repo's built-in marketplace. This document records the design rationale and layout.

> **Why a plugin (and not an `.mcpb` bundle):** an MCPB bundle ships only the MCP *tools*
> to Claude Desktop — carrying Claude **Skills** is not part of the MCPB manifest spec. A
> **Claude Code plugin** bundles the MCP server *and* its four companion MTG skills as a
> single installable unit, so a user gets both the raw tools and the expert coaching layer
> in one install. The project originally shipped both; the `.mcpb` was retired in favour of
> the plugin as the sole packaged distribution (Claude Desktop users connect via a manual
> `claude_desktop_config.json` entry instead — see the root README).

---

## What goes in the plugin

| Piece | Source | Role in the plugin |
|-------|--------|--------------------|
| MCP server | `src/` + `pyproject.toml` + `uv.lock` | Exposes the 16 tools (`lookup_card_by_name`, `analyze_mana_curve`, …) |
| `magic-deckbuilding` skill | `.claude/skills/magic-deckbuilding/SKILL.md` | Orchestrator: full "improve my deck" loop |
| `mana-curve-analysis` skill | `.claude/skills/mana-curve-analysis/SKILL.md` | Deep dive: curve / land count |
| `synergy-discovery` skill | `.claude/skills/synergy-discovery/SKILL.md` | Deep dive: interactions / combos |
| `format-legality` skill | `.claude/skills/format-legality/SKILL.md` | Deep dive: legality / banlist / sideboard |

The `bmad-*` skills are **dev tooling for this repo** and do *not* ship in the
end-user plugin — only the four MTG domain skills above.

---

## Directory layout (the committed `plugin/` tree)

```
plugin/
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
    ├── README.md                # required: pyproject's [project].readme
    ├── LICENSE                  # the MIT grant travels with the redistributed code
    ├── NOTICE                   # WotC Fan Content / Scryfall attribution
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

Skills under `skills/` are discovered automatically from the manifest's location —
they do **not** need to be listed in `plugin.json`.

---

## `.mcp.json` (plugin root)

The plugin's MCP server config mirrors the repo's `.mcp.json`, but anchors the working
directory to the installed plugin via `${CLAUDE_PLUGIN_ROOT}` so it runs no matter where
Claude Code installs it:

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
`src/mcp_server` registers (guarded by `tests/integration/test_build_plugin.py`).

---

## Runtime constraints that packaging can't solve

1. **Python + uv must exist on the user's machine.** Unlike a self-contained binary,
   this server shells out to `uv`. The plugin has no manifest field to declare that,
   so it's a README note.
2. **The ~250 MB Scryfall card DB is not bundled** (deliberately — Scryfall/WotC license).
   First-run bootstrap happens in-client via the `initialize_database` /
   `build_search_index` tools.
3. **`src/viewer/` must be copied in** — `src/mcp_server/tools/view_deck.py` imports it
   at module load. This is the exact bug that broke the first packaged build
   (commit `f567062`); the build hard-fails if the copy misses it.

---

## Building it

`scripts/build_plugin.py` assembles the whole `plugin/` tree from this repo's single
source of truth, so there's no hand-maintained second copy of `src/` or the skills:

```bash
uv run python -m scripts.build_plugin            # -> plugin/ (committed marketplace source)
uv run python -m scripts.build_plugin --out X    # build into X/ (scratch / testing)
```

Deterministically and idempotently, it:

1. **Copies the server** — `src/` (caches stripped) + `pyproject.toml` + `uv.lock` +
   `README.md` + `LICENSE` + `NOTICE` into `plugin/server/`.
2. **Copies the four MTG skills** into `plugin/skills/`.
3. **Generates the manifests** — `.claude-plugin/plugin.json` is derived from
   `pyproject.toml`'s `[project]` table (the single metadata source, so they never
   drift), and `.mcp.json` is written with the `${CLAUDE_PLUGIN_ROOT}/server` anchor
   shown above.

`plugin/` is **committed** — it is the marketplace `source` in
`.claude-plugin/marketplace.json`, so the two-command GitHub install clones a repo that
already contains the assembled plugin. Rebuild and commit `plugin/` whenever `src/`, the
skills, or the pyproject metadata change. CI rebuilds it and fails on drift.

## How a user installs it

```
/plugin marketplace add Sathias23/Artificial-Planeswalker
/plugin install artificial-planeswalker@artificial-planeswalker
```

After install, the user gets all 16 MCP tools **and** the four skills
(`magic-deckbuilding` and friends) auto-loaded — the coaching layer a bare MCP server
config can't provide.

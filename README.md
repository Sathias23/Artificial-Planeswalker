# Artificial Planeswalker

[![CI](https://github.com/Sathias23/Artificial-Planeswalker/actions/workflows/ci.yml/badge.svg)](https://github.com/Sathias23/Artificial-Planeswalker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

![Artificial Planeswalker](docs/hero-image.jpg)

An intelligent **Magic: The Gathering** deck-building assistant, exposed as a local
[MCP](https://modelcontextprotocol.io) server over a Scryfall card database.

Card lookup, multi-format deck validation, mana-curve and synergy analysis, **deck power
assessment**, and **local semantic card search** — all driven by your MCP client (Claude Code,
Claude Desktop, Cursor, …).
The server is **stateless** and makes **no LLM calls** of its own, so **no API key is required**:
your client supplies the model, the server supplies fast, accurate MTG data and analysis.

---

## What it does

| Capability | Tools |
|------------|-------|
| **Card lookup & search** | `lookup_card_by_name`, `search_cards` |
| **Semantic search** (local embeddings, no network) | `semantic_search_cards`, `find_similar_cards` |
| **Deck management** | `create_deck`, `list_decks`, `load_deck`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck`, `view_deck` *(deprecated — use the [companion app](#the-companion-app))*, `import_decklist` (bulk Arena import) |
| **Deck analysis** | `analyze_mana_curve`, `detect_synergies`, `validate_deck` |
| **Deck power assessment** *(experimental)* | `assess_deck_power`, `compare_deck_power` |
| **[Companion app](#the-companion-app)** | `companion_set_active_deck` — puts a saved deck on the companion's live browser view; `companion_show_suggestions` — puts a list of suggested cards on the same view, as cards rather than as text; `companion_show_swaps` — puts proposed card trades on the same view, out-card and in-card side by side with the reasoning; `companion_show_tier_list` — puts cards ranked into named S–D tiers on the same view, each tier a lettered chip with its cards beside it; `companion_show_groups` — puts titled card groups on the same view, each a heading with its rationale paragraph and its cards beneath it; `companion_status` — read-only: reports whether the companion is running, its URL, how many tabs are open, and the exact command that launches it. The others all report `app_not_running` when the companion isn't up, and the agent can then open it for you |
| **First-run setup** | `initialize_database`, `build_search_index` |

Five **skills** layer expert reasoning on top of the tools — `magic-deckbuilding` (the
orchestrator), `synergy-discovery`, `mana-curve-analysis`, and `format-legality` — so a client can
go from "improve my deck" to ranked, reasoned swaps; and `companion`, which opens the companion app
for you when you ask (or offers to, when a push finds it closed).

### Deck power assessment (experimental)

**`assess_deck_power`** scores a saved deck 0–100 for its format with a seven-dimension
vector (speed, consistency, resilience, interaction, mana efficiency, card advantage,
combo potential), a descriptive tier label, and — for Commander — a
[WotC Bracket](https://magic.wizards.com/en/news/announcements/commander-brackets-beta-update-april-22-2025)
floor plus cEDH candidacy. Every score comes with evidence: Game Changer names, detected
combos (in the deck, or one piece away), structural gaps, and a confidence block that names
any degraded inputs instead of silently guessing. **`compare_deck_power`** diffs two
assessments server-side — "did my edit make the deck stronger, and what changed?" Output is
deterministic (identical inputs serialize byte-identically), so results can be diffed and
tracked over time. Supported formats: Commander and Standard. Combo detection reads the
local [Commander Spellbook snapshot](#combo-snapshot-deck-power-assessment); without it,
assessment still runs at reduced confidence. *Experimental:* scoring calibration is still
being tuned — expect the numbers (not the shape of the output) to shift in upcoming
releases.

## Requirements

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** (package manager / runner)
- ~300 MB of disk for the card database + embedding index (built from a one-time ~500 MB
  download on first run), plus the companion's [image cache](docs/companion.md#image-cache)
  (~8.5 MB per 99-card deck viewed)
- **Nothing extra for the [companion app](#the-companion-app)** — its browser UI ships pre-built,
  so **Node is not required** at install or at runtime (only to change the UI)

## Quick start

```bash
git clone https://github.com/Sathias23/Artificial-Planeswalker.git
cd Artificial-Planeswalker
python3 setup.py        # installs deps + downloads the card database into a central location
```

`setup.py` is idempotent: it checks Python/uv, syncs dependencies, then downloads public
**Scryfall** bulk data (~500 MB covering every printing, deduplicated to ~35k cards with
cross-printing Arena/MTGO availability; a few minutes — no API key) into a shared OS location
(below), so every project and every MCP client reuses it. Run it once per machine.

To enable **semantic search** (`semantic_search_cards` / `find_similar_cards`), build the embedding
index once too — either ask your MCP client to run the **`build_search_index`** tool, or run
`uv run python scripts/build_card_embeddings.py`. (Until then those two tools report
`index_unavailable` with a build hint; the other tools work as soon as the card data is downloaded.)

Then point any MCP client at it — in this directory,
[`.mcp.json`](https://github.com/Sathias23/Artificial-Planeswalker/blob/master/.mcp.json) already does:

```bash
uv run python -m src.mcp_server          # stdio (default; how clients launch it)
MCP_TRANSPORT=streamable-http uv run python -m src.mcp_server   # serve over HTTP instead
```

## Connect your client

The launch command is the same everywhere — only the config file differs.

<details>
<summary><b>Claude Code</b> (plugin — tools + skills, two commands)</summary>

Install the plugin from this repo's built-in marketplace to get all 25 tools **and** the five
skills in any project — no clone required:

```
/plugin marketplace add Sathias23/Artificial-Planeswalker
/plugin install artificial-planeswalker@artificial-planeswalker
```

On first use, ask the assistant to run **`initialize_database`** (one-time ~500 MB card download,
a few minutes), then **`build_search_index`** for semantic search.

The plugin ships [the companion app](#the-companion-app) too — its browser UI is pre-built and
travels with the install, so there is nothing extra to fetch and no Node toolchain involved. Claude
Code starts the MCP server for you; the companion is a separate process you start yourself,
anchored at the installed plugin root — the exact recipe is
[Running from a plugin install](docs/companion.md#running-from-a-plugin-install) in the
companion guide.

*Developing in this repo instead?*
[`.mcp.json`](https://github.com/Sathias23/Artificial-Planeswalker/blob/master/.mcp.json) is
auto-detected when you open the directory — that gives you the tools (the skills come from the
plugin install above).
</details>

<details>
<summary><b>OpenAI Codex</b> (plugin or manual MCP config)</summary>

**Plugin route** — verified on the Codex app for Windows. Requires Codex ≥ 0.117.0
(first-class plugin support); the desktop app has no add-marketplace UI, so run the command
below with the Codex CLI — on native Windows they share the same `%USERPROFILE%\.codex`, and
the plugin appears in the app after a restart. Add this repo as a marketplace, then install
from the `/plugins` browser:

```
codex plugin marketplace add Sathias23/Artificial-Planeswalker
```

Open the `/plugins` browser inside Codex and install **artificial-planeswalker** — that gives
you the 25 tools *and* the five skills. If Codex also auto-surfaces this repo's
*Claude Code* marketplace, skip it — that variant's config only works inside Claude Code
(see [openai/codex#19372](https://github.com/openai/codex/issues/19372)).

The plugin route also carries [the companion app](#the-companion-app) — the same pre-built UI,
no Node involved. Codex keeps its own version-keyed plugin cache under `~/.codex`
(`%USERPROFILE%\.codex` on Windows); launch anchored at that root exactly as
[Running from a plugin install](docs/companion.md#running-from-a-plugin-install) shows for
Claude Code. The manual route has no plugin root: run the companion from your clone with the
plain `uv run artificial-planeswalker companion`.

**Manual route** — clone the repo, then register the server with one command:

```bash
codex mcp add artificial-planeswalker --env MCP_TRANSPORT=stdio -- uv run --directory /absolute/path/to/Artificial-Planeswalker python -m src.mcp_server
```

or add it to `~/.codex/config.toml` yourself:

```toml
[mcp_servers.artificial-planeswalker]
command = "uv"
args = ["run", "--directory", "/absolute/path/to/Artificial-Planeswalker", "python", "-m", "src.mcp_server"]
env = { MCP_TRANSPORT = "stdio" }
```

On first use, ask the assistant to run **`initialize_database`** (one-time card download,
~2–3 min), then **`build_search_index`** for semantic search. The manual route loads the 19
tools; the skills come with the plugin route.

> **First launch is slow:** the server's first start builds its Python environment with `uv`
> (a few minutes on a cold cache). If the tools don't appear in your first session, start a
> fresh session once the build has finished.
</details>

<details>
<summary><b>Claude Desktop</b></summary>

Clone the repo, then add the server to `claude_desktop_config.json`
(Settings → Developer → Edit Config; requires `uv` on your PATH):

```json
{
  "mcpServers": {
    "artificial-planeswalker": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Artificial-Planeswalker", "python", "-m", "src.mcp_server"]
    }
  }
}
```

No card data ships with the repo, so on first use ask the assistant to run the
**`initialize_database`** tool (a one-time ~500 MB card-data download, a few minutes) — and then
**`build_search_index`** if you want semantic search. Until then the card/deck tools reply with a
`database_not_initialized` hint instead of an error. When a new set releases, ask the assistant to
run `initialize_database` with `update=true` to pull in the new cards (then re-run
`build_search_index` to index them). Desktop loads the 25 tools; the five skills are a Claude Code
plugin feature.
</details>

<details>
<summary><b>Cursor / VS Code / Windsurf / Cline / Zed</b></summary>

Add an MCP server with:

```json
{
  "mcpServers": {
    "artificial-planeswalker": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Artificial-Planeswalker", "python", "-m", "src.mcp_server"]
    }
  }
}
```

Config locations: Cursor `.cursor/mcp.json` · VS Code `.vscode/mcp.json` · Windsurf Cascade MCP
settings · Cline MCP panel · Zed `context_servers`. Any other MCP client works the same way.
</details>

## The companion app

The companion is a small local web app that shows the deck your agent is working on — real card
images, laid out as cards instead of as a wall of text. Ask your agent to put a saved deck on it
(`companion_set_active_deck`), to show a list of suggested cards on the same view
(`companion_show_suggestions`), to show proposed card swaps as out/in pairs with the reasoning
(`companion_show_swaps`), to show cards ranked into named tiers (`companion_show_tier_list`),
or to show titled card groups with the reasoning behind each (`companion_show_groups`),
and the page updates while you watch.

**It is optional, and nothing depends on it.** Every agent workflow completes with the app closed:
the companion tools simply report `app_not_running`, and no other tool ever looks for it. The
companion adds a visual channel; it never replaces chat output.

### Open it

Say **"open the companion"** and the agent does the rest: the `companion` skill checks
`companion_status` (running? URL? tabs connected?) and, when nothing is running, launches it in a
background shell of its own. Or launch it yourself:

```bash
uv run artificial-planeswalker companion --open    # --open pops your default browser on the URL
```

From a **plugin install** there is no checkout to stand in, so anchor the launch at the installed
plugin root instead ([finding that root](docs/companion.md#running-from-a-plugin-install)):

```bash
PLUGIN_ROOT="$HOME/.claude/plugins/cache/<marketplace>/artificial-planeswalker/<version>"
uv run --directory "$PLUGIN_ROOT/server" artificial-planeswalker companion --open
```

It serves in the foreground until Ctrl-C and prints one launch line naming the real URL — port
**8765** preferred, with automatic fallback to a free port when it's taken. It binds
**loopback only** (`127.0.0.1`, plain HTTP, per-process token): a single-user local tool, never
on your network.

That is all most people need. The **[full companion guide](docs/companion.md)** covers the rest:

* [Launching, stopping, and the agent's launch flow](docs/companion.md#launch-it) — flags,
  stdout/stderr, stopping one the agent started
* [Choosing a port](docs/companion.md#choosing-a-port) — `--port` / `COMPANION_PORT`, and the
  ephemeral fallback
* [One companion at a time](docs/companion.md#one-companion-at-a-time) — why a second launch
  never fails and never forks a second server
* [How the tools find it](docs/companion.md#how-it-is-found-and-what-an-unclean-exit-leaves) —
  the discovery file, crashes, and the `app_not_running`-while-plainly-running gotcha
* [What it exposes](docs/companion.md#what-it-exposes) — the security envelope in full
* [First run on a fresh install](docs/companion.md#first-run-on-a-fresh-install) — the no-database
  state, and recovering from a failed import
* [Running from a plugin install](docs/companion.md#running-from-a-plugin-install) — anchoring
  the launch at the plugin root
* [Image cache](docs/companion.md#image-cache) — where card images land on disk, how big it gets,
  how to inspect and clear it

## Where the data lives

The card database and embedding index are stored once in a **central, OS-appropriate location** so
every clone and every client shares them:

| OS | Default location |
|----|------------------|
| Windows | `%LOCALAPPDATA%\artificial-planeswalker\` |
| macOS | `~/Library/Application Support/artificial-planeswalker/` |
| Linux | `~/.local/share/artificial-planeswalker/` (honours `XDG_DATA_HOME`) |

Override with `PLANESWALKER_DATA_DIR=/your/path`, or point the engine at any SQLite file with
`CARDS_DATABASE_URL`. See
[`.env.example`](https://github.com/Sathias23/Artificial-Planeswalker/blob/master/.env.example).

### Semantic search index

`semantic_search_cards` and `find_similar_cards` query a [`sqlite-vec`](https://github.com/asg017/sqlite-vec)
vector table (`card_vec`) in the **same** SQLite file, embedded locally with
[`fastembed`](https://github.com/qdrant/fastembed) (`bge-small-en-v1.5` — no API key, no network).
Building it is a separate one-time step (see [Quick start](#quick-start)) — ask your client to run
the **`build_search_index`** tool, or run it manually:

```bash
uv run python scripts/build_card_embeddings.py    # idempotent + incremental
```

Until built, both semantic tools return a graceful `status="index_unavailable"` (never an error).
The DB runs in WAL mode — **checkpoint before copying it** (`PRAGMA wal_checkpoint(TRUNCATE);`).

### Combo snapshot (deck power assessment)

Combo detection runs against a **local snapshot** of the
[Commander Spellbook](https://commanderspellbook.com) bulk combo export (~26 MB download,
~100k combo variants) stored in the same SQLite file — fully offline once imported, and
versioned with the export's own timestamp. Building it is a separate operator step:

```bash
uv run python scripts/import_spellbook_combos.py    # atomic replace, safe to re-run
```

Upstream regenerates the export roughly every 2 hours; refresh whenever you want fresher
combo data. Until imported, deck power assessment degrades gracefully
(`combo_data_unavailable`) instead of erroring. Combo data is provided by
[Commander Spellbook](https://commanderspellbook.com) via their public bulk export.

### Image cache (companion app)

The companion keeps every card image it fetches in `<data dir>/image_cache/` — decks you have
viewed repaint without touching the network. It only grows (no eviction; a measured ~8.5 MB per
99-card deck, ~95 MB for a ~1,000-printing library) and is **safe to delete at any time**. Layout,
inspect/clear commands, and what an uninstall leaves behind:
[the companion guide](docs/companion.md#image-cache).

## Development

```bash
uv run pytest                       # tests (add -m "not integration" to skip DB/network)
uv run ruff check . --fix           # lint
uv run ruff format .                # format
uv run mypy src/                    # strict type-check
uv run pre-commit install           # gate every commit
```

**Changing the companion's UI needs Node `>=20.19.0`** — the one thing here that needs Node.
The built SPA bundle is **committed** (that is what keeps installs Node-free), so rebuild and
commit it with every `ui/` change, then regenerate `plugin/` — CI fails on drift for both:

```bash
cd ui && npm ci && npm test && npm run build        # gate + bundle → src/companion/app/static/
uv run python -m scripts.build_plugin               # regenerate plugin/ from src/
```

The full gate (`lint`, `format:check`, `typecheck`) and the third generated artifact are in
[Generated artifacts](CONTRIBUTING.md#generated-artifacts) in `CONTRIBUTING.md`.

```
src/
├── data/        # SQLAlchemy models, Scryfall importers, repositories, schemas
├── logic/       # deck validation, mana curve, synergy detection, power assessment
├── search/      # sqlite-vec connection + fastembed embedder (semantic search)
├── companion/   # companion backend (FastAPI) + the committed SPA bundle it serves
├── viewer/      # the old one-shot HTML deck renderer (deprecated, frozen)
├── paths.py     # central data-dir resolution
└── mcp_server/  # FastMCP server + tool definitions (python -m src.mcp_server)
ui/              # companion SPA source (React + Vite) — Node, dev/CI only
plugin/          # generated Claude Code / Codex plugin tree — rebuild, never hand-edit
tests/           # unit + integration, mirroring src/
```

See [`docs/architecture.md`](https://github.com/Sathias23/Artificial-Planeswalker/blob/master/docs/architecture.md)
for the design of record and
[`CONTRIBUTING.md`](https://github.com/Sathias23/Artificial-Planeswalker/blob/master/CONTRIBUTING.md)
for the workflow.

## License & attribution

Released under the [MIT License](LICENSE).

Card data and card imagery are © Wizards of the Coast, courtesy of
[Scryfall](https://scryfall.com/docs/api) under Scryfall's terms — bulk data downloaded on first
run, and card images fetched by the companion app when it draws them. **This project bundles no
card data and no card images.** This project is not produced by, endorsed by, supported by, or
affiliated with Scryfall.

> Artificial Planeswalker is unofficial Fan Content permitted under the
> [Wizards of the Coast Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy).
> Not approved or endorsed by Wizards. Portions of the materials used are property of Wizards of
> the Coast. ©Wizards of the Coast LLC.

## Acknowledgments

- [Scryfall](https://scryfall.com/docs/api) — MTG card data and card imagery
- [Commander Spellbook](https://commanderspellbook.com) — combo data (public bulk export)
- [Model Context Protocol](https://modelcontextprotocol.io) & FastMCP — server framework
- [sqlite-vec](https://github.com/asg017/sqlite-vec) & [fastembed](https://github.com/qdrant/fastembed) — local semantic search

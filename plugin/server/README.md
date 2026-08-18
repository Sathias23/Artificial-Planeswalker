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
| **Deck management** | `create_deck`, `list_decks`, `load_deck`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck`, `view_deck` *(deprecated — use the companion app)*, `import_decklist` (bulk Arena import) |
| **Deck analysis** | `analyze_mana_curve`, `detect_synergies`, `validate_deck` |
| **Deck power assessment** *(experimental)* | `assess_deck_power`, `compare_deck_power` |
| **Companion app** *(in development)* | `companion_set_active_deck` — puts a saved deck on the companion's live browser view; `companion_show_suggestions` — puts a list of suggested cards on the same view, as cards rather than as text. Both report `app_not_running` when the companion isn't up |
| **First-run setup** | `initialize_database`, `build_search_index` |

Four companion **skills** layer expert reasoning on top of the tools —
`magic-deckbuilding` (the orchestrator), `synergy-discovery`, `mana-curve-analysis`, and
`format-legality` — so a client can go from "improve my deck" to ranked, reasoned swaps.

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
- ~300 MB of disk for the card database + embedding index (built from a one-time ~500 MB download on first run)

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

Install the plugin from this repo's built-in marketplace to get all 21 tools **and** the four
deckbuilding skills in any project — no clone required:

```
/plugin marketplace add Sathias23/Artificial-Planeswalker
/plugin install artificial-planeswalker@artificial-planeswalker
```

On first use, ask the assistant to run **`initialize_database`** (one-time ~500 MB card download,
a few minutes), then **`build_search_index`** for semantic search.

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
you the 21 tools *and* the four deckbuilding skills. If Codex also auto-surfaces this repo's
*Claude Code* marketplace, skip it — that variant's config only works inside Claude Code
(see [openai/codex#19372](https://github.com/openai/codex/issues/19372)).

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
`build_search_index` to index them). Desktop loads the 21 tools; the four skills are a Claude Code
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

The companion app stores every card image it fetches from Scryfall on disk, so a deck you have
already viewed repaints without touching the network. It is **one directory** inside the data
directory described above:

```
<data dir>/image_cache/
```

The per-OS default is the one in the table at the top of this section, and the location follows
`PLANESWALKER_DATA_DIR` — set that variable and the cache moves with everything else. Only the
companion app reads or writes it; the MCP server never touches it.

**Layout.** One file per card id + rendition + face:

```
image_cache/<first two characters of the card id>/<card id>/<size>_<face>.<ext>
```

for example `image_cache/81/813d0434-8e0f-4b0a-9c7e-1f2a3b4c5d6e/normal_0.jpg`. Card ids are
uuids, so the two-character shard splits the corpus evenly: all 256 shards are used, at roughly
150 cards each, instead of ~38,000 card directories side by side in one flat directory.

**Inspect it.** Both blocks resolve the path through the app's own code, so they are correct on
every OS and under a `PLANESWALKER_DATA_DIR` override — you never have to know where your data
directory is:

```bash
CACHE=$(uv run python -c "from src import paths; print(paths.data_dir() / 'image_cache')")
echo "$CACHE"                     # where it is
du -sh "$CACHE"                   # how big it is
find "$CACHE" -type f | wc -l     # how many images
```

```powershell
$Cache = uv run python -c "from src import paths; print(paths.data_dir() / 'image_cache')"
$Cache
Get-ChildItem -Recurse -File $Cache | Measure-Object -Property Length -Sum
```

**Clear it.**

```bash
CACHE=$(uv run python -c "from src import paths; print(paths.data_dir() / 'image_cache')")
rm -rf "$CACHE"
```

```powershell
$Cache = uv run python -c "from src import paths; print(paths.data_dir() / 'image_cache')"
Remove-Item -Recurse -Force $Cache
```

**Nothing is ever evicted.** There is no TTL, no size cap, no index and no cleanup pass — the cache
only grows, until you delete it. **Measured** on 2026-08-02 by fetching a real 99-card deck through
the app's own image route against the real Scryfall CDN: about **90 KB** per tile at the grid's
`normal` size, **8.5 MB** for a 99-tile deck, and about **95 MB** for this project's entire 40-deck,
1,061-distinct-card library. An earlier **arithmetic estimate** of *roughly 12 MB per 100-card deck*
(~124 KB per tile) circulated while the feature was being built and turned out to be a 38 %
overestimate — the measured figures are the ones to plan against, and both are quoted here so the
two numbers are not left to disagree in silence. If an eviction policy is ever added, it will be
sized against a measurement like this one rather than guessed.

**A data refresh does not invalidate it, deliberately.** An entry is keyed on card id + size + face
and **not** on the image URL, so re-importing card data that changes a card's `image_uris` keeps
serving the picture already on disk. That staleness is accepted behaviour rather than an oversight:
keying on the URL would turn every data refresh into a total cache miss for artwork that almost
never changes. The remedy is to delete the directory with the command above. Served images are also
stamped `immutable` for a year, so a browser tab that is already open may hold its own copy —
reload it after clearing.

**Safe to delete at any time**, running app or not: every entry is reconstructible by refetching it,
nothing indexes the directory, and no other feature reads it. The wholesale delete also removes any
`*.tmp` write debris that a hard kill or a power cut stranded mid-write — nothing sweeps for those,
and this is the intended remedy.

**What an uninstall leaves behind.** Deleting the checkout does not touch the data directory. Left
there:

* `image_cache/` — always, with everything it had cached.
* `companion.lock` — always, and **deliberately**. It is a zero-byte file the app never deletes,
  because on macOS and Linux the lock attaches to the file's inode: unlinking and recreating it
  would let two companions each believe they hold the single-instance lock. The app leaving it
  behind is correct, and deleting it out from under a running app is a correctness bug.
* `companion.json` — only if the app did not exit cleanly. A clean shutdown removes it; a crash or
  a kill leaves a stale one, which the next launch reads as "not running" rather than as an error.

The same directory also holds `cards.db` and `fastembed_cache/` (the semantic index's model files),
so deleting the data directory itself removes everything this project ever wrote.

**Two ways the cache switches itself off, both harmless.** If the cache directory cannot be created
at startup — an antivirus scanner briefly holding the data directory, say — the companion logs one
warning and runs with caching disabled for that process. And if five *consecutive* writes fail
afterwards, it says so once and stops writing for the rest of that process. In both cases every
image is still served and everything already cached is still read: you lose caching, never
pictures. There is no automatic retry, by design — **restarting the app** is the remedy.

## Development

```bash
uv run pytest                       # tests (add -m "not integration" to skip DB/network)
uv run ruff check . --fix           # lint
uv run ruff format .                # format
uv run mypy src/                    # strict type-check
uv run pre-commit install           # gate every commit
```

```
src/
├── data/        # SQLAlchemy models, Scryfall importers, repositories, schemas
├── logic/       # deck validation, mana curve, synergy detection, power assessment
├── search/      # sqlite-vec connection + fastembed embedder (semantic search)
├── paths.py     # central data-dir resolution
└── mcp_server/  # FastMCP server + tool definitions (python -m src.mcp_server)
tests/           # unit + integration, mirroring src/
```

See [`docs/architecture.md`](https://github.com/Sathias23/Artificial-Planeswalker/blob/master/docs/architecture.md)
for the design of record and
[`CONTRIBUTING.md`](https://github.com/Sathias23/Artificial-Planeswalker/blob/master/CONTRIBUTING.md)
for the workflow.

## License & attribution

Released under the [MIT License](LICENSE).

Card data is © Wizards of the Coast, sourced from [Scryfall](https://scryfall.com/docs/api) bulk
data under Scryfall's terms. **This project bundles no card data** — it is downloaded on first run.
This project is not produced by, endorsed by, supported by, or affiliated with Scryfall.

> Artificial Planeswalker is unofficial Fan Content permitted under the
> [Wizards of the Coast Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy).
> Not approved or endorsed by Wizards. Portions of the materials used are property of Wizards of
> the Coast. ©Wizards of the Coast LLC.

## Acknowledgments

- [Scryfall](https://scryfall.com/docs/api) — MTG card data
- [Commander Spellbook](https://commanderspellbook.com) — combo data (public bulk export)
- [Model Context Protocol](https://modelcontextprotocol.io) & FastMCP — server framework
- [sqlite-vec](https://github.com/asg017/sqlite-vec) & [fastembed](https://github.com/qdrant/fastembed) — local semantic search

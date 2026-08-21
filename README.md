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
| **[Companion app](#the-companion-app)** | `companion_set_active_deck` — puts a saved deck on the companion's live browser view; `companion_show_suggestions` — puts a list of suggested cards on the same view, as cards rather than as text; `companion_show_swaps` — puts proposed card trades on the same view, out-card and in-card side by side with the reasoning; `companion_show_tier_list` — puts cards ranked into named S–D tiers on the same view, each tier a lettered chip with its cards beside it; `companion_show_groups` — puts titled card groups on the same view, each a heading with its rationale paragraph and its cards beneath it. All report `app_not_running` when the companion isn't up |
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
- ~300 MB of disk for the card database + embedding index (built from a one-time ~500 MB
  download on first run), **plus** whatever the companion's
  [image cache](#image-cache-companion-app) grows to — a measured ~8.5 MB per 99-card deck you
  view and ~95 MB for a library of ~1,000 distinct printings, with no eviction
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

Install the plugin from this repo's built-in marketplace to get all 21 tools **and** the four
deckbuilding skills in any project — no clone required:

```
/plugin marketplace add Sathias23/Artificial-Planeswalker
/plugin install artificial-planeswalker@artificial-planeswalker
```

On first use, ask the assistant to run **`initialize_database`** (one-time ~500 MB card download,
a few minutes), then **`build_search_index`** for semantic search.

The plugin ships [the companion app](#the-companion-app) too — its browser UI is pre-built and
travels with the install, so there is nothing extra to fetch and no Node toolchain involved. Claude
Code starts the MCP server for you; the companion is a separate process you start yourself, anchored
at the installed plugin root. Find that root, then launch:

```bash
ls -d ~/.claude/plugins/cache/*/artificial-planeswalker/*/    # list the versioned install(s)
PLUGIN_ROOT="$HOME/.claude/plugins/cache/<marketplace>/artificial-planeswalker/<version>"
uv run --directory "$PLUGIN_ROOT/server" artificial-planeswalker companion
```

```powershell
# Windows (PowerShell) — same shape, wherever your client installed the plugin
Get-ChildItem -Directory -Recurse -Depth 3 "$HOME\.claude\plugins\cache" -Filter server
$PluginRoot = "<the directory listed above, without \server>"
uv run --directory "$PluginRoot/server" artificial-planeswalker companion
```

Claude Code installs into a **version-keyed** cache directory, so the path is specific to your
machine *and* to the plugin version — take it from your own install rather than pasting a literal
one, and expect it to change when you update the plugin. The first launch from a given root builds
a virtualenv and installs the server's dependencies inside it (tens of seconds, once), and a plugin
update to a new version repeats that in the new directory.

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

The plugin route also carries [the companion app](#the-companion-app) — it is the same tree, so
`server/` holds the same pre-built UI and no Node toolchain is involved. Codex keeps its own
version-keyed plugin cache under `~/.codex` (`%USERPROFILE%\.codex` on Windows), so find that
root first and launch anchored at it — the same shape as the Claude Code route above, and the
same caveat: the path is specific to your machine and to the plugin version, so read it off your
own install rather than pasting a literal one.

```bash
ls -d ~/.codex/plugins/cache/*/artificial-planeswalker/*/    # list the versioned install(s)
PLUGIN_ROOT="$HOME/.codex/plugins/cache/<marketplace>/artificial-planeswalker/<version>"
uv run --directory "$PLUGIN_ROOT/server" artificial-planeswalker companion
```

```powershell
# Windows (PowerShell) — where the Codex-app route verified above installs
Get-ChildItem -Directory -Recurse -Depth 3 "$HOME\.codex\plugins\cache" -Filter server
$PluginRoot = "<the directory listed above, without \server>"
uv run --directory "$PluginRoot/server" artificial-planeswalker companion
```

The manual route has no plugin root: run the companion from your clone with the plain
`uv run artificial-planeswalker companion`.

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

### Launch it

```bash
uv run artificial-planeswalker companion
```

It runs in the foreground until you interrupt it, and prints exactly one **launch line**:

```
[planeswalker] companion running at http://127.0.0.1:8765 — open this URL in your browser (Ctrl-C to stop)
```

That is the *only* launch line you will see: the app binds its own socket before handing it to
uvicorn, which suppresses uvicorn's own startup banner — so the URL on screen is always the one that
is actually bound. The address is printed as the literal `127.0.0.1` rather than `localhost` on
purpose: the socket is IPv4-only, and `localhost` resolves to `::1` first on Windows and on modern
Linux. Ctrl-C stops the app and exits `0`.

**Two streams, and it matters when something looks wrong.** The lines above — the launch line, the
fallback notice and both "already running" messages — go to **stdout**, because they are the point
of running the command. Everything the app logs goes to **stderr** at `INFO`, uvicorn's own records
included. A warning you have to go looking for is on stderr; the line you were told to open is on
stdout.

> **Node is never required** — not at install, not at runtime. The browser UI ships pre-built inside
> the Python package, and `fastapi` and `uvicorn` are ordinary base dependencies, so there is no
> extra, no dependency group and no build step between a fresh clone and a running app. The honest
> caveat: Node *is* required to **change** the UI. That is what the `ui/` tree in
> [Development](#development) is for, and it is a development and CI concern only.

**Installed via the plugin rather than a clone?** The command above assumes you are standing in a
checkout of this repo. The plugin carries the same app — every flag, message and behaviour on this
page applies to it unchanged — but the **invocation** is anchored at the installed plugin root
rather than at the working directory, so add `--directory` to each command below as well:

```bash
PLUGIN_ROOT="$HOME/.claude/plugins/cache/<marketplace>/artificial-planeswalker/<version>"
uv run --directory "$PLUGIN_ROOT/server" artificial-planeswalker companion
```

So `--port 9000` below becomes
`uv run --directory "$PLUGIN_ROOT/server" artificial-planeswalker companion --port 9000`, and the
`COMPANION_PORT` variants work the same way. See
[Connect your client](#connect-your-client) for how to find that root on your machine (it is
version-keyed, and the first launch from a new one installs the server's dependencies).

### Choosing a port

The companion prefers port **8765**. Two ways to ask for a different one — pick **one**, since each
block below is a whole launch on its own:

```bash
uv run artificial-planeswalker companion --port 9000      # or --port=9000
```

```bash
COMPANION_PORT=9000 uv run artificial-planeswalker companion          # macOS / Linux
```

```powershell
$env:COMPANION_PORT = 9000; uv run artificial-planeswalker companion  # Windows
```

So `--port` beats `COMPANION_PORT`, which beats the default. The rest of what the launcher accepts,
in one list:

* `--port N` and `--port=N` are both accepted. `-h` / `--help` prints the usage and exits `0`.
* `--port 0` is legal and means "give me any free port".
* A `COMPANION_PORT` that is not an integer, or an integer outside `0..65535`, is **ignored with a
  logged warning** on stderr and the default is used instead — a stale environment variable must
  never stop a launch. An out-of-range `--port` is treated the same way.
* A `--port` that is not an integer, a `--port` with no value, and `--port` given twice are all
  **usage errors**: you typed them in this invocation, so the launcher says what was wrong and
  exits `2` (the only non-zero status it ever returns).

**If the preferred port is taken, the launch still succeeds.** The app falls back to a
kernel-assigned ephemeral port on *any* bind failure — not only "address already in use", because
Windows refuses binds inside its reserved dynamic ranges with a different error entirely — and says
so first:

```
[planeswalker] port 8765 is unavailable — falling back to an ephemeral port
```

The usual launch line follows it, naming the port the kernel actually handed out — which is why no
example here prints one: an ephemeral port is whatever was free at the time. Read the port off that
line. It is always the real one.

### One companion at a time

Starting a second companion never starts a second server and never fails. The launcher has three
outcomes — it serves, or it prints one of the two messages below — and **every one of them exits
`0`**. Which of the two messages you get depends on how far along the other companion is.

If a companion is already up and answering, this launch tells you where it is:

```
[planeswalker] companion is already running at http://127.0.0.1:8765 — open that URL, or stop the other instance before starting a new one
```

If another launch is still inside its own startup window — it holds the single-instance lock but has
not published its port yet — you get the other message, which deliberately names **no** URL, because
none can be stated honestly yet:

```
[planeswalker] another companion is already starting up — wait for it to print its URL, or stop it before starting a new one
```

Either message means the companion is running, or is about to be. Nothing failed; the exit status is
`0` and there is no error to go looking for.

### How it is found, and what an unclean exit leaves

A running companion publishes one small JSON file — `companion.json`, in the data directory under
[Where the data lives](#where-the-data-lives) — naming the port it actually bound and a per-process
token. That file is the **sole** rendezvous: the MCP tools read it to learn both where to connect
and how to authenticate. There is no environment variable to set, no registry key and no port scan,
which is exactly why an ephemeral fallback costs you nothing.

> **If the tools say `app_not_running` while the app is plainly running**, the two processes
> resolved *different* data directories. The discovery file is the only rendezvous, so an MCP client
> started with a different `PLANESWALKER_DATA_DIR` than the terminal that launched the companion —
> or with none, when your shell sets one — looks in a directory the companion never wrote to and
> correctly concludes nothing is there. Set the variable the same way for both, or leave it unset
> for both.

* **A clean stop (Ctrl-C)** exits `0` and removes `companion.json`. It leaves `companion.lock`
  behind **deliberately** — the reasons, and everything else an uninstall leaves in the data
  directory, are under
  [what an uninstall leaves behind](#image-cache-companion-app).
* **An unclean exit** (a crash, a `kill`, the power going out) leaves `companion.json` behind
  stale. That is the *expected* post-crash state rather than an error: a stale file reads as "app
  not running", and the next launch reclaims it and says so in its log on stderr. There is nothing
  to clean up by hand.

### What it exposes

The companion binds a **loopback IPv4 socket and nothing else**. `127.0.0.1` is a constant in the
code rather than a setting, so there is no configuration that puts the app on your network, and the
traffic is plain HTTP — which is exactly why it has to stay on loopback. The endpoints your agent
uses are gated by a token minted fresh for each process and written into `companion.json`; that file
is created `0600` on macOS and Linux, but Windows has no equivalent, so there it is readable by any
account on the machine. Treat this as what it is: a single-user local tool, not something to leave
running on a machine you share with people you would not hand your decks to.

### First run on a fresh install

A fresh install ships **no card database** — the Scryfall set is excluded by licence, so `cards.db`
does not exist until you ask your agent to run `initialize_database`. The companion **starts
anyway** and serves the page: a missing database is a state the UI shows, not a startup failure.
The panel reads:

> **Card database not set up yet.**
>
> First build takes a few minutes — this page will come alive on its own when it's ready.
>
> In your agent session, ask it to initialize the database (`initialize_database`).

It means that literally. Readiness is re-probed on every request and never cached, so a database
built while the companion is running is picked up with **no restart** — leave the page open and it
will fill itself in.

**Recovering from a failed first import.** The importer creates the schema *before* it downloads, so
an import that fails partway can leave a `cards.db` with tables but no cards. The page is still
right — it goes on saying the database is not set up — but a running companion will have opened that
file and holds connections to it, and what happens next depends on your platform:

* **Windows** refuses the delete outright: the open handle blocks removal and replacement, so you
  find out immediately.
* **macOS and Linux** let the delete succeed and hand you a worse outcome quietly. The companion
  keeps the file it already opened, a re-import writes a *new* file in its place, and the app goes
  on reading the old one — so the page never fills in, and the "no restart needed" promise above
  does not apply to a database swapped out from under it.

**Stop the companion first (Ctrl-C), then delete it or re-run the import**, and start it again
afterwards. Nothing else is blocked: a second process *writing into* the file is fine, and only
wholesale replacement of it is not.

### Its images are cached on disk

Every card image the companion fetches from Scryfall is kept in one directory inside the same data
directory, so a deck you have already viewed repaints without touching the network. Where it is, how
big it gets, how to inspect it and how to remove it are all in
[Image cache (companion app)](#image-cache-companion-app) below.

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

The per-OS default is the one in the table under [Where the data lives](#where-the-data-lives), and
the location follows `PLANESWALKER_DATA_DIR` — set that variable and the cache moves with everything
else. It cannot be moved on its own: there is one data directory and the cache is inside it. Only
the companion app reads or writes it; the MCP server never touches it.

**Layout.** One file per card id + rendition + face:

```
image_cache/<first two characters of the card id>/<card id>/<size>_<face>.<ext>
```

for example `image_cache/81/813d0434-8e0f-4b0a-9c7e-1f2a3b4c5d6e/normal_0.jpg`. Card ids are
uuids, so the two-character shard spreads entries evenly across 256 shards instead of piling
every card directory side by side in one flat folder. (If every one of the ~38,000 printings
were cached that would be roughly 150 per shard; a typical ~1,000-printing library lands around
4 per shard — the cache only ever holds what you have viewed.)

**Inspect it.** Both blocks resolve the path through the app's own code, so they are correct on
every OS and under a `PLANESWALKER_DATA_DIR` override — you never have to know where your data
directory is. **Run them from the project directory** (they use `uv run`, so they need the checkout
and its environment); if you have already deleted the checkout, use the per-OS path from the table
above and append `image_cache`. Resolving the path creates the data directory if it does not exist
yet, and a "no such file or directory" from `du` simply means nothing has been cached yet:

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
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Cache
```

Clearing costs nothing but bandwidth: the next time you open a deck its art is fetched again, paced
at ten images a second, so a 100-card deck takes roughly ten seconds and needs a working connection.

**Nothing is ever evicted.** There is no TTL, no size cap, no index, no cleanup pass and no setting
that turns caching off — the cache only grows, until you delete it. **Measured** on 2026-08-02 by
fetching a real 99-card deck through the app's own image route against the real Scryfall CDN: about
**90 KB** per tile at the grid's `normal` size and **8.5 MB** for the whole 99-tile deck (the two
were measured separately, so they do not divide exactly). At that rate a library of ~1,000 distinct
printings comes to roughly **95 MB**. An earlier **arithmetic estimate** of *roughly 12 MB per
100-card deck* circulated while the feature was being built; it assumed ~124 KB per tile, which the
measurement put at ~90 KB — a **38 % overestimate**, and 8.5 MB rather than 12 MB per deck. The
measured figures are the ones to plan against, and both are quoted here so the two numbers are not
left to disagree in silence. If an eviction policy is ever added, it will be sized against a
measurement like this one rather than guessed.

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
both typically larger than the image cache, so deleting the data directory itself — the per-OS path
in the table above — removes everything this project ever wrote, including the three files listed
here. That is the one step to take after deleting the checkout.

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

**Changing the companion's UI needs Node `>=20.19.0`** — the one thing in this project that needs
Node at all. The built SPA bundle is **committed** (that is what keeps installs Node-free), so it
has to be rebuilt and committed with every `ui/` change or CI fails on drift:

```bash
cd ui
npm ci                  # locked install — never npm install
npm run lint            # eslint + stylelint
npm run format:check    # prettier (this one re-pads markdown tables under ui/)
npm run typecheck       # tsc -b
npm test                # vitest
npm run build           # writes the bundle into src/companion/app/static/
```

Commit `src/companion/app/static/` alongside your `ui/` change, then run
`uv run python -m scripts.build_plugin` and commit `plugin/` — CI checks both mirrors for drift.
There is a third generated artifact (the TypeScript types the UI compiles against); all three,
with what regenerates each, are listed under
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

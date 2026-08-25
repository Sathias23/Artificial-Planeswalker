# The companion app — full guide

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


This page is the whole operating manual: launching and stopping, ports, the single-instance rule,
how the MCP tools find a running companion, what it exposes, first-run states, and the on-disk
image cache. The [README's companion section](../README.md#the-companion-app) is the short version.

## Ask the agent to open it

You never need to know the launch command: say "open the companion" and the agent does the rest.
The `companion` skill calls the read-only `companion_status` tool — which reports whether a
companion is running, its URL, how many browser tabs are connected, and the exact launch command
for this install — and, when nothing is running, runs that command in a background shell of its
own. The companion starts, prints its URL, and opens your default browser on it itself (the
`--open` flag below). Ask again with a tab already open and the agent reports "already open" and
does nothing. If the companion is running but you closed the tab, the agent runs the same command
again — `--open` opens a fresh tab on the running instance without starting a second one — and
falls back to giving you the URL only if no browser could be opened. The MCP server never starts
the companion; the process belongs to the shell the agent runs it in.

**Stopping one the agent launched:** it lives in the agent's background shell, so the companion's
own Ctrl-C does not apply — ask the agent to stop its background task, or end the process yourself
(it is the `artificial-planeswalker companion` process on your machine). Closing the tab alone
leaves it running.

## Launch it

```bash
uv run artificial-planeswalker companion
```

Add `--open` to have the companion pop your default browser on its URL as soon as it is serving
(this is what the agent uses):

```bash
uv run artificial-planeswalker companion --open
```

`--open` is a bare flag (no value) and is safe to repeat across launches: if a companion is already
running, the launch prints its "already running" line, opens a tab on *that* instance's URL, and
exits `0` — it never starts a second one. If no browser can be opened, a warning lands on stderr
and the companion keeps serving; open the printed URL by hand.

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
> [Development](../README.md#development) is for, and it is a development and CI concern only.

**Installed via the plugin rather than a clone?** Same app, same flags — but the invocation is
anchored at the installed plugin root: see [Running from a plugin install](#running-from-a-plugin-install).

## Choosing a port

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
* `--open` is accepted in any position beside `--port`. `--open=yes` and a misspelt `--open` are
  usage errors like any unknown argument; so is `--open` given twice.
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

## One companion at a time

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

## How it is found, and what an unclean exit leaves

A running companion publishes one small JSON file — `companion.json`, in the data directory under
[Where the data lives](../README.md#where-the-data-lives) — naming the port it actually bound and a per-process
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
  [what an uninstall leaves behind](#image-cache).
* **An unclean exit** (a crash, a `kill`, the power going out) leaves `companion.json` behind
  stale. That is the *expected* post-crash state rather than an error: a stale file reads as "app
  not running", and the next launch reclaims it and says so in its log on stderr. There is nothing
  to clean up by hand.

## What it exposes

The companion binds a **loopback IPv4 socket and nothing else**. `127.0.0.1` is a constant in the
code rather than a setting, so there is no configuration that puts the app on your network, and the
traffic is plain HTTP — which is exactly why it has to stay on loopback. The endpoints your agent
uses are gated by a token minted fresh for each process and written into `companion.json`; that file
is created `0600` on macOS and Linux, but Windows has no equivalent, so there it is readable by any
account on the machine. Treat this as what it is: a single-user local tool, not something to leave
running on a machine you share with people you would not hand your decks to.

## First run on a fresh install

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


## Running from a plugin install

Every command on this page assumes you are standing in a checkout of this repo. The plugin carries
the same app — every flag, message and behaviour applies unchanged — but the **invocation** is
anchored at the installed plugin root rather than at the working directory, so add `--directory`
to each command:

```bash
# Claude Code keeps its plugin cache under ~/.claude, Codex under ~/.codex — same shape either way
ls -d ~/.claude/plugins/cache/*/artificial-planeswalker/*/    # list the versioned install(s)
PLUGIN_ROOT="$HOME/.claude/plugins/cache/<marketplace>/artificial-planeswalker/<version>"
uv run --directory "$PLUGIN_ROOT/server" artificial-planeswalker companion
```

```powershell
# Windows (PowerShell) — wherever your client installed the plugin (~\.claude or ~\.codex)
Get-ChildItem -Directory -Recurse -Depth 3 "$HOME\.claude\plugins\cache" -Filter server
$PluginRoot = "<the directory listed above, without \server>"
uv run --directory "$PluginRoot/server" artificial-planeswalker companion
```

So `--port 9000` becomes
`uv run --directory "$PLUGIN_ROOT/server" artificial-planeswalker companion --port 9000`, and the
`COMPANION_PORT` variants work the same way. This `--directory` form is exactly what
`companion_status` returns as its `launch_command` (with `--open` appended), derived from where the
server is actually installed — so the agent's launch works from a plugin install and a clone alike.

Both clients install into a **version-keyed** cache directory, so the path is specific to your
machine *and* to the plugin version — read it off your own install rather than pasting a literal
one, and expect it to change when you update the plugin. The first launch from a given root builds
a virtualenv and installs the server's dependencies inside it (tens of seconds, once), and a plugin
update to a new version repeats that in the new directory.

## Image cache

The companion app stores every card image it fetches from Scryfall on disk, so a deck you have
already viewed repaints without touching the network. It is **one directory** inside the data
directory described above:

```
<data dir>/image_cache/
```

The per-OS default is the one in the table under [Where the data lives](../README.md#where-the-data-lives), and
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


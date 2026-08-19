# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **The companion app** — an optional local browser view of the deck your agent
  is working on, launched with a single command:
  `uv run artificial-planeswalker companion`. It serves a read-only page at
  `http://127.0.0.1:8765` showing real card images laid out as cards rather
  than as text, and the two new tools **`companion_set_active_deck`** and
  **`companion_show_suggestions`** put a saved deck, or a list of suggested
  cards, on that page while you watch. Nothing depends on it: every agent
  workflow completes with the app closed, and both tools report
  `app_not_running` when it is not up. The browser UI ships pre-built inside
  the Python package, so **Node is required neither at install nor at
  runtime** — there is no build step between a fresh clone and a running app.
- **Self-diagnosable startup.** The preferred port is 8765, overridable with
  `--port` (highest precedence) or `COMPANION_PORT`; a value outside
  `0..65535` from either source is ignored with a warning rather than
  refused. If the preferred port is unavailable the app falls back to a
  kernel-assigned ephemeral port instead of failing, and the printed URL is
  always the bound one. Exactly one companion runs at a time — a second launch
  prints where the first one is (or, inside another launch's startup window,
  that one is starting up) and exits `0`. A running app publishes
  `companion.json` in the data directory as the sole rendezvous for the MCP
  tools; a clean stop removes it, and an unclean exit leaves a stale one that
  the next launch reclaims.
- **A fresh install with no card database starts anyway.** The absence of
  `cards.db` is a served UI state, not a startup failure: the page comes up and
  directs you to ask your agent to run `initialize_database`. Readiness is
  re-probed per request and never cached, so a database built while the app is
  running is picked up with no restart.
- **On-disk image cache.** Every card image the companion fetches from Scryfall
  is stored under `<data dir>/image_cache/`, sharded two characters deep and
  keyed by card id + size + face, so a deck already viewed repaints without
  touching the network. Measured footprint: ~90 KB per `normal` tile, ~8.5 MB
  for a 99-card deck, ~95 MB for a full set of printings. **Nothing evicts it** —
  no TTL, no size cap — and it is safe to delete at any time, running app or
  not; the README carries copy-pasteable inspect and clear commands for
  macOS/Linux and Windows.
- **New dependencies.** Two at runtime — `fastapi>=0.139.2` and
  `uvicorn[standard]>=0.51.0` — both in the base dependency list, so the
  companion needs no extra and no dependency group. One for development only:
  `websockets>=12.0` in the `dev` group, which is **not a new package in the
  install** (it already arrived transitively via `uvicorn[standard]`) but is now
  declared explicitly, because `scripts/cdp_harness.py` is a committed tool and
  a committed tool must not lean on another package's extra.

### Changed

- **Node is a development and CI dependency only**, floored at `>=20.19.0`, and
  is needed solely to *change* the companion's UI. The built bundle is
  committed to the repository and mirrored into the plugin tree, so installs
  and releases never compile it.
- **TypeScript is pinned `>=5.9 <6.1` rather than left as an open floor.** Two
  measured reasons, and both are needed. Unconstrained, an open floor resolves
  to TypeScript 7, which `typescript-eslint@8` refuses outright — it publishes a
  peer range of `>=4.8.4 <6.1.0` — and the ESLint gate dies with it. In this
  project npm never gets that far: with `typescript-eslint` present it
  back-solves, and the same open floor lands on **6.0.3, not 7**. So the pin's
  larger job is the second one — the constraint is declared here and owned,
  rather than emerging from a transitive peer that a future bump could relax
  silently.
- **Scryfall attribution now names card imagery** alongside card data, in both
  `README.md` and `NOTICE`. The app's footer has always said "Card data and
  imagery courtesy of Scryfall" and the companion does cache images; the
  documentation had not caught up. `NOTICE` ships in the distribution
  (`license-files`), so this is a licensing-relevant correction rather than a
  wording preference.

### Deprecated

- **`view_deck` is deprecated**, superseded by the companion app — use
  `companion_set_active_deck` to put a deck on the companion's live browser
  view instead of rendering a one-shot HTML file. The tool keeps working
  unchanged: its parameters, result shape, status tokens and rendered HTML are
  exactly as before, so every workflow that calls it still completes.
- **The `src/viewer` package is frozen.** No new capability lands there — no new
  module and no new public function; new deck-view work belongs in the companion
  app, and the companion never reuses the old renderer's HTML template.
- **Removal is deferred to the next minor release, once the companion app is
  proven.** `view_deck`, `src/viewer` and `scripts/view_deck.py` will be removed
  together at that point; until then nothing that depends on them breaks.

### Security

- **The companion opens a listening socket** — the first time anything in this
  project has. The envelope, stated plainly: it binds **loopback IPv4 only**
  (`127.0.0.1` is a constant in the code, not a setting, so no configuration
  exposes it to the network), it speaks plain HTTP, and its agent-only endpoints
  are gated by a token minted per process and written to `companion.json` in the
  data directory. That file is created `0600` on macOS and Linux; Windows has no
  equivalent, so there any account on the machine can read it. The MCP server
  itself is unchanged and still opens nothing.

### Upgrade notes

- **Nothing to migrate.** No schema change, no data-directory move, and no
  configuration to add: the companion is optional, off unless you start it, and
  every existing workflow completes with it closed. `view_deck` keeps working
  exactly as before.
- **Known limitation — a failed first import can wedge the database file.** The
  importer creates the schema before it downloads, so an import that fails
  partway leaves a `cards.db` with tables and no cards. That is displayed
  correctly (the page goes on saying the database is not set up), but a running
  companion will have opened the file, and from then on it cannot be deleted or
  replaced until the app stops. **Stop the companion first (Ctrl-C), then delete
  it or re-run the import.** Only wholesale replacement is blocked — a second
  process writing *into* the file is fine — and the recovery is in the README.

## [0.4.0] - 2026-07-18

### Added

- **Deck power assessment (experimental)** — the new **`assess_deck_power`** tool
  scores a saved deck 0–100 for its format with a seven-dimension vector (speed,
  consistency, resilience, interaction, mana efficiency, card advantage, combo
  potential), a descriptive tier label, and — for Commander — a WotC Bracket
  floor plus cEDH candidacy. Every score carries its evidence: Game Changer
  names, detected combos (in the deck, or one piece away), structural gaps,
  a `data_vintage` block dating the combo data, and a confidence level that
  names any degraded inputs (missing combo snapshot, unidentified commander,
  unknown Game Changer data) instead of silently guessing. Output is
  deterministic — the same deck against the same data serializes
  byte-identically. Supported formats: `commander` and `standard`.
  *Experimental:* scoring calibration is still being tuned; expect the numbers
  (not the shape of the output) to shift in upcoming releases.
- **`compare_deck_power`** — server-side diff of two assessments ("did my edit
  make the deck stronger, and what changed?"): per-dimension deltas, score
  endpoints and tiers, the Commander bracket pair, and sorted added/removed
  lists for Game Changers, combos (including included ↔ almost-included bucket
  flips), and structural gaps. Delta direction is always candidate − baseline.
- **Local Commander Spellbook combo snapshot.** Combo detection reads a local
  import of the [Commander Spellbook](https://commanderspellbook.com) bulk
  export (~26 MB download, ~100k variants) stored in the same SQLite file —
  fully offline once imported, refreshed on demand with
  `uv run python scripts/import_spellbook_combos.py` (atomic replace; a failed
  run keeps the previous snapshot). Without it, assessment still runs at
  reduced confidence (`combo_data_unavailable`) rather than erroring.
- **Commander identity on deck cards.** `add_card_to_deck` accepts a
  `commander` flag (two flagged rows = partners), used by format resolution
  and commander-gated combo matching; a sole legendary creature in a
  commander deck is inferred when nothing is flagged.
- **`game_changer` card field**, imported from Scryfall's curated Game
  Changers list and surfaced in assessment evidence.

### Upgrade notes

- **Existing databases need two additive columns** (`cards.game_changer`,
  `deck_cards.commander`) that new installs get automatically. Easiest path:
  delete the central data directory and re-run `initialize_database` +
  `build_search_index`. To keep saved decks instead, run the two idempotent
  migrations from a clone —
  `uv run python scripts/migrate_add_game_changer.py` and
  `uv run python scripts/migrate_add_deck_card_commander.py` — then refresh
  card data (`initialize_database` with `update=true`) to backfill
  `game_changer` values.
- Combo detection is empty until the snapshot import above has been run once.

## [0.3.0] - 2026-07-11

### Added

- **OpenAI Codex CLI plugin support.** One committed `plugin/` tree now serves
  both Claude Code and Codex: `build_plugin.py` emits `.codex-plugin/plugin.json`
  + `codex-mcp.json` alongside the Claude manifests, a repo-scoped marketplace
  enables `codex plugin marketplace add`, and the README gains an OpenAI Codex
  connect block. Live-smoked on the Codex app (Windows): skills + all 16 MCP
  tools working.
- **Bulk Arena deck-import tool.** Import a full MTG Arena decklist blob in one
  call — per-line resolution with an ok / ambiguous / not-found report — instead
  of dozens of individual `add_card_to_deck` calls. Recognizes the Companion
  section (mapped to the sideboard) and skips Arena's optional About/Name
  metadata block without degrading a valid import to `partial`.

### Changed

- **Reminder text is stripped from oracle text before embedding.** Parenthetical
  reminder text (Menace, Convoke, ...) was embedded verbatim into `card_vec`,
  polluting semantic recall (menace cards surfaced for "unblockable", convoke for
  "ramp"). A canonical `strip_reminder_text()` now cleans oracle text before both
  the embedded text and its change-detection hash, so a normal incremental
  `build_card_embeddings.py` re-embeds exactly the affected cards (no `--rebuild`).
  Query embeddings and the raw `cards.oracle_text` column are untouched.
- **Card import dedupes to one row per oracle identity with `games` unioned
  across all printings**, fixing Arena false-positives in `validate_deck` and
  games-filtered search/semantic tools silently dropping Arena staples. In
  addition, `validate_deck` now enforces a 1-copy singleton limit (basics exempt)
  for brawl / standardbrawl / commander / gladiator and friends, with
  case-insensitive format keys.

### Fixed

- **`validate_deck` no longer flags an entire legal deck as illegal on an
  unrecognized or capital-cased format.** Format keys are lowercased, and an
  unknown format now emits a single `unknown_format` violation instead of failing
  every card's legality check (Pre-Phase-2 Gate G-SD2a).
- **`detect_synergies` no longer invents phantom tribes from double-faced cards.**
  The `//` separator and non-creature back faces (e.g. "Sorcery", "Instant") are
  no longer treated as creature types; both-creature-face DFCs merge their tribes
  with cross-face de-duplication (Pre-Phase-2 Gate G-SD2b).
- **The bulk-import CLI defaults to the shared central database**
  (`src.paths.database_path()`) instead of a stale repo-local `data/cards.db`, so
  a refresh and the MCP server no longer silently read different files.
- **A process kill mid-import no longer leaves a partial database mistaken for
  complete.** The card importer commits per batch, so a hard kill between batches
  could leave a truncated `cards` table that the "≥1 row" idempotency check
  reported as `already_initialized` — permanently. A first-run import now writes a
  durable in-progress marker (`import_state`) that is cleared only after the import
  finishes, so a partial database reads as not-initialized and `initialize_database`
  re-imports it. Complete databases (including pre-existing ones with no marker) and
  `update=true` refreshes are unaffected.
- **Concurrent writers wait instead of failing instantly with "database is
  locked".** Both the async engine (`connect_args={"timeout": 5}`) and the sync
  sqlite-vec connection factory (`PRAGMA busy_timeout=5000`) now set a 5-second
  busy timeout, so a bulk import and an index build (or any two writers) no longer
  collide immediately under WAL.
- **Reversible / multi-face cards are no longer dropped on import.** Cards that
  carry their `oracle_id` only on `card_faces[0]` (reversible layouts) were grouped
  correctly in pass 1 but then rejected by the transformer's top-level-`oracle_id`
  requirement, so they never reached the database. Oracle-identity resolution is now
  shared between the aggregator and the transformer (`resolve_oracle_id`), so such a
  card imports as one row (with its cross-printing `games` union).
- **A failed `games` reconciliation no longer errors out a completed import.** The
  card import commits before the reconcile pass, so a transient reconcile failure
  (lock/disk) used to leave `initialize_database` reporting `error` over a fully
  populated database — and a plain retry then short-circuited as
  `already_initialized` with games left stale. Reconcile failures are now logged and
  swallowed; the affected pre-existing rows refresh on the next `update=true` run.

## [0.2.0] - 2026-07-06

The first public release.

### Added

- **Claude Code plugin distribution** via the repo's built-in marketplace: the
  committed `plugin/` tree (assembled by `scripts/build_plugin.py`) ships the MCP
  server *and* the four deckbuilding skills as one two-command install
  (`/plugin marketplace add Sathias23/Artificial-Planeswalker`, then
  `/plugin install artificial-planeswalker@artificial-planeswalker`). CI rebuilds
  the tree and fails on drift.
- `initialize_database` accepts `update=true` to pull newly released cards into
  an existing database.
- `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1); CI and license badges.

### Changed

- **Retired the `.mcpb` (Claude Desktop) bundle** — the MCPB format cannot carry
  skills, so the Claude Code plugin is the sole packaged distribution. Claude
  Desktop is still supported via a manual `claude_desktop_config.json` entry
  (see README). `manifest.json` and `.mcpbignore` are gone; plugin metadata now
  derives from `pyproject.toml`.
- `setup.py` runs its database-initialization step inside the uv-managed
  environment (`uv run`), fixing an ImportError on machines where the project
  dependencies aren't importable from the system interpreter.
- Declared `pydantic` (imported throughout) instead of the unused
  `pydantic-settings`; pyproject now carries license, keywords, URLs, and
  classifiers metadata.

### Security

- Bulk-data downloads land in a fresh private per-run temp directory instead of
  a fixed, world-shared `/tmp` path.
- Downloads enforce a byte ceiling derived from the size Scryfall advertises
  (disk-exhaustion guard), and the metadata-supplied `download_uri` must be
  https on a Scryfall host.

### Fixed

- Installed plugin now ships `LICENSE` and `NOTICE`; its bundled README no
  longer has dead relative links.
- README no longer claims `setup.py` builds the semantic index, documents the
  actual oracle-cards count (~30k), and carries Scryfall's requested
  non-endorsement notice (also in `NOTICE`, alongside hero-image provenance).

## [0.1.0] - 2026-06-28

Initial public release.

### Added

- Stateless MCP server exposing Magic: The Gathering deckbuilding tools over a
  local Scryfall card database: card lookup and keyword search, deck management,
  and mana-curve / synergy / format-legality analysis.
- Local semantic card search (`semantic_search_cards`, `find_similar_cards`)
  backed by `sqlite-vec` + `fastembed` (`bge-small-en-v1.5`) — no API key and no
  network at query time. Build the index with
  `uv run python scripts/build_card_embeddings.py`.
- Four companion skills layered on the tools: `magic-deckbuilding` (the
  orchestrator), `synergy-discovery`, `mana-curve-analysis`, and
  `format-legality`.
- Card database and embedding cache stored in a central, OS-appropriate data
  directory (`%LOCALAPPDATA%\artificial-planeswalker\` on Windows,
  `~/Library/Application Support/artificial-planeswalker/` on macOS,
  `~/.local/share/artificial-planeswalker/` on Linux), shared across clones and
  MCP clients. Override with `PLANESWALKER_DATA_DIR` or `CARDS_DATABASE_URL`.

### Upgrade notes

- Earlier development builds stored data under the project-relative `./data/`. As
  of 0.1.0 the default is the central OS data directory above. To reuse existing
  data, move the `data/` contents into the new directory, or set
  `PLANESWALKER_DATA_DIR` to its **absolute** path (a relative value resolves
  against the server's working directory, which an MCP client may not set to the
  repo root) — or point `CARDS_DATABASE_URL` at the old file. New installs need no
  action: `setup.py` imports the card database into the central directory
  automatically (the semantic index is built separately, see Added).

[Unreleased]: https://github.com/Sathias23/Artificial-Planeswalker/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Sathias23/Artificial-Planeswalker/releases/tag/v0.4.0
[0.3.0]: https://github.com/Sathias23/Artificial-Planeswalker/releases/tag/v0.3.0
[0.2.0]: https://github.com/Sathias23/Artificial-Planeswalker/releases/tag/v0.2.0
[0.1.0]: https://github.com/Sathias23/Artificial-Planeswalker/releases/tag/v0.1.0

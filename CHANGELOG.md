# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.3.0]: https://github.com/Sathias23/Artificial-Planeswalker/releases/tag/v0.3.0
[0.2.0]: https://github.com/Sathias23/Artificial-Planeswalker/releases/tag/v0.2.0
[0.1.0]: https://github.com/Sathias23/Artificial-Planeswalker/releases/tag/v0.1.0

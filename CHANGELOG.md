# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/Sathias23/Artificial-Planeswalker/releases/tag/v0.1.0

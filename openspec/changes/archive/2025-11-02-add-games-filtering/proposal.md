# Add Games Filtering Proposal

## Why

The Spider-Man series of cards (e.g., Cosmic Spider-Man, Spider-Woman Stunning Savior) and other cards are being returned in card searches even when they are not available in MTG Arena. Users building decks for specific platforms (paper Magic, Arena, or MTGO) need a way to filter cards by game availability to avoid adding cards they cannot use.

Currently, only format filtering (Standard, Modern, etc.) is supported, but this does not distinguish between paper-only cards and Arena-available cards. This creates friction for Arena players who find cards in search results that they cannot actually play.

## What Changes

- Import the `games` field from Scryfall bulk data (array containing "paper", "arena", and/or "mtgo")
- Add `games` field to CardModel and Card schema
- Create repository filtering method `_apply_games_filter()` following the format_filter pattern
- Add games filter to session state (AgentDependencies) with in-memory persistence
- Create `set_games_filter()` agent tool
- Update all search tools to accept games parameter with auto-filter bypass
- Display active **format_filter and games_filter** in Chainlit sidebar (both filters shown together)
- Update card display formatters to show game availability

**Research Sources:**
- Archon RAG: SQLModel filtering patterns (source: 61054360de16e6ba)
- Archon RAG: PydanticAI tool decorator patterns (source: ai.pydantic.dev)
- Scryfall API: games field documentation (https://scryfall.com/docs/api/cards)

## Impact

- **Affected specs:** card-queries, agent-tools, chainlit-ui
- **Affected code:**
  - `src/data/models/card.py` - Add games field
  - `src/data/schemas/card.py` - Add games field
  - `src/data/importers/transformers.py` - Import games from Scryfall
  - `src/data/repositories/card.py` - Add _apply_games_filter() method
  - `src/agent/dependencies.py` - Add games_filter to session state
  - `src/agent/tools/` - Create games_filter.py tool, update card_search.py and card_lookup.py
  - `src/ui/app.py` - Update sidebar to show both format_filter and games_filter
  - `src/ui/formatters.py` - Show game availability on cards
  - `tests/fixtures/card_data.py` - Add games to test fixtures

**Breaking changes:** None - this is additive functionality

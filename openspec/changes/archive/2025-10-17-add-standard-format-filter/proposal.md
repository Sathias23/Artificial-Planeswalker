# Standard Format Filtering Tool

## Why

Magic: The Gathering players building Standard format decks need to ensure they only consider cards that are legal in Standard. Currently, all card query tools return any matching card regardless of format legality, which can lead to deck building errors when illegal cards are included. This change implements Standard format filtering across the card query system to streamline the deck building workflow for Standard format players.

## What Changes

- Add format legality query filtering to CardRepository based on Scryfall's `legalities` JSON field
- Create new agent tool `set_format_filter` to enable/disable Standard format filtering in session context
- Extend existing card lookup and search tools to respect session format filter when enabled
- Add clear agent responses indicating when format filtering is active
- Provide user control to opt-out of filtering when exploring cards outside current format

## Impact

- **Affected specs**: `card-queries`, `data-layer`, `agent-tools`
- **Affected code**:
  - `src/data/repositories/card.py` - Add format legality filtering methods
  - `src/agent/tools/card_lookup.py` - Integrate format filter
  - `src/agent/tools/card_search.py` - Integrate format filter
  - `src/agent/dependencies.py` - Add format filter to session context
  - `src/agent/tools/format_filter.py` - New tool for filter control
- **Breaking changes**: None - format filtering is opt-in via agent tool
- **User workflow impact**: Standard format deck builders will have cleaner card query results by default after enabling format filter

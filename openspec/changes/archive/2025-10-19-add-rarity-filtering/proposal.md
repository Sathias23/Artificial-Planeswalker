# Add Rarity Filtering to Card Search

## Why

User bug report 5c15209f identified a gap in card search functionality: when users request cards of specific rarities (common, uncommon, rare, mythic), the agent cannot filter by rarity because `search_cards_advanced` lacks a rarity parameter.

This is a common deck-building need - users often want to find high-impact cards (rare/mythic) or budget-friendly options (common/uncommon) when building decks. Currently, the agent must return all results and apologize for not being able to filter by rarity.

The rarity data is already available in the Card schema and database (imported from Scryfall), but there's no query interface to access it.

## What Changes

- **ADDED**: Rarity filtering parameter to `CardRepository.search_advanced()` method
- **ADDED**: Rarity filtering parameter to `search_cards_advanced` agent tool
- **MODIFIED**: SQL query logic in `search_advanced()` to filter by rarity when specified
- **ADDED**: Unit tests for rarity filtering in repository and tool tests
- **ADDED**: Documentation of rarity values (common, uncommon, rare, mythic, special, bonus)

## Impact

- **Affected specs**: `card-queries`, `agent-tools`
- **Affected code**:
  - `src/data/repositories/card.py` - Add rarity parameter to `search_advanced()`
  - `src/agent/tools/card_search.py` - Add rarity parameter to `search_cards_advanced` tool
  - `tests/unit/data/test_card_repository.py` - Add rarity filter test cases
  - `tests/unit/agent/tools/test_card_search.py` - Add rarity filter test cases
- **User-visible changes**: Agent can now respond to queries like "show me rare red creatures" or "find mythic black cards"
- **Breaking changes**: None - this is an additive enhancement with optional parameter
- **Database changes**: None - rarity column already exists in CardModel

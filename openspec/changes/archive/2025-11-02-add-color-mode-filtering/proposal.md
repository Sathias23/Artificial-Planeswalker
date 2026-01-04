# Color Mode Filtering Enhancement

## Why

Currently, the agent can only search for cards that contain ANY of the specified colors (OR logic). When a user asks for "white AND blue cards," the agent explains it can only search for "white OR blue" cards, which returns mono-white, mono-blue, white-blue, and multicolor cards containing either color.

This limitation prevents users from finding:
- Cards that are specifically both white AND blue (Azorius multicolor cards)
- Cards that are exactly white-blue with no other colors
- Cards that fit within a specific color identity (at most W/U)

Magic: The Gathering has well-established color combination concepts (guilds, shards, wedges) that require precise color filtering. The current OR-only logic is insufficient for deck-building use cases.

## What Changes

Add a `color_mode` parameter to the card search system that controls how the `colors` list filter is interpreted:

- **`"any"`** (default, backward compatible): Contains ANY of the specified colors (current OR logic)
  - Example: `["W", "U"]` → mono-white, mono-blue, white-blue, white-blue-red, etc.

- **`"all"`**: Contains ALL of the specified colors (AND logic)
  - Example: `["W", "U"]` → white-blue, white-blue-red, white-blue-black, etc. (must have both W and U)

- **`"exact"`**: Exactly these colors, no more, no less
  - Example: `["W", "U"]` → only white-blue cards (not mono-white, not tricolor)

- **`"at_most"`**: Only these colors or fewer (subset/color identity)
  - Example: `["W", "U"]` → colorless, mono-white, mono-blue, white-blue

Changes affect three layers:
1. **Repository Layer**: Add `color_mode` parameter to `CardRepository.search_advanced()` with SQLite JSON filtering logic
2. **Agent Tools Layer**: Add `color_mode` field to `CardSearchFilters` Pydantic model with clear documentation
3. **Tests**: Add comprehensive test coverage for all four modes with edge cases

Default behavior remains unchanged (backward compatible).

## Impact

**Affected specs:**
- `card-queries` - MODIFIED: Advanced Multi-Criteria Search requirement

**Affected code:**
- `src/data/repositories/card.py` - Add `color_mode` parameter to `search_advanced()` method
- `src/agent/tools/card_search.py` - Add `color_mode` field to `CardSearchFilters` model
- `tests/unit/data/test_card_repository.py` - Add tests for all color modes
- `tests/unit/agent/tools/test_card_search.py` - Add tests for agent tool integration

**Performance impact:**
- `"any"` mode: No change (current implementation)
- `"all"` mode: Similar performance (AND instead of OR)
- `"exact"` mode: Adds `json_array_length()` check (minimal overhead)
- `"at_most"` mode: Most complex (requires JSON iteration) - may need optimization if slow

**User-facing impact:**
- Enables precise color queries matching MTG terminology ("Azorius cards", "exactly Boros", etc.)
- Agent can now fulfill requests like "show me white AND blue cards" correctly
- Backward compatible - existing queries work unchanged

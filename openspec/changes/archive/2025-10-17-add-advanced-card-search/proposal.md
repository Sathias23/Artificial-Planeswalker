# Add Advanced Card Search Tool

## Why

Users need to discover cards for deck building using complex criteria beyond simple name matching. The current card lookup tool (Story 2.2) only supports name-based queries. To enable questions like "show me red creatures with haste under 4 mana" or "find blue instants with draw effects," we need an advanced search tool that accepts multiple filter parameters and leverages the repository's query capabilities.

This directly implements Story 2.3 from the PRD: "Advanced Card Search Tool (Filters and Criteria)."

## What Changes

- Add new PydanticAI tool `search_cards_advanced()` with multi-criteria filtering support
- Support filters for: colors, card types, mana value range, and keyword abilities
- Integrate with existing `CardRepository` methods (from Story 1.3) for complex queries
- Handle edge cases: no results, too many results, invalid filter combinations
- Return paginated/limited results (default max: 20 cards) to prevent overwhelming responses
- Enable natural language interpretation of complex search queries via LLM parameter extraction

## Impact

- **Affected specs**: `agent-tools` (ADDED requirements)
- **Affected code**:
  - `src/agent/tools/` - New advanced search tool implementation
  - `src/data/repositories/card.py` - May need additional query methods for keyword search and combined filters
- **Dependencies**: Builds on Story 1.3 (card query functions) and Story 2.1-2.2 (agent core and basic lookup)
- **User benefit**: Users can perform sophisticated card discovery essential for deck building workflows

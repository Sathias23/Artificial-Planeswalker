# Add Synergy Detection

## Why

Users need help identifying card synergies within their decks to build more cohesive and powerful strategies. Currently, the system only provides mana curve analysis, but deck building success also depends on cards working well together. Story 5.3 from the PRD specifies basic synergy detection focusing on tribal synergies, keyword synergies, and mechanic combos.

## What Changes

- Add `detect_synergies()` function to analyze deck composition and identify card synergies
- Add `SynergyAnalysis` data structure to store detected synergy patterns with explanations
- Add `detect_synergies` PydanticAI agent tool for natural language synergy queries
- Add `format_synergies()` function to render synergy analysis as formatted markdown
- Implement pattern-based detection for:
  - Tribal synergies (shared creature types: Goblins, Elves, etc.)
  - Keyword synergies (keyword-matters cards: flying, lifelink, etc.)
  - Mechanic combos (sacrifice outlets + death triggers, etc.)
- Add comprehensive unit tests (90%+ coverage) and integration tests

## Impact

- **Affected specs**: `deck-intelligence` (ADDED requirements for synergy detection)
- **Affected code**:
  - `src/logic/synergy.py` (new module for synergy detection logic)
  - `src/agent/tools/deck_intelligence.py` (new `detect_synergies` tool)
  - `src/ui/formatters.py` (new `format_synergies()` function)
  - `tests/unit/logic/test_synergy.py` (new unit tests)
  - `tests/integration/test_synergy_tool.py` (new integration tests)
- **User benefit**: Users can ask "what synergies does my deck have?" and receive actionable insights about card interactions
- **Dependencies**: Requires existing deck management system and card data with type_line, oracle_text, and keywords fields

# Add Deck Strategy Field

## Why

Users need a way to specify the intended strategy for their decks (e.g., "control", "aggro", "midrange") to guide the AI agent in making synergistic card recommendations. Currently, the agent has no context about deck strategy, making it difficult to suggest cards that align with the deck's overall game plan.

## What Changes

- Add `strategy` field to DeckModel (SQLAlchemy) and Deck schema (Pydantic)
  - String column type (nullable, indexed)
  - Supports both simple labels ("control") and detailed explanations
- Update DeckRepository methods to handle strategy field (create, update, list)
- Display strategy in Chainlit deck information sidebar
- Update agent tools to use strategy as context for card recommendations

## Impact

### Affected Specs
- **deck-management**: Add strategy field to models, schemas, and repository
- **agent-tools**: Modify card recommendation tools to use strategy context
- **chainlit-ui**: Update sidebar to display strategy information

### Affected Code
- `src/data/models/deck.py` - Add strategy column
- `src/data/schemas/deck.py` - Add strategy field
- `src/data/repositories/deck.py` - Update CRUD methods
- `src/agent/tools/deck_tools.py` - Use strategy for recommendations
- `src/ui/app.py` - Display strategy in sidebar
- Database migration - Add strategy column to decks table

### Breaking Changes
None - strategy field is optional (nullable), backward compatible with existing decks.

## Research Summary

**Research conducted**: 2025-10-21

**Sources consulted**:
- Archon RAG: SQLAlchemy field types and patterns
- PydanticAI: Agent context and dependency injection patterns
- Existing codebase: DeckModel, Deck schema, DeckRepository

**Key findings**:
- SQLAlchemy String column type provides flexibility for both short labels and detailed explanations
- Nullable field ensures backward compatibility
- Index on strategy enables future filtering (e.g., "show all control decks")
- Agent dependencies pattern already supports passing deck context to tools
- Chainlit sidebar update mechanism (`update_deck_sidebar()`) exists and can be extended

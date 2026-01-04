# Implementation Tasks: Add Deck Strategy Field

## 1. Data Layer (Models & Schemas)
- [ ] 1.1 Add `strategy` column to DeckModel (src/data/models/deck.py)
- [ ] 1.2 Add `strategy` field to Deck Pydantic schema (src/data/schemas/deck.py)
- [ ] 1.3 Add unit tests for DeckModel with strategy field
- [ ] 1.4 Add unit tests for Deck schema with strategy validation

## 2. Repository Layer
- [ ] 2.1 Update `create_deck()` to accept optional strategy parameter
- [ ] 2.2 Update `update_deck()` to support updating strategy field
- [ ] 2.3 Update integration tests for deck creation with strategy
- [ ] 2.4 Update integration tests for deck updates (strategy changes)
- [ ] 2.5 Add test for listing decks with strategy field populated

## 3. Database Migration
- [ ] 3.1 Create Alembic migration to add strategy column to decks table
- [ ] 3.2 Add index on strategy column (ix_decks_strategy)
- [ ] 3.3 Test migration on development database
- [ ] 3.4 Test rollback migration
- [ ] 3.5 Verify existing decks work with strategy=NULL

## 4. Agent Tools
- [ ] 4.1 Update `create_deck` tool to accept optional strategy parameter
- [ ] 4.2 Update `update_deck_strategy` tool (new) to modify strategy
- [ ] 4.3 Update `view_deck` tool to display strategy in output
- [ ] 4.4 Update agent system prompt to use strategy context when available
- [ ] 4.5 Update `search_cards_advanced` tool to use strategy for recommendations
- [ ] 4.6 Add tests for tools with strategy context

## 5. UI Layer (Chainlit)
- [ ] 5.1 Update `update_deck_sidebar()` to display strategy field
- [ ] 5.2 Implement strategy truncation (200 chars) for display
- [ ] 5.3 Add conditional rendering (only show if strategy exists)
- [ ] 5.4 Test sidebar display with various strategy lengths
- [ ] 5.5 Test sidebar with decks without strategy (backward compatibility)

## 6. Documentation & Code Quality
- [ ] 6.1 Update CLAUDE.md with strategy field information
- [ ] 6.2 Run mypy type checking (must pass)
- [ ] 6.3 Run ruff linting and formatting
- [ ] 6.4 Update docstrings for modified functions
- [ ] 6.5 Run full test suite (all tests must pass)

## 7. Manual Testing
- [ ] 7.1 Create new deck with strategy via UI
- [ ] 7.2 Create new deck without strategy via UI
- [ ] 7.3 Update existing deck strategy via UI
- [ ] 7.4 Verify strategy appears in sidebar correctly
- [ ] 7.5 Verify agent uses strategy for card recommendations
- [ ] 7.6 Test with long strategy text (>200 chars)
- [ ] 7.7 Test with empty/null strategy

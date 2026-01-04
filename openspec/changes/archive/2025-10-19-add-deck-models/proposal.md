# Add Deck Database Models and CRUD Operations

## Why

Users need to create, save, and manage Standard format Magic: The Gathering decks through the AI assistant. Currently, the application only supports card queries without persistent deck storage. This change implements the foundation for deck building by adding database models for decks and deck-card relationships, along with repository methods for all CRUD operations.

## What Changes

- Add `DeckModel` SQLAlchemy model (id, name, format, created_at, updated_at)
- Add `DeckCardModel` SQLAlchemy model (deck_id, card_id, quantity, sideboard flag)
- Add `Deck` and `DeckCard` Pydantic schemas for type-safe data transfer
- Configure SQLAlchemy relationships between Deck, DeckCard, and Card models
- Add `DeckRepository` with CRUD operations:
  - `create_deck()`, `get_deck()`, `update_deck()`, `delete_deck()`, `list_decks()`
  - `add_card_to_deck()`, `remove_card_from_deck()`, `update_card_quantity()`
- Add database migrations/initialization for new deck tables
- Add comprehensive unit and integration tests for deck models and repository

## Impact

**Affected specs:**
- NEW: `deck-management` - New capability for deck persistence and CRUD operations
- MODIFIED: `data-layer` - Extends with new models and repository

**Affected code:**
- `src/data/models/` - New `deck.py` and `deck_card.py` model files
- `src/data/schemas/` - New `deck.py` schema file
- `src/data/repositories/` - New `deck.py` repository file
- `src/data/database.py` - Updated to initialize deck tables
- `tests/unit/data/` - New unit tests for deck models and schemas
- `tests/integration/data/` - New integration tests for DeckRepository

**Dependencies:**
- Requires existing Card model and CardRepository (already implemented)
- Blocks Epic 4 Stories 4.2-4.5 (deck creation tools depend on these models)
- Enables Epic 5 (deck analysis depends on deck data structure)

**Migration path:**
- No breaking changes (purely additive)
- Database migration creates new tables (decks, deck_cards) without affecting existing cards table
- No user data migration required (new functionality)

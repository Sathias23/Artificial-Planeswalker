# Implementation Tasks

## 1. Database Models

- [ ] 1.1 Create `src/data/models/deck.py` with DeckModel SQLAlchemy ORM class
  - UUID primary key (id)
  - String fields: name, format (indexed)
  - DateTime fields: created_at, updated_at (auto-managed)
  - Relationship to DeckCardModel (cascade delete)
  - Inherits from Base (MappedAsDataclass)

- [ ] 1.2 Create `src/data/models/deck_card.py` with DeckCardModel SQLAlchemy ORM class
  - Composite primary key: (deck_id, card_id, sideboard)
  - Foreign keys: deck_id (UUID, CASCADE), card_id (UUID)
  - Integer field: quantity (not null, >= 1)
  - Boolean field: sideboard (default False)
  - Relationships to DeckModel and CardModel

- [ ] 1.3 Update `src/data/models/__init__.py` to export DeckModel and DeckCardModel

## 2. Pydantic Schemas

- [ ] 2.1 Create `src/data/schemas/deck.py` with Deck and DeckCard Pydantic schemas
  - Deck schema: id, name, format, created_at, updated_at, deck_cards (optional list)
  - DeckCard schema: deck_id, card_id, quantity, sideboard, card (nested Card schema)
  - Format field with Literal type hint for valid formats
  - Validation rules: quantity >= 1, format in allowed list

- [ ] 2.2 Update `src/data/schemas/__init__.py` to export Deck and DeckCard schemas

## 3. Repository Layer

- [ ] 3.1 Create `src/data/repositories/deck.py` with DeckRepository class
  - Inherit from BaseRepository
  - Initialize with AsyncSession

- [ ] 3.2 Implement deck CRUD methods in DeckRepository
  - `create_deck(name: str, format: str) -> Deck` - Create new deck
  - `get_deck(deck_id: str) -> Deck | None` - Get deck by ID
  - `update_deck(deck_id: str, name: str | None = None) -> Deck | None` - Update deck
  - `delete_deck(deck_id: str) -> bool` - Delete deck (cascade to cards)
  - `list_decks(format_filter: str | None = None) -> list[Deck]` - List all decks

- [ ] 3.3 Implement card management methods in DeckRepository
  - `add_card_to_deck(deck_id: str, card_id: str, quantity: int, sideboard: bool = False) -> DeckCard` - Add card to deck
  - `remove_card_from_deck(deck_id: str, card_id: str, sideboard: bool = False) -> bool` - Remove card from deck
  - `update_card_quantity(deck_id: str, card_id: str, quantity: int, sideboard: bool = False) -> DeckCard | None` - Update card quantity
  - `get_deck_with_cards(deck_id: str) -> Deck | None` - Get deck with all cards loaded

- [ ] 3.4 Update `src/data/repositories/__init__.py` to export DeckRepository

## 4. Database Initialization

- [ ] 4.1 Update `src/data/database.py` init_database() to create deck tables
  - Ensure DeckModel and DeckCardModel metadata is registered
  - Verify tables are created on initialization

- [ ] 4.2 Test database initialization with new tables
  - Run init_database() and verify decks and deck_cards tables exist
  - Verify foreign key constraints are properly configured
  - Verify indexes are created on name and format columns

## 5. Unit Tests

- [ ] 5.1 Create `tests/unit/data/models/test_deck.py`
  - Test DeckModel instantiation with required fields
  - Test DeckModel default values (timestamps)
  - Test DeckModel __repr__ method

- [ ] 5.2 Create `tests/unit/data/models/test_deck_card.py`
  - Test DeckCardModel instantiation with required fields
  - Test DeckCardModel composite primary key
  - Test DeckCardModel __repr__ method

- [ ] 5.3 Create `tests/unit/data/schemas/test_deck.py`
  - Test Deck schema validation with valid data
  - Test Deck schema validation with invalid data (format, missing fields)
  - Test DeckCard schema validation with nested Card schema
  - Test DeckCard schema validation with invalid quantity

## 6. Integration Tests

- [ ] 6.1 Create `tests/integration/data/test_deck_repository.py`
  - Setup: In-memory database, create tables, populate with test cards

- [ ] 6.2 Test deck CRUD operations
  - Test create_deck() creates and returns deck
  - Test get_deck() retrieves existing deck
  - Test get_deck() returns None for non-existent deck
  - Test update_deck() modifies deck name and timestamp
  - Test delete_deck() removes deck and cascades to cards
  - Test list_decks() returns all decks in correct order
  - Test list_decks(format_filter) filters by format

- [ ] 6.3 Test card management operations
  - Test add_card_to_deck() adds card to mainboard
  - Test add_card_to_deck() adds card to sideboard
  - Test remove_card_from_deck() removes card from deck
  - Test update_card_quantity() changes card quantity
  - Test get_deck_with_cards() returns deck with populated cards
  - Test add duplicate card raises constraint error

- [ ] 6.4 Test foreign key cascade behavior
  - Test deleting deck deletes associated deck_cards
  - Test deleting deck does NOT delete cards themselves
  - Test deleting card with deck associations (should fail or cascade based on FK config)

## 7. Type Checking

- [ ] 7.1 Run mypy on new modules and fix any type errors
  - `uv run mypy src/data/models/deck.py`
  - `uv run mypy src/data/models/deck_card.py`
  - `uv run mypy src/data/schemas/deck.py`
  - `uv run mypy src/data/repositories/deck.py`

- [ ] 7.2 Run mypy on entire src/ directory and verify no regressions
  - `uv run mypy src/`

## 8. Code Quality

- [ ] 8.1 Run Ruff linting and formatting on new files
  - `uv run ruff check src/data/models/deck.py src/data/models/deck_card.py --fix`
  - `uv run ruff format src/data/models/deck.py src/data/models/deck_card.py`
  - `uv run ruff check src/data/schemas/deck.py --fix`
  - `uv run ruff format src/data/schemas/deck.py`
  - `uv run ruff check src/data/repositories/deck.py --fix`
  - `uv run ruff format src/data/repositories/deck.py`

- [ ] 8.2 Run Ruff on test files
  - `uv run ruff check tests/unit/data/models/test_deck*.py --fix`
  - `uv run ruff format tests/unit/data/models/test_deck*.py`
  - `uv run ruff check tests/integration/data/test_deck_repository.py --fix`
  - `uv run ruff format tests/integration/data/test_deck_repository.py`

## 9. Documentation

- [ ] 9.1 Add docstrings to all new classes and methods
  - DeckModel and DeckCardModel class docstrings
  - Deck and DeckCard schema docstrings
  - DeckRepository method docstrings with Args, Returns, Raises sections

- [ ] 9.2 Update CLAUDE.md if needed
  - Document DeckRepository API in "Agent Dependencies Pattern" or "Data Layer" section
  - Add examples of deck CRUD operations

## 10. Validation

- [ ] 10.1 Run all tests and verify they pass
  - `uv run pytest tests/unit/data/models/test_deck.py`
  - `uv run pytest tests/unit/data/models/test_deck_card.py`
  - `uv run pytest tests/unit/data/schemas/test_deck.py`
  - `uv run pytest tests/integration/data/test_deck_repository.py`
  - `uv run pytest` (full suite)

- [ ] 10.2 Verify test coverage meets goals
  - `uv run pytest --cov=src/data/models --cov=src/data/schemas --cov=src/data/repositories --cov-report=html`
  - Aim for 90%+ coverage on new code

- [ ] 10.3 Manual validation
  - Create test script to create deck, add cards, retrieve, and delete
  - Verify database tables have correct schema and constraints
  - Verify timestamps are auto-managed correctly

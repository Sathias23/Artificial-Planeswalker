# deck-management Specification

## Purpose
Provides database models and CRUD operations for Magic: The Gathering deck persistence, enabling users to create, save, and manage Standard format decks through the AI assistant.

## ADDED Requirements

### Requirement: Deck SQLAlchemy Model
The system SHALL provide a `DeckModel` SQLAlchemy ORM model for persisting deck metadata with proper type hints and relationships.

#### Scenario: Create deck model with required fields
- **GIVEN** a new Standard format deck with name "Mono Red Aggro"
- **WHEN** DeckModel is instantiated with name="Mono Red Aggro" and format="standard"
- **THEN** the model instance is created successfully
- **AND** id is auto-generated as UUID string
- **AND** created_at and updated_at timestamps are set to current UTC time

#### Scenario: Deck model with relationships
- **GIVEN** a DeckModel instance with deck_cards relationship configured
- **WHEN** DeckCardModel instances are associated with the deck
- **THEN** the deck.deck_cards relationship provides access to all deck cards
- **AND** the relationship supports async loading

#### Scenario: Update deck timestamp
- **GIVEN** an existing DeckModel instance
- **WHEN** the deck is modified (name change or cards added/removed)
- **THEN** the updated_at timestamp is automatically updated to current UTC time
- **AND** the created_at timestamp remains unchanged

### Requirement: DeckCard SQLAlchemy Model
The system SHALL provide a `DeckCardModel` SQLAlchemy ORM model for persisting deck card associations with quantity and sideboard tracking.

#### Scenario: Add card to deck mainboard
- **GIVEN** a DeckModel instance and a CardModel instance
- **WHEN** DeckCardModel is created with deck_id, card_id, quantity=4, sideboard=False
- **THEN** the model instance is created successfully
- **AND** the association links the deck and card with specified quantity
- **AND** the sideboard flag is False

#### Scenario: Add card to sideboard
- **GIVEN** a DeckModel instance and a CardModel instance
- **WHEN** DeckCardModel is created with sideboard=True and quantity=2
- **THEN** the card is associated with the deck's sideboard
- **AND** the sideboard flag is True

#### Scenario: DeckCard relationships
- **GIVEN** a DeckCardModel instance with deck and card relationships configured
- **WHEN** accessing deck_card.deck or deck_card.card
- **THEN** the related DeckModel and CardModel instances are accessible
- **AND** relationships support async loading

#### Scenario: Unique deck-card constraint
- **GIVEN** a deck with a card already added to mainboard
- **WHEN** attempting to add the same card to mainboard again
- **THEN** a database constraint violation occurs
- **AND** the operation fails with an appropriate error

### Requirement: Deck Pydantic Schemas
The system SHALL provide Pydantic schemas for Deck and DeckCard for type-safe data transfer between layers.

#### Scenario: Deck schema validation
- **GIVEN** a DeckModel instance from the database
- **WHEN** Deck.model_validate() is called with the model instance
- **THEN** a Deck Pydantic schema is returned with all fields populated
- **AND** the schema includes id, name, format, created_at, updated_at
- **AND** the schema passes Pydantic validation

#### Scenario: DeckCard schema with card details
- **GIVEN** a DeckCardModel instance with related CardModel
- **WHEN** DeckCard.model_validate() is called
- **THEN** a DeckCard Pydantic schema is returned
- **AND** the schema includes deck_id, card_id, quantity, sideboard
- **AND** the schema includes nested Card schema with full card details

#### Scenario: Invalid deck format
- **GIVEN** a Deck schema definition with format field
- **WHEN** instantiating with an invalid format (e.g., "invalid_format")
- **THEN** Pydantic raises a ValidationError
- **AND** the error indicates format must be one of the valid options

### Requirement: DeckRepository CRUD Operations
The system SHALL provide a `DeckRepository` with methods for creating, reading, updating, and deleting decks.

#### Scenario: Create new deck
- **GIVEN** a DeckRepository instance with an active session
- **WHEN** create_deck(name="Mono Red Aggro", format="standard") is called
- **THEN** a new deck is persisted to the database
- **AND** a Deck Pydantic schema is returned with generated id and timestamps
- **AND** the deck has no cards initially

#### Scenario: Get deck by ID
- **GIVEN** a deck exists in the database with id "deck-123"
- **WHEN** get_deck(deck_id="deck-123") is called
- **THEN** a Deck Pydantic schema is returned with all deck details
- **AND** the schema includes the list of deck cards

#### Scenario: Get non-existent deck
- **GIVEN** no deck exists with id "invalid-id"
- **WHEN** get_deck(deck_id="invalid-id") is called
- **THEN** None is returned
- **AND** no exceptions are raised

#### Scenario: Update deck name
- **GIVEN** a deck exists with name "Old Name"
- **WHEN** update_deck(deck_id="deck-123", name="New Name") is called
- **THEN** the deck name is updated in the database
- **AND** the updated_at timestamp is refreshed
- **AND** an updated Deck schema is returned

#### Scenario: Delete deck
- **GIVEN** a deck exists with id "deck-123"
- **WHEN** delete_deck(deck_id="deck-123") is called
- **THEN** the deck is removed from the database
- **AND** all associated DeckCard records are deleted (cascade)
- **AND** True is returned

#### Scenario: List all decks
- **GIVEN** multiple decks exist in the database
- **WHEN** list_decks() is called
- **THEN** a list of Deck Pydantic schemas is returned
- **AND** decks are ordered by created_at descending (newest first)

#### Scenario: List decks filtered by format
- **GIVEN** decks exist with formats "standard" and "commander"
- **WHEN** list_decks(format_filter="standard") is called
- **THEN** only Standard format decks are returned
- **AND** Commander decks are excluded

### Requirement: DeckRepository Card Management Operations
The system SHALL provide DeckRepository methods for adding, removing, and updating cards within decks.

#### Scenario: Add card to deck mainboard
- **GIVEN** a deck exists with id "deck-123"
- **AND** a card exists with id "card-456"
- **WHEN** add_card_to_deck(deck_id="deck-123", card_id="card-456", quantity=4, sideboard=False) is called
- **THEN** a DeckCard association is created in the database
- **AND** the deck now contains 4 copies of the card in mainboard
- **AND** a DeckCard schema is returned

#### Scenario: Add card to sideboard
- **GIVEN** a deck exists and a card exists
- **WHEN** add_card_to_deck(deck_id, card_id, quantity=2, sideboard=True) is called
- **THEN** the card is added to the deck's sideboard with quantity 2
- **AND** the sideboard flag is True in the returned schema

#### Scenario: Remove card from deck
- **GIVEN** a deck contains 4 copies of a card in mainboard
- **WHEN** remove_card_from_deck(deck_id="deck-123", card_id="card-456", sideboard=False) is called
- **THEN** the DeckCard association is deleted from the database
- **AND** the deck no longer contains the card

#### Scenario: Update card quantity
- **GIVEN** a deck contains 2 copies of a card
- **WHEN** update_card_quantity(deck_id="deck-123", card_id="card-456", quantity=4, sideboard=False) is called
- **THEN** the quantity is updated to 4 in the database
- **AND** an updated DeckCard schema is returned

#### Scenario: Get deck with cards
- **GIVEN** a deck contains multiple cards in mainboard and sideboard
- **WHEN** get_deck_with_cards(deck_id="deck-123") is called
- **THEN** a Deck schema is returned with deck_cards list populated
- **AND** each DeckCard schema includes full Card details
- **AND** cards are grouped by mainboard (sideboard=False) and sideboard (sideboard=True)

### Requirement: Deck Model Database Schema
The system SHALL create database tables for decks and deck_cards with proper constraints and indexes.

#### Scenario: Decks table schema
- **GIVEN** the database initialization is run
- **WHEN** the decks table is created
- **THEN** the table has columns: id (UUID primary key), name (string not null), format (string not null), created_at (timestamp), updated_at (timestamp)
- **AND** an index exists on the name column for fast lookups
- **AND** an index exists on the format column for filtering

#### Scenario: Deck_cards table schema
- **GIVEN** the database initialization is run
- **WHEN** the deck_cards table is created
- **THEN** the table has columns: deck_id (UUID FK), card_id (UUID FK), quantity (integer not null), sideboard (boolean not null)
- **AND** a composite primary key exists on (deck_id, card_id, sideboard)
- **AND** foreign key constraints exist for deck_id and card_id
- **AND** ON DELETE CASCADE is configured for deck_id foreign key

#### Scenario: Foreign key constraint enforcement
- **GIVEN** a deck with associated cards
- **WHEN** the deck is deleted
- **THEN** all associated deck_cards records are automatically deleted
- **AND** no orphaned deck_card records remain

### Requirement: Type Safety for Deck Operations
The system SHALL maintain strict type hints throughout deck models, schemas, and repository methods with mypy validation.

#### Scenario: DeckModel type hints
- **GIVEN** a DeckModel class definition
- **WHEN** mypy analyzes the model in strict mode
- **THEN** no type errors are reported
- **AND** all Mapped[] columns have explicit type annotations

#### Scenario: DeckRepository method type hints
- **GIVEN** DeckRepository method signatures
- **WHEN** mypy analyzes the repository in strict mode
- **THEN** no type errors are reported
- **AND** all methods have explicit return type hints (e.g., Deck | None, list[Deck])

#### Scenario: Pydantic schema type hints
- **GIVEN** Deck and DeckCard Pydantic schemas
- **WHEN** mypy analyzes the schemas in strict mode
- **THEN** no type errors are reported
- **AND** all fields have explicit type annotations

### Requirement: Unit Tests for Deck Models and Schemas
The system SHALL provide unit tests verifying deck model and schema creation and validation.

#### Scenario: Test DeckModel instantiation
- **GIVEN** a unit test for DeckModel
- **WHEN** creating a DeckModel instance with valid data
- **THEN** the instance is created without errors
- **AND** all fields are accessible with correct values
- **AND** timestamps are set automatically

#### Scenario: Test Deck schema validation
- **GIVEN** a unit test for Deck schema
- **WHEN** validating a dictionary with valid deck data
- **THEN** Deck.model_validate() succeeds
- **AND** the schema instance has all expected fields

#### Scenario: Test DeckCard schema with nested Card
- **GIVEN** a unit test for DeckCard schema
- **WHEN** validating data with nested card details
- **THEN** DeckCard.model_validate() succeeds
- **AND** the nested Card schema is properly instantiated

### Requirement: Integration Tests for DeckRepository
The system SHALL provide integration tests verifying end-to-end deck CRUD operations against a test database.

#### Scenario: Integration test deck creation and retrieval
- **GIVEN** an in-memory test database
- **WHEN** creating a deck and retrieving it by ID
- **THEN** the deck is persisted and retrieved successfully
- **AND** all fields match the created deck

#### Scenario: Integration test add and remove cards
- **GIVEN** a deck exists in the test database
- **WHEN** adding a card, retrieving the deck, then removing the card
- **THEN** the card is present after adding
- **AND** the card is absent after removing
- **AND** all operations complete without errors

#### Scenario: Integration test deck deletion cascade
- **GIVEN** a deck with multiple cards in the test database
- **WHEN** deleting the deck
- **THEN** the deck is removed
- **AND** all associated deck_card records are deleted
- **AND** the cards themselves remain in the cards table (no cascade to cards)

#### Scenario: Integration test list decks
- **GIVEN** multiple decks exist in the test database
- **WHEN** listing decks
- **THEN** all decks are returned in correct order (newest first)
- **AND** each deck schema is properly populated

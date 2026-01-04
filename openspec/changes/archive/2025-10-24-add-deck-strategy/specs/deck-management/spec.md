# Deck Management Spec Delta

## ADDED Requirements

### Requirement: Deck Strategy Field
The system SHALL support an optional `strategy` field on decks for storing strategic intent as free-form text.

#### Scenario: Create deck with strategy
- **GIVEN** a user wants to create a control deck
- **WHEN** create_deck(name="Control Deck", format="standard", strategy="Reactive control deck with counters and removal") is called
- **THEN** a deck is created with the specified strategy
- **AND** the strategy field contains "Reactive control deck with counters and removal"
- **AND** the strategy is persisted to the database

#### Scenario: Create deck without strategy
- **GIVEN** a user wants to create a deck without specifying strategy
- **WHEN** create_deck(name="Test Deck", format="standard") is called without strategy parameter
- **THEN** a deck is created successfully
- **AND** the strategy field is NULL
- **AND** the deck functions normally

#### Scenario: Update deck strategy
- **GIVEN** a deck exists with strategy="aggro"
- **WHEN** update_deck(deck_id="deck-123", strategy="Fast aggro with burn spells") is called
- **THEN** the deck strategy is updated to "Fast aggro with burn spells"
- **AND** the updated_at timestamp is refreshed
- **AND** the updated Deck schema is returned with new strategy

#### Scenario: Clear deck strategy
- **GIVEN** a deck exists with strategy="control"
- **WHEN** update_deck(deck_id="deck-123", strategy=None) is called
- **THEN** the deck strategy is set to NULL
- **AND** the deck no longer has an associated strategy

#### Scenario: Get deck with strategy
- **GIVEN** a deck exists with strategy="midrange value deck"
- **WHEN** get_deck(deck_id="deck-123") is called
- **THEN** the returned Deck schema includes strategy="midrange value deck"
- **AND** all other fields are populated correctly

### Requirement: Strategy Field Database Schema
The system SHALL store the strategy field as a nullable, indexed string column in the decks table.

#### Scenario: Strategy column schema
- **GIVEN** the database migration is applied
- **WHEN** inspecting the decks table schema
- **THEN** a strategy column exists with type String
- **AND** the column is nullable (NULL allowed)
- **AND** an index exists on the strategy column (ix_decks_strategy)

#### Scenario: Backward compatibility with existing decks
- **GIVEN** existing decks in the database before migration
- **WHEN** the migration adds the strategy column
- **THEN** all existing decks have strategy=NULL
- **AND** existing decks function normally
- **AND** no data migration is required

#### Scenario: Filter decks by strategy
- **GIVEN** multiple decks exist with various strategies
- **WHEN** querying decks with WHERE strategy LIKE '%control%'
- **THEN** only decks with "control" in their strategy are returned
- **AND** the indexed column enables efficient filtering

## MODIFIED Requirements

### Requirement: DeckRepository CRUD Operations
The system SHALL provide a `DeckRepository` with methods for creating, reading, updating, and deleting decks, including support for the strategy field.

#### Scenario: Create new deck
- **GIVEN** a DeckRepository instance with an active session
- **WHEN** create_deck(name="Mono Red Aggro", format="standard", strategy="Fast aggro") is called
- **THEN** a new deck is persisted to the database
- **AND** a Deck Pydantic schema is returned with generated id and timestamps
- **AND** the deck has no cards initially
- **AND** the strategy field is set to "Fast aggro"

#### Scenario: Get deck by ID
- **GIVEN** a deck exists in the database with id "deck-123"
- **WHEN** get_deck(deck_id="deck-123") is called
- **THEN** a Deck Pydantic schema is returned with all deck details
- **AND** the schema includes the list of deck cards
- **AND** the strategy field is included (may be NULL)

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
- **AND** the strategy field remains unchanged

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
- **AND** each deck includes its strategy field (may be NULL)

#### Scenario: List decks filtered by format
- **GIVEN** decks exist with formats "standard" and "commander"
- **WHEN** list_decks(format_filter="standard") is called
- **THEN** only Standard format decks are returned
- **AND** Commander decks are excluded
- **AND** strategy fields are included in results

# deck-management Delta

## MODIFIED Requirements

### Requirement: DeckRepository CRUD Operations
The system SHALL provide a `DeckRepository` with methods for creating, reading, updating, and deleting decks, including support for the strategy field. The list_decks method SHALL return enhanced metadata including deck colors, strategy, detailed card counts, and timestamps.

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

#### Scenario: List all decks with enhanced metadata
- **GIVEN** multiple decks exist in the database with cards
- **WHEN** list_decks() is called
- **THEN** a list of Deck Pydantic schemas is returned
- **AND** decks are ordered by created_at descending (newest first)
- **AND** each deck includes name, id, format, strategy
- **AND** each deck includes color_identity calculated from deck cards
- **AND** each deck includes mainboard_count and sideboard_count
- **AND** each deck includes created_at and updated_at timestamps
- **AND** each deck includes tags for win conditions and deck themes

#### Scenario: List decks filtered by format
- **GIVEN** decks exist with formats "standard" and "commander"
- **WHEN** list_decks(format_filter="standard") is called
- **THEN** only Standard format decks are returned
- **AND** Commander decks are excluded
- **AND** all enhanced metadata fields are included in results

## ADDED Requirements

### Requirement: Deck Timestamps
The system SHALL track creation and modification timestamps for all decks to support deck management and history tracking.

#### Scenario: New deck has current timestamps
- **GIVEN** a new deck is being created
- **WHEN** create_deck(name="Test Deck", format="standard") is called
- **THEN** created_at is set to current UTC timestamp
- **AND** updated_at is set to current UTC timestamp
- **AND** both timestamps are equal on initial creation

#### Scenario: Deck update refreshes timestamp
- **GIVEN** a deck exists with created_at "2025-01-01T00:00:00Z"
- **WHEN** any deck modification occurs (name change, cards added/removed)
- **THEN** updated_at is refreshed to current UTC timestamp
- **AND** created_at remains "2025-01-01T00:00:00Z"

### Requirement: Deck Tags and Win Conditions
The system SHALL support optional tags for decks to track win conditions, themes, and deck characteristics.

#### Scenario: Create deck with tags
- **GIVEN** a new deck is being created
- **WHEN** create_deck(name="Combo Deck", format="standard", tags=["combo", "infinite-loop"]) is called
- **THEN** the deck is created with the specified tags
- **AND** tags are persisted as a JSON array

#### Scenario: List decks shows tags
- **GIVEN** decks exist with various tags
- **WHEN** list_decks() is called
- **THEN** each deck includes its tags in the response
- **AND** decks without tags show empty array

### Requirement: Deck Color Identity Calculation
The system SHALL calculate and display deck color identity based on the color identity of all cards in the deck.

#### Scenario: Calculate color identity from cards
- **GIVEN** a deck contains cards with color identities ["R"], ["R", "G"], and ["R"]
- **WHEN** list_decks() is called
- **THEN** the deck's color_identity is ["R", "G"]
- **AND** colors are deduplicated and sorted

#### Scenario: Empty deck has no color identity
- **GIVEN** a deck has no cards
- **WHEN** list_decks() is called
- **THEN** the deck's color_identity is an empty array

### Requirement: Detailed Card Counts
The system SHALL provide separate counts for mainboard and sideboard cards in deck listings.

#### Scenario: Deck with mainboard and sideboard
- **GIVEN** a deck has 60 mainboard cards and 15 sideboard cards
- **WHEN** list_decks() is called
- **THEN** the deck shows mainboard_count=60
- **AND** the deck shows sideboard_count=15
- **AND** total_count=75

#### Scenario: Deck with only mainboard
- **GIVEN** a deck has 60 mainboard cards and 0 sideboard cards
- **WHEN** list_decks() is called
- **THEN** the deck shows mainboard_count=60
- **AND** the deck shows sideboard_count=0
- **AND** total_count=60

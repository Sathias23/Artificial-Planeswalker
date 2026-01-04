# data-layer Specification

## Purpose
TBD - created by archiving change story-1-2-database-models. Update Purpose after archive.
## Requirements
### Requirement: SQLAlchemy Async ORM Models
The system SHALL provide SQLAlchemy 2.0 async ORM models for Scryfall card data with proper type hints, async attribute access support, and image URI storage.

#### Scenario: Card model creation with required fields
- **GIVEN** a Scryfall card JSON object with core fields (id, name, mana_cost, type_line, oracle_text)
- **WHEN** the CardModel is instantiated with these fields
- **THEN** the model instance is created successfully with all fields accessible
- **AND** the model supports async attribute access via AsyncAttrs mixin

#### Scenario: Card model with optional fields
- **GIVEN** a Scryfall card with optional fields (color_indicator, keywords, card_faces, image_uris)
- **WHEN** the CardModel is instantiated
- **THEN** optional fields are set to None when not provided
- **AND** optional fields accept their expected types when provided

#### Scenario: Multi-face card support
- **GIVEN** a double-faced card from Scryfall with card_faces array
- **WHEN** the CardModel stores the card_faces data in JSON column
- **THEN** the card_faces data is preserved with all face details
- **AND** the data can be retrieved as a Python list of dictionaries

#### Scenario: Image URIs storage
- **GIVEN** a Scryfall card with image_uris object containing image URLs
- **WHEN** the CardModel stores the image_uris in JSON column
- **THEN** the image_uris object is preserved with all size variants (small, normal, large, png, art_crop, border_crop)
- **AND** the data can be retrieved as a Python dictionary

#### Scenario: Card without image URIs
- **GIVEN** a Scryfall card without image_uris field (e.g., double-faced card)
- **WHEN** the CardModel is instantiated with image_uris=None
- **THEN** the model instance is created successfully
- **AND** the image_uris field is None

### Requirement: Pydantic Schema for Type-Safe Data Transfer
The system SHALL provide Pydantic schemas corresponding to SQLAlchemy models for type-safe data transfer between application layers, including image URI data.

#### Scenario: Convert SQLAlchemy model to Pydantic schema
- **GIVEN** a CardModel instance retrieved from the database with image_uris populated
- **WHEN** Card.model_validate() is called with the CardModel instance
- **THEN** a Card Pydantic schema is returned with all fields populated including image_uris
- **AND** the schema passes Pydantic validation

#### Scenario: Pydantic schema enforces type constraints
- **GIVEN** a Card Pydantic schema definition
- **WHEN** instantiating with invalid types (e.g., cmc as string instead of float)
- **THEN** Pydantic raises a ValidationError
- **AND** the error message indicates the field and expected type

#### Scenario: Pydantic schema handles optional fields
- **GIVEN** a Card schema with optional fields (keywords, card_faces, color_indicator, image_uris)
- **WHEN** instantiating without these fields
- **THEN** the schema instance is created with optional fields set to None
- **AND** no validation errors are raised

#### Scenario: Pydantic schema with image URIs
- **GIVEN** a Card Pydantic schema with image_uris field
- **WHEN** instantiating with image_uris dictionary containing valid URLs
- **THEN** the schema instance is created successfully
- **AND** the image_uris field contains the provided dictionary

### Requirement: Async Database Engine and Session Management
The system SHALL provide an async database engine and session factory configured for SQLite with proper lifecycle management.

#### Scenario: Create async database engine
- **GIVEN** a DATABASE_URL environment variable with SQLite connection string
- **WHEN** the create_async_engine() function is called
- **THEN** an AsyncEngine instance is created successfully
- **AND** the engine is configured for aiosqlite driver

#### Scenario: Create async session factory
- **GIVEN** an AsyncEngine instance
- **WHEN** async_sessionmaker is configured with expire_on_commit=False
- **THEN** a session factory is created
- **AND** sessions created by the factory do not expire objects after commit

#### Scenario: Session context manager lifecycle
- **GIVEN** an async session factory
- **WHEN** using async with to create a session context
- **THEN** the session is created on entry
- **AND** the session is automatically closed on exit
- **AND** exceptions are propagated after session cleanup

### Requirement: Database Initialization
The system SHALL provide a database initialization function that creates all tables from SQLAlchemy model metadata.

#### Scenario: Initialize database schema
- **GIVEN** SQLAlchemy models are defined with metadata
- **WHEN** init_database() is called with an async engine
- **THEN** all tables are created in the SQLite database
- **AND** the database file exists at the configured path

#### Scenario: Initialize database idempotently
- **GIVEN** a database with existing schema
- **WHEN** init_database() is called again
- **THEN** no errors are raised
- **AND** existing tables remain unchanged

#### Scenario: Database initialization with in-memory SQLite
- **GIVEN** a DATABASE_URL for in-memory SQLite (:memory:)
- **WHEN** init_database() is called
- **THEN** tables are created in memory
- **AND** the database is available for testing

### Requirement: Repository Pattern Base Interface
The system SHALL provide a base repository class defining the interface for data access operations.

#### Scenario: BaseRepository initialization
- **GIVEN** an AsyncSession instance
- **WHEN** BaseRepository is instantiated with the session
- **THEN** the repository stores the session for database operations
- **AND** the repository provides access to the session

#### Scenario: Repository session lifecycle
- **GIVEN** a repository instance with an active session
- **WHEN** database operations are performed through the repository
- **THEN** the repository uses the injected session
- **AND** the session remains valid for the repository's lifetime

### Requirement: Card Schema Field Mapping
The system SHALL map Scryfall card JSON fields to SQLAlchemy model columns with appropriate types and constraints, including image URI data.

#### Scenario: Core card fields mapping
- **GIVEN** Scryfall card JSON with id, name, mana_cost, cmc, type_line, oracle_text
- **WHEN** these fields are mapped to CardModel columns
- **THEN** id is stored as String (UUID) primary key
- **AND** name is stored as String with index and not-null constraint
- **AND** cmc is stored as Float
- **AND** type_line and oracle_text are stored as String

#### Scenario: Color fields mapping
- **GIVEN** Scryfall card with colors, color_identity, color_indicator arrays
- **WHEN** these fields are mapped to CardModel columns
- **THEN** colors is stored as JSON array
- **AND** color_identity is stored as JSON array
- **AND** color_indicator is stored as optional JSON array

#### Scenario: Legalities field mapping
- **GIVEN** Scryfall card with legalities object (Standard: legal, Modern: not_legal)
- **WHEN** the legalities field is mapped to CardModel column
- **THEN** legalities is stored as JSON object
- **AND** the JSON preserves format names as keys and legality status as values

#### Scenario: Keywords and set info mapping
- **GIVEN** Scryfall card with keywords array, set, collector_number, rarity
- **WHEN** these fields are mapped to CardModel columns
- **THEN** keywords is stored as JSON array
- **AND** set, collector_number, and rarity are stored as String columns

#### Scenario: Image URIs field mapping
- **GIVEN** Scryfall card with image_uris object containing size-variant URLs
- **WHEN** the image_uris field is mapped to CardModel column
- **THEN** image_uris is stored as optional JSON object
- **AND** the JSON preserves all size keys (small, normal, large, png, art_crop, border_crop) and URL values
- **AND** cards without image_uris store NULL in this column

### Requirement: Database Health Check
The system SHALL provide a health check function to verify database connectivity and basic operations.

#### Scenario: Health check with successful INSERT and SELECT
- **GIVEN** an initialized database with schema
- **WHEN** health_check() creates a test CardModel record and queries it back
- **THEN** the INSERT operation succeeds
- **AND** the SELECT operation retrieves the test record
- **AND** the health check returns True

#### Scenario: Health check with database connection failure
- **GIVEN** an invalid DATABASE_URL or inaccessible database
- **WHEN** health_check() attempts to connect
- **THEN** a connection error is raised
- **AND** the health check returns False or raises an exception

#### Scenario: Health check cleanup
- **GIVEN** a health check test record inserted into the database
- **WHEN** the health check completes
- **THEN** the test record is deleted
- **AND** the database is left in a clean state

### Requirement: Type Safety and Mypy Compliance
The system SHALL maintain strict type hints throughout the data layer with mypy validation enabled.

#### Scenario: SQLAlchemy model type hints
- **GIVEN** a CardModel class definition
- **WHEN** mypy analyzes the model in strict mode
- **THEN** no type errors are reported
- **AND** all Mapped[] columns have explicit type annotations

#### Scenario: Pydantic schema type hints
- **GIVEN** a Card Pydantic schema definition
- **WHEN** mypy analyzes the schema in strict mode
- **THEN** no type errors are reported
- **AND** all fields have explicit type annotations with Optional[] for nullable fields

#### Scenario: Repository method type hints
- **GIVEN** a BaseRepository class with method signatures
- **WHEN** mypy analyzes the repository in strict mode
- **THEN** no type errors are reported
- **AND** async method return types use proper type hints (e.g., Card | None)

### Requirement: Unit Test Coverage for Models and Sessions
The system SHALL provide unit tests verifying model creation, validation, and session management without requiring database I/O.

#### Scenario: Test CardModel instantiation
- **GIVEN** a unit test for CardModel
- **WHEN** creating a CardModel instance with valid data
- **THEN** the instance is created without errors
- **AND** all fields are accessible with correct values

#### Scenario: Test Pydantic schema validation
- **GIVEN** a unit test for Card schema
- **WHEN** validating a dictionary with valid card data
- **THEN** Card.model_validate() succeeds
- **AND** the schema instance has all expected fields

#### Scenario: Test session factory configuration
- **GIVEN** a unit test for session factory creation
- **WHEN** async_sessionmaker is configured
- **THEN** the factory is created with expire_on_commit=False
- **AND** the factory produces AsyncSession instances

### Requirement: Integration Test for Database Operations
The system SHALL provide integration tests verifying end-to-end database operations including INSERT, SELECT, and health check.

#### Scenario: Integration test with in-memory database
- **GIVEN** an in-memory SQLite database (:memory:)
- **WHEN** the integration test initializes the database and performs operations
- **THEN** tables are created successfully
- **AND** INSERT and SELECT operations execute without errors
- **AND** the test completes with database cleanup

#### Scenario: Integration test health check validation
- **GIVEN** an initialized test database
- **WHEN** the health check function is executed
- **THEN** a test card is inserted and retrieved successfully
- **AND** the health check returns True
- **AND** the test card is cleaned up

#### Scenario: Integration test session lifecycle
- **GIVEN** a repository with an async session
- **WHEN** performing multiple database operations within a session context
- **THEN** all operations use the same session
- **AND** the session is closed properly after operations complete

### Requirement: Format Legality Filtering

The CardRepository SHALL provide methods to filter card queries by Magic: The Gathering format legality using Scryfall's `legalities` JSON field.

#### Scenario: Query Standard-legal cards only

- **GIVEN** cards exist with various legalities in the database
- **WHEN** a query method is called with `format_filter="standard"`
- **THEN** only cards with `legalities.standard = "legal"` are returned
- **AND** cards with `legalities.standard = "not_legal"` or `"banned"` are excluded

#### Scenario: Query without format filter

- **GIVEN** cards exist with various legalities in the database
- **WHEN** a query method is called with `format_filter=None`
- **THEN** all matching cards are returned regardless of format legality
- **AND** no legality filtering is applied

#### Scenario: Format filter with exact name search

- **GIVEN** a card "Sol Ring" exists with `legalities.standard = "not_legal"`
- **AND** a card "Lightning Bolt" exists with `legalities.standard = "legal"`
- **WHEN** `find_by_name_exact("Sol Ring", format_filter="standard")` is called
- **THEN** None is returned (card is not Standard-legal)
- **WHEN** `find_by_name_exact("Lightning Bolt", format_filter="standard")` is called
- **THEN** the card is returned (card is Standard-legal)

#### Scenario: Format filter with partial name search

- **GIVEN** cards "Lightning Bolt" (Standard: legal), "Lightning Strike" (Standard: not_legal), "Chain Lightning" (Standard: not_legal) exist
- **WHEN** `find_by_name_partial("lightning", format_filter="standard")` is called
- **THEN** only "Lightning Bolt" is returned in the list
- **AND** "Lightning Strike" and "Chain Lightning" are excluded

#### Scenario: Format filter with color search

- **GIVEN** red cards exist with mixed Standard legality
- **WHEN** `find_by_colors("R", format_filter="standard")` is called
- **THEN** only red cards with `legalities.standard = "legal"` are returned

#### Scenario: Format filter with type search

- **GIVEN** instant cards exist with mixed Standard legality
- **WHEN** `find_by_type("Instant", format_filter="standard")` is called
- **THEN** only instant cards with `legalities.standard = "legal"` are returned

#### Scenario: Handle cards with missing legalities field

- **GIVEN** a card exists without a `legalities` field in JSON
- **WHEN** a query with `format_filter="standard"` is executed
- **THEN** the card is excluded from results (treated as not legal)

### Requirement: Format Filter Type Safety

All format filtering parameters SHALL be type-safe with explicit type hints for supported formats.

#### Scenario: Format filter accepts valid format strings

- **GIVEN** a repository query method with format_filter parameter
- **WHEN** the method signature is analyzed
- **THEN** the format_filter parameter has type hint `Literal["standard"] | None`
- **AND** mypy validates only "standard" or None can be passed

#### Scenario: Format filter extensibility

- **GIVEN** the format_filter type definition
- **WHEN** future formats need to be added (e.g., "modern", "commander")
- **THEN** the Literal type can be extended without breaking existing code
- **AND** the type system enforces valid format strings at compile time

### Requirement: Repository Transaction Management with Rollback Handling

The system SHALL implement explicit transaction management in all repository write operations with proper rollback handling to prevent rolled-back session state from affecting subsequent operations.

#### Scenario: Write operation with IntegrityError triggers rollback

- **GIVEN** a DeckRepository with an active async session
- **WHEN** a write operation (e.g., add_card_to_deck) triggers an IntegrityError due to a UNIQUE constraint violation
- **THEN** the repository SHALL catch the IntegrityError
- **AND** call `await session.rollback()` to explicitly roll back the transaction
- **AND** re-raise the IntegrityError for upper layers to handle

#### Scenario: Write operation with database error triggers rollback

- **GIVEN** a DeckRepository performing a write operation
- **WHEN** a database-level exception occurs (e.g., OperationalError, DatabaseError)
- **THEN** the repository SHALL catch the exception
- **AND** call `await session.rollback()` to clean up the transaction state
- **AND** re-raise the original exception with preserved exception chain

#### Scenario: Multiple write operations in sequence after rollback

- **GIVEN** a repository session that has experienced a rollback due to an IntegrityError
- **WHEN** a subsequent write operation is attempted on the same session
- **THEN** the session SHALL be in a clean state (not rolled-back)
- **AND** the write operation SHALL execute successfully without "transaction has been rolled back" errors

#### Scenario: Read operation after write operation rollback

- **GIVEN** a repository session that has been rolled back due to a write operation error
- **WHEN** a read operation (e.g., get_deck_with_cards) is executed on the same session
- **THEN** the read operation SHALL execute successfully
- **AND** return accurate data from the database

#### Scenario: Transaction isolation in concurrent tool execution

- **GIVEN** multiple PydanticAI tools executing in sequence within a single request
- **AND** all tools share the same repository session
- **WHEN** the first tool triggers a rollback
- **THEN** subsequent tools SHALL NOT fail due to the rolled-back session state
- **AND** each tool's database operations SHALL execute independently

### Requirement: Repository Error Logging with Transaction Context

The system SHALL log transaction errors with sufficient context for debugging while preserving the original exception chain.

#### Scenario: IntegrityError logged with operation context

- **GIVEN** a repository write operation that triggers an IntegrityError
- **WHEN** the error is caught and rolled back
- **THEN** the system SHALL log the error with:
  - The repository method name
  - The operation being attempted (e.g., "add_card_to_deck")
  - The original exception message
- **AND** the logged error SHALL be at WARNING level
- **AND** the original exception SHALL be preserved for re-raising

#### Scenario: Database error logged with session state

- **GIVEN** a repository operation that encounters a database error
- **WHEN** the error is caught and rolled back
- **THEN** the system SHALL log the session state before rollback:
  - Whether the session was in a transaction
  - Whether the session had uncommitted changes
- **AND** the logged error SHALL be at ERROR level

### Requirement: Deck Merging Operations

The system SHALL provide a repository method to merge cards from a source deck into a target deck with configurable merge strategies.

#### Scenario: Merge decks with COMBINE strategy

- **GIVEN** a target deck contains 2 copies of "Lightning Bolt" in mainboard
- **AND** a source deck contains 3 copies of "Lightning Bolt" in mainboard
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck contains 5 copies of "Lightning Bolt" in mainboard
- **AND** the source deck remains unchanged (2 copies)
- **AND** the target deck's updated_at timestamp is refreshed
- **AND** an updated Deck schema is returned

#### Scenario: Merge decks with MAXIMUM strategy

- **GIVEN** a target deck contains 2 copies of "Lightning Bolt" in mainboard
- **AND** a source deck contains 3 copies of "Lightning Bolt" in mainboard
- **WHEN** `merge_decks(target_id, source_id, strategy="MAXIMUM")` is called
- **THEN** the target deck contains 3 copies of "Lightning Bolt" in mainboard (max of 2 and 3)
- **AND** the source deck remains unchanged
- **AND** the target deck's updated_at timestamp is refreshed
- **AND** an updated Deck schema is returned

#### Scenario: Merge decks with REPLACE strategy

- **GIVEN** a target deck contains 2 copies of "Lightning Bolt" in mainboard
- **AND** a source deck contains 3 copies of "Lightning Bolt" in mainboard
- **WHEN** `merge_decks(target_id, source_id, strategy="REPLACE")` is called
- **THEN** the target deck contains 3 copies of "Lightning Bolt" in mainboard (replaced with source quantity)
- **AND** the source deck remains unchanged
- **AND** the target deck's updated_at timestamp is refreshed
- **AND** an updated Deck schema is returned

#### Scenario: Merge decks with disjoint card sets

- **GIVEN** a target deck contains "Lightning Bolt" in mainboard
- **AND** a source deck contains "Shock" in mainboard (no overlap with target)
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck contains both "Lightning Bolt" and "Shock" in mainboard
- **AND** quantities match the original decks (no cards existed in both decks)
- **AND** the source deck remains unchanged

#### Scenario: Merge decks respects mainboard/sideboard separation

- **GIVEN** a target deck contains "Lightning Bolt" with 4 copies in mainboard
- **AND** a source deck contains "Lightning Bolt" with 2 copies in sideboard
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck contains 4 copies in mainboard (unchanged)
- **AND** the target deck contains 2 copies in sideboard (added from source)
- **AND** mainboard and sideboard cards are tracked separately (no cross-contamination)

#### Scenario: Merge updates deck color identity

- **GIVEN** a target deck contains only red cards (color_identity = ["R"])
- **AND** a source deck contains only blue cards (color_identity = ["U"])
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck's color_identity is updated to ["R", "U"]
- **AND** colors are sorted in WUBRG order
- **AND** the updated Deck schema reflects the new color_identity

#### Scenario: Merge with non-existent target deck

- **GIVEN** no deck exists with target_id "invalid-id"
- **WHEN** `merge_decks(target_id="invalid-id", source_id="valid-source", strategy="COMBINE")` is called
- **THEN** None is returned
- **AND** no database modifications occur
- **AND** no exceptions are raised

#### Scenario: Merge with non-existent source deck

- **GIVEN** no deck exists with source_id "invalid-id"
- **WHEN** `merge_decks(target_id="valid-target", source_id="invalid-id", strategy="COMBINE")` is called
- **THEN** None is returned
- **AND** the target deck remains unchanged
- **AND** no exceptions are raised

#### Scenario: Merge with empty source deck

- **GIVEN** a target deck contains cards
- **AND** a source deck exists but has no cards (deck_cards is empty)
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck remains unchanged (no cards added)
- **AND** the updated Deck schema is returned
- **AND** the updated_at timestamp is refreshed (operation occurred)

#### Scenario: Merge with empty target deck

- **GIVEN** a target deck exists but has no cards
- **AND** a source deck contains 4 copies of "Lightning Bolt"
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck contains 4 copies of "Lightning Bolt"
- **AND** quantities match the source deck (COMBINE with 0 yields source quantity)
- **AND** the source deck remains unchanged

#### Scenario: Merge transaction rollback on IntegrityError

- **GIVEN** a merge operation triggers an IntegrityError (e.g., database constraint violation)
- **WHEN** the repository catches the IntegrityError
- **THEN** the session is explicitly rolled back via `await session.rollback()`
- **AND** the IntegrityError is re-raised for upper layers to handle
- **AND** the session is left in a clean state (not rolled-back)
- **AND** subsequent operations on the same session succeed

#### Scenario: Merge transaction rollback on DatabaseError

- **GIVEN** a merge operation encounters a database-level error
- **WHEN** the repository catches the DatabaseError
- **THEN** the session is explicitly rolled back
- **AND** the error is logged with operation context (target_id, source_id, strategy)
- **AND** the original exception is re-raised with preserved exception chain
- **AND** the session is left in a clean state

### Requirement: Merge Strategy Type Safety

The system SHALL define a type-safe merge strategy parameter with explicit valid values.

#### Scenario: Merge strategy accepts valid strategy strings

- **GIVEN** the `merge_decks()` method signature
- **WHEN** the method is called with strategy="COMBINE", "MAXIMUM", or "REPLACE"
- **THEN** the method executes successfully
- **AND** mypy validates only valid strategy strings can be passed

#### Scenario: Merge strategy type definition

- **GIVEN** the merge strategy parameter type
- **WHEN** analyzing with mypy in strict mode
- **THEN** the parameter has type hint `Literal["COMBINE", "MAXIMUM", "REPLACE"]` or Enum
- **AND** passing invalid strategy strings causes type errors
- **AND** the type system enforces valid strategies at compile time

### Requirement: Merge Operation Logging

The system SHALL log deck merge operations with sufficient context for debugging and audit trails.

#### Scenario: Successful merge operation logged

- **GIVEN** a merge operation completes successfully
- **WHEN** the operation finishes
- **THEN** the system logs at INFO level with:
  - Target deck ID
  - Source deck ID
  - Merge strategy used
  - Number of cards merged
  - Number of new cards added to target
- **AND** the log message is concise and parseable

#### Scenario: Merge error logged with context

- **GIVEN** a merge operation encounters an error
- **WHEN** the error is caught
- **THEN** the system logs at ERROR level with:
  - Target deck ID
  - Source deck ID
  - Merge strategy
  - Session transaction state
  - Original exception message
- **AND** the log includes sufficient context for debugging


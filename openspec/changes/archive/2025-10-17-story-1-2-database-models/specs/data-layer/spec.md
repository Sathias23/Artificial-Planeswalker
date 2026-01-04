# Data Layer Specification

## ADDED Requirements

### Requirement: SQLAlchemy Async ORM Models
The system SHALL provide SQLAlchemy 2.0 async ORM models for Scryfall card data with proper type hints and async attribute access support.

#### Scenario: Card model creation with required fields
- **GIVEN** a Scryfall card JSON object with core fields (id, name, mana_cost, type_line, oracle_text)
- **WHEN** the CardModel is instantiated with these fields
- **THEN** the model instance is created successfully with all fields accessible
- **AND** the model supports async attribute access via AsyncAttrs mixin

#### Scenario: Card model with optional fields
- **GIVEN** a Scryfall card with optional fields (color_indicator, keywords, card_faces)
- **WHEN** the CardModel is instantiated
- **THEN** optional fields are set to None when not provided
- **AND** optional fields accept their expected types when provided

#### Scenario: Multi-face card support
- **GIVEN** a double-faced card from Scryfall with card_faces array
- **WHEN** the CardModel stores the card_faces data in JSON column
- **THEN** the card_faces data is preserved with all face details
- **AND** the data can be retrieved as a Python list of dictionaries

### Requirement: Pydantic Schema for Type-Safe Data Transfer
The system SHALL provide Pydantic schemas corresponding to SQLAlchemy models for type-safe data transfer between application layers.

#### Scenario: Convert SQLAlchemy model to Pydantic schema
- **GIVEN** a CardModel instance retrieved from the database
- **WHEN** Card.model_validate() is called with the CardModel instance
- **THEN** a Card Pydantic schema is returned with all fields populated
- **AND** the schema passes Pydantic validation

#### Scenario: Pydantic schema enforces type constraints
- **GIVEN** a Card Pydantic schema definition
- **WHEN** instantiating with invalid types (e.g., cmc as string instead of float)
- **THEN** Pydantic raises a ValidationError
- **AND** the error message indicates the field and expected type

#### Scenario: Pydantic schema handles optional fields
- **GIVEN** a Card schema with optional fields (keywords, card_faces, color_indicator)
- **WHEN** instantiating without these fields
- **THEN** the schema instance is created with optional fields set to None
- **AND** no validation errors are raised

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
The system SHALL map Scryfall card JSON fields to SQLAlchemy model columns with appropriate types and constraints.

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

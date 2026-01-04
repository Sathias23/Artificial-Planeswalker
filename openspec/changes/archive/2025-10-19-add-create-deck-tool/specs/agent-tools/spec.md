## ADDED Requirements

### Requirement: Create Deck Tool
The system SHALL provide a `create_deck` PydanticAI tool that enables users to create new decks through natural language conversation.

#### Scenario: Create deck with name only
- **GIVEN** the agent has `create_deck` tool registered
- **WHEN** user says "create a new deck called Mono Red Aggro"
- **THEN** the agent invokes `create_deck` tool with name="Mono Red Aggro" and default format="standard"
- **AND** a new deck is created in the database
- **AND** the agent responds with confirmation including deck name and ID
- **AND** the deck ID is stored as the active deck in session context

#### Scenario: Create deck with explicit format
- **GIVEN** the agent has `create_deck` tool registered
- **WHEN** user says "create a commander deck named Dragon Tribal"
- **THEN** the agent invokes `create_deck` tool with name="Dragon Tribal" and format="commander"
- **AND** a new deck is created with the specified format
- **AND** the agent confirms the deck creation with format information

#### Scenario: Create deck and track in session
- **GIVEN** the agent has an active session with session_id
- **WHEN** a deck is created via the tool
- **THEN** the tool calls `_session_manager.set_active_deck_id(session_id, deck_id)`
- **AND** the deck ID is stored in session manager
- **AND** subsequent messages in the session will have `deps.active_deck_id` populated

#### Scenario: Handle duplicate deck names
- **GIVEN** a deck named "Test Deck" already exists
- **WHEN** user says "create a deck called Test Deck"
- **THEN** the tool creates a new deck with duplicate name allowed
- **AND** the agent confirms creation and mentions duplicate name scenario
- **OR** the tool appends a timestamp/counter suffix (e.g., "Test Deck 2")
- **AND** the agent confirms creation with the modified name

#### Scenario: Invalid format parameter
- **GIVEN** the agent attempts to create a deck with an invalid format
- **WHEN** the tool is invoked with format="invalid_format"
- **THEN** Pydantic validation raises a ValidationError
- **AND** the agent responds with a helpful error message listing valid formats

#### Scenario: Database error during creation
- **GIVEN** the database is unavailable or encounters an error
- **WHEN** the tool attempts to create a deck
- **THEN** the tool catches the exception
- **AND** the agent responds with an error message asking user to retry
- **AND** no active deck ID is stored in session manager

### Requirement: Deck Repository in Agent Dependencies
The system SHALL provide `DeckRepository` and `active_deck_id` as part of `AgentDependencies` for deck tool access to database operations and session state.

#### Scenario: DeckRepository available in tools
- **GIVEN** an agent tool requires deck database access
- **WHEN** the tool is invoked with `deps: AgentDependencies` parameter
- **THEN** `deps.deck_repository` is available and initialized
- **AND** the repository can perform CRUD operations

#### Scenario: Active deck ID available in dependencies
- **GIVEN** a session has an active deck set
- **WHEN** `get_agent_dependencies(session_id)` creates dependencies
- **THEN** `deps.active_deck_id` contains the stored deck ID
- **AND** tools can access the active deck without additional lookups

#### Scenario: DeckRepository lifecycle
- **GIVEN** a user message is being processed by the agent
- **WHEN** `get_agent_dependencies()` context manager is used
- **THEN** a `DeckRepository` instance is created with the session
- **AND** `active_deck_id` is retrieved from session manager
- **AND** the repository is properly cleaned up when the context exits

### Requirement: Active Deck Session Management
The system SHALL maintain active deck state through `ConversationSessionManager` to enable deck building operations across multiple conversation turns.

#### Scenario: Set active deck on creation
- **GIVEN** a user creates a new deck
- **WHEN** the `create_deck` tool completes successfully
- **THEN** `_session_manager.set_active_deck_id(session_id, deck_id)` is called
- **AND** the active deck ID persists in session storage

#### Scenario: Retrieve active deck in new dependencies
- **GIVEN** a session has an active deck set from a previous message
- **WHEN** `get_agent_dependencies(session_id)` creates new dependencies
- **THEN** `active_deck_id` is retrieved from session manager
- **AND** `deps.active_deck_id` is populated with the stored deck ID

#### Scenario: Active deck persists across conversation turns
- **GIVEN** a deck was created and set as active in a previous message
- **WHEN** the user sends a new message in the same session
- **THEN** the active deck ID is retrieved from `_session_manager`
- **AND** `deps.active_deck_id` contains the deck ID for subsequent tools

#### Scenario: New session has no active deck
- **GIVEN** a user starts a new chat session
- **WHEN** `get_agent_dependencies(session_id)` is called for the first time
- **THEN** `_session_manager.get_active_deck_id(session_id)` returns None
- **AND** `deps.active_deck_id` is None until a deck is created or loaded

#### Scenario: Clear active deck
- **GIVEN** a session has an active deck set
- **WHEN** a tool calls `_session_manager.clear_active_deck_id(session_id)`
- **THEN** the active deck ID is removed from session storage
- **AND** subsequent calls to `get_active_deck_id(session_id)` return None

### Requirement: Create Deck Tool Type Safety
The system SHALL maintain strict type hints for the `create_deck` tool with mypy validation.

#### Scenario: Tool function type hints
- **GIVEN** the `create_deck` tool function definition
- **WHEN** mypy analyzes the function in strict mode
- **THEN** no type errors are reported
- **AND** all parameters have explicit type annotations
- **AND** the return type is explicitly declared

#### Scenario: Dependency injection type hints
- **GIVEN** the tool accepts `deps: AgentDependencies`
- **WHEN** mypy analyzes the dependency injection
- **THEN** no type errors are reported
- **AND** `deps.deck_repository` is recognized as `DeckRepository` type

### Requirement: Create Deck Tool Unit Tests
The system SHALL provide unit tests verifying deck creation tool behavior with mocked dependencies.

#### Scenario: Test successful deck creation
- **GIVEN** a unit test with mocked DeckRepository and mocked session manager
- **WHEN** `create_deck` is called with name="Test Deck"
- **THEN** the repository's `create_deck` method is called once
- **AND** `_session_manager.set_active_deck_id` is called with the deck ID
- **AND** a confirmation message is returned

#### Scenario: Test duplicate name handling
- **GIVEN** a unit test with mocked repository
- **WHEN** creating a deck with a duplicate name
- **THEN** the tool handles the scenario per design decision
- **AND** the test verifies the expected behavior (allow duplicate or append suffix)

#### Scenario: Test error handling
- **GIVEN** a unit test with mocked repository that raises an exception
- **WHEN** `create_deck` is called
- **THEN** the tool catches the exception
- **AND** returns an error message
- **AND** `_session_manager.set_active_deck_id` is NOT called

### Requirement: Create Deck Tool Integration Tests
The system SHALL provide integration tests verifying end-to-end deck creation through the agent with a test database.

#### Scenario: End-to-end deck creation via agent
- **GIVEN** an integration test with test database and agent instance
- **WHEN** agent processes natural language input "create deck named Integration Test"
- **THEN** the `create_deck` tool is invoked
- **AND** a deck is persisted to the test database
- **AND** the deck can be retrieved by ID

#### Scenario: Multiple deck creations in session
- **GIVEN** an integration test with test database and session manager
- **WHEN** creating multiple decks in sequence
- **THEN** each deck is persisted with unique ID
- **AND** the active deck ID in session manager updates to the most recently created deck
- **AND** all decks are retrievable from the database
- **AND** `deps.active_deck_id` reflects the latest deck ID

#### Scenario: Natural language variations
- **GIVEN** an integration test with the agent
- **WHEN** using various phrasings ("create deck X", "new deck called Y", "make a deck named Z")
- **THEN** all variations successfully invoke the tool
- **AND** decks are created for each variation
- **AND** the agent responds appropriately to each phrasing

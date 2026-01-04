# agent-tools Specification Changes

## ADDED Requirements

### Requirement: Tool-Level Session State Management for Write Operations

The agent SHALL implement defensive session state validation in all deck write tools to ensure clean transaction state before executing database operations.

#### Scenario: Deck write tool validates session state before operation

- **GIVEN** a deck write tool (add_card_to_deck, remove_card_from_deck, update_card_quantity, create_deck, delete_deck)
- **WHEN** the tool begins execution
- **THEN** the tool SHALL check if the repository session has an active rolled-back transaction
- **AND** if rolled back, the tool SHALL call `await session.rollback()` to clear the state
- **AND** proceed with the intended operation

#### Scenario: Tool executes after previous tool's rollback

- **GIVEN** a PydanticAI agent execution with multiple deck write tools in sequence
- **AND** the first tool triggers an IntegrityError and rolls back the session
- **WHEN** the second tool begins execution
- **THEN** the second tool SHALL detect the rolled-back session state
- **AND** clear the state with a defensive rollback
- **AND** execute its database operation successfully

#### Scenario: Deck write tool handles IntegrityError gracefully

- **GIVEN** a deck write tool that encounters an IntegrityError (e.g., duplicate card)
- **WHEN** the repository raises the IntegrityError after rolling back
- **THEN** the tool SHALL catch the IntegrityError
- **AND** return a user-friendly error message (e.g., "Card is already in your deck")
- **AND** NOT re-raise the exception to the agent runtime

#### Scenario: Deck read tool unaffected by rolled-back session

- **GIVEN** a deck read tool (view_deck, list_decks) executing after a write tool's rollback
- **WHEN** the read tool executes on the same session
- **THEN** the read tool SHALL execute successfully without session state errors
- **AND** return accurate deck data from the database

### Requirement: UI Layer Session Lifecycle Management

The system SHALL implement session lifecycle management in the UI layer to ensure clean session state at request boundaries.

#### Scenario: Session factory provides clean session state

- **GIVEN** the UI layer's `get_agent_dependencies()` context manager
- **WHEN** the context manager enters and creates a new session
- **THEN** the session SHALL be in a clean state (no active rolled-back transactions)
- **AND** if the session has a pending rolled-back transaction, it SHALL be cleared with `await session.rollback()`

#### Scenario: Session factory handles tool execution errors

- **GIVEN** the UI layer's `get_agent_dependencies()` context manager
- **AND** agent tools are executing within the context
- **WHEN** any tool raises an exception during execution
- **THEN** the context manager SHALL catch the exception
- **AND** call `await session.rollback()` to clean up the session
- **AND** re-raise the exception for the message handler to process

#### Scenario: Session factory cleans up on context exit

- **GIVEN** the UI layer's `get_agent_dependencies()` context manager
- **WHEN** the context manager exits (normally or via exception)
- **THEN** the session SHALL be closed properly
- **AND** any uncommitted transactions SHALL be rolled back automatically by SQLAlchemy
- **AND** the session SHALL be returned to the session pool

### Requirement: Improved Error Messages for Transaction Failures

The agent SHALL provide clear, actionable error messages when database transaction failures occur.

#### Scenario: IntegrityError translated to user-friendly message

- **GIVEN** a deck write tool that catches an IntegrityError
- **WHEN** the error is due to a UNIQUE constraint violation (duplicate card)
- **THEN** the tool SHALL return a message like "This card is already in your deck"
- **AND** the message SHALL NOT include SQL error codes or technical details

#### Scenario: Rolled-back session error translated to actionable advice

- **GIVEN** a tool that encounters a "transaction has been rolled back" error
- **WHEN** the error propagates to the user
- **THEN** the error message SHALL suggest trying the operation again
- **AND** include guidance like "Please try again or contact support if this issue persists"
- **AND** NOT expose SQLAlchemy internal error messages

# data-layer Specification Changes

## ADDED Requirements

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

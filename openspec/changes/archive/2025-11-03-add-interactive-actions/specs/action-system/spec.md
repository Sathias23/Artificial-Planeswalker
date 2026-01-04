# action-system Specification Delta

**Target Spec:** `chainlit-ui`

## ADDED Requirements

### Requirement: Action Callback Infrastructure
The system SHALL provide infrastructure for registering and executing Chainlit action callbacks with error handling and logging.

#### Scenario: Action callback decorator registration
- **WHEN** an action callback is defined using `@cl.action_callback("action_name")`
- **THEN** the callback is registered with Chainlit's action router
- **AND** the callback name must exactly match the action name used in cl.Action instances
- **AND** the callback accepts a single parameter of type `cl.Action`
- **AND** the callback is defined as an async function

#### Scenario: Action payload access
- **WHEN** an action button is clicked
- **AND** the corresponding callback is invoked
- **THEN** the callback receives an `action` parameter with payload data
- **AND** the payload can be accessed via `action.payload.get("key")`
- **AND** missing payload keys return None by default
- **AND** the callback can access arbitrary payload data

#### Scenario: Action callback error handling
- **WHEN** an action callback is executed
- **AND** the callback raises an exception
- **THEN** the exception is caught and logged with full context
- **AND** a user-friendly error message is sent to the chat
- **AND** the error does NOT expose sensitive information or stack traces to users
- **AND** the application continues running without crashing

#### Scenario: Action callback logging
- **WHEN** an action callback executes successfully
- **THEN** a log entry is created at INFO level with action name and session ID
- **WHEN** an action callback fails
- **THEN** a log entry is created at ERROR level with action name, session ID, and exception details

### Requirement: Session Message Tracking
The system SHALL track action-containing messages in user sessions to enable bulk action cleanup and state management.

#### Scenario: Store message reference for action cleanup
- **WHEN** a message with actions is sent to the user
- **THEN** the message reference is stored in `cl.user_session`
- **AND** the storage key includes a descriptive identifier (e.g., "format_selection_message", "pagination_message")
- **AND** the stored reference can be retrieved in action callbacks
- **AND** stored references are session-scoped (not shared across users)

#### Scenario: Retrieve message reference in callback
- **WHEN** an action callback needs to clean up action buttons
- **THEN** the callback retrieves the message reference via `cl.user_session.get("message_key")`
- **AND** the retrieved reference is a `cl.Message` instance
- **AND** the callback can call `await message.remove_actions()` to remove all buttons
- **AND** missing message references are handled gracefully (no error)

#### Scenario: Session isolation for message references
- **WHEN** multiple users interact with the application simultaneously
- **THEN** each user's message references are isolated to their session
- **AND** actions clicked by user A do NOT affect user B's UI
- **AND** session IDs uniquely identify each user's context

### Requirement: Action Removal Pattern
The system SHALL implement consistent action removal patterns to prevent duplicate submissions and UI clutter.

#### Scenario: Remove individual action after click
- **WHEN** an action button is clicked
- **AND** the action represents a one-time operation (e.g., filter selection)
- **THEN** the action callback calls `await action.remove()`
- **AND** the specific button disappears from the UI
- **AND** other buttons in the same message remain visible

#### Scenario: Remove all actions from message
- **WHEN** an action button is clicked
- **AND** the action represents a mutually exclusive choice (e.g., confirm/cancel)
- **THEN** the action callback retrieves the message reference from user session
- **AND** the callback calls `await message.remove_actions()`
- **AND** all buttons associated with that message disappear
- **AND** the message content remains visible

#### Scenario: Handle missing message reference gracefully
- **WHEN** an action callback attempts to remove actions
- **AND** the message reference is not found in user session
- **THEN** the callback logs a warning but does NOT crash
- **AND** a user-friendly message indicates the action was processed
- **AND** the UI remains functional despite missing reference

### Requirement: Action Payload Validation
The system SHALL validate action payloads before processing to prevent errors from malformed data.

#### Scenario: Required payload fields validation
- **WHEN** an action callback expects specific payload fields
- **AND** the payload is accessed via `action.payload.get("field_name")`
- **THEN** the callback checks if the field exists and is not None
- **AND** missing required fields result in a user-friendly error message
- **AND** the callback does NOT proceed with invalid payload data

#### Scenario: Payload type validation
- **WHEN** an action payload contains typed data (e.g., integers, lists)
- **THEN** the callback validates the data type before use
- **AND** type mismatches result in a user-friendly error message
- **AND** the callback uses isinstance() or similar for validation

#### Scenario: Session ID availability in callbacks
- **WHEN** an action callback is executed
- **THEN** the callback retrieves session ID via `cl.user_session.get("session_id")`
- **AND** the session ID is used to access agent dependencies
- **AND** missing session IDs result in an error message and callback termination
- **AND** session IDs are guaranteed to be strings

### Requirement: Agent Layer Independence Preservation
The system SHALL implement actions entirely in the UI layer without modifying the agent layer to maintain framework independence.

#### Scenario: No Chainlit imports in agent layer
- **WHEN** action callbacks are implemented
- **THEN** the agent layer code (`src/agent/`) does NOT import Chainlit
- **AND** action callbacks are defined exclusively in `src/ui/` module
- **AND** agent tools remain UI-framework agnostic

#### Scenario: Action callbacks use existing agent interfaces
- **WHEN** action callbacks need to update state or execute operations
- **THEN** callbacks use existing agent layer interfaces (dependencies, session manager)
- **AND** callbacks call `get_agent_dependencies(session_id)` for repository access
- **AND** callbacks do NOT create new agent-layer APIs specifically for actions

#### Scenario: State updates via session manager
- **WHEN** action callbacks update session state (format filter, active deck)
- **THEN** callbacks use `ConversationSessionManager` methods
- **AND** state updates follow existing patterns (e.g., `set_format_filter(session_id, format)`)
- **AND** no Chainlit-specific state management is introduced in agent layer

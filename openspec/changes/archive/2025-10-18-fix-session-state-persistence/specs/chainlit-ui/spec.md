# chainlit-ui Specification Delta

## ADDED Requirements

### Requirement: Integration Test Coverage for Multi-Turn Conversations
The system SHALL provide integration tests that verify conversation context preservation across multiple messages in realistic conversation scenarios.

#### Scenario: Integration test for card context follow-up
- **WHEN** integration test `test_multi_turn_conversation_context()` is executed
- **THEN** the test simulates a two-message conversation:
  - Message 1: "Tell me about Bloodhall Ooze"
  - Message 2: "What set is it from?"
- **AND** the test verifies the agent response to message 2 mentions "Conflux" or "Bloodhall Ooze"
- **AND** the test uses the same session ID for both messages
- **AND** the test confirms context is preserved via message history

#### Scenario: Integration test for format filter persistence
- **WHEN** integration test `test_format_filter_persistence_across_messages()` is executed
- **THEN** the test simulates a two-message conversation:
  - Message 1: "Only show me Standard cards"
  - Message 2: "Find red creatures"
- **AND** the test verifies all returned cards are Standard-legal
- **AND** the test confirms format filter was NOT re-specified in message 2
- **AND** the test uses the same session ID for both messages

#### Scenario: Integration test for session isolation
- **WHEN** integration test `test_session_isolation_format_filters()` is executed
- **THEN** the test creates two independent sessions (session-a, session-b)
- **AND** session-a sets format filter to "standard"
- **AND** session-b queries cards without setting filter
- **AND** the test verifies session-a gets Standard-only results
- **AND** the test verifies session-b gets all cards (no filter applied)
- **AND** the test confirms no cross-contamination between sessions

#### Scenario: Integration test for tool call context
- **WHEN** integration test `test_context_dependent_tool_calls()` is executed
- **THEN** the test simulates a conversation with tool execution:
  - Message 1: Card lookup tool executes
  - Message 2: Follow-up question about the looked-up card
- **AND** the test verifies the agent references tool results from message 1
- **AND** the test confirms the tool is NOT re-executed in message 2
- **AND** the test validates conversation history includes tool call and return

#### Scenario: Integration test execution environment
- **WHEN** integration tests are run via `pytest tests/integration/ -m integration`
- **THEN** tests use a real database session (not mocked repositories)
- **AND** tests use a real PydanticAI agent instance
- **AND** tests use actual `run_agent_with_session()` helper
- **AND** tests verify end-to-end behavior from UI layer to data layer
- **AND** tests are marked with `@pytest.mark.integration` decorator

#### Scenario: Integration test data setup
- **WHEN** integration tests require specific card data
- **THEN** tests use database fixtures to ensure required cards exist
- **AND** test data includes cards with known attributes (e.g., Bloodhall Ooze from Conflux set)
- **AND** test data includes both Standard-legal and non-Standard cards for filter testing
- **AND** fixtures clean up test data after test execution

### Requirement: Session ID Integration with Agent Dependencies
The system SHALL pass session IDs from the UI layer to `get_agent_dependencies()` to enable session-aware state restoration.

#### Scenario: UI layer retrieves and passes session ID
- **WHEN** a user sends a message via Chainlit
- **AND** the `@cl.on_message` handler is invoked
- **THEN** the handler retrieves session ID via `cl.user_session.get("id")`
- **AND** the handler passes session ID to `get_agent_dependencies(session_id)`
- **AND** the dependencies context manager retrieves format filter for that session
- **AND** the restored dependencies are passed to `run_agent_with_session()`

#### Scenario: Dependencies contain session-restored format filter
- **WHEN** a user has set format filter to "standard" in a previous message
- **AND** the user sends a new message in the same session
- **AND** `get_agent_dependencies(session_id)` is called
- **THEN** the returned `AgentDependencies` has `format_filter="standard"`
- **AND** agent tools can immediately access the filter without re-setting
- **AND** the UI layer does NOT need to track or restore format filter state

#### Scenario: New session gets clean dependencies
- **WHEN** a new user starts a chat session
- **AND** the user sends their first message
- **AND** `get_agent_dependencies(session_id)` is called with the new session ID
- **THEN** the returned `AgentDependencies` has `format_filter=None`
- **AND** the dependencies do NOT inherit state from other sessions
- **AND** the session starts with a clean slate

## MODIFIED Requirements

### Requirement: Context Preservation
The system SHALL maintain conversation context across multiple messages within a session to enable natural follow-up questions, AND this requirement is validated by comprehensive integration tests.

#### Scenario: Basic context continuity
- **WHEN** a user asks about a specific card (e.g., "Tell me about Bloodhall Ooze")
- **AND** the agent provides information about the card
- **AND** the user follows up with a context-dependent question (e.g., "What set is it from?")
- **THEN** the agent correctly identifies "it" refers to Bloodhall Ooze
- **AND** the agent provides the set information without asking for clarification

#### Scenario: Multi-turn conversation
- **WHEN** a user engages in a multi-turn conversation about deck building
- **AND** the user references previous topics (e.g., "add more red cards to that")
- **THEN** the agent maintains context about the deck colors and cards discussed
- **AND** the agent provides relevant suggestions based on conversation history

#### Scenario: Tool call context
- **WHEN** the agent executes a tool call (e.g., card lookup) in a previous message
- **AND** the user asks a follow-up question about the result
- **THEN** the agent remembers the tool execution context
- **AND** the agent provides relevant information without re-executing the tool

#### Scenario: Integration test validation (NEW)
- **WHEN** integration tests for context preservation are executed
- **THEN** all context preservation scenarios are validated with automated tests
- **AND** tests verify actual conversation flow, not just mocked behavior
- **AND** tests use real agent, real database, and real session management
- **AND** test failures indicate regression in context preservation

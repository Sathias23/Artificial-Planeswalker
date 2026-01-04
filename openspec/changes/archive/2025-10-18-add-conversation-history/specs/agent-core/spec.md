# Agent Core Capability - Message History Support

## ADDED Requirements

### Requirement: Conversation Session Manager
The system SHALL provide a session manager class to store and retrieve conversation history by session ID.

#### Scenario: Session manager instantiation
- **WHEN** the agent module is initialized
- **THEN** a `ConversationSessionManager` instance is created
- **AND** the manager uses an in-memory dict to store sessions
- **AND** the storage is keyed by session ID strings

#### Scenario: Get history for new session
- **WHEN** `get_history(session_id)` is called for a new session
- **THEN** an empty list is returned
- **AND** no errors occur for unknown session IDs

#### Scenario: Update and retrieve history
- **WHEN** `update_history(session_id, messages)` is called
- **THEN** the messages are stored for that session ID
- **AND** subsequent `get_history(session_id)` calls return the stored messages
- **AND** messages are returned as a list of `ModelMessage` objects

#### Scenario: Clear session
- **WHEN** `clear_session(session_id)` is called
- **THEN** the session history is removed from storage
- **AND** subsequent `get_history(session_id)` returns empty list
- **AND** no errors occur if session doesn't exist

#### Scenario: Session isolation
- **WHEN** multiple sessions are active
- **THEN** each session's history is stored independently
- **AND** calling `get_history(session_a)` returns only session A's messages
- **AND** no cross-contamination occurs between sessions

### Requirement: Agent Helper with Session Support
The system SHALL provide a helper function to invoke the agent with automatic session history management.

#### Scenario: Run agent with session
- **WHEN** `run_agent_with_session(user_input, session_id, deps)` is called
- **THEN** the helper retrieves history for the session ID from session manager
- **AND** the helper calls `agent.run()` with the user input and message history
- **AND** the helper extracts all messages from the result
- **AND** the helper updates the session manager with the new messages
- **AND** the helper returns the agent result

#### Scenario: Session-aware invocation integration
- **WHEN** the UI or other client invokes the agent helper
- **THEN** conversation context is automatically maintained across calls
- **AND** the client only needs to provide user input and session ID
- **AND** message history management is transparent to the client

### Requirement: Message History Parameter Support
The system SHALL accept message history as an optional parameter to agent invocations to enable contextual conversations.

#### Scenario: Agent accepts message history
- **WHEN** the agent is invoked via `agent.run()`
- **AND** a `message_history` parameter is provided
- **THEN** the agent processes the history before generating a response
- **AND** the agent uses historical context to inform its response
- **AND** the response is contextually aware of previous messages

#### Scenario: Agent works without message history
- **WHEN** the agent is invoked via `agent.run()`
- **AND** no `message_history` parameter is provided
- **THEN** the agent processes the message without historical context
- **AND** the agent responds based only on the current message
- **AND** no errors occur from missing history

#### Scenario: Message extraction from results
- **WHEN** the agent completes a run and returns a result
- **THEN** the result provides an `all_messages()` method
- **AND** calling `all_messages()` returns a list of `ModelMessage` objects
- **AND** the returned messages include the user prompt, tool calls, tool returns, and agent response
- **AND** the messages are properly structured for use in subsequent agent invocations

### Requirement: History Size Management
The system SHALL implement intelligent history truncation to prevent unbounded memory growth and token usage.

#### Scenario: History processor registration
- **WHEN** the agent is created
- **AND** history processors are configured
- **THEN** the processors are registered with the Agent using `history_processors` parameter
- **AND** the processors run automatically before each agent invocation
- **AND** the processors modify the message history according to defined strategies

#### Scenario: Recent messages retention
- **WHEN** message history exceeds the configured limit (e.g., 10 messages)
- **AND** the history processor runs
- **THEN** only the most recent messages are retained (e.g., last 10 messages = 5 exchanges)
- **AND** system messages are preserved even when truncating
- **AND** the truncated history maintains proper message structure
- **AND** tool call/return pairs remain intact (no orphaned tool calls)

#### Scenario: Token budget management
- **WHEN** the history processor limits message count to 20 messages
- **THEN** the total history token count remains within reasonable bounds (~2,000-10,000 tokens)
- **AND** the token usage is well under the model's context window (200k for Claude Haiku)
- **AND** the history provides sufficient context for meaningful conversations
- **AND** API costs remain predictable and manageable

### Requirement: Tool Call Pairing Integrity
The system SHALL maintain proper pairing of tool calls and returns in message history to prevent LLM errors.

#### Scenario: Tool call pairing preservation
- **WHEN** message history includes tool calls
- **AND** the history is truncated or processed
- **THEN** each `ToolCallPart` has its corresponding `ToolReturnPart`
- **AND** no orphaned tool calls exist (call without return)
- **AND** no orphaned tool returns exist (return without call)
- **AND** the pairing is maintained in chronological order

#### Scenario: Safe history slicing
- **WHEN** history processors truncate message history
- **THEN** the slicing logic validates tool call pairing
- **AND** messages are removed in complete units (not mid-exchange)
- **AND** the resulting history is valid for agent invocation
- **AND** no LLM errors occur from malformed history

### Requirement: Message Type Support
The system SHALL properly handle all PydanticAI message types in history to support complete conversation context.

#### Scenario: User and system prompts
- **WHEN** message history includes user prompts
- **THEN** `ModelRequest` messages with `UserPromptPart` are stored
- **AND** system prompts with `SystemPromptPart` are preserved
- **AND** the prompts are correctly restored in subsequent agent invocations

#### Scenario: Agent responses
- **WHEN** message history includes agent responses
- **THEN** `ModelResponse` messages with `TextPart` are stored
- **AND** the text content is preserved accurately
- **AND** the responses are available for context in future messages

#### Scenario: Tool interactions
- **WHEN** message history includes tool usage
- **THEN** `ToolCallPart` messages are stored with complete arguments
- **AND** `ToolReturnPart` messages are stored with complete results
- **AND** the tool interaction context is available for follow-up questions
- **AND** the agent can reference previous tool results in responses

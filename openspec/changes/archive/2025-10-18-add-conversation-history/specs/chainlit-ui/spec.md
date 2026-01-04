# Chainlit UI Capability - Conversation History

## ADDED Requirements

### Requirement: Session ID Management
The system SHALL provide session identifiers to the agent layer to enable conversation history tracking.

#### Scenario: Session ID retrieval
- **WHEN** a user sends a message (`@cl.on_message`)
- **THEN** the UI retrieves a session identifier from Chainlit
- **AND** the session ID is obtained via `cl.user_session.get("id")` or similar
- **AND** the session ID is passed to agent invocation functions

#### Scenario: Session ID consistency
- **WHEN** multiple messages are sent within the same chat session
- **THEN** the same session ID is used for all agent invocations
- **AND** the session ID persists for the duration of the session
- **AND** a new session receives a new session ID

### Requirement: Context Preservation
The system SHALL maintain conversation context across multiple messages within a session to enable natural follow-up questions.

#### Scenario: Basic context continuity
- **WHEN** a user asks about a specific card (e.g., "Tell me about Bloodhall Ooze")
- **AND** the agent provides information about the card
- **AND** the user follows up with a context-dependent question (e.g., "What set is it from?")
- **THEN** the agent recalls the previous card discussion
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

### Requirement: Agent Invocation with Session Context
The system SHALL invoke the agent with session identifiers to enable contextual conversations.

#### Scenario: Message handling with session
- **WHEN** a user sends a message
- **THEN** the UI retrieves the session ID
- **AND** the UI calls agent invocation helper with session ID parameter
- **AND** the agent uses the session ID to manage conversation history
- **AND** the agent provides contextually aware responses

## MODIFIED Requirements

### Requirement: Basic Message Echo Functionality
The system SHALL implement message handling that passes session context to the agent for contextual responses.

#### Scenario: User sends message with session context
- **WHEN** a user sends a chat message
- **THEN** the application receives the message
- **AND** the application retrieves the session ID from Chainlit
- **AND** the application calls agent helper with user input and session ID
- **AND** the agent provides a contextually aware response
- **AND** the response appears in the chat interface

#### Scenario: Message handler with session support
- **WHEN** the application code is examined
- **THEN** the Chainlit message handler retrieves session ID from `cl.user_session`
- **AND** the handler calls `run_agent_with_session(user_input, session_id, deps)`
- **AND** the handler does NOT directly manage message history (delegated to agent)
- **AND** the handler maintains UI layer separation from history management

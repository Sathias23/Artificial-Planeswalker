# agent-core Specification Delta

## MODIFIED Requirements

### Requirement: Conversation Session Manager
The system SHALL provide a session manager class to store and retrieve conversation history AND session state (including format filter preference) by session ID.

#### Scenario: Session manager instantiation
- **WHEN** the agent module is initialized
- **THEN** a `ConversationSessionManager` instance is created
- **AND** the manager uses an in-memory dict to store sessions
- **AND** the manager uses an in-memory dict to store format filters per session
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
- **AND** the format filter preference for that session is removed
- **AND** subsequent `get_history(session_id)` returns empty list
- **AND** subsequent `get_format_filter(session_id)` returns None
- **AND** no errors occur if session doesn't exist

#### Scenario: Session isolation
- **WHEN** multiple sessions are active
- **THEN** each session's history is stored independently
- **AND** each session's format filter is stored independently
- **AND** calling `get_history(session_a)` returns only session A's messages
- **AND** calling `get_format_filter(session_a)` returns only session A's filter
- **AND** no cross-contamination occurs between sessions

#### Scenario: Get format filter for new session
- **WHEN** `get_format_filter(session_id)` is called for a new session
- **THEN** `None` is returned (no filter set)
- **AND** no errors occur for unknown session IDs

#### Scenario: Set and retrieve format filter
- **WHEN** `set_format_filter(session_id, filter_value)` is called
- **THEN** the format filter is stored for that session ID
- **AND** subsequent `get_format_filter(session_id)` calls return the stored filter value
- **AND** the filter value is a `FormatFilter` enum or None

#### Scenario: Clear format filter
- **WHEN** `clear_format_filter(session_id)` is called
- **THEN** the format filter preference for that session is removed
- **AND** subsequent `get_format_filter(session_id)` returns None
- **AND** conversation history is NOT affected
- **AND** no errors occur if session doesn't exist

#### Scenario: Format filter isolation between sessions
- **WHEN** session A has format filter set to "standard"
- **AND** session B has no format filter set
- **THEN** `get_format_filter(session_a)` returns "standard"
- **AND** `get_format_filter(session_b)` returns None
- **AND** setting filter in session A does not affect session B

## ADDED Requirements

### Requirement: Session-Aware Agent Dependencies
The system SHALL provide session-aware dependency injection that retrieves format filter preferences from session storage.

#### Scenario: Get dependencies with session context
- **WHEN** `get_agent_dependencies(session_id)` is called
- **THEN** the function retrieves the format filter from the session manager for that session ID
- **AND** an `AgentDependencies` instance is created with the retrieved format filter
- **AND** if no format filter exists for the session, `format_filter=None` is used
- **AND** the dependencies are yielded within a context manager

#### Scenario: Dependencies restore session state
- **WHEN** a user sets a format filter in message 1
- **AND** message 2 is processed for the same session
- **AND** `get_agent_dependencies(session_id)` is called
- **THEN** the `AgentDependencies` instance has `format_filter` set to the value from message 1
- **AND** agent tools can access the persisted filter via `ctx.deps.format_filter`

#### Scenario: Different sessions get different dependencies
- **WHEN** `get_agent_dependencies(session_a)` is called with session A having "standard" filter
- **AND** `get_agent_dependencies(session_b)` is called with session B having no filter
- **THEN** session A's dependencies have `format_filter="standard"`
- **AND** session B's dependencies have `format_filter=None`
- **AND** the dependencies are isolated and independent

### Requirement: Format Filter Tool Persistence
The system SHALL persist format filter changes made via the `set_format_filter()` tool to the session manager.

#### Scenario: Tool persists format filter to session
- **WHEN** the `set_format_filter()` tool is invoked with a format value
- **AND** the tool is called within a session context
- **THEN** the tool updates `ctx.deps.format_filter` (current message scope)
- **AND** the tool calls `_session_manager.set_format_filter(session_id, filter_value)` (session scope)
- **AND** subsequent messages in the same session have the filter pre-loaded

#### Scenario: Tool clears format filter from session
- **WHEN** the `set_format_filter()` tool is invoked with `format=None`
- **AND** the tool is called within a session context
- **THEN** the tool sets `ctx.deps.format_filter = None`
- **AND** the tool calls `_session_manager.clear_format_filter(session_id)`
- **AND** subsequent messages in the same session have no filter

#### Scenario: Tool isolation between sessions
- **WHEN** session A invokes `set_format_filter(format="standard")`
- **AND** session B does not invoke the tool
- **THEN** session A's session manager has "standard" stored
- **AND** session B's session manager has no filter stored
- **AND** setting filter in session A does not affect session B

### Requirement: Multi-Turn Conversation Context Preservation
The system SHALL maintain conversation context across multiple messages within a session, enabling users to ask follow-up questions that reference previous exchanges.

#### Scenario: Follow-up question using pronouns
- **WHEN** a user asks "Tell me about Bloodhall Ooze" (message 1)
- **AND** the agent provides card information
- **AND** the user asks "What set is it from?" (message 2)
- **THEN** the agent correctly identifies "it" refers to Bloodhall Ooze
- **AND** the agent provides the set information (Conflux)
- **AND** the agent does NOT ask for clarification about which card

#### Scenario: Follow-up question about tool results
- **WHEN** a user asks "Find red creatures with haste" (message 1)
- **AND** the agent executes card search tool and returns results
- **AND** the user asks "How many did you find?" (message 2)
- **THEN** the agent references the previous search results from conversation history
- **AND** the agent provides the count without re-executing the search
- **AND** the response is contextually accurate

#### Scenario: Multi-turn deck building conversation
- **WHEN** a user asks "Create a deck called Mono Red Aggro" (message 1)
- **AND** the agent creates the deck
- **AND** the user asks "Add 4 Lightning Bolt" (message 2)
- **AND** the user asks "Show me my deck" (message 3)
- **THEN** the agent maintains context about which deck is active
- **AND** the agent adds cards to the correct deck without asking for deck name
- **AND** the agent displays the deck with all previously added cards

#### Scenario: Context preserved after tool failures
- **WHEN** a user asks "Find a card called XYZ12345" (message 1)
- **AND** the agent executes tool but card is not found
- **AND** the user asks "Try Lightning Bolt instead" (message 2)
- **THEN** the agent understands "instead" refers to replacing the previous search
- **AND** the agent executes a new search for Lightning Bolt
- **AND** the conversation history includes both the failed and successful searches

### Requirement: Format Filter Persistence Across Messages
The system SHALL persist format filter preferences across multiple messages within a session so users do not need to re-specify format constraints repeatedly.

#### Scenario: Format filter set once applies to subsequent messages
- **WHEN** a user says "Only show me Standard cards" (message 1)
- **AND** the agent sets the format filter to "standard"
- **AND** the user asks "Find red creatures" (message 2)
- **THEN** only Standard-legal red creatures are returned
- **AND** the user does NOT need to say "Standard" again
- **AND** the format filter is automatically applied from session storage

#### Scenario: Format filter persists across tool invocations
- **WHEN** a format filter is set to "standard" in message 1
- **AND** the user performs multiple card queries in messages 2, 3, 4
- **THEN** all card query tools apply the "standard" filter automatically
- **AND** the filter remains active until explicitly changed or session ends
- **AND** no re-specification of format is required

#### Scenario: Format filter can be changed mid-session
- **WHEN** a user sets format to "standard" in message 1
- **AND** the user queries for cards in messages 2-3 (Standard results)
- **AND** the user says "Show me all cards, not just Standard" in message 4
- **AND** the agent clears the format filter
- **AND** the user queries for cards in message 5
- **THEN** message 5 returns results from all formats (not just Standard)
- **AND** the updated filter preference persists for subsequent messages

#### Scenario: Format filter isolation between concurrent sessions
- **WHEN** user A sets format to "standard" in their session
- **AND** user B queries for cards in their separate session without setting format
- **THEN** user A's queries are filtered to Standard
- **AND** user B's queries return all cards (no filter)
- **AND** user A's filter does NOT affect user B's session
- **AND** both users have independent, isolated format preferences

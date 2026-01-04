# agent-core Specification

## Purpose
TBD - created by archiving change story-2-1-pydanticai-agent. Update Purpose after archive.
## Requirements
### Requirement: Agent Configuration Management

The system SHALL provide type-safe configuration management for agent initialization parameters via environment variables.

#### Scenario: Load configuration from environment
- **GIVEN** a `.env` file with `OPENROUTER_API_KEY=sk-test-key` and `AGENT_MODEL_NAME=openai/gpt-4-turbo`
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** the configuration SHALL load API key as "sk-test-key" and model name as "openai/gpt-4-turbo"

#### Scenario: Apply default configuration values
- **GIVEN** no environment variables are set for optional parameters
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** temperature SHALL default to 0.7 and max_tokens SHALL default to 2000

#### Scenario: Validate configuration parameter ranges
- **GIVEN** environment variable `AGENT_TEMPERATURE=2.5` (out of range)
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** a validation error SHALL be raised indicating temperature must be between 0.0 and 2.0

#### Scenario: Handle missing required configuration
- **GIVEN** no `OPENROUTER_API_KEY` environment variable is set
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** a validation error SHALL be raised indicating the API key is required

### Requirement: PydanticAI Agent Initialization

The system SHALL initialize a PydanticAI agent with OpenRouter model integration using provided configuration.

#### Scenario: Create agent with default configuration
- **GIVEN** valid agent configuration with OpenRouter API key
- **WHEN** `create_agent()` is called without arguments
- **THEN** an Agent instance SHALL be created with Claude Sonnet 4.5 model via OpenRouter

#### Scenario: Create agent with custom model selection
- **GIVEN** agent configuration with `model_name="openai/gpt-5"`
- **WHEN** `create_agent(config)` is called
- **THEN** an Agent instance SHALL be created with GPT-5 model via OpenRouter

#### Scenario: Create agent with deferred model check for testing
- **GIVEN** testing environment without valid API key
- **WHEN** `create_agent(defer_model_check=True)` is called
- **THEN** an Agent instance SHALL be created without validating the API key

#### Scenario: Apply custom model settings
- **GIVEN** agent configuration with `temperature=0.3` and `max_tokens=1500`
- **WHEN** `create_agent(config)` is called
- **THEN** the agent SHALL use temperature 0.3 and max_tokens 1500 for LLM requests

### Requirement: OpenRouter Model Integration

The system SHALL communicate with OpenRouter API using the OpenAI-compatible interface for LLM inference.

#### Scenario: Generate basic text response
- **GIVEN** an initialized agent with valid OpenRouter API key
- **WHEN** the agent runs with prompt "What is a planeswalker?"
- **THEN** the agent SHALL return a non-empty text response about planeswalkers

#### Scenario: Handle model-specific parameters
- **GIVEN** an agent configured for Claude Sonnet 4.5 model
- **WHEN** the agent runs with a complex reasoning prompt
- **THEN** the agent SHALL successfully invoke Claude via OpenRouter and return a response

#### Scenario: Support multiple model providers
- **GIVEN** OpenRouter configuration with different model names
- **WHEN** agents are created for "anthropic/claude-sonnet-4.5", "openai/gpt-5", and "google/gemini-2.5-flash"
- **THEN** all three agents SHALL initialize successfully and communicate with their respective models

### Requirement: API Error Handling

The system SHALL handle OpenRouter API errors gracefully with appropriate exceptions and user-friendly error messages.

#### Scenario: Handle authentication failure
- **GIVEN** an agent with invalid OpenRouter API key
- **WHEN** the agent attempts to generate a response
- **THEN** an `AuthenticationError` SHALL be raised with message "Invalid API key"

#### Scenario: Handle rate limit with retry
- **GIVEN** an agent that receives a 429 rate limit response
- **WHEN** the agent runs with retry logic enabled
- **THEN** the agent SHALL retry with exponential backoff up to 5 attempts

#### Scenario: Handle model unavailability
- **GIVEN** an agent where the selected model returns 503 unavailable
- **WHEN** the agent attempts to generate a response
- **THEN** a `ModelUnavailableError` SHALL be raised with message "Model unavailable"

#### Scenario: Handle network timeout
- **GIVEN** an agent where the API request times out
- **WHEN** the agent attempts to generate a response
- **THEN** an `AgentError` SHALL be raised with timeout details in the error message

#### Scenario: Provide clear error context
- **GIVEN** any agent error occurs
- **WHEN** the error is caught and logged
- **THEN** the error message SHALL include sufficient context for debugging (model name, prompt length, error type)

### Requirement: Basic Response Validation

The system SHALL validate that agent responses meet basic quality criteria for LLM communication.

#### Scenario: Validate non-empty response
- **GIVEN** an agent that successfully completes a run
- **WHEN** the response is validated
- **THEN** the response data SHALL be non-empty and contain at least 1 character

#### Scenario: Validate response structure
- **GIVEN** an agent run result object
- **WHEN** the result is inspected
- **THEN** the result SHALL contain `data` attribute with the response text

#### Scenario: Confirm LLM model metadata
- **GIVEN** an agent run result
- **WHEN** the result metadata is inspected
- **THEN** the result SHALL include model name and token usage information

### Requirement: Test Mode Support

The system SHALL support test mode operation using PydanticAI's TestModel for unit testing without API calls.

#### Scenario: Initialize agent in test mode
- **GIVEN** test environment without OpenRouter API key
- **WHEN** an agent is created with `defer_model_check=True`
- **THEN** the agent SHALL initialize successfully without API validation

#### Scenario: Run agent with TestModel
- **GIVEN** an agent created with `TestModel` instead of OpenRouter
- **WHEN** the agent runs a prompt
- **THEN** the agent SHALL return a mock response without making API calls

#### Scenario: Validate test mode configuration
- **GIVEN** unit test with mocked configuration
- **WHEN** agent initialization is tested
- **THEN** configuration loading SHALL work independently of OpenRouter API

### Requirement: Environment-Based Model Selection

The system SHALL support runtime model selection via environment variables without code changes.

#### Scenario: Switch model via environment variable
- **GIVEN** environment variable `AGENT_MODEL_NAME=openai/gpt-5`
- **WHEN** an agent is created with default configuration
- **THEN** the agent SHALL use GPT-5 instead of default Claude Sonnet 4.5

#### Scenario: Override temperature at runtime
- **GIVEN** environment variable `AGENT_TEMPERATURE=0.9`
- **WHEN** an agent is created
- **THEN** the agent SHALL use temperature 0.9 for all LLM requests

#### Scenario: Document supported models
- **GIVEN** agent configuration documentation
- **WHEN** a developer reviews supported models
- **THEN** documentation SHALL list Claude Sonnet 4.5 (77.2% SWE-bench, $3/$15), GPT-5 (74.9% SWE-bench, $1.25/$10), and Gemini 2.5 Flash as tested models with their benchmark scores and pricing

### Requirement: Async Operation Support

The system SHALL support asynchronous agent operations compatible with PydanticAI's async-first design.

#### Scenario: Run agent asynchronously
- **GIVEN** an initialized agent in async context
- **WHEN** `await agent.run(prompt)` is called
- **THEN** the agent SHALL execute asynchronously and return result without blocking

#### Scenario: Support concurrent agent requests
- **GIVEN** multiple agent run requests
- **WHEN** requests are executed concurrently with `asyncio.gather()`
- **THEN** all requests SHALL execute in parallel without race conditions

#### Scenario: Handle async errors
- **GIVEN** an agent run that fails asynchronously
- **WHEN** the error is propagated
- **THEN** the error SHALL be catchable with standard async exception handling

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

### Requirement: Agent Helper with Session Support

The system SHALL provide `run_agent_with_session` function that manages conversation history AND injects active deck context when present, ensuring consistent agent awareness of deck state.

#### Scenario: Run agent with session includes deck context injection
- **GIVEN** a session with active deck and conversation history
- **WHEN** `run_agent_with_session(user_input, session_id, deps, agent)` is called
- **THEN** the function SHALL retrieve conversation history from session manager
- **AND** IF `deps.active_deck` exists, function SHALL inject deck context into history
- **AND** the function SHALL run the agent with enhanced history
- **AND** the function SHALL update history with new messages after agent completes
- **AND** deck context injection SHALL occur BEFORE agent runs, not after

#### Scenario: Session helper logs deck context injection
- **GIVEN** a session with active deck
- **WHEN** `run_agent_with_session` injects deck context
- **THEN** the function SHALL log at INFO level: "Injected deck context for session={session_id}, deck={deck_name}"
- **AND** the log SHALL include deck ID (first 8 chars) for debugging
- **AND** the log SHALL NOT include full conversation history (privacy)

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

### Requirement: Session-Aware Agent Dependencies

The system SHALL provide session-aware dependency injection that retrieves format filter from session storage and loads the active deck from the database once per request, caching it for all tools in the same agent run.

#### Scenario: Get dependencies with session context
- **WHEN** `get_agent_dependencies(session_id)` is called
- **THEN** the function retrieves the format filter from the session manager for that session ID
- **AND** the function retrieves the active deck ID from the session manager
- **AND** if an active deck ID exists, the function loads the full `Deck` object from the database with cards
- **AND** an `AgentDependencies` instance is created with the loaded deck cached in `active_deck` field
- **AND** if no deck is active or deck not found, `active_deck=None` is set
- **AND** the dependencies are yielded within a context manager

#### Scenario: Dependencies restore session state with cached deck
- **WHEN** a user creates a deck in message 1
- **AND** message 2 is processed for the same session
- **AND** `get_agent_dependencies(session_id)` is called
- **THEN** the `AgentDependencies` instance has `active_deck` set to the loaded `Deck` object
- **AND** agent tools can access the deck directly via `ctx.deps.active_deck`
- **AND** no additional database queries are needed to fetch deck data

#### Scenario: Different sessions get different cached decks
- **WHEN** `get_agent_dependencies(session_a)` is called with session A having deck "deck-123" active
- **AND** `get_agent_dependencies(session_b)` is called with session B having deck "deck-456" active
- **THEN** session A's dependencies have `active_deck` containing data for "deck-123"
- **AND** session B's dependencies have `active_deck` containing data for "deck-456"
- **AND** the dependencies are isolated and independent

#### Scenario: Cached deck provides immediate access to cards
- **GIVEN** a deck tool needs to check if a card exists in the active deck
- **WHEN** the tool accesses `ctx.deps.active_deck.deck_cards`
- **THEN** the card list is immediately available from the cached object
- **AND** no database query is executed
- **AND** the tool can iterate over cards without additional repository calls

#### Scenario: No active deck results in None cache
- **GIVEN** a session has no active deck set
- **WHEN** `get_agent_dependencies(session_id)` is called
- **THEN** `active_deck=None` is set in the dependencies
- **AND** no database query is executed to load a deck
- **AND** tools checking `deps.active_deck` receive `None`

#### Scenario: Defensive handling of missing deck
- **GIVEN** the session manager returns deck ID "deck-999"
- **AND** the deck repository returns `None` (deck was deleted)
- **WHEN** `get_agent_dependencies(session_id)` is called
- **THEN** `active_deck=None` is set in the dependencies
- **AND** a warning is logged about the missing deck
- **AND** no error is raised during dependency creation

#### Scenario: Single database query per request
- **GIVEN** an agent run invokes 3 deck tools in sequence
- **WHEN** dependencies are created once at the start of the request
- **THEN** the deck is loaded from database exactly once
- **AND** all 3 tools access the same cached `Deck` object
- **AND** no redundant database queries occur

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

### Requirement: Logfire Configuration Management
The system SHALL provide type-safe configuration management for Pydantic Logfire observability settings via environment variables.

#### Scenario: Load Logfire configuration from environment
- **GIVEN** a `.env` file with `LOGFIRE_ENABLED=true`, `LOGFIRE_TOKEN=lf_test_token`, and `LOGFIRE_PROJECT=my-project`
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** the configuration SHALL load `logfire_enabled=True`, `logfire_token="lf_test_token"`, and `logfire_project="my-project"`

#### Scenario: Apply Logfire default configuration values
- **GIVEN** no environment variables are set for Logfire parameters
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** `logfire_enabled` SHALL default to `False`, `logfire_token` SHALL default to `None`, and `logfire_project` SHALL default to `"artificial-planeswalker"`

#### Scenario: Validate Logfire token requirement
- **GIVEN** environment variable `LOGFIRE_ENABLED=true` without `LOGFIRE_TOKEN` set
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** a validation error SHALL be raised indicating "LOGFIRE_TOKEN required when LOGFIRE_ENABLED=true"

#### Scenario: Allow disabled Logfire without token
- **GIVEN** environment variable `LOGFIRE_ENABLED=false` without `LOGFIRE_TOKEN` set
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** the configuration SHALL load successfully without requiring a token

### Requirement: Observability Initialization
The system SHALL provide a function to initialize Pydantic Logfire observability when enabled via configuration.

#### Scenario: Initialize Logfire when enabled
- **GIVEN** agent configuration with `logfire_enabled=True` and valid token
- **WHEN** `configure_observability(config)` is called
- **THEN** Logfire SHALL be configured with the provided token and project name
- **AND** PydanticAI instrumentation SHALL be enabled via `logfire.instrument_pydantic_ai()`

#### Scenario: Skip Logfire initialization when disabled
- **GIVEN** agent configuration with `logfire_enabled=False`
- **WHEN** `configure_observability(config)` is called
- **THEN** no Logfire configuration SHALL occur
- **AND** no instrumentation SHALL be enabled
- **AND** the function SHALL return without error

#### Scenario: Handle Logfire configuration errors gracefully
- **GIVEN** agent configuration with invalid Logfire token
- **WHEN** `configure_observability(config)` is called
- **THEN** the function SHALL log an error message
- **AND** the function SHALL NOT crash the application
- **AND** the application SHALL continue running without observability

#### Scenario: Initialize Logfire exactly once
- **GIVEN** the agent module is loaded
- **WHEN** `configure_observability(config)` is called during module initialization
- **THEN** Logfire SHALL be configured exactly once
- **AND** subsequent agent invocations SHALL NOT reconfigure Logfire

### Requirement: PydanticAI Agent Tracing
The system SHALL automatically trace all PydanticAI agent invocations when Logfire is enabled.

#### Scenario: Trace agent run with prompt and response
- **GIVEN** Logfire is enabled and configured
- **WHEN** an agent run is executed with prompt "Find Lightning Bolt"
- **THEN** a trace SHALL be created in Logfire with span name "agent.run"
- **AND** the trace SHALL include the prompt text
- **AND** the trace SHALL include the agent response
- **AND** the trace SHALL include token usage metadata

#### Scenario: Trace tool calls within agent run
- **GIVEN** Logfire is enabled and configured
- **WHEN** an agent run executes a tool call (e.g., `lookup_card_by_name`)
- **THEN** a child span SHALL be created for the tool call
- **AND** the span SHALL include tool name, arguments, and return value
- **AND** the span SHALL be correlated with the parent agent run trace

#### Scenario: No tracing when Logfire disabled
- **GIVEN** Logfire is disabled (`logfire_enabled=False`)
- **WHEN** an agent run is executed
- **THEN** no traces SHALL be created
- **AND** no data SHALL be sent to Logfire platform
- **AND** agent execution SHALL proceed normally with zero observability overhead

### Requirement: Database Query Tracing
The system SHALL automatically trace SQLAlchemy database queries when Logfire is enabled.

#### Scenario: Trace database queries during agent tool execution
- **GIVEN** Logfire is enabled and SQLAlchemy instrumentation is configured
- **WHEN** a card lookup tool executes a database query
- **THEN** a span SHALL be created for the SQL query
- **AND** the span SHALL include SQL statement text
- **AND** the span SHALL include query execution time
- **AND** the span SHALL be correlated with the parent tool call span

#### Scenario: No database tracing when Logfire disabled
- **GIVEN** Logfire is disabled
- **WHEN** a database query is executed
- **THEN** no query traces SHALL be created
- **AND** query execution SHALL proceed normally without instrumentation overhead

### Requirement: HTTP Request Tracing
The system SHALL automatically trace httpx HTTP requests when Logfire is enabled.

#### Scenario: Trace external HTTP requests
- **GIVEN** Logfire is enabled and httpx instrumentation is configured
- **WHEN** an HTTP request is made to Scryfall symbol API
- **THEN** a span SHALL be created for the HTTP request
- **AND** the span SHALL include request URL, method, and status code
- **AND** the span SHALL include request/response timing

#### Scenario: No HTTP tracing when Logfire disabled
- **GIVEN** Logfire is disabled
- **WHEN** an HTTP request is made
- **THEN** no HTTP traces SHALL be created
- **AND** HTTP requests SHALL proceed normally without instrumentation overhead

### Requirement: Logging Integration
The system SHALL send Python application logs to Logfire when enabled, with automatic correlation to distributed traces.

#### Scenario: Send logs to Logfire with trace correlation
- **GIVEN** Logfire is enabled and logging handler is configured
- **WHEN** application code calls `logging.info("Tool executed successfully")`
- **THEN** the log message SHALL be sent to Logfire
- **AND** the log SHALL be correlated with the current trace span (if active)
- **AND** the log SHALL include timestamp, level, and message

#### Scenario: Logs use standard Python logging when Logfire disabled
- **GIVEN** Logfire is disabled
- **WHEN** application code calls `logging.info()`
- **THEN** logs SHALL be output to console as normal
- **AND** no logs SHALL be sent to Logfire platform

### Requirement: Zero Performance Overhead When Disabled
The system SHALL ensure zero performance impact when Logfire observability is disabled.

#### Scenario: No instrumentation loaded when disabled
- **GIVEN** Logfire is disabled (`logfire_enabled=False`)
- **WHEN** the agent is initialized
- **THEN** no Logfire modules SHALL be imported
- **AND** no instrumentation hooks SHALL be registered
- **AND** no observability code SHALL execute during agent runs

#### Scenario: Equivalent performance with Logfire disabled
- **GIVEN** Logfire is disabled
- **WHEN** agent performance is measured for 100 invocations
- **THEN** the average latency SHALL be statistically equivalent to baseline (pre-Logfire)
- **AND** memory usage SHALL be statistically equivalent to baseline

### Requirement: Graceful Degradation on Logfire Errors
The system SHALL continue operating normally when Logfire platform is unavailable or returns errors.

#### Scenario: Handle Logfire API unavailability
- **GIVEN** Logfire is enabled but the platform API is unreachable
- **WHEN** an agent run is executed
- **THEN** the agent SHALL complete successfully
- **AND** an error SHALL be logged about Logfire unavailability
- **AND** traces SHALL be dropped (not sent)
- **AND** the application SHALL NOT crash or hang

#### Scenario: Handle invalid Logfire token
- **GIVEN** Logfire is enabled with invalid/expired token
- **WHEN** observability is initialized
- **THEN** an error SHALL be logged about authentication failure
- **AND** the application SHALL continue running without observability
- **AND** the agent SHALL function normally

#### Scenario: Handle Logfire rate limits
- **GIVEN** Logfire is enabled and rate limits are exceeded
- **WHEN** traces are sent to Logfire platform
- **THEN** traces SHALL be dropped or buffered according to Logfire SDK behavior
- **AND** the application SHALL NOT be blocked or slowed down
- **AND** a warning SHALL be logged about rate limiting

### Requirement: Active Deck Context Injection

The system SHALL inject active deck information into the conversation history as a system message on every agent run when a deck is active, ensuring the agent maintains awareness of deck state regardless of conversation history length.

#### Scenario: Inject deck context when active deck exists
- **GIVEN** a user has an active deck "Fire Lord Zuko Deck" with 5 cards
- **WHEN** `run_agent_with_session` is called with `deps.active_deck` populated
- **THEN** the agent history SHALL include a system message with active deck context
- **AND** the message SHALL contain deck name, ID (first 8 chars), format, and card count
- **AND** the message SHALL instruct agent to add cards to THIS deck by default
- **AND** the context SHALL be prepended to the most recent system message OR added as new system message

#### Scenario: No context injection when no active deck
- **GIVEN** a user has no active deck
- **WHEN** `run_agent_with_session` is called with `deps.active_deck=None`
- **THEN** no deck context SHALL be injected into history
- **AND** the agent runs with standard system prompt only
- **AND** no additional tokens are consumed for deck context

#### Scenario: Context injection preserves deck state across large conversations
- **GIVEN** a user created deck "Test Deck" in message 1
- **AND** messages 2-10 contained large search results (100+ cards, 20K tokens)
- **WHEN** message 11 requests "add Lightning Bolt"
- **THEN** the system message SHALL include "ACTIVE DECK: Test Deck"
- **AND** the agent SHALL recognize the active deck from system context
- **AND** the agent SHALL NOT create a new deck
- **AND** the agent SHALL call `add_card_to_deck` on the existing deck

#### Scenario: Context message format is concise and high-signal
- **GIVEN** an active deck "Mono Red Aggro" with 15 cards in Standard format
- **WHEN** deck context message is built
- **THEN** the message SHALL include exactly: deck name, deck ID (8 chars), format, card count
- **AND** the message SHALL include explicit instruction to add cards to THIS deck
- **AND** the message SHALL be no more than 200 tokens
- **AND** the message SHALL use clear, unambiguous language

#### Scenario: Context injection works with empty conversation history
- **GIVEN** a user starts a new message with an active deck
- **AND** the conversation history is empty (first message)
- **WHEN** `run_agent_with_session` is called
- **THEN** a new system message SHALL be created with deck context
- **AND** the message SHALL be inserted at the start of history
- **AND** subsequent messages append after this system message

#### Scenario: Context injection prepends to existing system message
- **GIVEN** conversation history has an existing system message at index 0
- **AND** a user has an active deck
- **WHEN** `run_agent_with_session` is called
- **THEN** deck context SHALL be prepended to the existing system message content
- **AND** the format SHALL be "{deck_context}\n\n{original_system_message}"
- **AND** no duplicate system messages are created

### Requirement: Tool-First Deck Operation System Prompt

The system SHALL include explicit instructions in the agent system prompt mandating tool-first behavior for deck operations, preventing premature agent decisions about deck state.

#### Scenario: System prompt includes tool-first deck rules
- **GIVEN** the agent is initialized via `create_agent()`
- **WHEN** the agent system prompt is constructed
- **THEN** the prompt SHALL include a "DECK OPERATION RULES" section
- **AND** the rules SHALL mandate calling `add_card_to_deck` before `create_deck`
- **AND** the rules SHALL instruct agent to trust tool errors over assumptions
- **AND** the rules SHALL specify agent should only create deck if tool says "No active deck"

#### Scenario: Agent follows tool-first approach when adding cards
- **GIVEN** a user with active deck says "add Lightning Bolt"
- **WHEN** the agent processes the request
- **THEN** the agent SHALL call `add_card_to_deck` tool first
- **AND** the agent SHALL NOT call `create_deck` if `add_card_to_deck` succeeds
- **AND** the agent SHALL NOT make assumptions about deck existence without calling tools

#### Scenario: Agent creates deck only after tool confirmation
- **GIVEN** a user with NO active deck says "add Lightning Bolt"
- **WHEN** the agent processes the request
- **THEN** the agent SHALL call `add_card_to_deck` first
- **AND** the tool SHALL return "No active deck. Create a deck first..."
- **AND** ONLY THEN SHALL the agent suggest or create a new deck
- **AND** the agent SHALL explain why deck creation is needed

#### Scenario: Agent explicitly creates deck when user requests it
- **GIVEN** a user says "create a new deck called Control Deck"
- **WHEN** the agent processes the request
- **THEN** the agent SHALL call `create_deck` tool directly
- **AND** the agent SHALL NOT call `add_card_to_deck` first
- **AND** explicit deck creation requests bypass tool-first validation

#### Scenario: Tool-first rules prevent duplicate deck creation
- **GIVEN** a user with active deck "Deck A"
- **AND** the agent has lost deck context in conversation history
- **WHEN** user says "add Boros Charm"
- **THEN** the agent SHALL call `add_card_to_deck` (per tool-first rules)
- **AND** the tool SHALL succeed using active deck from dependencies
- **AND** the agent SHALL NOT create "Deck B" despite lack of context awareness
- **AND** the tool enforces correct behavior even if agent is confused


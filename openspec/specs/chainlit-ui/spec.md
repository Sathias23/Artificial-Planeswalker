# chainlit-ui Specification

## Purpose
TBD - created by archiving change add-chainlit-ui. Update Purpose after archive.
## Requirements
### Requirement: Chainlit Installation and Configuration
The system SHALL have Chainlit installed and configured as a project dependency with custom application settings.

#### Scenario: Chainlit dependency installed
- **WHEN** the project dependencies are synced via `uv sync`
- **THEN** Chainlit is installed and available in the Python environment

#### Scenario: Chainlit configuration file exists
- **WHEN** the Chainlit application is initialized
- **THEN** a `.chainlit` configuration directory with config.toml exists
- **AND** the config.toml specifies custom app name "Artificial-Planeswalker"
- **AND** the config.toml includes appropriate UI settings

### Requirement: Application Entry Point
The system SHALL provide a Chainlit application entry point that can be run via UV command.

#### Scenario: Application starts successfully
- **WHEN** the command `uv run chainlit run app.py` is executed
- **THEN** the Chainlit web server starts without errors
- **AND** the application is accessible via localhost on the default Chainlit port

#### Scenario: Application module structure
- **WHEN** the UI module is examined
- **THEN** an `src/ui/app.py` file exists as the Chainlit entry point
- **AND** the file imports Chainlit and defines message handlers

### Requirement: Welcome Message Display
The system SHALL display a welcome message when the chat interface loads to onboard users.

#### Scenario: Initial load welcome message
- **WHEN** a user first accesses the Chainlit chat interface
- **THEN** a welcome message is automatically displayed
- **AND** the message introduces the Artificial-Planeswalker assistant
- **AND** the message provides basic usage instructions or capabilities

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

### Requirement: Graceful Startup and Shutdown
The system SHALL handle application startup and shutdown gracefully without errors or resource leaks.

#### Scenario: Clean startup
- **WHEN** the Chainlit application starts
- **THEN** all initialization completes without exceptions
- **AND** startup logs indicate successful initialization
- **AND** the web interface becomes available

#### Scenario: Clean shutdown
- **WHEN** the Chainlit application is stopped (SIGTERM or SIGINT)
- **THEN** the application shuts down gracefully
- **AND** all resources are properly released
- **AND** no error messages or stack traces are logged during shutdown

### Requirement: UI Layer Architecture Compliance
The system SHALL implement the UI layer as a thin delegation layer that does not access the database directly.

#### Scenario: No direct database imports
- **WHEN** the UI module code is examined
- **THEN** the UI module does NOT import database models or repositories
- **AND** the UI module does NOT import SQLAlchemy session management
- **AND** all data access is delegated through the agent layer

#### Scenario: Agent layer independence
- **WHEN** the agent layer code is examined
- **THEN** the agent layer does NOT import Chainlit
- **AND** the agent layer can be tested independently of the UI
- **AND** the agent layer uses standard Python types for inputs/outputs

### Requirement: Development Environment Integration
The system SHALL integrate Chainlit into the development workflow with proper tooling support.

#### Scenario: Pre-commit hooks compatibility
- **WHEN** pre-commit hooks are run
- **THEN** Ruff linting passes on UI module code
- **AND** mypy type checking passes on UI module code
- **AND** the Chainlit app.py file follows project code conventions

#### Scenario: Project structure consistency
- **WHEN** the repository structure is examined
- **THEN** the UI module exists at `src/ui/`
- **AND** the UI module contains an `__init__.py` for proper package structure
- **AND** the app.py entry point is located at `src/ui/app.py`

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

### Requirement: Agent Invocation with Session Context
The system SHALL invoke the agent with session identifiers to enable contextual conversations.

#### Scenario: Message handling with session
- **WHEN** a user sends a message
- **THEN** the UI retrieves the session ID
- **AND** the UI calls agent invocation helper with session ID parameter
- **AND** the agent uses the session ID to manage conversation history
- **AND** the agent provides contextually aware responses

### Requirement: Structured Card Data Display
The system SHALL format card data with clear structure separating name, cost, type, and oracle text on separate lines.

#### Scenario: Single card display formatting
- **WHEN** the agent returns a single card result
- **THEN** the UI displays the card name on the first line in bold markdown
- **AND** the mana cost appears on the second line with readable symbol notation
- **AND** the type line appears on a separate line
- **AND** the oracle text is formatted with proper line breaks
- **AND** all fields are visually separated for clarity

#### Scenario: Card with missing fields
- **WHEN** a card has optional fields missing (e.g., no mana cost for lands)
- **THEN** the UI gracefully handles missing data
- **AND** no blank lines or "None" values are displayed
- **AND** the formatting remains consistent

### Requirement: Mana Symbol Representation
The system SHALL represent mana symbols as readable text or unicode symbols for clear visual identification.

#### Scenario: Basic mana symbols
- **WHEN** a card has mana cost with basic colors
- **THEN** mana symbols are displayed as text notation (e.g., "{1}{R}{G}")
- **AND** symbols use standard Magic notation: {W}, {U}, {B}, {R}, {G}, {C}
- **AND** generic mana uses numbers: {1}, {2}, {3}, etc.

#### Scenario: Complex mana symbols
- **WHEN** a card has hybrid, Phyrexian, or snow mana costs
- **THEN** the UI displays these using appropriate text notation
- **AND** hybrid mana uses slash notation: {W/U}, {2/R}
- **AND** Phyrexian mana uses P notation: {W/P}, {U/P}
- **AND** snow mana uses {S} notation

### Requirement: Multiple Card Results Display
The system SHALL display multiple card results as a numbered or bulleted list with consistent formatting.

#### Scenario: List of 5-10 cards
- **WHEN** the agent returns 5-10 card results
- **THEN** the UI displays them as a numbered list
- **AND** each list item shows card name, mana cost, and type line
- **AND** the list uses consistent formatting for all entries
- **AND** all cards are visible without scrolling issues

#### Scenario: More than 10 cards returned
- **WHEN** the agent returns more than 10 card results
- **THEN** the UI displays the first 10 cards in the list
- **AND** a message appears indicating "...and X more results"
- **AND** the message suggests refining the search query

### Requirement: Chainlit Element Usage
The system SHALL use Chainlit message elements (cl.Text, cl.Message) for structured card information display.

#### Scenario: Single card with cl.Text element
- **WHEN** displaying a single card
- **THEN** the UI creates a cl.Text element with formatted card content
- **AND** the element display mode is set to "inline"
- **AND** the element is included in a cl.Message
- **AND** the message is sent to the user

#### Scenario: Multiple cards with message content
- **WHEN** displaying multiple cards
- **THEN** the UI formats the card list in the message content
- **AND** the message uses markdown for structure
- **AND** the message is sent without requiring separate elements for each card

### Requirement: Result Limiting and Pagination
The system SHALL limit long card lists to prevent chat overflow and maintain interface usability.

#### Scenario: Default result limit
- **WHEN** a card query returns results
- **THEN** the UI applies a default limit of 10 cards maximum
- **AND** results beyond the limit are not displayed
- **AND** a count of hidden results is shown ("...and 15 more")

#### Scenario: Configurable result limit
- **WHEN** the formatting function is called
- **THEN** the caller can specify a custom limit parameter
- **AND** the limit can be set between 1 and 15 cards
- **AND** limits exceeding 15 are capped at 15 to prevent overflow

### Requirement: Visual Card Type and Color Emphasis
The system SHALL highlight or emphasize card colors and types for visual clarity.

#### Scenario: Card type visual emphasis
- **WHEN** a card is displayed
- **THEN** the card type uses markdown emphasis (e.g., *Creature*, **Instant**)
- **AND** the type emphasis is consistent across all card displays
- **AND** the emphasis improves readability without excessive styling

#### Scenario: Color indication
- **WHEN** a card has color identity
- **THEN** the UI displays color names or symbols
- **AND** colors are shown in a standardized format (e.g., "Colors: Red, Green")
- **AND** colorless cards indicate "Colorless" clearly

### Requirement: Professional Formatting Validation
The system SHALL ensure card formatting is readable and professional through manual testing confirmation.

#### Scenario: Manual formatting review
- **WHEN** manual testing is performed
- **THEN** testers verify card information is easy to read at a glance
- **AND** testers confirm mana symbols are recognizable
- **AND** testers validate multi-card lists are scannable
- **AND** testers approve visual emphasis improves (not hinders) readability
- **AND** no formatting issues are present (overflow, wrapping, alignment)

### Requirement: Card Image Display
The system SHALL display Scryfall card images inline within chat messages when card information is requested and image URIs are available.

#### Scenario: Display card with image
- **WHEN** a user requests card information for a card with image_uris populated
- **AND** the agent retrieves the card data
- **THEN** the response includes both formatted text details and the card image
- **AND** the image is displayed inline within the chat message
- **AND** the image uses the "normal" size variant from image_uris

#### Scenario: Display card without image fallback
- **WHEN** a user requests card information for a card without image_uris (e.g., old data or double-faced card)
- **AND** the agent retrieves the card data
- **THEN** the response includes formatted text details only
- **AND** no error or missing image indicator is shown
- **AND** the conversation continues normally

#### Scenario: Image element creation
- **WHEN** the UI formatter creates a card message with image
- **THEN** a cl.Image element is created with url parameter pointing to Scryfall CDN
- **AND** the image element has display mode set to "inline"
- **AND** the image element name is set to the card name
- **AND** the image element is attached to the message via elements parameter

#### Scenario: Multiple card images in search results
- **WHEN** a user searches for multiple cards and results include 3+ cards with images
- **THEN** all card images are displayed inline in the response
- **AND** images are limited to the same result limit as text (10-15 cards max)
- **AND** the UI remains usable without excessive scrolling

### Requirement: Image Source Validation
The system SHALL only display card images from trusted Scryfall CDN sources to prevent security issues.

#### Scenario: Scryfall CDN URL validation
- **WHEN** the UI formatter prepares to display a card image
- **THEN** the image URL is verified to match Scryfall CDN pattern (cards.scryfall.io or c[0-9].scryfall.com)
- **AND** only HTTPS URLs are accepted
- **AND** malformed or non-Scryfall URLs result in text-only fallback

#### Scenario: Missing or invalid image URL handling
- **WHEN** image_uris exists but contains invalid URLs or is malformed
- **THEN** the formatter gracefully falls back to text-only display
- **AND** an error is logged for debugging purposes
- **AND** the user sees the card information without error messages

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

### Requirement: Tool Call Visibility with Chainlit Steps
The system SHALL display PydanticAI tool calls visually in the chat interface using Chainlit's Step API to provide transparency into agent operations, AND SHALL only display tool calls from the most recent agent turn to prevent historical clutter.

#### Scenario: Single tool call displays Step
- **WHEN** the agent invokes a single tool (e.g., `lookup_card_by_name`)
- **THEN** a Chainlit Step appears in the chat interface
- **AND** the Step shows the tool name as the step label
- **AND** the Step displays the tool parameters as input
- **AND** the Step shows a summary of the tool result as output
- **AND** the Step is marked with type="tool"

#### Scenario: Multiple parallel tool calls display multiple Steps
- **WHEN** the agent invokes multiple tools in parallel
- **THEN** each tool call appears as a separate Chainlit Step
- **AND** the Steps are displayed as siblings (not nested)
- **AND** all Steps show execution status independently
- **AND** the final agent response appears after all Steps complete

#### Scenario: Only current turn tool calls are shown
- **WHEN** a multi-turn conversation has occurred with tool calls in previous messages
- **AND** the agent responds to the current message with new tool calls
- **THEN** only the tool calls from the current response are displayed as Steps
- **AND** tool calls from previous turns do NOT appear as Steps in the current response
- **AND** the UI remains clean without historical tool call clutter

#### Scenario: Steps appear above streaming response
- **WHEN** the agent executes tool calls and generates a text response
- **THEN** the tool call Steps are created and displayed BEFORE the response text begins streaming
- **AND** users see the tool executions before reading the agent's answer
- **AND** the visual flow shows "what was queried" followed by "the answer"

#### Scenario: Step shows tool execution lifecycle
- **WHEN** a tool call Step is created
- **THEN** the Step initially shows as "running" status
- **AND** the Step updates to "completed" when the tool finishes
- **AND** if the tool fails, the Step shows "failed" status with error message

### Requirement: Tool Parameter Display in Steps
The system SHALL format tool parameters in a readable, non-verbose format suitable for user consumption.

#### Scenario: Simple parameters displayed clearly
- **WHEN** a tool is called with simple parameters (e.g., card_name="Lightning Bolt")
- **THEN** the Step input shows parameters as key-value pairs
- **AND** the format is human-readable (not raw JSON)
- **AND** string values are quoted for clarity

#### Scenario: Complex parameters simplified
- **WHEN** a tool is called with complex parameters (e.g., nested filters)
- **THEN** the Step input shows a simplified representation
- **AND** the simplification focuses on user-relevant information
- **AND** technical details are omitted if not useful to users

#### Scenario: No parameters displayed for parameterless tools
- **WHEN** a tool requires no parameters
- **THEN** the Step input is omitted or shows "No parameters"
- **AND** the Step focuses on the tool name and result

### Requirement: Tool Result Summarization in Steps
The system SHALL summarize tool results in Steps without duplicating full card data that appears in the final message.

#### Scenario: Card query result summary
- **WHEN** a tool returns card search results
- **THEN** the Step output shows a count (e.g., "Found 3 cards")
- **AND** the Step does NOT display full card details
- **AND** full card details appear in the final agent message

#### Scenario: Single card lookup summary
- **WHEN** a tool returns a single card
- **THEN** the Step output shows the card name found
- **AND** the Step does NOT duplicate the full card formatting
- **AND** full card details appear in the final agent message

#### Scenario: Tool execution with no results
- **WHEN** a tool returns no results (e.g., no cards found)
- **THEN** the Step output shows "No results found"
- **AND** the Step status is still "completed" (not failed)
- **AND** the agent message explains the empty result

### Requirement: Agent Layer Independence Maintained
The system SHALL implement tool visibility in the UI layer without modifying the agent layer to import Chainlit.

#### Scenario: No Chainlit imports in agent layer
- **WHEN** the agent layer code is examined
- **THEN** the agent layer does NOT import Chainlit (cl module)
- **AND** the agent tools do NOT reference cl.Step
- **AND** the agent remains UI-framework agnostic

#### Scenario: Tool visibility implemented via UI wrappers
- **WHEN** the UI layer code is examined
- **THEN** tool visibility is implemented by wrapping agent calls with cl.Step
- **AND** the wrappers are located in src/ui/ module
- **AND** the agent layer functions remain unchanged

### Requirement: Step Configuration for Tool Types
The system SHALL configure Steps with appropriate metadata to identify them as tool calls.

#### Scenario: Step type set to "tool"
- **WHEN** a Step is created for a tool call
- **THEN** the Step type parameter is set to "tool"
- **AND** this allows Chainlit to style tool Steps distinctively
- **AND** users can visually distinguish tool calls from other operations

#### Scenario: Step name reflects tool purpose
- **WHEN** a Step is created for a tool call
- **THEN** the Step name clearly describes the tool action (e.g., "Looking up card", "Searching cards")
- **AND** the name is user-friendly, not technical (e.g., not "lookup_card_by_name")
- **AND** the name provides context about what the agent is doing

### Requirement: Error Handling in Tool Steps
The system SHALL gracefully handle tool errors and display them clearly in Steps.

#### Scenario: Tool raises exception
- **WHEN** a tool call raises an exception
- **THEN** the Step status changes to "failed"
- **AND** the Step output shows a user-friendly error message
- **AND** the error does NOT include sensitive information or full stack traces
- **AND** the agent can still respond with a helpful message

#### Scenario: Tool timeout or delay
- **WHEN** a tool call takes longer than expected
- **THEN** the Step remains in "running" status
- **AND** users can see the tool is still executing
- **AND** the Step eventually completes or fails with timeout message

### Requirement: Performance Considerations for Steps
The system SHALL ensure Step creation does not significantly impact response time or user experience.

#### Scenario: Step overhead is minimal
- **WHEN** tool calls are wrapped with Steps
- **THEN** the overhead per Step is less than 50ms
- **AND** users do not perceive noticeable delay
- **AND** the system remains responsive

#### Scenario: Many tool calls handled efficiently
- **WHEN** the agent makes 5+ tool calls in a single conversation turn
- **THEN** all Steps are created and displayed efficiently
- **AND** the UI does not freeze or lag
- **AND** Steps load progressively (not all at once)

### Requirement: Tool Call Extraction Logic
The system SHALL extract tool call information only from the most recent agent response to prevent displaying historical tool calls from previous conversation turns.

#### Scenario: Extract tool calls from current turn only
- **WHEN** `extract_tool_calls(messages)` is called with agent result messages
- **AND** the messages list contains conversation history from multiple turns
- **THEN** the function identifies and returns only tool calls from the most recent model response
- **AND** tool calls from previous turns are excluded from the returned list
- **AND** the extraction logic differentiates between historical and current tool calls

#### Scenario: Multi-turn conversation without tool call duplication
- **WHEN** a user has a 3-message conversation where each message triggers tool calls
- **THEN** message 1 displays only tool calls from turn 1
- **AND** message 2 displays only tool calls from turn 2 (not turn 1 + turn 2)
- **AND** message 3 displays only tool calls from turn 3
- **AND** no tool call Steps are duplicated across messages

#### Scenario: Handle conversation with no tool calls
- **WHEN** the agent responds to a message without invoking any tools
- **THEN** `extract_tool_calls(messages)` returns an empty list
- **AND** no tool call Steps are created
- **AND** only the agent's text response is displayed

### Requirement: Chunk-Based Response Streaming
The system SHALL stream agent responses in word-based chunks to ensure performant streaming for responses of any length.

#### Scenario: Long response streams efficiently
- **WHEN** the agent generates a response over 5,000 characters
- **THEN** the response is streamed in chunks of 10-20 words per chunk
- **AND** the total streaming time is less than 5 seconds
- **AND** the streaming loop executes fewer than 500 operations
- **AND** no session timeout or reconnection occurs during streaming

#### Scenario: Short response streams smoothly
- **WHEN** the agent generates a response under 500 characters
- **THEN** the response is still chunked by words (not characters)
- **AND** the streaming appears smooth and progressive to the user
- **AND** the chunking does not introduce noticeable delays

#### Scenario: Word boundary preservation
- **WHEN** the response text is split into chunks
- **THEN** each chunk ends at a word boundary (space character)
- **AND** words are never split mid-word across chunks
- **AND** trailing whitespace and newlines are preserved in chunks

#### Scenario: Edge case handling
- **WHEN** the agent response is empty or very short (< 10 words)
- **THEN** the response is streamed as a single chunk
- **AND** no errors occur from chunking logic
- **AND** the streaming behavior gracefully handles edge cases

#### Scenario: Performance validation
- **WHEN** manual testing is performed with 10,000+ character responses
- **THEN** streaming completes in under 5 seconds
- **AND** no session timeout or welcome message re-appearance occurs
- **AND** users perceive the streaming as smooth and responsive

### Requirement: Visual Mana Symbol Rendering

The UI SHALL render mana costs and symbols using Scryfall's SVG images instead of plain text notation, with graceful fallback to text when visual rendering is unavailable.

#### Scenario: Display mana cost with visual symbols in card details

- **GIVEN** a card with mana cost `{2}{R}{G}` is being displayed
- **WHEN** the card details are rendered via `format_card_details()`
- **AND** visual symbols are enabled
- **THEN** the mana cost SHALL be displayed as three inline images
- **AND** the first image SHALL display the {2} symbol from Scryfall CDN
- **AND** the second image SHALL display the {R} symbol (red mana)
- **AND** the third image SHALL display the {G} symbol (green mana)
- **AND** each image SHALL have alt text matching the symbol notation (e.g., alt="{R}")
- **AND** images SHALL be styled with class "mana-symbol" for consistent sizing

#### Scenario: Display mana cost with visual symbols in card lists

- **GIVEN** a card list contains cards with mana costs
- **WHEN** the card list is formatted via `format_card_list()`
- **AND** visual symbols are enabled
- **THEN** all mana costs SHALL render with visual SVG symbols
- **AND** symbols SHALL be inline with card names and text
- **AND** symbols SHALL maintain consistent height with surrounding text

#### Scenario: Display mana symbols in deck lists

- **GIVEN** a deck contains cards with mana costs
- **WHEN** the deck is displayed via `format_deck_for_display()`
- **AND** visual symbols are enabled
- **THEN** all card mana costs SHALL render with visual symbols
- **AND** symbols SHALL be grouped and aligned correctly in deck list entries

#### Scenario: Fallback to text when visual symbols disabled

- **GIVEN** visual symbols are disabled via configuration
- **WHEN** any card with mana cost is displayed
- **THEN** the mana cost SHALL render as plain text notation (e.g., "{2}{R}{G}")
- **AND** text SHALL be properly escaped to prevent HTML injection

#### Scenario: Fallback to text when symbol not found

- **GIVEN** a card has an unrecognized symbol in mana cost
- **WHEN** the symbol is not in Scryfall's symbology cache
- **THEN** the system SHALL log a warning
- **AND** the unrecognized symbol SHALL render as text
- **AND** other recognized symbols SHALL still render visually

#### Scenario: Handle hybrid mana symbols

- **GIVEN** a card with hybrid mana cost `{W/U}` (white/blue)
- **WHEN** the mana cost is rendered visually
- **THEN** the hybrid symbol SHALL display as a single image
- **AND** the image SHALL show Scryfall's hybrid mana symbol
- **AND** alt text SHALL be "{W/U}"

#### Scenario: Handle Phyrexian mana symbols

- **GIVEN** a card with Phyrexian mana cost `{W/P}` (white/Phyrexian)
- **WHEN** the mana cost is rendered visually
- **THEN** the Phyrexian symbol SHALL display as a single image
- **AND** the image SHALL show Scryfall's Phyrexian mana symbol
- **AND** alt text SHALL be "{W/P}"

#### Scenario: Handle special symbols (tap, untap, snow)

- **GIVEN** a card with oracle text containing special symbols like {T} (tap) or {Q} (untap)
- **WHEN** the oracle text is rendered
- **THEN** special symbols SHALL render as visual images
- **AND** images SHALL use Scryfall's SVG for the symbol
- **AND** symbols SHALL be inline with surrounding text

#### Scenario: Handle colorless and generic mana

- **GIVEN** a card with mana cost `{5}{C}` (5 generic, 1 colorless)
- **WHEN** the mana cost is rendered visually
- **THEN** the {5} symbol SHALL display as Scryfall's generic mana 5 symbol
- **AND** the {C} symbol SHALL display as Scryfall's colorless mana symbol
- **AND** symbols SHALL be visually distinct from each other

### Requirement: Scryfall Symbology API Integration

The system SHALL integrate with Scryfall's Card Symbols API to fetch symbol metadata and SVG URIs, with in-memory caching for performance.

#### Scenario: Fetch all symbols on first use

- **GIVEN** the application starts with empty symbol cache
- **WHEN** the first card with mana symbols is displayed
- **THEN** the system SHALL make a single GET request to `https://api.scryfall.com/symbology`
- **AND** the response SHALL be parsed as JSON containing card symbol objects
- **AND** each symbol object SHALL be cached with keys: symbol, svg_uri, colors, english
- **AND** subsequent symbol lookups SHALL use the cache without API calls

#### Scenario: Cache lookup for symbol SVG URL

- **GIVEN** the symbol cache is populated with Scryfall symbols
- **WHEN** a formatter requests the SVG URL for "{R}"
- **THEN** the system SHALL return `https://svgs.scryfall.io/card-symbols/R.svg` from cache
- **AND** no API call SHALL be made

#### Scenario: Handle API timeout gracefully

- **GIVEN** the Scryfall API is slow or unresponsive
- **WHEN** fetching symbology data times out after 5 seconds
- **THEN** the system SHALL log an error message
- **AND** SHALL fall back to text notation for all symbols
- **AND** the application SHALL continue functioning normally

#### Scenario: Handle API error response

- **GIVEN** the Scryfall API returns a 5xx error
- **WHEN** attempting to fetch symbology data
- **THEN** the system SHALL log the error with details
- **AND** SHALL fall back to text notation for all symbols
- **AND** SHALL retry on the next application restart (no persistent failure state)

#### Scenario: Populate cache with symbol metadata

- **GIVEN** a successful API response from `/symbology`
- **WHEN** parsing the response data
- **THEN** the cache SHALL store each symbol with structure:
  ```python
  {
    "symbol": "{R}",
    "svg_uri": "https://svgs.scryfall.io/card-symbols/R.svg",
    "colors": ["R"],
    "english": "one red mana",
    "mana_value": 1.0
  }
  ```
- **AND** cache SHALL be indexed by symbol string for O(1) lookup

### Requirement: Symbol Rendering Configuration

The system SHALL provide configuration to toggle between visual and text symbol rendering for accessibility and debugging purposes.

#### Scenario: Enable visual symbols by default

- **GIVEN** no explicit configuration is set
- **WHEN** the application initializes
- **THEN** visual symbols SHALL be enabled by default
- **AND** all mana symbols SHALL render as images

#### Scenario: Disable visual symbols via environment variable

- **GIVEN** the environment variable `VISUAL_MANA_SYMBOLS=false` is set
- **WHEN** any formatter renders mana symbols
- **THEN** all symbols SHALL render as plain text notation
- **AND** no API calls to Scryfall SHALL be made

#### Scenario: Disable visual symbols via Chainlit config

- **GIVEN** the Chainlit config file has `features.visual_symbols = false`
- **WHEN** any formatter renders mana symbols
- **THEN** all symbols SHALL render as plain text notation

### Requirement: Symbol Display Styling

The system SHALL provide CSS styling for mana symbols to ensure consistent sizing, alignment, and spacing across all UI contexts.

#### Scenario: Style symbols with consistent height

- **GIVEN** visual mana symbols are rendered in any context
- **WHEN** the HTML is styled with CSS
- **THEN** the `.mana-symbol` class SHALL set `height: 1em`
- **AND** symbols SHALL scale proportionally with surrounding text
- **AND** `width: auto` SHALL maintain aspect ratio

#### Scenario: Align symbols vertically with text

- **GIVEN** mana symbols are inline with card names or oracle text
- **WHEN** rendered in the UI
- **THEN** symbols SHALL have `vertical-align: middle` or `vertical-align: text-bottom`
- **AND** symbols SHALL not appear higher or lower than surrounding text baseline

#### Scenario: Space symbols appropriately

- **GIVEN** multiple mana symbols are adjacent (e.g., {2}{R}{G})
- **WHEN** rendered as images
- **THEN** each symbol SHALL have small horizontal margin (1-2px)
- **AND** symbols SHALL not overlap or appear cramped
- **AND** spacing SHALL be visually similar to official MTG card layouts

#### Scenario: Display symbols inline with content

- **GIVEN** mana symbols appear in card lists, details, or deck views
- **WHEN** rendered in markdown or HTML
- **THEN** symbols SHALL use `display: inline-block`
- **AND** symbols SHALL flow naturally within text lines
- **AND** line breaks SHALL occur at word boundaries, not mid-symbol

### Requirement: Accessibility and Fallback

The system SHALL ensure mana symbols are accessible to screen readers and provide robust fallback when visual rendering fails.

#### Scenario: Provide alt text for all symbol images

- **GIVEN** a mana symbol is rendered as an IMG tag
- **WHEN** the HTML is generated
- **THEN** the IMG tag SHALL include an `alt` attribute with the symbol notation
- **AND** alt text SHALL match the original notation (e.g., `alt="{R}"`)
- **AND** screen readers SHALL announce the symbol text

#### Scenario: Escape text fallback for HTML safety

- **GIVEN** visual symbols are disabled or unavailable
- **WHEN** mana cost is rendered as text
- **THEN** the text SHALL be HTML-escaped to prevent injection
- **AND** special characters like `<`, `>`, `&` SHALL be properly encoded

#### Scenario: Log symbol rendering failures

- **GIVEN** a symbol fails to render visually
- **WHEN** the error occurs
- **THEN** the system SHALL log a warning with details:
  - Symbol that failed
  - Reason (API error, not found, timeout, etc.)
  - Context (card name, mana cost)
- **AND** the log SHALL be at WARNING level (not ERROR)
- **AND** the failure SHALL not block other operations

#### Scenario: Maintain readability with text fallback

- **GIVEN** a card mana cost rendered as text due to fallback
- **WHEN** displayed in any UI context
- **THEN** the text notation SHALL remain readable and properly formatted
- **AND** curly braces SHALL be preserved (e.g., "{2}{R}{G}" not "2RG")
- **AND** text SHALL be distinguishable from card names or descriptions

### Requirement: Persistent Deck Information Sidebar
The system SHALL display active deck information in a persistent sidebar using Chainlit's ElementSidebar API, providing continuous visibility of deck context during deck building, including strategy information.

#### Scenario: Sidebar displays when deck is active
- **WHEN** a user has an active deck loaded in their session
- **AND** the user is viewing the chat interface
- **THEN** a sidebar appears on the side of the chat
- **AND** the sidebar title shows "🃏 Active Deck"
- **AND** the sidebar displays deck name, ID, format, strategy (if set), and colors
- **AND** the sidebar shows current mainboard card count

#### Scenario: Sidebar closes when no active deck
- **WHEN** a user has no active deck (new session or deleted deck)
- **AND** the chat interface loads
- **THEN** the sidebar does NOT appear
- **AND** the chat interface shows only the main conversation area

#### Scenario: Sidebar updates after deck creation
- **WHEN** a user creates a new deck via the `create_deck` tool with strategy
- **THEN** the sidebar appears immediately after creation
- **AND** the sidebar displays the newly created deck's information including strategy
- **AND** the sidebar shows 0 cards in mainboard initially

#### Scenario: Sidebar updates after loading deck
- **WHEN** a user loads an existing deck via the `load_deck` tool
- **THEN** the sidebar updates immediately after loading
- **AND** the sidebar displays the loaded deck's information including strategy (if set)
- **AND** the sidebar shows the current card count from the loaded deck

#### Scenario: Sidebar updates after adding cards
- **WHEN** a user adds cards to the active deck via `add_card_to_deck`
- **THEN** the sidebar card count updates to reflect the new total
- **AND** the sidebar updates without requiring a page refresh
- **AND** the update happens immediately after the tool completes

#### Scenario: Sidebar updates after strategy change
- **WHEN** a user updates the deck strategy via `update_deck_strategy` tool
- **THEN** the sidebar strategy field updates immediately
- **AND** the new strategy text appears in the sidebar
- **AND** the update happens without requiring a page refresh

### Requirement: Deck Information Formatting
The system SHALL format deck information in the sidebar as clear, readable markdown text with all relevant deck attributes, including the optional strategy field.

#### Scenario: Sidebar shows all deck attributes
- **WHEN** the sidebar displays deck information
- **THEN** the sidebar shows deck name in bold markdown
- **AND** the sidebar shows deck ID on a separate line
- **AND** the sidebar shows format (or "All" if no format specified)
- **AND** if strategy is set, the sidebar shows "Strategy: {strategy}" on a separate line
- **AND** the sidebar shows color identity (or "Colorless" if no colors)
- **AND** the sidebar shows current card count with "X/60" format

#### Scenario: Sidebar displays deck with strategy
- **WHEN** the sidebar displays deck information for a deck with strategy="Fast aggro with burn spells"
- **THEN** the sidebar includes a line reading "Strategy: Fast aggro with burn spells"
- **AND** the strategy appears after the format and before the color identity

#### Scenario: Sidebar displays deck without strategy
- **WHEN** the sidebar displays deck information for a deck with strategy=NULL
- **THEN** the sidebar does NOT show a strategy line
- **AND** no blank "Strategy:" line appears
- **AND** the sidebar layout remains consistent with other fields

#### Scenario: Sidebar truncates long strategy text
- **WHEN** the sidebar displays a deck with strategy longer than 200 characters
- **THEN** the sidebar displays only the first 200 characters
- **AND** the truncated text ends with "..." to indicate truncation
- **AND** the full strategy is still stored in the database

#### Scenario: Sidebar handles empty color identity
- **WHEN** a deck has no color identity (colorless deck)
- **THEN** the sidebar displays "Colorless" for the colors field
- **AND** no blank lines or "None" values appear

#### Scenario: Sidebar handles "All" format
- **WHEN** a deck has format set to None or "all"
- **THEN** the sidebar displays "All" for the format field
- **AND** the format is shown consistently with other format values

### Requirement: Sidebar Lifecycle Management
The system SHALL manage sidebar state throughout the user session, updating in response to deck operations.

#### Scenario: Sidebar initializes on session start
- **WHEN** a new chat session starts via `on_chat_start()`
- **THEN** the `update_deck_sidebar()` function is called
- **AND** if an active deck exists in session, sidebar appears
- **AND** if no active deck exists, sidebar remains closed

#### Scenario: Sidebar persists across messages
- **WHEN** a user with an active deck sends multiple messages
- **THEN** the sidebar remains visible across all messages
- **AND** the sidebar content does NOT disappear between messages
- **AND** the sidebar maintains the most recent deck state

#### Scenario: Sidebar closes after deck deletion
- **WHEN** a user deletes the active deck via `delete_deck`
- **THEN** the sidebar closes immediately after deletion
- **AND** the sidebar does NOT show stale deck information

### Requirement: UI Layer Implementation Pattern
The system SHALL implement sidebar updates as a UI layer helper function without modifying agent layer code.

#### Scenario: Sidebar helper in UI module
- **WHEN** the `src/ui/app.py` code is examined
- **THEN** an `update_deck_sidebar()` helper function exists
- **AND** the function retrieves deck context from `cl.user_session`
- **AND** the function uses `cl.ElementSidebar.set_elements()` API
- **AND** the function uses `cl.Text` element for formatted content

#### Scenario: Agent layer remains unchanged
- **WHEN** the agent layer code is examined
- **THEN** agent tools do NOT directly reference `update_deck_sidebar()`
- **AND** agent tools do NOT import sidebar-related code
- **AND** sidebar updates are triggered in UI layer after tool execution

#### Scenario: Tool integration via UI wrapper
- **WHEN** deck tools are called from the UI layer
- **THEN** the UI layer calls `update_deck_sidebar()` after successful tool execution
- **AND** the sidebar update happens in the UI message handler
- **AND** the pattern maintains UI/agent separation

### Requirement: Card Name Hover Preview
The system SHALL display card images as hover previews when users mouse over card names in chat messages.

#### Scenario: Hover shows card image
- **WHEN** a user hovers their mouse over a card name in a chat message
- **THEN** a tooltip appears showing the card's image from Scryfall CDN
- **AND** the tooltip is positioned near the card name
- **AND** the tooltip disappears when the mouse moves away
- **AND** the tooltip does not obstruct other content unnecessarily

#### Scenario: Card image URL available
- **WHEN** a card is displayed with a valid image_uris field
- **THEN** the card name is wrapped in an HTML span element
- **AND** the span element contains a data-image-url attribute with the Scryfall CDN URL
- **AND** the span element has a CSS class for hover styling

#### Scenario: Card image URL unavailable
- **WHEN** a card is displayed without a valid image_uris field
- **THEN** the card name is displayed as plain text
- **AND** no hover preview is available
- **AND** no error is raised or logged

### Requirement: Card Hover CSS Styling
The system SHALL provide CSS styles for card image hover previews that work across different screen sizes and contexts, with support for configurable positioning.

#### Scenario: Responsive hover preview styling
- **GIVEN** the card-preview.css file is loaded
- **THEN** it defines styles for card name hover elements
- **AND** it supports both left and right positioning via CSS classes
- **AND** hover tooltip dimensions are responsive (250px desktop, 175px tablet, 140px mobile)
- **AND** tooltips maintain MTG card aspect ratio (5:7)
- **AND** tooltips use absolute positioning relative to the card name span

#### Scenario: Right-side hover positioning
- **GIVEN** a card name has the "card-hover-right" CSS class
- **WHEN** the card is hovered
- **THEN** the tooltip appears to the right of the card name
- **AND** the tooltip is offset appropriately to prevent text overlap

#### Scenario: Left-side hover positioning
- **GIVEN** a card name has the "card-hover-left" CSS class
- **WHEN** the card is hovered
- **THEN** the tooltip appears to the left of the card name
- **AND** the tooltip is offset appropriately to prevent text overlap
- **AND** the tooltip is positioned to avoid clipping off the screen edge

### Requirement: Card Hover Feature Toggle
The system SHALL allow the card image hover feature to be disabled via environment variable.

#### Scenario: Feature enabled by default
- **WHEN** the CARD_IMAGE_HOVER_ENABLED environment variable is not set
- **THEN** card names are wrapped with hover functionality
- **AND** card image previews appear on hover

#### Scenario: Feature explicitly disabled
- **WHEN** the CARD_IMAGE_HOVER_ENABLED environment variable is set to "false"
- **THEN** card names are displayed as plain text
- **AND** no hover HTML wrapper is applied
- **AND** no card image previews appear

#### Scenario: Environment variable documented
- **WHEN** the .env.example file is examined
- **THEN** it includes CARD_IMAGE_HOVER_ENABLED with description
- **AND** it documents the default value (true)
- **AND** it explains acceptable values (true/false)

### Requirement: Card Hover in All Display Contexts
The system SHALL apply card image hover functionality consistently across all card display contexts.

#### Scenario: Hover in card lookup results
- **WHEN** a user performs a card lookup and receives results
- **THEN** the card name in the result has hover preview enabled
- **AND** hovering displays the card image

#### Scenario: Hover in card search results
- **WHEN** a user performs a card search and receives multiple results
- **THEN** each card name in the results list has hover preview enabled
- **AND** hovering any card name displays its corresponding image

#### Scenario: Hover in deck view output
- **WHEN** a user views a deck with the view_deck tool
- **THEN** each card name in the deck list has hover preview enabled
- **AND** hovering any card name displays its corresponding image

#### Scenario: Hover in sidebar deck display
- **WHEN** a deck is active and displayed in the sidebar
- **THEN** each card name in the sidebar list has hover preview enabled
- **AND** hovering any card name displays its corresponding image

### Requirement: Card Hover Image Size Selection
The system SHALL use the appropriate Scryfall image size for hover previews to balance quality and loading speed.

#### Scenario: Prefer normal size image
- **WHEN** a card has multiple image sizes in image_uris
- **THEN** the formatter extracts the "normal" size image URL
- **AND** uses it as the hover preview source

#### Scenario: Fallback to available size
- **WHEN** a card does not have "normal" size image
- **THEN** the formatter tries other available sizes in order: "large", "small", "png"
- **AND** uses the first available size as the hover preview source

#### Scenario: No image URL available
- **WHEN** a card has an empty or null image_uris field
- **THEN** no hover wrapper is applied
- **AND** the card name displays as plain text

### Requirement: Configurable Card Hover Direction
The system SHALL allow users to configure the direction (left or right) in which card image hover previews appear, to accommodate different screen layouts and prevent UI overlap.

#### Scenario: Configure hover direction to right
- **GIVEN** the CARD_HOVER_DIRECTION environment variable is set to "right"
- **WHEN** a card name with hover preview is rendered
- **THEN** the hover preview appears on the right side of the card name
- **AND** the CSS class "card-hover-right" is applied to the span element

#### Scenario: Configure hover direction to left
- **GIVEN** the CARD_HOVER_DIRECTION environment variable is set to "left"
- **WHEN** a card name with hover preview is rendered
- **THEN** the hover preview appears on the left side of the card name
- **AND** the CSS class "card-hover-left" is applied to the span element

#### Scenario: Default hover direction
- **GIVEN** the CARD_HOVER_DIRECTION environment variable is not set
- **WHEN** a card name with hover preview is rendered
- **THEN** the hover preview defaults to appearing on the right side
- **AND** the CSS class "card-hover-right" is applied

#### Scenario: Invalid hover direction
- **GIVEN** the CARD_HOVER_DIRECTION environment variable is set to "invalid"
- **WHEN** a card name with hover preview is rendered
- **THEN** the hover preview defaults to appearing on the right side
- **AND** a warning is logged about invalid configuration

### Requirement: Sidebar Deck Panel Hover Position
The system SHALL ensure the sidebar deck panel card hovers always appear on the left side to prevent overlap with main content hover previews, regardless of the global hover direction setting.

#### Scenario: Sidebar overrides global hover direction
- **GIVEN** the CARD_HOVER_DIRECTION is set to "right"
- **AND** a deck is active and displayed in the sidebar
- **WHEN** a card name in the sidebar is rendered with hover preview
- **THEN** the hover preview appears on the left side
- **AND** the CSS class "card-hover-left" is applied
- **AND** the global hover direction setting is ignored for sidebar cards

#### Scenario: Sidebar hover prevents overlap
- **GIVEN** the sidebar is displaying a deck card list
- **AND** the main chat area is displaying cards with right-side hovers
- **WHEN** a user hovers over cards in both areas
- **THEN** sidebar hovers appear on the left
- **AND** main content hovers appear on the right (or configured direction)
- **AND** no visual overlap occurs between the two hover previews

### Requirement: Magic-Themed Thinking Indicator
The system SHALL display Magic: The Gathering-themed thinking messages while the agent processes user requests to provide clear, on-brand feedback.

#### Scenario: Thinking message appears on request
- **WHEN** a user sends a message to the agent
- **THEN** a thinking message is immediately displayed
- **AND** the message uses Magic-themed text (e.g., "🧙‍♂️ Consulting the multiverse...")
- **AND** the message appears as a system message in the chat interface

#### Scenario: Thinking message removed after response
- **WHEN** the agent completes processing and begins responding
- **THEN** the thinking message is removed from the chat interface
- **AND** the removal occurs before the agent response streams
- **AND** no placeholder or artifact remains in the conversation

#### Scenario: Multiple thinking message variants
- **WHEN** users send multiple messages across different sessions
- **THEN** the thinking message text varies randomly for engagement
- **AND** messages include MTG-themed phrases like:
  - "🧙‍♂️ Consulting the multiverse..."
  - "⚡ Searching the aether..."
  - "📜 Shuffling through the library..."
  - "✨ Planeswalking..."
  - "🔮 Scrying for answers..."
- **AND** the random selection provides variety without user configuration

#### Scenario: Thinking message doesn't interfere with tool Steps
- **WHEN** the agent executes tool calls that display as Chainlit Steps
- **THEN** the thinking message does not overlap or interfere with Step display
- **AND** the thinking message is removed before Steps appear
- **AND** the visual flow remains: thinking message → removed → Steps → response

#### Scenario: Thinking message removed on error
- **WHEN** the agent encounters an error during processing
- **THEN** the thinking message is still removed from the interface
- **AND** the error message is displayed normally
- **AND** no thinking message remains visible after error display

#### Scenario: Thinking message uses Chainlit Message API
- **WHEN** the thinking message is created in code
- **THEN** it uses `cl.Message()` with appropriate content
- **AND** the message is sent with `.send()` method
- **AND** the message is removed with `.remove()` method after processing
- **AND** no custom CSS or JavaScript is required for basic functionality

### Requirement: Session Filters Display in Sidebar

The Chainlit UI SHALL display both the active games filter and format filter in the sidebar above the active deck information.

#### Scenario: Display both filters in sidebar

- **GIVEN** the session format_filter is "standard" and games_filter is ["arena"]
- **WHEN** the sidebar is rendered
- **THEN** a "Filters" section is displayed above the deck information
- **AND** the section shows "Format: Standard"
- **AND** the section shows "Games: Arena"

#### Scenario: Display format filter only

- **GIVEN** the session format_filter is "standard" and games_filter is None
- **WHEN** the sidebar is rendered
- **THEN** the sidebar shows "Format: Standard"
- **AND** the sidebar shows "Games: All" or omits the games line

#### Scenario: Display games filter only

- **GIVEN** the session format_filter is None and games_filter is ["arena"]
- **WHEN** the sidebar is rendered
- **THEN** the sidebar shows "Format: All" or omits the format line
- **AND** the sidebar shows "Games: Arena"

#### Scenario: Display multiple games in filter

- **GIVEN** the session games_filter is set to ["paper", "arena"]
- **WHEN** the sidebar is rendered
- **THEN** the sidebar shows "Games: Paper, Arena"
- **AND** games are comma-separated and capitalized

#### Scenario: No filters shows "All" or omits section

- **GIVEN** the session format_filter is None and games_filter is None
- **WHEN** the sidebar is rendered
- **THEN** the sidebar shows "Format: All, Games: All"
- **OR** the filters section is omitted entirely

#### Scenario: Filters update in real-time

- **GIVEN** the games filter is changed from None to ["arena"]
- **OR** the format filter is changed from None to "standard"
- **WHEN** the `set_games_filter()` or `set_format_filter()` tool completes
- **THEN** the sidebar updates automatically
- **AND** the new filter values are displayed immediately

#### Scenario: Filters positioned above deck info

- **GIVEN** filters are active and an active deck exists
- **WHEN** the sidebar is rendered
- **THEN** the filters section appears first (top of sidebar)
- **AND** the active deck information appears below the filters section

### Requirement: Games Availability Display on Cards

The card formatters SHALL display game availability information on all card displays.

#### Scenario: Single card display shows games

- **GIVEN** a card with games=["paper", "arena"]
- **WHEN** the card is formatted for display (e.g., lookup result)
- **THEN** the card details include "Available in: Paper, Arena"
- **AND** the games are comma-separated and capitalized

#### Scenario: Card list shows games in table

- **GIVEN** multiple cards with various games values are displayed in a table
- **WHEN** the card list is formatted
- **THEN** each card row includes a "Games" column
- **AND** the column shows comma-separated game values (e.g., "Paper, Arena, MTGO")

#### Scenario: Card with all games shows "All Platforms"

- **GIVEN** a card with games=["paper", "arena", "mtgo"]
- **WHEN** the card is formatted for display
- **THEN** the games are shown as "Paper, Arena, MTGO"
- **OR** a shorthand "All Platforms" is displayed

#### Scenario: Card with single game

- **GIVEN** a card with games=["paper"]
- **WHEN** the card is formatted for display
- **THEN** "Available in: Paper" is shown
- **AND** the singular form is used

#### Scenario: Games display in card hover tooltips

- **GIVEN** card hover tooltips are enabled
- **WHEN** a user hovers over a card name
- **THEN** the tooltip shows the card image
- **AND** a text overlay or caption shows games availability (e.g., "Arena")

### Requirement: Sidebar Update Trigger for Games Filter

The UI layer SHALL update the sidebar when the games filter changes, using the same trigger mechanism as deck updates.

#### Scenario: Games filter change triggers sidebar update

- **GIVEN** the `set_games_filter()` tool is executed
- **WHEN** the tool sets `deps.sidebar_needs_update = True`
- **THEN** the UI layer checks the flag after tool execution
- **AND** `update_deck_sidebar(session_id)` is called
- **AND** the sidebar refreshes with the new games filter

#### Scenario: Sidebar shows both filters and deck

- **GIVEN** session has format_filter="standard", games_filter=["arena"], and an active deck
- **WHEN** the sidebar is rendered
- **THEN** the sidebar displays (in order from top):
  - **Filters Section:**
    - Format: Standard
    - Games: Arena
  - **Deck Section:**
    - Active Deck: [deck name and details]
    - Card list


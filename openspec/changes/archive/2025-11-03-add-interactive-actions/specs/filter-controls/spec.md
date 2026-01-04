# filter-controls Specification Delta

**Target Spec:** `chainlit-ui`

## ADDED Requirements

### Requirement: Format Filter Action Buttons on Startup
The system SHALL display format filter selection buttons when the chat session starts to provide quick access to format filtering.

#### Scenario: Format buttons appear on startup
- **WHEN** a user starts a new chat session (`@cl.on_chat_start`)
- **THEN** a message appears with format selection action buttons
- **AND** the buttons include "Standard" and "All Formats" options
- **AND** the buttons use Lucide icons ("zap" for Standard, "globe" for All Formats)
- **AND** the buttons appear after the welcome message

#### Scenario: Format action button configuration
- **WHEN** format selection buttons are created
- **THEN** each button is a `cl.Action` instance
- **AND** each button has `name="set_format_filter"`
- **AND** each button has a payload with `{"format": "standard"}` or `{"format": None}`
- **AND** each button has a descriptive label ("Standard", "All Formats")
- **AND** each button has a tooltip explaining the filter effect

#### Scenario: Format selection message stored
- **WHEN** the format selection message is sent
- **THEN** the message reference is stored in user session with key "format_selection_message"
- **AND** the reference can be retrieved in action callbacks for cleanup

### Requirement: Games Platform Filter Action Buttons on Startup
The system SHALL display games platform filter selection buttons when the chat session starts to enable filtering by card availability (Arena, Paper, MTGO).

#### Scenario: Games buttons appear on startup
- **WHEN** a user starts a new chat session (`@cl.on_chat_start`)
- **THEN** a message appears with games platform selection action buttons
- **AND** the buttons include "Arena", "Paper", "MTGO", and "All Platforms" options
- **AND** the buttons use Lucide icons ("monitor", "book-open", "laptop", "globe")
- **AND** the buttons appear after the format selection message

#### Scenario: Games action button configuration
- **WHEN** games platform selection buttons are created
- **THEN** each button is a `cl.Action` instance
- **AND** each button has `name="set_games_filter"`
- **AND** each button has a payload with `{"games": ["arena"]}`, `{"games": ["paper"]}`, `{"games": ["mtgo"]}`, or `{"games": None}`
- **AND** each button has a descriptive label ("Arena", "Paper", "MTGO", "All Platforms")
- **AND** each button has a tooltip explaining the platform filter

#### Scenario: Games selection message stored
- **WHEN** the games platform selection message is sent
- **THEN** the message reference is stored in user session with key "games_selection_message"
- **AND** the reference can be retrieved in action callbacks for cleanup

### Requirement: Format Filter Action Callback
The system SHALL process format filter button clicks to update session state without invoking the agent.

#### Scenario: Format filter set via action
- **WHEN** a user clicks a format selection button
- **THEN** the `set_format_filter` action callback is invoked
- **AND** the callback retrieves format value from `action.payload.get("format")`
- **AND** the callback retrieves session ID from `cl.user_session.get("session_id")`
- **AND** the callback calls `deps._session_manager.set_format_filter(session_id, format_val)`
- **AND** the session state is updated immediately without agent invocation

#### Scenario: Format selection buttons removed after click
- **WHEN** the format filter callback completes successfully
- **THEN** the callback retrieves the format selection message from user session
- **AND** the callback calls `await message.remove_actions()`
- **AND** all format selection buttons disappear from the UI
- **AND** the message content remains visible

#### Scenario: Format filter confirmation message
- **WHEN** the format filter is set successfully
- **THEN** a confirmation message is sent to the chat
- **AND** the message text is "Format set to **{format_name}**" (e.g., "Format set to **Standard**")
- **AND** the format name is capitalized ("Standard") or "All Formats" for None

#### Scenario: Format filter error handling
- **WHEN** the format filter callback encounters an error
- **THEN** the error is caught and logged
- **AND** a user-friendly error message is sent ("Error setting format: {error}")
- **AND** the buttons are NOT removed (user can retry)

### Requirement: Games Platform Filter Action Callback
The system SHALL process games platform filter button clicks to update session state without invoking the agent.

#### Scenario: Games filter set via action
- **WHEN** a user clicks a games platform selection button
- **THEN** the `set_games_filter` action callback is invoked
- **AND** the callback retrieves games value from `action.payload.get("games")`
- **AND** the callback retrieves session ID from `cl.user_session.get("session_id")`
- **AND** the callback calls `deps._session_manager.set_games_filter(session_id, games_val)`
- **AND** the session state is updated immediately without agent invocation

#### Scenario: Games selection buttons removed after click
- **WHEN** the games filter callback completes successfully
- **THEN** the callback retrieves the games selection message from user session
- **AND** the callback calls `await message.remove_actions()`
- **AND** all games platform buttons disappear from the UI
- **AND** the message content remains visible

#### Scenario: Games filter confirmation message
- **WHEN** the games filter is set successfully
- **AND** the filter is not None
- **THEN** a confirmation message is sent to the chat
- **AND** the message text is "Platform filter set to **{platform_name}**"
- **AND** the platform name is "MTG Arena", "Paper Magic", "Magic Online", or "All Platforms"

#### Scenario: Games filter cleared confirmation
- **WHEN** the games filter is set to None (All Platforms)
- **THEN** a confirmation message is sent: "Platform filter cleared. Searches will show all cards."

#### Scenario: Games filter error handling
- **WHEN** the games filter callback encounters an error
- **THEN** the error is caught and logged
- **AND** a user-friendly error message is sent
- **AND** the buttons are NOT removed (user can retry)

### Requirement: Filter State Persistence Across Messages
The system SHALL maintain filter state set via actions across subsequent conversational messages.

#### Scenario: Format filter persists for card queries
- **WHEN** a user clicks "Standard" format button
- **AND** the format filter is set to "standard"
- **AND** the user sends a conversational card query (e.g., "find red creatures")
- **THEN** the agent tools receive `deps.format_filter="standard"`
- **AND** the card query returns only Standard-legal cards
- **AND** the user does NOT need to re-specify the format filter

#### Scenario: Games filter persists for card queries
- **WHEN** a user clicks "Arena" games button
- **AND** the games filter is set to ["arena"]
- **AND** the user sends a conversational card query
- **THEN** the agent tools receive `deps.games_filter=["arena"]`
- **AND** the card query returns only Arena-available cards
- **AND** the user does NOT need to re-specify the games filter

#### Scenario: Filters persist across multiple queries
- **WHEN** both format and games filters are set via actions
- **AND** the user sends multiple card queries in the same session
- **THEN** both filters remain active for all subsequent queries
- **AND** the filters are not cleared between messages
- **AND** the user can see filter state in agent responses (if applicable)

### Requirement: Backward Compatibility with Conversational Filters
The system SHALL maintain support for conversational filter commands alongside action-based filter selection.

#### Scenario: Conversational format command still works
- **WHEN** a user types "only show standard cards" conversationally
- **THEN** the agent invokes the `set_format_filter` tool
- **AND** the format filter is set to "standard"
- **AND** the behavior is identical to clicking the "Standard" button
- **AND** subsequent queries respect the filter

#### Scenario: Conversational games command still works
- **WHEN** a user types "only show arena cards" conversationally
- **THEN** the agent invokes the `set_games_filter` tool
- **AND** the games filter is set to ["arena"]
- **AND** the behavior is identical to clicking the "Arena" button

#### Scenario: Conversational commands can override action filters
- **WHEN** a user sets format via action button
- **AND** later types a conversational command to change the filter
- **THEN** the new filter replaces the old filter
- **AND** the conversational command takes precedence
- **AND** no conflicts or errors occur

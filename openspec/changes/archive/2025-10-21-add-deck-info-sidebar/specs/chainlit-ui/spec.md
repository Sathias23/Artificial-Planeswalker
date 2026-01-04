## ADDED Requirements

### Requirement: Persistent Deck Information Sidebar
The system SHALL display active deck information in a persistent sidebar using Chainlit's ElementSidebar API, providing continuous visibility of deck context during deck building.

#### Scenario: Sidebar displays when deck is active
- **WHEN** a user has an active deck loaded in their session
- **AND** the user is viewing the chat interface
- **THEN** a sidebar appears on the side of the chat
- **AND** the sidebar title shows "🃏 Active Deck"
- **AND** the sidebar displays deck name, ID, format, and colors
- **AND** the sidebar shows current mainboard card count

#### Scenario: Sidebar closes when no active deck
- **WHEN** a user has no active deck (new session or deleted deck)
- **AND** the chat interface loads
- **THEN** the sidebar does NOT appear
- **AND** the chat interface shows only the main conversation area

#### Scenario: Sidebar updates after deck creation
- **WHEN** a user creates a new deck via the `create_deck` tool
- **THEN** the sidebar appears immediately after creation
- **AND** the sidebar displays the newly created deck's information
- **AND** the sidebar shows 0 cards in mainboard initially

#### Scenario: Sidebar updates after loading deck
- **WHEN** a user loads an existing deck via the `load_deck` tool
- **THEN** the sidebar updates immediately after loading
- **AND** the sidebar displays the loaded deck's information
- **AND** the sidebar shows the current card count from the loaded deck

#### Scenario: Sidebar updates after adding cards
- **WHEN** a user adds cards to the active deck via `add_card_to_deck`
- **THEN** the sidebar card count updates to reflect the new total
- **AND** the sidebar updates without requiring a page refresh
- **AND** the update happens immediately after the tool completes

### Requirement: Deck Information Formatting
The system SHALL format deck information in the sidebar as clear, readable markdown text with all relevant deck attributes.

#### Scenario: Sidebar shows all deck attributes
- **WHEN** the sidebar displays deck information
- **THEN** the sidebar shows deck name in bold markdown
- **AND** the sidebar shows deck ID on a separate line
- **AND** the sidebar shows format (or "All" if no format specified)
- **AND** the sidebar shows color identity (or "Colorless" if no colors)
- **AND** the sidebar shows current card count with "X/60" format

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

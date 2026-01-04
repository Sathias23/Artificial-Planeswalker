# Quick Deck Load Specification

## Purpose

Enable one-click deck loading from deck list results by displaying action buttons for recent decks, reducing friction in deck management workflows.

## ADDED Requirements

### Requirement: List Decks Tool Returns Structured Deck Data

The `list_decks` tool SHALL return structured deck data alongside formatted text to enable UI rendering of quick-load action buttons.

#### Scenario: Tool returns structured deck list
- **GIVEN** a user has 8 saved decks in the database
- **WHEN** the agent invokes `list_decks(ctx)`
- **THEN** the tool returns a dict with keys: `has_decks`, `decks`, `formatted_text`
- **AND** `has_decks` is True
- **AND** `decks` is a list of Deck objects (Pydantic schemas) limited to top 5 recent decks
- **AND** `formatted_text` is the existing text-based deck table

#### Scenario: Tool returns only text when no decks exist
- **GIVEN** a user has no saved decks
- **WHEN** the agent invokes `list_decks(ctx)`
- **THEN** the tool returns a string (backward compatible text response)
- **AND** the string indicates no decks found

#### Scenario: Tool limits quick-load suggestions to top 5 recent decks
- **GIVEN** a user has 12 saved decks
- **WHEN** the tool prepares the response
- **THEN** the `decks` list contains exactly 5 decks
- **AND** decks are ordered by last modified timestamp (most recent first)
- **AND** the `formatted_text` includes all 12 decks (not limited to 5)

#### Scenario: Tool respects format filter parameter
- **GIVEN** a user has 3 Standard decks and 2 Modern decks
- **WHEN** the agent invokes `list_decks(ctx, format_filter="standard")`
- **THEN** the `decks` list contains only the 3 Standard decks
- **AND** the `formatted_text` shows only Standard decks

### Requirement: UI Renders Quick-Load Action Buttons for Decks

The UI layer SHALL detect deck list tool responses with structured data and render quick-load action buttons for each deck.

#### Scenario: Quick-load buttons displayed for deck list
- **GIVEN** the `list_decks` tool returns a dict with `has_decks=True` and 5 decks
- **WHEN** the UI message handler processes the tool response
- **THEN** 5 action buttons are rendered below the agent response
- **AND** each button has label "Load [Deck Name]" (e.g., "Load Mono Red Aggro")
- **AND** each button has payload `{"deck_id": "...", "deck_name": "...", "deck_format": "..."}`
- **AND** each button has a tooltip showing deck metadata: "[Format] • [Card Count] cards • [Color Identity]"
- **AND** each button uses a Lucide icon (e.g., "folder-open")

#### Scenario: No action buttons when no decks exist
- **GIVEN** the `list_decks` tool returns a string (no structured data)
- **WHEN** the UI message handler processes the tool response
- **THEN** no action buttons are rendered
- **AND** only the formatted text appears in the chat

### Requirement: Quick-Load Action Callback Implementation

The system SHALL implement a `quick_load_deck` action callback that loads a deck, updates the sidebar, and syncs the format filter.

#### Scenario: Successfully load deck via quick-load button
- **GIVEN** a user has a saved deck "Mono Red Aggro" with format "standard"
- **WHEN** the user clicks the "Load Mono Red Aggro" action button
- **THEN** the `quick_load_deck` callback is invoked with payload
- **AND** the callback retrieves `deck_id`, `deck_name`, and `deck_format` from payload
- **AND** the callback loads the deck via `deps.deck_repository.load_deck(deck_id)`
- **AND** the callback sets the active deck ID via `_session_manager.set_active_deck_id(session_id, deck_id)`
- **AND** the callback syncs format filter via `_session_manager.set_format_filter(session_id, deck_format)`
- **AND** the callback sets `deps.sidebar_needs_update = True`
- **AND** all quick-load action buttons are removed via `remove_all_actions("deck_list_message")`
- **AND** a confirmation message is sent: "Loaded deck 'Mono Red Aggro' (Standard format)"
- **AND** the sidebar updates to show the loaded deck

#### Scenario: Format filter synced to deck format on load
- **GIVEN** a user has the format filter set to "all"
- **WHEN** the user loads a Standard deck via quick-load button
- **THEN** the format filter is automatically set to "standard"
- **AND** subsequent card searches respect the Standard format filter
- **AND** the confirmation message indicates format sync: "Loaded deck 'Deck Name' (Standard format - filter synced)"

#### Scenario: Format filter cleared for "all formats" deck
- **GIVEN** a user loads a deck with format "all" or null
- **WHEN** the deck is loaded via quick-load button
- **THEN** the format filter is cleared (set to None)
- **AND** subsequent card searches show cards from all formats
- **AND** the confirmation message indicates no filter: "Loaded deck 'Deck Name' (all formats)"

#### Scenario: Error when deck not found
- **GIVEN** a deck was deleted between listing and quick-load click
- **WHEN** the user clicks a quick-load button
- **THEN** the callback attempts to load the deck
- **AND** the repository returns None (deck not found)
- **AND** an error message is sent: "Error: Deck '[Deck Name]' not found. It may have been deleted."
- **AND** all quick-load buttons are removed

#### Scenario: Error when deck_id missing from payload
- **GIVEN** a quick-load action callback is invoked
- **WHEN** the payload is missing `deck_id`
- **THEN** the callback logs an ERROR: "Invalid payload: missing deck_id"
- **AND** an error message is sent: "Error: Invalid deck data. Please try again."
- **AND** the action button is removed

### Requirement: Action Cleanup and Session Management

The system SHALL store deck list action message references for later cleanup and manage action lifecycle correctly.

#### Scenario: Store deck list message reference
- **GIVEN** the UI renders quick-load action buttons
- **WHEN** the buttons are attached to a message and sent
- **THEN** the message reference is stored via `store_action_message("deck_list_message", message)`
- **AND** the message can be retrieved later for bulk action removal

#### Scenario: Remove all quick-load buttons after successful load
- **GIVEN** 5 quick-load buttons are displayed
- **WHEN** a user clicks one button and successfully loads a deck
- **THEN** all 5 quick-load buttons are removed via `remove_all_actions("deck_list_message")`
- **AND** the UI is cleaned up (prevents redundant loads)

#### Scenario: Cleanup quick-load buttons on new deck list request
- **GIVEN** quick-load buttons are displayed from a previous `list_decks` call
- **WHEN** the user requests a new deck list
- **THEN** the old quick-load buttons are removed before displaying new buttons
- **AND** stale deck references are cleared

### Requirement: Error Handling and Logging

The system SHALL handle errors gracefully during quick-load operations and log all actions for debugging.

#### Scenario: Log successful deck load
- **GIVEN** a user clicks a quick-load button
- **WHEN** the deck is successfully loaded
- **THEN** an INFO log is written: "Loaded deck [deck_name] (ID: [deck_id]) via quick-load"
- **AND** the log includes session ID and format sync details

#### Scenario: Log errors during deck load
- **GIVEN** a user clicks a quick-load button
- **WHEN** an error occurs during deck loading
- **THEN** an ERROR log is written with exception details
- **AND** the error is logged with session ID and deck information
- **AND** a user-friendly error message is sent to the chat

#### Scenario: Handle missing payload fields
- **GIVEN** a quick-load action callback is invoked
- **WHEN** the payload is missing `deck_id` or `deck_name`
- **THEN** the callback logs an ERROR: "Invalid payload: missing deck_id or deck_name"
- **AND** an error message is sent: "Error: Invalid deck data. Please try again."
- **AND** all quick-load buttons are removed

### Requirement: Backward Compatibility

The system SHALL maintain backward compatibility with existing conversational deck loading.

#### Scenario: Conversational deck loading still works
- **GIVEN** a user types "load Mono Red Aggro"
- **WHEN** the agent invokes the `load_deck` tool
- **THEN** the deck is loaded via the existing tool (no changes)
- **AND** the format filter is synced (existing behavior)
- **AND** the sidebar updates (existing behavior)
- **AND** quick-load actions are an optional shortcut, not a replacement

#### Scenario: Agent layer remains UI-agnostic
- **GIVEN** the `list_decks` tool returns structured data
- **WHEN** the tool code is examined
- **THEN** the tool does NOT import Chainlit
- **AND** the tool returns plain Python types (dict with Deck objects)
- **AND** the UI layer handles action rendering independently

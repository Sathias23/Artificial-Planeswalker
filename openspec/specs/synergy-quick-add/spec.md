# synergy-quick-add Specification

## Purpose
TBD - created by archiving change enhance-deck-actions-phase2. Update Purpose after archive.
## Requirements
### Requirement: Synergy Tool Returns Structured Card Data

The synergy detection tool SHALL return structured card data alongside formatted text to enable UI rendering of quick-add action buttons.

#### Scenario: Tool returns structured synergy data
- **GIVEN** a user has an active deck with cards
- **WHEN** the agent invokes `detect_deck_synergies(ctx)`
- **THEN** the tool returns a dict with keys: `has_synergies`, `synergy_cards`, `formatted_text`
- **AND** `has_synergies` is a boolean indicating if synergies were detected
- **AND** `synergy_cards` is a list of Card objects (Pydantic schemas) for suggested cards
- **AND** `formatted_text` is the existing text-based synergy analysis

#### Scenario: Tool returns only text when no synergies detected
- **GIVEN** a user has an active deck with no synergies
- **WHEN** the agent invokes `detect_deck_synergies(ctx)`
- **THEN** the tool returns a string (backward compatible text response)
- **AND** the string indicates no synergies detected

#### Scenario: Tool limits synergy suggestions to top 7 cards
- **GIVEN** the synergy detection algorithm finds 15 potential synergy cards
- **WHEN** the tool prepares the response
- **THEN** the `synergy_cards` list contains at most 7 cards
- **AND** cards are ordered by synergy strength (highest first)
- **AND** the `formatted_text` includes all synergies (not limited to 7)

### Requirement: UI Renders Quick-Add Action Buttons for Synergies

The UI layer SHALL detect synergy tool responses with structured data and render quick-add action buttons for each suggested card.

#### Scenario: Quick-add buttons displayed for synergy suggestions
- **GIVEN** the synergy tool returns a dict with `has_synergies=True` and 5 cards in `synergy_cards`
- **WHEN** the UI message handler processes the tool response
- **THEN** 5 action buttons are rendered below the agent response
- **AND** each button has label "Add [Card Name]" (e.g., "Add Lightning Bolt")
- **AND** each button has payload `{"card_name": "...", "card_id": "..."}`
- **AND** each button has a tooltip "Add 1 copy to active deck"
- **AND** each button uses a Lucide icon (e.g., "plus-circle")

#### Scenario: No action buttons when synergies not detected
- **GIVEN** the synergy tool returns a string (no structured data)
- **WHEN** the UI message handler processes the tool response
- **THEN** no action buttons are rendered
- **AND** only the formatted text appears in the chat

### Requirement: Quick-Add Action Callback Implementation

The system SHALL implement an `add_suggested_card` action callback that adds a card to the active deck and updates the UI.

#### Scenario: Successfully add synergy card to active deck
- **GIVEN** a user has an active deck with fewer than 4 copies of "Lightning Bolt"
- **WHEN** the user clicks the "Add Lightning Bolt" action button
- **THEN** the `add_suggested_card` callback is invoked with payload
- **AND** the callback retrieves the `card_name` and `card_id` from the payload
- **AND** the callback adds 1 copy of the card to the active deck via `deps.deck_repository.add_card_to_deck`
- **AND** the callback sets `deps.sidebar_needs_update = True`
- **AND** the action button is removed via `await action.remove()`
- **AND** a confirmation message is sent: "Added Lightning Bolt to deck"
- **AND** the sidebar updates to show the new card

#### Scenario: Error when no active deck exists
- **GIVEN** a user has no active deck
- **WHEN** the user clicks a synergy quick-add button
- **THEN** the callback detects no active deck via `deps.active_deck_id is None`
- **AND** an error message is sent: "No active deck. Create a deck first to add cards."
- **AND** the action button is NOT removed (user can try again after creating deck)

#### Scenario: Error when card already at maximum copies
- **GIVEN** a user has an active deck with 4 copies of "Lightning Bolt"
- **WHEN** the user clicks "Add Lightning Bolt" action button
- **THEN** the callback attempts to add the card
- **AND** the repository raises a validation error (max 4 copies exceeded)
- **AND** an error message is sent: "Cannot add Lightning Bolt - deck already at maximum 4 copies"
- **AND** the action button is removed (operation not retryable without deck changes)

#### Scenario: Error when card not found
- **GIVEN** a synergy suggestion payload contains an invalid `card_id`
- **WHEN** the user clicks the action button
- **THEN** the callback attempts to add the card
- **AND** the repository returns an error (card not found)
- **AND** an error message is sent: "Error adding card: card not found"
- **AND** the action button is removed

### Requirement: Action Cleanup and Session Management

The system SHALL store synergy action message references for later cleanup and manage action lifecycle correctly.

#### Scenario: Store synergy message reference
- **GIVEN** the UI renders synergy quick-add action buttons
- **WHEN** the buttons are attached to a message and sent
- **THEN** the message reference is stored via `store_action_message("synergy_suggestions_message", message)`
- **AND** the message can be retrieved later for bulk action removal

#### Scenario: Remove synergy action button after successful add
- **GIVEN** a user clicks a synergy quick-add button
- **WHEN** the card is successfully added to the deck
- **THEN** the specific action button is removed via `await action.remove()`
- **AND** other synergy buttons remain visible (individual removal, not bulk)

#### Scenario: Cleanup all synergy buttons on deck change
- **GIVEN** synergy suggestions are displayed with action buttons
- **WHEN** the user loads a different deck
- **THEN** all synergy action buttons are removed via `remove_all_actions("synergy_suggestions_message")`
- **AND** stale suggestions are cleared

### Requirement: Error Handling and Logging

The system SHALL handle errors gracefully during synergy quick-add operations and log all actions for debugging.

#### Scenario: Log successful card addition
- **GIVEN** a user clicks a synergy quick-add button
- **WHEN** the card is successfully added
- **THEN** an INFO log is written: "Added [card_name] to deck [deck_id] via synergy quick-add"
- **AND** the log includes session ID for traceability

#### Scenario: Log errors during card addition
- **GIVEN** a user clicks a synergy quick-add button
- **WHEN** an error occurs during card addition
- **THEN** an ERROR log is written with exception details
- **AND** the error is logged with session ID and card information
- **AND** a user-friendly error message is sent to the chat

#### Scenario: Handle missing payload fields
- **GIVEN** a synergy action callback is invoked
- **WHEN** the payload is missing `card_name` or `card_id`
- **THEN** the callback logs an ERROR: "Invalid payload: missing card_name or card_id"
- **AND** an error message is sent: "Error: Invalid action data. Please try again."
- **AND** the action button is removed

### Requirement: Backward Compatibility

The system SHALL maintain backward compatibility with existing conversational synergy suggestions.

#### Scenario: Conversational synergy suggestions still work
- **GIVEN** a user types "suggest cards for my deck"
- **WHEN** the agent invokes synergy detection
- **THEN** the agent receives the structured response
- **AND** the agent can display the `formatted_text` to the user
- **AND** the user can add cards conversationally (e.g., "add Lightning Bolt")
- **AND** quick-add actions are an optional shortcut, not a replacement

#### Scenario: Agent layer remains UI-agnostic
- **GIVEN** the synergy tool returns structured data
- **WHEN** the tool code is examined
- **THEN** the tool does NOT import Chainlit
- **AND** the tool returns plain Python types (dict with Card objects)
- **AND** the UI layer handles action rendering independently


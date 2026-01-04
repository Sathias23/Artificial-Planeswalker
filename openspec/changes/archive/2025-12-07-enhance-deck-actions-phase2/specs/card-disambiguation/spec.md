# Card Disambiguation Specification

## Purpose

Enable one-click card selection from ambiguous search results by displaying action buttons when 2-5 similar cards are found, reducing friction in card lookup workflows.

## ADDED Requirements

### Requirement: Card Lookup Tool Returns Structured Suggestions

The `lookup_card_by_name` tool SHALL return structured card data when 2-5 similar matches are found to enable UI rendering of disambiguation action buttons.

#### Scenario: Tool returns structured disambiguation data for 2-5 matches
- **GIVEN** a user searches for "bolt" and 3 cards match (Lightning Bolt, Bolt Bend, Shock Bolt)
- **WHEN** the agent invokes `lookup_card_by_name(ctx, "bolt")`
- **THEN** the tool returns a dict with keys: `needs_disambiguation`, `matches`, `formatted_text`
- **AND** `needs_disambiguation` is True
- **AND** `matches` is a list of 3 Card objects (Pydantic schemas)
- **AND** `formatted_text` is the existing text-based disambiguation message

#### Scenario: Tool returns exact match when single card found
- **GIVEN** a user searches for "Lightning Bolt" (exact match)
- **WHEN** the agent invokes `lookup_card_by_name(ctx, "Lightning Bolt")`
- **THEN** the tool returns a string or single card details (backward compatible)
- **AND** no disambiguation actions are needed

#### Scenario: Tool returns text-only when 6+ matches found
- **GIVEN** a user searches for "dragon" and 20 cards match
- **WHEN** the agent invokes `lookup_card_by_name(ctx, "dragon")`
- **THEN** the tool returns a string (backward compatible text response)
- **AND** the string suggests refining the search query
- **AND** no disambiguation actions are rendered (too many matches)

#### Scenario: Tool limits disambiguation buttons to 5 matches
- **GIVEN** a user searches and 5 cards match
- **WHEN** the tool prepares the response
- **THEN** the `matches` list contains all 5 cards
- **AND** if 6+ matches exist, the tool returns text-only (threshold check)

### Requirement: UI Renders Disambiguation Action Buttons

The UI layer SHALL detect card lookup tool responses with structured disambiguation data and render action buttons for each matching card.

#### Scenario: Disambiguation buttons displayed for 2-5 matches
- **GIVEN** the `lookup_card_by_name` tool returns a dict with `needs_disambiguation=True` and 3 matches
- **WHEN** the UI message handler processes the tool response
- **THEN** 3 action buttons are rendered below the agent response
- **AND** each button has label showing card name and type (e.g., "Lightning Bolt (Instant)")
- **AND** each button has payload `{"card_id": "...", "card_name": "...", "context": "view"}`
- **AND** each button has a tooltip "View card details"
- **AND** each button uses a Lucide icon (e.g., "eye")

#### Scenario: No action buttons when single exact match
- **GIVEN** the `lookup_card_by_name` tool returns a string or single card
- **WHEN** the UI message handler processes the tool response
- **THEN** no action buttons are rendered
- **AND** only the card details appear in the chat

#### Scenario: No action buttons when too many matches
- **GIVEN** the `lookup_card_by_name` tool returns text-only for 6+ matches
- **WHEN** the UI message handler processes the tool response
- **THEN** no action buttons are rendered
- **AND** the agent suggests refining the search conversationally

### Requirement: Disambiguation Action Callback with Context Awareness

The system SHALL implement a `select_card` action callback that handles card selection with context-aware behavior (view vs add).

#### Scenario: View context - display card details
- **GIVEN** a disambiguation button has payload with `context="view"`
- **WHEN** the user clicks the button
- **THEN** the `select_card` callback is invoked
- **AND** the callback retrieves `card_id`, `card_name`, and `context` from payload
- **AND** the callback loads card details via `deps.card_repository.find_by_id(card_id)`
- **AND** the callback formats card details using `format_card_for_display(card)`
- **AND** the card details are sent as a message
- **AND** all disambiguation buttons are removed via `remove_all_actions("disambiguation_message")`

#### Scenario: Add context - add card to active deck
- **GIVEN** a disambiguation button has payload with `context="add"`
- **WHEN** the user clicks the button
- **THEN** the `select_card` callback is invoked
- **AND** the callback retrieves `card_id` and `card_name` from payload
- **AND** the callback adds 1 copy to active deck via `deps.deck_repository.add_card_to_deck`
- **AND** the callback sets `deps.sidebar_needs_update = True`
- **AND** all disambiguation buttons are removed
- **AND** a confirmation message is sent: "Added [Card Name] to deck"
- **AND** the sidebar updates to show the new card

#### Scenario: Add context error - no active deck
- **GIVEN** a disambiguation button has payload with `context="add"`
- **AND** the user has no active deck
- **WHEN** the user clicks the button
- **THEN** the callback detects no active deck via `deps.active_deck_id is None`
- **AND** an error message is sent: "No active deck. Create a deck first to add cards."
- **AND** the disambiguation buttons remain visible (user can try again after creating deck)

#### Scenario: Default to view context when context ambiguous
- **GIVEN** a disambiguation button payload has no `context` field
- **WHEN** the user clicks the button
- **THEN** the callback defaults to `context="view"`
- **AND** card details are displayed (safe default behavior)

### Requirement: Context Detection from Tool Invocation

The system SHALL detect user intent (view vs add) when rendering disambiguation actions based on the tool invocation context.

#### Scenario: Detect add intent from user message
- **GIVEN** a user types "add bolt to my deck"
- **WHEN** the agent invokes `lookup_card_by_name(ctx, "bolt")` with disambiguation
- **THEN** the UI detects "add" intent from the original user message
- **AND** the disambiguation buttons are rendered with `context="add"`
- **AND** button labels include "Add" prefix (e.g., "Add Lightning Bolt")
- **AND** button tooltips say "Add 1 copy to active deck"

#### Scenario: Default to view intent for generic searches
- **GIVEN** a user types "search for bolt"
- **WHEN** the agent invokes `lookup_card_by_name(ctx, "bolt")` with disambiguation
- **THEN** the UI defaults to "view" intent (no "add" keywords detected)
- **AND** the disambiguation buttons are rendered with `context="view"`
- **AND** button labels are plain card names (e.g., "Lightning Bolt")
- **AND** button tooltips say "View card details"

#### Scenario: Add intent keywords detection
- **GIVEN** a user message contains keywords: "add", "include", "put in deck"
- **WHEN** the UI processes disambiguation signals
- **THEN** the context is set to "add"
- **AND** buttons enable card addition

#### Scenario: View intent keywords detection
- **GIVEN** a user message contains keywords: "show", "view", "look up", "find", "search"
- **WHEN** the UI processes disambiguation signals
- **THEN** the context is set to "view" (default)
- **AND** buttons display card details

### Requirement: Action Cleanup and Session Management

The system SHALL store disambiguation action message references for later cleanup and manage action lifecycle correctly.

#### Scenario: Store disambiguation message reference
- **GIVEN** the UI renders disambiguation action buttons
- **WHEN** the buttons are attached to a message and sent
- **THEN** the message reference is stored via `store_action_message("disambiguation_message", message)`
- **AND** the message can be retrieved later for bulk action removal

#### Scenario: Remove all disambiguation buttons after selection
- **GIVEN** 3 disambiguation buttons are displayed
- **WHEN** a user clicks one button
- **THEN** all 3 disambiguation buttons are removed via `remove_all_actions("disambiguation_message")`
- **AND** the UI is cleaned up (prevents redundant selections)

#### Scenario: Cleanup disambiguation buttons on new search
- **GIVEN** disambiguation buttons are displayed from a previous search
- **WHEN** the user performs a new card search
- **THEN** the old disambiguation buttons are removed before displaying new results
- **AND** stale card references are cleared

### Requirement: Error Handling and Logging

The system SHALL handle errors gracefully during disambiguation operations and log all actions for debugging.

#### Scenario: Log successful card selection
- **GIVEN** a user clicks a disambiguation button
- **WHEN** the card is successfully selected (view or add)
- **THEN** an INFO log is written: "Card [card_name] selected via disambiguation (context: [context])"
- **AND** the log includes session ID and action context

#### Scenario: Log errors during card selection
- **GIVEN** a user clicks a disambiguation button
- **WHEN** an error occurs during card selection or addition
- **THEN** an ERROR log is written with exception details
- **AND** the error is logged with session ID and card information
- **AND** a user-friendly error message is sent to the chat

#### Scenario: Handle missing payload fields
- **GIVEN** a disambiguation action callback is invoked
- **WHEN** the payload is missing `card_id` or `card_name`
- **THEN** the callback logs an ERROR: "Invalid payload: missing card_id or card_name"
- **AND** an error message is sent: "Error: Invalid card data. Please try again."
- **AND** all disambiguation buttons are removed

#### Scenario: Handle card not found error
- **GIVEN** a disambiguation button references a deleted card
- **WHEN** the user clicks the button
- **THEN** the repository returns None (card not found)
- **AND** an error message is sent: "Error: Card not found. It may have been removed."
- **AND** all disambiguation buttons are removed

### Requirement: Backward Compatibility

The system SHALL maintain backward compatibility with existing conversational card lookup.

#### Scenario: Conversational disambiguation still works
- **GIVEN** a user types "show bolt" with multiple matches
- **WHEN** the agent displays disambiguation text
- **THEN** the user can refine the query conversationally (e.g., "I meant Lightning Bolt")
- **AND** the agent responds with the correct card
- **AND** disambiguation actions are an optional shortcut, not a replacement

#### Scenario: Agent layer remains UI-agnostic
- **GIVEN** the `lookup_card_by_name` tool returns structured disambiguation data
- **WHEN** the tool code is examined
- **THEN** the tool does NOT import Chainlit
- **AND** the tool returns plain Python types (dict with Card objects)
- **AND** the UI layer handles action rendering independently

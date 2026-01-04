# Agent Tools Spec Delta

## ADDED Requirements

### Requirement: Update Deck Strategy Tool
The system SHALL provide an `update_deck_strategy` tool that allows users to modify the strategy of the active deck.

#### Scenario: Update deck strategy with new text
- **GIVEN** an active deck exists with strategy="aggro"
- **WHEN** user says "update the deck strategy to control deck with counters"
- **THEN** the agent invokes `update_deck_strategy` tool with strategy="control deck with counters"
- **AND** the deck strategy is updated in the database
- **AND** the agent confirms the strategy update

#### Scenario: Clear deck strategy
- **GIVEN** an active deck exists with strategy="midrange"
- **WHEN** user says "remove the deck strategy" or "clear strategy"
- **THEN** the agent invokes `update_deck_strategy` tool with strategy=None
- **AND** the deck strategy is set to NULL
- **AND** the agent confirms strategy was cleared

#### Scenario: Update strategy with no active deck
- **GIVEN** no active deck is set in session context
- **WHEN** user tries to update strategy
- **THEN** the tool returns error message "No active deck. Create or load a deck first."

### Requirement: Strategy Context in Card Recommendations
The system SHALL use deck strategy as context when making card recommendations through search and lookup tools.

#### Scenario: Search cards with strategy context
- **GIVEN** an active deck exists with strategy="Fast aggro with burn spells"
- **WHEN** user says "find me some good creatures"
- **AND** the agent invokes `search_cards_advanced` tool
- **THEN** the tool SHALL include strategy context in the search
- **AND** the agent SHALL prioritize low-cost, aggressive creatures
- **AND** recommendations align with the aggro strategy

#### Scenario: Card lookup with strategy context
- **GIVEN** an active deck exists with strategy="Control with card advantage"
- **WHEN** user searches for removal spells
- **THEN** the agent SHALL consider the strategy when presenting options
- **AND** prioritize cards that provide card advantage (e.g., multi-target removal, card draw)

#### Scenario: No strategy context available
- **GIVEN** an active deck exists with strategy=NULL
- **WHEN** user searches for cards
- **THEN** the tool SHALL search normally without strategy bias
- **AND** recommendations are based only on format and deck composition

## MODIFIED Requirements

### Requirement: Create Deck Tool
The system SHALL provide a `create_deck` PydanticAI tool that enables users to create new decks through natural language conversation, including optional strategy specification.

#### Scenario: Create deck with name only
- **GIVEN** the agent has `create_deck` tool registered
- **WHEN** user says "create a new deck called Mono Red Aggro"
- **THEN** the agent invokes `create_deck` tool with name="Mono Red Aggro" and default format="standard"
- **AND** a new deck is created in the database
- **AND** the agent responds with confirmation including deck name and ID
- **AND** the deck ID is stored as the active deck in session context
- **AND** the strategy field is NULL (not specified)

#### Scenario: Create deck with explicit format
- **GIVEN** the agent has `create_deck` tool registered
- **WHEN** user says "create a commander deck named Dragon Tribal"
- **THEN** the agent invokes `create_deck` tool with name="Dragon Tribal" and format="commander"
- **AND** a new deck is created with the specified format
- **AND** the agent confirms the deck creation with format information
- **AND** the strategy field is NULL

#### Scenario: Create deck with strategy
- **GIVEN** the agent has `create_deck` tool registered
- **WHEN** user says "create a control deck called Counter Magic with strategy focused on counters and card draw"
- **THEN** the agent invokes `create_deck` tool with name="Counter Magic", format="standard", strategy="focused on counters and card draw"
- **AND** a new deck is created with the specified strategy
- **AND** the agent confirms deck creation including strategy information
- **AND** the strategy is stored in the database

#### Scenario: Create deck and track in session
- **GIVEN** the agent has an active session with session_id
- **WHEN** a deck is created via the tool
- **THEN** the tool calls `_session_manager.set_active_deck_id(session_id, deck_id)`
- **AND** the deck ID is stored in session manager
- **AND** subsequent messages in the session will have `deps.active_deck_id` populated

#### Scenario: Handle duplicate deck names
- **GIVEN** a deck named "Test Deck" already exists
- **WHEN** user says "create a deck called Test Deck"
- **THEN** the tool creates a new deck with duplicate name allowed
- **AND** the agent confirms creation and mentions duplicate name scenario
- **OR** the tool appends a timestamp/counter suffix (e.g., "Test Deck 2")
- **AND** the agent confirms creation with the modified name

#### Scenario: Invalid format parameter
- **GIVEN** the agent attempts to create a deck with an invalid format
- **WHEN** the tool is invoked with format="invalid_format"
- **THEN** Pydantic validation raises a ValidationError
- **AND** the agent responds with a helpful error message listing valid formats

#### Scenario: Database error during creation
- **GIVEN** the database is unavailable or encounters an error
- **WHEN** the tool attempts to create a deck
- **THEN** the tool catches the exception
- **AND** the agent responds with an error message asking user to retry
- **AND** no active deck ID is stored in session manager

### Requirement: View Deck Tool
The agent SHALL provide a `view_deck` tool that displays the current active deck contents with formatted card list, total counts, summary statistics, and strategy information.

#### Scenario: View non-empty deck grouped by card type
- **GIVEN** an active deck exists with cards in mainboard and sideboard
- **WHEN** the user asks "show my deck" or "what's in my deck?"
- **AND** the `view_deck` tool is invoked
- **THEN** the tool SHALL return a formatted deck list grouped by card type
- **AND** cards SHALL be grouped as: Creatures, Spells (Instants/Sorceries/Enchantments/Artifacts), Lands
- **AND** within each group, cards SHALL be sorted by mana cost ascending, then alphabetically
- **AND** each card SHALL display: quantity, name, mana cost, type line
- **AND** the display SHALL include total mainboard count and total sideboard count
- **AND** the display SHALL indicate if the deck meets minimum deck size (60+ cards for Standard)
- **AND** if strategy is set, display "Strategy: {strategy}" at the top

#### Scenario: View empty deck
- **GIVEN** an active deck exists with no cards added
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL return message: "Your deck is empty. Add cards to get started."
- **AND** indicate deck name and format
- **AND** if strategy is set, include "Strategy: {strategy}"

#### Scenario: View deck with no active deck set
- **GIVEN** no active deck is set in session context (active_deck_id is None)
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL return message: "No active deck. Create a new deck or load an existing one to get started."
- **AND** suggest using deck creation or loading commands

#### Scenario: View deck with mainboard and sideboard
- **GIVEN** an active deck has cards in both mainboard and sideboard
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL display mainboard cards first, grouped by type
- **AND** then display sideboard cards separately with header "Sideboard:"
- **AND** sideboard cards SHALL also be grouped and sorted by type and mana cost
- **AND** if strategy is set, display at the top

#### Scenario: View deck summary statistics
- **GIVEN** an active deck with multiple cards
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL include summary statistics:
  - Deck name and format
  - Strategy (if set)
  - Total mainboard cards
  - Total sideboard cards
  - Number of unique cards
- **AND** indicate whether deck is legal for format (60+ cards for Standard)

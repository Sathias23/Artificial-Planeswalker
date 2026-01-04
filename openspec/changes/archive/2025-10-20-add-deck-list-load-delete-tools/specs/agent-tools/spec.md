## ADDED Requirements

### Requirement: List Decks Tool

The agent SHALL provide a tool that lists all saved decks with their names, formats, and basic statistics.

#### Scenario: List all decks successfully

- **GIVEN** the user has 3 saved decks in the database
- **WHEN** the tool is invoked
- **THEN** the tool SHALL return a formatted string containing:
  - Deck name
  - Deck format (e.g., "standard", "commander")
  - Total card count (mainboard)
  - Deck ID for reference
- **AND** decks SHALL be ordered by created_at descending (newest first)

#### Scenario: List decks when no decks exist

- **GIVEN** the user has no saved decks
- **WHEN** the tool is invoked
- **THEN** the tool SHALL return a message indicating no decks are saved
- **AND** suggest creating a new deck

#### Scenario: List decks filtered by format

- **GIVEN** the user has decks in "standard" and "commander" formats
- **WHEN** the tool is invoked with format_filter="standard"
- **THEN** the tool SHALL return only decks with format="standard"
- **AND** other format decks are excluded

#### Scenario: Natural language invocation

- **GIVEN** a user asks "show my decks" or "what decks do I have?"
- **WHEN** the agent processes the query
- **THEN** the agent SHALL invoke the list_decks tool
- **AND** return the formatted deck list to the user

#### Scenario: Database error during list operation

- **GIVEN** the database is unavailable
- **WHEN** the tool is invoked
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework

### Requirement: Load Deck Tool

The agent SHALL provide a tool that loads a previously saved deck by name or ID and sets it as the active deck in the session.

#### Scenario: Load deck by exact name match

- **GIVEN** a deck named "Mono Red Aggro" exists in the database
- **WHEN** the tool is invoked with name="Mono Red Aggro"
- **THEN** the deck SHALL be retrieved from the database
- **AND** the deck SHALL be set as the active deck in the session context
- **AND** a summary SHALL be returned containing:
  - Deck name
  - Format
  - Total mainboard card count
  - Total sideboard card count
  - Message confirming the deck is now active

#### Scenario: Load deck by ID

- **GIVEN** a deck exists with id="deck-abc-123"
- **WHEN** the tool is invoked with deck_id="deck-abc-123"
- **THEN** the deck SHALL be loaded and set as active
- **AND** a deck summary SHALL be returned

#### Scenario: Load deck with partial name match

- **GIVEN** a deck named "Mono Red Aggro" exists
- **WHEN** the tool is invoked with name="mono red"
- **THEN** the tool SHALL find the deck via case-insensitive partial match
- **AND** set it as the active deck

#### Scenario: Deck not found by name

- **GIVEN** no deck exists with name matching "Nonexistent Deck"
- **WHEN** the tool is invoked with name="Nonexistent Deck"
- **THEN** the tool SHALL return an error message indicating deck not found
- **AND** suggest listing decks to see available options
- **AND** the active deck SHALL NOT be changed

#### Scenario: Deck not found by ID

- **GIVEN** no deck exists with id="invalid-id"
- **WHEN** the tool is invoked with deck_id="invalid-id"
- **THEN** the tool SHALL return an error message indicating deck not found
- **AND** the active deck SHALL NOT be changed

#### Scenario: Natural language invocation

- **GIVEN** a user asks "load my Mono Red Aggro deck"
- **WHEN** the agent processes the query
- **THEN** the agent SHALL invoke the load_deck tool with name="Mono Red Aggro"
- **AND** return the deck summary to confirm loading

#### Scenario: Switch between decks

- **GIVEN** "Deck A" is currently the active deck
- **AND** "Deck B" exists in the database
- **WHEN** the tool is invoked to load "Deck B"
- **THEN** "Deck B" SHALL become the active deck
- **AND** subsequent deck operations (add card, view, etc.) SHALL operate on "Deck B"

#### Scenario: Database error during load operation

- **GIVEN** the database is unavailable
- **WHEN** the tool is invoked
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework

### Requirement: Delete Deck Tool

The agent SHALL provide a tool that deletes a deck by name or ID with an explicit confirmation requirement to prevent accidental deletion.

#### Scenario: Delete deck by name with confirmation

- **GIVEN** a deck named "Test Deck" exists in the database
- **WHEN** the tool is invoked with name="Test Deck" and confirmed=True
- **THEN** the deck SHALL be deleted from the database
- **AND** all associated deck_cards records SHALL be deleted (cascade)
- **AND** a confirmation message SHALL be returned
- **AND** if "Test Deck" was the active deck, the active deck SHALL be cleared from session

#### Scenario: Delete deck by ID with confirmation

- **GIVEN** a deck exists with id="deck-xyz-789"
- **WHEN** the tool is invoked with deck_id="deck-xyz-789" and confirmed=True
- **THEN** the deck SHALL be deleted
- **AND** a confirmation message SHALL be returned

#### Scenario: Delete deck without confirmation

- **GIVEN** a deck named "Important Deck" exists
- **WHEN** the tool is invoked with name="Important Deck" and confirmed=False
- **THEN** the deck SHALL NOT be deleted
- **AND** a warning message SHALL be returned asking for explicit confirmation
- **AND** suggest invoking again with confirmation

#### Scenario: Deck not found during delete

- **GIVEN** no deck exists with name="Nonexistent Deck"
- **WHEN** the tool is invoked with name="Nonexistent Deck"
- **THEN** the tool SHALL return an error message indicating deck not found
- **AND** no deletion operation SHALL be attempted

#### Scenario: Natural language invocation with confirmation flow

- **GIVEN** a user asks "delete Test Deck"
- **WHEN** the agent processes the query
- **THEN** the agent SHALL invoke the delete_deck tool with confirmed=False initially
- **AND** prompt the user for confirmation
- **WHEN** the user confirms deletion
- **THEN** the agent SHALL invoke the tool again with confirmed=True
- **AND** the deck SHALL be deleted

#### Scenario: Clear active deck after deletion

- **GIVEN** "Deck A" is the active deck in the session
- **WHEN** "Deck A" is deleted via the tool
- **THEN** the active deck SHALL be cleared from the session context
- **AND** subsequent deck operations SHALL indicate no active deck

#### Scenario: Database error during delete operation

- **GIVEN** the database is unavailable
- **WHEN** the tool is invoked
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework

## MODIFIED Requirements

### Requirement: Active Deck Session Management

The system SHALL maintain an active deck in the session context to support deck building operations across multiple user interactions, and SHALL support switching between decks when loading a different deck.

#### Scenario: Set active deck on creation

- **GIVEN** no active deck exists in the session
- **WHEN** a user creates a new deck via the create_deck tool
- **THEN** the newly created deck SHALL be set as the active deck
- **AND** the session context SHALL store the deck ID and name

#### Scenario: Set active deck on load

- **GIVEN** "Deck A" is currently the active deck
- **WHEN** a user loads "Deck B" via the load_deck tool
- **THEN** "Deck B" SHALL become the active deck
- **AND** the session context SHALL be updated with "Deck B" ID and name
- **AND** subsequent operations SHALL target "Deck B"

#### Scenario: Clear active deck on deletion

- **GIVEN** "Deck A" is the active deck
- **WHEN** "Deck A" is deleted via the delete_deck tool
- **THEN** the active deck SHALL be cleared from the session context
- **AND** the session SHALL have no active deck
- **AND** deck operations requiring an active deck SHALL prompt user to create or load a deck

#### Scenario: Retrieve active deck context

- **GIVEN** an active deck is set in the session
- **WHEN** any deck operation tool is invoked
- **THEN** the tool SHALL access the active deck ID from `ctx.deps.format_context['active_deck_id']`
- **AND** use the ID for deck-specific operations

#### Scenario: No active deck context

- **GIVEN** no active deck is set in the session
- **WHEN** a user attempts an operation requiring an active deck (e.g., "add card to deck")
- **THEN** the tool SHALL return a friendly error message
- **AND** prompt the user to create a new deck or load an existing deck

#### Scenario: Active deck persists across multiple turns

- **GIVEN** a user creates "Deck A" in turn 1
- **WHEN** the user adds cards in turns 2-5
- **THEN** all operations SHALL target "Deck A"
- **AND** the session context SHALL maintain the active deck ID throughout the conversation

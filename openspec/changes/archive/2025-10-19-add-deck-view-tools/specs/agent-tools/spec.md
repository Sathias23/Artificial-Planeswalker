## ADDED Requirements

### Requirement: View Deck Tool

The agent SHALL provide a `view_deck` tool that displays the current active deck contents with formatted card list, total counts, and summary statistics.

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

#### Scenario: View empty deck

- **GIVEN** an active deck exists with no cards added
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL return message: "Your deck is empty. Add cards to get started."
- **AND** indicate deck name and format

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

#### Scenario: View deck summary statistics

- **GIVEN** an active deck with multiple cards
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL include summary statistics:
  - Total mainboard cards
  - Total sideboard cards
  - Number of unique cards
  - Deck name and format
- **AND** indicate whether deck is legal for format (60+ cards for Standard)

### Requirement: Remove Card from Deck Tool

The agent SHALL provide a `remove_card_from_deck` tool that removes cards from the active deck with quantity validation and user-friendly error handling.

#### Scenario: Remove card from mainboard

- **GIVEN** an active deck contains 4 copies of "Lightning Bolt" in mainboard
- **WHEN** the user asks "remove 2 Lightning Bolt from my deck"
- **AND** the `remove_card_from_deck` tool is invoked with card_name="Lightning Bolt", sideboard=False
- **THEN** the tool SHALL look up the card by name to resolve card_id
- **AND** call `deck_repository.remove_card_from_deck(deck_id, card_id, sideboard=False)`
- **AND** return confirmation: "Removed Lightning Bolt from your deck."

#### Scenario: Remove card from sideboard

- **GIVEN** an active deck contains 2 copies of "Rest in Peace" in sideboard
- **WHEN** the user asks "remove Rest in Peace from sideboard"
- **AND** the `remove_card_from_deck` tool is invoked with card_name="Rest in Peace", sideboard=True
- **THEN** the tool SHALL remove the card from sideboard
- **AND** return confirmation: "Removed Rest in Peace from sideboard."

#### Scenario: Remove card not in deck

- **GIVEN** an active deck does not contain "Sol Ring"
- **WHEN** the `remove_card_from_deck` tool is invoked with card_name="Sol Ring"
- **THEN** the tool SHALL return message: "Sol Ring not found in your deck. Check the card name or view your deck to see current contents."
- **AND** NOT raise an exception

#### Scenario: Remove card with invalid name

- **GIVEN** the user attempts to remove "Nonexistent Card XYZ"
- **WHEN** the `remove_card_from_deck` tool looks up the card
- **AND** the card is not found in the card database
- **THEN** the tool SHALL return message: "Card 'Nonexistent Card XYZ' not found in card database. Check spelling or use card search."

#### Scenario: Remove card with no active deck

- **GIVEN** no active deck is set in session context
- **WHEN** the `remove_card_from_deck` tool is invoked
- **THEN** the tool SHALL return message: "No active deck. Create or load a deck first."
- **AND** NOT attempt database operations

### Requirement: Update Card Quantity Tool

The agent SHALL provide an `update_card_quantity` tool that modifies the quantity of a card in the active deck with validation against deck construction rules.

#### Scenario: Increase card quantity

- **GIVEN** an active deck contains 2 copies of "Lightning Bolt" in mainboard
- **WHEN** the user asks "add 2 more Lightning Bolt to my deck" or "change Lightning Bolt to 4 copies"
- **AND** the `update_card_quantity` tool is invoked with card_name="Lightning Bolt", quantity=4, sideboard=False
- **THEN** the tool SHALL validate the new quantity against deck rules (max 4 for non-basic lands)
- **AND** call `deck_repository.update_card_quantity(deck_id, card_id, quantity=4, sideboard=False)`
- **AND** return confirmation: "Updated Lightning Bolt to 4 copies in your deck."

#### Scenario: Decrease card quantity

- **GIVEN** an active deck contains 4 copies of "Lightning Bolt"
- **WHEN** the `update_card_quantity` tool is invoked with quantity=1
- **THEN** the tool SHALL update the quantity to 1
- **AND** return confirmation: "Updated Lightning Bolt to 1 copy in your deck."

#### Scenario: Set quantity to zero (equivalent to remove)

- **GIVEN** an active deck contains 3 copies of "Lightning Bolt"
- **WHEN** the `update_card_quantity` tool is invoked with quantity=0
- **THEN** the tool SHALL remove the card from the deck
- **AND** call `deck_repository.remove_card_from_deck(deck_id, card_id, sideboard)`
- **AND** return confirmation: "Removed Lightning Bolt from your deck."

#### Scenario: Validate max 4 copy rule

- **GIVEN** an active deck contains 2 copies of "Lightning Bolt" (non-basic land)
- **WHEN** the `update_card_quantity` tool is invoked with quantity=5
- **THEN** the tool SHALL return error: "Standard format allows maximum 4 copies of Lightning Bolt. (Basic lands are unlimited.)"
- **AND** NOT update the quantity in the database

#### Scenario: Allow unlimited basic lands

- **GIVEN** an active deck contains 10 copies of "Mountain" (basic land)
- **WHEN** the `update_card_quantity` tool is invoked with quantity=15
- **THEN** the tool SHALL allow the update (basic lands are unlimited)
- **AND** return confirmation: "Updated Mountain to 15 copies in your deck."

#### Scenario: Update card not in deck (add instead)

- **GIVEN** an active deck does not contain "Lightning Bolt"
- **WHEN** the `update_card_quantity` tool is invoked with card_name="Lightning Bolt", quantity=4
- **THEN** the tool SHALL add the card to the deck with quantity 4
- **AND** call `deck_repository.add_card_to_deck(deck_id, card_id, quantity=4, sideboard=False)`
- **AND** return confirmation: "Added 4 copies of Lightning Bolt to your deck."

#### Scenario: Update with no active deck

- **GIVEN** no active deck is set in session context
- **WHEN** the `update_card_quantity` tool is invoked
- **THEN** the tool SHALL return message: "No active deck. Create or load a deck first."

### Requirement: Active Deck Session Context

The agent dependencies SHALL include `deck_context` dictionary to track the active deck across tool invocations within a session.

#### Scenario: Active deck set on creation

- **GIVEN** a user creates a new deck via `create_deck` tool (Story 4.2)
- **WHEN** the deck is created successfully
- **THEN** the tool SHALL set `ctx.deps.deck_context["active_deck_id"]` to the new deck's ID
- **AND** subsequent deck operations SHALL use this deck by default

#### Scenario: Active deck set on load

- **GIVEN** a user loads an existing deck via `load_deck` tool (Story 4.5)
- **WHEN** the deck is loaded successfully
- **THEN** the tool SHALL set `ctx.deps.deck_context["active_deck_id"]` to the loaded deck's ID
- **AND** subsequent deck operations SHALL use this deck

#### Scenario: Active deck persists across tool calls

- **GIVEN** an active deck is set to "deck-123"
- **WHEN** multiple deck tools are invoked in the same session (view, add, remove)
- **THEN** all tools SHALL access the same active deck ID from context
- **AND** the user SHALL NOT need to specify deck name in each command

#### Scenario: New session initializes with no active deck

- **GIVEN** a new Chainlit session is started
- **WHEN** AgentDependencies is initialized for the session
- **THEN** `deck_context["active_deck_id"]` SHALL be None
- **AND** deck tools SHALL prompt user to create or load a deck

#### Scenario: Active deck context accessible to all tools

- **GIVEN** the `deck_context` is stored in AgentDependencies
- **WHEN** any agent tool accesses the context via `ctx.deps.deck_context`
- **THEN** the tool SHALL read the current `active_deck_id` value
- **AND** use it for deck operations without requiring deck parameter

### Requirement: Deck Display Formatting

The system SHALL provide a `format_deck_for_display` function that formats deck contents as readable markdown grouped by card type.

#### Scenario: Format deck grouped by type

- **GIVEN** a deck contains creatures, spells, and lands
- **WHEN** `format_deck_for_display(deck, grouping="type")` is called
- **THEN** the function SHALL return markdown with sections:
  - "Creatures (X cards)"
  - "Spells (Y cards)" (Instants, Sorceries, Enchantments, Artifacts)
  - "Lands (Z cards)"
- **AND** each card SHALL be formatted as: `Quantity - Card Name (Mana Cost) [Type Line]`

#### Scenario: Sort cards within groups

- **GIVEN** a deck type group contains multiple cards
- **WHEN** formatting the group for display
- **THEN** cards SHALL be sorted by mana cost (ascending), then alphabetically by name
- **AND** maintain consistent ordering across multiple invocations

#### Scenario: Format empty card group

- **GIVEN** a deck has no creatures
- **WHEN** formatting the deck for display
- **THEN** the "Creatures" section SHALL be omitted (not shown as empty)
- **AND** only non-empty groups SHALL be displayed

#### Scenario: Format sideboard separately

- **GIVEN** a deck has cards in both mainboard and sideboard
- **WHEN** formatting the deck for display
- **THEN** mainboard cards SHALL be displayed first with all type groupings
- **AND** sideboard cards SHALL be displayed after with header "Sideboard:"
- **AND** sideboard cards SHALL also be grouped by type

#### Scenario: Include deck summary in formatting

- **GIVEN** a deck with cards
- **WHEN** formatting the deck for display
- **THEN** the output SHALL include header with:
  - Deck name
  - Format (e.g., "Standard")
  - Total mainboard count (e.g., "60 cards")
  - Total sideboard count (e.g., "15 cards")
- **AND** indicate legality: "✓ Legal for Standard" or "⚠ Needs 60+ cards for Standard"

#### Scenario: Format with UI independence

- **GIVEN** the formatting function is called
- **WHEN** generating the output
- **THEN** the function SHALL return plain markdown string
- **AND** NOT import or depend on Chainlit UI elements
- **AND** be reusable across different UI implementations

### Requirement: Deck Tool Error Handling

Deck management tools SHALL handle edge cases with user-friendly error messages and graceful degradation.

#### Scenario: Handle database connection failure

- **GIVEN** the database is unavailable or connection fails
- **WHEN** any deck tool attempts to access the repository
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework
- **AND** the agent SHALL display a user-friendly error message

#### Scenario: Handle card name ambiguity

- **GIVEN** the user says "remove Bolt"
- **WHEN** the card lookup finds multiple matches ("Lightning Bolt", "Lava Burst", etc.)
- **AND** none are exact matches
- **THEN** the tool SHALL return: "Multiple cards match 'Bolt'. Did you mean: Lightning Bolt, Lava Burst? Please specify."
- **AND** NOT perform the removal operation

#### Scenario: Handle exact match preference

- **GIVEN** the user says "remove Lightning Bolt"
- **WHEN** the card lookup finds both exact match "Lightning Bolt" and partial match "Lightning Bolt Horde"
- **THEN** the tool SHALL use the exact match
- **AND** proceed with removing "Lightning Bolt"

#### Scenario: Handle concurrent deck modifications

- **GIVEN** an active deck is being modified by the user
- **WHEN** a deck tool reads the deck state
- **THEN** the tool SHALL use the current database state (no caching)
- **AND** reflect any recent modifications made by other tools in the same session

### Requirement: Integration Tests for Deck View Tools

The system SHALL provide integration tests verifying end-to-end deck viewing and management operations through agent tools.

#### Scenario: Integration test view deck workflow

- **GIVEN** an in-memory test database with a deck containing cards
- **WHEN** the `view_deck` tool is invoked via agent
- **THEN** the tool SHALL return formatted deck list
- **AND** include all cards with correct quantities and groupings
- **AND** display summary statistics

#### Scenario: Integration test remove card workflow

- **GIVEN** a deck with "Lightning Bolt" exists in test database
- **WHEN** `remove_card_from_deck` tool is invoked with card_name="Lightning Bolt"
- **THEN** the card SHALL be removed from the deck in database
- **AND** subsequent `view_deck` SHALL NOT show the card
- **AND** confirmation message is returned

#### Scenario: Integration test update quantity workflow

- **GIVEN** a deck with 2 copies of "Lightning Bolt" exists
- **WHEN** `update_card_quantity` tool is invoked with quantity=4
- **THEN** the quantity SHALL be updated in database
- **AND** subsequent `view_deck` SHALL show 4 copies
- **AND** confirmation message is returned

#### Scenario: Integration test deck context persistence

- **GIVEN** an active deck is set in session context
- **WHEN** multiple tools are invoked (view, remove, view again)
- **THEN** all tools SHALL operate on the same active deck
- **AND** changes SHALL be reflected across invocations

#### Scenario: Integration test edge case handling

- **GIVEN** various edge cases (empty deck, invalid card, no active deck)
- **WHEN** tools are invoked with edge case inputs
- **THEN** all tools SHALL return appropriate error messages
- **AND** NOT raise unhandled exceptions
- **AND** database state SHALL remain consistent

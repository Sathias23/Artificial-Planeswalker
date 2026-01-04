## ADDED Requirements

### Requirement: Add Card to Deck Tool

The agent SHALL provide a tool that enables adding cards to the active deck with quantity specification, Standard format validation, and deck construction rule enforcement.

#### Scenario: Add card to active deck successfully

- **GIVEN** an active deck is set in session context
- **AND** a user requests "add 4 Lightning Bolt to my deck"
- **WHEN** the tool is invoked with name="Lightning Bolt" and quantity=4
- **AND** Lightning Bolt is Standard-legal
- **AND** the deck currently has 0 copies of Lightning Bolt
- **THEN** the tool SHALL add 4 copies of Lightning Bolt to the deck
- **AND** return a confirmation message with card name, quantity, and updated total deck count

#### Scenario: Add single card with default quantity

- **GIVEN** an active deck exists
- **AND** a user requests "add Sheoldred to my deck"
- **WHEN** the tool is invoked with name="Sheoldred" (no quantity specified)
- **THEN** the tool SHALL add 1 copy of the card (quantity defaults to 1)
- **AND** return confirmation with the added card details

#### Scenario: Attempt to add card with no active deck

- **GIVEN** no active deck is set in session context
- **AND** a user requests "add Lightning Bolt to my deck"
- **WHEN** the tool is invoked with name="Lightning Bolt"
- **THEN** the tool SHALL return an error message: "No active deck. Create a deck first with 'create a new deck'."
- **AND** NO database operation SHALL be performed

#### Scenario: Card not found by exact name

- **GIVEN** an active deck exists
- **AND** a user requests "add Lightningbolt to my deck"
- **WHEN** the tool is invoked with name="Lightningbolt"
- **AND** no exact match exists for "Lightningbolt"
- **THEN** the tool SHALL search for partial matches
- **AND** return an error with suggestions: "Card 'Lightningbolt' not found. Did you mean: Lightning Bolt, Lightning Strike?"

#### Scenario: Card not Standard-legal

- **GIVEN** an active deck with format="standard"
- **AND** a user requests "add Sol Ring to my deck"
- **WHEN** the tool is invoked with name="Sol Ring"
- **AND** Sol Ring has `legalities.standard = "not_legal"`
- **THEN** the tool SHALL return an error: "'Sol Ring' is not legal in Standard format."
- **AND** the card SHALL NOT be added to the deck

#### Scenario: Exceeds 4-copy limit for non-basic land

- **GIVEN** an active Standard deck with 3 copies of Lightning Bolt
- **AND** a user requests "add 2 Lightning Bolt to my deck"
- **WHEN** the tool is invoked with name="Lightning Bolt" and quantity=2
- **THEN** the deck construction validator SHALL detect that 3 + 2 = 5 exceeds the 4-copy limit
- **AND** the tool SHALL return an error: "Cannot add 2 copies of 'Lightning Bolt'. Deck would have 5 copies (max 4 for non-basic lands)."
- **AND** NO cards SHALL be added to the deck

#### Scenario: Add basic land exceeding 4 copies (allowed)

- **GIVEN** an active deck with 10 copies of Mountain (a basic land)
- **AND** a user requests "add 5 Mountain to my deck"
- **WHEN** the tool is invoked with name="Mountain" and quantity=5
- **THEN** the validator SHALL recognize Mountain as a basic land (unlimited copies allowed)
- **AND** the tool SHALL add 5 copies of Mountain successfully
- **AND** return confirmation that the deck now has 15 copies of Mountain

#### Scenario: Add card that is already in deck (update quantity)

- **GIVEN** an active deck with 2 copies of Opt
- **AND** a user requests "add 1 Opt to my deck"
- **WHEN** the tool is invoked with name="Opt" and quantity=1
- **THEN** the DeckRepository SHALL update the quantity to 3 copies (2 + 1)
- **AND** return confirmation: "Added 1 copy of 'Opt'. Deck now has 3 copies (total: 61 cards)."

#### Scenario: Database error during card addition

- **GIVEN** an active deck exists
- **AND** the database connection fails during the add operation
- **WHEN** the tool is invoked
- **THEN** the tool SHALL allow the database exception to propagate
- **AND** the agent framework SHALL handle the exception with a user-friendly message

### Requirement: Deck Construction Rule Validation

The system SHALL validate deck construction rules in the business logic layer before adding cards to decks.

#### Scenario: Validate 4-copy limit for non-basic cards

- **GIVEN** a deck with 2 copies of Lightning Bolt
- **WHEN** `validate_card_addition(deck, card=Lightning Bolt, quantity=3)` is called
- **THEN** the validator SHALL return `ValidationResult(is_valid=False, error_message="Cannot add 3 copies...")`

#### Scenario: Allow unlimited basic lands

- **GIVEN** a deck with 20 copies of Forest
- **WHEN** `validate_card_addition(deck, card=Forest, quantity=10)` is called
- **AND** Forest has `type_line` containing "Basic Land"
- **THEN** the validator SHALL return `ValidationResult(is_valid=True, error_message=None)`

#### Scenario: Validate card not already at 4-copy limit

- **GIVEN** a deck with 4 copies of Llanowar Elves
- **WHEN** `validate_card_addition(deck, card=Llanowar Elves, quantity=1)` is called
- **THEN** the validator SHALL return `ValidationResult(is_valid=False, error_message="Cannot add 1 copy of 'Llanowar Elves'. Deck already has 4 copies (max 4 for non-basic lands).")`

#### Scenario: Helper function identifies basic lands correctly

- **GIVEN** a card with `type_line = "Basic Land — Mountain"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `True`

#### Scenario: Helper function identifies non-basic lands correctly

- **GIVEN** a card with `type_line = "Creature — Goblin"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `False`

#### Scenario: Get current card count from deck

- **GIVEN** a deck with 3 copies of Shock in mainboard and 1 copy in sideboard
- **WHEN** `get_current_card_count(deck, card_id="shock-id")` is called
- **THEN** the function SHALL return 3 (mainboard only, sideboard excluded)

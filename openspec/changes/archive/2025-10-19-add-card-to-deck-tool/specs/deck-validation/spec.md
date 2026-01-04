## ADDED Requirements

### Requirement: Deck Construction Validation Function

The system SHALL provide a `validate_card_addition()` function in the business logic layer that validates whether adding a specified quantity of a card to a deck would comply with Standard format deck construction rules.

#### Scenario: Valid addition under 4-copy limit

- **GIVEN** a deck with 2 copies of Lightning Bolt
- **AND** Lightning Bolt is not a basic land
- **WHEN** `validate_card_addition(deck, card=Lightning Bolt, quantity=2)` is called
- **THEN** the function SHALL return `ValidationResult(is_valid=True, error_message=None)`

#### Scenario: Invalid addition exceeding 4-copy limit

- **GIVEN** a deck with 3 copies of Counterspell
- **AND** Counterspell is not a basic land
- **WHEN** `validate_card_addition(deck, card=Counterspell, quantity=2)` is called
- **THEN** the function SHALL return `ValidationResult(is_valid=False, error_message="Cannot add 2 copies of 'Counterspell'. Deck would have 5 copies (max 4 for non-basic lands).")`

#### Scenario: Valid addition of basic land exceeding 4 copies

- **GIVEN** a deck with 15 copies of Plains
- **AND** Plains has `type_line` containing "Basic Land"
- **WHEN** `validate_card_addition(deck, card=Plains, quantity=10)` is called
- **THEN** the function SHALL return `ValidationResult(is_valid=True, error_message=None)`

#### Scenario: Adding to empty deck

- **GIVEN** a deck with 0 cards
- **WHEN** `validate_card_addition(deck, card=any_card, quantity=4)` is called
- **THEN** the function SHALL return `ValidationResult(is_valid=True, error_message=None)` for non-basic lands
- **AND** return `ValidationResult(is_valid=True, error_message=None)` for basic lands

#### Scenario: Adding to deck at 4-copy limit

- **GIVEN** a deck with exactly 4 copies of Thoughtseize
- **WHEN** `validate_card_addition(deck, card=Thoughtseize, quantity=1)` is called
- **THEN** the function SHALL return `ValidationResult(is_valid=False, error_message="Cannot add 1 copy of 'Thoughtseize'. Deck already has 4 copies (max 4 for non-basic lands).")`

### Requirement: Basic Land Detection

The system SHALL provide an `is_basic_land()` function that determines whether a card is a basic land based on its type line.

#### Scenario: Detect basic land - Mountain

- **GIVEN** a card with `type_line = "Basic Land — Mountain"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `True`

#### Scenario: Detect basic land - Island

- **GIVEN** a card with `type_line = "Basic Land — Island"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `True`

#### Scenario: Detect non-basic land

- **GIVEN** a card with `type_line = "Land — Mountain"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `False`

#### Scenario: Detect creature (not a land)

- **GIVEN** a card with `type_line = "Creature — Goblin Warrior"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `False`

#### Scenario: Detect instant (not a land)

- **GIVEN** a card with `type_line = "Instant"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `False`

#### Scenario: Case-insensitive detection

- **GIVEN** a card with `type_line = "BASIC LAND — Forest"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `True` (detection is case-insensitive)

### Requirement: Current Card Count Calculation

The system SHALL provide a `get_current_card_count()` function that calculates how many copies of a specific card are currently in a deck's mainboard.

#### Scenario: Card not in deck

- **GIVEN** a deck with no copies of Lightning Bolt
- **WHEN** `get_current_card_count(deck, card_id="lightning-bolt-id")` is called
- **THEN** the function SHALL return `0`

#### Scenario: Card in deck mainboard

- **GIVEN** a deck with 3 copies of Shock in mainboard
- **WHEN** `get_current_card_count(deck, card_id="shock-id")` is called
- **THEN** the function SHALL return `3`

#### Scenario: Card in both mainboard and sideboard

- **GIVEN** a deck with 2 copies of Negate in mainboard
- **AND** 1 copy of Negate in sideboard
- **WHEN** `get_current_card_count(deck, card_id="negate-id")` is called
- **THEN** the function SHALL return `2` (mainboard only, excludes sideboard)

#### Scenario: Card only in sideboard

- **GIVEN** a deck with 0 copies of Rest in Peace in mainboard
- **AND** 2 copies of Rest in Peace in sideboard
- **WHEN** `get_current_card_count(deck, card_id="rest-in-peace-id")` is called
- **THEN** the function SHALL return `0` (sideboard excluded)

#### Scenario: Empty deck

- **GIVEN** a deck with 0 total cards
- **WHEN** `get_current_card_count(deck, card_id="any-card-id")` is called
- **THEN** the function SHALL return `0`

### Requirement: Validation Result Type

The system SHALL define a `ValidationResult` data class with `is_valid` boolean and optional `error_message` string fields.

#### Scenario: ValidationResult for valid case

- **GIVEN** a validation passes
- **WHEN** `ValidationResult(is_valid=True, error_message=None)` is created
- **THEN** the instance SHALL have `is_valid == True`
- **AND** `error_message == None`

#### Scenario: ValidationResult for invalid case

- **GIVEN** a validation fails with a specific error
- **WHEN** `ValidationResult(is_valid=False, error_message="Exceeds 4-copy limit")` is created
- **THEN** the instance SHALL have `is_valid == False`
- **AND** `error_message == "Exceeds 4-copy limit"`

#### Scenario: ValidationResult is a dataclass

- **GIVEN** the ValidationResult class definition
- **WHEN** inspecting the class
- **THEN** it SHALL be a dataclass or Pydantic model
- **AND** provide type hints for all fields

### Requirement: Type Safety for Validation Functions

The system SHALL maintain strict type hints for all validation functions with mypy compliance.

#### Scenario: Type hints for validate_card_addition

- **GIVEN** the `validate_card_addition` function signature
- **WHEN** mypy analyzes the function in strict mode
- **THEN** no type errors SHALL be reported
- **AND** the return type SHALL be explicitly `ValidationResult`

#### Scenario: Type hints for helper functions

- **GIVEN** the `is_basic_land` and `get_current_card_count` function signatures
- **WHEN** mypy analyzes in strict mode
- **THEN** no type errors SHALL be reported
- **AND** return types SHALL be explicitly `bool` and `int` respectively

### Requirement: Unit Tests for Validation Logic

The system SHALL provide comprehensive unit tests for all deck validation functions achieving 90%+ coverage.

#### Scenario: Test validate_card_addition with mocked deck

- **GIVEN** a unit test with a mocked Deck instance
- **WHEN** testing `validate_card_addition` with various quantities and existing counts
- **THEN** the function SHALL return correct ValidationResult for all test cases
- **AND** no database calls SHALL be made (pure business logic)

#### Scenario: Test is_basic_land with various card types

- **GIVEN** unit tests with cards of different types
- **WHEN** testing `is_basic_land` with basic lands, non-basic lands, creatures, etc.
- **THEN** the function SHALL correctly identify basic lands in all cases

#### Scenario: Test get_current_card_count with deck data

- **GIVEN** a Deck instance with known deck_cards list
- **WHEN** testing `get_current_card_count`
- **THEN** the function SHALL correctly sum quantities for mainboard cards only

#### Scenario: Test ValidationResult dataclass

- **GIVEN** unit tests for ValidationResult
- **WHEN** creating instances with various parameters
- **THEN** fields SHALL be accessible and type-safe

### Requirement: Error Message Clarity

The system SHALL provide clear, actionable error messages that help users understand deck construction rule violations.

#### Scenario: Error message format for exceeding limit

- **GIVEN** validation fails because adding would exceed 4-copy limit
- **WHEN** the error message is generated
- **THEN** it SHALL include:
  - The quantity being added
  - The card name
  - The total count after addition
  - The maximum allowed (4 for non-basic lands)
- **AND** follow the format: "Cannot add {quantity} copies of '{card_name}'. Deck would have {total} copies (max 4 for non-basic lands)."

#### Scenario: Error message when already at limit

- **GIVEN** validation fails because deck already has 4 copies
- **WHEN** the error message is generated
- **THEN** it SHALL clearly state the deck already has the maximum
- **AND** follow the format: "Cannot add {quantity} copy/copies of '{card_name}'. Deck already has 4 copies (max 4 for non-basic lands)."

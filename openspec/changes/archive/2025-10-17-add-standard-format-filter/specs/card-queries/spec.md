## MODIFIED Requirements

### Requirement: Exact Name Search

The CardRepository SHALL provide a method to find a card by exact name match (case-insensitive) with optional format legality filtering.

#### Scenario: Find card by exact name

- **GIVEN** a card named "Lightning Bolt" exists in the database
- **WHEN** `find_by_name_exact("lightning bolt")` is called
- **THEN** the card with name "Lightning Bolt" is returned

#### Scenario: Exact name not found

- **GIVEN** no card named "Nonexistent Card" exists in the database
- **WHEN** `find_by_name_exact("Nonexistent Card")` is called
- **THEN** None is returned

#### Scenario: Exact name with format filter

- **GIVEN** a card named "Sol Ring" exists with `legalities.standard = "not_legal"`
- **WHEN** `find_by_name_exact("Sol Ring", format_filter="standard")` is called
- **THEN** None is returned (card filtered out by format)

### Requirement: Partial Name Search

The CardRepository SHALL provide a method to find all cards matching a partial name (case-insensitive substring) with optional format legality filtering.

#### Scenario: Find cards by partial name

- **GIVEN** cards "Lightning Bolt", "Lightning Strike", and "Chain Lightning" exist in the database
- **WHEN** `find_by_name_partial("lightning")` is called
- **THEN** all three cards are returned in a list

#### Scenario: Partial name no matches

- **GIVEN** no cards contain "Nonexistent" in their name
- **WHEN** `find_by_name_partial("Nonexistent")` is called
- **THEN** an empty list is returned

#### Scenario: Partial name case-insensitive

- **GIVEN** a card named "Counterspell" exists
- **WHEN** `find_by_name_partial("COUNTER")` is called
- **THEN** the card "Counterspell" is returned in the list

#### Scenario: Partial name with format filter

- **GIVEN** cards "Lightning Bolt" (Standard: legal), "Lightning Strike" (Standard: not_legal) exist
- **WHEN** `find_by_name_partial("lightning", format_filter="standard")` is called
- **THEN** only "Lightning Bolt" is returned in the list

### Requirement: Color Filtering

The CardRepository SHALL provide a method to find all cards containing a specific color in their `colors` array with optional format legality filtering.

#### Scenario: Find cards by single color

- **GIVEN** cards with colors ["R"], ["U"], and ["R", "U"] exist in the database
- **WHEN** `find_by_colors("R")` is called
- **THEN** the cards with colors ["R"] and ["R", "U"] are returned

#### Scenario: Find colorless cards

- **GIVEN** an artifact card with colors [] exists in the database
- **WHEN** `find_by_colors("")` is called with empty string
- **THEN** the colorless artifact card is returned

#### Scenario: Color not found

- **GIVEN** no green cards exist in the database
- **WHEN** `find_by_colors("G")` is called
- **THEN** an empty list is returned

#### Scenario: Color filtering with format filter

- **GIVEN** red cards exist with mixed Standard legality
- **WHEN** `find_by_colors("R", format_filter="standard")` is called
- **THEN** only red cards with `legalities.standard = "legal"` are returned

### Requirement: Type Filtering

The CardRepository SHALL provide a method to find all cards matching a type substring in their `type_line` field (case-insensitive) with optional format legality filtering.

#### Scenario: Find cards by type

- **GIVEN** cards with type_line "Instant", "Legendary Instant", and "Creature — Human" exist
- **WHEN** `find_by_type("Instant")` is called
- **THEN** cards with type_line "Instant" and "Legendary Instant" are returned

#### Scenario: Type case-insensitive

- **GIVEN** a card with type_line "Creature — Dragon" exists
- **WHEN** `find_by_type("dragon")` is called
- **THEN** the card with type_line "Creature — Dragon" is returned

#### Scenario: Type not found

- **GIVEN** no planeswalker cards exist in the database
- **WHEN** `find_by_type("Planeswalker")` is called
- **THEN** an empty list is returned

#### Scenario: Type filtering with format filter

- **GIVEN** instant cards exist with mixed Standard legality
- **WHEN** `find_by_type("Instant", format_filter="standard")` is called
- **THEN** only instant cards with `legalities.standard = "legal"` are returned

### Requirement: Pydantic Schema Return Types

All CardRepository query methods SHALL return Pydantic Card schemas, not SQLAlchemy CardModel instances.

#### Scenario: Query returns Pydantic schema

- **GIVEN** a card "Lightning Bolt" exists in the database
- **WHEN** `find_by_name_exact("Lightning Bolt")` is called
- **THEN** the returned object is an instance of the Pydantic Card schema
- **AND** the object can be serialized to JSON without errors

### Requirement: Async Query Interface

All CardRepository query methods SHALL be async functions accepting an AsyncSession.

#### Scenario: Repository accepts AsyncSession

- **GIVEN** an AsyncSession from the session factory
- **WHEN** `CardRepository(session)` is instantiated
- **THEN** the repository is ready to execute queries

#### Scenario: Query methods are awaitable

- **GIVEN** a CardRepository instance
- **WHEN** any query method is called
- **THEN** the method returns an awaitable coroutine that must be awaited

### Requirement: Unit Test Coverage

All CardRepository query methods SHALL have comprehensive unit tests with >80% code coverage.

#### Scenario: All query methods tested

- **GIVEN** the CardRepository implementation
- **WHEN** the test suite is executed
- **THEN** tests exist for `find_by_name_exact()`, `find_by_name_partial()`, `find_by_colors()`, and `find_by_type()`
- **AND** all tests pass

#### Scenario: Edge cases tested

- **GIVEN** the CardRepository test suite
- **WHEN** tests are reviewed
- **THEN** edge cases are covered: empty results, None handling, case sensitivity, multi-face cards

#### Scenario: Format filter edge cases tested

- **GIVEN** the CardRepository test suite with format filter tests
- **WHEN** tests are reviewed
- **THEN** edge cases are covered: missing legalities field, None filter, invalid format values

### Requirement: CLI Demonstration Script

A CLI test script SHALL be provided to manually demonstrate all query functions with sample data.

#### Scenario: CLI script demonstrates queries

- **GIVEN** the CLI script `scripts/test_queries.py` exists
- **WHEN** the script is executed with `uv run python scripts/test_queries.py`
- **THEN** sample cards are inserted into a test database
- **AND** all four query methods are demonstrated with visible output
- **AND** the script completes without errors

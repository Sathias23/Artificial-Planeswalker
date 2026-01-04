## ADDED Requirements

### Requirement: Format Legality Filtering

The CardRepository SHALL provide methods to filter card queries by Magic: The Gathering format legality using Scryfall's `legalities` JSON field.

#### Scenario: Query Standard-legal cards only

- **GIVEN** cards exist with various legalities in the database
- **WHEN** a query method is called with `format_filter="standard"`
- **THEN** only cards with `legalities.standard = "legal"` are returned
- **AND** cards with `legalities.standard = "not_legal"` or `"banned"` are excluded

#### Scenario: Query without format filter

- **GIVEN** cards exist with various legalities in the database
- **WHEN** a query method is called with `format_filter=None`
- **THEN** all matching cards are returned regardless of format legality
- **AND** no legality filtering is applied

#### Scenario: Format filter with exact name search

- **GIVEN** a card "Sol Ring" exists with `legalities.standard = "not_legal"`
- **AND** a card "Lightning Bolt" exists with `legalities.standard = "legal"`
- **WHEN** `find_by_name_exact("Sol Ring", format_filter="standard")` is called
- **THEN** None is returned (card is not Standard-legal)
- **WHEN** `find_by_name_exact("Lightning Bolt", format_filter="standard")` is called
- **THEN** the card is returned (card is Standard-legal)

#### Scenario: Format filter with partial name search

- **GIVEN** cards "Lightning Bolt" (Standard: legal), "Lightning Strike" (Standard: not_legal), "Chain Lightning" (Standard: not_legal) exist
- **WHEN** `find_by_name_partial("lightning", format_filter="standard")` is called
- **THEN** only "Lightning Bolt" is returned in the list
- **AND** "Lightning Strike" and "Chain Lightning" are excluded

#### Scenario: Format filter with color search

- **GIVEN** red cards exist with mixed Standard legality
- **WHEN** `find_by_colors("R", format_filter="standard")` is called
- **THEN** only red cards with `legalities.standard = "legal"` are returned

#### Scenario: Format filter with type search

- **GIVEN** instant cards exist with mixed Standard legality
- **WHEN** `find_by_type("Instant", format_filter="standard")` is called
- **THEN** only instant cards with `legalities.standard = "legal"` are returned

#### Scenario: Handle cards with missing legalities field

- **GIVEN** a card exists without a `legalities` field in JSON
- **WHEN** a query with `format_filter="standard"` is executed
- **THEN** the card is excluded from results (treated as not legal)

### Requirement: Format Filter Type Safety

All format filtering parameters SHALL be type-safe with explicit type hints for supported formats.

#### Scenario: Format filter accepts valid format strings

- **GIVEN** a repository query method with format_filter parameter
- **WHEN** the method signature is analyzed
- **THEN** the format_filter parameter has type hint `Literal["standard"] | None`
- **AND** mypy validates only "standard" or None can be passed

#### Scenario: Format filter extensibility

- **GIVEN** the format_filter type definition
- **WHEN** future formats need to be added (e.g., "modern", "commander")
- **THEN** the Literal type can be extended without breaking existing code
- **AND** the type system enforces valid format strings at compile time

# Card Queries Specification - Delta Changes

## MODIFIED Requirements

### Requirement: Advanced Multi-Criteria Search

The CardRepository SHALL provide a search_advanced method that combines multiple filter criteria using AND logic, with oracle text phrase search, pagination support, and configurable color filtering modes.

#### Scenario: Combined filters with multiple criteria

- **GIVEN** various cards in the database
- **WHEN** `search_advanced(colors=["R"], types=["Creature"], keywords=["haste"], mana_value_max=3)` is called
- **THEN** only red creature cards with haste and CMC ≤ 3 are returned
- **AND** all filter criteria are combined with AND logic

#### Scenario: Advanced search with format filter

- **GIVEN** cards exist in multiple formats
- **WHEN** `search_advanced(colors=["U"], types=["Instant"], format_filter="standard")` is called
- **THEN** only Standard-legal blue instant cards are returned
- **AND** non-Standard cards are excluded even if they match other criteria

#### Scenario: Advanced search with pagination and oracle text

- **GIVEN** various cards in the database
- **WHEN** `search_advanced(oracle_text_phrases=["target creature"], colors=["W"], page=1, page_size=15)` is called
- **THEN** a PaginatedResult is returned with up to 15 white cards containing "target creature"
- **AND** total_count reflects total matching cards across all pages
- **AND** all filters (oracle text, colors, pagination) work together

#### Scenario: Advanced search returns Pydantic schemas

- **GIVEN** any search query
- **WHEN** `search_advanced(...)` is called
- **THEN** a PaginatedResult[Card] is returned
- **AND** items contain Pydantic Card schemas (not ORM models)
- **AND** repository converts CardModel → Card before returning

#### Scenario: Advanced search with rarity filter

- **GIVEN** various cards in the database
- **WHEN** `search_advanced(rarity=["rare", "mythic"], colors=["B"])` is called
- **THEN** only rare or mythic black cards are returned
- **AND** rarity uses OR logic, other filters use AND logic

#### Scenario: Advanced search performance with pagination

- **GIVEN** a complex multi-criteria search with pagination
- **WHEN** `search_advanced(colors=["U"], types=["Creature"], oracle_text_phrases=["draw"], page=2, page_size=20)` is called
- **THEN** the query completes in less than 500ms
- **AND** total count is calculated efficiently (single COUNT query)
- **AND** pagination uses OFFSET/LIMIT for efficient result slicing

#### Scenario: Advanced search with no results

- **GIVEN** no cards match the filter criteria
- **WHEN** `search_advanced(colors=["W"], types=["Dragon"], oracle_text_phrases=["destroy all creatures"])` is called
- **THEN** a PaginatedResult is returned with:
  - items: empty list
  - total_count: 0
  - page: 1 (requested page)
  - page_size: 20 (default)
  - total_pages: 0

#### Scenario: Color mode "any" - Contains ANY specified colors (OR logic, default)

- **GIVEN** cards with colors ["W"], ["U"], ["W", "U"], ["W", "U", "B"] exist
- **WHEN** `search_advanced(colors=["W", "U"], color_mode="any")` is called
- **THEN** all four cards are returned (any card containing W OR U)
- **AND** this is the default behavior when color_mode is not specified

#### Scenario: Color mode "all" - Contains ALL specified colors (AND logic)

- **GIVEN** cards with colors ["W"], ["U"], ["W", "U"], ["W", "U", "B"] exist
- **WHEN** `search_advanced(colors=["W", "U"], color_mode="all")` is called
- **THEN** cards with colors ["W", "U"] and ["W", "U", "B"] are returned
- **AND** mono-white and mono-blue cards are excluded (must have BOTH W AND U)

#### Scenario: Color mode "exact" - Exactly these colors, no more, no less

- **GIVEN** cards with colors ["W"], ["U"], ["W", "U"], ["W", "U", "B"] exist
- **WHEN** `search_advanced(colors=["W", "U"], color_mode="exact")` is called
- **THEN** only the card with colors ["W", "U"] is returned
- **AND** cards with fewer colors (mono-white, mono-blue) are excluded
- **AND** cards with more colors (["W", "U", "B"]) are excluded

#### Scenario: Color mode "at_most" - Only these colors or fewer (subset/color identity)

- **GIVEN** cards with colors [], ["W"], ["U"], ["W", "U"], ["W", "U", "B"] exist
- **WHEN** `search_advanced(colors=["W", "U"], color_mode="at_most")` is called
- **THEN** cards with colors [], ["W"], ["U"], and ["W", "U"] are returned
- **AND** the card with ["W", "U", "B"] is excluded (has extra color B)

#### Scenario: Color mode with single color behaves consistently

- **GIVEN** cards with colors ["R"], ["R", "G"], ["U"] exist
- **WHEN** `search_advanced(colors=["R"], color_mode="any")` is called
- **THEN** cards with ["R"] and ["R", "G"] are returned
- **WHEN** `search_advanced(colors=["R"], color_mode="all")` is called
- **THEN** cards with ["R"] and ["R", "G"] are returned (same as "any")
- **WHEN** `search_advanced(colors=["R"], color_mode="exact")` is called
- **THEN** only the card with ["R"] is returned (not ["R", "G"])
- **WHEN** `search_advanced(colors=["R"], color_mode="at_most")` is called
- **THEN** cards with [] and ["R"] are returned (not ["R", "G"])

#### Scenario: Color mode "exact" with empty colors finds colorless cards

- **GIVEN** cards with colors [], ["W"], ["U"] exist
- **WHEN** `search_advanced(colors=[], color_mode="exact")` is called
- **THEN** only the card with colors [] is returned (colorless)
- **AND** cards with any colors are excluded

#### Scenario: Color mode backward compatibility

- **GIVEN** existing code calling `search_advanced(colors=["R", "G"])`
- **WHEN** the call is made without specifying color_mode
- **THEN** color_mode defaults to "any" (OR logic)
- **AND** behavior is unchanged from previous implementation

#### Scenario: Color mode with format filter and pagination

- **GIVEN** 50 white-blue cards exist with mixed Standard legality
- **WHEN** `search_advanced(colors=["W", "U"], color_mode="exact", format_filter="standard", page=1, page_size=20)` is called
- **THEN** a PaginatedResult is returned with up to 20 Standard-legal white-blue cards
- **AND** all filters (color mode, format, pagination) work together

#### Scenario: Color mode with other filters

- **GIVEN** various cards in the database
- **WHEN** `search_advanced(colors=["W", "U"], color_mode="exact", types=["Creature"], keywords=["flying"], mana_value_max=4)` is called
- **THEN** only white-blue creature cards with flying and CMC ≤ 4 are returned
- **AND** color_mode combines with all other filters using AND logic

#### Scenario: Invalid color mode raises validation error

- **GIVEN** the search_advanced method with color_mode parameter
- **WHEN** `search_advanced(colors=["R"], color_mode="invalid")` is called
- **THEN** a validation error is raised (type checking prevents invalid values)
- **AND** valid values are: "any", "all", "exact", "at_most"

## ADDED Requirements

### Requirement: Color Mode Parameter Type Safety

The CardRepository search_advanced method SHALL accept a color_mode parameter with type `Literal["any", "all", "exact", "at_most"]` to ensure type safety and prevent invalid values.

#### Scenario: Type checking prevents invalid color modes

- **GIVEN** the CardRepository.search_advanced() method signature
- **WHEN** a developer attempts to pass an invalid color_mode value
- **THEN** type checkers (mypy) flag the error before runtime
- **AND** only "any", "all", "exact", or "at_most" are valid

#### Scenario: Default color_mode is "any"

- **GIVEN** the CardRepository.search_advanced() method signature
- **WHEN** color_mode is not specified in the call
- **THEN** color_mode defaults to "any"
- **AND** backward compatibility is maintained with existing code

### Requirement: Agent Tool Color Mode Integration

The CardSearchFilters Pydantic model SHALL include a color_mode field with comprehensive documentation and examples for LLM agent interpretation.

#### Scenario: CardSearchFilters includes color_mode field

- **GIVEN** the CardSearchFilters Pydantic model
- **WHEN** an instance is created with color_mode="exact"
- **THEN** the field validates successfully
- **AND** the value is passed through to the repository layer

#### Scenario: CardSearchFilters provides LLM-friendly documentation

- **GIVEN** the CardSearchFilters.color_mode field description
- **WHEN** an LLM agent reads the field documentation
- **THEN** the description includes clear explanations of each mode
- **AND** examples for common MTG queries (Azorius, Boros, etc.) are provided
- **AND** the agent can correctly interpret user queries like "white and blue cards"

#### Scenario: CardSearchFilters color_mode defaults to "any"

- **GIVEN** the CardSearchFilters Pydantic model
- **WHEN** an instance is created without specifying color_mode
- **THEN** color_mode defaults to "any"
- **AND** existing agent behavior is unchanged

#### Scenario: Agent tool passes color_mode to repository

- **GIVEN** the search_cards_advanced agent tool
- **WHEN** filters.color_mode is set to "exact"
- **THEN** the value is passed to repo.search_advanced(color_mode="exact")
- **AND** the color filtering behaves according to the specified mode

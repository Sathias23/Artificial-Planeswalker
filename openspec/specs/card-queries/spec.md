# card-queries Specification

## Purpose
TBD - created by archiving change story-1-3-card-queries. Update Purpose after archive.
## Requirements
### Requirement: Exact Name Search

The CardRepository SHALL provide a method to find a card by exact name match (case-insensitive) with optional format legality and games availability filtering.

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

#### Scenario: Exact name with games filter

- **GIVEN** a card named "Cosmic Spider-Man" exists with games=["paper"]
- **WHEN** `find_by_name_exact("Cosmic Spider-Man", games=["arena"])` is called
- **THEN** None is returned (card filtered out by games availability)

#### Scenario: Exact name with both format and games filters

- **GIVEN** a card named "Lightning Bolt" exists with legalities.standard="legal" and games=["paper", "arena", "mtgo"]
- **WHEN** `find_by_name_exact("Lightning Bolt", format_filter="standard", games=["arena"])` is called
- **THEN** the card is returned (matches both filters)

### Requirement: Partial Name Search

The CardRepository SHALL provide a method to find all cards matching a partial name (case-insensitive substring) with optional format legality and games availability filtering.

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

#### Scenario: Partial name with games filter

- **GIVEN** cards "Spider-Woman" (games=["paper"]) and "Spider-Man" (games=["paper"]) exist
- **WHEN** `find_by_name_partial("spider", games=["arena"])` is called
- **THEN** an empty list is returned (no Arena-available Spider cards)

### Requirement: Color Filtering

The CardRepository SHALL provide a method to find all cards containing a specific color in their `colors` array with optional format legality and games availability filtering.

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

#### Scenario: Color filtering with games filter

- **GIVEN** red cards exist with mixed games availability
- **WHEN** `find_by_colors("R", games=["arena"])` is called
- **THEN** only red cards with "arena" in their games array are returned

### Requirement: Type Filtering

The CardRepository SHALL provide a method to find all cards matching a type substring in their `type_line` field (case-insensitive) with optional format legality and games availability filtering.

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

#### Scenario: Type filtering with games filter

- **GIVEN** instant cards exist with mixed games availability
- **WHEN** `find_by_type("Instant", games=["arena"])` is called
- **THEN** only instant cards with "arena" in their games array are returned

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

### Requirement: Rarity Filtering in Advanced Search

The CardRepository `search_advanced()` method SHALL accept an optional `rarity` parameter to filter cards by rarity with support for single or multiple rarity values.

#### Scenario: Filter by single rarity value

- **GIVEN** cards with rarities "common", "rare", and "mythic" exist in the database
- **WHEN** `search_advanced(rarity="rare")` is called
- **THEN** only cards with `rarity = "rare"` are returned
- **AND** cards with other rarity values are excluded

#### Scenario: Filter by multiple rarity values

- **GIVEN** cards with various rarities exist in the database
- **WHEN** `search_advanced(rarity=["rare", "mythic"])` is called
- **THEN** only cards with `rarity IN ("rare", "mythic")` are returned
- **AND** common and uncommon cards are excluded

#### Scenario: Rarity filter combined with color filter

- **GIVEN** red cards exist with rarities common, rare, and mythic
- **WHEN** `search_advanced(colors=["R"], rarity="rare")` is called
- **THEN** only red cards with `rarity = "rare"` are returned
- **AND** results match both color AND rarity criteria

#### Scenario: Rarity filter with format filter

- **GIVEN** rare cards exist with mixed Standard legality
- **WHEN** `search_advanced(rarity="rare", format_filter="standard")` is called
- **THEN** only Standard-legal rare cards are returned
- **AND** rare cards not legal in Standard are excluded

#### Scenario: Rarity filter case-insensitive

- **GIVEN** cards with `rarity = "rare"` exist
- **WHEN** `search_advanced(rarity="Rare")` is called
- **THEN** cards with `rarity = "rare"` are returned (case-insensitive match)

#### Scenario: No rarity parameter returns all rarities

- **GIVEN** cards with various rarities exist
- **WHEN** `search_advanced(rarity=None)` is called with no rarity filter
- **THEN** cards of all rarities are returned
- **AND** no rarity filtering is applied

#### Scenario: Empty list when no matches

- **GIVEN** no mythic red creatures exist
- **WHEN** `search_advanced(colors=["R"], types=["Creature"], rarity="mythic")` is called
- **THEN** an empty list is returned
- **AND** no error is raised

#### Scenario: Valid rarity values

- **GIVEN** the Scryfall card database
- **WHEN** querying by rarity
- **THEN** valid rarity values are: "common", "uncommon", "rare", "mythic"
- **AND** special values include: "special", "bonus" (for promotional/special cards)

### Requirement: Paginated Search Results

The CardRepository SHALL support pagination for search_advanced method to enable efficient navigation through large result sets.

#### Scenario: First page of paginated results

- **GIVEN** a search query matches 52 cards
- **WHEN** `search_advanced(..., page=1, page_size=20)` is called
- **THEN** a PaginatedResult is returned with:
  - items: list of first 20 cards
  - total_count: 52
  - page: 1
  - page_size: 20
  - total_pages: 3

#### Scenario: Middle page of paginated results

- **GIVEN** a search query matches 52 cards
- **WHEN** `search_advanced(..., page=2, page_size=20)` is called
- **THEN** a PaginatedResult is returned with cards 21-40
- **AND** page=2, total_pages=3

#### Scenario: Last page with partial results

- **GIVEN** a search query matches 52 cards
- **WHEN** `search_advanced(..., page=3, page_size=20)` is called
- **THEN** a PaginatedResult is returned with 12 cards (41-52)
- **AND** page=3, total_pages=3

#### Scenario: Page beyond available results

- **GIVEN** a search query matches 52 cards
- **WHEN** `search_advanced(..., page=10, page_size=20)` is called
- **THEN** a PaginatedResult is returned with:
  - items: empty list
  - total_count: 52
  - page: 10
  - total_pages: 3

#### Scenario: Custom page size

- **GIVEN** a search query matches 52 cards
- **WHEN** `search_advanced(..., page=1, page_size=10)` is called
- **THEN** a PaginatedResult is returned with 10 cards
- **AND** total_pages=6 (52 / 10, rounded up)

#### Scenario: Default pagination parameters

- **GIVEN** a search query is performed
- **WHEN** `search_advanced(...)` is called without page or page_size
- **THEN** default to page=1, page_size=20
- **AND** return first 20 results

#### Scenario: Pagination with other filters

- **GIVEN** a search with colors=["R"], types=["Creature"] matches 100 cards
- **WHEN** `search_advanced(colors=["R"], types=["Creature"], page=2, page_size=25)` is called
- **THEN** a PaginatedResult is returned with cards 26-50
- **AND** total_count=100, total_pages=4

### Requirement: Oracle Text Phrase Search

The CardRepository SHALL support oracle text phrase search in search_advanced method to enable precise effect-based queries.

#### Scenario: Single oracle text phrase match

- **GIVEN** cards with oracle text "Target creature gets +2/+2" and "Destroy target creature"
- **WHEN** `search_advanced(oracle_text_phrases=["target creature"])` is called
- **THEN** both cards are returned
- **AND** the phrase "target creature" appears in each card's oracle_text

#### Scenario: Multiple oracle text phrases with AND logic

- **GIVEN** cards with various oracle texts
- **WHEN** `search_advanced(oracle_text_phrases=["target creature you control", "gains flying"])` is called
- **THEN** only cards containing BOTH phrases in their oracle text are returned
- **AND** cards with only one phrase are excluded

#### Scenario: Oracle text case-insensitive matching

- **GIVEN** a card with oracle text "Target creature gains Flying until end of turn"
- **WHEN** `search_advanced(oracle_text_phrases=["flying"])` is called
- **THEN** the card is returned (case-insensitive match)

#### Scenario: Oracle text with None value

- **GIVEN** some cards have oracle_text=None (e.g., basic lands)
- **WHEN** `search_advanced(oracle_text_phrases=["draw a card"])` is called
- **THEN** cards with oracle_text=None are excluded from results
- **AND** only cards with non-None oracle_text matching the phrase are returned

#### Scenario: Empty oracle text phrases list

- **GIVEN** any search query
- **WHEN** `search_advanced(oracle_text_phrases=[])` is called
- **THEN** no oracle text filtering is applied
- **AND** results are based on other filters only (equivalent to oracle_text_phrases=None)

#### Scenario: Oracle text with special characters

- **GIVEN** a card with oracle text containing apostrophes or quotes (e.g., "opponent's creature")
- **WHEN** `search_advanced(oracle_text_phrases=["opponent's creature"])` is called
- **THEN** the card is returned
- **AND** special characters are matched literally

#### Scenario: Oracle text combined with color and type filters

- **GIVEN** various cards in the database
- **WHEN** `search_advanced(oracle_text_phrases=["destroy target"], colors=["B"], types=["Instant"])` is called
- **THEN** only black instant cards with "destroy target" in oracle text are returned
- **AND** all filters use AND logic

#### Scenario: Oracle text with format filter

- **GIVEN** cards with matching oracle text in both Standard and non-Standard formats
- **WHEN** `search_advanced(oracle_text_phrases=["draw a card"], format_filter="standard")` is called
- **THEN** only Standard-legal cards matching the oracle text are returned
- **AND** non-Standard cards are excluded

#### Scenario: Oracle text with pagination

- **GIVEN** a search with oracle_text_phrases=["draw a card"] matches 45 cards
- **WHEN** `search_advanced(oracle_text_phrases=["draw a card"], page=2, page_size=20)` is called
- **THEN** a PaginatedResult is returned with cards 21-40
- **AND** total_count=45, total_pages=3
- **AND** all returned cards match the oracle text phrase

### Requirement: Advanced Multi-Criteria Search

The CardRepository SHALL provide a search_advanced method that combines multiple filter criteria using AND logic, with oracle text phrase search, pagination support, and games availability filtering.

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

#### Scenario: Advanced search with games filter

- **GIVEN** various cards in the database
- **WHEN** `search_advanced(colors=["U"], types=["Creature"], games=["arena"])` is called
- **THEN** only blue creature cards available in Arena are returned
- **AND** paper-only cards are excluded

#### Scenario: Advanced search with combined format and games filters

- **GIVEN** various cards in the database
- **WHEN** `search_advanced(colors=["R"], format_filter="standard", games=["arena"])` is called
- **THEN** only red cards that are BOTH Standard-legal AND Arena-available are returned
- **AND** both filters use AND logic with all other criteria

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

### Requirement: Games Availability Filtering

The CardRepository SHALL provide a `_apply_games_filter()` method to filter cards by game availability (paper, arena, mtgo) using OR logic for multiple games.

#### Scenario: Filter by single game

- **GIVEN** cards with games=["paper", "arena"], games=["arena", "mtgo"], and games=["paper"] exist
- **WHEN** `_apply_games_filter(stmt, games=["arena"])` is called
- **THEN** only cards with "arena" in their games array are returned
- **AND** cards with games=["paper", "arena"] and games=["arena", "mtgo"] are included

#### Scenario: Filter by multiple games with OR logic

- **GIVEN** cards with various games combinations exist
- **WHEN** `_apply_games_filter(stmt, games=["paper", "arena"])` is called
- **THEN** cards with "paper" OR "arena" in their games array are returned
- **AND** a card with games=["paper"] is included
- **AND** a card with games=["arena", "mtgo"] is included
- **AND** a card with games=["mtgo"] only is excluded

#### Scenario: None games filter returns all cards

- **GIVEN** cards with various games values exist
- **WHEN** `_apply_games_filter(stmt, games=None)` is called
- **THEN** the statement is returned unmodified
- **AND** no games filtering is applied

#### Scenario: Empty games list returns all cards

- **GIVEN** cards with various games values exist
- **WHEN** `_apply_games_filter(stmt, games=[])` is called
- **THEN** the statement is returned unmodified
- **AND** no games filtering is applied

#### Scenario: Games filter combined with format filter

- **GIVEN** cards exist with various games and legalities
- **WHEN** `_apply_games_filter()` and `_apply_format_filter()` are both applied to a statement
- **THEN** cards must match BOTH filters (AND logic)
- **AND** only cards legal in the format AND available in the specified games are returned

#### Scenario: SQLite JSON array filtering with LIKE

- **GIVEN** a card with games=["paper", "arena"]
- **WHEN** `_apply_games_filter(stmt, games=["arena"])` is called
- **THEN** the SQL query uses `CAST(games AS TEXT) LIKE '%"arena"%'` pattern
- **AND** the card is returned in results

### Requirement: Games Field in Card Schema

The Card Pydantic schema SHALL include a `games` field as a list of strings representing game availability.

#### Scenario: Card schema has games field

- **GIVEN** a Card Pydantic schema instance
- **WHEN** the schema is inspected
- **THEN** a `games` field exists with type `list[str]`
- **AND** the field can contain values "paper", "arena", "mtgo"

#### Scenario: Card schema serializes games field

- **GIVEN** a Card instance with games=["paper", "arena"]
- **WHEN** the Card is serialized to JSON
- **THEN** the games field is included: `{"games": ["paper", "arena"]}`
- **AND** the games array is preserved in serialization

### Requirement: Games Field in CardModel

The CardModel ORM SHALL include a `games` field as a JSON array column storing game availability strings.

#### Scenario: CardModel has games column

- **GIVEN** the CardModel SQLAlchemy definition
- **WHEN** the model is inspected
- **THEN** a `games` column exists with type JSON
- **AND** the column is NOT NULL with default empty list

#### Scenario: CardModel stores games as JSON array

- **GIVEN** a CardModel instance with games=["arena"]
- **WHEN** the instance is committed to the database
- **THEN** the games field is stored as JSON: `["arena"]`
- **AND** the field can be queried using SQLite JSON functions


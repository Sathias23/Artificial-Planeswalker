# Card Queries Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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

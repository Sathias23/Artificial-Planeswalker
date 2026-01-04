# card-queries Spec Delta

## ADDED Requirements

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

The CardRepository SHALL provide a search_advanced method that combines multiple filter criteria using AND logic, with oracle text phrase search and pagination support.

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

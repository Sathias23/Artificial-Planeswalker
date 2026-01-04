# agent-tools Spec Delta

## ADDED Requirements

### Requirement: Oracle Text Search in Advanced Search

The agent SHALL provide oracle text phrase search capability in the advanced card search tool to enable precise effect-based queries.

#### Scenario: Single oracle text phrase match

- **GIVEN** the user searches for cards with oracle_text=["target creature you control"]
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return only cards whose oracle text contains the phrase "target creature you control"
- **AND** the search SHALL be case-insensitive
- **AND** the phrase can appear anywhere in the oracle text

#### Scenario: Multiple oracle text phrases with AND logic

- **GIVEN** the user searches for cards with oracle_text=["target creature you control", "gains flying"]
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return only cards whose oracle text contains BOTH phrases
- **AND** all phrases must be present in the oracle text
- **AND** the order of phrases in the card's oracle text does not matter

#### Scenario: Oracle text with other filters

- **GIVEN** the user searches for oracle_text=["target creature"], colors=["U"], types=["Instant"]
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return only blue instants whose oracle text contains "target creature"
- **AND** all filter criteria must be satisfied (AND logic across all filters)

#### Scenario: Oracle text search case-insensitivity

- **GIVEN** the user searches for oracle_text=["flying"]
- **WHEN** cards in the database have oracle text with "Flying", "flying", or "FLYING"
- **THEN** all variations SHALL match
- **AND** the search is case-insensitive

#### Scenario: Oracle text with format filter

- **GIVEN** a Standard deck is loaded (format filter = "standard")
- **AND** the user searches for oracle_text=["destroy target creature"]
- **WHEN** the search_cards_advanced tool is invoked with auto_filter=True
- **THEN** the tool SHALL return only Standard-legal cards matching the oracle text
- **AND** non-Standard cards are excluded even if they match the oracle text

#### Scenario: Oracle text search with no matches

- **GIVEN** the user searches for oracle_text=["this exact phrase does not exist"]
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return zero results
- **AND** provide helpful suggestions including "try different oracle text phrases"

#### Scenario: Bug 77c559f3 resolution

- **GIVEN** the user searches for oracle_text=["target creature you control", "gains flying"]
- **AND** the format filter is set to "standard"
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return exactly 3 cards: Acrobatic Leap, Fleeting Flight, and Secret Identity
- **AND** SHALL NOT return all 31 cards with the flying keyword
- **AND** only cards whose oracle text contains both exact phrases are included

### Requirement: Pagination in Advanced Search

The agent SHALL provide pagination support in the advanced card search tool to enable navigation through large result sets.

#### Scenario: First page of results

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=1, page_size=20
- **THEN** the tool SHALL return cards 1-20
- **AND** the response SHALL indicate "Page 1 of 3"
- **AND** the response SHALL indicate "showing 1-20 of 52 results"
- **AND** the response SHALL suggest how to view next page

#### Scenario: Middle page of results

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=2, page_size=20
- **THEN** the tool SHALL return cards 21-40
- **AND** the response SHALL indicate "Page 2 of 3"
- **AND** the response SHALL indicate "showing 21-40 of 52 results"

#### Scenario: Last page of results

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=3, page_size=20
- **THEN** the tool SHALL return cards 41-52 (12 cards)
- **AND** the response SHALL indicate "Page 3 of 3"
- **AND** the response SHALL indicate "showing 41-52 of 52 results"
- **AND** the response SHALL NOT suggest viewing next page

#### Scenario: Page beyond last page

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=4, page_size=20
- **THEN** the tool SHALL return zero cards
- **AND** the response SHALL indicate "Page 4 of 3 (no results)"
- **AND** suggest returning to valid page range

#### Scenario: Custom page size

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=1, page_size=10
- **THEN** the tool SHALL return cards 1-10
- **AND** the response SHALL indicate "Page 1 of 6"
- **AND** the response SHALL indicate "showing 1-10 of 52 results"

#### Scenario: Page size limit enforcement

- **GIVEN** the user requests page_size=100
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL cap page_size at 50
- **AND** return maximum 50 results per page
- **AND** recalculate total pages based on capped page_size

#### Scenario: Pagination with oracle text search

- **GIVEN** the user searches for oracle_text=["draw a card"] with page=1, page_size=20
- **WHEN** the search returns 45 matching cards
- **THEN** the first page SHALL return cards 1-20 matching the oracle text
- **AND** the response SHALL indicate "Page 1 of 3"
- **AND** subsequent pages can be requested to view remaining 25 cards

#### Scenario: Natural language pagination request

- **GIVEN** the user previously searched and received page 1 of 3
- **AND** the user says "show me more" or "next page"
- **WHEN** the agent processes the request
- **THEN** the agent SHALL invoke search_cards_advanced with page=2
- **AND** repeat the previous search filters
- **AND** return the next page of results

#### Scenario: Default pagination behavior

- **GIVEN** the user performs a search without specifying page or page_size
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL default to page=1, page_size=20
- **AND** return the first 20 results
- **AND** indicate pagination metadata if more results exist

### Requirement: Backward Compatibility with max_results

The advanced search tool SHALL maintain backward compatibility with the deprecated max_results parameter while transitioning to page/page_size pagination.

#### Scenario: Legacy max_results parameter

- **GIVEN** existing code uses filters with max_results=30
- **WHEN** the search_cards_advanced tool is invoked without page or page_size
- **THEN** the tool SHALL interpret max_results as page_size=30
- **AND** default to page=1
- **AND** return up to 30 results
- **AND** function as before (no breaking change)

#### Scenario: page_size overrides max_results

- **GIVEN** filters specify both max_results=30 and page_size=20
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL use page_size=20
- **AND** ignore max_results
- **AND** max_results is deprecated in favor of page_size

#### Scenario: max_results with pagination

- **GIVEN** filters specify max_results=30 and page=2
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL use page_size=30 (from max_results)
- **AND** return page 2 with 30-result pages
- **AND** calculate pagination metadata accordingly

## MODIFIED Requirements

### Requirement: Advanced Search Result Formatting

The advanced search tool SHALL format results in a clear, scannable list optimized for chat display, including pagination metadata when applicable.

#### Scenario: Standard result formatting

- **GIVEN** the advanced search returns 5 matching cards
- **WHEN** the results are formatted for display
- **THEN** each card SHALL be displayed as:
  - Card name
  - Mana cost (using text notation like "{2}{R}")
  - Type line
  - Power/toughness (if creature)
- **AND** results SHALL be numbered for easy reference

#### Scenario: Result formatting with pagination

- **GIVEN** the advanced search returns 52 cards with page=1, page_size=20
- **WHEN** the results are formatted for display
- **THEN** the header SHALL include "Found 52 cards (Page 1 of 3, showing 1-20)"
- **AND** the footer SHALL indicate "32 more results available"
- **AND** suggest "Say 'next page' or 'show me more' to see page 2"

#### Scenario: Result formatting with oracle text filter

- **GIVEN** the advanced search uses oracle_text=["target creature", "gains flying"]
- **WHEN** the results are formatted for display
- **THEN** the filter summary SHALL include "Oracle text: 'target creature', 'gains flying'"
- **AND** clearly indicate that oracle text filtering was applied

#### Scenario: Result grouping by mana value

- **GIVEN** the advanced search returns cards with various mana values
- **WHEN** formatting for display
- **THEN** results MAY be optionally grouped by mana value
- **AND** include section headers (e.g., "0-1 Mana", "2-3 Mana")

#### Scenario: No results with oracle text suggestion

- **GIVEN** a search with multiple filters returns no results
- **WHEN** oracle text search is available but not used
- **THEN** the "no results" message SHALL suggest "try oracle text search for specific effects"
- **AND** provide an example (e.g., "oracle_text=['destroy target creature']")

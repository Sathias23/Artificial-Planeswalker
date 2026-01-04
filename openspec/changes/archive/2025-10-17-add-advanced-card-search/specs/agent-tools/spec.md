## ADDED Requirements

### Requirement: Advanced Card Search with Multiple Filters

The agent SHALL provide a tool that enables searching for cards using multiple filter criteria including colors, card types, mana value range, and keyword abilities.

#### Scenario: Search by color and type

- **GIVEN** a user asks "show me red creatures"
- **WHEN** the tool is invoked with filters `colors=["R"]` and `types=["Creature"]`
- **THEN** the tool SHALL return a list of cards matching both criteria
- **AND** each result SHALL include card name, mana cost, and type line

#### Scenario: Search by mana value range

- **GIVEN** a user asks "find creatures under 4 mana"
- **WHEN** the tool is invoked with filters `types=["Creature"]` and `mana_value_max=3`
- **THEN** the tool SHALL return cards with mana value 0-3 matching the type filter
- **AND** results SHALL be sorted by mana value ascending

#### Scenario: Search by keyword ability

- **GIVEN** a user asks "show me cards with haste"
- **WHEN** the tool is invoked with filter `keywords=["haste"]`
- **THEN** the tool SHALL search oracle_text for the keyword "haste"
- **AND** return cards containing that keyword in their rules text

#### Scenario: Complex multi-criteria search

- **GIVEN** a user asks "red creatures with haste under 4 mana"
- **WHEN** the tool is invoked with filters `colors=["R"]`, `types=["Creature"]`, `keywords=["haste"]`, `mana_value_max=3`
- **THEN** the tool SHALL return cards matching ALL specified criteria
- **AND** limit results to maximum 20 cards
- **AND** provide count of total matches if more than 20 exist

#### Scenario: No results found

- **GIVEN** a user searches with very restrictive criteria
- **WHEN** the tool query returns zero matching cards
- **THEN** the tool SHALL return a message indicating no cards found
- **AND** suggest relaxing filter criteria (e.g., "Try increasing mana range or removing color restrictions")

#### Scenario: Too many results without refinement

- **GIVEN** a user searches with broad criteria
- **WHEN** the tool query returns more than 20 matching cards
- **THEN** the tool SHALL return the first 20 results
- **AND** indicate total match count (e.g., "Showing 20 of 147 results")
- **AND** suggest adding more filters to narrow the search

#### Scenario: Invalid filter value

- **GIVEN** a user query results in invalid filter parameters
- **WHEN** the tool receives an invalid color code or non-existent type
- **THEN** the tool SHALL return an error message explaining the invalid parameter
- **AND** suggest valid options (e.g., "Valid colors are W, U, B, R, G")

### Requirement: Advanced Search Result Formatting

The advanced search tool SHALL format results in a clear, scannable list optimized for chat display.

#### Scenario: Standard result formatting

- **GIVEN** the advanced search returns 5 matching cards
- **WHEN** the results are formatted for display
- **THEN** each card SHALL be displayed as:
  - Card name
  - Mana cost (using text notation like "{2}{R}")
  - Type line
  - Power/toughness (if creature)
- **AND** results SHALL be numbered for easy reference

#### Scenario: Result grouping by mana value

- **GIVEN** the advanced search returns cards with various mana values
- **WHEN** formatting for display
- **THEN** results MAY be optionally grouped by mana value
- **AND** include section headers (e.g., "0-1 Mana", "2-3 Mana")

### Requirement: Advanced Search Performance

The advanced search tool SHALL execute queries efficiently to meet system performance requirements.

#### Scenario: Query execution time within limits

- **GIVEN** a multi-criteria search is performed
- **WHEN** the repository executes the combined filter query
- **THEN** the query SHALL complete in less than 500ms (per NFR7)
- **AND** use appropriate database indexes for common filter combinations

#### Scenario: Efficient keyword search

- **GIVEN** a keyword ability search is performed
- **WHEN** searching oracle_text for keyword terms
- **THEN** the query SHALL use case-insensitive substring matching
- **AND** limit text search to indexed columns where possible

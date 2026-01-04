# Agent Tools Specification Delta

## MODIFIED Requirements

### Requirement: Advanced Card Search with Multiple Filters

The agent SHALL provide a tool that enables searching for cards using multiple filter criteria including colors, card types, mana value range, keyword abilities, **rarity**, and optional format filtering.

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

#### Scenario: Search by single rarity

- **GIVEN** a user asks "show me rare red creatures"
- **WHEN** the tool is invoked with filters `colors=["R"]`, `types=["Creature"]`, `rarity="rare"`
- **THEN** the tool SHALL return only rare red creatures
- **AND** exclude cards of other rarities

#### Scenario: Search by multiple rarities

- **GIVEN** a user asks "find mythic or rare black cards"
- **WHEN** the tool is invoked with filters `colors=["B"]`, `rarity=["mythic", "rare"]`
- **THEN** the tool SHALL return black cards with rarity mythic OR rare
- **AND** exclude common and uncommon cards

#### Scenario: Complex multi-criteria search

- **GIVEN** a user asks "red creatures with haste under 4 mana"
- **WHEN** the tool is invoked with filters `colors=["R"]`, `types=["Creature"]`, `keywords=["haste"]`, `mana_value_max=3`
- **THEN** the tool SHALL return cards matching ALL specified criteria
- **AND** limit results to maximum 20 cards
- **AND** provide count of total matches if more than 20 exist

#### Scenario: Complex search with rarity filter

- **GIVEN** a user asks "rare or mythic red creatures with haste under 4 mana"
- **WHEN** the tool is invoked with filters `colors=["R"]`, `types=["Creature"]`, `keywords=["haste"]`, `mana_value_max=3`, `rarity=["rare", "mythic"]`
- **THEN** the tool SHALL return only rare or mythic cards matching ALL other criteria
- **AND** common and uncommon cards are excluded even if they match other filters

#### Scenario: Advanced search with format filter

- **GIVEN** the session format filter is set to "standard"
- **AND** a user asks "show me red creatures with haste"
- **WHEN** the tool executes the search
- **THEN** only Standard-legal cards matching the criteria are returned
- **AND** results include format indicator: "(Showing Standard-legal cards only)"

#### Scenario: Advanced search with rarity and format filters

- **GIVEN** the session format filter is set to "standard"
- **AND** a user asks "show me rare black cards"
- **WHEN** the tool executes the search with `colors=["B"]`, `rarity="rare"`
- **THEN** only Standard-legal rare black cards are returned
- **AND** results indicate both rarity and format filtering applied

#### Scenario: No results found

- **GIVEN** a user searches with very restrictive criteria
- **WHEN** the tool query returns zero matching cards
- **THEN** the tool SHALL return a message indicating no cards found
- **AND** suggest relaxing filter criteria (e.g., "Try increasing mana range or removing color restrictions")

#### Scenario: Too many results without refinement

- **GIVEN** a user searches with broad criteria (e.g., "show me creatures")
- **WHEN** the tool query returns more than 20 matches
- **THEN** the tool SHALL return the first 20 results
- **AND** indicate total match count: "Found 150 cards (showing first 20)"
- **AND** suggest adding more filters: "Try refining your search for more specific results"

#### Scenario: Rarity filter displayed in tool Step

- **GIVEN** a user asks "find rare red creatures"
- **WHEN** the agent invokes the tool with `rarity="rare"` parameter
- **THEN** the Chainlit tool Step SHALL display the rarity parameter
- **AND** the Step input shows: `colors=["R"], types=["Creature"], rarity="rare"`

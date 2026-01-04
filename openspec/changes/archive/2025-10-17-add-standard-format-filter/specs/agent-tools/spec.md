## ADDED Requirements

### Requirement: Format Filter Control Tool

The agent SHALL provide a tool that enables users to set or clear the format legality filter for card queries.

#### Scenario: Enable Standard format filter

- **GIVEN** the format filter is currently disabled (None)
- **WHEN** the user asks "only show me Standard-legal cards"
- **AND** the `set_format_filter` tool is invoked with format="standard"
- **THEN** the session context format filter is set to "standard"
- **AND** the agent responds with confirmation: "Format filter set to Standard. I'll only show Standard-legal cards in searches."

#### Scenario: Disable format filter

- **GIVEN** the format filter is currently set to "standard"
- **WHEN** the user asks "show me all cards regardless of format"
- **AND** the `set_format_filter` tool is invoked with format=None
- **THEN** the session context format filter is cleared
- **AND** the agent responds with confirmation: "Format filter disabled. I'll show all cards regardless of format legality."

#### Scenario: Check current filter status

- **GIVEN** a format filter is currently set
- **WHEN** the user asks "what format filter is active?"
- **THEN** the agent responds with the current filter status
- **AND** indicates whether filtering is enabled or disabled

#### Scenario: Invalid format value

- **GIVEN** the user attempts to set an unsupported format
- **WHEN** the `set_format_filter` tool is invoked with format="modern"
- **THEN** the tool returns an error message: "Format 'modern' is not supported yet. Supported formats: standard"
- **AND** the session context format filter remains unchanged

### Requirement: Format-Aware Card Lookup

The card lookup tool SHALL respect the session format filter when querying cards.

#### Scenario: Card lookup with Standard filter active

- **GIVEN** the session format filter is set to "standard"
- **WHEN** the user asks "Show me Sol Ring"
- **AND** Sol Ring has `legalities.standard = "not_legal"`
- **THEN** the tool returns: "Sol Ring not found in Standard-legal cards. (Format filter: Standard)"
- **AND** suggests: "To see all cards, disable the format filter."

#### Scenario: Card lookup without format filter

- **GIVEN** the session format filter is None
- **WHEN** the user asks "Show me Sol Ring"
- **THEN** the tool returns Sol Ring's card details
- **AND** no format legality message is included

#### Scenario: Partial match with format filter

- **GIVEN** the session format filter is set to "standard"
- **WHEN** the user asks "Show me Bolt"
- **AND** only Standard-legal "Bolt" cards exist in results
- **THEN** the tool returns only Standard-legal matching cards
- **AND** includes note: "(Showing Standard-legal cards only)"

### Requirement: Format-Aware Advanced Search

The advanced card search tool SHALL respect the session format filter when executing multi-criteria searches.

#### Scenario: Advanced search with Standard filter active

- **GIVEN** the session format filter is set to "standard"
- **WHEN** the user asks "show me red creatures with haste under 4 mana"
- **THEN** the tool applies all search criteria AND format filter
- **AND** returns only cards with `legalities.standard = "legal"`
- **AND** includes header: "Standard-legal red creatures with haste under 4 mana:"

#### Scenario: Advanced search without format filter

- **GIVEN** the session format filter is None
- **WHEN** the user asks "show me red creatures with haste under 4 mana"
- **THEN** the tool applies search criteria without format restriction
- **AND** returns all matching cards regardless of format
- **AND** no format indicator is included in results

#### Scenario: Format filter reduces results to zero

- **GIVEN** the session format filter is set to "standard"
- **WHEN** the user performs a search that returns no Standard-legal cards
- **THEN** the tool returns: "No Standard-legal cards found matching your criteria."
- **AND** suggests: "Try relaxing your search criteria or disable the format filter to see all cards."

### Requirement: Format Filter Session Context

The agent dependencies SHALL include format filter state that persists across tool invocations within a session.

#### Scenario: Format filter persists across tool calls

- **GIVEN** the format filter is set to "standard"
- **WHEN** multiple card queries are made in the same session
- **THEN** all queries use the "standard" format filter
- **AND** the user does not need to specify format on each query

#### Scenario: New session resets format filter

- **GIVEN** a previous session had format filter set to "standard"
- **WHEN** a new session is started
- **THEN** the format filter is initialized to None (disabled)
- **AND** the user must explicitly set format filter if desired

#### Scenario: Format filter accessible to all tools

- **GIVEN** the format filter is stored in session context
- **WHEN** any card query tool accesses the context
- **THEN** the tool can read the current format filter value
- **AND** apply it to repository queries

## MODIFIED Requirements

### Requirement: Card Lookup by Name

The agent SHALL provide a tool that enables looking up Magic: The Gathering cards by name using natural language queries with optional format filtering.

#### Scenario: Exact name match found

- **GIVEN** a user asks "Show me Lightning Bolt"
- **WHEN** the tool is invoked with query "Lightning Bolt"
- **THEN** the tool SHALL return a formatted string containing:
  - Card name
  - Mana cost
  - Type line
  - Oracle text
  - Color identity

#### Scenario: Partial name match with single result

- **GIVEN** a user asks "Show me cards with 'Lightning Bol' in the name"
- **WHEN** the tool is invoked with query "Lightning Bol"
- **AND** only one card matches the partial query
- **THEN** the tool SHALL return the matching card's formatted details

#### Scenario: Partial name match with multiple results

- **GIVEN** a user asks "Show me Bolt"
- **WHEN** the tool is invoked with query "Bolt"
- **AND** multiple cards (2-10) match the partial query
- **THEN** the tool SHALL return a list of matching card names with a "Did you mean?" message

#### Scenario: Partial name match with too many results

- **GIVEN** a user asks "Show me cards with 'a' in the name"
- **WHEN** the tool is invoked with query "a"
- **AND** more than 10 cards match the partial query
- **THEN** the tool SHALL return the first 10 matching card names with a suggestion to refine the search

#### Scenario: Card not found

- **GIVEN** a user asks "Show me Nonexistent Card XYZ"
- **WHEN** the tool is invoked with query "Nonexistent Card XYZ"
- **AND** no cards match (exact or partial)
- **THEN** the tool SHALL return a helpful "not found" message suggesting the user check spelling

#### Scenario: Card not found due to format filter

- **GIVEN** the session format filter is set to "standard"
- **AND** a user asks "Show me Sol Ring"
- **WHEN** Sol Ring exists but has `legalities.standard = "not_legal"`
- **THEN** the tool SHALL return a "not found" message indicating format filter is active
- **AND** suggest disabling format filter to see the card

#### Scenario: Database connection failure

- **GIVEN** the database is unavailable or connection fails
- **WHEN** the tool is invoked with any query
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework

### Requirement: Advanced Card Search with Multiple Filters

The agent SHALL provide a tool that enables searching for cards using multiple filter criteria including colors, card types, mana value range, and keyword abilities, with optional format filtering.

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

#### Scenario: Advanced search with format filter

- **GIVEN** the session format filter is set to "standard"
- **AND** a user asks "show me red creatures with haste"
- **WHEN** the tool executes the search
- **THEN** only Standard-legal cards matching the criteria are returned
- **AND** results include format indicator: "(Showing Standard-legal cards only)"

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

### Requirement: Agent Dependency Injection

The agent SHALL support dependency injection for repositories and services via a type-safe dependencies structure.

#### Scenario: Dependencies provided to agent at runtime

- **GIVEN** an agent is created with `AgentDependencies` as the deps type
- **WHEN** the agent is invoked with `agent.run(deps=dependencies_instance)`
- **THEN** tools SHALL access repositories via `ctx.deps.card_repository`

#### Scenario: Tool accesses repository via context

- **GIVEN** a tool function decorated with `@agent.tool`
- **WHEN** the tool receives `RunContext[AgentDependencies]` as first parameter
- **THEN** the tool SHALL access the card repository via `ctx.deps.card_repository`
- **AND** invoke repository methods for database queries

### Requirement: Tool Documentation

The card lookup tool SHALL provide clear documentation via docstring for LLM schema generation.

#### Scenario: LLM receives tool description

- **GIVEN** the agent is processing a user query
- **WHEN** the LLM decides which tool to use
- **THEN** the LLM SHALL receive a tool description extracted from the function docstring

#### Scenario: LLM receives parameter descriptions

- **GIVEN** the card lookup tool has parameters
- **WHEN** the LLM constructs a tool call
- **THEN** the LLM SHALL receive parameter descriptions extracted from docstring Args section

### Requirement: Tool Error Handling

The card lookup tool SHALL handle expected errors gracefully with user-friendly messages.

#### Scenario: User-friendly error for not found

- **GIVEN** a card query returns no results
- **WHEN** the tool returns an error message
- **THEN** the message SHALL be conversational and suggest next steps
- **AND** the message SHALL NOT include technical error codes or stack traces

#### Scenario: User-friendly error for ambiguous query

- **GIVEN** a card query returns too many results
- **WHEN** the tool returns an error message
- **THEN** the message SHALL list matching options (up to 10)
- **AND** suggest refining the search

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

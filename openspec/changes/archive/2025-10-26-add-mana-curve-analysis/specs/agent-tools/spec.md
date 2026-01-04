## ADDED Requirements

### Requirement: Analyze Mana Curve Tool

The agent SHALL provide an `analyze_mana_curve` tool that analyzes the active deck's mana curve and returns formatted analysis with visualization.

#### Scenario: Tool available in agent tools list

- **GIVEN** the PydanticAI agent is initialized
- **WHEN** querying available tools
- **THEN** `analyze_mana_curve` SHALL be present in the tools list
- **AND** tool metadata SHALL describe its purpose as "Analyze the mana curve of the active deck"

#### Scenario: Tool execution with active deck

- **GIVEN** a user has loaded deck "Mono Red Aggro" as active deck
- **WHEN** agent invokes `analyze_mana_curve` tool
- **THEN** tool SHALL retrieve active deck from repository
- **AND** calculate mana curve distribution
- **AND** analyze curve for problems and archetype
- **AND** return formatted markdown string with chart and recommendations

#### Scenario: Tool returns formatted markdown

- **GIVEN** `analyze_mana_curve` tool executes successfully
- **WHEN** the tool returns its result
- **THEN** result SHALL be markdown-formatted string
- **AND** include mana curve chart as markdown table
- **AND** include summary statistics (total cards, avg CMC, lands)
- **AND** include detected problems (if any)
- **AND** include archetype-specific recommendations

#### Scenario: Natural language query triggers tool

- **GIVEN** agent is running with conversation session
- **WHEN** user sends message "analyze my mana curve"
- **THEN** agent SHALL select and invoke `analyze_mana_curve` tool
- **AND** stream formatted analysis back to user in chat

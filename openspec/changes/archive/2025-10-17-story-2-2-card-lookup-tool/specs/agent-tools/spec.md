# Agent Tools Specification

## ADDED Requirements

### Requirement: Card Lookup by Name

The agent SHALL provide a tool that enables looking up Magic: The Gathering cards by name using natural language queries.

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

#### Scenario: Database connection failure

- **GIVEN** the database is unavailable or connection fails
- **WHEN** the tool is invoked with any query
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework

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

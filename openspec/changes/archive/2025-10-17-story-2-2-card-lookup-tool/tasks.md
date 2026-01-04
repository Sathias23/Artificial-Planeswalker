# Implementation Tasks: Story 2.2 Card Lookup Tool

## 1. Core Infrastructure

- [x] 1.1 Create `src/agent/tools/` directory and `__init__.py`
- [x] 1.2 Create `AgentDependencies` dataclass in `src/agent/dependencies.py`
- [x] 1.3 Update `src/agent/core.py` to accept `deps_type=AgentDependencies`
- [x] 1.4 Update agent type signature from `Agent[None, str]` to `Agent[AgentDependencies, str]`

## 2. Card Lookup Tool Implementation

- [x] 2.1 Create `src/agent/tools/card_lookup.py` module
- [x] 2.2 Implement `lookup_card_by_name` tool function with `@agent.tool` decorator
- [x] 2.3 Implement exact match logic using `card_repository.find_by_name_exact()`
- [x] 2.4 Implement partial match fallback using `card_repository.find_by_name_partial()`
- [x] 2.5 Implement query result handling:
  - [x] Single result: Format and return card details
  - [x] Multiple results (2-10): Return "Did you mean?" list
  - [x] Many results (>10): Return truncated list with refinement message
  - [x] No results: Return helpful "not found" message
- [x] 2.6 Implement card formatting helper function (name, mana_cost, type_line, oracle_text, colors)
- [x] 2.7 Add comprehensive docstring for LLM schema generation

## 3. Agent Integration

- [x] 3.1 Import tool in `src/agent/core.py`
- [x] 3.2 Register tool with agent instance (if not auto-registered by decorator)
- [x] 3.3 Update `create_agent()` factory to configure dependencies

## 4. Unit Tests

- [x] 4.1 Create `tests/agent/tools/` directory and `__init__.py`
- [x] 4.2 Create `tests/agent/tools/test_card_lookup.py`
- [x] 4.3 Test exact match found scenario (mock repository returning single card)
- [x] 4.4 Test partial match with single result scenario
- [x] 4.5 Test partial match with multiple results (2-10) scenario
- [x] 4.6 Test partial match with many results (>10) scenario
- [x] 4.7 Test card not found scenario (empty results)
- [x] 4.8 Test database error handling (repository raises exception)
- [x] 4.9 Test card formatting output format
- [x] 4.10 Verify tool docstring is properly formatted for schema generation

## 5. Integration Tests

- [x] 5.1 Create `tests/integration/` directory if not exists
- [x] 5.2 Create `tests/integration/test_agent_card_lookup.py`
- [x] 5.3 Set up integration test fixtures:
  - [x] In-memory SQLite database
  - [x] Sample card data (10-20 cards including "Lightning Bolt", "Shock", "Bolt Bend")
  - [x] CardRepository with test session
  - [x] AgentDependencies with test repository
- [x] 5.4 Test end-to-end agent invocation with card lookup:
  - [x] Exact name query ("Show me Lightning Bolt")
  - [x] Partial name query ("Show me cards with bolt")
  - [x] Ambiguous query ("Show me Bolt" with multiple results)
  - [x] Not found query ("Show me Nonexistent Card")
- [x] 5.5 Verify agent response contains expected card data
- [x] 5.6 Verify agent handles tool errors gracefully

## 6. Documentation

- [x] 6.1 Add docstring examples to `lookup_card_by_name` function
- [x] 6.2 Update `src/agent/README.md` (if exists) to document tool usage
- [x] 6.3 Add inline comments for complex query logic

## 7. Code Quality

- [x] 7.1 Run `ruff check` and fix linting issues
- [x] 7.2 Run `ruff format` to format code
- [x] 7.3 Run `mypy` strict type checking and resolve all errors
- [x] 7.4 Ensure test coverage for tool module ≥70%
- [x] 7.5 Verify pre-commit hooks pass

## 8. Manual Testing

- [x] 8.1 Test tool in isolation with real database (use test script)
- [x] 8.2 Verify exact match queries return correct card
- [x] 8.3 Verify partial match queries handle ambiguity well
- [x] 8.4 Verify error messages are user-friendly and actionable
- [x] 8.5 Test with edge cases:
  - [x] Very short query ("a")
  - [x] Query with special characters ("Jace, the Mind Sculptor")
  - [x] Query with punctuation ("Lightning Bolt!")
  - [x] Empty string (if possible to trigger)

# Story 2.2: Card Lookup Tool Implementation

## Why

[Reference Archon task: Story 2.2 - Task ID: 38cb6148-bbe8-43b7-85dd-419dbadeb6af]

Enable users to ask the agent for specific cards by name using natural language to quickly find card details without memorizing exact card names. This tool bridges the gap between user intent and the existing card query infrastructure (Story 1.3), providing the agent with structured access to card data.

Currently, the PydanticAI agent (Story 2.1) lacks tools to interact with the local card database. Users cannot ask questions like "Show me Lightning Bolt" or "Find cards with 'bolt' in the name" because the agent has no mechanism to invoke the existing `CardRepository` query functions.

## What Changes

This change introduces a PydanticAI tool that enables the agent to look up cards by name:

1. **New tool module**: `src/agent/tools/card_lookup.py` with `@agent.tool` decorated function
2. **Tool capabilities**:
   - Accept natural language card name queries (exact or partial matches)
   - Invoke `CardRepository.find_by_name_exact()` for exact matches
   - Invoke `CardRepository.find_by_name_partial()` for partial matches
   - Return structured card data (name, mana cost, type, oracle text, colors)
   - Handle ambiguous queries by suggesting alternatives
   - Gracefully handle "card not found" scenarios with helpful error messages
3. **Dependencies management**: Tool uses `RunContext` to access `CardRepository` via dependency injection
4. **Error handling**: Structured error responses for database failures and edge cases
5. **Testing**:
   - Unit tests for tool invocation with various query patterns
   - Integration tests for end-to-end agent + tool + database flow

## Impact

### Affected Specs
- **New capability**: `agent-tools` (card lookup tools for PydanticAI agent)
- **Existing capability**: `agent-core` (Story 2.1 agent configuration - minor update to register tool)

### Affected Code
- `src/agent/tools/` (new directory)
  - `src/agent/tools/__init__.py` (new)
  - `src/agent/tools/card_lookup.py` (new)
- `src/agent/core.py` (modify to register tool with agent)
- `tests/agent/tools/` (new directory)
  - `tests/agent/tools/test_card_lookup.py` (new)
- `tests/integration/` (new directory if not exists)
  - `tests/integration/test_agent_card_lookup.py` (new)

### Dependencies
- No new external dependencies required
- Leverages existing:
  - `CardRepository` (Story 1.3)
  - `Card` Pydantic schema (Story 1.2)
  - `Agent` and `RunContext` from PydanticAI (Story 2.1)

## Research Summary

### Archon RAG Knowledge Sources

**Source: ai.pydantic.dev (PydanticAI Documentation)**

Key findings from RAG search:

1. **Tool Definition Pattern**:
   - Use `@agent.tool` decorator for functions that take `RunContext` as first argument
   - Tool functions can be sync or async (prefer async for database operations)
   - Docstrings are inspected to generate tool descriptions and parameter schemas for LLM
   - Example pattern:
     ```python
     @agent.tool
     async def my_tool(ctx: RunContext[DepsType], param: str) -> ReturnType:
         """Tool description for LLM.

         Args:
             param: Parameter description for LLM schema
         """
         # Access dependencies via ctx.deps
         return result
     ```

2. **Dependency Injection via RunContext**:
   - `RunContext[DepsType]` provides access to injected dependencies via `ctx.deps`
   - Dependencies passed to agent via `deps` parameter in `agent.run()` or `agent.run_sync()`
   - Enables testing with mock repositories

3. **Error Handling**:
   - Tools can raise exceptions that the agent will see
   - Return structured error messages as strings for better UX
   - Use `retries` parameter in decorator for transient errors

4. **Tool Registration**:
   - Tools automatically registered when decorated with `@agent.tool`
   - Alternative: Use `Tool.from_schema()` for custom JSON schemas
   - Can group tools into `FunctionToolset` for modularity

### Additional Research

**CardRepository Analysis** (from codebase inspection):
- `find_by_name_exact(name: str) -> Card | None`: Case-insensitive exact match
- `find_by_name_partial(query: str) -> list[Card]`: Case-insensitive substring search
- Both return `Card` Pydantic schemas (not ORM models)
- Async methods requiring `AsyncSession`

**Agent Core Analysis** (from `src/agent/core.py`):
- Current agent has no `deps_type` configured (`Agent[None, str]`)
- Need to update agent to accept repository dependencies
- Agent uses OpenRouter + PydanticAI with custom system prompt

### Web Search

No additional web search required - Archon RAG provided sufficient documentation.

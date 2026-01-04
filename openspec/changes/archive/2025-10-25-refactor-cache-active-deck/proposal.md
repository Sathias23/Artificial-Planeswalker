# Cache Active Deck in AgentDependencies

## Why

Currently, every deck tool performs repetitive operations: check if `active_deck_id` exists, fetch deck from database, handle null cases. This creates two database queries per tool invocation (ID check + fetch) and duplicates error handling across 6+ tools. The active deck ID property returns only a UUID string, requiring tools to make repository calls to get actual deck data.

Caching the active deck in `AgentDependencies` eliminates this repetitive pattern, reduces database queries from 2 to 1 per request, and provides tools with immediate access to deck data.

## What Changes

- Modify `AgentDependencies` to cache the full active `Deck` object instead of just the ID
- Update `get_agent_dependencies()` in UI layer to load active deck once per request
- Add `active_deck` property to `AgentDependencies` (replaces `active_deck_id`)
- Refactor all deck tools to use `deps.active_deck` directly (eliminating boilerplate)
- Update tests to reflect new caching behavior

**Performance Impact**: Reduces database queries for deck tools from 2 per invocation to 1 per request (shared across all tools in the same agent run).

**No Breaking Changes**: This is an internal refactoring that does not affect user-facing behavior or API contracts.

## Impact

- **Affected specs**: `agent-core` (AgentDependencies structure, session-aware dependencies)
- **Affected code**:
  - `src/agent/dependencies.py` - Add `active_deck` field, update property
  - `src/ui/app.py` - Update `get_agent_dependencies()` to load deck
  - `src/agent/tools/deck_tools.py` - Simplify all 6+ deck tools
  - `tests/unit/agent/tools/test_deck_tools.py` - Update mocks for cached deck
  - `tests/integration/agent/test_deck_creation.py` - Update deck access patterns

## Research Findings

No external research required - this is an internal refactoring based on existing patterns:
- Dependency injection pattern already established in `AgentDependencies`
- Session manager pattern already handles state persistence
- Database session lifecycle already managed in `get_agent_dependencies()`

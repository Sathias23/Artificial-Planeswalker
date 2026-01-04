# Fix Database Transaction Rollback Isolation Bug

## Why

**Bug Report**: #2a1c1f29 - Database transaction locking issue

When PydanticAI agent tools execute multiple database operations within a single request (e.g., adding multiple cards to a deck in rapid succession), they share a single SQLAlchemy async session. If one tool triggers an IntegrityError (like trying to add a duplicate card), the session enters a rolled-back state. Subsequent tools fail with:

```
This Session's transaction has been rolled back due to a previous exception during flush.
```

This prevents users from completing deck operations and degrades the user experience. The bug manifests when:
- Multiple cards are added rapidly in one conversation turn
- A UNIQUE constraint violation occurs (duplicate card)
- Subsequent operations fail because the session is in a rolled-back state

**Root Cause**: The UI layer creates one session per request (`get_agent_dependencies()` at src/ui/app.py:87-117), which is shared across all tool executions in that request. SQLAlchemy automatically rolls back transactions on errors, but the code doesn't handle the rolled-back state properly.

## What Changes

This proposal implements session-level transaction isolation and rollback recovery to prevent shared session state from causing cascading failures:

1. **Repository Layer** - Add explicit transaction management with try/except/rollback in all write operations
2. **UI Layer** - Add session state validation in `get_agent_dependencies()` to ensure clean session state
3. **Tool Layer** - Add defensive session rollback at the start of write operations (deck modifications)
4. **Error Recovery** - Implement rollback-and-retry pattern for IntegrityError in `add_card_to_deck()`

**Breaking Changes**: None - All changes are internal implementation details

## Impact

**Affected Specs**:
- `data-layer` - Repository transaction management
- `agent-tools` - Deck tool session handling

**Affected Code**:
- `src/data/repositories/deck.py` - All write methods (add_card_to_deck, remove_card_from_deck, update_card_quantity, create_deck, delete_deck)
- `src/ui/app.py` - get_agent_dependencies() session lifecycle
- `src/agent/tools/deck_tools.py` - All deck modification tools (add_card_to_deck, remove_card_from_deck, update_card_quantity, create_deck, delete_deck)

**Testing Strategy**:
- Unit tests for concurrent card additions to same deck
- Integration tests for session rollback scenarios
- Regression tests for bug report scenario (rapid sequential adds)

**Migration**: No database or API changes required

## Research Summary

**Archon RAG Sources**:
- FastAPI dependency patterns with exception handling (fastapi.tiangolo.com)
- SQLModel session management best practices (sqlmodel.tiangolo.com)

**Key Findings**:
1. FastAPI best practice: Catch exceptions in dependency functions, rollback session, re-raise
2. SQLAlchemy 2.0 pattern: Use explicit `session.rollback()` in exception handlers
3. Async session behavior: Automatically rolls back on unhandled exceptions, but doesn't reset state

**Web Research**:
- SQLAlchemy 2.0 documentation emphasizes explicit transaction boundaries
- Context managers with `session.begin()` handle rollback automatically
- Traditional try/except pattern recommended for granular control

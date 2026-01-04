# Design: Database Transaction Rollback Isolation

## Context

The application uses SQLAlchemy 2.0 async sessions with SQLite backend. PydanticAI agents execute multiple tools per request, all sharing a single session created by `get_agent_dependencies()`. When a tool triggers an IntegrityError (e.g., duplicate card insertion), SQLAlchemy automatically rolls back the transaction, leaving the session in an unusable state for subsequent tools.

**Current Architecture**:
```
User Message
  → on_message() (app.py:178)
    → get_agent_dependencies() [creates ONE session] (app.py:87-117)
      → run_agent_with_session() (app.py:207)
        → Tool 1: add_card_to_deck() [uses session]
          → IntegrityError → SESSION ROLLED BACK
        → Tool 2: view_deck() [uses SAME rolled-back session]
          → FAILS: "transaction has been rolled back"
```

**Constraints**:
- SQLite backend (limited transaction isolation features)
- Async/await throughout (no sync fallbacks)
- Must maintain existing tool interfaces (no breaking changes)
- Session lifecycle managed by UI layer context manager

## Goals / Non-Goals

**Goals**:
- Prevent rolled-back sessions from causing cascading tool failures
- Add defensive session state management in repositories
- Implement rollback recovery in UI layer session factory
- Maintain existing error reporting and user experience

**Non-Goals**:
- Full nested transaction support (SQLite limitations)
- Per-tool session isolation (would break potential future multi-tool transactions)
- Retry logic at agent level (keep retries in tool layer)
- Database migration or schema changes

## Decisions

### Decision 1: Three-Layer Defense Strategy

**What**: Implement transaction safety at three layers:
1. **Repository Layer** - Explicit try/except/rollback in all write operations
2. **UI Layer** - Session state validation and recovery in `get_agent_dependencies()`
3. **Tool Layer** - Defensive rollback at start of write operations

**Why**: Defense in depth ensures robustness. Each layer handles different failure scenarios:
- Repository: Catches database-level errors (IntegrityError, OperationalError)
- UI Layer: Ensures clean session state before tool execution
- Tool Layer: Adds redundancy for edge cases

**Alternatives Considered**:
- **Per-tool sessions**: Would prevent transaction sharing across tools (future feature)
- **Agent-level retry**: Would duplicate error handling, harder to test
- **Savepoint-based nested transactions**: SQLite has limited support, added complexity

### Decision 2: Repository Layer Transaction Management

**Pattern**:
```python
async def add_card_to_deck(...) -> DeckCard:
    try:
        deck_card_model = DeckCardModel(...)
        self.session.add(deck_card_model)
        await self.session.commit()

        # Reload with relationships
        stmt = select(DeckCardModel).where(...).options(...)
        result = await self.session.execute(stmt)
        return DeckCard.model_validate(result.scalar_one())

    except IntegrityError as e:
        await self.session.rollback()
        raise  # Re-raise for tool layer to handle
    except Exception as e:
        await self.session.rollback()
        raise
```

**Why**: Explicit transaction boundaries make error handling predictable. Repositories are the single source of truth for database operations.

**Trade-off**: Slight performance overhead for rollback calls (negligible with SQLite)

### Decision 3: UI Layer Session State Recovery

**Pattern**:
```python
@asynccontextmanager
async def get_agent_dependencies(session_id: str) -> AsyncGenerator[AgentDependencies, None]:
    async with _session_factory() as session:
        try:
            # Ensure clean session state before tools execute
            if session.in_transaction() and session.is_modified:
                await session.rollback()

            # Create dependencies and yield
            yield AgentDependencies(...)

        except Exception as e:
            # Rollback on any error during tool execution
            await session.rollback()
            raise
```

**Why**: Guarantees clean session state at request boundaries. Prevents state leakage between tool calls.

### Decision 4: Tool Layer Defensive Rollback

**Pattern** (applied to deck write operations):
```python
async def add_card_to_deck(ctx: RunContext[AgentDependencies], ...) -> str:
    try:
        deps = ctx.deps

        # Defensive: Ensure clean session state
        if deps.deck_repository.session.in_transaction():
            await deps.deck_repository.session.rollback()

        # ... existing logic ...

    except IntegrityError as e:
        # Repository already rolled back, handle user-facing error
        return f"Failed to add card: {user_friendly_message}"
```

**Why**: Adds redundancy for edge cases. Low cost (rollback is cheap when no active transaction).

**Trade-off**: Slight code duplication, but improves robustness.

## Risks / Trade-offs

**Risk 1: Performance Overhead**
- **Impact**: Additional rollback calls add latency
- **Mitigation**: SQLite rollback is fast (<1ms), negligible impact
- **Measurement**: Add performance test for rapid deck operations

**Risk 2: Lost Transaction Context**
- **Impact**: Defensive rollbacks could lose intended transaction state
- **Mitigation**: Currently no multi-tool transactions, so no impact
- **Future**: Document transaction boundaries for future features

**Risk 3: Error Message Clarity**
- **Impact**: Rollback errors might obscure root cause
- **Mitigation**: Log original error before rollback, preserve exception chain

## Migration Plan

**Phase 1: Repository Layer** (Highest Risk Area)
1. Add try/except/rollback to `DeckRepository` write methods
2. Add unit tests for IntegrityError scenarios
3. Verify existing tests pass

**Phase 2: UI Layer** (Session Lifecycle)
1. Add session state validation in `get_agent_dependencies()`
2. Add integration tests for rolled-back session recovery
3. Test with multiple concurrent tool calls

**Phase 3: Tool Layer** (Defensive Layer)
1. Add defensive rollback to deck write tools
2. Add regression test for bug #2a1c1f29 scenario
3. Performance test for rapid deck operations

**Rollback Plan**:
- All changes are internal, can revert without data loss
- No database migrations required
- Existing error handling remains as fallback

## Open Questions

1. **Should we implement session pooling or per-tool sessions in the future?**
   - Deferred: Current approach is sufficient, revisit if concurrent operations needed

2. **Should we add observability for rolled-back sessions?**
   - Recommended: Add Logfire instrumentation for rollback events (separate change)

3. **Should we validate session state in all repositories, not just DeckRepository?**
   - Deferred: CardRepository is read-only, add if write operations added later

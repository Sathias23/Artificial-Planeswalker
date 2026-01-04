# Fix Session State Persistence

## Why

Story 3.4 (Conversation Session Management) from the PRD is 85% complete with production-ready infrastructure, but has two critical gaps that prevent full acceptance:

1. **Format filter preference does not persist across messages in a session** - When users set a format filter (e.g., "Only show me Standard cards"), it applies only to the current message. The next message resets `format_filter` to `None` because `get_agent_dependencies()` creates a fresh instance per message.

2. **Missing integration test for multi-turn conversations** - While 15 comprehensive unit tests exist for `ConversationSessionManager` and `run_agent_with_session()`, there are no integration tests verifying that context actually preserves across multiple messages in realistic conversation scenarios. This blocks Story 3.4 Acceptance Criteria #7: "Integration tests verify context preservation across multiple messages."

These gaps prevent the application from providing a seamless conversational experience where user preferences persist and context flows naturally across the conversation.

## What Changes

### Code Changes

- **Modify** `AgentDependencies` to include session-aware format filter retrieval
- **Add** session state storage for format filter in `ConversationSessionManager`
- **Modify** `get_agent_dependencies()` context manager to restore format filter from session
- **Modify** `set_format_filter()` tool to persist changes to session storage

### Test Changes

- **Add** integration test `test_multi_turn_conversation_context()` in `tests/integration/agent/`
- **Add** integration test `test_format_filter_persistence_across_messages()` in `tests/integration/agent/`
- **Add** integration test `test_context_dependent_follow_up_questions()` in `tests/integration/ui/`

### Non-Breaking Changes

All changes are additive or internal refactoring. No breaking API changes. Existing functionality continues to work unchanged.

## Impact

### Affected Specs
- `agent-core` - Session state management expanded to include format filter
- `chainlit-ui` - Context preservation requirements fully validated with integration tests

### Affected Code
- `src/agent/core.py` - `ConversationSessionManager` class (add format filter storage)
- `src/agent/dependencies.py` - `AgentDependencies` dataclass (session-aware format filter)
- `src/ui/app.py` - `get_agent_dependencies()` context manager (restore session state)
- `src/agent/tools/format_filter.py` - `set_format_filter()` tool (persist to session)
- `tests/integration/agent/test_session_context.py` - NEW FILE
- `tests/integration/ui/test_chainlit_session.py` - NEW FILE (or modify existing `test_chainlit_agent_integration.py`)

### User Impact
- **Positive:** Users can set format preference once and it persists for the entire session
- **Positive:** More natural conversation flow with proper context retention
- **No Breaking Changes:** Existing conversations continue to work unchanged

### Testing Impact
- Integration test coverage increases from 0% to 100% for multi-turn conversation scenarios
- Completes Story 3.4 Acceptance Criteria #7
- Provides regression protection for session state management

## Research Summary

### Problem Analysis

**Format Filter Persistence Gap:**

The current implementation stores format filter in `AgentDependencies.format_filter`, but this is recreated on every message:

```python
# src/ui/app.py - Current behavior
async with get_agent_dependencies() as deps:  # Creates NEW AgentDependencies
    response_text = await run_agent_with_session(
        user_input=user_input,
        session_id=session_id,
        deps=deps,  # format_filter is always None here
        agent=_agent,
    )
```

**Integration Test Gap:**

The existing integration tests in `tests/integration/agent/test_agent_card_lookup.py:313` have `test_multiple_consecutive_lookups()` but it does NOT pass message history between calls - each call is independent.

### Solution Approach

**Option A: Store format filter in ConversationSessionManager (RECOMMENDED)**
- Consistent with how message history is managed
- Clean separation of concerns
- No coupling to UI layer (Chainlit)

**Option B: Store in Chainlit's cl.user_session**
- Tighter coupling to Chainlit UI
- Harder to test in agent layer unit tests
- Less portable if UI layer changes

**Selected:** Option A - Store in `ConversationSessionManager` for consistency

### Research Findings

Reviewed PydanticAI documentation on message history and dependency injection:
- `AgentDependencies` is designed as a dependency injection container
- Dependencies can include mutable session state
- PydanticAI supports accessing session context via `RunContext.deps`

Reviewed Chainlit session management:
- `cl.user_session` provides per-session key-value storage
- Session IDs are stable throughout conversation
- Session state is isolated between concurrent users

## Design Decisions

### Format Filter Storage Architecture

**Decision:** Store format filter in `ConversationSessionManager` alongside message history

**Rationale:**
- Keeps all session state in one place
- Agent layer remains independent of UI framework
- Easy to test and reason about
- Consistent with existing message history pattern

**Implementation:**
```python
class ConversationSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, list[ModelMessage]] = {}
        self._format_filters: dict[str, FormatFilter] = {}  # NEW

    def get_format_filter(self, session_id: str) -> FormatFilter:
        return self._format_filters.get(session_id, None)

    def set_format_filter(self, session_id: str, filter: FormatFilter) -> None:
        self._format_filters[session_id] = filter
```

### Integration Test Scenarios

**Test 1: Multi-turn conversation with context**
```python
async def test_multi_turn_conversation_context():
    """Verify agent remembers context across multiple messages."""
    # Message 1: Ask about a card
    response1 = await run_agent_with_session("Tell me about Bloodhall Ooze", session_id, deps)
    assert "Bloodhall Ooze" in response1

    # Message 2: Follow-up question using "it"
    response2 = await run_agent_with_session("What set is it from?", session_id, deps)
    assert "Conflux" in response2 or "Bloodhall Ooze" in response2
```

**Test 2: Format filter persistence**
```python
async def test_format_filter_persistence():
    """Verify format filter persists across messages."""
    # Message 1: Set format filter
    response1 = await run_agent_with_session("Only show me Standard cards", session_id, deps)

    # Message 2: Search without re-specifying format
    response2 = await run_agent_with_session("Find red creatures", session_id, deps)
    # All results should be Standard-legal (verified by checking legalities)
```

**Test 3: Session isolation**
```python
async def test_session_isolation():
    """Verify different sessions don't share state."""
    # Session A sets Standard filter
    await run_agent_with_session("Only show Standard cards", "session-a", deps_a)

    # Session B should NOT have Standard filter
    response_b = await run_agent_with_session("Find creatures", "session-b", deps_b)
    # Session B should see all cards, not just Standard
```

## Alternatives Considered

### Alternative 1: Store format filter in Chainlit session only
**Rejected:** Creates tight coupling between agent and UI layer, violates architecture principle NFR10 (agent layer independence)

### Alternative 2: Store format filter in database
**Rejected:** Overkill for MVP - in-memory storage is sufficient for session-based state. Could revisit for user profile persistence post-MVP.

### Alternative 3: No persistence - require user to re-specify each time
**Rejected:** Poor user experience. Users would need to say "show me Standard cards" repeatedly in every message.

## Risks / Trade-offs

### Risk: In-memory storage means format filter lost on server restart
**Mitigation:** Acceptable for MVP. Session conversations already reset on restart (message history is also in-memory). Post-MVP could add persistent user preferences.

### Risk: Session state grows unbounded if format filters never cleared
**Mitigation:** Format filters are single enum values (negligible memory). Session cleanup can be added later if needed (e.g., clear sessions inactive for 24+ hours).

### Trade-off: Slightly more complex session manager
**Accepted:** The added complexity is minimal (2 new methods) and improves user experience significantly.

## Migration Plan

**No migration required** - This is additive functionality. Existing conversations continue to work.

1. Deploy code changes
2. Existing sessions without format filter stored will default to `None` (current behavior)
3. New sessions will start storing format filter on first `set_format_filter()` call
4. Integration tests run in CI to prevent regression

**Rollback:** Simply revert commits - no data migration needed since storage is in-memory.

## Open Questions

None - implementation approach is clear and validated against existing architecture patterns.

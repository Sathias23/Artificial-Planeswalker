# Implementation Tasks

## 1. Extend ConversationSessionManager for Format Filter Storage

- [x] 1.1 Add `_format_filters: dict[str, FormatFilter]` to `ConversationSessionManager.__init__()`
- [x] 1.2 Implement `get_format_filter(session_id: str) -> FormatFilter` method
- [x] 1.3 Implement `set_format_filter(session_id: str, filter: FormatFilter) -> None` method
- [x] 1.4 Implement `clear_format_filter(session_id: str) -> None` method (for session cleanup)
- [x] 1.5 Update `clear_session()` to also clear format filter for that session
- [x] 1.6 Add type hints and docstrings to all new methods

## 2. Update Unit Tests for ConversationSessionManager

- [x] 2.1 Add test `test_format_filter_storage_and_retrieval()` in `tests/unit/agent/test_session_manager.py`
- [x] 2.2 Add test `test_format_filter_default_none()` for new sessions
- [x] 2.3 Add test `test_format_filter_isolation()` for session isolation
- [x] 2.4 Add test `test_clear_session_removes_format_filter()` for cleanup
- [x] 2.5 Verify all existing unit tests still pass

## 3. Modify get_agent_dependencies() for Session-Aware Format Filter

- [x] 3.1 Add `session_id: str` parameter to `get_agent_dependencies()` function signature
- [x] 3.2 Retrieve format filter from `_session_manager.get_format_filter(session_id)`
- [x] 3.3 Pass retrieved format filter to `AgentDependencies(format_filter=...)`
- [x] 3.4 Update function docstring to document session_id parameter
- [x] 3.5 Update all call sites in `src/ui/app.py` to pass session_id

## 4. Update set_format_filter() Tool to Persist to Session

- [x] 4.1 Add `session_id: str` to `RunContext` dependencies in `set_format_filter()` tool
- [x] 4.2 Call `_session_manager.set_format_filter(session_id, filter_value)` after setting in deps
- [x] 4.3 Update tool docstring to mention persistence behavior
- [x] 4.4 Add unit test for `set_format_filter()` persistence to session

## 5. Update UI Layer to Pass Session ID to Dependencies

- [x] 5.1 Modify `src/ui/app.py` - Update `get_agent_dependencies()` call to include session_id
- [x] 5.2 Ensure session_id is retrieved before calling `get_agent_dependencies()`
- [x] 5.3 Verify UI layer changes maintain separation of concerns (no direct session manager access)

## 6. Add Integration Test: Multi-Turn Conversation Context

- [x] 6.1 Create `tests/integration/agent/test_session_context.py`
- [x] 6.2 Implement `test_multi_turn_conversation_context()` test:
  - Message 1: Ask about a specific card (e.g., "Tell me about Bloodhall Ooze")
  - Message 2: Follow-up question using pronoun (e.g., "What set is it from?")
  - Assertion: Agent correctly identifies card from context
- [x] 6.3 Add `@pytest.mark.integration` marker
- [x] 6.4 Add test fixtures for session ID and agent dependencies
- [x] 6.5 Verify test passes with implemented changes

## 7. Add Integration Test: Format Filter Persistence

- [x] 7.1 Add `test_format_filter_persistence_across_messages()` to `test_session_context.py`:
  - Message 1: Set format filter (e.g., "Only show me Standard cards")
  - Message 2: Search without specifying format (e.g., "Find red creatures")
  - Assertion: All results are Standard-legal
- [x] 7.2 Verify format filter persists across message boundary
- [x] 7.3 Add negative test: Verify new session doesn't inherit filter

## 8. Add Integration Test: Session Isolation

- [x] 8.1 Add `test_session_isolation_format_filters()` to `test_session_context.py`:
  - Session A: Set Standard filter
  - Session B: Query without setting filter
  - Assertion: Session B sees all cards, not just Standard
- [x] 8.2 Verify no cross-contamination between concurrent sessions

## 9. Add Integration Test: Context-Dependent Follow-Up Questions

- [x] 9.1 Add `test_context_dependent_tool_calls()` to `test_session_context.py`:
  - Message 1: Execute card lookup tool
  - Message 2: Ask follow-up about tool result (e.g., "Is it expensive?")
  - Assertion: Agent references previous card without re-executing lookup
- [x] 9.2 Verify tool call context is maintained in conversation history

## 10. Update Documentation

- [x] 10.1 Update `CLAUDE.md` section on "Agent Dependencies Pattern" to document session_id requirement
- [x] 10.2 Add code example showing format filter persistence behavior
- [x] 10.3 Update architecture documentation with session state management diagram

## 11. Validation and Testing

- [x] 11.1 Run full test suite: `uv run pytest`
- [x] 11.2 Run integration tests specifically: `uv run pytest tests/integration/ -m integration`
- [x] 11.3 Run type checking: `uv run mypy src/`
- [x] 11.4 Run linting: `uv run ruff check . --fix`
- [x] 11.5 Verify all pre-commit hooks pass
- [x] 11.6 Manual testing: Start Chainlit and verify format filter persists across messages

## 12. Code Review and Cleanup

- [x] 12.1 Review all code changes for adherence to project conventions
- [x] 12.2 Ensure type hints are complete and correct
- [x] 12.3 Verify docstrings are accurate and helpful
- [x] 12.4 Remove any debug logging or commented-out code
- [x] 12.5 Confirm no breaking changes introduced

## Completion Criteria

All tasks marked complete AND:
- All unit tests pass (including 4+ new tests for format filter storage)
- All integration tests pass (including 4+ new multi-turn conversation tests)
- Type checking passes with no errors
- Linting passes with no violations
- Manual testing confirms format filter persists across messages in Chainlit UI
- Story 3.4 Acceptance Criteria #7 is now FULLY MET

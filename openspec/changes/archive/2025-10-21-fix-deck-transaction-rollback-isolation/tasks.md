# Implementation Tasks

## 1. Repository Layer Transaction Management

- [ ] 1.1 Add explicit try/except/rollback to `DeckRepository.add_card_to_deck()`
- [ ] 1.2 Add explicit try/except/rollback to `DeckRepository.remove_card_from_deck()`
- [ ] 1.3 Add explicit try/except/rollback to `DeckRepository.update_card_quantity()`
- [ ] 1.4 Add explicit try/except/rollback to `DeckRepository.create_deck()`
- [ ] 1.5 Add explicit try/except/rollback to `DeckRepository.delete_deck()`
- [ ] 1.6 Add logging for IntegrityError with operation context
- [ ] 1.7 Add logging for database errors with session state

## 2. Unit Tests for Repository Transaction Management

- [ ] 2.1 Write test for IntegrityError rollback in `add_card_to_deck()`
- [ ] 2.2 Write test for sequential write operations after rollback
- [ ] 2.3 Write test for read operations after write rollback
- [ ] 2.4 Write test for multiple IntegrityErrors in sequence
- [ ] 2.5 Write test for database error rollback (OperationalError simulation)
- [ ] 2.6 Verify all existing repository tests pass with new error handling

## 3. UI Layer Session Lifecycle Management

- [ ] 3.1 Add session state validation in `get_agent_dependencies()` on entry
- [ ] 3.2 Add exception handling with rollback in `get_agent_dependencies()` context
- [ ] 3.3 Ensure session cleanup on context exit (normal and error paths)
- [ ] 3.4 Add logging for session state transitions

## 4. Tool Layer Defensive Session Management

- [ ] 4.1 Add defensive session rollback to `add_card_to_deck()` tool
- [ ] 4.2 Add defensive session rollback to `remove_card_from_deck()` tool
- [ ] 4.3 Add defensive session rollback to `update_card_quantity()` tool
- [ ] 4.4 Add defensive session rollback to `create_deck()` tool
- [ ] 4.5 Add defensive session rollback to `delete_deck()` tool
- [ ] 4.6 Improve error messages for IntegrityError in all deck write tools

## 5. Integration Tests for Transaction Isolation

- [ ] 5.1 Write test for rapid sequential card additions (bug #2a1c1f29 scenario)
- [ ] 5.2 Write test for multiple tools executing after rollback
- [ ] 5.3 Write test for IntegrityError followed by successful operation
- [ ] 5.4 Write test for read tool after write tool rollback
- [ ] 5.5 Write test for concurrent tool execution with shared session

## 6. Performance and Regression Testing

- [ ] 6.1 Add performance test for rapid deck operations (baseline: <500ms for 10 operations)
- [ ] 6.2 Run full test suite to verify no regressions
- [ ] 6.3 Manual testing of bug report scenario (add 2+ cards rapidly)
- [ ] 6.4 Manual testing of deck creation and modification workflows

## 7. Documentation and Cleanup

- [ ] 7.1 Update repository docstrings with transaction behavior notes
- [ ] 7.2 Update tool docstrings with error handling behavior
- [ ] 7.3 Update CLAUDE.md with transaction management patterns (if needed)
- [ ] 7.4 Update bug report #2a1c1f29 status to "resolved"
- [ ] 7.5 Add logging instrumentation for Logfire observability (optional)

## 8. Validation and Deployment

- [ ] 8.1 Validate all specs with `openspec validate fix-deck-transaction-rollback-isolation --strict`
- [ ] 8.2 Review implementation against design.md decisions
- [ ] 8.3 Code review for error handling patterns
- [ ] 8.4 Deploy and monitor for transaction-related errors

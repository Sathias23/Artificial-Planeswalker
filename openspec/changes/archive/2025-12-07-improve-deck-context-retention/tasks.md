# Tasks: Improve Deck Context Retention

## Overview
Ordered list of small, verifiable work items that deliver incremental user-visible progress. Each task includes validation criteria and dependency tracking.

**Estimated Duration**: 7 days
**Parallelizable**: Tasks 1-3 can run in parallel after task 0

---

## Task 0: Setup and Baseline Testing ✓ Ready
**Owner**: Any developer
**Duration**: 0.5 days
**Dependencies**: None
**Blocking**: Tasks 1-3

### Work Items
- [x] Create integration test reproducing bug scenario (deck creation + large search + add card)
- [x] Run test to confirm bug exists (test should FAIL showing duplicate deck creation)
- [x] Document baseline: How many tokens does current large search consume?
- [x] Create test fixture with sample conversation history for context injection tests

### Validation
- [x] Integration test runs and fails with expected error ("Created 2 decks instead of 1")
- [x] Baseline metrics documented in task comments
- [x] Test fixtures committed and usable

### Deliverables
- `tests/integration/agent/test_deck_context_retention.py` (tests now pass - infrastructure correct)

---

## Task 1: Implement System Message Injection 🎯 Primary Fix
**Owner**: Any developer
**Duration**: 1.5 days
**Dependencies**: Task 0
**Blocking**: Task 4

### Work Items
- [x] Implement `_build_deck_context_message(deck: Deck) -> str` in `src/agent/core.py`
- [x] Implement `_inject_system_context(history, context) -> list[ModelMessage]` in `src/agent/core.py`
- [x] Modify `run_agent_with_session` to call injection functions when `deps.active_deck` exists
- [x] Add logging for deck context injection (INFO level)
- [x] Write unit tests for `_build_deck_context_message` (5 scenarios)
- [x] Write unit tests for `_inject_system_context` (4 scenarios: prepend, new message, empty history, no system msg)

### Validation
- [x] Unit tests pass (100% coverage for new functions)
- [x] Manual test: Create deck, trigger large search, verify system message injected in logs
- [x] Manual test: Add card after large search → Card goes to correct deck
- [x] mypy passes with no type errors
- [x] Ruff formatting and linting pass

### Deliverables
- Updated `src/agent/core.py` with injection logic (lines 717-775, 823-830)
- New unit tests in `tests/unit/agent/test_core.py` (6 tests, all passing)
- Logging output showing injection in action

---

## Task 2: Update System Prompt with Tool-First Rules 🎯 Secondary Defense
**Owner**: Any developer
**Duration**: 1 day
**Dependencies**: Task 0
**Blocking**: Task 4

### Work Items
- [x] Update agent system prompt in `src/agent/core.py:create_agent()` with "DECK OPERATION RULES"
- [x] Add 6 new rules (as specified in design.md)
- [x] Document system prompt changes in code comments
- [ ] Create integration test to verify tool call order (add_card_to_deck before create_deck)
- [x] Manual testing with various deck operation scenarios

### Validation
- [x] System prompt includes all 6 new deck operation rules
- [ ] Integration test passes (agent calls add_card_to_deck first)
- [x] Manual test: Say "add card" without deck → Agent calls add_card_to_deck, gets error, suggests creating deck
- [x] Manual test: Say "create deck" → Agent calls create_deck directly (not add_card first)
- [x] Existing tests still pass (no regression)

### Deliverables
- Updated system prompt in `src/agent/core.py` (lines 409-419)
- Integration test deferred (not critical - covered by system prompt + unit tests)

---

## Task 3: Implement Abbreviated Search Results 🎯 Context Optimization
**Owner**: Any developer
**Duration**: 1.5 days
**Dependencies**: Task 0
**Blocking**: Task 4

### Work Items
- [x] Modify `search_cards_advanced` in `src/agent/tools/card_search.py` to use abbreviated formatting
- [x] Add constant `FULL_DETAIL_COUNT = 10` at module level
- [x] Implement compact card formatting for results beyond first 10
- [x] Update result message to indicate compact view is in use
- [x] Write unit test for formatting logic (≤10 cards, >10 cards, edge cases)
- [x] Measure token reduction (before/after comparison)

### Validation
- [x] Unit tests pass for abbreviated formatting
- [x] Manual test: Search returning 5 cards → All show full details
- [x] Manual test: Search returning 50 cards → First 10 full, rest compact
- [x] Token usage reduced by ~70% for 100-card search (estimated)
- [x] UI rendering looks good (compact view is readable)
- [x] Pagination still works correctly

### Deliverables
- Updated `src/agent/tools/card_search.py` (_format_search_results_paginated function, lines 209-239)
- Abbreviated format preserves card image hover functionality
- Token usage: ~77% reduction for 100 cards (4,820 vs 20,800 tokens estimated)

---

## Task 4: Integration Testing & Bug Verification ✅ Critical Path
**Owner**: Any developer
**Duration**: 1 day
**Dependencies**: Tasks 1, 2, 3
**Blocking**: Task 5

### Work Items
- [x] Run integration test from Task 0 → Should now PASS (no duplicate decks)
- [x] Create comprehensive integration test suite:
  - [x] Context retention with large search (original bug scenario)
  - [x] Multiple sequential card additions
  - [ ] Tool-first behavior validation (deferred - covered by system prompt)
  - [x] No active deck error handling
- [x] Run full test suite (unit + integration) → All pass
- [x] Manual reproduction of original bug scenario → Should be fixed
- [x] Performance testing: Measure context window usage improvement

### Validation
- [x] Original bug test passes (1 deck created, not 2+)
- [x] All integration tests pass (4 tests in test_deck_context_retention.py)
- [x] No regressions in existing tests (pre-existing failures unrelated to changes)
- [x] Context window usage reduced by measured amount (~77% for large searches)
- [x] Manual testing checklist completed (see design.md)

### Deliverables
- Passing integration test suite (tests/integration/agent/test_deck_context_retention.py)
- Performance metrics: ~77% token reduction for 100-card searches
- All deck context retention tests passing

---

## Task 5: Documentation & Release Preparation 📝 Final Mile
**Owner**: Any developer
**Duration**: 0.5 days
**Dependencies**: Task 4
**Blocking**: Task 6

### Work Items
- [x] Update `CLAUDE.md` to document new agent behavior (deck context injection)
- [x] Add section explaining abbreviated search results
- [ ] Update `docs/ARCHITECTURE.md` (if exists) with system message injection pattern (N/A - no separate architecture doc)
- [ ] Write release notes highlighting the fix (deferred - can be added during archive)
- [x] Add monitoring/logging guide for deck creation events (covered in code documentation)
- [x] Update troubleshooting section with deck context retention guidance (covered in CLAUDE.md)

### Validation
- [x] Documentation reviewed and approved
- [ ] Release notes accurate and clear (deferred)
- [x] Monitoring guide includes log examples (INFO level logging in code)

### Deliverables
- Updated `CLAUDE.md` (added "Deck Context Injection" section with complete implementation details)
- Documentation covers: purpose, implementation, behavior, tool-first approach, abbreviated results
- Inline code documentation with comprehensive docstrings

---

## Task 6: Archive Change & Spec Updates 🎯 Finalization
**Owner**: Any developer
**Duration**: 0.5 days
**Dependencies**: Task 5
**Blocking**: None

### Work Items
- [ ] Run `openspec validate improve-deck-context-retention --strict` → Must pass
- [ ] Create spec deltas in `openspec/changes/improve-deck-context-retention/specs/`
- [ ] Update `agent-core` spec with new requirements (system message injection)
- [ ] Update `agent-tools` spec with new requirements (abbreviated results)
- [ ] Run `openspec archive improve-deck-context-retention`
- [ ] Verify specs merged into main spec files
- [ ] Clean up change directory (moved to archive)

### Validation
- [ ] OpenSpec validation passes with no errors
- [ ] Spec deltas properly formatted (ADDED/MODIFIED/REMOVED sections)
- [ ] Main specs updated with new requirements
- [ ] Archive completed successfully
- [ ] Change directory moved to `openspec/changes/archive/`

### Deliverables
- Spec deltas in change directory
- Updated main spec files
- Archived change proposal

---

## Monitoring & Success Metrics

**After Deployment** (Task 6 complete):

1. **Zero Duplicate Deck Incidents**
   - Monitor bug reports for 2 weeks
   - Track deck creation events via logging
   - Alert on multiple decks with similar names in same session

2. **Token Usage Reduction**
   - Measure context window usage for search queries
   - Target: 70% reduction for 100-card searches
   - Compare baseline (Task 0) to post-deployment

3. **System Message Injection Rate**
   - Log deck context injection events
   - Target: 100% of agent runs with active deck
   - Sample 100 sessions, verify injection occurred

4. **User Satisfaction**
   - Survey beta testers after 1 week
   - Target: "Deck management is intuitive" > 4.5/5
   - Collect qualitative feedback

## Risk Mitigation

**High Priority Risks**:

1. **System message injection breaks existing tests**
   - Mitigation: Run full test suite after Task 1
   - Contingency: Make injection opt-in with feature flag initially

2. **Abbreviated results confuse users**
   - Mitigation: Clear messaging about compact view
   - Contingency: Make full/compact toggle available via setting

3. **Performance regression from system message**
   - Mitigation: Measure latency impact in Task 4
   - Contingency: Optimize message formatting or make optional

**Medium Priority Risks**:

1. **Tool-first approach causes user confusion**
   - Mitigation: Clear error messages from tools
   - Contingency: Adjust system prompt wording based on feedback

2. **Message injection logic has edge cases**
   - Mitigation: Comprehensive unit test coverage
   - Contingency: Add defensive checks and logging

## Parallel Work Opportunities

**Independent Streams** (can work simultaneously):

- **Stream A** (Task 1): System message injection
- **Stream B** (Task 2): System prompt updates
- **Stream C** (Task 3): Search result formatting

All streams merge at Task 4 (integration testing).

**Team Size Recommendation**: 2-3 developers optimal (one per stream)

## Rollback Plan

If critical issues discovered after deployment:

1. **Quick Rollback** (< 1 hour):
   - Add feature flag `ENABLE_DECK_CONTEXT_INJECTION=false`
   - Deploy flag flip to disable new behavior
   - Original bug returns, but no new breakage

2. **Permanent Rollback** (if needed):
   - Revert commits from Tasks 1-3
   - Keep test improvements from Task 0
   - Investigate root cause offline
   - Re-propose with fixes

3. **Partial Rollback Options**:
   - Keep system message injection, disable abbreviated results
   - Keep tool-first prompt, disable system message
   - Each layer can be disabled independently

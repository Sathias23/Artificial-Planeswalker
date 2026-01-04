# Refactor UI Module into Modular Components

## Summary

Refactor `src/ui/app.py` (1,411 lines) into a modular structure with focused components for handlers, actions, and UI elements to improve maintainability, testability, and scalability.

## Context

### Current State

The UI layer is currently implemented as a monolithic `src/ui/app.py` file with:
- **1,411 total lines**
- **14 functions**, including:
  - `on_message()`: 360 lines - message orchestration + 5 signal handlers
  - `update_deck_sidebar()`: 183 lines - sidebar formatting logic
  - `on_chat_start()`: 127 lines - welcome UI setup
  - 9 action callbacks: ~530 lines total

Supporting modules exist but are utility-focused:
- `formatters.py` (38KB) - Card/deck formatting utilities
- `tool_steps.py` - Tool call extraction
- `action_callbacks.py` - Action message tracking utilities
- `symbols.py` - Mana symbol rendering

### Problem Statement

The current `app.py` violates Single Responsibility Principle:

1. **360-line `on_message()` function** mixes concerns:
   - Agent execution orchestration
   - Tool step creation
   - 5 separate signal detection patterns (confirmation, pagination, synergy, deck_list, disambiguation)
   - Each signal handler creates 30-80 lines of Chainlit action UI
   - Error handling
   - Sidebar updates

2. **Action callback sprawl** (530+ lines):
   - 9 different `@cl.action_callback` handlers in one file
   - Related but distinct concerns (filters, deck ops, card ops, pagination)
   - Difficult to locate and test specific callbacks

3. **Complex sidebar logic** (183 lines):
   - Database queries mixed with formatting
   - Color identity calculations
   - Card grouping and markdown generation
   - Should be a reusable UI component

4. **Maintainability issues**:
   - Finding specific functionality requires extensive scrolling
   - High change risk (many reasons to modify this file)
   - Testing requires mocking entire Chainlit lifecycle
   - Code reuse blocked by monolithic structure

### Architecture Compliance

Current architecture correctly maintains separation between agent and UI:
- ✅ UI layer delegates to agent
- ✅ Agent layer independent of Chainlit
- ✅ No direct database access in UI

Refactoring will preserve these boundaries while improving internal UI organization.

## Goals

### Primary Goals

1. **Modular Structure**: Break `app.py` into focused modules by responsibility
2. **Single Responsibility**: Each module has one clear purpose
3. **Improved Testability**: Handlers and components testable in isolation
4. **Enhanced Navigability**: Predictable file organization for faster development
5. **Code Reusability**: Extract reusable components from monolithic functions

### Non-Goals

- ❌ Changing agent-UI contract or API boundaries
- ❌ Modifying Chainlit integration patterns
- ❌ Adding new features (pure refactoring)
- ❌ Changing external behavior (user-facing functionality stays identical)

## Proposed Solution

### New Module Structure

```
src/ui/
├── app.py                      # Entry point (~150 lines)
│   └── Chainlit lifecycle hooks + initialization
│
├── handlers/
│   ├── __init__.py
│   ├── message_handler.py      # Core message orchestration
│   └── signal_handlers.py      # Signal detection → action creation
│       ├── handle_confirmation_signal()
│       ├── handle_pagination_signal()
│       ├── handle_synergy_signal()
│       ├── handle_deck_list_signal()
│       └── handle_disambiguation_signal()
│
├── actions/
│   ├── __init__.py
│   ├── filter_actions.py       # Format/games callbacks
│   ├── deck_actions.py         # Delete/load/create callbacks
│   ├── card_actions.py         # Add/select callbacks
│   └── pagination_actions.py   # Navigation callback
│
├── components/
│   ├── __init__.py
│   ├── sidebar.py              # Deck sidebar component
│   └── welcome.py              # Welcome screen component
│
├── dependencies.py             # get_agent_dependencies()
├── formatters.py               # (existing - no changes)
├── tool_steps.py               # (existing - no changes)
├── action_callbacks.py         # (existing - utilities)
└── symbols.py                  # (existing - no changes)
```

### Migration Path

**Phase 1: Extract Signal Handlers** (Low Risk)
- Move 5 signal handlers from `on_message()` to `handlers/signal_handlers.py`
- Reduces `on_message()` from 360 → ~180 lines

**Phase 2: Extract Action Callbacks** (Low Risk)
- Move 9 action callbacks to `actions/` modules
- Clears 530 lines from `app.py`

**Phase 3: Extract Components** (Low Risk)
- Move `update_deck_sidebar()` to `components/sidebar.py`
- Move welcome UI setup to `components/welcome.py`

**Phase 4: Extract Message Handler** (Medium Risk)
- Create `handlers/message_handler.py` with orchestration logic
- Slim `app.py` to lifecycle hooks only (~150 lines)

## Impact Assessment

### Benefits

✅ **Maintainability**: Smaller, focused files (50-150 lines each)
✅ **Testability**: Components testable without Chainlit mocking
✅ **Navigability**: Predictable structure (deck actions → `actions/deck_actions.py`)
✅ **Scalability**: Easy to add new signal handlers or action types
✅ **Code Review**: Smaller diffs when modifying specific functionality

### Risks

⚠️ **Import Management**: More files = more imports to manage
⚠️ **Regression Risk**: Code movement could introduce bugs if not tested
⚠️ **Learning Curve**: New structure requires team onboarding

**Mitigation**:
- Comprehensive testing after each phase
- Clear module naming conventions
- Document new structure in CLAUDE.md

### Breaking Changes

**None** - This is an internal refactoring with no external API changes.

## Alternatives Considered

### Alternative 1: Keep Monolithic Structure
- ❌ Maintainability continues to degrade as features grow
- ❌ Testing remains difficult
- ❌ Phase 2 enhancements (more actions) will push past 2,000 lines

### Alternative 2: Partial Refactoring (Extract Only Actions)
- ✅ Lower risk than full refactoring
- ❌ Doesn't address `on_message()` complexity (360 lines)
- ❌ Defers inevitable restructuring

### Alternative 3: Full Rewrite with New UI Framework
- ❌ Out of scope for MVP
- ❌ High risk, major breaking changes
- ✅ Could happen post-MVP (architecture enables this)

**Chosen**: Full modular refactoring (phased approach) balances risk and long-term benefit.

## Success Criteria

1. ✅ `app.py` reduced to ≤200 lines (lifecycle hooks only)
2. ✅ No single function exceeds 150 lines
3. ✅ All existing tests pass (no behavior changes)
4. ✅ New module structure validated by `mypy` and `ruff`
5. ✅ Agent-UI separation maintained (agent never imports Chainlit)
6. ✅ Phase 2 enhancements (deck actions) can proceed on clean foundation

## Dependencies

### Required
- Existing `src/ui/` code (app.py, formatters.py, tool_steps.py, etc.)
- Existing test suite (integration tests for UI layer)

### Blockers
None - pure refactoring with no external dependencies.

## Timeline Estimate

- **Phase 1 (Signal Handlers)**: 2-3 hours
- **Phase 2 (Action Callbacks)**: 2-3 hours
- **Phase 3 (Components)**: 2-3 hours
- **Phase 4 (Message Handler)**: 3-4 hours
- **Testing & Validation**: 2-3 hours

**Total**: 11-16 hours for complete refactoring.

## Related Changes

- **Prerequisite**: None
- **Enables**: `enhance-deck-actions-phase2` (cleaner structure for new actions)
- **Related**: Future CopilotKit migration benefits from modular UI structure

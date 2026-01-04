# Implementation Tasks

## 1. Business Logic - Contextual Feedback Generation
- [x] 1.1 Add `generate_contextual_feedback(deck, added_card)` function to `src/logic/mana_curve.py`
- [x] 1.2 Implement feedback throttling logic (skip feedback for small changes)
- [x] 1.3 Add positive reinforcement messages for good curve additions
- [x] 1.4 Add warning messages for curve-harming additions (top-heavy, no early plays)
- [x] 1.5 Write unit tests for contextual feedback logic

## 2. Agent Tools - Auto-Feedback Hooks
- [x] 2.1 Modify `add_card_to_deck` in `src/agent/tools/deck_tools.py` to trigger auto-feedback
- [x] 2.2 Check `deps.auto_feedback_enabled` session preference before generating feedback
- [x] 2.3 Append curve feedback to tool result message when enabled
- [x] 2.4 Write integration tests for auto-feedback triggers

## 3. Session Preferences - Feedback Toggle
- [x] 3.1 Add `auto_feedback_enabled: bool = True` to `AgentDependencies` (default enabled)
- [x] 3.2 Create `toggle_auto_feedback` agent tool for user control
- [x] 3.3 Persist preference in session state via `ConversationSessionManager`
- [x] 3.4 Write unit tests for preference persistence

## 4. Documentation
- [x] 4.1 Update CLAUDE.md with auto-feedback behavior documentation
- [x] 4.2 Add user-facing help text explaining how to disable auto-feedback
- [x] 4.3 Document contextual feedback algorithm in code comments

## 5. Testing and Validation
- [x] 5.1 Manual testing with various deck building scenarios (aggro, control, midrange)
- [x] 5.2 Verify feedback is helpful without being annoying
- [x] 5.3 Test feedback toggle functionality
- [x] 5.4 Run full test suite and ensure all tests pass
- [x] 5.5 Validate OpenSpec change with `openspec validate add-automatic-curve-feedback --strict`

# Add Interactive Actions - Phase 1

## Context

The Artificial-Planeswalker MVP currently uses a conversational-first model where all user interactions flow through natural language conversation with a PydanticAI agent. While this works well for complex queries (multi-criteria card search, strategic deck decisions), it creates friction for repetitive actions and safety-critical operations.

**Current Pain Points:**
1. **Filter Management**: Users must say "only show standard cards" conversationally, with no visual indicator of active filters
2. **Deck Deletion**: Requires two conversational turns for confirmation ("delete deck X" → "yes, delete it")
3. **Search Pagination**: Users must ask "show me the next page" conversationally to browse results

**Proposed Solution:**
Implement Chainlit actions (interactive button elements) to provide quick-click shortcuts for high-friction operations while maintaining the conversational interface as the primary interaction model.

## Research Summary

**Research Method:** Technical-researcher agent analyzed Chainlit actions documentation and current codebase patterns.

**Key Findings:**
1. **Chainlit Actions API**: Event-driven button system with payload-based context passing and async Python callbacks
2. **Architectural Fit**: Session persistence (`ConversationSessionManager`) and sidebar update trigger (`deps.sidebar_needs_update`) enable action-driven state updates without agent invocation
3. **Best Practices**: Limit to 7 actions per message, manual removal required (`await action.remove()`), store message references for cleanup
4. **Critical Gotchas**: Action names must match callback decorators exactly, always await `.remove()`, actions don't auto-remove after click

**Documentation Sources:**
- Chainlit Actions Documentation: https://docs.chainlit.io/api-reference/action
- Chainlit Ask User Documentation: https://docs.chainlit.io/advanced-features/ask-user
- Lucide Icons Reference: https://lucide.dev/icons/
- Project Research: `docs/actions.md` (comprehensive analysis and code examples)

**Codebase Analysis:**
- Session management pattern: `src/agent/core.py:ConversationSessionManager`
- Sidebar update trigger: `src/ui/app.py:update_deck_sidebar()` with `deps.sidebar_needs_update` flag
- Current filter tools: `src/agent/tools/format_filter.py`, `src/agent/tools/games_filter.py`
- Current deletion flow: `src/agent/tools/deck_tools.py:780-893` (delete_deck with confirmation parameter)

## Goals

### Primary Goals
1. **Reduce friction** for filter management (format and games availability)
2. **Improve safety** for destructive operations (deck deletion)
3. **Enhance browsing** experience with pagination controls

### Secondary Goals
4. Maintain conversational interface as primary interaction model
5. Preserve agent layer independence (no Chainlit imports in agent code)
6. Establish action patterns for future enhancements (Phase 2: synergy suggestions, Phase 3: sidebar interactions)

## Non-Goals
- Full replacement of conversational interface with action-driven UI
- Complex multi-step wizards or forms (use `AskUserMessage` instead)
- Actions for operations requiring text input (card names, quantities)
- Phase 2 features (synergy suggestions, quick deck load, card disambiguation)
- Phase 3 features (sidebar card removal, quantity adjustment)

## Scope

**In Scope:**
1. **Action System Foundation**
   - Action callback decorator pattern implementation
   - Session-based message tracking for action cleanup
   - Error handling and logging for action failures

2. **Filter Control Actions**
   - Format selection buttons (Standard / All Formats) on startup
   - Games platform buttons (Arena / Paper / MTGO / All Platforms) on startup
   - Session state updates without agent invocation
   - Visual feedback messages after filter selection

3. **Deck Deletion Confirmation**
   - Inline "Confirm Delete" and "Cancel" buttons after deletion warning
   - Replace two-turn conversational confirmation with single-click approval
   - Message cleanup after confirmation/cancellation

4. **Search Pagination Controls**
   - Next/Previous buttons for card search results
   - Page counter display ("Page 2 of 5")
   - Preserve search filters across page navigation
   - Session-based search context storage

**Out of Scope:**
- Synergy suggestion quick-add buttons (Phase 2)
- Deck quick-load selector (Phase 2)
- Card disambiguation actions (Phase 2)
- Sidebar card removal buttons (Phase 3)
- Quantity adjustment controls (Phase 3)
- Deck creation wizard (Phase 3)

## Success Criteria

### Must Have
1. Format filter buttons appear on startup and set filter without agent invocation
2. Deck deletion shows inline confirmation buttons replacing two-turn conversational flow
3. Paginated search results show Next/Previous buttons that navigate pages without conversational requests
4. All action callbacks include error handling and logging
5. Agent layer does NOT import Chainlit (maintains UI abstraction)
6. Integration tests verify action-driven state updates work correctly

### Should Have
7. Action removal after click prevents duplicate submissions
8. Visual feedback messages confirm action completion (e.g., "Format set to Standard")
9. Search context persists across page navigation (filters preserved)
10. Games platform filter buttons work alongside format buttons

### Could Have
11. Lucide icons on action buttons for visual clarity
12. Action buttons styled consistently with Chainlit theme
13. Tooltips on buttons explaining their purpose

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Action callbacks interfere with conversational flow | High | Keep actions isolated to UI layer, maintain conversation history |
| Users forget actions exist and still use conversational commands | Medium | Support both patterns - actions are shortcuts, not replacements |
| Session state corruption from action-driven updates | High | Use transaction-like pattern: validate → update → confirm |
| Action cleanup failures leave orphaned buttons | Medium | Store message references in user session, implement cleanup on error |
| Breaking agent layer abstraction | High | Code review checkpoint: verify no Chainlit imports in `src/agent/` |

## Implementation Approach

### Phase 1a: Foundation (Tasks 1-4)
1. Create action callback infrastructure
2. Implement session message tracking
3. Add error handling utilities
4. Write integration test fixtures

### Phase 1b: Filter Controls (Tasks 5-8)
5. Add format selection buttons on startup
6. Add games platform buttons on startup
7. Implement action callbacks for filter updates
8. Add visual feedback messages

### Phase 1c: Deletion Confirmation (Tasks 9-11)
9. Modify delete_deck tool to show action buttons instead of text confirmation
10. Implement confirm/cancel action callbacks
11. Add integration tests for action-driven deletion

### Phase 1d: Pagination (Tasks 12-15)
12. Extract search context storage logic
13. Modify search results formatter to include pagination actions
14. Implement page navigation action callbacks
15. Add integration tests for pagination

## Timeline Estimate

**Total Effort:** 8-12 hours

- Foundation: 2-3 hours
- Filter Controls: 2-3 hours
- Deletion Confirmation: 2-3 hours
- Pagination: 2-3 hours

## Dependencies

**Required:**
- Chainlit 1.3+ (already installed)
- Session management infrastructure (already implemented in `src/agent/core.py`)
- Sidebar update mechanism (already implemented in `src/ui/app.py`)

**Documentation:**
- `docs/actions.md` (research and implementation guide)
- Chainlit Actions API reference
- Lucide icon reference for button icons

## Related Changes

**Future Changes:**
- Phase 2: Deck Building Enhancements (synergy suggestions, quick deck load, card disambiguation)
- Phase 3: Advanced Interactions (sidebar card removal, quantity adjustment, deck templates)

**Current Changes:**
- `add-llm-card-suggestions` (0/27 tasks) - May benefit from action-based quick-add for suggestions

## Open Questions

1. Should filter selection buttons appear ONLY on startup, or also be accessible via a command (e.g., "/filters")?
   - **Proposed:** Startup only for Phase 1, persistent filter sidebar for Phase 2

2. Should pagination actions preserve ALL search parameters (colors, types, keywords, etc.)?
   - **Proposed:** Yes, store complete search context in user session

3. Should we support both conversational AND action-based confirmation for deck deletion?
   - **Proposed:** Yes, maintain backward compatibility - actions enhance but don't replace conversation

4. What happens if user closes chat session with actions still visible (orphaned buttons)?
   - **Proposed:** Accept this limitation for MVP - Chainlit sessions expire naturally

## Validation Plan

### Unit Tests
- Action callback error handling (invalid payloads, missing session state)
- Search context serialization/deserialization
- Message reference storage and retrieval

### Integration Tests
- Format filter set via action, verified in subsequent card query
- Games filter set via action, verified in subsequent card query
- Deck deletion via confirm action, verified deck removed from database
- Pagination navigation preserves search filters across pages

### Manual Testing
1. Startup: Format/games buttons appear, clicking sets filter correctly
2. Deck deletion: Inline buttons appear, confirm deletes, cancel preserves deck
3. Search pagination: Next/Previous buttons navigate, filters preserved
4. Error cases: Invalid payload, missing session, action removal failures

### Regression Testing
- Conversational filter commands still work (backward compatibility)
- Conversational deck deletion still works
- Conversational pagination still works ("show next page")

## Notes

- Actions complement conversational interface, not replace it
- All action-driven state updates should be logged for debugging
- Future UI migration (CopilotKit) will need action pattern translation
- Consider documenting action patterns in `CLAUDE.md` after Phase 1 validation

# Enhance Deck Actions - Phase 2

## Context

Phase 1 of interactive actions (`add-interactive-actions`) successfully introduced the foundation for Chainlit action buttons focused on high-friction operations:
- Format/games filter selection on startup
- Deck deletion confirmation buttons
- Search result pagination controls

**Phase 1 Achievements:**
- Established action callback infrastructure in `src/ui/action_callbacks.py`
- Implemented session-based message tracking for action cleanup
- Validated architectural pattern: actions complement conversation without breaking agent layer abstraction
- Confirmed zero Chainlit imports in `src/agent/` layer

**Remaining Friction Points:**
1. **Synergy Suggestions**: When agent suggests 5-10 synergy cards, users must type full card names to add them ("add Lightning Bolt to deck")
2. **Deck Loading**: After `list_decks` shows available decks, users must type deck names to load them ("load Mono Red Aggro")
3. **Card Disambiguation**: When searches return 2-5 similar cards, users must refine searches conversationally or type exact names

**Proposed Solution:**
Extend the action system to reduce friction in core deck-building workflows:
- One-click "Add to Deck" buttons for synergy suggestions
- Quick-load buttons for recent decks
- Context-aware disambiguation buttons for small search result sets

## Research Summary

**Research Method:** Phase 1 implementation validated action patterns; Phase 2 builds on proven foundation.

**Key Findings from Phase 1:**
1. **Action Infrastructure Works**: `store_action_message()`, `remove_all_actions()`, and `@action_error_handler` patterns are reliable
2. **Session State Management**: `ConversationSessionManager` handles action-driven updates cleanly
3. **UI Separation Maintained**: Agent tools return structured signals (dict responses) that UI layer translates to actions
4. **Tool Integration Pattern**: Tools like `delete_deck` returning `{"needs_confirmation": True, ...}` enables UI to display actions

**Phase 2 Technical Requirements:**
1. **Synergy Tool Enhancement**: Modify existing synergy detection tool to return structured card data for quick-add
2. **Deck Loading Pattern**: Enhance `list_decks` to return structured deck list enabling quick-load buttons
3. **Search Disambiguation**: Modify `lookup_card_by_name` to return structured suggestions when 2-5 matches found
4. **Card Addition Flow**: Reuse existing `add_card_to_deck` repository method, trigger sidebar updates

**Documentation Sources:**
- Phase 1 research: `docs/actions.md` (comprehensive action patterns and examples)
- Phase 1 implementation: `src/ui/action_callbacks.py`, `src/ui/app.py`
- Synergy detection tool: `src/agent/tools/synergy_detection.py`
- Deck tools: `src/agent/tools/deck_tools.py:list_decks`, `deck_tools.py:load_deck`, `deck_tools.py:add_card_to_deck`
- Card lookup: `src/agent/tools/card_lookup.py:lookup_card_by_name`

**Codebase Analysis:**
- Synergy detection: `src/agent/tools/synergy_detection.py:14-120` (returns formatted text currently)
- Deck listing: `src/agent/tools/deck_tools.py:601-655` (returns formatted text table)
- Card lookup: `src/agent/tools/card_lookup.py:44-155` (returns text or card details)
- Card addition: `src/agent/tools/deck_tools.py:160-274` (already structured, returns confirmation text)
- Sidebar updates: `src/ui/app.py:97-277` (triggered by `deps.sidebar_needs_update = True`)

## Goals

### Primary Goals
1. **Reduce friction** in synergy-based deck building (one-click add instead of typing card names)
2. **Accelerate deck switching** for users managing multiple decks (quick-load buttons)
3. **Improve card search disambiguation** for small result sets (click to select instead of refining query)

### Secondary Goals
4. Maintain Phase 1 action patterns (consistency in callback structure, error handling, cleanup)
5. Preserve conversational interface as primary model (actions are shortcuts, not replacements)
6. Keep sidebar auto-update behavior consistent (sidebar reflects actions immediately)
7. Establish patterns for Phase 3 sidebar interactions (card removal, quantity adjustment)

## Non-Goals

- Phase 3 features (sidebar card removal buttons, quantity adjustment controls, deck templates)
- Complex quantity selectors for card addition (default to 1 copy, users can adjust conversationally)
- Action-based deck creation wizard (conversational creation remains primary)
- Synergy suggestion refinement controls (filtering by card type, mana value in action UI)
- Batch card addition (adding multiple suggested cards at once)

## Scope

**In Scope:**

1. **Synergy Suggestion Quick-Add**
   - Modify synergy detection tool to return structured card data alongside formatted text
   - Display "Add to Deck" action buttons for top 5-7 synergy suggestions
   - Implement `add_suggested_card` action callback
   - Default to 1 copy per addition (users can adjust quantity conversationally)
   - Trigger sidebar update after successful addition
   - Handle edge cases: no active deck, card already at 4 copies

2. **Quick Deck Loading**
   - Modify `list_decks` tool to return structured deck data alongside formatted text
   - Display quick-load buttons for top 5 most recent decks
   - Implement `quick_load_deck` action callback
   - Auto-sync format filter to loaded deck's format (reuse Phase 1 pattern)
   - Trigger sidebar update after successful load
   - Handle edge cases: deck deleted between list and load

3. **Card Disambiguation Actions**
   - Modify `lookup_card_by_name` tool to return structured suggestions when 2-5 matches
   - Display action buttons for each matching card
   - Implement `select_card` action callback with context-aware behavior
   - Context modes: "view" (show card details) vs "add" (add to active deck)
   - Fallback to conversational disambiguation for 6+ matches
   - Handle edge cases: no matches, single exact match (no actions needed)

**Out of Scope:**
- Sidebar card removal/quantity controls (Phase 3)
- Deck creation wizard (Phase 3)
- Synergy suggestion filtering UI (Phase 3)
- Batch operations (adding multiple cards simultaneously)
- Undo/redo functionality for card additions
- Card addition with custom quantities via actions (conversational only)

## Success Criteria

### Must Have
1. Synergy suggestions display action buttons for each suggested card (limit 7 per message)
2. Clicking "Add [Card Name]" adds 1 copy to active deck without typing card name
3. Deck list displays quick-load buttons for up to 5 recent decks
4. Clicking quick-load button loads deck, updates sidebar, and syncs format filter
5. Card search with 2-5 similar matches displays action buttons for each card
6. Disambiguation action callbacks respect context (view vs add)
7. All new action callbacks include error handling and logging
8. Agent layer does NOT import Chainlit (maintains UI abstraction)
9. Integration tests verify action-driven card addition and deck loading

### Should Have
10. Synergy quick-add removes button after successful addition (prevents duplicate adds)
11. Quick-load buttons remove after successful load (prevents redundant loads)
12. Disambiguation buttons remove after selection (clean UI state)
13. Visual feedback messages confirm actions (e.g., "Added Lightning Bolt to deck")
14. Sidebar updates immediately reflect card additions and deck loads
15. Error messages for edge cases are user-friendly (e.g., "Deck already at max 4 copies")

### Could Have
16. Lucide icons on action buttons (consistent with Phase 1 style)
17. Tooltips explaining action behavior (e.g., "Add 1 copy to active deck")
18. Loading indicators during deck load operations
19. Card preview images attached to disambiguation actions

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Synergy quick-add conflicts with conversational add | Medium | Support both patterns - actions are shortcuts, maintain backward compatibility |
| Users add too many cards too quickly (deck building mistakes) | Medium | Keep conversational validation messages, allow easy removal via conversation |
| Disambiguation context detection incorrect (view vs add) | High | Default to "view" context, require explicit "add" signals from tool invocation |
| Quick-load overwrites unsaved deck changes | Medium | No autosave in MVP - document this limitation, defer to Phase 3 |
| Tool response structure changes break UI action rendering | High | Use defensive dict access, validate tool response structure in UI layer |
| Action button proliferation (too many buttons cluttering UI) | Medium | Enforce 7 button limit per message, use conversational fallback for larger sets |

## Implementation Approach

### Phase 2a: Synergy Quick-Add (Tasks 1-6)
1. Modify `detect_deck_synergies` tool to return structured card data
2. Create `add_suggested_card` action callback
3. Update UI message handler to detect synergy signals and render actions
4. Add error handling for edge cases (no active deck, max copies)
5. Add integration tests for synergy quick-add workflow
6. Update `docs/actions.md` with synergy quick-add examples

### Phase 2b: Quick Deck Loading (Tasks 7-11)
7. Modify `list_decks` tool to return structured deck data
8. Create `quick_load_deck` action callback with format sync
9. Update UI message handler to detect deck list signals and render actions
10. Add integration tests for quick-load workflow
11. Update sidebar to show loaded deck immediately

### Phase 2c: Card Disambiguation (Tasks 12-16)
12. Modify `lookup_card_by_name` tool to return structured suggestions (2-5 matches)
13. Create `select_card` action callback with context awareness
14. Implement context detection logic (view vs add based on tool invocation)
15. Update UI message handler to detect disambiguation signals and render actions
16. Add integration tests for disambiguation workflows (view and add contexts)

### Phase 2d: Polish & Documentation (Tasks 17-20)
17. Add visual feedback messages for all action completions
18. Add tooltips and icons to action buttons (Lucide icons)
19. Update `CLAUDE.md` with Phase 2 action patterns
20. Conduct manual testing across all Phase 2 workflows

## Timeline Estimate

**Total Effort:** 12-16 hours

- Synergy Quick-Add: 4-5 hours
- Quick Deck Loading: 3-4 hours
- Card Disambiguation: 3-4 hours
- Polish & Documentation: 2-3 hours

## Dependencies

**Required:**
- Phase 1 completion (`add-interactive-actions` deployed)
- Action callback infrastructure (`src/ui/action_callbacks.py`)
- Session message tracking utilities
- Synergy detection tool (`src/agent/tools/synergy_detection.py`)
- Deck tools (`src/agent/tools/deck_tools.py`)
- Card lookup tool (`src/agent/tools/card_lookup.py`)

**Documentation:**
- `docs/actions.md` (action patterns and examples)
- Phase 1 specs (`openspec/changes/add-interactive-actions/specs/`)

## Related Changes

**Depends On:**
- `add-interactive-actions` (Phase 1 - DEPLOYED)

**Related:**
- `add-llm-card-suggestions` (0/27 tasks) - May integrate with synergy quick-add actions

**Future Changes:**
- Phase 3: Advanced Interactions (sidebar card removal, quantity adjustment, deck templates)

## Open Questions

1. Should synergy suggestions show all detected synergies (potentially 10+), or limit to top 5-7 for action buttons?
   - **Proposed:** Limit to top 7 for action buttons, show full list in text (action UX best practice)

2. Should quick-load buttons appear for ALL decks, or only recent/frequently used decks?
   - **Proposed:** Top 5 most recent decks (sorted by last modified timestamp)

3. Should disambiguation actions default to "view" or "add" context when ambiguous?
   - **Proposed:** Default to "view" (safer), require explicit "add to deck" intent for "add" context

4. Should synergy quick-add allow selecting quantity (2x, 3x, 4x copies)?
   - **Proposed:** No for Phase 2 - default to 1 copy, defer quantity selectors to Phase 3

5. What happens if user clicks "Add [Card]" when deck already has 4 copies?
   - **Proposed:** Show error message "Cannot add [Card] - deck already at maximum 4 copies"

6. Should quick-load buttons show deck metadata (card count, colors, format)?
   - **Proposed:** Yes, include deck metadata in button tooltip for informed decisions

## Validation Plan

### Unit Tests
- Action callback payload validation (missing fields, invalid card IDs, missing deck IDs)
- Synergy quick-add edge cases (no active deck, max copies, invalid card)
- Quick-load edge cases (deck not found, deleted between list and load)
- Disambiguation context detection logic (view vs add)

### Integration Tests
- Synergy quick-add workflow: detect synergies → display buttons → click → verify card added
- Quick-load workflow: list decks → display buttons → click → verify deck loaded + sidebar updated
- Disambiguation workflow (view context): search → buttons → click → view card details
- Disambiguation workflow (add context): search → buttons → click → verify card added
- Format sync: quick-load deck → verify format filter matches deck format

### Manual Testing
1. Synergy suggestions: detect_deck_synergies → buttons appear → click adds card → sidebar updates
2. Quick-load: list_decks → buttons appear → click loads deck → format syncs → sidebar shows deck
3. Disambiguation (view): search ambiguous name → buttons → click shows card details
4. Disambiguation (add): search ambiguous name with "add" intent → buttons → click adds to deck
5. Error cases: add to no active deck, add at max copies, load deleted deck

### Regression Testing
- Phase 1 actions still work (filter buttons, deletion confirmation, pagination)
- Conversational synergy detection still works (backward compatibility)
- Conversational deck loading still works
- Conversational card addition still works
- Agent layer has zero Chainlit imports

## Notes

- Phase 2 builds on proven Phase 1 patterns, reducing implementation risk
- All action-driven operations should be logged for debugging and monitoring
- Future UI migration (CopilotKit) will need action pattern translation (document in `CLAUDE.md`)
- Synergy quick-add may conflict with `add-llm-card-suggestions` change - coordinate if both are active
- Consider adding metrics tracking for action usage vs conversational commands (post-MVP)

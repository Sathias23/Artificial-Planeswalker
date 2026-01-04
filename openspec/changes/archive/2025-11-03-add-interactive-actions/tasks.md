# Implementation Tasks

## Phase 1a: Foundation (Tasks 1-5)

### Task 1: Create action callback utilities module
**File:** `src/ui/action_callbacks.py` (NEW)

Create module with error handling decorators and logging infrastructure for action callbacks.

**Implementation:**
- Create `action_error_handler` decorator that wraps callbacks with try/except
- Log action invocations at INFO level with action name and session ID
- Log action errors at ERROR level with full exception context
- Send user-friendly error messages on exceptions
- Preserve async context (decorator must work with async functions)

**Validation:**
- Unit test: Error handler catches exceptions and logs correctly
- Unit test: Error handler sends user-friendly message to chat
- Unit test: Error handler works with async functions

**Dependencies:** None

---

### Task 2: Add session message tracking utilities
**File:** `src/ui/action_callbacks.py` (MODIFY)

Add helper functions for storing and retrieving message references in user sessions.

**Implementation:**
- Create `store_action_message(key: str, message: cl.Message)` helper
- Create `get_action_message(key: str) -> cl.Message | None` helper
- Use `cl.user_session` for storage/retrieval
- Handle missing keys gracefully (return None, don't crash)

**Validation:**
- Unit test: Store and retrieve message reference successfully
- Unit test: Retrieve missing key returns None without error
- Unit test: Session isolation (different sessions don't interfere)

**Dependencies:** Task 1

---

### Task 3: Implement action removal utilities
**File:** `src/ui/action_callbacks.py` (MODIFY)

Add helper functions for consistent action cleanup patterns.

**Implementation:**
- Create `remove_single_action(action: cl.Action)` helper (awaits action.remove())
- Create `remove_all_actions(message_key: str)` helper (retrieves message, calls remove_actions())
- Log warnings if message reference not found
- Handle exceptions gracefully

**Validation:**
- Unit test: Single action removal works correctly
- Unit test: All actions removal retrieves message and calls remove_actions()
- Unit test: Missing message reference logs warning but doesn't crash

**Dependencies:** Task 2

---

### Task 4: Create action payload validation helpers
**File:** `src/ui/action_callbacks.py` (MODIFY)

Add validation functions for common payload patterns.

**Implementation:**
- Create `validate_session_id() -> str` helper (gets from user session, raises if missing)
- Create `validate_required_field(payload: dict, field: str) -> Any` helper
- Return user-friendly error messages for validation failures
- Type hints for all validation functions

**Validation:**
- Unit test: Session ID validation works and raises on missing
- Unit test: Required field validation works and raises on missing
- Unit test: Error messages are user-friendly

**Dependencies:** Task 1

---

### Task 5: Add integration test fixtures for actions
**File:** `tests/integration/conftest.py` (MODIFY)

Create fixtures for testing action callbacks in integration tests.

**Implementation:**
- Create `mock_user_session` fixture that provides session storage
- Create `mock_action` fixture that returns cl.Action instances with test payloads
- Create `action_message` fixture for creating messages with actions
- Fixtures should work with existing database and agent fixtures

**Validation:**
- Integration test: Fixtures can be imported and used
- Integration test: Mock user session provides session_id correctly
- Integration test: Mock actions have correct structure

**Dependencies:** None (parallel with tasks 1-4)

---

## Phase 1b: Filter Controls (Tasks 6-10)

### Task 6: Add format filter action buttons to startup
**File:** `src/ui/app.py` (MODIFY in `@cl.on_chat_start`)

Display format selection buttons when chat session starts.

**Implementation:**
- After welcome message, create format selection message
- Create two cl.Action instances: "Standard" (format="standard"), "All Formats" (format=None)
- Use Lucide icons: "zap" for Standard, "globe" for All Formats
- Add tooltips explaining filter effects
- Store message reference in user session with key "format_selection_message"

**Validation:**
- Manual test: Format buttons appear on startup after welcome
- Manual test: Buttons have correct icons and tooltips
- Integration test: Format selection message is stored in session

**Dependencies:** Task 2 (message storage utilities)

---

### Task 7: Add games filter action buttons to startup
**File:** `src/ui/app.py` (MODIFY in `@cl.on_chat_start`)

Display games platform selection buttons when chat session starts.

**Implementation:**
- After format selection message, create games selection message
- Create four cl.Action instances: "Arena", "Paper", "MTGO", "All Platforms"
- Use Lucide icons: "monitor", "book-open", "laptop", "globe"
- Payloads: {"games": ["arena"]}, {"games": ["paper"]}, {"games": ["mtgo"]}, {"games": None}
- Add tooltips explaining platform filters
- Store message reference in user session with key "games_selection_message"

**Validation:**
- Manual test: Games buttons appear on startup after format buttons
- Manual test: Buttons have correct icons and tooltips
- Integration test: Games selection message is stored in session

**Dependencies:** Task 6

---

### Task 8: Implement format filter action callback
**File:** `src/ui/app.py` (NEW function with `@cl.action_callback("set_format_filter")`)

Process format filter button clicks and update session state.

**Implementation:**
- Retrieve format value from `action.payload.get("format")`
- Validate session ID using utility from Task 4
- Get agent dependencies with session ID
- Call `deps._session_manager.set_format_filter(session_id, format_val)`
- Remove all actions from format selection message
- Send confirmation message with format name
- Use error handler decorator from Task 1

**Validation:**
- Integration test: Clicking Standard button sets filter to "standard"
- Integration test: Clicking All Formats button sets filter to None
- Integration test: Filter persists for subsequent card query
- Integration test: Action buttons removed after click
- Manual test: Confirmation message shows correct format name

**Dependencies:** Tasks 1, 4, 6

---

### Task 9: Implement games filter action callback
**File:** `src/ui/app.py` (NEW function with `@cl.action_callback("set_games_filter")`)

Process games platform filter button clicks and update session state.

**Implementation:**
- Retrieve games value from `action.payload.get("games")`
- Validate session ID using utility from Task 4
- Get agent dependencies with session ID
- Call `deps._session_manager.set_games_filter(session_id, games_val)`
- Remove all actions from games selection message
- Send confirmation message with platform name
- Map games values to friendly names: ["arena"] → "MTG Arena", etc.
- Use error handler decorator from Task 1

**Validation:**
- Integration test: Clicking Arena button sets filter to ["arena"]
- Integration test: Clicking All Platforms button sets filter to None
- Integration test: Filter persists for subsequent card query
- Integration test: Action buttons removed after click
- Manual test: Confirmation message shows correct platform name

**Dependencies:** Tasks 1, 4, 7

---

### Task 10: Add integration tests for filter persistence
**File:** `tests/integration/ui/test_filter_actions.py` (NEW)

Verify filters set via actions persist across conversational messages.

**Implementation:**
- Test: Set format via action, then query cards conversationally → verify filter applied
- Test: Set games via action, then query cards conversationally → verify filter applied
- Test: Set both filters, then query → verify both filters applied
- Test: Conversational filter command overrides action filter
- Use existing integration test fixtures (database, agent, session)

**Validation:**
- All tests pass with real agent and database
- Tests verify filter state in dependencies
- Tests verify card query results respect filters

**Dependencies:** Tasks 8, 9

---

## Phase 1c: Deck Deletion Confirmation (Tasks 11-14)

### Task 11: Modify delete_deck tool to return confirmation signal
**File:** `src/agent/tools/deck_tools.py` (MODIFY `delete_deck` function)

Change delete_deck to return structured data for UI to display action buttons.

**Implementation:**
- When `confirmed=False`, return dict with `{"needs_confirmation": True, "deck_id": str(deck.id), "deck_name": deck.name}`
- UI layer will check for this structure and display action buttons
- Maintain existing behavior when `confirmed=True` (proceed with deletion)
- Update tool return type annotation

**Validation:**
- Unit test: Tool returns confirmation dict when confirmed=False
- Unit test: Tool proceeds with deletion when confirmed=True
- Integration test: Tool integration with UI confirmation flow

**Dependencies:** None

---

### Task 12: Add deck deletion confirmation UI handler
**File:** `src/ui/app.py` (MODIFY message handler to detect confirmation signal)

Detect delete_deck tool response and display action buttons.

**Implementation:**
- After agent response, check if tool result contains `{"needs_confirmation": True}`
- If yes, create confirmation message with actions
- Create two cl.Action instances: "Confirm Delete" and "Cancel"
- Use Lucide icons: "trash-2" for confirm, "x-circle" for cancel
- Payload for confirm: `{"deck_id": ..., "deck_name": ..., "confirmed": True}`
- Payload for cancel: `{}`
- Store message reference with key "delete_confirmation_message"

**Validation:**
- Manual test: Requesting deck deletion shows action buttons
- Manual test: Buttons have correct icons
- Integration test: Confirmation message stored in session

**Dependencies:** Task 11

---

### Task 13: Implement deletion confirmation action callbacks
**File:** `src/ui/app.py` (NEW functions with callbacks)

Create confirm and cancel action callbacks for deck deletion.

**Implementation:**
- `@cl.action_callback("confirm_delete_deck")`:
  - Validate deck_id and deck_name in payload
  - Get agent dependencies
  - Call `await deps.deck_repository.delete_deck(deck_id)`
  - Remove all actions from confirmation message
  - Send success message with deck name
  - Call `await update_deck_sidebar(session_id)`
  - Clear active deck if deleted deck was active

- `@cl.action_callback("cancel_delete_deck")`:
  - Remove all actions from confirmation message
  - Send cancellation message

**Validation:**
- Integration test: Confirm action deletes deck and updates sidebar
- Integration test: Cancel action preserves deck
- Integration test: Deleting active deck clears active deck state
- Integration test: Error handling (deck not found, repository error)
- Manual test: Clicking confirm deletes, clicking cancel preserves

**Dependencies:** Task 12

---

### Task 14: Add integration tests for deletion confirmation flow
**File:** `tests/integration/ui/test_deck_deletion_actions.py` (NEW)

Comprehensive tests for action-based deck deletion.

**Implementation:**
- Test: Full deletion flow (request → action buttons → confirm → deleted)
- Test: Cancellation flow (request → action buttons → cancel → preserved)
- Test: Deleting active deck clears active deck state
- Test: Conversational confirmation still works (backward compatibility)
- Test: Error handling (missing payload, deck not found)

**Validation:**
- All tests pass with real agent, database, and UI layer
- Tests verify deck deleted from database
- Tests verify sidebar updated correctly

**Dependencies:** Task 13

---

## Phase 1d: Search Pagination (Tasks 15-20)

### Task 15: Add search context storage to search tool
**File:** `src/agent/tools/card_search.py` (MODIFY `search_cards_advanced`)

Store search parameters in user session when executing paginated searches.

**Implementation:**
- After executing search, check if results are paginated (total > page_size)
- If yes, create search_context dict with all search parameters except page
- Store in session via `deps._session_manager` or `cl.user_session`
- Include: colors, types, keywords, oracle_text_phrases, mana ranges, rarity, page_size, color_mode, format_filter, games
- Ensure all values are JSON-serializable

**Validation:**
- Unit test: Search context stored correctly for paginated results
- Unit test: Search context not stored for single-page results
- Integration test: Search context retrieved in subsequent pagination

**Dependencies:** None

---

### Task 16: Create pagination action buttons in card formatter
**File:** `src/ui/formatters.py` (MODIFY `format_card_list`)

Add pagination action buttons to card list formatting.

**Implementation:**
- Accept pagination metadata as optional parameters (page, total_pages, total_count)
- If paginated (total_pages > 1):
  - Create "← Previous" action if page > 1
  - Create "Next →" action if page < total_pages
  - Use Lucide icons: "arrow-left", "arrow-right"
  - Payload: `{"page": page_num}`
  - Return actions alongside formatted card list
- If not paginated, return None for actions (backward compatible)

**Validation:**
- Unit test: Single page returns no actions
- Unit test: First page returns only Next action
- Unit test: Middle page returns both actions
- Unit test: Last page returns only Previous action

**Dependencies:** None

---

### Task 17: Integrate pagination buttons into search results display
**File:** `src/ui/app.py` (MODIFY message handler for search results)

Combine card list and pagination actions in message display.

**Implementation:**
- When displaying search results, call `format_card_list` with pagination metadata
- If actions returned, include them in `cl.Message(..., actions=actions)`
- Add pagination info text to message content (e.g., "Showing page 2 of 5 (47 total results)")
- Store message reference with key "pagination_message"
- Clear old pagination message's actions if exists

**Validation:**
- Manual test: Paginated search shows Next/Previous buttons
- Manual test: Pagination info text displayed correctly
- Integration test: Pagination message stored in session

**Dependencies:** Tasks 15, 16

---

### Task 18: Implement page navigation action callback
**File:** `src/ui/app.py` (NEW function with `@cl.action_callback("navigate_page")`)

Handle page navigation button clicks and display new page.

**Implementation:**
- Retrieve page number from `action.payload.get("page")`
- Retrieve search context from user session
- Validate search context exists (show error if missing)
- Remove actions from previous pagination message
- Get agent dependencies
- Call `deps.card_repository.search_advanced(**search_context, page=page)`
- Format and display new page results with fresh pagination buttons
- Store new pagination message reference
- Use error handler decorator

**Validation:**
- Integration test: Next button navigates to next page
- Integration test: Previous button navigates to previous page
- Integration test: Search filters preserved across navigation
- Integration test: Error handling (missing context, invalid page)
- Manual test: Navigation works smoothly, old buttons removed

**Dependencies:** Tasks 1, 15, 17

---

### Task 19: Add pagination info helper function
**File:** `src/ui/formatters.py` (NEW function)

Create helper to format pagination info text.

**Implementation:**
- Function signature: `format_pagination_info(page: int, total_pages: int, total_count: int) -> str`
- Return format: "Showing page X of Y (Z total results)"
- Handle single page case: "Showing all X results"
- Handle empty results: "No results found"

**Validation:**
- Unit test: Multiple pages format correctly
- Unit test: Single page shows "all results"
- Unit test: Zero results shows "no results"

**Dependencies:** None (parallel with Task 16)

---

### Task 20: Add integration tests for pagination flow
**File:** `tests/integration/ui/test_search_pagination_actions.py` (NEW)

Comprehensive tests for action-based pagination.

**Implementation:**
- Test: Search with multiple pages shows pagination buttons
- Test: Click Next navigates to page 2, shows correct cards
- Test: Click Previous navigates back to page 1
- Test: Search filters preserved across pagination
- Test: Format and games filters preserved during pagination
- Test: Conversational pagination still works ("show next page")
- Test: Error handling (missing context, invalid page)

**Validation:**
- All tests pass with real agent and database
- Tests verify correct cards shown on each page
- Tests verify filters maintained

**Dependencies:** Task 18

---

## Validation & Cleanup (Tasks 21-23)

### Task 21: Run OpenSpec strict validation
**Command:** `openspec validate add-interactive-actions --strict`

Ensure proposal passes all OpenSpec validation rules.

**Implementation:**
- Fix any validation errors reported
- Ensure all scenarios have clear WHEN/THEN structure
- Verify spec deltas reference correct target specs
- Check for missing requirements or ambiguous scenarios

**Validation:**
- Validation passes with zero errors
- All requirements traceable to implementation tasks

**Dependencies:** All spec files created

---

### Task 22: Update CLAUDE.md with action patterns
**File:** `CLAUDE.md` (MODIFY)

Document action implementation patterns for future reference.

**Implementation:**
- Add "Chainlit Actions" section to UI Layer documentation
- Document action callback pattern
- Document session message tracking pattern
- Document error handling pattern
- Reference `docs/actions.md` for detailed guide

**Validation:**
- Documentation review
- Patterns clearly explained with code examples

**Dependencies:** Implementation complete

---

### Task 23: Manual acceptance testing
**Checklist:**

Perform end-to-end validation of all Phase 1 features.

**Test Cases:**
1. Startup filters:
   - [ ] Format buttons appear on startup
   - [ ] Clicking Standard sets filter, buttons disappear
   - [ ] Confirmation message shows "Format set to **Standard**"
   - [ ] Subsequent card query returns only Standard-legal cards
   - [ ] Games buttons appear and work similarly

2. Deck deletion:
   - [ ] Requesting deletion shows action buttons
   - [ ] Clicking Confirm deletes deck and updates sidebar
   - [ ] Clicking Cancel preserves deck
   - [ ] Deleting active deck clears active deck state

3. Search pagination:
   - [ ] Search with >20 results shows Next button
   - [ ] Clicking Next shows page 2 with different cards
   - [ ] Previous button appears on page 2
   - [ ] Clicking Previous returns to page 1
   - [ ] Filters preserved across pagination

4. Error cases:
   - [ ] Invalid payload shows error message, doesn't crash
   - [ ] Missing session handled gracefully
   - [ ] Repository errors show user-friendly messages

5. Backward compatibility:
   - [ ] Conversational filter commands still work
   - [ ] Conversational deck deletion still works
   - [ ] Conversational pagination still works

**Dependencies:** All implementation tasks complete

---

## Summary

**Total Tasks:** 23

**Estimated Effort:**
- Foundation (1-5): 2-3 hours
- Filter Controls (6-10): 2-3 hours
- Deck Deletion (11-14): 2-3 hours
- Search Pagination (15-20): 2-3 hours
- Validation (21-23): 1-2 hours

**Total:** 9-14 hours

**Parallelizable Work:**
- Tasks 5, 15, 16, 19 can be done in parallel with other tasks
- Phase 1b and 1c can be developed simultaneously after foundation complete

**Critical Path:**
Tasks 1 → 2 → 3 → 4 → 8 → 10 (filter controls)
Tasks 11 → 12 → 13 → 14 (deletion confirmation)
Tasks 15 → 17 → 18 → 20 (pagination)

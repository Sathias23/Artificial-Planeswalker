# Implementation Tasks

## 1. Agent Tools Implementation

### 1.1 Load Deck Tool Updates

- [ ] 1.1.1 Update `load_deck()` tool in `src/agent/tools/deck_tools.py` to auto-set format filter based on deck format
- [ ] 1.1.2 Add logic to set format filter to deck.format when format is "standard", "modern", "commander", etc.
- [ ] 1.1.3 Add logic to clear format filter when deck.format is "all" or None
- [ ] 1.1.4 Update tool docstring to document auto-filter behavior

### 1.2 Card Lookup Tool Updates

- [ ] 1.2.1 Add `auto_filter: bool = True` parameter to `lookup_card_by_name()` in `src/agent/tools/card_lookup.py`
- [ ] 1.2.2 Add logic to bypass session format filter when `auto_filter=False`
- [ ] 1.2.3 Update tool docstring to document auto_filter parameter behavior
- [ ] 1.2.4 Update error messages and format indicators based on auto_filter state

### 1.3 Advanced Search Tool Updates

- [ ] 1.3.1 Add `auto_filter: bool = True` parameter to `search_cards_advanced()` in `src/agent/tools/card_search.py`
- [ ] 1.3.2 Add logic to bypass session format filter when `auto_filter=False`
- [ ] 1.3.3 Update tool docstring to document auto_filter parameter behavior
- [ ] 1.3.4 Update `_format_search_results()` to handle auto_filter state for format indicators

## 2. Session Management

- [ ] 2.1 Verify `_session_manager.set_format_filter()` is called after loading deck
- [ ] 2.2 Ensure format filter persists correctly across subsequent tool calls in the session

## 3. Unit Tests

### 3.1 Load Deck Tool Tests

- [ ] 3.1.1 Write unit test for `load_deck()` auto-setting format filter for Standard deck in `tests/unit/agent/tools/test_deck_tools.py`
- [ ] 3.1.2 Write unit test for `load_deck()` clearing format filter for "all" format deck
- [ ] 3.1.3 Write unit test verifying format filter is accessible in session context after load

### 3.2 Card Lookup Tool Tests

- [ ] 3.2.1 Write unit test for `lookup_card_by_name()` with auto_filter=True (respects format filter)
- [ ] 3.2.2 Write unit test for `lookup_card_by_name()` with auto_filter=False (bypasses format filter)
- [ ] 3.2.3 Write unit test verifying auto_filter has no effect when no format filter is set

### 3.3 Advanced Search Tool Tests

- [ ] 3.3.1 Write unit test for `search_cards_advanced()` with auto_filter=True (respects format filter)
- [ ] 3.3.2 Write unit test for `search_cards_advanced()` with auto_filter=False (bypasses format filter)
- [ ] 3.3.3 Write unit test verifying token creatures excluded when auto_filter=True
- [ ] 3.3.4 Write unit test verifying token creatures included when auto_filter=False

## 4. Integration Tests

- [ ] 4.1 Write integration test for end-to-end auto-format workflow in `tests/integration/agent/test_deck_tools_integration.py`:
  - Create Standard deck
  - Load deck (verify format filter auto-set to "standard")
  - Search for cards with auto_filter=True (verify only Standard-legal cards returned)
  - Verify no token/non-Standard cards in results
- [ ] 4.2 Write integration test for auto_filter bypass workflow:
  - Load Standard deck (format filter = "standard")
  - Search with auto_filter=False
  - Verify non-Standard cards ARE included in results
  - Search with auto_filter=True
  - Verify non-Standard cards ARE NOT included

## 5. Code Quality

- [ ] 5.1 Run `uv run mypy src/` and fix any type errors
- [ ] 5.2 Run `uv run ruff check . --fix` and address linting issues
- [ ] 5.3 Run `uv run ruff format .` to ensure consistent formatting

## 6. Documentation

- [ ] 6.1 Update `CLAUDE.md` to document auto-format-filter behavior in `load_deck` tool description
- [ ] 6.2 Add note about automatic format synchronization when loading decks

## 7. Testing and Validation

- [ ] 7.1 Run all tests: `uv run pytest`
- [ ] 7.2 Manual test via Chainlit - Auto-filter on load:
  - Create Standard deck
  - Load deck and verify format filter message appears
  - Search for cards and verify only Standard results
  - Verify bug scenario (token creatures) no longer occurs
- [ ] 7.3 Manual test via Chainlit - Auto-filter bypass:
  - Load Standard deck
  - Ask "show me Lightning Bolt from any format" (should use auto_filter=False)
  - Verify non-Standard printings are shown
  - Ask "show me red creatures" (should use auto_filter=True, default)
  - Verify only Standard cards shown
- [ ] 7.4 Validate OpenSpec change: `openspec validate add-auto-format-filter-for-decks --strict`

## 8. Bug Report Update

- [ ] 8.1 Update bug report #f2c05a23 status to "resolved" using `scripts/manage_bug_reports.py`
- [ ] 8.2 Verify bug report archive workflow if applicable

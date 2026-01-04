# Implementation Tasks

## 1. Core Implementation
- [x] 1.1 Create `update_deck_sidebar()` helper function in `src/ui/app.py`
- [x] 1.2 Format deck information as markdown text (name, ID, format, colors, card count)
- [x] 1.3 Use `cl.ElementSidebar.set_elements()` to display/update sidebar
- [x] 1.4 Use `cl.ElementSidebar.set_title()` to set sidebar title
- [x] 1.5 Close sidebar when no active deck (set_elements to empty array)

## 2. Integration Points
- [x] 2.1 Call `update_deck_sidebar()` in `on_chat_start()` to initialize
- [x] 2.2 Call `update_deck_sidebar()` after `create_deck` tool execution
- [x] 2.3 Call `update_deck_sidebar()` after `load_deck` tool execution
- [x] 2.4 Call `update_deck_sidebar()` after `add_card_to_deck` tool execution (update card count)
- [x] 2.5 Call `update_deck_sidebar()` after `delete_deck` tool execution

## 3. Testing
- [x] 3.1 Manual test: Verify sidebar appears when deck is loaded
- [x] 3.2 Manual test: Verify sidebar updates when cards are added
- [x] 3.3 Manual test: Verify sidebar shows correct format and colors
- [x] 3.4 Manual test: Verify sidebar closes when deck is deleted
- [x] 3.5 Manual test: Verify sidebar persists across messages in same session

## 4. Documentation
- [x] 4.1 Update CLAUDE.md with sidebar feature description
- [x] 4.2 Document `update_deck_sidebar()` function with docstring

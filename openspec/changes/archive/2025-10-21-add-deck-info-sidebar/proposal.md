# Add Deck Information Sidebar

## Why

Users need persistent visibility of their active deck's key information (name, ID, format, color identity) while building and modifying decks in the chat interface. Currently, this context is only visible in conversation messages, requiring users to scroll back through chat history to recall basic deck details.

## What Changes

- Add persistent sidebar display using Chainlit's `ElementSidebar` API
- Display active deck information: name, ID, format, and colors
- Update sidebar automatically when deck state changes (create, load, modify)
- Use simple text-based formatting with markdown (Option 1 from research)
- Close sidebar when no active deck is loaded

**Implementation approach**: Simple text-based display using `cl.Text` elements, suitable for MVP. Custom JSX elements deferred for future UI replacement.

## Impact

- **Affected specs**: `chainlit-ui` (add new sidebar requirement)
- **Affected code**:
  - `src/ui/app.py` - Add `update_deck_sidebar()` helper function
  - `src/ui/app.py:on_chat_start()` - Initialize sidebar on session start
  - `src/agent/tools/deck.py` - Call sidebar update after deck operations
- **Breaking changes**: None
- **Dependencies**: Chainlit `cl.ElementSidebar` API (already available in current version)

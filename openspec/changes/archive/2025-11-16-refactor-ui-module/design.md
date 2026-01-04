# UI Module Refactoring Design

## Architecture Overview

### Current Architecture Problems

```
src/ui/app.py (1,411 lines)
├── Initialization (100 lines)
├── on_message() - BLOATED (360 lines)
│   ├── Agent orchestration
│   ├── Tool step creation
│   ├── 5 inline signal handlers (150 lines)
│   ├── Error handling
│   └── Sidebar updates
├── update_deck_sidebar() - COMPLEX (183 lines)
│   ├── Database queries
│   ├── Color calculations
│   ├── Card grouping
│   └── Markdown formatting
├── on_chat_start() - SETUP (127 lines)
│   ├── Welcome message
│   └── Filter UI initialization
└── 9 action callbacks - SPRAWL (530 lines)
    ├── Filter callbacks (2)
    ├── Deck callbacks (3)
    ├── Card callbacks (2)
    └── Pagination callbacks (2)
```

**Problems**:
1. Single Responsibility violation (10+ responsibilities in one file)
2. Testing requires full Chainlit mock setup
3. Finding code requires extensive scrolling
4. High coupling between unrelated features

### Target Architecture

```
src/ui/
├── app.py (~150 lines)
│   ├── Lifecycle hooks (@cl.on_chat_start, @cl.on_message)
│   ├── Global initialization
│   └── Delegates to handlers
│
├── handlers/ (orchestration layer)
│   ├── message_handler.py
│   │   └── async def handle_user_message(message, agent, session_id)
│   │       ├── Run agent
│   │       ├── Extract tool calls → create steps
│   │       ├── Detect signals → delegate to signal handlers
│   │       ├── Handle errors
│   │       └── Update sidebar if needed
│   │
│   └── signal_handlers.py
│       ├── async def handle_confirmation_signal(signal)
│       ├── async def handle_pagination_signal(signal)
│       ├── async def handle_synergy_signal(signal)
│       ├── async def handle_deck_list_signal(signal)
│       └── async def handle_disambiguation_signal(signal)
│
├── actions/ (Chainlit action callbacks)
│   ├── filter_actions.py
│   │   ├── on_set_format_filter()
│   │   └── on_set_games_filter()
│   │
│   ├── deck_actions.py
│   │   ├── on_confirm_delete_deck()
│   │   ├── on_cancel_delete_deck()
│   │   └── on_quick_load_deck()
│   │
│   ├── card_actions.py
│   │   ├── on_add_suggested_card()
│   │   └── on_select_card()
│   │
│   └── pagination_actions.py
│       └── on_navigate_page()
│
├── components/ (UI component logic)
│   ├── sidebar.py
│   │   ├── async def update_deck_sidebar(session_id)
│   │   ├── async def _fetch_deck_data(session_id)
│   │   ├── def _calculate_color_identity(cards)
│   │   ├── def _group_cards_by_type(cards)
│   │   └── def _format_sidebar_markdown(deck, cards, colors)
│   │
│   └── welcome.py
│       ├── async def show_welcome_message()
│       └── async def initialize_filter_actions()
│
├── dependencies.py
│   └── async def get_agent_dependencies(session_id)
│
└── [existing utility modules unchanged]
    ├── formatters.py
    ├── tool_steps.py
    ├── action_callbacks.py
    └── symbols.py
```

## Module Responsibilities

### `app.py` - Entry Point (Thin Layer)

**Responsibility**: Chainlit lifecycle hook registration only

**Functions**:
- `async def initialize_app()` - One-time setup (DB, agent)
- `@cl.on_chat_start` - Delegate to `welcome.show_welcome_message()`
- `@cl.on_message` - Delegate to `message_handler.handle_user_message()`

**Size**: ~150 lines (down from 1,411)

**Why**: Keeps entry point minimal, easy to understand app flow at a glance.

---

### `handlers/message_handler.py` - Message Orchestration

**Responsibility**: Coordinate agent execution → result processing → UI updates

**Functions**:
```python
async def handle_user_message(
    message: cl.Message,
    agent: Agent,
    session_id: str
) -> None:
    """Orchestrate message handling workflow."""
    # 1. Show thinking message
    # 2. Run agent with session context
    # 3. Extract tool calls → create Chainlit Steps
    # 4. Send agent response
    # 5. Detect signals → delegate to signal_handlers
    # 6. Update sidebar if needed
    # 7. Handle errors
```

**Size**: ~120 lines

**Why**: Single place to understand entire message flow without implementation details.

---

### `handlers/signal_handlers.py` - Signal → Action Mapping

**Responsibility**: Detect agent signals and create corresponding Chainlit action UIs

**Functions** (one per signal type):
```python
async def handle_confirmation_signal(signal: dict) -> None:
    """Create delete confirmation action buttons."""

async def handle_pagination_signal(signal: dict) -> None:
    """Create pagination navigation buttons."""

async def handle_synergy_signal(signal: dict) -> None:
    """Create synergy card quick-add buttons."""

async def handle_deck_list_signal(signal: dict) -> None:
    """Create deck quick-load buttons."""

async def handle_disambiguation_signal(signal: dict) -> None:
    """Create card selection buttons."""
```

**Size**: ~200 lines total (~40 lines per handler)

**Why**:
- Isolates signal detection logic from orchestration
- Easy to add new signal types without touching orchestration
- Each handler testable in isolation

---

### `actions/*.py` - Chainlit Action Callbacks

**Responsibility**: Handle user clicks on action buttons (filters, deck ops, card ops, pagination)

**Module Breakdown**:

**`filter_actions.py`** (~80 lines):
```python
@cl.action_callback("set_format_filter")
async def on_set_format_filter(action: cl.Action) -> None

@cl.action_callback("set_games_filter")
async def on_set_games_filter(action: cl.Action) -> None
```

**`deck_actions.py`** (~150 lines):
```python
@cl.action_callback("confirm_delete_deck")
async def on_confirm_delete_deck(action: cl.Action) -> None

@cl.action_callback("cancel_delete_deck")
async def on_cancel_delete_deck(action: cl.Action) -> None

@cl.action_callback("quick_load_deck")
async def on_quick_load_deck(action: cl.Action) -> None
```

**`card_actions.py`** (~200 lines):
```python
@cl.action_callback("add_suggested_card")
async def on_add_suggested_card(action: cl.Action) -> None

@cl.action_callback("select_card")
async def on_select_card(action: cl.Action) -> None
```

**`pagination_actions.py`** (~80 lines):
```python
@cl.action_callback("navigate_page")
async def on_navigate_page(action: cl.Action) -> None
```

**Why**:
- Related callbacks grouped by feature domain
- Easy to find callback for specific action
- Can test action handling without full app context

---

### `components/sidebar.py` - Deck Sidebar Component

**Responsibility**: Fetch deck data, calculate metadata, format sidebar UI

**Functions**:
```python
async def update_deck_sidebar(session_id: str) -> None:
    """Main entry point - update or clear sidebar."""

async def _fetch_deck_data(session_id: str) -> tuple[Deck | None, list[Card]]:
    """Query database for active deck and cards."""

def _calculate_color_identity(cards: list[Card]) -> list[str]:
    """Compute color identity from card list."""

def _group_cards_by_type(cards: list[Card]) -> dict[str, list[Card]]:
    """Group cards by type (Creatures, Spells, Lands)."""

def _format_sidebar_markdown(
    deck: Deck,
    cards: list[Card],
    colors: list[str]
) -> tuple[str, str]:
    """Generate deck info and card list markdown."""
```

**Size**: ~200 lines (broken into 5 focused functions)

**Why**:
- Sidebar logic reusable outside Chainlit context (future UIs)
- Each helper function testable independently
- Clear separation: data fetching → calculation → formatting

---

### `components/welcome.py` - Welcome Screen Component

**Responsibility**: Initial user onboarding and filter UI setup

**Functions**:
```python
async def show_welcome_message() -> None:
    """Display welcome message with quick-start tips."""

async def initialize_filter_actions() -> None:
    """Create format/games filter action buttons."""
```

**Size**: ~80 lines

**Why**: Separates welcome flow from message handling lifecycle.

---

## Design Patterns

### 1. Layered Architecture

```
Chainlit Lifecycle (app.py)
         ↓
Orchestration Layer (handlers/)
         ↓
Component Layer (components/)
         ↓
Utility Layer (formatters.py, tool_steps.py, etc.)
```

**Benefits**:
- Clear dependency direction (top → down)
- Components reusable in different orchestration contexts
- Easy to swap Chainlit for different UI framework

---

### 2. Delegation Pattern

**Before** (monolithic):
```python
@cl.on_message
async def on_message(message):
    # 360 lines of logic here
```

**After** (delegating):
```python
@cl.on_message
async def on_message(message: cl.Message) -> None:
    session_id = cl.user_session.get("id")
    await handle_user_message(message, _agent, session_id)
```

**Benefits**: Entry point tells "what" not "how".

---

### 3. Signal-Handler Pattern

**Concept**: Agent tools return dict signals, UI layer maps signals → actions

**Example**:
```python
# Agent tool returns signal
return {"has_pagination": True, "page": 2, "total_pages": 5}

# Signal handler creates UI
async def handle_pagination_signal(signal: dict) -> None:
    page = signal["page"]
    total_pages = signal["total_pages"]
    actions = create_pagination_actions(page, total_pages)
    await send_action_message(actions)
```

**Benefits**:
- Agent layer never knows about Chainlit
- Easy to add new signal types
- Signal handlers testable with mock dicts

---

### 4. Component Decomposition

**Sidebar component** broken into pipeline stages:

```
fetch_data() → calculate_metadata() → format_ui()
    ↓               ↓                      ↓
Database       Pure function          Markdown
(async)        (sync, testable)       (string output)
```

**Benefits**:
- Each stage testable independently
- Pure functions easy to unit test
- Clear data flow

---

## Testing Strategy

### Unit Tests (New)

**`tests/unit/ui/handlers/test_signal_handlers.py`**:
```python
async def test_pagination_signal_creates_correct_actions():
    signal = {"has_pagination": True, "page": 2, "total_pages": 5}
    # Mock Chainlit message sending
    with mock_chainlit_message():
        await handle_pagination_signal(signal)
        # Assert correct actions created
```

**`tests/unit/ui/components/test_sidebar.py`**:
```python
def test_calculate_color_identity():
    cards = [Card(colors=["W", "U"]), Card(colors=["U"])]
    colors = _calculate_color_identity(cards)
    assert colors == ["W", "U"]
```

**Benefits**: Fast, isolated tests for pure logic.

---

### Integration Tests (Existing - Minimal Changes)

**`tests/integration/ui/test_message_flow.py`**:
```python
async def test_user_message_triggers_agent_response():
    # Test full message flow end-to-end
    # Should still work after refactoring (behavior unchanged)
```

**Benefits**: Catch regression during refactoring.

---

## Migration Strategy

### Phase 1: Extract Signal Handlers (Low Risk)

**Steps**:
1. Create `handlers/signal_handlers.py`
2. Copy 5 signal handler blocks from `on_message()`
3. Convert to standalone async functions
4. Import and call from `on_message()`
5. Test: Verify signals still create correct actions

**Risk**: Low - pure code movement, no logic changes

**Validation**: Manual testing of each signal type (delete confirmation, pagination, synergy, deck list, disambiguation)

---

### Phase 2: Extract Action Callbacks (Low Risk)

**Steps**:
1. Create `actions/*.py` modules
2. Move `@cl.action_callback` functions by domain
3. Update imports in `app.py`
4. Test: Click each action button, verify behavior

**Risk**: Low - decorators work the same regardless of file location

**Validation**: Manual testing of all 9 action types

---

### Phase 3: Extract Components (Low Risk)

**Steps**:
1. Create `components/sidebar.py`
2. Move `update_deck_sidebar()` and break into helpers
3. Create `components/welcome.py`
4. Move welcome message logic from `on_chat_start()`
5. Test: Verify sidebar updates and welcome screen

**Risk**: Low - component logic self-contained

**Validation**:
- Unit tests for helper functions
- Integration test for sidebar updates

---

### Phase 4: Extract Message Handler (Medium Risk)

**Steps**:
1. Create `handlers/message_handler.py`
2. Move orchestration logic from `on_message()`
3. Slim `app.py` to delegation only
4. Test: Full conversation flow

**Risk**: Medium - core message flow logic being moved

**Validation**:
- Comprehensive integration testing
- Manual conversation testing with all features

---

## Rollback Plan

Each phase is independently deployable:

**If Phase X fails**:
1. Revert commits for that phase
2. Previous phases remain (partial improvement better than none)
3. Debug issue in isolation
4. Re-attempt phase after fix

**Example**: If Phase 4 breaks something, Phases 1-3 still provide value (cleaner `on_message()`, organized callbacks).

---

## Future Extensibility

### Adding New Signal Types

**Current**: Add 30-40 lines to `on_message()` (360 → 400 lines)

**After Refactoring**:
```python
# handlers/signal_handlers.py
async def handle_new_signal(signal: dict) -> None:
    # 30-40 lines here (isolated)
```

**Benefit**: No changes to orchestration logic.

---

### Adding New Action Types

**Current**: Add to growing list of 9 callbacks in `app.py`

**After Refactoring**:
```python
# actions/new_feature_actions.py
@cl.action_callback("new_action")
async def on_new_action(action: cl.Action) -> None:
    # New action logic
```

**Benefit**: New file, no impact on existing code.

---

### Replacing Chainlit (Future)

**Current**: UI logic deeply embedded in `app.py`

**After Refactoring**:
- Components in `components/` are UI-framework-agnostic
- Replace `app.py` + `handlers/` with CopilotKit equivalents
- Reuse `components/`, `formatters.py`, `tool_steps.py`

**Benefit**: 50%+ code reuse in UI migration.

---

## Performance Considerations

### Import Overhead

**Concern**: More modules = more import time?

**Analysis**:
- Python import caching makes this negligible
- Initial app startup: +10-20ms (imperceptible)
- Per-message overhead: 0ms (imports cached)

**Verdict**: Not a concern for this application.

---

### Function Call Overhead

**Concern**: Extra function calls from delegation?

**Analysis**:
- Delegation adds ~1-2 function calls per message
- Overhead: <1ms per message (async overhead dominates)
- Agent LLM calls: 500-2000ms (dwarfs function overhead)

**Verdict**: Not a concern - readability benefit >> performance cost.

---

## Success Metrics

### Code Quality Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Largest file | 1,411 lines | ~200 lines | ≤250 lines |
| Largest function | 360 lines | ~120 lines | ≤150 lines |
| Functions per file | 14 (app.py) | ~3-5 per file | ≤10 per file |
| Modules in `ui/` | 6 | 13 | N/A |

---

### Maintainability Metrics

- **Time to locate code**: 30s → 10s (predictable structure)
- **Test setup complexity**: Full Chainlit mock → Mock specific layer
- **Change impact**: 5-10 files touched → 1-2 files touched

---

## Open Questions

1. **Should `dependencies.py` move to `handlers/`?**
   - Pro: Dependencies used by handlers
   - Con: Also used by components
   - **Decision**: Keep at root level (shared utility)

2. **Should `formatters.py` be split further?**
   - Current: 38KB (large)
   - Pro: Many formatting functions
   - Con: All related to card/deck formatting
   - **Decision**: Defer to future refactoring (out of scope)

3. **Should we add unit tests during refactoring or after?**
   - Pro (during): Catch issues early
   - Con (during): Slows down refactoring
   - **Decision**: Integration tests during, unit tests after (Phase 5)

---

## Conclusion

This refactoring transforms a monolithic 1,411-line file into a modular structure with:
- ✅ Clear separation of concerns
- ✅ Improved testability
- ✅ Enhanced navigability
- ✅ Future-proof extensibility
- ✅ No breaking changes
- ✅ Phased, low-risk migration

The investment (11-16 hours) prevents technical debt accumulation and enables faster Phase 2 feature development.

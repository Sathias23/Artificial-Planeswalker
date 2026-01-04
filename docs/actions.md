# Chainlit Actions Implementation Guide

**Status**: Research Complete
**Last Updated**: 2025-11-02

This document provides a comprehensive analysis of Chainlit actions for the Artificial-Planeswalker project, including implementation recommendations and architectural considerations.

---

## Executive Summary

Chainlit actions are **interactive button elements** that attach to chat messages and trigger Python functions when clicked. After thorough research and codebase analysis, **actions are an excellent fit for this project** and should be implemented to complement our conversational-first architecture.

**Key Findings:**
- Actions work best for fixed-choice interactions (filters, confirmations, quick-add)
- Our session-based architecture is perfectly structured for action integration
- Hybrid approach (conversation + actions) provides power user shortcuts while maintaining discoverability
- Phase 1 implementation targets high-impact quick wins with minimal refactoring

---

## What Are Chainlit Actions?

**Chainlit Actions** are interactive button elements that attach to chat messages and trigger Python functions when clicked by users. They provide a declarative way to create structured interactions without requiring text input.

### Core Characteristics

- **Visual elements**: Buttons displayed in the chat interface with customizable labels and icons
- **Event-driven**: Click events trigger async Python callbacks via `@cl.action_callback` decorator
- **Payload system**: Each action carries a dictionary payload with contextual data (e.g., card IDs, operation types)
- **Non-blocking**: Unlike Ask APIs, actions don't block the chat interface (user can continue chatting)
- **Lifecycle management**: Actions can be removed individually (`action.remove()`) or in bulk (`message.remove_actions()`)

---

## API & Implementation Patterns

### Action Class Definition

```python
import chainlit as cl

action = cl.Action(
    name="action_identifier",        # Required: matches @cl.action_callback parameter
    payload={"key": "value"},         # Required: dictionary with contextual data
    label="Button Text",              # Optional: user-facing button label
    tooltip="Hover description",      # Optional: shown on hover
    icon="mouse-pointer-click"        # Optional: Lucide icon name (https://lucide.dev/icons/)
)
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | Yes | Unique identifier matching callback decorator |
| `payload` | `Dict` | Yes | Data passed to callback when clicked |
| `label` | `str` | No | Button text (defaults to `name` if not provided) |
| `tooltip` | `str` | No | Description shown on hover |
| `icon` | `str` | No | Lucide icon name for visual indicator |

### Action Callback Pattern

```python
@cl.action_callback("action_identifier")
async def handle_action(action: cl.Action):
    # Access payload data
    value = action.payload.get("key")

    # Perform operation (e.g., add card to deck)
    result = await some_async_operation(value)

    # Send response message
    await cl.Message(content=f"Operation complete: {result}").send()

    # Remove the action button
    await action.remove()
```

### Attaching Actions to Messages

```python
@cl.on_chat_start
async def start():
    actions = [
        cl.Action(name="option_a", payload={"choice": "A"}, label="Option A"),
        cl.Action(name="option_b", payload={"choice": "B"}, label="Option B"),
        cl.Action(name="cancel", payload={}, label="Cancel", icon="x-circle")
    ]

    await cl.Message(
        content="Choose an option:",
        actions=actions
    ).send()
```

### Removing All Actions from a Message

```python
# Store message reference for later action removal
message = cl.Message(content="Choose an option:", actions=actions)
await message.send()

# In action callback, remove all actions from the message
@cl.action_callback("option_a")
async def handle_option_a(action: cl.Action):
    # Get the message object (requires storing reference in user session)
    message = cl.user_session.get("choice_message")

    # Remove all action buttons
    await message.remove_actions()

    # Proceed with operation
    await cl.Message(content="You selected Option A").send()
```

### Session-Based Action Tracking Pattern

```python
import chainlit as cl

@cl.on_chat_start
async def start():
    actions = [
        cl.Action(name="confirm", payload={"deck_id": "123"}, label="Confirm Delete"),
        cl.Action(name="cancel", payload={}, label="Cancel")
    ]

    message = cl.Message(content="Delete this deck?", actions=actions)
    await message.send()

    # Store message reference for later cleanup
    cl.user_session.set("delete_confirmation_message", message)

@cl.action_callback("confirm")
async def handle_confirm(action: cl.Action):
    # Retrieve message and remove all actions
    message = cl.user_session.get("delete_confirmation_message")
    await message.remove_actions()

    # Perform deletion
    deck_id = action.payload["deck_id"]
    await delete_deck(deck_id)
    await cl.Message(content="Deck deleted successfully").send()

@cl.action_callback("cancel")
async def handle_cancel(action: cl.Action):
    message = cl.user_session.get("delete_confirmation_message")
    await message.remove_actions()
    await cl.Message(content="Deletion cancelled").send()
```

---

## When to Use Actions vs Other Chainlit Features

### Use Actions When

- **Fixed set of choices**: User selects from predefined options (e.g., format selection: Standard, Modern, Commander)
- **One-click operations**: Quick actions that don't require text input (e.g., "Add this card to deck")
- **Confirmation workflows**: Approve/deny actions for destructive operations (e.g., delete deck confirmation)
- **Menu-driven navigation**: Guided workflows where user clicks through options
- **Moderate number of options**: 2-7 buttons per message (beyond that, UI gets cluttered)

**Example - Format Selection:**
```python
actions = [
    cl.Action(name="set_standard", payload={"format": "standard"}, label="Standard"),
    cl.Action(name="set_modern", payload={"format": "modern"}, label="Modern"),
    cl.Action(name="set_commander", payload={"format": "commander"}, label="Commander")
]
await cl.Message(content="Select deck format:", actions=actions).send()
```

### Use AskActionMessage When

- **Blocking required**: Must prevent further chat until user responds (compliance workflows)
- **Synchronous decision**: Application logic requires user choice before proceeding
- **Timeout control**: Need to enforce time limits on user responses

**Example - Blocking Confirmation:**
```python
res = await cl.AskActionMessage(
    content="This will delete 40 cards. Continue?",
    actions=[
        cl.Action(name="confirm", label="Yes, delete", payload={"confirmed": True}),
        cl.Action(name="cancel", label="Cancel", payload={"confirmed": False})
    ],
    timeout=30  # 30 second timeout
).send()

if res and res.get("value") == "confirm":
    await delete_deck()
```

### Use AskUserMessage / Chat Input When

- **Freeform text required**: Card names, search queries, deck names
- **Number input**: Card quantities, mana value ranges
- **Complex queries**: Multi-criteria searches with natural language

**Example - Card Quantity:**
```python
res = await cl.AskUserMessage(
    content="How many copies of Lightning Bolt? (1-4)"
).send()

try:
    quantity = int(res["output"])
    if 1 <= quantity <= 4:
        await add_card_to_deck("Lightning Bolt", quantity)
except ValueError:
    await cl.Message(content="Please enter a valid number").send()
```

---

## Limitations & Best Practices

### Limitations

1. **No built-in state management**: Must use `cl.user_session` or `contextvars` to track action state across messages
2. **Fixed payload at creation**: Cannot dynamically update payload after action is sent
3. **Manual removal required**: Actions don't auto-disappear after click (must call `.remove()`)
4. **UI clutter with many actions**: More than 7 buttons becomes unwieldy
5. **No input validation**: Payload is a free-form dict, application must validate
6. **Limited customization**: Button styling controlled by Chainlit theme (no custom CSS per action)
7. **Toaster notifications**: Processing actions show toaster at top-right (may not suit all UX preferences)

### Best Practices

**1. Unique Action Names:**
```python
# Good: Descriptive, unique names
cl.Action(name="add_lightning_bolt", payload={"card_id": "123"})

# Bad: Generic names (causes callback conflicts)
cl.Action(name="add_card", payload={"card_id": "123"})
```

**2. Comprehensive Error Handling:**
```python
@cl.action_callback("add_card")
async def handle_add_card(action: cl.Action):
    try:
        card_id = action.payload.get("card_id")
        if not card_id:
            raise ValueError("Missing card_id in payload")

        await add_card_to_deck(card_id)
        await action.remove()
        await cl.Message(content="Card added successfully").send()

    except ValueError as e:
        await cl.Message(content=f"Error: {e}").send()
    except Exception as e:
        await cl.Message(content="An unexpected error occurred").send()
        import logging
        logging.error(f"Action error: {e}", exc_info=True)
```

**3. Payload Validation:**
```python
@cl.action_callback("delete_deck")
async def handle_delete(action: cl.Action):
    # Validate payload structure
    deck_id = action.payload.get("deck_id")
    confirmed = action.payload.get("confirmed", False)

    if not deck_id:
        await cl.Message(content="Invalid action: missing deck ID").send()
        return

    if not confirmed:
        await cl.Message(content="Deletion not confirmed").send()
        return

    # Proceed with deletion
    await delete_deck(deck_id)
```

**4. Action Removal Patterns:**
```python
# Pattern 1: Remove individual action after click
@cl.action_callback("add_card")
async def handle_add(action: cl.Action):
    await add_card(action.payload["card_id"])
    await action.remove()  # Remove this specific button

# Pattern 2: Remove all actions from message
@cl.action_callback("option_a")
async def handle_option(action: cl.Action):
    message = cl.user_session.get("options_message")
    await message.remove_actions()  # Remove all buttons from this message
```

**5. Session State Management:**
```python
@cl.on_chat_start
async def start():
    # Initialize session state for tracking actions
    cl.user_session.set("pending_confirmations", {})

@cl.action_callback("confirm_delete")
async def handle_confirm(action: cl.Action):
    # Track confirmation in session
    pending = cl.user_session.get("pending_confirmations")
    deck_id = action.payload["deck_id"]
    pending[deck_id] = True
    cl.user_session.set("pending_confirmations", pending)
```

### Common Gotchas

**1. Action Name Mismatch:**
```python
# WRONG: Name doesn't match callback
cl.Action(name="add_card", ...)

@cl.action_callback("add_card_to_deck")  # Won't trigger!
async def handle_add(action):
    pass

# CORRECT: Names must match exactly
cl.Action(name="add_card_to_deck", ...)

@cl.action_callback("add_card_to_deck")
async def handle_add(action):
    pass
```

**2. Forgetting to Await `.remove()`:**
```python
# WRONG: Missing await
@cl.action_callback("confirm")
async def handle_confirm(action):
    action.remove()  # Won't remove! Silent failure

# CORRECT: Always await
@cl.action_callback("confirm")
async def handle_confirm(action):
    await action.remove()  # Properly removes button
```

**3. Assuming Actions Auto-Remove:**
```python
# WRONG: Actions persist after click unless explicitly removed
@cl.action_callback("add_card")
async def handle_add(action):
    await add_card(action.payload["card_id"])
    # Button still visible! User could click again

# CORRECT: Always remove after processing
@cl.action_callback("add_card")
async def handle_add(action):
    await add_card(action.payload["card_id"])
    await action.remove()  # Cleanup
```

**4. Not Storing Message References:**
```python
# WRONG: Can't remove all actions later
actions = [cl.Action(name="a"), cl.Action(name="b")]
await cl.Message(content="Choose:", actions=actions).send()
# Lost reference to message!

# CORRECT: Store message for later cleanup
message = cl.Message(content="Choose:", actions=actions)
await message.send()
cl.user_session.set("choice_message", message)

@cl.action_callback("a")
async def handle_a(action):
    msg = cl.user_session.get("choice_message")
    await msg.remove_actions()  # Can clean up all buttons
```

---

## Evaluation for Artificial-Planeswalker

### User-Proposed Use Cases

#### 1. Initial Filters on Startup ✅ EXCELLENT FIT

**Why it works:**
- Fixed set of choices (Standard/Modern/Commander, Paper/Arena/MTGO)
- Non-blocking quick selection
- Immediate session state update without agent overhead
- Visual menu is clearer than reading text examples

**Current pain point:** Users currently must say "only show standard cards" conversationally, and there's no visual indicator of active filters (`src/ui/app.py:401-418`).

**Implementation pattern:**
```python
@cl.on_chat_start
async def start():
    # Show welcome + filter selection buttons
    filter_actions = [
        cl.Action(name="set_standard", payload={"format": "standard"},
                  label="Standard", icon="zap"),
        cl.Action(name="set_all_formats", payload={"format": None},
                  label="All Formats", icon="globe")
    ]

    games_actions = [
        cl.Action(name="set_arena", payload={"games": ["arena"]},
                  label="Arena", icon="monitor"),
        cl.Action(name="set_paper", payload={"games": ["paper"]},
                  label="Paper", icon="book-open")
    ]
```

#### 2. Disambiguation When Searching for Cards ⚠️ CONDITIONAL FIT

**When it works well:**
- Small number of matches (2-5 similar cards)
- Exact operation context (e.g., "add to deck" vs "view details")

**When it doesn't work:**
- Large result sets (15+ cards) → too many buttons clutters UI
- User wants to compare cards before deciding → conversational works better

**Better approach:** Hybrid model
```python
# If 2-5 exact matches → show action buttons
if len(suggestions) <= 5:
    actions = [cl.Action(name="select_card", payload={"card_id": c.id},
                         label=c.name) for c in suggestions]

# If 6-15 matches → show table with hover preview, let user ask conversationally
# If 15+ matches → paginated results with Next/Previous buttons
```

**Current implementation:** `src/agent/tools/card_lookup.py:66-74` returns text list only.

#### 3. Card Add Offers After Card Search ✅ EXCELLENT FIT (with limits)

**Why it works:**
- Synergy suggestions (5-10 cards) → perfect for "Add to Deck" buttons
- Search results showing 3-7 cards → can add quick-add buttons
- Saves typing card names repeatedly

**Implementation:**
```python
@cl.action_callback("add_suggested_card")
async def handle_add_suggested_card(action: cl.Action):
    card_name = action.payload.get("card_name")
    card_id = action.payload.get("card_id")

    async with get_agent_dependencies(session_id) as deps:
        await deps.deck_repository.add_card_to_deck(
            deck_id=deps.active_deck_id,
            card_id=card_id,
            quantity=1  # Could add quantity selector
        )

    await action.remove()
    await cl.Message(content=f"Added {card_name} to deck").send()
    await update_deck_sidebar(session_id)
```

**Limitation:** Large search results (20+ cards) should NOT show 20 action buttons. Use pagination + conversational add instead.

**Current implementation:** `src/agent/tools/synergy.py:279-385` (synergy suggestion tool - perfect candidate)

### Additional High-Value Use Cases

#### 4. Deck Deletion Confirmation ✅ HIGH PRIORITY

**Current friction:** `src/agent/tools/deck_tools.py:865-871`
```python
# User must confirm deletion in second conversational message
if not confirmed:
    return "⚠ Are you sure? To confirm, please explicitly request deletion again."
```

**Better with actions:**
```python
actions = [
    cl.Action(name="confirm_delete", payload={"deck_id": deck.id},
              label="Yes, delete", icon="trash-2"),
    cl.Action(name="cancel_delete", payload={},
              label="Cancel", icon="x-circle")
]
```

#### 5. Search Pagination ✅ HIGH PRIORITY

**Current friction:** `src/ui/formatters.py:260-270`
```python
# Pagination shown as text, user must ask conversationally for next page
f"Showing {len(cards)} of {total} results (Page {page}/{total_pages})"
```

**Better with actions:**
```python
if page < total_pages:
    actions.append(cl.Action(name="next_page", payload={"page": page+1},
                             label="Next →"))
if page > 1:
    actions.append(cl.Action(name="prev_page", payload={"page": page-1},
                             label="← Previous"))
```

#### 6. Quick Deck Load ✅ MEDIUM PRIORITY

**Current friction:** User must remember deck name, type "load Mono Red Aggro"

**Better approach:** Show deck selector after `list_decks`
```python
# After listing decks, show quick-load buttons
for deck in recent_decks[:5]:
    actions.append(cl.Action(name="load_deck", payload={"deck_id": deck.id},
                             label=f"Load {deck.name}"))
```

**Current implementation:** `src/agent/tools/deck_tools.py:571-634` (list_decks tool)

---

## Current Pain Points & Friction Areas

### Card Search & Lookup Friction

**Problem:** Multi-step interaction required for complex searches
- User must specify filters conversationally: "Find red creatures with haste under 4 mana"
- Agent must parse natural language → invoke `search_cards_advanced` with correct filters
- Result may be overwhelming (up to 15 cards displayed)
- No quick "refine search" or "show next page" buttons - must ask conversationally again

**File Reference:** `src/ui/app.py:500-517` (tool steps displayed after execution)

### Format/Games Filter Management

**Problem:** No visual feedback when filters are active
- Filters are set via conversational requests: "Only show Standard-legal cards"
- No persistent UI indicator of active filters
- Users can easily forget filter state or accidentally have filters enabled
- Filter changes require full agent invocation (tool execution overhead)

**File Reference:** `src/ui/app.py:172-179` (sidebar filter display - text only)

### Deck Operations Without Context

**Problem:** User must remember to create deck before adding cards
- No guided onboarding - welcome message suggests commands but doesn't show options
- Error messages are helpful but reactive: "No active deck. Create a deck first..."
- Cannot see available decks without asking agent
- No quick "Create Deck" button with sensible defaults

**File Reference:** `src/agent/tools/deck_tools.py:16-98` (create_deck tool)

### Confirmation & Safety UX

**Problem:** Binary confirmation model doesn't match natural conversation
- Delete deck confirmation message shows warning but user must explicitly ask to delete again
- "yes, delete it" → agent must recognize confirmation intent → re-invoke delete_deck with confirmed=True
- User doesn't see inline confirmation button after deletion warning

**File Reference:** `src/agent/tools/deck_tools.py:780-893` (delete_deck with confirmation)

### Sidebar Information Overload

**Problem:** Sidebar card list grows unwieldy for large decks
- All 60+ cards listed in sidebar, grouped by type, but no search/filter in sidebar
- No interaction with cards from sidebar (can't remove/edit quantity from sidebar)
- Sidebar updates happen after tool execution, so users see momentary blank state
- No indication of deck legality/card count warnings until user asks

**File Reference:** `src/ui/app.py:97-277` (update_deck_sidebar function)

---

## Implementation Roadmap

### Phase 1: High-Impact Quick Wins

**Scope:** Foundation + safety improvements

1. **Format/Games filter buttons** on startup and as persistent sidebar controls
   - Quick-select buttons for Standard/Modern/Commander
   - Checkbox-style buttons for Paper/Arena/MTGO
   - Direct session state update (no agent invocation)
   - Visual indicator of active filters

2. **Deck deletion confirmation** buttons
   - Inline "Confirm Delete" and "Cancel" buttons after warning message
   - Immediate action without second conversational turn
   - Safety improvement for destructive operations

3. **Pagination buttons** for search results
   - Next/Previous buttons with page counter
   - Preserve search filters across pages
   - Reduce conversational friction for browsing results

**Estimated Effort:** 8-12 hours
**Risk:** Low (minimal refactoring, clear boundaries)

### Phase 2: Deck Building Enhancements

**Scope:** Improving core deck-building workflows

4. **Synergy suggestion buttons** (5-10 cards with "Add to Deck")
   - One-click add for AI-suggested cards
   - Quantity selector (default: 1)
   - Sidebar auto-updates after add

5. **Quick deck load** from list_decks results
   - Show top 5 recent decks as quick-load buttons
   - Direct deck switching without typing name
   - Auto-sync format filter to deck format

6. **Card disambiguation** for 2-5 match scenarios
   - Show action buttons when search returns small number of exact matches
   - Context-aware actions (view vs add)
   - Fallback to conversational for larger result sets

**Estimated Effort:** 12-16 hours
**Risk:** Medium (integration with existing tools)

### Phase 3: Advanced Interactions

**Scope:** Power user features and sidebar interactivity

7. **Sidebar card removal** (X button next to each card)
   - Direct removal without conversational request
   - Confirmation for last copy of a card
   - Immediate sidebar refresh

8. **Quantity adjustment** (+/- buttons in sidebar)
   - In-place editing without opening full deck view
   - Validation (max 4 copies, except basic lands)
   - Visual feedback on change

9. **Deck templates** (quick-start wizard)
   - Pre-built starter decks for common archetypes
   - One-click import with auto-format setting
   - Tutorial prompts for new users

**Estimated Effort:** 16-20 hours
**Risk:** High (requires sidebar refactoring, complex state management)

---

## Architectural Advantages

Our codebase is **perfectly structured** for actions:

1. **Session persistence** (`src/agent/core.py:ConversationSessionManager`)
   - Actions can directly update format/games filters
   - Active deck ID can be set without agent invocation
   - State persists across conversation turns

2. **Sidebar update trigger** (`deps.sidebar_needs_update`)
   - Actions can trigger UI refresh without agent
   - Clear separation between state change and UI update
   - Maintains single source of truth

3. **Tool transparency** (`extract_tool_calls`)
   - Actions can be logged as tool-like steps
   - User sees what happened (filter changed, card added)
   - Maintains audit trail

4. **Agent independence**
   - Actions bypass agent for simple operations
   - Reduces API costs and latency
   - Agent remains authoritative for complex decisions

---

## Code Examples for Artificial-Planeswalker

### Format Selection on Startup

```python
import chainlit as cl
from src.ui.app import get_agent_dependencies, update_deck_sidebar

@cl.on_chat_start
async def start():
    # Welcome message
    await cl.Message(content="Welcome to Artificial-Planeswalker!").send()

    # Format selection actions
    format_actions = [
        cl.Action(
            name="set_format_filter",
            payload={"format": "standard"},
            label="Standard",
            icon="zap",
            tooltip="Show only Standard-legal cards"
        ),
        cl.Action(
            name="set_format_filter",
            payload={"format": None},
            label="All Formats",
            icon="globe",
            tooltip="Remove format filter"
        )
    ]

    format_message = cl.Message(
        content="Select a format to begin:",
        actions=format_actions
    )
    await format_message.send()
    cl.user_session.set("format_selection_message", format_message)


@cl.action_callback("set_format_filter")
async def handle_set_format(action: cl.Action):
    """Set the format filter for card searches."""
    format_val = action.payload.get("format")
    session_id = cl.user_session.get("session_id")

    try:
        # Direct session update (no agent needed)
        async with get_agent_dependencies(session_id) as deps:
            deps._session_manager.set_format_filter(session_id, format_val)

        # Remove all format buttons
        message = cl.user_session.get("format_selection_message")
        await message.remove_actions()

        # Confirmation message
        format_name = format_val.capitalize() if format_val else "All Formats"
        await cl.Message(content=f"Format set to **{format_name}**").send()

    except Exception as e:
        await cl.Message(content=f"Error setting format: {e}").send()
        import logging
        logging.error(f"Format filter action error: {e}", exc_info=True)
```

### Deck Deletion Confirmation

```python
@cl.action_callback("confirm_delete_deck")
async def handle_confirm_delete(action: cl.Action):
    """Confirm deck deletion and execute."""
    deck_id = action.payload.get("deck_id")
    deck_name = action.payload.get("deck_name")

    # Remove all action buttons
    message = cl.user_session.get("delete_confirmation_message")
    await message.remove_actions()

    try:
        # Get dependencies and delete deck
        session_id = cl.user_session.get("session_id")
        async with get_agent_dependencies(session_id) as deps:
            await deps.deck_repository.delete_deck(deck_id)

        await cl.Message(content=f"Deck '{deck_name}' deleted successfully").send()

        # Clear sidebar
        await update_deck_sidebar(session_id)

    except Exception as e:
        await cl.Message(content=f"Error deleting deck: {e}").send()


@cl.action_callback("cancel_delete_deck")
async def handle_cancel_delete(action: cl.Action):
    """Cancel deck deletion."""
    # Remove all action buttons
    message = cl.user_session.get("delete_confirmation_message")
    await message.remove_actions()

    await cl.Message(content="Deck deletion cancelled").send()


async def show_delete_confirmation(deck_id: str, deck_name: str):
    """Show confirmation dialog before deleting deck."""
    actions = [
        cl.Action(
            name="confirm_delete_deck",
            payload={"deck_id": deck_id, "deck_name": deck_name},
            label="Yes, delete deck",
            icon="trash-2",
            tooltip="Permanently delete this deck"
        ),
        cl.Action(
            name="cancel_delete_deck",
            payload={},
            label="Cancel",
            icon="x-circle",
            tooltip="Keep the deck"
        )
    ]

    message = cl.Message(
        content=f"Are you sure you want to delete '{deck_name}'? This cannot be undone.",
        actions=actions
    )
    await message.send()

    # Store for cleanup in callbacks
    cl.user_session.set("delete_confirmation_message", message)
```

### Search Pagination

```python
@cl.action_callback("navigate_page")
async def handle_navigate_page(action: cl.Action):
    """Navigate to a specific page of search results."""
    page = action.payload.get("page")
    search_context = cl.user_session.get("search_context")

    if not search_context:
        await cl.Message(content="No active search. Please start a new search.").send()
        return

    # Remove pagination buttons from previous results
    message = cl.user_session.get("pagination_message")
    if message:
        await message.remove_actions()

    try:
        session_id = cl.user_session.get("session_id")
        async with get_agent_dependencies(session_id) as deps:
            # Re-run search with new page number
            result = await deps.card_repository.search_advanced(
                **search_context,
                page=page
            )

        # Display results with new pagination buttons
        await display_search_results(result, search_context, page)

    except Exception as e:
        await cl.Message(content=f"Error navigating to page {page}: {e}").send()


async def display_search_results(result, search_context, current_page):
    """Display search results with pagination actions."""
    # Format card list
    from src.ui.formatters import format_card_list
    card_table = format_card_list(result.items)

    # Build pagination actions
    actions = []
    if current_page > 1:
        actions.append(cl.Action(
            name="navigate_page",
            payload={"page": current_page - 1},
            label="← Previous",
            icon="arrow-left"
        ))

    if current_page < result.total_pages:
        actions.append(cl.Action(
            name="navigate_page",
            payload={"page": current_page + 1},
            label="Next →",
            icon="arrow-right"
        ))

    # Send results with pagination
    pagination_info = (
        f"Showing page {current_page} of {result.total_pages} "
        f"({result.total_count} total results)"
    )

    message = cl.Message(
        content=f"{card_table}\n\n{pagination_info}",
        actions=actions if actions else None
    )
    await message.send()

    # Store context for pagination callbacks
    cl.user_session.set("pagination_message", message)
    cl.user_session.set("search_context", search_context)
```

### Synergy Suggestions with Quick Add

```python
@cl.action_callback("add_suggested_card")
async def handle_add_suggested_card(action: cl.Action):
    """Add a suggested card to the active deck."""
    try:
        card_name = action.payload.get("card_name")
        card_id = action.payload.get("card_id")

        # Get dependencies from session
        session_id = cl.user_session.get("session_id")
        async with get_agent_dependencies(session_id) as deps:
            # Check if active deck exists
            if not deps.active_deck_id:
                await cl.Message(
                    content="No active deck. Create a deck first to add cards."
                ).send()
                return

            # Add card to deck
            await deps.deck_repository.add_card_to_deck(
                deck_id=deps.active_deck_id,
                card_id=card_id,
                quantity=1
            )

        # Remove this action button
        await action.remove()

        # Send confirmation
        await cl.Message(content=f"Added {card_name} to deck").send()

        # Update sidebar
        await update_deck_sidebar(session_id)

    except Exception as e:
        await cl.Message(content=f"Error adding card: {e}").send()


async def display_synergy_suggestions(suggestions: list):
    """Display synergy suggestions with action buttons to add cards."""
    from src.data.schemas import Card

    # Create action button for each suggested card (limit to 7 for UX)
    actions = []
    for card in suggestions[:7]:
        actions.append(
            cl.Action(
                name="add_suggested_card",
                payload={
                    "card_name": card.name,
                    "card_id": str(card.id)
                },
                label=f"Add {card.name}",
                icon="plus-circle",
                tooltip=f"Add {card.name} to your deck"
            )
        )

    # Format card list as message content
    card_list = "\n".join([f"- {card.name} ({card.type_line})" for card in suggestions])

    message = cl.Message(
        content=f"**Synergy Suggestions:**\n{card_list}\n\nClick to add cards to your deck:",
        actions=actions
    )
    await message.send()

    # Store message reference for potential cleanup
    cl.user_session.set("synergy_suggestions_message", message)
```

---

## Critical Gotchas from Research

1. **Action removal is manual** - Must call `await action.remove()` or user can click repeatedly
2. **Store message references** - Need `cl.user_session.set("msg", message)` to clean up all buttons
3. **Limit to 7 actions** - Beyond that, UI gets cluttered
4. **Session state required** - No built-in state management, must use existing session manager
5. **Payload validation needed** - Actions accept free-form dict, must validate in callbacks
6. **Name matching critical** - Action name must exactly match `@cl.action_callback` parameter
7. **Always await removal** - `action.remove()` without `await` fails silently

---

## References

- [Chainlit Actions Documentation](https://docs.chainlit.io/api-reference/action)
- [Chainlit Ask User Documentation](https://docs.chainlit.io/advanced-features/ask-user)
- [Lucide Icons](https://lucide.dev/icons/) - Icon reference for action buttons
- Project architecture: `CLAUDE.md`
- Session management: `src/agent/core.py`
- UI layer: `src/ui/app.py`

---

## Phase 2 Implementation Details

Phase 2 implemented three key action types to reduce friction in deck-building workflows.

### Synergy Quick-Add (Implemented)

**Tool Signal** (`src/agent/tools/synergy_detection.py`):
```python
# detect_deck_synergies returns structured dict when synergies found
return {
    "has_synergies": True,
    "synergy_cards": synergy_cards[:7],  # Limit to 7 cards
    "formatted_text": formatted_response,  # Backward compatible
}
```

**Signal Handler** (`src/ui/handlers/signal_handlers.py:handle_synergy_signal`):
- Creates "Add [Card Name]" buttons with plus-circle icon
- Limits to 7 buttons max for UX
- Uses `get_display_name(card)` for printed_name support (OM1 cards)

**Action Callback** (`src/ui/actions/card_actions.py:on_add_suggested_card`):
- Validates session ID and card info from payload
- Checks for active deck (error if none)
- Adds 1 copy via `deck_repository.add_card_to_deck()`
- Updates sidebar and removes button on success
- Handles max copies exceeded error gracefully

### Quick Deck Load (Implemented)

**Tool Signal** (`src/agent/tools/deck_tools.py:list_decks`):
```python
# list_decks returns structured dict when decks exist
return {
    "has_decks": True,
    "decks": decks[:5],  # Limit to 5 decks
    "formatted_text": formatted_table,  # Backward compatible
}
```

**Signal Handler** (`src/ui/handlers/signal_handlers.py:handle_deck_list_signal`):
- Creates "Load [Deck Name]" buttons with folder-open icon
- Tooltip shows: "Format • Card Count • Color Identity"
- Limits to 5 buttons max

**Action Callback** (`src/ui/actions/deck_actions.py:on_quick_load_deck`):
- Loads deck via `deck_repository.get_deck_with_cards()`
- Sets active deck ID in session manager
- Auto-syncs format filter to deck format (or clears for "all" format)
- Updates sidebar and removes all quick-load buttons on success

### Card Disambiguation (Implemented)

**Tool Signal** (`src/agent/tools/card_lookup.py:lookup_card_by_name`):
```python
# Returns structured dict when 2-5 partial matches found
if 2 <= len(matches) <= 5:
    return {
        "needs_disambiguation": True,
        "matches": matches,
        "formatted_text": disambiguation_message,
    }
# Returns string for 1 match (exact) or 6+ matches (refine query)
```

**Context Detection** (`src/ui/app.py:detect_disambiguation_context`):
```python
def detect_disambiguation_context(user_message: str) -> str:
    """Detect user intent from message keywords."""
    add_keywords = ["add", "include", "put in", "put into"]
    message_lower = user_message.lower()
    for keyword in add_keywords:
        if keyword in message_lower:
            return "add"
    return "view"  # Default to view
```

**Signal Handler** (`src/ui/handlers/signal_handlers.py:handle_disambiguation_signal`):
- Detects context from user message
- View context: "[Card Name] (Type)" button with eye icon
- Add context: "Add [Card Name]" button with plus-circle icon
- Limits to 5 buttons (2-5 matches only)

**Action Callback** (`src/ui/actions/card_actions.py:on_select_card`):
- Extracts context from payload (defaults to "view")
- View path: Formats and displays card details with image
- Add path: Adds card to active deck, updates sidebar
- Removes all disambiguation buttons after selection

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-11-02 | Adopt Chainlit actions for UI interactions | Research confirms excellent fit with architecture |
| 2025-11-02 | Prioritize Phase 1 implementation | High impact, low risk, clear boundaries |
| 2025-11-02 | Maintain conversational-first model | Actions complement, not replace, natural language |
| 2025-11-02 | Limit actions to 7 per message | UX research shows clutter beyond this threshold |
| 2025-12-07 | Implement Phase 2 actions | Reduce friction in synergy/deck/disambiguation workflows |
| 2025-12-07 | Use context detection for disambiguation | Safer default (view), explicit add keywords required |
| 2025-12-07 | Auto-sync format filter on deck load | Prevents format mismatch errors after loading deck |

---

## Implementation Status

### Phase 1 (Completed)
1. ✅ Format filter selection buttons
2. ✅ Games filter selection buttons
3. ✅ Deck deletion confirmation
4. ✅ Search result pagination

### Phase 2 (Completed)
5. ✅ Synergy quick-add buttons
6. ✅ Quick deck load buttons
7. ✅ Card disambiguation actions
8. ✅ Context detection (view vs add)
9. ⏳ Integration tests (deferred)
10. ⏳ User testing and feedback collection

### Phase 3 (Planned)
11. ⏳ Sidebar card removal buttons
12. ⏳ Card quantity adjustment controls
13. ⏳ Deck templates/presets

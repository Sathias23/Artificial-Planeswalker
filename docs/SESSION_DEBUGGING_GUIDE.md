# Session State Debugging Guide

## Overview
This guide documents the logging instrumentation added to diagnose session state loss issues (Bug #82e10b66).

## Logging Added

### 1. SessionManager (src/agent/core.py)

#### `get_active_deck_id()`
- **Level**: DEBUG
- **Message**: `SessionManager.get_active_deck_id: session_id=%s, deck_id=%s, total_sessions=%d`
- **When**: Every time active deck ID is retrieved from session manager
- **Purpose**: Track if deck ID is persisting across messages

#### `set_active_deck_id()`
- **Level**: INFO
- **Message**: `SessionManager.set_active_deck_id: session_id=%s, deck_id=%s, total_sessions=%d`
- **When**: When a deck is created or loaded
- **Purpose**: Track when deck IDs are stored in session manager

#### `clear_active_deck_id()`
- **Level**: INFO
- **Message**: `SessionManager.clear_active_deck_id: session_id=%s, cleared_deck_id=%s, total_sessions=%d`
- **When**: When a deck is deleted or session is cleared
- **Purpose**: Track when and why deck IDs are removed

### 2. Dependency Creation (src/ui/app.py)

#### `get_agent_dependencies()` - Entry
- **Level**: INFO
- **Message**: `get_agent_dependencies: session_id=%s, format_filter=%s, active_deck_id=%s`
- **When**: At the start of each agent invocation, after retrieving session state
- **Purpose**: Verify session state is being retrieved correctly

#### `get_agent_dependencies()` - Exit
- **Level**: INFO
- **Message**: `Created agent dependencies: session_id=%s, active_deck_id=%s, active_deck_name=%s, format_filter=%s`
- **When**: After loading active deck from database
- **Purpose**: Confirm dependencies are created with correct state

### 3. Message Handler (src/ui/app.py)

#### `on_message()`
- **Level**: INFO
- **Message**: `on_message: message_id=%s, session_id=%s, user_input_length=%d`
- **When**: Every incoming user message
- **Purpose**: Track Chainlit session IDs and ensure consistency

### 4. Tool Invocation (src/agent/tools/deck_tools.py)

#### `add_card_to_deck()`
- **Level**: INFO
- **Message**: `add_card_to_deck: session_id=%s, card_name=%s, quantity=%d, active_deck=%s`
- **When**: Every time the tool is invoked
- **Purpose**: Verify tool receives correct deck state from dependencies

#### `add_card_to_deck()` - No Deck Warning
- **Level**: WARNING
- **Message**: `add_card_to_deck: No active deck for session_id=%s`
- **When**: When tool is called but no active deck exists
- **Purpose**: Track when and why "no active deck" errors occur

## How to Use This Logging

### Enable DEBUG Logging
Add to your Chainlit config or environment:
```bash
export LOG_LEVEL=DEBUG
```

Or in your logging configuration:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Trace a Session State Loss Issue

1. **Start with session ID tracking**: Look for `on_message` logs to see the session ID
   ```
   INFO on_message: message_id=abc123, session_id=340e30a8-7682-44bf-b0ba-fc957b748ea2, user_input_length=50
   ```

2. **Check if session manager has the deck ID**: Look for `get_active_deck_id` logs
   ```
   DEBUG SessionManager.get_active_deck_id: session_id=340e30a8..., deck_id=550e8400..., total_sessions=1
   ```

3. **Verify dependencies creation**: Look for `get_agent_dependencies` logs
   ```
   INFO get_agent_dependencies: session_id=340e30a8..., format_filter=standard, active_deck_id=550e8400...
   INFO Created agent dependencies: session_id=340e30a8..., active_deck_id=550e8400..., active_deck_name=Jurassic Park, format_filter=standard
   ```

4. **Track tool invocations**: Look for tool-specific logs
   ```
   INFO add_card_to_deck: session_id=340e30a8..., card_name=Huatli, quantity=2, active_deck=Jurassic Park
   ```

### Diagnosis Patterns

#### Pattern 1: Session ID Changed
**Symptom**: Different session_id between consecutive messages
**Logs**:
```
INFO on_message: session_id=abc-123 ...
INFO on_message: session_id=def-456 ...  # Different ID!
```
**Cause**: Chainlit session reset or browser refresh

#### Pattern 2: Deck ID Not in Session Manager
**Symptom**: `get_active_deck_id` returns None despite deck being created
**Logs**:
```
INFO SessionManager.set_active_deck_id: session_id=abc-123, deck_id=xyz-789 ...
DEBUG SessionManager.get_active_deck_id: session_id=abc-123, deck_id=None ...  # Lost!
```
**Cause**: Session manager instance not shared or session cleared

#### Pattern 3: Deck Deleted from Database
**Symptom**: Deck ID exists but deck not found
**Logs**:
```
INFO get_agent_dependencies: active_deck_id=xyz-789 ...
WARNING Active deck xyz-789 for session abc-123 not found, clearing stale ID
INFO SessionManager.clear_active_deck_id: session_id=abc-123, cleared_deck_id=xyz-789 ...
```
**Cause**: Deck was deleted from database but ID not cleared from session

#### Pattern 4: Tool Called Without Deck
**Symptom**: Tool invoked but reports no active deck
**Logs**:
```
INFO add_card_to_deck: session_id=abc-123, card_name=Huatli, quantity=2, active_deck=None
WARNING add_card_to_deck: No active deck for session_id=abc-123
```
**Cause**: Dependencies created without active deck (check previous patterns)

## Logfire Integration

These logs are automatically captured by Logfire when enabled. Search for:
- Span name: Contains tool names or "agent run"
- Attributes: Contains session_id, deck_id, etc.
- Message: Contains the log messages above

## Next Steps

If session state loss is detected:
1. Identify which pattern matches the issue
2. Check if session_id changes between messages (Pattern 1)
3. Verify session manager instance persistence (Pattern 2)
4. Check database for deck existence (Pattern 3)
5. Add more granular logging if needed

## Related Files
- `src/agent/core.py` - ConversationSessionManager
- `src/ui/app.py` - get_agent_dependencies, on_message
- `src/agent/tools/deck_tools.py` - Tool implementations
- `src/agent/dependencies.py` - AgentDependencies dataclass

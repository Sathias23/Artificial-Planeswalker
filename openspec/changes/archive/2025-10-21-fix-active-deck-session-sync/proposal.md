# Fix Active Deck Session Synchronization

## Why

Active deck context is lost between tool calls within the same agent run, causing "No active deck" errors when tools try to add cards or view decks immediately after creating or loading a deck.

**Root cause**: `AgentDependencies.active_deck_id` is a snapshot taken at the start of each agent run. When tools like `create_deck` or `load_deck` update the session manager with the new active deck ID, other tools in the SAME run still read the stale value from `deps.active_deck_id`.

**Example bug scenario**:
```
User: "Create a deck called Test and add Lightning Bolt"
  ↓
Agent Run Starts:
  - deps.active_deck_id = None (snapshot from session manager)

Tool 1: create_deck("Test")
  - Creates deck with ID "deck-123"
  - Updates: _session_manager.set_active_deck_id("deck-123") ✓
  - Does NOT update: deps.active_deck_id (still None) ✗

Tool 2: add_card_to_deck("Lightning Bolt")
  - Reads: deps.active_deck_id (still None) ✗
  - Returns: "No active deck" ❌
```

## What Changes

- Convert `AgentDependencies.active_deck_id` from a dataclass field to a `@property` that reads from the session manager in real-time
- Add private `_session_manager` reference to `AgentDependencies` to enable property access
- Remove `active_deck_id` parameter from `AgentDependencies.__init__()` signature
- Update `get_agent_dependencies()` to inject session manager reference instead of snapshot value

This ensures tools always read the current active deck ID from the session manager, preventing stale data issues.

## Impact

- **Affected specs**: `agent-core` (Session-Aware Agent Dependencies requirement)
- **Affected code**:
  - `src/agent/dependencies.py` - Add property and session manager reference
  - `src/ui/app.py:get_agent_dependencies()` - Pass session manager instead of snapshot
  - `src/agent/tools/deck_tools.py` - No changes needed (tools already use `deps.active_deck_id`)
- **Breaking changes**: None (property access is transparent to tool code)
- **Backward compatibility**: Full (external API unchanged)

## Research Summary

**Research conducted**: Archon RAG search for state management patterns in PydanticAI
- Source: `ai.pydantic.dev` (PydanticAI documentation)
- Finding: PydanticAI uses dataclass-based state management but allows custom property accessors
- Pattern: Python `@property` decorator enables transparent computed attributes

**Decision rationale**: Using a property provides the cleanest API (no code changes in tools) while ensuring consistency between session manager and dependencies.

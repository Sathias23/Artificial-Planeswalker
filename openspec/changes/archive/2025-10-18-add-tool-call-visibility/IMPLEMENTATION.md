# Tool Call Visibility - Implementation Summary

## What Was Implemented

Implemented visual feedback for PydanticAI tool calls using Chainlit's Step API, providing users with transparency into what operations the AI agent is performing.

## Changes Made

### 1. New File: `src/ui/tool_steps.py`

Created a new module with helper functions for tool call visualization:

- **`format_tool_params(tool_name, args)`**: Formats tool parameters for readable display in Steps
  - Handles dict, JSON string, and None arguments
  - Omits None values, quotes strings, formats lists/dicts compactly

- **`format_tool_result_summary(tool_name, result)`**: Creates brief summaries of tool results
  - Extracts card names from formatted output
  - Counts cards found ("Found 3 cards")
  - Shows "No results found" for empty results

- **`extract_tool_calls(messages)`**: Parses PydanticAI message history to find tool calls
  - Scans ModelResponse messages for ToolCallPart instances
  - Returns structured info: tool_name, tool_call_id, args

- **`get_friendly_tool_name(tool_name)`**: Converts technical names to user-friendly labels
  - `lookup_card_by_name` → "Looking up card"
  - `search_cards_advanced` → "Searching cards"
  - `set_format_filter` → "Setting format filter"

### 2. Modified: `src/agent/core.py`

**Changed `run_agent_with_session()` return type:**
- **Before**: Returned `str` (just the agent's text response)
- **After**: Returns full `AgentRunResult` object with `.output` and `.all_messages()`
- **Reason**: UI layer needs access to message history to extract tool call information
- **Breaking change**: Minor - UI layer updated to use `result.output` instead of direct string

### 3. Modified: `src/ui/app.py`

**Updated `on_message` handler:**
1. Calls `run_agent_with_session()` and receives full result object
2. Extracts tool calls from `result.all_messages()` using `extract_tool_calls()`
3. Creates a Chainlit Step for each tool call:
   - Step type: `"tool"` (Chainlit displays with special styling)
   - Step name: Friendly tool name (e.g., "Looking up card")
   - Step input: Formatted parameters
   - Step output: "Tool executed" (MVP - future: match with actual results)
4. Streams response text from `result.output` to user
5. Attaches UI elements (card images) as before

## Architecture Compliance

✅ **No Chainlit imports in agent layer** - Verified with grep
- All Step creation logic is in `src/ui/` module
- Agent layer remains UI-framework agnostic
- Tool visibility is purely a UI concern

## Code Quality

✅ **Linting**: Ruff passes with auto-fix
✅ **Type checking**: Mypy passes (with one `type: ignore` for inferred return type)
✅ **Formatting**: Ruff format applied
✅ **Tests**: All existing unit tests pass (95 tests)

## What Works (MVP)

1. **Tool call detection**: System successfully detects when agent uses tools
2. **Step creation**: Creates one Step per tool call with tool icon/badge
3. **Parameter display**: Shows tool parameters in readable format
4. **Tool identification**: Displays user-friendly tool names
5. **Architecture separation**: No coupling between UI and agent layers

## Known Limitations (Future Enhancements)

1. **No result matching**: Steps currently show "Tool executed" instead of actual tool result
   - **Reason**: Need to match ToolCallPart with ToolReturnPart in message history
   - **Task**: See tasks.md section 4.1 - "Result Summary Helper"

2. **No streaming/real-time status**: Steps appear after agent execution completes
   - **Reason**: MVP uses post-execution message parsing, not live streaming
   - **Future**: Use PydanticAI streaming API for real-time Step updates

3. **Steps appear all at once**: Not progressive during tool execution
   - **Reason**: Steps are created after `agent.run()` completes
   - **Future**: Hook into PydanticAI execution lifecycle for real-time updates

## Testing Performed

- ✅ Code linting and formatting (ruff)
- ✅ Type checking (mypy)
- ✅ Architecture compliance (grep for Chainlit imports)
- ✅ Unit tests (95 tests passing)
- ⏳ Manual UI testing (requires running Chainlit app)

## Manual Testing Instructions

### Prerequisites
```bash
# Ensure database is populated
uv run python scripts/import_scryfall_data.py

# Start Chainlit app
uv run chainlit run src/ui/app.py
```

### Test Scenarios

1. **Single card lookup**
   - User: "Show me Lightning Bolt"
   - Expected: See Step labeled "Looking up card" with parameter `card_name="Lightning Bolt"`

2. **Card search with filters**
   - User: "Find red creatures with haste under 4 mana"
   - Expected: See Step labeled "Searching cards" with color/type/mana parameters

3. **Format filter**
   - User: "Only show me Standard-legal cards"
   - Expected: See Step labeled "Setting format filter" with parameter `format="standard"`

4. **Multi-tool conversation**
   - User: "Set format to Standard, then find all blue counterspells"
   - Expected: See two Steps - one for set_format_filter, one for search_cards_advanced

5. **Verify Step styling**
   - Check: Steps appear with "tool" type icon/badge
   - Check: Steps are collapsible (Chainlit default)
   - Check: Parameters are readable (not raw JSON dumps)

## Rollback Plan

If issues arise:
1. Revert `src/ui/app.py` changes (lines 203-220)
2. Revert `src/agent/core.py` return type change (line 321: return `result.output` instead of `result`)
3. Delete `src/ui/tool_steps.py`

No database or data layer changes - safe to rollback.

## Next Steps

To complete the full feature per `tasks.md`:

1. **Implement result matching** (tasks.md section 4)
   - Parse message history to find ToolReturnPart for each ToolCallPart
   - Use `format_tool_result_summary()` to show actual results

2. **Add error handling** (tasks.md section 5)
   - Wrap Step creation in try/except
   - Show error Steps when tools fail

3. **Performance testing** (tasks.md section 9)
   - Measure Step creation overhead
   - Test with 5+ tool calls in single turn

4. **Documentation** (tasks.md section 8)
   - Update CLAUDE.md with Step pattern
   - Add code comments explaining Step wrapper approach

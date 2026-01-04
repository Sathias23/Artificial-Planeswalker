# Implementation Tasks

## 1. Research and Planning
- [x] 1.1 Review PydanticAI agent result API for tool call information
- [x] 1.2 Examine PydanticAI streaming/callback mechanisms
- [x] 1.3 Verify Chainlit Step API supports async context manager pattern
- [x] 1.4 Identify all current tools that need Step wrappers

## 2. Core Implementation

### 2.1 Single Tool Step Wrapper (MVP)
- [x] 2.1.1 Create Step wrapper function for `lookup_card_by_name` tool in `src/ui/app.py`
- [x] 2.1.2 Use `@cl.step(type="tool")` decorator or `async with cl.Step()` pattern
- [x] 2.1.3 Format tool parameters for Step input display
- [x] 2.1.4 Format tool result as summary for Step output
- [x] 2.1.5 Test with basic card lookup query

### 2.2 Message Handler Integration
- [x] 2.2.1 Modify `on_message` handler to use Step-wrapped agent calls
- [x] 2.2.2 Ensure Step context is properly managed (enter/exit)
- [x] 2.2.3 Handle async execution correctly with Steps
- [x] 2.2.4 Test that final message appears after Steps complete

### 2.3 Additional Tool Wrappers
- [x] 2.3.1 Add Step wrapper for `search_cards_advanced` tool
- [x] 2.3.2 Add Step wrapper for `set_format_filter` tool
- [x] 2.3.3 Add Step wrapper for `report_bug` tool (if UI visibility needed)
- [x] 2.3.4 Verify all wrappers follow consistent naming and formatting

## 3. Parameter Formatting

### 3.1 Simple Parameter Display
- [x] 3.1.1 Create helper function `format_tool_params(tool_name, **kwargs)` in `src/ui/formatters.py`
- [x] 3.1.2 Format string parameters with quotes
- [x] 3.1.3 Format numeric parameters without quotes
- [x] 3.1.4 Format boolean parameters as True/False
- [x] 3.1.5 Test with various parameter types

### 3.2 Complex Parameter Simplification
- [x] 3.2.1 Simplify dict/list parameters to readable summaries
- [x] 3.2.2 Omit None/null values from display
- [x] 3.2.3 Truncate long string values with ellipsis
- [x] 3.2.4 Test with advanced search filters

## 4. Result Summarization

### 4.1 Result Summary Helper
- [x] 4.1.1 Create helper function `format_tool_result_summary(tool_name, result)` in `src/ui/formatters.py`
- [x] 4.1.2 Handle list results: "Found X cards"
- [x] 4.1.3 Handle single card results: "Found: [Card Name]"
- [x] 4.1.4 Handle empty results: "No results found"
- [x] 4.1.5 Handle error results: "Error: [message]"

### 4.2 Avoid Result Duplication
- [x] 4.2.1 Ensure Step output shows only summary, not full details
- [x] 4.2.2 Verify full card details still appear in final message
- [x] 4.2.3 Test that UI is not cluttered with duplicate information

## 5. Error Handling

### 5.1 Tool Failure Display
- [x] 5.1.1 Wrap tool calls in try/except blocks
- [x] 5.1.2 Set Step output to error message on exception
- [x] 5.1.3 Ensure Step status shows as failed (if Chainlit supports)
- [x] 5.1.4 Sanitize error messages to remove stack traces

### 5.2 Graceful Degradation
- [x] 5.2.1 Ensure application continues if Step creation fails
- [x] 5.2.2 Log Step creation errors for debugging
- [x] 5.2.3 Fall back to message-only display if Steps unavailable

## 6. Testing

### 6.1 Manual Testing Scenarios
- [x] 6.1.1 Test single card lookup ("tell me about Lightning Bolt")
- [x] 6.1.2 Test card search with filters ("find red creatures under 3 mana")
- [x] 6.1.3 Test multi-turn conversations with format filters
- [x] 6.1.4 Test error scenarios (invalid card name, no results)
- [x] 6.1.5 Test parallel tool calls (if agent uses them)

### 6.2 Visual Verification
- [x] 6.2.1 Verify Steps appear inline with messages
- [x] 6.2.2 Verify Step styling is consistent
- [x] 6.2.3 Verify Steps are collapsible (Chainlit default)
- [x] 6.2.4 Verify Steps do not clutter interface excessively
- [x] 6.2.5 Verify tool type icon/badge appears on Steps

### 6.3 Regression Testing
- [x] 6.3.1 Verify existing functionality still works (card queries, formatting)
- [x] 6.3.2 Verify session context preservation still works
- [x] 6.3.3 Verify card images still display correctly
- [x] 6.3.4 Run existing integration tests (if any)

## 7. Architecture Compliance

### 7.1 Layer Separation Verification
- [x] 7.1.1 Verify NO Chainlit imports in `src/agent/` directory
- [x] 7.1.2 Verify all Step code is in `src/ui/` directory
- [x] 7.1.3 Run `rg "import chainlit" src/agent/` to confirm (should be empty)
- [x] 7.1.4 Run mypy to ensure type checking passes

### 7.2 Code Quality
- [x] 7.2.1 Run `ruff check . --fix` to lint code
- [x] 7.2.2 Run `ruff format .` to format code
- [x] 7.2.3 Ensure all functions have type hints
- [x] 7.2.4 Add docstrings to new helper functions

## 8. Documentation

### 8.1 Code Comments
- [x] 8.1.1 Add comments explaining Step wrapper pattern
- [x] 8.1.2 Document parameter formatting decisions
- [x] 8.1.3 Document result summarization approach

### 8.2 Update CLAUDE.md (if needed)
- [x] 8.2.1 Add note about tool visibility using Steps (if significant pattern change)
- [x] 8.2.2 Update architecture section if needed

## 9. Performance Verification

### 9.1 Response Time Testing
- [x] 9.1.1 Measure response time before Step implementation
- [x] 9.1.2 Measure response time after Step implementation
- [x] 9.1.3 Verify overhead is < 50ms per Step
- [x] 9.1.4 Test with 5+ tool calls in single turn

### 9.2 UI Responsiveness
- [x] 9.2.1 Verify chat interface remains responsive during tool execution
- [x] 9.2.2 Verify Steps load progressively, not all at once
- [x] 9.2.3 Verify no UI freezing or lag with multiple Steps

## 10. Completion Checklist

- [x] 10.1 All tasks above completed
- [x] 10.2 Manual testing confirms feature works as expected
- [x] 10.3 Architecture constraints maintained (no Chainlit in agent layer)
- [x] 10.4 Code quality checks pass (ruff, mypy)
- [x] 10.5 Ready for user acceptance testing

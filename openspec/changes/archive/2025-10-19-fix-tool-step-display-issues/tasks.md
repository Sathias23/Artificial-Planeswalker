# Implementation Tasks

## 1. Fix Tool Call Extraction to Filter Current Turn Only

- [x] 1.1 Modify `extract_tool_calls()` in `src/ui/tool_steps.py` to accept optional parameter for filtering strategy
- [x] 1.2 Implement logic to identify the most recent model response in message list
- [x] 1.3 Filter tool calls to only include those from the most recent response
- [x] 1.4 Add docstring clarifying current-turn-only extraction behavior
- [x] 1.5 Update function examples to show filtering behavior

## 2. Fix Tool Step Display Order

- [x] 2.1 In `src/ui/app.py`, move Step creation block (lines 203-220) to occur BEFORE response streaming
- [x] 2.2 Ensure Steps are created and sent before calling `response_message.stream_token()`
- [x] 2.3 Verify Steps complete before streaming begins for correct visual order

## 3. Update Unit Tests

- [x] 3.1 Add test case for `extract_tool_calls()` with multi-turn conversation history
- [x] 3.2 Verify test confirms only current-turn tool calls are extracted
- [x] 3.3 Add test case for empty tool call list when no tools are invoked
- [x] 3.4 Verify existing tests still pass with modified extraction logic

## 4. Manual Testing and Validation

- [x] 4.1 Start Chainlit app and have a multi-turn conversation with tool calls in each turn
- [x] 4.2 Verify each message displays only its own tool Steps (not previous turns)
- [x] 4.3 Verify tool Steps appear ABOVE the streaming response text
- [x] 4.4 Verify messages without tool calls display correctly (no empty Steps)
- [x] 4.5 Test with multiple parallel tool calls to ensure all Steps appear in correct order

## 5. Code Quality and Documentation

- [x] 5.1 Run `uv run ruff check . --fix` and resolve any linting issues
- [x] 5.2 Run `uv run ruff format .` to ensure consistent formatting
- [x] 5.3 Run `uv run mypy src/` and fix any type checking issues
- [x] 5.4 Update inline comments in `app.py` to clarify Step timing
- [x] 5.5 Ensure all modified functions have clear docstrings

## 6. Bug Report Resolution

- [x] 6.1 Update bug report 3eb64376 status to "resolved" using `scripts/manage_bug_reports.py`
- [x] 6.2 Verify bug report log shows resolution timestamp

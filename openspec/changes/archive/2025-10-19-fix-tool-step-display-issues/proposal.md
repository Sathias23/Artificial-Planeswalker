# Fix Tool Step Display Issues

## Why

Bug report 3eb64376 identifies two critical UI/UX issues with tool call visibility in the Chainlit chat interface:

1. **Historical tool call pollution**: Tool calls from previous conversation turns are being displayed alongside current tool calls, cluttering the chat history and confusing users about which tools were called for the current response.

2. **Incorrect visual ordering**: Tool call Steps appear below the streaming agent response instead of above it, creating an illogical flow where users see the answer before understanding what data was queried to produce that answer.

These issues significantly degrade user experience and reduce the transparency value of tool call visibility.

## What Changes

- **MODIFIED**: Tool call extraction logic to filter only tool calls from the most recent agent turn, preventing display of historical tool calls
- **MODIFIED**: Step creation timing to occur before response streaming, ensuring tool Steps appear above the agent response
- **MODIFIED**: Requirements in chainlit-ui spec to clarify tool Step display expectations and constraints

## Impact

- **Affected specs**: `chainlit-ui` (Tool Call Visibility with Chainlit Steps requirement)
- **Affected code**:
  - `src/ui/app.py` (on_message handler - lines 203-230)
  - `src/ui/tool_steps.py` (extract_tool_calls function - lines 142-189)
- **User-visible changes**: Tool Steps will only display for the current response and will appear above (not below) the agent's text response
- **Breaking changes**: None - this is a bug fix that restores intended behavior

# Tool Call Visibility in UI

## Why

Users currently cannot see what tool calls the agent is executing behind the scenes. When the agent searches for cards or performs other operations, multiple PydanticAI tool calls happen, but nothing is reflected in the UI. This creates a "black box" experience where users don't understand:

- What queries are being executed
- What parameters are being used
- Why certain results are returned
- How to debug unexpected behavior

This lack of transparency reduces user trust and makes it difficult to refine queries or understand the system's behavior.

**Bug Report Reference**: `b12e6634-9c79-4009-81a0-6d123e6fadef`

## What Changes

Add visual feedback for PydanticAI tool calls using Chainlit's `cl.Step` API to display:
- Tool name being called (e.g., "Searching cards", "Looking up card by name")
- Tool parameters/inputs (e.g., query filters, card name)
- Tool execution status (running, completed, failed)
- Tool outputs when relevant

This provides real-time transparency into agent operations without requiring code changes to existing tools.

## Impact

### Affected Specs
- `chainlit-ui` - Add requirements for tool call visualization using `cl.Step`

### Affected Code
- `src/ui/app.py` - Wrap agent tool calls with Chainlit Steps
- `src/agent/core.py` - May need hooks or callbacks for tool execution events (if not using decorator pattern)
- Agent tools (`src/agent/tools/`) - Potentially wrap individual tools with `@cl.step` decorator

### User Experience Impact
- **Positive**: Users can see what the agent is doing in real-time
- **Positive**: Better debugging and query refinement
- **Positive**: Increased trust and transparency
- **Neutral**: Slightly more visual clutter in chat (but configurable)

## Research Sources

### Chainlit Step API (docs.chainlit.io)
- `cl.Step` class for context manager pattern
- `@cl.step` decorator for function wrapping
- Step properties: `name`, `type`, `input`, `output`, `show_input`
- Step types include `"tool"` for tool calls
- Supports nested steps and streaming output

### PydanticAI Tool Execution
- Tools defined with `@agent.tool` decorator
- Parallel tool calls executed via `asyncio.create_task`
- Tool results returned to agent for processing
- No built-in UI visibility features

## Alternative Approaches Considered

1. **Log-based visibility**: Show tool calls in a separate log panel
   - **Rejected**: Less integrated with chat flow, requires additional UI components

2. **Message annotations**: Add tool info as metadata to messages
   - **Rejected**: Less visible, harder to parse visually

3. **Custom UI components**: Build proprietary tool visualization
   - **Rejected**: Reinvents Chainlit's built-in capabilities

4. **Chainlit Steps (SELECTED)**: Use `cl.Step` for integrated tool visibility
   - Native Chainlit feature designed for this exact use case
   - Minimal code changes required
   - Consistent with Chainlit best practices

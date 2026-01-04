# Tool Call Visibility Design

## Context

The application uses PydanticAI agents with tool capabilities for card queries. Tools are defined in `src/agent/tools/` and registered with the agent. When users send messages, the agent may invoke one or more tools to gather information before responding. Currently, these tool executions are invisible to users.

Chainlit provides a `Step` concept specifically designed for showing intermediate operations in the UI. We need to integrate PydanticAI tool calls with Chainlit Steps without violating the architecture constraint that the agent layer must not import Chainlit.

## Goals

- Display tool calls visually in the Chainlit UI
- Show tool name, parameters, and results
- Maintain agent layer independence from UI framework
- Support both single and parallel tool calls
- Minimal changes to existing tool implementations

## Non-Goals

- Modifying PydanticAI's tool execution internals
- Building custom visualization components
- Tracking tool performance metrics (future enhancement)
- Showing tool calls in non-Chainlit UIs (out of scope for MVP)

## Decisions

### Decision 1: Use Wrapper Functions in UI Layer

**Choice**: Wrap PydanticAI tools with Chainlit Step decorators at the UI layer, not in the agent layer.

**Rationale**:
- Maintains agent layer independence (no Chainlit imports in `src/agent/`)
- Allows agent to be tested without UI dependencies
- Keeps UI concerns in UI layer where they belong
- Minimal changes to existing tool code

**Implementation**:
```python
# src/ui/app.py
@cl.step(type="tool", name="Card Lookup")
async def lookup_card_wrapper(name: str, deps: AgentDependencies):
    """Wrapper to add Step visibility to card lookup tool."""
    # The actual tool is called through the agent
    # The step just provides UI visibility
    return await agent.run(...)
```

**Alternative Considered**: Modify tools directly with `@cl.step`
- Rejected: Violates architecture (agent imports Chainlit)
- Rejected: Makes tools UI-framework dependent

### Decision 2: Hook into Agent Run Lifecycle

**Choice**: Use PydanticAI's result streaming or callback mechanisms (if available) to trigger Step creation per tool call.

**Rationale**:
- Allows automatic Step creation for any tool call
- Doesn't require manual wrapping of each tool
- Maintains single source of truth for tool definitions

**Implementation Approach**:
1. Research PydanticAI's `agent.run()` return type and streaming capabilities
2. Check if PydanticAI exposes tool call events during execution
3. If available, subscribe to tool call events and create Steps dynamically
4. If not available, fall back to wrapping individual tool functions

**Open Question**: Does PydanticAI provide tool execution hooks or callbacks?
- Need to verify in PydanticAI documentation
- May require examining agent result objects for tool call history

### Decision 3: Step Content Format

**Choice**: Display tool name, simplified parameters, and result summary in Steps.

**Format**:
```
Step name: "Looking up card: Lightning Bolt"
Step input: "name='Lightning Bolt'"
Step output: "Found 1 card"
```

**Rationale**:
- Concise and scannable
- Shows essential information without overwhelming users
- Parameters simplified to avoid JSON dumps in UI
- Results summarized (not full card data, which appears in final message)

**Configuration**:
- `show_input=True` to display parameters
- `type="tool"` to identify as tool call
- Use async context manager pattern for automatic status updates

### Decision 4: Parallel Tool Call Handling

**Choice**: Create separate Steps for parallel tool calls, displayed as siblings.

**Rationale**:
- Chainlit Steps support parallel execution naturally
- Users can see multiple operations happening simultaneously
- Aligns with PydanticAI's `asyncio.create_task` behavior

**Implementation**:
```python
# When agent runs multiple tools in parallel
async with cl.Step(name="Search cards") as step1:
    ...
async with cl.Step(name="Get mana curve") as step2:
    ...
# Both appear in UI simultaneously
```

## Risks / Trade-offs

### Risk: Performance Overhead
- **Impact**: Step creation adds small overhead per tool call
- **Likelihood**: Low (Chainlit Steps are lightweight)
- **Mitigation**: Benchmark with multiple tool calls; if needed, add toggle to disable Steps

### Risk: UI Clutter
- **Impact**: Too many Steps could clutter chat interface
- **Likelihood**: Medium (depends on tool call frequency)
- **Mitigation**: Use collapsible Steps (Chainlit default); consider Step grouping

### Trade-off: Agent Layer Complexity vs UI Coupling
- **Decision**: Keep agent simple, add complexity in UI layer
- **Rationale**: UI changes more frequently than core logic; better to isolate UI concerns
- **Consequence**: UI layer has more responsibility for visualization logic

### Risk: Architecture Constraint Violation
- **Impact**: Accidentally importing Chainlit in agent layer
- **Likelihood**: Low (tooling can catch this)
- **Mitigation**: Add import linter rule or test to prevent Chainlit imports outside `src/ui/`

## Migration Plan

### Phase 1: Single Tool Visibility (MVP)
1. Add Step wrapper for `lookup_card_by_name` tool
2. Test with basic card queries
3. Verify Steps appear correctly in UI

### Phase 2: All Tool Visibility
1. Add Step wrappers for remaining tools:
   - `search_cards_advanced`
   - `set_format_filter`
   - `report_bug`
2. Test with multi-tool conversations

### Phase 3: Parallel Tool Support
1. Test agent scenarios with parallel tool calls
2. Verify Steps appear as siblings (not nested)
3. Ensure proper async handling

### Rollback Plan
If Steps cause issues:
1. Remove `@cl.step` decorators from UI layer
2. Return to original message handler implementation
3. No agent layer changes required (no rollback needed there)

## Open Questions

1. **PydanticAI Tool Hooks**: Does PydanticAI expose tool execution events we can subscribe to?
   - **Action**: Review PydanticAI docs on agent results and streaming
   - **Assignee**: Developer implementing this change

2. **Step Configuration**: Should Steps be collapsible by default, or always expanded?
   - **Action**: Test both modes with real user scenarios
   - **Decision**: Default to collapsible to reduce clutter

3. **Error Handling**: How should failed tool calls appear in Steps?
   - **Action**: Test error scenarios and decide on error visualization
   - **Decision**: Steps should show error state with message

4. **Step Nesting**: Should tool calls inside other operations be nested Steps?
   - **Action**: Defer to Phase 3 (out of MVP scope)
   - **Decision**: MVP uses flat Steps; nesting is future enhancement

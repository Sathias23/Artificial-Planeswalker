# Integrate PydanticAI Agent with Chainlit - Story 3.2

## Why

Users need to interact with the PydanticAI agent through the Chainlit chat interface to ask card-related questions and receive AI-powered responses. Currently, the Chainlit UI only provides basic echo functionality (Story 3.1). This change connects the agent layer to the UI layer, enabling end-to-end conversational card queries using the local database and agent tools built in Epics 1-2.

## What Changes

- Integrate PydanticAI agent invocation within Chainlit message handlers
- Stream agent responses back to the Chainlit chat interface
- Enable agent tool execution (card queries) from Chainlit context
- Implement error handling that displays user-friendly messages in chat for agent failures
- Maintain conversation context across multiple messages within a chat session
- Add integration tests verifying end-to-end Chainlit → Agent → Database flow

This change enhances the existing `chainlit-ui` capability with agent integration and adds agent invocation requirements to the `agent-core` capability.

## Impact

- **Affected capabilities**: `chainlit-ui` (MODIFIED), `agent-core` (ADDED requirements for UI integration)
- **Affected code**:
  - `src/ui/app.py` - Message handlers will invoke agent instead of echoing
  - `src/agent/core.py` - May need helper functions for Chainlit integration
  - New integration tests in `tests/integration/` for end-to-end flow
- **Dependencies**: Builds on Story 3.1 (basic Chainlit setup) and Epic 2 (PydanticAI agent with tools)
- **Architecture**: Completes the connection between UI and Agent layers while maintaining separation (agent layer does NOT import Chainlit)
- **User experience**: Enables first functional user-facing feature - conversational card queries
- **Testing**: Integration tests required for full stack validation (Chainlit → Agent → Tools → Database)

## Notes

This is Story 3.2 from Epic 3 (Chainlit Chat Interface Integration). This builds directly on Story 3.1 (basic Chainlit setup) by replacing the echo handler with actual agent invocations. The implementation must maintain architectural separation - the agent layer remains independently testable and does not import Chainlit.

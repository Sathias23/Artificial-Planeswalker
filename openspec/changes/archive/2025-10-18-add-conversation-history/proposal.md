# Add Conversation History Support

## Why

The agent currently has no memory between messages within a chat session. When users refer to previously discussed cards or concepts (e.g., "what set is it from?" after discussing Bloodhall Ooze), the agent cannot recall the context and asks for clarification. This breaks the conversational flow and creates a poor user experience.

**Example Failure**:
```
User: Tell me about Bloodhall Ooze
Agent: [Provides detailed card information]

User: What set is it from?
Agent: I'd be happy to help you find out what set a card is from!
       However, I need to know which card you're asking about...
```

The agent should remember the conversation context and provide the set information directly.

## What Changes

- Add session-based message history management to the agent layer
- Implement agent-side history storage using session IDs (in-memory dict for MVP)
- Update UI to pass session IDs to agent invocations (using Chainlit's session.id)
- Integrate PydanticAI's native message history support in agent invocations
- Implement intelligent history size management using PydanticAI history processors
- Ensure proper handling of tool call pairing in message history
- Add conversation continuity tests

This change enhances the `agent-core` capability with session management and message history storage, and modifies the `chainlit-ui` capability to pass session identifiers to the agent.

## Impact

- **Affected capabilities**: `agent-core` (MODIFIED - adds session management), `chainlit-ui` (MODIFIED - passes session IDs)
- **Affected code**:
  - `src/agent/core.py` - Add session manager class and history processor (~80 lines)
  - `src/ui/app.py` - Pass session ID to agent invocations (~5 lines)
  - `tests/unit/agent/` - New tests for session manager
  - `tests/integration/ui/` - New tests for context preservation
- **Performance**: +100-500ms latency per request, +2,000-10,000 tokens per request (within budget)
- **Memory**: Negligible (~10KB per session for 20 messages)
- **User experience**: Enables natural follow-up questions and contextual conversations
- **Dependencies**: Builds on existing Chainlit UI setup (Story 3.1)

## Notes

- Uses PydanticAI's built-in message history support (`result.all_messages()` and `message_history` parameter)
- History processors ensure tool call/return pairing remains intact
- MVP targets in-memory session history (no persistence across sessions)
- Future enhancements: persistent history, conversation summaries, multi-session context

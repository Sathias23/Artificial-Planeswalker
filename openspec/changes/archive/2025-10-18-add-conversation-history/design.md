# Design Document - Conversation History

## Context

The Artificial-Planeswalker agent currently has no memory between messages, requiring users to repeat context in every message. This change implements conversation memory using PydanticAI's native message history support and Chainlit's session management.

**Background**:
- PydanticAI provides built-in message history via `message_history` parameter and `result.all_messages()`
- Chainlit provides session storage via `cl.user_session` that persists for session duration
- Message history includes user prompts, agent responses, tool calls, and tool returns
- Unbounded history growth can cause token budget and latency issues

**Constraints**:
- Must maintain UI/Agent layer separation (no Chainlit imports in agent layer)
- Must work with all OpenRouter models (Claude, GPT, Gemini)
- Must handle tool call pairing correctly to avoid LLM errors
- MVP: In-memory only (no persistence across sessions)

**Stakeholders**:
- End users: Better conversation UX with natural follow-ups
- Developers: Clear pattern for message history management
- Infrastructure: Token budget and latency implications

## Goals / Non-Goals

**Goals**:
- Enable contextual follow-up questions within a session
- Prevent unbounded memory and token growth
- Maintain proper tool call/return pairing
- Keep latency increase under 1 second per message
- Support session isolation (no context leakage between users)

**Non-Goals**:
- Persistent history across sessions (future enhancement)
- Conversation summaries or compression (future enhancement)
- Multi-session context ("remember from last week") (future enhancement)
- Custom message filtering or editing (use PydanticAI's API as-is)

## Decisions

### Decision 1: Use PydanticAI Native Message History API

**What**: Use `result.all_messages()` and `message_history` parameter instead of custom message tracking.

**Why**:
- PydanticAI handles message serialization/deserialization automatically
- Ensures compatibility across different LLM providers
- Includes all message types (prompts, responses, tool calls/returns)
- Reduces custom code and potential bugs

**Alternatives considered**:
- Custom message tracking: More control but duplicates PydanticAI functionality and requires manual serialization
- Store only text messages: Simpler but loses tool call context and breaks multi-turn tool interactions

**Trade-offs**: Couples implementation to PydanticAI's API structure, but this is already a core dependency.

### Decision 2: Use History Processors for Size Management

**What**: Implement `keep_recent_messages` history processor registered with Agent.

**Why**:
- Automatic execution before each agent invocation
- Clean separation of concerns (processor vs application logic)
- PydanticAI guarantees proper message structure after processing
- Handles tool call pairing automatically

**Alternatives considered**:
- Manual slicing before agent.run(): More explicit but error-prone with tool call pairing
- Dynamic limits based on token count: More sophisticated but adds complexity without clear MVP benefit

**Trade-offs**: Less control over exact slicing behavior, but safer and cleaner.

### Decision 3: Fixed History Limit of 10 Messages (5 Exchanges)

**What**: Keep last 10 messages (approximately 5 user-agent exchanges) plus system messages.

**Why**:
- Covers typical conversation depth for card queries
- Token budget: ~2,000-10,000 tokens (well under 200k context window)
- Latency: ~100-500ms increase is acceptable
- Simple, predictable behavior

**Alternatives considered**:
- 20 messages (10 exchanges): More context but higher latency/cost with diminishing returns
- Dynamic limit based on token count: More optimal but adds complexity and unpredictability
- No limit: Unbounded growth leads to performance degradation

**Trade-offs**: May lose early context in very long conversations, but users can start new sessions.

### Decision 4: Agent-Managed Session Storage

**What**: Implement `ConversationSessionManager` class in agent layer with in-memory dict storage keyed by session ID.

**Why**:
- UI-agnostic: Works with Chainlit, REST API, CLI, or any future interface
- Proper separation: Agent owns conversation state, UI only manages session identity
- Reusable: Same session manager works across different UIs
- Testable: Can test session management independently of UI framework

**Alternatives considered**:
- Store in cl.user_session: Simpler MVP but couples history to Chainlit, not reusable
- Database storage: Better for persistence but over-engineering for MVP
- Separate session service: Cleanest but adds complexity without clear MVP benefit

**Trade-offs**: Slightly more code (~50 lines for session manager) but much better architecture.

### Decision 5: No Message Filtering or Transformation

**What**: Store all messages from `result.all_messages()` without filtering or modification.

**Why**:
- Preserves complete conversation context
- Ensures tool call pairing integrity
- Simplifies implementation and reduces bug surface
- PydanticAI handles message structure validation

**Alternatives considered**:
- Filter out error messages: Cleaner history but loses error context for recovery
- Remove failed tool calls: Simpler history but agent can't learn from failures
- Custom message transformation: More control but high complexity and risk of breaking LLM compatibility

**Trade-offs**: History includes errors and failed attempts, but this provides richer context.

## Risks / Trade-offs

### Risk: Tool Call Pairing Errors
**Description**: Incorrectly slicing history could separate tool calls from returns, causing LLM errors.

**Mitigation**:
- Use PydanticAI history processors (automatic pairing preservation)
- Add integration tests specifically for tool call scenarios
- Document pairing requirements in code comments

### Risk: Token Budget Overruns
**Description**: Long conversations could exceed expected token usage.

**Mitigation**:
- Fixed 10-message limit provides predictable upper bound
- Monitor token usage in production logs
- Document token budget assumptions for future tuning

### Risk: Latency Increase
**Description**: Passing history adds 100-500ms per request.

**Mitigation**:
- 10-message limit keeps latency under 500ms
- Acceptable for conversational interface (not real-time)
- Future: Implement streaming responses to mask latency

### Risk: Session Storage Limitations
**Description**: Chainlit session storage might have size or lifecycle limitations.

**Mitigation**:
- 10-message limit keeps session data under 10KB (negligible)
- Chainlit handles session lifecycle automatically
- Document session assumptions for future scaling

### Trade-off: No Cross-Session Persistence
**Description**: Users lose context when starting a new session.

**Acceptance Rationale**:
- MVP prioritizes simple, working implementation
- Future enhancement can add database persistence
- Most card queries are self-contained conversations
- Users can work around by keeping session active

## Migration Plan

**Phase 1: Implementation** (Current Change)
1. Add message history storage to UI layer (app.py)
2. Add history processor to agent core
3. Add unit and integration tests
4. Deploy and monitor token usage and latency

**Phase 2: Monitoring** (Post-Deployment)
1. Monitor Chainlit session lifecycle behavior
2. Track token usage and latency metrics
3. Gather user feedback on context retention
4. Identify edge cases or failure modes

**Phase 3: Future Enhancements** (Later Changes)
1. Add database persistence for cross-session history
2. Implement conversation summaries for token efficiency
3. Add user controls (clear history, export conversation)
4. Explore semantic search over conversation history

**Rollback Plan**:
- Remove `message_history` parameter from agent.run() calls
- Remove history storage from cl.user_session
- Remove history processor from agent configuration
- Revert to stateless message handling

**Deployment Strategy**:
- No database migrations required (in-memory only)
- Backward compatible (history parameter is optional)
- Can deploy without feature flag (graceful degradation)

## Open Questions

### Q1: Should we preserve system messages across truncation?
**Answer**: Yes - include logic to preserve initial system prompt when truncating to maintain agent behavior consistency.

### Q2: How to handle very long tool results in history?
**Answer**: For MVP, include complete tool results. Future enhancement: truncate or summarize long tool results.

### Q3: Should error messages be included in history?
**Answer**: Yes - include all messages to provide complete context. Agent can learn from errors and avoid repeated mistakes.

### Q4: What happens on Chainlit session timeout?
**Answer**: Chainlit clears session automatically on disconnect. No action needed for MVP. Document behavior for users.

### Q5: Should we expose history management controls to users?
**Answer**: Not in MVP. Future enhancement: Add UI controls to clear history, view history, or export conversation.

## Implementation Notes

**Key Files**:
- `src/agent/core.py:ConversationSessionManager` - Session manager class (~50 lines)
- `src/agent/core.py:run_agent_with_session` - Helper function with session support (~30 lines)
- `src/agent/core.py:keep_recent_messages` - History processor function (~20 lines)
- `src/ui/app.py:@cl.on_message` - Pass session ID to agent (~5 lines)

**Testing Strategy**:
- Unit tests: Message storage, retrieval, update, truncation
- Integration tests: Multi-turn conversations, tool calls, session isolation
- Manual tests: Real conversation flows, edge cases, latency measurement

**Performance Targets**:
- Latency increase: < 500ms per message
- Token usage: < 10,000 tokens per request
- Memory usage: < 10KB per session
- No degradation after 10+ messages (due to truncation)

**Code Review Checklist**:
- ✅ No Chainlit imports in agent layer
- ✅ Message history typed as `list[ModelMessage]`
- ✅ Session key "message_history" used consistently
- ✅ History processor handles tool call pairing
- ✅ Tests cover multi-turn and tool call scenarios
- ✅ Docstrings explain truncation strategy
- ✅ Error handling preserves session on failures

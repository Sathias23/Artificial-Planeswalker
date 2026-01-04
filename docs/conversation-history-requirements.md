# Conversation History Requirements

**Status**: Draft
**Priority**: High
**Effort**: Medium (4-6 hours)
**Created**: 2025-10-18

## Problem Statement

The agent currently has no memory between messages within a chat session. When users refer to previously discussed cards or concepts (e.g., "what set is it from?" after discussing Bloodhall Ooze), the agent cannot recall the context and asks for clarification.

**Example Chat Failure**:
```
User: Tell me about Bloodhall Ooze
Agent: [Provides detailed card information]

User: What set is it from?
Agent: I'd be happy to help you find out what set a card is from!
       However, I need to know which card you're asking about...
```

The agent should remember it was just discussing Bloodhall Ooze and provide the set information.

---

## Requirements

### 1. Message History Storage

**What**: Store conversation history in memory for the duration of a Chainlit session

**Details**:
- Use Chainlit's `cl.user_session` to store message history per user session
- Initialize empty message list on `@cl.on_chat_start`
- Append messages after each agent interaction
- Clear automatically when session ends (Chainlit handles this)

**Data Structure**:
```python
from pydantic_ai.messages import ModelMessage

# Stored in cl.user_session
message_history: list[ModelMessage] = []
```

### 2. PydanticAI Integration

**What**: Pass conversation history to `agent.run()` using PydanticAI's native message history support

**API Reference** (from PydanticAI docs):
```python
# Extract all messages from previous run
result = await agent.run("Tell me a joke", deps=deps)
history = result.all_messages()  # Returns list[ModelMessage]

# Use history in next run
result2 = await agent.run(
    "Tell me another joke",
    deps=deps,
    message_history=history  # Pass previous messages
)
```

**Message Types**:
- `ModelRequest` - Contains user prompts and system prompts
- `ModelResponse` - Contains agent responses (text, tool calls, etc.)
- Each message has `parts` which can be:
  - `UserPromptPart` - User text
  - `SystemPromptPart` - System instructions
  - `TextPart` - Agent text response
  - `ToolCallPart` - Agent calling a tool
  - `ToolReturnPart` - Tool response

**CRITICAL**: Tool calls and returns must stay paired in history. Slicing history incorrectly can cause LLM errors.

### 3. History Size Management

**What**: Prevent unbounded memory growth with intelligent history truncation

**Strategy**: Use PydanticAI's history processors to limit message count

**Implementation**:
```python
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

async def keep_recent_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Keep only the last 10 messages (5 exchanges) to manage token usage."""
    if len(messages) > 10:
        # Keep system prompt + recent messages
        system_messages = [m for m in messages[:2] if m.parts and
                          any(isinstance(p, SystemPromptPart) for p in m.parts)]
        recent_messages = messages[-10:]
        return system_messages + recent_messages
    return messages

# Register with agent
agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    history_processors=[keep_recent_messages]
)
```

**Alternative**: Set hard limit (e.g., 20 messages = ~10 exchanges) and slice manually before passing to `agent.run()`.

**Token Budget Consideration**:
- Average message: ~100-500 tokens
- 20 messages: ~2,000-10,000 tokens
- Agent model (Claude Haiku): 200k context window
- History is safe at 20 messages, provides good context

### 4. Chainlit Session Integration

**What**: Integrate message history storage with Chainlit's lifecycle hooks

**Implementation Pattern**:

```python
@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize message history for new chat session."""
    # Initialize empty message history in session
    cl.user_session.set("message_history", [])

    # Initialize app as before...
    await initialize_app()
    await cl.Message(content="Welcome message...").send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle message with history support."""
    user_input = message.content

    # Retrieve history from session
    message_history: list[ModelMessage] = cl.user_session.get("message_history", [])

    response_message = cl.Message(content="")
    await response_message.send()

    try:
        async with get_agent_dependencies() as deps:
            # Run agent WITH history
            result = await _agent.run(
                user_input,
                deps=deps,
                message_history=message_history  # Pass history here
            )

            # Extract ALL messages from this run (includes user prompt + response)
            new_messages = result.all_messages()

            # Update session history with new messages
            updated_history = message_history + new_messages
            cl.user_session.set("message_history", updated_history)

            # Display response
            response_text = result.output
            for char in response_text:
                await response_message.stream_token(char)

            await response_message.update()

    except Exception as e:
        # Handle errors...
        pass
```

**Key Points**:
- `result.all_messages()` returns complete conversation including the current exchange
- Append these to existing history for cumulative context
- History processors (if configured) run automatically before each agent call

### 5. Message Serialization (Future Enhancement)

**What**: Optional - serialize message history to JSON for Chainlit data persistence

**Note**: Not required for MVP since we're not using Chainlit persistence. Document for future reference.

**API** (from PydanticAI docs):
```python
from pydantic_core import to_jsonable_python
from pydantic_ai.messages import ModelMessagesTypeAdapter

# Serialize
history_json = to_jsonable_python(message_history)

# Deserialize
restored_history = ModelMessagesTypeAdapter.validate_python(history_json)
```

---

## Implementation Steps

1. **Update `src/ui/app.py`**:
   - Add `message_history` initialization in `on_chat_start` (1 line)
   - Retrieve history from session in `on_message` (1 line)
   - Pass `message_history` to `agent.run()` (1 parameter)
   - Extract and store `result.all_messages()` back to session (2 lines)

2. **Add history processor to `src/agent/core.py`** (optional):
   - Implement `keep_recent_messages` function
   - Register with `Agent` constructor

3. **Test conversation continuity**:
   - Start chat, ask about a card
   - Follow up with context-dependent question
   - Verify agent remembers previous context

---

## Technical Constraints

### Tool Call Pairing
**CRITICAL**: When slicing message history, ensure tool calls and returns stay paired.

**Problem**:
```python
# BAD - Can break if slice splits tool call from its return
history[-5:]  # Might include ToolCallPart without ToolReturnPart
```

**Solution**: PydanticAI's history processors handle this automatically. If implementing manual slicing, validate pairing.

### Performance Impact
- **Memory**: Negligible (~10KB per session for 20 messages)
- **Latency**: +100-500ms per request (depends on history size)
- **Tokens**: 2,000-10,000 additional tokens per request (within budget)

### Model Compatibility
- All OpenRouter models support message history (Claude, GPT, Gemini)
- Message format is model-agnostic (PydanticAI handles translation)

---

## Testing Strategy

### Unit Tests
```python
# tests/unit/ui/test_message_history.py

async def test_message_history_stored():
    """Verify messages are stored in session."""
    # Initialize session
    # Send message
    # Check session contains history

async def test_history_passed_to_agent():
    """Verify history is passed to agent.run()."""
    # Mock agent.run
    # Verify message_history parameter is passed

async def test_context_preserved():
    """Verify agent remembers previous context."""
    # Send message about Bloodhall Ooze
    # Send follow-up "what set is it from?"
    # Verify agent knows context
```

### Manual Testing Scenarios
1. **Basic continuity**:
   - Ask about card → Follow up with "what set?" → Should remember
2. **Multi-turn context**:
   - Discuss deck → Ask "add more red cards" → Should remember deck colors
3. **History limit**:
   - Send 15+ messages → Verify old messages dropped, recent kept
4. **Tool call handling**:
   - Trigger tool call → Follow up question → Verify no errors

---

## Success Criteria

- ✅ Agent remembers cards/topics discussed in same session
- ✅ Context-dependent questions work ("what set is it from?", "tell me more about it")
- ✅ No memory leaks (history clears on new session)
- ✅ No LLM errors from malformed message history
- ✅ Latency increase < 1 second per message

---

## Future Enhancements

### Phase 2: Persistent History (Post-MVP)
- Store conversation history in database
- Resume conversations across sessions
- Export conversation transcripts
- Requires Chainlit data persistence setup

### Phase 3: Advanced Context Management
- Summarize old messages to save tokens
- Semantic search over conversation history
- Multi-session context ("remember from our chat last week")

---

## References

- **PydanticAI Message History**: https://ai.pydantic.dev/messages-and-chat-history/
- **PydanticAI History Processors**: https://ai.pydantic.dev/messages-and-chat-history/#history-processors
- **Chainlit Session Management**: https://docs.chainlit.io/backend/user-session
- **Tool Call Pairing Issue**: https://github.com/pydantic/pydantic-ai/issues/2050#issuecomment-3019976269

---

## Example: Complete Flow

```python
# Session 1, Message 1
User: "Tell me about Bloodhall Ooze"
→ message_history = []
→ agent.run(user_input, message_history=[])
→ result.all_messages() = [
    ModelRequest(parts=[UserPromptPart("Tell me about...")]),
    ModelResponse(parts=[
        ToolCallPart(name="lookup_card_by_name", args={"card_name": "Bloodhall Ooze"}),
    ]),
    ModelRequest(parts=[ToolReturnPart(content="...")]),  # Tool response
    ModelResponse(parts=[TextPart("Bloodhall Ooze is a really interesting...")])
]
→ Store in session: message_history = [... 4 messages above ...]

# Session 1, Message 2
User: "What set is it from?"
→ Retrieve from session: message_history = [... 4 messages ...]
→ agent.run("What set is it from?", message_history=message_history)
→ Agent sees full context, knows "it" refers to Bloodhall Ooze
→ Response: "Bloodhall Ooze is from Conflux (2009)..."
```

---

## Open Questions

1. **History processor vs manual slicing?**
   - Recommendation: Use history processor (cleaner, handles tool pairing)

2. **What to do with error messages?**
   - Include in history so agent can learn from errors
   - Alternative: Filter out failed tool calls

3. **Should system prompt be in every message?**
   - No - PydanticAI includes it automatically
   - Don't duplicate in message_history

4. **Handle session timeout?**
   - Chainlit clears session on disconnect
   - No action needed for MVP

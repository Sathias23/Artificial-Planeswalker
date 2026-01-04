# Implementation Tasks - Conversation History

## 1. Agent Session Manager Setup
- [x] 1.1 Create `ConversationSessionManager` class in `src/agent/core.py`
- [x] 1.2 Implement in-memory dict storage for sessions (`dict[str, list[ModelMessage]]`)
- [x] 1.3 Add `get_history(session_id: str) -> list[ModelMessage]` method
- [x] 1.4 Add `update_history(session_id: str, messages: list[ModelMessage])` method
- [x] 1.5 Add `clear_session(session_id: str)` method for cleanup
- [x] 1.6 Add type hints and docstrings to all methods

## 2. Agent Invocation Helper with History
- [x] 2.1 Create `run_agent_with_session` helper function in `src/agent/core.py`
- [x] 2.2 Accept `user_input: str`, `session_id: str`, and `deps` parameters
- [x] 2.3 Retrieve history from session manager using session_id
- [x] 2.4 Pass `message_history` to `agent.run()` invocation
- [x] 2.5 Extract all messages from result using `result.all_messages()`
- [x] 2.6 Update session manager with new messages
- [x] 2.7 Return agent result to caller

## 3. History Size Management
- [x] 3.1 Create `keep_recent_messages` history processor function in `src/agent/core.py`
- [x] 3.2 Implement logic to keep last 10 messages (5 exchanges)
- [x] 3.3 Preserve system messages when truncating history
- [x] 3.4 Register processor with Agent using `history_processors` parameter
- [x] 3.5 Add docstring explaining truncation strategy and rationale

## 4. Tool Call Pairing Safety
- [x] 4.1 Review PydanticAI history processor documentation for tool pairing
- [x] 4.2 Verify history processor maintains tool call/return pairing
- [x] 4.3 Add comments explaining tool pairing requirements
- [x] 4.4 Test with scenarios that include tool calls in history

## 5. UI Integration
- [x] 5.1 Update `@cl.on_message` handler in `src/ui/app.py`
- [x] 5.2 Get session ID from Chainlit: `session_id = cl.user_session.get("id")`
- [x] 5.3 Call `run_agent_with_session(user_input, session_id, deps)` instead of direct `agent.run()`
- [x] 5.4 Handle response streaming and display as before
- [x] 5.5 Add session cleanup in `@cl.on_chat_end` if needed

## 6. Unit Testing
- [x] 6.1 Create `tests/unit/agent/test_session_manager.py`
- [x] 6.2 Write test for session manager initialization
- [x] 6.3 Write test for get_history with new session (returns empty list)
- [x] 6.4 Write test for update_history and retrieval
- [x] 6.5 Write test for clear_session
- [x] 6.6 Write test for history processor truncation logic
- [x] 6.7 Write test for run_agent_with_session helper
- [x] 6.8 Ensure all unit tests pass

## 7. Integration Testing
- [x] 7.1 Create `tests/integration/ui/test_conversation_context.py`
- [x] 7.2 Write test for basic continuity (ask about card, follow up "what set?")
- [x] 7.3 Write test for multi-turn context preservation
- [x] 7.4 Write test for history size limit enforcement
- [x] 7.5 Write test for tool call handling in history
- [x] 7.6 Write test for session isolation (multiple users)
- [x] 7.7 Ensure all integration tests pass

## 8. Manual Testing
- [x] 8.1 Start Chainlit application locally
- [x] 8.2 Test basic continuity: "Tell me about Bloodhall Ooze" → "What set is it from?"
- [x] 8.3 Test multi-turn: Discuss deck → "Add more red cards" → Verify context remembered
- [x] 8.4 Test history limit: Send 15+ messages → Verify old messages dropped
- [x] 8.5 Test tool calls: Trigger card lookup → Follow up question → No errors
- [x] 8.6 Test error handling: Agent error → Follow up message → Session still works
- [x] 8.7 Document any issues or unexpected behaviors

## 9. Code Quality
- [x] 9.1 Add docstrings to session manager and history processor
- [x] 9.2 Add inline comments for message history management
- [x] 9.3 Run `uv run ruff check . --fix` and resolve linting issues
- [x] 9.4 Run `uv run mypy src/` and resolve type checking errors
- [x] 9.5 Run `uv run pre-commit run --all-files` and ensure all checks pass
- [x] 9.6 Verify code follows project conventions (line length, naming, etc.)

## 10. Documentation
- [x] 10.1 Add comments explaining PydanticAI message history API usage
- [x] 10.2 Document message history limits and rationale in code comments
- [x] 10.3 Document session manager architecture in module docstrings
- [x] 10.4 Verify example usage is clear for future developers

## 11. Acceptance Criteria Verification
- [x] 11.1 Agent remembers cards/topics discussed in same session
- [x] 11.2 Context-dependent questions work ("what set?", "tell me more")
- [x] 11.3 No memory leaks (history clears when appropriate)
- [x] 11.4 No LLM errors from malformed message history
- [x] 11.5 Latency increase < 1 second per message
- [x] 11.6 All tests pass (unit + integration)

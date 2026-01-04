# Implementation Tasks - Story 3.2

## 1. Agent Core Integration Preparation
- [x] 1.1 Review agent core module (`src/agent/core.py`) to identify invocation interface
- [x] 1.2 Create agent invocation helper function if needed (e.g., `run_agent_with_context`)
- [x] 1.3 Ensure agent can accept conversation history as parameter
- [x] 1.4 Add support for streaming vs non-streaming mode selection

## 2. Chainlit Message Handler Update
- [x] 2.1 Update `@cl.on_message` handler in `src/ui/app.py` to invoke agent instead of echo
- [x] 2.2 Pass user message text to agent invocation function
- [x] 2.3 Implement conversation history tracking in Chainlit user session
- [x] 2.4 Provide conversation history to agent on each invocation
- [x] 2.5 Update conversation history with agent responses

## 3. Response Streaming Implementation
- [x] 3.1 Investigate Chainlit streaming message capabilities
- [x] 3.2 Implement agent response streaming if supported by Chainlit
- [x] 3.3 Fall back to complete message display if streaming not available
- [x] 3.4 Ensure responses display properly in chat interface

## 4. Error Handling Implementation
- [x] 4.1 Add try-catch block around agent invocation in message handler
- [x] 4.2 Handle `AuthenticationError` with user-friendly message about configuration
- [x] 4.3 Handle `RateLimitError` with message about retrying later
- [x] 4.4 Handle tool errors (card not found) with helpful suggestions
- [x] 4.5 Handle general exceptions with generic error message
- [x] 4.6 Log all errors with full details for debugging
- [x] 4.7 Ensure chat session remains active after errors (no crashes)

## 5. Dependency Injection for Tools
- [x] 5.1 Create database session in Chainlit session initialization if needed
- [x] 5.2 Pass database session (or repository instances) to agent tools
- [x] 5.3 Ensure tools can access database through injected dependencies
- [x] 5.4 Verify no direct database imports in UI layer (architectural compliance)

## 6. Integration Testing
- [x] 6.1 Create `tests/integration/test_chainlit_agent.py` for end-to-end tests
- [x] 6.2 Write test for successful card lookup through Chainlit → Agent → Database flow
- [x] 6.3 Write test for advanced search tool execution from UI context
- [x] 6.4 Write test for error handling (simulated agent failure)
- [x] 6.5 Write test for conversation context preservation across multiple messages
- [x] 6.6 Write test for session isolation (multiple users don't interfere)
- [x] 6.7 Ensure all integration tests pass with test database

## 7. Manual Testing and Validation
- [x] 7.1 Start Chainlit application locally
- [x] 7.2 Manually test basic card lookup ("Show me Lightning Bolt")
- [x] 7.3 Manually test advanced search ("Find red creatures with haste under 4 mana")
- [x] 7.4 Manually test multi-turn conversation with follow-up questions
- [x] 7.5 Manually test error scenarios (invalid query, API key issue)
- [x] 7.6 Verify user experience is conversational and responses are helpful
- [x] 7.7 Confirm welcome message still displays on initial load

## 8. Documentation and Code Quality
- [x] 8.1 Add docstrings to new agent invocation helper functions
- [x] 8.2 Add inline comments explaining conversation history management
- [x] 8.3 Update `src/ui/` module docstring to reflect agent integration
- [x] 8.4 Run `uv run ruff check . --fix` and resolve linting issues
- [x] 8.5 Run `uv run mypy src/` and resolve type checking errors
- [x] 8.6 Run pre-commit hooks and ensure all checks pass
- [x] 8.7 Verify no Chainlit imports in agent layer (architectural compliance check)

## 9. Story 3.2 Acceptance Criteria Verification
- [x] 9.1 Verify: Chainlit message handlers invoke PydanticAI agent with user input
- [x] 9.2 Verify: Agent responses stream back to Chainlit chat interface
- [x] 9.3 Verify: User can ask card lookup questions and receive answers
- [x] 9.4 Verify: Agent tool calls (card queries) execute successfully from Chainlit context
- [x] 9.5 Verify: Error handling displays user-friendly messages in chat for failures
- [x] 9.6 Verify: Chat maintains conversation context across multiple messages
- [x] 9.7 Verify: Integration tests confirm end-to-end Chainlit → Agent → Database flow

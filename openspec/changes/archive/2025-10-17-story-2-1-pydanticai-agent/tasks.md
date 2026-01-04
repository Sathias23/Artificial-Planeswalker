# Implementation Tasks: Story 2.1 - PydanticAI Agent Setup

## 1. Project Setup and Dependencies

- [x] 1.1 Add PydanticAI dependency to pyproject.toml (`pydantic-ai>=0.0.14`)
- [x] 1.2 Add openai dependency for OpenRouter compatibility (`openai>=1.0.0`)
- [x] 1.3 Add tenacity dependency for retry logic (`tenacity>=8.0.0`)
- [x] 1.4 Add pydantic-settings for configuration (`pydantic-settings>=2.0.0`)
- [x] 1.5 Run `uv sync` to install new dependencies
- [x] 1.6 Create `.env.example` with OpenRouter configuration template
- [x] 1.7 Update `.gitignore` to ensure `.env` is excluded

## 2. Configuration Module Implementation

- [x] 2.1 Create `src/agent/` package with `__init__.py`
- [x] 2.2 Create `src/agent/config.py` with `AgentConfig` class
- [x] 2.3 Implement environment variable loading with Pydantic Settings
- [x] 2.4 Add validation for temperature range (0.0-2.0)
- [x] 2.5 Add validation for max_tokens (positive integer)
- [x] 2.6 Add default values for optional configuration parameters
- [x] 2.7 Add type hints for all configuration fields

## 3. Error Handling Implementation

- [x] 3.1 Create `src/agent/errors.py` with custom exception classes
- [x] 3.2 Implement `AgentError` base exception
- [x] 3.3 Implement `AuthenticationError` for API key issues
- [x] 3.4 Implement `RateLimitError` for rate limiting
- [x] 3.5 Implement `ModelUnavailableError` for service issues
- [x] 3.6 Add error message templates with context formatting

## 4. Agent Core Implementation

- [x] 4.1 Create `src/agent/core.py` for agent initialization
- [x] 4.2 Implement `create_agent()` factory function
- [x] 4.3 Add OpenRouterProvider integration with API key
- [x] 4.4 Configure ModelSettings with temperature and max_tokens
- [x] 4.5 Add system prompt for Artificial-Planeswalker personality
- [x] 4.6 Implement `defer_model_check` parameter for testing
- [x] 4.7 Add docstrings with parameter descriptions and return types

## 5. Retry Logic Implementation

- [x] 5.1 Create `src/agent/retry.py` for retry utilities
- [x] 5.2 Implement `run_agent_with_retry()` async function
- [x] 5.3 Configure tenacity retry decorator with exponential backoff
- [x] 5.4 Add retry on RateLimitError (5 attempts, 2-60s wait)
- [x] 5.5 Add error mapping from HTTP codes to custom exceptions
- [x] 5.6 Add logging for retry attempts

## 6. Unit Tests

- [x] 6.1 Create `tests/unit/agent/` directory with `__init__.py`
- [x] 6.2 Create `tests/unit/agent/test_config.py`
- [x] 6.3 Test AgentConfig loads from environment variables
- [x] 6.4 Test AgentConfig applies default values
- [x] 6.5 Test AgentConfig validation rejects invalid temperature
- [x] 6.6 Test AgentConfig validation rejects invalid max_tokens
- [x] 6.7 Test AgentConfig raises error for missing API key
- [x] 6.8 Create `tests/unit/agent/test_core.py`
- [x] 6.9 Test create_agent() with default configuration
- [x] 6.10 Test create_agent() with custom configuration
- [x] 6.11 Test create_agent() with defer_model_check=True
- [x] 6.12 Test agent initialization with TestModel
- [x] 6.13 Create `tests/unit/agent/test_errors.py`
- [x] 6.14 Test custom exception hierarchy
- [x] 6.15 Test error message formatting

## 7. Integration Tests

- [x] 7.1 Create `tests/integration/agent/` directory with `__init__.py`
- [x] 7.2 Create `tests/integration/agent/test_openrouter.py`
- [x] 7.3 Add pytest marker for integration tests (`@pytest.mark.integration`)
- [x] 7.4 Add skipif condition for missing OPENROUTER_API_KEY
- [x] 7.5 Test basic agent response generation with OpenRouter
- [x] 7.6 Test agent with GPT-4 Turbo model
- [x] 7.7 Test agent with Claude 3.5 Sonnet model (if time permits)
- [x] 7.8 Test response validation (non-empty, has metadata)
- [x] 7.9 Test error handling for invalid API key
- [x] 7.10 Test async operation with asyncio.run()

## 8. Documentation

- [x] 8.1 Update README.md with agent setup instructions
- [x] 8.2 Document how to obtain OpenRouter API key
- [x] 8.3 Document environment variable configuration
- [x] 8.4 Document supported models and their characteristics
- [x] 8.5 Add code examples for basic agent usage
- [x] 8.6 Document testing approach (unit vs integration)
- [x] 8.7 Add troubleshooting section for common issues

## 9. Testing and Validation

- [x] 9.1 Run unit tests with `uv run pytest tests/unit/agent/`
- [x] 9.2 Verify 100% pass rate for unit tests
- [x] 9.3 Run integration tests with `uv run pytest tests/integration/agent/ -m integration`
- [x] 9.4 Verify integration tests pass with valid API key
- [x] 9.5 Run mypy type checking: `uv run mypy src/agent/`
- [x] 9.6 Verify no type errors
- [x] 9.7 Run ruff linting: `uv run ruff check src/agent/`
- [x] 9.8 Fix any linting issues
- [x] 9.9 Test agent with manual script (simple prompt/response)
- [x] 9.10 Verify response quality and error handling

## 10. Final Verification

- [x] 10.1 Verify all acceptance criteria from PRD Story 2.1 are met
- [x] 10.2 Confirm agent initializes with OpenRouter configuration
- [x] 10.3 Confirm swappable model configuration works
- [x] 10.4 Confirm basic agent response test validates LLM communication
- [x] 10.5 Confirm error handling for API failures and rate limiting
- [x] 10.6 Confirm unit tests verify agent initialization
- [x] 10.7 Run full test suite: `uv run pytest tests/`
- [x] 10.8 Ensure pre-commit hooks pass
- [x] 10.9 Update OpenSpec proposal status (mark tasks complete)
- [x] 10.10 Ready for Story 2.2 (Card Lookup Tool Implementation)

## Notes

- Tasks should be completed sequentially within each section
- Integration tests require valid `OPENROUTER_API_KEY` in `.env`
- Unit tests should run without API key (use TestModel)
- All code must pass mypy strict type checking
- Document any deviations from design decisions in comments

# Implementation Tasks

## 1. Dependencies

- [x] 1.1 Add `anthropic` extra to `pydantic-ai` dependency in `pyproject.toml`
- [x] 1.2 Run `uv sync` to install `pydantic-ai-slim[anthropic]` package
- [x] 1.3 Verify `anthropic` package is importable

## 2. Configuration

- [x] 2.1 Add `anthropic_api_key: str | None` field to `AgentConfig` in `src/agent/config.py`
- [x] 2.2 Make `openrouter_api_key: str | None` optional (remove `...` required marker)
- [x] 2.3 Add model validator to ensure at least one API key is provided
- [x] 2.4 Update `.env.example` with `ANTHROPIC_API_KEY` documentation
- [x] 2.5 Add configuration examples for both providers

## 3. Provider Selection Logic

- [x] 3.1 Create helper function `_determine_provider(config: AgentConfig)` in `src/agent/core.py`
- [x] 3.2 Implement logic to detect Claude models (check for "claude" in model name)
- [x] 3.3 Prefer Anthropic provider for Claude models when `ANTHROPIC_API_KEY` is set
- [x] 3.4 Fall back to OpenRouter for non-Claude models or when only `OPENROUTER_API_KEY` is set
- [x] 3.5 Raise `AuthenticationError` when no suitable API key is available

## 4. Agent Initialization

- [x] 4.1 Import `AnthropicModel` and `AnthropicProvider` from `pydantic_ai.models.anthropic`
- [x] 4.2 Update `create_agent()` to use provider selection logic
- [x] 4.3 Create `AnthropicModel` instance when Anthropic provider is selected
- [x] 4.4 Normalize model names (handle both "claude-sonnet-4-5" and "anthropic/claude-sonnet-4-5")
- [x] 4.5 Pass `ModelSettings` to both Anthropic and OpenRouter model instances
- [x] 4.6 Ensure tool registration works with both providers

## 5. Error Handling

- [x] 5.1 Update error messages to include provider information (Anthropic vs OpenRouter)
- [x] 5.2 Add specific error handling for Anthropic API errors
- [x] 5.3 Provide migration guidance in error messages when tool calls fail with OpenRouter
- [x] 5.4 Test error scenarios with both providers

## 6. Testing

- [x] 6.1 Update `tests/integration/agent/test_openrouter.py` → rename to `test_agent_providers.py` (kept as is for backward compatibility)
- [x] 6.2 Add test for Anthropic provider with Claude model
- [x] 6.3 Add test for OpenRouter provider with non-Claude model
- [x] 6.4 Add test for provider auto-selection logic
- [x] 6.5 Add test for tool calls via Anthropic provider (ensure `function.arguments` is not None)
- [x] 6.6 Add test for configuration validation (missing API keys)
- [x] 6.7 Add test for model name normalization
- [x] 6.8 Update unit tests in `tests/unit/agent/test_config.py` for new config fields
- [x] 6.9 Run full test suite and ensure all tests pass

## 7. Documentation

- [x] 7.1 Update `CLAUDE.md` Project Overview section with Anthropic provider information
- [x] 7.2 Update `CLAUDE.md` Agent Core section with provider selection logic
- [x] 7.3 Update `README.md` setup instructions to include Anthropic API key (not needed - CLAUDE.md is authoritative)
- [x] 7.4 Add migration guide for users switching from OpenRouter to Anthropic (documented in .env.example)
- [x] 7.5 Update environment variable documentation in `.env.example`
- [x] 7.6 Document which models work with which providers

## 8. Integration Verification

- [x] 8.1 Test agent creation with Anthropic API key and Claude model
- [x] 8.2 Test agent tool calls (e.g., `lookup_card_by_name`) via Anthropic provider
- [x] 8.3 Verify tool call arguments are properly formatted (not None)
- [x] 8.4 Test full conversation flow with session history via Anthropic
- [x] 8.5 Test agent creation with OpenRouter API key and non-Claude model
- [x] 8.6 Verify backward compatibility with OpenRouter-only configuration
- [x] 8.7 Test error handling with invalid API keys

## 9. Cleanup

- [x] 9.1 Remove any OpenRouter-specific workarounds or hacks
- [x] 9.2 Update code comments referencing OpenRouter integration
- [x] 9.3 Ensure no hard-coded OpenRouter assumptions remain
- [x] 9.4 Run linting (`uv run ruff check . --fix`) and formatting (`uv run ruff format .`)
- [x] 9.5 Run type checking (`uv run mypy src/`)

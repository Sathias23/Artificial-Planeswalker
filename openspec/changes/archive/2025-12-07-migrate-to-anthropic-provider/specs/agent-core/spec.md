## MODIFIED Requirements

### Requirement: Agent Configuration Management

The system SHALL provide type-safe configuration management for agent initialization parameters via environment variables, supporting both Anthropic and OpenRouter providers.

#### Scenario: Load Anthropic configuration from environment
- **GIVEN** a `.env` file with `ANTHROPIC_API_KEY=sk-ant-test-key` and `AGENT_MODEL=claude-sonnet-4-5`
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** the configuration SHALL load API key as "sk-ant-test-key" and model name as "claude-sonnet-4-5"

#### Scenario: Load OpenRouter configuration from environment
- **GIVEN** a `.env` file with `OPENROUTER_API_KEY=sk-or-test-key` and `AGENT_MODEL=openai/gpt-5`
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** the configuration SHALL load API key as "sk-or-test-key" and model name as "openai/gpt-5"

#### Scenario: Apply default configuration values
- **GIVEN** no environment variables are set for optional parameters
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** temperature SHALL default to 0.7 and max_tokens SHALL default to 2000

#### Scenario: Validate configuration parameter ranges
- **GIVEN** environment variable `AGENT_TEMPERATURE=2.5` (out of range)
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** a validation error SHALL be raised indicating temperature must be between 0.0 and 2.0

#### Scenario: Handle missing API keys
- **GIVEN** neither `ANTHROPIC_API_KEY` nor `OPENROUTER_API_KEY` environment variables are set
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** a validation error SHALL be raised indicating at least one API key is required

#### Scenario: Prefer Anthropic for Claude models
- **GIVEN** both `ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY` are set
- **AND** `AGENT_MODEL` is a Claude model (e.g., "anthropic/claude-sonnet-4-5" or "claude-sonnet-4-5")
- **WHEN** the `AgentConfig` is used to determine provider
- **THEN** the Anthropic provider SHALL be preferred over OpenRouter

### Requirement: PydanticAI Agent Initialization

The system SHALL initialize a PydanticAI agent with the appropriate provider (Anthropic or OpenRouter) based on model and available API keys.

#### Scenario: Create agent with Anthropic provider
- **GIVEN** valid agent configuration with Anthropic API key and Claude model
- **WHEN** `create_agent()` is called
- **THEN** an Agent instance SHALL be created using `AnthropicModel` provider
- **AND** the agent SHALL communicate directly with Anthropic's API

#### Scenario: Create agent with OpenRouter provider
- **GIVEN** valid agent configuration with OpenRouter API key and non-Claude model (e.g., "openai/gpt-5")
- **WHEN** `create_agent()` is called
- **THEN** an Agent instance SHALL be created using `OpenAIChatModel` with OpenRouter base URL
- **AND** the agent SHALL communicate with OpenRouter's API

#### Scenario: Create agent with deferred model check for testing
- **GIVEN** testing environment without valid API key
- **WHEN** `create_agent(defer_model_check=True)` is called
- **THEN** an Agent instance SHALL be created without validating the API key

#### Scenario: Apply custom model settings
- **GIVEN** agent configuration with `temperature=0.3` and `max_tokens=1500`
- **WHEN** `create_agent(config)` is called
- **THEN** the agent SHALL use temperature 0.3 and max_tokens 1500 for LLM requests

### Requirement: Anthropic Direct API Integration

The system SHALL communicate directly with Anthropic's API using the native `AnthropicModel` provider for Claude models, avoiding translation layers.

#### Scenario: Generate basic text response via Anthropic
- **GIVEN** an initialized agent with valid Anthropic API key and Claude model
- **WHEN** the agent runs with prompt "What is a planeswalker?"
- **THEN** the agent SHALL return a non-empty text response about planeswalkers
- **AND** the request SHALL be sent directly to Anthropic's API

#### Scenario: Execute tool calls via Anthropic
- **GIVEN** an agent configured with Anthropic provider and tools registered
- **WHEN** the agent runs with a prompt requiring tool use
- **THEN** the agent SHALL successfully invoke tools using Anthropic's native tool call format
- **AND** tool calls SHALL have properly formatted arguments (not None)
- **AND** tool execution SHALL complete without validation errors

#### Scenario: Handle Anthropic-specific model names
- **GIVEN** agent configuration with model name "claude-sonnet-4-5" (short form without provider prefix)
- **WHEN** an agent is created
- **THEN** the agent SHALL successfully initialize with Anthropic provider
- **AND** the model name SHALL be correctly interpreted by Anthropic's API

### Requirement: OpenRouter Fallback Integration

The system SHALL support OpenRouter API as a fallback provider for non-Claude models using the OpenAI-compatible interface.

#### Scenario: Use OpenRouter for non-Anthropic models
- **GIVEN** agent configuration with OpenRouter API key and model "openai/gpt-5"
- **WHEN** an agent is created
- **THEN** the agent SHALL use OpenRouter's API endpoint
- **AND** the agent SHALL communicate via OpenAI-compatible interface

#### Scenario: Support multiple model providers via OpenRouter
- **GIVEN** OpenRouter configuration with different model names
- **WHEN** agents are created for "openai/gpt-5" and "google/gemini-2.5-flash"
- **THEN** both agents SHALL initialize successfully via OpenRouter
- **AND** each agent SHALL communicate with their respective models through OpenRouter

### Requirement: API Error Handling

The system SHALL handle both Anthropic and OpenRouter API errors gracefully with appropriate exceptions and user-friendly error messages.

#### Scenario: Handle Anthropic authentication failure
- **GIVEN** an agent with invalid Anthropic API key
- **WHEN** the agent attempts to generate a response
- **THEN** an `AuthenticationError` SHALL be raised with message "Invalid API key"

#### Scenario: Handle OpenRouter authentication failure
- **GIVEN** an agent with invalid OpenRouter API key
- **WHEN** the agent attempts to generate a response
- **THEN** an `AuthenticationError` SHALL be raised with message "Invalid API key"

#### Scenario: Handle rate limit with retry
- **GIVEN** an agent that receives a 429 rate limit response
- **WHEN** the agent runs with retry logic enabled
- **THEN** the agent SHALL retry with exponential backoff up to 5 attempts

#### Scenario: Handle model unavailability
- **GIVEN** an agent where the selected model returns 503 unavailable
- **WHEN** the agent attempts to generate a response
- **THEN** a `ModelUnavailableError` SHALL be raised with message "Model unavailable"

#### Scenario: Handle network timeout
- **GIVEN** an agent where the API request times out
- **WHEN** the agent attempts to generate a response
- **THEN** an `AgentError` SHALL be raised with timeout details in the error message

#### Scenario: Provide clear error context
- **GIVEN** any agent error occurs
- **WHEN** the error is caught and logged
- **THEN** the error message SHALL include sufficient context for debugging (model name, provider, prompt length, error type)

## ADDED Requirements

### Requirement: Provider Selection Logic

The system SHALL automatically select the appropriate provider (Anthropic or OpenRouter) based on model name and available API keys.

#### Scenario: Auto-select Anthropic for Claude models
- **GIVEN** configuration with `ANTHROPIC_API_KEY` set and model "claude-sonnet-4-5"
- **WHEN** `create_agent()` determines the provider
- **THEN** Anthropic provider SHALL be selected automatically
- **AND** the agent SHALL use `AnthropicModel` for initialization

#### Scenario: Auto-select Anthropic for prefixed Claude models
- **GIVEN** configuration with `ANTHROPIC_API_KEY` set and model "anthropic/claude-sonnet-4-5"
- **WHEN** `create_agent()` determines the provider
- **THEN** Anthropic provider SHALL be selected automatically
- **AND** the model name prefix SHALL be handled correctly

#### Scenario: Auto-select OpenRouter for non-Claude models
- **GIVEN** configuration with `OPENROUTER_API_KEY` set and model "openai/gpt-5"
- **WHEN** `create_agent()` determines the provider
- **THEN** OpenRouter provider SHALL be selected automatically
- **AND** the agent SHALL use `OpenAIChatModel` with OpenRouter base URL

#### Scenario: Prefer Anthropic when both keys available
- **GIVEN** both `ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY` are set
- **AND** model is "claude-sonnet-4-5"
- **WHEN** `create_agent()` determines the provider
- **THEN** Anthropic provider SHALL be selected (preferred for Claude models)
- **AND** OpenRouter SHALL NOT be used

#### Scenario: Fail gracefully when no provider available
- **GIVEN** no API keys are configured
- **WHEN** `create_agent()` is called
- **THEN** an `AuthenticationError` SHALL be raised
- **AND** the error message SHALL indicate which API keys are required

### Requirement: Anthropic Dependency Management

The system SHALL properly manage the `anthropic` Python package dependency for native Anthropic integration.

#### Scenario: Install Anthropic provider package
- **GIVEN** the project dependencies in `pyproject.toml`
- **WHEN** dependencies are installed via `uv sync`
- **THEN** the `anthropic` package SHALL be installed via `pydantic-ai-slim[anthropic]`
- **AND** the Anthropic SDK SHALL be available for import

#### Scenario: Graceful degradation without Anthropic package
- **GIVEN** the `anthropic` package is not installed
- **AND** configuration specifies a Claude model
- **WHEN** `create_agent()` is called
- **THEN** a clear error message SHALL indicate the missing `anthropic` package
- **AND** installation instructions SHALL be provided (e.g., "pip install 'pydantic-ai-slim[anthropic]'")

### Requirement: Configuration Migration Support

The system SHALL support smooth migration from OpenRouter-only configuration to Anthropic-first configuration.

#### Scenario: Backward compatibility with OpenRouter-only setup
- **GIVEN** existing `.env` file with only `OPENROUTER_API_KEY` set
- **AND** no `ANTHROPIC_API_KEY` set
- **WHEN** `create_agent()` is called
- **THEN** the agent SHALL continue working with OpenRouter provider
- **AND** no breaking changes occur for existing users

#### Scenario: Optional migration to Anthropic
- **GIVEN** existing setup using OpenRouter for Claude models
- **WHEN** user adds `ANTHROPIC_API_KEY` to `.env`
- **AND** keeps `OPENROUTER_API_KEY` for other models
- **THEN** Claude models SHALL automatically switch to Anthropic provider
- **AND** other models SHALL continue using OpenRouter
- **AND** no code changes are required

#### Scenario: Clear migration guidance
- **GIVEN** user experiences tool call errors with OpenRouter
- **WHEN** error occurs during agent initialization or execution
- **THEN** the error message SHALL suggest adding `ANTHROPIC_API_KEY` for Claude models
- **AND** guidance SHALL include link to Anthropic console for API key generation

## REMOVED Requirements

### Requirement: OpenRouter Model Integration

**Reason**: This requirement is being replaced by provider-specific requirements (Anthropic Direct API Integration and OpenRouter Fallback Integration) that better reflect the multi-provider architecture.

**Migration**: The functionality is preserved but split into provider-specific requirements. Tool calls now work reliably through native Anthropic integration instead of OpenRouter's translation layer.

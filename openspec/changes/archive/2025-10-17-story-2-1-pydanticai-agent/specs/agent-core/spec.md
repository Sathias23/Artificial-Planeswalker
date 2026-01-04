# Agent Core Capability Specification

## ADDED Requirements

### Requirement: Agent Configuration Management

The system SHALL provide type-safe configuration management for agent initialization parameters via environment variables.

#### Scenario: Load configuration from environment
- **GIVEN** a `.env` file with `OPENROUTER_API_KEY=sk-test-key` and `AGENT_MODEL_NAME=openai/gpt-4-turbo`
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** the configuration SHALL load API key as "sk-test-key" and model name as "openai/gpt-4-turbo"

#### Scenario: Apply default configuration values
- **GIVEN** no environment variables are set for optional parameters
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** temperature SHALL default to 0.7 and max_tokens SHALL default to 2000

#### Scenario: Validate configuration parameter ranges
- **GIVEN** environment variable `AGENT_TEMPERATURE=2.5` (out of range)
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** a validation error SHALL be raised indicating temperature must be between 0.0 and 2.0

#### Scenario: Handle missing required configuration
- **GIVEN** no `OPENROUTER_API_KEY` environment variable is set
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** a validation error SHALL be raised indicating the API key is required

### Requirement: PydanticAI Agent Initialization

The system SHALL initialize a PydanticAI agent with OpenRouter model integration using provided configuration.

#### Scenario: Create agent with default configuration
- **GIVEN** valid agent configuration with OpenRouter API key
- **WHEN** `create_agent()` is called without arguments
- **THEN** an Agent instance SHALL be created with Claude Sonnet 4.5 model via OpenRouter

#### Scenario: Create agent with custom model selection
- **GIVEN** agent configuration with `model_name="openai/gpt-5"`
- **WHEN** `create_agent(config)` is called
- **THEN** an Agent instance SHALL be created with GPT-5 model via OpenRouter

#### Scenario: Create agent with deferred model check for testing
- **GIVEN** testing environment without valid API key
- **WHEN** `create_agent(defer_model_check=True)` is called
- **THEN** an Agent instance SHALL be created without validating the API key

#### Scenario: Apply custom model settings
- **GIVEN** agent configuration with `temperature=0.3` and `max_tokens=1500`
- **WHEN** `create_agent(config)` is called
- **THEN** the agent SHALL use temperature 0.3 and max_tokens 1500 for LLM requests

### Requirement: OpenRouter Model Integration

The system SHALL communicate with OpenRouter API using the OpenAI-compatible interface for LLM inference.

#### Scenario: Generate basic text response
- **GIVEN** an initialized agent with valid OpenRouter API key
- **WHEN** the agent runs with prompt "What is a planeswalker?"
- **THEN** the agent SHALL return a non-empty text response about planeswalkers

#### Scenario: Handle model-specific parameters
- **GIVEN** an agent configured for Claude Sonnet 4.5 model
- **WHEN** the agent runs with a complex reasoning prompt
- **THEN** the agent SHALL successfully invoke Claude via OpenRouter and return a response

#### Scenario: Support multiple model providers
- **GIVEN** OpenRouter configuration with different model names
- **WHEN** agents are created for "anthropic/claude-sonnet-4.5", "openai/gpt-5", and "google/gemini-2.5-flash"
- **THEN** all three agents SHALL initialize successfully and communicate with their respective models

### Requirement: API Error Handling

The system SHALL handle OpenRouter API errors gracefully with appropriate exceptions and user-friendly error messages.

#### Scenario: Handle authentication failure
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
- **THEN** the error message SHALL include sufficient context for debugging (model name, prompt length, error type)

### Requirement: Basic Response Validation

The system SHALL validate that agent responses meet basic quality criteria for LLM communication.

#### Scenario: Validate non-empty response
- **GIVEN** an agent that successfully completes a run
- **WHEN** the response is validated
- **THEN** the response data SHALL be non-empty and contain at least 1 character

#### Scenario: Validate response structure
- **GIVEN** an agent run result object
- **WHEN** the result is inspected
- **THEN** the result SHALL contain `data` attribute with the response text

#### Scenario: Confirm LLM model metadata
- **GIVEN** an agent run result
- **WHEN** the result metadata is inspected
- **THEN** the result SHALL include model name and token usage information

### Requirement: Test Mode Support

The system SHALL support test mode operation using PydanticAI's TestModel for unit testing without API calls.

#### Scenario: Initialize agent in test mode
- **GIVEN** test environment without OpenRouter API key
- **WHEN** an agent is created with `defer_model_check=True`
- **THEN** the agent SHALL initialize successfully without API validation

#### Scenario: Run agent with TestModel
- **GIVEN** an agent created with `TestModel` instead of OpenRouter
- **WHEN** the agent runs a prompt
- **THEN** the agent SHALL return a mock response without making API calls

#### Scenario: Validate test mode configuration
- **GIVEN** unit test with mocked configuration
- **WHEN** agent initialization is tested
- **THEN** configuration loading SHALL work independently of OpenRouter API

### Requirement: Environment-Based Model Selection

The system SHALL support runtime model selection via environment variables without code changes.

#### Scenario: Switch model via environment variable
- **GIVEN** environment variable `AGENT_MODEL_NAME=openai/gpt-5`
- **WHEN** an agent is created with default configuration
- **THEN** the agent SHALL use GPT-5 instead of default Claude Sonnet 4.5

#### Scenario: Override temperature at runtime
- **GIVEN** environment variable `AGENT_TEMPERATURE=0.9`
- **WHEN** an agent is created
- **THEN** the agent SHALL use temperature 0.9 for all LLM requests

#### Scenario: Document supported models
- **GIVEN** agent configuration documentation
- **WHEN** a developer reviews supported models
- **THEN** documentation SHALL list Claude Sonnet 4.5 (77.2% SWE-bench, $3/$15), GPT-5 (74.9% SWE-bench, $1.25/$10), and Gemini 2.5 Flash as tested models with their benchmark scores and pricing

### Requirement: Async Operation Support

The system SHALL support asynchronous agent operations compatible with PydanticAI's async-first design.

#### Scenario: Run agent asynchronously
- **GIVEN** an initialized agent in async context
- **WHEN** `await agent.run(prompt)` is called
- **THEN** the agent SHALL execute asynchronously and return result without blocking

#### Scenario: Support concurrent agent requests
- **GIVEN** multiple agent run requests
- **WHEN** requests are executed concurrently with `asyncio.gather()`
- **THEN** all requests SHALL execute in parallel without race conditions

#### Scenario: Handle async errors
- **GIVEN** an agent run that fails asynchronously
- **WHEN** the error is propagated
- **THEN** the error SHALL be catchable with standard async exception handling

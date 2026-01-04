# Story 2.1: PydanticAI Agent Setup with OpenRouter Integration

## Why

Story 2.1 establishes the foundational AI agent infrastructure for Artificial-Planeswalker. With Epic 1 complete (local card database operational), we need to create the PydanticAI agent core that will power natural language card queries and deck building assistance. This story delivers a configured, tested agent with OpenRouter integration, enabling the subsequent tool-based card query features in Stories 2.2-2.4.

The OpenRouter API provides access to multiple LLM providers (GPT-4 Turbo, Claude 3.5 Sonnet) through a unified interface, allowing us to test different models and select the best performer for MTG card queries without being locked into a single provider.

## What Changes

- **ADDED**: PydanticAI agent configuration module with OpenRouter model integration
- **ADDED**: Environment-based configuration for API keys and model selection
- **ADDED**: Error handling for API failures, rate limiting, and authentication issues
- **ADDED**: Basic agent response validation to confirm LLM communication
- **ADDED**: Unit tests for agent initialization and model configuration
- **ADDED**: Integration tests for end-to-end agent response generation

## Impact

**Affected Specs**:
- `agent-core` (new capability) - Core AI agent configuration and management

**Affected Code**:
- `src/agent/` - New module for PydanticAI agent implementation
- `src/agent/config.py` - Agent configuration with environment variable support
- `src/agent/core.py` - Agent initialization and basic operations
- `tests/unit/agent/` - Unit tests for agent components
- `tests/integration/agent/` - Integration tests for agent responses
- `.env.example` - Updated with OpenRouter configuration variables
- `pyproject.toml` - Add `openai` dependency for OpenRouter compatibility

**Dependencies**:
- Requires Epic 1 complete (database layer operational)
- Enables Stories 2.2-2.4 (card query tools depend on this agent)

## Research Summary

### Archon RAG Sources
- **PydanticAI Documentation** (ai.pydantic.dev):
  - Agent initialization patterns with `Agent` class
  - OpenRouter integration via `OpenAIModel` with `OpenRouterProvider`
  - Model settings configuration (temperature, max_tokens, etc.)
  - Environment variable patterns for API key management
  - Error handling and retry mechanisms with tenacity

### Key Research Findings

**1. OpenRouter Integration Pattern**:
```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

model = OpenAIModel(
    'anthropic/claude-3.5-sonnet',
    provider=OpenRouterProvider(api_key='your-api-key'),
)
agent = Agent(model)
```

**2. Simplified Shorthand Syntax**:
- Can use `Agent("openrouter:anthropic/claude-3.5-sonnet")` for automatic provider selection
- PydanticAI automatically creates appropriate model and provider instances

**3. Model Settings Configuration**:
- Three-level hierarchy: model defaults → agent defaults → runtime overrides
- Settings merge with runtime taking precedence
- Common settings: temperature, max_tokens, top_p, frequency_penalty

**4. Environment Variable Patterns**:
- Standard `OPENROUTER_API_KEY` environment variable
- Can override at runtime via provider initialization
- Deferred model check option for testing flexibility

**5. Error Handling**:
- Built-in retry mechanisms with tenacity library
- Transport layer supports custom retry policies
- Validation functions for response handling

**6. Testing Patterns**:
- `TestModel` available for unit testing without API calls
- `defer_model_check=True` for test environments
- Mock provider patterns for integration tests

### Web Search Findings

**OpenRouter API 2025 Status**:
- Official PydanticAI support via `OpenRouterProvider`
- OpenAI-compatible API (supports standard chat completions)
- Third-party `openrouter-agent` package available but not needed
- Rate limiting varies by model (~200 req/min for GPT-4)
- API key management via openrouter.ai/keys

**Recommended Models (October 2025)**:
- Primary: `anthropic/claude-sonnet-4.5` - Latest model (Sept 2025), world's best for coding (77.2% SWE-bench), 30+ hour autonomous work, $3/$15 per million tokens
- Alternative: `openai/gpt-5` - OpenAI's most advanced model (Aug 2025), 74.9% SWE-bench, 88% Aider polyglot benchmark, 400K context, $1.25/$10 per million tokens
- Fallback: `google/gemini-2.5-flash` - Fast, cost-effective with thinking capabilities, 20-30% token reduction, strong reasoning

### Architecture Decisions

**1. Configuration Strategy**:
- Use environment variables as primary configuration source
- Support runtime model override for testing/experimentation
- Centralize configuration in `src/agent/config.py`

**2. Error Handling Approach**:
- Implement retry logic with exponential backoff for rate limits
- Clear error messages for authentication failures
- Model fallback strategy (Claude Sonnet 4.5 → GPT-5 → Gemini 2.5 Flash)

**3. Testing Strategy**:
- Unit tests: Use `TestModel` for agent initialization
- Integration tests: Use real OpenRouter API with test API key
- Provide mock fixtures for CI/CD environments

**4. Model Selection**:
- Default to `anthropic/claude-sonnet-4.5` for superior coding and reasoning (state-of-the-art 77.2% SWE-bench)
- Allow environment variable override for experimentation with GPT-5 (74.9% SWE-bench, cheaper) or Gemini 2.5 Flash
- Document model comparison results in tests (SWE-bench scores, token costs, latency, context limits)

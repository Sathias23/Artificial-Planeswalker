# Technical Design: PydanticAI Agent Setup with OpenRouter

## Context

Story 2.1 establishes the PydanticAI agent infrastructure for Artificial-Planeswalker's natural language card query and deck building assistance. With the local Scryfall database operational (Epic 1), we now need an AI agent that can understand user requests, invoke tools (Stories 2.2-2.4), and generate helpful responses.

### Stakeholders
- **Developers**: Need clear agent initialization patterns and configuration management
- **End Users**: Benefit from reliable AI responses with appropriate model selection
- **Future Contributors**: Need extensible architecture for additional models and tools

### Constraints
- **UI Independence**: Agent layer must not import Chainlit (enables future UI replacement)
- **Type Safety**: Strict mypy compliance throughout agent code
- **Async Operations**: PydanticAI is async-first, must maintain async patterns
- **Cost Optimization**: OpenRouter provides model flexibility for cost/performance tuning

## Research Findings

### Archon RAG Knowledge

**PydanticAI Agent Architecture**:
- Agent as container: system prompts + tools + structured output type + dependencies
- Model-agnostic design with provider abstraction
- Three-level settings hierarchy (model → agent → runtime)
- Built-in retry/error handling via transport layer

**OpenRouter Integration**:
- Official support via `OpenRouterProvider`
- OpenAI-compatible API (standard chat completions format)
- Shorthand syntax: `Agent("openrouter:model-name")`
- Standard environment variable: `OPENROUTER_API_KEY`

**Error Handling Patterns**:
- Tenacity-based retry with exponential backoff
- Transport layer validation functions
- Async retry support via `AsyncTenacityTransport`

### Additional Research

**OpenRouter API Characteristics** (Web Search 2025):
- Multiple provider access through unified interface
- Rate limits vary by model (~200 req/min for GPT-4)
- API key management via openrouter.ai/keys
- Supports streaming, tool calling, and structured outputs

**Model Recommendations (October 2025)**:
1. **Claude Sonnet 4.5** (`anthropic/claude-sonnet-4.5`): World's best coding model (77.2% SWE-bench), 30+ hour autonomous work, superior reasoning - $3/$15 per million tokens
2. **GPT-5** (`openai/gpt-5`): OpenAI's most advanced (74.9% SWE-bench, 88% Aider polyglot, 94.6% AIME math), 400K context, excellent tool calling - $1.25/$10 per million tokens (cheaper!)
3. **Gemini 2.5 Flash** (`google/gemini-2.5-flash`): Fast with thinking capabilities, 20-30% token reduction, cost-effective

## Goals / Non-Goals

### Goals
- Provide simple, type-safe agent initialization
- Support multiple models via OpenRouter with easy switching
- Implement robust error handling for API failures
- Enable testing without live API calls
- Document model selection rationale

### Non-Goals
- Multi-agent orchestration (deferred to Epic 5+)
- Custom retry policies beyond defaults (use PydanticAI built-ins)
- Model performance benchmarking (manual testing sufficient for MVP)
- Streaming responses (will add in Story 3.2 for Chainlit integration)

## Technical Decisions

### Decision 1: Configuration Management

**What**: Centralized configuration module with environment variable support

**Implementation**:
```python
# src/agent/config.py
from pydantic import Field
from pydantic_settings import BaseSettings

class AgentConfig(BaseSettings):
    """Agent configuration from environment variables."""

    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")
    model_name: str = Field(
        default="anthropic/claude-sonnet-4.5",
        alias="AGENT_MODEL_NAME"
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, gt=0)

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }
```

**Why**:
- Pydantic Settings provides type-safe environment variable parsing
- Centralized configuration prevents scattered env var access
- Default values enable quick setup
- Validation ensures valid temperature/token ranges

**Alternatives Considered**:
- **python-decouple**: Less type-safe than Pydantic Settings
- **Direct os.environ access**: No validation, error-prone
- **Config file (TOML/YAML)**: Overkill for MVP, env vars simpler

**Trade-offs**:
- ✅ Pro: Type safety, validation, clear defaults
- ✅ Pro: Familiar pattern (matches project.md conventions)
- ❌ Con: Requires `.env` file setup (acceptable for MVP)

### Decision 2: Agent Initialization Pattern

**What**: Factory function for agent creation with dependency injection

**Implementation**:
```python
# src/agent/core.py
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings

def create_agent(
    config: AgentConfig | None = None,
    defer_model_check: bool = False
) -> Agent:
    """Create PydanticAI agent with OpenRouter integration.

    Args:
        config: Agent configuration (uses defaults if None)
        defer_model_check: Defer model validation for testing

    Returns:
        Configured PydanticAI agent instance
    """
    if config is None:
        config = AgentConfig()

    model = OpenAIModel(
        config.model_name,
        provider=OpenRouterProvider(api_key=config.openrouter_api_key),
        settings=ModelSettings(
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )
    )

    return Agent(
        model,
        defer_model_check=defer_model_check,
        system_prompt=(
            "You are Artificial-Planeswalker, an expert Magic: The Gathering "
            "deck building assistant with encyclopedic card knowledge."
        )
    )
```

**Why**:
- Factory pattern enables dependency injection for testing
- `defer_model_check` allows test environments without API keys
- System prompt centralizes agent personality
- Type hints enable IDE support and mypy validation

**Alternatives Considered**:
- **Global agent singleton**: Hard to test, not thread-safe
- **Class-based agent wrapper**: Over-engineering for MVP
- **Direct Agent() calls**: Config scattered, hard to test

**Trade-offs**:
- ✅ Pro: Testable, flexible, type-safe
- ✅ Pro: Consistent with repository pattern (project.md)
- ❌ Con: Requires function call (vs direct import), acceptable

### Decision 3: Error Handling Strategy

**What**: Three-tier error handling with retries, fallbacks, and user-friendly messages

**Implementation**:
```python
# src/agent/errors.py
class AgentError(Exception):
    """Base exception for agent errors."""
    pass

class ModelUnavailableError(AgentError):
    """LLM model unavailable or overloaded."""
    pass

class AuthenticationError(AgentError):
    """OpenRouter API key invalid or missing."""
    pass

class RateLimitError(AgentError):
    """OpenRouter rate limit exceeded."""
    pass

# src/agent/core.py (enhanced)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5)
)
async def run_agent_with_retry(
    agent: Agent,
    prompt: str
) -> str:
    """Run agent with automatic retry on rate limits."""
    try:
        result = await agent.run(prompt)
        return result.data
    except Exception as e:
        # Map OpenRouter errors to our exceptions
        if "429" in str(e):
            raise RateLimitError("Rate limit exceeded") from e
        elif "401" in str(e):
            raise AuthenticationError("Invalid API key") from e
        elif "503" in str(e):
            raise ModelUnavailableError("Model unavailable") from e
        raise AgentError(f"Agent error: {e}") from e
```

**Why**:
- Custom exceptions enable specific error handling at UI layer
- Tenacity provides battle-tested retry logic
- Exponential backoff prevents API hammering
- Error mapping translates HTTP codes to domain exceptions

**Alternatives Considered**:
- **PydanticAI built-in retries**: Less control, harder to test
- **Manual retry loops**: Reinventing wheel, error-prone
- **No retry logic**: Poor user experience on transient failures

**Trade-offs**:
- ✅ Pro: Robust, production-ready error handling
- ✅ Pro: Clear error messages for debugging
- ❌ Con: Adds tenacity dependency (acceptable, lightweight)

### Decision 4: Testing Strategy

**What**: Layered testing with TestModel for unit tests, real API for integration

**Implementation**:
```python
# tests/unit/agent/test_core.py
from pydantic_ai.models.test import TestModel

def test_agent_initialization():
    """Agent initializes with test model."""
    agent = create_agent(defer_model_check=True)
    assert agent is not None
    assert isinstance(agent, Agent)

# tests/integration/agent/test_openrouter.py
import pytest

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OpenRouter API key not configured"
)
async def test_basic_agent_response():
    """Agent generates response via OpenRouter."""
    agent = create_agent()
    result = await agent.run("What is a planeswalker?")
    assert result.data
    assert len(result.data) > 0
```

**Why**:
- Unit tests fast and isolated (no API calls)
- Integration tests validate real API interaction
- Skip integration tests when API key missing (CI-friendly)
- Pytest markers enable selective test execution

**Alternatives Considered**:
- **VCR.py for recording API responses**: Complex setup, stale recordings
- **Only mock tests**: Doesn't catch API changes
- **Only live tests**: Slow, requires API key, costs money

**Trade-offs**:
- ✅ Pro: Fast unit tests, reliable integration tests
- ✅ Pro: CI can run without API keys (unit only)
- ❌ Con: Integration tests require API key, cost minimal

## Risks / Trade-offs

### Risk 1: OpenRouter API Reliability
**Risk**: OpenRouter downtime or rate limiting impacts application availability

**Mitigation**:
- Implement retry logic with exponential backoff
- Document fallback models in configuration
- Future: Add model fallback chain (Story 2.5+)

### Risk 2: API Cost
**Risk**: Uncontrolled API usage in development/testing leads to unexpected costs

**Mitigation**:
- Use `TestModel` for unit tests (no API calls)
- Limit integration test volume
- Document cost-effective models (Gemini Flash)
- OpenRouter has spending limits feature

### Risk 3: Model Performance Variance
**Risk**: Different models have varying quality for MTG card queries

**Mitigation**:
- Default to Claude Sonnet 4.5 (state-of-the-art coding, 77.2% SWE-bench)
- Document model comparison in tests with benchmark scores
- Easy switching via environment variable (GPT-5: 74.9% SWE-bench & cheaper, Gemini 2.5)
- GPT-5 offers excellent cost/performance balance at $1.25/$10 vs Claude's $3/$15
- Future: A/B testing framework (post-MVP)

### Risk 4: Breaking API Changes
**Risk**: OpenRouter or PydanticAI updates break integration

**Mitigation**:
- Pin PydanticAI version in pyproject.toml
- Integration tests catch API changes
- Monitor PydanticAI changelog
- OpenRouter has stable API (OpenAI-compatible)

## Migration Plan

### Phase 1: Setup (Story 2.1)
1. Add PydanticAI and openai dependencies to pyproject.toml
2. Create `.env.example` with OpenRouter configuration template
3. Implement configuration module (`src/agent/config.py`)
4. Implement agent core (`src/agent/core.py`)
5. Add error handling utilities (`src/agent/errors.py`)

### Phase 2: Testing
1. Write unit tests for configuration loading
2. Write unit tests for agent initialization with TestModel
3. Write integration tests for OpenRouter communication
4. Document test execution in README

### Phase 3: Validation
1. Manual testing with OpenRouter API key
2. Test model switching (GPT-4, Claude, Gemini)
3. Test error scenarios (invalid key, rate limit)
4. Verify async operation with `asyncio.run()`

### Rollback Strategy
If OpenRouter integration fails:
1. Can revert to local models via Ollama (supported by PydanticAI)
2. Can use TestModel for demo purposes
3. No database migrations needed (agent is stateless)

## Open Questions

### Q1: Should we cache LLM responses?
**Status**: Deferred to Epic 3+

**Context**: Caching could reduce API costs and improve response time for repeated queries

**Decision Needed**: Cache strategy (Redis, SQLite, in-memory), TTL, cache key generation

**Impact**: Medium - affects cost and performance but not MVP functionality

### Q2: Should we implement streaming responses in Story 2.1?
**Status**: No, defer to Story 3.2

**Rationale**: Story 3.2 (Chainlit integration) is natural place for streaming implementation

**Impact**: Low - doesn't block tool development in Stories 2.2-2.4

### Q3: Should we support multiple simultaneous models?
**Status**: No, single model per agent instance for MVP

**Rationale**: Model switching via config is sufficient for MVP, multi-model adds complexity

**Future**: Could implement FallbackModel in Epic 5+ for redundancy

**Impact**: Low - model switching meets MVP requirements

## References

### Documentation
- [PydanticAI Agents](https://ai.pydantic.dev/agents/)
- [PydanticAI OpenAI Model](https://ai.pydantic.dev/models/openai/)
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [Tenacity Retry Library](https://tenacity.readthedocs.io/)

### Code Examples
- PydanticAI weather agent example (tool usage patterns)
- OpenRouter Python integration examples

### Research Sources
- Archon RAG: ai.pydantic.dev (PydanticAI documentation)
- Web search: OpenRouter API 2025 status and best practices

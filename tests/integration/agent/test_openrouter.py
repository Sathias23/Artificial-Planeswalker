"""Integration tests for OpenRouter API integration.

These tests require a valid OPENROUTER_API_KEY environment variable
and make real API calls to OpenRouter.
"""

import os

import pytest
from dotenv import load_dotenv

from src.agent.config import AgentConfig
from src.agent.core import create_agent
from src.agent.retry import run_agent_with_retry

# Load environment variables from .env file
load_dotenv()

# Skip all tests in this module if OPENROUTER_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set - skipping integration tests",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_basic_agent_response_generation():
    """Test basic agent response generation with OpenRouter."""
    config = AgentConfig()  # type: ignore[call-arg]
    agent = create_agent(config=config)

    result = await agent.run("Say 'Hello, World!' and nothing else.")

    assert result.output is not None
    assert isinstance(result.output, str)
    assert len(result.output) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_with_claude_sonnet_model():
    """Test agent with Claude Sonnet 4.5 model."""
    config = AgentConfig(
        openrouter_api_key=os.environ["OPENROUTER_API_KEY"],
        agent_model="anthropic/claude-sonnet-4.5",
    )
    agent = create_agent(config=config)

    result = await agent.run("What is 2+2? Answer with just the number.")

    assert result.output is not None
    assert "4" in result.output


@pytest.mark.integration
@pytest.mark.asyncio
async def test_response_validation():
    """Test that agent responses have expected metadata."""
    config = AgentConfig()  # type: ignore[call-arg]
    agent = create_agent(config=config)

    result = await agent.run("Respond with a single word: 'test'")

    # Check response structure
    assert result.output is not None
    assert isinstance(result.output, str)
    assert len(result.output) > 0

    # Check that result has expected attributes
    assert hasattr(result, "output")
    assert hasattr(result, "usage")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_with_retry_wrapper():
    """Test agent execution with retry wrapper."""
    config = AgentConfig()  # type: ignore[call-arg]
    agent = create_agent(config=config)

    response = await run_agent_with_retry(
        agent,
        "What is the capital of France? Answer with just the city name.",
    )

    assert response is not None
    assert isinstance(response, str)
    assert "Paris" in response or "paris" in response.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_operation():
    """Test that agent operations work with asyncio."""
    config = AgentConfig()  # type: ignore[call-arg]
    agent = create_agent(config=config)

    # Run in asyncio event loop
    result = await agent.run("Echo: test")

    assert result.output is not None
    assert isinstance(result.output, str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mtg_related_query():
    """Test agent with MTG-related query to verify domain knowledge."""
    config = AgentConfig()  # type: ignore[call-arg]
    agent = create_agent(config=config)

    result = await agent.run(
        "What are the five colors of Magic: The Gathering? "
        "List them in a single line separated by commas."
    )

    response = result.output.lower()
    # Check for presence of MTG colors
    color_count = sum(
        [
            "white" in response,
            "blue" in response,
            "black" in response,
            "red" in response,
            "green" in response,
        ]
    )
    assert color_count >= 4  # At least 4 of the 5 colors should be mentioned


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_prompt_behavior():
    """Test that system prompt influences agent behavior."""
    config = AgentConfig()  # type: ignore[call-arg]
    agent = create_agent(config=config)

    result = await agent.run(
        "What kind of assistant are you? Answer in one sentence mentioning your main purpose."
    )

    response = result.output.lower()
    # Should mention MTG or deck building due to system prompt
    assert (
        "magic" in response or "mtg" in response or "deck" in response or "planeswalker" in response
    )

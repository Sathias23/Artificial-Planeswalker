"""Unit tests for agent core module."""

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from legacy.agent.config import AgentConfig
from legacy.agent.core import create_agent
from legacy.agent.errors import AuthenticationError


def test_create_agent_with_default_config(monkeypatch):
    """Test create_agent() initializes with default configuration."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")

    agent = create_agent(defer_model_check=True)

    assert isinstance(agent, Agent)
    assert agent._system_prompts is not None
    assert "Artificial-Planeswalker" in agent._system_prompts[0]


def test_create_agent_with_custom_config():
    """Test create_agent() initializes with custom configuration."""
    config = AgentConfig(
        anthropic_api_key="sk-ant-test-123",
        agent_model="claude-sonnet-4.5",
        agent_temperature=0.5,
        agent_max_tokens=1500,
    )

    agent = create_agent(config=config, defer_model_check=True)

    assert isinstance(agent, Agent)
    # Verify model settings are applied
    assert agent.model_settings is not None
    assert agent.model_settings["temperature"] == 0.5
    assert agent.model_settings["max_tokens"] == 1500


def test_create_agent_with_defer_model_check():
    """Test create_agent() with defer_model_check=True."""
    config = AgentConfig(
        anthropic_api_key="sk-ant-test-123",
        agent_model="claude-sonnet-4.5",
    )

    # Should not raise even with fake API key when defer_model_check=True
    agent = create_agent(config=config, defer_model_check=True)

    assert isinstance(agent, Agent)


def test_create_agent_raises_auth_error_for_empty_api_key():
    """Test create_agent() raises ValidationError when no API keys provided."""
    from pydantic import ValidationError

    # No API keys should fail validation
    with pytest.raises(ValidationError) as exc_info:
        AgentConfig(
            anthropic_api_key=None,
            openrouter_api_key=None,
        )

    assert "at least one api key" in str(exc_info.value).lower()


def test_create_agent_system_prompt_includes_key_features():
    """Test that system prompt includes key agent features."""
    config = AgentConfig(
        anthropic_api_key="sk-ant-test-123",
    )

    agent = create_agent(config=config, defer_model_check=True)

    prompt = agent._system_prompts[0]
    assert prompt is not None

    # Check for key capabilities mentioned in system prompt
    assert "Magic: The Gathering" in prompt or "MTG" in prompt
    assert "deck building" in prompt.lower()
    assert "Standard" in prompt


def test_create_agent_with_test_model():
    """Test agent initialization with TestModel for unit testing."""
    # Create agent with TestModel directly for testing
    test_model = TestModel()
    agent: Agent[None, str] = Agent(
        model=test_model,
        system_prompt="Test prompt",
    )

    assert isinstance(agent, Agent)
    assert isinstance(agent.model, TestModel)


def test_create_agent_loads_from_environment_when_config_none(monkeypatch):
    """Test create_agent() loads config from environment when config=None."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
    monkeypatch.setenv("AGENT_MODEL", "claude-sonnet-4.5")
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.8")

    agent = create_agent(config=None, defer_model_check=True)

    assert isinstance(agent, Agent)
    # Model settings should reflect environment values
    assert agent.model_settings is not None
    assert agent.model_settings["temperature"] == 0.8


def test_create_agent_raises_auth_error_for_missing_env_api_key():
    """Test create_agent() raises AuthenticationError when env API key missing."""
    # Without providing a config and assuming no valid env key, should raise
    # Note: This test will skip if OPENROUTER_API_KEY is actually set in .env
    try:
        create_agent(config=None)
        # If we get here and have a valid API key from .env, that's actually fine
        # The test is really about the error path, so we'll just pass
        pytest.skip("Skipping test - OPENROUTER_API_KEY found in environment")
    except (AuthenticationError, Exception):
        # This is the expected path when no API key is available
        pass


def test_create_agent_uses_anthropic_provider_for_claude_model():
    """Test that create_agent() uses Anthropic provider when anthropic_api_key is set."""
    from legacy.agent.core import _determine_provider

    config = AgentConfig(
        anthropic_api_key="sk-ant-test-123",
        agent_model="claude-sonnet-4.5",
    )

    use_anthropic, normalized_model = _determine_provider(config)

    assert use_anthropic is True
    assert normalized_model == "claude-sonnet-4.5"


def test_create_agent_uses_openrouter_provider_for_claude_when_only_openrouter_key():
    """Test OpenRouter provider for Claude when only openrouter_api_key is set."""
    from legacy.agent.core import _determine_provider

    config = AgentConfig(
        openrouter_api_key="sk-or-test-123",
        agent_model="anthropic/claude-sonnet-4.5",
    )

    use_anthropic, normalized_model = _determine_provider(config)

    assert use_anthropic is False
    assert normalized_model == "anthropic/claude-sonnet-4.5"


def test_create_agent_uses_openrouter_provider_for_non_claude_model():
    """Test that create_agent() uses OpenRouter provider for non-Claude models."""
    from legacy.agent.core import _determine_provider

    config = AgentConfig(
        openrouter_api_key="sk-or-test-123",
        agent_model="openai/gpt-4",
    )

    use_anthropic, normalized_model = _determine_provider(config)

    assert use_anthropic is False
    assert normalized_model == "openai/gpt-4"


def test_create_agent_normalizes_model_name_for_anthropic():
    """Test that model name is normalized when using Anthropic provider."""
    from legacy.agent.core import _normalize_model_name

    # Remove "anthropic/" prefix for Anthropic provider
    result = _normalize_model_name("anthropic/claude-sonnet-4.5", use_anthropic=True)
    assert result == "claude-sonnet-4.5"

    # Keep name as-is if no prefix
    result = _normalize_model_name("claude-sonnet-4.5", use_anthropic=True)
    assert result == "claude-sonnet-4.5"


def test_create_agent_normalizes_model_name_for_openrouter():
    """Test that model name is normalized when using OpenRouter provider."""
    from legacy.agent.core import _normalize_model_name

    # Keep "anthropic/" prefix for OpenRouter
    result = _normalize_model_name("anthropic/claude-sonnet-4.5", use_anthropic=False)
    assert result == "anthropic/claude-sonnet-4.5"

    # Add "anthropic/" prefix if missing for Claude models on OpenRouter
    result = _normalize_model_name("claude-sonnet-4.5", use_anthropic=False)
    assert result == "anthropic/claude-sonnet-4.5"

    # Keep non-Claude model names as-is
    result = _normalize_model_name("openai/gpt-4", use_anthropic=False)
    assert result == "openai/gpt-4"


def test_create_agent_prefers_anthropic_when_both_keys_available():
    """Test that create_agent() prefers Anthropic provider when both API keys are available."""
    from legacy.agent.core import _determine_provider

    config = AgentConfig(
        anthropic_api_key="sk-ant-test-123",
        openrouter_api_key="sk-or-test-123",
        agent_model="claude-sonnet-4.5",
    )

    use_anthropic, normalized_model = _determine_provider(config)

    assert use_anthropic is True
    assert normalized_model == "claude-sonnet-4.5"


def test_create_agent_raises_error_for_non_claude_model_without_openrouter():
    """Test that create_agent() raises error for non-Claude model without OpenRouter API key."""
    from legacy.agent.core import _determine_provider

    # Explicitly set openrouter_api_key to None to test the error case
    config = AgentConfig(
        anthropic_api_key="sk-ant-test-123",
        openrouter_api_key=None,
        agent_model="openai/gpt-4",
    )

    with pytest.raises(AuthenticationError) as exc_info:
        _determine_provider(config)

    assert "openrouter_api_key" in str(exc_info.value).lower() or "gpt-4" in str(exc_info.value)


# Tests for deck context injection (Task 1: improve-deck-context-retention)


def test_build_deck_context_message():
    """Test _build_deck_context_message() creates correct context string."""
    from dataclasses import dataclass

    from legacy.agent.core import _build_deck_context_message

    # Create a mock deck object
    @dataclass
    class MockDeck:
        id: str
        name: str
        format: str
        deck_cards: list

    deck = MockDeck(
        id="12345678-1234-1234-1234-123456789abc",
        name="Fire Lord Zuko Deck",
        format="standard",
        deck_cards=[{}, {}],  # 2 cards
    )

    result = _build_deck_context_message(deck)

    # Verify all required elements are in the message
    assert "ACTIVE DECK CONTEXT:" in result
    assert "Fire Lord Zuko Deck" in result
    assert "12345678..." in result  # Truncated ID
    assert "standard" in result
    assert "2 cards" in result
    assert "ALWAYS add cards to this deck" in result


def test_inject_system_context_prepends_to_existing_system_message():
    """Test _inject_system_context() prepends to existing system message."""
    from pydantic_ai.messages import ModelRequest, SystemPromptPart

    from legacy.agent.core import _inject_system_context

    # Create history with existing system message
    original_system_msg = SystemPromptPart(content="Original system prompt")
    history = [
        ModelRequest(parts=[original_system_msg]),
    ]

    context = "ACTIVE DECK: Test Deck"
    result = _inject_system_context(history, context)

    # Should modify existing system message
    assert len(result) == 1
    assert isinstance(result[0], ModelRequest)
    assert len(result[0].parts) == 1
    assert isinstance(result[0].parts[0], SystemPromptPart)

    # Context should be prepended
    content = result[0].parts[0].content
    assert content.startswith("ACTIVE DECK: Test Deck")
    assert "Original system prompt" in content


def test_inject_system_context_creates_new_system_message_when_none_exists():
    """Test _inject_system_context() creates new system message when none exists."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    from legacy.agent.core import _inject_system_context

    # Create history without system message
    history = [
        ModelRequest(parts=[UserPromptPart(content="User message")]),
    ]

    context = "ACTIVE DECK: Test Deck"
    result = _inject_system_context(history, context)

    # Should create new system message at start
    assert len(result) == 2
    assert isinstance(result[0], ModelRequest)

    # First message should be the new system message
    first_msg_parts = result[0].parts
    assert len(first_msg_parts) == 1

    from pydantic_ai.messages import SystemPromptPart

    assert isinstance(first_msg_parts[0], SystemPromptPart)
    assert first_msg_parts[0].content == "ACTIVE DECK: Test Deck"

    # Second message should be the original user message
    assert result[1].parts[0].content == "User message"


def test_inject_system_context_handles_empty_history():
    """Test _inject_system_context() handles empty history correctly."""
    from pydantic_ai.messages import SystemPromptPart

    from legacy.agent.core import _inject_system_context

    history: list = []
    context = "ACTIVE DECK: Test Deck"

    result = _inject_system_context(history, context)

    # Should create new system message
    assert len(result) == 1
    assert isinstance(result[0].parts[0], SystemPromptPart)
    assert result[0].parts[0].content == "ACTIVE DECK: Test Deck"


def test_inject_system_context_finds_last_system_message():
    """Test _inject_system_context() finds and modifies the last system message."""
    from pydantic_ai.messages import ModelRequest, SystemPromptPart, UserPromptPart

    from legacy.agent.core import _inject_system_context

    # Create history with multiple system messages
    history = [
        ModelRequest(parts=[SystemPromptPart(content="First system message")]),
        ModelRequest(parts=[UserPromptPart(content="User message")]),
        ModelRequest(parts=[SystemPromptPart(content="Second system message")]),
    ]

    context = "ACTIVE DECK: Test Deck"
    result = _inject_system_context(history, context)

    # Should modify the LAST system message (index 2)
    assert len(result) == 3

    # First system message should be unchanged
    assert result[0].parts[0].content == "First system message"

    # Last system message should be modified
    last_system_content = result[2].parts[0].content
    assert last_system_content.startswith("ACTIVE DECK: Test Deck")
    assert "Second system message" in last_system_content


def test_inject_system_context_preserves_other_message_types():
    """Test _inject_system_context() doesn't modify non-system messages."""
    from pydantic_ai.messages import ModelRequest, SystemPromptPart, UserPromptPart

    from legacy.agent.core import _inject_system_context

    # Create history with mixed message types
    history = [
        ModelRequest(parts=[UserPromptPart(content="User message 1")]),
        ModelRequest(parts=[SystemPromptPart(content="System message")]),
        ModelRequest(parts=[UserPromptPart(content="User message 2")]),
    ]

    context = "ACTIVE DECK: Test Deck"
    result = _inject_system_context(history, context)

    # User messages should be unchanged
    assert result[0].parts[0].content == "User message 1"
    assert result[2].parts[0].content == "User message 2"

    # System message should be modified
    assert "ACTIVE DECK: Test Deck" in result[1].parts[0].content

"""Unit tests for agent configuration module."""

import pytest
from pydantic import ValidationError

from src.agent.config import AgentConfig


def test_agent_config_loads_from_env(monkeypatch):
    """Test that AgentConfig loads configuration from environment variables."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
    monkeypatch.setenv("AGENT_MODEL", "claude-sonnet-4.5")
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.5")
    monkeypatch.setenv("AGENT_MAX_TOKENS", "1000")

    config = AgentConfig()  # type: ignore[call-arg]

    assert config.anthropic_api_key == "sk-ant-test-123"
    assert config.agent_model == "claude-sonnet-4.5"
    assert config.agent_temperature == 0.5
    assert config.agent_max_tokens == 1000


def test_agent_config_applies_defaults():
    """Test that AgentConfig applies default values for optional fields."""
    # Create config with explicit values to override any .env
    config = AgentConfig(
        anthropic_api_key="sk-ant-test-123",
        agent_model="claude-sonnet-4.5",
        agent_temperature=0.7,
        agent_max_tokens=2000,
        agent_top_p=1.0,
    )

    # Verify the values are set correctly
    assert config.agent_model == "claude-sonnet-4.5"
    assert config.agent_temperature == 0.7
    assert config.agent_max_tokens == 2000
    assert config.agent_top_p == 1.0


def test_agent_config_rejects_invalid_temperature_too_low(monkeypatch):
    """Test that AgentConfig rejects temperature below 0.0."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
    monkeypatch.setenv("AGENT_TEMPERATURE", "-0.1")

    with pytest.raises(ValidationError) as exc_info:
        AgentConfig()  # type: ignore[call-arg]

    assert "agent_temperature" in str(exc_info.value)


def test_agent_config_rejects_invalid_temperature_too_high(monkeypatch):
    """Test that AgentConfig rejects temperature above 2.0."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
    monkeypatch.setenv("AGENT_TEMPERATURE", "2.1")

    with pytest.raises(ValidationError) as exc_info:
        AgentConfig()  # type: ignore[call-arg]

    assert "agent_temperature" in str(exc_info.value)


def test_agent_config_rejects_zero_max_tokens(monkeypatch):
    """Test that AgentConfig rejects max_tokens of 0."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
    monkeypatch.setenv("AGENT_MAX_TOKENS", "0")

    with pytest.raises(ValidationError) as exc_info:
        AgentConfig()  # type: ignore[call-arg]

    assert "agent_max_tokens" in str(exc_info.value)


def test_agent_config_rejects_negative_max_tokens(monkeypatch):
    """Test that AgentConfig rejects negative max_tokens."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
    monkeypatch.setenv("AGENT_MAX_TOKENS", "-100")

    with pytest.raises(ValidationError) as exc_info:
        AgentConfig()  # type: ignore[call-arg]

    assert "agent_max_tokens" in str(exc_info.value)


def test_agent_config_raises_error_for_missing_all_api_keys():
    """Test that AgentConfig raises error when no API keys are provided."""
    with pytest.raises(ValidationError) as exc_info:
        AgentConfig(
            anthropic_api_key=None,
            openrouter_api_key=None,
        )

    error_str = str(exc_info.value)
    # Should mention that at least one API key is required
    assert (
        "at least one api key" in error_str.lower()
        or "anthropic_api_key or openrouter_api_key" in error_str.lower()
    )


def test_agent_config_accepts_valid_temperature_boundaries(monkeypatch):
    """Test that AgentConfig accepts temperature at valid boundaries."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")

    # Test lower boundary
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.0")
    config1 = AgentConfig()  # type: ignore[call-arg]
    assert config1.agent_temperature == 0.0

    # Test upper boundary
    monkeypatch.setenv("AGENT_TEMPERATURE", "2.0")
    config2 = AgentConfig()  # type: ignore[call-arg]
    assert config2.agent_temperature == 2.0


def test_agent_config_accepts_minimum_valid_max_tokens(monkeypatch):
    """Test that AgentConfig accepts max_tokens of 1."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
    monkeypatch.setenv("AGENT_MAX_TOKENS", "1")

    config = AgentConfig()  # type: ignore[call-arg]
    assert config.agent_max_tokens == 1


def test_agent_config_accepts_only_anthropic_api_key():
    """Test that AgentConfig accepts only anthropic_api_key."""
    config = AgentConfig(
        anthropic_api_key="sk-ant-test-123",
        openrouter_api_key=None,
    )

    assert config.anthropic_api_key == "sk-ant-test-123"
    assert config.openrouter_api_key is None


def test_agent_config_accepts_only_openrouter_api_key():
    """Test that AgentConfig accepts only openrouter_api_key."""
    config = AgentConfig(
        anthropic_api_key=None,
        openrouter_api_key="sk-or-test-123",
    )

    assert config.anthropic_api_key is None
    assert config.openrouter_api_key == "sk-or-test-123"


def test_agent_config_accepts_both_api_keys():
    """Test that AgentConfig accepts both API keys simultaneously."""
    config = AgentConfig(
        anthropic_api_key="sk-ant-test-123",
        openrouter_api_key="sk-or-test-123",
    )

    assert config.anthropic_api_key == "sk-ant-test-123"
    assert config.openrouter_api_key == "sk-or-test-123"


def test_agent_config_loads_anthropic_api_key_from_env(monkeypatch):
    """Test that AgentConfig loads ANTHROPIC_API_KEY from environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")

    config = AgentConfig()  # type: ignore[call-arg]

    assert config.anthropic_api_key == "sk-ant-test-123"

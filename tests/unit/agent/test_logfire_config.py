"""Tests for Logfire configuration in AgentConfig."""

import pytest
from pydantic import ValidationError

from src.agent.config import AgentConfig


class TestLogfireConfiguration:
    """Test Logfire configuration validation in AgentConfig."""

    def test_logfire_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that Logfire is disabled by default."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.delenv("LOGFIRE_ENABLED", raising=False)

        config = AgentConfig()  # type: ignore[call-arg]

        assert config.logfire_enabled is False
        assert config.logfire_token is None
        assert config.logfire_project == "artificial-planeswalker"

    def test_logfire_enabled_without_token_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that enabling Logfire without token raises validation error."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setenv("LOGFIRE_ENABLED", "true")
        monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            AgentConfig()  # type: ignore[call-arg]

        assert "LOGFIRE_TOKEN required when LOGFIRE_ENABLED=true" in str(exc_info.value)

    def test_logfire_enabled_with_token_loads_successfully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that Logfire configuration loads when enabled with token."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setenv("LOGFIRE_ENABLED", "true")
        monkeypatch.setenv("LOGFIRE_TOKEN", "lf_test_token_12345")
        monkeypatch.setenv("LOGFIRE_PROJECT", "test-project")

        config = AgentConfig()  # type: ignore[call-arg]

        assert config.logfire_enabled is True
        assert config.logfire_token == "lf_test_token_12345"
        assert config.logfire_project == "test-project"

    def test_logfire_disabled_without_token_loads_successfully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that disabled Logfire loads successfully without token."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setenv("LOGFIRE_ENABLED", "false")
        monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)

        config = AgentConfig()  # type: ignore[call-arg]

        assert config.logfire_enabled is False
        assert config.logfire_token is None

    def test_logfire_default_project_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that Logfire project defaults to 'artificial-planeswalker'."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.delenv("LOGFIRE_PROJECT", raising=False)

        config = AgentConfig()  # type: ignore[call-arg]

        assert config.logfire_project == "artificial-planeswalker"

    def test_logfire_custom_project_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that custom Logfire project name is respected."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setenv("LOGFIRE_PROJECT", "custom-project-name")

        config = AgentConfig()  # type: ignore[call-arg]

        assert config.logfire_project == "custom-project-name"

    def test_logfire_enabled_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that LOGFIRE_ENABLED accepts case-insensitive values."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setenv("LOGFIRE_ENABLED", "True")  # Capitalized
        monkeypatch.setenv("LOGFIRE_TOKEN", "lf_test_token")

        config = AgentConfig()  # type: ignore[call-arg]

        assert config.logfire_enabled is True

    def test_logfire_enabled_string_parsing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that LOGFIRE_ENABLED parses '1' as True."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setenv("LOGFIRE_ENABLED", "1")
        monkeypatch.setenv("LOGFIRE_TOKEN", "lf_test_token")

        config = AgentConfig()  # type: ignore[call-arg]

        assert config.logfire_enabled is True

"""Agent configuration module for Artificial-Planeswalker.

This module provides configuration management for the PydanticAI agent,
including OpenRouter integration settings and model parameters.
"""

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    """Configuration for the PydanticAI agent with Anthropic and OpenRouter integration.

    Attributes:
        anthropic_api_key: API key for Anthropic service (preferred for Claude models)
        openrouter_api_key: API key for OpenRouter service (for non-Claude models)
        model: Model identifier (e.g., "claude-sonnet-4.5" or "openai/gpt-4")
        temperature: Sampling temperature (0.0-2.0), controls randomness
        max_tokens: Maximum tokens in response, must be positive
        top_p: Nucleus sampling parameter (0.0-1.0)
        logfire_enabled: Enable Pydantic Logfire observability
        logfire_token: API token for Logfire platform (required when enabled)
        logfire_project: Logfire project name

    Note:
        At least one of anthropic_api_key or openrouter_api_key must be provided.
        For Claude models, anthropic_api_key is preferred when available.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables like DATABASE_URL
        env_ignore_empty=True,  # Ignore empty values
    )

    # API Keys (at least one required, validated in model_validator)
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key for Claude models (preferred)",
    )

    openrouter_api_key: str | None = Field(
        default=None,
        description="OpenRouter API key for multi-model access",
    )

    # Model configuration with defaults
    agent_model: str = Field(
        default="anthropic/claude-sonnet-4.5",
        description="Model identifier for OpenRouter",
    )

    agent_temperature: float = Field(
        default=0.7,
        description="Sampling temperature (0.0-2.0)",
        ge=0.0,
        le=2.0,
    )

    agent_max_tokens: int = Field(
        default=2000,
        description="Maximum tokens in response",
        gt=0,
    )

    agent_top_p: float = Field(
        default=1.0,
        description="Nucleus sampling parameter",
        ge=0.0,
        le=1.0,
    )

    # Logfire observability configuration
    logfire_enabled: bool = Field(
        default=False,
        description="Enable Pydantic Logfire observability tracing",
    )

    logfire_token: str | None = Field(
        default=None,
        description="Logfire API token (required when logfire_enabled=True)",
    )

    logfire_project: str = Field(
        default="artificial-planeswalker",
        description="Logfire project name",
    )

    @field_validator("agent_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range.

        Args:
            v: Temperature value to validate

        Returns:
            Validated temperature value

        Raises:
            ValueError: If temperature is outside valid range
        """
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {v}")
        return v

    @field_validator("agent_max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        """Validate max_tokens is positive.

        Args:
            v: Max tokens value to validate

        Returns:
            Validated max tokens value

        Raises:
            ValueError: If max_tokens is not positive
        """
        if v <= 0:
            raise ValueError(f"Max tokens must be positive, got {v}")
        return v

    @model_validator(mode="after")
    def validate_logfire_config(self) -> "AgentConfig":
        """Validate Logfire configuration consistency.

        Ensures that when Logfire is enabled, a valid token is provided.

        Returns:
            Validated AgentConfig instance

        Raises:
            ValueError: If logfire_enabled=True but logfire_token is not provided
        """
        if self.logfire_enabled and not self.logfire_token:
            raise ValueError("LOGFIRE_TOKEN required when LOGFIRE_ENABLED=true")
        return self

    @model_validator(mode="after")
    def validate_api_keys(self) -> "AgentConfig":
        """Validate that at least one API key is provided.

        Ensures that either anthropic_api_key or openrouter_api_key is configured.

        Returns:
            Validated AgentConfig instance

        Raises:
            ValueError: If no API keys are provided
        """
        if not self.anthropic_api_key and not self.openrouter_api_key:
            raise ValueError(
                "At least one API key required: set ANTHROPIC_API_KEY or OPENROUTER_API_KEY"
            )
        return self

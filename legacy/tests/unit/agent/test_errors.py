"""Unit tests for agent error classes."""

from legacy.agent.errors import (
    AgentError,
    AuthenticationError,
    ModelUnavailableError,
    RateLimitError,
)


def test_agent_error_with_message_only():
    """Test AgentError with message only."""
    error = AgentError("Something went wrong")

    assert error.message == "Something went wrong"
    assert error.details == {}
    assert str(error) == "Something went wrong"


def test_agent_error_with_details():
    """Test AgentError with message and details."""
    error = AgentError(
        "Operation failed",
        details={"code": "500", "reason": "server_error"},
    )

    assert error.message == "Operation failed"
    assert error.details == {"code": "500", "reason": "server_error"}
    assert "code=500" in str(error)
    assert "reason=server_error" in str(error)


def test_agent_error_format_message():
    """Test AgentError message formatting."""
    error = AgentError("Test error", details={"key": "value"})
    formatted = error.format_message()

    assert "Test error" in formatted
    assert "key=value" in formatted


def test_authentication_error_default_message():
    """Test AuthenticationError has appropriate default message."""
    error = AuthenticationError()

    assert "Authentication failed" in error.message
    assert "OpenRouter API key" in error.message
    assert isinstance(error, AgentError)


def test_authentication_error_with_details():
    """Test AuthenticationError with additional details."""
    error = AuthenticationError(details={"status_code": "401"})

    assert "Authentication failed" in error.message
    assert error.details == {"status_code": "401"}
    assert "status_code=401" in str(error)


def test_authentication_error_inheritance():
    """Test AuthenticationError inherits from AgentError."""
    error = AuthenticationError()

    assert isinstance(error, AgentError)
    assert isinstance(error, Exception)


def test_rate_limit_error_default_message():
    """Test RateLimitError has appropriate default message."""
    error = RateLimitError()

    assert "Rate limit exceeded" in error.message
    assert "OpenRouter API" in error.message
    assert isinstance(error, AgentError)


def test_rate_limit_error_with_retry_after():
    """Test RateLimitError with retry_after parameter."""
    error = RateLimitError(retry_after=60)

    assert "Rate limit exceeded" in error.message
    assert error.details == {"retry_after": "60"}
    assert "retry_after=60" in str(error)


def test_rate_limit_error_inheritance():
    """Test RateLimitError inherits from AgentError."""
    error = RateLimitError()

    assert isinstance(error, AgentError)
    assert isinstance(error, Exception)


def test_model_unavailable_error_with_model():
    """Test ModelUnavailableError with model parameter."""
    error = ModelUnavailableError(model="anthropic/claude-sonnet-4.5")

    assert "Model unavailable" in error.message
    assert "anthropic/claude-sonnet-4.5" in error.message
    assert error.details["model"] == "anthropic/claude-sonnet-4.5"


def test_model_unavailable_error_with_additional_details():
    """Test ModelUnavailableError with additional details."""
    error = ModelUnavailableError(
        model="openai/gpt-5",
        details={"status_code": "503", "message": "Service unavailable"},
    )

    assert "Model unavailable" in error.message
    assert "openai/gpt-5" in error.message
    assert error.details["model"] == "openai/gpt-5"
    assert error.details["status_code"] == "503"
    assert error.details["message"] == "Service unavailable"


def test_model_unavailable_error_inheritance():
    """Test ModelUnavailableError inherits from AgentError."""
    error = ModelUnavailableError(model="test-model")

    assert isinstance(error, AgentError)
    assert isinstance(error, Exception)


def test_error_hierarchy():
    """Test that all custom errors inherit from AgentError."""
    auth_error = AuthenticationError()
    rate_error = RateLimitError()
    model_error = ModelUnavailableError(model="test")

    assert isinstance(auth_error, AgentError)
    assert isinstance(rate_error, AgentError)
    assert isinstance(model_error, AgentError)


def test_error_can_be_caught_as_agent_error():
    """Test that specific errors can be caught as AgentError."""
    try:
        raise AuthenticationError()
    except AgentError as e:
        assert isinstance(e, AuthenticationError)
        assert "Authentication failed" in str(e)


def test_error_message_formatting_with_empty_details():
    """Test error message formatting when details dict is empty."""
    error = AgentError("Test message", details={})

    formatted = error.format_message()
    assert formatted == "Test message"
    assert "=" not in formatted

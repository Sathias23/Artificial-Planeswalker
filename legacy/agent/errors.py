"""Custom exception classes for agent operations.

This module defines exception hierarchy for handling agent-related errors
including authentication, rate limiting, and model availability issues.
"""


class AgentError(Exception):
    """Base exception for all agent-related errors.

    Attributes:
        message: Human-readable error message
        details: Additional context about the error
    """

    def __init__(self, message: str, details: dict[str, str] | None = None) -> None:
        """Initialize agent error.

        Args:
            message: Human-readable error message
            details: Optional dict with additional error context
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format error message with details.

        Returns:
            Formatted error message string
        """
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class AuthenticationError(AgentError):
    """Exception raised for API key authentication failures.

    This error indicates invalid or missing API credentials.
    """

    def __init__(self, details: dict[str, str] | None = None) -> None:
        """Initialize authentication error.

        Args:
            details: Optional dict with additional error context
        """
        super().__init__(
            "Authentication failed: Invalid or missing OpenRouter API key",
            details,
        )


class RateLimitError(AgentError):
    """Exception raised when API rate limits are exceeded.

    This error indicates too many requests have been made
    and retry with exponential backoff should be attempted.
    """

    def __init__(self, retry_after: int | None = None) -> None:
        """Initialize rate limit error.

        Args:
            retry_after: Optional seconds to wait before retry
        """
        details = {"retry_after": str(retry_after)} if retry_after else None
        super().__init__(
            "Rate limit exceeded: Too many requests to OpenRouter API",
            details,
        )


class ModelUnavailableError(AgentError):
    """Exception raised when requested model is unavailable.

    This error indicates the model service is down or the
    specified model identifier is invalid.
    """

    def __init__(self, model: str, details: dict[str, str] | None = None) -> None:
        """Initialize model unavailable error.

        Args:
            model: Model identifier that was unavailable
            details: Optional dict with additional error context
        """
        error_details = {"model": model}
        if details:
            error_details.update(details)
        super().__init__(
            f"Model unavailable: {model} cannot be accessed",
            error_details,
        )

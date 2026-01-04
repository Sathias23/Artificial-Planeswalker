"""Retry utilities for agent operations with exponential backoff.

This module provides retry logic for handling transient failures
such as rate limiting and temporary service unavailability.
"""

import logging
from typing import Any

from openai import APIError, APIStatusError
from openai import RateLimitError as OpenAIRateLimitError
from pydantic_ai import Agent
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .errors import AuthenticationError, ModelUnavailableError, RateLimitError

logger = logging.getLogger(__name__)


def map_openai_error(error: Exception) -> Exception:
    """Map OpenAI SDK errors to custom agent errors.

    Args:
        error: Original exception from OpenAI SDK

    Returns:
        Mapped custom exception or original if no mapping exists
    """
    if isinstance(error, OpenAIRateLimitError):
        # Extract retry_after from error if available
        retry_after = getattr(error, "retry_after", None)
        return RateLimitError(retry_after=retry_after)

    if isinstance(error, APIStatusError):
        if error.status_code == 401:
            return AuthenticationError(details={"status_code": str(error.status_code)})
        if error.status_code in (502, 503, 504):
            return ModelUnavailableError(
                model="unknown",
                details={"status_code": str(error.status_code), "message": str(error)},
            )

    return error


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    reraise=True,
)
async def run_agent_with_retry(
    agent: Agent[None, str],
    prompt: str,
    **kwargs: Any,
) -> str:
    """Run agent with automatic retry on rate limit errors.

    This function wraps agent execution with exponential backoff retry logic
    for rate limit errors. Non-retryable errors are raised immediately.

    Args:
        agent: PydanticAI agent instance
        prompt: User prompt to send to agent
        **kwargs: Additional arguments to pass to agent.run()

    Returns:
        Agent response text

    Raises:
        RateLimitError: If rate limit persists after all retries
        AuthenticationError: If authentication fails
        ModelUnavailableError: If model is unavailable
        AgentError: For other agent-related errors

    Example:
        >>> agent = create_agent()
        >>> response = await run_agent_with_retry(agent, "Show me Lightning Bolt")
    """
    try:
        result = await agent.run(prompt, **kwargs)
        output: str = result.output
        return output
    except (APIError, APIStatusError, OpenAIRateLimitError) as e:
        # Map OpenAI errors to custom errors
        mapped_error = map_openai_error(e)

        # Log retry attempts for rate limits
        if isinstance(mapped_error, RateLimitError):
            logger.warning(
                "Rate limit encountered, retrying with exponential backoff",
                extra={"details": mapped_error.details},
            )

        raise mapped_error from e

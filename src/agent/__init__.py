"""Agent module for Artificial-Planeswalker.

This module provides the PydanticAI agent infrastructure with OpenRouter integration,
including configuration, error handling, and retry logic.
"""

from .config import AgentConfig
from .core import create_agent, run_agent_with_session
from .dependencies import AgentDependencies
from .errors import (
    AgentError,
    AuthenticationError,
    ModelUnavailableError,
    RateLimitError,
)
from .retry import run_agent_with_retry

__all__ = [
    "AgentConfig",
    "AgentDependencies",
    "AgentError",
    "AuthenticationError",
    "ModelUnavailableError",
    "RateLimitError",
    "create_agent",
    "run_agent_with_retry",
    "run_agent_with_session",
]

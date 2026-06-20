"""Chainlit-based chat interface for Artificial-Planeswalker.

This module provides the UI layer in the four-layer architecture:
Data -> Logic -> Agent -> UI

The UI layer is intentionally thin, delegating all business logic and data
access to the agent layer. This separation enables future UI replacements
(e.g., CopilotKit + AG-UI) without refactoring core functionality.
"""

__all__: list[str] = []

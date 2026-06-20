"""Agent tools for PydanticAI agent.

This package contains all tool implementations that the PydanticAI agent
can use to interact with the system. Tools are registered with the agent
using the @agent.tool decorator and receive dependencies through RunContext.

Available tools:
    - card_lookup: Search and retrieve Magic: The Gathering card information
"""

from legacy.agent.tools.card_lookup import lookup_card_by_name

__all__ = ["lookup_card_by_name"]

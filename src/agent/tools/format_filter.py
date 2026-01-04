"""Format filter control tool for card queries.

This module provides an agent tool that allows users to enable or disable
format legality filtering for card searches.
"""

from pydantic_ai import RunContext

from src.agent.core import _session_manager
from src.agent.dependencies import AgentDependencies


async def set_format_filter(
    ctx: RunContext[AgentDependencies],
    format_name: str | None,
) -> str:
    """Enable or disable format legality filtering for card queries.

    This tool allows users to control whether card searches should be filtered
    by format legality. When enabled, only cards legal in the specified format
    will be returned by card query tools. The filter preference is persisted to
    the session and will remain active across subsequent messages.

    Args:
        ctx: PydanticAI context containing agent dependencies
        format_name: Format to filter by ("standard") or None to disable filtering.
            Use None or empty string to show all cards regardless of legality.

    Returns:
        Confirmation message indicating the new filter status

    Examples:
        >>> # Enable Standard format filter
        >>> result = await set_format_filter(ctx, "standard")
        >>> # Disable format filter
        >>> result = await set_format_filter(ctx, None)
    """
    session_id = ctx.deps.session_id

    # Normalize empty string to None
    if format_name == "" or format_name is None:
        # Update current message scope
        ctx.deps.format_filter = None
        # Persist to session for future messages
        _session_manager.set_format_filter(session_id, None)
        return (
            "Format filter disabled. I'll now show all cards regardless of format legality. "
            "This includes cards from sets outside Standard."
        )

    # Validate format name
    format_lower = format_name.lower()
    if format_lower == "standard":
        # Update current message scope
        ctx.deps.format_filter = "standard"
        # Persist to session for future messages
        _session_manager.set_format_filter(session_id, "standard")
        return (
            "Format filter set to Standard. I'll now only show Standard-legal cards in searches. "
            "To see all cards, you can disable the format filter anytime."
        )
    else:
        # Unsupported format
        return (
            f"Format '{format_name}' is not supported yet. "
            f"Currently supported formats: standard. "
            f"The format filter remains unchanged ({ctx.deps.format_filter or 'disabled'})."
        )

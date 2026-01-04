"""User preference management tools for PydanticAI agent.

This module provides tools for managing user preferences that persist across
conversation sessions (e.g., auto-feedback settings).
"""

from pydantic_ai import RunContext

from src.agent.dependencies import AgentDependencies


async def toggle_auto_feedback(ctx: RunContext[AgentDependencies], enabled: bool) -> str:
    """Toggle automatic mana curve feedback on or off for the current session.

    This tool allows users to enable or disable automatic mana curve feedback
    that is generated when cards are added to a deck. The preference persists
    across messages within the same session until explicitly changed or the
    session ends.

    Default state: Enabled (auto-feedback is on by default).

    Args:
        ctx: PydanticAI run context with agent dependencies
        enabled: True to enable auto-feedback, False to disable

    Returns:
        User-friendly confirmation message

    Examples:
        User: "disable curve feedback" or "turn off auto-feedback"
        Agent invokes: toggle_auto_feedback(ctx, enabled=False)
        Returns: "Automatic curve feedback disabled. You can still request
                 analysis with 'analyze my mana curve'."

        User: "enable curve feedback" or "turn on auto-feedback"
        Agent invokes: toggle_auto_feedback(ctx, enabled=True)
        Returns: "Automatic curve feedback enabled. I'll provide real-time
                 curve guidance as you build."

    Notes:
        - Preference persists across messages in same session
        - Default is enabled (opt-out model)
        - Users can always request manual analysis via analyze_mana_curve tool
    """
    # Extract dependencies from context
    deps = ctx.deps

    # Set preference via AgentDependencies
    deps.set_auto_feedback_enabled(enabled)

    # Return confirmation message
    if enabled:
        return (
            "Automatic curve feedback enabled. I'll provide real-time curve guidance "
            "as you build your deck."
        )
    else:
        return (
            "Automatic curve feedback disabled. You can still request analysis anytime "
            "with 'analyze my mana curve'."
        )

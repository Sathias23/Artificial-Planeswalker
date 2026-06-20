"""Games availability filter control tool for card queries.

This module provides an agent tool that allows users to enable or disable
games availability filtering for card searches.
"""

from pydantic_ai import RunContext

from legacy.agent.core import _session_manager
from legacy.agent.dependencies import AgentDependencies


async def set_games_filter(
    ctx: RunContext[AgentDependencies],
    games: list[str] | None,
) -> str:
    """Enable or disable games availability filtering for card queries.

    This tool allows users to control whether card searches should be filtered
    by game availability (paper, arena, mtgo). When enabled, only cards available
    on the specified platform(s) will be returned by card query tools. The filter
    preference is persisted to the session and will remain active across subsequent
    messages.

    Args:
        ctx: PydanticAI context containing agent dependencies
        games: List of games to filter by (["paper"], ["arena"], ["mtgo"], or
            combinations like ["paper", "arena"]) or None to disable filtering.
            Use None or empty list to show all cards regardless of platform.

    Returns:
        Confirmation message indicating the new filter status

    Examples:
        >>> # Enable Arena-only filter
        >>> result = await set_games_filter(ctx, ["arena"])
        >>> # Enable paper and MTGO filter
        >>> result = await set_games_filter(ctx, ["paper", "mtgo"])
        >>> # Disable games filter
        >>> result = await set_games_filter(ctx, None)
    """
    session_id = ctx.deps.session_id

    # Normalize empty list/None to None
    if games is None or len(games) == 0:
        # Update current message scope
        ctx.deps.games_filter = None
        # Persist to session for future messages
        _session_manager.set_games_filter(session_id, None)
        return (
            "Games filter disabled. I'll now show all cards regardless of platform "
            "availability (paper, Arena, MTGO)."
        )

    # Validate game names
    valid_games = {"paper", "arena", "mtgo"}
    normalized_games = [g.lower() for g in games]
    invalid_games = set(normalized_games) - valid_games

    if invalid_games:
        return (
            f"Invalid game(s): {', '.join(invalid_games)}. "
            f"Valid options are: {', '.join(sorted(valid_games))}. "
            f"The games filter remains unchanged ({ctx.deps.games_filter or 'disabled'})."
        )

    # Update current message scope
    ctx.deps.games_filter = normalized_games
    # Persist to session for future messages
    _session_manager.set_games_filter(session_id, normalized_games)

    # Build friendly message
    if len(normalized_games) == 1:
        platform_desc = normalized_games[0].capitalize()
    else:
        platform_desc = " and ".join([g.capitalize() for g in normalized_games])

    return (
        f"Games filter set to {platform_desc}. I'll now only show cards available on "
        f"{platform_desc} in searches. To see all cards, you can disable the games filter anytime."
    )

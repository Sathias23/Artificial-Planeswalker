"""FastMCP server builder for the Arena game-state server.

One read-only tool over :mod:`src.arena`. The reading is synchronous file and SQLite work, so the
tool runs it in ``asyncio.to_thread`` and the card database connection is opened, used and closed
on that worker thread.
"""

import asyncio
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from src.arena.models import GameStateResult
from src.arena.reader import read_game_state as _read_game_state


def build_server(log_path: Path | None = None, card_database: Path | None = None) -> FastMCP:
    """Build the FastMCP server with its tool registered.

    Args:
        log_path: The ``Player.log`` to read. ``None`` (production) discovers it on every call.
        card_database: The Arena client's card database file. ``None`` (production) discovers it
            on every call. Both are test seams.

    Returns:
        A configured ``FastMCP`` instance.
    """
    mcp = FastMCP("arena-game-state")

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def read_game_state(
        recent_events: int = 15, include_card_text: bool = False
    ) -> GameStateResult:
        """Read the current MTG Arena game straight from the running client: no screenshot needed.

        Use this whenever the user asks about a game they are playing or just played in MTG
        Arena ("what should I play?", "what's on the board?", "what just happened?"). It returns
        what the user can see on screen, as exact card names: both life totals, the turn and
        phase, the user's hand, both battlefields (tapped, attacking and blocking state, current
        power/toughness, counters, attachments), graveyards, exile, the command zone, the stack
        with targets, and the plays the game is currently offering the user. Hidden information
        stays hidden: the opponent's hand and both libraries are counts only.

        It reads the latest game in Arena's log, so call it again for a fresh state each time
        the user asks; nothing is remembered between calls. A finished game is still returned
        (``in_progress`` false, ``result`` set) so it can be reviewed. Read-only: it cannot act
        in the game.

        Identical cards are merged into one entry with a ``count``, and fields with nothing to
        report are left out, so an absent ``flags`` means untapped and not in combat. Card names
        match this plugin's card tools, so pass one to ``lookup_card_by_name`` for full details,
        or set ``include_card_text`` for every card at once.

        Args:
            recent_events: How many of the latest game events to list in ``recent_events``,
                oldest first (0 to 50; default 15).
            include_card_text: Also return ``card_text``, the cost, type and rules text of every
                card named in the result (basic lands excepted). Set it on the first call of a
                game or when unfamiliar cards appear; leave it off for quick follow-ups.

        Returns:
            A result whose ``status`` is ``ok`` (``you``, ``opponent``, ``turn``, ``stack``,
            ``pending_decision`` and ``recent_events`` describe the game), ``no_game`` (Arena has
            not played a game since it started), ``detailed_logs_disabled`` (``message`` says
            how the user turns logging on), ``log_not_found`` (Arena is not installed here or
            has never run) or ``error``. ``seconds_since_last_update`` is the age of the newest
            game message; ``warnings`` lists anything that degraded the result.
        """
        return await asyncio.to_thread(
            _read_game_state,
            log_path=log_path,
            card_database=card_database,
            recent_events=recent_events,
            include_card_text=include_card_text,
        )

    return mcp

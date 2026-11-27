"""One never-raising call from "where is the log" to the result an agent reads."""

import logging
import time
from pathlib import Path

from src.arena.card_database import ArenaCardDatabase
from src.arena.locate import LOG_PATH_ENV, find_card_database, find_player_log
from src.arena.log_reader import scan_log
from src.arena.models import GameStateResult
from src.arena.snapshot import DEFAULT_RECENT_EVENTS, SnapshotBuilder

logger = logging.getLogger(__name__)

_ENABLE_DETAILED_LOGS = (
    "In Arena, open Options, then Account, tick 'Detailed Logs (Plugin Support)' and restart "
    "the client."
)


def read_game_state(
    *,
    log_path: Path | None = None,
    card_database: Path | None = None,
    recent_events: int = DEFAULT_RECENT_EVENTS,
    include_card_text: bool = False,
) -> GameStateResult:
    """Read the latest Arena game from the client's log.

    Synchronous and blocking (it reads a multi-megabyte file and queries SQLite); an async caller
    runs it in a worker thread.

    Args:
        log_path: The ``Player.log`` to read; discovered when ``None``.
        card_database: The client's card database file; discovered when ``None``, using the
            install directory the log itself names.
        recent_events: How many of the latest game events to describe.
        include_card_text: Attach rules text for every named card.

    Returns:
        A result whose ``status`` is ``ok`` (a game was found, in progress or finished),
        ``no_game``, ``detailed_logs_disabled``, ``log_not_found`` or ``error``. Never raises for
        a missing, unreadable or unexpected log.
    """
    path = log_path or find_player_log()
    if path is None or not path.is_file():
        return GameStateResult(
            status="log_not_found",
            message=(
                "MTG Arena's Player.log was not found. Start Arena once, or set "
                f"{LOG_PATH_ENV} to the log file."
            ),
        )

    try:
        scan = scan_log(path)
    except OSError as exc:
        logger.warning("Arena log %s could not be read: %s", path, exc)
        return GameStateResult(status="error", message=f"Arena's log could not be read: {exc}")

    if not scan.tracker.has_game:
        if scan.detailed_logs is False:
            return GameStateResult(
                status="detailed_logs_disabled",
                message=f"Arena is not logging game state. {_ENABLE_DETAILED_LOGS}",
            )
        return GameStateResult(
            status="no_game",
            message="No game has been played since Arena last started.",
        )

    cards = ArenaCardDatabase(card_database or find_card_database(scan.install_dir))
    try:
        return SnapshotBuilder(scan.tracker, cards).build(
            recent_events=recent_events,
            include_card_text=include_card_text,
            now_ms=int(time.time() * 1000),
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        # The log's format is undocumented and the snapshot reads many fields; one of an
        # unexpected shape must come back as a status, not as a failed tool call.
        logger.exception("Arena game state could not be rendered")
        return GameStateResult(
            status="error",
            message=f"The game in Arena's log could not be read ({type(exc).__name__}: {exc}).",
        )
    finally:
        cards.close()

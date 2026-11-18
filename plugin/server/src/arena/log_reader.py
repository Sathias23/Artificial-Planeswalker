"""Scan ``Player.log`` and feed its game messages to a :class:`~src.arena.tracker.GameTracker`.

The whole file is read on every call rather than tailed. The log restarts with the client, a game's
state only exists as the sum of its diffs, and a scan costs well under a second, so there is no
offset to keep and nothing to go stale between calls.

Only two kinds of line are parsed: the engine-to-client game events and the match-room
announcements, each one a single JSON document on its own line. Everything else (the client's own
outgoing messages, which are pretty-printed across many lines, and the rest of the Unity log) is
skipped by a substring test before any JSON work is done.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.arena.tracker import GameTracker

_GRE_KEY = '"greToClientEvent"'
_ROOM_KEY = '"matchGameRoomStateChangedEvent"'
_DETAILED_LOGS = "DETAILED LOGS:"
_MONO_PATH = "Mono path[0] = '"
_MANAGED_SUFFIX = "/MTGA_Data/Managed"


@dataclass
class LogScan:
    """What one pass over the log found.

    Attributes:
        tracker: The state of the latest game in the log; ``tracker.has_game`` is false when the
            log holds none.
        detailed_logs: Whether the client reports detailed logging as on, or ``None`` when the log
            does not say.
        install_dir: The client's install directory as the log's first line names it.
    """

    tracker: GameTracker = field(default_factory=GameTracker)
    detailed_logs: bool | None = None
    install_dir: Path | None = None


def scan_log(path: Path, *, event_history: int = 50) -> LogScan:
    """Read the log and return the state of the latest game in it.

    Args:
        path: The ``Player.log`` to read. The client holds it open for writing; a final line caught
            half-written fails to parse and is skipped, to be picked up by the next call.
        event_history: How many recent events the tracker keeps.

    Returns:
        The scan.

    Raises:
        OSError: The file cannot be opened or read.
    """
    scan = LogScan(tracker=GameTracker(event_history=event_history))
    with path.open(encoding="utf-8", errors="replace") as log:
        for line in log:
            is_game = _GRE_KEY in line
            if is_game or _ROOM_KEY in line:
                start = line.find("{")
                if start < 0:
                    continue
                try:
                    document = json.loads(line[start:])
                except json.JSONDecodeError:
                    continue
                if not isinstance(document, dict):
                    continue
                if is_game:
                    scan.tracker.feed_gre(document)
                else:
                    scan.tracker.feed_room(document)
            elif _DETAILED_LOGS in line:
                scan.detailed_logs = "ENABLED" in line
            elif scan.install_dir is None and line.startswith(_MONO_PATH):
                managed = line[len(_MONO_PATH) :].strip().rstrip("'")
                if managed.endswith(_MANAGED_SUFFIX):
                    scan.install_dir = Path(managed[: -len(_MANAGED_SUFFIX)])
    return scan

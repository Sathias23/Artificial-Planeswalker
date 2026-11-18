"""Fixtures for the Arena game-state tests: a synthetic log, a synthetic card database."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from src.arena.locate import CARD_DATABASE_ENV, INSTALL_DIR_ENV, LOG_PATH_ENV
from src.arena.models import GameStateResult
from src.arena.reader import read_game_state
from tests.fixtures import arena as a


@pytest.fixture(autouse=True)
def _no_arena_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's own ``MTGA_*`` settings out of every test."""
    for variable in (LOG_PATH_ENV, CARD_DATABASE_ENV, INSTALL_DIR_ENV):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def card_database(tmp_path: Path) -> Path:
    return a.build_card_database(tmp_path / "Raw_CardDatabase_test.mtga")


@pytest.fixture
def read(tmp_path: Path, card_database: Path) -> Callable[..., GameStateResult]:
    """Write the given log lines and read the game state back through the real reader."""

    def _read(lines: list[str], **options: Any) -> GameStateResult:
        log_options = {k: options.pop(k) for k in ("detailed_logs", "install_dir") if k in options}
        log = a.write_log(tmp_path / "Player.log", lines, **log_options)
        options.setdefault("card_database", card_database)
        return read_game_state(log_path=log, **options)

    return _read


def opening_state(seat: int = 2, **overrides: Any) -> dict[str, Any]:
    """A full state, mid-game, seen from ``seat`` (2 by default).

    Seat 2 holds Giant Growth and Grizzly Bears, and controls three Forests (two tapped), a
    Grizzly Bears with a +1/+1 counter carrying a Bonesplitter, and a commander in the command
    zone. Seat 1 holds three hidden cards and controls an untapped Serra Angel, with a Giant
    Growth in the graveyard.
    """
    zones = a.empty_zones()
    contents = {
        a.COMMAND: [230],
        a.BATTLEFIELD: [210, 211, 212, 213, 214, 310],
        a.HAND_1: [301, 302, 303],
        a.LIBRARY_1: list(range(1000, 1050)),
        a.GRAVEYARD_1: [320],
        a.HAND_2: [201, 202],
        a.LIBRARY_2: list(range(2000, 2049)),
    }
    for zone in zones:
        zone["objectInstanceIds"] = contents.get(zone["zoneId"], [])
    fields: dict[str, Any] = {
        "gameInfo": {"matchID": "match-1", "gameNumber": 1, "stage": "GameStage_Play"},
        "players": [a.player(1, life=18), a.player(2, life=20)],
        "turnInfo": a.turn(5, active=2, step="Step_Draw", decisionPlayer=2),
        "zones": zones,
        "gameObjects": [
            a.card(201, a.GIANT_GROWTH, a.HAND_2, 2),
            a.card(202, a.BEAR, a.HAND_2, 2),
            a.card(210, a.FOREST, a.BATTLEFIELD, 2, isTapped=True, cardTypes=["CardType_Land"]),
            a.card(211, a.FOREST, a.BATTLEFIELD, 2, isTapped=True, cardTypes=["CardType_Land"]),
            a.card(212, a.FOREST, a.BATTLEFIELD, 2, cardTypes=["CardType_Land"]),
            a.card(213, a.BEAR, a.BATTLEFIELD, 2, **a.stats(3, 3)),
            a.card(214, a.EQUIPMENT, a.BATTLEFIELD, 2),
            a.card(230, a.COMMANDER, a.COMMAND, 2),
            a.card(310, a.ANGEL, a.BATTLEFIELD, 1, **a.stats(4, 4)),
            a.card(320, a.GIANT_GROWTH, a.GRAVEYARD_1, 1),
        ],
        "persistentAnnotations": [
            a.annotation(1, ["Counter"], affector=4002, affected=[213], count=1, counter_type=1),
            a.annotation(2, ["Attachment"], affector=214, affected=[213]),
            a.annotation(3, ["Designation"], affector=2, affected=[2], grpid=a.COMMANDER),
        ],
    }
    fields.update(overrides)
    return a.game_state(1, seat, full=True, **fields)


@pytest.fixture
def opening() -> list[str]:
    """Log lines for a game that has just reached :func:`opening_state`."""
    return [a.gre_line(a.connect(2)), a.gre_line(opening_state())]

"""Builders for synthetic MTG Arena logs and card databases.

A real ``Player.log`` names the player, their opponents and their account ids, so none is
committed. These builders write the same line and message shapes the client does, verified against
a live client on 2026-11-18, with just the fields the reader consumes.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

# Zone ids as the engine numbers them in a two-player game.
COMMAND, STACK, BATTLEFIELD, EXILE = 26, 27, 28, 29
HAND_1, LIBRARY_1, GRAVEYARD_1 = 31, 32, 33
HAND_2, LIBRARY_2, GRAVEYARD_2 = 35, 36, 37

FOREST, BEAR, GIANT_GROWTH, ANGEL, EQUIPMENT, COMMANDER, TOKEN = 100, 101, 102, 103, 104, 105, 106
UNKNOWN_CARD = 999
BEAR_TRIGGER, EQUIP_ABILITY = 9001, 9002


def connect(seat: int) -> dict[str, Any]:
    """The message that opens a game and says which seat this player has."""
    return {"type": "GREMessageType_ConnectResp", "systemSeatIds": [seat]}


def zone(zone_id: int, zone_type: str, ids: list[int], owner: int | None = None) -> dict[str, Any]:
    """One zone and the instance ids in it."""
    data: dict[str, Any] = {
        "zoneId": zone_id,
        "type": f"ZoneType_{zone_type}",
        "objectInstanceIds": ids,
    }
    if owner is not None:
        data["ownerSeatId"] = owner
    return data


def empty_zones() -> list[dict[str, Any]]:
    """Every zone of a two-player game, all empty."""
    return [
        zone(COMMAND, "Command", []),
        zone(STACK, "Stack", []),
        zone(BATTLEFIELD, "Battlefield", []),
        zone(EXILE, "Exile", []),
        zone(HAND_1, "Hand", [], owner=1),
        zone(LIBRARY_1, "Library", [], owner=1),
        zone(GRAVEYARD_1, "Graveyard", [], owner=1),
        zone(HAND_2, "Hand", [], owner=2),
        zone(LIBRARY_2, "Library", [], owner=2),
        zone(GRAVEYARD_2, "Graveyard", [], owner=2),
    ]


def card(instance_id: int, grp_id: int, zone_id: int, owner: int, **extra: Any) -> dict[str, Any]:
    """A game object. ``extra`` overrides or adds engine fields (``isTapped``, ``power``)."""
    data: dict[str, Any] = {
        "instanceId": instance_id,
        "grpId": grp_id,
        "type": "GameObjectType_Card",
        "zoneId": zone_id,
        "ownerSeatId": owner,
        "controllerSeatId": owner,
    }
    data.update(extra)
    return data


def stats(power: int, toughness: int) -> dict[str, Any]:
    """Current power and toughness, as the engine nests them."""
    return {"power": {"value": power}, "toughness": {"value": toughness}}


def player(seat: int, life: int = 20, **extra: Any) -> dict[str, Any]:
    """One player's entry."""
    return {"systemSeatNumber": seat, "teamId": seat, "lifeTotal": life, **extra}


def annotation(
    annotation_id: int,
    types: list[str],
    affector: int | None = None,
    affected: list[int] | None = None,
    **details: int | str,
) -> dict[str, Any]:
    """An annotation with its details in the engine's key/value list form."""
    data: dict[str, Any] = {
        "id": annotation_id,
        "type": [f"AnnotationType_{name}" for name in types],
        "affectedIds": affected or [],
        "details": [
            {"key": key, "valueString": [value]}
            if isinstance(value, str)
            else {"key": key, "valueInt32": [value]}
            for key, value in details.items()
        ],
    }
    if affector is not None:
        data["affectorId"] = affector
    return data


def turn(number: int, active: int, phase: str = "Main1", **extra: Any) -> dict[str, Any]:
    """A complete turn description."""
    return {
        "turnNumber": number,
        "phase": f"Phase_{phase}",
        "activePlayer": active,
        "priorityPlayer": active,
        **extra,
    }


def game_state(
    game_state_id: int, seat: int, *, full: bool = False, **fields: Any
) -> dict[str, Any]:
    """A game-state message addressed to ``seat``; ``fields`` are the state's own keys."""
    return {
        "type": "GREMessageType_GameStateMessage",
        "systemSeatIds": [seat],
        "gameStateId": game_state_id,
        "gameStateMessage": {
            "type": "GameStateType_Full" if full else "GameStateType_Diff",
            "gameStateId": game_state_id,
            **fields,
        },
    }


def request(kind: str, game_state_id: int, seat: int, **body: Any) -> dict[str, Any]:
    """A decision request such as ``ActionsAvailableReq``."""
    return {
        "type": f"GREMessageType_{kind}",
        "systemSeatIds": [seat],
        "gameStateId": game_state_id,
        **body,
    }


def gre_line(*messages: dict[str, Any], timestamp_ms: int = 1_794_994_893_580) -> str:
    """One engine-to-client event as the client logs it: a header line, then one JSON line."""
    document = {
        "transactionId": "t",
        "timestamp": str(timestamp_ms),
        "greToClientEvent": {"greToClientMessages": list(messages)},
    }
    header = "[UnityCrossThreadLogger]18/11/2026 8:11:32 PM: Match to PLAYER: GreToClientEvent"
    return f"{header}\n{json.dumps(document)}"


def room_line(match_id: str, seat: int, event_id: str) -> str:
    """A match-room announcement naming the event this player queued for."""
    document = {
        "matchGameRoomStateChangedEvent": {
            "gameRoomInfo": {
                "gameRoomConfig": {
                    "matchId": match_id,
                    "reservedPlayers": [{"systemSeatId": seat, "eventId": event_id}],
                }
            }
        }
    }
    return json.dumps(document)


def write_log(
    path: Path,
    lines: list[str],
    *,
    detailed_logs: bool | None = True,
    install_dir: str | None = None,
) -> Path:
    """Write a ``Player.log`` with the client's preamble around ``lines``."""
    preamble = []
    if install_dir is not None:
        preamble.append(f"Mono path[0] = '{install_dir}/MTGA_Data/Managed'")
    preamble.append("Initialize engine version: 6000.3.14f1")
    if detailed_logs is not None:
        preamble.append(f"DETAILED LOGS: {'ENABLED' if detailed_logs else 'DISABLED'}")
    path.write_text("\n".join([*preamble, *lines]) + "\n", encoding="utf-8")
    return path


def build_card_database(path: Path, *, formatted_column: bool = True) -> Path:
    """Write a card database in the client's schema, holding the cards these tests use.

    Args:
        path: Where to write the SQLite file.
        formatted_column: ``False`` writes the localization table without its ``Formatted``
            column, the shape of an older client.
    """
    texts = {
        1: "Forest",
        2: "Grizzly Bears",
        3: "Giant Growth",
        4: "Serra Angel",
        5: "Bonesplitter",
        6: "Jadzia Dax",
        7: "Bear",
        20: "Basic Land",
        21: "Creature",
        22: "Instant",
        23: "Artifact",
        24: "Legendary Creature",
        30: "Forest",
        31: "Bear",
        32: "Angel",
        33: "Equipment",
        40: "{oT}: Add {oG}.",
        41: "When CARDNAME enters, you gain 1 life.",
        42: "Target creature gets +3/+3 until end of turn.",
        43: "Flying",
        44: "Vigilance",
        45: "Equip {o1}",
        50: "+1/+1",
        60: "Choose targets.",
        61: "Would you like to mulligan to {1, NumberOfCards} card(s)?",
        62: "#Deprecated PromptMessage_ActionsAvailableReq",
    }
    # grp id, title, cost, type, subtype, power, toughness, abilities
    cards = [
        (FOREST, 1, "", 20, 30, "", "", "1005:40"),
        (BEAR, 2, "o1oG", 21, 31, "2", "2", f"{BEAR_TRIGGER}:41"),
        (GIANT_GROWTH, 3, "oG", 22, 0, "", "", "9003:42"),
        (ANGEL, 4, "o3oWoW", 21, 32, "4", "4", "8:43,15:44"),
        (EQUIPMENT, 5, "o1", 23, 33, "", "", f"{EQUIP_ABILITY}:45"),
        (COMMANDER, 6, "o1oG", 24, 0, "0", "1", ""),
        (TOKEN, 7, "", 21, 31, "2", "2", ""),
    ]
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE Cards(GrpId INT PRIMARY KEY, TitleId INT, OldSchoolManaText TEXT,
                TypeTextId INT, SubtypeTextId INT, Power TEXT, Toughness TEXT, AbilityIds TEXT);
            CREATE TABLE Abilities(Id INT PRIMARY KEY, TextId INT);
            CREATE TABLE Enums(Type TEXT, Value INT, LocId INT);
            CREATE TABLE Prompts(Id INT PRIMARY KEY, LocId INT);
            """
        )
        if formatted_column:
            connection.execute(
                "CREATE TABLE Localizations_enUS(LocId INT, Formatted INT, Loc TEXT)"
            )
            rows = [(loc_id, 1, f"<nobr>{text}</nobr>") for loc_id, text in texts.items()]
            # The trigger also has a plain variant, which must win over the marked-up one.
            rows.append((41, 0, texts[41]))
            connection.executemany("INSERT INTO Localizations_enUS VALUES (?, ?, ?)", rows)
        else:
            connection.execute("CREATE TABLE Localizations_enUS(LocId INT, Loc TEXT)")
            connection.executemany("INSERT INTO Localizations_enUS VALUES (?, ?)", texts.items())
        connection.executemany("INSERT INTO Cards VALUES (?, ?, ?, ?, ?, ?, ?, ?)", cards)
        connection.executemany(
            "INSERT INTO Abilities VALUES (?, ?)",
            [(BEAR_TRIGGER, 41), (EQUIP_ABILITY, 45), (1005, 40)],
        )
        connection.execute("INSERT INTO Enums VALUES ('CounterType', 1, 50)")
        connection.executemany("INSERT INTO Prompts VALUES (?, ?)", [(10, 60), (34, 61), (2, 62)])
        connection.commit()
    finally:
        connection.close()
    return path

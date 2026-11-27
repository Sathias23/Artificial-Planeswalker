"""Replay the Arena client's game-state messages into the current raw state of one game.

The game engine sends one full state when a game starts (and again after an undo or a reconnect)
and diffs from then on. A diff carries only the zones, objects and players that changed, plus the
ids of objects and annotations that ceased to exist, so the current state exists nowhere in the log
and has to be accumulated. :class:`GameTracker` does that and nothing else: it holds the engine's
own dictionaries, unnamed and uninterpreted, and :mod:`src.arena.snapshot` reads them.

The one thing it interprets is the transient annotations on each message (a spell cast, damage
dealt), because the objects they refer to can be gone by the next message. Those become
:class:`GameEvent` records, kept as ids so that naming stays the snapshot's job.

The log format is undocumented, so every container is checked before it is walked: a field that
is ``null`` or the wrong type where a list or an object was expected is treated as absent.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

_FULL_STATE = "GameStateType_Full"
_CONNECT = "GREMessageType_ConnectResp"
_GAME_STATE = "GREMessageType_GameStateMessage"


@dataclass(frozen=True)
class GameEvent:
    """One thing that happened, recorded as ids at the moment the log reported it.

    Attributes:
        turn: The turn number the event happened in, when known.
        kind: ``turn``, ``zone``, ``damage``, ``life``, ``counter``, ``token`` or ``ability``.
        seat: The player the event belongs to (who cast, drew or lost life), when known.
        grp_id: The card or token involved, when its identity is visible to this player.
        category: The engine's own zone-transfer category (``CastSpell``, ``Draw``, ``Destroy``).
        source_zone: The zone type a card left (``ZoneType_Hand``).
        destination_zone: The zone type a card arrived in.
        amount: Damage dealt, life changed (signed) or counters changed (signed).
        target_seat: The player damaged.
        target_grp_id: The permanent damaged.
        ability_id: The ability that triggered or was activated.
        counter_type: The engine's counter-kind number.
    """

    turn: int | None
    kind: str
    seat: int | None = None
    grp_id: int | None = None
    category: str | None = None
    source_zone: str | None = None
    destination_zone: str | None = None
    amount: int | None = None
    target_seat: int | None = None
    target_grp_id: int | None = None
    ability_id: int | None = None
    counter_type: int | None = None


@dataclass(frozen=True)
class PendingRequest:
    """A decision the engine is waiting on this player for."""

    message_type: str
    game_state_id: int
    message: dict[str, Any]


def _dicts(value: Any) -> Iterator[dict[str, Any]]:
    """Yield the objects in ``value`` if it is a list, and nothing otherwise."""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item


def _ints(value: Any) -> list[int]:
    """Return the integers in ``value`` if it is a list, and nothing otherwise."""
    return [item for item in value if isinstance(item, int)] if isinstance(value, list) else []


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def annotation_details(annotation: dict[str, Any]) -> dict[str, Any]:
    """Flatten an annotation's key/value detail list to ``{key: first value}``."""
    details: dict[str, Any] = {}
    for detail in _dicts(annotation.get("details")):
        values = (
            detail.get("valueInt32")
            or detail.get("valueString")
            or detail.get("valueUint32")
            or detail.get("valueInt64")
        )
        if isinstance(values, list) and values:
            details[str(detail.get("key", ""))] = values[0]
    return details


class GameTracker:
    """The accumulated state of the latest game seen in a stream of log messages.

    Feed it every message in log order; it resets itself when a new game starts, so after the last
    message it holds the latest game and no earlier one.

    ``events`` is every event of that game, oldest first. It is not capped: a game runs to a few
    hundred events, and how many of them an agent is shown is the snapshot's decision.
    """

    def __init__(self) -> None:
        self.room: dict[str, Any] = {}
        self.last_timestamp_ms: int | None = None
        self.events: list[GameEvent] = []
        self._reset()

    def _reset(self) -> None:
        """Forget the game, keeping the match room (it is announced before the game connects)."""
        self.seat: int | None = None
        self.game_info: dict[str, Any] = {}
        self.turn_info: dict[str, Any] = {}
        self.players: dict[int, dict[str, Any]] = {}
        self.pending: PendingRequest | None = None
        self.game_state_id: int | None = None
        self.events.clear()
        self._reset_board()

    def _reset_board(self) -> None:
        """Forget what a full state message replaces."""
        self.zones: dict[int, dict[str, Any]] = {}
        self.objects: dict[int, dict[str, Any]] = {}
        self.annotations: dict[int, dict[str, Any]] = {}

    @property
    def has_game(self) -> bool:
        """Whether any game state has been seen."""
        return self.game_state_id is not None

    def feed_room(self, document: dict[str, Any]) -> None:
        """Record a match-room announcement (players, event name, final result)."""
        event = document.get("matchGameRoomStateChangedEvent")
        room = event.get("gameRoomInfo") if isinstance(event, dict) else None
        if isinstance(room, dict):
            self.room = room

    def feed_gre(self, document: dict[str, Any]) -> None:
        """Apply one logged engine-to-client event (a batch of messages)."""
        timestamp = document.get("timestamp")
        if isinstance(timestamp, str) and timestamp.isdigit():
            self.last_timestamp_ms = int(timestamp)
        event = document.get("greToClientEvent")
        if isinstance(event, dict):
            for message in _dicts(event.get("greToClientMessages")):
                self._apply(message)

    def _apply(self, message: dict[str, Any]) -> None:
        message_type = str(message.get("type", ""))
        seats = _ints(message.get("systemSeatIds"))

        if message_type == _CONNECT:
            self._reset()
            if seats:
                self.seat = seats[0]
            return

        if message_type == _GAME_STATE:
            state = message.get("gameStateMessage")
            if isinstance(state, dict):
                if self.seat is None and seats:
                    # A log that starts mid-game has no connect message; every game-state message
                    # in this player's log is addressed to this player's seat.
                    self.seat = seats[0]
                self._apply_game_state(state)
            return

        if message_type.endswith("Req") and (self.seat is None or self.seat in seats):
            self.pending = PendingRequest(
                message_type=message_type,
                game_state_id=_int(message.get("gameStateId")),
                message=message,
            )

    def _apply_game_state(self, state: dict[str, Any]) -> None:
        game_state_id = _int(state.get("gameStateId"))
        if state.get("type") == _FULL_STATE:
            self._reset_board()
            self.players = {}
            self.pending = None
        elif self.pending is not None and game_state_id > self.pending.game_state_id:
            # The engine only moves on once the decision has been answered.
            self.pending = None
        self.game_state_id = game_state_id

        if isinstance(state.get("gameInfo"), dict):
            self.game_info.update(state["gameInfo"])
        turn_info = state.get("turnInfo")
        if isinstance(turn_info, dict):
            if "phase" in turn_info:
                # A complete turn description: a field it omits (no step in a main phase, nobody
                # to decide) is genuinely absent, so merging would keep a stale one.
                self.turn_info = dict(turn_info)
            else:
                # A partial update, e.g. only who decides next.
                self.turn_info.update(turn_info)
        for player in _dicts(state.get("players")):
            seat = player.get("systemSeatNumber")
            if isinstance(seat, int):
                # A diff sends the whole player, so replace: a merged dict would keep a mana pool
                # that has since emptied.
                self.players[seat] = player
        for zone in _dicts(state.get("zones")):
            if isinstance(zone.get("zoneId"), int):
                self.zones[zone["zoneId"]] = zone
        for game_object in _dicts(state.get("gameObjects")):
            if isinstance(game_object.get("instanceId"), int):
                self.objects[game_object["instanceId"]] = game_object
        for annotation in _dicts(state.get("persistentAnnotations")):
            if isinstance(annotation.get("id"), int):
                self.annotations[annotation["id"]] = annotation
        for annotation_id in _ints(state.get("diffDeletedPersistentAnnotationIds")):
            self.annotations.pop(annotation_id, None)

        # Events are read before deletions are applied: an annotation may name an object this
        # same message removes.
        for annotation in _dicts(state.get("annotations")):
            self._record_events(annotation)
        for instance_id in _ints(state.get("diffDeletedInstanceIds")):
            self.objects.pop(instance_id, None)

    # -- events -------------------------------------------------------------------------------

    def _zone(self, zone_id: Any) -> dict[str, Any]:
        zone = self.zones.get(zone_id) if isinstance(zone_id, int) else None
        return zone or {}

    def _grp_id(self, instance_id: Any) -> int | None:
        game_object = self.objects.get(instance_id) if isinstance(instance_id, int) else None
        grp_id = game_object.get("grpId") if game_object else None
        return grp_id if isinstance(grp_id, int) and grp_id > 0 else None

    def _record_events(self, annotation: dict[str, Any]) -> None:
        types = annotation.get("type")
        if not isinstance(types, list):
            return
        details = annotation_details(annotation)
        affector = annotation.get("affectorId")
        affected = _ints(annotation.get("affectedIds"))
        turn = self.turn_info.get("turnNumber")

        if "AnnotationType_NewTurnStarted" in types:
            self.events.append(
                GameEvent(turn=turn, kind="turn", seat=self.turn_info.get("activePlayer"))
            )

        if "AnnotationType_ZoneTransfer" in types:
            source = self._zone(details.get("zone_src"))
            destination = self._zone(details.get("zone_dest"))
            for instance_id in affected:
                game_object = self.objects.get(instance_id, {})
                seat = (
                    game_object.get("controllerSeatId")
                    or destination.get("ownerSeatId")
                    or source.get("ownerSeatId")
                )
                self.events.append(
                    GameEvent(
                        turn=turn,
                        kind="zone",
                        seat=seat,
                        grp_id=self._grp_id(instance_id),
                        category=str(details.get("category") or "") or None,
                        source_zone=source.get("type"),
                        destination_zone=destination.get("type"),
                    )
                )

        if "AnnotationType_DamageDealt" in types:
            for target in affected:
                is_player = target in self.players
                self.events.append(
                    GameEvent(
                        turn=turn,
                        kind="damage",
                        grp_id=self._grp_id(affector),
                        amount=details.get("damage"),
                        target_seat=target if is_player else None,
                        target_grp_id=None if is_player else self._grp_id(target),
                    )
                )

        if "AnnotationType_ModifiedLife" in types:
            for target in affected:
                self.events.append(
                    GameEvent(turn=turn, kind="life", seat=target, amount=details.get("life"))
                )

        for counter_type, sign in (
            ("AnnotationType_CounterAdded", 1),
            ("AnnotationType_CounterRemoved", -1),
        ):
            if counter_type in types:
                amount = details.get("transaction_amount")
                for target in affected:
                    self.events.append(
                        GameEvent(
                            turn=turn,
                            kind="counter",
                            grp_id=self._grp_id(target),
                            target_seat=target if target in self.players else None,
                            amount=sign * amount if isinstance(amount, int) else None,
                            counter_type=details.get("counter_type"),
                        )
                    )

        if "AnnotationType_TokenCreated" in types:
            for instance_id in affected:
                token = self.objects.get(instance_id, {})
                self.events.append(
                    GameEvent(
                        turn=turn,
                        kind="token",
                        seat=token.get("controllerSeatId"),
                        grp_id=self._grp_id(instance_id),
                    )
                )

        if "AnnotationType_AbilityInstanceCreated" in types:
            for instance_id in affected:
                ability = self.objects.get(instance_id)
                if not ability:
                    # A mana ability never becomes an object, and tapping a land is not news.
                    continue
                self.events.append(
                    GameEvent(
                        turn=turn,
                        kind="ability",
                        seat=ability.get("controllerSeatId"),
                        grp_id=self._grp_id(affector) or ability.get("objectSourceGrpId"),
                        ability_id=ability.get("grpId"),
                    )
                )

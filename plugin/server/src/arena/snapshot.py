"""Render a :class:`~src.arena.tracker.GameTracker`'s raw state as the result an agent reads.

Everything here is presentation: which seat is "you", what a card is called, how a cost reads.
The tracker's dictionaries are the engine's own and are read defensively, since a field this
module has never seen populated (a loyalty value, a blocker assignment) may be shaped differently
than expected, and a missing detail must cost one field, never the whole board.
"""

import re
from collections import defaultdict
from typing import Any

from src.arena.card_database import ArenaCardDatabase, format_mana_cost
from src.arena.models import (
    CardView,
    GameStateResult,
    LegalAction,
    PendingDecision,
    PlayerView,
    Seat,
    StackItem,
    TurnView,
)
from src.arena.tracker import GameEvent, GameTracker, annotation_details

MAX_RECENT_EVENTS = 50

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_MANA_LETTERS = {
    "ManaColor_White": "W",
    "ManaColor_Blue": "U",
    "ManaColor_Black": "B",
    "ManaColor_Red": "R",
    "ManaColor_Green": "G",
    "ManaColor_Colorless": "C",
    "ManaColor_X": "X",
}
_GENERIC = "ManaColor_Generic"
# Used only when the client's database cannot name a counter kind.
_COUNTER_FALLBACKS = {1: "+1/+1", 2: "-1/-1", 7: "loyalty"}
_DECISION_KINDS = {
    "GREMessageType_ActionsAvailableReq": "actions_available",
    "GREMessageType_SelectTargetsReq": "select_targets",
    "GREMessageType_DeclareAttackersReq": "declare_attackers",
    "GREMessageType_DeclareBlockersReq": "declare_blockers",
    "GREMessageType_MulliganReq": "mulligan",
}
# Offered on every priority and never a decision worth reporting.
_ROUTINE_ACTIONS = {"ActionType_Activate_Mana", "ActionType_FloatMana", "ActionType_Pass"}
_NOT_A_DECISION = {"GREMessageType_IntermissionReq"}
_ZONE_VERBS = {
    "CastSpell": "{who} cast {card}",
    "PlayLand": "{who} played {card}",
    "Draw": "{who} drew {card}",
    "Mill": "{who} milled {card}",
    "Discard": "{who} discarded {card}",
    "Sacrifice": "{who} sacrificed {card}",
    "Resolve": "{card} resolved",
    "Destroy": "{card} was destroyed",
    "Exile": "{card} was exiled",
    "Countered": "{card} was countered",
    "SBA_Damage": "{card} died from damage",
}
_ABILITY_TEXT_LIMIT = 160
# The zones whose cards the result lists, and so the only ones a reference can point into.
_PUBLIC_ZONES = {
    "ZoneType_Battlefield",
    "ZoneType_Stack",
    "ZoneType_Graveyard",
    "ZoneType_Exile",
    "ZoneType_Command",
}
_HAND_ZONE = "ZoneType_Hand"


def _list(value: Any) -> list[Any]:
    """Return ``value`` if it is a list, and an empty one for ``null`` or any other shape."""
    return value if isinstance(value, list) else []


def _enum(value: Any) -> str | None:
    """Turn ``Phase_Main1`` / ``Step_DeclareAttack`` into ``main1`` / ``declare_attack``."""
    if not isinstance(value, str) or not value:
        return None
    _, _, name = value.partition("_")
    return _CAMEL_BOUNDARY.sub("_", name or value).lower()


def _mana_cost(entries: Any) -> str | None:
    """Render the engine's cost list (``[{color: [Generic], count: 4}, ...]``) as ``{4}{G}``."""
    if not isinstance(entries, list):
        return None
    symbols: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        colors = entry.get("color") or []
        count = entry.get("count") or 0
        if not colors or not isinstance(count, int) or count <= 0:
            continue
        if colors == [_GENERIC]:
            symbols.append(f"{{{count}}}")
            continue
        symbol = "/".join(_MANA_LETTERS.get(color, _enum(color) or "?") for color in colors)
        symbols.extend([f"{{{symbol}}}"] * count)
    return "".join(symbols) or None


class SnapshotBuilder:
    """Builds one :class:`GameStateResult` from a tracker and a card database."""

    def __init__(self, tracker: GameTracker, cards: ArenaCardDatabase) -> None:
        self._tracker = tracker
        self._cards = cards
        self._seen: dict[str, int] = {}
        self._unnamed = False
        self._counters: dict[int, dict[str, int]] = defaultdict(dict)
        self._attached_to: dict[int, int] = {}
        self._targets: dict[int, list[int]] = defaultdict(list)
        self._commanders: dict[int, list[int]] = defaultdict(list)
        # instance id -> the number shared by the cards it is interchangeable with, for a card
        # whose name alone does not say which one is meant; see _number_lookalikes.
        self._refs: dict[int, int] = {}
        self._referenced: set[int] = set()
        self._read_annotations()
        self._number_lookalikes()

    # -- annotations --------------------------------------------------------------------------

    def _read_annotations(self) -> None:
        """Index the standing annotations: counters, attachments, targets and commanders."""
        for annotation in self._tracker.annotations.values():
            types = _list(annotation.get("type"))
            details = annotation_details(annotation)
            affector = annotation.get("affectorId")
            affected = [i for i in annotation.get("affectedIds") or [] if isinstance(i, int)]

            if "AnnotationType_Counter" in types and isinstance(details.get("count"), int):
                name = self._counter_name(details.get("counter_type"))
                for target in affected:
                    bucket = self._counters[target]
                    bucket[name] = bucket.get(name, 0) + details["count"]
            if "AnnotationType_Attachment" in types and isinstance(affector, int) and affected:
                self._attached_to[affector] = affected[0]
            if "AnnotationType_TargetSpec" in types and isinstance(affector, int):
                self._targets[affector].extend(affected)
            if "AnnotationType_Designation" in types and isinstance(details.get("grpid"), int):
                for target in affected:
                    if target in self._tracker.players:
                        self._commanders[target].append(details["grpid"])

    def _counter_name(self, counter_type: Any) -> str:
        if not isinstance(counter_type, int):
            return "unknown"
        return (
            self._cards.counter_name(counter_type)
            or _COUNTER_FALLBACKS.get(counter_type)
            or f"counter type {counter_type}"
        )

    # -- naming -------------------------------------------------------------------------------

    def _seat(self, seat: Any) -> Seat:
        return "you" if seat == self._tracker.seat else "opponent"

    def _seat_or_none(self, seat: Any) -> Seat | None:
        return self._seat(seat) if isinstance(seat, int) else None

    def _grp_name(self, grp_id: Any) -> str | None:
        if not isinstance(grp_id, int) or grp_id <= 0:
            return None
        name = self._cards.card_name(grp_id)
        if name is None:
            self._unnamed = True
            return f"unknown card #{grp_id}"
        self._seen.setdefault(name, grp_id)
        return name

    def _object_name(self, game_object: dict[str, Any]) -> str:
        if game_object.get("type") == "GameObjectType_Ability":
            source = self._grp_name(game_object.get("objectSourceGrpId")) or "a card"
            return f"ability of {source}"
        grp_id = game_object.get("grpId")
        if not isinstance(grp_id, int) or grp_id <= 0:
            return "face-down card"
        known = self._cards.card_name(grp_id) or self._cards.card_name(
            game_object.get("overlayGrpId")
        )
        if known is None:
            # A token the Cards table does not list still carries its own title id.
            known = self._cards.text(game_object.get("name"))
        if known is None:
            self._unnamed = True
            return f"unknown card #{grp_id}"
        self._seen.setdefault(known, grp_id)
        return known

    def _object(self, identifier: Any) -> dict[str, Any] | None:
        return self._tracker.objects.get(identifier) if isinstance(identifier, int) else None

    def _name_of(self, identifier: Any) -> str:
        """Name whatever an id refers to: a player's seat or an object's instance.

        A card that shares its name with a distinguishable one is named with its number
        (``Grizzly Bears #213``), the same number its own entry carries as ``ref``.
        """
        if isinstance(identifier, int) and identifier in self._tracker.players:
            return self._seat(identifier)
        game_object = self._object(identifier)
        if not game_object:
            return "something no longer visible"
        return self._numbered(self._object_name(game_object), identifier)

    def _numbered(self, name: str, identifier: Any) -> str:
        """Append the card's number to ``name`` when it has one, and note that it was used."""
        ref = self._refs.get(identifier) if isinstance(identifier, int) else None
        if ref is None:
            return name
        self._referenced.add(ref)
        return f"{name} #{ref}"

    def _number_lookalikes(self) -> None:
        """Number the cards a bare name would leave ambiguous.

        Two cards are interchangeable when they sit in the same place in the same state: the four
        untapped Forests, the eleven identical tokens. A name needs a number only when it is
        carried by cards that are *not* interchangeable (a Grizzly Bears on each side, one tapped
        and one not), and then every interchangeable set gets one number, so a reference to "one
        of these three" still reads as one entry with a ``count``. The hand is numbered apart
        from the public zones: nothing targets a card in hand, so a copy held there does not
        make the one on the battlefield ambiguous.
        """
        hosting: dict[int, list[int]] = defaultdict(list)
        for attachment, host in self._attached_to.items():
            hosting[host].append(attachment)
        # (hand or public, name) -> state -> the instances in that state
        lookalikes: dict[tuple[bool, str], dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for zone in self._tracker.zones.values():
            zone_type = zone.get("type")
            if zone_type != _HAND_ZONE and zone_type not in _PUBLIC_ZONES:
                continue
            for game_object in self._objects_in(zone):
                instance_id = game_object.get("instanceId")
                if not isinstance(instance_id, int):
                    continue
                view = self._card_view(
                    game_object, detailed=zone_type == "ZoneType_Battlefield", cost=False
                )
                block_info = game_object.get("blockInfo")
                state = repr(
                    (
                        zone.get("zoneId"),
                        game_object.get("ownerSeatId"),
                        game_object.get("controllerSeatId"),
                        view.model_dump_json(),
                        # What it is attached to, what is attached to it and what it blocks, by
                        # id: the view names these, and a name is what is being disambiguated.
                        self._attached_to.get(instance_id),
                        sorted(hosting.get(instance_id, [])),
                        block_info.get("attackerIds") if isinstance(block_info, dict) else None,
                        # Order on the stack matters, so nothing there is interchangeable.
                        instance_id if zone_type == "ZoneType_Stack" else None,
                    )
                )
                lookalikes[zone_type == _HAND_ZONE, view.name][state].append(instance_id)
        for states in lookalikes.values():
            if len(states) > 1:
                for instances in states.values():
                    ref = min(instances)
                    self._refs.update(dict.fromkeys(instances, ref))

    # -- cards --------------------------------------------------------------------------------

    def _objects_in(self, zone: dict[str, Any]) -> list[dict[str, Any]]:
        """Return the zone's objects whose data this player can see, in zone order."""
        objects = self._tracker.objects
        return [
            objects[i]
            for i in _list(zone.get("objectInstanceIds"))
            if isinstance(i, int) and i in objects
        ]

    def _card_view(self, game_object: dict[str, Any], *, detailed: bool, cost: bool) -> CardView:
        """Build one card's view.

        Args:
            game_object: The engine's object.
            detailed: Include battlefield state (stats, flags, counters, attachments).
            cost: Include the mana cost.
        """
        name = self._object_name(game_object)
        grp_id = game_object.get("grpId")
        view = CardView(name=name)
        if cost:
            card = self._cards.card(grp_id if isinstance(grp_id, int) else None)
            view.mana_cost = card.mana_cost if card is not None else None
        is_token = game_object.get("type") == "GameObjectType_Token"
        if is_token:
            view.flags.append("token")
            view.type_line = self._type_line(game_object)
        owner = game_object.get("ownerSeatId")
        if isinstance(owner, int) and grp_id in self._commanders.get(owner, []):
            view.flags.append("commander")
        instance_id = game_object.get("instanceId")
        ref = self._refs.get(instance_id) if isinstance(instance_id, int) else None
        if ref in self._referenced:
            view.ref = ref
        if not detailed:
            return view

        power = (game_object.get("power") or {}).get("value")
        toughness = (game_object.get("toughness") or {}).get("value")
        if power is not None and toughness is not None:
            view.power_toughness = f"{power}/{toughness}"
        if game_object.get("isTapped"):
            view.flags.append("tapped")
        if game_object.get("hasSummoningSickness"):
            view.flags.append("summoning_sick")
        if game_object.get("isFacedown"):
            view.flags.append("face_down")
        attack_state = game_object.get("attackState")
        if attack_state and attack_state != "AttackState_None":
            view.flags.append("attacking")
        block_state = game_object.get("blockState")
        if block_state in ("BlockState_Blocked", "BlockState_Unblocked"):
            view.flags.append(_enum(block_state) or "blocked")
        attackers = (game_object.get("blockInfo") or {}).get("attackerIds") or []
        if attackers:
            view.flags.append("blocking")
            view.blocking = [self._name_of(attacker) for attacker in attackers]
        if game_object.get("controllerSeatId") != owner:
            view.flags.append("controlled_by_other_player")
        if isinstance(game_object.get("damage"), int) and game_object["damage"] > 0:
            view.damage = game_object["damage"]
        if isinstance(instance_id, int):
            view.counters = dict(self._counters.get(instance_id, {}))
            if instance_id in self._attached_to:
                view.attached_to = self._name_of(self._attached_to[instance_id])
        return view

    @staticmethod
    def _type_line(game_object: dict[str, Any]) -> str | None:
        def words(key: str) -> list[str]:
            return [
                str(value).partition("_")[2].replace("_", " ")
                for value in _list(game_object.get(key))
                if isinstance(value, str)
            ]

        types = " ".join(words("superTypes") + words("cardTypes"))
        subtypes = " ".join(words("subtypes"))
        if types and subtypes:
            return f"{types} — {subtypes}"
        return types or subtypes or None

    @staticmethod
    def _grouped(views: list[CardView]) -> list[CardView]:
        """Collapse identical views into one entry with a ``count``, keeping first-seen order."""
        grouped: dict[str, CardView] = {}
        counts: dict[str, int] = defaultdict(int)
        for view in views:
            key = view.model_dump_json()
            grouped.setdefault(key, view)
            counts[key] += 1
        for key, view in grouped.items():
            if counts[key] > 1:
                view.count = counts[key]
        return list(grouped.values())

    def _views(
        self, objects: list[dict[str, Any]], *, detailed: bool = False, cost: bool = False
    ) -> list[CardView]:
        return self._grouped([self._card_view(o, detailed=detailed, cost=cost) for o in objects])

    # -- players ------------------------------------------------------------------------------

    def _player(self, seat: int) -> PlayerView:
        tracker = self._tracker
        player = tracker.players.get(seat, {})
        view = PlayerView(life=player.get("lifeTotal"))
        commanders = [self._grp_name(grp_id) for grp_id in self._commanders.get(seat, [])]
        view.commander = " + ".join(dict.fromkeys(name for name in commanders if name)) or None
        pool = [
            {"color": [mana.get("color")], "count": mana.get("count", 1)}
            for mana in _list(player.get("manaPool"))
            if isinstance(mana, dict)
        ]
        view.mana_pool = _mana_cost(pool)
        view.counters = dict(self._counters.get(seat, {}))

        for zone in tracker.zones.values():
            zone_type = zone.get("type")
            visible = self._objects_in(zone)
            if zone_type == "ZoneType_Battlefield":
                mine = [o for o in visible if o.get("controllerSeatId") == seat]
                # Stable: permanents that do something first, lands last.
                mine.sort(key=lambda o: "CardType_Land" in _list(o.get("cardTypes")))
                view.battlefield = self._views(mine, detailed=True)
            elif zone_type == "ZoneType_Exile":
                view.exile = self._views([o for o in visible if o.get("ownerSeatId") == seat])
            elif zone_type == "ZoneType_Command":
                view.command_zone = self._views(
                    [o for o in visible if o.get("ownerSeatId") == seat], cost=True
                )
            elif zone.get("ownerSeatId") != seat:
                continue
            elif zone_type == "ZoneType_Hand":
                view.hand_count = len(_list(zone.get("objectInstanceIds")))
                known = [o for o in visible if isinstance(o.get("grpId"), int) and o["grpId"] > 0]
                view.hand = self._views(known, cost=True)
            elif zone_type == "ZoneType_Library":
                view.library_count = len(_list(zone.get("objectInstanceIds")))
            elif zone_type == "ZoneType_Graveyard":
                view.graveyard = self._views(visible)
        return view

    def _turn(self) -> TurnView:
        info = self._tracker.turn_info
        return TurnView(
            number=info.get("turnNumber"),
            phase=_enum(info.get("phase")),
            step=_enum(info.get("step")),
            active_player=self._seat_or_none(info.get("activePlayer")),
            priority_player=self._seat_or_none(info.get("priorityPlayer")),
            decision_player=self._seat_or_none(info.get("decisionPlayer")),
        )

    # -- stack --------------------------------------------------------------------------------

    def _stack(self) -> list[StackItem]:
        items: list[StackItem] = []
        for zone in self._tracker.zones.values():
            if zone.get("type") != "ZoneType_Stack":
                continue
            for game_object in self._objects_in(zone):
                is_ability = game_object.get("type") == "GameObjectType_Ability"
                grp_id = game_object.get("grpId")
                item = StackItem(
                    name=self._object_name(game_object),
                    kind="ability" if is_ability else "spell",
                    controller=self._seat(game_object.get("controllerSeatId")),
                )
                if is_ability:
                    source = self._grp_name(game_object.get("objectSourceGrpId"))
                    item.text = self._cards.ability_text(
                        grp_id if isinstance(grp_id, int) else None, source
                    )
                else:
                    card = self._cards.card(grp_id if isinstance(grp_id, int) else None)
                    item.mana_cost = card.mana_cost if card is not None else None
                instance_id = game_object.get("instanceId")
                if isinstance(instance_id, int):
                    ref = self._refs.get(instance_id)
                    item.ref = ref if ref in self._referenced else None
                    item.targets = [self._name_of(t) for t in self._targets.get(instance_id, [])]
                items.append(item)
        return items

    # -- decisions ----------------------------------------------------------------------------

    def _pending_decision(self) -> PendingDecision | None:
        pending = self._tracker.pending
        if pending is None or pending.message_type in _NOT_A_DECISION:
            return None
        message = pending.message
        kind = _DECISION_KINDS.get(pending.message_type)
        if kind is None:
            kind = _enum(pending.message_type.removesuffix("Req")) or "unknown"
        decision = PendingDecision(kind=kind, prompt=self._prompt(message.get("prompt")))

        if kind == "actions_available":
            actions = (message.get("actionsAvailableReq") or {}).get("actions") or []
            decision.actions = self._legal_actions(actions)
        elif kind == "select_targets":
            request = message.get("selectTargetsReq") or {}
            if self._object(request.get("sourceId")):
                decision.source = self._name_of(request.get("sourceId"))
            for group in request.get("targets") or []:
                # The per-target prompt ("Target a creature.") says more than the outer one.
                decision.prompt = self._prompt(group.get("prompt")) or decision.prompt
            decision.options = self._names(
                target.get("targetInstanceId")
                for group in request.get("targets") or []
                for target in group.get("targets") or []
            )
        elif kind == "declare_attackers":
            request = message.get("declareAttackersReq") or {}
            attackers = request.get("qualifiedAttackers") or request.get("attackers") or []
            decision.options = self._names(a.get("attackerInstanceId") for a in attackers)
        elif kind == "declare_blockers":
            request = message.get("declareBlockersReq") or {}
            decision.options = self._names(
                b.get("blockerInstanceId") for b in request.get("blockers") or []
            )
        else:
            # Selection-style requests name their candidates under one of these keys.
            for body in message.values():
                if isinstance(body, dict):
                    candidates = body.get("ids") or body.get("instanceIds")
                    if isinstance(candidates, list):
                        decision.options = self._names(candidates)
                        break
        return decision

    def _prompt(self, prompt: Any) -> str | None:
        """Return the client's own wording for a decision prompt, placeholders filled."""
        if not isinstance(prompt, dict) or not isinstance(prompt.get("promptId"), int):
            return None
        parameters: dict[str, str] = {}
        for parameter in prompt.get("parameters") or []:
            if not isinstance(parameter, dict):
                continue
            name = str(parameter.get("parameterName"))
            if "numberValue" in parameter:
                parameters[name] = str(parameter["numberValue"])
            elif "stringValue" in parameter:
                value = str(parameter["stringValue"])
                parameters[name] = format_mana_cost(value) or value
        return self._cards.prompt_text(prompt["promptId"], parameters)

    def _names(self, identifiers: Any) -> list[str]:
        """Name each id once, in order, skipping anything that is not an id."""
        names = [self._name_of(i) for i in identifiers if isinstance(i, int)]
        return list(dict.fromkeys(names))

    def _legal_actions(self, actions: list[Any]) -> list[LegalAction]:
        result: dict[str, LegalAction] = {}
        for action in actions:
            if not isinstance(action, dict) or action.get("actionType") in _ROUTINE_ACTIONS:
                continue
            source = self._object(action.get("instanceId"))
            card = self._grp_name(action.get("grpId")) or (
                self._object_name(source) if source else None
            )
            if card and source:
                card = self._numbered(card, action.get("instanceId"))
            legal = LegalAction(
                action=_enum(action.get("actionType")) or "unknown",
                card=card,
                mana_cost=_mana_cost(action.get("manaCost")),
                affordable=True if action.get("autoTapSolution") else None,
            )
            if action.get("actionType") == "ActionType_Activate":
                legal.ability = self._cards.ability_text(action.get("abilityGrpId"), card)
            # Two copies of a card in hand offer the same play twice.
            result.setdefault(legal.model_dump_json(), legal)
        return list(result.values())

    # -- events -------------------------------------------------------------------------------

    def _describe(self, event: GameEvent) -> str | None:
        who = self._seat(event.seat) if event.seat is not None else None
        card = self._grp_name(event.grp_id)
        prefix = f"T{event.turn} " if event.turn else ""

        if event.kind == "turn":
            return f"{prefix}turn begins ({who})" if who else f"{prefix}turn begins"
        if event.kind == "zone":
            template = _ZONE_VERBS.get(event.category or "")
            if template is None:
                source = _enum(event.source_zone) or "?"
                destination = _enum(event.destination_zone) or "?"
                reason = f" ({event.category})" if event.category else ""
                template = f"{{card}} moved {source} -> {destination}{reason}"
            text = template.format(who=who or "a player", card=card or "a card")
            return prefix + text
        if event.kind == "damage":
            target = (
                self._seat(event.target_seat)
                if event.target_seat is not None
                else self._grp_name(event.target_grp_id) or "a permanent"
            )
            return f"{prefix}{card or 'a source'} dealt {event.amount} damage to {target}"
        if event.kind == "life" and isinstance(event.amount, int):
            verb = "gained" if event.amount >= 0 else "lost"
            return f"{prefix}{who} {verb} {abs(event.amount)} life"
        if event.kind == "counter" and isinstance(event.amount, int):
            subject = (
                self._seat(event.target_seat) if event.target_seat is not None else card or "a card"
            )
            verb = "got" if event.amount >= 0 else "lost"
            counter = self._counter_name(event.counter_type)
            return f"{prefix}{subject} {verb} {abs(event.amount)} {counter} counter(s)"
        if event.kind == "token":
            return f"{prefix}{who or 'a player'} created a {card or 'token'} token"
        if event.kind == "ability":
            ability = self._cards.ability_text(event.ability_id, card)
            if ability and len(ability) > _ABILITY_TEXT_LIMIT:
                ability = ability[: _ABILITY_TEXT_LIMIT - 1] + "…"
            detail = f": {ability}" if ability else ""
            return f"{prefix}{card or 'a card'} ability ({who or 'a player'}){detail}"
        return None

    # -- result -------------------------------------------------------------------------------

    def _game_result(self) -> tuple[bool, str | None]:
        """Return ``(in_progress, how it ended)``."""
        info = self._tracker.game_info
        over = info.get("stage") == "GameStage_GameOver" or info.get("matchState") in (
            "MatchState_GameComplete",
            "MatchState_MatchComplete",
        )
        if not over:
            return True, None
        game_results = [
            r
            for r in _list(info.get("results"))
            if isinstance(r, dict) and r.get("scope") == "MatchScope_Game"
        ]
        if not game_results:
            return False, "game over"
        last = game_results[-1]
        seat = self._tracker.seat
        my_team = self._tracker.players.get(seat, {}).get("teamId", seat) if seat else None
        winner = last.get("winningTeamId")
        if last.get("result") == "ResultType_Draw" or winner is None:
            outcome = "draw"
        else:
            outcome = "you won" if winner == my_team else "you lost"
        reason = _enum(last.get("reason"))
        return False, f"{outcome} ({reason})" if reason and reason != "game" else outcome

    def _event_name(self) -> str | None:
        room = self._tracker.room
        config = room.get("gameRoomConfig") or {}
        match_id = self._tracker.game_info.get("matchID")
        if match_id and config.get("matchId") and config["matchId"] != match_id:
            return None  # The room on record belongs to an earlier match.
        for player in config.get("reservedPlayers") or []:
            if isinstance(player, dict) and player.get("systemSeatId") == self._tracker.seat:
                return player.get("eventId")
        return None

    def _board(
        self, in_progress: bool
    ) -> tuple[PlayerView | None, PlayerView | None, list[StackItem], PendingDecision | None]:
        """Render both players, the stack and the pending decision."""
        seat = self._tracker.seat
        opponents = [s for s in self._tracker.players if s != seat]
        return (
            self._player(seat) if seat is not None else None,
            self._player(opponents[0]) if opponents else None,
            self._stack(),
            self._pending_decision() if in_progress else None,
        )

    def build(self, *, recent_events: int, include_card_text: bool, now_ms: int) -> GameStateResult:
        """Render the tracker's current state.

        Args:
            recent_events: How many of the latest events to describe (0 to
                :data:`MAX_RECENT_EVENTS`).
            include_card_text: Attach rules text for every named card.
            now_ms: The current time in epoch milliseconds, for the staleness figure.
        """
        tracker = self._tracker
        in_progress, outcome = self._game_result()

        board = self._board(in_progress)
        if self._referenced:
            # A card only shows its number when something points at it, and a pointer can sit
            # anywhere (the opponent's Aura on your creature, a decision built last), so the
            # first pass finds every pointer and this one marks the cards they name.
            board = self._board(in_progress)
        you, opponent, stack, pending_decision = board

        result = GameStateResult(
            status="ok",
            in_progress=in_progress,
            result=outcome,
            event=self._event_name(),
            game_number=tracker.game_info.get("gameNumber"),
            turn=self._turn(),
            you=you,
            opponent=opponent,
            stack=stack,
            pending_decision=pending_decision,
        )
        if tracker.last_timestamp_ms is not None:
            result.seconds_since_last_update = max(0, (now_ms - tracker.last_timestamp_ms) // 1000)

        wanted = max(0, min(recent_events, MAX_RECENT_EVENTS))
        if wanted:
            described = [self._describe(event) for event in list(tracker.events)[-wanted:]]
            result.recent_events = [text for text in described if text]

        if include_card_text:
            for name, grp_id in sorted(self._seen.items()):
                card = self._cards.card(grp_id)
                if card is not None and (card.type_line or "").startswith("Basic Land"):
                    continue
                text = self._cards.card_text(grp_id)
                if text:
                    result.card_text[name] = text

        if not self._cards.available:
            result.warnings.append(
                "Arena's card database was not found, so cards are shown by number. Set "
                "MTGA_INSTALL_DIR to the Arena install folder."
            )
        elif self._unnamed:
            result.warnings.append(
                "Some cards are not in Arena's card database and are shown by number."
            )
        return result

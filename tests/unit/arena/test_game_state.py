"""Reading the live game from an Arena log, through the real reader and the real MCP tool."""

import json
import time
from pathlib import Path

import pytest

from src.arena import locate
from src.arena.locate import CARD_DATABASE_ENV, LOG_PATH_ENV
from src.arena.reader import read_game_state
from src.arena.snapshot import SnapshotBuilder
from src.arena.tracker import GameTracker
from src.arena_server.server import build_server
from tests.fixtures import arena as a
from tests.unit.arena.conftest import opening_state


def _names(views) -> list[str]:
    return [view.name for view in views]


class TestTheBoard:
    def test_reports_both_life_totals_and_the_turn(self, read, opening):
        result = read(opening)

        assert result.status == "ok"
        assert result.in_progress is True
        assert (result.you.life, result.opponent.life) == (20, 18)
        assert result.turn.number == 5
        assert result.turn.phase == "main1"
        assert result.turn.step == "draw"
        assert result.turn.active_player == "you"
        assert result.turn.decision_player == "you"

    def test_your_hand_is_named_with_costs(self, read, opening):
        hand = read(opening).you.hand

        assert [(card.name, card.mana_cost) for card in hand] == [
            ("Giant Growth", "{G}"),
            ("Grizzly Bears", "{1}{G}"),
        ]

    def test_the_opponents_hand_and_both_libraries_are_counts_only(self, read, opening):
        result = read(opening)

        assert result.opponent.hand_count == 3
        assert result.opponent.hand == []
        assert (result.you.library_count, result.opponent.library_count) == (49, 50)

    def test_identical_permanents_collapse_and_lands_come_last(self, read, opening):
        battlefield = read(opening).you.battlefield

        assert _names(battlefield) == ["Grizzly Bears", "Bonesplitter", "Forest", "Forest"]
        tapped, untapped = battlefield[2], battlefield[3]
        assert (tapped.count, tapped.flags) == (2, ["tapped"])
        assert (untapped.count, untapped.flags) == (None, [])

    def test_counters_stats_and_attachments_are_read(self, read, opening):
        bear, equipment, *_ = read(opening).you.battlefield

        assert bear.power_toughness == "3/3"
        assert bear.counters == {"+1/+1": 1}
        assert equipment.attached_to == "Grizzly Bears"

    def test_the_commander_is_named_and_flagged(self, read, opening):
        you = read(opening).you

        assert you.commander == "Jadzia Dax"
        assert _names(you.command_zone) == ["Jadzia Dax"]
        assert you.command_zone[0].flags == ["commander"]

    def test_the_opponents_side_is_split_out(self, read, opening):
        opponent = read(opening).opponent

        assert [(c.name, c.power_toughness) for c in opponent.battlefield] == [
            ("Serra Angel", "4/4")
        ]
        assert _names(opponent.graveyard) == ["Giant Growth"]

    def test_a_stolen_permanent_is_listed_under_its_controller_and_flagged(self, read, opening):
        steal = a.game_state(
            2,
            2,
            gameObjects=[
                a.card(310, a.ANGEL, a.BATTLEFIELD, 1, controllerSeatId=2, **a.stats(4, 4))
            ],
        )

        result = read([*opening, a.gre_line(steal)])

        assert "Serra Angel" in _names(result.you.battlefield)
        assert result.opponent.battlefield == []
        angel = next(c for c in result.you.battlefield if c.name == "Serra Angel")
        assert angel.flags == ["controlled_by_other_player"]

    def test_combat_state_is_flagged(self, read, opening):
        combat = a.game_state(
            2,
            2,
            gameObjects=[
                a.card(
                    213,
                    a.BEAR,
                    a.BATTLEFIELD,
                    2,
                    isTapped=True,
                    attackState="AttackState_Attacking",
                    blockState="BlockState_Blocked",
                    damage=4,
                    **a.stats(3, 3),
                ),
                a.card(
                    310,
                    a.ANGEL,
                    a.BATTLEFIELD,
                    1,
                    blockState="BlockState_Declared",
                    blockInfo={"attackerIds": [213]},
                    **a.stats(4, 4),
                ),
            ],
        )

        result = read([*opening, a.gre_line(combat)])

        bear = result.you.battlefield[0]
        assert bear.flags == ["tapped", "attacking", "blocked"]
        assert bear.damage == 4
        angel = result.opponent.battlefield[0]
        assert angel.flags == ["blocking"]
        assert angel.blocking == ["Grizzly Bears"]

    def test_a_token_is_flagged_and_given_its_type(self, read, opening):
        token = a.card(
            240,
            a.TOKEN,
            a.BATTLEFIELD,
            2,
            type="GameObjectType_Token",
            cardTypes=["CardType_Creature"],
            subtypes=["SubType_Bear"],
            **a.stats(2, 2),
        )
        diff = a.game_state(
            2,
            2,
            zones=[a.zone(a.BATTLEFIELD, "Battlefield", [210, 211, 212, 213, 214, 310, 240])],
            gameObjects=[token],
        )

        view = next(
            c for c in read([*opening, a.gre_line(diff)]).you.battlefield if c.name == "Bear"
        )

        assert view.flags == ["token"]
        assert view.type_line == "Creature — Bear"

    def test_floating_mana_is_shown(self, read):
        state = opening_state(
            players=[
                a.player(1),
                a.player(2, manaPool=[{"color": "ManaColor_Green", "count": 2}]),
            ]
        )

        assert read([a.gre_line(a.connect(2)), a.gre_line(state)]).you.mana_pool == "{G}{G}"


class TestReplayingDiffs:
    def test_a_diff_changes_only_what_it_names(self, read, opening):
        diff = a.game_state(
            2,
            2,
            players=[a.player(1, life=15)],
            zones=[a.zone(a.HAND_2, "Hand", [201], owner=2)],
            diffDeletedInstanceIds=[202],
        )

        result = read([*opening, a.gre_line(diff)])

        assert (result.you.life, result.opponent.life) == (20, 15)
        assert _names(result.you.hand) == ["Giant Growth"]
        assert result.you.hand_count == 1
        assert len(result.you.battlefield) == 4

    def test_a_removed_annotation_takes_its_counter_with_it(self, read, opening):
        diff = a.game_state(2, 2, diffDeletedPersistentAnnotationIds=[1])

        assert read([*opening, a.gre_line(diff)]).you.battlefield[0].counters == {}

    def test_a_later_full_state_replaces_the_board(self, read, opening):
        zones = a.empty_zones()
        replacement = a.game_state(
            9,
            2,
            full=True,
            players=[a.player(1, life=7), a.player(2, life=3)],
            turnInfo=a.turn(9, active=1),
            zones=zones,
        )

        result = read([*opening, a.gre_line(replacement)])

        assert (result.you.life, result.opponent.life) == (3, 7)
        assert result.you.battlefield == []
        assert result.you.hand_count == 0

    def test_a_complete_turn_update_drops_a_step_it_no_longer_names(self, read, opening):
        diff = a.game_state(2, 2, turnInfo=a.turn(5, active=2, phase="Main1"))

        turn = read([*opening, a.gre_line(diff)]).turn

        assert turn.step is None
        assert turn.decision_player is None

    def test_a_partial_turn_update_keeps_the_rest(self, read, opening):
        diff = a.game_state(2, 2, turnInfo={"decisionPlayer": 1})

        turn = read([*opening, a.gre_line(diff)]).turn

        assert turn.number == 5
        assert turn.phase == "main1"
        assert turn.decision_player == "opponent"

    def test_a_new_game_starts_from_nothing(self, read, opening):
        second = opening_state(
            seat=1,
            gameInfo={"matchID": "match-2", "gameNumber": 1, "stage": "GameStage_Play"},
            zones=a.empty_zones(),
            gameObjects=[],
            persistentAnnotations=[],
        )

        result = read([*opening, a.gre_line(a.connect(1)), a.gre_line(second)])

        # Seat 1 this time, so the life totals swap sides and nothing of game one remains.
        assert (result.you.life, result.opponent.life) == (18, 20)
        assert result.you.battlefield == []
        assert result.you.commander is None
        assert result.recent_events == []

    def test_a_log_that_starts_mid_game_takes_the_seat_from_the_state_message(self, read):
        result = read([a.gre_line(opening_state())])

        assert result.you.life == 20
        assert _names(result.you.hand) == ["Giant Growth", "Grizzly Bears"]

    def test_a_half_written_last_line_is_skipped(self, read, opening):
        partial = a.gre_line(a.game_state(2, 2, players=[a.player(2, life=1)]))[:-40]

        assert read([*opening, partial]).you.life == 20


class TestTheStack:
    def _on_the_stack(self) -> str:
        spell = a.card(400, a.GIANT_GROWTH, a.STACK, 1)
        trigger = a.card(
            401,
            a.BEAR_TRIGGER,
            a.STACK,
            2,
            type="GameObjectType_Ability",
            objectSourceGrpId=a.BEAR,
        )
        diff = a.game_state(
            2,
            2,
            zones=[a.zone(a.STACK, "Stack", [401, 400])],
            gameObjects=[spell, trigger],
            persistentAnnotations=[a.annotation(9, ["TargetSpec"], affector=400, affected=[310])],
        )
        return a.gre_line(diff)

    def test_lists_the_top_first_with_text_cost_and_targets(self, read, opening):
        top, bottom = read([*opening, self._on_the_stack()]).stack

        assert (top.name, top.kind, top.controller) == (
            "ability of Grizzly Bears",
            "ability",
            "you",
        )
        assert top.text == "When Grizzly Bears enters, you gain 1 life."
        assert (bottom.name, bottom.kind, bottom.controller) == (
            "Giant Growth",
            "spell",
            "opponent",
        )
        assert bottom.mana_cost == "{G}"
        assert bottom.targets == ["Serra Angel"]


class TestPendingDecisions:
    def _priority(self, game_state_id: int = 1) -> dict:
        return a.request(
            "ActionsAvailableReq",
            game_state_id,
            2,
            actionsAvailableReq={
                "actions": [
                    {
                        "actionType": "ActionType_Cast",
                        "grpId": a.BEAR,
                        "instanceId": 202,
                        "manaCost": [
                            {"color": ["ManaColor_Generic"], "count": 1},
                            {"color": ["ManaColor_Green"], "count": 1},
                        ],
                    },
                    {
                        "actionType": "ActionType_Cast",
                        "grpId": a.GIANT_GROWTH,
                        "instanceId": 201,
                        "manaCost": [{"color": ["ManaColor_Green"], "count": 1}],
                        "autoTapSolution": {"autoTapActions": [{}]},
                    },
                    {
                        "actionType": "ActionType_Activate",
                        "grpId": a.EQUIPMENT,
                        "instanceId": 214,
                        "abilityGrpId": a.EQUIP_ABILITY,
                        "manaCost": [{"color": ["ManaColor_Generic"], "count": 1}],
                        "autoTapSolution": {"autoTapActions": [{}]},
                    },
                    {
                        "actionType": "ActionType_Activate_Mana",
                        "grpId": a.FOREST,
                        "instanceId": 212,
                    },
                    {"actionType": "ActionType_Pass"},
                ]
            },
        )

    def test_priority_lists_the_plays_on_offer_without_the_routine_ones(self, read, opening):
        decision = read([*opening, a.gre_line(self._priority())]).pending_decision

        assert decision.kind == "actions_available"
        assert [(x.action, x.card, x.mana_cost, x.affordable) for x in decision.actions] == [
            ("cast", "Grizzly Bears", "{1}{G}", None),
            ("cast", "Giant Growth", "{G}", True),
            ("activate", "Bonesplitter", "{1}", True),
        ]
        assert decision.actions[2].ability == "Equip {1}"

    def test_a_loyalty_activation_names_its_cost(self, read, opening):
        priority = a.request(
            "ActionsAvailableReq",
            1,
            2,
            actionsAvailableReq={
                "actions": [
                    {
                        "actionType": "ActionType_Activate",
                        "grpId": a.PLANESWALKER,
                        "instanceId": 230,
                        "abilityGrpId": a.WALKER_MINUS,
                    },
                    {"actionType": "ActionType_Pass"},
                ]
            },
        )

        decision = read([*opening, a.gre_line(priority)]).pending_decision

        assert [(x.action, x.card, x.ability) for x in decision.actions] == [
            ("activate", "Sorin Markov", "−3: Target opponent's life total becomes 10."),
        ]

    def test_a_decision_is_dropped_once_the_game_moves_on(self, read, opening):
        moved_on = a.game_state(2, 2, players=[a.player(2, life=20)])

        result = read([*opening, a.gre_line(self._priority()), a.gre_line(moved_on)])

        assert result.pending_decision is None

    def test_target_selection_names_the_source_the_prompt_and_the_options(self, read, opening):
        choose = a.request(
            "SelectTargetsReq",
            1,
            2,
            prompt={"promptId": 2},
            selectTargetsReq={
                "sourceId": 201,
                "targets": [
                    {
                        "prompt": {"promptId": 10},
                        "targets": [
                            {"targetInstanceId": 213},
                            {"targetInstanceId": 310},
                            {"targetInstanceId": 1},
                        ],
                    }
                ],
            },
        )

        decision = read([*opening, a.gre_line(choose)]).pending_decision

        assert decision.kind == "select_targets"
        assert decision.source == "Giant Growth"
        assert decision.prompt == "Choose targets."
        assert decision.options == ["Grizzly Bears", "Serra Angel", "opponent"]

    def test_attackers_are_named(self, read, opening):
        attack = a.request(
            "DeclareAttackersReq",
            1,
            2,
            declareAttackersReq={"qualifiedAttackers": [{"attackerInstanceId": 213}]},
        )

        decision = read([*opening, a.gre_line(attack)]).pending_decision

        assert (decision.kind, decision.options) == ("declare_attackers", ["Grizzly Bears"])

    def test_a_mulligan_prompt_is_worded_as_the_client_words_it(self, read, opening):
        mulligan = a.request(
            "MulliganReq",
            1,
            2,
            prompt={
                "promptId": 34,
                "parameters": [{"parameterName": "NumberOfCards", "numberValue": 6}],
            },
        )

        decision = read([*opening, a.gre_line(mulligan)]).pending_decision

        assert decision.kind == "mulligan"
        assert decision.prompt == "Would you like to mulligan to 6 card(s)?"

    def test_an_unfamiliar_request_is_still_reported_with_its_candidates(self, read, opening):
        pick = a.request("SelectNReq", 1, 2, selectNReq={"ids": [213, 310]})

        decision = read([*opening, a.gre_line(pick)]).pending_decision

        assert (decision.kind, decision.options) == ("select_n", ["Grizzly Bears", "Serra Angel"])

    def test_a_request_addressed_to_the_other_seat_is_ignored(self, read, opening):
        theirs = a.request("SelectNReq", 1, 1, selectNReq={"ids": [310]})

        assert read([*opening, a.gre_line(theirs)]).pending_decision is None


class TestRecentEvents:
    def _a_turn_of_play(self) -> str:
        opponent_draw = a.game_state(
            2,
            2,
            turnInfo=a.turn(6, active=1),
            zones=[a.zone(a.HAND_1, "Hand", [301, 302, 303, 304], owner=1)],
            annotations=[
                a.annotation(50, ["NewTurnStarted"], affector=1, affected=[1]),
                a.annotation(
                    51,
                    ["ZoneTransfer"],
                    affector=1,
                    affected=[304],
                    zone_src=a.LIBRARY_1,
                    zone_dest=a.HAND_1,
                    category="Draw",
                ),
            ],
        )
        cast_and_hit = a.game_state(
            3,
            2,
            gameObjects=[a.card(400, a.GIANT_GROWTH, a.STACK, 1)],
            annotations=[
                a.annotation(
                    52,
                    ["ZoneTransfer"],
                    affector=1,
                    affected=[400],
                    zone_src=a.HAND_1,
                    zone_dest=a.STACK,
                    category="CastSpell",
                ),
                a.annotation(53, ["DamageDealt"], affector=310, affected=[2], damage=7),
                a.annotation(54, ["ModifiedLife"], affector=310, affected=[2], life=-7),
                a.annotation(
                    55,
                    ["CounterAdded"],
                    affector=400,
                    affected=[310],
                    counter_type=1,
                    transaction_amount=2,
                ),
                a.annotation(
                    56,
                    ["ZoneTransfer"],
                    affector=1,
                    affected=[213],
                    zone_src=a.BATTLEFIELD,
                    zone_dest=a.EXILE,
                    category="Blink",
                ),
            ],
        )
        return "\n".join([a.gre_line(opponent_draw), a.gre_line(cast_and_hit)])

    def test_events_are_described_in_order_with_hidden_cards_left_hidden(self, read, opening):
        events = read([*opening, self._a_turn_of_play()]).recent_events

        assert events == [
            "T6 turn begins (opponent)",
            "T6 opponent drew a card",
            "T6 opponent cast Giant Growth",
            "T6 Serra Angel dealt 7 damage to you",
            "T6 you lost 7 life",
            "T6 Serra Angel got 2 +1/+1 counter(s)",
            "T6 Grizzly Bears moved battlefield -> exile (Blink)",
        ]

    def test_the_caller_chooses_how_many(self, read, opening):
        lines = [*opening, self._a_turn_of_play()]

        assert len(read(lines, recent_events=2).recent_events) == 2
        assert read(lines, recent_events=0).recent_events == []
        assert len(read(lines, recent_events=10_000).recent_events) == 7

    def _life_ticks(self, count: int) -> str:
        """One message in which you lose 1, then 2, then 3 life: ``count`` events in all."""
        ticks = [
            a.annotation(100 + n, ["ModifiedLife"], affector=310, affected=[2], life=-n)
            for n in range(1, count + 1)
        ]
        return a.gre_line(a.game_state(2, 2, annotations=ticks))

    def test_the_latest_fifty_are_listed_unless_more_are_asked_for(self, read, opening):
        lines = [*opening, self._life_ticks(60)]

        latest = read(lines)
        whole_game = read(lines, recent_events=60)

        assert len(latest.recent_events) == 50
        assert latest.recent_events[0] == "T5 you lost 11 life"
        assert latest.recent_events[-1] == "T5 you lost 60 life"
        assert latest.earlier_events == 10
        assert len(whole_game.recent_events) == 60
        assert whole_game.recent_events[0] == "T5 you lost 1 life"
        assert whole_game.earlier_events is None

    def test_events_left_out_are_counted(self, read, opening):
        lines = [*opening, self._a_turn_of_play()]

        assert read(lines, recent_events=2).earlier_events == 5
        assert read(lines, recent_events=0).earlier_events == 7
        assert read(lines, recent_events=7).earlier_events is None

    def test_one_call_lists_five_hundred_at_most(self, read, opening):
        result = read([*opening, self._life_ticks(510)], recent_events=10_000)

        assert len(result.recent_events) == 500
        assert result.recent_events[0] == "T5 you lost 11 life"
        assert result.earlier_events == 10

    def test_a_triggered_ability_is_reported_with_its_text_and_a_mana_ability_is_not(
        self, read, opening
    ):
        trigger = a.card(
            401, a.BEAR_TRIGGER, a.STACK, 2, type="GameObjectType_Ability", objectSourceGrpId=a.BEAR
        )
        diff = a.game_state(
            2,
            2,
            gameObjects=[trigger],
            annotations=[
                a.annotation(60, ["AbilityInstanceCreated"], affector=213, affected=[401]),
                # A mana ability is announced the same way but never becomes an object.
                a.annotation(61, ["AbilityInstanceCreated"], affector=212, affected=[402]),
            ],
        )

        assert read([*opening, a.gre_line(diff)]).recent_events == [
            "T5 Grizzly Bears ability (you): When Grizzly Bears enters, you gain 1 life."
        ]


class TestTheEndOfTheGame:
    def _conceded(self, winner: int) -> str:
        over = a.game_state(
            2,
            2,
            gameInfo={
                "matchID": "match-1",
                "stage": "GameStage_GameOver",
                "results": [
                    {
                        "scope": "MatchScope_Game",
                        "result": "ResultType_WinLoss",
                        "winningTeamId": winner,
                        "reason": "ResultReason_Concede",
                    }
                ],
            },
        )
        return a.gre_line(over)

    @pytest.mark.parametrize(
        ("winner", "expected"), [(1, "you lost (concede)"), (2, "you won (concede)")]
    )
    def test_the_result_is_reported_from_this_players_side(self, read, opening, winner, expected):
        result = read([*opening, self._conceded(winner)])

        assert result.status == "ok"
        assert result.in_progress is False
        assert result.result == expected

    def test_the_final_board_is_still_there_to_review(self, read, opening):
        result = read([*opening, self._conceded(1)])

        assert _names(result.you.hand) == ["Giant Growth", "Grizzly Bears"]

    def test_no_decision_is_pending_once_the_game_is_over(self, read, opening):
        intermission = a.request("IntermissionReq", 2, 2)
        stale = a.request("SelectNReq", 2, 2, selectNReq={"ids": [213]})

        result = read([*opening, self._conceded(1), a.gre_line(intermission, stale)])

        assert result.pending_decision is None


class TestMatchDetails:
    def test_the_event_name_comes_from_the_match_room(self, read, opening):
        assert read([a.room_line("match-1", 2, "Brawl_Ladder"), *opening]).event == "Brawl_Ladder"

    def test_a_room_from_an_earlier_match_is_not_used(self, read, opening):
        assert read([a.room_line("match-0", 2, "Old_Event"), *opening]).event is None

    def test_staleness_is_measured_from_the_newest_game_message(self, read):
        five_minutes_ago = int(time.time() * 1000) - 300_000
        lines = [a.gre_line(opening_state(), timestamp_ms=five_minutes_ago)]

        assert 299 <= read(lines).seconds_since_last_update <= 310


class TestCardText:
    def test_is_off_unless_asked_for(self, read, opening):
        assert read(opening).card_text == {}

    def test_covers_every_named_card_but_basic_lands(self, read, opening):
        card_text = read(opening, include_card_text=True).card_text

        assert sorted(card_text) == [
            "Bonesplitter",
            "Giant Growth",
            "Grizzly Bears",
            "Jadzia Dax",
            "Serra Angel",
        ]
        assert card_text["Serra Angel"] == "{3}{W}{W} | Creature — Angel | 4/4 | Flying / Vigilance"


class TestWhenTheGameCannotBeRead:
    def test_no_log(self, tmp_path: Path):
        result = read_game_state(log_path=tmp_path / "absent" / "Player.log")

        assert result.status == "log_not_found"
        assert LOG_PATH_ENV in result.message

    def test_logging_switched_off_says_how_to_switch_it_on(self, read):
        result = read([], detailed_logs=False)

        assert result.status == "detailed_logs_disabled"
        assert "Detailed Logs" in result.message

    def test_logging_on_but_no_game_played(self, read):
        assert read([]).status == "no_game"

    def test_a_game_in_the_log_wins_over_a_disabled_notice(self, read, opening):
        assert read(opening, detailed_logs=False).status == "ok"

    def test_without_a_card_database_cards_are_numbered_and_the_result_says_why(
        self, read, opening, tmp_path: Path
    ):
        result = read(opening, card_database=tmp_path / "absent.mtga")

        assert result.status == "ok"
        assert result.you.life == 20
        assert _names(result.you.hand) == [
            f"unknown card #{a.GIANT_GROWTH}",
            f"unknown card #{a.BEAR}",
        ]
        assert len(result.warnings) == 1
        assert "MTGA_INSTALL_DIR" in result.warnings[0]

    def test_a_card_the_database_does_not_know_is_numbered_and_flagged(self, read):
        state = opening_state()
        state["gameStateMessage"]["gameObjects"].append(a.card(202, a.UNKNOWN_CARD, a.HAND_2, 2))

        result = read([a.gre_line(a.connect(2)), a.gre_line(state)])

        assert _names(result.you.hand) == ["Giant Growth", f"unknown card #{a.UNKNOWN_CARD}"]
        assert result.warnings == [
            "Some cards are not in Arena's card database and are shown by number."
        ]


class TestFindingTheFiles:
    def test_the_log_override_is_used_alone(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv(LOG_PATH_ENV, str(tmp_path / "elsewhere.log"))

        assert locate.player_log_candidates() == [tmp_path / "elsewhere.log"]
        assert locate.find_player_log() is None

    def test_the_default_log_is_found_under_the_home_directory(self, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        default = locate.player_log_candidates()[0]
        assert default.is_relative_to(tmp_path)
        assert default.parts[-3:] == ("Wizards Of The Coast", "MTGA", "Player.log")
        default.parent.mkdir(parents=True)
        default.write_text("", encoding="utf-8")

        assert locate.find_player_log() == default

    def test_the_card_database_is_found_from_the_install_directory_the_log_names(
        self, opening, tmp_path: Path
    ):
        install = tmp_path / "Games" / "MTGA"
        raw = install / "MTGA_Data" / "Downloads" / "Raw"
        raw.mkdir(parents=True)
        a.build_card_database(raw / "Raw_CardDatabase_abc.mtga")
        log = a.write_log(tmp_path / "Player.log", opening, install_dir=install.as_posix())

        result = read_game_state(log_path=log)

        assert _names(result.you.hand) == ["Giant Growth", "Grizzly Bears"]
        assert result.warnings == []

    def test_the_card_database_override_naming_a_missing_file_finds_nothing(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setenv(CARD_DATABASE_ENV, str(tmp_path / "absent.mtga"))

        assert locate.find_card_database(tmp_path) is None


class TestTellingLookalikesApart:
    """A reference to a card whose name is shared says which one, and that card says so too."""

    def _refs(self, views) -> list[tuple[str, int | None, int | None]]:
        return [(view.name, view.ref, view.count) for view in views if view.name == "Grizzly Bears"]

    def test_a_unique_name_is_referred_to_bare(self, read, opening):
        result = read(opening)

        bears, equipment = result.you.battlefield[0], result.you.battlefield[1]
        # The copy in hand cannot be equipped, so it does not make this one ambiguous.
        assert equipment.attached_to == "Grizzly Bears"
        assert bears.ref is None
        assert "ref" not in bears.model_dump()

    def test_a_target_names_the_right_one_of_two_same_named_creatures(self, read, opening):
        diff = a.game_state(
            2,
            2,
            zones=[
                a.zone(a.STACK, "Stack", [400]),
                a.zone(a.BATTLEFIELD, "Battlefield", [210, 211, 212, 213, 214, 310, 311]),
            ],
            gameObjects=[
                a.card(311, a.BEAR, a.BATTLEFIELD, 1, **a.stats(2, 2)),
                a.card(400, a.GIANT_GROWTH, a.STACK, 2),
            ],
            persistentAnnotations=[a.annotation(9, ["TargetSpec"], affector=400, affected=[311])],
        )

        result = read([*opening, a.gre_line(diff)])

        assert result.stack[0].targets == ["Grizzly Bears #311"]
        assert self._refs(result.opponent.battlefield) == [("Grizzly Bears", 311, None)]
        # Its own Bonesplitter points at yours, so yours is numbered as well.
        assert self._refs(result.you.battlefield) == [("Grizzly Bears", 213, None)]
        assert result.you.battlefield[1].attached_to == "Grizzly Bears #213"
        # Nothing points at the spell itself.
        assert result.stack[0].ref is None

    def test_interchangeable_copies_share_one_number_and_stay_merged(self, read, opening):
        diff = a.game_state(
            2,
            2,
            zones=[a.zone(a.BATTLEFIELD, "Battlefield", [210, 211, 212, 213, 214, 310, 311, 312])],
            gameObjects=[
                a.card(311, a.BEAR, a.BATTLEFIELD, 1, **a.stats(2, 2)),
                a.card(312, a.BEAR, a.BATTLEFIELD, 1, **a.stats(2, 2)),
            ],
        )
        choose = a.request(
            "SelectTargetsReq",
            2,
            2,
            selectTargetsReq={
                "targets": [
                    {
                        "targets": [
                            {"targetInstanceId": 213},
                            {"targetInstanceId": 311},
                            {"targetInstanceId": 312},
                        ]
                    }
                ]
            },
        )

        result = read([*opening, a.gre_line(diff, choose)])

        assert result.pending_decision.options == ["Grizzly Bears #213", "Grizzly Bears #311"]
        assert self._refs(result.opponent.battlefield) == [("Grizzly Bears", 311, 2)]

    def test_a_blocker_names_which_attacker_it_blocks(self, read, opening):
        diff = a.game_state(
            2,
            2,
            zones=[a.zone(a.BATTLEFIELD, "Battlefield", [210, 211, 212, 213, 214, 310, 311, 312])],
            gameObjects=[
                a.card(
                    311,
                    a.BEAR,
                    a.BATTLEFIELD,
                    1,
                    attackState="AttackState_Attacking",
                    **a.stats(2, 2),
                ),
                a.card(312, a.BEAR, a.BATTLEFIELD, 1, **a.stats(2, 2)),
                a.card(213, a.BEAR, a.BATTLEFIELD, 2, blockInfo={"attackerIds": [311]}),
            ],
        )

        result = read([*opening, a.gre_line(diff)])

        mine = next(view for view in result.you.battlefield if view.name == "Grizzly Bears")
        assert mine.blocking == ["Grizzly Bears #311"]
        theirs = [v for v in result.opponent.battlefield if v.name == "Grizzly Bears"]
        assert [(view.ref, view.flags) for view in theirs] == [(311, ["attacking"]), (None, [])]

    def _two_identical_opposing_bears(self, **attacker) -> dict:
        return {
            "zones": [
                a.zone(a.BATTLEFIELD, "Battlefield", [210, 211, 212, 213, 214, 310, 311, 312]),
                a.zone(a.STACK, "Stack", [400]),
            ],
            "gameObjects": [
                a.card(311, a.BEAR, a.BATTLEFIELD, 1, **attacker, **a.stats(2, 2)),
                a.card(312, a.BEAR, a.BATTLEFIELD, 1, **attacker, **a.stats(2, 2)),
                a.card(400, a.GIANT_GROWTH, a.STACK, 2),
            ],
        }

    def test_being_targeted_sets_one_of_two_identical_creatures_apart(self, read, opening):
        diff = a.game_state(
            2,
            2,
            **self._two_identical_opposing_bears(),
            persistentAnnotations=[a.annotation(9, ["TargetSpec"], affector=400, affected=[312])],
        )

        result = read([*opening, a.gre_line(diff)])

        assert result.stack[0].targets == ["Grizzly Bears #312"]
        assert self._refs(result.opponent.battlefield) == [
            ("Grizzly Bears", None, None),
            ("Grizzly Bears", 312, None),
        ]

    def test_being_blocked_sets_one_of_two_identical_attackers_apart(self, read, opening):
        fields = self._two_identical_opposing_bears(attackState="AttackState_Attacking")
        fields["gameObjects"].append(
            a.card(213, a.BEAR, a.BATTLEFIELD, 2, blockInfo={"attackerIds": [312]})
        )

        result = read([*opening, a.gre_line(a.game_state(2, 2, **fields))])

        mine = next(view for view in result.you.battlefield if view.name == "Grizzly Bears")
        assert mine.blocking == ["Grizzly Bears #312"]
        assert self._refs(result.opponent.battlefield) == [
            ("Grizzly Bears", None, None),
            ("Grizzly Bears", 312, None),
        ]

    def test_being_the_only_legal_choice_sets_one_of_two_identical_creatures_apart(
        self, read, opening
    ):
        choose = a.request(
            "SelectTargetsReq",
            2,
            2,
            selectTargetsReq={"targets": [{"targets": [{"targetInstanceId": 312}]}]},
        )
        diff = a.game_state(2, 2, **self._two_identical_opposing_bears())

        result = read([*opening, a.gre_line(diff, choose)])

        assert result.pending_decision.options == ["Grizzly Bears #312"]
        assert self._refs(result.opponent.battlefield) == [
            ("Grizzly Bears", None, None),
            ("Grizzly Bears", 312, None),
        ]

    def test_a_card_is_numbered_by_a_pointer_that_is_rendered_after_it(self, read, opening):
        # The opponent's Equipment sits on one of your two otherwise identical creatures; your
        # side is rendered before theirs.
        diff = a.game_state(
            2,
            2,
            zones=[
                a.zone(a.BATTLEFIELD, "Battlefield", [210, 211, 212, 213, 214, 215, 216, 310, 330])
            ],
            gameObjects=[
                a.card(215, a.BEAR, a.BATTLEFIELD, 2, **a.stats(2, 2)),
                a.card(216, a.BEAR, a.BATTLEFIELD, 2, **a.stats(2, 2)),
                a.card(330, a.EQUIPMENT, a.BATTLEFIELD, 1),
            ],
            persistentAnnotations=[a.annotation(9, ["Attachment"], affector=330, affected=[215])],
        )

        result = read([*opening, a.gre_line(diff)])

        theirs = next(view for view in result.opponent.battlefield if view.name == "Bonesplitter")
        assert theirs.attached_to == "Grizzly Bears #215"
        assert self._refs(result.you.battlefield) == [
            ("Grizzly Bears", 213, None),
            ("Grizzly Bears", 215, None),
            ("Grizzly Bears", None, None),
        ]


class TestAnUnexpectedLogShape:
    """Valid JSON of a shape the reader has never seen costs that field, not the game."""

    _LIFE_CHANGE = a.game_state(3, 2, players=[a.player(2, life=11)])

    @pytest.mark.parametrize(
        "line",
        [
            '{"greToClientEvent": null}',
            '{"greToClientEvent": []}',
            '{"greToClientEvent": {"greToClientMessages": null}}',
            '{"greToClientEvent": {"greToClientMessages": "none"}}',
            '{"greToClientEvent": {"greToClientMessages": [null, 5, "text"]}}',
            '{"matchGameRoomStateChangedEvent": null}',
            '{"matchGameRoomStateChangedEvent": "closed"}',
        ],
    )
    def test_an_event_with_no_usable_body_is_passed_over(self, read, opening, line, caplog):
        result = read([*opening, line, a.gre_line(self._LIFE_CHANGE)])

        assert result.status == "ok"
        assert result.you.life == 11
        assert _names(result.you.hand) == ["Giant Growth", "Grizzly Bears"]
        # Recognised as empty, not rescued by the reader's catch-all.
        assert "unexpected shape" not in caplog.text

    @pytest.mark.parametrize(
        "fields",
        [
            {"players": None, "zones": None, "gameObjects": None, "annotations": None},
            {"players": "x", "zones": 3, "gameObjects": {"a": 1}, "annotations": True},
            {"players": [None], "zones": [7], "gameObjects": ["x"], "annotations": [None]},
            {"persistentAnnotations": None, "diffDeletedPersistentAnnotationIds": None},
            {"persistentAnnotations": [5], "diffDeletedPersistentAnnotationIds": [[1], "2"]},
            {"diffDeletedInstanceIds": None},
            {"diffDeletedInstanceIds": [[213], {"id": 213}]},
            {"annotations": [{"id": 1, "type": None, "affectedIds": None, "details": None}]},
            {
                "annotations": [
                    {
                        "id": 1,
                        "type": ["AnnotationType_ZoneTransfer", "AnnotationType_DamageDealt"],
                        "affectedIds": 213,
                        "details": [None, {"key": "zone_src", "valueInt32": 31}],
                    }
                ]
            },
            {"annotations": [{"type": ["AnnotationType_ZoneTransfer"], "affectedIds": [[213]]}]},
        ],
    )
    def test_a_game_state_with_misshapen_fields_keeps_the_rest_of_the_game(
        self, read, opening, fields, caplog
    ):
        odd = a.game_state(2, 2, **fields)

        result = read([*opening, a.gre_line(odd), a.gre_line(self._LIFE_CHANGE)])

        assert "unexpected shape" not in caplog.text
        assert result.status == "ok"
        assert result.you.life == 11
        assert _names(result.you.battlefield) == [
            "Grizzly Bears",
            "Bonesplitter",
            "Forest",
            "Forest",
        ]

    @pytest.mark.parametrize(
        "overrides", [{"systemSeatIds": 2}, {"systemSeatIds": None}, {"gameStateId": "soon"}]
    )
    def test_a_message_with_a_misshapen_envelope_is_survived(self, read, opening, overrides):
        odd = {**a.game_state(2, 2), **overrides}
        request = {**a.request("ActionsAvailableReq", 2, 2), **overrides}

        result = read([*opening, a.gre_line(odd, request), a.gre_line(self._LIFE_CHANGE)])

        assert result.status == "ok"
        assert result.you.life == 11

    def test_null_where_the_board_expects_a_list_costs_only_that_detail(self, read):
        state = opening_state()
        message = state["gameStateMessage"]
        message["players"][1]["manaPool"] = None
        message["gameInfo"]["results"] = None
        message["gameObjects"][2]["cardTypes"] = None  # the first Forest
        message["persistentAnnotations"].append({"id": 8, "type": None})
        next(z for z in message["zones"] if z["zoneId"] == a.LIBRARY_1)["objectInstanceIds"] = None

        result = read([a.gre_line(a.connect(2)), a.gre_line(state)])

        assert result.status == "ok"
        assert result.opponent.library_count == 0
        assert result.you.library_count == 49
        assert "Forest" in _names(result.you.battlefield)

    def test_an_event_the_tracker_cannot_apply_costs_only_that_event(
        self, read, opening, monkeypatch
    ):
        def broken(self, document):
            raise TypeError("a shape nobody has seen yet")

        monkeypatch.setattr(GameTracker, "feed_room", broken)

        result = read([a.room_line("match-1", 2, "Brawl_Ladder"), *opening])

        assert result.status == "ok"
        assert result.event is None
        assert result.you.life == 20

    def test_a_board_that_cannot_be_rendered_is_an_error_status_not_an_exception(
        self, read, opening, monkeypatch
    ):
        def broken(self, **_):
            raise TypeError("a shape nobody has seen yet")

        monkeypatch.setattr(SnapshotBuilder, "build", broken)

        result = read(opening)

        assert result.status == "error"
        assert "a shape nobody has seen yet" in result.message


class TestARelativeCardDatabasePath:
    def test_the_override_may_be_relative_to_the_working_directory(
        self, monkeypatch, tmp_path: Path, opening
    ):
        a.build_card_database(tmp_path / "cards.mtga")
        log = a.write_log(tmp_path / "Player.log", opening)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv(CARD_DATABASE_ENV, "cards.mtga")

        result = read_game_state(log_path=log)

        assert result.status == "ok"
        assert _names(result.you.hand) == ["Giant Growth", "Grizzly Bears"]
        assert result.warnings == []


class TestTheMcpTool:
    async def test_the_tool_is_registered_read_only(self, tmp_path: Path, card_database: Path):
        server = build_server(log_path=tmp_path / "Player.log", card_database=card_database)

        (tool,) = await server.list_tools()

        assert tool.name == "read_game_state"
        assert tool.annotations.readOnlyHint is True

    async def test_the_wire_result_leaves_out_everything_unset(
        self, opening, tmp_path: Path, card_database: Path
    ):
        log = a.write_log(tmp_path / "Player.log", opening)
        server = build_server(log_path=log, card_database=card_database)

        content, structured = await server.call_tool("read_game_state", {"recent_events": 0})

        assert json.loads(content[0].text) == structured
        assert structured["status"] == "ok"
        assert structured["opponent"]["hand_count"] == 3
        assert "hand" not in structured["opponent"]
        assert "stack" not in structured
        assert "null" not in content[0].text
        untapped_forest = structured["you"]["battlefield"][3]
        assert untapped_forest == {"name": "Forest"}

    async def test_the_tool_lists_fifty_events_unless_told_otherwise(
        self, opening, tmp_path: Path, card_database: Path
    ):
        ticks = [
            a.annotation(100 + n, ["ModifiedLife"], affector=310, affected=[2], life=-1)
            for n in range(60)
        ]
        lines = [*opening, a.gre_line(a.game_state(2, 2, annotations=ticks))]
        log = a.write_log(tmp_path / "Player.log", lines)
        server = build_server(log_path=log, card_database=card_database)

        _, by_default = await server.call_tool("read_game_state", {})
        _, asked = await server.call_tool("read_game_state", {"recent_events": 60})

        assert len(by_default["recent_events"]) == 50
        assert by_default["earlier_events"] == 10
        assert len(asked["recent_events"]) == 60
        assert "earlier_events" not in asked

    async def test_a_missing_log_is_a_status_not_an_error(self, tmp_path: Path):
        server = build_server(log_path=tmp_path / "Player.log")

        _, structured = await server.call_tool("read_game_state", {})

        assert structured["status"] == "log_not_found"

"""The game-state result an agent reads.

These models serialize compactly on purpose. A board can hold dozens of permanents, and a result
that spelled out every unset field for each one would bury the state in ``null``. So an unset
field is omitted from the output entirely, per-card booleans are folded into one ``flags`` list,
and identical cards (four untapped Forests, eleven of the same token) collapse into one entry with
a ``count``.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer

GameStateStatus = Literal["ok", "no_game", "detailed_logs_disabled", "log_not_found", "error"]
Seat = Literal["you", "opponent"]


class CompactModel(BaseModel):
    """A model that leaves ``None`` and empty collections out of its serialized form."""

    @model_serializer(mode="wrap")
    def _omit_unset(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        return {
            key: value
            for key, value in data.items()
            if value is not None and value != [] and value != {}
        }


class CardView(CompactModel):
    """One card, or several identical ones, in a zone."""

    name: str
    ref: int | None = Field(
        default=None,
        description=(
            "Set when something points at this card and its name alone is ambiguous: a target, "
            "attachment, blocker or option written 'Name #N' means the entry whose ref is N."
        ),
    )
    count: int | None = Field(default=None, description="Identical copies, when more than one.")
    type_line: str | None = Field(default=None, description="Shown for tokens only.")
    mana_cost: str | None = Field(default=None, description="Shown in hand and on the stack.")
    power_toughness: str | None = Field(
        default=None, description="Current power/toughness, counters and effects included."
    )
    flags: list[str] = Field(
        default_factory=list,
        description=(
            "Any of: tapped, summoning_sick, attacking, blocked, unblocked, blocking, token, "
            "commander, face_down, controlled_by_other_player."
        ),
    )
    damage: int | None = Field(default=None, description="Damage marked on it this turn.")
    counters: dict[str, int] = Field(default_factory=dict)
    attached_to: str | None = Field(default=None, description="What an Aura or Equipment is on.")
    blocking: list[str] = Field(default_factory=list, description="The attackers it blocks.")


class StackItem(CompactModel):
    """A spell or ability on the stack."""

    name: str
    ref: int | None = Field(default=None, description="As on a card: 'Name #N' points here.")
    kind: Literal["spell", "ability"]
    controller: Seat
    mana_cost: str | None = None
    text: str | None = Field(default=None, description="An ability's rules text.")
    targets: list[str] = Field(default_factory=list)


class PlayerView(CompactModel):
    """Everything this player can see of one player's side."""

    life: int | None = None
    commander: str | None = None
    mana_pool: str | None = Field(default=None, description="Unspent mana, e.g. {G}{G}.")
    counters: dict[str, int] = Field(default_factory=dict, description="Player counters (poison).")
    hand_count: int = 0
    hand: list[CardView] = Field(
        default_factory=list,
        description="The cards whose identity is known: all of yours, revealed ones of theirs.",
    )
    library_count: int = 0
    battlefield: list[CardView] = Field(default_factory=list)
    graveyard: list[CardView] = Field(default_factory=list)
    exile: list[CardView] = Field(default_factory=list)
    command_zone: list[CardView] = Field(default_factory=list)


class TurnView(CompactModel):
    """Where the game is in the turn structure."""

    number: int | None = None
    phase: str | None = None
    step: str | None = None
    active_player: Seat | None = None
    priority_player: Seat | None = None
    decision_player: Seat | None = Field(
        default=None, description="Who the game is waiting on right now."
    )


class LegalAction(CompactModel):
    """One play the game is offering."""

    action: str = Field(description="cast, play (a land), activate, or another engine action.")
    card: str | None = None
    mana_cost: str | None = None
    ability: str | None = Field(default=None, description="The rules text of an activated ability.")
    affordable: bool | None = Field(
        default=None,
        description="True when Arena found a way to pay for it with the mana available now.",
    )


class PendingDecision(CompactModel):
    """What the game is waiting for you to decide."""

    kind: str = Field(
        description=(
            "actions_available (you have priority), select_targets, declare_attackers, "
            "declare_blockers, mulligan, or another engine request."
        )
    )
    prompt: str | None = None
    source: str | None = Field(default=None, description="The card asking for the decision.")
    actions: list[LegalAction] = Field(default_factory=list)
    options: list[str] = Field(
        default_factory=list,
        description="Legal targets, attackers or blockers, by name ('Name #N' when ambiguous).",
    )


class GameStateResult(CompactModel):
    """The latest Arena game as this player sees it."""

    status: GameStateStatus
    message: str | None = None
    in_progress: bool | None = None
    result: str | None = Field(default=None, description="How the game ended, once it has.")
    event: str | None = Field(default=None, description="Arena's event name, e.g. Brawl_Ladder.")
    game_number: int | None = None
    seconds_since_last_update: int | None = Field(
        default=None, description="Age of the newest game message in the log."
    )
    turn: TurnView | None = None
    you: PlayerView | None = None
    opponent: PlayerView | None = None
    stack: list[StackItem] = Field(default_factory=list, description="Top of the stack first.")
    pending_decision: PendingDecision | None = None
    recent_events: list[str] = Field(default_factory=list, description="Oldest first.")
    earlier_events: int | None = Field(
        default=None,
        description=(
            "How many older events of this game were not listed; ask for more recent_events to "
            "see them."
        ),
    )
    card_text: dict[str, str] = Field(
        default_factory=dict, description="Rules text by card name, when requested."
    )
    warnings: list[str] = Field(default_factory=list)

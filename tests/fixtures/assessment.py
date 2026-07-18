"""Shared Card/DeckCard factories for the assessment-core test modules (Stories 5.3+).

Promoted from ``tests/unit/logic/test_assessment_classifiers.py`` when Story 5.4 became the
second consumer (the ``_FakeEmbedder`` "consolidate before the second copy" lesson, pre-epic-3
gate G1). Import these from every ``src/logic/assessment`` test module instead of redefining.
"""

from typing import Any

from src.data.schemas.card import Card
from src.data.schemas.combo import ComboRecord
from src.data.schemas.deck import DeckCard


def make_card(**overrides: Any) -> Card:
    """Build a minimal valid ``Card``, overriding only the fields a test cares about."""
    defaults: dict[str, Any] = {
        "id": "00000000-0000-0000-0000-000000000000",
        "name": "Test Card",
        "oracle_id": "11111111-1111-1111-1111-111111111111",
        "mana_cost": "{1}",
        "cmc": 1.0,
        "type_line": "Sorcery",
        "oracle_text": "",
        "rarity": "common",
        "set_code": "tst",
        "set_name": "Test Set",
        "collector_number": "1",
        "colors": [],
        "color_identity": [],
        "legalities": {},
    }
    defaults.update(overrides)
    return Card(**defaults)


def make_deck_card(card: Card, quantity: int = 1, sideboard: bool = False) -> DeckCard:
    """Wrap a ``Card`` in a ``DeckCard`` association row."""
    return DeckCard(
        deck_id="deck-1",
        card_id=card.id,
        quantity=quantity,
        sideboard=sideboard,
        card=card,
    )


def make_combo_record(**overrides: Any) -> ComboRecord:
    """Build a minimal valid ``ComboRecord``, overriding only the fields a test cares about.

    Defaults: two already-sorted piece names, ``CASUAL`` bracket tag, no commander
    requirement, ``bucket=None`` (the stored/repo state), one infinite ``produces``
    entry, and ``popularity=None`` (Story 5.6).
    """
    defaults: dict[str, Any] = {
        "spellbook_id": "1000-2000",
        "cards": ("Combo Piece A", "Combo Piece B"),
        "commander_required": False,
        "bucket": None,
        "bracket_tag": "CASUAL",
        "produces": ("Infinite mana",),
        "popularity": None,
    }
    defaults.update(overrides)
    return ComboRecord(**defaults)


# ---------------------------------------------------------------------------
# Tagged-card builders (Story 5.9) — promoted from the local builders in
# tests/unit/logic/test_assessment_dimensions.py when the scorer tests became the
# second consumer (the _FakeEmbedder "consolidate before the second copy" lesson).
# Each targets exactly one classifier category via canonical oracle-text phrasing.
# ---------------------------------------------------------------------------


def make_vanilla_card(name: str = "Vanilla Bear", cmc: float = 2.0, **overrides: Any) -> Card:
    """An untagged filler creature — matches no classifier category."""
    defaults: dict[str, Any] = {
        "name": name,
        "cmc": cmc,
        "mana_cost": "{2}",
        "type_line": "Creature — Bear",
        "oracle_text": "",
    }
    defaults.update(overrides)
    return make_card(**defaults)


def make_land_card(name: str = "Barren Land") -> Card:
    """A colorless land (no colored sources, no ramp tag)."""
    return make_card(
        name=name, cmc=0.0, mana_cost="", type_line="Land", oracle_text="{T}: Add {C}."
    )


def make_ramp_card(name: str = "Mana Rock", cmc: float = 2.0) -> Card:
    """A RAMP-tagged non-land mana producer."""
    return make_card(
        name=name, cmc=cmc, mana_cost="{2}", type_line="Artifact", oracle_text="{T}: Add {C}{C}."
    )


def make_tutor_card(name: str = "Grim Tutor Copy", cmc: float = 2.0) -> Card:
    """A TUTOR-tagged generic library search to hand."""
    return make_card(
        name=name,
        cmc=cmc,
        mana_cost="{2}",
        type_line="Sorcery",
        oracle_text="Search your library for a card, put it into your hand, then shuffle.",
    )


def make_draw_card(name: str = "Divination Copy", cmc: float = 3.0) -> Card:
    """A CARD_DRAW-tagged spell."""
    return make_card(
        name=name, cmc=cmc, mana_cost="{3}", type_line="Sorcery", oracle_text="Draw two cards."
    )


def make_interaction_card(
    name: str = "Doom Blade Copy", cmc: float = 2.0, type_line: str = "Instant"
) -> Card:
    """An INTERACTION-tagged removal spell (instant-speed unless overridden)."""
    return make_card(
        name=name,
        cmc=cmc,
        mana_cost="{2}",
        type_line=type_line,
        oracle_text="Destroy target creature.",
    )


def make_wincon_card(name: str = "Lab Man Copy", cmc: float = 3.0) -> Card:
    """A WINCON_EXPLICIT-tagged card."""
    return make_card(
        name=name,
        cmc=cmc,
        mana_cost="{3}",
        type_line="Creature — Human Wizard",
        oracle_text="You win the game.",
    )


def make_extra_turn_card(name: str = "Time Warp Copy", cmc: float = 5.0) -> Card:
    """An EXTRA_TURN-tagged spell."""
    return make_card(
        name=name,
        cmc=cmc,
        mana_cost="{5}",
        type_line="Sorcery",
        oracle_text="Take an extra turn after this one.",
    )


def make_mld_card(name: str = "Armageddon Copy", cmc: float = 4.0) -> Card:
    """A MASS_LAND_DENIAL-tagged spell."""
    return make_card(
        name=name, cmc=cmc, mana_cost="{4}", type_line="Sorcery", oracle_text="Destroy all lands."
    )


def make_gc_card(name: str, value: bool | None) -> Card:
    """An otherwise-untagged creature with an EXPLICIT game_changer state."""
    return make_vanilla_card(name=name, game_changer=value)

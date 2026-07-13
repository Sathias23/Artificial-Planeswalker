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

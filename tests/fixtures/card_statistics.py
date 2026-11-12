"""The card-statistics verify deck and edge-case cards, shared by the unit, pin and parity tests.

One definition of each card, as plain column values, so the same card reaches a ``Card`` schema
(the logic tests), a ``DeckCard`` row (the assessment pins) and a ``CardModel`` row in a real
database (the MCP-client and ``GET /api/deck/{id}`` parity test) without three hand-kept copies.

The verify deck is the story's I/O matrix row: a ``Sorcery // Land`` MDFC, a 0-cost artifact, a
7-drop, a 9-drop, two basic Forests, two ``{G/W}`` hybrid creatures, a commander and one
sideboard card. Every card carries a cost whose pips are distinct from its neighbours', so a pip
counted twice, or not at all, changes a total.
"""

from typing import Any

from src.data.models.card import CardModel
from src.data.schemas.card import Card
from src.data.schemas.deck import DeckCard


def card_fields(card_id: str, name: str, **overrides: Any) -> dict[str, Any]:
    """Return a complete card row's column values, overriding only what a test cares about."""
    fields: dict[str, Any] = {
        "id": card_id,
        "name": name,
        "printed_name": None,
        "oracle_id": f"oracle-{card_id}",
        "mana_cost": "",
        "cmc": 0.0,
        "type_line": "Sorcery",
        "oracle_text": "",
        "rarity": "common",
        "set_code": "TST",
        "set_name": "Test Set",
        "collector_number": "1",
        "colors": [],
        "color_identity": [],
        "legalities": {"commander": "legal", "standard": "legal"},
        "games": ["paper", "arena", "mtgo"],
    }
    fields.update(overrides)
    return fields


#: The verify deck's cards, by id.
VERIFY_CARDS: dict[str, dict[str, Any]] = {
    "card-mdfc": card_fields(
        "card-mdfc",
        "Verdant Summons // Verdant Hollow",
        type_line="Sorcery // Land",
        mana_cost="",
        cmc=1.0,
        card_faces=[
            {
                "name": "Verdant Summons",
                "mana_cost": "{G}",
                "type_line": "Sorcery",
                "oracle_text": "Search your library for a creature card.",
            },
            {
                "name": "Verdant Hollow",
                "mana_cost": "",
                "type_line": "Land",
                "oracle_text": "{T}: Add {W}.",
            },
        ],
        colors=["G"],
        color_identity=["G", "W"],
    ),
    "card-mox": card_fields("card-mox", "Zero Mox", type_line="Artifact", mana_cost="{0}", cmc=0.0),
    "card-seven": card_fields(
        "card-seven",
        "Seven Drop",
        type_line="Creature — Elemental",
        mana_cost="{5}{G}{G}",
        cmc=7.0,
        colors=["G"],
        color_identity=["G"],
    ),
    "card-nine": card_fields(
        "card-nine",
        "Nine Drop",
        type_line="Creature — Wurm",
        mana_cost="{7}{G}{G}",
        cmc=9.0,
        colors=["G"],
        color_identity=["G"],
    ),
    "card-forest": card_fields(
        "card-forest",
        "Forest",
        type_line="Basic Land — Forest",
        oracle_text="({T}: Add {G}.)",
    ),
    "card-hybrid": card_fields(
        "card-hybrid",
        "Hybrid Finks",
        type_line="Creature — Ouphe",
        mana_cost="{1}{G/W}{G/W}",
        cmc=3.0,
        colors=["G", "W"],
        color_identity=["G", "W"],
    ),
    "card-commander": card_fields(
        "card-commander",
        "Tester, the Commander",
        type_line="Legendary Creature — Elf Druid",
        mana_cost="{2}{G}{W}",
        cmc=4.0,
        colors=["G", "W"],
        color_identity=["G", "W"],
    ),
    "card-sideboard": card_fields(
        "card-sideboard",
        "Sideboard Bomb",
        type_line="Instant",
        mana_cost="{R}{R}",
        cmc=2.0,
        colors=["R"],
        color_identity=["R"],
    ),
}

#: The verify deck's rows: ``(card_id, quantity, sideboard, commander)``.
VERIFY_ROWS: tuple[tuple[str, int, bool, bool], ...] = (
    ("card-mdfc", 1, False, False),
    ("card-mox", 1, False, False),
    ("card-seven", 1, False, False),
    ("card-nine", 1, False, False),
    ("card-forest", 2, False, False),
    ("card-hybrid", 2, False, False),
    ("card-commander", 1, False, True),
    ("card-sideboard", 1, True, False),
)


#: The matrix's edge-case cards, one rule each, by id.
EDGE_CARDS: dict[str, dict[str, Any]] = {
    # A land face behind a spell: the front face decides, so this is a spell.
    "card-florahedron": card_fields(
        "card-florahedron",
        "Tangled Florahedron // Tangled Vale",
        type_line="Creature — Elemental // Land",
        mana_cost="",
        cmc=2.0,
        card_faces=[
            {
                "name": "Tangled Florahedron",
                "mana_cost": "{1}{G}",
                "type_line": "Creature — Elemental",
                "oracle_text": "{T}: Add {G}.",
            },
            {
                "name": "Tangled Vale",
                "mana_cost": "",
                "type_line": "Land",
                "oracle_text": "Tangled Vale enters tapped.\n{T}: Add {G}.",
            },
        ],
    ),
    # The degenerate printing whose real front-face type lives only in card_faces[0].
    "card-card-card": card_fields(
        "card-card-card",
        "Hidden Vale // Hidden Beast",
        type_line="Card // Card",
        mana_cost="",
        cmc=0.0,
        card_faces=[
            {
                "name": "Hidden Vale",
                "mana_cost": "",
                "type_line": "Land",
                "oracle_text": "{T}: Add {U}.",
            },
            {
                "name": "Hidden Beast",
                "mana_cost": "{3}{U}",
                "type_line": "Creature — Beast",
                "oracle_text": "",
            },
        ],
    ),
    # A subtype that contains the letters but is not the word.
    "card-lander": card_fields(
        "card-lander",
        "Lander Scout",
        type_line="Artifact Creature — Lander",
        mana_cost="{2}",
        cmc=2.0,
        oracle_text="Search your library for a basic land card, put it onto the battlefield.",
    ),
    "card-dryad-arbor": card_fields(
        "card-dryad-arbor",
        "Dryad Arbor",
        type_line="Land Creature — Forest Dryad",
        mana_cost="",
        cmc=0.0,
        oracle_text="(Dryad Arbor isn't a spell, it's affected by summoning sickness.)",
    ),
    "card-half": card_fields(
        "card-half", "Little Girl", type_line="Creature — Human Child", mana_cost="{HW}", cmc=0.5
    ),
    "card-huge": card_fields(
        "card-huge", "Gleemax", type_line="Legendary Artifact", mana_cost="{1000000}", cmc=1e6
    ),
}


def make_card(fields: dict[str, Any]) -> Card:
    """Build a ``Card`` schema from column values."""
    return Card(**fields)


def make_deck_card(
    card: Card, quantity: int = 1, *, sideboard: bool = False, commander: bool = False
) -> DeckCard:
    """Wrap a ``Card`` in a ``DeckCard`` association row."""
    return DeckCard(
        deck_id="deck-verify",
        card_id=card.id,
        quantity=quantity,
        sideboard=sideboard,
        commander=commander,
        card=card,
    )


def verify_deck_cards() -> list[DeckCard]:
    """Return the verify deck as ``DeckCard`` rows, sideboard row included."""
    return [
        make_deck_card(
            make_card(VERIFY_CARDS[card_id]), quantity, sideboard=sideboard, commander=commander
        )
        for card_id, quantity, sideboard, commander in VERIFY_ROWS
    ]


def verify_card_models() -> list[CardModel]:
    """Return the verify deck's cards as unsaved ``CardModel`` rows."""
    return [CardModel(**fields) for fields in VERIFY_CARDS.values()]


def expanded_mainboard(deck_cards: list[DeckCard]) -> list[Card]:
    """Expand the non-sideboard rows by quantity, the way ``analyze_mana_curve``'s tool does."""
    return [dc.card for dc in deck_cards if not dc.sideboard for _ in range(dc.quantity)]

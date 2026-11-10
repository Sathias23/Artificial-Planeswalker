"""Assessment-grade card rows and a deck builder, shared by the assess / compare / e2e suites.

The three suites each seeded the same commander candidates, combo partners and Game Changer
states through a private copy of one ``CardModel`` builder. Each suite keeps its own ``session``
fixture (their seeds differ: the assess suite adds DFC and planeswalker cards, the compare suite
leaves out the NULL Game Changer), and builds it from these.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.card import CardModel
from src.data.repositories.deck import DeckRepository


def assessment_card(
    card_id: str,
    name: str,
    *,
    type_line: str,
    cmc: float = 2.0,
    oracle_text: str = "Does a thing.",
    colors: list[str] | None = None,
    game_changer: bool | None = False,
) -> CardModel:
    """Build a CardModel legal in commander and standard, on every platform, with its own oracle id.

    ``game_changer`` defaults to ``False`` (confirmed not) so a seed never trips
    ``game_changer_data_unavailable`` unless a card opts in with ``None``.
    """
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
        mana_cost="{R}",
        cmc=cmc,
        type_line=type_line,
        oracle_text=oracle_text,
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=colors if colors is not None else ["R"],
        color_identity=colors if colors is not None else ["R"],
        legalities={"standard": "legal", "commander": "legal"},
        games=["paper", "arena", "mtgo"],
        game_changer=game_changer,
    )


def assessment_core_cards(prefix: str) -> list[CardModel]:
    """The core seed: a basic land, two legendary commanders, two spells and two Game Changers.

    Ids are ``{prefix}mountain``, ``{prefix}krenko``, ``{prefix}zada``, ``{prefix}goblin-guide``,
    ``{prefix}shock``, ``{prefix}gc-bolas`` and ``{prefix}gc-aura``. The two confirmed Game
    Changers come in reverse bytewise name order ("Bolas's Citadel" before "Aura Shards"), so a
    sorted-emission assertion cannot pass by insert-order accident.
    """
    return [
        assessment_card(
            f"{prefix}mountain",
            "Mountain",
            type_line="Basic Land — Mountain",
            cmc=0.0,
            oracle_text="{T}: Add {R}.",
            colors=[],
        ),
        assessment_card(
            f"{prefix}krenko",
            "Krenko, Mob Boss",
            type_line="Legendary Creature — Goblin",
            cmc=4.0,
        ),
        assessment_card(
            f"{prefix}zada",
            "Zada, Hedron Grinder",
            type_line="Legendary Creature — Goblin Ally",
            cmc=3.0,
        ),
        assessment_card(
            f"{prefix}goblin-guide",
            "Goblin Guide",
            type_line="Creature — Goblin Scout",
            cmc=1.0,
        ),
        assessment_card(f"{prefix}shock", "Shock", type_line="Instant", cmc=1.0),
        assessment_card(
            f"{prefix}gc-bolas",
            "Bolas's Citadel",
            type_line="Legendary Artifact",
            cmc=6.0,
            game_changer=True,
        ),
        assessment_card(
            f"{prefix}gc-aura",
            "Aura Shards",
            type_line="Enchantment",
            cmc=3.0,
            colors=["G", "W"],
            game_changer=True,
        ),
    ]


def null_game_changer_card(prefix: str) -> CardModel:
    """``{prefix}gc-null``, "Mystery Relic": a card whose Game Changer state is unknown (NULL)."""
    return assessment_card(
        f"{prefix}gc-null",
        "Mystery Relic",
        type_line="Artifact",
        cmc=2.0,
        game_changer=None,
    )


async def make_deck(
    session: AsyncSession,
    rows: list[tuple[str, int, bool, bool]],
    *,
    name: str = "Deck",
    format: str = "commander",
) -> str:
    """Create a deck and add ``(card_id, quantity, sideboard, commander)`` rows; return its id."""
    repo = DeckRepository(session)
    deck = await repo.create_deck(name=name, format=format)
    for card_id, quantity, sideboard, commander in rows:
        await repo.add_card_to_deck(deck.id, card_id, quantity, sideboard, commander)
    return deck.id

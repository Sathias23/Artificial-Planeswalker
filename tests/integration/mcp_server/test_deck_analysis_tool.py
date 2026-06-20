"""Integration tests for the deck-analysis helpers (Story 1.6, Task 5).

Exercises the three helpers (``analyze_mana_curve`` / ``detect_synergies`` /
``validate_deck``) directly against a seeded session, building decks via
``DeckRepository``. Covers each analysis path (curve distribution / expansion /
sideboard exclusion, tribal synergy detection, the whole-deck legality rules)
plus the graceful statuses (``deck_not_found`` / ``empty`` / ``invalid``). The
end-to-end MCP-client wiring is covered separately in test_mcp_tools.py.

Uses a file-backed engine and a single shared ``session`` fixture seeded with a
richer card set than the shared 3-card fixture, so each analysis branch is
reachable without editing the cross-story seed.
"""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.repositories.deck import DeckRepository
from src.mcp_server.tools.deck_analysis import (
    analyze_mana_curve,
    detect_synergies,
    validate_deck,
)


def _card(
    card_id: str,
    name: str,
    *,
    type_line: str,
    cmc: float,
    oracle_text: str = "Does a thing.",
    legalities: dict[str, str] | None = None,
    games: list[str] | None = None,
    colors: list[str] | None = None,
) -> CardModel:
    """Build a CardModel with a unique oracle_id (standard-legal, all platforms by default)."""
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
        legalities=legalities if legalities is not None else {"standard": "legal"},
        games=games if games is not None else ["paper", "arena", "mtgo"],
    )


def _seed_cards() -> list[CardModel]:
    """A richer card set exercising lands, a Goblin tribe, varied CMC, and edge legalities."""
    return [
        _card(
            "card-mountain",
            "Mountain",
            type_line="Basic Land — Mountain",
            cmc=0.0,
            oracle_text="{T}: Add {R}.",
            colors=[],
            games=["paper", "arena"],
        ),
        _card(
            "card-goblin-guide",
            "Goblin Guide",
            type_line="Creature — Goblin",
            cmc=1.0,
            oracle_text="Goblin Guide attacks each combat if able.",
        ),
        _card(
            "card-goblin-chieftain",
            "Goblin Chieftain",
            type_line="Creature — Goblin",
            cmc=3.0,
            oracle_text="Other Goblins you control get +1/+1 and have haste.",
        ),
        _card(
            "card-shock",
            "Shock",
            type_line="Instant",
            cmc=1.0,
            oracle_text="Shock deals 2 damage to any target.",
        ),
        _card(
            "card-divination",
            "Divination",
            type_line="Sorcery",
            cmc=3.0,
            oracle_text="Draw two cards.",
        ),
        _card(
            "card-dreadmaw",
            "Colossal Dreadmaw",
            type_line="Creature — Dinosaur",
            cmc=6.0,
            oracle_text="Trample",
        ),
        _card(
            "card-modern-staple",
            "Modern Staple",
            type_line="Instant",
            cmc=2.0,
            oracle_text="Counter target spell.",
            legalities={"modern": "legal"},
        ),
        _card(
            "card-paper-promo",
            "Paper Promo",
            type_line="Instant",
            cmc=2.0,
            oracle_text="Draw a card.",
            games=["paper"],
        ),
    ]


@pytest.fixture
async def session(tmp_path: Path):
    """File-backed engine + a single shared session, seeded with cards (no decks)."""
    db_path = tmp_path / "analysis.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        for card in _seed_cards():
            session.add(card)
        await session.commit()
        yield session
    await engine.dispose()


async def _make_deck(
    session: AsyncSession,
    cards: list[tuple[str, int, bool]],
    *,
    name: str = "Deck",
    format: str = "standard",
) -> str:
    """Create a deck via DeckRepository and add (card_id, quantity, sideboard) rows. Returns id."""
    repo = DeckRepository(session)
    deck = await repo.create_deck(name=name, format=format)
    for card_id, quantity, sideboard in cards:
        await repo.add_card_to_deck(deck.id, card_id, quantity, sideboard)
    return deck.id


# --- analyze_mana_curve (AC1, AC4) ---


async def test_analyze_mana_curve_ok(session: AsyncSession) -> None:
    """Curve analysis expands by quantity, excludes the sideboard, and reports the distribution."""
    deck_id = await _make_deck(
        session,
        [
            ("card-mountain", 4, False),
            ("card-shock", 4, False),
            ("card-divination", 2, False),
            ("card-dreadmaw", 3, True),  # sideboard — must be excluded
        ],
    )

    result = await analyze_mana_curve(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.total_lands == 4
    assert result.total_spells == 6  # 4 Shock + 2 Divination, expanded by quantity
    assert result.distribution == {1: 4, 3: 2}
    assert 6 not in result.distribution  # the CMC-6 sideboard card is excluded
    assert result.land_ratio == 40.0  # 4 lands / 10 mainboard cards
    assert result.average_cmc == pytest.approx((4 * 1 + 2 * 3) / 6)
    assert result.playable_cards_by_turn[1] == 4
    assert result.playable_cards_by_turn[3] == 6


async def test_analyze_mana_curve_deck_not_found(session: AsyncSession) -> None:
    """A bogus deck_id returns status='deck_not_found' (graceful)."""
    result = await analyze_mana_curve(session, deck_id="no-such-deck")

    assert result.status == "deck_not_found"
    assert result.deck_name is None


async def test_analyze_mana_curve_empty_mainboard(session: AsyncSession) -> None:
    """A deck with only sideboard cards has no mainboard to analyze -> status='empty'."""
    deck_id = await _make_deck(session, [("card-shock", 3, True)])

    result = await analyze_mana_curve(session, deck_id=deck_id)

    assert result.status == "empty"
    assert result.deck_name == "Deck"


# --- detect_synergies (AC2, AC4, AC6) ---


async def test_detect_synergies_tribal_goblins(session: AsyncSession) -> None:
    """A Goblin tribe with a tribal payoff yields a tribal SynergyPattern."""
    deck_id = await _make_deck(
        session,
        [
            ("card-goblin-guide", 4, False),
            ("card-goblin-chieftain", 4, False),
        ],
    )

    result = await detect_synergies(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.synergy_count >= 1
    tribal = [s for s in result.synergies if s.pattern_type == "tribal"]
    assert tribal, "expected a tribal synergy"
    goblin = next(s for s in tribal if s.subtype == "Goblin")
    assert {"Goblin Guide", "Goblin Chieftain"} <= set(goblin.affected_cards)
    assert all(isinstance(name, str) for name in goblin.affected_cards)


async def test_detect_synergies_no_full_card_leakage(session: AsyncSession) -> None:
    """The synergy result carries only names/strings — no full-Card or HTML blobs."""
    deck_id = await _make_deck(
        session,
        [
            ("card-goblin-guide", 4, False),
            ("card-goblin-chieftain", 4, False),
        ],
    )

    result = await detect_synergies(session, deck_id=deck_id)

    dumped = result.model_dump_json()
    assert "legalities" not in dumped
    assert "image_uris" not in dumped
    assert "oracle_text" not in dumped


async def test_detect_synergies_vanilla_deck_low_cohesion(session: AsyncSession) -> None:
    """A deck of unrelated spells detects no synergies and reports low cohesion."""
    deck_id = await _make_deck(
        session,
        [
            ("card-shock", 4, False),
            ("card-divination", 2, False),
        ],
    )

    result = await detect_synergies(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.synergies == []
    assert result.synergy_count == 0
    assert result.deck_cohesion == "low"


async def test_detect_synergies_deck_not_found(session: AsyncSession) -> None:
    """A bogus deck_id returns status='deck_not_found'."""
    result = await detect_synergies(session, deck_id="no-such-deck")

    assert result.status == "deck_not_found"


async def test_detect_synergies_empty_mainboard(session: AsyncSession) -> None:
    """A deck with only sideboard cards returns status='empty'."""
    deck_id = await _make_deck(session, [("card-goblin-guide", 4, True)])

    result = await detect_synergies(session, deck_id=deck_id)

    assert result.status == "empty"


# --- validate_deck (AC3, AC4, AC6) ---


async def test_validate_deck_legal_60_card_standard(session: AsyncSession) -> None:
    """A 60-card mainboard of standard-legal basics is legal with no violations."""
    deck_id = await _make_deck(session, [("card-mountain", 60, False)])

    result = await validate_deck(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.report is not None
    assert result.report.is_legal is True
    assert result.report.violations == []
    assert result.report.mainboard_count == 60


async def test_validate_deck_under_60_flags_min_deck_size(session: AsyncSession) -> None:
    """A mainboard under 60 cards is illegal with a min_deck_size violation."""
    deck_id = await _make_deck(session, [("card-shock", 4, False)])

    result = await validate_deck(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.report is not None
    assert result.report.is_legal is False
    assert any(v.rule == "min_deck_size" for v in result.report.violations)


async def test_validate_deck_five_copies_flags_copy_limit(session: AsyncSession) -> None:
    """Five copies of a non-basic card yields a copy_limit violation naming the card."""
    deck_id = await _make_deck(session, [("card-shock", 5, False)])

    result = await validate_deck(session, deck_id=deck_id)

    assert result.report is not None
    copy_violations = [v for v in result.report.violations if v.rule == "copy_limit"]
    assert len(copy_violations) == 1
    assert copy_violations[0].card_name == "Shock"


async def test_validate_deck_format_legality_and_param_is_stateless(
    session: AsyncSession,
) -> None:
    """A modern-only card fails standard legality but passes when format='modern' (no state)."""
    deck_id = await _make_deck(session, [("card-modern-staple", 4, False)])

    standard = await validate_deck(session, deck_id=deck_id, format="standard")
    modern = await validate_deck(session, deck_id=deck_id, format="modern")

    assert standard.report is not None
    assert any(
        v.rule == "format_legality" and v.card_name == "Modern Staple"
        for v in standard.report.violations
    )
    # format is a real per-call parameter — the same deck is legal-by-legality in modern.
    assert modern.report is not None
    assert modern.report.format == "modern"
    assert not any(v.rule == "format_legality" for v in modern.report.violations)


async def test_validate_deck_game_availability(session: AsyncSession) -> None:
    """games=['arena'] flags a paper-only card with a game_availability violation."""
    deck_id = await _make_deck(session, [("card-paper-promo", 4, False)])

    result = await validate_deck(session, deck_id=deck_id, games=["arena"])

    assert result.status == "ok"
    assert result.report is not None
    assert any(
        v.rule == "game_availability" and v.card_name == "Paper Promo"
        for v in result.report.violations
    )


async def test_validate_deck_invalid_games_value(session: AsyncSession) -> None:
    """A games value outside {paper, arena, mtgo} returns status='invalid' (no DB load)."""
    deck_id = await _make_deck(session, [("card-shock", 4, False)])

    result = await validate_deck(session, deck_id=deck_id, games=["xbox"])

    assert result.status == "invalid"
    assert result.report is None
    assert "xbox" in result.message


async def test_validate_deck_deck_not_found(session: AsyncSession) -> None:
    """A bogus deck_id returns status='deck_not_found'."""
    result = await validate_deck(session, deck_id="no-such-deck")

    assert result.status == "deck_not_found"
    assert result.report is None

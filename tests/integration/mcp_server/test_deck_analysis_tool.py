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
from sqlalchemy.exc import DatabaseError
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
        _card(
            "card-brawl-goblin",
            "Brawl Goblin",
            type_line="Creature — Goblin",
            cmc=2.0,
            oracle_text="Haste",
            legalities={"brawl": "legal", "standardbrawl": "legal", "standard": "legal"},
        ),
        _card(
            "card-snow-forest",
            "Snow-Covered Forest",
            type_line="Basic Snow Land — Forest",
            cmc=0.0,
            oracle_text="({T}: Add {G}.)",
            colors=[],
            legalities={"standard": "legal", "vintage": "legal"},
        ),
        _card(
            "card-black-lotus",
            "Black Lotus",
            type_line="Artifact",
            cmc=0.0,
            oracle_text="{T}, Sacrifice Black Lotus: Add three mana of any one color.",
            colors=[],
            legalities={"vintage": "restricted", "legacy": "banned", "standard": "not_legal"},
        ),
        _card(
            "card-wastes",
            "Wastes",
            type_line="Basic Land",
            cmc=0.0,
            oracle_text="{T}: Add {C}.",
            colors=[],
            legalities={"commander": "legal", "standard": "legal"},
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


async def test_validate_deck_brawl_flags_singleton(session: AsyncSession) -> None:
    """format='brawl': a doubled non-basic (across boards) yields a singleton violation."""
    deck_id = await _make_deck(
        session,
        [
            ("card-brawl-goblin", 1, False),
            ("card-brawl-goblin", 1, True),  # 2 combined across both boards
        ],
        format="brawl",
    )

    result = await validate_deck(session, deck_id=deck_id, format="brawl")

    assert result.status == "ok"
    assert result.report is not None
    assert result.report.is_legal is False
    singleton = [v for v in result.report.violations if v.rule == "singleton"]
    assert len(singleton) == 1
    assert singleton[0].card_name == "Brawl Goblin"
    assert not any(v.rule == "copy_limit" for v in result.report.violations)
    # The brawl-legal card must NOT be flagged format_legality (lowercase key resolved).
    assert not any(v.rule == "format_legality" for v in result.report.violations)


async def test_validate_deck_format_is_case_insensitive(session: AsyncSession) -> None:
    """format=' BRAWL ' behaves exactly as 'brawl' (trimmed + lowercased at the tool layer)."""
    deck_id = await _make_deck(
        session,
        [
            ("card-brawl-goblin", 1, False),
            ("card-brawl-goblin", 1, True),
        ],
        format="brawl",
    )

    result = await validate_deck(session, deck_id=deck_id, format=" BRAWL ")

    assert result.status == "ok"
    assert result.report is not None
    assert result.report.format == "brawl"  # echoes the normalized key
    assert any(
        v.rule == "singleton" and v.card_name == "Brawl Goblin" for v in result.report.violations
    )
    # No spurious all-cards format_legality flags from a wrong-case key.
    assert not any(v.rule == "format_legality" for v in result.report.violations)


# --- snow basics and restricted cards (quality story 7.1: M2 / B4-P1 / B4-D1) ---


async def test_validate_deck_ten_snow_basics_are_legal(session: AsyncSession) -> None:
    """Ten Snow-Covered Forests in a 60-card Standard deck break no copy limit."""
    deck_id = await _make_deck(
        session, [("card-mountain", 50, False), ("card-snow-forest", 10, False)]
    )

    result = await validate_deck(session, deck_id=deck_id, format="standard")

    assert result.status == "ok"
    assert result.report is not None
    assert result.report.violations == []
    assert result.report.is_legal is True


async def test_validate_deck_one_restricted_copy_is_legal_in_vintage(
    session: AsyncSession,
) -> None:
    """One Black Lotus in Vintage is legal: restricted means one copy, not "not legal"."""
    deck_id = await _make_deck(
        session,
        [("card-snow-forest", 59, False), ("card-black-lotus", 1, False)],
        format="vintage",
    )

    result = await validate_deck(session, deck_id=deck_id, format="vintage")

    assert result.status == "ok"
    assert result.report is not None
    assert result.report.violations == []
    assert result.report.is_legal is True


async def test_validate_deck_two_restricted_copies_are_one_violation(
    session: AsyncSession,
) -> None:
    """1 main + 1 side Black Lotus in Vintage is exactly one ``restricted_card`` violation."""
    deck_id = await _make_deck(
        session,
        [
            ("card-snow-forest", 59, False),
            ("card-black-lotus", 1, False),
            ("card-black-lotus", 1, True),
        ],
        format="vintage",
    )

    result = await validate_deck(session, deck_id=deck_id, format="vintage")

    assert result.report is not None
    assert result.report.is_legal is False
    assert [(v.rule, v.card_name, v.detail) for v in result.report.violations] == [
        (
            "restricted_card",
            "Black Lotus",
            "2 copies of 'Black Lotus'; it is restricted in vintage (max 1 copy).",
        )
    ]


# --- visible legality coverage (quick wins ticket 4): what was NOT checked ---
#
# Every verdict and violation list below is the PRE-CHANGE expectation: ``unchecked`` is
# reporting only, so the rules that ran must answer exactly as they did before it existed.


async def test_validate_deck_commander_lists_the_unchecked_rules(session: AsyncSession) -> None:
    """A 100-card Commander deck is legal, and says size, commander and identity went unchecked."""
    deck_id = await _make_deck(session, [("card-wastes", 100, False)], format="commander")

    result = await validate_deck(session, deck_id=deck_id, format="commander")

    assert result.status == "ok"
    assert result.report is not None
    assert result.report.is_legal is True
    assert result.report.violations == []
    assert [rule.rule for rule in result.report.unchecked] == [
        "deck_size",
        "sideboard_size",
        "commander_eligibility",
        "color_identity",
        "copy_exceptions",
    ]
    assert all("commander" in rule.detail for rule in result.report.unchecked)
    assert result.message == (
        "Deck is legal in commander (100-card mainboard). Not checked: deck size, "
        "sideboard size, commander eligibility, color identity, copy exceptions."
    )


async def test_validate_deck_commander_violations_are_unchanged(session: AsyncSession) -> None:
    """The list does not touch the verdict: a broken Commander deck reports the same two faults."""
    deck_id = await _make_deck(
        session,
        [("card-wastes", 98, False), ("card-brawl-goblin", 2, False)],
        format="commander",
    )

    result = await validate_deck(session, deck_id=deck_id, format="commander")

    assert result.report is not None
    assert result.report.is_legal is False
    assert [(v.rule, v.card_name, v.detail) for v in result.report.violations] == [
        (
            "singleton",
            "Brawl Goblin",
            "2 copies of 'Brawl Goblin'; commander is a singleton format "
            "(max 1 copy of any non-basic card).",
        ),
        ("format_legality", "Brawl Goblin", "'Brawl Goblin' is not legal in commander."),
    ]
    assert result.message == (
        "Deck has 2 issues for commander legality. Not checked: deck size, "
        "sideboard size, commander eligibility, color identity, copy exceptions."
    )


async def test_validate_deck_vintage_lists_no_restricted_rule(session: AsyncSession) -> None:
    """Restricted cards are checked in Vintage, so only copy exceptions go unchecked."""
    deck_id = await _make_deck(
        session,
        [("card-snow-forest", 59, False), ("card-black-lotus", 1, False)],
        format="vintage",
    )

    result = await validate_deck(session, deck_id=deck_id, format="vintage")

    assert result.report is not None
    assert result.report.is_legal is True
    assert result.report.violations == []
    assert [rule.rule for rule in result.report.unchecked] == ["copy_exceptions"]
    assert not any("restricted" in rule.detail for rule in result.report.unchecked)


async def test_validate_deck_standard_lists_rotation_and_copy_exceptions(
    session: AsyncSession,
) -> None:
    """Standard reports nothing beyond rotation and copy exceptions."""
    deck_id = await _make_deck(session, [("card-mountain", 60, False)])

    result = await validate_deck(session, deck_id=deck_id, format="standard")

    assert result.report is not None
    assert result.report.is_legal is True
    assert result.report.violations == []
    assert [rule.rule for rule in result.report.unchecked] == ["rotation", "copy_exceptions"]
    assert result.message == (
        "Deck is legal in standard (60-card mainboard). Not checked: rotation exposure, "
        "copy exceptions."
    )


async def test_validate_deck_unknown_format_lists_nothing(session: AsyncSession) -> None:
    """An unknown format's own violation says what was skipped; the list and message add nothing."""
    deck_id = await _make_deck(session, [("card-mountain", 60, False)])

    result = await validate_deck(session, deck_id=deck_id, format="potato")

    assert result.report is not None
    assert result.report.is_legal is False
    assert [(v.rule, v.detail) for v in result.report.violations] == [
        (
            "unknown_format",
            "'potato' is not a recognized format; per-card legality was not checked.",
        )
    ]
    assert result.report.unchecked == []
    assert result.message == "Deck has 1 issue for potato legality."


# --- the DatabaseError arm of each helper ---


@pytest.mark.parametrize(
    ("helper", "message"),
    [
        (analyze_mana_curve, "A database error occurred analyzing the deck's mana curve."),
        (detect_synergies, "A database error occurred detecting deck synergies."),
        (validate_deck, "A database error occurred validating the deck."),
    ],
    ids=["analyze_mana_curve", "detect_synergies", "validate_deck"],
)
async def test_a_database_error_loading_the_deck_is_status_error(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, helper, message: str
) -> None:
    """A ``DatabaseError`` from the deck load is the helper's own ``error``, never a raise.

    Patched where the compare suite patches it (``DeckRepository.get_deck_with_cards``); the
    recorded call proves the planted failure was reached rather than short-circuited, and the
    exact message proves it was this helper's arm that answered.
    """
    deck_id = await _make_deck(session, [("card-shock", 4, False)])
    calls: list[str] = []

    async def boom(self: DeckRepository, deck_id: str) -> object:
        calls.append(deck_id)
        raise DatabaseError("SELECT deck", None, Exception("database is locked"))

    monkeypatch.setattr(DeckRepository, "get_deck_with_cards", boom)

    result = await helper(session, deck_id=deck_id)

    assert calls == [deck_id]
    assert result.status == "error"
    assert result.deck_id == deck_id
    assert result.message == message

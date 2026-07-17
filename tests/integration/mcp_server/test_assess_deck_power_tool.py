"""Integration tests for the assess_deck_power helper (Stories 7.1/7.2/7.3).

Exercises the tool directly against a seeded session: the format-resolution
ladder (explicit param → stored ``Deck.format`` → commander flag structural
signal → ``unsupported_format``), AD-13 commander resolution (flagged →
sole-legendary inference → unidentified, plus the degenerate flag states),
mainboard-only filtering, the graceful statuses (``deck_not_found`` /
``database_not_initialized``), the 7.2 combo-provisioning/degradation matrix,
and the 7.3 output contract — the fixed-shape AD-7 ``assessment`` block,
AD-8-deterministic serialization (byte-identical repeat calls, pre-sorted
lists, no call-time clock), and the summary projection (bucket-split combo
counts, Bracket-floor phrasing, the multiplayer-variance caveat). The
end-to-end MCP-client wiring is covered separately in test_mcp_tools.py.

Uses a file-backed engine and a single shared ``session`` fixture seeded with
legendary / non-legendary / DFC / planeswalker cards so every resolution branch
is reachable without editing the cross-story seed.
"""

import dataclasses
import logging
from pathlib import Path

import pytest
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.models.combo import ComboSnapshotMetaModel
from src.data.repositories.deck import DeckRepository
from src.logic.assessment import (
    CARDS_UNRESOLVED,
    COMBO_DATA_UNAVAILABLE,
    COMMANDER_UNIDENTIFIED,
    CONFIDENCE_REASON_TOKENS,
    GAME_CHANGER_DATA_UNAVAILABLE,
    STANDARD_PROFILE,
    TIER_LABELS,
)
from src.mcp_server.tools.assess_deck_power import (
    _FORMAT_PROFILES,
    MULTIPLAYER_VARIANCE_CAVEAT,
    Assessment,
    AssessmentFlags,
    AssessmentVector,
    Confidence,
    DataVintage,
    _build_summary,
    _derive_confidence,
    _is_legendary_creature,
    _provision_combos,
    _resolve_format,
    assess_deck_power,
)
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE
from tests.fixtures.combo_snapshot import (
    seed_snapshot as _seed_snapshot,
)
from tests.fixtures.combo_snapshot import (
    snapshot_variant as _snapshot_variant,
)


def _card(
    card_id: str,
    name: str,
    *,
    type_line: str,
    cmc: float = 2.0,
    oracle_text: str = "Does a thing.",
    colors: list[str] | None = None,
    game_changer: bool | None = False,
) -> CardModel:
    """Build a CardModel with a unique oracle_id (standard-legal, all platforms).

    ``game_changer`` defaults to ``False`` (confirmed not) so the shared seed never
    trips ``game_changer_data_unavailable``; the NULL fixture opts in explicitly.
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


def _seed_cards() -> list[CardModel]:
    """Cards exercising every commander-resolution branch."""
    return [
        _card(
            "card-mountain",
            "Mountain",
            type_line="Basic Land — Mountain",
            cmc=0.0,
            oracle_text="{T}: Add {R}.",
            colors=[],
        ),
        _card(
            "card-krenko",
            "Krenko, Mob Boss",
            type_line="Legendary Creature — Goblin",
            cmc=4.0,
        ),
        _card(
            "card-zada",
            "Zada, Hedron Grinder",
            type_line="Legendary Creature — Goblin Ally",
            cmc=3.0,
        ),
        _card(
            "card-goblin-guide",
            "Goblin Guide",
            type_line="Creature — Goblin Scout",
            cmc=1.0,
        ),
        _card(
            "card-shock",
            "Shock",
            type_line="Instant",
            cmc=1.0,
        ),
        _card(
            "card-dfc-front-legend",
            "Hero of the Hunt // Rampage",
            type_line="Legendary Creature — Human // Instant",
            cmc=3.0,
        ),
        _card(
            "card-dfc-back-legend",
            "Quiet Study // Ancient Spirit",
            type_line="Instant // Legendary Creature — Spirit",
            cmc=2.0,
        ),
        _card(
            "card-chandra",
            "Chandra, Torch of Defiance",
            type_line="Legendary Planeswalker — Chandra",
            cmc=4.0,
        ),
        _card(
            "card-gc-null",
            "Mystery Relic",
            type_line="Artifact",
            cmc=2.0,
            game_changer=None,  # unknown state — the AD-4 unknown_count fixture
        ),
        # Two confirmed Game Changers whose names are deliberately out of seed order
        # bytewise ("Aura Shards" < "Bolas's Citadel") — the flags.game_changers
        # sorted-emission fixtures (Story 7.3).
        _card(
            "card-gc-bolas",
            "Bolas's Citadel",
            type_line="Legendary Artifact",
            cmc=6.0,
            game_changer=True,
        ),
        _card(
            "card-gc-aura",
            "Aura Shards",
            type_line="Enchantment",
            cmc=3.0,
            colors=["G", "W"],
            game_changer=True,
        ),
    ]


@pytest.fixture
async def session(tmp_path: Path):
    """File-backed engine + a single shared session, seeded with cards (no decks)."""
    db_path = tmp_path / "assess.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        for card in _seed_cards():
            session.add(card)
        await session.commit()
        yield session
    await engine.dispose()


@pytest.fixture
async def uninitialized_session(tmp_path: Path):
    """A session against a DB where init_database has never run (no tables at all)."""
    db_path = tmp_path / "uninitialized.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _make_deck(
    session: AsyncSession,
    rows: list[tuple[str, int, bool, bool]],
    *,
    name: str = "Deck",
    format: str = "commander",
) -> str:
    """Create a deck and add (card_id, quantity, sideboard, commander) rows. Returns id."""
    repo = DeckRepository(session)
    deck = await repo.create_deck(name=name, format=format)
    for card_id, quantity, sideboard, commander in rows:
        await repo.add_card_to_deck(deck.id, card_id, quantity, sideboard, commander)
    return deck.id


# --- format-resolution ladder (AC 3) ---


async def test_explicit_format_beats_stored(session: AsyncSession) -> None:
    """An explicit format param overrides the stored Deck.format."""
    deck_id = await _make_deck(session, [("card-krenko", 1, False, True)], format="standard")

    result = await assess_deck_power(session, deck_id=deck_id, format="commander")

    assert result.status == "ok"
    assert "commander-v4" in result.summary


async def test_explicit_format_is_normalized(session: AsyncSession) -> None:
    """The explicit param is stripped and lowercased before the map lookup."""
    deck_id = await _make_deck(session, [("card-shock", 4, False, False)], format="commander")

    result = await assess_deck_power(session, deck_id=deck_id, format="  Standard \n")

    assert result.status == "ok"
    assert "standard-v4" in result.summary


async def test_explicit_unsupported_format_short_circuits_before_db(
    session: AsyncSession,
) -> None:
    """A bad explicit format returns unsupported_format even for a bogus deck_id."""
    result = await assess_deck_power(session, deck_id="bogus-deck", format="modern")

    assert result.status == "unsupported_format"
    assert result.assessment is None
    assert "Supported formats: commander, standard" in result.summary
    assert 'format="commander"' in result.summary


async def test_stored_commander_format_resolves(session: AsyncSession) -> None:
    """Stored Deck.format='commander' selects the Commander profile."""
    deck_id = await _make_deck(session, [("card-krenko", 1, False, False)], format="commander")

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "commander-v4" in result.summary


async def test_stored_format_is_normalized(session: AsyncSession) -> None:
    """The stored free-text format is stripped/lowercased before the map lookup."""
    deck_id = await _make_deck(session, [("card-shock", 4, False, False)], format=" COMMANDER ")

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "commander-v4" in result.summary


@pytest.mark.parametrize("stored", ["brawl", "standardbrawl", "historic", "no-such-format"])
async def test_stored_unsupported_format_is_graceful(session: AsyncSession, stored: str) -> None:
    """Brawl-family and unknown stored formats return unsupported_format, never a crash."""
    deck_id = await _make_deck(session, [("card-shock", 4, False, False)], format=stored)

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "unsupported_format"
    assert result.deck_id == deck_id
    assert result.assessment is None
    assert "Supported formats: commander, standard" in result.summary
    assert 'format="commander"' in result.summary


async def test_commander_flag_signal_resolves_brawl_deck(session: AsyncSession) -> None:
    """A flagged mainboard commander resolves an otherwise-unsupported stored format."""
    deck_id = await _make_deck(session, [("card-krenko", 1, False, True)], format="brawl")

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "commander-v4" in result.summary


async def test_stored_standard_beats_flag_signal(session: AsyncSession) -> None:
    """The stored format outranks the structural commander-flag signal in the ladder."""
    deck_id = await _make_deck(session, [("card-krenko", 1, False, True)], format="standard")

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "standard-v4" in result.summary


def test_resolve_format_ladder_pure() -> None:
    """The pure ladder handles every rung, including stored None (unreachable via ORM)."""
    assert _resolve_format(None, None, has_flagged_commander=False) is None
    assert _resolve_format(None, None, has_flagged_commander=True) == "commander"
    assert _resolve_format(None, "commander", has_flagged_commander=False) == "commander"
    assert _resolve_format(None, " Standard ", has_flagged_commander=False) == "standard"
    assert _resolve_format(None, "brawl", has_flagged_commander=False) is None
    # The explicit param wins outright — an unsupported value never falls through.
    assert _resolve_format("modern", "commander", has_flagged_commander=True) is None
    assert _resolve_format("commander", "standard", has_flagged_commander=False) == "commander"
    # Whitespace-only explicit param counts as omitted.
    assert _resolve_format("   ", "standard", has_flagged_commander=False) == "standard"


# --- commander resolution (AC 6) ---


async def test_flagged_single_commander(session: AsyncSession) -> None:
    """One flagged mainboard row resolves as the commander, name verbatim."""
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, True), ("card-shock", 4, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "Krenko, Mob Boss" in result.summary
    assert "flagged" in result.summary


async def test_flagged_partner_commanders(session: AsyncSession) -> None:
    """Two flagged mainboard rows resolve as partner commanders."""
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, True), ("card-zada", 1, False, True)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "Krenko, Mob Boss" in result.summary
    assert "Zada, Hedron Grinder" in result.summary
    assert "flagged" in result.summary


async def test_more_than_two_flagged_is_unidentified(
    session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    """>2 flagged rows resolve honestly to unidentified with a warning, never a subset."""
    deck_id = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, True),
            ("card-zada", 1, False, True),
            ("card-dfc-front-legend", 1, False, True),
        ],
    )

    with caplog.at_level(logging.WARNING, logger="src.mcp_server.tools.assess_deck_power"):
        result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "unidentified" in result.summary
    assert "Krenko" not in result.summary
    assert any("flagged" in record.message for record in caplog.records)


async def test_sideboard_flag_ignored_when_mainboard_flagged(session: AsyncSession) -> None:
    """Sideboard-flagged rows are never commanders; the mainboard flag stands alone."""
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, True), ("card-zada", 1, True, True)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "Krenko, Mob Boss" in result.summary
    assert "Zada" not in result.summary


async def test_sideboard_only_flags_are_unidentified(
    session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    """Flags only in the sideboard resolve to unidentified (no inference), with a warning."""
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, False), ("card-zada", 1, True, True)],
    )

    with caplog.at_level(logging.WARNING, logger="src.mcp_server.tools.assess_deck_power"):
        result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "unidentified" in result.summary
    # The sole mainboard legendary must NOT be inferred over the degenerate flag state.
    assert "inferred" not in result.summary
    assert any("sideboard" in record.message for record in caplog.records)


async def test_sole_legendary_is_inferred(session: AsyncSession) -> None:
    """With no flags in a commander deck, a sole legendary creature is inferred, no penalty."""
    deck_id = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, False),
            ("card-goblin-guide", 4, False, False),
            ("card-mountain", 20, False, False),
        ],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "Krenko, Mob Boss" in result.summary
    assert "inferred" in result.summary


async def test_sole_legendary_multiple_copies_still_infers(session: AsyncSession) -> None:
    """Distinctness is by name: multiple copies of one legendary still infer."""
    deck_id = await _make_deck(session, [("card-krenko", 2, False, False)])

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "Krenko, Mob Boss" in result.summary
    assert "inferred" in result.summary


async def test_multiple_distinct_legendaries_unidentified(session: AsyncSession) -> None:
    """Two distinct unflagged legendary creatures cannot be disambiguated — unidentified."""
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, False), ("card-zada", 1, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "unidentified" in result.summary


async def test_no_legendary_unidentified(session: AsyncSession) -> None:
    """No flags and no legendary creature resolves to unidentified."""
    deck_id = await _make_deck(
        session,
        [("card-goblin-guide", 4, False, False), ("card-shock", 4, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "unidentified" in result.summary


async def test_standard_format_never_infers(session: AsyncSession) -> None:
    """Sole-legendary inference is Commander-only: a standard deck never infers."""
    deck_id = await _make_deck(session, [("card-krenko", 1, False, False)], format="standard")

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "unidentified" in result.summary
    assert "inferred" not in result.summary


async def test_dfc_front_face_legendary_is_inferred(session: AsyncSession) -> None:
    """A DFC whose FRONT face is a legendary creature infers with the full stored name."""
    deck_id = await _make_deck(
        session,
        [("card-dfc-front-legend", 1, False, False), ("card-shock", 4, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "Hero of the Hunt // Rampage" in result.summary
    assert "inferred" in result.summary


async def test_dfc_back_face_legendary_not_inferred(session: AsyncSession) -> None:
    """A back-face-only legendary creature is not castable from the command zone — no inference."""
    deck_id = await _make_deck(
        session,
        [("card-dfc-back-legend", 1, False, False), ("card-shock", 4, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "unidentified" in result.summary


async def test_legendary_planeswalker_not_inferred(session: AsyncSession) -> None:
    """FR25 scopes inference to legendary creatures — planeswalkers degrade honestly."""
    deck_id = await _make_deck(
        session,
        [("card-chandra", 1, False, False), ("card-shock", 4, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "unidentified" in result.summary


def test_is_legendary_creature_pure() -> None:
    """The legendary-creature check: case-insensitive, front face only for DFCs."""
    assert _is_legendary_creature("Legendary Creature — Goblin")
    assert _is_legendary_creature("LEGENDARY CREATURE — GOBLIN")
    assert _is_legendary_creature("Legendary Enchantment Creature — God")
    assert _is_legendary_creature("Legendary Creature — Human // Instant")
    assert not _is_legendary_creature("Creature — Goblin")
    assert not _is_legendary_creature("Legendary Planeswalker — Chandra")
    assert not _is_legendary_creature("Instant // Legendary Creature — Spirit")
    assert not _is_legendary_creature("")


# --- mainboard-only filtering + resolution counts (AC 2, 5, 7) ---


async def test_summary_counts_mainboard_only(session: AsyncSession) -> None:
    """The ok summary reports quantity-expanded mainboard cards and 0 unresolved."""
    deck_id = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, True),
            ("card-goblin-guide", 3, False, False),
            ("card-shock", 2, True, False),  # sideboard — must be excluded
        ],
        name="Krenko Aggro",
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.deck_id == deck_id
    assert "Krenko Aggro" in result.summary
    assert "4 mainboard cards" in result.summary
    assert "0 unresolved" in result.summary


# --- graceful statuses (AC 4) ---


async def test_deck_not_found(session: AsyncSession) -> None:
    """A bogus deck_id returns status='deck_not_found' with the id echoed."""
    result = await assess_deck_power(session, deck_id="no-such-deck")

    assert result.status == "deck_not_found"
    assert result.deck_id == "no-such-deck"
    assert result.schema_version == "1"
    assert result.assessment is None
    assert "no-such-deck" in result.summary


async def test_database_not_initialized(uninitialized_session: AsyncSession) -> None:
    """An un-imported database returns the graceful first-run status, not an error."""
    result = await assess_deck_power(uninitialized_session, deck_id="any-deck")

    assert result.status == "database_not_initialized"
    assert result.schema_version == "1"
    assert result.assessment is None
    assert result.summary == DATABASE_NOT_INITIALIZED_MESSAGE


async def test_ok_result_carries_schema_version_and_assessment(
    session: AsyncSession,
) -> None:
    """AD-7: schema_version is always present; the ok path populates the assessment block."""
    deck_id = await _make_deck(session, [("card-krenko", 1, False, True)])

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.schema_version == "1"
    assert result.assessment is not None
    # The 7.1/7.2 provisional pointer sentence is gone (AC 4).
    assert "7.3" not in result.summary


# --- pure confidence ladder (Story 7.2, AC 4/5) ---


@pytest.mark.parametrize("unresolved_count", [0, 1])
@pytest.mark.parametrize("combo_data_unavailable", [False, True])
@pytest.mark.parametrize("gc_unknown_count", [0, 1])
@pytest.mark.parametrize("commander_unidentified", [False, True])
def test_derive_confidence_full_matrix(
    unresolved_count: int,
    combo_data_unavailable: bool,
    gc_unknown_count: int,
    commander_unidentified: bool,
) -> None:
    """All 16 fact combinations: token presence, bytewise sort, 0/1/≥2 level mapping."""
    level, reasons = _derive_confidence(
        unresolved_count=unresolved_count,
        combo_data_unavailable=combo_data_unavailable,
        gc_unknown_count=gc_unknown_count,
        commander_unidentified=commander_unidentified,
    )

    expected_reasons = tuple(
        token
        for token, active in (
            (CARDS_UNRESOLVED, unresolved_count > 0),
            (COMBO_DATA_UNAVAILABLE, combo_data_unavailable),
            (COMMANDER_UNIDENTIFIED, commander_unidentified),
            (GAME_CHANGER_DATA_UNAVAILABLE, gc_unknown_count > 0),
        )
        if active
    )
    assert reasons == expected_reasons
    # AD-8: emitted bytewise-sorted; every token from the closed enum only.
    assert list(reasons) == sorted(reasons)
    assert set(reasons) <= set(CONFIDENCE_REASON_TOKENS)

    expected_level = "high" if len(reasons) == 0 else "medium" if len(reasons) == 1 else "low"
    assert level == expected_level


def test_derive_confidence_reasons_follow_token_tuple_order() -> None:
    """The all-degradations case emits exactly CONFIDENCE_REASON_TOKENS (already sorted)."""
    level, reasons = _derive_confidence(
        unresolved_count=3,
        combo_data_unavailable=True,
        gc_unknown_count=2,
        commander_unidentified=True,
    )

    assert reasons == CONFIDENCE_REASON_TOKENS
    assert level == "low"


def test_derive_confidence_counts_never_embed_in_tokens() -> None:
    """Tokens are count-free: a large count changes nothing but presence (AD-6)."""
    _, reasons_one = _derive_confidence(
        unresolved_count=1,
        combo_data_unavailable=False,
        gc_unknown_count=0,
        commander_unidentified=False,
    )
    _, reasons_many = _derive_confidence(
        unresolved_count=99,
        combo_data_unavailable=False,
        gc_unknown_count=0,
        commander_unidentified=False,
    )

    assert reasons_one == reasons_many == (CARDS_UNRESOLVED,)


# --- combo provisioning + degradation matrix (Story 7.2, AC 1/2/3/6) ---


async def test_absent_snapshot_degrades_and_still_scores(session: AsyncSession) -> None:
    """Empty snapshot tables → combo_data_unavailable + medium confidence, scored ok (AC 2)."""
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, True), ("card-goblin-guide", 4, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "/100" in result.summary  # scoring proceeded despite the degradation
    assert COMBO_DATA_UNAVAILABLE in result.summary
    assert "confidence medium" in result.summary


async def test_seeded_snapshot_matched_combo_no_token(session: AsyncSession) -> None:
    """A healthy snapshot with an included combo surfaces the match and no token (AC 1/3)."""
    await _seed_snapshot(
        session,
        [_snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])],
    )
    deck_id = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, True),
            ("card-zada", 1, False, False),
            ("card-goblin-guide", 4, False, False),
        ],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "1 combo variant" in result.summary
    assert COMBO_DATA_UNAVAILABLE not in result.summary
    assert "confidence high" in result.summary
    assert "no degradations" in result.summary


async def test_zero_overlap_healthy_snapshot_no_token(session: AsyncSession) -> None:
    """A healthy snapshot with zero overlapping variants is NOT a degradation (AC 2, G-R2)."""
    await _seed_snapshot(
        session,
        [_snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
    )
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, True), ("card-goblin-guide", 4, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "0 combo variants" in result.summary
    assert COMBO_DATA_UNAVAILABLE not in result.summary
    assert "confidence high" in result.summary


async def test_provisioning_database_error_returns_error_status(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DatabaseError from combo provisioning is caught → status='error', never uncaught.

    The new snapshot reads run outside the deck-load try/except and the repo swallows
    only OperationalError, so a sibling DatabaseError would otherwise escape to the
    client — 7.1's DB-failure contract (AC 6 / NFR3) must hold on the new path too.
    """
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, True), ("card-goblin-guide", 4, False, False)],
    )

    async def _boom(*_args: object, **_kwargs: object) -> object:
        raise DatabaseError("SELECT combo", None, Exception("database is locked"))

    monkeypatch.setattr("src.mcp_server.tools.assess_deck_power._provision_combos", _boom)

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "error"
    assert result.deck_id == deck_id
    assert "database error" in result.summary.lower()


async def test_combos_disabled_profile_skips_repo_and_token(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """combos_enabled=False skips provisioning entirely: no repo read, no token (AC 1).

    The snapshot is ABSENT here — a token would fire if the availability probe ran, so
    its absence proves the gate short-circuits before the probe (AD-6: a profile choice
    is not a run-specific degradation).
    """
    disabled = dataclasses.replace(STANDARD_PROFILE, combos_enabled=False)
    monkeypatch.setitem(_FORMAT_PROFILES, "standard", disabled)
    deck_id = await _make_deck(session, [("card-shock", 4, False, False)], format="standard")

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert COMBO_DATA_UNAVAILABLE not in result.summary
    assert "confidence high" in result.summary


async def test_combos_disabled_never_constructs_repo(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The disabled gate short-circuits before ComboSnapshotRepository is even built (AC 1)."""

    def _explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("ComboSnapshotRepository must not be constructed when disabled")

    monkeypatch.setattr("src.mcp_server.tools.assess_deck_power.ComboSnapshotRepository", _explode)
    disabled = dataclasses.replace(STANDARD_PROFILE, combos_enabled=False)

    variants, vintage, unavailable = await _provision_combos(session, (), disabled)

    assert variants == ()
    assert vintage is None
    assert unavailable is False


async def test_commander_unidentified_token_fires_for_commander_format(
    session: AsyncSession,
) -> None:
    """A Commander deck with an unidentified commander carries the token (AC 4)."""
    await _seed_snapshot(
        session,
        [_snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
    )
    # Two distinct unflagged legendaries → unidentified.
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, False), ("card-zada", 1, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert COMMANDER_UNIDENTIFIED in result.summary
    assert "confidence medium" in result.summary


async def test_standard_deck_never_carries_commander_unidentified(
    session: AsyncSession,
) -> None:
    """Standard resolves unidentified by construction — no token, no penalty (AC 4)."""
    await _seed_snapshot(
        session,
        [_snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
    )
    deck_id = await _make_deck(session, [("card-shock", 4, False, False)], format="standard")

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert COMMANDER_UNIDENTIFIED not in result.summary
    assert "confidence high" in result.summary
    assert "no degradations" in result.summary


async def test_null_game_changer_card_degrades(session: AsyncSession) -> None:
    """A game_changer=None card fires game_changer_data_unavailable via unknown_count (AC 4)."""
    await _seed_snapshot(
        session,
        [_snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
    )
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, True), ("card-gc-null", 1, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert GAME_CHANGER_DATA_UNAVAILABLE in result.summary
    assert "confidence medium" in result.summary


async def test_multi_degradation_is_low_with_sorted_reasons(session: AsyncSession) -> None:
    """Absent snapshot + unidentified commander + NULL gc → low, sorted reasons (AC 4/5)."""
    # No snapshot seeded; commander deck with no flags and no sole legendary.
    deck_id = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, False),
            ("card-zada", 1, False, False),
            ("card-gc-null", 1, False, False),
        ],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "confidence low" in result.summary
    # The three active tokens must appear in bytewise order (AD-8).
    expected = ", ".join(
        [COMBO_DATA_UNAVAILABLE, COMMANDER_UNIDENTIFIED, GAME_CHANGER_DATA_UNAVAILABLE]
    )
    assert expected in result.summary


async def test_empty_mainboard_deck_scores_without_crash(session: AsyncSession) -> None:
    """An all-sideboard deck still returns a scored ok result — score() is zero-safe (AC 3/6)."""
    deck_id = await _make_deck(session, [("card-shock", 4, True, False)])

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert "0 mainboard cards" in result.summary
    assert "/100" in result.summary


# --- assessment block: shape, determinism & summary projection (Story 7.3) ---

#: The AD-7 key orders — declaration order IS emission order (AC 2).
_ASSESSMENT_KEYS = [
    "format",
    "vector",
    "for_format_score",
    "tier",
    "bracket",
    "data_vintage",
    "confidence",
    "flags",
]
_VECTOR_KEYS = [
    "speed",
    "consistency",
    "resilience",
    "interaction",
    "mana_efficiency",
    "card_advantage",
    "combo_potential",
]
_VINTAGE_KEYS = [
    "combo_snapshot_imported_at",
    "combo_snapshot_export_version",
    "format_profile_version",
]
_FLAGS_KEYS = [
    "game_changers",
    "combos",
    "structural_gaps",
    "mass_land_denial",
    "extra_turn_chains",
    "cedh_candidate",
]


async def test_ok_assessment_populated_with_full_shape(session: AsyncSession) -> None:
    """The ok path fills the full AD-7 assessment block from the seam (AC 1/2)."""
    await _seed_snapshot(
        session,
        [_snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])],
    )
    deck_id = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, True),
            ("card-zada", 1, False, False),
            ("card-goblin-guide", 4, False, False),
            ("card-mountain", 20, False, False),
        ],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    a = result.assessment
    assert a is not None
    assert a.format == "commander"
    assert list(a.model_dump()) == _ASSESSMENT_KEYS
    vector = a.vector.model_dump()
    assert list(vector) == _VECTOR_KEYS
    assert all(isinstance(v, int) and 0 <= v <= 100 for v in vector.values())
    assert isinstance(a.for_format_score, int) and 0 <= a.for_format_score <= 100
    assert a.tier in TIER_LABELS
    assert a.bracket in {2, 3, 4}  # Commander always computes a floor
    assert list(a.data_vintage.model_dump()) == _VINTAGE_KEYS
    assert a.data_vintage.combo_snapshot_imported_at == "2026-07-16T09:07:00+00:00"
    assert a.data_vintage.combo_snapshot_export_version == "5.6.0"
    assert a.data_vintage.format_profile_version == "commander-v4"
    assert a.confidence.level == "high"
    assert a.confidence.reasons == ()
    assert list(a.flags.model_dump()) == _FLAGS_KEYS
    assert [c.spellbook_id for c in a.flags.combos] == ["1-1"]
    assert a.flags.combos[0].bucket == "included"
    assert isinstance(a.flags.mass_land_denial, bool)
    assert isinstance(a.flags.extra_turn_chains, bool)
    assert isinstance(a.flags.cedh_candidate, bool)


async def test_every_non_ok_status_keeps_assessment_none(
    session: AsyncSession,
    uninitialized_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All four non-ok statuses keep assessment=None — construction sites unchanged (AC 1)."""
    not_found = await assess_deck_power(session, deck_id="no-such-deck")
    assert not_found.status == "deck_not_found"
    assert not_found.assessment is None

    unsupported = await assess_deck_power(session, deck_id="whatever", format="modern")
    assert unsupported.status == "unsupported_format"
    assert unsupported.assessment is None

    uninitialized = await assess_deck_power(uninitialized_session, deck_id="any-deck")
    assert uninitialized.status == "database_not_initialized"
    assert uninitialized.assessment is None

    deck_id = await _make_deck(session, [("card-krenko", 1, False, True)])

    async def _boom(*_args: object, **_kwargs: object) -> object:
        raise DatabaseError("SELECT combo", None, Exception("database is locked"))

    monkeypatch.setattr("src.mcp_server.tools.assess_deck_power._provision_combos", _boom)
    error = await assess_deck_power(session, deck_id=deck_id)
    assert error.status == "error"
    assert error.assessment is None


async def test_shape_parity_commander_vs_standard(session: AsyncSession) -> None:
    """Fixed closed shape: identical key sets for both formats, no conditional keys (AC 2)."""
    await _seed_snapshot(
        session,
        [_snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
    )
    commander_id = await _make_deck(
        session,
        [("card-krenko", 1, False, True), ("card-goblin-guide", 4, False, False)],
    )
    standard_id = await _make_deck(
        session,
        [("card-shock", 4, False, False), ("card-mountain", 20, False, False)],
        format="standard",
    )

    commander_result = await assess_deck_power(session, deck_id=commander_id)
    standard_result = await assess_deck_power(session, deck_id=standard_id)

    assert commander_result.assessment is not None
    assert standard_result.assessment is not None
    c, s = commander_result.assessment.model_dump(), standard_result.assessment.model_dump()
    assert list(c) == list(s) == _ASSESSMENT_KEYS
    assert list(c["vector"]) == list(s["vector"]) == _VECTOR_KEYS
    assert list(c["data_vintage"]) == list(s["data_vintage"]) == _VINTAGE_KEYS
    assert list(c["flags"]) == list(s["flags"]) == _FLAGS_KEYS
    assert list(c["confidence"]) == list(s["confidence"]) == ["level", "reasons"]
    # Standard: bracket null + candidacy False — fixed shape, never a missing key.
    assert s["format"] == "standard"
    assert s["bracket"] is None
    assert s["flags"]["cedh_candidate"] is False
    assert s["data_vintage"]["format_profile_version"] == "standard-v4"
    assert commander_result.assessment.bracket in {2, 3, 4}


async def test_data_vintage_null_keys_when_snapshot_absent(session: AsyncSession) -> None:
    """Absent snapshot → both combo vintage keys present with None values (decide-once #2)."""
    deck_id = await _make_deck(session, [("card-krenko", 1, False, True)])

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.assessment is not None
    vintage = result.assessment.data_vintage.model_dump()
    assert vintage == {
        "combo_snapshot_imported_at": None,
        "combo_snapshot_export_version": None,
        "format_profile_version": "commander-v4",
    }
    # The degradation token fired, and the null vintage keys are still present.
    assert COMBO_DATA_UNAVAILABLE in result.assessment.confidence.reasons


async def test_data_vintage_survives_meta_without_variants(session: AsyncSession) -> None:
    """Meta row present but zero variants: token fires AND vintage passes through verbatim.

    The reason token and the vintage are independent facts (decide-once #2) — a
    degraded run must not blank the stored metadata it did find.
    """
    session.add(
        ComboSnapshotMetaModel(
            imported_at="2026-07-16T09:07:00+00:00",
            export_timestamp="2026-07-16T07:28:23+00:00",
            export_version="5.6.0",
            variant_count=0,
        )
    )
    await session.commit()
    deck_id = await _make_deck(session, [("card-krenko", 1, False, True)])

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.assessment is not None
    assert COMBO_DATA_UNAVAILABLE in result.assessment.confidence.reasons
    vintage = result.assessment.data_vintage
    assert vintage.combo_snapshot_imported_at == "2026-07-16T09:07:00+00:00"
    assert vintage.combo_snapshot_export_version == "5.6.0"


async def test_two_calls_serialize_byte_identically(session: AsyncSession) -> None:
    """Same deck + card snapshot + combo snapshot → byte-identical JSON (AC 3, AD-8/NFR1)."""
    await _seed_snapshot(
        session,
        [
            _snapshot_variant("2-2", ["Krenko, Mob Boss", "Zada, Hedron Grinder"]),
            _snapshot_variant("1-1", ["Zada, Hedron Grinder", "Goblin Guide"]),
        ],
    )
    deck_id = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, True),
            ("card-zada", 1, False, False),
            ("card-goblin-guide", 4, False, False),
            ("card-gc-bolas", 1, False, False),
            ("card-gc-aura", 1, False, False),
            ("card-gc-null", 1, False, False),
            ("card-mountain", 20, False, False),
        ],
    )

    result_a = await assess_deck_power(session, deck_id=deck_id)
    result_b = await assess_deck_power(session, deck_id=deck_id)

    assert result_a.status == result_b.status == "ok"
    # String equality, not dict equality — dict equality would mask unstable ordering.
    assert result_a.model_dump_json() == result_b.model_dump_json()


async def test_lists_are_emitted_sorted(session: AsyncSession) -> None:
    """reasons/gaps/game_changers bytewise ascending; combos by spellbook_id (AC 3)."""
    await _seed_snapshot(
        session,
        [
            _snapshot_variant("2-2", ["Krenko, Mob Boss", "Zada, Hedron Grinder"]),
            _snapshot_variant("1-1", ["Zada, Hedron Grinder", "Goblin Guide"]),
        ],
    )
    # Unidentified commander (two unflagged legendaries) + a NULL-GC card → two
    # degradation reasons; GC cards seeded in reverse-sorted deck order.
    deck_id = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, False),
            ("card-zada", 1, False, False),
            ("card-goblin-guide", 4, False, False),
            ("card-gc-bolas", 1, False, False),
            ("card-gc-aura", 1, False, False),
            ("card-gc-null", 1, False, False),
        ],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    a = result.assessment
    assert a is not None
    assert list(a.confidence.reasons) == sorted(a.confidence.reasons)
    assert len(a.confidence.reasons) >= 2
    assert list(a.flags.structural_gaps) == sorted(a.flags.structural_gaps)
    assert a.flags.game_changers == ("Aura Shards", "Bolas's Citadel")
    assert [c.spellbook_id for c in a.flags.combos] == ["1-1", "2-2"]
    for combo in a.flags.combos:
        assert list(combo.cards) == sorted(combo.cards)
        assert list(combo.produces) == sorted(combo.produces)


async def test_serialized_result_embeds_no_clock(session: AsyncSession) -> None:
    """No call-time timestamp anywhere in the result — 'as of' lives in data_vintage only (AC 3)."""
    await _seed_snapshot(
        session,
        [_snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])],
    )
    deck_id = await _make_deck(session, [("card-krenko", 1, False, True)])

    result = await assess_deck_power(session, deck_id=deck_id)

    dump = result.model_dump_json()
    assert "assessed_at" not in dump
    # The only timestamp-typed content is the verbatim stored vintage string.
    assert dump.count("2026-07-16T09:07:00+00:00") == 1


async def test_summary_projects_commander_facts_and_caveat(session: AsyncSession) -> None:
    """Commander summary: profile version, N/100 (tier), Bracket floor, buckets, caveat (AC 4-6)."""
    await _seed_snapshot(
        session,
        [
            _snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"]),
            _snapshot_variant("7-7", ["Zada, Hedron Grinder", "Chandra, Torch of Defiance"]),
        ],
    )
    deck_id = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, True),
            ("card-zada", 1, False, False),
            ("card-gc-aura", 1, False, False),
        ],
        name="Krenko Combo",
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    a = result.assessment
    assert a is not None
    summary = result.summary
    assert "Krenko Combo" in summary
    assert "commander-v4" in summary
    assert f"{a.for_format_score}/100 ({a.tier})" in summary
    assert f"Bracket {a.bracket} floor" in summary
    # Bucket-split counts: 1-1 is fully included; 7-7 is one card away (Chandra absent).
    assert "1 combo variant included" in summary
    assert "1 combo variant one card away" in summary
    assert "1 Game Changer" in summary
    assert "confidence high" in summary
    assert "no degradations" in summary
    assert summary.endswith(MULTIPLAYER_VARIANCE_CAVEAT)


async def test_summary_standard_omits_bracket_and_caveat(session: AsyncSession) -> None:
    """Standard summary: no Bracket sentence, no multiplayer caveat (AC 4/6)."""
    deck_id = await _make_deck(
        session,
        [("card-shock", 4, False, False), ("card-mountain", 20, False, False)],
        format="standard",
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    a = result.assessment
    assert a is not None
    summary = result.summary
    assert "standard-v4" in summary
    assert f"{a.for_format_score}/100 ({a.tier})" in summary
    assert "Bracket" not in summary
    assert MULTIPLAYER_VARIANCE_CAVEAT not in summary


async def test_almost_included_never_reads_as_matched(session: AsyncSession) -> None:
    """A shortfall-1 variant is reported one-card-away, never included/matched (AC 5)."""
    await _seed_snapshot(
        session,
        [_snapshot_variant("7-7", ["Zada, Hedron Grinder", "Chandra, Torch of Defiance"])],
    )
    deck_id = await _make_deck(
        session,
        [("card-krenko", 1, False, True), ("card-zada", 1, False, False)],
    )

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    a = result.assessment
    assert a is not None
    assert [c.bucket for c in a.flags.combos] == ["almost_included"]
    assert "0 combo variants included" in result.summary
    assert "1 combo variant one card away" in result.summary
    assert "matched" not in result.summary


# --- the pure summary builder: branches unreachable via fixtures (Story 7.3) ---


def _assessment(**overrides: object) -> Assessment:
    """A hand-built Assessment for exercising summary branches directly."""
    fields: dict[str, object] = {
        "format": "commander",
        "vector": AssessmentVector(
            speed=50,
            consistency=50,
            resilience=50,
            interaction=50,
            mana_efficiency=50,
            card_advantage=50,
            combo_potential=50,
        ),
        "for_format_score": 71,
        "tier": "High-Power",
        "bracket": 4,
        "data_vintage": DataVintage(
            combo_snapshot_imported_at="2026-07-16T09:07:00+00:00",
            combo_snapshot_export_version="5.6.0",
            format_profile_version="commander-v4",
        ),
        "confidence": Confidence(level="high", reasons=()),
        "flags": AssessmentFlags(
            game_changers=(),
            combos=(),
            structural_gaps=(),
            mass_land_denial=False,
            extra_turn_chains=False,
            cedh_candidate=False,
        ),
    }
    fields.update(overrides)
    return Assessment(**fields)  # type: ignore[arg-type]


def test_build_summary_cedh_candidate_is_candidacy_never_bracket_5() -> None:
    """cedh_candidate=True reads as candidacy; Bracket 5 is never asserted (FR18)."""
    flags = AssessmentFlags(
        game_changers=(),
        combos=(),
        structural_gaps=(),
        mass_land_denial=False,
        extra_turn_chains=False,
        cedh_candidate=True,
    )
    summary = _build_summary(
        _assessment(flags=flags),
        deck_name="Turbo Naus",
        commander_text="commander K'rrik, Son of Yawgmoth (flagged)",
        mainboard_total=99,
        unresolved_count=0,
        multiplayer_variance_caveat=True,
    )

    assert "cEDH candidate" in summary
    assert "Bracket 5" not in summary
    assert "Bracket 4 floor" in summary
    assert summary.endswith(MULTIPLAYER_VARIANCE_CAVEAT)


def test_build_summary_structural_gaps_and_reasons_are_listed() -> None:
    """The summary surfaces the exact gap tokens and sorted reasons (AC 4/NFR2)."""
    flags = AssessmentFlags(
        game_changers=("Aura Shards", "Bolas's Citadel"),
        combos=(),
        structural_gaps=("card_draw_below_baseline", "wincon_missing"),
        mass_land_denial=False,
        extra_turn_chains=False,
        cedh_candidate=False,
    )
    confidence = Confidence(level="low", reasons=(COMBO_DATA_UNAVAILABLE, COMMANDER_UNIDENTIFIED))
    summary = _build_summary(
        _assessment(flags=flags, confidence=confidence),
        deck_name="Gappy",
        commander_text="commander unidentified",
        mainboard_total=60,
        unresolved_count=0,
        multiplayer_variance_caveat=False,
    )

    assert "card_draw_below_baseline, wincon_missing" in summary
    assert "2 Game Changers" in summary
    assert (
        f"confidence low (reasons: {COMBO_DATA_UNAVAILABLE}, {COMMANDER_UNIDENTIFIED})" in summary
    )
    assert MULTIPLAYER_VARIANCE_CAVEAT not in summary


def test_build_summary_bracket_none_has_no_bracket_fragment() -> None:
    """bracket=None (Standard) drops the Bracket fragment from the prose (AC 4)."""
    summary = _build_summary(
        _assessment(format="standard", bracket=None),
        deck_name="Mono Red",
        commander_text="commander unidentified",
        mainboard_total=60,
        unresolved_count=0,
        multiplayer_variance_caveat=False,
    )

    assert "Bracket" not in summary
    assert "71/100 (High-Power)" in summary

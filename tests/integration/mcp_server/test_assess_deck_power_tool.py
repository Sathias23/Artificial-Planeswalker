"""Integration tests for the assess_deck_power helper (Story 7.1).

Exercises the ingest/resolve slice directly against a seeded session: the
format-resolution ladder (explicit param → stored ``Deck.format`` → commander
flag structural signal → ``unsupported_format``), AD-13 commander resolution
(flagged → sole-legendary inference → unidentified, plus the degenerate flag
states), mainboard-only filtering, and the graceful statuses
(``deck_not_found`` / ``database_not_initialized``). The end-to-end MCP-client
wiring is covered separately in test_mcp_tools.py.

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
from src.data.models.combo import (
    ComboSnapshotMetaModel,
    ComboVariantModel,
    ComboVariantPieceModel,
)
from src.data.repositories.deck import DeckRepository
from src.data.schemas.combo import name_keys
from src.logic.assessment import (
    CARDS_UNRESOLVED,
    COMBO_DATA_UNAVAILABLE,
    COMMANDER_UNIDENTIFIED,
    CONFIDENCE_REASON_TOKENS,
    GAME_CHANGER_DATA_UNAVAILABLE,
    STANDARD_PROFILE,
)
from src.mcp_server.tools.assess_deck_power import (
    _FORMAT_PROFILES,
    _derive_confidence,
    _is_legendary_creature,
    _provision_combos,
    _resolve_format,
    assess_deck_power,
)
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE


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


async def test_ok_result_carries_schema_version_and_null_assessment(
    session: AsyncSession,
) -> None:
    """AD-7 subset: schema_version is always present; assessment stays None until 7.3."""
    deck_id = await _make_deck(session, [("card-krenko", 1, False, True)])

    result = await assess_deck_power(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.schema_version == "1"
    assert result.assessment is None
    assert "7.3" in result.summary or "pending" in result.summary


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


def _snapshot_variant(
    spellbook_id: str,
    cards: list[str],
    *,
    commander_required: bool = False,
    bracket_tag: str = "POWERFUL",
) -> tuple[ComboVariantModel, list[ComboVariantPieceModel]]:
    """One variant row + its piece-index rows (the 6.3 test-suite seeding pattern)."""
    variant = ComboVariantModel(
        spellbook_id=spellbook_id,
        commander_required=commander_required,
        bracket_tag=bracket_tag,
        popularity=None,
    )
    variant.cards_list = cards
    variant.produces_list = ["Infinite value"]
    keys = {key for name in cards for key in name_keys(name)}
    pieces = [
        ComboVariantPieceModel(spellbook_id=spellbook_id, name_key=key) for key in sorted(keys)
    ]
    return variant, pieces


async def _seed_snapshot(
    session: AsyncSession,
    variants: list[tuple[ComboVariantModel, list[ComboVariantPieceModel]]],
) -> None:
    """Seed the meta row + the supplied variants — a healthy, available snapshot."""
    session.add(
        ComboSnapshotMetaModel(
            imported_at="2026-07-16T09:07:00+00:00",
            export_timestamp="2026-07-16T07:28:23+00:00",
            export_version="5.6.0",
            variant_count=len(variants),
        )
    )
    for variant, pieces in variants:
        session.add(variant)
        session.add_all(pieces)
    await session.commit()


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

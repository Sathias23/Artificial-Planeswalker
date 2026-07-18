"""Integration tests for the compare_deck_power helper (Story 7.5).

Exercises the result-model contract (fixed AD-7 shape, closed status Literal,
frozen blocks, AD-8 ``model_dump_json()`` byte determinism) and the helper
against a seeded session: ok-path delta arithmetic (field-wise subtraction
equality against two direct ``assess_deck_power`` calls), self-compare
all-zero, each failure side (`a` fails / `b` fails / both /
``database_not_initialized``), ``format_mismatch`` + explicit-``format``
forcing, and sorted diff lists. The end-to-end MCP-client wiring is covered
separately in test_mcp_tools.py.

Mirrors test_assess_deck_power_tool.py: a file-backed engine and a single
shared ``session`` fixture seeded with the cards both suites need.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.repositories.deck import DeckRepository
from src.mcp_server.tools.assess_deck_power import (
    AssessDeckPowerResult,
    Confidence,
    DataVintage,
    assess_deck_power,
)
from src.mcp_server.tools.compare_deck_power import (
    COMPARE_SCHEMA_VERSION,
    ComboBucketChange,
    CompareDeckPowerResult,
    Comparison,
    VectorDelta,
    compare_deck_power,
)
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE
from tests.fixtures.combo_snapshot import (
    seed_snapshot as _seed_snapshot,
)
from tests.fixtures.combo_snapshot import (
    snapshot_variant as _snapshot_variant,
)

# --- model-contract fixtures (Story 7.5 Task 1) ---


def _vector_delta(**overrides: int) -> VectorDelta:
    """An all-zero VectorDelta with per-field overrides."""
    values: dict[str, int] = {
        "speed": 0,
        "consistency": 0,
        "resilience": 0,
        "interaction": 0,
        "mana_efficiency": 0,
        "card_advantage": 0,
        "combo_potential": 0,
    }
    values.update(overrides)
    return VectorDelta(**values)


def _data_vintage() -> DataVintage:
    return DataVintage(
        combo_snapshot_imported_at="2026-07-16T09:07:00+00:00",
        combo_snapshot_export_version="5.6.0",
        format_profile_version="commander-v4",
    )


def _confidence() -> Confidence:
    return Confidence(level="high", reasons=())


def _comparison(**overrides: object) -> Comparison:
    """A fully-populated commander Comparison; overrides replace named fields."""
    values: dict[str, object] = {
        "format": "commander",
        "vector_delta": _vector_delta(),
        "for_format_score_delta": 12,
        "for_format_score_a": 43,
        "for_format_score_b": 55,
        "tier_a": "Focused",
        "tier_b": "Tuned",
        "bracket_a": 2,
        "bracket_b": 3,
        "game_changers_added": ("Bolas's Citadel",),
        "game_changers_removed": (),
        "structural_gaps_added": (),
        "structural_gaps_removed": (),
        "combos_added": (),
        "combos_removed": (),
        "combos_bucket_changed": (
            ComboBucketChange(spellbook_id="1-1", bucket_a="almost_included", bucket_b="included"),
        ),
        "mass_land_denial_a": False,
        "mass_land_denial_b": False,
        "extra_turn_chains_a": False,
        "extra_turn_chains_b": False,
        "cedh_candidate_a": False,
        "cedh_candidate_b": False,
        "data_vintage_a": _data_vintage(),
        "data_vintage_b": _data_vintage(),
        "confidence_a": _confidence(),
        "confidence_b": _confidence(),
    }
    values.update(overrides)
    return Comparison(**values)  # type: ignore[arg-type]


class TestCompareResultModels:
    """The AD-7-sibling result contract: fixed shape, closed enums, frozen blocks."""

    def test_schema_version_constant_and_default(self):
        """COMPARE_SCHEMA_VERSION is "1" and the result defaults to it (AC 3)."""
        assert COMPARE_SCHEMA_VERSION == "1"
        result = CompareDeckPowerResult(
            status="deck_a_failed", summary="x", deck_id_a="a", deck_id_b="b"
        )
        assert result.schema_version == "1"
        assert result.comparison is None

    def test_status_literal_is_closed(self):
        """An out-of-vocabulary status raises — the Literal is closed (AC 3)."""
        with pytest.raises(ValidationError):
            CompareDeckPowerResult(
                status="partial",  # type: ignore[arg-type]
                summary="x",
                deck_id_a="a",
                deck_id_b="b",
            )

    def test_full_status_vocabulary_constructs(self):
        """Every decide-once #1 status token is accepted (AC 3/4)."""
        for status in (
            "ok",
            "deck_a_failed",
            "deck_b_failed",
            "both_decks_failed",
            "format_mismatch",
            "database_not_initialized",
            "error",
        ):
            result = CompareDeckPowerResult(
                status=status,  # type: ignore[arg-type]
                summary="x",
                deck_id_a="a",
                deck_id_b="b",
            )
            assert result.status == status

    def test_comparison_blocks_are_frozen(self):
        """VectorDelta / ComboBucketChange / Comparison reject mutation (AC 3)."""
        comparison = _comparison()
        with pytest.raises(ValidationError):
            comparison.for_format_score_delta = 99  # type: ignore[misc]
        with pytest.raises(ValidationError):
            comparison.vector_delta.speed = 1  # type: ignore[misc]
        change = comparison.combos_bucket_changed[0]
        with pytest.raises(ValidationError):
            change.bucket_b = "almost_included"  # type: ignore[misc]

    def test_bracket_literal_is_closed(self):
        """bracket_a/_b admit only 2/3/4/None — never 5 (FR18, AC 3)."""
        with pytest.raises(ValidationError):
            _comparison(bracket_b=5)
        assert _comparison(bracket_a=None, bracket_b=None).bracket_a is None

    def test_comparison_emission_order_is_declaration_order(self):
        """The wire key order is the fixed AC-3 declaration order (AD-8)."""
        dumped = _comparison().model_dump()
        assert list(dumped) == [
            "format",
            "vector_delta",
            "for_format_score_delta",
            "for_format_score_a",
            "for_format_score_b",
            "tier_a",
            "tier_b",
            "bracket_a",
            "bracket_b",
            "game_changers_added",
            "game_changers_removed",
            "structural_gaps_added",
            "structural_gaps_removed",
            "combos_added",
            "combos_removed",
            "combos_bucket_changed",
            "mass_land_denial_a",
            "mass_land_denial_b",
            "extra_turn_chains_a",
            "extra_turn_chains_b",
            "cedh_candidate_a",
            "cedh_candidate_b",
            "data_vintage_a",
            "data_vintage_b",
            "confidence_a",
            "confidence_b",
        ]
        assert list(dumped["vector_delta"]) == [
            "speed",
            "consistency",
            "resilience",
            "interaction",
            "mana_efficiency",
            "card_advantage",
            "combo_potential",
        ]

    def test_result_emission_order_is_declaration_order(self):
        """Top-level key order: status, schema_version, summary, ids, comparison."""
        result = CompareDeckPowerResult(
            status="ok",
            summary="x",
            deck_id_a="a",
            deck_id_b="b",
            comparison=_comparison(),
        )
        assert list(result.model_dump()) == [
            "status",
            "schema_version",
            "summary",
            "deck_id_a",
            "deck_id_b",
            "comparison",
        ]

    def test_model_dump_json_byte_determinism(self):
        """Two identically-built results serialize byte-identically (AC 6, AD-8)."""

        def build() -> CompareDeckPowerResult:
            return CompareDeckPowerResult(
                status="ok",
                summary="deterministic",
                deck_id_a="a",
                deck_id_b="b",
                comparison=_comparison(),
            )

        assert build().model_dump_json() == build().model_dump_json()


# --- helper-level fixtures (mirroring test_assess_deck_power_tool.py) ---


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
    """Build a CardModel with a unique oracle_id (commander+standard legal).

    ``game_changer`` defaults to ``False`` (confirmed not) so the seed never
    trips ``game_changer_data_unavailable`` — compare tests want clean
    high-confidence sides unless a scenario opts in.
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
    """Compare-grade seed: commander candidates, combo partners, reverse-order GCs."""
    return [
        _card(
            "card-mountain",
            "Mountain",
            type_line="Basic Land — Mountain",
            cmc=0.0,
            oracle_text="{T}: Add {R}.",
            colors=[],
        ),
        _card("card-krenko", "Krenko, Mob Boss", type_line="Legendary Creature — Goblin", cmc=4.0),
        _card(
            "card-zada",
            "Zada, Hedron Grinder",
            type_line="Legendary Creature — Goblin Ally",
            cmc=3.0,
        ),
        _card("card-goblin-guide", "Goblin Guide", type_line="Creature — Goblin Scout", cmc=1.0),
        _card("card-shock", "Shock", type_line="Instant", cmc=1.0),
        # Two confirmed Game Changers seeded in reverse bytewise name order
        # ("Bolas's Citadel" enters decks before "Aura Shards") so sorted-emission
        # assertions on game_changers_added cannot pass by insert-order accident.
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
    db_path = tmp_path / "compare.db"
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


_BASE_ROWS: list[tuple[str, int, bool, bool]] = [
    ("card-krenko", 1, False, True),
    ("card-goblin-guide", 4, False, False),
    ("card-shock", 4, False, False),
    ("card-mountain", 20, False, False),
]


# --- ok-path delta arithmetic (AC 2/3/7) ---


async def test_ok_deltas_equal_direct_subtraction(session: AsyncSession) -> None:
    """Every delta equals field-wise subtraction of two direct assess calls (AC 2).

    The no-second-scoring-path proof: whatever the composed pipeline scores,
    compare's numbers must be exactly ``b − a`` over the two Assessment blocks
    — with the endpoints, tiers, brackets, vintage, and confidence carried
    verbatim.
    """
    await _seed_snapshot(
        session, [_snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])]
    )
    deck_a = await _make_deck(session, _BASE_ROWS, name="Baseline")
    deck_b = await _make_deck(
        session,
        [*_BASE_ROWS, ("card-zada", 1, False, False), ("card-gc-bolas", 1, False, False)],
        name="Candidate",
    )

    direct_a = await assess_deck_power(session, deck_id=deck_a)
    direct_b = await assess_deck_power(session, deck_id=deck_b)
    assert direct_a.status == direct_b.status == "ok"
    a = direct_a.assessment
    b = direct_b.assessment
    assert a is not None and b is not None

    result = await compare_deck_power(session, deck_id_a=deck_a, deck_id_b=deck_b)

    assert result.status == "ok"
    assert result.schema_version == COMPARE_SCHEMA_VERSION
    assert result.deck_id_a == deck_a
    assert result.deck_id_b == deck_b
    comparison = result.comparison
    assert comparison is not None
    assert comparison.format == a.format == b.format
    for key in (
        "speed",
        "consistency",
        "resilience",
        "interaction",
        "mana_efficiency",
        "card_advantage",
        "combo_potential",
    ):
        assert getattr(comparison.vector_delta, key) == getattr(b.vector, key) - getattr(
            a.vector, key
        )
    assert comparison.for_format_score_delta == b.for_format_score - a.for_format_score
    assert comparison.for_format_score_a == a.for_format_score
    assert comparison.for_format_score_b == b.for_format_score
    assert comparison.tier_a == a.tier
    assert comparison.tier_b == b.tier
    assert comparison.bracket_a == a.bracket
    assert comparison.bracket_b == b.bracket
    # Pass-through blocks verbatim — never recomputed (AC 6).
    assert comparison.data_vintage_a == a.data_vintage
    assert comparison.data_vintage_b == b.data_vintage
    assert comparison.confidence_a == a.confidence
    assert comparison.confidence_b == b.confidence
    assert comparison.mass_land_denial_a == a.flags.mass_land_denial
    assert comparison.mass_land_denial_b == b.flags.mass_land_denial
    assert comparison.extra_turn_chains_a == a.flags.extra_turn_chains
    assert comparison.extra_turn_chains_b == b.flags.extra_turn_chains
    assert comparison.cedh_candidate_a == a.flags.cedh_candidate
    assert comparison.cedh_candidate_b == b.flags.cedh_candidate
    # The seeded scenario: one GC added, the 2-card variant completed by Zada.
    assert comparison.game_changers_added == ("Bolas's Citadel",)
    assert comparison.game_changers_removed == ()
    assert comparison.bracket_a == 2  # almost_included combos never lift the floor
    # Completing the 2-card variant makes it an included two_card_infinite — the
    # FR15 hard trigger floors deck_b at 4, outranking the 1-GC floor of 3.
    assert comparison.bracket_b == 4
    assert comparison.combos_bucket_changed == (
        ComboBucketChange(spellbook_id="1-1", bucket_a="almost_included", bucket_b="included"),
    )
    assert comparison.vector_delta.combo_potential > 0


async def test_self_compare_all_zero(session: AsyncSession) -> None:
    """deck_id_a == deck_id_b is legal: all-zero deltas, empty diff lists (AC 6)."""
    await _seed_snapshot(
        session, [_snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])]
    )
    deck_id = await _make_deck(session, _BASE_ROWS, name="Selfsame")

    result = await compare_deck_power(session, deck_id_a=f"  {deck_id} ", deck_id_b=deck_id)

    assert result.status == "ok"
    assert result.deck_id_a == deck_id  # ids are stripped before use
    assert result.deck_id_b == deck_id
    comparison = result.comparison
    assert comparison is not None
    assert comparison.vector_delta == VectorDelta(
        speed=0,
        consistency=0,
        resilience=0,
        interaction=0,
        mana_efficiency=0,
        card_advantage=0,
        combo_potential=0,
    )
    assert comparison.for_format_score_delta == 0
    assert comparison.for_format_score_a == comparison.for_format_score_b
    assert comparison.tier_a == comparison.tier_b
    assert comparison.bracket_a == comparison.bracket_b
    assert comparison.game_changers_added == ()
    assert comparison.game_changers_removed == ()
    assert comparison.structural_gaps_added == ()
    assert comparison.structural_gaps_removed == ()
    assert comparison.combos_added == ()
    assert comparison.combos_removed == ()
    assert comparison.combos_bucket_changed == ()
    assert comparison.data_vintage_a == comparison.data_vintage_b
    assert comparison.confidence_a == comparison.confidence_b


# --- graceful failure, side named (AC 4/7) ---


async def test_deck_a_failed_names_side_and_token(session: AsyncSession) -> None:
    """A bogus deck_id_a yields deck_a_failed naming the id and the assess token."""
    deck_b = await _make_deck(session, _BASE_ROWS, name="Healthy B")

    result = await compare_deck_power(session, deck_id_a="bogus-a", deck_id_b=deck_b)

    assert result.status == "deck_a_failed"
    assert result.comparison is None
    assert "'bogus-a'" in result.summary
    assert "deck_not_found" in result.summary


async def test_deck_b_failed_names_side_and_token(session: AsyncSession) -> None:
    """A bogus deck_id_b yields deck_b_failed naming the id and the assess token."""
    deck_a = await _make_deck(session, _BASE_ROWS, name="Healthy A")

    result = await compare_deck_power(session, deck_id_a=deck_a, deck_id_b="bogus-b")

    assert result.status == "deck_b_failed"
    assert result.comparison is None
    assert "'bogus-b'" in result.summary
    assert "deck_not_found" in result.summary


async def test_both_decks_failed_names_both_tokens(session: AsyncSession) -> None:
    """Both sides failing yields both_decks_failed naming each id and token."""
    result = await compare_deck_power(session, deck_id_a="bogus-a", deck_id_b="bogus-b")

    assert result.status == "both_decks_failed"
    assert result.comparison is None
    assert "'bogus-a'" in result.summary
    assert "'bogus-b'" in result.summary
    assert "deck_not_found" in result.summary


async def test_both_decks_failed_names_distinct_tokens(session: AsyncSession) -> None:
    """Asymmetric per-side failures each render distinctly in the summary (AC 4).

    Guards the ``both_decks_failed`` summary interpolation against a bug that
    renders only one branch: a bogus ``deck_id_a`` (``deck_not_found``) paired
    with a deck whose stored format resolves unsupported (``unsupported_format``
    — ``format`` omitted so each side resolves its own, and no flagged commander
    so ``modern`` never falls through to the commander signal) must surface BOTH
    tokens, not a single shared one.
    """
    no_commander_rows: list[tuple[str, int, bool, bool]] = [
        ("card-goblin-guide", 4, False, False),
        ("card-shock", 4, False, False),
        ("card-mountain", 20, False, False),
    ]
    deck_b = await _make_deck(session, no_commander_rows, name="Modern B", format="modern")

    result = await compare_deck_power(session, deck_id_a="bogus-a", deck_id_b=deck_b)

    assert result.status == "both_decks_failed"
    assert result.comparison is None
    assert "'bogus-a'" in result.summary
    assert "deck_not_found" in result.summary
    assert "unsupported_format" in result.summary


async def test_explicit_unsupported_format_fails_both_sides(session: AsyncSession) -> None:
    """An unsupported explicit format surfaces via the underlying assess status (AC 5)."""
    deck_a = await _make_deck(session, _BASE_ROWS, name="A")
    deck_b = await _make_deck(session, _BASE_ROWS, name="B")

    result = await compare_deck_power(session, deck_id_a=deck_a, deck_id_b=deck_b, format="modern")

    assert result.status == "both_decks_failed"
    assert result.comparison is None
    assert "unsupported_format" in result.summary


async def test_database_not_initialized_is_global(uninitialized_session: AsyncSession) -> None:
    """An un-imported DB yields the global status, never a side fault (AC 4)."""
    result = await compare_deck_power(uninitialized_session, deck_id_a="deck-a", deck_id_b="deck-b")

    assert result.status == "database_not_initialized"
    assert result.comparison is None
    assert result.summary == DATABASE_NOT_INITIALIZED_MESSAGE


async def test_defensive_error_when_ok_result_lacks_assessment(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reserved top-level error fires if an ok assess result lacks its block.

    Structurally unreachable through the real assess helper (status="ok"
    always populates ``assessment``), so the contract is proven by stubbing
    the composed helper — the one place a test double is unavoidable.
    """
    from src.mcp_server.tools import compare_deck_power as module

    async def fake_assess(
        session: AsyncSession, *, deck_id: str, format: str | None = None
    ) -> AssessDeckPowerResult:
        return AssessDeckPowerResult(status="ok", deck_id=deck_id, summary="stub")

    monkeypatch.setattr(module, "assess_deck_power", fake_assess)

    result = await module.compare_deck_power(session, deck_id_a="a", deck_id_b="b")

    assert result.status == "error"
    assert result.comparison is None


# --- format mismatch + explicit forcing (AC 5/7) ---


async def test_format_mismatch_names_both_formats_and_hint(session: AsyncSession) -> None:
    """Different resolved formats with format omitted yield format_mismatch (AC 5)."""
    deck_a = await _make_deck(session, _BASE_ROWS, name="Commander A", format="commander")
    deck_b = await _make_deck(
        session,
        [("card-shock", 4, False, False), ("card-mountain", 20, False, False)],
        name="Standard B",
        format="standard",
    )

    result = await compare_deck_power(session, deck_id_a=deck_a, deck_id_b=deck_b)

    assert result.status == "format_mismatch"
    assert result.comparison is None
    assert "commander" in result.summary
    assert "standard" in result.summary
    assert 'format="commander"' in result.summary  # the explicit-override hint


async def test_explicit_format_forces_both_sides(session: AsyncSession) -> None:
    """An explicit format is passed verbatim to both assess calls (AC 5)."""
    deck_a = await _make_deck(session, _BASE_ROWS, name="Commander A", format="commander")
    deck_b = await _make_deck(
        session,
        [("card-shock", 4, False, False), ("card-mountain", 20, False, False)],
        name="Standard B",
        format="standard",
    )

    result = await compare_deck_power(
        session, deck_id_a=deck_a, deck_id_b=deck_b, format="commander"
    )

    assert result.status == "ok"
    comparison = result.comparison
    assert comparison is not None
    assert comparison.format == "commander"


# --- sorted diff lists (AC 6/7) ---


async def test_diff_lists_sorted_bytewise(session: AsyncSession) -> None:
    """game_changers_added and combos_added emit sorted ascending bytewise (AC 6).

    GCs enter deck_b in reverse bytewise order (Bolas's Citadel before Aura
    Shards); variants are seeded "2-2" before "1-1" — sorted emission cannot
    pass by insertion order.
    """
    await _seed_snapshot(
        session,
        [
            _snapshot_variant("2-2", ["Zada, Hedron Grinder", "Goblin Guide"]),
            _snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"]),
        ],
    )
    # Deck_a holds no variant piece at all → zero matched combos.
    deck_a = await _make_deck(
        session,
        [("card-shock", 4, False, False), ("card-mountain", 20, False, False)],
        name="Pieceless A",
    )
    deck_b = await _make_deck(
        session,
        [
            ("card-krenko", 1, False, True),
            ("card-zada", 1, False, False),
            ("card-goblin-guide", 4, False, False),
            ("card-gc-bolas", 1, False, False),
            ("card-gc-aura", 1, False, False),
            ("card-mountain", 20, False, False),
        ],
        name="Everything B",
    )

    result = await compare_deck_power(session, deck_id_a=deck_a, deck_id_b=deck_b)

    assert result.status == "ok"
    comparison = result.comparison
    assert comparison is not None
    assert comparison.game_changers_added == ("Aura Shards", "Bolas's Citadel")
    assert comparison.combos_added == ("1-1", "2-2")
    assert comparison.combos_removed == ()
    assert comparison.combos_bucket_changed == ()
    # The reverse direction: a → b removals mirror as removed lists.
    reverse = await compare_deck_power(session, deck_id_a=deck_b, deck_id_b=deck_a)
    assert reverse.comparison is not None
    assert reverse.comparison.game_changers_removed == ("Aura Shards", "Bolas's Citadel")
    assert reverse.comparison.combos_removed == ("1-1", "2-2")


# --- determinism (AC 6/7) ---


async def test_compare_model_dump_json_deterministic(session: AsyncSession) -> None:
    """Two identical compare runs serialize to byte-identical JSON (AC 6, AD-8)."""
    await _seed_snapshot(
        session, [_snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])]
    )
    deck_a = await _make_deck(session, _BASE_ROWS, name="Det A")
    deck_b = await _make_deck(
        session,
        [*_BASE_ROWS, ("card-zada", 1, False, False), ("card-gc-bolas", 1, False, False)],
        name="Det B",
    )

    first = await compare_deck_power(session, deck_id_a=deck_a, deck_id_b=deck_b)
    second = await compare_deck_power(session, deck_id_a=deck_a, deck_id_b=deck_b)

    assert first.status == "ok"
    assert first.model_dump_json() == second.model_dump_json()


# --- summary projection (AC 3/7, decide-once #5) ---


async def test_ok_summary_is_deterministic_projection(session: AsyncSession) -> None:
    """The ok summary carries score movement, tiers, bracket pair, and confidence."""
    await _seed_snapshot(
        session, [_snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])]
    )
    deck_a = await _make_deck(session, _BASE_ROWS, name="Sum A")
    deck_b = await _make_deck(
        session,
        [*_BASE_ROWS, ("card-zada", 1, False, False), ("card-gc-bolas", 1, False, False)],
        name="Sum B",
    )

    result = await compare_deck_power(session, deck_id_a=deck_a, deck_id_b=deck_b)

    assert result.status == "ok"
    comparison = result.comparison
    assert comparison is not None
    delta = comparison.for_format_score_delta
    assert "(baseline)" in result.summary
    assert (
        f"score {comparison.for_format_score_a} → {comparison.for_format_score_b} ({delta:+d})"
        in result.summary
    )
    assert f"tier {comparison.tier_a} → {comparison.tier_b}" in result.summary
    # 2 → 4: the completed two-card infinite is the FR15 hard Bracket-4 trigger.
    assert "Bracket floor 2 → 4" in result.summary
    assert "confidence" in result.summary
    # A diff is not a strength read: the assess-summary multiplayer caveat
    # never re-appends here (decide-once #5).
    assert "multiplayer" not in result.summary

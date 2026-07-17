"""In-memory MCP client harness for the Story 1.3 tools (AC7).

Drives ``lookup_card_by_name`` through an in-process MCP client connected to a
real ``build_server`` instance — no subprocess. The server is wired to a
file-backed, seeded DB via the shared ``seeded_card_db`` fixture (see
tests/integration/conftest.py). Asserts on the structured tool output and
verifies persistence by querying the same session factory.

Story 7.4 adds the ``assess_deck_power`` end-to-end regression section: wire-level
byte determinism, fixed-shape parity across formats, diff-sensitivity through real
tool edits, and the degradation-path matrix — all driven through this same
in-process client against the module-local ``assessment_card_db`` fixture.

``cards_unresolved`` e2e gap (Story 7.4 decide-once #2): that confidence token is
structurally unreachable through the client — ``DeckCard.card`` is a required
field (src/data/schemas/deck.py), so an orphaned deck row fails validation inside
``get_deck_with_cards`` before the tool ever runs, and forcing a ``card=None`` row
would test a state the system cannot produce. The token's guard remains the pure
confidence-ladder matrix
(tests/integration/mcp_server/test_assess_deck_power_tool.py::
test_derive_confidence_full_matrix); orphaned-row handling belongs to the
deferred data-layer orphan story (7.1 review disposition).
"""

import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.logic.assessment import (
    COMBO_DATA_UNAVAILABLE,
    COMMANDER_UNIDENTIFIED,
    GAME_CHANGER_DATA_UNAVAILABLE,
    TIER_LABELS,
)
from src.mcp_server.server import build_server
from src.mcp_server.tools.assess_deck_power import MULTIPLAYER_VARIANCE_CAVEAT
from src.viewer import present
from tests.fixtures.combo_snapshot import seed_snapshot, snapshot_variant
from tests.integration.conftest import SeededVecDB


async def test_lookup_card_exact_hit(seeded_card_db: async_sessionmaker[AsyncSession]):
    """An exact name returns structured status='found' with the card."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("lookup_card_by_name", {"card_name": "Lightning Bolt"})

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "found"
    assert result.structuredContent["card"]["name"] == "Lightning Bolt"


async def test_lookup_card_ambiguous(seeded_card_db: async_sessionmaker[AsyncSession]):
    """A fuzzy query matching multiple cards returns status='ambiguous' with matches."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("lookup_card_by_name", {"card_name": "bolt"})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ambiguous"
    names = {match["name"] for match in sc["matches"]}
    assert {"Lightning Bolt", "Thunderbolt"} <= names


async def test_lookup_card_no_match_is_graceful(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """A no-match returns a graceful structured not_found, not a surfaced error."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "lookup_card_by_name", {"card_name": "Nonexistent Planeswalker"}
        )

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "not_found"
    assert sc["card"] is None
    assert sc["message"]


async def test_search_cards_by_color(seeded_card_db: async_sessionmaker[AsyncSession]):
    """search_cards by color returns lightweight CardSummary rows via the harness."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("search_cards", {"colors": ["R"]})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assert sc["total_count"] == 2
    names = {card["name"] for card in sc["cards"]}
    assert names == {"Lightning Bolt", "Thunderbolt"}
    # CardSummary projection: heavy detail fields are not serialized to the client.
    first = sc["cards"][0]
    assert "legalities" not in first
    assert "image_uris" not in first


async def test_search_cards_format_filter_excludes_non_legal(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """format is a per-call parameter: the modern-only Thunderbolt is excluded from standard."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("search_cards", {"colors": ["R"], "format": "standard"})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assert {card["name"] for card in sc["cards"]} == {"Lightning Bolt"}


async def test_search_cards_invalid_is_graceful(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """A bad filter value returns a graceful structured invalid result, not a surfaced error."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("search_cards", {"colors": ["X"]})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "invalid"
    assert "X" in sc["message"]


async def test_deck_lifecycle_through_client(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """Full deck CRUD lifecycle through the in-process MCP client (no subprocess).

    create_deck → add by name → add by card_id → load_deck → list_decks →
    remove_card_from_deck → delete_deck → load_deck (now not_found). Builds the deck
    purely through the tools against the shared file-backed seeded DB (AC7).
    """
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        created = await client.call_tool("create_deck", {"name": "My Deck"})
        assert created.isError is False
        assert created.structuredContent is not None
        assert created.structuredContent["status"] == "ok"
        deck_id = created.structuredContent["deck"]["id"]
        assert deck_id

        # Add 4 Lightning Bolt via the name path.
        added_name = await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "name": "Lightning Bolt", "quantity": 4}
        )
        assert added_name.isError is False
        assert added_name.structuredContent["status"] == "ok"
        assert added_name.structuredContent["card_id"] == "card-lightning-bolt"

        # Add 1 Counterspell via the card_id path.
        added_id = await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-counterspell"}
        )
        assert added_id.isError is False
        assert added_id.structuredContent["status"] == "ok"

        # load_deck: 2 distinct cards, mainboard_count 5, cards are lightweight summaries.
        loaded = await client.call_tool("load_deck", {"deck_id": deck_id})
        assert loaded.isError is False
        deck = loaded.structuredContent["deck"]
        assert deck["distinct_cards"] == 2
        assert deck["mainboard_count"] == 5
        # Deck cards are DeckCardSummary with a CardSummary inside — no heavy keys.
        nested_card = deck["cards"][0]["card"]
        assert "legalities" not in nested_card
        assert "image_uris" not in nested_card
        assert "card_faces" not in nested_card

        # list_decks: the deck appears with counts (assert by id, NOT order).
        listed = await client.call_tool("list_decks", {})
        assert listed.isError is False
        assert listed.structuredContent["status"] == "ok"
        by_id = {d["id"]: d for d in listed.structuredContent["decks"]}
        assert deck_id in by_id
        assert by_id[deck_id]["mainboard_count"] == 5
        assert by_id[deck_id]["distinct_cards"] == 2

        # Remove a card, then delete the deck.
        removed = await client.call_tool(
            "remove_card_from_deck", {"deck_id": deck_id, "card_id": "card-lightning-bolt"}
        )
        assert removed.isError is False
        assert removed.structuredContent["status"] == "ok"

        deleted = await client.call_tool("delete_deck", {"deck_id": deck_id})
        assert deleted.isError is False
        assert deleted.structuredContent["status"] == "ok"

        # The deck is gone — load now reports not_found gracefully.
        gone = await client.call_tool("load_deck", {"deck_id": deck_id})
        assert gone.isError is False
        assert gone.structuredContent["status"] == "not_found"


async def test_add_card_to_bogus_deck_is_graceful(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """add_card_to_deck on a missing deck returns deck_not_found (not a surfaced error)."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "add_card_to_deck", {"deck_id": "bogus-deck", "card_id": "card-counterspell"}
        )

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "deck_not_found"


async def test_import_decklist_through_client(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """The bulk importer is registered, serializes line results, and persists successes."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        created = await client.call_tool("create_deck", {"name": "Arena Import"})
        deck_id = created.structuredContent["deck"]["id"]

        imported = await client.call_tool(
            "import_decklist",
            {
                "deck_id": deck_id,
                "arena_export": (
                    "Deck\n"
                    "4 Lightning Bolt (M11) 149\n"
                    "1 Missing Card (TST) 999\n"
                    "Sideboard\n"
                    "2 Counterspell (DMR) 50"
                ),
            },
        )
        loaded = await client.call_tool("load_deck", {"deck_id": deck_id})

    assert imported.isError is False
    sc = imported.structuredContent
    assert sc is not None
    assert sc["status"] == "partial"
    assert sc["total_lines"] == 3
    assert sc["imported_lines"] == 2
    assert sc["imported_copies"] == 6
    assert [line["status"] for line in sc["results"]] == ["ok", "not_found", "ok"]
    assert sc["results"][0]["set_code"] == "M11"
    assert sc["results"][1]["line_number"] == 3

    deck = loaded.structuredContent["deck"]
    cards = {
        (entry["card"]["name"], entry["sideboard"]): entry["quantity"] for entry in deck["cards"]
    }
    assert cards == {("Lightning Bolt", False): 4, ("Counterspell", True): 2}


async def test_view_deck_through_client(
    seeded_card_db: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
):
    """view_deck renders through the MCP client and reports a reachable file path (AC7).

    ``open_browser=False`` keeps CI headless; the temp dir is redirected to ``tmp_path``
    so nothing leaks into the system temp.
    """
    monkeypatch.setattr(present.tempfile, "gettempdir", lambda: str(tmp_path))
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        created = await client.call_tool("create_deck", {"name": "Client Deck"})
        deck_id = created.structuredContent["deck"]["id"]
        await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "name": "Lightning Bolt", "quantity": 1}
        )
        result = await client.call_tool("view_deck", {"deck_id": deck_id, "open_browser": False})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assert sc["opened_in_browser"] is False
    assert sc["deck_name"] == "Client Deck"
    assert sc["file_path"]
    assert Path(sc["file_path"]).exists()


async def test_deck_analysis_through_client(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """Drive analyze_mana_curve / detect_synergies / validate_deck end-to-end (AC7).

    Builds a 6-card deck through the tools (4x Lightning Bolt + Counterspell +
    Thunderbolt) from the shared 3-card fixture, then asserts each analysis tool's
    structuredContent. Confirms ``format`` is a real per-call parameter:
    Thunderbolt (modern-only) trips standard legality but not modern legality.
    """
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        created = await client.call_tool("create_deck", {"name": "Analysis Deck"})
        deck_id = created.structuredContent["deck"]["id"]
        assert deck_id

        # Build the deck through the tools (do not edit the shared fixture).
        await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "name": "Lightning Bolt", "quantity": 4}
        )
        await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-counterspell"}
        )
        await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-thunderbolt"}
        )

        # analyze_mana_curve: 6 spells, no lands; JSON dict keys are strings.
        curve = await client.call_tool("analyze_mana_curve", {"deck_id": deck_id})
        assert curve.isError is False
        curve_sc = curve.structuredContent
        assert curve_sc["status"] == "ok"
        assert curve_sc["total_spells"] == 6  # 4 + 1 + 1
        assert curve_sc["total_lands"] == 0
        assert curve_sc["distribution"]["1"] == 4  # four CMC-1 Lightning Bolts

        # detect_synergies: 3 unrelated cards -> runs, structured, no synergies.
        synergy = await client.call_tool("detect_synergies", {"deck_id": deck_id})
        assert synergy.isError is False
        synergy_sc = synergy.structuredContent
        assert synergy_sc["status"] == "ok"
        assert synergy_sc["synergies"] == []
        assert synergy_sc["deck_cohesion"] == "low"

        # validate_deck(standard): illegal (6 < 60) AND Thunderbolt is modern-only.
        standard = await client.call_tool(
            "validate_deck", {"deck_id": deck_id, "format": "standard"}
        )
        assert standard.isError is False
        report = standard.structuredContent["report"]
        assert report["is_legal"] is False
        rules = {v["rule"] for v in report["violations"]}
        assert "min_deck_size" in rules
        assert any(
            v["rule"] == "format_legality" and v["card_name"] == "Thunderbolt"
            for v in report["violations"]
        )

        # validate_deck(modern): the same deck drops the Thunderbolt legality violation.
        modern = await client.call_tool("validate_deck", {"deck_id": deck_id, "format": "modern"})
        modern_report = modern.structuredContent["report"]
        assert modern_report["format"] == "modern"
        assert not any(v["rule"] == "format_legality" for v in modern_report["violations"])


async def test_analysis_tools_on_bogus_deck_are_graceful(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """Each analysis tool on a bogus deck_id returns deck_not_found, isError False (AC7)."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        for tool in (
            "analyze_mana_curve",
            "detect_synergies",
            "validate_deck",
            "assess_deck_power",
        ):
            result = await client.call_tool(tool, {"deck_id": "bogus-deck"})
            assert result.isError is False, tool
            assert result.structuredContent is not None
            assert result.structuredContent["status"] == "deck_not_found", tool


async def test_assess_deck_power_through_client(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """assess_deck_power is listed, callable, and round-trips structuredContent (Story 7.1/7.3).

    Builds a standard deck purely through the tools, then asserts the full AD-7
    shape: status ok, always-present schema_version, the populated assessment
    block (vector + flags), and the deterministic summary projection.
    """
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        tools = await client.list_tools()
        assert "assess_deck_power" in {t.name for t in tools.tools}

        created = await client.call_tool("create_deck", {"name": "Bolt Deck"})
        deck_id = created.structuredContent["deck"]["id"]
        added = await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "name": "Lightning Bolt", "quantity": 4}
        )
        assert added.structuredContent["status"] == "ok"

        result = await client.call_tool("assess_deck_power", {"deck_id": deck_id})
        assert result.isError is False
        sc = result.structuredContent
        assert sc is not None
        assert sc["status"] == "ok"
        assert sc["schema_version"] == "1"
        assert sc["deck_id"] == deck_id
        # Story 7.3: the assessment block round-trips through structuredContent.
        assessment = sc["assessment"]
        assert assessment is not None
        assert assessment["format"] == "standard"
        assert list(assessment["vector"]) == _VECTOR_KEYS
        assert all(isinstance(v, int) for v in assessment["vector"].values())
        assert assessment["bracket"] is None  # standard: fixed shape, null bracket
        assert assessment["flags"]["cedh_candidate"] is False
        assert assessment["data_vintage"]["format_profile_version"] == "standard-v4"
        assert "standard-v4" in sc["summary"]  # create_deck default format resolves via ladder
        # Story 7.2 summary facts: scored + a categorical confidence with reasons text.
        assert "/100" in sc["summary"]
        assert "confidence " in sc["summary"]

        # The format param is per-call state: an unsupported value is graceful.
        unsupported = await client.call_tool(
            "assess_deck_power", {"deck_id": deck_id, "format": "modern"}
        )
        assert unsupported.isError is False
        assert unsupported.structuredContent["status"] == "unsupported_format"
        assert "Supported formats: commander, standard" in unsupported.structuredContent["summary"]


# --- assess_deck_power e2e: shape, determinism, diff-sensitivity, degradations (Story 7.4) ---


#: The seven AD-7 vector keys in emission order (mirrors the model declaration).
_VECTOR_KEYS = [
    "speed",
    "consistency",
    "resilience",
    "interaction",
    "mana_efficiency",
    "card_advantage",
    "combo_potential",
]


def _assessment_card(
    card_id: str,
    name: str,
    *,
    type_line: str,
    cmc: float = 2.0,
    oracle_text: str = "Does a thing.",
    colors: list[str] | None = None,
    game_changer: bool | None = False,
) -> CardModel:
    """Build a CardModel legal in commander+standard with a unique oracle_id.

    Mirrors the ``_card`` builder shape in test_assess_deck_power_tool.py.
    ``game_changer`` defaults to ``False`` (confirmed not) so high-confidence
    paths stay clean; the NULL fixture card opts in explicitly.
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


def _assessment_cards() -> list[CardModel]:
    """Assessment-grade seed: commander candidates, combo partners, GC states, lands.

    Deliberately NOT added to the shared ``_sample_cards`` — its counts are pinned
    by existing assertions (Story 7.4 AC 5). The two confirmed Game Changers are
    seeded in reverse bytewise name order ("Bolas's Citadel" before "Aura Shards")
    so sorted-emission assertions cannot pass by insert-order accident.
    """
    return [
        _assessment_card(
            "e2e-mountain",
            "Mountain",
            type_line="Basic Land — Mountain",
            cmc=0.0,
            oracle_text="{T}: Add {R}.",
            colors=[],
        ),
        _assessment_card(
            "e2e-krenko",
            "Krenko, Mob Boss",
            type_line="Legendary Creature — Goblin",
            cmc=4.0,
        ),
        _assessment_card(
            "e2e-zada",
            "Zada, Hedron Grinder",
            type_line="Legendary Creature — Goblin Ally",
            cmc=3.0,
        ),
        _assessment_card(
            "e2e-goblin-guide",
            "Goblin Guide",
            type_line="Creature — Goblin Scout",
            cmc=1.0,
        ),
        _assessment_card(
            "e2e-shock",
            "Shock",
            type_line="Instant",
            cmc=1.0,
        ),
        _assessment_card(
            "e2e-gc-bolas",
            "Bolas's Citadel",
            type_line="Legendary Artifact",
            cmc=6.0,
            game_changer=True,
        ),
        _assessment_card(
            "e2e-gc-aura",
            "Aura Shards",
            type_line="Enchantment",
            cmc=3.0,
            colors=["G", "W"],
            game_changer=True,
        ),
        _assessment_card(
            "e2e-gc-null",
            "Mystery Relic",
            type_line="Artifact",
            cmc=2.0,
            game_changer=None,  # unknown state — the game_changer_data_unavailable fixture
        ),
    ]


@pytest.fixture
async def assessment_card_db(
    tmp_path: Path,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Session factory on a file-backed DB seeded with the assessment-grade card set.

    Module-local (not conftest): the shared ``seeded_card_db`` 3-card seed leaves
    ``game_changer`` NULL everywhere, which forces ``game_changer_data_unavailable``
    on every assessment — unusable for the high-confidence e2e paths. File-backed
    (WAL) so the tools' own sessions from the same factory see committed writes.
    """
    db_path = tmp_path / "assess_e2e.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        for card in _assessment_cards():
            session.add(card)
        await session.commit()

    try:
        yield session_factory
    finally:
        await engine.dispose()


async def _build_deck(
    client: ClientSession,
    *,
    name: str,
    format: str,
    rows: list[tuple[str, int, bool]],
) -> str:
    """create_deck + add (card_id, quantity, commander) rows through the tools; returns deck id.

    Named for reuse: Story 7.5 (compare_deck_power) builds its two-deck setups
    with this same shape.
    """
    created = await client.call_tool("create_deck", {"name": name, "format": format})
    assert created.structuredContent is not None
    assert created.structuredContent["status"] == "ok"
    deck_id: str = created.structuredContent["deck"]["id"]
    for card_id, quantity, commander in rows:
        added = await client.call_tool(
            "add_card_to_deck",
            {"deck_id": deck_id, "card_id": card_id, "quantity": quantity, "commander": commander},
        )
        assert added.structuredContent is not None
        assert added.structuredContent["status"] == "ok"
    return deck_id


async def test_assess_commander_deck_through_client(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """A Commander deck built purely through the tools scores with bracket + caveat (AC 1)."""
    async with assessment_card_db() as session:
        await seed_snapshot(
            session,
            [snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])],
        )
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        deck_id = await _build_deck(
            client,
            name="Krenko E2E",
            format="commander",
            rows=[
                ("e2e-krenko", 1, True),
                ("e2e-zada", 1, False),
                ("e2e-goblin-guide", 4, False),
                ("e2e-shock", 4, False),
                ("e2e-mountain", 20, False),
            ],
        )
        result = await client.call_tool("assess_deck_power", {"deck_id": deck_id})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assessment = sc["assessment"]
    assert assessment["format"] == "commander"
    assert assessment["bracket"] in {2, 3, 4}
    assert list(assessment["vector"]) == _VECTOR_KEYS
    assert all(isinstance(v, int) and 0 <= v <= 100 for v in assessment["vector"].values())
    # Calibration-free liveness (Story 7.4 review): a healthy, fully-known deck must
    # not score globally zero. Guards against a scorer regressed to all-zeros, which
    # the per-value 0–100 range checks alone would pass. Asserts no magnitude (AC 6 /
    # decide-once #4), only non-degeneracy.
    assert sum(assessment["vector"].values()) > 0
    assert assessment["tier"] in TIER_LABELS
    # Snapshot present + flagged commander + every GC state known → no degradations.
    assert assessment["confidence"]["level"] == "high"
    assert assessment["confidence"]["reasons"] == []
    assert [combo["bucket"] for combo in assessment["flags"]["combos"]] == ["included"]
    assert sc["summary"].endswith(MULTIPLAYER_VARIANCE_CAVEAT)


async def test_assess_standard_deck_full_contract_through_client(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """A Standard deck scores with the vector, tier, null bracket, and no caveat (AC 1)."""
    async with assessment_card_db() as session:
        await seed_snapshot(
            session,
            [snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
        )
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        deck_id = await _build_deck(
            client,
            name="Shock Standard",
            format="standard",
            rows=[
                ("e2e-shock", 4, False),
                ("e2e-goblin-guide", 4, False),
                ("e2e-mountain", 20, False),
            ],
        )
        result = await client.call_tool("assess_deck_power", {"deck_id": deck_id})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assessment = sc["assessment"]
    assert assessment["format"] == "standard"
    assert isinstance(assessment["for_format_score"], int)
    assert 0 <= assessment["for_format_score"] <= 100
    assert list(assessment["vector"]) == _VECTOR_KEYS
    assert all(isinstance(v, int) and 0 <= v <= 100 for v in assessment["vector"].values())
    assert assessment["tier"] in TIER_LABELS
    assert assessment["bracket"] is None  # fixed shape at the wire: null, never missing
    assert "/100" in sc["summary"]
    assert MULTIPLAYER_VARIANCE_CAVEAT not in sc["summary"]


def _shape(value: object) -> object:
    """Recursive key shape of a wire payload: dicts map keys to sub-shapes.

    Lists collapse to a marker rather than recursing because their lengths and
    contents legitimately differ between formats (e.g. matched combos); AD-7
    fixes the *key* shape, not list contents.
    """
    if isinstance(value, dict):
        return {key: _shape(sub) for key, sub in value.items()}
    if isinstance(value, list):
        return "list"
    return "scalar"


async def test_wire_shape_parity_commander_vs_standard(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """Both formats' assessment blocks carry identical key sets at every level (AC 1, AD-7)."""
    async with assessment_card_db() as session:
        await seed_snapshot(
            session,
            [snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
        )
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        commander_id = await _build_deck(
            client,
            name="Parity Commander",
            format="commander",
            rows=[
                ("e2e-krenko", 1, True),
                ("e2e-goblin-guide", 4, False),
                ("e2e-mountain", 20, False),
            ],
        )
        standard_id = await _build_deck(
            client,
            name="Parity Standard",
            format="standard",
            rows=[("e2e-shock", 4, False), ("e2e-mountain", 20, False)],
        )
        commander_result = await client.call_tool("assess_deck_power", {"deck_id": commander_id})
        standard_result = await client.call_tool("assess_deck_power", {"deck_id": standard_id})

    c = commander_result.structuredContent["assessment"]
    s = standard_result.structuredContent["assessment"]
    # Recursive key-set equality at every nesting level (null bracket is a key, not a hole).
    assert _shape(c) == _shape(s)
    # Emission (declaration) key order also matches at each named level.
    assert list(c) == list(s)
    assert list(c["vector"]) == list(s["vector"]) == _VECTOR_KEYS
    assert list(c["data_vintage"]) == list(s["data_vintage"])
    assert list(c["confidence"]) == list(s["confidence"])
    assert list(c["flags"]) == list(s["flags"])
    assert s["bracket"] is None
    assert s["flags"]["cedh_candidate"] is False
    assert c["bracket"] in {2, 3, 4}


async def test_assess_deck_power_wire_bytes_deterministic(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """Two identical calls produce byte-identical serialized wire JSON (AC 2, AD-8/NFR1).

    Byte-comparison surface (Story 7.4 decide-once #3): ``result.content[0].text``.
    The Task-0 probe showed ``call_tool`` returns exactly one TextContent whose
    ``.text`` IS the JSON projection of the result (it parses back equal to
    ``structuredContent`` with model-declaration key order preserved), so the wire
    text is the strictest available surface. The assertion is STRING equality —
    dict equality would pass even with unstable key or list ordering. Story 7.5
    reuses this surface for compare_deck_power.
    """
    async with assessment_card_db() as session:
        # Variant ids deliberately out of insert order: emission must sort, not echo.
        await seed_snapshot(
            session,
            [
                snapshot_variant("2-2", ["Krenko, Mob Boss", "Zada, Hedron Grinder"]),
                snapshot_variant("1-1", ["Zada, Hedron Grinder", "Goblin Guide"]),
            ],
        )
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        # Maximally exercised payload: combos, confirmed GCs (reverse-sorted insert
        # order), a NULL-GC card, lands.
        deck_id = await _build_deck(
            client,
            name="Determinism Deck",
            format="commander",
            rows=[
                ("e2e-krenko", 1, True),
                ("e2e-zada", 1, False),
                ("e2e-goblin-guide", 4, False),
                ("e2e-gc-bolas", 1, False),
                ("e2e-gc-aura", 1, False),
                ("e2e-gc-null", 1, False),
                ("e2e-mountain", 20, False),
            ],
        )
        result_a = await client.call_tool("assess_deck_power", {"deck_id": deck_id})
        result_b = await client.call_tool("assess_deck_power", {"deck_id": deck_id})

    assert result_a.isError is False
    assert result_b.isError is False
    assert result_a.structuredContent["status"] == "ok"
    [block_a] = result_a.content
    [block_b] = result_b.content
    # Pin the surface to the payload so the equality below can't pass vacuously:
    # the wire text must be non-empty and parse back to structuredContent (the
    # decide-once #3 probe invariant), not just equal a constant/empty string.
    assert block_a.text
    assert json.loads(block_a.text) == result_a.structuredContent
    assert block_a.text == block_b.text  # byte-identical serialized JSON at the wire

    # The sorted-emission facts survive the wire — the edge re-sorts nothing, so
    # a failure here means a producer (core/matcher/ladder) regressed.
    assessment = result_a.structuredContent["assessment"]
    reasons = assessment["confidence"]["reasons"]
    assert reasons == sorted(reasons)
    assert reasons == [GAME_CHANGER_DATA_UNAVAILABLE]  # the sole degradation seeded
    assert assessment["flags"]["game_changers"] == ["Aura Shards", "Bolas's Citadel"]
    assert [c["spellbook_id"] for c in assessment["flags"]["combos"]] == ["1-1", "2-2"]


async def test_add_game_changer_raises_bracket_floor(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """Adding a confirmed Game Changer through the tools lifts Bracket 2 → 3 (AC 3).

    Directions mirror tests/unit/logic/test_assessment_scorer.py
    (TestMonotonicityProperties) and the GC gate in
    src/logic/assessment/dimensions.py (1–3 confirmed GCs floor at Bracket 3).
    Only guaranteed-direction facts are asserted — total-score movement is
    weight-dependent calibration territory (Story 7.4 decide-once #4).
    """
    async with assessment_card_db() as session:
        # Healthy zero-overlap snapshot: no combo degradation, no combo bracket lift.
        await seed_snapshot(
            session,
            [snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
        )
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        deck_id = await _build_deck(
            client,
            name="GC Diff Deck",
            format="commander",
            rows=[
                ("e2e-krenko", 1, True),
                ("e2e-goblin-guide", 4, False),
                ("e2e-shock", 4, False),
                ("e2e-mountain", 20, False),
            ],
        )
        before = await client.call_tool("assess_deck_power", {"deck_id": deck_id})
        added = await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "card_id": "e2e-gc-bolas"}
        )
        assert added.structuredContent["status"] == "ok"
        after = await client.call_tool("assess_deck_power", {"deck_id": deck_id})

    a_before = before.structuredContent["assessment"]
    a_after = after.structuredContent["assessment"]
    assert a_before["bracket"] == 2  # 0-GC, combo-free baseline floors at exactly 2
    assert a_before["flags"]["game_changers"] == []
    assert a_after["bracket"] == 3  # the GC gate: 1–3 confirmed GCs floor at Bracket 3
    assert a_after["flags"]["game_changers"] == ["Bolas's Citadel"]
    assert a_after["bracket"] >= a_before["bracket"]  # never lowers


async def test_combo_completion_flips_bucket_and_raises_combo_potential(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """Adding the completing combo piece flips almost_included → included (AC 3).

    Directions mirror tests/unit/logic/test_assessment_scorer.py::
    test_diff_sensitivity_second_piece: the bucket flips, ``combo_potential``
    strictly rises, and the bracket never lowers. No magnitude assertions
    (Story 7.4 decide-once #4).
    """
    async with assessment_card_db() as session:
        await seed_snapshot(
            session,
            [snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])],
        )
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        # Deck holds exactly one piece of the 2-card variant → almost_included.
        deck_id = await _build_deck(
            client,
            name="Combo Diff Deck",
            format="commander",
            rows=[
                ("e2e-krenko", 1, True),
                ("e2e-goblin-guide", 4, False),
                ("e2e-mountain", 20, False),
            ],
        )
        before = await client.call_tool("assess_deck_power", {"deck_id": deck_id})
        added = await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "card_id": "e2e-zada"}
        )
        assert added.structuredContent["status"] == "ok"
        after = await client.call_tool("assess_deck_power", {"deck_id": deck_id})

    a_before = before.structuredContent["assessment"]
    a_after = after.structuredContent["assessment"]
    assert [c["bucket"] for c in a_before["flags"]["combos"]] == ["almost_included"]
    assert [c["bucket"] for c in a_after["flags"]["combos"]] == ["included"]
    assert a_after["vector"]["combo_potential"] > a_before["vector"]["combo_potential"]
    assert a_after["bracket"] >= a_before["bracket"]  # never lowers


async def test_absent_combo_snapshot_degrades_gracefully_e2e(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """No snapshot seeded → scored ok + combo_data_unavailable + null combo vintage (AC 4)."""
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        deck_id = await _build_deck(
            client,
            name="No Snapshot Deck",
            format="commander",
            rows=[
                ("e2e-krenko", 1, True),
                ("e2e-goblin-guide", 4, False),
                ("e2e-mountain", 20, False),
            ],
        )
        result = await client.call_tool("assess_deck_power", {"deck_id": deck_id})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assert "/100" in sc["summary"]  # scored, never a silent zero
    assessment = sc["assessment"]
    assert assessment is not None
    assert COMBO_DATA_UNAVAILABLE in assessment["confidence"]["reasons"]
    assert assessment["data_vintage"]["combo_snapshot_imported_at"] is None
    assert assessment["data_vintage"]["combo_snapshot_export_version"] is None


async def test_null_game_changer_degrades_gracefully_e2e(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """A NULL game_changer card fires game_changer_data_unavailable, still scored (AC 4)."""
    async with assessment_card_db() as session:
        await seed_snapshot(
            session,
            [snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
        )
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        deck_id = await _build_deck(
            client,
            name="Null GC Deck",
            format="commander",
            rows=[
                ("e2e-krenko", 1, True),
                ("e2e-gc-null", 1, False),
                ("e2e-mountain", 20, False),
            ],
        )
        result = await client.call_tool("assess_deck_power", {"deck_id": deck_id})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assert "/100" in sc["summary"]
    assessment = sc["assessment"]
    assert assessment is not None
    assert assessment["confidence"]["reasons"] == [GAME_CHANGER_DATA_UNAVAILABLE]
    assert assessment["confidence"]["level"] == "medium"


async def test_unidentified_commander_degrades_gracefully_e2e(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """A Commander deck with no flags and two distinct legendaries degrades honestly (AC 4)."""
    async with assessment_card_db() as session:
        await seed_snapshot(
            session,
            [snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
        )
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        # Two distinct unflagged legendary creatures → no inference possible.
        deck_id = await _build_deck(
            client,
            name="Headless Commander Deck",
            format="commander",
            rows=[
                ("e2e-krenko", 1, False),
                ("e2e-zada", 1, False),
                ("e2e-goblin-guide", 4, False),
                ("e2e-mountain", 20, False),
            ],
        )
        result = await client.call_tool("assess_deck_power", {"deck_id": deck_id})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assert "/100" in sc["summary"]
    assessment = sc["assessment"]
    assert assessment is not None
    assert assessment["confidence"]["reasons"] == [COMMANDER_UNIDENTIFIED]
    assert assessment["confidence"]["level"] == "medium"


async def test_standard_deck_never_fires_commander_unidentified_e2e(
    assessment_card_db: async_sessionmaker[AsyncSession],
):
    """A Standard deck never carries the commander_unidentified token (AC 4)."""
    async with assessment_card_db() as session:
        await seed_snapshot(
            session,
            [snapshot_variant("9-9", ["Thassa's Oracle", "Demonic Consultation"])],
        )
    server = build_server(session_factory=assessment_card_db)
    async with create_connected_server_and_client_session(server) as client:
        deck_id = await _build_deck(
            client,
            name="Standard Never Unidentified",
            format="standard",
            rows=[("e2e-shock", 4, False), ("e2e-mountain", 20, False)],
        )
        result = await client.call_tool("assess_deck_power", {"deck_id": deck_id})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assert "/100" in sc["summary"]
    assessment = sc["assessment"]
    assert assessment is not None
    assert COMMANDER_UNIDENTIFIED not in assessment["confidence"]["reasons"]
    assert assessment["confidence"]["level"] == "high"
    assert assessment["confidence"]["reasons"] == []


# --- semantic_search_cards: the sync RAG tool through the in-process MCP client (Story 2.4) --


def _vec_server(vec_db: SeededVecDB):
    """build_server wired with the vector fixture's sync seams + the SAME fake embedder."""
    return build_server(
        session_factory=vec_db.session_factory,
        connection_factory=vec_db.connection_factory,
        embedder=vec_db.embedder,
    )


async def test_semantic_search_sync_tool_is_hosted_alongside_async(seeded_vec_db: SeededVecDB):
    """FastMCP hosts the sync semantic_search_cards tool next to the async Epic-1 tools."""
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools.tools}
    assert "semantic_search_cards" in names  # the sync tool
    assert {"search_cards", "lookup_card_by_name"} <= names  # the async tools still present


async def test_semantic_search_returns_nearest_card(seeded_vec_db: SeededVecDB):
    """A relevant query returns status='ok' with the expected nearest card (with a distance)."""
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "semantic_search_cards", {"query": seeded_vec_db.query_text("Inferno Dragon")}
        )

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assert sc["total_count"] == len(sc["cards"])
    assert sc["total_count"] > 0
    assert sc["cards"][0]["card"]["name"] == "Inferno Dragon"
    assert "distance" in sc["cards"][0]
    # Lightweight projection through the wire: no heavy detail fields on the nested card.
    assert "legalities" not in sc["cards"][0]["card"]
    assert "image_uris" not in sc["cards"][0]["card"]


async def test_semantic_search_format_filter_excludes_non_legal(seeded_vec_db: SeededVecDB):
    """format is a per-call hybrid filter through the wire: the modern-only goblin drops out."""
    query = seeded_vec_db.query_text("Backstreet Goblin")
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        unfiltered = await client.call_tool("semantic_search_cards", {"query": query})
        filtered = await client.call_tool(
            "semantic_search_cards", {"query": query, "format": "standard"}
        )

    # Without a format filter the modern-only goblin is the nearest hit...
    assert unfiltered.isError is False
    assert unfiltered.structuredContent["cards"][0]["card"]["name"] == "Backstreet Goblin"
    # ...but it is excluded once Standard legality is required (hybrid JOIN post-filter).
    assert filtered.isError is False
    assert filtered.structuredContent["status"] == "ok"
    filtered_names = {c["card"]["name"] for c in filtered.structuredContent["cards"]}
    assert "Backstreet Goblin" not in filtered_names


async def test_semantic_search_empty_when_filters_exclude_all(seeded_vec_db: SeededVecDB):
    """A valid query with no surviving matches returns status='empty', isError=False (AC6)."""
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        # No seeded card is White — the color pre-filter excludes every card.
        result = await client.call_tool(
            "semantic_search_cards",
            {"query": seeded_vec_db.query_text("Inferno Dragon"), "colors": ["W"]},
        )

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "empty"
    assert sc["cards"] == []
    assert sc["total_count"] == 0
    assert sc["message"]


async def test_semantic_search_invalid_color_is_graceful(seeded_vec_db: SeededVecDB):
    """A bad color value returns a graceful structured invalid result, not a surfaced error."""
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "semantic_search_cards",
            {"query": seeded_vec_db.query_text("Inferno Dragon"), "colors": ["X"]},
        )

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "invalid"
    assert "X" in sc["message"]


# --- find_similar_cards: the second sync RAG tool through the in-process MCP client (Story 2.5) -


async def test_find_similar_sync_tool_is_hosted_alongside_others(seeded_vec_db: SeededVecDB):
    """FastMCP hosts the sync find_similar_cards tool next to semantic_search + the async tools."""
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools.tools}
    assert "find_similar_cards" in names  # the 14th tool
    assert "semantic_search_cards" in names
    assert {"search_cards", "lookup_card_by_name"} <= names


async def test_find_similar_returns_alternatives_excluding_seed_oracle(seeded_vec_db: SeededVecDB):
    """A seed returns status='ok' alternatives with the seed's own oracle absent (plus distance)."""
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("find_similar_cards", {"card_name": "Inferno Dragon"})

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "ok"
    assert sc["total_count"] == len(sc["cards"])
    assert sc["total_count"] > 0
    assert sc["seed"]["name"] == "Inferno Dragon"  # the resolved seed is echoed back
    names = {c["card"]["name"] for c in sc["cards"]}
    assert "Inferno Dragon" not in names  # the seed (its oracle) is excluded — alternatives only
    assert names <= {"Backstreet Goblin", "Mind Dissolve", "Verdant Elf"}
    assert len(names) > 0
    assert "distance" in sc["cards"][0]
    # Lightweight projection through the wire: no heavy detail fields on the nested card.
    assert "legalities" not in sc["cards"][0]["card"]
    assert "image_uris" not in sc["cards"][0]["card"]


async def test_find_similar_format_filter_excludes_non_legal(seeded_vec_db: SeededVecDB):
    """format is a per-call hybrid filter through the wire: the modern-only goblin drops out."""
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        unfiltered = await client.call_tool("find_similar_cards", {"card_name": "Inferno Dragon"})
        filtered = await client.call_tool(
            "find_similar_cards", {"card_name": "Inferno Dragon", "format": "standard"}
        )

    # Without a format filter the modern-only goblin is a candidate alternative...
    assert unfiltered.isError is False
    assert "Backstreet Goblin" in {c["card"]["name"] for c in unfiltered.structuredContent["cards"]}
    # ...but it is excluded once Standard legality is required (hybrid JOIN post-filter).
    assert filtered.isError is False
    assert filtered.structuredContent["status"] == "ok"
    filtered_names = {c["card"]["name"] for c in filtered.structuredContent["cards"]}
    assert "Backstreet Goblin" not in filtered_names


async def test_find_similar_bad_seed_name_is_graceful(seeded_vec_db: SeededVecDB):
    """An unknown seed name returns status='not_found', isError=False (no surfaced exception)."""
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "find_similar_cards", {"card_name": "Nonexistent Planeswalker"}
        )

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "not_found"
    assert sc["cards"] == []
    assert sc["seed"] is None
    assert sc["message"]


async def test_find_similar_invalid_filter_is_graceful(seeded_vec_db: SeededVecDB):
    """An invalid color filter returns status='invalid', isError=False through the MCP wire."""
    server = _vec_server(seeded_vec_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "find_similar_cards", {"card_name": "Inferno Dragon", "colors": ["X"]}
        )

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    assert sc["status"] == "invalid"
    assert "X" in sc["message"]

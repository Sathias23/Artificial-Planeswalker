"""In-memory MCP client harness for the Story 1.3 tools (AC7).

Drives ``lookup_card_by_name`` and ``report_bug`` through an in-process MCP
client connected to a real ``build_server`` instance — no subprocess. The server
is wired to a file-backed, seeded DB via the shared ``seeded_card_db`` fixture
(see tests/integration/conftest.py). Asserts on the structured tool output and
verifies persistence by querying the same session factory.
"""

from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.models.bug_report import BugReportModel
from src.mcp_server.server import build_server


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


async def test_report_bug_persists_and_confirms(
    seeded_card_db: async_sessionmaker[AsyncSession],
):
    """report_bug returns a confirmation with the id AND writes a row to bug_reports."""
    server = build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "report_bug", {"description": "Card search returned the wrong result"}
        )

    assert result.isError is False
    sc = result.structuredContent
    assert sc is not None
    report_id = sc["id"]
    assert report_id
    assert report_id in sc["message"]

    # The row exists when queried via the same session factory (shared file DB).
    async with seeded_card_db() as session:
        stmt = select(BugReportModel).where(BugReportModel.id == report_id)
        row = (await session.execute(stmt)).scalar_one()
        assert row.description == "Card search returned the wrong result"
        assert row.status == "open"


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
        for tool in ("analyze_mana_curve", "detect_synergies", "validate_deck"):
            result = await client.call_tool(tool, {"deck_id": "bogus-deck"})
            assert result.isError is False, tool
            assert result.structuredContent is not None
            assert result.structuredContent["status"] == "deck_not_found", tool

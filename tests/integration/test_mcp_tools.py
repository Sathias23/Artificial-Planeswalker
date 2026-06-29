"""In-memory MCP client harness for the Story 1.3 tools (AC7).

Drives ``lookup_card_by_name`` through an in-process MCP client connected to a
real ``build_server`` instance — no subprocess. The server is wired to a
file-backed, seeded DB via the shared ``seeded_card_db`` fixture (see
tests/integration/conftest.py). Asserts on the structured tool output and
verifies persistence by querying the same session factory.
"""

from pathlib import Path

from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.mcp_server.server import build_server
from src.viewer import present
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
        for tool in ("analyze_mana_curve", "detect_synergies", "validate_deck"):
            result = await client.call_tool(tool, {"deck_id": "bogus-deck"})
            assert result.isError is False, tool
            assert result.structuredContent is not None
            assert result.structuredContent["status"] == "deck_not_found", tool


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

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

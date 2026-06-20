"""Integration tests for the lookup_card helper (Story 1.3, Task 2).

Exercises the disambiguation buckets (0 / 1 / 2-5 / 6+) and format filtering of
the structured card-lookup logic directly against a seeded session. The
end-to-end MCP-client wiring is covered separately in test_mcp_tools.py.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.mcp_server.tools.card_lookup import CardLookupResult, lookup_card


def _card(card_id: str, name: str, legalities: dict[str, str] | None = None) -> CardModel:
    """Build a minimal valid CardModel for seeding."""
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Does a thing.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        legalities=legalities if legalities is not None else {"standard": "legal"},
    )


@pytest.fixture
async def in_memory_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(in_memory_engine):
    """Create a test session and seed cards (same session seeds and queries)."""
    session_factory = create_session_factory(in_memory_engine)
    async with session_factory() as session:
        cards = [
            _card("c-lbolt", "Lightning Bolt"),
            _card("c-tbolt", "Thunderbolt"),
            _card("c-bhound", "Bolt Hound"),
            _card("c-counter", "Counterspell"),
            _card("c-d1", "Storm Drake"),
            _card("c-d2", "Wind Drake"),
            _card("c-d3", "Azure Drake"),
            _card("c-d4", "Mist Drake"),
            _card("c-d5", "Fire Drake"),
            _card("c-d6", "Sea Drake"),
            _card("c-modern", "Modern Relic", legalities={"modern": "legal"}),
        ]
        for card in cards:
            session.add(card)
        await session.commit()
        yield session


async def test_exact_match_returns_found(session: AsyncSession):
    """An exact (case-insensitive) name returns status='found' with the card."""
    result = await lookup_card(session, "lightning bolt")

    assert isinstance(result, CardLookupResult)
    assert result.status == "found"
    assert result.card is not None
    assert result.card.name == "Lightning Bolt"
    assert result.matches == []


async def test_single_partial_match_returns_found(session: AsyncSession):
    """A partial query with exactly one match returns status='found'."""
    result = await lookup_card(session, "counterspell")

    assert result.status == "found"
    assert result.card is not None
    assert result.card.name == "Counterspell"


async def test_ambiguous_small_bucket_returns_matches(session: AsyncSession):
    """A 2-5 match partial query returns status='ambiguous' with all matches."""
    result = await lookup_card(session, "bolt")

    assert result.status == "ambiguous"
    assert result.card is None
    names = {c.name for c in result.matches}
    assert names == {"Lightning Bolt", "Thunderbolt", "Bolt Hound"}
    assert "which one" in result.message.lower()


async def test_ambiguous_large_bucket_suggests_refine(session: AsyncSession):
    """A 6+ match partial query returns status='ambiguous' and suggests refining."""
    result = await lookup_card(session, "drake")

    assert result.status == "ambiguous"
    assert len(result.matches) == 6
    assert "refine" in result.message.lower()


async def test_no_match_returns_not_found(session: AsyncSession):
    """A query with no matches returns a graceful status='not_found' (no exception)."""
    result = await lookup_card(session, "Nonexistent Planeswalker")

    assert result.status == "not_found"
    assert result.card is None
    assert result.matches == []
    assert result.message


async def test_format_filter_excludes_non_legal(session: AsyncSession):
    """format is a tool parameter: a non-legal format yields not_found."""
    # "Modern Relic" is only modern-legal, so a standard filter excludes it.
    result = await lookup_card(session, "Modern Relic", format="standard")

    assert result.status == "not_found"

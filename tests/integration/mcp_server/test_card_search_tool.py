"""Integration tests for the search_cards helper (Story 1.4, Task 2/4).

Exercises the relational filter combinations, the four color_mode semantics,
pagination, the graceful empty path, and graceful input validation of the
structured card-search logic directly against a seeded session. The end-to-end
MCP-client wiring is covered separately in test_mcp_tools.py.

Helper tests seed and query in the SAME session, so an in-memory SQLite DB is
fine here (mirrors test_card_lookup_tool.py). The cross-session harness test must
use the file-backed fixture instead.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.schemas.card import CardSummary
from src.mcp_server.tools.card_search import CardSearchResult, search_cards


def _card(
    card_id: str,
    name: str,
    *,
    colors: list[str],
    type_line: str = "Creature",
    cmc: float = 2.0,
    rarity: str = "common",
    legalities: dict[str, str] | None = None,
    mana_cost: str = "{1}",
    oracle_text: str = "Does a thing.",
    games: list[str] | None = None,
) -> CardModel:
    """Build a CardModel with a unique oracle_id (avoids unique-oracle collapsing)."""
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
        mana_cost=mana_cost,
        cmc=cmc,
        type_line=type_line,
        oracle_text=oracle_text,
        rarity=rarity,
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=colors,
        color_identity=colors or [],
        legalities=legalities
        if legalities is not None
        else {"standard": "legal", "modern": "legal"},
        games=games if games is not None else ["paper", "arena", "mtgo"],
    )


def _seed_cards() -> list[CardModel]:
    """A richer seed spanning W/U/B/R/G + multicolor + colorless, types, cmc, rarity, format.

    Counts relied on by tests:
      - 8 mono-red cards (one modern-only: "Shock") → pagination + format coverage.
      - colors W: 4 mono-W + Azorius Charm (WU) + Esper Sentinel (WUB) = 6 contain W.
      - colors U: 3 mono-U + Azorius Charm + Esper Sentinel = 5 contain U.
      - mythic: Inferno Titan, Esper Sentinel, Craterhoof Behemoth = 3.
      - rare: Savannah Lions, Ember Hauler, Flame Wave, Wrath of God = 4.
    """
    return [
        # --- Mono red (8) ---
        _card("r-goblin", "Goblin Raider", colors=["R"], type_line="Creature", cmc=1.0),
        _card("r-strike", "Lightning Strike", colors=["R"], type_line="Instant", cmc=2.0),
        _card(
            "r-firedrake",
            "Fire Drake",
            colors=["R"],
            type_line="Creature",
            cmc=3.0,
            rarity="uncommon",
        ),
        _card(
            "r-titan", "Inferno Titan", colors=["R"], type_line="Creature", cmc=6.0, rarity="mythic"
        ),
        _card(
            "r-shock",
            "Shock",
            colors=["R"],
            type_line="Instant",
            cmc=1.0,
            legalities={"modern": "legal"},
        ),
        _card(
            "r-hauler", "Ember Hauler", colors=["R"], type_line="Creature", cmc=2.0, rarity="rare"
        ),
        _card(
            "r-flamewave", "Flame Wave", colors=["R"], type_line="Sorcery", cmc=4.0, rarity="rare"
        ),
        _card("r-raging", "Raging Goblin", colors=["R"], type_line="Creature", cmc=1.0),
        # --- Mono white (4) ---
        _card(
            "w-lions", "Savannah Lions", colors=["W"], type_line="Creature", cmc=1.0, rarity="rare"
        ),
        _card("w-pacifism", "Pacifism", colors=["W"], type_line="Enchantment", cmc=2.0),
        _card(
            "w-serra", "Serra Angel", colors=["W"], type_line="Creature", cmc=5.0, rarity="uncommon"
        ),
        _card("w-wrath", "Wrath of God", colors=["W"], type_line="Sorcery", cmc=4.0, rarity="rare"),
        # --- Mono blue (3) ---
        _card("u-counter", "Counterspell", colors=["U"], type_line="Instant", cmc=2.0),
        _card(
            "u-looter",
            "Merfolk Looter",
            colors=["U"],
            type_line="Creature",
            cmc=2.0,
            rarity="uncommon",
        ),
        _card("u-manaleak", "Mana Leak", colors=["U"], type_line="Instant", cmc=2.0),
        # --- Mono black (3) ---
        _card("b-ritual", "Dark Ritual", colors=["B"], type_line="Instant", cmc=1.0),
        _card("b-doomblade", "Doom Blade", colors=["B"], type_line="Instant", cmc=2.0),
        _card("b-sign", "Sign in Blood", colors=["B"], type_line="Sorcery", cmc=2.0),
        # --- Mono green (4) ---
        _card("g-llanowar", "Llanowar Elves", colors=["G"], type_line="Creature", cmc=1.0),
        _card("g-growth", "Giant Growth", colors=["G"], type_line="Instant", cmc=1.0),
        _card("g-rampant", "Rampant Growth", colors=["G"], type_line="Sorcery", cmc=2.0),
        _card(
            "g-craterhoof",
            "Craterhoof Behemoth",
            colors=["G"],
            type_line="Creature",
            cmc=8.0,
            rarity="mythic",
        ),
        # --- Multicolor ---
        _card(
            "wu-charm",
            "Azorius Charm",
            colors=["W", "U"],
            type_line="Instant",
            cmc=3.0,
            rarity="uncommon",
        ),
        _card(
            "wub-sentinel",
            "Esper Sentinel",
            colors=["W", "U", "B"],
            type_line="Creature",
            cmc=3.0,
            rarity="mythic",
        ),
        # --- Colorless (2) ---
        _card("c-ornithopter", "Ornithopter", colors=[], type_line="Artifact Creature", cmc=0.0),
        _card("c-solring", "Sol Ring", colors=[], type_line="Artifact", cmc=1.0, rarity="uncommon"),
    ]


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
        for card in _seed_cards():
            session.add(card)
        await session.commit()
        yield session


# --- Single + multi-filter (AC1) ---


async def test_single_filter_colors(session: AsyncSession):
    """colors=['R'] returns every card containing red, as lightweight CardSummary rows."""
    result = await search_cards(session, colors=["R"])

    assert isinstance(result, CardSearchResult)
    assert result.status == "ok"
    assert result.total_count == 8
    assert all(isinstance(c, CardSummary) for c in result.cards)
    assert all("R" in c.colors for c in result.cards)
    # CardSummary is the lightweight projection — heavy detail fields are absent.
    dumped = result.cards[0].model_dump()
    assert "legalities" not in dumped
    assert "image_uris" not in dumped


async def test_multi_filter_and(session: AsyncSession):
    """colors + types + mana_value_max combine with AND logic."""
    result = await search_cards(session, colors=["R"], types=["Creature"], mana_value_max=3)

    assert result.status == "ok"
    assert result.total_count == 4
    names = {c.name for c in result.cards}
    assert names == {"Goblin Raider", "Fire Drake", "Ember Hauler", "Raging Goblin"}
    assert all("Creature" in c.type_line and c.cmc <= 3 for c in result.cards)


# --- color_mode semantics (AC1) ---


async def test_color_mode_any(session: AsyncSession):
    """color_mode='any' returns cards with W OR U (OR logic)."""
    result = await search_cards(session, colors=["W", "U"], color_mode="any")

    assert result.status == "ok"
    assert result.total_count == 9


async def test_color_mode_all(session: AsyncSession):
    """color_mode='all' returns only cards containing BOTH W and U."""
    result = await search_cards(session, colors=["W", "U"], color_mode="all")

    assert result.status == "ok"
    assert result.total_count == 2
    assert {c.name for c in result.cards} == {"Azorius Charm", "Esper Sentinel"}


async def test_color_mode_exact(session: AsyncSession):
    """color_mode='exact' returns only cards whose colors are exactly {W, U}."""
    result = await search_cards(session, colors=["W", "U"], color_mode="exact")

    assert result.status == "ok"
    assert result.total_count == 1
    assert result.cards[0].name == "Azorius Charm"


async def test_color_mode_at_most(session: AsyncSession):
    """color_mode='at_most' returns the {W,U} subset (incl. colorless), excluding B/R/G."""
    result = await search_cards(session, colors=["W", "U"], color_mode="at_most")

    assert result.status == "ok"
    assert result.total_count == 10
    names = {c.name for c in result.cards}
    assert "Esper Sentinel" not in names  # has black
    assert "Goblin Raider" not in names  # red
    assert "Ornithopter" in names  # colorless is a subset of everything


# --- rarity (AC1) ---


async def test_rarity_single(session: AsyncSession):
    """A single rarity value filters case-insensitively."""
    result = await search_cards(session, rarity="mythic")

    assert result.status == "ok"
    assert result.total_count == 3
    assert all(c.rarity == "mythic" for c in result.cards)


async def test_rarity_list_uses_or(session: AsyncSession):
    """A list of rarities uses OR logic (rare OR mythic)."""
    result = await search_cards(session, rarity=["rare", "mythic"])

    assert result.status == "ok"
    assert result.total_count == 7


# --- format filter (AC2) ---


async def test_format_filter_excludes_non_legal(session: AsyncSession):
    """format restricts to legal cards; the modern-only 'Shock' is excluded from standard."""
    result = await search_cards(session, colors=["R"], format="standard")

    assert result.status == "ok"
    assert result.total_count == 7
    assert "Shock" not in {c.name for c in result.cards}


# --- pagination (AC3) ---


async def test_pagination_reports_metadata(session: AsyncSession):
    """Paging the 8 red cards with page_size=5 yields 5 + 3 with correct metadata."""
    page1 = await search_cards(session, colors=["R"], page=1, page_size=5)
    page2 = await search_cards(session, colors=["R"], page=2, page_size=5)

    assert page1.status == "ok"
    assert page1.total_count == 8
    assert page1.total_pages == 2
    assert page1.page == 1
    assert page1.page_size == 5
    assert len(page1.cards) == 5
    assert "page=2" in page1.message  # tells the client how to get more

    assert page2.page == 2
    assert len(page2.cards) == 3

    # The two pages together cover all 8 red cards with no overlap.
    page1_ids = {c.id for c in page1.cards}
    page2_ids = {c.id for c in page2.cards}
    assert page1_ids.isdisjoint(page2_ids)
    assert len(page1_ids | page2_ids) == 8


# --- empty (AC3) ---


async def test_empty_result_is_graceful(session: AsyncSession):
    """A query that matches nothing returns status='empty' (not an exception)."""
    result = await search_cards(session, mana_value_min=99)

    assert result.status == "empty"
    assert result.cards == []
    assert result.total_count == 0
    assert result.message


# --- validation (AC4) ---


async def test_invalid_color_returns_invalid(session: AsyncSession):
    """A bad color code returns status='invalid' naming the bad value (no raise)."""
    result = await search_cards(session, colors=["X"])

    assert result.status == "invalid"
    assert "X" in result.message


async def test_invalid_rarity_returns_invalid(session: AsyncSession):
    """An unknown rarity returns status='invalid'."""
    result = await search_cards(session, rarity="legendary")

    assert result.status == "invalid"
    assert "legendary" in result.message


async def test_invalid_game_returns_invalid(session: AsyncSession):
    """A game outside paper/arena/mtgo returns status='invalid'."""
    result = await search_cards(session, games=["switch"])

    assert result.status == "invalid"
    assert "switch" in result.message


async def test_invalid_mana_range_returns_invalid(session: AsyncSession):
    """mana_value_min > mana_value_max returns status='invalid'."""
    result = await search_cards(session, mana_value_min=5, mana_value_max=2)

    assert result.status == "invalid"


async def test_invalid_page_returns_invalid(session: AsyncSession):
    """page < 1 returns status='invalid' (PaginatedResult has no validators of its own)."""
    result = await search_cards(session, page=0)

    assert result.status == "invalid"

"""The agent and the companion report the same card statistics for the same deck.

One database, one verify deck, two real entry points: ``analyze_mana_curve`` through an in-process
MCP client on ``build_server``, and ``GET /api/deck/{deck_id}`` through ``build_app()``. Both are
compared with each other and with the committed ``ui/src/test-fixtures/deck-statistics.json``,
which the UI's panel test renders — so the tool, the payload and the bars on screen are tied to
one file and cannot drift apart without a red test on one side.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from src.companion.app.main import build_app
from src.data.database import create_engine, create_session_factory, init_database
from src.data.repositories.deck import DeckRepository
from src.mcp_server.server import build_server
from tests.fixtures.card_statistics import VERIFY_ROWS, verify_card_models
from tests.unit.companion.conftest import _lifespan_client, _point_at

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_PATH = _REPO_ROOT / "ui" / "src" / "test-fixtures" / "deck-statistics.json"


@pytest.fixture
async def verify_deck(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Build the verify deck in a real database the companion is pointed at; return its id."""
    db_path = _point_at(monkeypatch, tmp_path / "cards.db")
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    try:
        await init_database(engine)
        async with create_session_factory(engine)() as session:
            session.add_all(verify_card_models())
            await session.commit()
            repo = DeckRepository(session)
            deck = await repo.create_deck(name="Verify Deck", format="commander")
            for card_id, quantity, sideboard, commander in VERIFY_ROWS:
                await repo.add_card_to_deck(
                    deck.id, card_id, quantity, sideboard=sideboard, commander=commander
                )
    finally:
        await engine.dispose()
    return db_path, deck.id


async def _tool_figures(db_path: Path, deck_id: str) -> dict[str, Any]:
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    try:
        server = build_server(session_factory=create_session_factory(engine))
        async with create_connected_server_and_client_session(server) as client:
            result = await client.call_tool("analyze_mana_curve", {"deck_id": deck_id})
    finally:
        await engine.dispose()
    assert result.isError is False
    content = result.structuredContent
    assert content is not None
    assert content["status"] == "ok", content
    return content


async def _payload_statistics(deck_id: str) -> dict[str, Any]:
    async with _lifespan_client(build_app()) as client:
        response = await client.get(f"/api/deck/{deck_id}")
    assert response.status_code == 200, response.text
    statistics: dict[str, Any] = response.json()["statistics"]
    return statistics


def _committed_fixture() -> dict[str, Any]:
    fixture: dict[str, Any] = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    return fixture


async def test_tool_and_payload_report_the_same_figures(verify_deck: tuple[Path, str]) -> None:
    db_path, deck_id = verify_deck
    tool = await _tool_figures(db_path, deck_id)
    statistics = await _payload_statistics(deck_id)

    assert tool["total_lands"] == statistics["land_count"]
    assert tool["total_spells"] == statistics["spell_count"]
    assert list(tool["distribution"].values()) == statistics["curve"]
    assert list(tool["distribution"]) == ["1", "2", "3", "4", "5", "6", "7"]
    assert tool["colour_pips"] == statistics["colour_pips"]


async def test_both_equal_the_committed_ui_fixture(verify_deck: tuple[Path, str]) -> None:
    db_path, deck_id = verify_deck
    tool = await _tool_figures(db_path, deck_id)
    statistics = await _payload_statistics(deck_id)
    fixture = _committed_fixture()

    assert {
        key: tool[key] for key in ("total_lands", "total_spells", "distribution", "colour_pips")
    } == fixture["analyze_mana_curve"]
    assert statistics == fixture["statistics"]


def test_the_committed_fixture_is_the_verify_deck() -> None:
    """The matrix row, by hand: an independent read of what the fixture must say."""
    fixture = _committed_fixture()
    assert fixture["statistics"]["land_count"] == 2
    assert fixture["statistics"]["curve"] == [2, 0, 2, 1, 0, 0, 2]
    pips = {entry["colour"]: entry["count"] for entry in fixture["statistics"]["colour_pips"]}
    assert pips == {"W": 5, "U": 0, "B": 0, "R": 0, "G": 10, "C": 0}

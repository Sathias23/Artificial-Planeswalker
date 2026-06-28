"""Integration tests for the ``view_deck`` helper (render a deck, best-effort open browser).

Exercises the helper directly against a seeded session: the happy path (render +
browser open), render-only mode, an empty deck, and the ``not_found`` guard. The
``database_not_initialized`` guard is covered in test_first_run_data_init.py and the
end-to-end MCP-client wiring in test_mcp_tools.py. ``webbrowser.open`` is monkey-
patched and the temp dir redirected to ``tmp_path`` throughout, so no real browser
launches and nothing leaks into the system temp.
"""

import webbrowser
from pathlib import Path

import pytest

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.mcp_server.tools.deck_management import add_card_to_deck, create_deck
from src.mcp_server.tools.view_deck import view_deck
from src.viewer import present


def _card(card_id: str, name: str) -> CardModel:
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Deals 3 damage.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "legal"},
    )


@pytest.fixture
async def session(tmp_path: Path):
    """File-backed engine + a shared session seeded with one card (no decks)."""
    db_path = tmp_path / "view.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as db_session:
        db_session.add(_card("card-bolt", "Lightning Bolt"))
        await db_session.commit()
        yield db_session
    await engine.dispose()


@pytest.fixture
def no_browser(monkeypatch, tmp_path: Path) -> list[str]:
    """Record webbrowser.open calls (reporting success) and redirect the temp dir."""
    monkeypatch.setattr(present.tempfile, "gettempdir", lambda: str(tmp_path))
    opened: list[str] = []
    monkeypatch.setattr(present.webbrowser, "open", lambda uri: opened.append(uri) or True)
    return opened


async def test_view_deck_ok_opens_browser(session, no_browser: list[str]) -> None:
    created = await create_deck(session, name="Burn")
    deck_id = created.deck.id
    await add_card_to_deck(session, deck_id=deck_id, name="Lightning Bolt", quantity=2)

    result = await view_deck(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.deck_id == deck_id
    assert result.deck_name == "Burn"
    assert result.opened_in_browser is True
    assert result.file_path is not None
    path = Path(result.file_path)
    assert path.exists()
    assert "Burn" in path.read_text(encoding="utf-8")
    assert no_browser == [path.as_uri()]


async def test_view_deck_render_only_skips_browser(session, no_browser: list[str]) -> None:
    created = await create_deck(session, name="No Pop")  # an empty deck is still viewable

    result = await view_deck(session, deck_id=created.deck.id, open_browser=False)

    assert result.status == "ok"
    assert result.opened_in_browser is False
    assert no_browser == []  # browser never invoked
    assert result.file_path is not None
    assert Path(result.file_path).exists()


async def test_view_deck_not_found(session, no_browser: list[str]) -> None:
    result = await view_deck(session, deck_id="does-not-exist")

    assert result.status == "not_found"
    assert "does-not-exist" in result.message
    assert no_browser == []


async def test_view_deck_ok_when_browser_raises(session, monkeypatch, tmp_path: Path) -> None:
    """A host where webbrowser.open *raises* still yields ok — opening is never load-bearing."""
    monkeypatch.setattr(present.tempfile, "gettempdir", lambda: str(tmp_path))

    def _no_browser(uri: str) -> bool:
        raise webbrowser.Error("no usable browser on this host")

    monkeypatch.setattr(present.webbrowser, "open", _no_browser)

    created = await create_deck(session, name="Headless")
    result = await view_deck(session, deck_id=created.deck.id)

    assert result.status == "ok"
    assert result.opened_in_browser is False
    assert result.file_path is not None
    assert Path(result.file_path).exists()


async def test_view_deck_write_failure_is_graceful(
    session, no_browser: list[str], monkeypatch
) -> None:
    """A file-write failure becomes a graceful error status, not a raised exception."""

    def _boom(self: Path, *args: object, **kwargs: object) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _boom)

    created = await create_deck(session, name="Disk Full")
    result = await view_deck(session, deck_id=created.deck.id)

    assert result.status == "error"
    assert no_browser == []  # write fails before any browser attempt

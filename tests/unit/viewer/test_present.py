"""Unit tests for the deck-viewer presentation helper (render -> temp file -> browser).

Isolates :func:`~src.viewer.present.present_deck`'s own responsibility — writing the
rendered HTML to the temp path and best-effort opening it — from the rendering
itself (covered by test_deck_view_model.py): ``render_html`` and ``webbrowser.open``
are monkeypatched, and the temp dir is redirected to ``tmp_path``, so no real browser
launches and no files leak into the system temp.
"""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from src.data.schemas.deck import Deck
from src.viewer import present
from src.viewer.present import deck_viewer_path, present_deck


def _deck(name: str = "Test Deck") -> Deck:
    """A minimal deck — only ``name`` matters once ``render_html`` is patched."""
    now = datetime.now(UTC)
    return Deck(id="d1", name=name, format="standard", created_at=now, updated_at=now)


def test_deck_viewer_path_slugifies_name_and_keys_on_id() -> None:
    deck = _deck("Rakdos Aggro!")
    path = deck_viewer_path(deck)
    assert path.name == f"ap-deck-viewer-rakdos-aggro-{deck.id}.html"
    assert path.parent == Path(tempfile.gettempdir())


def test_deck_viewer_path_falls_back_for_unsluggable_name() -> None:
    deck = _deck("!!!")
    assert deck_viewer_path(deck).name == f"ap-deck-viewer-deck-{deck.id}.html"


def test_present_deck_writes_file_and_opens_browser(monkeypatch, tmp_path: Path) -> None:
    opened: list[str] = []
    monkeypatch.setattr(present.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(present, "render_html", lambda deck: "<html>RENDERED</html>")
    monkeypatch.setattr(present.webbrowser, "open", lambda uri: opened.append(uri) or True)

    path, was_opened = present_deck(_deck("Open Me"))

    assert was_opened is True
    assert path.parent == tmp_path
    assert path.read_text(encoding="utf-8") == "<html>RENDERED</html>"
    assert opened == [path.as_uri()]


def test_present_deck_render_only_skips_browser(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(present.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(present, "render_html", lambda deck: "<html>X</html>")
    monkeypatch.setattr(present.webbrowser, "open", lambda uri: calls.append(uri) or True)

    path, was_opened = present_deck(_deck("Render Only"), open_browser=False)

    assert was_opened is False
    assert calls == []  # browser never invoked
    assert path.exists()

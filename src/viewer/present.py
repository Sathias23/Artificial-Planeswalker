"""Present a rendered deck to the user: deck -> HTML file -> default browser.

The I/O companion to the pure :func:`~src.viewer.render.render_html`. ``render_html``
stays a pure ``deck -> str`` transform; this module owns the side effects — writing
the document to a temp file and (best-effort) opening it in the host's default
browser. Both composition roots — the ``view_deck`` MCP tool and the
``scripts/view_deck.py`` CLI — call :func:`present_deck`, so the temp-path, slug,
and browser-open logic lives in exactly one place.

Opening a browser is a host side effect that only makes sense for the local stdio
bundle (the server runs on the user's own machine). It is therefore best-effort and
never load-bearing: :func:`present_deck` always returns the written file path, so a
headless or remote host degrades to "here is the file" rather than failing.
"""

import tempfile
import webbrowser
from pathlib import Path

from src.data.schemas.deck import Deck
from src.viewer.render import render_html


def _slug(name: str) -> str:
    """Make a filesystem-safe slug from a deck name (ASCII alphanumerics only)."""
    ascii_alnum = "".join(ch if ch.isascii() and ch.isalnum() else "-" for ch in name)
    return ascii_alnum.strip("-").lower() or "deck"


def deck_viewer_path(deck: Deck) -> Path:
    """Return the temp-file path the viewer HTML for ``deck`` is written to.

    Keyed by the unique deck id (alongside a human-readable name slug), so two decks
    whose names slugify identically never collide on the same temp file.
    """
    return Path(tempfile.gettempdir()) / f"ap-deck-viewer-{_slug(deck.name)}-{deck.id}.html"


def present_deck(deck: Deck, *, open_browser: bool = True) -> tuple[Path, bool]:
    """Render ``deck`` to a temp HTML file and optionally open it in the browser.

    Args:
        deck: A deck with ``deck_cards[].card`` populated.
        open_browser: When ``True`` (default), best-effort open the rendered file in
            the host's default browser.

    Returns:
        A ``(path, opened)`` tuple: the written HTML file path, and whether a browser
        was actually launched — always ``False`` when ``open_browser`` is ``False``,
        or when the platform reports no browser could be opened.
    """
    html = render_html(deck)
    path = deck_viewer_path(deck)
    path.write_text(html, encoding="utf-8")
    opened = False
    if open_browser:
        try:
            opened = webbrowser.open(path.as_uri())
        except (webbrowser.Error, OSError):
            # Best-effort only: a headless/remote host with no usable browser (open may
            # raise, not just return False) must not turn a successful render into a
            # failure — the written file path is still returned.
            opened = False
    return path, opened

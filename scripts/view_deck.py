#!/usr/bin/env python3
"""Open the read-only deck viewer for a nominated deck.

Composition root for the ``src/viewer`` feature: loads a deck from the database
(by id or name), hands it to the pure :func:`~src.viewer.render.render_html`
renderer, writes the result to a temp file, and opens it in the default browser.
On command, Claude Code runs this to view any deck. A deck id or name is
required — there is no implicit "current" deck (the MCP architecture keeps no
server-side active-deck state).

Run with:
    # By name (case-insensitive partial match):
    uv run python scripts/view_deck.py --deck "Rakdos Aggro"

    # By id:
    uv run python scripts/view_deck.py --deck 408512ff-1911-4194-976e-96c911699e46

    # Render only (skip opening a browser); prints the file path:
    uv run python scripts/view_deck.py --deck "Faerie" --no-open
"""

import argparse
import asyncio
import logging
import sys
import tempfile
import webbrowser
from pathlib import Path

from src.data.database import create_engine, create_session_factory
from src.data.repositories.deck import DeckRepository
from src.data.schemas.deck import Deck
from src.viewer import render_html

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def _resolve_deck(repo: DeckRepository, identifier: str) -> Deck | None:
    """Resolve a deck by id first, then by name.

    Tries an exact id match, then an exact (case-insensitive) name match, then a
    unique case-insensitive substring match. Ambiguous or absent matches log a
    helpful message and return ``None`` rather than silently opening the wrong
    deck (``find_deck_by_name`` is avoided because it raises on multiple matches).

    Args:
        repo: The deck repository.
        identifier: A deck id (UUID) or a (partial) name.

    Returns:
        The deck with cards eagerly loaded, or ``None`` if not uniquely resolved.
    """
    by_id = await repo.get_deck_with_cards(identifier)
    if by_id is not None:
        return by_id

    decks = await repo.list_decks()  # eager-loads deck_cards
    needle = identifier.lower()
    exact = [d for d in decks if d.name.lower() == needle]
    matches = exact or [d for d in decks if needle in d.name.lower()]

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        logger.error("%r is ambiguous — it matches multiple decks:", identifier)
        for d in matches:
            logger.error("  - %s", d.name)
        return None

    logger.error("No deck matched %r.", identifier)
    if decks:
        logger.error("Available decks:")
        for d in decks:
            logger.error("  - %s", d.name)
    else:
        logger.error("No decks exist yet. Create one first.")
    return None


def _slug(name: str) -> str:
    """Make a filesystem-safe slug from a deck name."""
    return "".join(ch if ch.isalnum() else "-" for ch in name).strip("-").lower() or "deck"


async def _run(identifier: str, open_browser: bool) -> int:
    """Load, render, and (optionally) open the viewer. Returns an exit code."""
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            repo = DeckRepository(session)
            deck = await _resolve_deck(repo, identifier)
            if deck is None:
                return 1  # _resolve_deck already logged why
            html = render_html(deck)
    finally:
        await engine.dispose()

    out_path = Path(tempfile.gettempdir()) / f"ap-deck-viewer-{_slug(deck.name)}.html"
    out_path.write_text(html, encoding="utf-8")
    logger.info("Rendered %s -> %s", deck.name, out_path)
    if open_browser:
        webbrowser.open(out_path.as_uri())
    return 0


def main() -> int:
    """Parse arguments and run the viewer. Returns a process exit code."""
    parser = argparse.ArgumentParser(description="Open the read-only deck viewer for a deck.")
    parser.add_argument("--deck", required=True, help="Deck id (UUID) or (partial) name.")
    parser.add_argument(
        "--no-open", action="store_true", help="Render the file but do not open a browser."
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.deck, open_browser=not args.no_open))


if __name__ == "__main__":
    sys.exit(main())

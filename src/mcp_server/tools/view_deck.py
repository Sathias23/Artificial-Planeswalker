"""Structured deck-viewer logic for the ``view_deck`` MCP tool.

Loads a saved deck by id and hands it to the read-only viewer: the pure
:func:`~src.viewer.render.render_html` renderer produces a self-contained HTML page,
and the shared :func:`~src.viewer.present.present_deck` helper writes it to a temp
file and best-effort opens it in the host's default browser (the bundle runs as a
local stdio server on the user's own machine). Browser-open is never load-bearing —
``file_path`` is always returned — so a headless/remote host degrades gracefully
instead of failing.

Stateless (D5): the deck is the client-supplied ``deck_id`` on every call. Mirrors
the other deck tools — guards an un-imported database with
``database_not_initialized`` and converts a repository ``DatabaseError`` into a
graceful ``error`` status rather than raising to the MCP client.
"""

import asyncio
import logging
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.deck import DeckRepository
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE
from src.viewer import present_deck

logger = logging.getLogger(__name__)


class ViewDeckResult(BaseModel):
    """Structured result of ``view_deck``.

    Attributes:
        status: ``ok`` (rendered — see ``file_path``), ``not_found`` (no such deck),
            ``error`` (a database error), or ``database_not_initialized``.
        deck_id: The viewed deck's id (when ``status == "ok"``).
        deck_name: The viewed deck's name (when ``status == "ok"``).
        file_path: Absolute path to the rendered HTML file — always set on ``ok``,
            even when no browser was opened.
        opened_in_browser: Whether a browser was actually launched.
        message: Human-facing summary.
    """

    status: Literal["ok", "not_found", "error", "database_not_initialized"]
    deck_id: str | None = None
    deck_name: str | None = None
    file_path: str | None = None
    opened_in_browser: bool = False
    message: str


async def view_deck(
    session: AsyncSession, *, deck_id: str, open_browser: bool = True
) -> ViewDeckResult:
    """Render a saved deck to HTML and (optionally) open it in the browser.

    Args:
        session: Async database session to read the deck through.
        deck_id: The id of the deck to view (from ``create_deck`` / ``list_decks``).
        open_browser: When ``True`` (default), best-effort open the rendered file in
            the host's default browser; the path is returned regardless.

    Returns:
        A ``ViewDeckResult``. A missing deck yields ``not_found``; an un-imported
        database yields ``database_not_initialized``; a database error yields a
        graceful ``error`` (never raised to the client).
    """
    if not await is_database_initialized(session):
        return ViewDeckResult(
            status="database_not_initialized", message=DATABASE_NOT_INITIALIZED_MESSAGE
        )

    repo = DeckRepository(session)
    try:
        deck = await repo.get_deck_with_cards(deck_id)
    except DatabaseError:
        logger.exception("view_deck failed for deck_id=%s", deck_id)
        return ViewDeckResult(status="error", message="A database error occurred loading the deck.")

    if deck is None:
        return ViewDeckResult(status="not_found", message=f"No deck found with id '{deck_id}'.")

    # Offload the sync file-write + webbrowser.open (which spawns the OS browser
    # handler) off the FastMCP event loop so the tool never blocks it. A browser that
    # cannot open is already swallowed inside present_deck; a file-write failure (OSError)
    # is converted here to a graceful error so nothing raises to the MCP client.
    try:
        path, opened = await asyncio.to_thread(present_deck, deck, open_browser=open_browser)
    except OSError:
        logger.exception("view_deck failed to write the viewer file for deck_id=%s", deck_id)
        return ViewDeckResult(
            status="error",
            message="The deck rendered, but its viewer file could not be written.",
        )

    where = "opened in your browser" if opened else "ready to open"
    return ViewDeckResult(
        status="ok",
        deck_id=deck.id,
        deck_name=deck.name,
        file_path=str(path),
        opened_in_browser=opened,
        message=f"Rendered deck '{deck.name}' — {where}: {path}",
    )

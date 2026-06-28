"""``initialize_database`` MCP tool: in-client, one-time Scryfall card import (build-on-first-run).

A fresh MCPB / Claude Desktop install ships no card data by design (the Scryfall/WotC license means
the bundle carries no DB). This tool is the in-client bootstrap: it creates the schema and imports
the ``oracle_cards`` bulk set into the shared central data directory, so the card/deck tools start
working. It is **explicit and consent-gated** — the assistant calls it on the user's behalf; it
never runs on startup or from another tool — and **idempotent**: if the ``cards`` table is already
populated it reports ``already_initialized`` and re-downloads nothing. Building the semantic index
is a separate, optional step (``build_search_index``).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import (
    create_engine,
    create_session_factory,
    init_database,
    is_database_initialized,
)
from src.data.importers.importer import ImportStatistics
from src.data.importers.scryfall import import_scryfall_bulk_data

logger = logging.getLogger(__name__)

#: Default Scryfall bulk set — unique by oracle id, smaller/faster than ``default_cards``; the same
#: set ``setup.py`` imports.
_DEFAULT_BULK_TYPE = "oracle_cards"

#: The import seam: ``(session, bulk_type=...) -> ImportStatistics``. Defaults to the real Scryfall
#: importer; tests inject a fake that inserts a few cards with no network/download.
ImportFn = Callable[..., Awaitable[ImportStatistics]]


class InitializeDatabaseResult(BaseModel):
    """Structured result of ``initialize_database``.

    Attributes:
        status: ``ok`` (cards imported on this run), ``already_initialized`` (cards were already
            present — nothing downloaded), or ``error`` (the import failed; ``message`` explains).
        cards_imported: Cards inserted on this run (``0`` for ``already_initialized`` / ``error``).
        cards_total: Total cards in the database after this run.
        message: Human-facing summary, including the next step (build the index) on success.
    """

    status: Literal["ok", "already_initialized", "error"]
    cards_imported: int = 0
    cards_total: int = 0
    message: str


async def _card_count(session: AsyncSession) -> int:
    """Return the number of rows in the ``cards`` table."""
    return int((await session.execute(text("SELECT count(*) FROM cards"))).scalar() or 0)


async def _clear_cards(session: AsyncSession) -> None:
    """Remove any partially-imported rows so a failed import can be retried from a clean state."""
    await session.rollback()  # discard the importer's failed in-flight transaction first
    await session.execute(text("DELETE FROM cards"))
    await session.commit()


async def initialize_database(
    *,
    import_fn: ImportFn | None = None,
    bulk_type: str = _DEFAULT_BULK_TYPE,
) -> InitializeDatabaseResult:
    """Create the schema and import Scryfall card data when the database is empty.

    Self-contained (mirrors ``setup.py::initialize_database``): it manages its own async engine so
    it does not depend on server wiring, and disposes it before returning. Idempotent — skips the
    import when ``cards`` is already populated.

    Args:
        import_fn: Test seam for the importer; defaults to the real
            :func:`~src.data.importers.scryfall.import_scryfall_bulk_data`.
        bulk_type: Scryfall bulk set to import (default ``"oracle_cards"``).

    Returns:
        An :class:`InitializeDatabaseResult`. Any schema-creation or import failure is caught and
        returned as ``status="error"`` rather than raised to the MCP client; a partial import is
        rolled back so a retry starts from a clean empty database.
    """
    importer: ImportFn = import_fn or import_scryfall_bulk_data
    engine = create_engine()
    try:
        try:
            # create_all is idempotent — makes a fresh DB usable without clobbering existing data.
            await init_database(engine)
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                if await is_database_initialized(session):
                    total = await _card_count(session)
                    return InitializeDatabaseResult(
                        status="already_initialized",
                        cards_total=total,
                        message=(
                            f"The card database is already set up ({total:,} cards). "
                            "Run `build_search_index` if you want semantic search too."
                        ),
                    )
                try:
                    stats = await importer(session, bulk_type=bulk_type)
                except Exception:
                    # The importer commits per batch, so a mid-import failure leaves a partial
                    # ``cards`` table that the >=1-row idempotency check would later mistake for a
                    # complete import. Clear it so a retry re-imports from a clean empty DB.
                    await _clear_cards(session)
                    raise
                total = await _card_count(session)
                return InitializeDatabaseResult(
                    status="ok",
                    cards_imported=stats.total_inserted,
                    cards_total=total,
                    message=(
                        f"Imported {stats.total_inserted:,} cards ({total:,} total). Card and deck "
                        "tools are ready. To enable semantic search (`semantic_search_cards` / "
                        "`find_similar_cards`), ask me to run `build_search_index` next."
                    ),
                )
        except Exception as exc:
            logger.exception("initialize_database failed")
            return InitializeDatabaseResult(
                status="error",
                message=(
                    f"Database initialization failed: {exc}. Check the connection and try again."
                ),
            )
    finally:
        await engine.dispose()

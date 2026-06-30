"""``initialize_database`` MCP tool: in-client Scryfall card import (build-on-first-run + updates).

A fresh MCPB / Claude Desktop install ships no card data by design (the Scryfall/WotC license means
the bundle carries no DB). This tool is the in-client bootstrap: it creates the schema and imports
the ``oracle_cards`` bulk set into the shared central data directory, so the card/deck tools start
working. It is **explicit and consent-gated** — the assistant calls it on the user's behalf; it
never runs on startup or from another tool — and **idempotent**: if the ``cards`` table is already
populated it reports ``already_initialized`` and re-downloads nothing.

The same tool also keeps the database current. When a new set releases, calling it with
``update=True`` re-downloads the latest ``oracle_cards`` set and **upserts** it (the importer's
``INSERT ... ON CONFLICT DO UPDATE``): new cards are added and existing rows refreshed (errata,
banlist/legality changes), without wiping the user's existing data. Building the semantic index is a
separate, optional step (``build_search_index``) — re-run it after an update to index the new cards.
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
        status: ``ok`` (first-run import — cards imported into an empty DB), ``updated`` (an
            ``update=True`` run refreshed an already-populated DB), ``already_initialized`` (cards
            were already present and ``update`` was not requested — nothing downloaded), or
            ``error`` (the import failed; ``message`` explains).
        cards_imported: On ``ok``, the cards inserted on this run; on ``updated``, the number of
            *new* cards added (existing rows are also refreshed in place). ``0`` for
            ``already_initialized`` / ``error``.
        cards_total: Total cards in the database after this run.
        message: Human-facing summary, including the next step (build the index) on success.
    """

    status: Literal["ok", "updated", "already_initialized", "error"]
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
    update: bool = False,
) -> InitializeDatabaseResult:
    """Create the schema and import (or update) Scryfall card data.

    Self-contained (mirrors ``setup.py::initialize_database``): it manages its own async engine so
    it does not depend on server wiring, and disposes it before returning.

    Two modes:

    * **First-run / idempotent** (``update=False``, the default): import the cards when ``cards`` is
      empty; if it is already populated, skip the download and report ``already_initialized``.
    * **Update** (``update=True``): re-download and upsert the latest set even when ``cards`` is
      already populated, so newly released cards are added and existing rows refreshed. The import
      is an upsert (``INSERT ... ON CONFLICT DO UPDATE``), so it never drops existing rows.

    Args:
        import_fn: Test seam for the importer; defaults to the real
            :func:`~src.data.importers.scryfall.import_scryfall_bulk_data`.
        bulk_type: Scryfall bulk set to import (default ``"oracle_cards"``).
        update: When ``True``, refresh an already-populated database (pull in new sets) instead of
            short-circuiting with ``already_initialized``. No effect on an empty database — that is
            always a first-run import.

    Returns:
        An :class:`InitializeDatabaseResult`. Any schema-creation or import failure is caught and
        returned as ``status="error"`` rather than raised to the MCP client. A failed **first-run**
        import is rolled back so a retry starts from a clean empty database; a failed **update**
        leaves the existing (already-populated) data intact — an upsert that partially completed
        loses nothing.
    """
    importer: ImportFn = import_fn or import_scryfall_bulk_data
    engine = create_engine()
    try:
        try:
            # create_all is idempotent — makes a fresh DB usable without clobbering existing data.
            await init_database(engine)
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                already_populated = await is_database_initialized(session)
                if already_populated and not update:
                    total = await _card_count(session)
                    return InitializeDatabaseResult(
                        status="already_initialized",
                        cards_total=total,
                        message=(
                            f"The card database is already set up ({total:,} cards). To pull in "
                            "newly released sets, run this again with `update=true`. Run "
                            "`build_search_index` if you want semantic search too."
                        ),
                    )
                cards_before = await _card_count(session)
                try:
                    stats = await importer(session, bulk_type=bulk_type)
                except Exception:
                    # The importer commits per batch. On a *first run* a mid-import failure leaves
                    # a partial ``cards`` table that the >=1-row idempotency check would later
                    # mistake for a complete import, so clear it for a clean retry. On an *update*
                    # the DB was already populated and the importer only upserts — a partial failure
                    # drops no rows, so never wipe the user's existing cards.
                    if cards_before == 0:
                        await _clear_cards(session)
                    raise
                total = await _card_count(session)
                if already_populated:
                    added = total - cards_before
                    return InitializeDatabaseResult(
                        status="updated",
                        cards_imported=added,
                        cards_total=total,
                        message=(
                            f"Card database updated: {added:,} new card(s) added and existing "
                            f"cards refreshed ({total:,} total). If you use semantic search, "
                            "re-run `build_search_index` to index the new cards."
                        ),
                    )
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

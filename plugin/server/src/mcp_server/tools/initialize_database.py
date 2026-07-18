"""``initialize_database`` MCP tool: in-client Scryfall card import (build-on-first-run + updates).

A fresh plugin / Claude Desktop install ships no card data by design (the Scryfall/WotC license
means the package carries no DB). This tool is the in-client bootstrap: it creates the schema and
imports the ``default_cards`` bulk set (~500 MB download) into the shared central data directory,
so the card/deck tools start working. The importer deduplicates to **one row per oracle identity**
and stores ``games`` as the **union across all printings**, so Arena/MTGO availability is never
masked by a paper-only representative printing. It is **explicit and consent-gated** — the
assistant calls it on the user's behalf; it never runs on startup or from another tool — and
**idempotent**: if the ``cards`` table is already populated it reports ``already_initialized`` and
re-downloads nothing.

The same tool also keeps the database current. When a new set releases, calling it with
``update=True`` re-downloads the latest ``default_cards`` set and **upserts** it (the importer's
``INSERT ... ON CONFLICT DO UPDATE``): new cards are added, existing rows refreshed (errata,
banlist/legality changes), and a final reconcile pass collapses duplicates left by older imports —
stale printing rows are **removed**, deck references are repointed to the surviving canonical row
(user decks are preserved), and ``games`` is rewritten to the cross-printing union. Building the
semantic index is a separate, optional step (``build_search_index``) — re-run it after an update to
index the new cards (with ``prune=true`` when the reconcile removed rows, so their vectors go too).
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

#: Default Scryfall bulk set — every printing (~500 MB download); the importer deduplicates to one
#: row per oracle identity with union-of-printings ``games``. The same set ``setup.py`` imports.
_DEFAULT_BULK_TYPE = "default_cards"

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
            *new* cards added (existing rows are also refreshed in place), clamped at ``0`` —
            the reconcile can delete more stale duplicate rows than the update adds. ``0`` for
            ``already_initialized`` / ``error``.
        cards_total: Total cards in the database after this run.
        message: Human-facing summary, including the next step (build the index) on success.
    """

    status: Literal["ok", "updated", "already_initialized", "error"]
    cards_imported: int = 0
    cards_total: int = 0
    message: str


#: How many reject identities to name in the result message (the full list is in the logs).
_REJECT_SAMPLE_SIZE = 5


def _import_notes(stats: ImportStatistics) -> str:
    """Diagnostics suffix for a successful import: rejects, reconcile outcome, stale warning.

    Args:
        stats: The importer's statistics for this run.

    Returns:
        An empty string when the run was clean; otherwise sentences (leading space
        included) naming the reject count, up to five sample card names, rows removed
        by the reconcile, and warnings when the reconcile failed or skipped identities.
    """
    notes = ""
    if stats.total_errors > 0:
        notes += f" {stats.total_errors} card(s) could not be imported"
        sample = [reject.identity for reject in stats.rejects[:_REJECT_SAMPLE_SIZE]]
        if sample:
            notes += f" (e.g. {', '.join(sample)})"
        notes += "."
    if stats.reconcile.failed:
        notes += (
            " Warning: the reconcile stage failed - stale duplicates may remain; "
            "run this again with `update=true` to retry."
        )
    if stats.reconcile.rows_deleted > 0:
        notes += (
            f" Removed {stats.reconcile.rows_deleted:,} stale duplicate row(s) during reconcile."
        )
    if stats.reconcile.stale_remaining > 0:
        count = stats.reconcile.stale_remaining
        noun = "identity" if count == 1 else "identities"
        notes += (
            f" Warning: {count} oracle {noun} kept pre-existing rows because their "
            "current printing was rejected this run; a later `update=true` run will retry."
        )
    return notes


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
        bulk_type: Scryfall bulk set to import (default ``"default_cards"`` — deduplicated to
            one row per oracle identity with union-of-printings ``games``).
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
                    # The reconcile deletes stale duplicate rows, so the net change can be
                    # negative — clamp; _import_notes names the deletions that explain it.
                    added = max(0, total - cards_before)
                    if stats.reconcile.rows_deleted > 0:
                        index_hint = (
                            " If you use semantic search, re-run `build_search_index` with "
                            "`prune=true` to index the new cards and drop the vectors of "
                            "the removed rows."
                        )
                    else:
                        index_hint = (
                            " If you use semantic search, re-run `build_search_index` to "
                            "index the new cards."
                        )
                    return InitializeDatabaseResult(
                        status="updated",
                        cards_imported=added,
                        cards_total=total,
                        message=(
                            f"Card database updated: {added:,} new card(s) added and existing "
                            f"cards refreshed ({total:,} total)."
                            f"{_import_notes(stats)}"
                            f"{index_hint}"
                        ),
                    )
                return InitializeDatabaseResult(
                    status="ok",
                    cards_imported=stats.total_inserted,
                    cards_total=total,
                    message=(
                        f"Imported {stats.total_inserted:,} cards ({total:,} total)."
                        f"{_import_notes(stats)}"
                        " Card and deck "
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

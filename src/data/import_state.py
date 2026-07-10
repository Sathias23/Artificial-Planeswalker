"""First-run import-completion marker.

The card importer commits per 1,000-card batch (to bound transaction size and lock
duration), so a **hard process kill** between batches leaves a partial ``cards`` table on
disk — say 1,000 of ~30,000 rows. A plain "``cards`` has ≥1 row" idempotency check would then
mistake that truncated database for a complete import and refuse to retry, permanently.

To tell "complete" from "killed mid-import" apart, a first-run import writes a durable
**in-progress marker** in its own committed transaction *before* the first batch commits, and
clears it only *after* the whole import (including reconcile) finishes. A crash therefore leaves
``in_progress = 1`` on disk, and the initialization checks treat the database as not-yet-ready so
the next run re-imports (the upsert cleans up the partial rows).

The marker is only managed for **first-run / resumed** imports — never for an ``update=True``
refresh of an already-complete database, which stays fully usable throughout its upsert. Legacy
databases imported before this marker existed have no ``import_state`` table at all, which reads as
"not in progress" — so they are never misclassified as partial.
"""

import sqlite3

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Single-row table (``id`` pinned to 1) holding the first-run import-completion flag.
_TABLE = "import_state"

_CREATE = text(
    f"CREATE TABLE IF NOT EXISTS {_TABLE} "
    "(id INTEGER PRIMARY KEY CHECK (id = 1), in_progress INTEGER NOT NULL)"
)
_UPSERT = text(
    f"INSERT INTO {_TABLE} (id, in_progress) VALUES (1, :flag) "
    "ON CONFLICT(id) DO UPDATE SET in_progress = excluded.in_progress"
)
_SELECT = text(f"SELECT in_progress FROM {_TABLE} WHERE id = 1")
_TABLE_EXISTS = text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'import_state'")


async def _set_in_progress(session: AsyncSession, flag: bool) -> None:
    """Create the marker table if needed and set the single row's flag, committed on its own."""
    await session.execute(_CREATE)
    await session.execute(_UPSERT, {"flag": 1 if flag else 0})
    await session.commit()


async def mark_import_started(session: AsyncSession) -> None:
    """Durably record that a first-run import is underway (survives a process kill)."""
    await _set_in_progress(session, True)


async def mark_import_finished(session: AsyncSession) -> None:
    """Durably record that the first-run import completed — the database is now trustworthy."""
    await _set_in_progress(session, False)


async def is_import_in_progress(session: AsyncSession) -> bool:
    """Return whether a first-run import was started but never finished (partial database).

    Returns ``False`` when the ``import_state`` table is absent — the state of every database
    imported before this marker existed, and of a fresh empty database — so a complete legacy
    database is never mistaken for a partial one.
    """
    if (await session.execute(_TABLE_EXISTS)).first() is None:
        return False
    return bool((await session.execute(_SELECT)).scalar())


def is_import_in_progress_sync(conn: sqlite3.Connection) -> bool:
    """Sync counterpart of :func:`is_import_in_progress` for the sqlite-vec tools' connection."""
    if conn.execute(str(_TABLE_EXISTS)).fetchone() is None:
        return False
    row = conn.execute(str(_SELECT)).fetchone()
    return bool(row[0]) if row else False

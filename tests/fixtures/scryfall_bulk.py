"""A stand-in for Scryfall's network seams, so a test runs the real import orchestrator offline.

:func:`~src.data.importers.scryfall.import_scryfall_bulk_data` talks to the network at exactly two
seams: the bulk-data metadata call and the file download. :func:`serve_bulk_file` replaces both and
leaves every later stage real (pass 1 off the loop, the first-run marker, the batched upsert, the
reconcile and the temp-file cleanup), which is what an end-to-end import test has to exercise.
Copying those stages into a test helper instead let their wiring break unnoticed (review finding
T1-1-P1).
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.importers.importer import ImportStatistics
from src.data.importers.scryfall import import_scryfall_bulk_data

#: The bulk type :func:`serve_bulk_file` advertises unless told otherwise.
DEFAULT_BULK_TYPE = "default_cards"


def serve_bulk_file(
    monkeypatch: pytest.MonkeyPatch,
    printings: list[dict[str, Any]],
    *,
    bulk_type: str = DEFAULT_BULK_TYPE,
) -> None:
    """Make the orchestrator's metadata call list *bulk_type* and its download write *printings*.

    The payload is a JSON array (``stream_cards`` reads the bytes to decide the format, so the
    array shape is as real as the live JSONL one). Calling this again in the same test replaces the
    payload, which is how a test imports a second snapshot over the same database.

    Args:
        monkeypatch: The test's monkeypatch; the stand-ins are undone at teardown.
        printings: Raw Scryfall card objects, as the bulk file carries them.
        bulk_type: The one bulk type the metadata call advertises.
    """
    payload = json.dumps(printings)

    async def fake_fetch_bulk_data_list() -> list[dict[str, Any]]:
        return [
            {
                "type": bulk_type,
                "download_uri": f"https://data.scryfall.io/{bulk_type}.json",
                "size": len(payload),
            }
        ]

    async def fake_download(uri: str, output_file: Path, max_bytes: int = 0) -> Path:
        output_file.write_text(payload, encoding="utf-8")
        return output_file

    monkeypatch.setattr(
        "src.data.importers.scryfall.fetch_bulk_data_list", fake_fetch_bulk_data_list
    )
    monkeypatch.setattr("src.data.importers.scryfall.download_bulk_data", fake_download)


async def import_through_orchestrator(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    printings: list[dict[str, Any]],
    *,
    temp_dir: Path,
) -> ImportStatistics:
    """Serve *printings* and run the real :func:`import_scryfall_bulk_data` over them.

    Args:
        session: The session the import writes through.
        monkeypatch: The test's monkeypatch, for :func:`serve_bulk_file`.
        printings: Raw Scryfall card objects, as the bulk file carries them.
        temp_dir: The caller-owned download directory (the test's ``tmp_path``), so nothing lands
            in the shared temp root.

    Returns:
        The orchestrator's own statistics, ``reconcile`` included.
    """
    serve_bulk_file(monkeypatch, printings)
    return await import_scryfall_bulk_data(session, bulk_type=DEFAULT_BULK_TYPE, temp_dir=temp_dir)

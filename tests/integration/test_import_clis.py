"""The two import CLIs write the database the server reads (``scripts/import_*.py``).

Both CLIs defaulted to ``src.paths.database_path()`` — ``cards.db`` in the data dir — while the
server opens ``src.paths.database_url()``, which an exported ``CARDS_DATABASE_URL`` outranks. With
the URL set, a "refresh" therefore imported into a file the server never reads and reported
success. These tests drive each CLI's real ``main()`` with its importer stubbed (no network), and
assert on the files that exist afterwards: the target is written, the data dir is not.

Every test isolates both ``PLANESWALKER_DATA_DIR`` and ``CARDS_DATABASE_URL``, so nothing here can
reach the developer's real data dir.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pytest

import scripts.import_scryfall_data as scryfall_cli
import scripts.import_spellbook_combos as spellbook_cli
from src.data.importers.importer import ImportStatistics
from src.data.importers.spellbook import SpellbookImportStats


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated data dir, with no URL exported unless a test sets one."""
    data = tmp_path / "data"
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(data))
    monkeypatch.delenv("CARDS_DATABASE_URL", raising=False)
    return data


@pytest.fixture
def stubbed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace both importers with stubs that record the file their session is bound to."""
    bound: list[str] = []

    async def fake_scryfall(session: Any, bulk_type: str, temp_dir: Path | None) -> Any:
        bound.append(str(session.get_bind().url.database))
        return ImportStatistics()

    async def fake_spellbook(session: Any, *, temp_dir: Path | None = None) -> Any:
        bound.append(str(session.get_bind().url.database))
        return SpellbookImportStats()

    monkeypatch.setattr(scryfall_cli, "import_scryfall_bulk_data", fake_scryfall)
    monkeypatch.setattr(spellbook_cli, "import_spellbook_snapshot", fake_spellbook)
    return bound


CLIS = [
    pytest.param(scryfall_cli, id="scryfall"),
    pytest.param(spellbook_cli, id="spellbook"),
]


async def _main(module: Any, monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", [f"{module.__name__}.py", *argv])
    result: int = await module.main()
    return result


@pytest.mark.parametrize("module", CLIS)
async def test_an_exported_url_is_the_file_written(
    module: Any,
    data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stubbed: list[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``CARDS_DATABASE_URL`` names the file the server opens, so it is the one imported into."""
    other = tmp_path / "other" / "cards.db"
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{other.as_posix()}")

    with caplog.at_level(logging.INFO, logger=module.__name__):
        assert await _main(module, monkeypatch) == 0

    assert other.is_file(), "the URL's file was not written"
    assert not (data_dir / "cards.db").exists(), "the import wrote the data dir's cards.db"
    assert [Path(p) for p in stubbed] == [other]
    assert f"Database path: {other}" in caplog.text


@pytest.mark.parametrize("module", CLIS)
async def test_an_explicit_db_path_beats_the_url(
    module: Any,
    data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stubbed: list[str],
) -> None:
    """``--db-path`` is the operator's explicit choice and outranks the environment."""
    other = tmp_path / "other" / "cards.db"
    explicit = tmp_path / "explicit" / "cards.db"
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{other.as_posix()}")

    assert await _main(module, monkeypatch, "--db-path", str(explicit)) == 0

    assert explicit.is_file()
    assert not other.exists()
    assert not (data_dir / "cards.db").exists()
    assert [Path(p) for p in stubbed] == [explicit]


@pytest.mark.parametrize("module", CLIS)
async def test_the_twin_with_no_url_writes_the_data_dir(
    module: Any, data_dir: Path, monkeypatch: pytest.MonkeyPatch, stubbed: list[str]
) -> None:
    """No URL and no ``--db-path``: the data dir's ``cards.db``, the server's default."""
    assert await _main(module, monkeypatch) == 0

    assert (data_dir / "cards.db").is_file()
    assert [Path(p) for p in stubbed] == [data_dir / "cards.db"]

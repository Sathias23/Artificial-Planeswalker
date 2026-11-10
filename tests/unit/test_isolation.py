"""Pins the root ``isolated_data_dir`` fixture: no test resolves the developer's real data.

Deleting or weakening the fixture in ``tests/conftest.py`` turns these red instead of letting the
suite quietly read a stale ``companion.json`` or write the operator's ``cards.db``.
"""

import os
from pathlib import Path

from src import paths
from tests.fixtures.real_data import MODEL_CACHE_DIR


def test_data_dir_resolves_to_this_tests_tmp_path(tmp_path: Path) -> None:
    assert paths.data_dir() == tmp_path
    assert Path(paths.database_file()) == tmp_path / "cards.db"


def test_the_fixture_returns_the_same_directory(isolated_data_dir: Path, tmp_path: Path) -> None:
    assert isolated_data_dir == tmp_path


def test_no_database_url_reaches_a_test() -> None:
    assert "CARDS_DATABASE_URL" not in os.environ


def test_the_model_cache_is_pinned_to_the_persistent_one(tmp_path: Path) -> None:
    cache = Path(os.environ["FASTEMBED_CACHE_DIR"])
    assert cache == MODEL_CACHE_DIR
    assert not cache.is_relative_to(tmp_path)

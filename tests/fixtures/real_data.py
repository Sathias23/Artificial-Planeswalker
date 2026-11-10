"""Where the developer's real data lives, read once at import and never created.

The root ``isolated_data_dir`` fixture points every test at its own ``tmp_path``, so by the time a
test body runs, ``src.paths`` no longer resolves the developer's directories. Two things still need
them, and this module is the one place they are named:

* the fastembed model cache, pinned (not isolated) because the ~80 MB ONNX model is a download
  cache rather than operator data, and AGENTS.md requires a persistent path for it;
* the real ``cards.db``, which the assessment benchmark opens read-only and immutable.

Both are snapshotted from the environment at import, before any fixture patches it. Nothing here
calls :func:`src.paths.data_dir`, which creates the directory it returns.
"""

import os
from pathlib import Path

from platformdirs import user_data_dir

from src.paths import sqlite_file_from_url

_APP = "artificial-planeswalker"


def _real_data_dir() -> Path:
    """Return the developer's data dir the way ``src.paths.data_dir`` resolves it, without mkdir."""
    override = (os.getenv("PLANESWALKER_DATA_DIR") or "").strip()
    if override:
        base = Path(override).expanduser()
        return base if base.is_absolute() else base.resolve()
    return Path(user_data_dir(_APP, appauthor=False))


def _model_cache_dir() -> Path:
    explicit = (os.getenv("FASTEMBED_CACHE_DIR") or "").strip()
    return Path(explicit) if explicit else _real_data_dir() / "fastembed_cache"


def _real_database_file() -> Path:
    explicit = (os.getenv("CARDS_DATABASE_URL") or "").strip()
    return Path(sqlite_file_from_url(explicit)) if explicit else _real_data_dir() / "cards.db"


MODEL_CACHE_DIR: Path = _model_cache_dir()
"""The persistent fastembed model cache every test is pinned to (it may not exist yet)."""

REAL_DATABASE_FILE: Path = _real_database_file()
"""The developer's card database. Only the assessment benchmark reads it, read-only."""

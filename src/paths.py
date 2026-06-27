"""Central, OS-appropriate data paths shared by the DB engine, search layer, and embedder.

A **leaf** module: it imports nothing from ``src`` so every layer (``data`` / ``search`` /
``mcp_server``) can use it without breaking the ``data -> logic -> mcp_server`` import direction.

Resolution precedence (highest first):

1. An explicit argument from the caller (tests pin a ``tmp_path``) — handled in the consuming
   modules, not here.
2. A dedicated env var: ``PLANESWALKER_DATA_DIR`` for the whole data dir, or the long-standing
   ``CARDS_DATABASE_URL`` / ``FASTEMBED_CACHE_DIR`` for the DB URL / model cache (back-compat).
3. The central OS data directory below (the new default), shared across every MCP client.
"""

import os
from pathlib import Path

from platformdirs import user_data_dir

_APP = "artificial-planeswalker"


def data_dir() -> Path:
    """Return the shared, OS-appropriate data directory, creating it if absent.

    Override the whole location with the ``PLANESWALKER_DATA_DIR`` env var (a relative value is
    resolved to an absolute path so the sync factory and async engine never disagree). Otherwise
    the platform-standard per-user data directory is used:

    * Windows: ``%LOCALAPPDATA%\\artificial-planeswalker``
    * macOS:   ``~/Library/Application Support/artificial-planeswalker``
    * Linux:   ``~/.local/share/artificial-planeswalker`` (honours ``XDG_DATA_HOME``)

    Returns:
        The data directory as a ``Path``; created (with parents) if it does not yet exist.
    """
    override = (os.getenv("PLANESWALKER_DATA_DIR") or "").strip()
    if override:
        base = Path(override).expanduser()
        if not base.is_absolute():
            base = base.resolve()
    else:
        base = Path(user_data_dir(_APP, appauthor=False))
    base.mkdir(parents=True, exist_ok=True)
    return base


def database_path() -> Path:
    """Return the shared SQLite card database (``cards.db``) inside :func:`data_dir`."""
    return data_dir() / "cards.db"


def fastembed_cache_dir() -> Path:
    """Return the persistent fastembed model cache directory, creating it if absent.

    Lives beside ``cards.db`` under :func:`data_dir` so the ~80 MB ONNX model downloads once and
    survives reboots — never fastembed's volatile ``%TEMP%\\fastembed_cache`` default.

    Returns:
        The cache directory as a ``Path``; created (with parents) if it does not yet exist.
    """
    cache = data_dir() / "fastembed_cache"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def database_url() -> str:
    """Return the async SQLAlchemy URL for the shared database.

    An explicit ``CARDS_DATABASE_URL`` still wins (back-compat); otherwise the URL points at
    :func:`database_path` in the central data dir. ``.as_posix()`` keeps the URL valid on Windows
    (forward slashes after the ``sqlite+aiosqlite:///`` scheme).

    Returns:
        A ``sqlite+aiosqlite:///...`` connection URL string.
    """
    explicit = (os.getenv("CARDS_DATABASE_URL") or "").strip()
    return explicit or f"sqlite+aiosqlite:///{database_path().as_posix()}"

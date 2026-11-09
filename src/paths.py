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

# SQLAlchemy URL schemes the project's engines use; everything after one is the database file.
_SQLITE_URL_PREFIXES = ("sqlite+aiosqlite:///", "sqlite:///")


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
    """Return ``cards.db`` inside :func:`data_dir`.

    Not necessarily the database the server opens: an explicit ``CARDS_DATABASE_URL`` outranks it.
    Resolve the file to open or write with :func:`database_file`.
    """
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


def sqlite_file_from_url(url: str) -> str:
    """Return the database *file* a SQLite SQLAlchemy URL names. Pure: touches no filesystem.

    Strips a ``sqlite+aiosqlite:///`` or ``sqlite:///`` scheme and returns the rest verbatim, so a
    relative URL path (``./data/cards.db``) stays relative and resolves against the working
    directory exactly as the engine resolves it. A value with neither scheme is returned unchanged.

    Args:
        url: A SQLAlchemy SQLite URL, e.g. ``sqlite+aiosqlite:///C:/data/cards.db``.

    Returns:
        The file path the URL names, as a string.
    """
    for prefix in _SQLITE_URL_PREFIXES:
        if url.startswith(prefix):
            return url[len(prefix) :]
    return url


def database_file() -> str:
    """Return the SQLite file :func:`database_url` names: the one file every component opens.

    With ``CARDS_DATABASE_URL`` set (empty or whitespace counts as unset), the URL's file, and the
    data dir is neither consulted nor created. Otherwise ``str(database_path())``, which creates the
    data dir as :func:`data_dir` always does. Anything that needs the database as a *file* (the
    sync connection factory, the import CLIs, the startup diagnostics) resolves it here, never
    from :func:`database_path`, which ignores the URL and so names a different file whenever the
    URL is set.

    Returns:
        The file path as a string; a URL path is passed through verbatim (no resolution).
    """
    explicit = (os.getenv("CARDS_DATABASE_URL") or "").strip()
    if explicit:
        return sqlite_file_from_url(explicit)
    return str(database_path())

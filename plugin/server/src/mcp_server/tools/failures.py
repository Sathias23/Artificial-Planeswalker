"""The tool-edge guard that answers infrastructure failures as ``status="error"``.

Every MCP tool promises never to raise for a failure it models (``server.py``'s module docstring),
and the helpers keep that promise around their own repository calls. What they cannot guard is the
work that runs *before* their own ``try`` — the readiness probe, opening the sqlite-vec connection,
loading the embedding model — so a corrupt or locked ``cards.db``, a missing sqlite-vec extension
or an offline first model load used to reach the agent as an MCP ``isError``. The guard here
wraps each database-backed tool wrapper in ``server.py`` once, at the edge, so those failures
answer as the tool's own ``status="error"`` with a message that says what went wrong.

**Exactly the infrastructure set, and nothing else** (:data:`INFRASTRUCTURE_ERRORS`): the driver's
``DatabaseError`` family from either seam (SQLAlchemy over aiosqlite, or the stdlib ``sqlite3`` the
search tools use) and the search stack's named load failures
(:class:`~src.search.errors.SearchBackendUnavailableError`). The two third-party loaders are
narrowed where they fail (``src/search/connection.py``, ``src/search/embedder.py``), so this edge
never catches a bare ``ValueError`` or ``OSError``. A ``ProgrammingError`` — the driver saying the
code misused it — is a subclass of ``DatabaseError`` in both families and is re-raised first, as is
everything outside the set (``TypeError``, ``MissingGreenlet``, ``InvalidRequestError``, a
``ValidationError``): those are bugs, and a bug must still surface as an MCP error, never as a
status that blames the database.

Known limit: SQLite reports an SQL syntax error as ``OperationalError``, not
``ProgrammingError``, so a malformed query in a helper answers ``error`` too. It is logged at error
level with its traceback on stderr, which is where it will be seen.
"""

import logging
import sqlite3
from collections.abc import Awaitable, Callable
from typing import Final

from sqlalchemy.exc import DatabaseError as SQLAlchemyDatabaseError
from sqlalchemy.exc import ProgrammingError as SQLAlchemyProgrammingError

from src.search.errors import SearchBackendUnavailableError

logger = logging.getLogger(__name__)

#: The failures the edge answers as ``status="error"``.
INFRASTRUCTURE_ERRORS: Final[tuple[type[Exception], ...]] = (
    SQLAlchemyDatabaseError,
    sqlite3.DatabaseError,
    SearchBackendUnavailableError,
)

#: Subclasses of :data:`INFRASTRUCTURE_ERRORS` that mean a bug in the caller, re-raised untouched.
PROGRAMMING_ERRORS: Final[tuple[type[Exception], ...]] = (
    SQLAlchemyProgrammingError,
    sqlite3.ProgrammingError,
)

#: The longest driver text a message carries; a corrupt-file error can quote arbitrary bytes.
DETAIL_LIMIT: Final = 200

_LOCK_WORDS: Final = ("locked", "busy")


def failure_detail(exc: BaseException) -> str:
    """The failure's own text, capped at :data:`DETAIL_LIMIT` characters.

    For a SQLAlchemy error this is the DB-API exception it wraps (``exc.orig``), never SQLAlchemy's
    own string, which echoes the whole SQL statement and its bound parameters.
    """
    source = getattr(exc, "orig", None) or exc
    text = " ".join(str(source).split()) or type(source).__name__
    if len(text) > DETAIL_LIMIT:
        text = text[: DETAIL_LIMIT - 1] + "…"
    return text


def infrastructure_error_message(exc: BaseException) -> str:
    """Build the human-facing ``message`` for an infrastructure failure.

    Args:
        exc: One of :data:`INFRASTRUCTURE_ERRORS`.

    Returns:
        One or two sentences: what could not be used and the driver's or loader's own reason, plus
        a wait-and-retry hint when the reason says the database is locked or busy.
    """
    detail = failure_detail(exc)
    if isinstance(exc, SearchBackendUnavailableError):
        # The loader's message already names the extension or the model.
        return (
            f"{detail.rstrip('.')}. Semantic search is unavailable until this is fixed; the other "
            "card and deck tools are unaffected."
        )
    message = f"The local card database could not be used: {detail.rstrip('.')}."
    if any(word in detail.lower() for word in _LOCK_WORDS):
        message += (
            " Another process (an import or an index build) is using it — wait a moment and try "
            "again."
        )
    else:
        message += " If this keeps happening, the database file may be damaged or unreadable."
    return message


async def answer_infrastructure_failures[ResultT](
    tool: str,
    call: Callable[[], Awaitable[ResultT]],
    on_error: Callable[[str], ResultT],
) -> ResultT:
    """Await ``call()``, answering an infrastructure failure as ``on_error(message)``.

    Args:
        tool: The MCP tool name, for the log line.
        call: The wrapped tool body (session or worker thread included).
        on_error: Builds the tool's ``status="error"`` result from the message.

    Returns:
        Whatever ``call()`` returned, or the ``on_error`` result for an infrastructure failure.

    Raises:
        Exception: Any :data:`PROGRAMMING_ERRORS` member, and anything outside
            :data:`INFRASTRUCTURE_ERRORS`, unchanged.
    """
    try:
        return await call()
    except PROGRAMMING_ERRORS:
        raise
    except INFRASTRUCTURE_ERRORS as exc:
        logger.error("%s answered status=error", tool, exc_info=exc)
        return on_error(infrastructure_error_message(exc))

"""Base repository class for data access operations."""

from sqlalchemy.ext.asyncio import AsyncSession

#: The escape character every user-text ``LIKE`` declares (``ilike(pattern, escape=LIKE_ESCAPE)``).
LIKE_ESCAPE = "\\"


def contains_pattern(text: str) -> str:
    """Return a ``LIKE`` pattern matching ``text`` as a literal substring.

    ``\\``, ``%`` and ``_`` in ``text`` are escaped with :data:`LIKE_ESCAPE`, so a user's ``50%``
    matches the characters ``50%`` rather than every value containing ``50``. Pair the pattern with
    ``escape=LIKE_ESCAPE`` on the ``like`` / ``ilike`` call, or the escapes are literal backslashes.

    Args:
        text: The user's substring.

    Returns:
        ``%<escaped text>%``.
    """
    escaped = (
        text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", f"{LIKE_ESCAPE}%")
        .replace("_", f"{LIKE_ESCAPE}_")
    )
    return f"%{escaped}%"


class BaseRepository:
    """Base repository providing common database access patterns.

    All repository classes should inherit from this base to ensure
    consistent session management and interface patterns.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with an async database session.

        Args:
            session: AsyncSession for database operations.
        """
        self.session = session

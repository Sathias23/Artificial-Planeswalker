"""Base repository class for data access operations."""

from sqlalchemy.ext.asyncio import AsyncSession


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

"""Bug report repository for database operations on bug-report data."""

import logging

from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.bug_report import BugReportModel
from src.data.repositories.base import BaseRepository
from src.data.schemas.bug_report import BugReport

logger = logging.getLogger(__name__)


class BugReportRepository(BaseRepository):
    """Repository for bug-report database operations.

    Provides creation of user-submitted bug reports. Extends BaseRepository
    for consistent session management.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: AsyncSession for database operations.
        """
        super().__init__(session)

    async def create(self, description: str, context: str | None = None) -> BugReport:
        """Create a new bug report.

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination.

        Args:
            description: User-supplied description of the bug.
            context: Optional free-text/JSON context supplied by the client.

        Returns:
            BugReport schema with generated id, default "open" status, and timestamps.

        Raises:
            IntegrityError: For constraint violations.
            DatabaseError: For other database-level errors.

        Example:
            report = await repo.create(description="Search returned the wrong card")
        """
        try:
            bug_report_model = BugReportModel(description=description, context=context)
            self.session.add(bug_report_model)
            await self.session.commit()
            await self.session.refresh(bug_report_model)
        except IntegrityError as e:
            await self.session.rollback()
            logger.warning("IntegrityError in create bug report: %s", str(e))
            raise
        except DatabaseError as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in create bug report: in_transaction=%s - %s",
                self.session.in_transaction(),
                str(e),
            )
            raise
        # Schema conversion is outside the DB-error block: a ValidationError here
        # means the committed row has an unexpected status value and does NOT warrant
        # rolling back an already-persisted transaction.
        return BugReport.model_validate(bug_report_model)

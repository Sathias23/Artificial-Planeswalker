"""Structured bug-report logic for the ``report_bug`` MCP tool.

Persists a user-submitted bug report to the ``bug_reports`` SQLite table via the
async ``BugReportRepository`` (D-1.3b — superseding the legacy JSONL store) and
returns a structured confirmation. Stateless: no session id or conversation
history is captured (FR3). DB errors are caught and surfaced as a graceful
message rather than raised to the MCP client.
"""

import logging

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.repositories.bug_report import BugReportRepository

logger = logging.getLogger(__name__)


class BugReportResult(BaseModel):
    """Structured result of filing a bug report.

    Attributes:
        id: The new report's id, or an empty string if persistence failed.
        message: Human-facing confirmation (or graceful error) message.
    """

    id: str
    message: str


async def file_bug_report(session: AsyncSession, description: str) -> BugReportResult:
    """Persist a bug report and return a structured confirmation.

    Args:
        session: Async database session to write through.
        description: User-supplied description of the bug or issue.

    Returns:
        A ``BugReportResult``. On a database error, returns a graceful message
        with an empty ``id`` instead of raising to the client.
    """
    repo = BugReportRepository(session)
    try:
        report = await repo.create(description=description)
    except Exception:
        logger.exception("Failed to persist bug report")
        return BugReportResult(
            id="",
            message="Sorry — your bug report could not be saved. Please try again.",
        )
    return BugReportResult(
        id=report.id,
        message=f"Bug report {report.id} submitted. Thank you for reporting this issue!",
    )

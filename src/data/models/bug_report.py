"""SQLAlchemy ORM model for user-submitted bug reports."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.base import Base


class BugReportModel(Base):
    """SQLAlchemy model for a bug report filed via the MCP ``report_bug`` tool.

    Stores the user-supplied description plus lifecycle status and timestamps.
    Stateless by design (Story 1.3 / FR3): no session id or conversation history
    is retained; ``context`` is an optional free-text/JSON field for any
    client-supplied detail.
    """

    __tablename__ = "bug_reports"

    # Primary key - UUID
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )

    # User-supplied bug description
    description: Mapped[str] = mapped_column(Text, nullable=False, init=True)

    # Lifecycle status (see BugReportStatus); defaults to "open" for new reports
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="open", index=True, init=True
    )

    # Optional free-text / JSON context supplied by the client
    context: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, init=True)

    # Timestamps - auto-managed
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(UTC), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default_factory=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        init=False,
    )

    def __repr__(self) -> str:
        """String representation of the bug report."""
        return f"<BugReportModel(id='{self.id}', status='{self.status}')>"

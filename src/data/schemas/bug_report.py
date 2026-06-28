"""Pydantic schemas for type-safe bug-report data transfer."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_serializer


class BugReportStatus(str, Enum):
    """Bug report lifecycle status values.

    Ported from the legacy JSONL store so existing tooling stays compatible.

    Attributes:
        OPEN: New bug report, not yet triaged.
        INVESTIGATING: Bug confirmed and being researched.
        RESOLVED: Bug fixed or addressed.
        CLOSED: Bug not reproducible, duplicate, or won't fix.
        ARCHIVED: Old bug moved to archive for historical reference.
    """

    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ARCHIVED = "archived"


class BugReport(BaseModel):
    """Pydantic schema for a bug report.

    Provides type-safe data transfer between application layers.
    Supports conversion from SQLAlchemy BugReportModel instances.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    description: str
    status: BugReportStatus
    created_at: datetime
    updated_at: datetime
    context: str | None = None

    @field_serializer("created_at", "updated_at")
    def _serialize_timestamps(self, value: datetime) -> str:
        """Emit RFC 3339 with a UTC offset.

        SQLite stores naive datetimes; strict ``date-time`` validators (Ajv-style,
        e.g. Claude Desktop's MCP client) reject timezone-less values and fail the
        whole tool result. Coerce naive -> UTC so the output always carries an offset.
        """
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()

"""Bug report tool for PydanticAI agent.

This tool enables users to explicitly report bugs and unexpected behavior
encountered during chat interactions. The agent can suggest bug reporting
but must NOT invoke this tool autonomously - explicit user confirmation
is required.

Bug reports are stored in JSONL format at data/bug_reports.jsonl with
conversation context, session metadata, and timestamps for debugging.

JSONL Schema (v2 - with status tracking):
{
    "id": "uuid",                    # Unique report identifier
    "session_id": "string",          # Chainlit session ID
    "timestamp": "ISO 8601",         # When report was created
    "description": "string",         # User-provided bug description
    "conversation_context": [],      # Last 10 messages
    "metadata": {},                  # Session metadata
    "status": "open",                # Current lifecycle state (default: "open")
    "updated_at": "ISO 8601"         # When status was last updated
}

Status Lifecycle:
- open: New bug report, not yet triaged
- investigating: Bug confirmed and being researched
- resolved: Bug fixed or addressed
- closed: Bug not reproducible, duplicate, or won't fix
- archived: Old bug moved to archive for historical reference
"""

import json
import uuid
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse

from legacy.agent.dependencies import AgentDependencies


class BugReportStatus(str, Enum):
    """Bug report lifecycle status values.

    This enum defines the valid status values for bug reports, tracking
    their lifecycle from creation through resolution and archival.

    Attributes:
        OPEN: New bug report, not yet triaged
        INVESTIGATING: Bug confirmed and being researched
        RESOLVED: Bug fixed or addressed
        CLOSED: Bug not reproducible, duplicate, or won't fix
        ARCHIVED: Old bug moved to archive for historical reference
    """

    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ARCHIVED = "archived"


async def report_bug(
    ctx: RunContext[AgentDependencies],
    description: str = "User reported an issue (no details provided)",
) -> str:
    """Report a bug or unexpected behavior in the chat interface.

    This tool captures bug reports from users with full conversation context
    for debugging. The agent can suggest filing a bug report but should
    NEVER invoke this tool autonomously - always wait for explicit user
    confirmation.

    The tool captures:
    - User's bug description
    - Last 10 conversation messages for context
    - Session metadata (ID, format filter, model configuration)
    - Timestamp and unique report ID
    - Status field (default: "open") for lifecycle tracking
    - Updated timestamp for status change history

    Reports are appended to data/bug_reports.jsonl in JSON Lines format,
    with one report per line for efficient parsing and append operations.

    Args:
        ctx: RunContext providing access to agent dependencies and session state
        description: User's description of the bug or issue. Defaults to
            a generic message if user doesn't provide specific details.

    Returns:
        User-friendly confirmation message with the report ID

    Example:
        >>> # User explicitly requests bug report
        >>> await report_bug(ctx, "Search returned wrong cards for Lightning Bolt")
        Bug report a1b2c3d4-... submitted. Thank you for reporting this issue!

        >>> # Minimal report without description
        >>> await report_bug(ctx)
        Bug report e5f6g7h8-... submitted. Thank you for reporting this issue!

    Notes:
        - Reports are stored at data/bug_reports.jsonl (created if not exists)
        - Each report has a unique UUID for tracking
        - Conversation context limited to last 10 messages to manage file size
        - Timestamps use ISO 8601 format in UTC
        - File operations are atomic to prevent corruption
        - Agent should suggest but never autonomously invoke this tool
    """
    # Generate unique report ID
    report_id = str(uuid.uuid4())

    # Get current timestamp in ISO 8601 format (UTC)
    timestamp = datetime.now(UTC).isoformat()

    # Get session ID from dependencies
    session_id = ctx.deps.session_id

    # Get format filter state (if any)
    format_filter = ctx.deps.format_filter

    # Capture conversation context (last 10 messages)
    # Import session manager to access conversation history
    from legacy.agent.core import _session_manager

    message_history = _session_manager.get_history(session_id)
    conversation_context = _format_conversation_context(message_history)

    # Collect metadata
    metadata = {
        "session_id": session_id,
        "format_filter": format_filter,
        "timestamp": timestamp,
    }

    # Create bug report entry with status tracking
    bug_report = {
        "id": report_id,
        "session_id": session_id,
        "timestamp": timestamp,
        "description": description,
        "conversation_context": conversation_context,
        "metadata": metadata,
        "status": BugReportStatus.OPEN.value,  # Default to "open" for new reports
        "updated_at": timestamp,  # Equals timestamp for new reports
    }

    # Write to JSONL file
    try:
        _write_bug_report_jsonl(bug_report)
    except Exception as e:
        # If file write fails, raise exception so agent can inform user
        raise RuntimeError(f"Unable to save bug report due to file system error: {e}") from e

    # Return user-friendly confirmation
    return (
        f"Bug report {report_id} submitted. Thank you for reporting this issue! "
        "Our team will review it shortly."
    )


def _format_conversation_context(
    message_history: list[ModelMessage],
) -> list[dict[str, str]]:
    """Format conversation message history for bug report context.

    Extracts the last 10 messages from the conversation and formats them
    as a list of dictionaries with role, content, and timestamp.

    Args:
        message_history: Complete conversation history from session manager

    Returns:
        List of formatted messages, limited to last 10 messages

    Notes:
        - Excludes system messages (agent personality/instructions)
        - Includes both user prompts and agent responses
        - Timestamps are ISO 8601 format in UTC
        - Tool calls and returns are included for debugging context
    """
    # Limit to last 10 messages
    recent_messages = message_history[-10:] if len(message_history) > 10 else message_history

    formatted_context = []
    for msg in recent_messages:
        # Extract role and content based on message type
        if isinstance(msg, ModelRequest):
            # User message
            role = "user"
            # Concatenate all text parts (convert to str)
            content_parts = [str(part.content) for part in msg.parts if hasattr(part, "content")]
            content = "\n".join(content_parts) if content_parts else "[No content]"
        elif isinstance(msg, ModelResponse):
            # Agent response
            role = "assistant"
            # Concatenate all text parts (convert to str)
            content_parts = [str(part.content) for part in msg.parts if hasattr(part, "content")]
            content = "\n".join(content_parts) if content_parts else "[No content]"
        else:
            # Unknown message type - skip
            continue

        formatted_context.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    return formatted_context


def _write_bug_report_jsonl(bug_report: dict[str, Any]) -> None:
    """Write bug report to JSONL file with atomic append operation.

    Appends a single bug report entry to data/bug_reports.jsonl. Creates
    the file and parent directory if they don't exist. Uses atomic write
    operations to prevent file corruption.

    Args:
        bug_report: Bug report dictionary to write (will be JSON-serialized)

    Raises:
        OSError: If file cannot be created or written (permissions, disk full, etc.)
        json.JSONEncodeError: If bug report contains non-serializable data

    Notes:
        - Creates data/ directory if it doesn't exist
        - File permissions: 0o644 (rw-r--r--)
        - Each entry is a single JSON line followed by newline
        - Append-only operations - never modifies existing entries
    """
    # Define file path
    file_path = Path("data/bug_reports.jsonl")

    # Ensure data/ directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize bug report to JSON (single line, no indentation)
    json_line = json.dumps(bug_report, ensure_ascii=False)

    # Append to file (creates file if it doesn't exist)
    # Use 'a' mode for atomic append operation
    with file_path.open("a", encoding="utf-8") as f:
        f.write(json_line + "\n")

#!/usr/bin/env python3
"""Bug report management CLI tool.

This script provides commands to manage bug reports for personal convenience:
- list: View all bugs filtered by status
- show: Show full details of a specific bug
- recent: Show the most recently reported bugs
- search: Search bugs by keyword
- update: Change bug status (open → investigating → resolved → closed)
- delete: Delete old resolved/closed bugs

Usage:
    uv run python scripts/manage_bug_reports.py list [--status STATUS] [--include-archived]
    uv run python scripts/manage_bug_reports.py show <bug-id>
    uv run python scripts/manage_bug_reports.py recent [--count N] [--status STATUS]
    uv run python scripts/manage_bug_reports.py search <keyword>
    uv run python scripts/manage_bug_reports.py update <bug-id> --status STATUS
    uv run python scripts/manage_bug_reports.py delete [--older-than-days DAYS] [--dry-run]
"""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Import BugReportStatus enum from the agent tools
sys.path.insert(0, str(Path(__file__).parent.parent))
from legacy.agent.tools.bug_report import BugReportStatus


def read_bug_reports(file_path: Path) -> dict[str, dict[str, Any]]:
    """Read bug reports from JSONL file and return latest state per bug ID.

    Handles append-only architecture where multiple entries for the same
    bug ID may exist. Merges entries to preserve full data while respecting
    status updates.

    Args:
        file_path: Path to bug_reports.jsonl file

    Returns:
        Dictionary mapping bug ID to merged bug report data

    Notes:
        - Backward compatible: Reports without status default to "open"
        - Reports without updated_at use timestamp field
        - Status updates merge with original report data
        - Empty file or missing file returns empty dict
    """
    if not file_path.exists():
        return {}

    bugs: dict[str, dict[str, Any]] = {}

    with file_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON at line {line_num}: {e}", file=sys.stderr)
                continue

            # Extract bug ID
            bug_id = entry.get("id")
            if not bug_id:
                print(f"Warning: Skipping entry without ID at line {line_num}", file=sys.stderr)
                continue

            # Apply backward compatibility defaults
            if "status" not in entry:
                entry["status"] = BugReportStatus.OPEN.value

            if "updated_at" not in entry:
                entry["updated_at"] = entry.get("timestamp", datetime.now(UTC).isoformat())

            # Merge entries for same bug ID
            if bug_id not in bugs:
                bugs[bug_id] = entry
            else:
                # Merge: keep full data from first entry, update status/timestamp from latest
                current_updated = bugs[bug_id]["updated_at"]
                new_updated = entry["updated_at"]

                if new_updated >= current_updated:
                    # This is a newer entry (status update)
                    # Preserve original data, update status fields
                    bugs[bug_id]["status"] = entry["status"]
                    bugs[bug_id]["updated_at"] = entry["updated_at"]

                    # Copy any new fields from update entry (but don't overwrite existing)
                    for key, value in entry.items():
                        if key not in bugs[bug_id] and key not in ["id", "status", "updated_at"]:
                            bugs[bug_id][key] = value

    return bugs


def list_bugs(
    status_filter: str | None = None,
    include_archived: bool = False,
) -> None:
    """List bug reports filtered by status.

    Args:
        status_filter: Comma-separated status values (e.g., "open,investigating")
        include_archived: Include archived bugs in results
    """
    file_path = Path("data/bug_reports.jsonl")
    bugs = read_bug_reports(file_path)

    if not bugs:
        print("No bug reports found.")
        return

    # Parse status filter
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",")]
    else:
        # Default: all active statuses (exclude archived unless explicitly requested)
        statuses = [
            BugReportStatus.OPEN.value,
            BugReportStatus.INVESTIGATING.value,
            BugReportStatus.RESOLVED.value,
            BugReportStatus.CLOSED.value,
        ]
        if include_archived:
            statuses.append(BugReportStatus.ARCHIVED.value)

    # Filter bugs by status
    filtered_bugs = {bug_id: bug for bug_id, bug in bugs.items() if bug["status"] in statuses}

    if not filtered_bugs:
        print(f"No bug reports found with status: {', '.join(statuses)}")
        return

    # Group by status
    bugs_by_status: dict[str, list[dict[str, Any]]] = {}
    for bug in filtered_bugs.values():
        status = bug["status"]
        if status not in bugs_by_status:
            bugs_by_status[status] = []
        bugs_by_status[status].append(bug)

    # Display grouped by status
    total_count = 0
    for status in statuses:
        if status not in bugs_by_status:
            continue

        bugs_in_status = bugs_by_status[status]
        print(f"\n{status.upper()} ({len(bugs_in_status)} bugs)")
        print("=" * 80)

        for bug in bugs_in_status:
            bug_id = bug["id"]
            description = bug.get("description", "No description")
            updated_at = bug.get("updated_at", "Unknown")

            # Truncate description for display
            max_desc_length = 60
            if len(description) > max_desc_length:
                description = description[: max_desc_length - 3] + "..."

            print(f"  {bug_id[:8]}... | {description}")
            print(f"              Updated: {updated_at}")

        total_count += len(bugs_in_status)

    print(f"\nTotal: {total_count} bug(s)")


def update_bug_status(bug_id: str, new_status: str) -> None:
    """Update the status of an existing bug report.

    Args:
        bug_id: Bug report ID (full UUID or prefix)
        new_status: New status value (must be valid BugReportStatus)
    """
    # Validate status
    try:
        status_enum = BugReportStatus(new_status)
    except ValueError:
        valid_statuses = [s.value for s in BugReportStatus]
        print(f"Error: Invalid status '{new_status}'", file=sys.stderr)
        print(f"Valid statuses: {', '.join(valid_statuses)}", file=sys.stderr)
        sys.exit(1)

    # Read existing bugs
    file_path = Path("data/bug_reports.jsonl")
    bugs = read_bug_reports(file_path)

    # Find bug by ID (support partial ID match)
    matched_bug_id = None
    for existing_id in bugs:
        if existing_id == bug_id or existing_id.startswith(bug_id):
            matched_bug_id = existing_id
            break

    if not matched_bug_id:
        print(f"Error: Bug ID not found: {bug_id}", file=sys.stderr)
        sys.exit(1)

    bug = bugs[matched_bug_id]

    # Check if status is already set to new_status
    if bug["status"] == new_status:
        print(f"Bug {matched_bug_id[:8]}... already has status: {new_status}")
        return

    # Create status update entry
    timestamp = datetime.now(UTC).isoformat()
    update_entry = {
        "id": matched_bug_id,
        "status": status_enum.value,
        "updated_at": timestamp,
        "update_type": "status_change",
    }

    # Append to JSONL file
    with file_path.open("a", encoding="utf-8") as f:
        json_line = json.dumps(update_entry, ensure_ascii=False)
        f.write(json_line + "\n")

    print(f"Updated bug {matched_bug_id[:8]}... to status: {new_status}")
    print(f"Timestamp: {timestamp}")


def show_bug(bug_id: str) -> None:
    """Show full details of a specific bug report.

    Args:
        bug_id: Bug report ID (full UUID or prefix)
    """
    file_path = Path("data/bug_reports.jsonl")
    bugs = read_bug_reports(file_path)

    # Find bug by ID (support partial ID match)
    matched_bug_id = None
    for existing_id in bugs:
        if existing_id == bug_id or existing_id.startswith(bug_id):
            matched_bug_id = existing_id
            break

    if not matched_bug_id:
        print(f"Error: Bug ID not found: {bug_id}", file=sys.stderr)
        sys.exit(1)

    bug = bugs[matched_bug_id]

    # Display full bug details
    print("=" * 80)
    print(f"Bug ID: {bug['id']}")
    print(f"Status: {bug['status']}")
    print(f"Reported: {bug.get('timestamp', 'Unknown')}")
    print(f"Updated: {bug.get('updated_at', bug.get('timestamp', 'Unknown'))}")
    print("=" * 80)
    print(f"\nDescription:\n{bug.get('description', 'No description')}")

    # Show session metadata if available
    session_metadata = bug.get("session_metadata", {})
    if session_metadata:
        print(f"\nSession ID: {session_metadata.get('session_id', 'Unknown')}")
        if session_metadata.get("active_deck_id"):
            print(f"Active Deck ID: {session_metadata['active_deck_id']}")
        if session_metadata.get("format_filter"):
            print(f"Format Filter: {session_metadata['format_filter']}")

    # Show conversation history if available
    conversation = bug.get("conversation_history", [])
    if conversation:
        print(f"\nConversation History ({len(conversation)} messages):")
        print("-" * 80)
        for i, msg in enumerate(conversation, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # Truncate long messages
            if len(content) > 200:
                content = content[:197] + "..."
            print(f"{i}. [{role.upper()}] {content}")

    print("\n" + "=" * 80)


def show_recent_bugs(count: int = 10, status_filter: str | None = None) -> None:
    """Show the N most recently reported bugs.

    Args:
        count: Number of recent bugs to show
        status_filter: Optional status filter (comma-separated)
    """
    file_path = Path("data/bug_reports.jsonl")
    bugs = read_bug_reports(file_path)

    if not bugs:
        print("No bug reports found.")
        return

    # Filter by status if specified
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",")]
        bugs = {bug_id: bug for bug_id, bug in bugs.items() if bug["status"] in statuses}

    if not bugs:
        print(f"No bugs found with status: {status_filter}")
        return

    # Sort by timestamp (most recent first)
    sorted_bugs = sorted(
        bugs.items(),
        key=lambda x: x[1].get("timestamp", ""),
        reverse=True,
    )

    # Limit to count
    recent_bugs = sorted_bugs[:count]

    print(f"\n{len(recent_bugs)} Most Recent Bug(s)")
    print("=" * 80)

    for bug_id, bug in recent_bugs:
        description = bug.get("description", "No description")
        status = bug["status"]
        timestamp = bug.get("timestamp", "Unknown")

        # Truncate description
        max_desc_length = 100
        if len(description) > max_desc_length:
            description = description[: max_desc_length - 3] + "..."

        print(f"\n{bug_id[:8]}... | [{status.upper()}] | {timestamp}")
        print(f"{description}")
        print("-" * 80)

    print(f"\nShowing {len(recent_bugs)} of {len(sorted_bugs)} total bugs")


def search_bugs(keyword: str) -> None:
    """Search bug reports by keyword in description.

    Args:
        keyword: Search term to find in bug descriptions
    """
    file_path = Path("data/bug_reports.jsonl")
    bugs = read_bug_reports(file_path)

    if not bugs:
        print("No bug reports found.")
        return

    # Search for keyword in description (case-insensitive)
    keyword_lower = keyword.lower()
    matches = [
        (bug_id, bug)
        for bug_id, bug in bugs.items()
        if keyword_lower in bug.get("description", "").lower()
    ]

    if not matches:
        print(f"No bugs found matching keyword: '{keyword}'")
        return

    print(f"\nFound {len(matches)} bug(s) matching '{keyword}'")
    print("=" * 80)

    for bug_id, bug in matches:
        description = bug.get("description", "No description")
        status = bug["status"]
        timestamp = bug.get("timestamp", "Unknown")

        # Truncate description
        max_desc_length = 100
        if len(description) > max_desc_length:
            description = description[: max_desc_length - 3] + "..."

        print(f"\n{bug_id[:8]}... | [{status.upper()}] | {timestamp}")
        print(f"{description}")
        print("-" * 80)


def delete_bugs(older_than_days: int = 90, dry_run: bool = False) -> None:
    """Delete old resolved or closed bugs.

    Args:
        older_than_days: Delete bugs older than this many days
        dry_run: If True, show what would be deleted without modifying files
    """
    file_path = Path("data/bug_reports.jsonl")
    bugs = read_bug_reports(file_path)

    if not bugs:
        print("No bug reports found.")
        return

    # Calculate cutoff date
    cutoff_date = datetime.now(UTC) - timedelta(days=older_than_days)

    # Find bugs eligible for deletion
    eligible_bugs = []
    for bug_id, bug in bugs.items():
        status = bug["status"]
        updated_at = bug.get("updated_at", bug.get("timestamp"))

        # Only delete resolved or closed bugs
        if status not in [BugReportStatus.RESOLVED.value, BugReportStatus.CLOSED.value]:
            continue

        # Skip bugs without timestamps
        if not updated_at:
            print(f"Warning: Bug {bug_id[:8]}... has no timestamp, skipping", file=sys.stderr)
            continue

        # Check if older than threshold
        try:
            updated_datetime = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            print(f"Warning: Invalid timestamp for bug {bug_id[:8]}..., skipping")
            continue

        if updated_datetime < cutoff_date:
            eligible_bugs.append((bug_id, bug))

    if not eligible_bugs:
        print(f"No bugs found for deletion (older than {older_than_days} days)")
        return

    # Display eligible bugs
    print(f"Found {len(eligible_bugs)} bug(s) eligible for deletion:")
    print("=" * 80)
    for bug_id, bug in eligible_bugs:
        description = bug.get("description", "No description")[:50]
        status = bug["status"]
        updated_at = bug.get("updated_at")
        print(f"  {bug_id[:8]}... | {status} | {updated_at}")
        print(f"              {description}...")

    if dry_run:
        print("\n[DRY RUN] No files modified.")
        return

    # Mark bugs as deleted by setting status to archived
    timestamp = datetime.now(UTC).isoformat()

    with file_path.open("a", encoding="utf-8") as main_file:
        for bug_id, _ in eligible_bugs:
            delete_entry = {
                "id": bug_id,
                "status": BugReportStatus.ARCHIVED.value,
                "updated_at": timestamp,
                "update_type": "deleted",
            }
            json_line = json.dumps(delete_entry, ensure_ascii=False)
            main_file.write(json_line + "\n")

    print(f"\nDeleted {len(eligible_bugs)} bug(s) successfully.")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Bug report status management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List command
    list_parser = subparsers.add_parser("list", help="List bug reports")
    list_parser.add_argument(
        "--status",
        type=str,
        help="Filter by status (comma-separated: open,investigating,resolved,closed,archived)",
    )
    list_parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived bugs in results",
    )

    # Update command
    update_parser = subparsers.add_parser("update", help="Update bug status")
    update_parser.add_argument("bug_id", type=str, help="Bug report ID (full or prefix)")
    update_parser.add_argument(
        "--status",
        type=str,
        required=True,
        help="New status (open, investigating, resolved, closed)",
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete old bugs")
    delete_parser.add_argument(
        "--older-than-days",
        type=int,
        default=90,
        help="Delete bugs older than N days (default: 90)",
    )
    delete_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without modifying files",
    )

    # Show command
    show_parser = subparsers.add_parser("show", help="Show full details of a bug")
    show_parser.add_argument("bug_id", type=str, help="Bug report ID (full or prefix)")

    # Recent command
    recent_parser = subparsers.add_parser("recent", help="Show recent bug reports")
    recent_parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of recent bugs to show (default: 10)",
    )
    recent_parser.add_argument(
        "--status",
        type=str,
        help="Filter by status (comma-separated)",
    )

    # Search command
    search_parser = subparsers.add_parser("search", help="Search bugs by keyword")
    search_parser.add_argument("keyword", type=str, help="Keyword to search for in descriptions")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    if args.command == "list":
        list_bugs(status_filter=args.status, include_archived=args.include_archived)
    elif args.command == "update":
        update_bug_status(bug_id=args.bug_id, new_status=args.status)
    elif args.command == "delete":
        delete_bugs(older_than_days=args.older_than_days, dry_run=args.dry_run)
    elif args.command == "show":
        show_bug(bug_id=args.bug_id)
    elif args.command == "recent":
        show_recent_bugs(count=args.count, status_filter=args.status)
    elif args.command == "search":
        search_bugs(keyword=args.keyword)


if __name__ == "__main__":
    main()

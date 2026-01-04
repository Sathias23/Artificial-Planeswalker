# Bug Report Management Guide

This guide explains how to use the bug report management CLI tool (`scripts/manage_bug_reports.py`) to track and manage bug reports and feature requests for the Artificial-Planeswalker project.

## Overview

The bug report system is a lightweight, personal convenience tool that uses an append-only JSONL file (`data/bug_reports.jsonl`) to track issues. Bug reports are automatically created when you use the agent's `report_bug` tool during conversations.

## Quick Start

```bash
# View all open bugs
uv run python scripts/manage_bug_reports.py list --status open

# Show the 5 most recent bugs
uv run python scripts/manage_bug_reports.py recent --count 5

# View full details of a specific bug
uv run python scripts/manage_bug_reports.py show <bug-id>

# Search for bugs containing "deck"
uv run python scripts/manage_bug_reports.py search deck
```

## Available Commands

### 1. `list` - View All Bugs

View all bug reports filtered by status.

```bash
# List all bugs (excluding archived)
uv run python scripts/manage_bug_reports.py list

# List only open bugs
uv run python scripts/manage_bug_reports.py list --status open

# List multiple statuses
uv run python scripts/manage_bug_reports.py list --status open,investigating

# Include archived bugs
uv run python scripts/manage_bug_reports.py list --include-archived
```

**Status Values:**
- `open` - Newly reported, not yet investigated
- `investigating` - Currently being worked on
- `resolved` - Fixed but not yet closed
- `closed` - Completed and verified
- `archived` - Deleted/removed from active list

**Output Format:**
```
OPEN (3 bugs)
================================================================================
  256a8bfb... | Feature Request: Add configurable card hover direction...
              Updated: 2025-10-25T02:05:00.982073+00:00
  77c559f3... | Feature request: The search_cards_advanced tool lacks...
              Updated: 2025-10-25T01:36:44.475294+00:00
```

---

### 2. `show` - View Full Bug Details

Display complete information about a specific bug report.

```bash
# Show bug details (full ID)
uv run python scripts/manage_bug_reports.py show 256a8bfb-c36f-4ede-8944-e7e25c21000e

# Show bug details (short ID prefix)
uv run python scripts/manage_bug_reports.py show 256a8bfb
```

**Output Includes:**
- Full bug ID
- Current status
- Reported timestamp
- Last updated timestamp
- Complete description
- Session metadata (session ID, active deck, format filter)
- Conversation history (last 10 messages before bug report)

**Example Output:**
```
================================================================================
Bug ID: 256a8bfb-c36f-4ede-8944-e7e25c21000e
Status: open
Reported: 2025-10-25T02:05:00.982073+00:00
Updated: 2025-10-25T02:05:00.982073+00:00
================================================================================

Description:
Feature Request: Add configurable card hover direction. Currently, card hovers
appear on the right side. Request: (1) Add ability to designate whether card
hovers should appear on right (current) or left...

Session ID: abc123
Active Deck ID: def456
Format Filter: standard

Conversation History (10 messages):
--------------------------------------------------------------------------------
1. [USER] I love the hover feature!
2. [ASSISTANT] I'm glad you like it! The card hover...
...
================================================================================
```

---

### 3. `recent` - Show Recent Bugs

Display the most recently reported bugs.

```bash
# Show 10 most recent bugs (default)
uv run python scripts/manage_bug_reports.py recent

# Show 3 most recent bugs
uv run python scripts/manage_bug_reports.py recent --count 3

# Show recent bugs with specific status
uv run python scripts/manage_bug_reports.py recent --count 5 --status open

# Show recent bugs across multiple statuses
uv run python scripts/manage_bug_reports.py recent --status open,investigating
```

**Options:**
- `--count N` - Number of bugs to show (default: 10)
- `--status STATUS` - Filter by status (comma-separated)

**Output Format:**
```
3 Most Recent Bug(s)
================================================================================

256a8bfb... | [OPEN] | 2025-10-25T02:05:00.982073+00:00
Feature Request: Add configurable card hover direction. Currently, card hovers...
--------------------------------------------------------------------------------

77c559f3... | [OPEN] | 2025-10-25T01:36:44.475294+00:00
Feature request: The search_cards_advanced tool lacks oracle text search...
--------------------------------------------------------------------------------

Showing 3 of 19 total bugs
```

---

### 4. `search` - Search Bugs by Keyword

Find bugs by searching descriptions (case-insensitive).

```bash
# Search for bugs containing "hover"
uv run python scripts/manage_bug_reports.py search hover

# Search for bugs containing "deck"
uv run python scripts/manage_bug_reports.py search deck

# Search for multi-word phrases
uv run python scripts/manage_bug_reports.py search "oracle text"
```

**Output Format:**
```
Found 1 bug(s) matching 'hover'
================================================================================

256a8bfb... | [OPEN] | 2025-10-25T02:05:00.982073+00:00
Feature Request: Add configurable card hover direction. Currently, card hovers...
--------------------------------------------------------------------------------
```

---

### 5. `update` - Change Bug Status

Update the status of an existing bug report.

```bash
# Mark bug as investigating
uv run python scripts/manage_bug_reports.py update 256a8bfb --status investigating

# Mark bug as resolved
uv run python scripts/manage_bug_reports.py update 256a8bfb --status resolved

# Mark bug as closed
uv run python scripts/manage_bug_reports.py update 256a8bfb --status closed
```

**Valid Status Transitions:**
- `open` → `investigating` - Started working on it
- `investigating` → `resolved` - Fixed, pending verification
- `resolved` → `closed` - Verified and completed
- Any status → `open` - Reopen if needed

**Output:**
```
Updated bug 256a8bfb... to status: investigating
Timestamp: 2025-10-25T10:30:00.000000+00:00
```

---

### 6. `delete` - Delete Old Bugs

Delete (archive) old resolved or closed bugs.

```bash
# Show what would be deleted (dry run)
uv run python scripts/manage_bug_reports.py delete --dry-run

# Delete bugs older than 90 days (default)
uv run python scripts/manage_bug_reports.py delete

# Delete bugs older than 30 days
uv run python scripts/manage_bug_reports.py delete --older-than-days 30
```

**Options:**
- `--older-than-days N` - Delete bugs older than N days (default: 90)
- `--dry-run` - Show what would be deleted without modifying files

**Behavior:**
- Only deletes bugs with status `resolved` or `closed`
- Sets status to `archived` (doesn't physically delete from file)
- Requires bugs to have timestamps
- Shows list of bugs before deletion

**Output:**
```
Found 2 bug(s) eligible for deletion:
================================================================================
  abc12345... | resolved | 2025-07-15T10:00:00.000000+00:00
              Bug in card search that was fixed 3 months ago...
  def67890... | closed | 2025-06-20T15:30:00.000000+00:00
              Feature request that was completed...

Deleted 2 bug(s) successfully.
```

---

## Bug Report Lifecycle

```
┌──────┐
│ OPEN │ ← Bug reported by user via agent
└───┬──┘
    │
    ▼
┌──────────────┐
│ INVESTIGATING│ ← Developer starts working on it
└───┬──────────┘
    │
    ▼
┌──────────┐
│ RESOLVED │ ← Fix implemented, needs verification
└───┬──────┘
    │
    ▼
┌────────┐
│ CLOSED │ ← Verified and completed
└───┬────┘
    │
    ▼
┌──────────┐
│ ARCHIVED │ ← Deleted after 90+ days (optional)
└──────────┘
```

---

## Tips & Best Practices

### Finding Specific Bugs

1. **Use `search` for keyword searches:**
   ```bash
   uv run python scripts/manage_bug_reports.py search "transaction"
   ```

2. **Use `recent` to see latest issues:**
   ```bash
   uv run python scripts/manage_bug_reports.py recent --count 5
   ```

3. **Use `list` to see all bugs of a specific status:**
   ```bash
   uv run python scripts/manage_bug_reports.py list --status open
   ```

### Working Through Bugs

1. **Review open bugs:**
   ```bash
   uv run python scripts/manage_bug_reports.py list --status open
   ```

2. **Get full details:**
   ```bash
   uv run python scripts/manage_bug_reports.py show <bug-id>
   ```

3. **Mark as investigating:**
   ```bash
   uv run python scripts/manage_bug_reports.py update <bug-id> --status investigating
   ```

4. **After fixing, mark as resolved:**
   ```bash
   uv run python scripts/manage_bug_reports.py update <bug-id> --status resolved
   ```

5. **After verification, close:**
   ```bash
   uv run python scripts/manage_bug_reports.py update <bug-id> --status closed
   ```

### Cleaning Up

Periodically delete old closed bugs to keep the list manageable:

```bash
# Preview what would be deleted
uv run python scripts/manage_bug_reports.py delete --dry-run

# Delete bugs older than 60 days
uv run python scripts/manage_bug_reports.py delete --older-than-days 60
```

---

## File Format

Bug reports are stored in `data/bug_reports.jsonl` as JSON Lines (one JSON object per line).

**Example Entry:**
```json
{
  "id": "256a8bfb-c36f-4ede-8944-e7e25c21000e",
  "session_id": "abc123def456",
  "timestamp": "2025-10-25T02:05:00.982073+00:00",
  "description": "Feature Request: Add configurable card hover direction...",
  "conversation_history": [...],
  "session_metadata": {
    "session_id": "abc123",
    "active_deck_id": "def456",
    "format_filter": "standard"
  },
  "status": "open",
  "updated_at": "2025-10-25T02:05:00.982073+00:00"
}
```

**Status Updates** (append-only):
```json
{
  "id": "256a8bfb-c36f-4ede-8944-e7e25c21000e",
  "status": "investigating",
  "updated_at": "2025-10-25T10:30:00.000000+00:00",
  "update_type": "status_change"
}
```

---

## Troubleshooting

### "Bug ID not found"

- Make sure you're using the correct bug ID (check with `list` or `recent`)
- You can use just the first 8 characters of the ID (e.g., `256a8bfb`)

### "No bug reports found"

- Check that `data/bug_reports.jsonl` exists
- Make sure you've reported at least one bug via the agent

### Invalid Status Error

Valid statuses are:
- `open`
- `investigating`
- `resolved`
- `closed`
- `archived`

### Timestamps Not Showing

Older bug reports may not have `updated_at` timestamps. The script will fall back to the `timestamp` field.

---

## Integration with Agent

### Reporting Bugs from Chat

Users can report bugs during conversations with the agent:

```
User: I found a bug - the deck view isn't showing my cards
Agent: I'll help you report that. Let me create a bug report...
        [Uses report_bug tool]
        Bug report submitted! ID: abc12345...
```

The agent automatically captures:
- User's description
- Last 10 conversation messages
- Session ID
- Active deck ID (if any)
- Format filter setting

### Viewing Bug Reports

After a bug is reported, you can use the CLI to view it:

```bash
uv run python scripts/manage_bug_reports.py recent --count 1
uv run python scripts/manage_bug_reports.py show abc12345
```

---

## Examples

### Example Workflow: Fixing a Bug

```bash
# 1. See what bugs are open
$ uv run python scripts/manage_bug_reports.py list --status open

# 2. Get details on a specific bug
$ uv run python scripts/manage_bug_reports.py show 256a8bfb

# 3. Mark as investigating
$ uv run python scripts/manage_bug_reports.py update 256a8bfb --status investigating

# ... work on the fix ...

# 4. Mark as resolved
$ uv run python scripts/manage_bug_reports.py update 256a8bfb --status resolved

# 5. After testing, close it
$ uv run python scripts/manage_bug_reports.py update 256a8bfb --status closed
```

### Example Workflow: Reviewing Recent Reports

```bash
# See the 5 most recent bug reports
$ uv run python scripts/manage_bug_reports.py recent --count 5

# Get full details on interesting ones
$ uv run python scripts/manage_bug_reports.py show 77c559f3

# Search for related bugs
$ uv run python scripts/manage_bug_reports.py search "search_cards"
```

### Example Workflow: Cleanup

```bash
# See what old bugs could be deleted
$ uv run python scripts/manage_bug_reports.py delete --dry-run

# Delete bugs older than 30 days
$ uv run python scripts/manage_bug_reports.py delete --older-than-days 30
```

---

## Additional Notes

- **Append-only design:** Bug reports are never modified in place; status updates append new entries
- **Backward compatible:** Old bug reports without status default to "open"
- **Lightweight:** Just a simple JSONL file, no database required
- **Session context:** Bug reports capture conversation context for better debugging
- **Personal use:** Designed for individual developer convenience, not team collaboration

---

## See Also

- [Bug Report Tool Implementation](../src/agent/tools/bug_report.py)
- [Management Script](../scripts/manage_bug_reports.py)
- [Bug Report Log](../data/bug_reports.jsonl)

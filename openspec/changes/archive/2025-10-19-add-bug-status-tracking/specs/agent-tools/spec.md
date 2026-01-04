## ADDED Requirements

### Requirement: Bug Report Status Lifecycle

Bug reports SHALL include a status field that tracks the lifecycle state from creation through resolution and archival.

#### Scenario: New bug report created with open status

- **GIVEN** a user reports a bug via the `report_bug` tool
- **WHEN** the bug report is written to `data/bug_reports.jsonl`
- **THEN** the report SHALL include `status="open"` by default
- **AND** SHALL include `updated_at` timestamp matching the creation timestamp

#### Scenario: Bug status updated to investigating

- **GIVEN** a bug report with status="open" exists
- **WHEN** a developer updates the status to "investigating"
- **THEN** a new JSONL entry SHALL be appended with:
  - Same `id` as original bug
  - `status="investigating"`
  - `updated_at` with current timestamp
  - `update_type="status_change"`
- **AND** the original bug entry SHALL remain unchanged (append-only)

#### Scenario: Bug marked as resolved

- **GIVEN** a bug report with status="investigating" exists
- **WHEN** a developer updates the status to "resolved"
- **THEN** a new JSONL entry SHALL be appended indicating resolution
- **AND** the bug is eligible for archival after 90 days

#### Scenario: Bug closed without resolution

- **GIVEN** a bug report with any status exists
- **WHEN** a developer updates the status to "closed" (duplicate, won't fix, etc.)
- **THEN** a new JSONL entry SHALL be appended with status="closed"
- **AND** the bug is eligible for archival after 90 days

#### Scenario: Bug archived for historical reference

- **GIVEN** a bug report with status="resolved" or "closed" exists
- **AND** the `updated_at` timestamp is more than 90 days old
- **WHEN** the archive process is executed
- **THEN** the bug SHALL be copied to `data/bug_reports_archive.jsonl`
- **AND** a new entry SHALL be appended to main file with status="archived"

#### Scenario: Reading bug with multiple status entries

- **GIVEN** a bug ID has multiple JSONL entries (status updates)
- **WHEN** the bug report is read from the file
- **THEN** the system SHALL use the entry with the **latest** `updated_at` timestamp
- **AND** discard earlier entries for the same bug ID

### Requirement: Bug Status Values

The bug status field SHALL use a defined set of lifecycle values with clear semantics.

#### Scenario: Valid status values

- **GIVEN** a bug report is created or updated
- **WHEN** setting the status field
- **THEN** the status SHALL be one of:
  - `"open"`: New bug, not yet triaged
  - `"investigating"`: Bug confirmed and being researched
  - `"resolved"`: Bug fixed or addressed
  - `"closed"`: Bug not reproducible, duplicate, or won't fix
  - `"archived"`: Old bug moved to archive file
- **AND** invalid status values SHALL be rejected with an error

#### Scenario: Invalid status value rejected

- **GIVEN** a bug status update is attempted
- **WHEN** the status value is not in the allowed set (e.g., "pending", "complete")
- **THEN** the system SHALL raise a validation error
- **AND** the bug report SHALL NOT be updated

### Requirement: Bug Report Schema with Status

Bug reports SHALL include status and update timestamp fields in the JSONL schema.

#### Scenario: JSONL entry with status fields

- **GIVEN** a bug report is written to `data/bug_reports.jsonl`
- **WHEN** the JSONL entry is created
- **THEN** the entry SHALL include these fields:
  - `id` (string, UUID): Unique report identifier
  - `session_id` (string): Chainlit session ID
  - `timestamp` (string, ISO 8601): When report was created
  - `description` (string): User-provided bug description
  - `conversation_context` (array): Last 10 messages
  - `metadata` (object): Agent model and session info
  - `status` (string): Current lifecycle state (default: "open")
  - `updated_at` (string, ISO 8601): When status was last updated
- **AND** for new reports, `updated_at` SHALL equal `timestamp`

#### Scenario: Status update JSONL entry

- **GIVEN** a bug status is being updated
- **WHEN** the update entry is written to JSONL
- **THEN** the entry SHALL include:
  - `id` (same as original bug)
  - `status` (new status value)
  - `updated_at` (current timestamp)
  - `update_type` (string): "status_change"
- **AND** SHALL NOT include full conversation context (update-only entry)

#### Scenario: Backward compatibility with legacy reports

- **GIVEN** existing bug reports in JSONL format without `status` field
- **WHEN** reading the bug reports file
- **THEN** reports without `status` SHALL be treated as status="open"
- **AND** reports without `updated_at` SHALL use `timestamp` as `updated_at`
- **AND** no data migration is required

### Requirement: Bug Report Status Management CLI

Developers SHALL have a CLI tool to manage bug report statuses and perform archival operations.

#### Scenario: List all bugs with status filter

- **GIVEN** the CLI tool `manage_bug_reports.py` is available
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py list --status open`
- **THEN** the tool SHALL display all bugs with status="open"
- **AND** output SHALL include: bug ID, description (truncated), status, updated_at

#### Scenario: List all bugs without filter

- **GIVEN** the CLI tool is available
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py list`
- **THEN** the tool SHALL display all active bugs (non-archived)
- **AND** group by status (open, investigating, resolved, closed)

#### Scenario: Update bug status

- **GIVEN** the CLI tool is available
- **AND** a bug with ID "abc-123" exists with status="open"
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py update abc-123 --status investigating`
- **THEN** the tool SHALL append a new JSONL entry with:
  - `id="abc-123"`
  - `status="investigating"`
  - `updated_at=<current timestamp>`
  - `update_type="status_change"`
- **AND** confirm the update to the developer

#### Scenario: Update status with invalid bug ID

- **GIVEN** the CLI tool is available
- **WHEN** developer runs update command with non-existent bug ID
- **THEN** the tool SHALL return error: "Bug ID not found: [id]"
- **AND** no JSONL entry SHALL be created

#### Scenario: Archive old resolved bugs

- **GIVEN** the CLI tool is available
- **AND** bugs exist with status="resolved" or "closed"
- **AND** `updated_at` is older than 90 days
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py archive --older-than-days 90`
- **THEN** the tool SHALL:
  1. Copy matching bugs to `data/bug_reports_archive.jsonl`
  2. Append archive entry to main file with status="archived"
  3. Report count of bugs archived

#### Scenario: Dry run archive operation

- **GIVEN** the CLI tool is available
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py archive --older-than-days 90 --dry-run`
- **THEN** the tool SHALL display which bugs would be archived
- **AND** NOT modify any files

### Requirement: Bug Report Archival Process

Old resolved or closed bugs SHALL be moved to an archive file to keep the active bug list manageable.

#### Scenario: Archive file creation

- **GIVEN** the archive process is executed for the first time
- **WHEN** bugs are archived
- **THEN** the file `data/bug_reports_archive.jsonl` SHALL be created
- **AND** archived bugs SHALL be appended to this file
- **AND** file permissions SHALL be set to 0o644 (rw-r--r--)

#### Scenario: Bug copied to archive

- **GIVEN** a bug with status="resolved" and updated_at > 90 days old
- **WHEN** the archive process runs
- **THEN** the complete bug report entry SHALL be copied to archive file
- **AND** retain all original fields (id, description, conversation_context, etc.)

#### Scenario: Archive marker in main file

- **GIVEN** a bug has been copied to archive file
- **WHEN** the archive process completes
- **THEN** a new entry SHALL be appended to main JSONL with:
  - Same bug `id`
  - `status="archived"`
  - `updated_at=<current timestamp>`
  - `update_type="archived"`
- **AND** future reads SHALL treat this bug as archived

#### Scenario: Archived bugs excluded from active list

- **GIVEN** bugs have been archived
- **WHEN** listing bugs without `--include-archived` flag
- **THEN** archived bugs SHALL NOT appear in results
- **AND** only bugs with status in (open, investigating, resolved, closed) SHALL be shown

#### Scenario: Include archived bugs in query

- **GIVEN** bugs have been archived
- **WHEN** developer runs `list --include-archived`
- **THEN** both active and archived bugs SHALL be displayed
- **AND** archived bugs SHALL be marked with status="archived"

### Requirement: Bug Status Filtering

The CLI tool SHALL support filtering bug reports by status to aid in triage and workflow management.

#### Scenario: Filter by single status

- **GIVEN** the bug reports file contains bugs with various statuses
- **WHEN** developer runs `list --status investigating`
- **THEN** only bugs with status="investigating" SHALL be displayed
- **AND** bugs with other statuses SHALL be excluded

#### Scenario: Filter by multiple statuses

- **GIVEN** the bug reports file contains bugs with various statuses
- **WHEN** developer runs `list --status open,investigating`
- **THEN** bugs with status="open" OR status="investigating" SHALL be displayed
- **AND** bugs with status="resolved", "closed", or "archived" SHALL be excluded

#### Scenario: Default filter excludes archived

- **GIVEN** the bug reports file contains archived bugs
- **WHEN** developer runs `list` without status filter
- **THEN** archived bugs SHALL be excluded by default
- **AND** only active bugs (open, investigating, resolved, closed) SHALL be shown

### Requirement: Bug Status Audit Trail

All status changes SHALL be recorded as append-only JSONL entries to maintain a complete audit trail.

#### Scenario: Full status history preserved

- **GIVEN** a bug has been updated multiple times (open → investigating → resolved → archived)
- **WHEN** reading all JSONL entries for that bug ID
- **THEN** all status transitions SHALL be present in the file
- **AND** each entry SHALL have an `updated_at` timestamp
- **AND** entries SHALL be in chronological order (appended sequentially)

#### Scenario: Status change attribution

- **GIVEN** a bug status update is recorded
- **WHEN** the JSONL entry is written
- **THEN** the entry MAY include an optional `updated_by` field
- **AND** this field SHALL indicate who/what updated the status (e.g., "developer", "automated-script")
- **AND** if omitted, defaults to "manual"

#### Scenario: Reconstruct bug lifecycle

- **GIVEN** a bug with multiple status entries in JSONL
- **WHEN** a developer reviews the bug history
- **THEN** the full lifecycle SHALL be reconstructable:
  - Created at timestamp X with status="open"
  - Updated at timestamp Y to status="investigating"
  - Updated at timestamp Z to status="resolved"
  - Archived at timestamp W with status="archived"
- **AND** timeline is deterministic based on `updated_at` fields

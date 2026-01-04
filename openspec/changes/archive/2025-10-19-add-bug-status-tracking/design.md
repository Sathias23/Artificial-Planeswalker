# Bug Report Status Tracking Design

## Context

The current bug tracking system stores all reports in `data/bug_reports.jsonl` as append-only entries with no status tracking. This makes it impossible to:
- Mark bugs as resolved or closed
- Filter active vs. inactive issues
- Archive old reports
- Track bug lifecycle progress

This design addresses these limitations while maintaining backward compatibility with existing bug reports.

## Goals / Non-Goals

### Goals
- Add status lifecycle tracking (open → investigating → resolved → closed → archived)
- Enable filtering bug reports by status
- Provide archival mechanism for resolved/closed bugs
- Maintain backward compatibility with existing JSONL entries
- Keep append-only JSONL architecture (no in-place edits)

### Non-Goals
- Full bug tracking system with assignments, priorities, labels
- Web UI for bug management (CLI-only for MVP)
- Exposing status management to end users (developer tool only)
- Real-time status updates during chat sessions
- Integration with external issue trackers (GitHub Issues, Jira, etc.)

## Decisions

### Status Lifecycle

**Decision**: Use five status values:
- `open`: New bug report, not yet triaged
- `investigating`: Bug confirmed and being researched
- `resolved`: Bug fixed or addressed
- `closed`: Bug not reproducible, duplicate, or won't fix
- `archived`: Old bug moved to archive for historical reference

**Rationale**:
- `open` vs `investigating`: Distinguishes new reports from active work
- `resolved` vs `closed`: Differentiates "fixed" from "won't fix" or "duplicate"
- `archived`: Separate state for historical records vs. active tracking

**Alternatives considered**:
- Simpler 3-state model (open/resolved/closed) - Rejected: Doesn't distinguish active investigation
- More granular states (triaged, in-progress, testing, verified) - Rejected: Overkill for current needs

### JSONL Schema Evolution

**Decision**: Add optional `status` and `updated_at` fields to JSONL schema:

```json
{
  "id": "uuid",
  "session_id": "string",
  "timestamp": "ISO 8601",
  "description": "string",
  "conversation_context": [],
  "metadata": {},
  "status": "open",           // NEW (default: "open")
  "updated_at": "ISO 8601"    // NEW (default: equals timestamp)
}
```

**Rationale**:
- Backward compatible: Old reports without `status` are treated as "open"
- `updated_at` tracks when status last changed (useful for archival queries)
- No data migration required - handle missing fields at read time

**Alternatives considered**:
- Create new versioned schema (v2) - Rejected: Adds complexity without benefit
- Separate status file (bug_id → status mapping) - Rejected: Two files to manage, synchronization issues

### Status Update Mechanism

**Decision**: JSONL append-only architecture means status updates append new entries:

```jsonl
{"id": "abc-123", "status": "open", "timestamp": "2025-10-18T10:00:00Z", ...}
{"id": "abc-123", "status": "resolved", "updated_at": "2025-10-19T14:30:00Z", "update_type": "status_change"}
```

**Rationale**:
- Preserves append-only architecture (no file rewrites)
- Maintains full audit trail of status changes
- Simplifies file operations (no locking required)

**Alternatives considered**:
- In-place status updates (rewrite entire file) - Rejected: Violates append-only principle, requires file locking
- Separate status log file - Rejected: Harder to query, two files to manage
- Use SQLite database - Rejected: Adds dependency, overkill for current volume

**Implementation note**: When reading bug reports, always use the **latest entry** for each `bug_id` to get current status.

### Archive Process

**Decision**: Move old resolved/closed bugs to `data/bug_reports_archive.jsonl`:
- Criteria: Status = "resolved" or "closed" AND updated_at > 90 days ago
- Process: Copy to archive file, mark as "archived" in original file (append archive entry)
- Frequency: Manual via CLI command (not automated)

**Rationale**:
- Keeps active bug list manageable
- Preserves historical data in separate file
- 90-day threshold balances cleanup vs. accessibility
- Manual process gives developer control

**Alternatives considered**:
- Delete archived bugs - Rejected: Lose historical data
- Automated archival (cron/scheduled) - Rejected: Not needed at current scale
- Keep everything in one file with status filter - Rejected: File grows unbounded

### CLI Tool Design

**Decision**: Create `scripts/manage_bug_reports.py` with subcommands:

```bash
# List bugs filtered by status
uv run python scripts/manage_bug_reports.py list [--status open|investigating|resolved|closed]

# Update bug status
uv run python scripts/manage_bug_reports.py update <bug-id> --status <new-status>

# Archive old bugs
uv run python scripts/manage_bug_reports.py archive [--older-than-days 90] [--dry-run]
```

**Rationale**:
- Familiar CLI pattern (git-style subcommands)
- Scriptable for automation if needed later
- `--dry-run` for safe testing of archive operation

**Alternatives considered**:
- Separate scripts per operation - Rejected: More files to manage
- Interactive TUI - Rejected: Overkill for simple operations
- Python functions only (no CLI) - Rejected: Less accessible for non-developers

## Risks / Trade-offs

### Risk: JSONL File Growth
- **Risk**: Append-only updates increase file size
- **Mitigation**: Archive old bugs periodically; current volume is low (<100 bugs expected)
- **Trade-off**: Accepting file growth for simplicity vs. database complexity

### Risk: Duplicate Bug IDs in JSONL
- **Risk**: Multiple entries per bug ID could confuse parsing
- **Mitigation**: Always read entire file and use latest entry per ID; validate unique IDs on creation
- **Trade-off**: Slight performance cost (read entire file) vs. data integrity

### Risk: Backward Compatibility Issues
- **Risk**: Old code reading new JSONL schema might break
- **Mitigation**: Make new fields optional; document schema version in comments
- **Trade-off**: None - purely additive change

## Migration Plan

### Phase 1: Add Status Field (No Disruption)
1. Update `report_bug()` to include `status="open"` and `updated_at=timestamp`
2. Deploy change - all new bugs created with status
3. Old bugs without status are treated as "open" (backward compatible)

### Phase 2: Add CLI Management Tool
1. Implement `manage_bug_reports.py` script
2. Test on development environment
3. Document usage in CLAUDE.md

### Phase 3: Archive Existing Bugs (Optional)
1. Run `list` command to review current bugs
2. Manually update status of known resolved bugs
3. Run `archive` with `--dry-run` to test
4. Execute archive operation

### Rollback Plan
If issues arise:
- Phase 1: Remove `status` and `updated_at` fields from new bugs (old bugs unaffected)
- Phase 2: Delete CLI script (no impact on existing data)
- Phase 3: Restore archived bugs from `bug_reports_archive.jsonl` by appending back to main file

## Open Questions

1. **Should archived bugs be searchable via CLI?**
   - Proposed: Yes, add `--include-archived` flag to list command
   - Decision: Defer to implementation phase

2. **Should we expose status updates to end users via agent tool?**
   - Proposed: No - keep status management developer-facing only
   - Decision: Confirmed in goals/non-goals

3. **What happens if same bug ID appears with different statuses?**
   - Proposed: Last entry wins (read entire file, keep latest per ID)
   - Decision: Confirmed in design decisions

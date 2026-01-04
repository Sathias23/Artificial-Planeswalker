# Add Bug Report Status Tracking

## Why

**Problem**: Bug tracking system currently has no mechanism to mark bugs as resolved, close obsolete issues, or archive old reports. This leads to:
- **Report clutter**: All bugs remain visible forever, making it difficult to identify active issues
- **No workflow visibility**: Cannot track which bugs are being investigated vs. already fixed
- **No closure process**: No way to indicate when bugs have been addressed
- **Difficult prioritization**: Cannot distinguish between new, active, and resolved issues

**Bug Report Reference**: de430e8a-f523-4e3f-b2bd-1db62d56076c

**Opportunity**: Implementing status tracking enables proper bug lifecycle management, improves visibility into active issues, and provides closure for resolved problems.

## What Changes

- **Add status field** to bug reports with lifecycle states: `open`, `investigating`, `resolved`, `closed`, `archived`
- **Add status update tool** allowing developers to update bug report status (not exposed to end users)
- **Add status filtering** to query bug reports by status (e.g., show only open bugs)
- **Implement archival process** to move old resolved/closed bugs to archive file
- **Update JSONL schema** to include `status` and `updated_at` fields
- **Backward compatibility** for existing bug reports (default status to `open`)

## Impact

- **Affected specs**: agent-tools (bug report requirements)
- **Affected code**:
  - `src/agent/tools/bug_report.py` - Add status field and update logic
  - `data/bug_reports.jsonl` - Schema update (backward compatible)
  - New file: `scripts/manage_bug_reports.py` - CLI for status management
  - New file: `data/bug_reports_archive.jsonl` - Archive storage
- **Data migration**: None required (existing reports default to "open" status)
- **User impact**: None (status management is developer-facing only)
- **Performance impact**: Minimal (additional field in JSONL, optional filtering)

## Research Summary

**Archon RAG Research**:
- Searched for "bug tracking status lifecycle" - No specific results from knowledge base
- Searched for "JSONL append-only data" - No specific results from knowledge base

**Best Practices** (general software engineering):
- Bug lifecycles typically include: New → In Progress → Resolved → Closed → Archived
- JSONL format supports schema evolution through optional fields
- Append-only logs benefit from separate archive files for long-term storage
- Status tracking should distinguish between "fixed" (resolved) and "no longer relevant" (closed)

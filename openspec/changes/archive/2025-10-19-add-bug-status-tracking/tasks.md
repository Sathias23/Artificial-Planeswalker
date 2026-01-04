# Implementation Tasks

## 1. Core Implementation

- [x] 1.1 Add `BugReportStatus` enum to `src/agent/tools/bug_report.py`
- [x] 1.2 Update `report_bug()` to include default status="open"
- [x] 1.3 Add `updated_at` timestamp field to bug report schema
- [x] 1.4 Update `_write_bug_report_jsonl()` to handle status field
- [x] 1.5 Add backward compatibility check (set status="open" for legacy reports without status)

## 2. Status Management Tool

- [x] 2.1 Create `scripts/manage_bug_reports.py` CLI script
- [x] 2.2 Implement `list_bugs(status_filter=None)` - Read and filter bug reports
- [x] 2.3 Implement `update_bug_status(bug_id, new_status)` - Update status and `updated_at`
- [x] 2.4 Implement `archive_bugs(status=["resolved", "closed"], older_than_days=90)` - Move to archive file
- [x] 2.5 Add CLI argument parsing with subcommands (list, update, archive)

## 3. JSONL Schema Updates

- [x] 3.1 Document new schema in bug_report.py docstring
- [x] 3.2 Add status validation (must be valid enum value)
- [x] 3.3 Update example JSONL entries in documentation

## 4. Testing

- [x] 4.1 Unit tests for `BugReportStatus` enum
- [x] 4.2 Unit tests for status update logic
- [x] 4.3 Unit tests for backward compatibility (reading old reports without status)
- [x] 4.4 Integration test for archive process
- [x] 4.5 Test CLI commands (`list`, `update`, `archive`)

## 5. Documentation

- [x] 5.1 Update CLAUDE.md to document bug status workflow
- [x] 5.2 Add usage examples for `manage_bug_reports.py` script
- [x] 5.3 Update agent-tools specification with status tracking requirements

# Implementation Tasks

## 1. Core Implementation

- [x] 1.1 Create `src/agent/tools/bug_report.py` module
  - [x] 1.1.1 Implement `report_bug` tool function with `@agent.tool` decorator
  - [x] 1.1.2 Add function docstring for LLM schema generation
  - [x] 1.1.3 Implement conversation context capture (last 10 messages)
  - [x] 1.1.4 Implement metadata collection (model, session info, timestamp)
  - [x] 1.1.5 Add JSONL file writing logic with error handling
  - [x] 1.1.6 Generate unique report ID using UUID
  - [x] 1.1.7 Return user-friendly confirmation message

- [x] 1.2 Create JSONL utility functions in `bug_report.py`
  - [x] 1.2.1 Implement `_write_bug_report_jsonl()` for atomic append operations
  - [x] 1.2.2 Ensure `data/` directory exists before writing
  - [x] 1.2.3 Handle file creation on first write
  - [x] 1.2.4 Use ISO 8601 timestamps (UTC)

- [x] 1.3 Register bug report tool with agent
  - [x] 1.3.1 Import `report_bug` tool in `src/agent/core.py`
  - [x] 1.3.2 Add tool to agent's tools list in `create_agent()`

## 2. Testing

- [x] 2.1 Create `tests/unit/agent/tools/test_bug_report.py`
  - [x] 2.1.1 Test successful bug report submission
  - [x] 2.1.2 Test conversation context capture (last 10 messages)
  - [x] 2.1.3 Test metadata collection
  - [x] 2.1.4 Test JSONL format validation
  - [x] 2.1.5 Test file creation on first write
  - [x] 2.1.6 Test append operation for multiple reports
  - [x] 2.1.7 Test minimal bug report (no description)
  - [x] 2.1.8 Test file write failure handling
  - [x] 2.1.9 Test UUID generation for report ID
  - [x] 2.1.10 Test ISO 8601 timestamp format

- [x] 2.2 Create integration test in `tests/integration/agent/test_agent_bug_report.py`
  - [x] 2.2.1 Test end-to-end bug report flow with agent
  - [x] 2.2.2 Test agent does not autonomously invoke tool
  - [x] 2.2.3 Test bug report file creation and content
  - [x] 2.2.4 Verify conversation context in generated report

## 3. Documentation

- [x] 3.1 Update `CLAUDE.md` agent tools section
  - [x] 3.1.1 Add `report_bug` to available tools list
  - [x] 3.1.2 Document JSONL log location and format

## 4. Validation

- [x] 4.1 Run OpenSpec validation
  - [x] 4.1.1 Execute `openspec validate add-bug-report-tool --strict`
  - [x] 4.1.2 Fix any validation errors

- [x] 4.2 Run tests
  - [x] 4.2.1 Execute `uv run pytest tests/unit/agent/tools/test_bug_report.py`
  - [x] 4.2.2 Execute `uv run pytest tests/integration/agent/test_agent_bug_report.py`
  - [x] 4.2.3 Verify all tests pass

- [x] 4.3 Manual testing
  - [x] 4.3.1 Start Chainlit UI: `uv run chainlit run src/ui/app.py`
  - [x] 4.3.2 Test bug report submission with user request
  - [x] 4.3.3 Verify JSONL file created at `data/bug_reports.jsonl`
  - [x] 4.3.4 Inspect JSONL content for correctness
  - [x] 4.3.5 Verify agent does not submit reports autonomously

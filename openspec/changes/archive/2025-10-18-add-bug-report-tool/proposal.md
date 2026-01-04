# Add Bug Report Tool

## Why

Users need a mechanism to report issues and unexpected behavior encountered during chat interactions. Currently, there is no way to capture bug reports systematically, making it difficult to track and address user-reported issues.

## What Changes

- Add `report_bug` agent tool that captures user-reported issues with conversation context
- Implement JSONL (JSON Lines) file-based error log at `data/bug_reports.jsonl`
- Capture bug metadata including session ID, timestamp, user description, and conversation context
- Add safeguards to prevent autonomous agent reporting (user must explicitly request bug report submission)

## Impact

- **Affected specs**: `agent-tools`
- **Affected code**:
  - `src/agent/tools/` - New `bug_report.py` module
  - `src/agent/core.py` - Register new tool with agent
  - `tests/unit/agent/tools/` - New `test_bug_report.py` unit tests
  - `tests/integration/agent/` - Integration tests for bug reporting flow

## Research Summary

**Sources**: PydanticAI documentation (Archon RAG source: `ai.pydantic.dev`)

**Key Findings**:
- PydanticAI tools use `@agent.tool` decorator for type-safe tool registration
- Tools access dependencies via `RunContext[AgentDependencies]` parameter
- Tool functions support both sync and async implementations
- Docstrings are used for LLM schema generation and parameter descriptions
- Session context persists across tool invocations via `AgentDependencies`

**Patterns Applied**:
- Follow existing tool pattern from `card_lookup.py` and `card_search.py`
- Use `RunContext[AgentDependencies]` for dependency injection
- JSONL format for append-only, line-by-line parseable error log
- JSON serialization for structured metadata storage

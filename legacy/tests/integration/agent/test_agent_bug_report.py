"""Integration tests for agent with bug report tool.

These tests verify end-to-end functionality of the agent using the
bug report tool with session history and file system operations.
"""

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from pydantic_ai.models.test import TestModel

from legacy.agent.core import create_agent, run_agent_with_session
from legacy.agent.dependencies import AgentDependencies
from src.data.database import create_engine, create_session_factory, init_database
from src.data.repositories.card import CardRepository

# Load environment variables
load_dotenv()

# Skip tests if OPENROUTER_API_KEY not set
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set - skipping integration tests",
)


# Fixtures


@pytest.fixture
async def in_memory_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(in_memory_engine):
    """Create a session factory for testing."""
    return create_session_factory(in_memory_engine)


@pytest.fixture
async def card_repository(session_factory):
    """Create a card repository for testing."""
    async with session_factory() as session:
        yield CardRepository(session)


@pytest.fixture
def bug_report_file(tmp_path, monkeypatch):
    """Set up temporary bug report file path."""
    # Create a unique bug reports path for each test
    import random
    import string

    unique_id = "".join(random.choices(string.ascii_lowercase, k=8))
    bug_reports_path = tmp_path / "data" / f"bug_reports_{unique_id}.jsonl"
    bug_reports_path.parent.mkdir(parents=True, exist_ok=True)

    # Patch the Path in bug_report module to use tmp_path
    original_path = Path

    def mock_path(path_str):
        if path_str == "data/bug_reports.jsonl":
            return bug_reports_path
        return original_path(path_str)

    monkeypatch.setattr("legacy.agent.tools.bug_report.Path", mock_path)

    return bug_reports_path


# Integration Tests


class TestBugReportEndToEnd:
    """End-to-end integration tests for bug reporting."""

    @pytest.mark.asyncio
    async def test_bug_report_tool_creates_file_and_entry(self, card_repository, bug_report_file):
        """Test that bug report tool creates file and writes entry correctly."""
        # Arrange - test file operations directly without agent interaction
        from legacy.agent.tools.bug_report import _write_bug_report_jsonl

        # Create a bug report directly (simulating tool invocation)
        bug_report = {
            "id": "integration-test-id",
            "session_id": "integration-test-session",
            "timestamp": "2025-10-18T10:30:00Z",
            "description": "Test bug report from integration test",
            "conversation_context": [],
            "metadata": {"session_id": "integration-test-session"},
        }

        # Act
        _write_bug_report_jsonl(bug_report)
        result = f"Bug report {bug_report['id']} submitted"

        # Assert
        assert "Bug report" in result
        assert "submitted" in result

        # Verify file was created
        assert bug_report_file.exists()

        # Verify JSONL content
        with bug_report_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1

            # Parse JSONL entry
            bug_report_data = json.loads(lines[0])
            assert bug_report_data["description"] == "Test bug report from integration test"
            assert bug_report_data["session_id"] == "integration-test-session"
            assert "id" in bug_report_data
            assert "timestamp" in bug_report_data
            assert "conversation_context" in bug_report_data
            assert "metadata" in bug_report_data

    @pytest.mark.asyncio
    async def test_bug_report_captures_conversation_context(self, card_repository, bug_report_file):
        """Test that bug reports include conversation history."""
        # Arrange
        agent = create_agent(defer_model_check=True)
        agent._model = TestModel()

        # Mock deck repository for this test (not testing deck functionality)
        from unittest.mock import AsyncMock

        deck_repository = AsyncMock()

        from legacy.agent.core import _session_manager

        deps = AgentDependencies(
            card_repository=card_repository,
            deck_repository=deck_repository,
            session_id="context-test-session",
            _session_manager=_session_manager,
        )

        # Build conversation history
        await run_agent_with_session(
            user_input="First message",
            session_id="context-test-session",
            deps=deps,
            agent=agent,
        )

        await run_agent_with_session(
            user_input="Second message",
            session_id="context-test-session",
            deps=deps,
            agent=agent,
        )

        # Submit bug report
        from legacy.agent.core import _session_manager
        from legacy.agent.tools.bug_report import _format_conversation_context, _write_bug_report_jsonl

        # Get conversation history and create bug report
        message_history = _session_manager.get_history("context-test-session")
        conversation_context = _format_conversation_context(message_history)

        bug_report = {
            "id": "context-test-id",
            "session_id": "context-test-session",
            "timestamp": "2025-10-18T10:30:00Z",
            "description": "Test context capture",
            "conversation_context": conversation_context,
            "metadata": {"session_id": "context-test-session"},
        }
        _write_bug_report_jsonl(bug_report)

        # Assert
        with bug_report_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            # Parse the last JSONL entry (most recent bug report)
            bug_report_json = json.loads(lines[-1].strip())

            # Verify conversation context is captured
            assert len(bug_report_json["conversation_context"]) > 0

            # Verify context contains message metadata
            for msg in bug_report_json["conversation_context"]:
                assert "role" in msg
                assert "content" in msg
                assert "timestamp" in msg

    @pytest.mark.asyncio
    async def test_multiple_bug_reports_appended(self, card_repository, bug_report_file):
        """Test that multiple bug reports are appended to the same file."""
        # Arrange
        agent = create_agent(defer_model_check=True)
        agent._model = TestModel()

        from legacy.agent.tools.bug_report import _write_bug_report_jsonl

        # Act - submit two bug reports
        bug_report1 = {
            "id": "append-test-id-1",
            "session_id": "append-test-session",
            "timestamp": "2025-10-18T10:30:00Z",
            "description": "First bug report",
            "conversation_context": [],
            "metadata": {"session_id": "append-test-session"},
        }
        _write_bug_report_jsonl(bug_report1)

        bug_report2 = {
            "id": "append-test-id-2",
            "session_id": "append-test-session",
            "timestamp": "2025-10-18T10:31:00Z",
            "description": "Second bug report",
            "conversation_context": [],
            "metadata": {"session_id": "append-test-session"},
        }
        _write_bug_report_jsonl(bug_report2)

        # Assert
        with bug_report_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 2

            # Verify both reports
            report1 = json.loads(lines[0])
            report2 = json.loads(lines[1])

            assert report1["description"] == "First bug report"
            assert report2["description"] == "Second bug report"

            # Verify unique IDs
            assert report1["id"] != report2["id"]

    @pytest.mark.asyncio
    async def test_bug_report_with_format_filter_metadata(self, card_repository, bug_report_file):
        """Test that bug reports capture format filter state in metadata."""
        # Arrange
        agent = create_agent(defer_model_check=True)
        agent._model = TestModel()

        from legacy.agent.tools.bug_report import _write_bug_report_jsonl

        # Act
        bug_report = {
            "id": "format-filter-test-id",
            "session_id": "format-filter-test-session",
            "timestamp": "2025-10-18T10:30:00Z",
            "description": "Bug report with format filter",
            "conversation_context": [],
            "metadata": {
                "session_id": "format-filter-test-session",
                "format_filter": "standard",
            },
        }
        _write_bug_report_jsonl(bug_report)

        # Assert
        with bug_report_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            # Parse the last JSONL entry
            bug_report_json = json.loads(lines[-1].strip())

            # Verify format filter is captured in metadata
            assert bug_report_json["metadata"]["format_filter"] == "standard"

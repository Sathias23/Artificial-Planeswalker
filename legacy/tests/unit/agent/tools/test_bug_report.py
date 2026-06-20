"""Unit tests for bug report tool."""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from legacy.agent.dependencies import AgentDependencies
from legacy.agent.tools.bug_report import (
    BugReportStatus,
    _format_conversation_context,
    _write_bug_report_jsonl,
    report_bug,
)

# Fixtures


@pytest.fixture
def mock_card_repository():
    """Create a mock CardRepository for testing."""
    return MagicMock()


@pytest.fixture
def mock_dependencies(mock_card_repository, mock_session_manager):
    """Create mock AgentDependencies for testing."""
    mock_deck_repository = MagicMock()
    return AgentDependencies(
        card_repository=mock_card_repository,
        deck_repository=mock_deck_repository,
        session_id="test-session-123",
        _session_manager=mock_session_manager,
        format_filter="standard",
    )


@pytest.fixture
def mock_run_context(mock_dependencies):
    """Create a mock RunContext for testing."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_dependencies
    return ctx


@pytest.fixture
def sample_message_history():
    """Create sample message history for testing."""
    # Create realistic message history with user prompts and agent responses
    messages = [
        # System message (should be excluded from context)
        ModelRequest(parts=[SystemPromptPart(content="You are a helpful assistant.")]),
        # User message
        ModelRequest(parts=[UserPromptPart(content="Show me Lightning Bolt")]),
        # Agent response
        ModelResponse(
            parts=[TextPart(content="Here is Lightning Bolt: An instant that deals 3 damage...")]
        ),
        # Another user message
        ModelRequest(parts=[UserPromptPart(content="Find red creatures with haste")]),
        # Another agent response
        ModelResponse(
            parts=[TextPart(content="I found 5 red creatures with haste: Goblin Guide...")]
        ),
    ]
    return messages


# Tests for report_bug


class TestReportBug:
    """Tests for the report_bug tool."""

    @pytest.mark.asyncio
    async def test_successful_bug_report_submission(
        self, mock_run_context, tmp_path, sample_message_history
    ):
        """Test successful bug report with user description."""
        # Arrange
        description = "Search returned wrong cards for Lightning Bolt"

        # Mock session manager to return message history
        with (
            patch("legacy.agent.core._session_manager") as mock_session_mgr,
            patch("legacy.agent.tools.bug_report.Path") as mock_path_cls,
            patch("uuid.uuid4") as mock_uuid,
            patch("legacy.agent.tools.bug_report.datetime") as mock_datetime,
        ):
            # Setup mocks
            mock_session_mgr.get_history.return_value = sample_message_history
            mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")
            mock_dt = datetime(2025, 10, 18, 10, 30, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_dt
            mock_datetime.UTC = UTC

            # Setup file path mock
            file_path = tmp_path / "data" / "bug_reports.jsonl"
            file_path.parent.mkdir(parents=True)
            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            mock_path_instance.open = MagicMock(return_value=file_path.open("a", encoding="utf-8"))
            mock_path_cls.return_value = mock_path_instance

            # Act
            result = await report_bug(mock_run_context, description)

            # Assert
            assert "Bug report 12345678-1234-5678-1234-567812345678 submitted" in result
            assert "Thank you for reporting this issue" in result

            # Verify session manager was called
            mock_session_mgr.get_history.assert_called_once_with("test-session-123")

            # Verify file was written
            mock_path_instance.open.assert_called_once_with("a", encoding="utf-8")

    @pytest.mark.asyncio
    async def test_minimal_bug_report_no_description(
        self, mock_run_context, tmp_path, sample_message_history
    ):
        """Test bug report with default description when user provides none."""
        # Arrange - use default description
        with (
            patch("legacy.agent.core._session_manager") as mock_session_mgr,
            patch("legacy.agent.tools.bug_report.Path") as mock_path_cls,
            patch("uuid.uuid4") as mock_uuid,
        ):
            mock_session_mgr.get_history.return_value = sample_message_history
            mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")

            # Setup file path mock
            file_path = tmp_path / "data" / "bug_reports.jsonl"
            file_path.parent.mkdir(parents=True)
            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            mock_path_instance.open = MagicMock(return_value=file_path.open("a", encoding="utf-8"))
            mock_path_cls.return_value = mock_path_instance

            # Act - call with default description
            result = await report_bug(mock_run_context)

            # Assert
            assert "Bug report 12345678-1234-5678-1234-567812345678 submitted" in result

    @pytest.mark.asyncio
    async def test_conversation_context_capture_last_10_messages(self, mock_run_context):
        """Test that conversation context is limited to last 10 messages."""
        # Arrange - create 15 user messages (30 total with responses)
        messages = []
        for i in range(15):
            messages.append(ModelRequest(parts=[UserPromptPart(content=f"User message {i}")]))
            messages.append(ModelResponse(parts=[TextPart(content=f"Agent response {i}")]))

        with patch("legacy.agent.core._session_manager") as mock_session_mgr:
            mock_session_mgr.get_history.return_value = messages

            # Act
            context = _format_conversation_context(messages)

            # Assert - should only have last 10 messages
            assert len(context) <= 10
            # Verify it's the most recent messages (last 10 from 30 total messages)
            # The last message should be "Agent response 14"
            assert "Agent response 14" in context[-1]["content"]

    @pytest.mark.asyncio
    async def test_metadata_collection(self, mock_run_context, tmp_path, sample_message_history):
        """Test that metadata is correctly collected."""
        # Arrange
        mock_run_context.deps.session_id = "session-abc-123"
        mock_run_context.deps.format_filter = "standard"

        with (
            patch("legacy.agent.core._session_manager") as mock_session_mgr,
            patch("legacy.agent.tools.bug_report.Path") as mock_path_cls,
            patch("uuid.uuid4") as mock_uuid,
            patch("legacy.agent.tools.bug_report.datetime") as mock_datetime,
        ):
            mock_session_mgr.get_history.return_value = sample_message_history
            mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")
            mock_dt = datetime(2025, 10, 18, 10, 30, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_dt
            mock_datetime.UTC = UTC

            # Capture the written bug report
            written_data = []

            def capture_write(content):
                written_data.append(content)

            file_mock = MagicMock()
            file_mock.write = capture_write
            file_mock.__enter__ = MagicMock(return_value=file_mock)
            file_mock.__exit__ = MagicMock(return_value=False)

            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            mock_path_instance.open = MagicMock(return_value=file_mock)
            mock_path_cls.return_value = mock_path_instance

            # Act
            await report_bug(mock_run_context, "Test bug")

            # Assert - parse written JSON
            json_line = written_data[0].strip()
            bug_report = json.loads(json_line)

            assert bug_report["metadata"]["session_id"] == "session-abc-123"
            assert bug_report["metadata"]["format_filter"] == "standard"
            assert "timestamp" in bug_report["metadata"]

    @pytest.mark.asyncio
    async def test_uuid_generation(self, mock_run_context, tmp_path, sample_message_history):
        """Test that unique UUIDs are generated for report IDs."""
        # Arrange
        with (
            patch("legacy.agent.core._session_manager") as mock_session_mgr,
            patch("legacy.agent.tools.bug_report.Path") as mock_path_cls,
            patch("uuid.uuid4") as mock_uuid,
        ):
            mock_session_mgr.get_history.return_value = sample_message_history

            # First call
            mock_uuid.return_value = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

            file_path = tmp_path / "data" / "bug_reports.jsonl"
            file_path.parent.mkdir(parents=True)
            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            # Return a new file handle for each call
            mock_path_instance.open = MagicMock(
                side_effect=[
                    file_path.open("a", encoding="utf-8"),
                    file_path.open("a", encoding="utf-8"),
                ]
            )
            mock_path_cls.return_value = mock_path_instance

            result1 = await report_bug(mock_run_context, "Bug 1")
            assert "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in result1

            # Second call with different UUID
            mock_uuid.return_value = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
            result2 = await report_bug(mock_run_context, "Bug 2")
            assert "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" in result2

    @pytest.mark.asyncio
    async def test_iso_8601_timestamp_format(
        self, mock_run_context, tmp_path, sample_message_history
    ):
        """Test that timestamps use ISO 8601 format in UTC."""
        # Arrange
        with (
            patch("legacy.agent.core._session_manager") as mock_session_mgr,
            patch("legacy.agent.tools.bug_report.Path") as mock_path_cls,
            patch("legacy.agent.tools.bug_report.datetime") as mock_datetime,
        ):
            mock_session_mgr.get_history.return_value = sample_message_history
            mock_dt = datetime(2025, 10, 18, 14, 30, 45, 123456, tzinfo=UTC)
            mock_datetime.now.return_value = mock_dt
            mock_datetime.UTC = UTC

            # Capture written data
            written_data = []

            def capture_write(content):
                written_data.append(content)

            file_mock = MagicMock()
            file_mock.write = capture_write
            file_mock.__enter__ = MagicMock(return_value=file_mock)
            file_mock.__exit__ = MagicMock(return_value=False)

            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            mock_path_instance.open = MagicMock(return_value=file_mock)
            mock_path_cls.return_value = mock_path_instance

            # Act
            await report_bug(mock_run_context, "Test bug")

            # Assert - verify ISO 8601 format
            json_line = written_data[0].strip()
            bug_report = json.loads(json_line)
            timestamp = bug_report["timestamp"]

            # ISO 8601 format: YYYY-MM-DDTHH:MM:SS.ffffffZ
            assert timestamp == "2025-10-18T14:30:45.123456+00:00"

    @pytest.mark.asyncio
    async def test_file_write_failure_handling(self, mock_run_context, sample_message_history):
        """Test that file write failures raise RuntimeError."""
        # Arrange
        with (
            patch("legacy.agent.core._session_manager") as mock_session_mgr,
            patch("legacy.agent.tools.bug_report.Path") as mock_path_cls,
        ):
            mock_session_mgr.get_history.return_value = sample_message_history

            # Simulate permission error
            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            mock_path_instance.open.side_effect = PermissionError("Permission denied")
            mock_path_cls.return_value = mock_path_instance

            # Act & Assert
            with pytest.raises(RuntimeError, match="Unable to save bug report"):
                await report_bug(mock_run_context, "Test bug")


# Tests for _write_bug_report_jsonl


class TestWriteBugReportJsonl:
    """Tests for the _write_bug_report_jsonl utility function."""

    def test_file_creation_on_first_write(self, tmp_path):
        """Test that file and directory are created on first write."""
        # Arrange
        with patch("legacy.agent.tools.bug_report.Path") as mock_path_cls:
            file_path = tmp_path / "data" / "bug_reports.jsonl"
            # Create parent directory for test
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mock_path_instance = MagicMock()
            # Mock the parent's mkdir method properly
            mock_parent = MagicMock()
            mock_parent.mkdir = MagicMock()
            mock_path_instance.parent = mock_parent
            mock_path_instance.open = MagicMock(return_value=file_path.open("a", encoding="utf-8"))
            mock_path_cls.return_value = mock_path_instance

            bug_report = {
                "id": "test-id",
                "session_id": "session-1",
                "timestamp": "2025-10-18T10:30:00Z",
                "description": "Test bug",
                "conversation_context": [],
                "metadata": {},
            }

            # Act
            _write_bug_report_jsonl(bug_report)

            # Assert
            mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_append_operation_for_multiple_reports(self, tmp_path):
        """Test that multiple reports are appended to the file."""
        # Arrange
        file_path = tmp_path / "bug_reports.jsonl"

        # Create test reports
        report1 = {
            "id": "report-1",
            "session_id": "session-1",
            "timestamp": "2025-10-18T10:00:00Z",
            "description": "First bug",
            "conversation_context": [],
            "metadata": {},
        }
        report2 = {
            "id": "report-2",
            "session_id": "session-2",
            "timestamp": "2025-10-18T11:00:00Z",
            "description": "Second bug",
            "conversation_context": [],
            "metadata": {},
        }

        # Act - write both reports
        with patch("legacy.agent.tools.bug_report.Path") as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            # Return a new file handle for each call
            mock_path_instance.open = MagicMock(
                side_effect=[
                    file_path.open("a", encoding="utf-8"),
                    file_path.open("a", encoding="utf-8"),
                ]
            )
            mock_path_cls.return_value = mock_path_instance

            _write_bug_report_jsonl(report1)
            _write_bug_report_jsonl(report2)

        # Assert - verify both reports in file
        lines = file_path.read_text().strip().split("\n")
        assert len(lines) == 2

        parsed_report1 = json.loads(lines[0])
        parsed_report2 = json.loads(lines[1])
        assert parsed_report1["id"] == "report-1"
        assert parsed_report2["id"] == "report-2"

    def test_jsonl_format_validation(self, tmp_path):
        """Test that written data is valid JSONL format."""
        # Arrange
        file_path = tmp_path / "bug_reports.jsonl"
        bug_report = {
            "id": "test-id-123",
            "session_id": "session-abc",
            "timestamp": "2025-10-18T10:30:00Z",
            "description": "Test bug with unicode: 日本語",
            "conversation_context": [
                {"role": "user", "content": "Test message", "timestamp": "2025-10-18T10:29:00Z"}
            ],
            "metadata": {"session_id": "session-abc", "format_filter": "standard"},
        }

        # Act
        with patch("legacy.agent.tools.bug_report.Path") as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            mock_path_instance.open = MagicMock(return_value=file_path.open("a", encoding="utf-8"))
            mock_path_cls.return_value = mock_path_instance

            _write_bug_report_jsonl(bug_report)

        # Assert - verify valid JSON
        json_line = file_path.read_text().strip()
        parsed = json.loads(json_line)

        assert parsed["id"] == "test-id-123"
        assert parsed["description"] == "Test bug with unicode: 日本語"
        assert len(parsed["conversation_context"]) == 1


# Tests for _format_conversation_context


class TestFormatConversationContext:
    """Tests for the _format_conversation_context helper function."""

    def test_empty_conversation_context(self):
        """Test formatting with no messages returns empty list."""
        # Arrange
        messages: list[ModelMessage] = []

        # Act
        result = _format_conversation_context(messages)

        # Assert
        assert result == []

    def test_context_includes_message_metadata(self):
        """Test that formatted context includes role, content, timestamp."""
        # Arrange
        messages = [
            ModelRequest(parts=[UserPromptPart(content="Hello")]),
            ModelResponse(parts=[TextPart(content="Hi there")]),
        ]

        # Act
        result = _format_conversation_context(messages)

        # Assert
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert "timestamp" in result[0]
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Hi there"
        assert "timestamp" in result[1]

    def test_context_limited_to_last_10_messages(self):
        """Test that context is limited to last 10 messages."""
        # Arrange - create 15 messages
        messages = []
        for i in range(15):
            messages.append(ModelRequest(parts=[UserPromptPart(content=f"Message {i}")]))

        # Act
        result = _format_conversation_context(messages)

        # Assert
        assert len(result) <= 10
        # Verify it's the most recent messages (5-14)
        assert "Message 14" in result[-1]["content"]
        assert "Message 5" in result[0]["content"]


# Tests for Bug Report Status Tracking


class TestBugReportStatus:
    """Tests for the BugReportStatus enum."""

    def test_status_enum_values(self):
        """Test that all expected status values are defined."""
        # Assert all status values exist
        assert BugReportStatus.OPEN.value == "open"
        assert BugReportStatus.INVESTIGATING.value == "investigating"
        assert BugReportStatus.RESOLVED.value == "resolved"
        assert BugReportStatus.CLOSED.value == "closed"
        assert BugReportStatus.ARCHIVED.value == "archived"

    def test_status_enum_count(self):
        """Test that enum contains exactly 5 status values."""
        # Assert
        assert len(BugReportStatus) == 5

    def test_status_values_are_lowercase(self):
        """Test that all status values are lowercase strings."""
        # Assert
        for status in BugReportStatus:
            assert status.value.islower()
            assert isinstance(status.value, str)


class TestBugReportWithStatus:
    """Tests for bug report creation with status tracking."""

    @pytest.mark.asyncio
    async def test_new_bug_report_has_default_status_open(
        self, mock_run_context, tmp_path, sample_message_history
    ):
        """Test that new bug reports default to status='open'."""
        # Arrange
        with (
            patch("legacy.agent.core._session_manager") as mock_session_mgr,
            patch("legacy.agent.tools.bug_report.Path") as mock_path_cls,
        ):
            mock_session_mgr.get_history.return_value = sample_message_history

            # Capture written data
            written_data = []

            def capture_write(content):
                written_data.append(content)

            file_mock = MagicMock()
            file_mock.write = capture_write
            file_mock.__enter__ = MagicMock(return_value=file_mock)
            file_mock.__exit__ = MagicMock(return_value=False)

            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            mock_path_instance.open = MagicMock(return_value=file_mock)
            mock_path_cls.return_value = mock_path_instance

            # Act
            await report_bug(mock_run_context, "Test bug")

            # Assert - parse written JSON and verify status
            json_line = written_data[0].strip()
            bug_report = json.loads(json_line)

            assert bug_report["status"] == "open"
            assert bug_report["status"] == BugReportStatus.OPEN.value

    @pytest.mark.asyncio
    async def test_new_bug_report_has_updated_at_field(
        self, mock_run_context, tmp_path, sample_message_history
    ):
        """Test that new bug reports include updated_at timestamp."""
        # Arrange
        with (
            patch("legacy.agent.core._session_manager") as mock_session_mgr,
            patch("legacy.agent.tools.bug_report.Path") as mock_path_cls,
            patch("legacy.agent.tools.bug_report.datetime") as mock_datetime,
        ):
            mock_session_mgr.get_history.return_value = sample_message_history
            mock_dt = datetime(2025, 10, 18, 14, 30, 45, 123456, tzinfo=UTC)
            mock_datetime.now.return_value = mock_dt
            mock_datetime.UTC = UTC

            # Capture written data
            written_data = []

            def capture_write(content):
                written_data.append(content)

            file_mock = MagicMock()
            file_mock.write = capture_write
            file_mock.__enter__ = MagicMock(return_value=file_mock)
            file_mock.__exit__ = MagicMock(return_value=False)

            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            mock_path_instance.open = MagicMock(return_value=file_mock)
            mock_path_cls.return_value = mock_path_instance

            # Act
            await report_bug(mock_run_context, "Test bug")

            # Assert - parse written JSON and verify updated_at
            json_line = written_data[0].strip()
            bug_report = json.loads(json_line)

            assert "updated_at" in bug_report
            # For new reports, updated_at should equal timestamp
            assert bug_report["updated_at"] == bug_report["timestamp"]
            assert bug_report["updated_at"] == "2025-10-18T14:30:45.123456+00:00"

    @pytest.mark.asyncio
    async def test_bug_report_schema_includes_all_status_fields(
        self, mock_run_context, tmp_path, sample_message_history
    ):
        """Test that bug report schema includes all required status fields."""
        # Arrange
        with (
            patch("legacy.agent.core._session_manager") as mock_session_mgr,
            patch("legacy.agent.tools.bug_report.Path") as mock_path_cls,
        ):
            mock_session_mgr.get_history.return_value = sample_message_history

            # Capture written data
            written_data = []

            def capture_write(content):
                written_data.append(content)

            file_mock = MagicMock()
            file_mock.write = capture_write
            file_mock.__enter__ = MagicMock(return_value=file_mock)
            file_mock.__exit__ = MagicMock(return_value=False)

            mock_path_instance = MagicMock()
            mock_path_instance.parent.mkdir = MagicMock()
            mock_path_instance.open = MagicMock(return_value=file_mock)
            mock_path_cls.return_value = mock_path_instance

            # Act
            await report_bug(mock_run_context, "Test bug")

            # Assert - verify all required fields
            json_line = written_data[0].strip()
            bug_report = json.loads(json_line)

            # Original fields
            assert "id" in bug_report
            assert "session_id" in bug_report
            assert "timestamp" in bug_report
            assert "description" in bug_report
            assert "conversation_context" in bug_report
            assert "metadata" in bug_report

            # New status tracking fields
            assert "status" in bug_report
            assert "updated_at" in bug_report

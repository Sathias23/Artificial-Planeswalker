"""Unit tests for format filter control tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext

from legacy.agent.dependencies import AgentDependencies
from legacy.agent.tools.format_filter import set_format_filter


@pytest.fixture
def mock_dependencies(mock_session_manager):
    """Create mock dependencies for testing."""
    mock_repo = AsyncMock()
    mock_deck_repo = AsyncMock()
    deps = AgentDependencies(
        card_repository=mock_repo,
        deck_repository=mock_deck_repo,
        session_id="test-session",
        _session_manager=mock_session_manager,
        format_filter=None,
    )
    return deps


@pytest.fixture
def mock_context(mock_dependencies):
    """Create mock RunContext for testing."""
    context = MagicMock(spec=RunContext)
    context.deps = mock_dependencies
    return context


class TestSetFormatFilter:
    """Tests for set_format_filter tool."""

    async def test_enable_standard_filter(self, mock_context: MagicMock) -> None:
        """Test enabling Standard format filter."""
        result = await set_format_filter(mock_context, "standard")

        assert mock_context.deps.format_filter == "standard"
        assert "Standard" in result
        assert "only show Standard-legal cards" in result

    async def test_enable_standard_filter_case_insensitive(self, mock_context: MagicMock) -> None:
        """Test enabling Standard filter with different case."""
        result = await set_format_filter(mock_context, "STANDARD")

        assert mock_context.deps.format_filter == "standard"
        assert "Standard" in result

    async def test_disable_filter_with_none(self, mock_context: MagicMock) -> None:
        """Test disabling format filter with None."""
        # First enable a filter
        mock_context.deps.format_filter = "standard"

        # Then disable it
        result = await set_format_filter(mock_context, None)

        assert mock_context.deps.format_filter is None
        assert "disabled" in result
        assert "all cards regardless of format" in result

    async def test_disable_filter_with_empty_string(self, mock_context: MagicMock) -> None:
        """Test disabling format filter with empty string."""
        # First enable a filter
        mock_context.deps.format_filter = "standard"

        # Then disable it with empty string
        result = await set_format_filter(mock_context, "")

        assert mock_context.deps.format_filter is None
        assert "disabled" in result

    async def test_unsupported_format(self, mock_context: MagicMock) -> None:
        """Test attempting to set an unsupported format."""
        result = await set_format_filter(mock_context, "modern")

        # Format should remain unchanged
        assert mock_context.deps.format_filter is None
        assert "not supported yet" in result
        assert "modern" in result
        assert "standard" in result.lower()

    async def test_filter_persists_across_calls(self, mock_context: MagicMock) -> None:
        """Test that filter setting persists in context."""
        # Enable filter
        await set_format_filter(mock_context, "standard")
        assert mock_context.deps.format_filter == "standard"

        # Filter should still be set
        assert mock_context.deps.format_filter == "standard"

        # Disable filter
        await set_format_filter(mock_context, None)
        assert mock_context.deps.format_filter is None

    async def test_switch_between_formats(self, mock_context: MagicMock) -> None:
        """Test switching between different format settings."""
        # Enable Standard
        result1 = await set_format_filter(mock_context, "standard")
        assert mock_context.deps.format_filter == "standard"
        assert "Standard" in result1

        # Try to switch to unsupported format
        result2 = await set_format_filter(mock_context, "commander")
        assert mock_context.deps.format_filter == "standard"  # Should remain unchanged
        assert "not supported" in result2

        # Disable
        result3 = await set_format_filter(mock_context, None)
        assert mock_context.deps.format_filter is None
        assert "disabled" in result3

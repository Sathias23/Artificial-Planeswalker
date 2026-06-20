"""Unit tests for games filter control tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext

from legacy.agent.dependencies import AgentDependencies
from legacy.agent.tools.games_filter import set_games_filter


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
        games_filter=None,
    )
    return deps


@pytest.fixture
def mock_context(mock_dependencies):
    """Create mock RunContext for testing."""
    context = MagicMock(spec=RunContext)
    context.deps = mock_dependencies
    return context


class TestSetGamesFilter:
    """Tests for set_games_filter tool."""

    async def test_enable_arena_filter(self, mock_context: MagicMock) -> None:
        """Test enabling Arena games filter."""
        result = await set_games_filter(mock_context, ["arena"])

        assert mock_context.deps.games_filter == ["arena"]
        assert "Arena" in result
        assert "only show cards available on Arena" in result

    async def test_enable_paper_filter(self, mock_context: MagicMock) -> None:
        """Test enabling paper games filter."""
        result = await set_games_filter(mock_context, ["paper"])

        assert mock_context.deps.games_filter == ["paper"]
        assert "Paper" in result
        assert "only show cards available on Paper" in result

    async def test_enable_mtgo_filter(self, mock_context: MagicMock) -> None:
        """Test enabling MTGO games filter."""
        result = await set_games_filter(mock_context, ["mtgo"])

        assert mock_context.deps.games_filter == ["mtgo"]
        assert "Mtgo" in result
        assert "only show cards available on Mtgo" in result

    async def test_enable_multiple_games_filter(self, mock_context: MagicMock) -> None:
        """Test enabling filter with multiple games (OR logic)."""
        result = await set_games_filter(mock_context, ["paper", "arena"])

        assert mock_context.deps.games_filter == ["paper", "arena"]
        assert "Paper and Arena" in result
        assert "only show cards available on Paper and Arena" in result

    async def test_enable_filter_case_insensitive(self, mock_context: MagicMock) -> None:
        """Test enabling filter with uppercase game names (normalized to lowercase)."""
        result = await set_games_filter(mock_context, ["ARENA", "PAPER"])

        assert mock_context.deps.games_filter == ["arena", "paper"]
        assert "Arena and Paper" in result

    async def test_disable_filter_with_none(self, mock_context: MagicMock) -> None:
        """Test disabling games filter with None."""
        # First enable a filter
        mock_context.deps.games_filter = ["arena"]

        # Then disable it
        result = await set_games_filter(mock_context, None)

        assert mock_context.deps.games_filter is None
        assert "disabled" in result
        assert "all cards regardless of platform" in result

    async def test_disable_filter_with_empty_list(self, mock_context: MagicMock) -> None:
        """Test disabling games filter with empty list."""
        # First enable a filter
        mock_context.deps.games_filter = ["paper", "mtgo"]

        # Then disable it with empty list
        result = await set_games_filter(mock_context, [])

        assert mock_context.deps.games_filter is None
        assert "disabled" in result

    async def test_invalid_game_name(self, mock_context: MagicMock) -> None:
        """Test attempting to set an invalid game name."""
        result = await set_games_filter(mock_context, ["invalid_platform"])

        # Filter should remain unchanged (None)
        assert mock_context.deps.games_filter is None
        assert "Invalid game(s): invalid_platform" in result
        assert "Valid options are:" in result
        assert "paper" in result
        assert "arena" in result
        assert "mtgo" in result

    async def test_mixed_valid_and_invalid_games(self, mock_context: MagicMock) -> None:
        """Test attempting to set mix of valid and invalid games."""
        result = await set_games_filter(mock_context, ["arena", "invalid"])

        # Filter should remain unchanged
        assert mock_context.deps.games_filter is None
        assert "Invalid game(s): invalid" in result
        assert "Valid options are:" in result

    async def test_filter_persists_across_calls(self, mock_context: MagicMock) -> None:
        """Test that filter setting persists in context."""
        # Enable filter
        await set_games_filter(mock_context, ["arena"])
        assert mock_context.deps.games_filter == ["arena"]

        # Filter should still be set
        assert mock_context.deps.games_filter == ["arena"]

        # Disable filter
        await set_games_filter(mock_context, None)
        assert mock_context.deps.games_filter is None

    async def test_switch_between_games(self, mock_context: MagicMock) -> None:
        """Test switching between different game settings."""
        # Enable Arena
        result1 = await set_games_filter(mock_context, ["arena"])
        assert mock_context.deps.games_filter == ["arena"]
        assert "Arena" in result1

        # Switch to paper
        result2 = await set_games_filter(mock_context, ["paper"])
        assert mock_context.deps.games_filter == ["paper"]
        assert "Paper" in result2

        # Switch to multiple games
        result3 = await set_games_filter(mock_context, ["paper", "mtgo"])
        assert mock_context.deps.games_filter == ["paper", "mtgo"]
        assert "Paper and Mtgo" in result3

        # Disable
        result4 = await set_games_filter(mock_context, None)
        assert mock_context.deps.games_filter is None
        assert "disabled" in result4

    async def test_three_games_filter(self, mock_context: MagicMock) -> None:
        """Test enabling filter with all three games."""
        result = await set_games_filter(mock_context, ["paper", "arena", "mtgo"])

        assert mock_context.deps.games_filter == ["paper", "arena", "mtgo"]
        assert "Paper and Arena and Mtgo" in result

    async def test_duplicate_games_normalized(self, mock_context: MagicMock) -> None:
        """Test that duplicate games are handled (normalized to lowercase)."""
        result = await set_games_filter(mock_context, ["Arena", "ARENA", "arena"])

        # Should be normalized to lowercase (duplicates will exist but functionally same)
        assert mock_context.deps.games_filter == ["arena", "arena", "arena"]
        # The message should still work correctly
        assert "Arena" in result

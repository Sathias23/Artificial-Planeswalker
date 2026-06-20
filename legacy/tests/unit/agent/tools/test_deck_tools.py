"""Unit tests for deck management tools."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic_ai import RunContext

from legacy.agent.dependencies import AgentDependencies
from legacy.agent.tools.deck_tools import create_deck, load_deck
from src.data.schemas.deck import Deck


@pytest.fixture
def mock_dependencies(mock_session_manager):
    """Create mock dependencies for testing."""
    mock_card_repo = AsyncMock()
    mock_deck_repo = AsyncMock()
    deps = AgentDependencies(
        card_repository=mock_card_repo,
        deck_repository=mock_deck_repo,
        session_id="test-session-123",
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


class TestCreateDeck:
    """Tests for create_deck tool."""

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_create_deck_with_default_format(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test successful deck creation with default format."""
        # Arrange
        deck_id = str(uuid4())
        test_deck = Deck(
            id=deck_id,
            name="Test Deck",
            format="standard",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_context.deps.deck_repository.create_deck.return_value = test_deck

        # Act
        result = await create_deck(mock_context, name="Test Deck")

        # Assert
        mock_context.deps.deck_repository.create_deck.assert_called_once_with(
            name="Test Deck", format="standard", strategy=None
        )
        mock_session_manager.set_active_deck_id.assert_called_once_with("test-session-123", deck_id)
        assert "Test Deck" in result
        assert "standard format" in result
        assert deck_id in result
        assert "now active" in result

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_create_deck_with_explicit_format(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test deck creation with explicit format parameter."""
        # Arrange
        deck_id = str(uuid4())
        test_deck = Deck(
            id=deck_id,
            name="Standard Deck",
            format="standard",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_context.deps.deck_repository.create_deck.return_value = test_deck

        # Act
        result = await create_deck(mock_context, name="Standard Deck", format="standard")

        # Assert
        mock_context.deps.deck_repository.create_deck.assert_called_once_with(
            name="Standard Deck", format="standard", strategy=None
        )
        mock_session_manager.set_active_deck_id.assert_called_once_with("test-session-123", deck_id)
        assert "Standard Deck" in result
        assert "standard format" in result
        assert deck_id in result

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_create_deck_with_duplicate_name(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that duplicate deck names are allowed (IDs are unique)."""
        # Arrange
        deck_id_1 = str(uuid4())
        deck_id_2 = str(uuid4())

        # First deck
        test_deck_1 = Deck(
            id=deck_id_1,
            name="Duplicate Name",
            format="standard",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        # Second deck with same name but different ID
        test_deck_2 = Deck(
            id=deck_id_2,
            name="Duplicate Name",
            format="standard",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        # Act - Create first deck
        mock_context.deps.deck_repository.create_deck.return_value = test_deck_1
        result_1 = await create_deck(mock_context, name="Duplicate Name")

        # Act - Create second deck with same name
        mock_context.deps.deck_repository.create_deck.return_value = test_deck_2
        result_2 = await create_deck(mock_context, name="Duplicate Name")

        # Assert - Both decks created successfully with different IDs
        assert deck_id_1 in result_1
        assert deck_id_2 in result_2
        assert deck_id_1 != deck_id_2
        assert mock_context.deps.deck_repository.create_deck.call_count == 2

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_create_deck_database_error(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test error handling when database operation fails."""
        # Arrange
        mock_context.deps.deck_repository.create_deck.side_effect = Exception(
            "Database connection failed"
        )

        # Act
        result = await create_deck(mock_context, name="Error Deck")

        # Assert
        mock_context.deps.deck_repository.create_deck.assert_called_once_with(
            name="Error Deck", format="standard", strategy=None
        )
        # Session manager should NOT be called when database fails
        mock_session_manager.set_active_deck_id.assert_not_called()
        assert "Failed to create deck" in result
        assert "Error Deck" in result
        assert "Database connection failed" in result

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_create_deck_sets_active_deck(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that created deck is set as active in session."""
        # Arrange
        deck_id = str(uuid4())
        test_deck = Deck(
            id=deck_id,
            name="Active Deck",
            format="standard",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_context.deps.deck_repository.create_deck.return_value = test_deck

        # Act
        await create_deck(mock_context, name="Active Deck")

        # Assert
        mock_session_manager.set_active_deck_id.assert_called_once_with("test-session-123", deck_id)

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_create_deck_confirmation_message_format(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that confirmation message has expected format and content."""
        # Arrange
        deck_id = str(uuid4())
        test_deck = Deck(
            id=deck_id,
            name="Confirmation Test",
            format="standard",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_context.deps.deck_repository.create_deck.return_value = test_deck

        # Act
        result = await create_deck(mock_context, name="Confirmation Test")

        # Assert
        assert "Created deck 'Confirmation Test'" in result
        assert "(standard format)" in result
        assert f"ID: {deck_id}" in result
        assert "now active" in result
        assert "ready for card additions" in result


class TestLoadDeckAutoFilter:
    """Tests for load_deck tool auto-filter behavior."""

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_load_standard_deck_auto_sets_format_filter(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test loading Standard deck automatically sets format filter to 'standard'."""
        # Arrange
        deck_id = str(uuid4())
        test_deck = Deck(
            id=deck_id,
            name="Standard Deck",
            format="standard",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            deck_cards=[],
        )
        mock_context.deps.deck_repository.find_deck_by_name.return_value = Deck(
            id=deck_id,
            name="Standard Deck",
            format="standard",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_context.deps.deck_repository.get_deck_with_cards.return_value = test_deck

        # Act
        result = await load_deck(mock_context, name="Standard Deck")

        # Assert
        mock_session_manager.set_active_deck_id.assert_called_once_with("test-session-123", deck_id)
        mock_session_manager.set_format_filter.assert_called_once_with(
            "test-session-123", "standard"
        )
        assert "Standard Deck" in result

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_load_modern_deck_auto_sets_format_filter(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test loading Modern deck automatically sets format filter to 'modern'."""
        # Arrange
        deck_id = str(uuid4())
        test_deck = Deck(
            id=deck_id,
            name="Modern Deck",
            format="modern",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            deck_cards=[],
        )
        mock_context.deps.deck_repository.find_deck_by_name.return_value = Deck(
            id=deck_id,
            name="Modern Deck",
            format="modern",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_context.deps.deck_repository.get_deck_with_cards.return_value = test_deck

        # Act
        result = await load_deck(mock_context, name="Modern Deck")

        # Assert
        mock_session_manager.set_active_deck_id.assert_called_once_with("test-session-123", deck_id)
        mock_session_manager.set_format_filter.assert_called_once_with("test-session-123", "modern")
        assert "Modern Deck" in result

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_load_all_formats_deck_clears_format_filter(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test loading 'all' format deck clears format filter."""
        # Arrange
        deck_id = str(uuid4())
        test_deck = Deck(
            id=deck_id,
            name="All Formats Deck",
            format="all",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            deck_cards=[],
        )
        mock_context.deps.deck_repository.find_deck_by_name.return_value = Deck(
            id=deck_id,
            name="All Formats Deck",
            format="all",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_context.deps.deck_repository.get_deck_with_cards.return_value = test_deck

        # Act
        result = await load_deck(mock_context, name="All Formats Deck")

        # Assert
        mock_session_manager.set_active_deck_id.assert_called_once_with("test-session-123", deck_id)
        mock_session_manager.clear_format_filter.assert_called_once_with("test-session-123")
        mock_session_manager.set_format_filter.assert_not_called()
        assert "All Formats Deck" in result

    @patch("legacy.agent.tools.deck_tools._session_manager")
    async def test_load_deck_with_none_format_clears_filter(
        self, mock_session_manager: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test loading deck with None format clears format filter."""
        # Arrange
        deck_id = str(uuid4())
        test_deck = Deck(
            id=deck_id,
            name="No Format Deck",
            format=None,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            deck_cards=[],
        )
        mock_context.deps.deck_repository.find_deck_by_name.return_value = Deck(
            id=deck_id,
            name="No Format Deck",
            format=None,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        mock_context.deps.deck_repository.get_deck_with_cards.return_value = test_deck

        # Act
        result = await load_deck(mock_context, name="No Format Deck")

        # Assert
        mock_session_manager.set_active_deck_id.assert_called_once_with("test-session-123", deck_id)
        mock_session_manager.clear_format_filter.assert_called_once_with("test-session-123")
        mock_session_manager.set_format_filter.assert_not_called()
        assert "No Format Deck" in result

"""Unit tests for repository classes."""

from unittest.mock import AsyncMock

from src.data.repositories.base import BaseRepository
from src.data.repositories.card import CardRepository


def test_base_repository_initialization() -> None:
    """Test BaseRepository stores session on initialization."""
    mock_session = AsyncMock()
    repository = BaseRepository(mock_session)

    assert repository.session is mock_session


def test_card_repository_initialization() -> None:
    """Test CardRepository inherits from BaseRepository."""
    mock_session = AsyncMock()
    repository = CardRepository(mock_session)

    assert repository.session is mock_session
    assert isinstance(repository, BaseRepository)

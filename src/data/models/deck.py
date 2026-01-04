"""SQLAlchemy ORM model for Magic: The Gathering decks."""

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base

if TYPE_CHECKING:
    from src.data.models.deck_card import DeckCardModel


class DeckModel(Base):
    """SQLAlchemy model for deck metadata and relationships.

    Stores deck information including name, format, optional strategy, and timestamps.
    Links to cards through DeckCardModel association table.
    """

    __tablename__ = "decks"

    # Primary key - UUID
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )

    # Deck metadata
    name: Mapped[str] = mapped_column(String, nullable=False, index=True, init=True)
    format: Mapped[str] = mapped_column(String, nullable=False, index=True, init=True)
    strategy: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True, default=None, init=True
    )

    # Color identity (JSON array of color codes: ["W", "U", "B", "R", "G"])
    # Automatically computed from deck cards, stored as JSON text
    color_identity: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, init=False
    )

    # Tags for categorization (JSON array of strings: ["aggro", "combo", "control"])
    # User-defined tags/win conditions
    tags: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, init=True)

    # Timestamps - auto-managed
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(UTC), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default_factory=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        init=False,
    )

    # Relationships
    deck_cards: Mapped[list["DeckCardModel"]] = relationship(  # noqa: F821
        "DeckCardModel",
        back_populates="deck",
        cascade="all, delete-orphan",
        lazy="noload",
        init=False,
        default_factory=list,
    )

    @property
    def color_identity_list(self) -> list[str]:
        """Parse color_identity JSON field into Python list.

        Returns:
            List of color codes (e.g., ["W", "U", "B"]) or empty list if not set
        """
        if not self.color_identity:
            return []
        try:
            parsed = json.loads(self.color_identity)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @color_identity_list.setter
    def color_identity_list(self, colors: list[str] | None) -> None:
        """Set color_identity field from Python list.

        Args:
            colors: List of color codes or None to clear
        """
        if colors is None or not colors:
            self.color_identity = None
        else:
            self.color_identity = json.dumps(colors)

    @property
    def tags_list(self) -> list[str]:
        """Parse tags JSON field into Python list.

        Returns:
            List of tag strings or empty list if not set
        """
        if not self.tags:
            return []
        try:
            parsed = json.loads(self.tags)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @tags_list.setter
    def tags_list(self, tag_list: list[str] | None) -> None:
        """Set tags field from Python list.

        Args:
            tag_list: List of tag strings or None to clear
        """
        if tag_list is None or not tag_list:
            self.tags = None
        else:
            self.tags = json.dumps(tag_list)

    def __repr__(self) -> str:
        """String representation of the deck."""
        return f"<DeckModel(id='{self.id}', name='{self.name}', format='{self.format}')>"

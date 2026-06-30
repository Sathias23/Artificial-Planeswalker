"""SQLAlchemy ORM model for deck-card associations."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base

if TYPE_CHECKING:
    from src.data.models.card import CardModel
    from src.data.models.deck import DeckModel


class DeckCardModel(Base):
    """SQLAlchemy model for deck-card associations.

    Association table linking decks to cards with quantity and sideboard tracking.
    Uses composite primary key (deck_id, card_id, sideboard) to ensure uniqueness.
    """

    __tablename__ = "deck_cards"

    # Composite primary key
    deck_id: Mapped[str] = mapped_column(
        String, ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True, init=True
    )
    card_id: Mapped[str] = mapped_column(
        String, ForeignKey("cards.id"), primary_key=True, init=True
    )

    # Association attributes
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, init=True)
    sideboard: Mapped[bool] = mapped_column(Boolean, primary_key=True, default=False, init=True)

    # Relationships
    deck: Mapped["DeckModel"] = relationship(  # noqa: F821
        "DeckModel", back_populates="deck_cards", init=False
    )
    card: Mapped["CardModel"] = relationship("CardModel", init=False)  # noqa: F821

    def __repr__(self) -> str:
        """String representation of the deck-card association."""
        location = "sideboard" if self.sideboard else "mainboard"
        return (
            f"<DeckCardModel(deck_id='{self.deck_id}', card_id='{self.card_id}', "
            f"quantity={self.quantity}, location='{location}')>"
        )

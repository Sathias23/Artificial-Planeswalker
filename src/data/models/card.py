"""SQLAlchemy ORM model for Magic: The Gathering cards."""

from typing import Any

from sqlalchemy import JSON, Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.base import Base


class CardModel(Base):
    """SQLAlchemy model for Scryfall card data.

    Stores Magic: The Gathering card information from Scryfall API.
    Uses JSON columns for arrays and objects to simplify schema.
    """

    __tablename__ = "cards"

    # Primary key - Scryfall card ID (UUID)
    id: Mapped[str] = mapped_column(String, primary_key=True, init=True)

    # Core card identification
    name: Mapped[str] = mapped_column(String, nullable=False, index=True, init=True)
    printed_name: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True, default=None, kw_only=True, init=True
    )
    oracle_id: Mapped[str] = mapped_column(String, nullable=False, init=True)

    # Mana and casting cost
    mana_cost: Mapped[str] = mapped_column(String, nullable=False, init=True)
    cmc: Mapped[float] = mapped_column(Float, nullable=False, init=True)

    # Card type and text
    type_line: Mapped[str] = mapped_column(String, nullable=False, init=True)
    oracle_text: Mapped[str] = mapped_column(String, nullable=False, init=True)

    # Combat stats (creatures/vehicles only; Scryfall strings like "2", "*", "1+*").
    # Nullable: non-creatures have no P/T. kw_only matches printed_name to keep the
    # dataclass init signature valid (defaulted fields precede non-defaulted ones).
    power: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, kw_only=True, init=True
    )
    toughness: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, kw_only=True, init=True
    )

    # Official WotC Game Changer status (Commander Brackets initiative; Scryfall `is:gamechanger`).
    # Three-state and nullable: None = "unknown / not yet backfilled", True = confirmed Game
    # Changer, False = confirmed not. Never coalesce None to False (AD-4) — a later story lowers
    # assessment confidence on None and must not lower the Commander Bracket floor on absent data.
    game_changer: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=None, kw_only=True, init=True
    )

    # Rarity and set information
    rarity: Mapped[str] = mapped_column(String, nullable=False, init=True)
    set_code: Mapped[str] = mapped_column(String, nullable=False, init=True)
    set_name: Mapped[str] = mapped_column(String, nullable=False, init=True)
    collector_number: Mapped[str] = mapped_column(String, nullable=False, init=True)

    # Color information (JSON arrays)
    colors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default_factory=list, init=True)
    color_identity: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default_factory=list, init=True
    )
    color_indicator: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, default=None, init=True
    )

    # Keywords (JSON array)
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=None, init=True)

    # Legalities (JSON object: format -> legality status)
    legalities: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default_factory=dict, init=True
    )

    # Multi-face cards (JSON array of face objects)
    card_faces: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True, default=None, init=True
    )

    # Image URIs (JSON object with size keys: small, normal, large, png, art_crop, border_crop)
    image_uris: Mapped[dict[str, str] | None] = mapped_column(
        JSON, nullable=True, default=None, init=True
    )

    # Game availability (JSON array: "paper", "arena", "mtgo")
    # Nullable at DB level but always set to list in Python (handles Scryfall null values)
    games: Mapped[list[str]] = mapped_column(JSON, nullable=True, default_factory=list, init=True)

    def __repr__(self) -> str:
        """String representation of the card."""
        return f"<CardModel(id='{self.id}', name='{self.name}')>"

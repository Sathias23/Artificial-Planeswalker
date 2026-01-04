"""Pydantic schemas for type-safe deck data transfer."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from src.data.schemas.card import Card

# Type alias for supported formats (extensible post-MVP)
# Common MTG formats: standard, modern, commander, legacy, vintage, pioneer, pauper, all
FormatType = str | None


class DeckCard(BaseModel):
    """Pydantic schema for deck-card associations.

    Provides type-safe data transfer for card associations within decks.
    Includes nested Card schema with full card details.
    """

    model_config = ConfigDict(from_attributes=True)

    deck_id: str
    card_id: str
    quantity: int
    sideboard: bool
    card: Card  # Nested full card details

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        """Validate quantity is at least 1."""
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v


class Deck(BaseModel):
    """Pydantic schema for deck metadata and relationships.

    Provides type-safe data transfer for deck information.
    Supports conversion from SQLAlchemy DeckModel instances.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    format: FormatType
    strategy: str | None = None
    color_identity: list[str] = []
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    deck_cards: list[DeckCard] = []

    @field_validator("color_identity", mode="before")
    @classmethod
    def parse_color_identity(cls, v: str | list[str] | None) -> list[str]:
        """Parse color_identity from JSON string or return list directly."""
        if v is None:
            return []
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return v if isinstance(v, list) else []

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: str | list[str] | None) -> list[str]:
        """Parse tags from JSON string or return list directly."""
        if v is None:
            return []
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return v if isinstance(v, list) else []

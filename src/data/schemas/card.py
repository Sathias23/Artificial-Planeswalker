"""Pydantic schemas for type-safe card data transfer."""

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class Card(BaseModel):
    """Pydantic schema for Magic: The Gathering card data.

    Provides type-safe data transfer between application layers.
    Supports conversion from SQLAlchemy CardModel instances.
    """

    model_config = ConfigDict(from_attributes=True)

    # Primary key - Scryfall card ID (UUID)
    id: str

    # Core card identification
    name: str
    printed_name: str | None = None
    oracle_id: str

    # Mana and casting cost
    mana_cost: str
    cmc: float

    # Card type and text
    type_line: str
    oracle_text: str

    # Rarity and set information
    rarity: str
    set_code: str
    set_name: str
    collector_number: str

    # Color information
    colors: list[str]
    color_identity: list[str]
    color_indicator: list[str] | None = None

    # Keywords
    keywords: list[str] | None = None

    # Legalities (format -> legality status)
    legalities: dict[str, str]

    # Multi-face cards
    card_faces: list[dict[str, Any]] | None = None

    # Image URIs (Scryfall CDN URLs for different image sizes)
    image_uris: dict[str, str] | None = None

    # Game availability ("paper", "arena", "mtgo")
    games: list[str] = []

    @field_validator("games", mode="before")
    @classmethod
    def validate_games(cls, v: Any) -> list[str]:
        """Ensure games is always a list, converting None to empty list."""
        return v if v is not None else []


class CardSummary(BaseModel):
    """Lightweight card projection for list-returning tools (search, etc.).

    A bounded subset of :class:`Card` for tools that return many cards at once
    (e.g. ``search_cards``), keeping the payload small for LLM clients. Retains
    ``oracle_text`` for relevance while omitting the heavy detail fields
    (``legalities``, ``image_uris``, ``card_faces``). Because
    ``from_attributes=True`` is set, ``CardSummary.model_validate(card)`` builds
    a summary directly from a full ``Card``. Callers that need full detail (e.g.
    legalities/images) should follow up with ``lookup_card_by_name``.

    ``set_name`` may be added later if display needs it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    mana_cost: str
    cmc: float
    type_line: str
    oracle_text: str
    colors: list[str]
    rarity: str
    set_code: str

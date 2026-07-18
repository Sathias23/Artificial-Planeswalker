"""Pydantic schemas for type-safe deck data transfer."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from src.data.schemas.card import Card, CardSummary

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
    commander: bool = False
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

    @field_serializer("created_at", "updated_at")
    def _serialize_timestamps(self, value: datetime) -> str:
        """Emit RFC 3339 with a UTC offset.

        SQLite stores naive datetimes; strict ``date-time`` validators (Ajv-style,
        e.g. Claude Desktop's MCP client) reject timezone-less values and fail the
        whole tool result. Coerce naive -> UTC so the output always carries an offset.
        """
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()

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


class DeckCardSummary(BaseModel):
    """Lightweight projection of a deck-card entry for deck-returning tools.

    The bounded counterpart to :class:`DeckCard`, which nests the full
    :class:`Card` (with ``legalities``/``image_uris``/``card_faces``). This nests
    a :class:`CardSummary` instead, keeping ``load_deck`` payloads small for LLM
    clients. Callers that need full card detail should follow up with
    ``lookup_card_by_name``. Reused by the Story 1.6 deck-analysis tools.
    """

    model_config = ConfigDict(from_attributes=True)

    card_id: str
    quantity: int
    sideboard: bool
    commander: bool = False
    card: CardSummary


class DeckSummary(BaseModel):
    """Lightweight deck projection (metadata + counts, no card list) for list_decks.

    Mirrors the Story 1.4 ``CardSummary`` decision: returns deck metadata plus
    aggregate counts without the heavy nested card list, so ``list_decks`` never
    dumps full decks at the LLM client. The count fields
    (``mainboard_count``/``sideboard_count``/``distinct_cards``) are **computed by
    the tool helper** from a source ``Deck``'s ``deck_cards`` — a ``Deck`` has no
    such attributes, so ``model_validate`` would silently use the ``0`` defaults.
    Build via the helper's explicit constructor, not ``model_validate``. Reused by
    the Story 1.6 deck-analysis tools.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    format: FormatType
    strategy: str | None = None
    color_identity: list[str] = []
    tags: list[str] = []
    mainboard_count: int = 0
    sideboard_count: int = 0
    distinct_cards: int = 0
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_timestamps(self, value: datetime) -> str:
        """Emit RFC 3339 with a UTC offset.

        SQLite stores naive datetimes; strict ``date-time`` validators (Ajv-style,
        e.g. Claude Desktop's MCP client) reject timezone-less values and fail the
        whole tool result. Coerce naive -> UTC so the output always carries an offset.
        """
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()


class DeckDetail(DeckSummary):
    """Deck metadata + counts + its cards as lightweight projections.

    Extends :class:`DeckSummary` with ``cards`` as :class:`DeckCardSummary` rows
    (each nesting a :class:`CardSummary`, not the full :class:`Card`). Returned by
    ``create_deck`` (empty ``cards``) and ``load_deck`` (full contents). Like
    ``DeckSummary``, the counts are computed by the tool helper, not
    ``model_validate``. Reused by the Story 1.6 deck-analysis tools.
    """

    cards: list[DeckCardSummary] = []

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

    # Combat stats (None for non-creatures)
    power: str | None = None
    toughness: str | None = None

    # Official WotC Game Changer status. Three-state (AD-4): None = unknown / not yet backfilled,
    # True = confirmed Game Changer, False = confirmed not. Intentionally NOT in any coercion
    # validator below — None must survive as None so downstream confidence signalling stays honest.
    game_changer: bool | None = None

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

    # NULL-coercion (Epic 1 retro gate): real Scryfall data stores NULL for these fields
    # on tokens / split cards / lands. The schema keeps the non-optional types but coerces
    # NULL to an empty default so reads (e.g. Epic 2's embedding builder over the full
    # corpus) never raise ValidationError.
    @field_validator("oracle_text", "mana_cost", mode="before")
    @classmethod
    def _coerce_none_to_empty_str(cls, v: Any) -> Any:
        """Coerce a NULL text field to an empty string."""
        return "" if v is None else v

    @field_validator("colors", "games", mode="before")
    @classmethod
    def _coerce_none_to_empty_list(cls, v: Any) -> Any:
        """Coerce a NULL list field to an empty list."""
        return [] if v is None else v

    @field_validator("legalities", mode="before")
    @classmethod
    def _coerce_none_to_empty_dict(cls, v: Any) -> Any:
        """Coerce a NULL dict field to an empty dict."""
        return {} if v is None else v


class CardSummary(BaseModel):
    """The card fields needed to identify and display a card in a list.

    A bounded subset of the full card record: name, mana cost, converted mana
    cost, type line, oracle text, colours, rarity and set code. It omits the
    heavy detail fields — legalities, image URIs and card faces — so a response
    carrying many cards stays small. Fetch the full card separately when that
    detail is needed.

    Attributes:
        Used by list-returning tools (e.g. ``search_cards``), where payload size
        matters most for LLM clients. Because ``from_attributes=True`` is set,
        ``CardSummary.model_validate(card)`` builds a summary directly from a full
        :class:`Card`. Callers needing legalities/images follow up with
        ``lookup_card_by_name``. ``set_name`` may be added later if display needs
        it.
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

    # NULL-coercion gate — mirrors Card so summaries built from NULL-bearing rows
    # (split cards, lands) never raise. See Card for rationale.
    @field_validator("oracle_text", "mana_cost", mode="before")
    @classmethod
    def _coerce_none_to_empty_str(cls, v: Any) -> Any:
        """Coerce a NULL text field to an empty string."""
        return "" if v is None else v

    @field_validator("colors", mode="before")
    @classmethod
    def _coerce_none_to_empty_list(cls, v: Any) -> Any:
        """Coerce a NULL list field to an empty list."""
        return [] if v is None else v

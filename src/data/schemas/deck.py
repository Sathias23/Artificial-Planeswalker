"""Pydantic schemas for type-safe deck data transfer."""

from datetime import UTC, datetime
from typing import Any, Self

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


def _counts(deck: Deck) -> tuple[int, int]:
    """Return ``(mainboard_count, sideboard_count)`` summed from a deck's cards."""
    mainboard = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)
    sideboard = sum(dc.quantity for dc in deck.deck_cards if dc.sideboard)
    return mainboard, sideboard


class DeckCardSummary(BaseModel):
    """One card entry in a deck: how many, which board, and the card itself.

    Carries the quantity, whether the entry is sideboard, whether it is the
    commander, and a summary of the card. The card is a bounded summary rather
    than the full card record, so a decklist stays small; fetch the full card
    separately when detail (legalities, images, faces) is needed.

    Attributes:
        The bounded counterpart to :class:`DeckCard`, which nests the full
        :class:`Card`. Keeping ``load_deck`` payloads small matters most for LLM
        clients, which pay for every token of a tool result; those callers follow
        up with ``lookup_card_by_name``. Reused by the Story 1.6 deck-analysis
        tools.
    """

    model_config = ConfigDict(from_attributes=True)

    card_id: str
    quantity: int
    sideboard: bool
    commander: bool = False
    card: CardSummary


class DeckSummary(BaseModel):
    """A saved deck's metadata and card counts, without the card list itself.

    What a deck listing returns for each deck: identity, format, strategy, colour
    identity, tags, timestamps, and three counts summarising the contents —
    ``mainboard_count`` and ``sideboard_count`` (sums of quantities) and
    ``distinct_cards`` (how many different cards, counting a card in both boards
    once). Enough to render a deck in a list without transferring the deck.

    Attributes:
        Build with :meth:`from_deck`, never ``model_validate``: the counts are
        computed from a source ``Deck``'s ``deck_cards``, and a ``Deck`` has no
        such attributes, so ``model_validate`` would silently apply the ``0``
        defaults. Mirrors the Story 1.4 ``CardSummary`` decision so ``list_decks``
        never dumps full decks at an LLM client. Reused by the Story 1.6
        deck-analysis tools.
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

    @classmethod
    def _summary_fields(cls, deck: Deck) -> dict[str, Any]:
        """Return every ``DeckSummary`` field, projected from *deck*.

        **The one implementation of the projection**, factored out so that
        ``DeckDetail`` extends it rather than restating it. Restating was the old
        shape (``_deck_summary`` and ``_deck_detail`` each listed all eleven
        fields), and it is precisely how ``distinct_cards`` semantics drift: a
        field added to ``DeckSummary`` and set in one constructor but not the
        other silently defaults on the other's route, with no type error.
        """
        mainboard, sideboard = _counts(deck)
        return {
            "id": deck.id,
            "name": deck.name,
            "format": deck.format,
            "strategy": deck.strategy,
            "color_identity": deck.color_identity,
            "tags": deck.tags,
            "mainboard_count": mainboard,
            "sideboard_count": sideboard,
            "distinct_cards": len({dc.card_id for dc in deck.deck_cards}),
            "created_at": deck.created_at,
            "updated_at": deck.updated_at,
        }

    @classmethod
    def from_deck(cls, deck: Deck) -> Self:
        """Project a full ``Deck`` into a summary, computing the counts.

        Lives here, beside the fields it computes, so both shells over this core
        (``src/mcp_server`` and ``src/companion``) share one implementation rather
        than each keeping its own count arithmetic.

        Constructs ``cls``, not a hardcoded ``DeckSummary``, so a subclass gets its
        own type back. A subclass that adds a **required** field must override this
        (as ``DeckDetail`` does for ``cards``); one that adds only optional fields
        inherits it safely.

        Args:
            deck: The source deck, with ``deck_cards`` already loaded. The
                underlying ``DeckModel.deck_cards`` relationship is
                ``lazy="noload"``, so a ``Deck`` obtained from a repository method
                that does **not** eager-load (``get_deck``, ``find_deck_by_name``,
                ``update_deck``) arrives with an empty list and yields **zero
                counts** rather than raising. Use ``get_deck_with_cards`` or
                ``list_decks``, both of which eager-load.

        Returns:
            The summary, with all three counts computed rather than defaulted.
        """
        return cls(**cls._summary_fields(deck))


class DeckDetail(DeckSummary):
    """A saved deck's metadata, card counts and full card list.

    Everything ``DeckSummary`` carries, plus ``cards``: one ``DeckCardSummary``
    per entry. This is the whole decklist — the shape a deck view renders from.

    The order of ``cards`` is **not** meaningful and is not the order the cards
    were added. The underlying relationship declares no ``order_by``, so entries
    arrive in the composite primary key's order — effectively ``card_id``, which
    is a Scryfall UUID. A consumer that wants a stable presentation order (by
    type, by mana value, by name) must sort them itself.

    Attributes:
        Returned by ``create_deck`` (empty ``cards``) and ``load_deck`` (full
        contents), and by ``GET /api/deck/{deck_id}``. Like ``DeckSummary``, build
        it with :meth:`from_deck` rather than ``model_validate``. Reused by the
        Story 1.6 deck-analysis tools.
    """

    cards: list[DeckCardSummary] = []

    @classmethod
    def from_deck(cls, deck: Deck) -> Self:
        """Project a full ``Deck`` into a detail, computing the counts.

        Overrides :meth:`DeckSummary.from_deck` only to add ``cards`` — every
        other field comes from the shared ``_summary_fields``, so a field added to
        ``DeckSummary`` reaches this route too without an edit here.

        Args:
            deck: The source deck, with ``deck_cards`` (and each entry's ``card``)
                already loaded. See :meth:`DeckSummary.from_deck` for what happens
                when they are not.

        Returns:
            The detail, with all three counts computed rather than defaulted. The
            ``cards`` list is in whatever order the repository returned
            ``deck_cards`` — see the class docstring.
        """
        cards = [
            DeckCardSummary(
                card_id=dc.card_id,
                quantity=dc.quantity,
                sideboard=dc.sideboard,
                commander=dc.commander,
                card=CardSummary.model_validate(dc.card),
            )
            for dc in deck.deck_cards
        ]
        return cls(**cls._summary_fields(deck), cards=cards)

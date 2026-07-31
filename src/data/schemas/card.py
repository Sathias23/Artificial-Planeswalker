"""Pydantic schemas for type-safe card data transfer.

**The FIRST PARAGRAPH of every class docstring in this module is published to the outside
world**, and the position of the first Google-style section header is what stops the rest from
being. Both classes here reach the companion's OpenAPI document — ``Card`` as the
``response_model`` of ``GET /api/cards/{card_id}``, ``CardSummary`` indirectly, nested inside
``DeckCardSummary`` on the deck routes (no route declares it directly). ``src.companion.app.main``
truncates each description at that header and ships what is above it into ``ui/src/api/types.d.ts``
as JSDoc and into ``/docs`` — read by frontend authors who have never seen this file.

The truncating set is ``main._DOCSTRING_SECTIONS``: twelve headers, of which ``Attributes:``,
``Args:``, ``Returns:``, ``Raises:`` and ``Example:`` are the ones that turn up here.
``Note:`` and ``Warning:`` are deliberately **not** in it — they are prose a consumer wants, so
they do **not** stop the truncation and anything under them ships.

Two consequences, and neither is obvious from inside ``src/data``:

* **A header that documents no attributes is still load-bearing.** The ``Attributes:`` sections
  below hold prose rather than a field list, which reads like an editing mistake and is not one:
  the header is the truncation marker. Deleting it because "there are no attributes under it"
  silently republishes implementation detail — SQLAlchemy, ``model_validate``, layer names — onto
  a public HTTP surface, and **no gate goes red** (the drift gates compare bytes, not meaning).
  Rewrite the prose freely; move it above the header only if a TypeScript reader should see it.
* **The summary is for a consumer, not a maintainer.** Anything about how this class is built,
  which ORM it converts from, or which internal layer calls it belongs *below* the header.

This module is otherwise ordinary ``src/data``: it neither imports nor knows about the companion
(AD-1). The rule is written here because this is where it is broken.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class Card(BaseModel):
    """One Magic: The Gathering card printing, as held in the local card database.

    Everything known about a single printing: its name and mana cost, type line and oracle text,
    power and toughness, rarity, set and collector number, colours, keywords, format legalities,
    and its images.

    Some fields are always present but may be empty rather than absent — ``mana_cost`` and
    ``oracle_text`` are empty strings on a card that has none, ``colors`` and ``games`` empty
    lists, ``legalities`` an empty object. Combat stats are null on anything that is not a
    creature, and ``game_changer`` is a three-state flag whose null means "not yet determined",
    not "no".

    Images live in one of two places, and **which one is decided by the presence of per-face
    ``image_uris`` — never by whether ``card_faces`` is present**. Most cards carry a top-level
    ``image_uris``. A card whose faces have their own artwork carries a null ``image_uris`` and
    per-face ``image_uris`` inside its ``card_faces`` entries instead. The two are mutually
    exclusive; nothing carries both.

    ``card_faces`` is **not** the discriminator, and treating it as one is wrong for real cards:
    a split card has a ``card_faces`` array *and* a top-level image, because its two halves share
    one piece of artwork — so its faces carry names and costs but no images of their own. Reading
    "has faces" as "has per-face images" renders nothing for those cards. Some cards have no image
    data anywhere, which is ordinary and not an error.

    There is no price data of any kind in this record.

    Attributes:
        The section header above is the boundary between what crosses the HTTP boundary and what
        does not — see this module's docstring before deleting it. Below it, the Python detail:
        ``from_attributes=True`` is set, so ``Card.model_validate(card_model)`` builds one
        directly from a ``CardModel`` ORM row, which is how ``CardRepository`` returns it. The
        ``field_validator``s at the bottom of the class coerce the NULLs real Scryfall data
        stores for text/list/dict fields into empty values (Epic 1 retro gate) so a read over the
        full corpus never raises ``ValidationError``; ``game_changer`` is deliberately excluded
        from them (AD-4).
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

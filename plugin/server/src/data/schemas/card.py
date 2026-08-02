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

from pydantic import BaseModel, ConfigDict, Field, field_validator

IMAGE_DISCRIMINATOR = (
    "Images live in one of two places, and which one is decided by the presence of per-face "
    "image_uris — never by whether card_faces is present. Most cards carry a top-level "
    "image_uris; a card whose faces have their own artwork carries a null image_uris and "
    "per-face image_uris inside its card_faces entries instead. The two are mutually exclusive; "
    "nothing carries both. Reading 'has faces' as 'has per-face images' is the trap: a split "
    "card has faces and a top-level image, because its halves share one piece of artwork, so "
    "its faces carry names and costs but no images of their own. Some cards have no image data "
    "anywhere, which is ordinary and not an error."
)
"""The image discriminator, stated **once**, where the data lives (Q6, Brad 2026-08-01).

Until this story the same three paragraphs lived in :class:`Card`'s docstring and in
``routes/cards.py``'s ``read_card`` docstring, regenerated into two places in ``openapi.json``
with no drift gate between them; ``deferred-work.md`` homed the repair here by name, because
c3-5's image route would otherwise have made it a third copy.

It is attached as the ``description`` of every ``image_uris`` field rather than written into a
class docstring, for two reasons. A docstring is a literal and cannot interpolate a constant, so
"stated once" is only achievable at field level. And the field is where the rule is *about*
something: a reader of ``types.d.ts`` meets the sentence on the exact property it constrains
rather than three screens up.

``tests/unit/companion/test_committed_schema.py`` gates it as a **family**: any wire description
mentioning both "per-face" and "image_uris" must contain this string verbatim, so a fourth
paraphrase cannot appear silently. Route docstrings therefore state only what their own operation
does with the rule, and point here.
"""


class CardFace(BaseModel):
    """One face of a multi-faced card printing, exactly as Scryfall publishes it.

    A card's ``card_faces`` entries carry each half of its identity — that face's own name, mana
    cost, type line and oracle text — and, on some cards, its own artwork. Five fields are named
    below; **every other key Scryfall sends is kept and served unchanged**, so a consumer that
    knows about ``power``, ``flavor_text``, ``loyalty``, ``defense``, ``artist``, ``printed_name``
    or ``color_indicator`` still finds them.

    A card having faces does **not** mean its faces have artwork. The ``image_uris`` field below
    carries the rule that decides it; this summary deliberately does not repeat it.

    Attributes:
        The header above is the truncation marker; see this module's docstring. Below it, the
        Python detail.

        **Why** ``extra="allow"``, **and it is load-bearing rather than lenient** (Q4, Brad
        2026-08-01). A census over the 6,455 face objects in the shipped 38,261-card database
        found **24 distinct keys**: ``object``, ``name``, ``mana_cost`` and ``oracle_text`` on all
        of them, ``type_line`` on 6,445, ``image_uris`` on 5,556, then ``artist``, ``artist_id``,
        ``illustration_id``, ``colors``, ``power``/``toughness`` (935), ``flavor_text``,
        ``color_indicator``, ``loyalty``, ``defense``, ``printed_name``, ``watermark``,
        ``layout`` (66) and the rest. ``Card`` is ``src/data`` and is returned by shipped MCP
        tools, so Pydantic's default — silently dropping unknown keys — would truncate
        ``lookup_card_by_name``'s output for every one of those cards.
        ``test_card_face_schema.py`` proves a real 24-key face round-trips with no key lost and
        no value changed. c3-4 chose ``extra="forbid"`` for a *request* model with no clients;
        this is a *response* model with live consumers, and the two situations are opposites.

        **Why every named field is optional.** Only ``name``/``mana_cost``/``oracle_text`` are
        present on 100% of the corpus today, and a required field would turn a future import that
        omitted one into a ``ValidationError`` raised in the middle of a full-corpus read — the
        failure mode the Epic 1 retro NULL-coercion gate exists to prevent. The cost is that
        ``model_dump()`` emits an explicit ``null`` for a key the source object omitted (the 10
        faces with no ``type_line``, say); that is additive to an MCP payload, never a
        truncation, and it is asserted rather than assumed.
    """

    model_config = ConfigDict(extra="allow")

    name: str | None = None
    mana_cost: str | None = None
    type_line: str | None = None
    oracle_text: str | None = None
    image_uris: dict[str, str] | None = Field(default=None, description=IMAGE_DISCRIMINATOR)


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

    Where a card's artwork lives is stated on the ``image_uris`` and ``card_faces`` fields
    themselves — read those descriptions before rendering anything, because the rule is not the
    obvious one.

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

        The three image paragraphs that used to sit above this header are now
        :data:`IMAGE_DISCRIMINATOR`, attached to the fields they describe (Q6, c3-5). They were
        duplicated verbatim in ``read_card``'s docstring with no gate between the copies, and
        c3-5's image route would have made a third.
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
    card_faces: list[CardFace] | None = Field(default=None, description=IMAGE_DISCRIMINATOR)

    # Image URIs (Scryfall CDN URLs for different image sizes)
    image_uris: dict[str, str] | None = Field(default=None, description=IMAGE_DISCRIMINATOR)

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

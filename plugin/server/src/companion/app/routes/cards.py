"""``GET /api/cards/{card_id}`` — hydrating one card from the local database (FR-03).

The companion's card-reading routes. Its own module rather than a section of :mod:`.decks`
because c3-5's ``GET /api/card-image/{scryfall_id}`` is this route's natural sibling — same
identifier, same corpus, same cache story — while ``decks.py``'s docstring is written entirely
about deck reads.

There is deliberately **nothing here but a lookup**. ``CardRepository.get_by_id`` already returns
the exact ``Card`` schema this route answers with, so AD-1's "no second card shape in this shell"
is satisfied by writing no projection at all: no ``from_deck``-style constructor, no counts, no
``select``. The session and both ``503`` paths arrive with
:data:`~src.companion.app.deps.DbSession`, and the ``404`` token and its status live in
:mod:`src.companion.app.errors`.

The body is unwrapped (AD-16): the card itself, with no ``status``/``card`` envelope.
"""

from typing import Annotated

from fastapi import APIRouter, Path

from src.companion.app.deps import DbSession
from src.companion.app.errors import CompanionError, error_responses
from src.data.repositories.card import CardRepository
from src.data.schemas.card import Card

router = APIRouter(prefix="/api")

_CARD_ID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
"""The canonical Scryfall printing uuid, and nothing else (Q2, Brad 2026-07-31).

**Why a pattern and not** ``uuid.UUID``. Typing the parameter ``uuid.UUID`` would accept
32-hex-without-dashes, ``{braced}``, ``urn:uuid:`` and uppercase spellings — and *normalise* them,
turning a malformed id into a **found** card, which is the opposite of what the route promises.
The pattern is the precise instrument: it is exact, it generates a ``pattern`` into the OpenAPI
document the UI can read, and a failure routes through the existing ``validation_error_handler``
as ``400 invalid_request`` with no code here at all.

**Why lowercase-only.** All 38,261 ids in the shipped corpus are canonical lowercase hyphenated
uuids — zero exceptions, measured. Nothing is reachable by normalising an uppercase id that is not
also reachable by sending the id as stored, so accepting one would only ever quietly serve a client
bug. Unlike a deck id — which c3-1 correctly ruled has no declared shape, making every unknown deck
id simply *not found* — a card id has a declared shape, so "malformed" is decidable and gets its
own answer.

**One measured dependency, because it is invisible and it bites.** ``$`` does not mean the same
thing in every engine: Python's ``re`` matches ``$`` *before a trailing newline*, so under
``re`` a request for ``<canonical-id>%0A`` would validate, miss, and answer ``404
card_not_found`` instead of ``400``. Pydantic 2.12 defaults to the Rust engine, where ``$`` is
end-of-input and that spelling is correctly refused (measured both ways, 2026-07-31). Anything
that changes the engine — a ``regex_engine="python-re"`` config, a major-version change in how
Pydantic compiles patterns — silently reopens it, which is why
``test_routes_cards.py`` pins the trailing-newline spelling by name rather than trusting the
anchor. ``\\A``/``\\z`` would state it unambiguously but are not valid ECMA regex, and this
pattern is published into the OpenAPI document for the UI to read.
"""

CardId = Annotated[str, Path(pattern=_CARD_ID_PATTERN)]
"""The path parameter's type: a string, constrained, never parsed into a ``uuid.UUID``.

``str`` rather than ``UUID`` keeps the value byte-identical to the database key all the way to the
``WHERE`` clause. Any conversion is a chance to normalise, and normalising is what
:data:`_CARD_ID_PATTERN` exists to refuse.
"""


@router.get(
    "/cards/{card_id}",
    response_model=Card,
    responses=error_responses("card_not_found"),
)
async def read_card(card_id: CardId, session: DbSession) -> Card:
    """Return everything known about one card printing.

    The canonical record behind a printing id: its name, mana cost, converted mana cost, type
    line, oracle text, power and toughness, rarity, set, collector number, colours, keywords,
    format legalities, and its images. Views that were given only an id use this to fill
    themselves in.

    Two fields answer the same question and never both do. A single-faced card carries
    ``image_uris`` and a null ``card_faces``; a card with distinct faces carries a null
    ``image_uris`` and per-face image data inside ``card_faces`` instead. Read the presence of
    per-face images, not a layout name. A small number of cards carry no image data at all, which
    is ordinary and not an error.

    ``prices`` is absent from this response, not empty: the local database holds no price data of
    any kind.

    Args:
        card_id: The Scryfall printing uuid — the value in ``cards.id``, and the same value a
            deck's entries carry in ``card_id`` (FR-13). Constrained to the canonical lowercase
            hyphenated spelling by :data:`CardId`; anything else is ``400 invalid_request``,
            answered by the app-wide validation handler before this function runs. (A value that
            is not a single well-formed path segment — one containing an encoded ``/``, say —
            never reaches routing's card branch at all.)
        session: The request-scoped database session (see ``DbSession``).

    Returns:
        The card, unwrapped.

    Raises:
        CompanionError: ``card_not_found`` when the id is well-formed but no card carries it.
    """
    card = await CardRepository(session).get_by_id(card_id)
    if card is None:
        raise CompanionError("card_not_found")
    return card

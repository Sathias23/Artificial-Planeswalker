"""Structured deck-management logic for the Epic-1 deck tools (Story 1.5).

Wraps the existing ``DeckRepository`` 1:1 (D-1.4a): these helpers hold no SQL —
they validate inputs gracefully, await the async repositories, and project each
deck to lightweight summaries (``DeckSummary`` / ``DeckDetail`` / ``DeckCardSummary``,
D-1.5e) so neither ``list_decks`` nor ``load_deck`` dumps full ``Card`` payloads at
the LLM client. The six helpers back the ``list_decks`` / ``create_deck`` /
``load_deck`` / ``delete_deck`` / ``add_card_to_deck`` / ``remove_card_from_deck``
tools.

Stateless (FR3 / D5 / D-1.5d): the "active deck" is the client-supplied
``deck_id`` on every call — there is no server-side active-deck, format-filter,
session, or delete-confirmation handshake (all of the legacy ``_session_manager``
machinery is dropped). Pure CRUD (D-1.5b): ``add_card_to_deck`` only persists the
association — Standard-legality, the 4-copy limit, and deck-size checks are
deferred to ``validate_deck`` (Story 1.6). Because foreign-key enforcement is OFF
on the async engine, add/remove pre-validate that the deck and card exist before
touching ``deck_cards`` (AC4).
"""

import logging
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import DeckRepository
from src.data.schemas.card import Card, CardSummary
from src.data.schemas.deck import Deck, DeckCardSummary, DeckDetail, DeckSummary
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

logger = logging.getLogger(__name__)

# Maximum number of candidate cards returned for an ambiguous name resolution.
_MAX_MATCHES = 10


class DeckListResult(BaseModel):
    """Structured result of ``list_decks``.

    Attributes:
        status: ``ok`` (``decks`` populated) or ``empty`` (no decks — graceful).
        decks: Lightweight ``DeckSummary`` rows (metadata + counts, no card list).
        count: Number of decks in ``decks``.
        message: Human-facing summary.
    """

    status: Literal["ok", "empty", "error", "database_not_initialized"]
    decks: list[DeckSummary] = []
    count: int = 0
    message: str


class DeckResult(BaseModel):
    """Structured result of ``create_deck`` / ``load_deck``.

    Attributes:
        status: ``ok`` (``deck`` populated), ``not_found`` (no such deck), or
            ``invalid`` (a bad input, e.g. a blank name).
        deck: The deck as a ``DeckDetail`` (metadata + counts + lightweight
            ``cards``) when ``status == "ok"``, else ``None``.
        message: Human-facing summary.
    """

    status: Literal["ok", "not_found", "invalid", "error", "database_not_initialized"]
    deck: DeckDetail | None = None
    message: str


class DeckDeleteResult(BaseModel):
    """Structured result of ``delete_deck``.

    Attributes:
        status: ``ok`` (deleted) or ``not_found`` (no such deck — graceful).
        deck_id: The id that was targeted.
        message: Human-facing summary.
    """

    status: Literal["ok", "not_found", "error", "database_not_initialized"]
    deck_id: str
    message: str


class DeckCardResult(BaseModel):
    """Structured result of ``add_card_to_deck`` / ``remove_card_from_deck``.

    Attributes:
        status: ``ok`` (change persisted); ``exists`` (already in that location —
            adjust quantity instead, no upsert); ``not_in_deck`` (nothing to
            remove); ``deck_not_found`` / ``card_not_found`` (pre-validation
            failed, no row written); ``ambiguous`` (a partial name hit >1 card —
            see ``matches``); ``invalid`` (bad input, e.g. both/neither of
            ``card_id``/``name``, or ``quantity < 1``).
        deck_id: The targeted deck id.
        card_id: The resolved card id when known (``ok`` / ``exists`` /
            ``not_in_deck``), else ``None``.
        matches: Candidate cards when ``status == "ambiguous"``, else empty.
        message: Human-facing summary naming the problem on any failure path.
    """

    status: Literal[
        "ok",
        "exists",
        "not_in_deck",
        "deck_not_found",
        "card_not_found",
        "ambiguous",
        "invalid",
        "error",
        "database_not_initialized",
    ]
    deck_id: str | None = None
    card_id: str | None = None
    matches: list[CardSummary] = []
    message: str


def _blank_to_none(value: str | None) -> str | None:
    """Treat a blank/whitespace-only string as omitted (returns ``None``)."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _counts(deck: Deck) -> tuple[int, int]:
    """Return ``(mainboard_count, sideboard_count)`` summed from a deck's cards."""
    mainboard = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)
    sideboard = sum(dc.quantity for dc in deck.deck_cards if dc.sideboard)
    return mainboard, sideboard


def _deck_summary(deck: Deck) -> DeckSummary:
    """Project a full ``Deck`` to a lightweight ``DeckSummary`` (computes counts)."""
    mainboard, sideboard = _counts(deck)
    return DeckSummary(
        id=deck.id,
        name=deck.name,
        format=deck.format,
        strategy=deck.strategy,
        color_identity=deck.color_identity,
        tags=deck.tags,
        mainboard_count=mainboard,
        sideboard_count=sideboard,
        distinct_cards=len({dc.card_id for dc in deck.deck_cards}),
        created_at=deck.created_at,
        updated_at=deck.updated_at,
    )


def _deck_detail(deck: Deck) -> DeckDetail:
    """Project a full ``Deck`` to a ``DeckDetail`` with lightweight ``cards``.

    Counts are computed (not ``model_validate``'d); each card becomes a
    ``DeckCardSummary`` nesting a ``CardSummary`` rather than the full ``Card``.
    """
    mainboard, sideboard = _counts(deck)
    cards = [
        DeckCardSummary(
            card_id=dc.card_id,
            quantity=dc.quantity,
            sideboard=dc.sideboard,
            card=CardSummary.model_validate(dc.card),
        )
        for dc in deck.deck_cards
    ]
    return DeckDetail(
        id=deck.id,
        name=deck.name,
        format=deck.format,
        strategy=deck.strategy,
        color_identity=deck.color_identity,
        tags=deck.tags,
        mainboard_count=mainboard,
        sideboard_count=sideboard,
        distinct_cards=len({dc.card_id for dc in deck.deck_cards}),
        created_at=deck.created_at,
        updated_at=deck.updated_at,
        cards=cards,
    )


def _selector_error(card_id: str | None, name: str | None) -> str | None:
    """Return an error message unless exactly one of ``card_id`` / ``name`` is set.

    Expects already-blank-normalized values (see :func:`_blank_to_none`).
    """
    provided = [v for v in (card_id, name) if v is not None]
    if not provided:
        return "Provide exactly one of card_id or name (neither was given)."
    if len(provided) == 2:
        return "Provide exactly one of card_id or name (both were given)."
    return None


async def _resolve_card(
    card_repo: CardRepository, *, card_id: str | None, name: str | None
) -> tuple[Card | None, str | None, list[Card]]:
    """Resolve a card by ``card_id`` OR ``name`` for the add/remove helpers.

    The ``card_id`` path is a point lookup; the ``name`` path mirrors
    ``lookup_card_by_name``'s exact→partial bucketing (0 / 1 / >1). The caller
    guarantees exactly one of ``card_id`` / ``name`` is set before calling.

    Returns:
        A ``(card, error_status, matches)`` triple. On success ``card`` is set and
        ``error_status`` is ``None``; on failure ``card`` is ``None`` and
        ``error_status`` is ``"card_not_found"`` or ``"ambiguous"`` (with
        ``matches`` populated, capped at ``_MAX_MATCHES``).
    """
    if card_id is not None:
        card = await card_repo.get_by_id(card_id)
        if card is None:
            return None, "card_not_found", []
        return card, None, []

    assert name is not None  # guaranteed by _selector_error before call
    exact = await card_repo.find_by_name_exact(name)
    if exact is not None:
        return exact, None, []

    matches = await card_repo.find_by_name_partial(name)
    if not matches:
        return None, "card_not_found", []
    if len(matches) == 1:
        return matches[0], None, []
    return None, "ambiguous", matches[:_MAX_MATCHES]


async def list_decks(session: AsyncSession, *, format: str | None = None) -> DeckListResult:
    """List saved decks (newest first), optionally filtered by format.

    Returns lightweight ``DeckSummary`` rows (metadata + mainboard/sideboard/
    distinct-card counts, no card list). Use ``load_deck`` for a deck's full
    contents. Stateless: pass ``format`` on every call.

    Args:
        session: Async database session to query against.
        format: Optional MTG format to filter by (e.g. ``"standard"``); blank/None
            applies no filter.

    Returns:
        A ``DeckListResult`` with ``status`` of ``ok``, ``empty``, ``error``, or
        ``database_not_initialized`` (run ``initialize_database`` first).
    """
    if not await is_database_initialized(session):
        return DeckListResult(
            status="database_not_initialized", message=DATABASE_NOT_INITIALIZED_MESSAGE
        )

    format = _blank_to_none(format)
    repo = DeckRepository(session)
    try:
        decks = await repo.list_decks(format_filter=format)
    except DatabaseError:
        logger.exception("list_decks failed")
        return DeckListResult(status="error", message="A database error occurred listing decks.")

    if not decks:
        hint = f" matching format '{format}'" if format else ""
        return DeckListResult(
            status="empty",
            message=f"No decks found{hint}. Use create_deck to start a new deck.",
        )

    summaries = [_deck_summary(d) for d in decks]
    return DeckListResult(
        status="ok",
        decks=summaries,
        count=len(summaries),
        message=f"Found {len(summaries)} deck(s).",
    )


async def create_deck(
    session: AsyncSession,
    *,
    name: str,
    format: str = "standard",
    strategy: str | None = None,
    tags: list[str] | None = None,
) -> DeckResult:
    """Create a new deck and return it as a ``DeckDetail`` (empty ``cards``).

    Deck names are not unique — two decks may share a name, distinguished by
    ``id``. The client tracks the returned ``id`` to act on the deck later.

    Args:
        session: Async database session.
        name: Deck name (must be non-blank).
        format: Deck format (default ``"standard"``).
        strategy: Optional free-text strategy description.
        tags: Optional list of tags / win conditions.

    Returns:
        A ``DeckResult`` with ``status`` of ``ok``, ``invalid`` (blank name), ``error``, or
        ``database_not_initialized`` (run ``initialize_database`` first).
    """
    if not name or not name.strip():
        return DeckResult(status="invalid", message="Deck name must not be empty.")

    if not await is_database_initialized(session):
        return DeckResult(
            status="database_not_initialized", message=DATABASE_NOT_INITIALIZED_MESSAGE
        )

    format = _blank_to_none(format) or "standard"
    repo = DeckRepository(session)
    try:
        created = await repo.create_deck(
            name=name.strip(), format=format, strategy=strategy, tags=tags
        )
    except DatabaseError:
        logger.exception("create_deck failed")
        return DeckResult(status="error", message="A database error occurred creating the deck.")
    return DeckResult(
        status="ok",
        deck=_deck_detail(created),
        message=f"Created deck '{created.name}' (id: {created.id}).",
    )


async def load_deck(session: AsyncSession, *, deck_id: str) -> DeckResult:
    """Load a deck and its cards as a ``DeckDetail``.

    Cards are lightweight ``DeckCardSummary`` rows (each nesting a ``CardSummary``,
    not the full ``Card``); use ``lookup_card_by_name`` for full card detail.

    Args:
        session: Async database session.
        deck_id: The deck id (from ``create_deck`` / ``list_decks``).

    Returns:
        A ``DeckResult`` with ``status`` of ``ok``, ``not_found``, ``error``, or
        ``database_not_initialized`` (run ``initialize_database`` first).
    """
    if not await is_database_initialized(session):
        return DeckResult(
            status="database_not_initialized", message=DATABASE_NOT_INITIALIZED_MESSAGE
        )

    repo = DeckRepository(session)
    try:
        deck = await repo.get_deck_with_cards(deck_id)
    except DatabaseError:
        logger.exception("load_deck failed for deck_id=%s", deck_id)
        return DeckResult(status="error", message="A database error occurred loading the deck.")
    if deck is None:
        return DeckResult(status="not_found", message=f"No deck found with id '{deck_id}'.")

    return DeckResult(
        status="ok",
        deck=_deck_detail(deck),
        message=f"Loaded deck '{deck.name}' ({len(deck.deck_cards)} distinct card(s)).",
    )


async def delete_deck(session: AsyncSession, *, deck_id: str) -> DeckDeleteResult:
    """Delete a deck by id.

    Destructive and irreversible — the client (LLM) is responsible for confirming
    with the user beforehand; there is no server-side confirmation flag.

    Args:
        session: Async database session.
        deck_id: The deck id to delete.

    Returns:
        A ``DeckDeleteResult`` with ``status`` of ``ok``, ``not_found``, ``error``, or
        ``database_not_initialized`` (run ``initialize_database`` first).
    """
    if not await is_database_initialized(session):
        return DeckDeleteResult(
            status="database_not_initialized",
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    repo = DeckRepository(session)
    try:
        deleted = await repo.delete_deck(deck_id)
    except DatabaseError:
        logger.exception("delete_deck failed for deck_id=%s", deck_id)
        return DeckDeleteResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred deleting the deck.",
        )
    if not deleted:
        return DeckDeleteResult(
            status="not_found",
            deck_id=deck_id,
            message=f"No deck found with id '{deck_id}'.",
        )

    return DeckDeleteResult(status="ok", deck_id=deck_id, message=f"Deleted deck '{deck_id}'.")


async def add_card_to_deck(
    session: AsyncSession,
    *,
    deck_id: str,
    card_id: str | None = None,
    name: str | None = None,
    quantity: int = 1,
    sideboard: bool = False,
) -> DeckCardResult:
    """Add a card to a deck, identified by ``card_id`` OR ``name`` (exactly one).

    Pure persistence: this does NOT check Standard-legality, the 4-copy limit, or
    deck size — those belong to ``validate_deck``. Adding a card already present in
    that exact location returns ``status="exists"`` (no quantity merge). The
    ``name`` path resolves exact→partial; a partial name hitting multiple cards
    returns ``status="ambiguous"`` with candidate ``matches`` (re-call with a
    ``card_id``). Stateless: pass ``deck_id`` every call.

    Args:
        session: Async database session.
        deck_id: The target deck id.
        card_id: The card id to add (mutually exclusive with ``name``).
        name: A card name to resolve and add (mutually exclusive with ``card_id``).
        quantity: Number of copies to add (must be >= 1; default 1).
        sideboard: Add to the sideboard instead of the mainboard (default False).

    Returns:
        A ``DeckCardResult`` whose ``status`` reports the outcome.
    """
    deck_id = deck_id.strip()
    card_id = _blank_to_none(card_id)
    name = _blank_to_none(name)

    selector_error = _selector_error(card_id, name)
    if selector_error is not None:
        return DeckCardResult(status="invalid", deck_id=deck_id, message=selector_error)
    if quantity < 1:
        return DeckCardResult(
            status="invalid",
            deck_id=deck_id,
            message=f"quantity must be >= 1 (got {quantity}).",
        )

    if not await is_database_initialized(session):
        return DeckCardResult(
            status="database_not_initialized",
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    deck_repo = DeckRepository(session)
    card_repo = CardRepository(session)

    # Pre-validate the deck (FK enforcement is OFF — a bogus id would orphan a row).
    deck = await deck_repo.get_deck(deck_id)
    if deck is None:
        return DeckCardResult(
            status="deck_not_found",
            deck_id=deck_id,
            message=f"No deck found with id '{deck_id}'.",
        )

    card, error_status, matches = await _resolve_card(card_repo, card_id=card_id, name=name)
    if error_status == "ambiguous":
        return DeckCardResult(
            status="ambiguous",
            deck_id=deck_id,
            matches=[CardSummary.model_validate(c) for c in matches],
            message=(
                f"'{name}' matches {len(matches)} cards. "
                "Re-call with a specific card_id, or refine the name."
            ),
        )
    if card is None:
        identifier = f"card_id '{card_id}'" if card_id is not None else f"name '{name}'"
        return DeckCardResult(
            status="card_not_found",
            deck_id=deck_id,
            card_id=card_id,
            message=f"No card found for {identifier}.",
        )

    location = "sideboard" if sideboard else "mainboard"
    try:
        await deck_repo.add_card_to_deck(deck_id, card.id, quantity, sideboard)
    except IntegrityError:
        return DeckCardResult(
            status="exists",
            deck_id=deck_id,
            card_id=card.id,
            message=(
                f"'{card.name}' is already in the {location} of this deck; "
                "adjust the quantity instead."
            ),
        )
    except DatabaseError:
        logger.exception("add_card_to_deck failed for deck_id=%s card_id=%s", deck_id, card.id)
        return DeckCardResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred adding the card.",
        )

    copies = "copy" if quantity == 1 else "copies"
    return DeckCardResult(
        status="ok",
        deck_id=deck_id,
        card_id=card.id,
        message=f"Added {quantity} {copies} of '{card.name}' to the {location}.",
    )


async def remove_card_from_deck(
    session: AsyncSession,
    *,
    deck_id: str,
    card_id: str | None = None,
    name: str | None = None,
    sideboard: bool = False,
) -> DeckCardResult:
    """Remove a card from a deck, identified by ``card_id`` OR ``name`` (exactly one).

    The ``name`` path resolves exact→partial like ``add_card_to_deck``; a partial
    name hitting multiple cards returns ``status="ambiguous"``. Removing a card not
    present in that location returns ``status="not_in_deck"`` (graceful). Stateless:
    pass ``deck_id`` every call.

    Args:
        session: Async database session.
        deck_id: The target deck id.
        card_id: The card id to remove (mutually exclusive with ``name``).
        name: A card name to resolve and remove (mutually exclusive with ``card_id``).
        sideboard: Remove from the sideboard instead of the mainboard (default False).

    Returns:
        A ``DeckCardResult`` whose ``status`` reports the outcome.
    """
    deck_id = deck_id.strip()
    card_id = _blank_to_none(card_id)
    name = _blank_to_none(name)

    selector_error = _selector_error(card_id, name)
    if selector_error is not None:
        return DeckCardResult(status="invalid", deck_id=deck_id, message=selector_error)

    if not await is_database_initialized(session):
        return DeckCardResult(
            status="database_not_initialized",
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    deck_repo = DeckRepository(session)
    card_repo = CardRepository(session)

    deck = await deck_repo.get_deck(deck_id)
    if deck is None:
        return DeckCardResult(
            status="deck_not_found",
            deck_id=deck_id,
            message=f"No deck found with id '{deck_id}'.",
        )

    card, error_status, matches = await _resolve_card(card_repo, card_id=card_id, name=name)
    if error_status == "ambiguous":
        return DeckCardResult(
            status="ambiguous",
            deck_id=deck_id,
            matches=[CardSummary.model_validate(c) for c in matches],
            message=(
                f"'{name}' matches {len(matches)} cards. "
                "Re-call with a specific card_id, or refine the name."
            ),
        )
    if card is None:
        identifier = f"card_id '{card_id}'" if card_id is not None else f"name '{name}'"
        return DeckCardResult(
            status="card_not_found",
            deck_id=deck_id,
            card_id=card_id,
            message=f"No card found for {identifier}.",
        )

    location = "sideboard" if sideboard else "mainboard"
    try:
        removed = await deck_repo.remove_card_from_deck(deck_id, card.id, sideboard)
    except DatabaseError:
        logger.exception("remove_card_from_deck failed for deck_id=%s card_id=%s", deck_id, card.id)
        return DeckCardResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred removing the card.",
        )
    if not removed:
        return DeckCardResult(
            status="not_in_deck",
            deck_id=deck_id,
            card_id=card.id,
            message=f"'{card.name}' is not in the {location} of this deck.",
        )

    return DeckCardResult(
        status="ok",
        deck_id=deck_id,
        card_id=card.id,
        message=f"Removed '{card.name}' from the {location}.",
    )

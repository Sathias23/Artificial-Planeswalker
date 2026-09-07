"""Structured deck-management logic for the deck tools.

Wraps the existing ``DeckRepository`` 1:1 (D-1.4a): these helpers hold no SQL —
they validate inputs gracefully, await the async repositories, and project each
deck to lightweight summaries (``DeckSummary.from_deck`` / ``DeckDetail.from_deck``,
D-1.5e) so neither ``list_decks`` nor ``load_deck`` dumps full ``Card`` payloads at
the LLM client. Those constructors live on the schemas in ``src.data.schemas.deck``,
so the companion's REST shell projects decks through the same code rather
than its own copy of the count arithmetic. The nine helpers back the ``list_decks`` /
``create_deck`` / ``clone_deck`` / ``load_deck`` / ``update_deck`` / ``delete_deck`` /
``add_card_to_deck`` / ``set_card_quantity`` / ``remove_card_from_deck`` tools.

Stateless (FR3 / D5 / D-1.5d): the "active deck" is the client-supplied
``deck_id`` on every call — there is no server-side active-deck, format-filter,
session, or delete-confirmation handshake (all of the legacy ``_session_manager``
machinery is dropped). Pure CRUD (D-1.5b): ``add_card_to_deck`` and
``set_card_quantity`` only persist the association — Standard-legality, the 4-copy
limit, and deck-size checks are deferred to ``validate_deck``.

``update_deck`` takes its edits as a nested :class:`DeckMetadataUpdate` rather than
flat parameters on purpose: FastMCP validates top-level tool arguments into a model
and dumps them one level deep, so a flat ``strategy: str | None = None`` cannot tell
"omitted" from "sent as null". A nested model keeps its own ``model_fields_set``, which
is what maps a field that is absent to the repository's ``_UNSET`` sentinel (leave
alone) and a field that is present-as-null to ``None`` (clear).

Foreign keys are enforced per connection by the engine's connect hook, so a dangling
id is rejected by the database; the card tools still pre-validate that the deck and
card exist so the caller gets the friendlier ``deck_not_found`` / ``card_not_found``
answer instead of an integrity error.
"""

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import _UNSET, DeckRepository
from src.data.schemas.card import Card, CardSummary
from src.data.schemas.deck import DeckDetail, DeckSummary
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

logger = logging.getLogger(__name__)

# Maximum number of candidate cards returned for an ambiguous name resolution.
_MAX_MATCHES = 10

# Ceilings on the LLM-supplied arguments (nothing at the MCP boundary bounds them otherwise).
# ``MAX_CARD_QUANTITY`` is the single copy cap shared with ``deck_import``: no real deck holds
# more than 250 of one card, and an unbounded integer would be stored as-is.
MAX_CARD_QUANTITY = 250
MAX_DECK_NAME_CHARS = 100
MAX_STRATEGY_CHARS = 2000
MAX_TAGS = 20
MAX_TAG_CHARS = 50


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
    """Structured result of ``create_deck`` / ``load_deck`` / ``update_deck``.

    Attributes:
        status: ``ok`` (``deck`` populated — except an ``update_deck`` whose write
            committed but whose reload failed, which answers ``ok`` with ``deck=None``),
            ``not_found`` (no such deck), or ``invalid`` (a bad input, e.g. a blank name
            or an empty ``changes``).
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
    """Structured result of ``add_card_to_deck`` / ``set_card_quantity`` /
    ``remove_card_from_deck``.

    Attributes:
        status: ``ok`` (change persisted); ``exists`` (already in that location —
            use ``set_card_quantity`` instead, no upsert); ``unchanged``
            (``set_card_quantity`` asked for the quantity already stored — nothing
            written); ``not_in_deck`` (nothing to remove); ``deck_not_found`` /
            ``card_not_found`` (pre-validation failed, no row written — for
            ``set_card_quantity`` this also covers a known card that is not in the
            requested board); ``ambiguous`` (a partial name hit >1 card — see
            ``matches``); ``invalid`` (bad input, e.g. both/neither of
            ``card_id``/``name``, or a quantity outside its bounds).
        deck_id: The targeted deck id.
        card_id: The resolved card id when known (``ok`` / ``exists`` /
            ``unchanged`` / ``not_in_deck``), else ``None``.
        quantity: The copies now stored for that card in that board after a
            ``set_card_quantity`` call (``0`` once removed); ``None`` elsewhere.
        matches: Candidate cards when ``status == "ambiguous"``, else empty.
        message: Human-facing summary naming the problem on any failure path.
    """

    status: Literal[
        "ok",
        "exists",
        "unchanged",
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
    quantity: int | None = None
    matches: list[CardSummary] = []
    message: str


class DeckMetadataUpdate(BaseModel):
    """The edits ``update_deck`` applies, as one nested object.

    Every field is optional and *absence* is meaningful: a field left out of the
    object is not touched, a field sent as ``null`` is cleared (``strategy`` /
    ``tags``; a blank ``strategy`` string clears it too), and a field sent with a
    value replaces the stored one. ``name`` cannot be cleared: sending it as
    ``null`` or blank is ``invalid``. The distinction survives the MCP wire
    because this is a nested model, whose ``model_fields_set`` records which keys
    the caller actually sent. Unknown keys are rejected (``extra="forbid"``) so a
    typo'd field name fails validation instead of silently changing nothing.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        description="New deck name (1 to 100 characters); omit to keep the current name.",
    )
    strategy: str | None = Field(
        default=None,
        description=(
            "New strategy text (up to 2000 characters); null or blank clears it, omit to keep it."
        ),
    )
    tags: list[str] | None = Field(
        default=None,
        description=(
            "Replacement tag list (up to 20 tags of 50 characters); null clears it, "
            "omit to keep it."
        ),
    )


def _blank_to_none(value: str | None) -> str | None:
    """Treat a blank/whitespace-only string as omitted (returns ``None``)."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


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


def _location(sideboard: bool) -> str:
    return "sideboard" if sideboard else "mainboard"


def ambiguous_message(name: str, match_count: int) -> str:
    """The ``ambiguous`` message shared by ``add_card_to_deck`` and ``import_decklist``."""
    return (
        f"'{name}' matches {match_count} cards. "
        "Re-call with a specific card_id, or refine the name."
    )


def card_not_found_message(*, card_id: str | None, name: str | None) -> str:
    """The ``card_not_found`` message shared by the deck tools (one selector is set)."""
    identifier = f"card_id '{card_id}'" if card_id is not None else f"name '{name}'"
    return f"No card found for {identifier}."


def card_exists_message(card_name: str, *, sideboard: bool) -> str:
    """The ``exists`` message shared by ``add_card_to_deck`` and ``import_decklist``."""
    return (
        f"'{card_name}' is already in the {_location(sideboard)} of this deck; "
        "use set_card_quantity to change how many copies it has."
    )


def card_added_message(card_name: str, quantity: int, *, sideboard: bool) -> str:
    """The ``ok`` message shared by ``add_card_to_deck`` and ``import_decklist``."""
    copies = "copy" if quantity == 1 else "copies"
    return f"Added {quantity} {copies} of '{card_name}' to the {_location(sideboard)}."


async def resolve_card(
    card_repo: CardRepository, *, card_id: str | None, name: str | None
) -> tuple[Card | None, str | None, list[Card]]:
    """Resolve a card by ``card_id`` OR ``name`` for the add/remove/import helpers.

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

    summaries = [DeckSummary.from_deck(d) for d in decks]
    return DeckListResult(
        status="ok",
        decks=summaries,
        count=len(summaries),
        message=f"Found {len(summaries)} deck(s).",
    )


def _metadata_bounds_error(
    *, name: str | None, strategy: str | None, tags: list[str] | None
) -> str | None:
    """Return a message naming the first metadata value over its cap, else None.

    Shared by ``create_deck`` and ``update_deck``; ``None`` for any argument means
    "not being set" and is skipped. Blankness is the callers' concern (they differ on
    whether a missing name is an error).
    """
    if name is not None and len(name.strip()) > MAX_DECK_NAME_CHARS:
        return f"name must be at most {MAX_DECK_NAME_CHARS} characters (got {len(name.strip())})."
    if strategy is not None and len(strategy) > MAX_STRATEGY_CHARS:
        return f"strategy must be at most {MAX_STRATEGY_CHARS} characters (got {len(strategy)})."
    if tags is not None:
        if len(tags) > MAX_TAGS:
            return f"tags must hold at most {MAX_TAGS} entries (got {len(tags)})."
        for tag in tags:
            if len(tag) > MAX_TAG_CHARS:
                return f"each tag must be at most {MAX_TAG_CHARS} characters (got {len(tag)})."
    return None


def _create_deck_validation_error(
    *, name: str, strategy: str | None, tags: list[str] | None
) -> str | None:
    """Return a message naming the first ``create_deck`` argument outside its bounds, else None."""
    if not name or not name.strip():
        return "Deck name must not be empty."
    return _metadata_bounds_error(name=name, strategy=strategy, tags=tags)


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
        A ``DeckResult`` with ``status`` of ``ok``, ``invalid`` (blank or over-long name, or a
        strategy / tags value over its cap), ``error``, or ``database_not_initialized`` (run
        ``initialize_database`` first).
    """
    invalid = _create_deck_validation_error(name=name, strategy=strategy, tags=tags)
    if invalid is not None:
        return DeckResult(status="invalid", message=invalid)

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
        deck=DeckDetail.from_deck(created),
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
        deck=DeckDetail.from_deck(deck),
        message=f"Loaded deck '{deck.name}' ({len(deck.deck_cards)} distinct card(s)).",
    )


async def update_deck(
    session: AsyncSession, *, deck_id: str, changes: DeckMetadataUpdate
) -> DeckResult:
    """Change a deck's name, strategy and/or tags, and return the reloaded ``DeckDetail``.

    Only the fields present in ``changes`` are touched (see
    :class:`DeckMetadataUpdate` for the omitted-vs-null rule; a blank ``strategy``
    clears like ``null``); an empty ``changes`` is ``invalid`` rather than a silent
    no-op, so a write never happens for nothing.
    Metadata only: cards, format and colour identity are never altered here.
    Stateless: pass ``deck_id`` every call.

    Args:
        session: Async database session.
        deck_id: The deck id to update.
        changes: The edits to apply.

    Returns:
        A ``DeckResult`` with ``status`` of ``ok``, ``not_found``, ``invalid`` (empty
        ``changes``, a blank/null ``name``, or a value over its cap), ``error``, or
        ``database_not_initialized`` (run ``initialize_database`` first). ``error`` means
        nothing was written; if the write committed but the deck could not be reloaded for
        the response, the status is still ``ok`` with ``deck=None`` and a message saying so.
    """
    deck_id = deck_id.strip()
    sent = changes.model_fields_set
    if not sent:
        return DeckResult(
            status="invalid",
            message="Nothing to change: send at least one of name, strategy or tags in changes.",
        )

    name: str | None = None
    if "name" in sent:
        name = _blank_to_none(changes.name)
        if name is None:
            return DeckResult(status="invalid", message="Deck name must not be empty.")
    # A blank strategy is the module's "omitted" spelling (``_blank_to_none``); here the field
    # was sent, so blank means the same as null: clear it.
    strategy = _blank_to_none(changes.strategy) if "strategy" in sent else None
    tags = changes.tags if "tags" in sent else None

    invalid = _metadata_bounds_error(name=name, strategy=strategy, tags=tags)
    if invalid is not None:
        return DeckResult(status="invalid", message=invalid)

    if not await is_database_initialized(session):
        return DeckResult(
            status="database_not_initialized", message=DATABASE_NOT_INITIALIZED_MESSAGE
        )

    repo = DeckRepository(session)
    try:
        updated = await repo.update_deck(
            deck_id,
            name=name,
            strategy=strategy if "strategy" in sent else _UNSET,
            tags=tags if "tags" in sent else _UNSET,
        )
    except DatabaseError:
        logger.exception("update_deck failed for deck_id=%s", deck_id)
        return DeckResult(status="error", message="A database error occurred updating the deck.")
    if updated is None:
        return DeckResult(status="not_found", message=f"No deck found with id '{deck_id}'.")

    changed = ", ".join(f for f in ("name", "strategy", "tags") if f in sent)
    # The write is committed above this line. A failure reloading the deck for the response is a
    # reporting problem, not a failed mutation: the answer stays ``ok`` (so the wrapper still
    # emits ``deck_changed``) with ``deck=None`` and a message pointing at ``load_deck``.
    try:
        deck = await repo.get_deck_with_cards(deck_id)
    except DatabaseError:
        logger.exception("update_deck committed but the reload failed for deck_id=%s", deck_id)
        deck = None
    if deck is None:
        return DeckResult(
            status="ok",
            deck=None,
            message=(
                f"Updated deck '{updated.name}' ({changed}), but reloading it for this "
                "response failed; call load_deck to see the result."
            ),
        )
    return DeckResult(
        status="ok",
        deck=DeckDetail.from_deck(deck),
        message=f"Updated deck '{deck.name}' ({changed}).",
    )


async def clone_deck(session: AsyncSession, *, deck_id: str, name: str | None = None) -> DeckResult:
    """Create an independent copy; only explicitly supplied names use input bounds."""
    deck_id = deck_id.strip()
    if name is not None:
        name = _blank_to_none(name)
        if name is None:
            return DeckResult(status="invalid", message="Deck name must not be empty.")
        invalid = _metadata_bounds_error(name=name, strategy=None, tags=None)
        if invalid is not None:
            return DeckResult(status="invalid", message=invalid)
    try:
        if not await is_database_initialized(session):
            return DeckResult(
                status="database_not_initialized", message=DATABASE_NOT_INITIALIZED_MESSAGE
            )
        deck = await DeckRepository(session).clone_deck(deck_id, name)
    except DatabaseError:
        logger.exception("clone_deck failed for deck_id=%s", deck_id)
        return DeckResult(status="error", message="A database error occurred cloning the deck.")
    if deck is None:
        return DeckResult(status="not_found", message=f"No deck found with id '{deck_id}'.")
    return DeckResult(
        status="ok", deck=DeckDetail.from_deck(deck), message=f"Cloned deck as '{deck.name}'."
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
    commander: bool = False,
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
        quantity: Number of copies to add (1 to ``MAX_CARD_QUANTITY``; default 1).
        sideboard: Add to the sideboard instead of the mainboard (default False).
        commander: Mark this card as the deck's commander (default False; flag
            two cards for partners).

    Returns:
        A ``DeckCardResult`` whose ``status`` reports the outcome.
    """
    deck_id = deck_id.strip()
    card_id = _blank_to_none(card_id)
    name = _blank_to_none(name)

    selector_error = _selector_error(card_id, name)
    if selector_error is not None:
        return DeckCardResult(status="invalid", deck_id=deck_id, message=selector_error)
    if quantity < 1 or quantity > MAX_CARD_QUANTITY:
        return DeckCardResult(
            status="invalid",
            deck_id=deck_id,
            message=f"quantity must be between 1 and {MAX_CARD_QUANTITY} (got {quantity}).",
        )

    if not await is_database_initialized(session):
        return DeckCardResult(
            status="database_not_initialized",
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    deck_repo = DeckRepository(session)
    card_repo = CardRepository(session)

    # Pre-validate the deck for the friendlier answer; the database would reject a bogus id
    # with an IntegrityError anyway (foreign keys are enforced on every connection).
    deck = await deck_repo.get_deck(deck_id)
    if deck is None:
        return DeckCardResult(
            status="deck_not_found",
            deck_id=deck_id,
            message=f"No deck found with id '{deck_id}'.",
        )

    card, error_status, matches = await resolve_card(card_repo, card_id=card_id, name=name)
    if error_status == "ambiguous":
        assert name is not None  # only the name path can be ambiguous
        return DeckCardResult(
            status="ambiguous",
            deck_id=deck_id,
            matches=[CardSummary.model_validate(c) for c in matches],
            message=ambiguous_message(name, len(matches)),
        )
    if card is None:
        return DeckCardResult(
            status="card_not_found",
            deck_id=deck_id,
            card_id=card_id,
            message=card_not_found_message(card_id=card_id, name=name),
        )

    try:
        await deck_repo.add_card_to_deck(deck_id, card.id, quantity, sideboard, commander=commander)
    except IntegrityError:
        return DeckCardResult(
            status="exists",
            deck_id=deck_id,
            card_id=card.id,
            message=card_exists_message(card.name, sideboard=sideboard),
        )
    except DatabaseError:
        logger.exception("add_card_to_deck failed for deck_id=%s card_id=%s", deck_id, card.id)
        return DeckCardResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred adding the card.",
        )

    return DeckCardResult(
        status="ok",
        deck_id=deck_id,
        card_id=card.id,
        message=card_added_message(card.name, quantity, sideboard=sideboard),
    )


def _not_in_board_message(card_name: str, location: str) -> str:
    return (
        f"'{card_name}' is not in the {location} of this deck, so there is no quantity to set; "
        "use add_card_to_deck to add it."
    )


async def set_card_quantity(
    session: AsyncSession,
    *,
    deck_id: str,
    quantity: int,
    card_id: str | None = None,
    name: str | None = None,
    sideboard: bool = False,
) -> DeckCardResult:
    """Set how many copies of a card a deck holds in one board, or remove it with ``0``.

    Absolute, not additive: ``quantity`` replaces the stored count. The card must
    already be in that board — this never adds a card (use ``add_card_to_deck``), so
    a known card that is not in the requested board answers ``card_not_found``
    for every quantity, ``0`` included. Asking for the count already stored is
    ``unchanged`` and writes nothing. Pure persistence, like ``add_card_to_deck``:
    no legality, copy-limit or deck-size check. Stateless: pass ``deck_id`` every
    call.

    Args:
        session: Async database session.
        deck_id: The target deck id.
        quantity: The new number of copies (0 to ``MAX_CARD_QUANTITY``); ``0`` removes
            the card from that board. Required — there is no default, so an omitted
            quantity can never silently trim a playset.
        card_id: The card id to adjust (mutually exclusive with ``name``).
        name: A card name to resolve and adjust (mutually exclusive with ``card_id``).
        sideboard: Adjust the sideboard entry instead of the mainboard one (default False).

    Returns:
        A ``DeckCardResult`` whose ``status`` reports the outcome; ``quantity`` carries
        the stored count on ``ok`` / ``unchanged``.
    """
    deck_id = deck_id.strip()
    card_id = _blank_to_none(card_id)
    name = _blank_to_none(name)

    selector_error = _selector_error(card_id, name)
    if selector_error is not None:
        return DeckCardResult(status="invalid", deck_id=deck_id, message=selector_error)
    if quantity < 0 or quantity > MAX_CARD_QUANTITY:
        return DeckCardResult(
            status="invalid",
            deck_id=deck_id,
            message=f"quantity must be between 0 and {MAX_CARD_QUANTITY} (got {quantity}).",
        )

    if not await is_database_initialized(session):
        return DeckCardResult(
            status="database_not_initialized",
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    deck_repo = DeckRepository(session)
    card_repo = CardRepository(session)

    # The deck's current rows serve both as the deck-exists check and as the "is the card in
    # that board, and at what count" read that keeps the unchanged / card_not_found answers
    # free of any write.
    deck = await deck_repo.get_deck_with_cards(deck_id)
    if deck is None:
        return DeckCardResult(
            status="deck_not_found",
            deck_id=deck_id,
            message=f"No deck found with id '{deck_id}'.",
        )

    card, error_status, matches = await resolve_card(card_repo, card_id=card_id, name=name)
    if error_status == "ambiguous":
        assert name is not None  # only the name path can be ambiguous
        return DeckCardResult(
            status="ambiguous",
            deck_id=deck_id,
            matches=[CardSummary.model_validate(c) for c in matches],
            message=ambiguous_message(name, len(matches)),
        )
    if card is None:
        return DeckCardResult(
            status="card_not_found",
            deck_id=deck_id,
            card_id=card_id,
            message=card_not_found_message(card_id=card_id, name=name),
        )

    location = _location(sideboard)
    entry = next(
        (e for e in deck.deck_cards if e.card_id == card.id and e.sideboard == sideboard), None
    )
    if entry is None:
        return DeckCardResult(
            status="card_not_found",
            deck_id=deck_id,
            card_id=card.id,
            message=_not_in_board_message(card.name, location),
        )
    if entry.quantity == quantity:
        copies = "copy" if quantity == 1 else "copies"
        return DeckCardResult(
            status="unchanged",
            deck_id=deck_id,
            card_id=card.id,
            quantity=quantity,
            message=f"'{card.name}' already has {quantity} {copies} in the {location}.",
        )

    try:
        if quantity == 0:
            written = await deck_repo.remove_card_from_deck(deck_id, card.id, sideboard)
        else:
            updated = await deck_repo.update_card_quantity(deck_id, card.id, quantity, sideboard)
            written = updated is not None
    except DatabaseError:
        logger.exception("set_card_quantity failed for deck_id=%s card_id=%s", deck_id, card.id)
        return DeckCardResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred setting the card quantity.",
        )
    if not written:
        # The row went away between the read above and the write (another writer got there
        # first): the same answer the pre-read gives, since nothing changed here either.
        return DeckCardResult(
            status="card_not_found",
            deck_id=deck_id,
            card_id=card.id,
            message=_not_in_board_message(card.name, location),
        )

    if quantity == 0:
        message = f"Removed '{card.name}' from the {location} (quantity set to 0)."
    else:
        copies = "copy" if quantity == 1 else "copies"
        message = (
            f"Set '{card.name}' to {quantity} {copies} in the {location} (was {entry.quantity})."
        )
    return DeckCardResult(
        status="ok", deck_id=deck_id, card_id=card.id, quantity=quantity, message=message
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

    card, error_status, matches = await resolve_card(card_repo, card_id=card_id, name=name)
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

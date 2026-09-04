"""Reading saved decks: the list, one deck in full, and one deck's format check (FR-02, UX-DR21).

Deliberately thin routes. Everything they need already exists and is already gated: the
session and both ``503`` paths arrive with :data:`~src.companion.app.deps.DbSession`, the
``404`` token and its status live in :mod:`src.companion.app.errors`, and the response
shapes are ``src.data``'s and ``src.logic``'s own models projected by their own
constructors (AD-1 — this shell defines no second deck shape, holds no SQL, and knows no
deck-construction rule). What is left is a repository call apiece.

Every body is unwrapped (AD-16): the list is a bare JSON array, the detail is the deck
itself and the format check is the report itself, with no ``status``/``count``/``decks``/
``report`` envelope around any of them.

``/deck/{deck_id}/format-check`` is a **sub-resource of the detail route**, which is why it
lives here rather than in a module of its own: it is a deck read, ``decks.router`` is
already registered above ``install_spa(app)``, and the differential router list in
``tests/unit/companion/test_spa.py`` compares path sets built from these same routers — so a
new path on an existing router needs no line there. Both facts are measured in the story
record rather than assumed.
"""

from fastapi import APIRouter

from src.companion.app.deps import DbSession
from src.companion.app.errors import CompanionError, error_responses
from src.data.repositories.deck import DeckRepository
from src.data.schemas.deck import DeckDetailFull, DeckSummary
from src.logic.deck_validator import FormatCheckReport, format_check

router = APIRouter(prefix="/api")


@router.get("/decks", response_model=list[DeckSummary])
async def read_decks(session: DbSession) -> list[DeckSummary]:
    """List every saved deck, newest first, with counts but without the cards.

    Each deck carries its metadata and three counts summarising its contents — enough
    to render a deck list without transferring any decklist. Decks created at the same
    moment tie-break in arbitrary order, so within a tie newest-first is not a strict
    guarantee. Having no saved decks is an ordinary answer, not an error: the array is
    simply empty.

    Args:
        session: The request-scoped database session (see ``DbSession``).

    Returns:
        Every saved deck as a bare array, ordered newest-first. Decks created within
        the same clock tick fall back to id order, which is a UUID and therefore
        arbitrary — do not read a strict newest-first guarantee into a tie.
    """
    # list_deck_summaries, not list_decks: the counts are three aggregates the database can
    # compute, and the eager-loaded alternative reads every card of every deck to produce them.
    # The MCP list_decks tool keeps the eager-loaded path; both live in src/data, so this route
    # still defines no deck shape of its own (AD-1).
    return await DeckRepository(session).list_deck_summaries()


@router.get(
    "/deck/{deck_id}",
    response_model=DeckDetailFull,
    responses=error_responses("deck_not_found"),
)
async def read_deck(deck_id: str, session: DbSession) -> DeckDetailFull:
    """Return one saved deck in full: its metadata, its counts and every card in it.

    The whole decklist, with each entry naming its quantity, which board it belongs
    to, whether it is the commander, and the whole card record itself — legalities, image
    URLs and faces included — so a client needs no follow-up request per card. The order of
    ``cards`` is not meaningful — see ``DeckDetailFull``.

    Args:
        deck_id: The deck's id. A deck id has no declared shape, so any id this
            route receives and cannot find is simply unknown: there is no
            malformed-deck-id answer. (A value that is not a single well-formed
            path segment — one containing an encoded ``/``, say — never reaches
            this handler at all; routing rejects it as ``invalid_request`` first.)
        session: The request-scoped database session (see ``DbSession``).

    Returns:
        The deck, unwrapped.

    Raises:
        CompanionError: ``deck_not_found`` when no saved deck has that id.
    """
    deck = await DeckRepository(session).get_deck_with_cards(deck_id)
    if deck is None:
        raise CompanionError("deck_not_found")
    return DeckDetailFull.from_deck(deck)


@router.get(
    "/deck/{deck_id}/format-check",
    response_model=FormatCheckReport,
    responses=error_responses("deck_not_found"),
)
async def read_deck_format_check(deck_id: str, session: DbSession) -> FormatCheckReport:
    """Check one saved deck against its own format, as a row per check rather than a fault list.

    Six checks — legality, deck size, copy limit, sideboard, banned cards and rotation exposure
    — each answered with ``pass``, ``advisory`` or ``violation`` and a sentence explaining the
    outcome. A row is present whether or not anything is wrong, so the whole check list can be
    rendered rather than only the bad news.

    ``advisory`` means a check could **not** be answered, not that the deck failed it. Two
    things produce it: rotation, which no local data can determine, and a deck whose format is
    missing or unrecognised, which leaves legality and banned cards with nothing to check
    against. A deck in that state is still answered with an ordinary report — the same shape as
    every other answer, never an error.

    The verdicts come from the same rules the agent-side deck validator applies — the *rules* are
    shared, though the inputs need not be: this route always checks a deck against its own saved
    format and never against a platform, so an agent asking about a different format will
    reasonably get a different answer.

    Args:
        deck_id: The deck's id. A deck id has no declared shape, so any id this route receives
            and cannot find is simply unknown: there is no malformed-deck-id answer.
        session: The request-scoped database session (see ``DbSession``).

    Returns:
        The report, unwrapped.

    Raises:
        CompanionError: ``deck_not_found`` when no saved deck has that id.
    """
    # get_deck_with_cards, and it is load-bearing rather than a preference: `deck_cards` is
    # lazy="noload", so a deck from get_deck() arrives with an EMPTY card list and the report
    # that follows is a confident, plausible-looking "mainboard has 0 cards" violation. Nothing
    # raises. test_routes_format_check.py::TestCountsAreReal is what notices.
    deck = await DeckRepository(session).get_deck_with_cards(deck_id)
    if deck is None:
        raise CompanionError("deck_not_found")
    # No `games` argument, deliberately: UX-DR21 asks for six checks and platform availability
    # is not one of them, so `game_availability` never fires from this route.
    return format_check(deck)

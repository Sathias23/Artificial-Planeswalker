"""``GET``/``PUT /api/active-deck`` — which deck the glass is showing (FR-07, AD-16).

The read model's one asymmetric resource: **the browser reads it, the agent writes it.** The
``GET`` is credential-free because the SPA calls it on every cold open and reconnect and holds no
credential (AD-5); the ``PUT`` is credential-gated because setting what a user is looking at is an
agent action, and the agent is the party the discovery file hands a token to.

Its own module rather than a section of :mod:`.decks`, and that cost a hand-synchronised edit in
``build_app()`` and another in ``test_spa.py``'s differential router list (Q1, Brad 2026-08-01).
The alternative — joining ``decks.router`` — was free, and wrong: every route there takes a
``DbSession`` and that module's docstring is written entirely about reading saved decks. An
authenticated in-memory write that touches no database is not a deck read, and hiding it there
would have made a shipped docstring false to save two lines.

**There is deliberately no database here at all.** Not a ``DbSession``, not a repository import, not
a ``503`` path — this is the first route since ``/health`` with no data dependency. That is AD-16's
ruling and not an oversight: *deck-existence validation for* ``companion_set_active_deck`` *belongs
to the MCP tool — it has DB access and it is the one that must report* ``deck_not_found`` *to the
agent; the backend stores what it is given.* A ``PUT`` naming a deck that does not exist therefore
**succeeds**, and the UI meets the ordinary ``deck_not_found`` path when it tries to fetch it.

The state is in memory and dies with the process (:mod:`src.companion.app.state`), so a restart
reports none — FR-07's specified behaviour, not a limitation. Nothing here broadcasts the change
either: **c5-4** adds one call after the store, to a handler that will exist by then, and building a
hook, callback registry or placeholder for it now would be scaffolding designed against a story that
has not been written.

Both bodies are unwrapped (AD-16) and both are the **same model**, so the "none" state is a value
rather than a second shape.
"""

from fastapi import APIRouter, Request

from src.companion.app.errors import error_responses
from src.companion.app.security import AgentToken
from src.companion.app.state import ActiveDeckSlot, active_deck
from src.companion.contracts import ActiveDeck, ActiveDeckRequest

router = APIRouter(prefix="/api")


def _slot(request: Request) -> ActiveDeckSlot:
    """Return the active-deck slot for the app serving *request*.

    Args:
        request: The request being served.

    Returns:
        The slot the lifespan created.

    Raises:
        AttributeError: Deliberately unguarded, unlike
            :func:`~src.companion.app.deps.get_session`'s missing-holder branch. That one models
            the absence because a *database* can legitimately be missing and the distinction
            between "no holder" and "no database" is real. Here there is no such ambiguity: a
            missing slot can only mean the lifespan never ran, which is a wiring bug with no
            modelled token, and letting it reach
            :class:`~src.companion.app.errors.UnhandledErrorMiddleware` as ``500 internal_error``
            is exactly the right answer — the one AD-16 added that token for.
    """
    slot = active_deck(request.app)
    if slot is None:
        raise AttributeError("no active-deck slot on this app; the lifespan did not run")
    return slot


@router.get("/active-deck", response_model=ActiveDeck)
async def read_active_deck(request: Request) -> ActiveDeck:
    """Report which deck the companion is currently displaying.

    Answers ``200`` in both states — a deck, or ``deck_id: null`` for none. There is no ``404`` and
    no second shape: the active deck is a resource that always exists and whose value may be "no
    deck", so a cold open reads the same field it will read once something is set.

    Requires **no credential**: this is what the browser calls on first paint and after every
    reconnect, and the browser never holds one (AD-5).

    After a restart this reports none, whatever was displayed before — the value lives in the
    backend's memory and dies with the process (FR-07).

    Args:
        request: The request being served, used only to reach the app's in-memory slot.

    Returns:
        The active deck, unwrapped.
    """
    return ActiveDeck(deck_id=_slot(request).deck_id)


@router.put(
    "/active-deck",
    response_model=ActiveDeck,
    responses=error_responses("forbidden"),
)
async def set_active_deck(
    request: Request, body: ActiveDeckRequest, _credential: AgentToken
) -> ActiveDeck:
    """Set which deck the companion displays, and echo back what was stored.

    **This endpoint is for the agent, not the browser.** It requires a credential the browser does
    not have and must never be given, so a page has nothing to call here; a request that presents
    no valid credential is refused and the active deck is left untouched.

    Idempotent, which is why the verb is ``PUT``: setting the same deck twice is the same state.
    Answers ``200`` with the stored value rather than ``204``, so one shape serves the read, the
    write and the change notification a later story broadcasts.

    **The deck is not checked for existence.** Any non-blank id is accepted and stored verbatim,
    including one that names no deck. Validating it belongs to the caller that has database access
    and can report the failure meaningfully; a client that then fetches the deck gets the ordinary
    not-found answer.

    Args:
        request: The request being served, used only to reach the app's in-memory slot.
        body: The deck to display.
        _credential: The agent-credential gate — ``Authorization: Bearer <token>``, carrying the
            token this process published in its discovery file. **The header spelling lives down
            here deliberately**: this section is truncated out of the generated TypeScript and
            ``/docs`` (see ``main._DOCSTRING_SECTIONS``), and a browser-facing document is the
            wrong place to teach a page where a credential it must never hold is kept (AD-5). The
            audience that needs the spelling is c6-1, reading this source.

            Injects nothing — the parameter exists so FastAPI solves the dependency, and it is
            underscore-prefixed because the value is deliberately useless. Handing the token to the
            endpoint would put it in a local variable one careless f-string away from a log line.

    Returns:
        The active deck as it now stands, in the same shape the ``GET`` answers with.
    """
    slot = _slot(request)
    slot.set(body.deck_id)
    # c5-4 adds its active_deck_changed broadcast on the line below, after the store and before the
    # return. Nothing is stubbed for it here on purpose: an unused hook is a design decision made
    # by a story that cannot see the requirements.
    # Answered from the slot, not from `body`: "echo back what was stored" stays true by
    # construction if set() ever gains normalisation or rejection.
    return ActiveDeck(deck_id=slot.deck_id)

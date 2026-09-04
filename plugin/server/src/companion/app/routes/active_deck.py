"""``GET``/``PUT /api/active-deck`` — which deck the glass is showing (FR-07, AD-16).

The read model's one asymmetric resource: **the browser reads it, the agent writes it.** The
``GET`` is credential-free because the SPA calls it on every cold open and reconnect and holds no
credential (AD-5); the ``PUT`` is credential-gated because setting what a user is looking at is an
agent action, and the agent is the party the discovery file hands a token to.

Its own module rather than a section of :mod:`.decks`, at the cost of a hand-synchronised edit in
``build_app()`` and another in ``test_spa.py``'s differential router list. The alternative —
joining ``decks.router`` — was free, and wrong: every route there takes a ``DbSession`` and that
module's docstring is written entirely about reading saved decks. An authenticated in-memory write
that touches no database is not a deck read, and hiding it there would have made a shipped
docstring false to save two lines.

**There is deliberately no database here at all.** Not a ``DbSession``, not a repository import, not
a ``503`` path. AD-16 is explicit: *deck-existence validation for* ``companion_set_active_deck``
*belongs to the MCP tool — it has DB access and it is the one that must report* ``deck_not_found``
*to the agent; the backend stores what it is given.* A ``PUT`` naming a deck that does not exist
therefore **succeeds**, and the UI meets the ordinary ``deck_not_found`` path when it tries to fetch
it.

The state is in memory and dies with the process (:mod:`src.companion.app.state`), so a restart
reports none — FR-07's specified behaviour, not a limitation.

**The ``PUT`` broadcasts, in one awaited line and no more.** The route calls
:func:`src.companion.app.ws.broadcast_active_deck_changed` after the store and before the return;
it deliberately holds no hook, callback registry, event bus or any knowledge of the envelope — the
id, the timestamp and the wire shape are all minted in ``ws.py``, which is where the fan-out lives.

**A broadcast failure cannot reach the caller.** The fan-out contains every per-client fault and
returns a delivery count rather than raising, so a ``PUT`` that stored successfully answers ``200``
whether zero, one or twenty tabs were listening (NFR-04's fire-and-forget). Refused credentials and
failed stores never reach the call at all — it sits on the success path, after the write.

Both bodies are unwrapped (AD-16), and both declare ``deck_id`` identically, so the "none" state is
a value rather than a second shape. The models themselves are two, not one: the write answers
:class:`~src.companion.contracts.ActiveDeckSetReceipt` — the read's shape plus the delivered client
count, which the ``GET``'s audience has no use for and the agent's cannot do without.
"""

from fastapi import APIRouter, Request

from src.companion.app.errors import error_responses
from src.companion.app.security import AgentToken
from src.companion.app.state import ActiveDeckSlot, active_deck
from src.companion.app.ws import broadcast_active_deck_changed
from src.companion.contracts import ActiveDeck, ActiveDeckRequest, ActiveDeckSetReceipt

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


# `payload_too_large` is declared here, per operation, rather than in `build_app()`'s include: this
# route has a body and can genuinely answer 413, while the sibling `GET` above carries no body and
# cannot. The cap is enforced by `BodyCapMiddleware` for BOTH body endpoints with one mechanism,
# but only the operations that can answer it say so.
@router.put(
    "/active-deck",
    response_model=ActiveDeckSetReceipt,
    responses=error_responses("forbidden", "payload_too_large"),
)
async def set_active_deck(
    request: Request, body: ActiveDeckRequest, _credential: AgentToken
) -> ActiveDeckSetReceipt:
    """Set which deck the companion displays, and report what was stored and who saw it.

    **This endpoint is for the agent, not the browser.** It requires a credential the browser does
    not have and must never be given, so a page has nothing to call here; a request that presents
    no valid credential is refused and the active deck is left untouched.

    Idempotent, which is why the verb is ``PUT``: setting the same deck twice is the same state.
    Answers ``200`` with the stored value rather than ``204``, and beside it the number of connected
    browsers the change actually reached — so a caller can distinguish *switched, and a tab is
    watching* from *switched, and nobody is looking*.

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
            audience that needs the spelling is ``src.companion.client._send``, reading this source.

            Injects nothing — the parameter exists so FastAPI solves the dependency, and it is
            underscore-prefixed because the value is deliberately useless. Handing the token to the
            endpoint would put it in a local variable one careless f-string away from a log line.

    Returns:
        The active deck as it now stands, plus the delivered client count.

        **The write's shape diverges from the read's by one field.** The *agent* asks a question
        the browser never does — **did anyone see it?** — and the answer is already in hand from
        the fan-out. ``deck_id`` is declared exactly as the read declares it, so the divergence is
        one added field and nothing else. The read is untouched, which is the half AD-5 cares
        about: the SPA never calls this operation.

        **The change notification is a different class with the same field.** The broadcast
        carries an :class:`~src.companion.contracts.ActiveDeckChangedEvent` whose ``payload`` is
        an :class:`~src.companion.contracts.ActiveDeckChangedPayload` — the same field name and
        the same nullability as this body (``{deck_id: string | null}``), but **not** the same
        bound: :class:`~src.companion.contracts.ActiveDeck` declares ``deck_id`` as a bare
        ``str | None`` with no length cap and no blank-refusal, while
        :class:`~src.companion.contracts.ActiveDeckChangedPayload` bounds it at
        ``_MAX_DECK_ID_LENGTH`` and refuses a blank string. A client that can read this response
        body can read that payload, but must not assume the two validate identically. The
        separate payload class is deliberate, so that a later deck-agnostic signal can diverge in
        validation without touching this endpoint's contract. This precision lives down here
        because the paragraphs above ``Args:`` ship into ``components.schemas``, and editing it
        costs no schema regeneration.
    """
    slot = _slot(request)
    slot.set(body.deck_id)
    # Captured once, immediately after `set()` and before any suspension point — this is still a
    # read from the slot rather than from `body` (echo-what-was-stored), but a *single* read: the
    # broadcast below awaits, and a second `PUT` landing during that await can rewrite the slot
    # before a later read would see it. Reading the slot again after the broadcast would let this
    # request's own response disagree with both what it stored and what it just broadcast.
    # `broadcast_active_deck_changed` never raises — a client that cannot be written to is that
    # client's problem, and this mutation already succeeded.
    deck_id = slot.deck_id
    # The fan-out returns its delivered count, and capturing it is the whole of the difference
    # between the read's shape and the write's — no second broadcast, no registry sample, and no
    # new failure mode: the helper cannot raise, so a count is always in hand.
    delivered = await broadcast_active_deck_changed(request.app, deck_id)
    # Answered from the captured value, not a fresh slot read: "echo back what was stored" stays
    # true even if a second `PUT` rewrites the slot while this one's broadcast is still in flight.
    return ActiveDeckSetReceipt(deck_id=deck_id, clients=delivered)

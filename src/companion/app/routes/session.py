"""``GET /api/session`` — the browser's short-lived WebSocket ticket (NFR-01, AD-5).

**The endpoint exists because CORS cannot protect a WebSocket upgrade.** A handshake is not a
fetch: the browser sends no preflight, and ``Access-Control-Allow-Origin`` has no say in whether it
proceeds. So an upgrade authenticated by nothing but its ``Host`` is authenticated by nothing a
local page cannot also present. The ticket closes that gap by moving the authentication onto a
resource CORS *does* govern — this one.

**Why no ``Origin`` check here (c5-2, Q1, Brad 2026-08-08), closing the question c1-5 homed on this
story by name.** c1-5 installs no ``CORSMiddleware`` at all, deliberately and permanently
(``test_security.py::TestCorsIsDeliberatelyAbsent``), because AD-13 serves the SPA from this same
backend and an empty grant *is* "restricted to the app's own origin". A page on another origin can
therefore issue this ``GET`` — but with no ``Access-Control-Allow-Origin`` on the response it cannot
**read** the result, so it cannot learn a ticket. It can only burn them — and burning is
repeatable, not one-shot: a page that *loops* the mint keeps the store at ``MAX_TICKETS`` and can
evict each of the legitimate client's replacement tickets in turn, costing it a failed upgrade and
a re-mint per attempt for as long as the flood runs. That is denial, never theft, it requires a
hostile page live on this machine for the whole duration, and the alternative — refusing the mint
at the cap — hands the same attacker a *permanent* denial instead (see :data:`MAX_TICKETS`). AD-5
and
review finding S-6 both home ``Origin`` validation on the **upgrade**, which is c5-3's; duplicating
it here would put the same decision in two places to keep in sync, and would break any future Vite
dev proxy that rewrites ``Host`` but not ``Origin``.

**What this module deliberately does not do.** It does not import
:mod:`src.companion.discovery`, read ``app.state.agent_token``, or route anything through the agent
credential — AD-5 requires the ticket and the token to share no storage and no code path, and
:class:`~src.companion.app.state.TicketStore` mints with its own
:func:`secrets.token_urlsafe` call. ``test_routes_active_deck.py`` asserts that structurally rather
than trusting this paragraph.

**No database, so no ``503``** — the second route after ``/health`` and c3-4's active deck with no
data dependency at all — and **no body, so no ``413``**: declaring either would promise a
``types.d.ts`` consumer a branch that can never answer, which is the ruling c3-4 already set at
``main.py``'s active-deck include.

The consume half of the lifecycle ships in :class:`~src.companion.app.state.TicketStore` and is
unit-tested here at c5-2; **c5-3** is the story that calls it, from the upgrade.
"""

from fastapi import APIRouter, Request, Response

from src.companion.app.state import TicketStore, ticket_store
from src.companion.contracts import SessionTicket

router = APIRouter(prefix="/api")


def _store(request: Request) -> TicketStore:
    """Return the ticket store for the app serving *request*.

    Args:
        request: The request being served.

    Returns:
        The store the lifespan created.

    Raises:
        AttributeError: Raised by hand when the store is missing — the accessor's ``getattr``
            already swallowed the attribute miss, so this restores the loud failure a bare
            ``app.state.ticket_store`` read would have produced, for the reason
            :func:`src.companion.app.routes.active_deck._slot` states: a missing store can only
            mean the lifespan never ran, which is a wiring bug with no modelled token, and letting
            it reach :class:`~src.companion.app.errors.UnhandledErrorMiddleware` as
            ``500 internal_error`` is exactly the right answer.
    """
    store = ticket_store(request.app)
    if store is None:
        raise AttributeError("no ticket store on this app; the lifespan did not run")
    return store


@router.get("/session", response_model=SessionTicket)
async def mint_session_ticket(request: Request, response: Response) -> SessionTicket:
    """Issue a single-use ticket for one WebSocket upgrade.

    Call this immediately before opening the socket, and present the ticket on the upgrade. Every
    call issues a **new** ticket — there is no session to resume and nothing is reused — so a client
    that reconnects asks again rather than holding one.

    Requires **no credential**: the browser holds none and never will (AD-5), the same ruling
    ``GET /api/active-deck`` already answers under. There is no failure path to model, so under a
    running lifespan the response is always ``200``.

    Args:
        request: The request being served, used only to reach the app's in-memory store.
        response: The outgoing response, used only to set ``Cache-Control``. Injecting it is what
            lets the handler keep its ``response_model`` — returning a hand-built ``JSONResponse``
            to attach one header would leave FastAPI nothing to validate the body against.

    Returns:
        The ticket, unwrapped: AD-16 keeps the MCP result envelope out of REST.
    """
    # `no-store` on a SUCCESS path, and it is the first in this app to do so — c5-2, Q5, Brad
    # 2026-08-08, deliberate rather than copied hygiene. `errors.error_response` sets it on every
    # typed failure (`errors.py:161`), but no 200 has needed it until now, because no 200 has
    # carried a credential before. A single-use ticket that a browser's back/forward cache, an
    # extension or an intermediary is free to store is single-use in name only: the response is
    # already unreadable cross-origin, so this is about the CLIENT's own storage layers, which are
    # exactly the ones same-origin policy does not defend against.
    response.headers["Cache-Control"] = "no-store"
    return SessionTicket(ticket=_store(request).mint())

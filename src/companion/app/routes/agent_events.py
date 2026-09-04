"""``POST /agent/events`` — the agent pushes to the glass, and learns who was listening (FR-06).

**The one endpoint the whole event contract exists for.** The six-kind envelope union, the socket
and the fan-out each live elsewhere; this is the route that joins them, and it is deliberately
thin: validate, authorise, broadcast, report the number. Every hard decision it relies on was made
somewhere else and is *inherited* rather than restated here.

**What it inherits, and therefore does not implement.**

* The credential is :data:`~src.companion.app.security.AgentToken` and nothing else — no ``Header``
  declaration, no security class, no second comparison. ``PUT /api/active-deck`` uses the same
  gate, and the whole contract comes with it: the header spelling, the fail-closed comparison, and
  a ``forbidden`` token that is byte-identical whether the credential was missing, malformed or
  simply wrong. Which of the three it was goes to the log alone.
* The body is the :data:`~src.companion.contracts.AgentEvent` union, validated by FastAPI as an
  ordinary request-body annotation. A violated field cap is a pydantic ``RequestValidationError``
  and answers **400** ``invalid_request`` through the AD-16 handler — *not* 413. That is deliberate:
  field caps are pydantic constraints, and reclassifying them per-route would mean introspecting
  pydantic error internals for a distinction AD-8's tool layer folds back into one
  ``payload_rejected`` token anyway. **413 is the envelope byte cap alone**, enforced pre-parse by
  :class:`~src.companion.app.body_cap.BodyCapMiddleware` before this module is reached. The
  property that matters — *rejected, never truncated; a partial render is impossible* — holds in
  both arms.
* The fan-out is one awaited call to :func:`~src.companion.app.ws.broadcast`. There is no second
  loop, no re-serialisation and no route-level ``try``: that function is total, so a per-client
  fault is contained to its own socket and reported as a smaller number rather than as an
  exception.

**No database, at all** (AD-7, NFR-05). Not a ``DbSession``, not a repository import, not a 503
path — and card ids are **never** checked against the corpus. An id naming no card is accepted and
relayed: validating it would put a database read on the push path AD-7 forbids one on, and would
let a single unknown id discard an otherwise legitimate finding. The UI degrades that entry and
renders the rest (EXPERIENCE.md), which is the behaviour the no-database rule buys.

**The number in the response is the delivered count** — what ``broadcast()`` returned, not what
:attr:`~src.companion.app.state.ConnectionRegistry.connected_count` holds. They differ only when a
client fails mid-fan-out, and in exactly that window the delivered count is the truthful answer to
"how many browsers saw it", which is the question this endpoint exists to answer.
``connected_count`` is what ``GET /health`` reports instead: a live gauge, not a delivery receipt.

**A novel first path segment**, and the only thing standing between ``/agent`` and the SPA
catch-all is registration order in ``build_app()`` — ``/api``'s belt-and-braces seed in
:mod:`src.companion.app.spa` does not cover it. The mount derives ``agent`` as a reserved prefix
from the route table automatically (the ``/ws`` precedent), so a typo under it answers a typed 404
rather than the index; that derivation is what ``test_routes_agent_events.py`` asserts, and the
ordering is what makes it possible.
"""

from fastapi import APIRouter, Request

from src.companion.app.security import AgentToken
from src.companion.app.ws import broadcast
from src.companion.contracts import AgentEvent, EventIngestReceipt

router = APIRouter()


@router.post("/agent/events", response_model=EventIngestReceipt)
async def ingest_event(
    request: Request, body: AgentEvent, _credential: AgentToken
) -> EventIngestReceipt:
    """Relay one agent event to every connected client, and report how many received it.

    Answers ``200`` whether twenty tabs were listening or none were. **Zero is a success**: a
    companion with no browser open is the ordinary state, the event was delivered exactly as
    instructed, and a caller that retried on zero would push duplicates at the first tab to open.

    The event is relayed **verbatim** — nothing here rewrites, enriches or validates its contents
    beyond the envelope's own declared shape. Card ids in particular are not checked against the
    database; a view degrades an unknown entry and renders the rest.

    Args:
        request: The request being served, used only to reach the app's connection registry.
        body: The event to relay, as one of the six envelope kinds. FastAPI validates the
            discriminated union natively as a request-body annotation, so nothing here needs a
            ``TypeAdapter``; ``kind`` selects which payload shape is required.
        _credential: The agent-credential gate — ``Authorization: Bearer <token>``, carrying the
            token this process published in its discovery file. **The header spelling lives down
            here deliberately**: this section is truncated out of the generated TypeScript and
            ``/docs`` (``main._DOCSTRING_SECTIONS``), and a browser-facing document is the wrong
            place to teach a page where a credential it must never hold is kept (AD-5). The
            audience that needs the spelling is ``src.companion.client._send``, reading this source.

            Injects nothing — the parameter exists so FastAPI solves the dependency, and it is
            underscore-prefixed because the value is deliberately useless. Handing the token to the
            endpoint would put it in a local variable one careless f-string away from a log line.

    Returns:
        The receipt, carrying the delivered client count and no echo of the payload (CM-1).

        **There is no route-level** ``try`` **here, and that is deliberate rather than an
        oversight.** :func:`~src.companion.app.ws.broadcast` contains every per-client fault
        itself — a send that raises is logged at ``DEBUG``, discarded from the registry, closed
        best-effort, and the loop continues — and returns a count rather than raising. Wrapping it
        would add a branch no test can reach through the wire, and would invite a future author to
        answer ``500`` for something the fan-out already decided is not a failure.
    """
    return EventIngestReceipt(clients=await broadcast(request.app, body))

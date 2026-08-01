"""The companion's wire contract — pydantic models shared by the app and the leaf (AD-3, AD-12).

These models are the **single source of truth** for every shape that crosses the companion's HTTP
and WebSocket boundary: the backend declares them as ``response_model`` so they land in
``app.openapi()``, and the TypeScript the frontend compiles against is generated from that same
schema (AD-12). A hand-built ``dict`` return would leave the generator with nothing to emit, so a
second shape would drift into existence — exactly what AD-1 and AD-12 exist to prevent.

This module is a **leaf** (AD-3): it may import only the stdlib, ``pydantic``, ``httpx``,
``src.paths`` and its sibling leaf modules — never ``fastapi``, ``sqlalchemy`` or
``src.companion.app``, and not even under ``if TYPE_CHECKING:``. That constraint is what lets the
MCP server import these models (the AD-4 identity probe lives in the leaf and is shared by the
startup check and the companion tools) without a stdio session transitively importing a web
framework. ``tests/unit/companion/test_import_boundary.py`` enforces it.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    """The body of ``GET /health`` — the companion's unauthenticated identity probe (FR-14).

    A caller reads this *before* deciding to send its token: it confirms that whatever answered on
    the discovered port is this companion process and not some unrelated local server that happens
    to hold the port (AD-4). ``status`` is deliberately **not** the project's MCP result envelope
    (AD-16 bans that from REST) — the body *is* the health resource and ``status`` is a field of it.

    Attributes:
        status: A closed token, extendable only by adding a member to the ``Literal``. Always
            ``"ok"`` today; ``/health`` has no failure path to model, since a companion that cannot
            answer does not answer at all.
        instance_id: The per-process identity minted at startup, echoed so a caller can match it
            against the value the discovery file advertised.

    Example:
        >>> HealthResponse(status="ok", instance_id="0f6e...").status
        'ok'
    """

    status: Literal["ok"]
    instance_id: str


_MAX_DECK_ID_LENGTH = 256
"""An upper bound on a stored deck id, and deliberately **not** a claim about its shape (Q4).

c3-1 ruled that a deck id has no declared shape, and this does not declare one: there is no pattern,
no format and no exact length here, so every real id is accepted and an unknown one is simply *not
found* rather than *malformed*. All 40 ids in the shipped database are 36-character uuids (measured
2026-08-01), so 256 is roughly seven times the observed maximum — wide enough that a future id
scheme is not pre-refused, narrow enough that the value the backend agrees to hold in memory and
echo back is bounded.

It bounds a *field*, not a *request*. The body is read and parsed before dependencies are solved
(measured against FastAPI 0.140.0's ``routing.py``: body at lines 423-448, ``solve_dependencies`` at
473), so this constraint cannot stop an unauthenticated caller from making the process buffer a
large body — only from storing one. The pre-parse cap belongs to **c5-5**, which owns
``payload_too_large`` and AD-7's 64 KB envelope limit, and should be one mechanism for both
endpoints rather than two; ``deferred-work.md`` homes it there by name.
"""


ErrorReason = Literal[
    "deck_not_found",
    "card_not_found",
    "database_not_initialized",
    "database_unavailable",
    "invalid_request",
    "forbidden",
    "payload_too_large",
    "internal_error",
]
"""The closed set of reasons any non-2xx response may give (AD-16).

Closed at **eight**, with nothing planned. Adding another is a deliberate act with a failing test
attached (``tests/unit/companion/test_errors.py``), because AD-16's extension rule is that a new
token and the UI state it drives are added together — never a token alone. ``internal_error`` was
added under exactly that rule by the c1-4 review (Brad, 2026-07-25): an unhandled bug must be
distinguishable from a transient database outage *before* Epic 2 freezes the TypeScript union,
with its state panel homed on c2-9. ``card_not_found`` was added the same way by c3-2, under the
C2 retro's R1 ruling that made the pairing explicit — its UI destination shipped in the same
commit as the token (see :class:`ErrorResponse` below, and ``ui/src/components/StatePanel/
states.ts``), because C1 shipping ``internal_error`` alone had already cost c2-9 a repair AC.

``forbidden`` is c3-4's, and it is the first token whose paired "UI state" is a **decision that the
glass shows nothing** rather than a panel (Q2, Brad 2026-08-01). ``payload_too_large`` is the
precedent: an agent-facing rejection has no business interrupting a human reading a deck. What made
it worth the eight-site ripple rather than reusing ``invalid_request``: AD-8 requires the agent-side
client to **re-read the discovery file and retry exactly once** on an auth rejection, and to do no
such thing on a malformed request. Both answering ``400 invalid_request`` would make that rule
unimplementable — c6-1 would retry the wrong failure or fail to retry the right one — and this epic
is where the wire is settled, before Epic 5 freezes the union.

Adding one is genuinely eight edits, and the list is worth reading before starting a ninth:
this ``Literal``, ``errors.STATUS_BY_REASON``, ``test_errors.py``'s two pins, ``ui/src/api/
schema.ts``'s count sentence, ``ui/src/api/schema.test.ts``'s explicit union, ``states.ts``'s
``satisfies Record<ErrorReason, …>`` (a **typecheck** failure, not a test failure) and its
``NO_UI_RESPONSE``/``PLACEHOLDER_FOR_REASON`` classification, and ``states.test.ts``'s exact
array. That is AD-16's pairing rule working as designed: the frontend cannot compile until somebody
decides what the token means on the glass.

A ``Literal`` rather than a ``StrEnum`` so it matches :attr:`HealthResponse.status`, generates a
plain TypeScript string union from ``openapi-typescript`` (AD-12), and lets a raise site write the
bare string that mypy still checks — no enum import at every call site.

The status code each token carries is **not** here: that pairing lives in
``src.companion.app.errors.STATUS_BY_REASON``, the one place in the codebase a token meets a status,
because a leaf module has no business knowing HTTP.
"""


class ErrorResponse(BaseModel):
    """The body of every non-2xx response — the token, and nothing else (AD-16).

    The serialised shape is exactly ``{"reason": "<token>"}``. There is deliberately **no**
    ``message``, ``detail``, ``status`` or ``errors[]`` field:

    * **the copy lives in the UI.** ``EXPERIENCE.md`` fixes the verbatim wording of every state
      panel, and UX-DR33 bans "something went wrong"; a server-side prose field would be a second
      source of user-facing copy that no UX review covers.
    * **prose would leak input back.** FastAPI's validation detail echoes the offending value, and
      the companion is one ``fetch`` away from any page in the browser. The detail goes to the log.
    * **the token is the contract.** Anything a human needs beyond it belongs in the log. If a
      later story genuinely needs machine-readable specifics, it adds a *typed* optional field with
      a named UX consumer — not a free-text bucket.

    What each token means on the glass, which is why the set is closed:

    * ``deck_not_found`` — the deck the caller asked for is gone (deleted between a push and a
      refetch); the SPA clears to the **No-active-deck** panel.
    * ``card_not_found`` — no card in the local database carries that printing id. The **only**
      token whose destination is not a panel: the view that referenced the card renders normally
      and shows an **"Unknown card"** placeholder in that one slot, with no banner and no apology
      (FR-13). One unknown card must never fail a whole view or a whole push. The placeholder is
      built in c4-3.
    * ``database_not_initialized`` — fresh install, no card database yet; the **"Card database not
      set up yet."** panel, which tells the user to ask their agent to run ``initialize_database``.
    * ``database_unavailable`` — reads are failing transiently (a bulk refresh in flight, or an
      unhandled backend fault); the **"Card database is updating."** panel, which retries quietly.
    * ``invalid_request`` — the request itself was malformed, or aimed at a path/method/``Host``
      the companion does not serve. No panel of its own: the SPA never generates one, so it means
      a client bug or a stray caller, and the log is where it is diagnosed.
    * ``forbidden`` — an agent-only endpoint was called without a valid credential (c3-4). Like
      ``payload_too_large``, the audience is the **agent**, not the glass: the browser never holds
      the credential and never calls a route that wants one, so a panel here would report a
      failure the reader did not cause and cannot fix. Its consumer is the MCP tool's outcome
      vocabulary, where AD-8's re-read-discovery-and-retry-once lives.
    * ``payload_too_large`` — an agent push exceeded the ingest cap (c5-5). Surfaced to the *agent*
      through the MCP tool's outcome vocabulary, not to the glass.
    * ``internal_error`` — the companion itself hit an unhandled bug (500). Deterministic, so the
      SPA must **not** quietly retry it the way ``database_unavailable`` retries; its state panel
      is written in Epic 2 (c2-9). The log carries the traceback; the wire carries the token.

    Attributes:
        reason: The token, drawn from :data:`ErrorReason`.

    Example:
        >>> ErrorResponse(reason="deck_not_found").model_dump()
        {'reason': 'deck_not_found'}
    """

    reason: ErrorReason


class ActiveDeck(BaseModel):
    """Which deck the companion is currently displaying, or ``null`` for none (FR-07).

    ``null`` is the answer, not the absence of one. The active deck is a resource that always
    exists and whose value may be "no deck", so asking on a cold open answers ``200`` with
    ``deck_id: null`` — never ``404``, and never a different shape. **The same model answers both
    operations**, so a reader has one shape to render and a writer has one shape to assert on.

    The value lives in the companion's memory and **dies with the process**: after a restart this
    reports ``null`` again, whatever was displayed before. That is specified behaviour rather than a
    limitation — the agent sets the deck, so a fresh backend genuinely has no deck to show until it
    is told (FR-07, CM-3).

    A non-null ``deck_id`` is **not a promise that the deck still exists.** Nothing validates it on
    the way in — that is the MCP tool's job, since it is the party with database access and the one
    that must tell the agent (AD-16) — and a deck can be deleted after being set. A reader that
    fetches the deck and gets ``deck_not_found`` is seeing the ordinary case, not a broken
    invariant.

    Attributes:
        deck_id: The displayed deck's id, or ``None`` if none has been set since this process
            started. Byte-identical to the value that was written. A reader fetching the deck
            interpolates it into ``GET /api/deck/{deck_id}`` **URL-encoded**, like any path
            segment: the id has no declared shape (Q4), so nothing forbids characters — ``/``,
            ``?``, ``#`` — that a raw interpolation would mis-route.

    Example:
        >>> ActiveDeck(deck_id=None).model_dump()
        {'deck_id': None}
    """

    deck_id: str | None


class ActiveDeckRequest(BaseModel):
    """The body of ``PUT /api/active-deck`` — the deck to display (FR-07).

    Carries the deck id and nothing else — **enforced**, not aspirational: an unknown field is
    refused (``extra="forbid"``), because silently dropping it would answer ``200`` to an agent
    whose mental model of this body is wrong and leave nothing to correct it (c3-4 review, Brad
    2026-08-01). The id must be a non-empty string, and *non-empty means non-blank*: a
    whitespace-only id is refused with the same reasoning as ``""`` — the alternative is storing a
    value that would be reported as the active deck forever while resolving to no deck at all, just
    spelled with characters ``min_length`` cannot see (same review). Beyond non-blankness and an
    upper length bound nothing about the id is constrained — a deck id has **no declared shape** in
    this system (Q4), so an id that names no deck is accepted here and simply not found later.

    There is deliberately **no way to clear the active deck** over the wire: the field is required
    and does not accept ``null``. Nothing in the feature asks for one — a deleted deck is a
    *client-side* transition (the refetch 404s), and a restart clears the slot anyway — so the verb
    is not built until something needs it.

    Attributes:
        deck_id: The deck to display, stored verbatim.

            The decision to ship no clearing verb is ledgered in ``deferred-work.md`` rather than
            left to be rediscovered. That pointer sits below this header on purpose: it is a
            repo-internal artifact name, useless to a TypeScript reader, and this section is
            truncated off the wire.

    Example:
        >>> ActiveDeckRequest(deck_id="076ac3ed-b59a-431f-b286-af7ed2c8704e").deck_id[:8]
        '076ac3ed'
    """

    model_config = ConfigDict(extra="forbid")

    deck_id: str = Field(min_length=1, max_length=_MAX_DECK_ID_LENGTH)

    @field_validator("deck_id")
    @classmethod
    def _refuse_blank(cls, value: str) -> str:
        """Refuse an id that is only whitespace — ``min_length`` counts characters, not content."""
        if not value.strip():
            raise ValueError("deck_id must not be blank")
        return value

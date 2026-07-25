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

from pydantic import BaseModel


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


ErrorReason = Literal[
    "deck_not_found",
    "database_not_initialized",
    "database_unavailable",
    "invalid_request",
    "payload_too_large",
]
"""The closed set of reasons any non-2xx response may give (AD-16).

Closed at **five**. Adding a sixth is a deliberate act with a failing test attached
(``tests/unit/companion/test_errors.py``), because AD-16's extension rule is that a new token and
the UI state it drives are added together — never a token alone. Story c3-2 adds ``card_not_found``
under exactly that rule; nothing else does.

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
    * ``database_not_initialized`` — fresh install, no card database yet; the **"Card database not
      set up yet."** panel, which tells the user to ask their agent to run ``initialize_database``.
    * ``database_unavailable`` — reads are failing transiently (a bulk refresh in flight, or an
      unhandled backend fault); the **"Card database is updating."** panel, which retries quietly.
    * ``invalid_request`` — the request itself was malformed, or aimed at a path/method/``Host``
      the companion does not serve. No panel of its own: the SPA never generates one, so it means
      a client bug or a stray caller, and the log is where it is diagnosed.
    * ``payload_too_large`` — an agent push exceeded the ingest cap (c5-5). Surfaced to the *agent*
      through the MCP tool's outcome vocabulary, not to the glass.

    Attributes:
        reason: The token, drawn from :data:`ErrorReason`.

    Example:
        >>> ErrorResponse(reason="deck_not_found").model_dump()
        {'reason': 'deck_not_found'}
    """

    reason: ErrorReason

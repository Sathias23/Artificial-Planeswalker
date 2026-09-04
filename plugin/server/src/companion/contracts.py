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

from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, field_validator


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
        clients: How many browser tabs hold an open WebSocket right now — the registry's own
            count, **not** a delivery receipt. Optional so a reader built against the older
            two-field body still parses a newer companion's answer, and ``None`` from an older
            companion that never sent it. This is the only read-only tab count the companion
            exposes: ``companion_status`` reads it so the agent can tell "running, no tab open"
            from "running, already on screen" without pushing anything.

    Example:
        >>> HealthResponse(status="ok", instance_id="0f6e...").status
        'ok'
    """

    status: Literal["ok"]
    instance_id: str
    clients: int | None = None


_MAX_DECK_ID_LENGTH = 256
"""An upper bound on a stored deck id, and deliberately **not** a claim about its shape.

A deck id has no declared shape, and this does not declare one: there is no pattern, no format and
no exact length here, so every real id is accepted and an unknown one is simply *not found* rather
than *malformed*. Every id in the shipped database is a 36-character uuid (measured), so 256 is
roughly seven times the observed maximum — wide enough that a future id scheme is not pre-refused,
narrow enough that the value the backend agrees to hold in memory and echo back is bounded.

It bounds a *field*, not a *request*. The body is read and parsed before dependencies are solved
(measured against FastAPI 0.140.0's ``routing.py``), so this constraint cannot stop an
unauthenticated caller from making the process buffer a large body — only from storing one. The
pre-parse cap is :class:`~src.companion.app.body_cap.BodyCapMiddleware`, which owns
``payload_too_large`` and AD-7's 64 KB envelope limit: one pure-ASGI middleware outside the routers,
so neither ``PUT /api/active-deck`` nor ``POST /agent/events`` contains a line about size.
"""


# NOT PUBLISHED. The attribute docstring below is a `__doc__` on a module-level assignment, which
# `app.openapi()` never reads — so editing it is free of wire consequences. A class docstring, by
# contrast, is the schema's `description` and does reach the generated files (measured: editing
# both produced a diff from the class docstring alone). See `scripts/dump_openapi.py` for the
# mechanism.
ErrorReason = Literal[
    "deck_not_found",
    "card_not_found",
    "database_not_initialized",
    "database_unavailable",
    "no_image_data",
    "image_fetch_failed",
    "invalid_request",
    "forbidden",
    "payload_too_large",
    "internal_error",
]
"""The closed set of reasons any non-2xx response may give (AD-16).

Closed at **ten**, with nothing planned. Adding another is a deliberate act with a failing test
attached (``tests/unit/companion/test_errors.py``), because AD-16's extension rule is that a new
token and the UI state it drives are added together — never a token alone. ``internal_error``
exists so an unhandled bug is distinguishable from a transient database outage, and it has a state
panel of its own; ``card_not_found`` shipped in the same commit as its UI destination (see
:class:`ErrorResponse` below, and ``ui/src/components/StatePanel/states.ts``).

``forbidden`` is the first token whose paired "UI state" is a **decision that the glass shows
nothing** rather than a panel, and ``payload_too_large`` follows the same precedent: an agent-facing
rejection has no business interrupting a human reading a deck. What makes ``forbidden`` worth a
token of its own rather than reusing ``invalid_request``: AD-8 requires the agent-side client to
**re-read the discovery file and retry exactly once** on an auth rejection, and to do no such thing
on a malformed request. Both answering ``400 invalid_request`` would make that rule unimplementable
— the client would retry the wrong failure or fail to retry the right one.

``no_image_data`` and ``image_fetch_failed`` are a pair, because AD-11 requires *"a card with no
image and a fetch failure are signalled distinguishably"*, and a status this codebase derives from
the token means distinguishable can only mean *different tokens*. The distinction is not cosmetic
even though the pixels are identical: one is permanent (79 cards in the shipped corpus carry no
image data at all, measured) and the other is transient (one flight-mode away), so a client may
retry exactly one of them — and negative caching with backoff was added as pure behaviour with no
wire change at all, because the vocabulary was already paid for here. Their UI half was cheap:
``EXPERIENCE.md`` already carried both rows — *"Card with no image data → Named Card placeholder"*
and *"CDN fetch failure → … UI renders the named Card placeholder"* — so AD-16's pairing rule was
satisfied by an artefact written before the tokens existed.

Adding one is genuinely eight edits, and the list is worth reading before starting an eleventh:
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


# WIRE-VISIBLE, IN FULL. This class docstring crosses the wire as the schema's `description`,
# uncut — `_CompanionFastAPI.openapi()` truncates at the first Google-style header, so every
# paragraph above `Attributes:` reaches `openapi.json`, `types.d.ts` and `/docs`. Editing it IS a
# wire change: regenerate with `npm run gen:api` and commit both generated files in the same
# commit, or `test_openapi_contract.py` turns CI red.
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
      later change genuinely needs machine-readable specifics, it adds a *typed* optional field
      with a named UX consumer — not a free-text bucket.

    What each token means on the glass, which is why the set is closed:

    * ``deck_not_found`` — the deck the caller asked for is gone (deleted between a push and a
      refetch); the SPA clears to the **No-active-deck** panel.
    * ``card_not_found`` — no card in the local database carries that printing id. The **only**
      token whose destination is not a panel: the view that referenced the card renders normally
      and shows an **"Unknown card"** placeholder in that one slot, with no banner and no apology
      (FR-13). One unknown card must never fail a whole view or a whole push.
    * ``no_image_data`` — the card exists, but there is no artwork to serve for what was asked:
      either the printing carries no image data at all (79 cards in the shipped corpus), or the
      requested face is beyond the images it has. **Permanent** — retrying cannot help — so the
      view renders normally and that one slot draws the **named Card placeholder** (the card's
      name, mana cost and type line, which the client already holds — from the deck detail's
      embedded card, or from ``GET /api/cards/{card_id}`` for an id outside the deck). Never a
      grey rectangle, a 1×1 pixel or a generic card back.
    * ``image_fetch_failed`` — the card's image URL is known but could not be retrieved: the CDN
      timed out, answered a non-2xx, returned something that was not an image, or the stored URL
      pointed somewhere the companion refuses to fetch from. **Transient**, which is the whole
      reason it is a separate token from ``no_image_data`` — the pixels are identical (the same
      named Card placeholder) but only this one may ever be retried. A failure is
      **negative-cached with an exponential backoff**, so a repeat request inside the window is
      answered from memory with this same token and no CDN request at all; the window starts at 30
      seconds, doubles per consecutive failure and is capped at 300. Indistinguishable from a fresh
      failure on the wire, deliberately: a client has no different action to take, and the
      consequence a reader of this file should know is that a tile can stay a placeholder for up to
      the ceiling **after** the CDN has recovered.
    * ``database_not_initialized`` — fresh install, no card database yet; the **"Card database not
      set up yet."** panel, which tells the user to ask their agent to run ``initialize_database``.
    * ``database_unavailable`` — reads are failing transiently (a bulk refresh in flight, or an
      unhandled backend fault); the **"Card database is updating."** panel, which retries quietly.
    * ``invalid_request`` — the request itself was malformed, or aimed at a path/method/``Host``
      the companion does not serve. No panel of its own: the SPA never generates one, so it means
      a client bug or a stray caller, and the log is where it is diagnosed.
    * ``forbidden`` — an agent-only endpoint was called without a valid credential. Like
      ``payload_too_large``, the audience is the **agent**, not the glass: the browser never holds
      the credential and never calls a route that wants one, so a panel here would report a
      failure the reader did not cause and cannot fix. Its consumer is the MCP tool's outcome
      vocabulary, where AD-8's re-read-discovery-and-retry-once lives.
    * ``payload_too_large`` — an agent push exceeded the ingest cap. Surfaced to the *agent*
      through the MCP tool's outcome vocabulary, not to the glass.
    * ``internal_error`` — the companion itself hit an unhandled bug (500). Deterministic, so the
      SPA must **not** quietly retry it the way ``database_unavailable`` retries; it has a state
      panel of its own. The log carries the traceback; the wire carries the token.

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
    ``deck_id: null`` — never ``404``, and never a different shape. **This is the read's model.**
    The write answers ``ActiveDeckSetReceipt``, which declares this same ``deck_id`` and adds the
    delivered client count — so a reader still has one shape to render, and a writer asserts on
    that one plus a number the browser never asks for.

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
            segment: the id has no declared shape, so nothing forbids characters — ``/``,
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
    whose mental model of this body is wrong and leave nothing to correct it. The id must be a
    non-empty string, and *non-empty means non-blank*: a whitespace-only id is refused with the
    same reasoning as ``""`` — the alternative is storing a value that would be reported as the
    active deck forever while resolving to no deck at all, just spelled with characters
    ``min_length`` cannot see. Beyond non-blankness and an upper length bound nothing about the id
    is constrained — a deck id has **no declared shape** in this system, so an id that names no
    deck is accepted here and simply not found later.

    There is deliberately **no way to clear the active deck** over the wire: the field is required
    and does not accept ``null``. Nothing in the feature asks for one — a deleted deck is a
    *client-side* transition (the refetch 404s), and a restart clears the slot anyway — so the verb
    is not built until something needs it.

    Attributes:
        deck_id: The deck to display, stored verbatim.

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


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class ActiveDeckSetReceipt(BaseModel):
    """The body of ``PUT /api/active-deck`` — what was stored, and how many tabs saw it (FR-07).

    ``ActiveDeck`` with one field added, and that is the whole difference: the id echoes back
    exactly as the read reports it, and beside it sits the number of connected browsers the change
    actually reached. **The read has no use for that number and does not carry it** — a page
    rendering the active deck is the audience, not the fan-out — so the two operations answer two
    shapes rather than one.

    The count is what makes an agent's report honest. Setting the deck succeeds whether or not
    anybody is looking, so without it the only truthful thing a caller could say is "it is set";
    with it, "switched — and no tab is open, so nothing changed on screen" is available instead.

    **Zero is a success, not a failure**, on exactly the terms ``EventIngestReceipt`` states: a
    companion with no tab open is the ordinary state, the value was stored regardless, and
    re-sending would change nothing. Nothing about the request is echoed beyond the id the caller
    is entitled to see confirmed (CM-1).

    Attributes:
        deck_id: The deck now being displayed, byte-identical to what was stored. Declared exactly
            as :attr:`ActiveDeck.deck_id` is — same nullability — so a reader that handles the read
            handles this. There is still no clearing verb, so the write cannot answer ``null``
            today; the shape admits it for the same reason the read's does.
        clients: How many connected browsers received the change notification, never negative.

            **Delivered, not registered**, and read from the same fan-out
            :class:`EventIngestReceipt` counts — see that model for why the alternative
            (sampling the registry around the broadcast) can over-report a tab that vanished
            mid-write. It is a count at the moment of the fan-out and not a live gauge.

    Example:
        >>> ActiveDeckSetReceipt(deck_id="deck-1", clients=0).model_dump()
        {'deck_id': 'deck-1', 'clients': 0}
    """

    # `extra="forbid"`, unlike `EventIngestReceipt`, the looser sibling this one deliberately does
    # not copy. Both are parsed by the leaf client from a
    # backend shipped in the SAME installed package — there is no version skew to be forward
    # compatible with — so an unexpected field means the two halves disagree about the contract,
    # and a `backend_error` is the honest report of that. (Contrast `HealthResponse`, which stays
    # open on purpose: it is read *before* identity is proven, from something that may not be this
    # application at all.) This comment sits below the docstring, so it costs no regeneration.
    model_config = ConfigDict(extra="forbid")

    deck_id: str | None
    clients: int = Field(ge=0)


class SessionTicket(BaseModel):
    """The body of ``GET /api/session`` — one short-lived credential for one WebSocket upgrade.

    Read this immediately before opening the socket and present it on the upgrade. It is
    **single-use** and **short-lived** — it expires soon after it was issued — so it cannot be
    stored, shared between tabs, or reused across reconnects: a client that reconnects asks for a
    new one every time, which is the intended and inexpensive path rather than a fallback.

    Consuming it destroys it whether or not the handshake then succeeds, so a retry needs a fresh
    ticket — including after an upgrade that failed for an unrelated reason.

    The endpoint is **same-origin and credential-free**: the browser holds no credential and never
    will, and it is the absence of any cross-origin read permission on this response — not a
    credential — that keeps another page from learning a ticket.

    Attributes:
        ticket: The value to present on the upgrade. Opaque: it has no parseable structure, carries
            no identity, and nothing about it should be inspected, logged or persisted.

            The remaining lifetime is deliberately **not** published. A client mints per attempt
            and never inspects the TTL, so a field would be a wire commitment with no consumer.
            This paragraph sits below the header on purpose: it is repo-internal reasoning, and
            ``main._DOCSTRING_SECTIONS`` truncates it off the wire. The concrete number stays out
            of the paragraphs *above* for the same reason — they ship verbatim as the schema
            description, and a number there would be a wire commitment.

    Example:
        >>> SessionTicket(ticket="p2s5...").model_dump()
        {'ticket': 'p2s5...'}
    """

    ticket: str


# ---------------------------------------------------------------------------------------------
# The agent event envelope and its six payloads (AD-6, AD-7, FR-11, FR-18)
#
# AD-6's envelope and AD-7's payload shapes are frozen up front so that MCP tools and views can be
# added while changing no contract at all. A shape narrowed "until somebody needs it" would be paid
# for later as a `.d.ts` regeneration through both mirrored plugin bundles.
#
# A model no route references never lands in `components.schemas`; these reach the document
# because `POST /agent/events` declares the union as its request body. A dummy endpoint to force
# models in early is banned.
# ---------------------------------------------------------------------------------------------


_MAX_ITEMS = 60
"""The most items one push may carry, and the most card ids one tier or group may list (AD-7).

One bound, used in both places, because both answer the same question: how long a list a single
agent view is allowed to hand the glass to render.

**It is not a deck-construction rule, and nothing here applies it as one.** The number coincides
with a familiar deck size, and the coincidence is close enough that the AD-1 scan in
``test_routes_format_check.py`` flags it on sight. But this module holds no deck, reads no card,
counts no copies and imports nothing from ``src.logic``; it bounds a list on a wire. The rule lives
in ``src.logic.deck_validator`` and is not restated, referenced or derived from here — see that
scan's narrowed exemption, which keeps every other AD-1 family live in this file.
"""

_MAX_BUCKETS = 12
"""The most tiers in a ``tier_list``, or groups in a ``groups`` push (AD-7).

Deliberately larger than the five tier letters: :data:`TierLetter` is closed at five but a payload
may legitimately repeat a letter with a different ``name``, and ``groups`` has no closed vocabulary
at all.
"""

_MAX_CARD_ID_LENGTH = 128
"""The cap on any single card id on this wire.

A bound, **not a shape**: AD-7's "not validated for shape" stands — an unknown id still resolves to
the unknown-card placeholder rather than a rejected push. Capped because an unbounded id string
would be the one field family through which a fully validating envelope could carry megabytes. A
Scryfall printing uuid is 36 characters; 128 is headroom, not a format claim.

**The field caps and the envelope cap are *not* nested.** A ``groups`` envelope with every string
at its limit and every list at its length is **104,067 bytes** (measured) — 1.6x the 64 KB ceiling
— and violates no field cap at all. So this bound narrows what one id may carry; it does not make
the envelope cap unreachable by well-formed content.
"""

_MAX_EVENT_ID_LENGTH = 128
"""The cap on an envelope ``id``.

The id is opaque and exists for identity and dedupe — a UUID4 fits three times over. The same
bound-not-shape stance as :data:`_MAX_CARD_ID_LENGTH`, and the same reason: no unbounded string
rides this wire.
"""

_MAX_REASON_LENGTH = 200
"""The cap on a suggestion's ``reason``, which is what makes "one line" honest (AD-7).

The suggestion row renders ``reason`` as a single line of secondary text beneath the card name. A
cap is the only thing that stops a paragraph from being handed to a one-line slot.
"""

_MAX_RATIONALE_LENGTH = 600
"""The cap on a swap's or a group's ``rationale`` — a paragraph, not an essay (AD-7)."""

_MAX_TITLE_LENGTH = 80
"""The cap on an agent-authored ``title``, both the per-payload header and a group's own (AD-7)."""

_MAX_CATEGORY_LENGTH = 80
"""The cap on a suggestion's ``category``.

AD-7's cap list covers ``reason``, ``rationale`` and ``title`` only, leaving three fields bounded
by nothing but the envelope byte cap. ``category`` renders inside a badge, so it is capped at what
a badge can hold rather than at 64 KB.
"""

_MAX_TIER_NAME_LENGTH = 40
"""The cap on a tier's ``name`` — it renders inside a 132px chip."""

_MAX_TIER_NOTE_LENGTH = 200
"""The cap on a tier's ``note`` — the same one-line budget as ``reason``."""

_MAX_ENVELOPE_BYTES = 64 * 1024
"""The ceiling on one serialised envelope, in bytes (AD-7).

**Declared here, enforced in** :mod:`src.companion.app.body_cap`. This is a bound on the
*request*, not on any field, and the property that matters is how much an unauthenticated caller
can make the process buffer. A pydantic model validator runs *after* parsing, so it could reject an
oversized envelope but could not stop it from being read into memory — which is the whole point of
the cap. The pre-parse mechanism therefore lives with ``payload_too_large`` in that module, as one
middleware covering both body endpoints rather than two per-route checks.

**Not nested with the field caps above.** A ``groups`` envelope at every field limit serialises to
104,067 bytes (measured), so this ceiling can refuse a payload pydantic would accept. The two
rejection classes overlap rather than partitioning the input — a field violation answers
``400 invalid_request`` (the AD-16 handler), a byte violation answers ``413`` here, and a body can
qualify for both, in which case the byte cap wins because it runs first.

Over-cap is **rejected, never truncated**: a truncated payload is a payload that renders wrong
without saying so. The answer is **413** ``payload_too_large``, not 422 — AD-16 supersedes AD-7's
422, and a 422 answer would also contradict a shipped pin, since ``test_committed_schema.py``
asserts FastAPI's auto-422 components are stripped.
"""


def _refuse_blank_text(value: str) -> str:
    """Refuse a string that is empty or only whitespace — ``min_length`` counts characters, not
    content (the same stance :class:`ActiveDeckRequest` already ships for ``deck_id``).

    Applied to the fields whose docstrings promise non-blankness (a tier's ``name``, a group's
    ``title``, the envelope ``id``) and to every optional ``title``: an empty title is not ``None``,
    so without this it would defeat the :data:`DEFAULT_TITLE_BY_KIND` fallback and leave a
    ``role="dialog"`` labelled by an empty string.
    """
    if not value.strip():
        raise ValueError("must not be empty or only whitespace")
    return value


# NOT PUBLISHED. Annotated aliases, not models: they inline into each field's schema (the
# `max_length` crosses the wire, the validator does not) and never become components of their own.
_CardId = Annotated[str, Field(max_length=_MAX_CARD_ID_LENGTH)]
"""A card id as this wire bounds it — length-capped, shape-unvalidated (AD-7)."""

_NonBlankTitle = Annotated[
    str, Field(max_length=_MAX_TITLE_LENGTH), AfterValidator(_refuse_blank_text)
]
"""An agent-authored title: capped, and refused when blank so the fallback contract holds."""

_NonBlankReason = Annotated[
    str, Field(max_length=_MAX_REASON_LENGTH), AfterValidator(_refuse_blank_text)
]
"""A suggestion's ``reason``: capped, and refused when blank.

``reason`` is required, one-line explanatory text with no fallback — unlike an optional title, an
empty or whitespace-only value here has no ``DEFAULT_TITLE_BY_KIND``-style substitute, so it would
ship a row with no stated reason at all.
"""

_NonBlankRationale = Annotated[
    str, Field(max_length=_MAX_RATIONALE_LENGTH), AfterValidator(_refuse_blank_text)
]
"""A swap's or group's ``rationale``: capped, and refused when blank.

Same stance as :data:`_NonBlankReason` — required explanatory text, no fallback."""

_NullableDeckId = (
    Annotated[str, Field(max_length=_MAX_DECK_ID_LENGTH), AfterValidator(_refuse_blank_text)] | None
)
"""A signal payload's ``deck_id``: ``None`` means "refetch whatever is active"; a present value is
capped and refused when blank — an empty string is a third state that is neither a real id nor the
documented ``None`` sentinel.
"""


# NOT PUBLISHED. Same mechanism as `ErrorReason` above: an attribute docstring on a module-level
# assignment is a `__doc__` that `app.openapi()` never reads, so editing the prose below is free of
# wire consequences.
EventKind = Literal[
    "suggestions",
    "swaps",
    "tier_list",
    "groups",
    "deck_changed",
    "active_deck_changed",
]
"""The closed set of things the agent or the backend may push to the glass (AD-6).

**Six kinds**, as AD-6 enumerates them. The first four are **agent pushes**, each carrying a
rendered view. The last two are **system signals**: no view, no items, just "something changed,
refetch" (NFR-04).

``deck_changed`` and ``active_deck_changed`` are distinct on purpose, and conflating them is a real
bug rather than a tidiness matter: ``active_deck_changed`` says *the companion is now showing a
different deck*, while ``deck_changed`` says *the deck you are showing has been edited*. A client
that treats the first as the second refetches the deck it is leaving instead of the one it is
switching to, and shows stale contents that look authoritative.

A ``Literal`` rather than a ``StrEnum`` to match :data:`ErrorReason` and
:attr:`HealthResponse.status`, so ``openapi-typescript`` emits a plain TypeScript string union
(AD-12) and a producer can write the bare string with mypy still checking it.
"""


# NOT PUBLISHED. An attribute docstring on a module-level assignment.
TierLetter = Literal["S", "A", "B", "C", "D"]
"""The closed five-value tier vocabulary (AD-7, UX-DR26/41).

Closed at five because the render is a five-stop colour ramp and a sixth letter would have no
colour to be. It is **not** :class:`~src.logic.assessment.profiles.TierLabel`, which is an unrelated
five-value deck-power vocabulary — same arity, different meaning; do not import or reuse it.

Colour never carries the rank alone: every letter ships beside its free-text ``name``, which is why
that field is ``min_length=1``.
"""


# NOT PUBLISHED. An attribute docstring on a module-level assignment.
Confidence = Literal["low", "medium", "high"]
"""How sure the agent is about one suggestion or one swap.

The design asks for a confidence indicator on both the suggestion row and the swap row. It cannot
be derived on the receiving side — the push path never reads the database — so if it is not
carried it does not exist.

Three tokens rather than a 0–1 float, to match the vocabulary ``assess_deck_power`` already uses.
A float would oblige every consumer to invent its own bucketing, and two consumers would invent
two.
"""


# WIRE-VISIBLE, IN FULL. This class docstring crosses the wire as the schema `description`, uncut —
# it carries no Google-style header above the `Attributes:` block, so every paragraph before that
# header reaches `openapi.json`, `types.d.ts` and `/docs`. Editing it IS a wire change and costs a
# regeneration.
class SuggestionItem(BaseModel):
    """One card the agent thinks is worth adding, and why (AD-7).

    Its own shape over a bare card reference, rather than one fat optional bag shared by all four
    payload kinds: a reader of the generated TypeScript should not have to know which fields are
    populated for which kind.

    ``reason`` is one line of secondary text beneath the card name — the cap is what makes that
    honest. ``category`` is a **badge, not a grouping**: suggestions render as a flat list with no
    sectioning, so two items carrying the same category sit next to unrelated ones and nothing
    reorders them.

    The card is named by its Scryfall printing uuid and by nothing else — no card name, no mana
    cost, no type line. Resolving a name to an id is the existing MCP tools' job, and duplicating
    card data here would create a second copy that can disagree with the database (FR-13).

    Attributes:
        card_id: A Scryfall printing uuid. **Not validated for shape** (AD-7): the companion has no
            business refusing an id it merely fails to recognise, and an id-shape pattern does exist
            at ``routes/cards.py`` but lives under ``app/``, which this leaf cannot import (AD-3).
            An unknown id resolves to the unknown-card placeholder, not to a rejected push.
            Length-capped at :data:`_MAX_CARD_ID_LENGTH` — a bound, not a shape.
        reason: One line saying why, capped at :data:`_MAX_REASON_LENGTH`.
        category: An optional badge label, capped at :data:`_MAX_CATEGORY_LENGTH`.
        confidence: How sure the agent is, or ``None`` if it did not say.

    Example:
        >>> SuggestionItem(card_id="076ac3ed", reason="Fixes the two-drop gap.").category is None
        True
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "card_id": "076ac3ed-b59a-431f-b286-af7ed2c8704e",
                    "reason": "Fills the two-drop gap and blocks the aggro decks in this meta.",
                    "category": "Curve",
                    "confidence": "high",
                }
            ]
        },
    )

    card_id: _CardId
    reason: _NonBlankReason
    category: str | None = Field(default=None, max_length=_MAX_CATEGORY_LENGTH)
    confidence: Confidence | None = None


# WIRE-VISIBLE, IN FULL. As above — the prose before `Attributes:` is the schema description and
# the generated JSDoc.
class SwapItem(BaseModel):
    """One card out, one card in, and the reasoning for the trade (AD-7).

    The two quantities render as the literal ``"Out · N copies"`` and ``"In · N copies"``, and the
    ``rationale`` sits beside the pair — it is per-swap, not per-payload, because a list of swaps
    with one shared justification is a list the reader cannot act on selectively.

    **Zero is a legal quantity.** A swap whose in-card has no copies available renders "0 copies"
    and is a designed case, not a malformed one, so neither quantity may be constrained to be
    positive. A ``ge=1`` here would reject a payload the experience specification asks for.

    There is deliberately **no price field.** No price data exists anywhere in this system — the
    card table carries no price column and the Scryfall importer never reads the ``prices`` object
    — so the field could never be populated. Nothing is lost that could have been shown.

    Attributes:
        out_card_id: The Scryfall printing uuid leaving the deck. Not validated for shape (AD-7).
        in_card_id: The Scryfall printing uuid entering the deck. Not validated for shape.
        rationale: Why the trade is worth making, capped at :data:`_MAX_RATIONALE_LENGTH`.
        out_qty: Copies leaving. **Zero is legal** — see above.
        in_qty: Copies entering. **Zero is legal** — see above.
        confidence: How sure the agent is, or ``None`` if it did not say.

        Mana value needs no field either: ``cmc`` arrives with the hydrated card, so a curve chip is
        derivable on the client. That pointer sits below this header on purpose, where truncation
        keeps it off the wire.

    Example:
        >>> SwapItem(out_card_id="a", in_card_id="b", rationale="Faster.", out_qty=2,
        ...          in_qty=0).in_qty
        0
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "out_card_id": "076ac3ed-b59a-431f-b286-af7ed2c8704e",
                    "in_card_id": "9f2b1c44-0d3e-4a77-8f21-6b0a5d3e2c19",
                    "rationale": "Same role one turn earlier, and it survives the format's "
                    "commonest removal spell.",
                    "out_qty": 2,
                    "in_qty": 0,
                    "confidence": "medium",
                }
            ]
        },
    )

    out_card_id: _CardId
    in_card_id: _CardId
    rationale: _NonBlankRationale
    out_qty: int = Field(ge=0)
    in_qty: int = Field(ge=0)
    confidence: Confidence | None = None


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class TierItem(BaseModel):
    """One tier of a tier list — a letter, the name that gives it meaning, and its cards (AD-7).

    The letter is a large glyph in a coloured chip and drives a five-stop ramp; the ``name`` sits
    beneath it and is the **accessible carrier of rank**, which is why it may not be blank. Colour
    alone must never be what tells a reader that S beats D, so a payload with an empty name silently
    breaks an accessibility floor rather than merely looking unfinished.

    Tiers appear in **payload order**. Nothing sorts them by letter, dedupes them or re-orders them,
    and two ``A`` tiers with different names is a legal payload — the agent's ordering is the
    agent's argument.

    An empty ``card_ids`` list is legal. The view skips an empty tier rather than rejecting the
    push, so a tier list that names a rank with nothing currently in it still arrives intact.

    Attributes:
        letter: One of :data:`TierLetter`.
        name: What the tier means in MTG terms — "Auto-include", "Filler", "Cut". Non-empty, capped
            at :data:`_MAX_TIER_NAME_LENGTH`.
        note: An optional line of commentary, capped at :data:`_MAX_TIER_NOTE_LENGTH`.
        card_ids: Scryfall printing uuids, in payload order, at most :data:`_MAX_ITEMS`. Not
            validated for shape (AD-7). May be empty.

    Example:
        >>> TierItem(letter="S", name="Auto-include", card_ids=[]).card_ids
        []
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "letter": "S",
                    "name": "Auto-include",
                    "note": "Play four of each in every build of this archetype.",
                    "card_ids": ["076ac3ed-b59a-431f-b286-af7ed2c8704e"],
                }
            ]
        },
    )

    letter: TierLetter
    name: Annotated[str, AfterValidator(_refuse_blank_text)] = Field(
        min_length=1, max_length=_MAX_TIER_NAME_LENGTH
    )
    note: str | None = Field(default=None, max_length=_MAX_TIER_NOTE_LENGTH)
    card_ids: list[_CardId] = Field(default_factory=list, max_length=_MAX_ITEMS)


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class GroupItem(BaseModel):
    """One named group of cards and the paragraph explaining it (AD-7).

    The ``title`` renders as a heading with a count and the ``rationale`` as the paragraph beneath
    it. This ``title`` is the **group's own**, not the payload-level agent-view header — the two
    live at different levels and a push may carry both.

    A group may reference cards **outside the active deck**: grouping is an argument about cards,
    not an inventory of the deck, so a group naming a card the reader does not own is legal and
    renders normally.

    An empty ``card_ids`` list is legal, and the view skips it.

    Attributes:
        title: The group's heading, capped at :data:`_MAX_TITLE_LENGTH`. Non-empty, for the same
            reason a tier's name is: it is the only thing distinguishing one group from the next.
        rationale: The paragraph, capped at :data:`_MAX_RATIONALE_LENGTH`.
        card_ids: Scryfall printing uuids, in payload order, at most :data:`_MAX_ITEMS`. Not
            validated for shape (AD-7). May be empty.

    Example:
        >>> GroupItem(title="Ramp", rationale="Accelerates into the six-drops.").card_ids
        []
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "title": "Ramp",
                    "rationale": "These accelerate you into the six-drops a turn early, which is "
                    "the whole plan.",
                    "card_ids": ["076ac3ed-b59a-431f-b286-af7ed2c8704e"],
                }
            ]
        },
    )

    title: Annotated[str, AfterValidator(_refuse_blank_text)] = Field(
        min_length=1, max_length=_MAX_TITLE_LENGTH
    )
    rationale: _NonBlankRationale
    card_ids: list[_CardId] = Field(default_factory=list, max_length=_MAX_ITEMS)


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class SuggestionsPayload(BaseModel):
    """A flat list of cards the agent suggests adding (AD-7).

    Flat is the specification, not a simplification: suggestions render as one list with no
    sectioning, and an item's ``category`` is a badge on the row rather than a heading above a
    block.

    An empty ``items`` list is legal. The view skips an empty push rather than rejecting it, so
    "I looked and found nothing" is expressible.

    Attributes:
        title: The optional agent-authored header for this view — see :data:`DEFAULT_TITLE_BY_KIND`
            for what a reader shows when it is absent.
        items: At most :data:`_MAX_ITEMS` suggestions, in payload order.

    Example:
        >>> SuggestionsPayload().items
        []
    """

    model_config = ConfigDict(extra="forbid")

    title: _NonBlankTitle | None = None
    items: list[SuggestionItem] = Field(default_factory=list, max_length=_MAX_ITEMS)


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class SwapsPayload(BaseModel):
    """A list of one-for-one card trades, each with its own reasoning (AD-7).

    An empty ``items`` list is legal and renders as a skipped view.

    Attributes:
        title: The optional agent-authored header for this view — see :data:`DEFAULT_TITLE_BY_KIND`
            for what a reader shows when it is absent.
        items: At most :data:`_MAX_ITEMS` swaps, in payload order.

    Example:
        >>> SwapsPayload().items
        []
    """

    model_config = ConfigDict(extra="forbid")

    title: _NonBlankTitle | None = None
    items: list[SwapItem] = Field(default_factory=list, max_length=_MAX_ITEMS)


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class TierListPayload(BaseModel):
    """Cards ranked into named tiers, in the order the agent put them (AD-7).

    The list is capped at twelve rather than at five: the letter vocabulary is closed at five, but
    repeating a letter under a different name is legal, so the number of tiers and the number of
    letters are different quantities.

    Nothing re-sorts the tiers. An empty ``items`` list is legal.

    Attributes:
        title: The optional agent-authored header for this view — see :data:`DEFAULT_TITLE_BY_KIND`
            for what a reader shows when it is absent.
        items: At most :data:`_MAX_BUCKETS` tiers, in payload order.

    Example:
        >>> TierListPayload().items
        []
    """

    model_config = ConfigDict(extra="forbid")

    title: _NonBlankTitle | None = None
    items: list[TierItem] = Field(default_factory=list, max_length=_MAX_BUCKETS)


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class GroupsPayload(BaseModel):
    """Cards gathered into named groups, each with a paragraph of reasoning (AD-7).

    Nothing re-sorts the groups. An empty ``items`` list is legal.

    Attributes:
        title: The optional agent-authored header for this view, distinct from each group's own
            ``title`` — see :data:`DEFAULT_TITLE_BY_KIND` for the absent case.
        items: At most :data:`_MAX_BUCKETS` groups, in payload order.

    Example:
        >>> GroupsPayload().items
        []
    """

    model_config = ConfigDict(extra="forbid")

    title: _NonBlankTitle | None = None
    items: list[GroupItem] = Field(default_factory=list, max_length=_MAX_BUCKETS)


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class DeckChangedPayload(BaseModel):
    """The contents of a deck were edited — refetch it (FR-11).

    A system signal, not a view: it carries no items and renders nothing. NFR-04's model is
    "something changed, refetch", so this says which deck and stops.

    ``deck_id`` is **nullable, and that is deliberate rather than lax**. A deck-agnostic version of
    this same signal — "some deck you may be showing changed" — is anticipated, and if the field
    shipped required, adding it would break a contract already committed into a ``.d.ts`` and two
    mirrored plugin bundles. The nullability is bought now, for free.

    Attributes:
        deck_id: The deck that changed, or ``None`` meaning **refetch whatever is active**. Bounded
            by the same length as every other deck id on this wire; no second bound is invented.

    Example:
        >>> DeckChangedPayload(deck_id=None).deck_id is None
        True
    """

    model_config = ConfigDict(extra="forbid")

    deck_id: _NullableDeckId = None


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class ActiveDeckChangedPayload(BaseModel):
    """The companion is now displaying a different deck — switch to it (FR-07, FR-11).

    **Not the same signal as** ``deck_changed``, and the distinction is load-bearing: this one says
    *which deck you are looking at* has changed, the other says *the deck you are looking at was
    edited*. A client that conflates them refetches the deck it is leaving instead of the one it is
    switching to, and shows stale contents that look authoritative.

    It fires on **every** set, including one that writes the same deck id again. Suppressing a
    redundant broadcast sounds like a free optimisation and is not: the active-deck slot needs no
    lock precisely because writing it is a single assignment that never consults the old value, and
    "only broadcast if it changed" is exactly a read-modify-write. A duplicate signal costs one
    idempotent refetch; the alternative costs a lock.

    Attributes:
        deck_id: The deck now being displayed, or ``None`` for the cleared case — the slot was
            emptied, or a fresh process has not been told what to show yet.

    Example:
        >>> ActiveDeckChangedPayload(deck_id="076ac3ed").deck_id
        '076ac3ed'
    """

    model_config = ConfigDict(extra="forbid")

    deck_id: _NullableDeckId = None


# NOT PUBLISHED. Private and never referenced by a route, so it never reaches
# `components.schemas`.
class _EventEnvelope(BaseModel):
    """The two fields every event carries, whatever its kind (AD-6) — ``kind`` and ``payload``
    live on each concrete subclass, which is what completes AD-6's ``{kind, id, ts, payload}``.

    Private and never referenced by a route, so it never reaches ``components.schemas``; the six
    concrete envelopes below are the named models the union is built from.

    Attributes:
        id: See the subclasses' published prose.
        ts: See the subclasses' published prose.
    """

    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, AfterValidator(_refuse_blank_text)] = Field(
        min_length=1, max_length=_MAX_EVENT_ID_LENGTH
    )
    ts: AwareDatetime


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class SuggestionsEvent(_EventEnvelope):
    """An agent push of suggested cards (AD-6).

    Every event on this wire is ``{kind, id, ts, payload}``, and ``kind`` is what tells a reader
    which payload shape it is holding — narrowing on it is a single step, in Python and in the
    generated TypeScript alike.

    ``id`` is **opaque**. It exists for identity and de-duplication and carries **no ordering**: a
    producer is free to mint a UUID4, and a reader that sorts by ``id`` because some id schemes
    happen to sort chronologically will get a wrong order from one that does not.

    ``ts`` is the ordering key, and it must be **timezone-aware** — a naive value is refused.
    Session history sorts across kinds and across tabs, so two events minted in different offsets
    have to be comparable; producers use the UTC clock.

    Attributes:
        kind: Always ``"suggestions"``.
        id: An opaque unique id. Identity and dedupe, never ordering.
        ts: When the event was minted. Timezone-aware; naive values are refused.
        payload: The suggestions.

    Example:
        >>> from datetime import UTC, datetime
        >>> SuggestionsEvent(kind="suggestions", id="e1", ts=datetime.now(UTC),
        ...                 payload=SuggestionsPayload()).kind
        'suggestions'
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "kind": "suggestions",
                    "id": "0f6e2a11-9c3d-4b7e-8a52-1d4f6c8b0e33",
                    "ts": "2026-08-07T09:15:00Z",
                    "payload": {
                        "title": "Resilience options",
                        "items": [
                            {
                                "card_id": "076ac3ed-b59a-431f-b286-af7ed2c8704e",
                                "reason": "Fills the two-drop gap.",
                                "category": "Curve",
                                "confidence": "high",
                            }
                        ],
                    },
                }
            ]
        },
    )

    kind: Literal["suggestions"]
    payload: SuggestionsPayload


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class SwapsEvent(_EventEnvelope):
    """An agent push of one-for-one card trades (AD-6).

    Same envelope as every other event: ``kind`` selects the payload shape, ``id`` is opaque
    identity, ``ts`` is the timezone-aware ordering key.

    Attributes:
        kind: Always ``"swaps"``.
        id: An opaque unique id. Identity and dedupe, never ordering.
        ts: When the event was minted. Timezone-aware; naive values are refused.
        payload: The swaps.

    Example:
        >>> from datetime import UTC, datetime
        >>> SwapsEvent(kind="swaps", id="e2", ts=datetime.now(UTC), payload=SwapsPayload()).kind
        'swaps'
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "kind": "swaps",
                    "id": "1a7c4b98-2e5f-4c10-9d3a-7b2e5f8c1a04",
                    "ts": "2026-08-07T09:16:00Z",
                    "payload": {
                        "title": "Cheaper removal",
                        "items": [
                            {
                                "out_card_id": "076ac3ed-b59a-431f-b286-af7ed2c8704e",
                                "in_card_id": "9f2b1c44-0d3e-4a77-8f21-6b0a5d3e2c19",
                                "rationale": "Same role, one turn earlier.",
                                "out_qty": 2,
                                "in_qty": 0,
                            }
                        ],
                    },
                }
            ]
        },
    )

    kind: Literal["swaps"]
    payload: SwapsPayload


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class TierListEvent(_EventEnvelope):
    """An agent push ranking cards into named tiers (AD-6).

    Same envelope as every other event: ``kind`` selects the payload shape, ``id`` is opaque
    identity, ``ts`` is the timezone-aware ordering key.

    Attributes:
        kind: Always ``"tier_list"``.
        id: An opaque unique id. Identity and dedupe, never ordering.
        ts: When the event was minted. Timezone-aware; naive values are refused.
        payload: The tiers.

    Example:
        >>> from datetime import UTC, datetime
        >>> TierListEvent(kind="tier_list", id="e3", ts=datetime.now(UTC),
        ...               payload=TierListPayload()).kind
        'tier_list'
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "kind": "tier_list",
                    "id": "2b8d5ca9-3f60-4d21-ae4b-8c3f6a9d2b15",
                    "ts": "2026-08-07T09:17:00Z",
                    "payload": {
                        "title": "How this deck's creatures rank",
                        "items": [
                            {
                                "letter": "S",
                                "name": "Auto-include",
                                "card_ids": ["076ac3ed-b59a-431f-b286-af7ed2c8704e"],
                            }
                        ],
                    },
                }
            ]
        },
    )

    kind: Literal["tier_list"]
    payload: TierListPayload


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class GroupsEvent(_EventEnvelope):
    """An agent push gathering cards into named groups (AD-6).

    Same envelope as every other event: ``kind`` selects the payload shape, ``id`` is opaque
    identity, ``ts`` is the timezone-aware ordering key.

    Attributes:
        kind: Always ``"groups"``.
        id: An opaque unique id. Identity and dedupe, never ordering.
        ts: When the event was minted. Timezone-aware; naive values are refused.
        payload: The groups.

    Example:
        >>> from datetime import UTC, datetime
        >>> GroupsEvent(kind="groups", id="e4", ts=datetime.now(UTC),
        ...             payload=GroupsPayload()).kind
        'groups'
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "kind": "groups",
                    "id": "3c9e6db0-4071-4e32-bf5c-9d407bae3c26",
                    "ts": "2026-08-07T09:18:00Z",
                    "payload": {
                        "title": "What this deck is doing",
                        "items": [
                            {
                                "title": "Ramp",
                                "rationale": "Accelerates into the six-drops.",
                                "card_ids": ["076ac3ed-b59a-431f-b286-af7ed2c8704e"],
                            }
                        ],
                    },
                }
            ]
        },
    )

    kind: Literal["groups"]
    payload: GroupsPayload


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class DeckChangedEvent(_EventEnvelope):
    """A system signal that a deck's contents were edited (AD-6, FR-11).

    Carries no view. A reader refetches and re-renders whatever it was already showing.

    Attributes:
        kind: Always ``"deck_changed"``.
        id: An opaque unique id. Identity and dedupe, never ordering.
        ts: When the event was minted. Timezone-aware; naive values are refused.
        payload: Which deck changed, or ``None`` for "whatever is active".

    Example:
        >>> from datetime import UTC, datetime
        >>> DeckChangedEvent(kind="deck_changed", id="e5", ts=datetime.now(UTC),
        ...                  payload=DeckChangedPayload()).payload.deck_id is None
        True
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "kind": "deck_changed",
                    "id": "4d0f7ec1-5182-4f43-a06d-ae518cbf4d37",
                    "ts": "2026-08-07T09:19:00Z",
                    "payload": {"deck_id": "076ac3ed-b59a-431f-b286-af7ed2c8704e"},
                }
            ]
        },
    )

    kind: Literal["deck_changed"]
    payload: DeckChangedPayload


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description.
class ActiveDeckChangedEvent(_EventEnvelope):
    """A system signal that the companion is now displaying a different deck (AD-6, FR-07).

    Carries no view. A reader switches to the named deck, or clears to the no-active-deck state
    when the id is ``None``.

    Attributes:
        kind: Always ``"active_deck_changed"``.
        id: An opaque unique id. Identity and dedupe, never ordering.
        ts: When the event was minted. Timezone-aware; naive values are refused.
        payload: Which deck is now displayed, or ``None`` for the cleared case.

    Example:
        >>> from datetime import UTC, datetime
        >>> ActiveDeckChangedEvent(kind="active_deck_changed", id="e6", ts=datetime.now(UTC),
        ...                        payload=ActiveDeckChangedPayload()).kind
        'active_deck_changed'
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "kind": "active_deck_changed",
                    "id": "5e1a8fd2-6293-4a54-b17e-bf629dca5e48",
                    "ts": "2026-08-07T09:20:00Z",
                    "payload": {"deck_id": "076ac3ed-b59a-431f-b286-af7ed2c8704e"},
                }
            ]
        },
    )

    kind: Literal["active_deck_changed"]
    payload: ActiveDeckChangedPayload


# NOT PUBLISHED. This is a module-level assignment with an attribute docstring, so the prose below
# never reaches the wire — but the six classes it names do, each as its own `$ref`. That is the
# point of the shape.
AgentEvent = Annotated[
    SuggestionsEvent
    | SwapsEvent
    | TierListEvent
    | GroupsEvent
    | DeckChangedEvent
    | ActiveDeckChangedEvent,
    Field(discriminator="kind"),
]
"""Everything the agent or the backend may push to the glass, as one tagged union (AD-6, NFR-03).

**A union of six envelope classes, not one envelope over a payload union.** Both satisfy AD-6's
``{kind, id, ts, payload}``, but putting the discriminator on the envelope makes narrowing a single
step in the generated TypeScript — ``if (event.kind === "swaps")`` narrows ``event.payload`` too.
The alternative puts ``kind`` one level above the union it selects, so a consumer narrows twice or
casts once, in every view, forever.

**Every member is its own named model, never an inline object.** That is what makes each branch a
``$ref`` in the generated schema. ``test_errors.py``'s ``_is_ref_rooted`` guard walks only the 2xx
*response* bodies of existing routes, and this union is a *request* body, so
``test_routes_agent_events.py`` asserts the six ``$ref`` arms by name against the committed
artifact instead.

Validate with ``TypeAdapter(AgentEvent)``: the alias is an ``Annotated`` union rather than a
``BaseModel``, so it has no ``model_validate`` of its own. **Not needed in the route** — FastAPI
validates a discriminated union natively as a request-body annotation, which is why
``routes/agent_events.py`` contains no adapter.
"""


DEFAULT_TITLE_BY_KIND: dict[EventKind, str] = {
    "suggestions": "Suggestions",
    "swaps": "Swaps",
    "tier_list": "Tier list",
    "groups": "Groups",
}
"""What a view calls itself when the agent supplied no ``title``.

The agent-authored ``title`` is optional, but the view heading is the ``aria-labelledby`` target of
a ``role="dialog"`` — so an absent title does not merely look plain, it leaves a dialog unlabelled
for a screen reader. The fallback is therefore decided at the contract rather than per view.

An agent-supplied title always wins, and is expected to be more useful than these: the worked
example in the design notes reads "Resilience options", not "Suggestions".

**Four entries, not six.** The two system signals are absent on purpose: they render no view and
open no dialog, so there is no heading for them to label and a string here would be UI copy
invented for something that never draws.

**The annotation does not police coverage.** ``dict[EventKind, str]`` constrains key *type*, and
mypy accepts a partial dict silently — a signal kind is a legal :data:`EventKind` with no entry
here, so a consumer indexes with ``.get`` or narrows to a view kind first. What pins the four-entry
decision is ``test_contracts.py``'s hand-written view-kind table: a seventh push kind reddens
there, not here.

**Also pinned at import time**: the assertion below fails at module load if this dict's keys drift
from exactly the four view kinds, so the moment a seventh push kind is added and forgotten here,
every process that imports this module refuses to start — a stronger guarantee than a test that
must be run to catch it.
"""

assert set(DEFAULT_TITLE_BY_KIND) == set(get_args(EventKind)) - {
    "deck_changed",
    "active_deck_changed",
}, (
    "DEFAULT_TITLE_BY_KIND must cover exactly the four view kinds (every EventKind member except "
    "the two system signals) — a missing or extra entry here is the 'seventh push kind added "
    "without meeting this decision' danger the docstring above describes."
)


# ---------------------------------------------------------------------------------------------
# The ingest receipt (FR-06, AD-8)
#
# The *answer* to a push of the union above rather than a member of it, which is why it is a
# sibling of the envelope block rather than an addition inside it.
# ---------------------------------------------------------------------------------------------


# WIRE-VISIBLE, IN FULL. The prose before `Attributes:` becomes the schema description, so it is
# written for the agent author reading `/docs`, not for a maintainer reading this file.
class EventIngestReceipt(BaseModel):
    """The body of ``POST /agent/events`` — how many connected clients received the push (FR-06).

    The push itself carries no answer: a WebSocket frame is written and not acknowledged, so this
    receipt is the **only** thing that tells a caller whether its content actually reached a
    browser. That is what the endpoint is for — an agent that pushed a tier list can say "shown in
    two tabs" or "nothing is listening" rather than guessing.

    **Zero is a success, not a failure.** A companion with no tab open is the ordinary state, and a
    push nobody heard is delivered exactly as instructed; the caller should report that rather than
    retry. Nothing about the payload is echoed back (CM-1) — the agent already has what it sent, and
    a body that repeated it would double the cost of every push to say nothing new.

    Attributes:
        clients: How many clients the event was written to, never negative.

            **Delivered, not registered.** This is
            :func:`~src.companion.app.ws.broadcast`'s return value: clients that took the frame,
            with any that failed mid-fan-out dropped from the count and from the registry. The
            alternative — sampling
            :attr:`~src.companion.app.state.ConnectionRegistry.connected_count` around the
            broadcast — reads the set the fan-out is concurrently pruning, so it can over-report a
            tab that vanished in exactly the window ``broadcast``'s accepted-residual paragraph
            describes. "How many browsers saw it" is the question this endpoint exists to answer,
            and only the delivered count answers it truthfully. This paragraph sits below the
            header deliberately: ``main._DOCSTRING_SECTIONS`` truncates it off the wire, and which
            of two internal accountings was chosen is repo-internal reasoning.

            It is a count at the moment of the fan-out and **not** a live gauge — a tab may open or
            close immediately afterwards. Nothing should be cached from it.

    Example:
        >>> EventIngestReceipt(clients=0).model_dump()
        {'clients': 0}
    """

    clients: int = Field(ge=0)

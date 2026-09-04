"""Talking *to* the companion backend from outside it: identity, then the push (AD-3, AD-4, AD-8).

:func:`live_instance` proves that a companion is genuinely running on the discovered port;
:func:`push_event`, :func:`set_active_deck` and :func:`notify_deck_changed` are the authenticated
verbs, sharing one discovery read, one retry shape and one closed outcome vocabulary.

Identity, not "something answered" (AD-4): a discovery file outlives the process that wrote it
(AD-15) and the port may be reused, so only an echoed ``instance_id`` matching the recorded one
proves anything. The authenticated verbs do not probe before each send: the discovery file is the
trust root (no usable file is ``app_not_running`` with zero network), a refused connection is
``app_not_running`` too, and a foreign loopback process already runs as the same user. ``/health``
is unauthenticated by design: it is read *before* the port is trusted, so requiring the token would
hand the credential to an unproven process. Nothing on that path sends, reads or logs a token.

Timeouts are split because a connect to a *dead* loopback port takes ~2 s to report refusal while
a live instance answers in ~15 ms, and a stale file is the ordinary post-crash state: the connect
deadline is tight (a live listener completes the handshake in the kernel, busy or not) and the read
deadline generous, since calling a live-but-busy companion dead starts the second instance the
startup check exists to prevent.

Leaf (AD-3): stdlib, ``pydantic``, ``httpx``, ``src.paths`` and sibling leaves only; never
``fastapi``, ``uvicorn``, ``sqlalchemy`` or ``src.companion.app``, not even under
``if TYPE_CHECKING:``, so ``src/mcp_server`` can import it without loading a web framework.
``tests/unit/companion/test_import_boundary.py`` enforces it.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal, get_args
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict

from src.companion.contracts import (
    ActiveDeckRequest,
    ActiveDeckSetReceipt,
    AgentEvent,
    DeckChangedEvent,
    DeckChangedPayload,
    EventIngestReceipt,
    HealthResponse,
)
from src.companion.discovery import DiscoveryRecord, read_discovery

logger = logging.getLogger(__name__)

LOOPBACK_HOST = "127.0.0.1"
"""The address a caller dials. Not imported from ``src.companion.app.server.HOST`` because a leaf
may not import the app (AD-3); NFR-01 fixes both to loopback IPv4.
"""

HEALTH_PATH = "/health"
"""The unauthenticated identity endpoint (FR-14)."""

EVENTS_PATH = "/agent/events"
"""The token-authenticated ingest endpoint (FR-06)."""

ACTIVE_DECK_PATH = "/api/active-deck"
"""The token-authenticated display-control endpoint (FR-07); only its ``PUT`` is called here."""

PROBE_TIMEOUT = httpx.Timeout(connect=1.0, read=2.0, write=2.0, pool=2.0)
"""Short connect (a dead loopback port takes ~2 s to refuse), long read (a busy live companion
must never be mistaken for a dead one); see the module docstring.
"""

_PROBE_TOTAL_SECONDS = 5.0
"""The whole-probe deadline: ``httpx``'s ``read`` caps only the gap *between chunks*, so a foreign
server dripping one byte a second would otherwise hold a launching ``run()`` open forever.
"""

_PUSH_TOTAL_SECONDS = 10.0
"""The deadline on a whole authenticated call, the request and its one retry together: ten seconds
so it clears both attempts, since a deadline firing mid-retry would turn a healthy restart into
``backend_error``. AD-9's ~1 s bound governs the notifier, which a *user* waits on, not this path.
"""

_NOTIFY_TOTAL_SECONDS = 1.0
"""The whole-call deadline for :func:`notify_deck_changed`: AD-9's ~1 s bound, its own constant
rather than a parameter a caller can widen. Losing the retry to the budget is acceptable.
"""

PushOutcomeToken = Literal[
    "displayed",
    "app_not_running",
    "no_clients_connected",
    "payload_rejected",
    "backend_error",
]
"""Everything this client can report about one authenticated call, and nothing else (AD-8).

Closed at five because five is what the *wire* can tell the client; a caller that can distinguish
more (``deck_not_found``, from the MCP tool's own database lookup) layers above this set. The count
travels beside the token in :attr:`PushOutcome.clients`, never inside it. The field is ``outcome``,
not ``status``, because ``status`` is already the MCP tool result key with its own vocabulary.
``no_clients_connected`` is a **success** on the wire that must never be retried (the backend will
not re-send, so a retry pushes duplicates at the first tab to open); ``app_not_running`` covers a
missing discovery file and a refused connection alike, because a caller can do one thing about
either; ``payload_rejected`` (400 or 413) needs a different payload, not a retry; ``backend_error``
is the residual, including a credential still refused after the one retry.
"""

PUSH_OUTCOMES: tuple[PushOutcomeToken, ...] = get_args(PushOutcomeToken)
"""The five tokens as data, derived from :data:`PushOutcomeToken` so they cannot drift apart."""


class PushOutcome(BaseModel):
    """What one authenticated call reports back: one token, and who received it (AD-8).

    Frozen: this value crosses into a tool's result assembly, and the tool's job is to *read* it.

    Attributes:
        outcome: The single token from :data:`PushOutcomeToken`.
        clients: How many connected browsers the backend **delivered** to, when it said. ``None``
            when no receipt was reached, deliberately distinct from ``0`` (a successful push).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: PushOutcomeToken
    clients: int | None = None


def base_url(port: int) -> str:
    """Assemble the companion's base URL (no trailing slash) for *port*, the one place that does.

    ``127.0.0.1`` literally rather than ``localhost``: the socket is IPv4-only and ``localhost``
    resolves to ``::1`` first on Windows and modern Linux.
    """
    return f"http://{LOOPBACK_HOST}:{port}"


_shared: tuple[asyncio.AbstractEventLoop, httpx.AsyncClient] | None = None
"""The cached ``(loop, client)`` pair behind :func:`_shared_client`."""


def _shared_client() -> httpx.AsyncClient:
    """Return the one ``httpx.AsyncClient`` every request in this module goes through.

    Cached against the running loop, since a pool belongs to the loop it was first used on.
    ``trust_env=False`` because a configured proxy would misroute the loopback dial and ``.netrc``
    would quietly attach an ``Authorization`` header. No default timeout: every call passes its
    own. ``keepalive_expiry=2.0`` because uvicorn closes an idle keep-alive after 5 s, as does
    httpx's default pool expiry, so a pooled socket could be closed at the moment it is reused.

    Returns:
        The shared client for the running loop.
    """
    global _shared
    loop = asyncio.get_running_loop()
    if _shared is not None:
        cached_loop, cached = _shared
        if cached_loop is loop and not cached.is_closed:
            return cached
    client = httpx.AsyncClient(trust_env=False, limits=httpx.Limits(keepalive_expiry=2.0))
    _shared = (loop, client)
    return client


def reset_shared_client() -> None:
    """Forget the cached client without closing it (test isolation only)."""
    global _shared
    _shared = None


async def aclose_shared_client() -> None:
    """Close the shared client if this loop owns one, and forget it; another loop's is dropped."""
    global _shared
    if _shared is None:
        return
    cached_loop, cached = _shared
    _shared = None
    if cached_loop is asyncio.get_running_loop() and not cached.is_closed:
        await cached.aclose()


async def probe_health(port: int, *, timeout: httpx.Timeout | None = None) -> HealthResponse | None:
    """Ask *port* who it is, and return its answer only if a companion gave one.

    **Never raises.** Every failure means *no companion is answering there*, so all return
    ``None``: nothing listening, a listener that never answers or is too slow overall (cut off by
    :data:`_PROBE_TOTAL_SECONDS`), a foreign body, and any status other than ``200``, the only one
    a real ``/health`` returns. The whole body sits inside one ``except (TimeoutError,
    httpx.HTTPError, ValueError)``; all three are load-bearing (``HTTPError`` is not a
    ``ValueError``, ``TimeoutError`` is an ``OSError``, the pydantic and decode errors are
    ``ValueError`` subclasses) and it is deliberately not ``except Exception``: a ``MemoryError``
    is a broken machine, not a companion that is not running. Rejections log at DEBUG because on
    the push path nothing being there is the expected case.

    Args:
        port: The loopback port to probe.
        timeout: Override the deadline (a test seam); production callers get :data:`PROBE_TIMEOUT`.

    Returns:
        The parsed health body, or ``None`` if anything other than this application answered.
    """
    url = f"{base_url(port)}{HEALTH_PATH}"
    try:
        async with asyncio.timeout(_PROBE_TOTAL_SECONDS):
            response = await _shared_client().get(
                url, timeout=PROBE_TIMEOUT if timeout is None else timeout
            )
            if response.status_code != 200:
                logger.debug(
                    "Probe of %s answered %d, not 200; treating as app not running",
                    url,
                    response.status_code,
                )
                return None
            return HealthResponse.model_validate_json(response.content)
    except (TimeoutError, httpx.HTTPError, ValueError) as exc:
        logger.debug("No companion answering at %s (%s)", url, type(exc).__name__)
        return None


async def live_instance(*, timeout: httpx.Timeout | None = None) -> DiscoveryRecord | None:
    """Answer "is a companion actually running?" in one call (AD-4). Never raises.

    With no usable discovery file **no network call is made at all**: a launch on a clean machine
    must not pay for a connect against a port nobody named. Otherwise the port is probed and only
    an exact identity match counts. The *record* is returned rather than a bool because callers
    need its ``port``; the token beside it is never read here.

    Args:
        timeout: Forwarded to :func:`probe_health`; ``None`` uses :data:`PROBE_TIMEOUT`.

    Returns:
        The published record when a companion matching it is genuinely answering, else ``None``.
    """
    record = read_discovery()
    if record is None:
        return None
    health = await probe_health(record.port, timeout=timeout)
    if health is None:
        return None
    if health.instance_id != record.instance_id:
        logger.debug(
            "Port %d is held by instance %s, not the recorded %s; treating as app not running",
            record.port,
            health.instance_id,
            record.instance_id,
        )
        return None
    return record


async def _send(
    record: DiscoveryRecord,
    *,
    method: str,
    path: str,
    body: str,
    timeout: httpx.Timeout | None,
) -> httpx.Response | PushOutcome:
    """Make one authenticated request to the companion the discovery record names.

    **Never raises**, with :func:`probe_health`'s net. A refused or never-completed connection is
    the ordinary post-crash state (a stale file naming a dead port) and is ``app_not_running``;
    any other incomplete exchange means something is listening and did not answer properly, which
    is ``backend_error``. Generic over method and path so every verb shares one header, timeout
    and net; it stays private. **The token is read here and nowhere else**, placed in exactly one
    header, and appears in no log line at any level.

    Args:
        record: The discovery record just read; its ``token`` is the credential.
        method: The HTTP method, e.g. ``"POST"``.
        path: The path to request, e.g. :data:`EVENTS_PATH`.
        body: The already-serialised JSON body.
        timeout: Override the per-request deadline; ``None`` uses :data:`PROBE_TIMEOUT`.

    Returns:
        The response, whatever its status, or the outcome to report if the exchange never completed.
    """
    url = f"{base_url(record.port)}{path}"
    try:
        return await _shared_client().request(
            method,
            url,
            content=body,
            headers={
                "Authorization": f"Bearer {record.token}",
                "content-type": "application/json",
            },
            timeout=PROBE_TIMEOUT if timeout is None else timeout,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        logger.debug("No companion answering at %s (%s)", url, type(exc).__name__)
        return PushOutcome(outcome="app_not_running")
    except (TimeoutError, httpx.HTTPError, ValueError) as exc:
        logger.debug("The %s to %s did not complete (%s)", method, url, type(exc).__name__)
        return PushOutcome(outcome="backend_error")


def _outcome_for(response: httpx.Response) -> PushOutcome | None:
    """Turn one answered request into its token, or into the decision to retry.

    Statuses only, never the ``reason`` string: the error body is written for humans, and the
    statuses already separate every case (``app/errors.py``'s ``STATUS_BY_REASON`` is one-to-one
    on the codes that reach here). ``400`` (a field cap) and ``413`` (the 64 KB envelope cap) fold
    into one token because both mean the payload was refused in full. A ``200`` is a delivery only
    if its body parses as an ``EventIngestReceipt``, so ``{"clients": -1}`` is a ``backend_error``.

    Args:
        response: The answer to a request that completed.

    Returns:
        The outcome, or ``None`` for a ``403``: whether a refused credential is a retry or a
        failure is the caller's budget to spend.
    """
    status = response.status_code
    if status == 403:
        return None
    if status == 200:
        try:
            receipt = EventIngestReceipt.model_validate_json(response.content)
        except ValueError as exc:
            logger.debug("The backend answered 200 with no usable receipt (%s)", type(exc).__name__)
            return PushOutcome(outcome="backend_error")
        if receipt.clients >= 1:
            return PushOutcome(outcome="displayed", clients=receipt.clients)
        return PushOutcome(outcome="no_clients_connected", clients=receipt.clients)
    if status in (400, 413):
        logger.debug("The backend refused the envelope with %d", status)
        return PushOutcome(outcome="payload_rejected")
    logger.debug("The backend answered %d, which is no outcome this client knows", status)
    return PushOutcome(outcome="backend_error")


async def _attempt(body: str, *, timeout: httpx.Timeout | None) -> PushOutcome | None:
    """Run one read-then-send cycle (discovery, then the POST) for the serialised *body*.

    Discovery is re-read on **every** attempt, since the retry exists to pick up a *different*
    token. Returns the outcome, or ``None`` if the credential was refused and a retry could help.
    """
    record = read_discovery()
    if record is None:
        return PushOutcome(outcome="app_not_running")
    response = await _send(record, method="POST", path=EVENTS_PATH, body=body, timeout=timeout)
    if isinstance(response, PushOutcome):
        return response
    return _outcome_for(response)


async def _once_then_retry(
    attempt: Callable[[], Awaitable[PushOutcome | None]],
    *,
    what: str,
    budget: float | None = None,
) -> PushOutcome:
    """Run *attempt*, and if the credential was refused, run it once more, then stop.

    **The retry is exactly one, spent on a refused credential alone** (FR-12): the backend mints a
    fresh token every start, so a companion restarted mid-session refuses the token a tool holds,
    the single case where trying again is a correction rather than a duplicate. A second refusal is
    ``backend_error``. **At most two authenticated requests ever leave a call through here.**

    Args:
        attempt: One whole read-then-send cycle; ``None`` means the credential was refused.
        what: The verb's name for the log line. Never a payload or a credential.
        budget: The whole-call deadline covering both attempts. ``None`` reads
            :data:`_PUSH_TOTAL_SECONDS` at call time so a ``monkeypatch`` of it takes effect.

    Returns:
        Exactly one :class:`PushOutcome`.
    """
    if budget is None:
        budget = _PUSH_TOTAL_SECONDS
    try:
        async with asyncio.timeout(budget):
            first = await attempt()
            if first is not None:
                return first
            logger.debug("The companion refused the credential; re-reading discovery and retrying")
            second = await attempt()
            if second is not None:
                return second
            logger.debug("The freshly read credential was refused too; not retrying again")
            return PushOutcome(outcome="backend_error")
    except TimeoutError:
        logger.debug("The %s did not complete within %.1fs", what, budget)
        return PushOutcome(outcome="backend_error")


async def push_event(event: AgentEvent, *, timeout: httpx.Timeout | None = None) -> PushOutcome:
    """Push one event to the companion's glass, and report the single thing that happened (AD-8).

    The one public way anything outside this module reaches ``POST /agent/events``. Every
    companion MCP tool funnels through it so they all fail the same way and **none can break an
    agent turn**: whatever the companion does is one of the five tokens, never an exception
    (FR-12); a ``MemoryError`` mid-call is a broken machine and is let through. The retry is spent
    on ``403`` alone: a ``500`` or a dropped connection buys no second attempt, because re-sending
    a payload the backend may already have accepted-then-failed on is how one push becomes two
    renders.

    Args:
        event: A concrete envelope, one member of :data:`~src.companion.contracts.AgentEvent`,
            taken already-built and **never re-validated**: the union is an ``Annotated``
            discriminated union with no ``.model_validate``.
        timeout: Override the per-request deadline (a test seam). It does **not** override
            :data:`_PUSH_TOTAL_SECONDS`.

    Returns:
        Exactly one :class:`PushOutcome`.
    """
    body = event.model_dump_json()
    return await _once_then_retry(lambda: _attempt(body, timeout=timeout), what="push")


async def notify_deck_changed(
    deck_id: str | None = None, *, timeout: httpx.Timeout | None = None
) -> PushOutcome:
    """Tell the companion a deck's contents changed, and never let the caller find out how (AD-9).

    The one shared notifier every deck-mutation tool funnels through. It mints the ``deck_changed``
    envelope itself, POSTs it through the same ``/agent/events`` route as :func:`push_event` (a
    system signal on the same wire, not a new endpoint), and reports the same five tokens (AD-8).

    **Bounded await, never a detached task.** A mutation tool awaits this after its transaction
    commits, and the notification must never outlive that call: ``asyncio.create_task``,
    ``ensure_future``, ``TaskGroup`` and ``gather`` are banned on this path (a task outliving the
    tool call can be torn down before it runs, silently losing the event);
    ``test_the_push_path_creates_no_task`` in ``test_ws.py`` sweeps ``src/companion`` for them.
    The bound is :data:`_NOTIFY_TOTAL_SECONDS`, ~1 s rather than :func:`push_event`'s ~10 s,
    because a mutation tool's response is held up by this await.

    **Every exception is caught**, the one divergence from :func:`push_event`: this runs inside a
    mutation tool's success path, where a notifier defect must never turn a successful add, remove
    or import into a failure. The outer ``except Exception`` logs at WARNING with ``exc_info``.

    **What the swallow costs (AD-9, ``ARCHITECTURE-SPINE.md:211``)**, stated at both sites that
    swallow, here and :func:`src.mcp_server.server._emit_deck_changed`, so an amendment starts at
    the spine and changes both: every token but ``displayed`` means the mutation committed and the
    glass did not hear, so the deck view is **stale until the next event or a WebSocket
    reconnect**. That window is accepted until FR-16 (out-of-band change detection), and until then
    the UI deliberately shows **no staleness warning** (``EXPERIENCE.md``'s Flow 1 failure path).
    Do not add a further retry, a persistent queue, or any surfacing path; the reconnect refetch in
    ``ui/src/state/connection.ts`` is the only healer this design has.

    Args:
        deck_id: The deck that changed, or ``None`` meaning "refetch whatever is active".
        timeout: Override the per-request deadline. It does **not** override
            :data:`_NOTIFY_TOTAL_SECONDS`.

    Returns:
        Exactly one :class:`PushOutcome`. Never raises.
    """
    try:
        event = DeckChangedEvent(
            kind="deck_changed",
            id=str(uuid4()),
            ts=datetime.now(UTC),
            payload=DeckChangedPayload(deck_id=deck_id),
        )
        body = event.model_dump_json()
        return await _once_then_retry(
            lambda: _attempt(body, timeout=timeout),
            what="notify",
            budget=_NOTIFY_TOTAL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 -- AD-9: a notifier bug must never fail the mutation
        logger.warning(
            "notify_deck_changed failed unexpectedly (%s)", type(exc).__name__, exc_info=True
        )
        return PushOutcome(outcome="backend_error")


def _active_deck_outcome_for(response: httpx.Response) -> PushOutcome | None:
    """Turn one answered ``PUT /api/active-deck`` into its token, or into the decision to retry.

    A sibling of :func:`_outcome_for` rather than a widening of it: the two agree on every status
    and disagree on what a ``200`` body is (``ActiveDeckSetReceipt`` here, ``EventIngestReceipt``
    for the push), and parsing either with the other model type-checks yet turns every success into
    ``backend_error``. ``401`` folds into ``backend_error`` unretried because this backend cannot
    answer it on this gate, so one arriving means something else answered. **There is no
    ``deck_not_found`` here** (AD-16): the route has no database and no ``404``.

    Args:
        response: The answer to a request that completed.

    Returns:
        The outcome, or ``None`` for a ``403``, the one status this function does not resolve.
    """
    status = response.status_code
    if status == 403:
        return None
    if status == 200:
        try:
            receipt = ActiveDeckSetReceipt.model_validate_json(response.content)
        except ValueError as exc:
            logger.debug("The backend answered 200 with no usable receipt (%s)", type(exc).__name__)
            return PushOutcome(outcome="backend_error")
        if receipt.clients >= 1:
            return PushOutcome(outcome="displayed", clients=receipt.clients)
        return PushOutcome(outcome="no_clients_connected", clients=receipt.clients)
    if status in (400, 413):
        logger.debug("The backend refused the active-deck request with %d", status)
        return PushOutcome(outcome="payload_rejected")
    logger.debug("The backend answered %d, which is no outcome this client knows", status)
    return PushOutcome(outcome="backend_error")


async def _active_deck_attempt(body: str, *, timeout: httpx.Timeout | None) -> PushOutcome | None:
    """Run one read-then-send cycle (discovery, then the ``PUT``); see :func:`_attempt`."""
    record = read_discovery()
    if record is None:
        return PushOutcome(outcome="app_not_running")
    response = await _send(record, method="PUT", path=ACTIVE_DECK_PATH, body=body, timeout=timeout)
    if isinstance(response, PushOutcome):
        return response
    return _active_deck_outcome_for(response)


async def set_active_deck(
    request: ActiveDeckRequest, *, timeout: httpx.Timeout | None = None
) -> PushOutcome:
    """Tell the companion which deck to display, and report the single thing that happened (FR-07).

    The one public way anything outside this module reaches ``PUT /api/active-deck``. A **control**
    call rather than a push, but :func:`push_event`'s shape: read discovery, send one authenticated
    request, report one of the five tokens, and **never break an agent turn** (FR-12). The backend
    broadcasts on **every** set, including a repeat of the same id, so this function must not
    dedupe. **The deck is not checked for existence anywhere on this path** (AD-16): the route has
    no database, so there is no ``404`` to observe; the MCP tool reports ``deck_not_found`` from
    its own lookup.

    Args:
        request: A concrete, already-valid :class:`~src.companion.contracts.ActiveDeckRequest`,
            **never re-validated**.
        timeout: Override the per-request deadline (a test seam). It does **not** override
            :data:`_PUSH_TOTAL_SECONDS`.

    Returns:
        Exactly one :class:`PushOutcome`.
    """
    body = request.model_dump_json()
    return await _once_then_retry(
        lambda: _active_deck_attempt(body, timeout=timeout), what="active-deck set"
    )

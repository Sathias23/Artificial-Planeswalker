"""Talking *to* the companion backend from outside it — identity, then the push (AD-3, AD-4, AD-8).

This is the whole leaf client named in the spine's Structural Seed
(``client.py # LEAF — /health + /agent/events, notifier``), in the two halves it was always meant
to have. c1-8 landed the **``/health`` half**: finding out whether a companion is genuinely live on
the discovered port, and refusing to believe anything else. c6-1 landed the **``POST /agent/events``
half**: :func:`push_event`, its retry-once, and the closed outcome vocabulary every companion MCP
tool reports through — and it reuses the probe below before *every* send rather than duplicating it,
including before the retry.

**Why the probe exists at all (AD-4).** The discovery file says *where* the companion is, but a
file outlives the process that wrote it: AD-15 accepts that a crash leaves a stale entry behind,
and the operating system is free to hand that port to something else entirely. "Something answered"
is therefore not evidence — a local dev server that returns ``200`` to every path would pass that
test. Only an ``instance_id`` echoed back that **matches the recorded one** proves the process
answering is the process the file describes. That match is what makes it safe to send the agent
token, and a mismatch is *app not running*, never *ambiguous* and never a reason to send a
credential.

**``/health`` is unauthenticated by design, and that is not a gap.** It is what a caller reads
*before* deciding to trust the port, so requiring the token to read it would invert the order: the
credential would have to be handed to an unproven process to find out whether that process deserved
it. Nothing on this path sends a token, reads one, or logs one.

**Why the timeout is split — a short connect, a longer read.** Measured on the primary development
platform, a TCP connect to a *dead* loopback port takes **~2 s** to report refusal (raw socket,
``asyncio.open_connection`` and httpx all agree), while a live instance answers ``/health`` in
~15 ms. A stale discovery file is the *ordinary* post-crash state, so a single undivided deadline
would make every launch after a crash stall for seconds. The connect deadline is therefore tight —
a live listener completes the loopback handshake in the kernel, in microseconds, busy or not, so a
short connect deadline cannot make a live instance look dead. The read deadline is deliberately
generous, because the read is the half that genuinely can be slow on a live app, and calling a
live-but-busy companion dead is the expensive mistake: it starts a second instance, which is
precisely what the startup check exists to prevent.

This module is a **leaf** (AD-3): stdlib, ``pydantic``, ``httpx``, ``src.paths`` and its sibling
leaves only — never ``fastapi``, ``uvicorn``, ``sqlalchemy`` or ``src.companion.app``, and not even
under ``if TYPE_CHECKING:``. That is what lets ``src/mcp_server`` import it so a stdio MCP session
can ask "is the app running?" without transitively importing a web framework and a server, and it
is why the probe lives here rather than as a private helper inside the runner.
``tests/unit/companion/test_import_boundary.py`` enforces it.
"""

import asyncio
import logging
from typing import Literal, get_args

import httpx
from pydantic import BaseModel, ConfigDict

from src.companion.contracts import AgentEvent, EventIngestReceipt, HealthResponse
from src.companion.discovery import DiscoveryRecord, read_discovery

logger = logging.getLogger(__name__)

LOOPBACK_HOST = "127.0.0.1"
"""The address a caller dials to reach the companion.

Deliberately **not** imported from ``src.companion.app.server.HOST``: a leaf may not import the
app (AD-3), and that constraint is worth more than removing one duplicated literal. The twin is
``server.HOST``, and NFR-01 fixes both to loopback IPv4 — neither is configurable, so they cannot
drift apart by configuration, only by an edit that would have to change both.
"""

HEALTH_PATH = "/health"
"""The unauthenticated identity endpoint c1-2 serves (FR-14)."""

EVENTS_PATH = "/agent/events"
"""The token-authenticated ingest endpoint c5-5 serves (FR-06)."""

PROBE_TIMEOUT = httpx.Timeout(connect=1.0, read=2.0, write=2.0, pool=2.0)
"""The measured connect/read split explained in the module docstring.

Short connect so a stale entry costs a fraction of a second rather than the ~2 s a dead loopback
port takes to refuse; long read so a live-but-busy companion is never mistaken for a dead one.
"""

_PROBE_TOTAL_SECONDS = 5.0
"""The whole-probe deadline that bounds what :data:`PROBE_TIMEOUT` cannot.

``httpx``'s ``read`` deadline caps the gap *between chunks*, not the whole exchange — a foreign
server on a recycled port that drips one byte every second, or streams an enormous body, would
otherwise hold the probe (and therefore a launching ``run()``) open indefinitely. Comfortably
above ``connect + read`` so it can never fire on the ordinary outcomes, and small enough that the
worst pathological listener costs a launch five seconds, not forever. (Review finding, c1-8:
a sanctioned widening of AC 4's net — the ``TimeoutError`` it raises is folded into ``None``.)
"""

_PUSH_TOTAL_SECONDS = 10.0
"""The deadline on a whole :func:`push_event` call — probe, post, re-probe and retry together.

The push has a second exposure the probe does not: :data:`PROBE_TIMEOUT`'s ``read`` still caps only
the gap between chunks, and now there are up to *four* legs behind that gap. One cap over all of
them is what makes "this call returns" a property of the function rather than a sum of four
independent hopes.

Ten seconds, not five, because it has to clear **two whole attempts**: a deadline that could fire
mid-retry would cut off the very transparency FR-12's retry exists to provide, turning a healthy
restart into a ``backend_error``. AD-9's ~1 s responsiveness bound governs c7's notifier — the
thing a *user* waits on — not this path, where the caller is an agent turn that has already
committed to a network round trip. (Q4, Brad 2026-08-09.)
"""

PushOutcomeToken = Literal[
    "displayed",
    "app_not_running",
    "no_clients_connected",
    "payload_rejected",
    "backend_error",
]
"""Everything a companion MCP tool may report about a push, and nothing else (AD-8).

**Five tokens, closed, and none of them carries a number or a phrase.** A caller switches on these;
a human reads the tool's own wording built *from* them. That split is the same convention the MCP
tools already use for their ``status`` values, and it is why the count travels beside the token in
:attr:`PushOutcome.clients` rather than inside it — ``displayed_to_two`` would be a token nothing
could compare and everything would have to parse.

**The field is named** ``outcome``, **not** ``status`` (dw:3098, ruled here). ``status`` is already
taken in this repo: it is the MCP tool result key whose values include ``deck_not_found`` and
``card_not_found``, spellings that predate the HTTP wire contract and are documented in shipped
``skills/**`` files. One word carrying two vocabularies in one skill document is a collision a
different field name costs nothing to avoid. This set is closed to exactly these five because it
is what the client itself can observe on the wire; a tool built above this client is free to layer
its own, wider vocabulary (see ``deferred-work.md``) — that layering does not belong here.

Why each token exists, in the order a caller cares:

* ``displayed`` — the backend delivered the event to at least one connected browser.
* ``no_clients_connected`` — the backend took it and no tab was listening. On the wire this is a
  **success** (``200 {"clients": 0}``), not an error; this is the only place it becomes "nobody saw
  it". A caller must not retry it — c5-5's ruling: the backend will not re-send, so a retry pushes
  duplicates at the first tab to open.
* ``app_not_running`` — no companion could be proven live, so nothing was sent. Covers a missing or
  unreadable discovery file, a dead or foreign port, and a failed identity match alike, because a
  caller can do exactly one thing about all of them.
* ``payload_rejected`` — the backend refused the envelope itself (400 or 413). Retrying is
  pointless; the payload has to change.
* ``backend_error`` — the companion is there and the push did not land. The residual: 5xx, an
  unexpected status, a body that is not a receipt, a dropped connection, a blown deadline, and a
  credential still refused after the one retry.
"""

PUSH_OUTCOMES: tuple[PushOutcomeToken, ...] = get_args(PushOutcomeToken)
"""The five tokens as data, derived from :data:`PushOutcomeToken` so they cannot drift apart."""


class PushOutcome(BaseModel):
    """What one :func:`push_event` call reports back — one token, and who received it (AD-8).

    Frozen, because a report a caller can edit is not a report: this value crosses from the client
    into a tool's own result assembly, and the tool's job is to *read* it.

    Attributes:
        outcome: The single token from :data:`PushOutcomeToken`.
        clients: How many connected browsers the backend delivered to, when it said — the receipt's
            own count (c5-5: **delivered**, not registered). ``None`` on every outcome that never
            reached a receipt, which is deliberately distinguishable from ``0``: "the backend never
            told us" and "the backend told us nobody was listening" are different facts, and only
            the second one is a successful push.

    Example:
        >>> PushOutcome(outcome="displayed", clients=2).model_dump()
        {'outcome': 'displayed', 'clients': 2}
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: PushOutcomeToken
    clients: int | None = None


def base_url(port: int) -> str:
    """Assemble the companion's base URL — the one place in the codebase that does.

    ``127.0.0.1`` literally rather than ``localhost``: the companion's socket is IPv4-only and
    ``localhost`` resolves to ``::1`` first on Windows and modern Linux, so the name would dial an
    address nothing is listening on. :func:`probe_health` and :func:`push_event` both dial what this
    returns, and the runner prints it.

    Args:
        port: The loopback port the companion bound.

    Returns:
        The scheme-and-authority prefix, with no trailing slash.
    """
    return f"http://{LOOPBACK_HOST}:{port}"


async def probe_health(port: int, *, timeout: httpx.Timeout | None = None) -> HealthResponse | None:
    """Ask *port* who it is, and return its answer only if a companion gave one.

    **Never raises.** Every way this can fail means the same thing to a caller — *no companion is
    answering there* — so all of them return ``None``: nothing listening (``ConnectTimeout`` under
    a short deadline, ``ConnectError`` under a long one), a listener that accepts and never answers
    (``ReadTimeout``), a listener that answers but too slowly overall — dripping chunks that each
    beat the read deadline, or streaming an endless body — cut off by the whole-probe
    :data:`_PROBE_TOTAL_SECONDS` (``TimeoutError``), a foreign server returning HTML, JSON of the
    wrong shape, bytes that are not UTF-8, and any status other than ``200`` — the only status a
    real companion's ``/health`` returns, so a ``201`` or ``204`` is just as foreign as a ``400``.
    The whole body sits inside one ``except (TimeoutError, httpx.HTTPError, ValueError)``,
    including the client's construction and teardown: a "never raises" promise that only covers
    the happy path is not one (the c1-7 review's first finding).

    All three members of that tuple are load-bearing and none is redundant — ``httpx.HTTPError``
    is the root of the transport family and is *not* a ``ValueError``, ``TimeoutError`` (what
    ``asyncio.timeout`` raises) is an ``OSError`` and belongs to neither family, while
    ``pydantic.ValidationError`` (and the ``UnicodeDecodeError`` / ``JSONDecodeError`` that
    ``model_validate_json`` raises on undecodable or non-JSON bytes) *are* ``ValueError``
    subclasses. It is deliberately **not** ``except Exception``: a ``MemoryError`` mid-probe is a
    broken machine, not a companion that is not running.

    **The dial ignores proxy environment variables** (``trust_env=False``). httpx grants loopback
    no exemption from ``HTTP_PROXY``/``ALL_PROXY``, so without this a machine with a proxy
    configured would send the probe *to the proxy*, judge the live companion dead, and start the
    duplicate instance this probe exists to prevent. It also stops ``.netrc`` from quietly
    attaching an ``Authorization`` header — nothing on this path may carry a credential (AC 6).

    The status is checked explicitly rather than via ``raise_for_status()``. That keeps "this is
    not our app" an ordinary outcome instead of an exception caught two lines later, and it keeps
    the non-2xx case distinguishable from a transport failure in the log.

    Rejections log at DEBUG, not WARNING: on the push path below, the *expected* case is that
    nothing is there, and a warning on every push would be noise in the user's terminal.

    Args:
        port: The loopback port to probe.
        timeout: Override the deadline. Exists so a test can drive the dead-port and
            never-answers cases in milliseconds; production callers pass nothing and get
            :data:`PROBE_TIMEOUT`.

    Returns:
        The parsed health body, or ``None`` if anything other than this application answered.
    """
    url = f"{base_url(port)}{HEALTH_PATH}"
    try:
        async with (
            asyncio.timeout(_PROBE_TOTAL_SECONDS),
            httpx.AsyncClient(
                timeout=PROBE_TIMEOUT if timeout is None else timeout, trust_env=False
            ) as client,
        ):
            response = await client.get(url)
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
    """Answer "is a companion actually running?" — the whole question, in one call (AD-4).

    The sequence short-circuits deliberately. With no usable discovery file there is nothing to
    probe and **no network call is made at all**, which is an assertable behaviour rather than an
    optimisation: a launch on a clean machine must not pay for a connect attempt against a port
    nobody named. With a record in hand, its port is probed and the echoed identity compared; only
    an exact match counts.

    The *record* is returned rather than a bool because both of its other fields are wanted the
    moment identity is proven — its ``port`` is what the runner's refusal message prints, and its
    ``token`` is the credential :func:`_send` puts on the wire. Nothing *here* reads that token:
    this function's contract is that it hands back a proven record, and the one place a credential
    is read is the one place it is sent.

    **Never raises.** ``read_discovery`` and :func:`probe_health` both make that promise already,
    and this function adds no third failure mode of its own.

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
) -> httpx.Response | None:
    """Make one authenticated request to a companion whose identity is already proven.

    **Never raises**, on the same terms and with the same net as :func:`probe_health`: the whole
    body — client construction and teardown included — sits inside one
    ``except (TimeoutError, httpx.HTTPError, ValueError)``, and deliberately not ``except
    Exception``. A ``MemoryError`` mid-send is a broken machine, not a backend that did not answer.

    ``trust_env=False`` is load-bearing here for *both* of its reasons, where the probe only had
    one. A configured proxy would misroute the loopback dial exactly as it would a probe — and this
    request carries a credential, so ``.netrc`` quietly attaching an ``Authorization`` header of its
    own would be a second one on a request that already has the right one.

    Generic over method and path rather than hard-wired to the push, so that a sibling verb against
    the same gate — same header, timeouts and net — can reuse this implementation instead of
    duplicating it (see ``deferred-work.md`` for the concrete case). It stays private — the public
    surface of this module is :func:`push_event`, and a story that needs another verb adds another
    named function rather than exporting this one (Q1, Brad 2026-08-09).

    **The token is read here and nowhere else**, is placed in exactly one header, and appears in no
    log line at any level. There is no error branch that echoes the request.

    Args:
        record: The discovery record whose identity has just been proven. Its ``token`` is the
            credential; passing an unproven record would send it to whatever holds that port.
        method: The HTTP method, e.g. ``"POST"``.
        path: The path to request, e.g. :data:`EVENTS_PATH`.
        body: The already-serialised JSON body.
        timeout: Override the per-request deadline; ``None`` uses :data:`PROBE_TIMEOUT`, whose
            connect/read split applies unchanged — a live companion answers this route as promptly
            as it answers ``/health``.

    Returns:
        The response, whatever its status, or ``None`` if the exchange never completed.
    """
    url = f"{base_url(record.port)}{path}"
    try:
        async with httpx.AsyncClient(
            timeout=PROBE_TIMEOUT if timeout is None else timeout, trust_env=False
        ) as http:
            return await http.request(
                method,
                url,
                content=body,
                headers={
                    "Authorization": f"Bearer {record.token}",
                    "content-type": "application/json",
                },
            )
    except (TimeoutError, httpx.HTTPError, ValueError) as exc:
        logger.debug("The %s to %s did not complete (%s)", method, url, type(exc).__name__)
        return None


def _outcome_for(response: httpx.Response) -> PushOutcome | None:
    """Turn one answered request into its token — or into the decision to retry.

    **Statuses only, never the** ``reason`` **string.** The error body is written for humans and
    logs; switching on its wording would break on any rewording and would buy nothing, because the
    statuses already separate every case this client distinguishes (``app/errors.py``'s
    ``STATUS_BY_REASON`` is the pairing, and it is one-to-one on the codes that reach here).

    ``400`` and ``413`` fold into one token deliberately (Q7, Brad 2026-08-08). A violated field cap
    is a pydantic error and answers ``400``; the 64 KB envelope cap is enforced pre-parse and
    answers ``413``. Both mean *the payload was refused, in full, and nothing was rendered* — the
    property the epic AC actually protects — and a caller can do the same one thing about either.

    A ``200`` is only a delivery if its body is a receipt. The parse is
    :class:`~src.companion.contracts.EventIngestReceipt` rather than a hand-rolled
    ``body["clients"]`` read, which is what makes ``{"clients": -1}`` a ``backend_error`` instead of
    quietly reading as *nobody was listening*.

    Args:
        response: The answer to a request that completed.

    Returns:
        The outcome, or ``None`` for a ``403`` — the one status this function does not resolve,
        because whether a refused credential is a retry or a failure is the caller's budget to
        spend, not a property of the response.
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
    """Run one whole prove-then-send cycle: discovery, ``/health``, identity, then the POST.

    Identity is re-proven on **every** attempt, including the retry (Q2, Brad 2026-08-09). AD-4's
    rule is "verify before you send the token", and it has no once-per-call exemption: the retry
    sends a *different* token, read from a file that has demonstrably just changed, to a port the
    operating system was free to reassign in the meantime.

    Args:
        body: The serialised envelope.
        timeout: Forwarded to both legs.

    Returns:
        The outcome, or ``None`` if the backend refused the credential and a retry could help.
    """
    record = await live_instance(timeout=timeout)
    if record is None:
        return PushOutcome(outcome="app_not_running")
    response = await _send(record, method="POST", path=EVENTS_PATH, body=body, timeout=timeout)
    if response is None:
        return PushOutcome(outcome="backend_error")
    return _outcome_for(response)


async def push_event(event: AgentEvent, *, timeout: httpx.Timeout | None = None) -> PushOutcome:
    """Push one event to the companion's glass, and report the single thing that happened (AD-8).

    The one public way anything outside this module reaches ``POST /agent/events``. Every companion
    MCP tool funnels through it so that they all fail the same way, and **none of them can break an
    agent turn** over anything the companion itself does: whatever the discovery file, the network,
    or the backend answer with — closed, crashed, restarting, wedged, malformed — is one of the five
    tokens above, never an exception. That is FR-12's actual requirement. The net is the same one
    :func:`probe_health` and :func:`_send` draw: a ``MemoryError`` (or similar) mid-call is a broken
    machine, not a companion that did not answer, and is deliberately let through rather than folded
    into ``backend_error``.

    **The sequence.** Read discovery → probe ``/health`` → match the echoed ``instance_id`` → only
    then send the token. A failure anywhere before that match is ``app_not_running`` and **no
    credential leaves the process** (AD-4).

    **The retry, and why it is exactly one** (FR-12). The backend mints a fresh token every start,
    so a companion restarted mid-session refuses the token a tool is holding with a ``403``. That is
    the single case where trying again is not a duplicate but a correction, and the whole cycle is
    re-run — file, probe, identity — before the newly read token is sent. A second ``403`` is
    ``backend_error``: the credential is not merely stale, and a client that kept retrying would
    re-send the payload indefinitely against a backend that keeps saying no. **At most two POSTs
    ever leave this function.** If the re-read finds nothing live, the honest answer is
    ``app_not_running`` — nothing broke; the app went away between the refusal and the retry.

    The retry is spent on ``403`` **alone**. A ``500`` or a dropped connection buys no second
    attempt: neither is a stale credential, and re-sending a payload the backend may already have
    accepted-then-failed on is how one push becomes two renders.

    Args:
        event: A concrete envelope instance — one of the six members of
            :data:`~src.companion.contracts.AgentEvent`. Taken already-built and **never
            re-validated**: the union is an ``Annotated`` discriminated union with no
            ``.model_validate``, and the caller has by construction handed over something valid.
        timeout: Override the per-request deadline for both legs. Exists so a test can drive the
            dead-port and never-answers cases in milliseconds; production callers pass nothing and
            get :data:`PROBE_TIMEOUT`. It does **not** override :data:`_PUSH_TOTAL_SECONDS`, which
            production callers must not be able to opt out of.

    Returns:
        Exactly one :class:`PushOutcome`.

    Example:
        >>> outcome = await push_event(event)  # doctest: +SKIP
        >>> outcome.outcome, outcome.clients  # doctest: +SKIP
        ('displayed', 2)
    """
    body = event.model_dump_json()
    try:
        async with asyncio.timeout(_PUSH_TOTAL_SECONDS):
            first = await _attempt(body, timeout=timeout)
            if first is not None:
                return first
            logger.debug("The companion refused the credential; re-reading discovery and retrying")
            second = await _attempt(body, timeout=timeout)
            if second is not None:
                return second
            logger.debug("The freshly read credential was refused too; not retrying again")
            return PushOutcome(outcome="backend_error")
    except TimeoutError:
        logger.debug("The push did not complete within %.1fs", _PUSH_TOTAL_SECONDS)
        return PushOutcome(outcome="backend_error")

"""Talking *to* the companion backend from outside it — the identity half (AD-3, AD-4).

This is one of the two halves of the leaf client named in the spine's Structural Seed
(``client.py # LEAF — /health + /agent/events, notifier``). It lands the **``/health`` half**:
finding out whether a companion is genuinely live on the discovered port, and refusing to believe
anything else. Story c6-1 adds the other half into this same module — the ``POST /agent/events``
push, its retry-once and its closed outcome vocabulary — and reuses the probe below before every
send rather than duplicating it.

**Why the probe exists at all (AD-4).** The discovery file says *where* the companion is, but a
file outlives the process that wrote it: AD-15 accepts that a crash leaves a stale entry behind,
and the operating system is free to hand that port to something else entirely. "Something answered"
is therefore not evidence — a local dev server that returns ``200`` to every path would pass that
test. Only an ``instance_id`` echoed back that **matches the recorded one** proves the process
answering is the process the file describes. That match is what makes it safe for c6-1 to send the
agent token, and a mismatch is *app not running*, never *ambiguous* and never a reason to send a
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

import httpx

from src.companion.contracts import HealthResponse
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


def base_url(port: int) -> str:
    """Assemble the companion's base URL — the one place in the codebase that does.

    ``127.0.0.1`` literally rather than ``localhost``: the companion's socket is IPv4-only and
    ``localhost`` resolves to ``::1`` first on Windows and modern Linux, so the name would dial an
    address nothing is listening on. c6-1 posts to this URL and the runner prints it.

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

    Rejections log at DEBUG, not WARNING: for c6-1's client the *expected* case is that nothing is
    there, and a warning on every push would be noise in the user's terminal.

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
    ``token`` is the credential c6-1 sends next. Nothing here reads that token.

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

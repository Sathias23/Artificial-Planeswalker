"""The companion's process runner: it owns the socket, the port and the launch line (AD-15).

Three things about this module are deliberate and load-bearing.

**The bind happens here, not in uvicorn.** ``uvicorn.Server.startup()`` awaits the lifespan
*before* it creates any listener, so on the ``host``/``port`` path the bound port is unknowable
until after startup has already run — and c1-7 homes the discovery-file write in that lifespan
(AD-4, AD-10). Pre-binding and handing uvicorn ``sockets=[sock]`` inverts the order, and is the only
arrangement in which both decisions hold. A consequence worth knowing: uvicorn suppresses its own
*"Uvicorn running on …"* banner when it is handed sockets, which is why the line printed here is the
only launch line the user sees.

**The host is a constant, never a parameter.** NFR-01 makes ``127.0.0.1`` the security envelope
rather than a default; a configurable bind address would reduce it to a suggestion.

**Nothing here runs at import time.** The socket is this feature's first effect outside the process
and it lives behind :func:`run`, so ``build_app()`` stays inert (AD-10) and the rest of the backend
remains testable without a port.

**The single-instance check runs before the bind, not after it.** :func:`run` asks
:func:`src.companion.client.live_instance` whether a verified companion is already answering
*before* it resolves a port, binds a socket or builds an app (AD-4). The ordering is behaviour
rather than tidiness: a launch that is about to refuse must not momentarily hold a port another
process might want, must not construct an application it will never serve, and — because it returns
before the lifespan — cannot overwrite the rendezvous of the instance it just found.

**The instance lock is held for the whole serve, and it is taken *after* the probe.** The probe
alone could not close the startup window — two launches that both probe before either publishes both
see an empty rendezvous and both proceed, which reproduced here with two live companions spawned
6 ms apart. :mod:`src.companion.app.singleton` supplies the atomic *whether*; the probe keeps
supplying the informative *who and where*, since only it can name a URL the user can open. Hence the
order: probe, then lock. The descriptor is released in :func:`run`'s outermost ``finally``, after
the socket close, so the lock outlives every other resource this process claims.
"""

import asyncio
import io
import logging
import os
import socket
import sys

import uvicorn
from fastapi import FastAPI

from src.companion import client, discovery
from src.companion.app import singleton
from src.companion.app.main import build_app

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
"""The only address the companion ever binds — loopback, IPv4, by NFR-01."""

DEFAULT_PORT = 8765
"""The preferred port (FR-01). This is the single place in ``src/`` that names the number."""

PORT_ENV_VAR = "COMPANION_PORT"
"""Environment override for the preferred port.

Renamed from ``PLANESWALKER_COMPANION_PORT`` by Brad's ruling at the C1 retro (2026-07-26), before
any documentation shipped. The vendor prefix went; the ``COMPANION`` disambiguator deliberately
stayed, because ``MCP_TRANSPORT`` already contemplates ``sse``/``streamable-http`` and an MCP
server running over HTTP would need a port of its own — a bare ``PLANESWALKER_PORT`` could not tell
the two processes apart.
"""

_MIN_PORT = 0
_MAX_PORT = 65535


def _usable_port(value: int) -> bool:
    """Report whether *value* is a port number the kernel would accept.

    Args:
        value: A candidate port.

    Returns:
        ``True`` when *value* lies in ``0..65535``; ``0`` is legal and means "assign me one".
    """
    return _MIN_PORT <= value <= _MAX_PORT


def resolve_preferred_port(explicit: int | None = None) -> int:
    """Decide which port to *try* first: argument, then environment, then the default.

    A value from either source that is not an integer in ``0..65535`` is ignored with a logged
    warning and the default is used — a typo'd environment variable must never stop the launch, and
    the entry point feeds a user-supplied ``--port`` through *explicit*, so both validate
    identically. (A ``--port`` that is not an integer at all never arrives here: that is a usage
    error the dispatcher rejects, because unlike a stale environment variable it was typed in this
    invocation.) ``0`` is a legal configured value meaning "go straight to an ephemeral port".

    Args:
        explicit: A port supplied in code or on the command line, if any.

    Returns:
        The port to attempt first. Note this is the *preferred* port, not the bound one —
        :func:`bind_localhost_socket` may still fall back.
    """
    if explicit is not None:
        if _usable_port(explicit):
            return explicit
        logger.warning(
            "Ignoring configured port %r: not in %d..%d; using %d",
            explicit,
            _MIN_PORT,
            _MAX_PORT,
            DEFAULT_PORT,
        )
        return DEFAULT_PORT

    raw = os.getenv(PORT_ENV_VAR)
    if raw is None:
        return DEFAULT_PORT

    try:
        candidate = int(raw)
    except ValueError:
        candidate = -1
    if _usable_port(candidate):
        return candidate

    logger.warning(
        "Ignoring %s=%r: not an integer in %d..%d; using %d",
        PORT_ENV_VAR,
        raw,
        _MIN_PORT,
        _MAX_PORT,
        DEFAULT_PORT,
    )
    return DEFAULT_PORT


def _new_socket() -> socket.socket:
    """Create a loopback-bound-to-be TCP socket with the platform's own reuse policy applied.

    ``SO_REUSEADDR`` is set on POSIX and **never** on Windows, mirroring asyncio's own rule for
    ``create_server`` (``reuse_address`` defaults to ``os.name == "posix"``). The two platforms give
    the option opposite meanings: on POSIX it lets a restart reclaim a port still held by lingering
    ``TIME_WAIT`` connections, while on Windows it would permit binding a port another process is
    *actively listening on* — silently defeating the conflict detection this module depends on.

    Windows gets ``SO_EXCLUSIVEADDRUSE`` instead, and the two are complements rather than
    contradictions: omitting ``SO_REUSEADDR`` stops *us* from binding over someone else, and
    ``SO_EXCLUSIVEADDRUSE`` stops *someone else* — any other local process setting ``SO_REUSEADDR``
    — from binding over a port we already hold. Without it the single-instance premise c1-8 is
    built on is only half enforced. Nothing else changes: a port that is now harder to get simply
    takes the ephemeral fallback :func:`bind_localhost_socket` already provides.

    The option exists only on Windows, so it is referenced inside a platform branch. The branch is
    written against ``sys.platform`` rather than ``os.name`` because that is the form mypy
    understands: on a Linux checker the body is unreachable and never type-checked, which is what
    keeps CI green against a constant its typeshed does not have.

    Returns:
        An unbound ``AF_INET``/``SOCK_STREAM`` socket.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == "posix":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    elif sys.platform == "win32":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    return sock


def bind_localhost_socket(preferred: int) -> socket.socket:
    """Bind loopback on *preferred*, falling back to a kernel-assigned port on any failure.

    The fallback triggers on **any** ``OSError``, not only ``EADDRINUSE``: Windows reserves dynamic
    port ranges (WinNAT / Hyper-V / WSL2) and refuses a bind inside them with ``WSAEACCES``, a
    different errno entirely. Catching the specific case would leave the machine most likely to hit
    it — Brad's — unable to start.

    The socket is bound but deliberately **not** listened on; ``loop.create_server(sock=…)`` calls
    ``listen()`` itself, and binding is all that is needed to reserve the port and learn its number.

    Invariant :func:`run` relies on: when the preferred bind succeeds, the returned socket holds
    **exactly** *preferred* — so a caller may infer "the fallback was taken" from the bound port
    differing from the preferred one.

    Args:
        preferred: The port to attempt first. ``0`` *is already* the ephemeral request, so it is
            bound exactly once — a failure propagates directly, with no pointless identical retry.

    Returns:
        A bound socket. Read the port it actually got from ``getsockname()[1]``.

    Raises:
        OSError: Only if the *ephemeral* bind fails — a conflict on *preferred* never escapes.
    """
    sock = _new_socket()
    try:
        sock.bind((HOST, preferred))
    except OSError:
        sock.close()
        if preferred == 0:
            raise
    else:
        return sock

    # WARNING, not INFO, and it stays that way now that c1-9's entry point configures the root
    # logger at INFO on stderr: a bind fallback is a genuine warning on its own merits — the user
    # asked for one port and got another. Note the fallback is now announced twice, as a record
    # here and as the stdout line run() prints; the duplication is accepted, not a defect.
    logger.warning("Port %d unavailable; falling back to an ephemeral port", preferred)
    fallback = _new_socket()
    try:
        fallback.bind((HOST, 0))
    except OSError:
        fallback.close()
        raise
    return fallback


def _serve(app: FastAPI, sock: socket.socket, port: int) -> None:
    """Serve *app* on the already-bound *sock*.

    ``sockets=[sock]`` rather than ``host``/``port`` is the whole design (see the module docstring):
    it is the only form in which the lifespan starts with the port already reserved. ``workers``
    is left at its default of 1 — the companion's active deck, connections and tickets live in
    this process's memory (AD-5), so a second worker would silently halve them, and uvicorn's
    multi-worker path re-shares the socket on Windows. ``lifespan="on"`` is explicit so a lifespan
    failure is loud rather than quietly skipped; c1-7's discovery-file write must never be bypassed.

    Isolated behind its own function so tests can replace the serving step without a real server.

    Args:
        app: The application to serve.
        sock: The bound socket uvicorn should listen on.
        port: The port *sock* holds, recorded in the config for uvicorn's own logging.
    """
    config = uvicorn.Config(app, host=HOST, port=port, lifespan="on")
    uvicorn.Server(config).run(sockets=[sock])


def _note_reclaimed_entry() -> None:
    """Log, at INFO, that the discovery file's entry is defunct and will be published over.

    "Defunct" covers both of run()'s proceed cases: a dead port with nothing answering (the
    post-crash state AD-15 describes) and a port answering as some *other* process (a recycled
    port, a foreign identity) — either way the record no longer describes a live companion. The
    reclaim itself happens later, at the lifespan's atomic publish, which is why the message says
    *will* reclaim: a launch that dies at the bind never touches the file, and the log must not
    claim otherwise.

    Called only once :func:`run` already knows no companion is live, and *only* to decide whether
    there is anything to say — which is why it re-reads the file rather than threading a value out
    of :func:`~src.companion.client.live_instance`. The cost lands where it belongs: a clean
    machine and a live instance each pay a single read (the probe's), and only the defunct-entry
    path pays a second one. Nothing here influences what :func:`run` does next; a race that changed
    the file between the two reads would change this log line and nothing else.

    **INFO, not WARNING.** AD-15 describes a stale file after a crash as the *expected* state, and
    warning about the ordinary case trains a user to ignore warnings. Since c1-9 the companion's
    entry point configures the root logger at INFO on stderr, so this record now reaches the user
    in a real run — which is the payoff, and why the level needs no revisiting: it is ordinary news
    rather than something to act on, unlike c1-3's fallback warning and c1-7's discovery warnings.
    """
    stale = discovery.read_discovery()
    if stale is None:
        return
    logger.info(
        "Discovery file names port %d but no matching companion is answering; "
        "this launch will reclaim it when it publishes",
        stale.port,
    )


def run(port: int | None = None) -> None:
    """Serve the companion — unless one is already running or starting up.

    Three outcomes, and all three are successes that exit ``0``. When
    :func:`~src.companion.client.live_instance` finds a companion whose echoed ``instance_id``
    matches the discovery file, this launch is redundant: the user's intent — *have the companion
    running* — is already satisfied, so the URL of the instance that **is** running is printed and
    the function returns. When the probe finds nothing but
    :func:`~src.companion.app.singleton.acquire_instance_lock` is refused, another launch is inside
    its own startup window: this one says so and returns without naming a URL, because no URL can
    be named honestly yet (c1-9 Decide-once #3). Otherwise the launch proceeds, holding the lock for
    as long as it serves, and leaves any old discovery file in place for c1-7's atomic publish to
    overwrite. None of the three raises or calls ``sys.exit``, so the process exits ``0``
    (Decide-once #3); AD-15 rules out the daemon, supervisor or auto-restart for which a non-zero
    status would mean anything.

    The probe happens **first**, above the lock, the port resolution and the bind. See the module
    docstring: a refusing launch must claim nothing, and only the probe can name *where* the other
    instance is. The lock is taken second and released last, in the outermost ``finally``.

    The announcement is ``print``ed, not logged, and that is deliberate: ``logging`` writes to
    stderr, while AD-15 puts this line on stdout. That is now the whole reason — c1-9's entry point
    configures the root logger, so an ``INFO`` record would no longer be dropped; it would simply
    land on the wrong stream, mixed in with uvicorn's own records, where the one thing the user
    *must* see would be harder to find. The host is printed as the literal ``127.0.0.1`` rather
    than ``localhost`` because the socket is IPv4-only and ``localhost`` resolves to ``::1`` first
    on Windows and modern Linux.

    Args:
        port: A port to prefer over the environment variable and the default. Invalid values are
            ignored with a warning rather than raising — see :func:`resolve_preferred_port`. It is
            a preference only: an explicit port does **not** bypass the single-instance check,
            because the discovery file can name just one instance whatever port it holds.
    """
    # The launch lines contain an em dash (AC 6's exact text). A redirected stdout under a
    # non-UTF-8 locale (LANG=C service capture, cp437 console) would otherwise raise
    # UnicodeEncodeError on the one line that must never fail — this process owns its stdout
    # (AD-15), so degrade unencodable characters instead of crashing. The refusal line below
    # carries an em dash too, which is why this stays the very first thing run() does.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    # asyncio.run here, before uvicorn exists: the probe is async because the leaf client is, and
    # one shared implementation beats a sync mirror of a network call (AD-8, Decide-once #2).
    # uvicorn creates its own loop inside _serve later, and two consecutive asyncio.run calls on
    # one thread are legal — but this must never move below _serve or inside a coroutine, because
    # calling asyncio.run from within a running loop raises.
    live = asyncio.run(client.live_instance())
    if live is not None:
        print(
            f"[planeswalker] companion is already running at {client.base_url(live.port)} — "
            "open that URL, or stop the other instance before starting a new one",
            flush=True,
        )
        return
    # The atomic "am I first?", and the one thing the probe cannot answer during another launch's
    # startup window. Deliberately no second probe here: reaching this branch means the probe has
    # already said nothing findable is running, so there is no honest URL to print, and re-probing
    # would spend up to five seconds on the one path whose whole job is to get out of the way fast.
    lock = singleton.acquire_instance_lock()
    if lock is None:
        print(
            "[planeswalker] another companion is already starting up — "
            "wait for it to print its URL, or stop it before starting a new one",
            flush=True,
        )
        return
    try:
        _note_reclaimed_entry()
        preferred = resolve_preferred_port(port)
        sock = bind_localhost_socket(preferred)
        try:
            actual: int = sock.getsockname()[1]
            app = build_app()
            app.state.bound_port = actual
            # `preferred == 0` asked for an ephemeral port, so getting one is success, not a
            # conflict.
            if preferred != 0 and actual != preferred:
                print(
                    f"[planeswalker] port {preferred} is unavailable — "
                    "falling back to an ephemeral port",
                    flush=True,
                )
            print(
                f"[planeswalker] companion running at http://{HOST}:{actual} — "
                "open this URL in your browser (Ctrl-C to stop)",
                flush=True,
            )
            _serve(app, sock, actual)
        finally:
            # Belt-and-braces: uvicorn's shutdown() already closes the sockets it was handed, and a
            # double close is harmless. This covers every path that never reached uvicorn at all.
            sock.close()
    finally:
        # Outside the socket's finally, so the lock is the last thing this process gives up. On any
        # death that never reaches here — Ctrl-C during the bind, a kill, a crash — the kernel
        # releases it, which is why there is no stale-lock state to recover from (AD-15).
        singleton.release_instance_lock(lock)

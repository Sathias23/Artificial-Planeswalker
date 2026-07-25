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
"""

import io
import logging
import os
import socket
import sys

import uvicorn
from fastapi import FastAPI

from src.companion.app.main import build_app

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
"""The only address the companion ever binds — loopback, IPv4, by NFR-01."""

DEFAULT_PORT = 8765
"""The preferred port (FR-01). This is the single place in ``src/`` that names the number."""

PORT_ENV_VAR = "PLANESWALKER_COMPANION_PORT"
"""Environment override for the preferred port.

Named for symmetry with ``PLANESWALKER_DATA_DIR``.
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
    c1-9 feeds a user-supplied ``--port`` through *explicit*, so both must validate identically.
    ``0`` is a legal configured value meaning "go straight to an ephemeral port".

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

    # WARNING, not INFO: no root handler is configured yet (see run()), and logging.lastResort
    # surfaces WARNING+ to stderr — an INFO record here would be dropped in every real run.
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


def run(port: int | None = None) -> None:
    """Bind the companion's port, announce the URL and serve until interrupted.

    The announcement is ``print``ed, not logged, and that is deliberate. ``logging`` writes to
    stderr, while AD-15 puts this line on stdout; and no story has yet configured a root handler, so
    an ``INFO`` record from this module would propagate to a handler-less root and be dropped
    entirely. The URL is the one thing the user *must* see, so it cannot depend on logging
    configuration that does not exist yet. The host is printed as the literal ``127.0.0.1`` rather
    than ``localhost`` because the socket is IPv4-only and ``localhost`` resolves to ``::1`` first
    on Windows and modern Linux.

    Args:
        port: A port to prefer over the environment variable and the default. Invalid values are
            ignored with a warning rather than raising — see :func:`resolve_preferred_port`.
    """
    # The launch lines contain an em dash (AC 6's exact text). A redirected stdout under a
    # non-UTF-8 locale (LANG=C service capture, cp437 console) would otherwise raise
    # UnicodeEncodeError on the one line that must never fail — this process owns its stdout
    # (AD-15), so degrade unencodable characters instead of crashing.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    preferred = resolve_preferred_port(port)
    sock = bind_localhost_socket(preferred)
    try:
        actual: int = sock.getsockname()[1]
        app = build_app()
        app.state.bound_port = actual
        # `preferred == 0` asked for an ephemeral port, so getting one is success, not a conflict.
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

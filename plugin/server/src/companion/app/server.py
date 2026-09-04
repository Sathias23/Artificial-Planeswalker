"""The companion's process runner: it owns the socket, the port and the launch line (AD-15).

Invariants this module protects:

- The bind happens here, not in uvicorn. ``uvicorn.Server.startup()`` awaits the lifespan before
  it creates any listener, and the discovery-file write lives in that lifespan (AD-4, AD-10), so
  the port must be reserved first and handed over as ``sockets=[sock]``. uvicorn suppresses its
  own banner when given sockets, which is why the line printed here is the only launch line.
- The host is a constant, never a parameter: NFR-01 makes ``127.0.0.1`` the security envelope.
- Nothing here runs at import time; the socket lives behind :func:`run`, so ``build_app()`` stays
  inert (AD-10) and the backend is testable without a port.
- The single-instance probe runs before the bind. A launch that is about to refuse must not hold a
  port another process might want, must not build an app it will never serve, and, because it
  returns before the lifespan, cannot overwrite the rendezvous of the instance it found (AD-4).
- The instance lock is taken after the probe and held for the whole serve. The probe alone cannot
  close the startup window (two launches that probe before either publishes both proceed);
  :mod:`src.companion.app.singleton` supplies the atomic *whether*, the probe the *who and where*.
  The lock is released in :func:`run`'s outermost ``finally``, after the socket close.
"""

import asyncio
import io
import logging
import os
import socket
import sys
import webbrowser

import uvicorn
from fastapi import FastAPI

from src.companion import client, discovery
from src.companion.app import singleton
from src.companion.app.main import build_app

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
"""The only address the companion ever binds: loopback, IPv4, by NFR-01."""

DEFAULT_PORT = 8765
"""The preferred port (FR-01). This is the single place in ``src/`` that names the number."""

PORT_ENV_VAR = "COMPANION_PORT"
"""Environment override for the preferred port.

The ``COMPANION`` disambiguator is deliberate: ``MCP_TRANSPORT`` contemplates HTTP transports, and
an MCP server over HTTP would need a port of its own that a bare ``PLANESWALKER_PORT`` could not
tell apart.
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
    """Decide which port to try first: argument, then environment, then the default.

    An out-of-range value from either source is ignored with a logged warning and the default is
    used: a typo'd environment variable must never stop the launch, and ``--port`` arrives through
    *explicit* so both validate identically. ``0`` means "go straight to an ephemeral port".

    Args:
        explicit: A port supplied in code or on the command line, if any.

    Returns:
        The port to attempt first; :func:`bind_localhost_socket` may still fall back.
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
    """Create an unbound TCP socket with the platform's own reuse policy applied.

    ``SO_REUSEADDR`` is set on POSIX and never on Windows, mirroring asyncio's ``create_server``
    default: on POSIX it lets a restart reclaim a ``TIME_WAIT`` port, on Windows it would permit
    binding a port another process is actively listening on. Windows gets ``SO_EXCLUSIVEADDRUSE``
    instead, so no other process can bind over a port we hold; without it the single-instance
    premise is only half enforced. The branch tests ``sys.platform`` because mypy treats the
    Windows-only constant as unreachable on a Linux checker.

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

    The fallback triggers on any ``OSError``, not only ``EADDRINUSE``: Windows refuses binds inside
    its reserved dynamic ranges with ``WSAEACCES``. The socket is bound but not listened on;
    ``loop.create_server(sock=...)`` calls ``listen()`` itself. When the preferred bind succeeds the
    returned socket holds exactly *preferred*, so :func:`run` infers a fallback from the bound port
    differing.

    Args:
        preferred: The port to attempt first. ``0`` is already the ephemeral request, so it is
            bound once and a failure propagates directly.

    Returns:
        A bound socket; read the port from ``getsockname()[1]``.

    Raises:
        OSError: Only if the ephemeral bind fails.
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

    # WARNING: the user asked for one port and got another. run() also prints the fallback to
    # stdout; the duplication is intended.
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

    ``sockets=[sock]`` is the only form in which the lifespan starts with the port already reserved.
    ``workers`` stays at 1 because the active deck, connections and tickets live in this process's
    memory (AD-5). ``lifespan="on"`` makes a lifespan failure loud; the discovery-file write must
    never be skipped. Kept as its own function so tests can replace the serving step.

    Args:
        app: The application to serve.
        sock: The bound socket uvicorn should listen on.
        port: The port *sock* holds, recorded in the config for uvicorn's own logging.
    """
    config = uvicorn.Config(app, host=HOST, port=port, lifespan="on")
    uvicorn.Server(config).run(sockets=[sock])


def _note_reclaimed_entry() -> None:
    """Log, at INFO, that the discovery file's entry is defunct and will be published over.

    Covers both proceed cases: a dead port and a port answering as some other process. The reclaim
    happens later, at the lifespan's atomic publish, so the message says *will*. Called only once
    :func:`run` knows no companion is live, and only to decide whether there is anything to say, so
    the second read is paid by the defunct-entry path alone and influences nothing. INFO rather than
    WARNING because a stale file after a crash is the expected state (AD-15).
    """
    stale = discovery.read_discovery()
    if stale is None:
        return
    logger.info(
        "Discovery file names port %d but no matching companion is answering; "
        "this launch will reclaim it when it publishes",
        stale.port,
    )


def _open_browser(url: str) -> None:
    """Best-effort: open the user's default browser on *url*; a failure decides nothing.

    Runs in the companion's process so the MCP server still spawns nothing (AD-15). A host with no
    usable browser (``open`` may raise, not just return ``False``) logs a warning; the URL line is
    already on stdout and the exit status is untouched.

    Args:
        url: The companion's base URL, the one the launch line just printed.
    """
    try:
        opened = webbrowser.open(url)
    except (webbrowser.Error, OSError) as exc:
        logger.warning("Could not open a browser on %s (%s); open it yourself", url, exc)
        return
    if not opened:
        logger.warning("No browser could be opened on %s; open it yourself", url)


def run(port: int | None = None, *, open_browser: bool = False) -> None:
    """Serve the companion unless one is already running or starting up.

    Three outcomes, all exiting ``0`` (AD-15 rules out any supervisor a non-zero status would
    serve). A live instance found by :func:`~src.companion.client.live_instance` means the user's
    intent is already satisfied, so its URL is printed. A refused
    :func:`~src.companion.app.singleton.acquire_instance_lock` means another launch is inside its
    startup window; this one says so without naming a URL, because none can be named honestly yet.
    Otherwise the launch proceeds, holding the lock for as long as it serves, and leaves any old
    discovery file for the lifespan's atomic publish to overwrite.

    The announcement is ``print``ed, not logged: ``logging`` writes to stderr and AD-15 puts this
    line on stdout. The host is printed as ``127.0.0.1`` rather than ``localhost`` because the
    socket is IPv4-only and ``localhost`` resolves to ``::1`` first on Windows and modern Linux.

    Args:
        port: A port to prefer over the environment variable and the default; invalid values warn
            rather than raise. An explicit port does not bypass the single-instance check, because
            the discovery file can name just one instance.
        open_browser: Open the default browser on the companion's URL once known (``--open``). On
            the already-running branch it opens the live instance's URL, so the launch command is
            safe to re-run whenever no tab is open.
    """
    # The launch and refusal lines contain an em dash; a redirected stdout under a non-UTF-8 locale
    # would raise UnicodeEncodeError on the one line that must never fail, so degrade instead.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    # The probe is async because the leaf client is (AD-8). uvicorn creates its own loop inside
    # _serve later; this call must never move below _serve or inside a coroutine.
    live = asyncio.run(client.live_instance())
    # asyncio.run closed that loop; the leaf's shared httpx client is cached against it.
    client.reset_shared_client()
    if live is not None:
        live_url = client.base_url(live.port)
        print(
            f"[planeswalker] companion is already running at {live_url} — "
            "open that URL, or stop the other instance before starting a new one",
            flush=True,
        )
        if open_browser:
            _open_browser(live_url)
        return
    # The atomic "am I first?". No second probe: it already said nothing findable is running, so
    # there is no honest URL to print, and re-probing would spend seconds on the get-out-fast path.
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
            # `preferred == 0` asked for an ephemeral port, so getting one is not a conflict.
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
            # A bound-but-not-listening socket refuses connections, and a fast browser can dial
            # before uvicorn's own listen() runs; listening here queues the connect in the backlog.
            if open_browser:
                sock.listen()
                _open_browser(f"http://{HOST}:{actual}")
            _serve(app, sock, actual)
        finally:
            # uvicorn closes handed sockets itself; this covers every path that never reached it.
            sock.close()
    finally:
        # Outside the socket's finally, so the lock is the last thing this process gives up. On a
        # death that never reaches here the kernel releases it, so there is no stale-lock state.
        singleton.release_instance_lock(lock)

"""Entry point for Artificial-Planeswalker: a subcommand dispatcher over two processes (AD-14).

The transport is selected here — and only here — so HTTP/SSE can swap in later
without changing any tool definition (AC2 / D7). Defaults to ``stdio``; override
via the ``MCP_TRANSPORT`` environment variable.

Run with:
    uv run python -m src.mcp_server              # the MCP server, exactly as always
    uv run artificial-planeswalker              # the same thing, via the console script
    uv run artificial-planeswalker companion    # the companion backend, in the foreground

**The bare invocation is unchanged, and that is the point.** ``artificial-planeswalker`` grew a
subcommand rather than moving, because every installed MCP client configuration points at this
module. Both ``.mcp.json`` files invoke ``python -m src.mcp_server`` directly and therefore never
pass through the console script at all, which is what makes the addition safe;
``tests/integration/mcp_server/test_entry_point.py`` pins both files, so a future story cannot
quietly rewrite them into a subcommand form.

**stdout belongs to whoever owns the process.** On the MCP path stdout carries the JSON-RPC stream
and nothing else — every diagnostic here goes to stderr, and nothing on that path configures logging
or imports anything under ``src/companion/``. The companion process inverts this (AD-15): it owns
its terminal, so it prints its launch URL to stdout and — from this story onward — configures the
root logger so records from ``src.*`` finally reach the user on stderr.

**The companion import is function-local, by AD-3.** ``from src.companion.app.server import run``
lives inside :func:`_run_companion` and nowhere else, so a stdio MCP session never imports FastAPI
or uvicorn. This module is the single exemption in
``tests/unit/companion/test_import_boundary.py``'s
``_APP_IMPORT_EXEMPT``, and that guard counts an ``if TYPE_CHECKING:`` import as module-level in
every role — so no annotation in this file may name a companion-app type either.
"""

import logging
import os
import sqlite3
import sys
from collections.abc import Sequence
from typing import Literal, TextIO, cast

from src.mcp_server.server import build_server

_Transport = Literal["stdio", "sse", "streamable-http"]

_USAGE = """\
usage: artificial-planeswalker [-h] [companion [--port PORT] [--open]]

Run the Artificial-Planeswalker MCP server, or the companion backend.

subcommands:
  (none)         run the MCP server over stdio, for an MCP client to drive
  companion      run the companion backend in the foreground until interrupted

options:
  --port PORT    port the companion should prefer, overriding COMPANION_PORT
                 and the default port; a value outside 0..65535 is ignored
                 with a warning
  --open         open the default browser on the companion's URL once it is
                 up (or on the running instance's URL, if one is already up)
  -h, --help     show this message and exit
"""
"""The usage text, deliberately naming **no port number**.

``tests/unit/companion/test_server.py::TestNothingElseHardcodesThePort`` AST-scans ``src/`` and
``scripts/`` for the literal and allows exactly one occurrence — ``server.DEFAULT_PORT``. This file
is inside that scan, so the default is described in words.
"""


def _log_startup_diagnostics() -> None:
    """Print resolved data-path diagnostics to STDERR.

    NEVER stdout — the stdio transport owns stdout for the JSON-RPC stream; writing there
    corrupts the protocol. stderr is surfaced in the MCP host's server log. This makes
    "no decks / database error" reports self-diagnosing: it shows which database the server
    actually resolved (important because a packaged/sandboxed host can virtualize
    ``%LOCALAPPDATA%``) and whether it is populated.
    """
    try:
        from src import paths

        db = paths.database_path()
        exists = db.exists()
        size = db.stat().st_size if exists else 0
        print(f"[planeswalker] data_dir={paths.data_dir()}", file=sys.stderr, flush=True)
        print(
            f"[planeswalker] database={db} exists={exists} size={size}", file=sys.stderr, flush=True
        )
        for var in ("PLANESWALKER_DATA_DIR", "CARDS_DATABASE_URL", "LOCALAPPDATA"):
            print(f"[planeswalker] env {var}={os.getenv(var)!r}", file=sys.stderr, flush=True)
        if exists:
            con = sqlite3.connect(str(db))
            try:
                has_decks = con.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='decks'"
                ).fetchone()[0]
                n_decks = (
                    con.execute("SELECT count(*) FROM decks").fetchone()[0] if has_decks else None
                )
                has_cards = con.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='cards'"
                ).fetchone()[0]
                n_cards = (
                    con.execute("SELECT count(*) FROM cards").fetchone()[0] if has_cards else None
                )
            finally:
                con.close()
            print(f"[planeswalker] decks={n_decks} cards={n_cards}", file=sys.stderr, flush=True)
    except Exception as exc:  # diagnostics must never break startup
        print(f"[planeswalker] startup-diagnostics-error: {exc!r}", file=sys.stderr, flush=True)


def _run_mcp_server() -> int:
    """Build the server and run it over the configured transport (default stdio).

    The body of the pre-dispatcher ``main()``, moved verbatim. Nothing may be added to this path:
    no logging configuration, no ``print`` and no import of anything under ``src/companion/``, so a
    bare invocation still emits exactly one stdout stream (JSON-RPC) and five stderr diagnostics.

    Returns:
        ``0`` once the server's own run loop returns.
    """
    transport = cast(_Transport, os.getenv("MCP_TRANSPORT", "stdio"))
    _log_startup_diagnostics()
    build_server().run(transport=transport)
    return 0


def _usage(stream: TextIO | None = None) -> None:
    """Write the usage text to *stream*.

    Args:
        stream: ``sys.stdout`` for ``--help`` (a user asking for help has made no error) or
            ``sys.stderr`` for a usage error. Defaults to stdout.
    """
    print(_USAGE, end="", file=stream or sys.stdout)


def _usage_error(message: str) -> int:
    """Report a malformed invocation on stderr and return the conventional usage status.

    Args:
        message: What the user got wrong, phrased so the fix is visible with the command still
            on screen.

    Returns:
        ``2`` — the status ``argparse`` would have used, and the only non-zero this program mints
        (c1-9 Decide-once #5).
    """
    print(f"artificial-planeswalker: error: {message}", file=sys.stderr)
    _usage(sys.stderr)
    return 2


def _parse_companion_args(args: Sequence[str]) -> tuple[int | None, bool] | str:
    """Parse ``companion``'s arguments down to a preferred port and an open-browser flag.

    Accepts ``--port N`` and ``--port=N``, in that one form pair only, **at most once** — this CLI
    has no alias-override use case, so a repeated ``--port`` is almost certainly a typo and
    silently letting the last one win could select an unintended port (Greptile PR #16, ruled by
    Brad 2026-07-26). A non-integer value is likewise a *usage* error — unlike a stale environment
    variable it is something the user typed in this invocation — while an out-of-range integer is
    not: it flows through to
    :func:`src.companion.app.server.resolve_preferred_port`, which logs a warning and uses the
    default, exactly as it treats ``COMPANION_PORT``.

    ``--open`` (17.4) is a bare flag and takes no value: ``--open=yes`` is an unrecognized
    argument like any other, and giving it twice is the same typo ``--port`` twice is. Order
    between the two options is free.

    Args:
        args: Everything after the ``companion`` subcommand.

    Returns:
        ``(port, open_browser)`` — the port ``None`` when ``--port`` was not given — or a ``str``
        describing the usage error when the arguments are malformed.
    """
    port: int | None = None
    open_browser = False
    remaining = list(args)
    while remaining:
        arg = remaining.pop(0)
        if arg == "--open":
            if open_browser:
                return "--open given more than once"
            open_browser = True
            continue
        if arg == "--port":
            if not remaining:
                return "--port needs a value"
            raw = remaining.pop(0)
        elif arg.startswith("--port="):
            raw = arg.partition("=")[2]
        else:
            return f"unrecognized argument: {arg}"
        if port is not None:
            return "--port given more than once"
        try:
            port = int(raw)
        except ValueError:
            return f"--port needs an integer, not {raw!r}"
    return port, open_browser


def _run_companion(args: Sequence[str]) -> int:
    """Run the companion backend in the foreground until it is interrupted.

    Args:
        args: Everything after the ``companion`` subcommand.

    Returns:
        ``0`` when the backend served and stopped, when it refused because another instance holds
        the machine, when the user interrupted it, or when they asked for help; ``2`` for a
        malformed invocation.
    """
    if any(arg in ("-h", "--help") for arg in args):
        # A user asking for help has made no error, wherever the flag sits (Decide-once #5,
        # extended by the c1-9 review ruling): usage on stdout, exit 0 — never the stderr banner.
        _usage()
        return 0
    parsed = _parse_companion_args(args)
    if isinstance(parsed, str):
        return _usage_error(parsed)
    port, open_browser = parsed

    # AD-15: this process owns its terminal, so unlike the MCP process it configures the root
    # logger — and this is what finally surfaces the records c1-3, c1-7 and c1-8 already emit
    # (the port fallback, the discovery-write warnings, the reclaim notice). It must happen before
    # run() is called, because the earliest of those records is emitted inside run() before uvicorn
    # exists. INFO rather than DEBUG: read_discovery and probe_health log their ordinary
    # "nothing there" outcomes at DEBUG, which would become per-push chatter once tools push.
    # stderr rather than stdout: the deliberate user-facing lines are already printed to stdout by
    # run(), and uvicorn's access log lands there too.
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        # Function-local by AD-3 — see the module docstring. A bare invocation must never import
        # FastAPI or uvicorn, and the boundary guard fails this file for a module-level form.
        # Inside the try: the import pulls in FastAPI + uvicorn (on the order of a second, cold),
        # and a Ctrl-C in that window is the same deliberate user action as one during the probe.
        from src.companion.app.server import run

        run(port, open_browser=open_browser)
    except KeyboardInterrupt:
        # Under uvicorn, Ctrl-C is handled internally and shuts the server down gracefully. An
        # interrupt *before* uvicorn exists — during the identity probe or the bind — propagates
        # out of run() instead, and a traceback is the wrong answer to a deliberate user action on
        # a foreground process. run()'s outermost finally has already released the instance lock.
        print(file=sys.stderr)
        return 0
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to the MCP server or the companion, and return the process's exit status.

    The installed console-script wrapper is ``sys.exit(main())`` and the module footer is
    ``raise SystemExit(main())``, so this return value *is* the exit status on both paths and
    nothing here calls ``sys.exit`` itself.

    Args:
        argv: The arguments after the program name. Defaults to ``sys.argv[1:]``; it exists so a
            test can dispatch without mutating ``sys.argv``, and it is resolved exactly once, here.

    Returns:
        ``0`` when the requested thing ran (or the user asked for help), ``2`` for an unknown
        subcommand or a malformed option (c1-9 Decide-once #5).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return _run_mcp_server()

    command, rest = args[0], args[1:]
    if command in ("-h", "--help"):
        _usage()
        return 0
    if command == "companion":
        return _run_companion(rest)
    return _usage_error(f"unknown subcommand: {command}")


if __name__ == "__main__":
    raise SystemExit(main())

"""Entry point for the Artificial-Planeswalker MCP server.

The transport is selected here — and only here — so HTTP/SSE can swap in later
without changing any tool definition (AC2 / D7). Defaults to ``stdio``; override
via the ``MCP_TRANSPORT`` environment variable.

Run with:
    uv run python -m src.mcp_server
"""

import os
import sqlite3
import sys
from typing import Literal, cast

from src.mcp_server.server import build_server

_Transport = Literal["stdio", "sse", "streamable-http"]


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


def main() -> None:
    """Build the server and run it over the configured transport (default stdio)."""
    transport = cast(_Transport, os.getenv("MCP_TRANSPORT", "stdio"))
    _log_startup_diagnostics()
    build_server().run(transport=transport)


if __name__ == "__main__":
    main()

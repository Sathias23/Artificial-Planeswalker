"""Entry point for the Artificial-Planeswalker MCP server.

The transport is selected here — and only here — so HTTP/SSE can swap in later
without changing any tool definition (AC2 / D7). Defaults to ``stdio``; override
via the ``MCP_TRANSPORT`` environment variable.

Run with:
    uv run python -m src.mcp_server
"""

import os
from typing import Literal, cast

from src.mcp_server.server import build_server

_Transport = Literal["stdio", "sse", "streamable-http"]


def main() -> None:
    """Build the server and run it over the configured transport (default stdio)."""
    transport = cast(_Transport, os.getenv("MCP_TRANSPORT", "stdio"))
    build_server().run(transport=transport)


if __name__ == "__main__":
    main()

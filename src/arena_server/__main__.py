"""Entry point for the Arena game-state MCP server.

Run with:
    uv run python -m src.arena_server

stdio only, like the deckbuilding server: stdout carries the JSON-RPC stream and nothing else, so
nothing here prints or configures logging.
"""

from src.arena_server.server import build_server


def main() -> int:
    """Run the server over stdio until the client disconnects.

    Returns:
        ``0`` once the server's own run loop returns.
    """
    build_server().run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""MCP server package (FastMCP) for Artificial-Planeswalker.

Exposes :func:`build_server`, which constructs the FastMCP server and registers
the card-lookup and bug-report tools. The transport is selected at the entry
point (:mod:`src.mcp_server.__main__`), keeping tool definitions transport-free.
"""

from src.mcp_server.server import build_server

__all__ = ["build_server"]

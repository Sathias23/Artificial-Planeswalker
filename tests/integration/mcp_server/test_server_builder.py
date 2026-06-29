"""Tests for build_server tool registration (Story 1.3, Task 4)."""

from mcp.server.fastmcp import FastMCP

import src.mcp_server as mcp_pkg
from src.mcp_server.server import build_server


async def test_build_server_returns_fastmcp_with_tools():
    """build_server() returns a FastMCP exposing the registered tools by name."""
    server = build_server()  # default factory; building does not touch the DB

    assert isinstance(server, FastMCP)
    tools = await server.list_tools()
    names = {tool.name for tool in tools}
    assert {"lookup_card_by_name", "search_cards"} <= names


def test_build_server_is_exported_from_package():
    """build_server is re-exported from the src.mcp_server package."""
    assert hasattr(mcp_pkg, "build_server")

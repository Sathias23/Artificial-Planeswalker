"""Tests for the MCP entry point and .mcp.json registration (Story 1.3, Task 5)."""

import json
from pathlib import Path

import pytest

import src.mcp_server.__main__ as main_mod


class _FakeServer:
    """Records the transport passed to run() instead of starting a server."""

    def __init__(self) -> None:
        self.transport: str | None = None

    def run(self, transport: str) -> None:
        self.transport = transport


def test_main_defaults_to_stdio_transport(monkeypatch: pytest.MonkeyPatch):
    """With no MCP_TRANSPORT set, the entry point runs over stdio (AC2)."""
    fake = _FakeServer()
    monkeypatch.setattr(main_mod, "build_server", lambda: fake)
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)

    main_mod.main()

    assert fake.transport == "stdio"


def test_main_honors_env_transport(monkeypatch: pytest.MonkeyPatch):
    """The transport is selected only at the entry point, from MCP_TRANSPORT (AC2/D7)."""
    fake = _FakeServer()
    monkeypatch.setattr(main_mod, "build_server", lambda: fake)
    monkeypatch.setenv("MCP_TRANSPORT", "sse")

    main_mod.main()

    assert fake.transport == "sse"


def test_mcp_json_registers_server():
    """The repo-root .mcp.json registers the server for Claude Code (AC1)."""
    mcp_json = Path(__file__).parents[3] / ".mcp.json"
    data = json.loads(mcp_json.read_text(encoding="utf-8"))

    server = data["mcpServers"]["artificial-planeswalker"]
    assert server["command"] == "uv"
    assert server["args"] == ["run", "python", "-m", "src.mcp_server"]

"""Regression tests for ``scripts/build_plugin.py`` — the Claude Code plugin assembler.

Guards the invariants that have actually broken builds, plus the server tool surface the
assembled plugin must expose:

* ``src/viewer/`` must ship — ``view_deck.py`` imports it at load (the f567062 ``.mcpb`` bug).
* Whatever file ``pyproject [project].readme`` points at must ship — ``uv run`` builds the
  server package, and hatchling hard-fails ("Readme file does not exist") without it.
* A missing ``SERVER_FILES`` entry aborts cleanly (exit 1), not with a raw traceback.
* The server registers the full 16-tool surface (AC1) — a presence-only build check can't see this.
"""

import json
import tomllib
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from scripts import build_plugin
from scripts.build_plugin import IGNORE, SKILLS, build
from src.mcp_server.server import build_server


def test_build_plugin_copies_build_critical_files(tmp_path: Path) -> None:
    """A clean build lands every build-critical file + the 4 skills + correct manifests."""
    out = tmp_path / "plugin"
    assert build(out) == 0

    server = out / "server"
    # src/viewer/ must come along — view_deck.py imports it at module load (f567062).
    assert (server / "src" / "viewer" / "__init__.py").is_file()
    assert (server / "pyproject.toml").is_file()
    assert (server / "uv.lock").is_file()

    # The installed plugin redistributes MIT-licensed code, so the license grant and the
    # WotC/Scryfall attribution must travel with it.
    assert (server / "LICENSE").is_file()
    assert (server / "NOTICE").is_file()

    # Contract, not symptom: whatever pyproject's [project].readme points at must ship, so a
    # future `readme = "README.rst"` rename can't silently re-break the package build.
    readme = tomllib.loads((server / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "readme"
    ]
    readme_name = readme["file"] if isinstance(readme, dict) else readme
    assert (server / readme_name).is_file(), f"declared readme {readme_name!r} missing from server/"

    # All four MTG skills, each with its SKILL.md.
    for skill in SKILLS:
        assert (out / "skills" / skill / "SKILL.md").is_file()

    # Generated plugin manifest carries the real metadata, sourced from pyproject.toml
    # (the .mcpb manifest.json is retired — pyproject is the single metadata source).
    plugin_json = json.loads((out / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert plugin_json["name"] == "artificial-planeswalker"
    assert plugin_json["license"] == "MIT"
    assert plugin_json["author"] == {"name": "Sathias", "email": "sathias@slopstudio.net"}
    assert plugin_json["repository"] == "https://github.com/Sathias23/Artificial-Planeswalker"
    assert "mtg" in plugin_json["keywords"]
    pyproject = tomllib.loads((server / "pyproject.toml").read_text(encoding="utf-8"))
    assert plugin_json["version"] == pyproject["project"]["version"]

    # Generated MCP config anchors the server to the installed plugin root.
    mcp_json = json.loads((out / ".mcp.json").read_text(encoding="utf-8"))
    args = mcp_json["mcpServers"]["artificial-planeswalker"]["args"]
    assert "${CLAUDE_PLUGIN_ROOT}/server" in args


def test_build_aborts_on_missing_server_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A SERVER_FILES entry absent from the repo root aborts with exit 1, not a traceback."""
    monkeypatch.setattr(
        build_plugin, "SERVER_FILES", [*build_plugin.SERVER_FILES, "DOES_NOT_EXIST.md"]
    )
    assert build(tmp_path / "plugin") == 1


def test_ignore_excludes_caches_and_cruft() -> None:
    """The IGNORE matcher drops caches/editor cruft and keeps real sources."""
    ignored = IGNORE("anydir", ["__pycache__", "mod.pyc", "note.swp", "keep.py"])
    assert ignored == {"__pycache__", "mod.pyc", "note.swp"}


async def test_server_registers_expected_tools() -> None:
    """AC1 guard: the server registers exactly the 16 expected tools."""
    server = build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()

    names = {tool.name for tool in result.tools}
    assert len(names) == 16
    # The two first-run maintenance tools must register alongside the 14 card/deck tools.
    assert {"initialize_database", "build_search_index"} <= names

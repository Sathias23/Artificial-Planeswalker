"""Regression tests for ``scripts/build_plugin.py`` — the Claude Code plugin assembler.

Guards the invariants that have actually broken builds, plus the server tool surface the
assembled plugin must expose:

* ``src/viewer/`` must ship — ``view_deck.py`` imports it at load (the f567062 ``.mcpb`` bug).
* Whatever file ``pyproject [project].readme`` points at must ship — ``uv run`` builds the
  server package, and hatchling hard-fails ("Readme file does not exist") without it.
* A missing ``SERVER_FILES`` entry aborts cleanly (exit 1), not with a raw traceback.
* The server registers the full 17-tool surface (AC1) — a presence-only build check can't see this.
* The Codex manifests (``.codex-plugin/plugin.json`` + ``codex-mcp.json``) keep their schema:
  snake_case ``mcp_servers`` wrapper, ``cwd`` anchor, and no ``${CLAUDE_PLUGIN_ROOT}`` leakage
  (Codex does no variable substitution — openai/codex#19372).
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

    # Codex manifest must be the Claude manifest plus exactly the two Codex pointer keys —
    # anything else means the two clients' metadata has drifted.
    codex_manifest = json.loads((out / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert codex_manifest == {
        **plugin_json,
        "skills": "./skills/",
        "mcpServers": "./codex-mcp.json",
    }
    assert codex_manifest["version"] == pyproject["project"]["version"]

    # Codex MCP config: camelCase `mcpServers` wrapper — verified against Codex's own
    # plugin-creator scaffold, which stubs `{"mcpServers": {}}`; a snake_case wrapper is
    # silently dropped and no tools mount. Launch is anchored via cwd because Codex does
    # NOT substitute ${CLAUDE_PLUGIN_ROOT} (openai/codex#19372) — a leaked Claude variable
    # (or a --directory anchor) would be passed through literally and break the launch.
    codex_mcp_text = (out / "codex-mcp.json").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" not in codex_mcp_text
    codex_mcp = json.loads(codex_mcp_text)
    codex_server = codex_mcp["mcpServers"]["artificial-planeswalker"]
    assert codex_server["cwd"] == "./server"
    assert codex_server["args"] == ["run", "python", "-m", "src.mcp_server"]
    assert codex_server["env"] == {"MCP_TRANSPORT": "stdio"}


def test_codex_marketplace_points_at_committed_plugin() -> None:
    """The hand-written Codex marketplace stays aligned with pyproject and the plugin tree.

    `.agents/plugins/marketplace.json` sits outside the build script and the CI drift
    check, so this is its only guard against a typo'd path or a renamed plugin.
    """
    marketplace = json.loads(
        (build_plugin.REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    pyproject = tomllib.loads(
        (build_plugin.REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    (entry,) = marketplace["plugins"]
    assert entry["name"] == pyproject["project"]["name"]
    assert entry["source"] == {"source": "local", "path": "./plugin"}
    # The local source path resolves against the repo checkout — the committed plugin tree.
    assert (build_plugin.REPO_ROOT / "plugin" / ".codex-plugin" / "plugin.json").is_file()


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
    """AC1 guard: the server registers exactly the 18 expected tools."""
    server = build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()

    names = {tool.name for tool in result.tools}
    assert names == {
        "lookup_card_by_name",
        "search_cards",
        "list_decks",
        "create_deck",
        "load_deck",
        "delete_deck",
        "add_card_to_deck",
        "import_decklist",
        "remove_card_from_deck",
        "view_deck",
        "analyze_mana_curve",
        "detect_synergies",
        "validate_deck",
        "assess_deck_power",
        "semantic_search_cards",
        "find_similar_cards",
        "initialize_database",
        "build_search_index",
    }

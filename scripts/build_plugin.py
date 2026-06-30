#!/usr/bin/env python3
"""Assemble a Claude Code plugin tree under ``plugin/`` from the single ``src/``.

The ``.mcpb`` bundle ships only the MCP *tools*; it cannot carry Claude **Skills**. A
Claude Code plugin can ship both, so this script packages the MCP server *and* its four
companion MTG skills as one installable unit. See ``docs/plugin-structure.md`` for the
design rationale and the resulting layout.

Single source of truth:

* Server code: this repo's ``src/`` + ``pyproject.toml`` + ``uv.lock`` (copied verbatim).
* Plugin/author metadata: ``manifest.json`` (reused so the plugin never drifts from the
  ``.mcpb``).
* Skills: the four MTG skills under ``.claude/skills/`` (the ``bmad-*`` skills are repo
  dev-tooling and are intentionally excluded).

The script is deterministic and idempotent: it rebuilds ``plugin/``'s generated contents
(leaving any runtime ``.venv``/caches in place), so running it twice yields the same committed
tree. ``plugin/`` is **committed** — it is the marketplace ``source``
(see ``.claude-plugin/marketplace.json``), so the GitHub two-command install
(``/plugin marketplace add`` → ``/plugin install``) clones a repo that already contains the
assembled plugin. Rebuild and commit ``plugin/`` whenever ``src/`` or the skills change.

Usage:
    uv run python -m scripts.build_plugin     # -> plugin/ (committed marketplace source)
    uv run python -m scripts.build_plugin --out X    # build into X/ (scratch / testing)
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Only the MTG domain skills ship to end users; bmad-* skills are repo dev-tooling.
SKILLS = [
    "magic-deckbuilding",
    "mana-curve-analysis",
    "synergy-discovery",
    "format-legality",
]

# Server files copied verbatim into <plugin>/server/. src/ is handled separately so we
# can drop caches; these are the rest of the runtime project root. README.md is required
# at build time: pyproject sets `readme = "README.md"`, so `uv run` (which builds the
# package before launching the server) hard-fails with "Readme file does not exist" without it.
SERVER_FILES = ["pyproject.toml", "uv.lock", "README.md"]

# Caches / cruft never copied into the plugin tree.
IGNORE = shutil.ignore_patterns("__pycache__", "*.py[cod]", "*.swp", "*.swo", ".DS_Store")


def _load_manifest() -> dict:
    """Read manifest.json — the shared metadata source for plugin.json."""
    return json.loads((REPO_ROOT / "manifest.json").read_text(encoding="utf-8"))


def _plugin_json(manifest: dict) -> dict:
    """Build the plugin manifest from the .mcpb manifest, so the two stay in sync."""
    return {
        "name": manifest["name"],
        "description": manifest["description"],
        "version": manifest["version"],
        "author": manifest["author"],
        "homepage": manifest.get("homepage"),
        "repository": manifest.get("repository", {}).get("url"),
        "license": manifest.get("license"),
        "keywords": manifest.get("keywords", []),
    }


def _mcp_json() -> dict:
    """MCP server config anchored to the installed plugin via CLAUDE_PLUGIN_ROOT."""
    return {
        "mcpServers": {
            "artificial-planeswalker": {
                "command": "uv",
                "args": [
                    "run",
                    "--directory",
                    "${CLAUDE_PLUGIN_ROOT}/server",
                    "python",
                    "-m",
                    "src.mcp_server",
                ],
                "env": {"MCP_TRANSPORT": "stdio"},
            }
        }
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    # newline="\n" forces LF on every OS. The plugin/ tree is committed, so a build on Windows
    # (CRLF) must produce the same bytes as the Linux CI rebuild — otherwise the plugin/-in-sync
    # check would diff on line endings alone.
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def build(out_dir: Path) -> int:
    """Assemble the plugin tree at *out_dir*. Returns a process exit code."""
    manifest = _load_manifest()

    # 1. Clean the build's MANAGED outputs only, leaving runtime cruft (a .venv or *.egg-info
    #    created by running the server in-place during local marketplace testing) untouched. A
    #    blanket rmtree(out_dir) chokes on a locked .venv on Windows and aborts mid-delete, leaving
    #    the committed tree half-built. They're gitignored, so they never get committed. (Local
    #    marketplace testing runs the server in-place; the GitHub install clones to a cache dir.)
    out_dir.mkdir(parents=True, exist_ok=True)
    server_dir = out_dir / "server"
    for managed in (server_dir / "src", out_dir / "skills", out_dir / ".claude-plugin"):
        if managed.exists():
            shutil.rmtree(managed)
    (out_dir / ".mcp.json").unlink(missing_ok=True)

    # 2. Server source. src/viewer/ MUST come along — src/mcp_server/tools/view_deck.py
    #    imports it at module load; omitting it broke the first .mcpb build (f567062).
    server_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_ROOT / "src", server_dir / "src", ignore=IGNORE)
    if not (server_dir / "src" / "viewer" / "__init__.py").exists():
        logger.error("src/viewer/ missing from copied server — aborting")
        return 1
    for name in SERVER_FILES:
        src_file = REPO_ROOT / name
        if not src_file.exists():
            logger.error("Required server file %s missing at %s — aborting", name, src_file)
            return 1
        shutil.copy2(src_file, server_dir / name)
    logger.info("Copied server -> %s", server_dir)

    # 3. The four MTG skills.
    skills_dir = out_dir / "skills"
    for skill in SKILLS:
        src = REPO_ROOT / ".claude" / "skills" / skill
        if not (src / "SKILL.md").exists():
            logger.error("Skill %s not found at %s — aborting", skill, src)
            return 1
        shutil.copytree(src, skills_dir / skill, ignore=IGNORE)
    logger.info("Copied %d skills -> %s", len(SKILLS), skills_dir)

    # 4. Generated manifests.
    _write_json(out_dir / ".claude-plugin" / "plugin.json", _plugin_json(manifest))
    _write_json(out_dir / ".mcp.json", _mcp_json())
    logger.info("Wrote .claude-plugin/plugin.json and .mcp.json")

    logger.info(
        "Plugin assembled at %s (v%s, %d skills)",
        out_dir,
        manifest["version"],
        len(SKILLS),
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "plugin",
        help="Output directory (default: plugin/, the committed marketplace source).",
    )
    args = parser.parse_args()
    return build(args.out.resolve())


if __name__ == "__main__":
    raise SystemExit(main())

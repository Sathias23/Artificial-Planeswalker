"""Regression tests for ``scripts/build_plugin.py`` — the Claude Code plugin assembler.

Guards the invariants that have actually broken builds, plus the server tool surface the
assembled plugin must expose:

* ``src/viewer/`` must ship — ``view_deck.py`` imports it at load (the f567062 ``.mcpb`` bug).
* Whatever file ``pyproject [project].readme`` points at must ship — ``uv run`` builds the
  server package, and hatchling hard-fails ("Readme file does not exist") without it.
* A missing ``SERVER_FILES`` entry aborts cleanly (exit 1), not with a raw traceback.
* The server registers its full tool surface (AC1) — a presence-only build check can't see this.
  The count is deliberately not repeated here: it lives once, as the exact name set in
  ``test_server_registers_expected_tools`` below. Stating it twice is how this line came to say
  "17" while the set below held 19.
* The Codex manifests (``.codex-plugin/plugin.json`` + ``codex-mcp.json``) keep their schema:
  snake_case ``mcp_servers`` wrapper, ``cwd`` anchor, and no ``${CLAUDE_PLUGIN_ROOT}`` leakage
  (Codex does no variable substitution — openai/codex#19372).
* **Distribution parity for the companion (story 15-5).** The plugin is the install route that
  has to carry the companion's UI, and until this story nothing proved it did: the two abort
  paths at ``build_plugin.py:194-216`` had never been fired, no assertion said the built tree
  carried the bundle at all, the skills check was presence-only (a ``bmad-*`` entry added to
  ``SKILLS`` would have shipped unnoticed), and nothing said the bytes a plugin user receives
  are the bytes the app serves. Everything below :class:`TestTheBuiltTreeCarriesTheCompanion`
  closes that.

**Why the built tree is built once.** A ``build()`` copies ~1.8 MB, so the read-only parity
assertions share one module-scoped tree rather than paying for it per test. The fault-injection
tests build their own, because they deliberately corrupt what they build.

**What a byte-comparison cannot prove** — that the served bundle renders in a real browser on a
genuinely clean machine. No hermetic test can produce one, and a browser check would need the
Node toolchain this story's acceptance is about *not* needing. What is proven here is the thing
that actually differs between the two copies: the mirrored bytes, and that they serve through the
real SPA mount. The residue is a recorded manual check, not a silent gap.
"""

import json
import logging
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from mcp.shared.memory import create_connected_server_and_client_session

from scripts import build_plugin
from scripts.build_plugin import IGNORE, SKILLS, build
from src.companion.app.spa import STATIC_DIR, install_spa
from src.mcp_server.server import build_server

_BUNDLE_RELATIVE = STATIC_DIR.resolve().relative_to((build_plugin.REPO_ROOT / "src").resolve())
"""The SPA bundle's path relative to ``src/`` — the same in the repo and in ``<plugin>/server/``.

Derived from the shipped :data:`~src.companion.app.spa.STATIC_DIR` rather than transcribed, so a
move of the bundle inside the package brings this module with it instead of leaving it asserting
about a directory nobody writes to any more.

Both sides are ``resolve()``d before the subtraction: ``REPO_ROOT`` is already resolved and
``STATIC_DIR`` is not, so in a checkout reached through a symlink ``relative_to`` would raise at
**import** time and collapse this whole module into a collection error.
"""

_SOURCE_BUNDLE = build_plugin.REPO_ROOT / "src" / _BUNDLE_RELATIVE
_MIRRORED_BUNDLE = build_plugin.REPO_ROOT / "plugin" / "server" / "src" / _BUNDLE_RELATIVE


_needs_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="this assertion shells out to git"
)
_needs_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="the workflow step under test is a bash script"
)
_SUBPROCESS_TIMEOUT = 60
"""Seconds any one git/bash call here may take. A hung git (a credential prompt on a misconfigured
machine is the usual one) must fail its test rather than wedge the whole suite behind it."""


def _tree(root: Path) -> dict[str, bytes]:
    """Map every file under *root* to its bytes, keyed by POSIX-relative path.

    Keys are compared as a *set* by the callers, so a copy that gained or lost a file names the
    difference instead of failing on the first byte mismatch. POSIX separators keep the keys
    identical on Windows, where the committed tree is also built.

    Names ``build_plugin.IGNORE`` drops are skipped, because a comparison between a source
    directory and its copy must apply the copy's own rules: a stray ``.DS_Store`` beside the
    bundle (macOS writes them into any browsed folder) is correctly absent from the built tree,
    and without this filter it would turn the byte-parity assertions red for a file the build was
    right to omit. ``ignore_patterns`` matchers ignore their directory argument, so each path
    segment is asked about on its own.

    Args:
        root: Directory to walk.

    Returns:
        ``{"assets/index-abc.js": b"...", ...}`` for every file below *root* the build would copy.
    """
    tree: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(IGNORE("", [segment]) for segment in relative.parts):
            continue
        tree[relative.as_posix()] = path.read_bytes()
    return tree


def _assert_bundles_match(actual: Path, expected: Path, remedy: str) -> None:
    """Assert two bundle directories hold the same relative paths with the same bytes.

    Args:
        actual: The copy under test.
        expected: The copy it must equal.
        remedy: The command a failure should tell the reader to run.
    """
    actual_tree, expected_tree = _tree(actual), _tree(expected)

    assert expected_tree, (
        f"{expected} holds no files — the source bundle is missing, so this comparison would "
        f"pass vacuously. Rebuild it with: cd ui && npm run build"
    )
    assert actual_tree.keys() == expected_tree.keys(), (
        f"{actual} and {expected} hold different files "
        f"(only in the first: {sorted(actual_tree.keys() - expected_tree.keys())}; "
        f"only in the second: {sorted(expected_tree.keys() - actual_tree.keys())}). {remedy}"
    )
    # Names AND bytes: CRLF mangling does not change a filename, so a name-only comparison would
    # pass over byte-divergent assets.
    divergent = sorted(name for name, blob in expected_tree.items() if actual_tree[name] != blob)
    assert not divergent, f"{actual} holds byte-divergent copies of {divergent}. {remedy}"


@pytest.fixture(scope="module")
def built_plugin(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One clean ``build()`` shared by every read-only assertion in this module.

    Returns:
        The root of a freshly built plugin tree.
    """
    out = tmp_path_factory.mktemp("built-plugin") / "plugin"
    assert build(out) == 0, "the clean build must succeed before anything can be asserted about it"
    return out


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
    """AC1 guard: the server registers exactly the tools named below and no others.

    Set equality, so an addition and a silent removal both fail and name themselves. c6-2 adds
    ``companion_set_active_deck`` — the first tool that talks to the companion backend rather than
    to the database alone — and c6-4 adds ``companion_show_suggestions``, the first that talks to it
    without touching the database at all.
    """
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
        "companion_status",
        "companion_set_active_deck",
        "companion_show_suggestions",
        "companion_show_swaps",
        "companion_show_tier_list",
        "companion_show_groups",
        "analyze_mana_curve",
        "detect_synergies",
        "validate_deck",
        "assess_deck_power",
        "compare_deck_power",
        "semantic_search_cards",
        "find_similar_cards",
        "initialize_database",
        "build_search_index",
    }


async def test_companion_show_suggestions_publishes_its_payload_shape_to_the_agent() -> None:
    """c6-4 AC1, mechanised: the published schema *is* the affordance the tool exists for.

    OQ-2 chose per-kind tools over one generic ``companion_display`` because a per-tool schema and
    docstring tell an agent more than a generic one can, and c6-4's Q1 made the contract model the
    tool's argument so FastMCP hands over the whole nested shape — the item fields and their caps —
    rather than an opaque ``object``. Nothing else in the suite would notice if that stopped being
    true: a "simplification" to a loose ``dict`` argument keeps every helper test green while
    silently reducing the agent's view of the payload to nothing.
    """
    server = build_server()
    async with create_connected_server_and_client_session(server) as client:
        tools = (await client.list_tools()).tools

    tool = next(candidate for candidate in tools if candidate.name == "companion_show_suggestions")
    schema = json.dumps(tool.inputSchema)

    assert "SuggestionItem" in schema, "the item shape must reach the agent, not just 'an object'"
    for field in ("card_id", "reason", "category", "confidence", "title"):
        assert field in schema, f"{field} is part of the payload the agent has to fill in"
    assert "maxItems" in schema, "the 60-item cap is part of the affordance, not a surprise"
    assert "maxLength" in schema, "so are the per-field length caps"
    assert tool.description is not None
    assert "Scryfall" in tool.description, (
        "FR-13: the docstring is the description, and it has to say ids rather than card names"
    )


async def test_companion_show_swaps_publishes_its_payload_shape_to_the_agent() -> None:
    """16-1's sibling of the suggestions publication guard: the schema IS the affordance.

    Same reasoning as above — a "simplification" to a loose ``dict`` argument would keep every
    helper test green while reducing the agent's view of the payload to an opaque object, and
    nothing else in the suite would notice.
    """
    server = build_server()
    async with create_connected_server_and_client_session(server) as client:
        tools = (await client.list_tools()).tools

    tool = next(candidate for candidate in tools if candidate.name == "companion_show_swaps")
    schema = json.dumps(tool.inputSchema)

    assert "SwapItem" in schema, "the item shape must reach the agent, not just 'an object'"
    fields = ("out_card_id", "in_card_id", "rationale", "out_qty", "in_qty", "confidence", "title")
    for field in fields:
        assert field in schema, f"{field} is part of the payload the agent has to fill in"
    assert "maxItems" in schema, "the 60-item cap is part of the affordance, not a surprise"
    assert "maxLength" in schema, "so are the per-field length caps"
    assert tool.description is not None
    assert "Scryfall" in tool.description, (
        "FR-13: the docstring is the description, and it has to say ids rather than card names"
    )


async def test_companion_show_tier_list_publishes_its_payload_shape_to_the_agent() -> None:
    """16-2's sibling of the two publication guards above: the schema IS the affordance.

    Same reasoning — a "simplification" to a loose ``dict`` argument would keep every helper test
    green while reducing the agent's view of the payload to an opaque object, and nothing else in
    the suite would notice.
    """
    server = build_server()
    async with create_connected_server_and_client_session(server) as client:
        tools = (await client.list_tools()).tools

    tool = next(candidate for candidate in tools if candidate.name == "companion_show_tier_list")
    schema = json.dumps(tool.inputSchema)

    assert "TierItem" in schema, "the tier shape must reach the agent, not just 'an object'"
    for field in ("letter", "name", "note", "card_ids", "title"):
        assert field in schema, f"{field} is part of the payload the agent has to fill in"
    assert "maxItems" in schema, "the 12-tier and 60-card caps are part of the affordance"
    assert "maxLength" in schema, "so are the per-field length caps"
    assert tool.description is not None
    assert "Scryfall" in tool.description, (
        "FR-13: the docstring is the description, and it has to say ids rather than card names"
    )


async def test_companion_show_groups_publishes_its_payload_shape_to_the_agent() -> None:
    """16-3's sibling of the three publication guards above: the schema IS the affordance.

    Same reasoning — a "simplification" to a loose ``dict`` argument would keep every helper test
    green while reducing the agent's view of the payload to an opaque object, and nothing else in
    the suite would notice. The per-field loop leans on ``rationale`` and ``card_ids`` rather
    than ``title``, which exists at both the payload and the item level and so discriminates
    nothing.
    """
    server = build_server()
    async with create_connected_server_and_client_session(server) as client:
        tools = (await client.list_tools()).tools

    tool = next(candidate for candidate in tools if candidate.name == "companion_show_groups")
    schema = json.dumps(tool.inputSchema)

    assert "GroupItem" in schema, "the group shape must reach the agent, not just 'an object'"
    for field in ("rationale", "card_ids"):
        assert field in schema, f"{field} is part of the payload the agent has to fill in"
    assert "maxItems" in schema, "the 12-group and 60-card caps are part of the affordance"
    assert "maxLength" in schema, "so are the per-field length caps"
    assert tool.description is not None
    assert "Scryfall" in tool.description, (
        "FR-13: the docstring is the description, and it has to say ids rather than card names"
    )


class TestTheBuiltTreeCarriesTheCompanion:
    """Story 15-5, AC 1 / AC 5 and the "no Node toolchain" half of AC 4.

    Read-only assertions over one shared clean build. Until this class existed, the build's own
    SPA guards were the *only* thing standing between a silent copy failure and a plugin that
    installs, launches, and has no UI — and those guards had never been fired either (see
    :class:`TestTheBundleGuardsFire`).
    """

    def test_the_built_bundle_matches_the_source_bundle(self, built_plugin: Path) -> None:
        """AC 1: what the build emits is the repository's bundle, path-for-path and byte-for-byte.

        The build's own guard only asks whether ``index.html`` exists and ``assets/`` is
        non-empty. A copy that dropped the font, or truncated a file, satisfies it completely.
        """
        _assert_bundles_match(
            built_plugin / "server" / "src" / _BUNDLE_RELATIVE,
            _SOURCE_BUNDLE,
            remedy="The build copies src/ verbatim, so this is a copy defect, not staleness.",
        )

    def test_the_built_skills_are_exactly_the_product_skills(self, built_plugin: Path) -> None:
        """AC 5: an *exclusive* set, so the shipped skills are bounded from above as well as below.

        The pre-existing per-skill ``SKILL.md`` check is presence-only: it cannot see an extra
        entry. Two assertions, because ``set(SKILLS)`` alone would be tautological — the build
        reads the same constant, so a widened ``SKILLS`` stays "correct" against itself. The
        literal set is the one the four skills are *named* in, exactly as the tool surface is
        named once in ``test_server_registers_expected_tools``: shipping a fifth skill is a
        product decision, and a product decision should have to edit a test that says so.
        """
        product_skills = {
            "magic-deckbuilding",
            "mana-curve-analysis",
            "synergy-discovery",
            "format-legality",
            "companion",
        }

        assert set(SKILLS) == product_skills
        assert {entry.name for entry in (built_plugin / "skills").iterdir()} == product_skills

    def test_no_bmad_skill_leaks_anywhere_into_the_built_tree(self, built_plugin: Path) -> None:
        """AC 5, over the whole tree — ``skills/`` is the expected route in, not the only one.

        Compared lowercased: ``rglob`` is case-sensitive on Linux (where CI runs), so a
        ``BMad-*`` directory would be invisible to the pattern on the one platform that matters
        while being the *same* directory on the macOS and Windows checkouts it came from.
        """
        leaked = [
            entry.name
            for entry in built_plugin.rglob("*")
            if entry.name.lower().startswith("bmad-")
        ]

        assert leaked == []

    def test_the_built_tree_carries_no_node_toolchain(self, built_plugin: Path) -> None:
        """AC 4: the UI ships as the built bundle alone — no sources, no manifest, no modules.

        The claim the README and ``docs/plugin-structure.md`` both make ("Node is never required,
        not at install and not at runtime") is only true while this holds. A wheel-build hook or a
        stray ``ui/`` copy would make the docs wrong without any other test noticing.

        The name list is wider than "a manifest and its modules" because the sentence
        ``docs/plugin-structure.md`` now commits to is wider — *nothing in the plugin tree
        references Node*. A committed ``vite.config.ts``, ``tsconfig.json`` or ``.nvmrc`` says
        otherwise just as loudly as a ``package.json``, and each one is a toolchain a plugin user
        would have to install to act on.
        """
        node_artifacts = {
            "package.json",
            "package-lock.json",
            "node_modules",
            ".nvmrc",
            "tsconfig.json",
            "tsconfig.app.json",
            "tsconfig.node.json",
            "vite.config.ts",
            "vitest.config.ts",
            "eslint.config.js",
        }

        found = sorted(
            str(entry.relative_to(built_plugin))
            for entry in built_plugin.rglob("*")
            if entry.name in node_artifacts
        )

        assert found == [], f"the built tree carries Node toolchain files: {found}"
        assert [str(entry) for entry in built_plugin.rglob("ui") if entry.is_dir()] == []


class TestTheBundleGuardsFire:
    """``build_plugin.py``'s two SPA aborts, exercised for the first time (story 15-5).

    Both are fault-injected by wrapping ``shutil.copytree`` so the **real** copy runs and the
    bundle is damaged immediately afterwards — the guards then see exactly what a genuine copy
    failure would leave behind, rather than a hand-built stub. Established idiom: the
    ``SERVER_FILES`` abort above monkeypatches the module the same way.
    """

    @staticmethod
    def _copytree_damaging_the_bundle(
        damage: Callable[[Path], None],
    ) -> Callable[..., str | Path]:
        """Wrap ``shutil.copytree`` so *damage* runs against the copied bundle directory.

        **Blast radius, because this is not the same shape as the ``SERVER_FILES`` monkeypatch it
        sits beside.** That one replaces a list on ``build_plugin``; this replaces an attribute of
        the *stdlib* ``shutil`` module object, which ``build_plugin`` merely imported — so for the
        duration of the patch every ``shutil.copytree`` call anywhere in the process is wrapped,
        not just the build's. It is bounded by ``monkeypatch`` (restored at teardown) and by the
        wrapper being a pass-through that only acts when the destination actually contains the
        bundle, which no caller but this build produces. Patching ``build_plugin.shutil`` itself
        would be no narrower: it *is* the stdlib module object.

        Args:
            damage: Callable invoked with the copied ``.../companion/app/static`` directory. Only
                the ``src/`` copy produces that path, so the later per-skill copies pass through
                untouched.

        Returns:
            A drop-in replacement for ``build_plugin.shutil.copytree``.
        """
        real_copytree = shutil.copytree

        def wrapper(src: str | Path, dst: str | Path = "", *args: object, **kwargs: object) -> str:
            # `dst` is accepted positionally *and* by keyword: the build passes it positionally
            # today, and a `copytree(src, dst=...)` refactor must not turn this guard green by
            # quietly never finding the bundle.
            destination = kwargs.pop("dst", dst)
            result = real_copytree(src, destination, *args, **kwargs)  # type: ignore[arg-type]
            bundle = Path(str(destination)) / _BUNDLE_RELATIVE
            if bundle.is_dir():
                damage(bundle)
            return str(result)

        return wrapper

    def test_a_copy_that_lost_the_index_aborts_cleanly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Exit 1 with the rebuild hint — never a traceback, and never a silent UI-less plugin.

        The message is pinned, not just the status. ``build()`` returns ``1`` from **six** places
        (the viewer check, these two, each ``SERVER_FILES`` entry and each missing ``SKILL.md``),
        so an exit code alone cannot say which guard fired — this test would stay green if the SPA
        check were deleted and the build happened to abort one line earlier.
        """
        monkeypatch.setattr(
            build_plugin.shutil,
            "copytree",
            self._copytree_damaging_the_bundle(lambda bundle: (bundle / "index.html").unlink()),
        )

        with caplog.at_level(logging.ERROR, logger=build_plugin.__name__):
            assert build(tmp_path / "plugin") == 1

        message = "\n".join(record.getMessage() for record in caplog.records)
        assert "SPA bundle missing" in message, (
            f"the build aborted, but not through the missing-index guard. Logged: {message!r}"
        )
        assert "index.html" in message
        assert "cd ui && npm run build" in message, (
            "the abort no longer names the command that fixes it — the whole point of failing "
            f"here rather than at the user's browser. Logged: {message!r}"
        )

    def test_a_copy_whose_assets_are_empty_aborts_cleanly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The second guard, reached only *because* the index survived.

        ``index.html`` alone is not the app: a copy that delivered the index and lost the JS/CSS
        would pass the first guard and ship a plugin whose every page renders blank. The message
        is pinned for the same reason as the sibling above, and here it also proves *which* of the
        two SPA guards ran.
        """

        def empty_the_assets(bundle: Path) -> None:
            # rmtree for directories: Vite emitting a nested output folder (fonts/, chunks/) would
            # otherwise make this an IsADirectoryError instead of the empty-assets case, and the
            # guard would never be reached.
            for asset in (bundle / "assets").iterdir():
                if asset.is_dir():
                    shutil.rmtree(asset)
                else:
                    asset.unlink()

        monkeypatch.setattr(
            build_plugin.shutil, "copytree", self._copytree_damaging_the_bundle(empty_the_assets)
        )

        with caplog.at_level(logging.ERROR, logger=build_plugin.__name__):
            assert build(tmp_path / "plugin") == 1

        message = "\n".join(record.getMessage() for record in caplog.records)
        assert "SPA assets missing" in message, (
            f"the build aborted, but not through the empty-assets guard. Logged: {message!r}"
        )
        assert "assets" in message
        assert "cd ui && npm run build" in message, (
            f"the abort no longer names the command that fixes it. Logged: {message!r}"
        )


class TestTheCommittedPairIsIdentical:
    """AC 2: the two committed copies are one artifact, and a hand-edit goes red locally.

    ``tests/unit/companion/test_spa.py::TestThePluginMirror`` compares ``index.html`` and
    ``assets/``; this compares the **whole** tree as a path set, so a file that exists in one copy
    and not the other (``favicon.svg`` today, whatever Vite emits next) cannot slip through. CI's
    rebuild-and-diff would catch it eventually — the point of asserting it here is that nobody
    should need a CI round-trip to learn they hand-edited a generated artifact.
    """

    def test_the_committed_mirror_matches_the_committed_source(self) -> None:
        _assert_bundles_match(
            _MIRRORED_BUNDLE,
            _SOURCE_BUNDLE,
            remedy=(
                "Both copies are generated and neither is ever hand-edited — rebuild with: "
                "uv run python -m scripts.build_plugin, and commit plugin/."
            ),
        )


class TestTheCommittedTreeIsExactlyWhatTheBuildEmits:
    """The gap ``git status --porcelain -- plugin/`` structurally cannot see (review, 2026-08-19).

    ``build()`` cleans only four managed paths — ``server/src``, ``skills/``, ``.claude-plugin/``
    and ``.codex-plugin/`` — and deletes the two root manifests (``build_plugin.py:176-185``).
    ``plugin/server/`` itself is never cleaned, deliberately: a blanket ``rmtree`` chokes on a
    locked ``.venv`` on Windows and leaves the committed tree half-built. The cost is that
    anything committed under ``plugin/server/`` outside ``src/`` **survives every rebuild
    untouched**, so the drift check finds no change and reports none. Drop an entry from
    ``SERVER_FILES`` and the orphaned ``plugin/server/NOTICE`` ships for as long as nobody looks.

    A set comparison is the only shape that catches a file the build no longer emits, because the
    failure is an *absence of change* rather than a change. Reading the committed side through
    ``git ls-files`` rather than a disk walk excludes gitignored runtime cruft (``.venv/``,
    ``.ruff_cache/``, ``*.egg-info/`` — the build preserves them on purpose) by construction
    rather than by an exclusion list that would need maintaining alongside ``.gitignore``.

    This also subsumes the vacuity question for everything else under ``plugin/``: ``skills/`` and
    both clients' manifests are in the compared set, so a plugin committed without them, or one
    carrying a skill the build stopped emitting, fails here too.
    """

    @_needs_git
    @pytest.mark.skipif(
        not (build_plugin.REPO_ROOT / ".git").exists(),
        reason="this assertion is about the repository's own tracked files",
    )
    def test_the_tracked_plugin_files_are_exactly_the_built_ones(self, built_plugin: Path) -> None:
        listing = subprocess.run(
            ["git", "ls-files", "--", "plugin/"],
            cwd=build_plugin.REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        tracked = {line[len("plugin/") :] for line in listing.stdout.splitlines() if line.strip()}
        emitted = {
            path.relative_to(built_plugin).as_posix()
            for path in built_plugin.rglob("*")
            if path.is_file()
        }

        assert tracked, (
            "no file under plugin/ is tracked, so this comparison would pass vacuously — the "
            "committed marketplace source is not committed."
        )
        orphaned, uncommitted = sorted(tracked - emitted), sorted(emitted - tracked)

        assert tracked == emitted, (
            "the committed plugin/ tree is not what a fresh build emits.\n"
            f"  committed but no rebuild emits them: {orphaned}\n"
            f"  emitted but not committed: {uncommitted}\n"
            "Orphans survive because build() cleans only its managed paths; delete them by hand "
            "and commit. Missing files mean the tree was committed without a rebuild: run "
            "uv run python -m scripts.build_plugin."
        )


class TestTheMirroredBundleServes:
    """AC 4: the copy a plugin user installs is the copy the app serves.

    Driven through the real ``install_spa`` mount — the same subclassed ``StaticFiles``, the same
    media-type registration production uses — over the freshly **built** bundle rather than the
    package's own. ``install_spa``'s ``static_dir`` override exists for exactly this.
    """

    async def test_the_built_bundle_serves_its_index_and_its_hashed_script(
        self, built_plugin: Path
    ) -> None:
        bundle = built_plugin / "server" / "src" / _BUNDLE_RELATIVE
        # Read the filename out of the bundle: Vite's hashes rot any literal, and a hard-coded
        # name would decay into asserting a 404. Asserted rather than tuple-unpacked: once code
        # splitting emits a second entry chunk, an unpack fails with an opaque ValueError about
        # arity instead of saying which entry chunk this test now has to choose between — and if
        # the glob found nothing it would say the same unhelpful thing about the empty case.
        entries = sorted((bundle / "assets").glob("index-*.js"))
        assert entries, (
            f"no index-*.js entry chunk in {bundle / 'assets'} — the built bundle carries no "
            f"JavaScript, so the assertions below would be about nothing."
        )
        script = entries[0]
        app = FastAPI()

        install_spa(app, static_dir=bundle)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            index = await client.get("/")
            asset = await client.get(f"/assets/{script.name}")

        assert index.status_code == 200
        assert index.content == (bundle / "index.html").read_bytes()
        assert asset.status_code == 200
        assert asset.content == script.read_bytes()
        # text/javascript, not text/plain: a module script served as text/plain refuses to
        # execute and the page renders blank behind a 200 (see spa.py's mimetypes note).
        assert asset.headers["content-type"].startswith("text/javascript")

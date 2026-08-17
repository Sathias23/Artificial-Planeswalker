"""``src/viewer`` is frozen and the companion never reuses it (AD-15, story 15.1).

Two guards live here. Neither changes behaviour — both turn a property that currently holds
**by coincidence** into one that holds by rule:

* **Freeze pin** — the set of files under ``src/viewer/`` and the set of public symbols each
  module exposes are pinned to what shipped. AD-15 rules the old HTML renderer *frozen, not
  removed*: no new capability lands there, and its removal is deferred to the next minor release
  once the companion app is proven. Adding a capability to a Python package is, in practice,
  adding a module or a public symbol — so the pin fires on the act itself, rather than on a
  reviewer noticing. Today the freeze is written in a docstring; a docstring stops nobody.
* **No-reuse sweep** — no git-tracked companion source (``src/companion/**/*.py``,
  ``ui/index.html``, ``ui/src/**``, ``ui/public/**``) may import ``src.viewer`` or name
  ``template.html`` / ``src/viewer``. AD-15's reason is that *two renderers of one deck would
  diverge*: the companion builds its deck view from the API contract, and lifting the old
  template into it would create a second, silently drifting source of truth for how a deck
  looks. Measured at ``999bacd``, no companion source reuses either — because nobody has
  written the line, not because anything forbade it.

Both guards are **pure functions with thin test callers**, and the file-level scans are
AST/text only: nothing here imports ``src.viewer`` or a companion module, so the guards run
without FastAPI installed and see violations in files no test ever imports.

**Declared residue — stated, not claimed complete.**

1. The freeze pin sees *addition*: a new module, a new public function or class, a new public
   module-level name, a changed ``__all__``. It cannot see a new behaviour grown **inside** an
   existing function body — ``build_view_model`` sprouting a sideboard section changes no
   symbol. That stays a reviewer's judgement, and the docstring in ``src/viewer/__init__.py``
   is what a reviewer is pointed at.
2. The no-reuse sweep scans **git-tracked source**. An un-``git add``ed file is invisible until
   it is staged (git is the file authority every sweep in this repo uses, so ``node_modules``
   and build output cannot make it pass vacuously). The generated bundle under
   ``src/companion/app/static/`` is deliberately out of scope: it is built from exactly the
   ``ui/`` sources this sweep already covers, so scanning it would only re-scan them.
3. A runtime-assembled spelling defeats the sweep — ``importlib.import_module("src." + "viewer")``
   and ``"temp" + "late.html"`` match no pattern here, the same residue
   ``ui/tests/read-only-glass.test.ts`` and ``tests/unit/companion/test_import_boundary.py``
   declare. The answer is review, not a longer pattern: in a codebase where the ordinary
   spelling is a plain import, an assembled one is a review-visible oddity.
"""

import ast
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------------------------
# Repository layout — resolved from __file__, never from the current working directory.
# ---------------------------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
_VIEWER_DIR = REPO_ROOT / "src" / "viewer"
_VIEWER_PREFIX = "src/viewer"

# ---------------------------------------------------------------------------------------------
# The frozen surface (AD-15). Keys are paths relative to src/viewer/, so the same pin runs
# against the real package and against a synthetic copy in tmp_path.
# ---------------------------------------------------------------------------------------------

_FROZEN_MODULES: dict[str, frozenset[str]] = {
    "__init__.py": frozenset(),  # re-exports only; its surface is __all__, pinned below
    "present.py": frozenset({"deck_viewer_path", "present_deck"}),
    "render.py": frozenset({"render_html"}),
    "view_model.py": frozenset(
        {
            "parse_mana_pips",
            "map_pips",
            "classify_color",
            "card_bucket",
            "is_land",
            "pick_art",
            "build_view_model",
        }
    ),
}

# Non-Python members of the frozen package. `template.html` is the file AD-15 forbids the
# companion from reusing; it is pinned here so it cannot be joined by a second template either.
_FROZEN_DATA_FILES = frozenset({"template.html"})

# `src/viewer/__init__.py`'s __all__, verbatim and in order.
_FROZEN_EXPORTS: tuple[str, ...] = (
    "build_view_model",
    "deck_viewer_path",
    "present_deck",
    "render_html",
)

_FREEZE_RULE = (
    "src/viewer is FROZEN (AD-15) — the companion app superseded it and its removal is deferred "
    "to the next minor release once the companion is proven; new deck-view capability belongs in "
    "src/companion and ui/, not here"
)
_FREEZE_FIX = (
    "if this addition is deliberate, it is the wrong package: build it in the companion. If "
    "src/viewer is genuinely being removed, that is a release action — delete the entry from "
    "_FROZEN_MODULES / _FROZEN_DATA_FILES in tests/unit/viewer/test_viewer_freeze.py in the same "
    "change"
)

# ---------------------------------------------------------------------------------------------
# The no-reuse sweep (AD-15). git is the file authority: `git ls-files` decides what is source.
# ---------------------------------------------------------------------------------------------

_COMPANION_PATHSPECS = ("src/companion", "ui/index.html", "ui/src", "ui/public")

# Under src/companion only *.py is companion source — the rest of that tree is the generated
# SPA bundle (residue 2). Under ui/ everything text-shaped is swept; these suffixes are binary
# assets that no `git ls-files` filter would otherwise exclude.
_BINARY_SUFFIXES = frozenset({".woff", ".woff2", ".ttf", ".otf", ".png", ".jpg", ".jpeg", ".ico"})

_BANNED_TEXT: tuple[str, ...] = ("template.html", "src/viewer", "src.viewer")
_VIEWER_PACKAGE = "src.viewer"

_NO_REUSE_RULE = (
    "a companion source must never reuse the frozen viewer or its template.html (AD-15) — two "
    "renderers of one deck would diverge; the companion renders from the API contract"
)

# The one permitted mention, and it is a citation rather than a reuse: two frontend modules
# explain their land-classification rule by pointing at the Python function that established it.
# A TypeScript module cannot import a Python one, so a prose reference carries no coupling. The
# exemption is keyed on this exact citation string and never excuses `template.html`, so a real
# reuse added to either file still fires.
_DOCUMENTED_CITATION = "src/viewer/view_model.py::is_land"
_CITATION_ALLOWED: dict[str, str] = {
    "ui/src/state/deckGroups.ts": "cites the front-face land rule the old view-model established",
    "ui/src/state/deckGroups.test.ts": "the same citation, in that module's own test",
}


# ---------------------------------------------------------------------------------------------
# Guard primitives — pure functions; the tests below are thin callers.
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """A single breach of the freeze or the no-reuse rule.

    Attributes:
        path: Repo-relative POSIX path of the offending file.
        line: 1-based line number, or 0 when the violation is about the file itself.
        symbol: The offending symbol or matched token, as written.
        rule: Which rule fired.
        note: Optional trailing note appended to the rendered message.
    """

    path: str
    line: int
    symbol: str
    rule: str
    note: str = ""

    def __str__(self) -> str:
        message = f"{self.path}:{self.line} — {self.symbol} ({self.rule})"
        return f"{message}; {self.note}" if self.note else message


def _render(violations: Iterable[Violation]) -> str:
    """Render violations one per line for an assertion message."""
    return "\n".join(f"  {violation}" for violation in violations)


def collect_viewer_files(directory: Path) -> dict[str, Path]:
    """Return every file under *directory*, keyed by its directory-relative POSIX path.

    ``__pycache__`` is excluded — it is build output, not package surface.

    Args:
        directory: The viewer package directory (the real one, or a copy in ``tmp_path``).

    Returns:
        A mapping of directory-relative POSIX path to absolute path.

    Raises:
        AssertionError: If the walk finds no files at all — a vacuous scan is a dead guard.
    """
    files = {
        path.relative_to(directory).as_posix(): path
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert files, (
        f"The viewer freeze scan found no files under {directory} — the guard would pass "
        "vacuously. Check the _VIEWER_DIR path constant."
    )
    return files


def public_symbols(source: str, *, filename: str) -> dict[str, int]:
    """Return the module-level public surface of *source*, mapped to its line number.

    A module's public surface is what another module can reach: top-level functions, classes
    and assignments whose name does not start with an underscore. Imports are excluded — a
    re-export is pinned through ``__all__`` instead (see :func:`declared_exports`).

    Args:
        source: Python source text.
        filename: Reported in any SyntaxError.

    Returns:
        A mapping of public name to the 1-based line it is defined on.
    """
    tree = ast.parse(source, filename=filename)
    surface: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if not node.name.startswith("_"):
                surface[node.name] = node.lineno
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    surface[target.id] = node.lineno
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and not node.target.id.startswith("_"):
                surface[node.target.id] = node.lineno
    return surface


def declared_exports(source: str, *, filename: str) -> tuple[tuple[str, ...], int]:
    """Return the ``__all__`` declared in *source*, with the line it sits on.

    Args:
        source: Python source text.
        filename: Reported in any SyntaxError.

    Returns:
        A ``(names, line)`` pair; ``((), 0)`` when the module declares no ``__all__``.
    """
    tree = ast.parse(source, filename=filename)
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            assert isinstance(node, ast.Assign)  # narrowed by the `targets` guard above
            value = ast.literal_eval(node.value)
            return tuple(str(name) for name in value), node.lineno
    return (), 0


def find_freeze_violations(directory: Path) -> list[Violation]:
    """Return every way *directory* differs from the frozen ``src/viewer`` surface (AD-15).

    Both directions are checked. An **addition** is a new capability landing in a package that
    is on its way out. A **removal** is a scheduled release action that must delete the pin's
    entry in the same change, rather than quietly shrinking the package the CHANGELOG still
    promises keeps working.

    Args:
        directory: The viewer package directory to inspect.

    Returns:
        A list of violations, each naming the file (and line, where a symbol has one).
    """
    present = collect_viewer_files(directory)
    expected = set(_FROZEN_MODULES) | set(_FROZEN_DATA_FILES)
    violations: list[Violation] = []

    for rel in sorted(set(present) - expected):
        violations.append(
            Violation(f"{_VIEWER_PREFIX}/{rel}", 0, rel, _FREEZE_RULE, note=_FREEZE_FIX)
        )
    for rel in sorted(expected - set(present)):
        violations.append(
            Violation(
                f"{_VIEWER_PREFIX}/{rel}",
                0,
                rel,
                "the freeze pin still lists this file, which no longer exists",
                note=_FREEZE_FIX,
            )
        )

    for rel, frozen in _FROZEN_MODULES.items():
        path = present.get(rel)
        if path is None:
            continue  # already reported as a missing file
        reported = f"{_VIEWER_PREFIX}/{rel}"
        source = path.read_text(encoding="utf-8-sig")
        surface = public_symbols(source, filename=rel)
        for name in sorted(set(surface) - frozen):
            violations.append(
                Violation(reported, surface[name], name, _FREEZE_RULE, note=_FREEZE_FIX)
            )
        for name in sorted(frozen - set(surface)):
            violations.append(
                Violation(
                    reported,
                    0,
                    name,
                    "the freeze pin still lists this public symbol, which no longer exists",
                    note=_FREEZE_FIX,
                )
            )
        if rel == "__init__.py":
            exports, line = declared_exports(source, filename=rel)
            if exports != _FROZEN_EXPORTS:
                violations.append(
                    Violation(
                        reported,
                        line,
                        f"__all__ = {list(exports)}",
                        _FREEZE_RULE,
                        note=f"the frozen export list is {list(_FROZEN_EXPORTS)}; {_FREEZE_FIX}",
                    )
                )

    return violations


def is_swept(rel_path: str) -> bool:
    """Return True when a git-tracked *rel_path* is companion source the sweep must read.

    Args:
        rel_path: A repo-relative POSIX path as ``git ls-files`` prints it.

    Returns:
        True for ``src/companion/**/*.py`` and every text-shaped file under the swept ``ui/``
        paths; False for the generated bundle and for binary assets.
    """
    if rel_path.startswith("src/companion/"):
        return rel_path.endswith(".py")
    return Path(rel_path).suffix.lower() not in _BINARY_SUFFIXES


def tracked_companion_sources() -> list[str]:
    """Return every git-tracked companion source path the no-reuse sweep covers.

    Returns:
        A sorted list of repo-relative POSIX paths.

    Raises:
        AssertionError: If the pathspecs match nothing — a vacuous sweep is a dead guard.
    """
    completed = subprocess.run(
        ["git", "ls-files", "--", *_COMPANION_PATHSPECS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    swept = sorted(rel for rel in completed.stdout.splitlines() if rel and is_swept(rel))
    assert swept, (
        "The no-reuse sweep matched no companion sources — the guard would pass vacuously. "
        f"Check the _COMPANION_PATHSPECS constant: {list(_COMPANION_PATHSPECS)}"
    )
    return swept


def _resolve_import(module: str | None, level: int, package: str) -> str:
    """Resolve a possibly relative ``from ... import`` target to an absolute dotted path.

    Args:
        module: The ``module`` of an ``ast.ImportFrom`` node (None for ``from . import x``).
        level: The node's ``level`` — 0 for absolute, 1 for ``.``, 2 for ``..``, and so on.
        package: The dotted package of the file containing the import.

    Returns:
        The absolute dotted path the import refers to.

    Raises:
        ValueError: If *level* reaches beyond the top-level package — real Python raises
            ImportError there, so the guard must not launder it into an allowed-looking name.
    """
    if level == 0:
        return module or ""
    parts = package.split(".") if package else []
    if level > len(parts):
        raise ValueError(f"relative import level {level} exceeds the depth of package {package!r}")
    if level > 1:
        parts = parts[: len(parts) - (level - 1)]
    base = ".".join(parts)
    if module:
        return f"{base}.{module}" if base else module
    return base


def _viewer_imports(source: str, *, rel_path: str) -> list[tuple[int, str]]:
    """Return every import of ``src.viewer`` in *source*, as ``(line, dotted target)`` pairs.

    Function-local imports count: a deferred import is still reuse at call time. Relative
    forms are resolved, so ``from ..viewer.render import render_html`` cannot hide.
    """
    package = ".".join(rel_path.split("/")[:-1])
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source, filename=rel_path)):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import(node.module, node.level, package)
            for alias in node.names:
                found.append((node.lineno, f"{base}.{alias.name}" if base else alias.name))
    return [
        (line, dotted)
        for line, dotted in found
        if dotted == _VIEWER_PACKAGE or dotted.startswith(f"{_VIEWER_PACKAGE}.")
    ]


def _is_documented_citation(rel_path: str, token: str, line: str) -> bool:
    """Return True for the one permitted mention: a prose citation in an allow-listed file."""
    return (
        token == "src/viewer"
        and rel_path in _CITATION_ALLOWED
        and _DOCUMENTED_CITATION in line
        and "template.html" not in line
    )


def find_reuse_violations(path: Path, *, rel_path: str) -> list[Violation]:
    """Return every AD-15 reuse of the frozen viewer in the source at *path*.

    Text patterns catch the mention in any language (a TSX file cannot import Python, but it
    can copy ``template.html``); an AST pass over Python files additionally catches the import
    forms plain text misses, such as ``from src import viewer``. A line already reported by the
    text pass is not reported twice.

    Args:
        path: Path to the source file to inspect.
        rel_path: Repo-relative path to report, to derive the package from, and to match
            against the citation allow-list.

    Returns:
        A list of violations, one per offending line, each naming file, line and token.
    """
    # Bytes -> lossy decode: a font or image that slipped past the suffix filter must not crash
    # the sweep, and a banned ASCII token would still be found in whatever did decode.
    text = path.read_bytes().decode("utf-8", errors="replace")
    violations: list[Violation] = []
    reported_lines: set[int] = set()

    for number, line in enumerate(text.splitlines(), start=1):
        for token in _BANNED_TEXT:
            if token in line and not _is_documented_citation(rel_path, token, line):
                violations.append(Violation(rel_path, number, token, _NO_REUSE_RULE))
                reported_lines.add(number)

    if rel_path.endswith(".py"):
        violations += [
            Violation(rel_path, line, dotted, _NO_REUSE_RULE)
            for line, dotted in _viewer_imports(text, rel_path=rel_path)
            if line not in reported_lines
        ]

    return violations


# ---------------------------------------------------------------------------------------------
# The guards, run against the real tree.
# ---------------------------------------------------------------------------------------------


def test_repo_root_is_resolved_from_file_not_cwd() -> None:
    """Both scans anchor on the repo root regardless of the runner's working directory."""
    assert (REPO_ROOT / "pyproject.toml").exists(), f"{REPO_ROOT} is not the repository root"
    assert _VIEWER_DIR.is_dir(), f"{_VIEWER_DIR} is not a directory — the freeze pin is misaimed"


class TestViewerIsFrozen:
    """AD-15: no new capability lands in ``src/viewer``; it is on its way out, not growing."""

    def test_public_surface_is_pinned(self) -> None:
        # Non-vacuity: the pin is only meaningful if it read the real package. Naming the
        # renderer entry point catches a scan pointed at an empty or wrong directory, which
        # collect_viewer_files would otherwise be alone in detecting.
        present = collect_viewer_files(_VIEWER_DIR)
        assert "render.py" in present, (
            f"The freeze scan did not visit src/viewer/render.py — {_VIEWER_DIR} is the wrong path."
        )

        violations = find_freeze_violations(_VIEWER_DIR)

        assert not violations, f"The src/viewer freeze has been broken:\n{_render(violations)}"


class TestCompanionNeverReusesTheViewer:
    """AD-15: one renderer per deck — the companion never reaches for the old one."""

    def test_no_companion_source_reuses_the_viewer(self) -> None:
        sources = tracked_companion_sources()
        # Non-vacuity: name one file from each swept half, so a pathspec that stopped matching
        # (a moved directory, a typo) fails loudly instead of sweeping an empty list forever.
        for expected in ("src/companion/app/routes/decks.py", "ui/src/App.tsx"):
            assert expected in sources, (
                f"The no-reuse sweep did not visit {expected} — the pathspecs are wrong."
            )

        violations = [
            violation
            for rel in sources
            for violation in find_reuse_violations(REPO_ROOT / rel, rel_path=rel)
        ]

        assert not violations, (
            f"A companion source now reaches for the frozen viewer:\n{_render(violations)}"
        )

    def test_every_citation_exemption_is_still_needed(self) -> None:
        """The staleness pin: an exemption nobody uses is a standing permission for a future
        reuse that nobody argued for."""
        stale = []
        for rel in _CITATION_ALLOWED:
            path = REPO_ROOT / rel
            assert path.exists(), (
                f"_CITATION_ALLOWED names {rel!r}, which does not exist — typo, or a moved file "
                "whose exemption did not move with it?"
            )
            if _DOCUMENTED_CITATION not in path.read_text(encoding="utf-8"):
                stale.append(rel)
        assert not stale, (
            f"Exempted file(s) that no longer cite the viewer: {sorted(stale)} — remove the "
            "entry rather than leaving a standing permission nothing uses."
        )


# ---------------------------------------------------------------------------------------------
# Proving the freeze pin fires — a synthetic package in tmp_path, never a violating real file.
#
# The fixture is *generated from the pin's own constants* rather than copied from src/viewer.
# Copying looked simpler and was wrong: planting a violation in the real package to prove the
# whole-tree pin fires would then also fire every case below, so the two halves would be one
# measurement wearing two hats. Generated, the synthetic half answers its own question — "given
# a package that matches the pin exactly, does each planted shape produce exactly one violation
# naming it?" — and cannot drift from the pin, because it *is* the pin.
# ---------------------------------------------------------------------------------------------


def _synthetic_module(rel: str, names: Iterable[str]) -> str:
    """Return minimal source exposing exactly *names* as public callables."""
    body = "".join(f"def {name}():\n    return None\n\n\n" for name in sorted(names))
    if rel == "__init__.py":
        exports = ", ".join(f'"{name}"' for name in _FROZEN_EXPORTS)
        body += f"__all__ = [{exports}]\n"
    return body or "pass\n"


@pytest.fixture
def viewer_copy(tmp_path: Path) -> Path:
    """A synthetic package in ``tmp_path`` matching the frozen surface exactly."""
    destination = tmp_path / "viewer"
    destination.mkdir()
    for rel, names in _FROZEN_MODULES.items():
        (destination / rel).write_text(_synthetic_module(rel, names), encoding="utf-8")
    for rel in _FROZEN_DATA_FILES:
        (destination / rel).write_text("<html>__DECK_JSON__</html>\n", encoding="utf-8")
    return destination


class TestFreezePinDetectsViolations:
    """Every shape of "a capability landed in the frozen package" is proven to fail."""

    def test_a_package_matching_the_pin_is_silent(self, viewer_copy: Path) -> None:
        """The silent half: a package whose surface is exactly the frozen one reports nothing."""
        assert find_freeze_violations(viewer_copy) == []

    def test_a_new_public_function_is_reported(self, viewer_copy: Path) -> None:
        module = viewer_copy / "view_model.py"
        planted = (
            module.read_text(encoding="utf-8")
            + '\n\ndef build_sideboard(deck):\n    """A new capability."""\n    return []\n'
        )  # noqa: E501
        module.write_text(planted, encoding="utf-8")

        violations = find_freeze_violations(viewer_copy)

        assert len(violations) == 1, _render(violations)
        message = str(violations[0])
        assert "src/viewer/view_model.py" in message, message
        assert "build_sideboard" in message, message
        assert "AD-15" in message, message

    def test_a_new_public_class_is_reported(self, viewer_copy: Path) -> None:
        module = viewer_copy / "render.py"
        planted = module.read_text(encoding="utf-8") + "\n\nclass RenderOptions:\n    pass\n"
        module.write_text(planted, encoding="utf-8")

        violations = find_freeze_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["RenderOptions"], _render(violations)

    def test_a_new_public_constant_is_reported(self, viewer_copy: Path) -> None:
        module = viewer_copy / "present.py"
        planted = module.read_text(encoding="utf-8") + '\n\nVIEWER_MODE = "compact"\n'
        module.write_text(planted, encoding="utf-8")

        violations = find_freeze_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["VIEWER_MODE"], _render(violations)

    def test_a_new_module_is_reported(self, viewer_copy: Path) -> None:
        (viewer_copy / "metrics.py").write_text("def collect():\n    return {}\n", encoding="utf-8")

        violations = find_freeze_violations(viewer_copy)

        assert len(violations) == 1, _render(violations)
        assert "src/viewer/metrics.py" in str(violations[0]), str(violations[0])

    def test_a_new_subpackage_is_reported(self, viewer_copy: Path) -> None:
        """A capability hidden one directory down is still a capability."""
        package = viewer_copy / "widgets"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")

        violations = find_freeze_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["widgets/__init__.py"], _render(violations)

    def test_a_second_template_is_reported(self, viewer_copy: Path) -> None:
        (viewer_copy / "template_compact.html").write_text("<html></html>", encoding="utf-8")

        violations = find_freeze_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["template_compact.html"], _render(violations)

    def test_a_widened_all_is_reported(self, viewer_copy: Path) -> None:
        module = viewer_copy / "__init__.py"
        widened = module.read_text(encoding="utf-8").replace(
            '"render_html"]', '"render_html", "render_compact"]'
        )
        module.write_text(widened, encoding="utf-8")

        violations = find_freeze_violations(viewer_copy)

        assert len(violations) == 1, _render(violations)
        assert "render_compact" in str(violations[0]), str(violations[0])

    def test_a_disappearing_module_is_reported_too(self, viewer_copy: Path) -> None:
        """Removal is a release action, not an edit: the pin's entry must go with the file."""
        (viewer_copy / "present.py").unlink()

        violations = find_freeze_violations(viewer_copy)
        messages = [str(violation) for violation in violations]

        assert any("src/viewer/present.py" in message for message in messages), messages
        assert any("no longer exists" in message for message in messages), messages

    def test_a_disappearing_public_function_is_reported_too(self, viewer_copy: Path) -> None:
        module = viewer_copy / "view_model.py"
        source = module.read_text(encoding="utf-8").replace("def is_land(", "def _is_land(")
        module.write_text(source, encoding="utf-8")

        violations = find_freeze_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["is_land"], _render(violations)


# ---------------------------------------------------------------------------------------------
# Proving the no-reuse sweep fires — synthetic sources in tmp_path, never a real file.
# ---------------------------------------------------------------------------------------------

_SRC_IMPORTS_VIEWER = """\
from src.viewer import present_deck
"""

_SRC_IMPORTS_VIEWER_MODULE = """\
import src.viewer.render
"""

_SRC_IMPORTS_VIEWER_AS_ATTRIBUTE = """\
from src import viewer
"""

_SRC_IMPORTS_VIEWER_RELATIVE = """\
from ..viewer.render import render_html
"""

_SRC_FUNCTION_LOCAL_VIEWER_IMPORT = """\
def render(deck):
    from src.viewer.render import render_html

    return render_html(deck)
"""

_SRC_READS_THE_TEMPLATE = """\
from pathlib import Path


def load():
    return Path(__file__).parents[2].joinpath("viewer", "template.html").read_text()
"""

_SRC_TSX_IMPORTS_THE_TEMPLATE = """\
import legacy from '../../../src/viewer/template.html?raw'
"""

_SRC_TS_NAMES_THE_TEMPLATE = """\
export const LEGACY_MARKUP_SOURCE = 'template.html'
"""

_REUSE_VIOLATION_CASES = [
    pytest.param(
        _SRC_IMPORTS_VIEWER,
        "src/companion/app/routes/decks.py",
        1,
        "src.viewer",
        id="python-imports-the-viewer",
    ),
    pytest.param(
        _SRC_IMPORTS_VIEWER_MODULE,
        "src/companion/app/spa.py",
        1,
        "src.viewer",
        id="python-imports-a-viewer-module",
    ),
    pytest.param(
        _SRC_IMPORTS_VIEWER_AS_ATTRIBUTE,
        "src/companion/client.py",
        1,
        "src.viewer",
        id="ast-catches-what-the-text-scan-cannot",
    ),
    pytest.param(
        _SRC_IMPORTS_VIEWER_RELATIVE,
        "src/companion/client.py",
        1,
        "src.viewer.render.render_html",
        id="relative-import-is-resolved-not-skipped",
    ),
    pytest.param(
        _SRC_FUNCTION_LOCAL_VIEWER_IMPORT,
        "src/companion/app/routes/decks.py",
        2,
        "src.viewer",
        id="a-deferred-import-is-still-reuse",
    ),
    pytest.param(
        _SRC_READS_THE_TEMPLATE,
        "src/companion/app/spa.py",
        5,
        "template.html",
        id="python-reads-the-template",
    ),
    pytest.param(
        _SRC_TS_NAMES_THE_TEMPLATE,
        "ui/src/state/deck.ts",
        1,
        "template.html",
        id="frontend-names-the-template",
    ),
]

_SRC_ORDINARY_COMPANION_MODULE = """\
from src.data.repositories import DeckRepository
from src.companion.contracts import DeckSummary


async def go(session):
    return await DeckRepository(session).list_decks()
"""

_SRC_ORDINARY_FRONTEND_MODULE = """\
import { fetchDeck } from '../api/client'

export const load = (id: string) => fetchDeck(id)
"""

_SRC_SERVES_ITS_OWN_INDEX = """\
INDEX = "index.html"
"""

_SRC_DOCUMENTED_CITATION = """\
// The land rule matches src/viewer/view_model.py::is_land — front face only.
export const isLand = (typeLine: string) => typeLine.split('//')[0].includes('Land')
"""

_REUSE_CLEAN_CASES = [
    pytest.param(
        _SRC_ORDINARY_COMPANION_MODULE,
        "src/companion/app/routes/decks.py",
        id="a-companion-module-that-touches-only-its-own-stack",
    ),
    pytest.param(
        _SRC_ORDINARY_FRONTEND_MODULE,
        "ui/src/state/deck.ts",
        id="an-ordinary-frontend-module",
    ),
    pytest.param(
        _SRC_SERVES_ITS_OWN_INDEX,
        "src/companion/app/spa.py",
        id="the-spa-serving-its-own-index-html",
    ),
    pytest.param(
        _SRC_DOCUMENTED_CITATION,
        "ui/src/state/deckGroups.ts",
        id="the-documented-citation-in-an-allow-listed-file",
    ),
]


def _write_source(tmp_path: Path, source: str, name: str = "sample.py") -> Path:
    """Write *source* to a throwaway file in *tmp_path* and return its path."""
    file = tmp_path / name
    file.write_text(source, encoding="utf-8")
    return file


class TestNoReuseSweepDetectsViolations:
    """Every reuse shape is proven to fail, and every permitted form to pass."""

    @pytest.mark.parametrize(("source", "rel", "line", "symbol"), _REUSE_VIOLATION_CASES)
    def test_a_reuse_is_reported(
        self, tmp_path: Path, source: str, rel: str, line: int, symbol: str
    ) -> None:
        violations = find_reuse_violations(_write_source(tmp_path, source), rel_path=rel)

        assert len(violations) == 1, f"expected exactly one violation, got {_render(violations)}"
        message = str(violations[0])
        assert f"{rel}:{line}" in message, message
        assert symbol in message, message
        assert "AD-15" in message, message

    @pytest.mark.parametrize(("source", "rel"), _REUSE_CLEAN_CASES)
    def test_a_permitted_form_is_not_reported(self, tmp_path: Path, source: str, rel: str) -> None:
        assert find_reuse_violations(_write_source(tmp_path, source), rel_path=rel) == []

    def test_a_tsx_import_of_the_template_is_reported(self, tmp_path: Path) -> None:
        """The frontend reuse that matters most: lifting the old markup into the SPA. It names
        both banned tokens on one line, so it is reported twice — deliberately, since a reader
        should see the path *and* the template."""
        rel = "ui/src/components/DeckGrid/DeckGrid.tsx"
        violations = find_reuse_violations(
            _write_source(tmp_path, _SRC_TSX_IMPORTS_THE_TEMPLATE, name="DeckGrid.tsx"),
            rel_path=rel,
        )

        assert {violation.symbol for violation in violations} == {"template.html", "src/viewer"}
        assert all(f"{rel}:1" in str(violation) for violation in violations), _render(violations)

    def test_the_citation_exemption_does_not_excuse_the_template(self, tmp_path: Path) -> None:
        """The allow-list is narrow by construction: it excuses the prose citation and nothing
        else, so an allow-listed file that starts reusing the template still fires."""
        source = _SRC_DOCUMENTED_CITATION + _SRC_TS_NAMES_THE_TEMPLATE
        violations = find_reuse_violations(
            _write_source(tmp_path, source, name="deckGroups.ts"),
            rel_path="ui/src/state/deckGroups.ts",
        )

        assert [violation.symbol for violation in violations] == ["template.html"], _render(
            violations
        )

    def test_the_citation_exemption_is_per_file(self, tmp_path: Path) -> None:
        """A file nobody argued an exemption for cannot borrow one by copying the sentence."""
        violations = find_reuse_violations(
            _write_source(tmp_path, _SRC_DOCUMENTED_CITATION, name="cards.ts"),
            rel_path="ui/src/state/cards.ts",
        )

        assert [violation.symbol for violation in violations] == ["src/viewer"], _render(violations)


class TestScansCannotPassVacuously:
    """An empty or mistyped scan path must fail loudly, not silently pass forever."""

    def test_an_empty_viewer_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AssertionError, match="found no files"):
            collect_viewer_files(tmp_path)

    def test_pycache_is_excluded_from_the_freeze_scan(self, tmp_path: Path) -> None:
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "render.cpython-312.pyc").write_bytes(b"")
        (tmp_path / "render.py").write_text("", encoding="utf-8")

        assert list(collect_viewer_files(tmp_path)) == ["render.py"]

    def test_the_sweep_pathspecs_match_both_halves(self) -> None:
        sources = tracked_companion_sources()
        assert any(rel.startswith("src/companion/") for rel in sources), sources
        assert any(rel.startswith("ui/") for rel in sources), sources

    def test_the_generated_bundle_is_out_of_scope_by_rule(self) -> None:
        """Residue 2, made mechanical: the bundle is skipped because it is built from the
        swept ui/ sources, and this is where that decision is visible."""
        assert not is_swept("src/companion/app/static/assets/index-DJ7dGud2.js")
        assert not is_swept("src/companion/app/static/index.html")
        assert is_swept("src/companion/app/spa.py")
        assert is_swept("ui/index.html")

    def test_binary_assets_are_skipped(self) -> None:
        assert not is_swept("ui/src/assets/fonts/space-grotesk-latin-wght-normal.woff2")
        assert is_swept("ui/public/favicon.svg")

    def test_relative_imports_are_resolved_not_skipped(self) -> None:
        assert _resolve_import("viewer", 2, "src.companion") == "src.viewer"
        assert _resolve_import("render", 1, "src.viewer") == "src.viewer.render"
        assert _resolve_import(None, 1, "src.viewer") == "src.viewer"
        assert _resolve_import("src.viewer", 0, "src.companion") == "src.viewer"

    def test_beyond_top_level_relative_import_raises_not_launders(self) -> None:
        with pytest.raises(ValueError, match="exceeds the depth"):
            _resolve_import("viewer", 6, "src.companion")

    def test_a_binary_file_does_not_crash_the_sweep(self, tmp_path: Path) -> None:
        file = tmp_path / "font.woff2"
        file.write_bytes(b"\x00\x01\xff\xfe wOF2 \x80")

        assert find_reuse_violations(file, rel_path="ui/src/assets/fonts/font.woff2") == []

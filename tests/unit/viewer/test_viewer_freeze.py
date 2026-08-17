"""``src/viewer`` is frozen and the companion never reuses it (AD-15, story 15.1).

Two guards live here. Neither changes behaviour — both turn a property that currently holds
**by coincidence** into one that holds by rule:

* **Freeze pin** — the set of git-tracked files under ``src/viewer/``, the public symbols each
  module defines, the public names each module binds **by import**, and the **bytes of**
  ``template.html`` are pinned to what shipped. AD-15 rules the old HTML renderer *frozen, not
  removed*: no new capability lands there, and its removal is deferred to the next minor release
  once the companion app is proven. Adding a capability to this package means adding a module,
  adding a public symbol, re-exporting one, or editing the template — so the pin fires on the act
  itself, rather than on a reviewer noticing. Today the freeze is written in a docstring; a
  docstring stops nobody.
* **No-reuse sweep** — no git-tracked companion source may import ``src.viewer`` or name
  ``template.html`` / ``src/viewer``. AD-15's reason is that *two renderers of one deck would
  diverge*: the companion builds its deck view from the API contract, and lifting the old
  template into it would create a second, silently drifting source of truth for how a deck
  looks. Measured at ``999bacd``, no companion source reuses either — because nobody has
  written the line, not because anything forbade it.

**Why the template's bytes are pinned and not merely its presence.** ``template.html`` *is* the
renderer. ``render_html`` only substitutes a JSON blob into it; the ~200 lines of inline
JavaScript inside it (``cardHtml``, ``columnsHtml``, ``curveHtml``) are where a deck actually
becomes a page. A pin that checked only presence would have let a whole new panel land in the
frozen package without a single Python symbol changing — while ``src/viewer/__init__.py`` and the
CHANGELOG both tell a reader that "no new behaviour" is enforced. The hash is taken over
CRLF-normalised bytes deliberately: the repo's ``.gitattributes`` scopes its ``-text`` rules to
the SPA bundle only, so ``template.html`` is checked out with CRLF on a Windows box running
``core.autocrlf=true``, and a raw hash would fire there and nowhere else.

**What each half treats as the file authority.** git, in both — ``git ls-files``. For the sweep
that was always true; the freeze pin used to walk the filesystem, which made a ``.DS_Store``, an
editor's ``render.py.orig`` or a stray ``.pyc`` report as *new capability in a frozen package*
on a working copy. The synthetic packages the firing proofs build in ``tmp_path`` are not git
repositories, so those use :func:`walk_viewer_files` instead; the real tree only ever uses
:func:`tracked_viewer_files`.

Both guards are **pure functions with thin test callers**, and the file-level scans are
AST/text only: nothing here imports ``src.viewer`` or a companion module, so the guards run
without FastAPI installed and see violations in files no test ever imports.

**Declared residue — stated, not claimed complete.**

1. The freeze pin sees *addition and edit*: a new module, a new public function, class or
   module-level name, a new public import binding, a changed ``__all__``, or any byte of
   ``template.html``. What it cannot see is a new behaviour grown **inside an existing Python
   function body** — ``build_view_model`` sprouting a sideboard section changes no symbol and
   touches no template. Nor can it see a capability written with names the module already binds,
   or reached through a *private* alias, which is the price of leaving ``as _x`` open as the
   honest way to use a name without offering it. Both stay a reviewer's judgement, and the
   docstring in ``src/viewer/__init__.py`` is what a reviewer is pointed at.
2. The no-reuse sweep scans **git-tracked source**, and that now includes the committed SPA
   bundle under ``src/companion/app/static/``. Correctness-by-construction was the wrong argument
   for excluding it: the bundle is a committed artifact that is *also* mirrored into ``plugin/``
   and shipped to users, and AC-4's subject is the companion's UI "when its assets are
   inspected" — inspection is exactly the thing that does not take the build's word for it. An
   un-``git add``ed file is still invisible until it is staged (git is the file authority every
   sweep in this repo uses, so ``node_modules`` and untracked build output cannot make it pass
   vacuously).
3. ``ui/tests/`` is deliberately **not** swept: a guard test may legitimately discuss the banned
   tokens, which is the same exclusion ``ui/tests/read-only-glass.test.ts`` makes for itself.
   Colocated ``ui/src/**/*.test.ts`` files *are* swept — that is why ``_CITATION_ALLOWED`` has a
   second entry rather than a blanket test exclusion.
4. A runtime-assembled spelling defeats the sweep — ``importlib.import_module("src." + "viewer")``
   and ``"temp" + "late.html"`` match no pattern here, the same residue
   ``ui/tests/read-only-glass.test.ts`` and ``tests/unit/companion/test_import_boundary.py``
   declare. The answer is review, not a longer pattern: in a codebase where the ordinary
   spelling is a plain import, an assembled one is a review-visible oddity.
5. **The sweep sees reference, not duplication.** Every rule here fires on a companion source
   *naming* the viewer. The most natural route to AD-15's stated failure — "two renderers of one
   entity would diverge" — is a developer copy-pasting the template's markup and inline styles
   into a React component, which mentions none of the banned tokens and would sail through.
   Nothing textual can close that; what can is the freeze pin above, which makes the source of
   such a copy visibly immutable, plus review.
"""

import ast
import hashlib
import subprocess
from collections.abc import Iterable, Iterator, Mapping
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
# against the real package and against a synthetic package in tmp_path.
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

# The public names each module binds by IMPORT. A def is not the only way to put a capability
# where another module can reach it: `from src.viewer.render import render_html` in present.py
# makes `viewer.present.render_html` reachable, and one added import line is all a re-export
# costs. public_symbols() deliberately does not see these — an import binding is a different
# kind of surface and deserves its own diagnosis — so they are pinned here instead, and only
# __init__.py's re-exports were pinned (through __all__) before this list existed.
_FROZEN_IMPORTS: dict[str, frozenset[str]] = {
    "__init__.py": frozenset(
        {"build_view_model", "deck_viewer_path", "present_deck", "render_html"}
    ),
    "present.py": frozenset({"Deck", "Path", "render_html", "tempfile", "webbrowser"}),
    "render.py": frozenset({"build_view_model", "Deck", "json", "Path"}),
    "view_model.py": frozenset({"Any", "Card", "Deck", "DeckCard", "re"}),
}

# Non-Python members of the frozen package, pinned by CONTENT (see the module docstring):
# template.html is the renderer, so presence alone would leave the freeze unenforced.
_FROZEN_DATA_FILES: dict[str, str] = {
    "template.html": "679dbb94d7750b749824f86063512022e7bf05445b1c6d4ebbd9ae9b9f64e797",
}

# `src/viewer/__init__.py`'s __all__. Compared by MEMBERSHIP, not order — reordering exports
# adds no capability, and firing on it would hand the reader the wrong diagnosis.
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
_TEMPLATE_RULE = (
    "template.html IS the renderer (its inline JS builds the page), so its bytes are pinned — "
    "editing it is adding behaviour to a frozen package (AD-15)"
)
_IMPORT_RULE = (
    "an import binds a module-level public name, so this is reachable as an attribute of a "
    "frozen module — a re-export is a capability the importing module now offers, and one line "
    "is all it costs (AD-15)"
)
_IMPORT_FIX = (
    "if the name is only used inside this module, import it privately (`import x as _x`, "
    "`from m import n as _n`) and the pin stops caring. If it is deliberately re-exported, it "
    "is the wrong package: build it in the companion. Otherwise update the module's entry in "
    "_FROZEN_IMPORTS in tests/unit/viewer/test_viewer_freeze.py in the same change"
)
_STAR_IMPORT_RULE = (
    "the freeze pin cannot read the names a star import binds, so the module's surface would be "
    "unpinnable — a `from ... import *` in a frozen package hides every future addition upstream "
    "makes (AD-15)"
)

# ---------------------------------------------------------------------------------------------
# The no-reuse sweep (AD-15). git is the file authority: `git ls-files` decides what is source.
# ---------------------------------------------------------------------------------------------

# ui/vite.config.ts, ui/config/ and ui/package.json are here because a BUILD-TIME reuse is wired
# there and nowhere else: a Vite `?raw` import, a copy plugin, or an npm script that pulls
# src/viewer/template.html into the bundle never appears in ui/src/. ui/tests/ is deliberately
# absent (residue 3).
_COMPANION_PATHSPECS = (
    "src/companion",
    "ui/index.html",
    "ui/src",
    "ui/public",
    "ui/config",
    "ui/vite.config.ts",
    "ui/package.json",
)

# One rule for both halves: every tracked text-shaped file is swept, the committed SPA bundle
# included (residue 2). Only genuinely binary assets are skipped — and an unrecognised binary is
# REPORTED rather than skipped (see _UNREADABLE_RULE), so this list cannot silently grow holes.
_BINARY_SUFFIXES = frozenset({".woff", ".woff2", ".ttf", ".otf", ".png", ".jpg", ".jpeg", ".ico"})

_BANNED_TEXT: tuple[str, ...] = ("template.html", "src/viewer", "src.viewer")
_VIEWER_PACKAGE = "src.viewer"

_NO_REUSE_RULE = (
    "a companion source must never reuse the frozen viewer or its template.html (AD-15) — two "
    "renderers of one deck would diverge; the companion renders from the API contract"
)
_NO_REUSE_FIX = (
    "render it from the API contract instead — the companion's own components and endpoints are "
    "the place for deck-view work. If this is a documentation reference rather than a reuse, it "
    "needs an argued entry in _CITATION_ALLOWED in tests/unit/viewer/test_viewer_freeze.py, and "
    "the exemption covers only a comment line carrying the exact citation string"
)
_UNREADABLE_RULE = (
    "the no-reuse sweep could not read this companion source, so it cannot be shown clean (AD-15)"
)
_UNREADABLE_FIX = (
    "if this is a binary asset, add its suffix to _BINARY_SUFFIXES; if it is source, fix the "
    "encoding or the syntax — an unreadable file must not pass as a clean one"
)
_UNRESOLVABLE_RULE = (
    "the sweep cannot resolve this relative import, so it cannot prove it is not src.viewer"
)

# The one permitted mention, and it is a citation rather than a reuse: two frontend modules
# explain their land-classification rule by pointing at the Python function that established it.
# A TypeScript module cannot import a Python one, so a prose reference carries no coupling. The
# exemption is keyed on this exact citation string, applies only on a COMMENT line, and never
# excuses `template.html` — so a real reuse added to either file still fires.
_DOCUMENTED_CITATION = "src/viewer/view_model.py::is_land"
_CITATION_ALLOWED: dict[str, str] = {
    "ui/src/state/deckGroups.ts": "cites the front-face land rule the old view-model established",
    "ui/src/state/deckGroups.test.ts": "the same citation, in that module's own test",
}
_COMMENT_STARTS = ("//", "#", "*", "/*")


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


@dataclass(frozen=True)
class AllDeclaration:
    """What a module says its ``__all__`` is, and every way it says it.

    Attributes:
        found: True when an ``__all__`` assignment exists at all.
        names: The declared names, or None when the value is not a literal the pin can read.
        line: 1-based line of the assignment; 0 when absent.
        mutations: ``(line, spelling)`` for every ``__all__ +=`` / ``.append`` / ``.extend``,
            which would widen the export surface past whatever the literal says.
    """

    found: bool
    names: tuple[str, ...] | None
    line: int
    mutations: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class ImportScan:
    """Every ``src.viewer`` import in a module, plus the imports the guard could not resolve.

    Attributes:
        viewer_targets: ``(line, dotted target)`` for each import of ``src.viewer``.
        unresolvable: ``(line, spelling)`` for each relative import reaching above the
            top-level package — real Python would raise ImportError, and the guard must say so
            rather than quietly treat it as "not the viewer".
    """

    viewer_targets: tuple[tuple[int, str], ...]
    unresolvable: tuple[tuple[int, str], ...]


def _render(violations: Iterable[Violation]) -> str:
    """Render violations one per line for an assertion message."""
    return "\n".join(f"  {violation}" for violation in violations)


def hash_bytes(data: bytes) -> str:
    """Return the sha256 of *data* with CRLF normalised to LF.

    Normalisation is not cosmetic: ``template.html`` carries no ``.gitattributes`` rule, so a
    Windows checkout under ``core.autocrlf=true`` rewrites every line ending and a raw hash
    would fire there and nowhere else.
    """
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def content_hash(path: Path) -> str:
    """Return the CRLF-normalised sha256 of the file at *path*."""
    return hash_bytes(path.read_bytes())


def _git_tracked(*pathspecs: str) -> list[str]:
    """Return every git-tracked path matching *pathspecs*, repo-relative and POSIX.

    ``-z`` with ``core.quotePath=false`` so a path containing a space, a quote or a non-ASCII
    character comes back as raw bytes rather than a C-quoted spelling that would then miss on
    disk. A git that cannot run is a **named** guard failure, not an opaque CalledProcessError:
    a non-git export or a missing binary should tell the reader what the guard needed.
    """
    command = ["git", "-c", "core.quotePath=false", "ls-files", "-z", "--", *pathspecs]
    try:
        completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, check=False)
    except OSError as error:  # pragma: no cover - a machine with no git binary
        pytest.fail(
            f"The AD-15 guards use `git ls-files` as their file authority, and git could not be "
            f"run in {REPO_ROOT}: {error}"
        )
    if completed.returncode != 0:
        pytest.fail(
            f"`{' '.join(command)}` failed with exit {completed.returncode} in {REPO_ROOT} — the "
            f"AD-15 guards need a git working tree to know what is source. "
            f"stderr: {completed.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return sorted(entry for entry in completed.stdout.decode("utf-8").split("\0") if entry)


def tracked_viewer_files() -> dict[str, Path]:
    """Return every git-tracked file under ``src/viewer/``, keyed by package-relative path.

    Returns:
        A mapping of ``src/viewer``-relative POSIX path to absolute path. A tracked path that
        is absent from the working tree (staged deletion, sparse checkout) is skipped rather
        than crashing the pin.

    Raises:
        AssertionError: If git tracks nothing there — a vacuous scan is a dead guard.
    """
    prefix = f"{_VIEWER_PREFIX}/"
    files = {
        rel[len(prefix) :]: REPO_ROOT / rel
        for rel in _git_tracked(_VIEWER_PREFIX)
        if rel.startswith(prefix) and (REPO_ROOT / rel).is_file()
    }
    assert files, (
        f"The viewer freeze scan found no git-tracked files under {_VIEWER_PREFIX} — the guard "
        "would pass vacuously. Check the _VIEWER_PREFIX path constant."
    )
    return files


def walk_viewer_files(directory: Path) -> dict[str, Path]:
    """Return every file under *directory*, keyed by its directory-relative POSIX path.

    The filesystem twin of :func:`tracked_viewer_files`, for the synthetic packages the firing
    proofs build in ``tmp_path`` — those are not git repositories, so git cannot be the
    authority there. ``__pycache__`` is excluded; it is build output, not package surface.

    Args:
        directory: A synthetic viewer package.

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
        "vacuously. Check the path it was handed."
    )
    return files


def _assigned_names(target: ast.expr) -> list[str]:
    """Return every plain name bound by an assignment *target*.

    Tuple and list targets are unpacked (``A, B = _load()`` binds two module-level names);
    attribute and subscript targets bind nothing at module scope and yield nothing.
    """
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Tuple | ast.List):
        return [name for element in target.elts for name in _assigned_names(element)]
    if isinstance(target, ast.Starred):
        return _assigned_names(target.value)
    return []


def _module_scope_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Yield every node of *node* that executes at module scope.

    The walk descends into module-level ``if`` / ``try`` / ``with`` / loop bodies — a capability
    added behind ``if sys.platform == "win32":`` is still a capability — but never into a
    function or class body, whose locals, methods and imports are not module surface.

    Args:
        node: The tree, or any node, to walk from.

    Yields:
        Each descendant node that runs when the module is imported.
    """
    for child in ast.iter_child_nodes(node):
        yield child
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue  # a def's body is not module surface
        yield from _module_scope_nodes(child)


def public_symbols(source: str, *, filename: str) -> dict[str, int]:
    """Return the module-level public surface *source* defines, mapped to its line number.

    A module's public surface is what another module can reach: functions, classes and
    assignments that execute at import time and whose name does not start with an underscore.
    Imports are excluded here and pinned by :func:`imported_symbols` instead — both are module
    surface, but "a capability was written in this package" and "a capability was re-exported
    from it" are different acts, and each gets the fix note that answers it.

    Args:
        source: Python source text.
        filename: Reported in any SyntaxError.

    Returns:
        A mapping of public name to the 1-based line it is defined on.
    """
    surface: dict[str, int] = {}
    for node in _module_scope_nodes(ast.parse(source, filename=filename)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if not node.name.startswith("_"):
                surface.setdefault(node.name, node.lineno)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for name in _assigned_names(target):
                    if not name.startswith("_"):
                        surface.setdefault(name, node.lineno)
        elif isinstance(node, ast.AnnAssign):
            for name in _assigned_names(node.target):
                if not name.startswith("_"):
                    surface.setdefault(name, node.lineno)
    return surface


def imported_symbols(source: str, *, filename: str) -> dict[str, int]:
    """Return the public names *source* binds by import, mapped to their line number.

    An import is an assignment with different syntax: ``from src.viewer.render import
    render_html`` in ``present.py`` puts ``render_html`` on ``present``, where any caller can
    reach it. Only what the statement actually *binds* counts — ``import a.b`` binds ``a``,
    ``import a.b as c`` binds ``c``, and an ``as _x`` alias is private and therefore invisible
    here, which is also the escape hatch for a module that needs a name without offering it.

    A star import binds names this scan cannot know, so it is reported as the literal ``"*"``
    rather than silently contributing nothing.

    Args:
        source: Python source text.
        filename: Reported in any SyntaxError.

    Returns:
        A mapping of public bound name to the 1-based line that binds it.
    """
    bound: dict[str, int] = {}
    for node in _module_scope_nodes(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # `import a.b` binds the ROOT package `a`, not `a.b`.
                name = alias.asname or alias.name.split(".")[0]
                if not name.startswith("_"):
                    bound.setdefault(name, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if not name.startswith("_"):
                    bound.setdefault(name, node.lineno)
    return bound


def declared_exports(source: str, *, filename: str) -> AllDeclaration:
    """Return what *source* declares as ``__all__``, including non-literal and mutated forms.

    ``__all__`` is not always a literal list. ``__all__ = _BASE + ["x"]`` cannot be read by
    ``ast.literal_eval``, and ``__all__ += [...]`` / ``.append`` / ``.extend`` widen the surface
    after the literal is written. Both are reported as violations by the caller rather than
    raising out of the guard — a pin that crashes on an unusual spelling is a pin that gets
    deleted.

    Args:
        source: Python source text.
        filename: Reported in any SyntaxError.

    Returns:
        An :class:`AllDeclaration` describing the declaration and any mutation of it.
    """
    tree = ast.parse(source, filename=filename)
    found = False
    names: tuple[str, ...] | None = None
    line = 0
    mutations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]

        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
            found, line = True, node.lineno
            try:
                names = tuple(str(name) for name in ast.literal_eval(value)) if value else None
            except (ValueError, TypeError):
                names = None  # a computed __all__ — reported, never guessed at
            continue

        if isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                mutations.append((node.lineno, "__all__ +="))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if isinstance(receiver, ast.Name) and receiver.id == "__all__":
                mutations.append((node.lineno, f"__all__.{node.func.attr}(...)"))

    return AllDeclaration(found=found, names=names, line=line, mutations=tuple(mutations))


def _import_violations(reported: str, source: str, rel: str) -> list[Violation]:
    """Return every way *rel*'s public import bindings differ from the frozen set.

    Both directions again, and for the same reason as the symbol pin: an added binding is a name
    the frozen module now offers, and a removed one means the pin is describing a module that no
    longer exists.

    Args:
        reported: The path to name in each violation.
        source: The module's source text.
        rel: The module's package-relative path — its key in :data:`_FROZEN_IMPORTS`.

    Returns:
        A list of violations, each naming the bound name and the line that binds it.
    """
    bound = imported_symbols(source, filename=rel)
    frozen = _FROZEN_IMPORTS.get(rel, frozenset())
    violations: list[Violation] = []

    if "*" in bound:
        violations.append(
            Violation(reported, bound.pop("*"), "import *", _STAR_IMPORT_RULE, note=_IMPORT_FIX)
        )
    for name in sorted(set(bound) - frozen):
        violations.append(Violation(reported, bound[name], name, _IMPORT_RULE, note=_IMPORT_FIX))
    for name in sorted(frozen - set(bound)):
        violations.append(
            Violation(
                reported,
                0,
                name,
                "the freeze pin still lists this import binding, which no longer exists",
                note=_IMPORT_FIX,
            )
        )
    return violations


def _export_violations(reported: str, source: str, rel: str) -> list[Violation]:
    """Return every ``__all__`` breach in the frozen package initializer."""
    declaration = declared_exports(source, filename=rel)
    violations: list[Violation] = []

    if not declaration.found:
        return [
            Violation(
                reported,
                0,
                "__all__",
                "the frozen package initializer no longer declares __all__",
                note=_FREEZE_FIX,
            )
        ]
    if declaration.names is None:
        violations.append(
            Violation(
                reported,
                declaration.line,
                "__all__ (not a literal)",
                "the freeze pin cannot read a computed __all__, so the export surface would be "
                "unpinned",
                note=_FREEZE_FIX,
            )
        )
    elif set(declaration.names) != set(_FROZEN_EXPORTS):
        added = sorted(set(declaration.names) - set(_FROZEN_EXPORTS))
        removed = sorted(set(_FROZEN_EXPORTS) - set(declaration.names))
        violations.append(
            Violation(
                reported,
                declaration.line,
                f"__all__ added={added} removed={removed}",
                _FREEZE_RULE,
                note=f"the frozen export list is {list(_FROZEN_EXPORTS)}; {_FREEZE_FIX}",
            )
        )

    violations += [
        Violation(
            reported,
            mutation_line,
            spelling,
            "__all__ is mutated after it is declared, which widens the export surface past the "
            "pinned literal",
            note=_FREEZE_FIX,
        )
        for mutation_line, spelling in declaration.mutations
    ]
    return violations


def find_freeze_violations(
    files: Mapping[str, Path], *, data_hashes: Mapping[str, str] = _FROZEN_DATA_FILES
) -> list[Violation]:
    """Return every way *files* differs from the frozen ``src/viewer`` surface (AD-15).

    Both directions are checked. An **addition** is a new capability landing in a package that
    is on its way out. A **removal** is a scheduled release action that must delete the pin's
    entry in the same change, rather than quietly shrinking the package the CHANGELOG still
    promises keeps working.

    Args:
        files: The package's files, keyed by package-relative POSIX path — from
            :func:`tracked_viewer_files` for the real tree, :func:`walk_viewer_files` for a
            synthetic one.
        data_hashes: Expected CRLF-normalised sha256 per non-Python file. Injected so a
            synthetic package can be pinned to its own content without borrowing the real
            template's bytes, which would re-couple the firing proofs to the real tree.

    Returns:
        A list of violations, each naming the file (and line, where a symbol has one).
    """
    expected = set(_FROZEN_MODULES) | set(data_hashes)
    violations: list[Violation] = []

    for rel in sorted(set(files) - expected):
        violations.append(
            Violation(f"{_VIEWER_PREFIX}/{rel}", 0, rel, _FREEZE_RULE, note=_FREEZE_FIX)
        )
    for rel in sorted(expected - set(files)):
        violations.append(
            Violation(
                f"{_VIEWER_PREFIX}/{rel}",
                0,
                rel,
                "the freeze pin still lists this file, which no longer exists",
                note=_FREEZE_FIX,
            )
        )

    for rel in sorted(data_hashes):
        path = files.get(rel)
        if path is None:
            continue  # already reported as a missing file
        actual = content_hash(path)
        if actual != data_hashes[rel]:
            violations.append(
                Violation(
                    f"{_VIEWER_PREFIX}/{rel}",
                    0,
                    f"{rel} content changed (sha256 {actual[:12]}, pinned {data_hashes[rel][:12]})",
                    _TEMPLATE_RULE,
                    note=_FREEZE_FIX,
                )
            )

    for rel, frozen in _FROZEN_MODULES.items():
        path = files.get(rel)
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
        violations += _import_violations(reported, source, rel)
        if rel == "__init__.py":
            violations += _export_violations(reported, source, rel)

    return violations


def is_swept(rel_path: str) -> bool:
    """Return True when a git-tracked *rel_path* is companion source the sweep must read.

    One rule for the whole swept set, backend and frontend alike: everything text-shaped is
    read. The committed SPA bundle under ``src/companion/app/static/`` is included — it is a
    shipped, mirrored artifact, and "it is built from sources we already scan" is an argument
    inspection exists to not have to take on faith. A backend template or fixture that is not
    ``*.py`` is therefore swept too, rather than escaping on a suffix.

    Args:
        rel_path: A repo-relative POSIX path as ``git ls-files`` prints it.

    Returns:
        True for every tracked file except recognised binary assets.
    """
    return Path(rel_path).suffix.lower() not in _BINARY_SUFFIXES


def tracked_companion_sources() -> list[str]:
    """Return every git-tracked companion source path the no-reuse sweep covers.

    Returns:
        A sorted list of repo-relative POSIX paths that exist in the working tree.

    Raises:
        AssertionError: If the pathspecs match nothing — a vacuous sweep is a dead guard.
    """
    tracked = [rel for rel in _git_tracked(*_COMPANION_PATHSPECS) if is_swept(rel)]
    assert tracked, (
        "The no-reuse sweep matched no companion sources — the guard would pass vacuously. "
        f"Check the _COMPANION_PATHSPECS constant: {list(_COMPANION_PATHSPECS)}"
    )
    # A tracked path can be absent from the working tree (staged deletion, sparse checkout);
    # skip it rather than crashing the sweep on read. The assertion above already proved the
    # pathspecs are live, so this cannot empty the sweep silently.
    return [rel for rel in tracked if (REPO_ROOT / rel).is_file()]


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
            Callers contain this and report it; it never escapes the sweep.
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


def _viewer_imports(source: str, *, rel_path: str) -> ImportScan:
    """Scan *source* for imports of ``src.viewer``, containing unresolvable relative forms.

    Function-local imports count: a deferred import is still reuse at call time. Relative forms
    are resolved, so ``from ..viewer.render import render_html`` cannot hide.

    Raises:
        SyntaxError: If *source* is not parsable Python. The caller reports it as a violation.
    """
    package = ".".join(rel_path.split("/")[:-1])
    found: list[tuple[int, str]] = []
    unresolvable: list[tuple[int, str]] = []

    for node in ast.walk(ast.parse(source, filename=rel_path)):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            try:
                base = _resolve_import(node.module, node.level, package)
            except ValueError:
                unresolvable.append((node.lineno, f"from {'.' * node.level}{node.module or ''}"))
                continue
            for alias in node.names:
                found.append((node.lineno, f"{base}.{alias.name}" if base else alias.name))

    return ImportScan(
        viewer_targets=tuple(
            (line, dotted)
            for line, dotted in found
            if dotted == _VIEWER_PACKAGE or dotted.startswith(f"{_VIEWER_PACKAGE}.")
        ),
        unresolvable=tuple(unresolvable),
    )


def _is_comment_line(line: str) -> bool:
    """Return True when *line* is a comment in any of the swept languages."""
    return line.lstrip().startswith(_COMMENT_STARTS)


def _is_documented_citation(rel_path: str, token: str, line: str) -> bool:
    """Return True for the one permitted mention: a prose citation on a comment line.

    The comment requirement is load-bearing rather than decorative. Without it the exemption is
    line-scoped, so ``import legacy from '../src/viewer/render' // src/viewer/view_model.py::
    is_land`` would be excused — and TypeScript gets no AST pass, so nothing else would catch
    it. Both real citation sites are comments, so the requirement costs nothing.
    """
    return (
        token == "src/viewer"
        and rel_path in _CITATION_ALLOWED
        and _DOCUMENTED_CITATION in line
        and "template.html" not in line
        and _is_comment_line(line)
    )


def find_reuse_violations(path: Path, *, rel_path: str) -> list[Violation]:
    """Return every AD-15 reuse of the frozen viewer in the source at *path*.

    Text patterns catch the mention in any language (a TSX file cannot import Python, but it
    can copy ``template.html``); an AST pass over Python files additionally catches the import
    forms plain text misses, such as ``from src import viewer``. A line already reported by the
    text pass is not reported twice.

    Nothing here raises. A file that cannot be decoded or parsed is **reported** rather than
    taking the whole guard down with it: one unreadable file must not be able to hide every
    other file's verdict.

    Args:
        path: Path to the source file to inspect.
        rel_path: Repo-relative path to report, to derive the package from, and to match
            against the citation allow-list.

    Returns:
        A list of violations, one per offending line, each naming file, line and token.
    """
    try:
        # utf-8-sig, not utf-8: a BOM-saved source is scanned rather than becoming an
        # "invalid non-printable character U+FEFF" SyntaxError, the same reason the sibling
        # guard in tests/unit/companion/test_import_boundary.py gives.
        text = path.read_bytes().decode("utf-8-sig")
    except OSError as error:
        return [Violation(rel_path, 0, f"unreadable ({error})", _UNREADABLE_RULE, _UNREADABLE_FIX)]
    except UnicodeDecodeError:
        return [Violation(rel_path, 0, "not valid UTF-8", _UNREADABLE_RULE, _UNREADABLE_FIX)]

    violations: list[Violation] = []
    reported_lines: set[int] = set()

    for number, line in enumerate(text.splitlines(), start=1):
        for token in _BANNED_TEXT:
            if token in line and not _is_documented_citation(rel_path, token, line):
                violations.append(Violation(rel_path, number, token, _NO_REUSE_RULE, _NO_REUSE_FIX))
                reported_lines.add(number)

    if rel_path.endswith(".py"):
        try:
            scan = _viewer_imports(text, rel_path=rel_path)
        except SyntaxError as error:
            return [
                *violations,
                Violation(
                    rel_path,
                    error.lineno or 0,
                    "unparsable Python",
                    _UNREADABLE_RULE,
                    _UNREADABLE_FIX,
                ),
            ]
        violations += [
            Violation(rel_path, line, dotted, _NO_REUSE_RULE, _NO_REUSE_FIX)
            for line, dotted in scan.viewer_targets
            if line not in reported_lines
        ]
        violations += [
            Violation(rel_path, line, spelling, _UNRESOLVABLE_RULE, _UNREADABLE_FIX)
            for line, spelling in scan.unresolvable
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
        # renderer entry point and the template catches a scan pointed at the wrong prefix,
        # which tracked_viewer_files would otherwise be alone in detecting.
        files = tracked_viewer_files()
        for expected in ("render.py", "template.html"):
            assert expected in files, (
                f"The freeze scan did not visit {_VIEWER_PREFIX}/{expected} — the scan path or "
                "the git pathspec is wrong."
            )

        violations = find_freeze_violations(files)

        assert not violations, f"The src/viewer freeze has been broken:\n{_render(violations)}"


class TestCompanionNeverReusesTheViewer:
    """AD-15: one renderer per deck — the companion never reaches for the old one."""

    def test_no_companion_source_reuses_the_viewer(self) -> None:
        sources = tracked_companion_sources()
        # Non-vacuity: name one file from each swept half — backend, frontend, the committed
        # bundle and the build configuration — so a pathspec that stopped matching (a moved
        # directory, a typo) fails loudly instead of sweeping a short list forever.
        for expected in (
            "src/companion/app/routes/decks.py",
            "ui/src/App.tsx",
            "src/companion/app/static/index.html",
            "ui/vite.config.ts",
        ):
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

    def test_every_real_citation_sits_on_a_comment_line(self) -> None:
        """The exemption's precondition, measured against the real files rather than assumed:
        if either citation ever moved onto a code line, the narrowing in
        :func:`_is_documented_citation` would start firing and the reader should learn it here,
        where the reason is written down."""
        for rel in _CITATION_ALLOWED:
            lines = (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()
            citing = [line for line in lines if _DOCUMENTED_CITATION in line]
            assert citing, f"{rel} no longer cites the viewer at all"
            for line in citing:
                assert _is_comment_line(line), (
                    f"{rel} cites the viewer outside a comment: {line.strip()!r} — the exemption "
                    "covers comments only, so this is a reuse-shaped mention."
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

_SYNTHETIC_TEMPLATE = "<html><script>renderDeck(__DECK_JSON__)</script></html>\n"
_SYNTHETIC_DATA_HASHES = {
    rel: hash_bytes(_SYNTHETIC_TEMPLATE.encode("utf-8")) for rel in _FROZEN_DATA_FILES
}


def _synthetic_module(rel: str, names: Iterable[str]) -> str:
    """Return minimal source binding exactly the pinned surface of *rel*.

    *names* become public callables; the module's pinned import bindings become plain ``import``
    statements. Nothing here is ever executed — every scan is AST-only — so binding ``Path`` with
    ``import Path`` is a legitimate stand-in for the real ``from pathlib import Path``, and it
    keeps the fixture generated from the pin rather than copied from ``src/viewer``.
    """
    body = "".join(f"import {name}\n" for name in sorted(_FROZEN_IMPORTS.get(rel, ())))
    if body:
        body += "\n\n"
    body += "".join(f"def {name}():\n    return None\n\n\n" for name in sorted(names))
    if rel == "__init__.py":
        exports = ", ".join(f'"{name}"' for name in _FROZEN_EXPORTS)
        body += f"__all__ = [{exports}]\n"
    return body or "pass\n"


def _synthetic_violations(directory: Path) -> list[Violation]:
    """Run the freeze pin over a synthetic package, pinned to the synthetic template."""
    return find_freeze_violations(walk_viewer_files(directory), data_hashes=_SYNTHETIC_DATA_HASHES)


@pytest.fixture
def viewer_copy(tmp_path: Path) -> Path:
    """A synthetic package in ``tmp_path`` matching the frozen surface exactly."""
    destination = tmp_path / "viewer"
    destination.mkdir()
    for rel, names in _FROZEN_MODULES.items():
        (destination / rel).write_text(_synthetic_module(rel, names), encoding="utf-8")
    for rel in _FROZEN_DATA_FILES:
        (destination / rel).write_text(_SYNTHETIC_TEMPLATE, encoding="utf-8")
    return destination


class TestFreezePinDetectsViolations:
    """Every shape of "a capability landed in the frozen package" is proven to fail."""

    def test_a_package_matching_the_pin_is_silent(self, viewer_copy: Path) -> None:
        """The silent half: a package whose surface is exactly the frozen one reports nothing."""
        assert _synthetic_violations(viewer_copy) == []

    def test_a_new_public_function_is_reported(self, viewer_copy: Path) -> None:
        module = viewer_copy / "view_model.py"
        planted = (
            module.read_text(encoding="utf-8")
            + '\n\ndef build_sideboard(deck):\n    """A new capability."""\n    return []\n'
        )
        module.write_text(planted, encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert len(violations) == 1, _render(violations)
        message = str(violations[0])
        assert "src/viewer/view_model.py" in message, message
        assert "build_sideboard" in message, message
        assert "AD-15" in message, message

    def test_a_new_public_class_is_reported(self, viewer_copy: Path) -> None:
        module = viewer_copy / "render.py"
        planted = module.read_text(encoding="utf-8") + "\n\nclass RenderOptions:\n    pass\n"
        module.write_text(planted, encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["RenderOptions"], _render(violations)

    def test_a_new_public_constant_is_reported(self, viewer_copy: Path) -> None:
        module = viewer_copy / "present.py"
        planted = module.read_text(encoding="utf-8") + '\n\nVIEWER_MODE = "compact"\n'
        module.write_text(planted, encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["VIEWER_MODE"], _render(violations)

    def test_a_capability_behind_a_module_level_branch_is_reported(self, viewer_copy: Path) -> None:
        """A def nested in a module-level ``if``/``try`` executes at import and is reachable —
        walking only ``tree.body`` would have missed it, which is a one-line way to add a
        capability to a frozen package."""
        module = viewer_copy / "render.py"
        planted = (
            module.read_text(encoding="utf-8")
            # Aliased private deliberately: a bare `import sys` is itself a new public binding,
            # which the import pin would report alongside the def and blur what this measures.
            + "\n\nimport sys as _sys\n\nif _sys.version_info >= (3, 12):\n\n"
            "    def render_compact(deck):\n        return None\n"
        )
        module.write_text(planted, encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["render_compact"], _render(violations)

    def test_a_tuple_unpacked_public_name_is_reported(self, viewer_copy: Path) -> None:
        """``A, B = _load()`` binds two module-level names; only walking Assign targets that are
        bare Names would have seen neither."""
        module = viewer_copy / "present.py"
        planted = module.read_text(encoding="utf-8") + "\n\nWIDTH, HEIGHT = (720, 1080)\n"
        module.write_text(planted, encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert sorted(v.symbol for v in violations) == ["HEIGHT", "WIDTH"], _render(violations)

    def test_a_new_module_is_reported(self, viewer_copy: Path) -> None:
        (viewer_copy / "metrics.py").write_text("def collect():\n    return {}\n", encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert len(violations) == 1, _render(violations)
        assert "src/viewer/metrics.py" in str(violations[0]), str(violations[0])

    def test_a_new_subpackage_is_reported(self, viewer_copy: Path) -> None:
        """A capability hidden one directory down is still a capability."""
        package = viewer_copy / "widgets"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["widgets/__init__.py"], _render(violations)

    def test_a_second_template_is_reported(self, viewer_copy: Path) -> None:
        (viewer_copy / "template_compact.html").write_text("<html></html>", encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["template_compact.html"], _render(violations)

    def test_an_edited_template_is_reported(self, viewer_copy: Path) -> None:
        """The renderer's own file. A panel added to the template's inline JS changes no Python
        symbol at all, so before the content pin this was the freeze's blind spot."""
        template = viewer_copy / "template.html"
        template.write_text(
            template.read_text(encoding="utf-8")
            + "<script>function sideboardPanel(){return 1}</script>\n",
            encoding="utf-8",
        )

        violations = _synthetic_violations(viewer_copy)

        assert len(violations) == 1, _render(violations)
        message = str(violations[0])
        assert "src/viewer/template.html" in message, message
        assert "content changed" in message, message
        assert "AD-15" in message, message

    def test_a_line_ending_rewrite_is_not_reported(self, viewer_copy: Path) -> None:
        """A CRLF checkout on Windows must not read as an edit — the pin hashes normalised
        bytes, because template.html carries no .gitattributes rule of its own."""
        template = viewer_copy / "template.html"
        template.write_bytes(template.read_bytes().replace(b"\n", b"\r\n"))

        assert _synthetic_violations(viewer_copy) == []

    def test_a_widened_all_is_reported(self, viewer_copy: Path) -> None:
        module = viewer_copy / "__init__.py"
        widened = module.read_text(encoding="utf-8").replace(
            '"render_html"]', '"render_html", "render_compact"]'
        )
        module.write_text(widened, encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert len(violations) == 1, _render(violations)
        assert "render_compact" in str(violations[0]), str(violations[0])

    def test_a_reordered_all_is_not_reported(self, viewer_copy: Path) -> None:
        """Membership, not order: reordering exports adds no capability, and firing on it would
        hand the reader "new deck-view capability belongs in src/companion" — a wrong
        diagnosis is worse than none."""
        module = viewer_copy / "__init__.py"
        exports = ", ".join(f'"{name}"' for name in reversed(_FROZEN_EXPORTS))
        source = module.read_text(encoding="utf-8")
        module.write_text(
            source[: source.index("__all__")] + f"__all__ = [{exports}]\n", encoding="utf-8"
        )

        assert _synthetic_violations(viewer_copy) == []

    def test_a_computed_all_is_reported_not_crashed(self, viewer_copy: Path) -> None:
        """``ast.literal_eval`` raises on a computed ``__all__``; the pin must report it as an
        unpinnable export surface rather than take the suite down with a ValueError."""
        module = viewer_copy / "__init__.py"
        source = module.read_text(encoding="utf-8")
        module.write_text(
            source[: source.index("__all__")] + '__all__ = _BASE + ["render_html"]\n',
            encoding="utf-8",
        )

        violations = _synthetic_violations(viewer_copy)

        assert len(violations) == 1, _render(violations)
        assert "not a literal" in str(violations[0]), str(violations[0])

    def test_a_mutated_all_is_reported(self, viewer_copy: Path) -> None:
        """``__all__ += [...]`` and ``__all__.append(...)`` widen the surface after the literal
        the pin read, so the literal alone is not the whole story."""
        module = viewer_copy / "__init__.py"
        source = module.read_text(encoding="utf-8")
        module.write_text(source + '__all__ += ["render_compact"]\n', encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["__all__ +="], _render(violations)

    def test_an_appended_all_is_reported(self, viewer_copy: Path) -> None:
        module = viewer_copy / "__init__.py"
        source = module.read_text(encoding="utf-8")
        module.write_text(source + '__all__.append("render_compact")\n', encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["__all__.append(...)"], _render(violations)

    def test_a_re_exported_capability_is_reported(self, viewer_copy: Path) -> None:
        """The blind spot this pin closes: a capability can land on a frozen module without a
        single ``def`` being written, because an import binds a public name too. One line in
        ``present.py`` and ``viewer.present.render_compact`` is a callable the package offers."""
        module = viewer_copy / "present.py"
        planted = "from src.viewer.render import render_compact\n" + module.read_text(
            encoding="utf-8"
        )
        module.write_text(planted, encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert len(violations) == 1, _render(violations)
        message = str(violations[0])
        assert "src/viewer/present.py" in message, message
        assert "render_compact" in message, message
        assert "AD-15" in message, message

    def test_a_new_plain_import_is_reported(self, viewer_copy: Path) -> None:
        """``import os`` binds ``os`` on the module. Whether the reader calls that a capability
        or housekeeping, it is a change to what a frozen module exposes, and the fix note offers
        the private alias for the housekeeping case."""
        module = viewer_copy / "render.py"
        module.write_text("import os\n" + module.read_text(encoding="utf-8"), encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["os"], _render(violations)

    def test_a_privately_aliased_import_is_not_reported(self, viewer_copy: Path) -> None:
        """The escape hatch, measured: a module that needs a name without offering it says so
        with ``as _x``, and the pin has nothing to report."""
        module = viewer_copy / "render.py"
        module.write_text(
            "import os as _os\nfrom pathlib import PurePath as _PurePath\n"
            + module.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        assert _synthetic_violations(viewer_copy) == []

    def test_a_dotted_import_is_pinned_by_its_root_binding(self, viewer_copy: Path) -> None:
        """``import xml.etree.ElementTree`` binds ``xml`` and nothing else — pinning the dotted
        spelling would have let the guard miss the name actually reachable on the module."""
        module = viewer_copy / "view_model.py"
        module.write_text(
            "import xml.etree.ElementTree\n" + module.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["xml"], _render(violations)

    def test_a_star_import_is_reported_as_unpinnable(self, viewer_copy: Path) -> None:
        """A star import binds names no AST scan can enumerate, so the module's surface stops
        being pinnable at all — reported as its own breach rather than contributing nothing."""
        module = viewer_copy / "present.py"
        module.write_text(
            "from src.viewer.render import *\n" + module.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["import *"], _render(violations)
        assert "unpinnable" in str(violations[0]), str(violations[0])

    def test_an_import_inside_a_function_is_not_module_surface(self, viewer_copy: Path) -> None:
        """A deferred import is a local binding: it is reachable from nowhere but that call, so
        it is not a capability the module offers."""
        module = viewer_copy / "render.py"
        module.write_text(
            module.read_text(encoding="utf-8")
            + "\n\ndef _load():\n    import os\n\n    return os\n",
            encoding="utf-8",
        )

        assert _synthetic_violations(viewer_copy) == []

    def test_a_disappearing_import_binding_is_reported_too(self, viewer_copy: Path) -> None:
        """Same contract as a disappearing symbol: the pin's entry goes in the same change, so a
        stale list cannot quietly describe a module that no longer exists."""
        module = viewer_copy / "render.py"
        source = module.read_text(encoding="utf-8").replace("import json\n", "")
        module.write_text(source, encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["json"], _render(violations)
        assert "no longer exists" in str(violations[0]), str(violations[0])

    def test_a_disappearing_module_is_reported_too(self, viewer_copy: Path) -> None:
        """Removal is a release action, not an edit: the pin's entry must go with the file."""
        (viewer_copy / "present.py").unlink()

        violations = _synthetic_violations(viewer_copy)
        messages = [str(violation) for violation in violations]

        assert any("src/viewer/present.py" in message for message in messages), messages
        assert any("no longer exists" in message for message in messages), messages

    def test_a_disappearing_public_function_is_reported_too(self, viewer_copy: Path) -> None:
        module = viewer_copy / "view_model.py"
        source = module.read_text(encoding="utf-8").replace("def is_land(", "def _is_land(")
        module.write_text(source, encoding="utf-8")

        violations = _synthetic_violations(viewer_copy)

        assert [v.symbol for v in violations] == ["is_land"], _render(violations)


class TestGitIsTheFreezePinsFileAuthority:
    """A working copy is not a source tree: only what git tracks is package surface."""

    def test_an_untracked_stray_is_not_a_new_capability(self) -> None:
        """Measured, not argued: a ``.DS_Store`` from a Finder visit, an editor's
        ``render.py.orig`` or a stray ``.pyc`` used to report as *new capability in a frozen
        package* — a red guard on an untouched tree, on the maintainer's own machine."""
        stray_name = ".viewer-freeze-probe.tmp"
        stray = _VIEWER_DIR / stray_name
        stray.write_bytes(b"stray working-copy file\n")
        try:
            files = tracked_viewer_files()

            assert stray_name not in files, sorted(files)
            # Scoped to the stray deliberately: asserting the WHOLE tree is clean here would
            # make this test a second reading of test_public_surface_is_pinned, and it would go
            # red alongside it whenever that pin is proven on a planted violation.
            reported = [v for v in find_freeze_violations(files) if stray_name in str(v)]
            assert not reported, _render(reported)
            # The filesystem walk is what would have reported it — the two collectors really do
            # disagree here, which is the whole reason git is the authority for the real tree.
            assert stray_name in walk_viewer_files(_VIEWER_DIR)
        finally:
            stray.unlink()


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

_SRC_VITE_COPIES_THE_TEMPLATE = """\
export default defineConfig({
  plugins: [viteStaticCopy({ targets: [{ src: '../src/viewer/template.html', dest: '.' }] })],
})
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
    pytest.param(
        "<div>{{ deck.name }}</div>\n<!-- lifted from src/viewer -->\n",
        "src/companion/app/templates/deck.html",
        2,
        "src/viewer",
        id="a-backend-template-outside-static-is-swept-too",
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

_SRC_CITATION_ON_A_CODE_LINE = """\
import legacy from '../../src/viewer/render' // src/viewer/view_model.py::is_land
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
        assert "_CITATION_ALLOWED" in message, "a violation must say what to do instead"

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

    def test_a_build_time_copy_of_the_template_is_reported(self, tmp_path: Path) -> None:
        """The reuse ui/src/ could never have shown: a Vite copy plugin wires the old template
        into the bundle from the build configuration."""
        violations = find_reuse_violations(
            _write_source(tmp_path, _SRC_VITE_COPIES_THE_TEMPLATE, name="vite.config.ts"),
            rel_path="ui/vite.config.ts",
        )

        assert {violation.symbol for violation in violations} == {"template.html", "src/viewer"}
        assert all("ui/vite.config.ts:2" in str(v) for v in violations), _render(violations)

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

    def test_the_citation_exemption_requires_a_comment_line(self, tmp_path: Path) -> None:
        """An import with the citation appended as a trailing comment is a reuse wearing the
        exemption's clothes. TypeScript gets no AST pass, so nothing else would catch it."""
        violations = find_reuse_violations(
            _write_source(tmp_path, _SRC_CITATION_ON_A_CODE_LINE, name="deckGroups.ts"),
            rel_path="ui/src/state/deckGroups.ts",
        )

        assert [violation.symbol for violation in violations] == ["src/viewer"], _render(violations)

    def test_the_citation_exemption_is_per_file(self, tmp_path: Path) -> None:
        """A file nobody argued an exemption for cannot borrow one by copying the sentence."""
        violations = find_reuse_violations(
            _write_source(tmp_path, _SRC_DOCUMENTED_CITATION, name="cards.ts"),
            rel_path="ui/src/state/cards.ts",
        )

        assert [violation.symbol for violation in violations] == ["src/viewer"], _render(violations)


_BOM = b"\xef\xbb\xbf"


class TestOneUnreadableFileCannotHideEveryVerdict:
    """Containment: the sweep reports what it cannot read instead of raising through the guard."""

    def test_a_bom_saved_python_source_is_scanned_not_crashed(self, tmp_path: Path) -> None:
        """utf-8 would make this an "invalid non-printable character U+FEFF" SyntaxError out of
        ast.parse — the exact failure the sibling guard documents utf-8-sig for."""
        file = tmp_path / "sample.py"
        # Spelled as bytes, never as an invisible character in this file's own source.
        file.write_bytes(_BOM + b"import json\n")

        assert find_reuse_violations(file, rel_path="src/companion/client.py") == []

    def test_a_bom_saved_source_still_reports_its_reuse(self, tmp_path: Path) -> None:
        file = tmp_path / "sample.py"
        file.write_bytes(_BOM + b"from src.viewer import present_deck\n")

        violations = find_reuse_violations(file, rel_path="src/companion/client.py")

        assert [violation.symbol for violation in violations] == ["src.viewer"], _render(violations)

    def test_an_undecodable_file_is_reported_not_raised(self, tmp_path: Path) -> None:
        file = tmp_path / "asset.bin"
        file.write_bytes(b"\x00\x01\xff\xfe wOF2 \x80")

        violations = find_reuse_violations(file, rel_path="ui/public/asset.bin")

        assert len(violations) == 1, _render(violations)
        assert "not valid UTF-8" in str(violations[0]), str(violations[0])
        assert "_BINARY_SUFFIXES" in str(violations[0]), str(violations[0])

    def test_a_missing_file_is_reported_not_raised(self, tmp_path: Path) -> None:
        violations = find_reuse_violations(tmp_path / "gone.py", rel_path="src/companion/gone.py")

        assert len(violations) == 1, _render(violations)
        assert "unreadable" in str(violations[0]), str(violations[0])

    def test_unparsable_python_is_reported_not_raised(self, tmp_path: Path) -> None:
        violations = find_reuse_violations(
            _write_source(tmp_path, "def broken(:\n"), rel_path="src/companion/client.py"
        )

        assert [v.symbol for v in violations] == ["unparsable Python"], _render(violations)

    def test_a_beyond_top_level_relative_import_is_reported_not_raised(
        self, tmp_path: Path
    ) -> None:
        """_resolve_import raises by design rather than laundering the name; the sweep contains
        that so one broken import cannot hide every other file's verdict."""
        violations = find_reuse_violations(
            _write_source(tmp_path, "from ......viewer import render_html\n"),
            rel_path="src/companion/client.py",
        )

        assert len(violations) == 1, _render(violations)
        assert "cannot resolve this relative import" in str(violations[0]), str(violations[0])


class TestScansCannotPassVacuously:
    """An empty or mistyped scan path must fail loudly, not silently pass forever."""

    def test_an_empty_viewer_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AssertionError, match="found no files"):
            walk_viewer_files(tmp_path)

    def test_pycache_is_excluded_from_the_freeze_walk(self, tmp_path: Path) -> None:
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "render.cpython-312.pyc").write_bytes(b"")
        (tmp_path / "render.py").write_text("", encoding="utf-8")

        assert list(walk_viewer_files(tmp_path)) == ["render.py"]

    def test_the_sweep_pathspecs_match_every_half(self) -> None:
        sources = tracked_companion_sources()
        assert any(rel.startswith("src/companion/app/") for rel in sources), sources
        assert any(rel.startswith("ui/src/") for rel in sources), sources
        assert any(rel.startswith("src/companion/app/static/") for rel in sources), sources
        assert "ui/package.json" in sources, sources
        assert any(rel.startswith("ui/config/") for rel in sources), sources

    def test_the_generated_bundle_is_swept_rather_than_trusted(self) -> None:
        """Residue 2, made mechanical: the committed bundle is a shipped, plugin-mirrored
        artifact, so inspection reads it rather than taking the build's word for it."""
        assert is_swept("src/companion/app/static/assets/index-DJ7dGud2.js")
        assert is_swept("src/companion/app/static/index.html")
        assert is_swept("src/companion/app/spa.py")
        assert is_swept("ui/index.html")

    def test_a_non_python_backend_file_is_swept(self) -> None:
        """The old "under src/companion only *.py is source" premise was true and pinned
        nowhere; a future backend template would have escaped on its suffix."""
        assert is_swept("src/companion/app/templates/deck.html")
        assert is_swept("src/companion/app/fixtures/sample.json")

    def test_the_guard_directory_is_not_swept(self) -> None:
        """Residue 3: ui/tests/ discusses the banned tokens for a living."""
        assert "ui/tests/read-only-glass.test.ts" not in tracked_companion_sources()

    def test_binary_assets_are_skipped(self) -> None:
        assert not is_swept("ui/src/assets/fonts/space-grotesk-latin-wght-normal.woff2")
        assert is_swept("ui/public/favicon.svg")

    def test_relative_imports_are_resolved_not_skipped(self) -> None:
        assert _resolve_import("viewer", 2, "src.companion") == "src.viewer"
        assert _resolve_import("render", 1, "src.viewer") == "src.viewer.render"
        assert _resolve_import(None, 1, "src.viewer") == "src.viewer"
        assert _resolve_import("src.viewer", 0, "src.companion") == "src.viewer"

    def test_beyond_top_level_relative_import_raises_not_launders(self) -> None:
        # A negative slice would otherwise resolve `from ......x` to a plausible absolute name
        # that could dodge the ban; real Python raises ImportError, so the resolver raises too.
        with pytest.raises(ValueError, match="exceeds the depth"):
            _resolve_import("viewer", 6, "src.companion")

    def test_tracked_paths_are_read_as_raw_utf8(self) -> None:
        """`core.quotePath=false` plus `-z`: a tracked path with a space or a non-ASCII
        character must come back as it is on disk, not C-quoted — a quoted spelling would miss
        on read and the file would go unswept."""
        for rel in tracked_companion_sources():
            assert not (rel.startswith('"') and rel.endswith('"')), rel
            assert (REPO_ROOT / rel).is_file(), rel

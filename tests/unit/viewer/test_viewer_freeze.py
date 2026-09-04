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
on a working copy. The real tree only ever uses :func:`tracked_viewer_files`.

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
# The frozen surface (AD-15). Keys are paths relative to src/viewer/.
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
        files: The package's files, keyed by package-relative POSIX path, from
            :func:`tracked_viewer_files`.
        data_hashes: Expected CRLF-normalised sha256 per non-Python file.

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

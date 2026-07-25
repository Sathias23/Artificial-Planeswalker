"""CI-enforced import boundaries for ``src/companion`` (AD-2, AD-3).

Two guards live here, deliberately landed *before* the code they constrain so the boundaries are
structural rather than aspirational:

* **Write guard (AD-2)** — no file under ``src/companion/**`` may reach a write path: a repository
  write method, a session mutation, a SQLAlchemy DML construct, schema creation
  (``init_database`` / ``create_all``) or ``src.data.importers``. ``src/mcp_server`` is the sole
  writer. Read-only is enforced here rather than by ``mode=ro`` (which drags in the WAL ``-shm``
  Windows landmine and would foreclose FR-16).
* **Leaf/app guard (AD-3)** — ``src/mcp_server`` may import the companion *leaf*
  (``contracts`` / ``discovery`` / ``client``) but never ``src.companion.app``; the leaf may import
  only the stdlib, ``pydantic``, ``httpx``, ``src.paths`` and its siblings; nothing outside
  ``src/companion/app/`` imports the app. ``tests/**`` is not scanned — the integration test in
  story c5-8 must be free to boot the real app.

Both guards are **AST-only**: they ``ast.parse`` source and never import the module under
inspection, so they run with neither ``fastapi`` nor ``uvicorn`` installed and they see violations
in modules that no test ever imports.

Known limitations — stated, not hidden:

1. **Raw SQL is not detected.** ``session.execute(text("DELETE ..."))`` passes, because banning
   ``sqlalchemy.text`` would also ban legitimate read-side pragmas. Accepted: the receiver and
   DML-construct rules cover every ORM-shaped write path.
2. **Aliased session receivers are not detected.** ``async with factory() as s: s.add(obj)``
   passes, because ``s`` is not in :data:`_SESSION_RECEIVERS`; adding single letters would fire on
   ordinary set/list code. Accepted: ``src/data`` uses ``session`` / ``self.session`` throughout,
   and the repository write-method ban catches the realistic path anyway.
"""

import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest

from src.data.repositories import CardRepository, ComboSnapshotRepository, DeckRepository

# ---------------------------------------------------------------------------------------------
# Repository layout — resolved from __file__, never from the current working directory (AC 7).
# ---------------------------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_DIR = REPO_ROOT / "src"
_COMPANION_DIR = _SRC_DIR / "companion"
_COMPANION_APP_DIR = _COMPANION_DIR / "app"
_MCP_SERVER_DIR = _SRC_DIR / "mcp_server"
_SCRIPTS_DIR = REPO_ROOT / "scripts"

# ---------------------------------------------------------------------------------------------
# The banned surface (AD-2). Each category is a closed frozenset with its rationale.
# ---------------------------------------------------------------------------------------------

# AD-2: the repository write methods. Distinctive enough that an unconditional ban on the
# attribute call — any receiver — has no plausible false positive. Pinned by AC 4 below.
_REPO_WRITE_METHODS = frozenset(
    {
        "create_deck",
        "update_deck",
        "delete_deck",
        "add_card_to_deck",
        "remove_card_from_deck",
        "update_card_quantity",
        "update_deck_color_identity",
        "merge_decks",
    }
)

# AD-2: SQLAlchemy session mutators. Banned only on a session-shaped receiver — an unrestricted
# ban would fire on `file.flush()` in discovery.py's atomic temp+rename write and on `set.add(...)`.
_SESSION_MUTATORS = frozenset(
    {"add", "add_all", "delete", "merge", "commit", "flush", "bulk_save_objects"}
)
_SESSION_RECEIVERS = frozenset(
    {"session", "sess", "db", "db_session", "database", "conn", "connection"}
)

# AD-2: DML constructs — closes the `session.execute(delete(...))` bypass the receiver rule leaves
# open. Banned at the import site, or on a sqlalchemy-shaped receiver (`sa.update(...)`); a bare
# `update(...)` on a dict/set receiver stays legal, which is why the receiver set is closed.
_DML_CONSTRUCTS = frozenset({"insert", "update", "delete"})
_DML_RECEIVERS = frozenset({"sqlalchemy", "sa", "sql"})

# AD-10 / FR-22: a missing database is a *served* UI state; the companion never creates the schema.
_SCHEMA_CREATION = frozenset({"init_database", "create_all"})

# AD-2: the bulk write path has no business inside a read model.
_BANNED_MODULES = frozenset({"src.data.importers"})

_SOLE_WRITER = "src/mcp_server is the sole writer"

# ---------------------------------------------------------------------------------------------
# The leaf/app surface (AD-3).
# ---------------------------------------------------------------------------------------------

# Checked only where the file exists — this story creates none of them (stories c1-4/c1-7/c6-1 do).
_LEAF_MODULES = (
    "src/companion/contracts.py",
    "src/companion/discovery.py",
    "src/companion/client.py",
)
_LEAF_ALLOWED_THIRD_PARTY = frozenset({"pydantic", "httpx"})
# Decide-once #2: the three leaf modules are collectively *the leaf*, so intra-leaf imports are
# permitted (c6-1's client posts contract models and reads discovery for port + token).
_LEAF_ALLOWED_SRC = frozenset(
    {
        "src.paths",
        "src.companion.contracts",
        "src.companion.discovery",
        "src.companion.client",
    }
)

_APP_PACKAGE = "src.companion.app"
# Decide-once #1: AD-14 puts the subcommand dispatcher in src/mcp_server/__main__.py, which AD-3
# forbids from importing the app. A *function-local* import there is permitted and nowhere else;
# a module-level one still fails. A bare `artificial-planeswalker` invocation never enters the
# `companion` branch, so a stdio MCP session still never imports FastAPI — AD-3's stated target.
_APP_IMPORT_EXEMPT = frozenset({"src/mcp_server/__main__.py"})

_Role = Literal["mcp_server", "leaf", "outside_app"]


# ---------------------------------------------------------------------------------------------
# Guard primitives — pure functions returning violations, with the tests as thin callers (AC 8).
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """A single import-boundary breach.

    Attributes:
        path: Repo-relative POSIX path of the offending file.
        line: 1-based line number of the offending node.
        symbol: The offending symbol, as written (dotted call target or import target).
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
class ImportedName:
    """One dotted import target extracted from an ``import`` / ``from ... import`` statement.

    Attributes:
        dotted: The absolute dotted path, with relative imports already resolved.
        line: 1-based line number of the import statement.
        module_level: True when the import is reachable from the module body without entering a
            function (an import nested only in ``if TYPE_CHECKING:`` counts as module-level).
        parent: For ``from X import Y``, the resolved ``X``; empty for plain ``import X``.
    """

    dotted: str
    line: int
    module_level: bool
    parent: str = ""


def repo_relative(path: Path) -> str:
    """Return *path* as a repo-root-relative POSIX string.

    Args:
        path: Any path inside the repository.

    Returns:
        The path relative to the repository root, using forward slashes.
    """
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def collect_python_files(directory: Path) -> list[Path]:
    """Return every ``*.py`` file under *directory*, excluding ``__pycache__`` (AC 7).

    Args:
        directory: Directory to walk recursively.

    Returns:
        A sorted list of Python source files.

    Raises:
        AssertionError: If the walk finds no files at all — a vacuous scan is a dead guard.
    """
    files = sorted(p for p in directory.rglob("*.py") if "__pycache__" not in p.parts)
    assert files, (
        f"Import-boundary scan found no Python files under {directory} — the guard would pass "
        "vacuously. Check the path constant."
    )
    return files


def package_for(rel_path: str) -> str:
    """Return the dotted package a module at *rel_path* lives in (its ``__package__``).

    Args:
        rel_path: Repo-relative POSIX path of a module, e.g. ``src/companion/client.py``.

    Returns:
        The containing package, e.g. ``src.companion``. For ``__init__.py`` this is the package
        the file *is* (``src/companion/app/__init__.py`` -> ``src.companion.app``), which is what
        relative-import resolution needs.
    """
    return ".".join(rel_path.split("/")[:-1])


def resolve_import(module: str | None, level: int, package: str) -> str:
    """Resolve a possibly relative ``from ... import`` target to an absolute dotted path (AC 6).

    Args:
        module: The ``module`` of an ``ast.ImportFrom`` node (None for ``from . import x``).
        level: The node's ``level`` — 0 for absolute, 1 for ``.``, 2 for ``..``, and so on.
        package: The dotted package of the file containing the import.

    Returns:
        The absolute dotted path the import refers to.
    """
    if level == 0:
        return module or ""
    parts = package.split(".") if package else []
    if level > 1:
        parts = parts[: len(parts) - (level - 1)]
    base = ".".join(parts)
    if module:
        return f"{base}.{module}" if base else module
    return base


def _parse(path: Path) -> ast.Module:
    """Parse *path* without importing it."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _last_segment(node: ast.expr) -> str:
    """Return the lower-cased last dotted segment of an unparsed receiver expression."""
    return ast.unparse(node).split(".")[-1].strip().lower()


def imported_names(tree: ast.Module, package: str) -> list[ImportedName]:
    """Extract every import target from *tree*, classified module-level vs function-local.

    ``ast.walk`` flattens nesting, so the module-level set is built by recursing from the module
    body and *not* descending into function bodies.

    Args:
        tree: A parsed module.
        package: The dotted package of the file, used to resolve relative imports.

    Returns:
        One :class:`ImportedName` per dotted target, in source order per statement.
    """
    names: list[ImportedName] = []

    def emit(node: ast.Import | ast.ImportFrom, module_level: bool) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(ImportedName(alias.name, node.lineno, module_level))
            return
        base = resolve_import(node.module, node.level, package)
        for alias in node.names:
            if alias.name == "*":
                names.append(ImportedName(base, node.lineno, module_level, parent=base))
                continue
            dotted = f"{base}.{alias.name}" if base else alias.name
            names.append(ImportedName(dotted, node.lineno, module_level, parent=base))

    def visit(node: ast.AST, module_level: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Import | ast.ImportFrom):
                emit(child, module_level)
            in_function = isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
            visit(child, module_level and not in_function)

    visit(tree, True)
    return names


def find_write_violations(path: Path, *, rel_path: str | None = None) -> list[Violation]:
    """Return every AD-2 write-path breach in the Python source at *path*.

    The file is parsed, never imported, so violations are found in modules that would fail to
    import in this environment.

    Args:
        path: Path to the source file to inspect.
        rel_path: Repo-relative path to report (and to derive the package from). Defaults to the
            file name, which is enough for synthetic sources written to ``tmp_path``.

    Returns:
        A list of violations, each naming the file path, offending symbol and line number.
    """
    rel = rel_path or path.name
    tree = _parse(path)
    violations: list[Violation] = []

    def flag(line: int, symbol: str, rule: str) -> None:
        violations.append(Violation(rel, line, symbol, rule, note=_SOLE_WRITER))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            target = node.func
            if target.attr in _REPO_WRITE_METHODS:
                flag(node.lineno, ast.unparse(target), "repository write method")
            elif (
                target.attr in _SESSION_MUTATORS
                and _last_segment(target.value) in _SESSION_RECEIVERS
            ):
                flag(node.lineno, ast.unparse(target), "session mutation")
        if isinstance(node, ast.Attribute):
            if node.attr in _SCHEMA_CREATION:
                flag(node.lineno, ast.unparse(node), "schema creation")
            elif node.attr in _DML_CONSTRUCTS and _last_segment(node.value) in _DML_RECEIVERS:
                flag(node.lineno, ast.unparse(node), "sqlalchemy DML construct")
        elif isinstance(node, ast.Name) and node.id in _SCHEMA_CREATION:
            flag(node.lineno, node.id, "schema creation")

    for imported in imported_names(tree, package_for(rel)):
        dotted = imported.dotted
        top, last = dotted.split(".")[0], dotted.split(".")[-1]
        if any(dotted == banned or dotted.startswith(f"{banned}.") for banned in _BANNED_MODULES):
            flag(imported.line, dotted, "import of a bulk write path")
        elif last in _SCHEMA_CREATION:
            flag(imported.line, dotted, "schema creation")
        elif top == "sqlalchemy" and last in _DML_CONSTRUCTS:
            flag(imported.line, dotted, "sqlalchemy DML construct")

    return violations


def _leaf_target_allowed(dotted: str) -> bool:
    """Return True when a leaf module may import *dotted* (AD-3)."""
    if not dotted:
        return False
    if dotted.split(".")[0] in sys.stdlib_module_names:
        return True
    if dotted.split(".")[0] in _LEAF_ALLOWED_THIRD_PARTY:
        return True
    return any(dotted == a or dotted.startswith(f"{a}.") for a in _LEAF_ALLOWED_SRC)


def _is_app_import(dotted: str) -> bool:
    """Return True when *dotted* refers to ``src.companion.app`` or a submodule."""
    return dotted == _APP_PACKAGE or dotted.startswith(f"{_APP_PACKAGE}.")


def find_import_violations(
    path: Path, *, role: _Role, rel_path: str | None = None
) -> list[Violation]:
    """Return every AD-3 leaf/app breach in the Python source at *path*.

    Args:
        path: Path to the source file to inspect.
        role: Which of the three AC-5 rules applies — ``mcp_server`` (may import the leaf, never
            the app, with the ``__main__.py`` function-local exemption), ``leaf`` (a closed
            allow-list of imports, with no ``TYPE_CHECKING`` escape) or ``outside_app`` (no
            module-level app import anywhere outside ``src/companion/app/``).
        rel_path: Repo-relative path to report, and to derive the package and the exemption from.

    Returns:
        A list of violations, each naming the file path, offending symbol and line number.
    """
    rel = rel_path or path.name
    tree = _parse(path)
    exempt = rel in _APP_IMPORT_EXEMPT
    violations: list[Violation] = []

    for imported in imported_names(tree, package_for(rel)):
        if role == "leaf":
            if _leaf_target_allowed(imported.dotted) or (
                imported.parent and _leaf_target_allowed(imported.parent)
            ):
                continue
            violations.append(
                Violation(
                    rel,
                    imported.line,
                    imported.dotted,
                    "a leaf module may import only the stdlib, pydantic, httpx, src.paths and "
                    "its sibling leaf modules (AD-3)",
                )
            )
            continue

        if not _is_app_import(imported.dotted):
            continue
        if role == "mcp_server":
            # The exemption covers function-local imports in __main__.py only; a module-level
            # import there still fails, and no other mcp_server module may import the app at all.
            if imported.module_level or not exempt:
                violations.append(
                    Violation(
                        rel,
                        imported.line,
                        imported.dotted,
                        "src/mcp_server must not import src.companion.app (AD-3)",
                    )
                )
        elif imported.module_level and not exempt:
            violations.append(
                Violation(
                    rel,
                    imported.line,
                    imported.dotted,
                    "nothing outside src/companion/app/ may import src.companion.app (AD-3)",
                )
            )

    return violations


def _render(violations: Iterable[Violation]) -> str:
    """Render violations one per line for an assertion message."""
    return "\n".join(f"  {violation}" for violation in violations)


def _is_under(path: Path, directory: Path) -> bool:
    """Return True when *path* lives inside *directory*."""
    return directory in path.resolve().parents


# ---------------------------------------------------------------------------------------------
# The guards, run against the real tree.
# ---------------------------------------------------------------------------------------------


def test_repo_root_is_resolved_from_file_not_cwd() -> None:
    """The scans must anchor on the repo root regardless of the runner's working directory."""
    assert (REPO_ROOT / "pyproject.toml").exists(), f"{REPO_ROOT} is not the repository root"
    assert _COMPANION_DIR.is_dir()


class TestWriteGuard:
    """AD-2: ``src/companion`` can never reach a write path."""

    def test_companion_package_contains_no_write_path(self) -> None:
        files = collect_python_files(_COMPANION_DIR)
        violations = [
            violation
            for file in files
            for violation in find_write_violations(file, rel_path=repo_relative(file))
        ]
        assert not violations, (
            "src/companion must never write — AD-2 makes src/mcp_server the sole writer:\n"
            f"{_render(violations)}"
        )


class TestLeafAppGuard:
    """AD-3: the leaf/app split, in all three directions."""

    def test_mcp_server_never_imports_the_companion_app(self) -> None:
        files = collect_python_files(_MCP_SERVER_DIR)
        relatives = [repo_relative(file) for file in files]
        assert "src/mcp_server/__main__.py" in relatives, (
            "The src/mcp_server scan did not visit __main__.py — the scan path is wrong."
        )
        violations = [
            violation
            for file, rel in zip(files, relatives, strict=True)
            for violation in find_import_violations(file, role="mcp_server", rel_path=rel)
        ]
        assert not violations, f"AD-3 leaf/app breach in src/mcp_server:\n{_render(violations)}"

    def test_leaf_modules_import_only_their_allowed_surface(self) -> None:
        for rel in _LEAF_MODULES:
            assert (REPO_ROOT / rel).parent == _COMPANION_DIR, (
                f"_LEAF_MODULES entry {rel!r} does not live in src/companion/ — typo?"
            )
        present = [rel for rel in _LEAF_MODULES if (REPO_ROOT / rel).exists()]
        violations = [
            violation
            for rel in present
            for violation in find_import_violations(REPO_ROOT / rel, role="leaf", rel_path=rel)
        ]
        assert not violations, f"AD-3 leaf import breach:\n{_render(violations)}"

    def test_nothing_outside_the_app_package_imports_the_app(self) -> None:
        files = [
            file
            for file in collect_python_files(_SRC_DIR)
            if not _is_under(file, _COMPANION_APP_DIR)
        ]
        files += collect_python_files(_SCRIPTS_DIR)
        violations = [
            violation
            for file in files
            for violation in find_import_violations(
                file, role="outside_app", rel_path=repo_relative(file)
            )
        ]
        assert not violations, (
            f"AD-3: src.companion.app must stay unimported outside itself:\n{_render(violations)}"
        )


# ---------------------------------------------------------------------------------------------
# Proving the guards fail (AC 8) — synthetic sources in tmp_path, never a violating committed file.
# ---------------------------------------------------------------------------------------------

_SRC_REPO_WRITE = """\
def go(repo):
    repo.create_deck(name="x")
"""

_SRC_SESSION_ADD = """\
def go(self):
    self.session.add(obj)
"""

_SRC_SESSION_COMMIT = """\
async def go(db):
    await db.commit()
"""

_SRC_DML_IMPORT = """\
from sqlalchemy import delete
"""

_SRC_DML_REFERENCE = """\
import sqlalchemy


def go(session):
    session.execute(sqlalchemy.delete(DeckModel))
"""

_SRC_SCHEMA_IMPORT = """\
from src.data.database import init_database
"""

_SRC_SCHEMA_CALL = """\
async def go():
    await init_database()
"""

_SRC_CREATE_ALL = """\
def go(engine):
    Base.metadata.create_all(engine)
"""

_SRC_IMPORTERS = """\
from src.data import importers
"""

_SRC_IMPORTERS_SUBMODULE = """\
from src.data.importers.scryfall import load_cards
"""

_WRITE_VIOLATION_CASES = [
    pytest.param(_SRC_REPO_WRITE, 2, "create_deck", id="repository-write-method"),
    pytest.param(_SRC_SESSION_ADD, 2, "session.add", id="session-mutation"),
    pytest.param(_SRC_SESSION_COMMIT, 2, "db.commit", id="session-commit"),
    pytest.param(_SRC_DML_IMPORT, 1, "sqlalchemy.delete", id="dml-import"),
    pytest.param(_SRC_DML_REFERENCE, 5, "sqlalchemy.delete", id="dml-reference"),
    pytest.param(_SRC_SCHEMA_IMPORT, 1, "init_database", id="schema-creation-import"),
    pytest.param(_SRC_SCHEMA_CALL, 2, "init_database", id="schema-creation-call"),
    pytest.param(_SRC_CREATE_ALL, 2, "create_all", id="create-all"),
    pytest.param(_SRC_IMPORTERS, 1, "src.data.importers", id="banned-module"),
    pytest.param(_SRC_IMPORTERS_SUBMODULE, 1, "src.data.importers.scryfall", id="banned-submodule"),
]

_SRC_FILE_FLUSH = """\
def go(path, payload):
    with open(path, "w", encoding="utf-8") as file:
        file.write(payload)
        file.flush()
"""

_SRC_SET_ADD = """\
def go(seen, item):
    seen.add(item)
"""

_SRC_DICT_UPDATE = """\
def go(payload):
    payload.update({"port": 8765})
"""

_SRC_REPOSITORY_READ = """\
from src.data.repositories import DeckRepository


async def go(session):
    return await DeckRepository(session).list_decks()
"""

_WRITE_CLEAN_CASES = [
    pytest.param(_SRC_FILE_FLUSH, id="file-flush-in-atomic-write"),
    pytest.param(_SRC_SET_ADD, id="set-add"),
    pytest.param(_SRC_DICT_UPDATE, id="dict-update"),
    pytest.param(_SRC_REPOSITORY_READ, id="repository-read"),
]


def _write_source(tmp_path: Path, source: str) -> Path:
    """Write *source* to a throwaway module in *tmp_path* and return its path."""
    file = tmp_path / "sample.py"
    file.write_text(source, encoding="utf-8")
    return file


class TestWriteGuardDetectsViolations:
    """Every banned category of AC 3 is proven to fail, with path + symbol + line in the message."""

    @pytest.mark.parametrize(("source", "line", "symbol"), _WRITE_VIOLATION_CASES)
    def test_banned_category_is_reported(self, tmp_path, source, line, symbol):
        rel = "src/companion/app/routes/decks.py"
        violations = find_write_violations(_write_source(tmp_path, source), rel_path=rel)

        assert len(violations) == 1, f"expected exactly one violation, got {_render(violations)}"
        message = str(violations[0])
        assert f"{rel}:{line}" in message, message
        assert symbol in message, message
        assert _SOLE_WRITER in message, message

    @pytest.mark.parametrize("source", _WRITE_CLEAN_CASES)
    def test_permitted_form_is_not_reported(self, tmp_path, source):
        violations = find_write_violations(
            _write_source(tmp_path, source), rel_path="src/companion/discovery.py"
        )
        assert not violations, _render(violations)


_SRC_MCP_MODULE_LEVEL_APP = """\
import src.companion.app
"""

_SRC_MAIN_MODULE_LEVEL_APP = """\
from src.companion.app.main import build_app
"""

_SRC_FUNCTION_LOCAL_APP = """\
def run():
    from src.companion.app.main import build_app

    return build_app()
"""

_SRC_LEAF_FASTAPI = """\
import fastapi
"""

_SRC_LEAF_SQLALCHEMY = """\
from sqlalchemy import select
"""

_SRC_LEAF_SRC_DATA = """\
from src.data.repositories import DeckRepository
"""

_SRC_LEAF_TYPE_CHECKING = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
"""

_SRC_LEAF_RELATIVE_APP = """\
from .app import main
"""

_SRC_OUTSIDE_APP_ABSOLUTE = """\
from src.companion.app import main
"""

_SRC_OUTSIDE_APP_RELATIVE = """\
from ..companion.app import main
"""

_IMPORT_VIOLATION_CASES = [
    pytest.param(
        _SRC_MCP_MODULE_LEVEL_APP,
        "src/mcp_server/server.py",
        "mcp_server",
        1,
        "src.companion.app",
        id="mcp-server-module-level-app",
    ),
    pytest.param(
        _SRC_MAIN_MODULE_LEVEL_APP,
        "src/mcp_server/__main__.py",
        "mcp_server",
        1,
        "src.companion.app.main.build_app",
        id="exempt-file-still-fails-at-module-level",
    ),
    pytest.param(
        _SRC_FUNCTION_LOCAL_APP,
        "src/mcp_server/server.py",
        "mcp_server",
        2,
        "src.companion.app.main.build_app",
        id="exemption-is-not-extended-to-other-mcp-modules",
    ),
    pytest.param(
        _SRC_LEAF_FASTAPI,
        "src/companion/client.py",
        "leaf",
        1,
        "fastapi",
        id="leaf-fastapi",
    ),
    pytest.param(
        _SRC_LEAF_SQLALCHEMY,
        "src/companion/discovery.py",
        "leaf",
        1,
        "sqlalchemy.select",
        id="leaf-sqlalchemy",
    ),
    pytest.param(
        _SRC_LEAF_SRC_DATA,
        "src/companion/contracts.py",
        "leaf",
        1,
        "src.data.repositories.DeckRepository",
        id="leaf-src-data",
    ),
    pytest.param(
        _SRC_LEAF_TYPE_CHECKING,
        "src/companion/contracts.py",
        "leaf",
        4,
        "fastapi.FastAPI",
        id="leaf-has-no-type-checking-exemption",
    ),
    pytest.param(
        _SRC_LEAF_RELATIVE_APP,
        "src/companion/client.py",
        "leaf",
        1,
        "src.companion.app.main",
        id="leaf-relative-app-import",
    ),
    pytest.param(
        _SRC_OUTSIDE_APP_ABSOLUTE,
        "src/logic/deck_analysis.py",
        "outside_app",
        1,
        "src.companion.app.main",
        id="outside-app-module-level",
    ),
    pytest.param(
        _SRC_OUTSIDE_APP_RELATIVE,
        "src/logic/deck_analysis.py",
        "outside_app",
        1,
        "src.companion.app.main",
        id="outside-app-relative-import",
    ),
]

_SRC_MCP_IMPORTS_LEAF = """\
import src.companion.discovery
from src.companion.contracts import DeckSummary
"""

_SRC_LEAF_ALLOWED_SURFACE = """\
import json

import httpx
from pydantic import BaseModel

from src import paths
from src.companion.contracts import DeckSummary
"""

_SRC_OUTSIDE_IMPORTS_LEAF = """\
from src.companion.contracts import DeckSummary
"""

_IMPORT_CLEAN_CASES = [
    pytest.param(
        _SRC_MCP_IMPORTS_LEAF,
        "src/mcp_server/tools/companion.py",
        "mcp_server",
        id="mcp-server-may-import-the-leaf",
    ),
    pytest.param(
        _SRC_FUNCTION_LOCAL_APP,
        "src/mcp_server/__main__.py",
        "mcp_server",
        id="dispatcher-function-local-exemption",
    ),
    pytest.param(
        _SRC_LEAF_ALLOWED_SURFACE,
        "src/companion/client.py",
        "leaf",
        id="leaf-allowed-surface",
    ),
    pytest.param(
        _SRC_OUTSIDE_IMPORTS_LEAF,
        "src/logic/deck_analysis.py",
        "outside_app",
        id="outside-app-may-import-the-leaf",
    ),
]


class TestLeafAppGuardDetectsViolations:
    """Every rule of AC 5 is proven to fail, and every permitted form to pass."""

    @pytest.mark.parametrize(("source", "rel", "role", "line", "symbol"), _IMPORT_VIOLATION_CASES)
    def test_banned_import_is_reported(self, tmp_path, source, rel, role, line, symbol):
        violations = find_import_violations(
            _write_source(tmp_path, source), role=role, rel_path=rel
        )

        assert len(violations) == 1, f"expected exactly one violation, got {_render(violations)}"
        message = str(violations[0])
        assert f"{rel}:{line}" in message, message
        assert symbol in message, message
        assert "AD-3" in message, message

    @pytest.mark.parametrize(("source", "rel", "role"), _IMPORT_CLEAN_CASES)
    def test_permitted_import_is_not_reported(self, tmp_path, source, rel, role):
        violations = find_import_violations(
            _write_source(tmp_path, source), role=role, rel_path=rel
        )
        assert not violations, _render(violations)


class TestScanCannotPassVacuously:
    """AC 7: an empty or mistyped scan path must fail, not silently pass forever."""

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(AssertionError, match="no Python files"):
            collect_python_files(tmp_path)

    def test_pycache_is_excluded(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "stale.py").write_text("", encoding="utf-8")
        (tmp_path / "real.py").write_text("", encoding="utf-8")

        assert [path.name for path in collect_python_files(tmp_path)] == ["real.py"]

    def test_relative_imports_are_resolved_not_skipped(self):
        assert resolve_import("app", 1, "src.companion") == "src.companion.app"
        assert resolve_import("companion.app", 2, "src.logic") == "src.companion.app"
        assert resolve_import(None, 1, "src.companion") == "src.companion"
        assert resolve_import("src.companion.app", 0, "src.logic") == "src.companion.app"

    def test_package_is_derived_from_the_file_position(self):
        assert package_for("src/companion/client.py") == "src.companion"
        assert package_for("src/companion/app/__init__.py") == "src.companion.app"


# ---------------------------------------------------------------------------------------------
# Guard-the-guard (AC 4): the repository surface is pinned, so a future write method cannot
# silently fall outside the ban. Importing the repositories here is fine — this file is a test,
# not a module under src/companion/.
# ---------------------------------------------------------------------------------------------

_REPO_READ_METHODS = frozenset(
    {
        # DeckRepository
        "get_deck",
        "list_decks",
        "find_deck_by_name",
        "get_deck_with_cards",
        # CardRepository
        "get_by_id",
        "find_by_name_exact",
        "find_by_name_partial",
        "find_by_colors",
        "find_by_type",
        "search_by_keywords",
        "search_advanced",
        # ComboSnapshotRepository
        "snapshot_is_available",
        "get_snapshot_state",
        "get_metadata",
        "get_variants_for_names",
    }
)

_PINNED_REPOSITORIES = (DeckRepository, CardRepository, ComboSnapshotRepository)


def _public_methods(cls: type) -> set[str]:
    """Return every public method name on *cls*, including inherited ones.

    Args:
        cls: A repository class.

    Returns:
        The set of public (non-underscore) callable attribute names across the MRO.
    """
    names: set[str] = set()
    for klass in cls.__mro__:
        if klass is object:
            continue
        names |= {
            name
            for name, value in vars(klass).items()
            if not name.startswith("_") and (callable(value) or isinstance(value, property))
        }
    return names


class TestRepositorySurfaceIsPinned:
    """AC 4: construction-site enumeration, turned into an executable assertion."""

    def test_every_public_repository_method_is_classified(self) -> None:
        classified = _REPO_WRITE_METHODS | _REPO_READ_METHODS
        unclassified = {
            f"{repository.__name__}.{name}"
            for repository in _PINNED_REPOSITORIES
            for name in _public_methods(repository)
            if name not in classified
        }
        assert not unclassified, (
            "Unclassified repository method(s): "
            + ", ".join(sorted(unclassified))
            + ". Add each to _REPO_WRITE_METHODS (if it writes — the companion import guard will "
            "then ban it) or to _REPO_READ_METHODS in "
            "tests/unit/companion/test_import_boundary.py."
        )

    def test_write_and_read_classifications_are_disjoint(self) -> None:
        overlap = _REPO_WRITE_METHODS & _REPO_READ_METHODS
        assert not overlap, f"Method(s) classified as both read and write: {sorted(overlap)}"

    def test_no_banned_write_method_is_stale(self) -> None:
        existing = set().union(*(_public_methods(repo) for repo in _PINNED_REPOSITORIES))
        stale = _REPO_WRITE_METHODS - existing
        assert not stale, (
            f"_REPO_WRITE_METHODS names method(s) no repository has: {sorted(stale)} — "
            "the ban is dead weight; remove or rename them."
        )

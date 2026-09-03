"""The package version has one source of truth: ``pyproject.toml``.

``src.__version__`` is read back from the installed distribution metadata and ``ui/package.json``
is bumped by hand at release time; both drifted (0.1.0 / 0.0.0 against 0.5.0) before this guard.
"""

import json
import tomllib
from pathlib import Path

import src

REPO_ROOT = Path(__file__).resolve().parents[2]


def _pyproject_version() -> str:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["project"]["version"])


def test_package_version_matches_pyproject() -> None:
    assert src.__version__ == _pyproject_version()


def test_ui_package_json_version_matches_pyproject() -> None:
    package_json = json.loads((REPO_ROOT / "ui" / "package.json").read_text(encoding="utf-8"))
    assert package_json["version"] == _pyproject_version()

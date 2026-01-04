"""Basic test to verify pytest configuration."""

import sys
from pathlib import Path


def test_python_version() -> None:
    """Verify Python version is 3.12 or higher."""
    assert sys.version_info >= (3, 12), "Python 3.12+ is required"


def test_project_structure() -> None:
    """Verify project structure exists."""
    project_root = Path(__file__).parent.parent

    # Check main source directories
    assert (project_root / "src" / "data").exists(), "src/data/ should exist"
    assert (project_root / "src" / "logic").exists(), "src/logic/ should exist"
    assert (project_root / "src" / "agent").exists(), "src/agent/ should exist"
    assert (project_root / "src" / "ui").exists(), "src/ui/ should exist"

    # Check __init__.py files
    assert (project_root / "src" / "__init__.py").exists(), "src/__init__.py should exist"
    assert (project_root / "src" / "data" / "__init__.py").exists()
    assert (project_root / "src" / "logic" / "__init__.py").exists()
    assert (project_root / "src" / "agent" / "__init__.py").exists()
    assert (project_root / "src" / "ui" / "__init__.py").exists()

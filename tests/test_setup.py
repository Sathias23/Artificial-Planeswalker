"""Basic test to verify pytest configuration."""

import sys
from pathlib import Path


def test_python_version() -> None:
    """Verify Python version is 3.12 or higher."""
    assert sys.version_info >= (3, 12), "Python 3.12+ is required"


def test_project_structure() -> None:
    """Verify project structure (MCP-server layout; agent + ui archived to legacy/ in Story 1.1)."""
    project_root = Path(__file__).parent.parent

    # Reusable core + new MCP/search packages
    assert (project_root / "src" / "data").exists(), "src/data/ should exist"
    assert (project_root / "src" / "logic").exists(), "src/logic/ should exist"
    assert (project_root / "src" / "mcp_server").exists(), "src/mcp_server/ should exist"
    assert (project_root / "src" / "search").exists(), "src/search/ should exist"

    # agent + ui were archived out of the active build to legacy/
    assert (project_root / "legacy" / "agent").exists(), "legacy/agent/ should exist"
    assert (project_root / "legacy" / "ui").exists(), "legacy/ui/ should exist"

    # Check __init__.py files
    assert (project_root / "src" / "__init__.py").exists(), "src/__init__.py should exist"
    assert (project_root / "src" / "data" / "__init__.py").exists()
    assert (project_root / "src" / "logic" / "__init__.py").exists()
    assert (project_root / "src" / "mcp_server" / "__init__.py").exists()
    assert (project_root / "src" / "search" / "__init__.py").exists()

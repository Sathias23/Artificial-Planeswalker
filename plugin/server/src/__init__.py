"""Artificial Planeswalker - MTG deck-building AI assistant."""

from importlib.metadata import PackageNotFoundError, version
from typing import Final

# The version has one source of truth: pyproject.toml's [project] version, read back through
# the installed distribution metadata. A source checkout that has not been `uv sync`ed (so no
# dist-info exists) reports 0.0.0 rather than failing to import.
try:
    __version__ = version("artificial-planeswalker")
except PackageNotFoundError:  # pragma: no cover - only when the package is not installed
    __version__ = "0.0.0"

__author__ = "Brad"

# Project metadata
PROJECT_NAME: Final[str] = "Artificial Planeswalker"
DESCRIPTION: Final[str] = "MTG Arena deck-building AI assistant"

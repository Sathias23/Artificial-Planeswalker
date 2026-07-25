"""Companion read model — the relay peer of :mod:`src.mcp_server` (AD-1, AD-3).

A **sibling** of the MCP server over the same ``src.data`` + ``src.logic`` core: it defines no
second card or deck shape and is not an MCP client. It only ever *reads* what the MCP server
writes — ``src/mcp_server`` is the sole writer (AD-2), enforced structurally by
``tests/unit/companion/test_import_boundary.py`` rather than by convention.

The package is split in two (AD-3):

* the **leaf** — ``contracts`` / ``discovery`` / ``client`` — dependency-light modules the MCP
  server may import (stdlib, ``pydantic``, ``httpx``, ``src.paths`` and each other, nothing more);
* the **app** — :mod:`src.companion.app` — the FastAPI shell, which nothing outside itself imports.
"""

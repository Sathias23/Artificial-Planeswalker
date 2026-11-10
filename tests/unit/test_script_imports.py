"""Importing a ``scripts.*`` module configures no logging.

A module-level ``logging.basicConfig`` installs a root handler as an import side effect: a test
that imports the script (or a tool that imports a helper from it) inherits a stdout or stderr
handler for the rest of the process. Logging is configured at each script's entry point instead,
as ``scripts/dump_openapi.py`` does.

Every module in the ``scripts`` package is imported in one fresh interpreter, because pytest's own
log capture would hide the handler in-process. After each import the root logger is checked and
then cleared, so a report names exactly the module whose import left a handler behind.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

_PROBE = """
import importlib, json, logging, pkgutil
import scripts

root = logging.getLogger()
root.handlers.clear()
offenders = {}
for info in sorted(pkgutil.iter_modules(scripts.__path__), key=lambda i: i.name):
    importlib.import_module(f"scripts.{info.name}")
    if root.handlers:
        offenders[info.name] = [repr(handler) for handler in root.handlers]
        root.handlers.clear()
print(json.dumps(offenders))
"""


def test_importing_a_script_leaves_the_root_logger_without_handlers() -> None:
    """No ``scripts.*`` import installs a root handler."""
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    offenders = json.loads(completed.stdout.strip().splitlines()[-1])
    assert offenders == {}

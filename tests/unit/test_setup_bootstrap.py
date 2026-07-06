"""Regression tests for setup.py's bootstrap flow (fresh-machine quick start).

``python3 setup.py`` runs in the *system* interpreter, where the project's dependencies
are not importable — `uv sync` provisions a project venv, not the invoking Python. The
DB-init step must therefore re-exec itself through ``uv run`` instead of importing
``src``/``sqlalchemy`` in-process (which ImportErrors on exactly the fresh machine the
quick start targets).
"""

import subprocess
import sys
import types

import setup


def test_initialize_database_reexecs_through_uv_run(monkeypatch):
    """The DB-init step shells out to `uv run python setup.py --init-db`, no in-process imports."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    setup.initialize_database()

    assert len(calls) == 1, "initialize_database must re-exec via subprocess, not import src"
    cmd, kwargs = calls[0]
    assert cmd == ["uv", "run", "python", "setup.py", "--init-db"]
    assert kwargs.get("check") is True


def test_main_with_init_db_flag_runs_only_the_db_step(monkeypatch):
    """`setup.py --init-db` (the re-exec'd child) runs the DB init and nothing else."""
    ran = []

    async def fake_impl() -> None:
        ran.append(True)

    def must_not_run() -> None:
        raise AssertionError("--init-db must not re-run the full setup flow")

    monkeypatch.setattr(setup, "_init_db", fake_impl, raising=False)
    monkeypatch.setattr(setup, "sync_dependencies", must_not_run)
    monkeypatch.setattr(sys, "argv", ["setup.py", "--init-db"])

    setup.main()

    assert ran == [True]

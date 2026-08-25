"""Tests for the MCP entry point, the subcommand dispatcher and .mcp.json registration.

Story 1.3, Task 5 established the transport tests and the repo-root ``.mcp.json`` pin. Story c1-9
added the dispatcher (AD-14) and its companion branch, plus the sibling pin for the committed
``plugin/.mcp.json`` — the assertion that goes red if a future story "helpfully" rewrites either
file into a console-script subcommand form.
"""

import json
import logging
from pathlib import Path

import pytest

import src.mcp_server.__main__ as main_mod


class _FakeServer:
    """Records the transport passed to run() instead of starting a server."""

    def __init__(self) -> None:
        self.transport: str | None = None

    def run(self, transport: str) -> None:
        self.transport = transport


class _RecordingRun:
    """Records the port handed to ``src.companion.app.server.run`` instead of serving.

    ``calls`` keeps the port-only shape every pre-17.4 assertion reads; ``opens`` records the
    ``open_browser`` keyword beside it, so the flag's plumbing is asserted separately from the
    port's rather than by widening every existing ``== [1234]``.
    """

    def __init__(self) -> None:
        self.calls: list[int | None] = []
        self.opens: list[bool] = []

    def __call__(self, port: int | None = None, *, open_browser: bool = False) -> None:
        self.calls.append(port)
        self.opens.append(open_browser)


class _RootLoggerGuard:
    """A handle on the root logger for a test that must observe ``basicConfig``'s effect."""

    def __init__(self, root: logging.Logger) -> None:
        self._root = root

    def make_pristine(self) -> None:
        """Drop every handler, so ``basicConfig`` is not a no-op for the call that follows.

        This must be called **inside the test body**, not from fixture setup: pytest's logging
        plugin installs its own handlers (``_LiveLoggingNullHandler``, two ``LogCaptureHandler``s
        and a ``_FileHandler``) around each *phase*, i.e. after fixtures have run. Clearing at
        setup time would therefore be undone before the test ever calls ``main``.
        """
        self._root.handlers.clear()

    @property
    def handlers(self) -> list[logging.Handler]:
        return self._root.handlers

    @property
    def level(self) -> int:
        return self._root.level


@pytest.fixture
def root_logger_guard():
    """Snapshot the root logger and restore it at teardown.

    ``logging.basicConfig`` mutates global state and is a **no-op when the root logger already has
    a handler**. Both halves of this fixture matter: without the restore, the companion tests leak
    a stderr handler into the rest of the session; without
    :meth:`_RootLoggerGuard.make_pristine`, an assertion that "a handler was added" passes
    vacuously because pytest's handlers made ``basicConfig`` do nothing at all.
    """
    root = logging.root
    handlers = root.handlers[:]
    level = root.level
    try:
        yield _RootLoggerGuard(root)
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)


@pytest.fixture
def recorded_run(monkeypatch: pytest.MonkeyPatch):
    """Replace ``src.companion.app.server.run`` with a recorder.

    Patching the *module attribute* is what the dispatcher's function-local
    ``from src.companion.app.server import run`` picks up, because that import is resolved at call
    time (AD-3). A module-level import in the dispatcher would bind the real function at import time
    and this fixture would silently stop working — one more reason the exemption is function-local.
    """
    import src.companion.app.server as server_mod

    recorder = _RecordingRun()
    monkeypatch.setattr(server_mod, "run", recorder)
    return recorder


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point ``PLANESWALKER_DATA_DIR`` at this test's own ``tmp_path``.

    ``_log_startup_diagnostics`` opens the real card database otherwise, and the companion path
    would take a lock in the developer's real data directory.
    """
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))


def test_main_defaults_to_stdio_transport(monkeypatch: pytest.MonkeyPatch):
    """With no MCP_TRANSPORT set, the entry point runs over stdio (AC2)."""
    fake = _FakeServer()
    monkeypatch.setattr(main_mod, "build_server", lambda: fake)
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)

    main_mod.main([])

    assert fake.transport == "stdio"


def test_main_honors_env_transport(monkeypatch: pytest.MonkeyPatch):
    """The transport is selected only at the entry point, from MCP_TRANSPORT (AC2/D7)."""
    fake = _FakeServer()
    monkeypatch.setattr(main_mod, "build_server", lambda: fake)
    monkeypatch.setenv("MCP_TRANSPORT", "sse")

    main_mod.main([])

    assert fake.transport == "sse"


class TestTheBareInvocationIsUnchanged:
    """AC 2: no arguments runs the MCP server, and stdout still carries only JSON-RPC."""

    def test_no_arguments_runs_the_mcp_server_and_returns_zero(self, monkeypatch):
        fake = _FakeServer()
        monkeypatch.setattr(main_mod, "build_server", lambda: fake)

        assert main_mod.main([]) == 0
        assert fake.transport == "stdio"

    def test_the_mcp_path_writes_nothing_to_stdout(self, monkeypatch, capsys):
        """The diagnostics reach stderr; stdout belongs to the JSON-RPC stream alone (AD-15)."""
        monkeypatch.setattr(main_mod, "build_server", _FakeServer)

        main_mod.main([])

        captured = capsys.readouterr()
        assert captured.out == ""
        assert "[planeswalker] data_dir=" in captured.err

    def test_the_mcp_path_configures_no_root_handler(self, monkeypatch, root_logger_guard):
        """Only the companion process configures logging (AC 6)."""
        monkeypatch.setattr(main_mod, "build_server", _FakeServer)
        root_logger_guard.make_pristine()

        main_mod.main([])

        assert root_logger_guard.handlers == []

    def test_the_mcp_path_imports_nothing_from_the_companion_app(self, monkeypatch):
        """AD-3's stated target: a stdio session never pulls in FastAPI or uvicorn."""
        import sys

        monkeypatch.setattr(main_mod, "build_server", _FakeServer)
        for name in [n for n in sys.modules if n.startswith("src.companion.app")]:
            monkeypatch.delitem(sys.modules, name, raising=False)

        main_mod.main([])

        assert not [n for n in sys.modules if n.startswith("src.companion.app")]


class TestTheCompanionSubcommand:
    """AC 3: ``companion`` starts the backend, and accepts ``--port`` in two forms."""

    def test_companion_runs_the_backend_with_no_port(self, recorded_run, root_logger_guard):
        assert main_mod.main(["companion"]) == 0
        assert recorded_run.calls == [None]

    def test_port_with_a_space_is_parsed(self, recorded_run, root_logger_guard):
        assert main_mod.main(["companion", "--port", "1234"]) == 0
        assert recorded_run.calls == [1234]

    def test_port_with_an_equals_sign_is_parsed(self, recorded_run, root_logger_guard):
        assert main_mod.main(["companion", "--port=1234"]) == 0
        assert recorded_run.calls == [1234]

    def test_open_is_off_unless_asked_for(self, recorded_run, root_logger_guard):
        """17.4: a plain launch never pops a browser — ``--open`` is opt-in."""
        assert main_mod.main(["companion"]) == 0
        assert recorded_run.opens == [False]

    @pytest.mark.parametrize(
        "argv",
        [
            ["companion", "--open"],
            ["companion", "--open", "--port", "1234"],
            ["companion", "--port=1234", "--open"],
        ],
        ids=["alone", "before-port", "after-port"],
    )
    def test_open_reaches_run_in_any_position(self, argv, recorded_run, root_logger_guard):
        assert main_mod.main(argv) == 0
        assert recorded_run.opens == [True]
        assert recorded_run.calls == [None if len(argv) == 2 else 1234]

    def test_an_out_of_range_port_is_not_a_usage_error(self, recorded_run, root_logger_guard):
        """It flows through to resolve_preferred_port, which warns and uses the default (AC 3)."""
        assert main_mod.main(["companion", "--port", "99999"]) == 0
        assert recorded_run.calls == [99999]

    def test_the_companion_path_configures_the_root_logger(self, recorded_run, root_logger_guard):
        """AC 6: INFO, on stderr, before run() is called — which is what makes c1-3/c1-7/c1-8's
        records visible for the first time."""
        import sys

        root_logger_guard.make_pristine()

        main_mod.main(["companion"])

        assert root_logger_guard.level == logging.INFO
        assert len(root_logger_guard.handlers) == 1
        handler = root_logger_guard.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stderr

    def test_logging_is_configured_before_run_is_called(self, monkeypatch, root_logger_guard):
        """The earliest records worth seeing are emitted inside run() before uvicorn exists, so
        configuring the root logger any later would lose them (AC 6)."""
        import src.companion.app.server as server_mod

        seen: list[int] = []
        monkeypatch.setattr(
            server_mod, "run", lambda port=None, **_: seen.append(len(logging.root.handlers))
        )
        root_logger_guard.make_pristine()

        main_mod.main(["companion"])

        assert seen == [1]

    def test_a_keyboard_interrupt_during_run_exits_zero(self, monkeypatch, root_logger_guard):
        """Ctrl-C before uvicorn exists must not print a traceback for a deliberate action."""
        import src.companion.app.server as server_mod

        def interrupt(port: int | None = None, **_: object) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(server_mod, "run", interrupt)

        assert main_mod.main(["companion"]) == 0


class TestUsageErrors:
    """AC 4: exit 2 with usage on stderr, and never a call into the backend."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["companion", "--port", "abc"],
            ["companion", "--port"],
            ["companion", "--port="],
            ["companion", "--bogus"],
            ["companion", "extra"],
            ["companion", "--port", "1234", "--port=5678"],
            ["companion", "--open=yes"],
            ["companion", "--opne"],
            ["companion", "--open", "--open"],
            ["nonsense"],
            ["--version"],
        ],
        ids=[
            "non-integer-port",
            "bare-port",
            "empty-port-value",
            "unknown-option",
            "stray-argument",
            "duplicate-port",
            "open-with-a-value",
            "misspelt-open",
            "duplicate-open",
            "unknown-subcommand",
            "unknown-option-as-subcommand",
        ],
    )
    def test_malformed_invocations_exit_two_with_usage_on_stderr(
        self, argv, recorded_run, capsys, root_logger_guard
    ):
        assert main_mod.main(argv) == 2

        captured = capsys.readouterr()
        assert captured.out == ""
        assert "usage: artificial-planeswalker" in captured.err
        assert recorded_run.calls == []

    def test_help_is_not_an_error(self, capsys):
        """``-h``/``--help`` prints the same text on **stdout** and exits 0 (AC 4)."""
        for flag in ("-h", "--help"):
            assert main_mod.main([flag]) == 0

            captured = capsys.readouterr()
            assert "usage: artificial-planeswalker" in captured.out
            assert captured.err == ""

    def test_help_after_the_companion_subcommand_is_not_an_error_either(
        self, recorded_run, capsys, root_logger_guard
    ):
        """A user asking for help has made no error, wherever the flag sits (c1-9 review
        ruling extending Decide-once #5): usage on stdout, exit 0, and the backend never runs."""
        for flag in ("-h", "--help"):
            assert main_mod.main(["companion", flag]) == 0

            captured = capsys.readouterr()
            assert "usage: artificial-planeswalker" in captured.out
            assert captured.err == ""
            assert recorded_run.calls == []

    def test_the_usage_text_names_every_valid_shape(self):
        for expected in ("artificial-planeswalker", "companion", "--port", "--open", "--help"):
            assert expected in main_mod._USAGE

    def test_the_usage_text_names_no_port_number(self):
        """TestNothingElseHardcodesThePort scans this file; the default is described in words."""
        assert "8765" not in main_mod._USAGE
        assert "the default port" in main_mod._USAGE


class TestArgvHandling:
    """AC 1: ``argv`` is resolved once, and a passed value is never second-guessed."""

    def test_an_explicit_argv_is_used_instead_of_sys_argv(self, monkeypatch, recorded_run):
        """Under pytest ``sys.argv[1:]`` is full of pytest's own flags; a dispatcher that fell back
        to it would try to dispatch ``-q`` and return 2 (gotcha 6)."""
        import sys

        fake = _FakeServer()
        monkeypatch.setattr(main_mod, "build_server", lambda: fake)
        monkeypatch.setattr(sys, "argv", ["artificial-planeswalker", "--not-a-real-flag"])

        assert main_mod.main([]) == 0
        assert fake.transport == "stdio"
        assert recorded_run.calls == []

    def test_sys_argv_is_the_default(self, monkeypatch, recorded_run, root_logger_guard):
        import sys

        monkeypatch.setattr(sys, "argv", ["artificial-planeswalker", "companion", "--port", "4242"])

        assert main_mod.main() == 0
        assert recorded_run.calls == [4242]


class TestMcpJsonNeedsNoChange:
    """AC 14: neither .mcp.json passes through the console script, and a test says so."""

    def test_mcp_json_registers_server(self):
        """The repo-root .mcp.json registers the server for Claude Code (AC1)."""
        mcp_json = Path(__file__).parents[3] / ".mcp.json"
        data = json.loads(mcp_json.read_text(encoding="utf-8"))

        server = data["mcpServers"]["artificial-planeswalker"]
        assert server["command"] == "uv"
        assert server["args"] == ["run", "python", "-m", "src.mcp_server"]

    def test_plugin_mcp_json_registers_server(self):
        """The committed plugin mirror invokes the module directly too (AC 14)."""
        mcp_json = Path(__file__).parents[3] / "plugin" / ".mcp.json"
        data = json.loads(mcp_json.read_text(encoding="utf-8"))

        server = data["mcpServers"]["artificial-planeswalker"]
        assert server["command"] == "uv"
        assert server["args"] == [
            "run",
            "--directory",
            "${CLAUDE_PLUGIN_ROOT}/server",
            "python",
            "-m",
            "src.mcp_server",
        ]

    @pytest.mark.parametrize("relative", [".mcp.json", "plugin/.mcp.json"])
    def test_no_subcommand_follows_the_module_path(self, relative):
        """The assertion that goes red if a future story rewrites either file into
        ``artificial-planeswalker companion`` — the exact regression AD-14 rules out."""
        mcp_json = Path(__file__).parents[3] / relative
        data = json.loads(mcp_json.read_text(encoding="utf-8"))

        args = data["mcpServers"]["artificial-planeswalker"]["args"]
        assert args[-3:] == ["python", "-m", "src.mcp_server"]
        assert "artificial-planeswalker" not in args
        assert "companion" not in args

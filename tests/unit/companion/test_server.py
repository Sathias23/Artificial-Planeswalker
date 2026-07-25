"""Story c1-3: port selection, the ephemeral fallback and the printed launch URL.

Every bind test here uses a **real** loopback socket. Mocking ``socket.socket.bind`` to raise would
prove only that an exception is caught, not that a genuinely occupied port produces a working
alternative — and the fallback is the whole point of the story (AC 11).

No test binds :data:`~src.companion.app.server.DEFAULT_PORT`. Occupying an ephemeral port and
passing it in as the *preferred* one exercises an identical code path while staying immune to a
real companion, another dev process, or a parallel CI job holding 8765 (Gotcha 8).
"""

import ast
import logging
import os
import socket
from pathlib import Path

import pytest

from src.companion.app import server
from src.companion.app.main import bound_port, build_app

REPO_ROOT = Path(__file__).resolve().parents[3]


class _Loopback:
    """Hands out real loopback ports and keeps every socket it opened for teardown."""

    def __init__(self):
        self._opened: list[socket.socket] = []

    def occupy(self, port: int = 0) -> socket.socket:
        """Bind *and listen on* a loopback port so nothing else can take it.

        ``listen()`` matters: on Linux a merely-bound socket can be re-bound by a second socket
        when both set ``SO_REUSEADDR``, which is exactly what this module does on POSIX. A
        listening socket is refused on every platform, so the "occupied" premise holds identically
        on Brad's Windows box and on CI's Linux runners (Gotcha 9).

        Args:
            port: The port to take, or ``0`` to let the kernel choose.

        Returns:
            The listening socket.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Tracked before bind/listen: if either raises, teardown still closes the socket.
        self._opened.append(sock)
        sock.bind((server.HOST, port))
        sock.listen(1)
        return sock

    def track(self, sock: socket.socket) -> socket.socket:
        """Adopt an externally created socket into this helper's teardown.

        This is how tests own sockets returned by ``bind_localhost_socket()`` without per-test
        ``try/finally`` — the testing standard this story set for itself.

        Args:
            sock: The socket to close at teardown.

        Returns:
            The same socket, for inline use.
        """
        self._opened.append(sock)
        return sock

    def free_port(self) -> int:
        """Return a loopback port that was free a moment ago.

        Reserving an ephemeral port and immediately releasing it is the standard way to name a
        port that is very likely free without ever touching :data:`server.DEFAULT_PORT`.

        Returns:
            A port number no longer held by this process.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((server.HOST, 0))
        port: int = sock.getsockname()[1]
        sock.close()
        return port

    def close_all(self) -> None:
        """Close every socket this helper opened; one failing close must not strand the rest."""
        for sock in self._opened:
            try:
                sock.close()
            except OSError:
                pass


@pytest.fixture
def loopback():
    """Yield a :class:`_Loopback` helper and close everything it opened at teardown.

    Teardown lives here rather than in per-test ``try/finally`` because a leaked listener on
    Windows surfaces as a failure in some *later* test — the worst kind of flake to diagnose.

    Yields:
        The helper.
    """
    helper = _Loopback()
    yield helper
    helper.close_all()


def _port_of(sock: socket.socket) -> int:
    """Return the port a bound socket actually got.

    Args:
        sock: A bound socket.

    Returns:
        The kernel-assigned (or requested) port number.
    """
    port: int = sock.getsockname()[1]
    return port


class TestPortResolution:
    """AC 1 + AC 3: argument beats env var beats default, and bad values are ignored loudly."""

    def test_defaults_when_nothing_is_configured(self, monkeypatch):
        monkeypatch.delenv(server.PORT_ENV_VAR, raising=False)

        assert server.resolve_preferred_port() == server.DEFAULT_PORT
        assert server.DEFAULT_PORT == 8765

    def test_env_var_is_honoured(self, monkeypatch):
        monkeypatch.setenv(server.PORT_ENV_VAR, "9100")

        assert server.resolve_preferred_port() == 9100

    def test_explicit_argument_beats_the_env_var(self, monkeypatch):
        monkeypatch.setenv(server.PORT_ENV_VAR, "9100")

        assert server.resolve_preferred_port(9200) == 9200

    def test_zero_is_a_legal_configured_value(self, monkeypatch):
        """AC 3: ``0`` means "go straight to ephemeral", not "unset"."""
        monkeypatch.delenv(server.PORT_ENV_VAR, raising=False)

        assert server.resolve_preferred_port(0) == 0

        monkeypatch.setenv(server.PORT_ENV_VAR, "0")
        assert server.resolve_preferred_port() == 0

    @pytest.mark.parametrize("raw", ["not-a-port", "", "80.5", "-1", "65536", "999999"])
    def test_unusable_env_values_fall_back_to_the_default_with_a_warning(
        self, monkeypatch, caplog, raw
    ):
        monkeypatch.setenv(server.PORT_ENV_VAR, raw)

        with caplog.at_level(logging.WARNING, logger=server.__name__):
            resolved = server.resolve_preferred_port()

        assert resolved == server.DEFAULT_PORT
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 1
        assert server.PORT_ENV_VAR in warnings[0].getMessage()

    @pytest.mark.parametrize("explicit", [-1, 65536])
    def test_unusable_explicit_values_fall_back_to_the_default_with_a_warning(
        self, monkeypatch, caplog, explicit
    ):
        """c1-9 feeds a user-supplied ``--port`` through this argument, so it validates too."""
        monkeypatch.delenv(server.PORT_ENV_VAR, raising=False)

        with caplog.at_level(logging.WARNING, logger=server.__name__):
            resolved = server.resolve_preferred_port(explicit)

        assert resolved == server.DEFAULT_PORT
        assert [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestBind:
    """AC 1 + AC 2 + AC 9: loopback IPv4 only, a conflict never exits, nothing leaks."""

    def test_a_free_port_is_taken_exactly(self, loopback):
        wanted = loopback.free_port()

        sock = loopback.track(server.bind_localhost_socket(wanted))

        assert _port_of(sock) == wanted

    def test_the_socket_is_loopback_ipv4_stream(self, loopback):
        sock = loopback.track(server.bind_localhost_socket(loopback.free_port()))

        assert sock.family == socket.AF_INET
        assert sock.type == socket.SOCK_STREAM
        assert sock.getsockname()[0] == "127.0.0.1"

    def test_an_occupied_port_falls_back_to_a_different_one(self, loopback):
        taken = _port_of(loopback.occupy())

        sock = loopback.track(server.bind_localhost_socket(taken))
        actual = _port_of(sock)

        assert actual != taken
        assert actual != 0
        assert sock.getsockname()[0] == "127.0.0.1"

    def test_zero_goes_straight_to_an_ephemeral_port(self, loopback):
        sock = loopback.track(server.bind_localhost_socket(0))

        assert _port_of(sock) != 0

    def test_the_failed_attempt_is_closed_before_the_fallback(self, loopback, monkeypatch):
        """AC 9: the conflicting socket is released, not left dangling for the GC to reap."""
        taken = _port_of(loopback.occupy())
        created: list[socket.socket] = []
        real_socket = socket.socket

        def recording(*args, **kwargs):
            sock = real_socket(*args, **kwargs)
            created.append(sock)
            return sock

        # Patched *after* the port is occupied, so only the sockets this call creates are recorded.
        monkeypatch.setattr(server.socket, "socket", recording)

        sock = loopback.track(server.bind_localhost_socket(taken))

        assert len(created) == 2, "expected one failed attempt and one ephemeral fallback"
        assert created[0].fileno() == -1, "the socket whose bind failed was not closed"
        assert created[1] is sock

    def test_reuseaddr_follows_asyncios_own_platform_policy(self, loopback):
        """Gotcha 2: wanted on POSIX (``TIME_WAIT``), actively harmful on Windows."""
        sock = loopback.track(server.bind_localhost_socket(loopback.free_port()))
        enabled = bool(sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR))

        assert enabled is (os.name == "posix")

    def test_exclusiveaddruse_is_set_on_windows_only(self, loopback):
        """c1-5 AC 10: nothing else on the machine may bind over a port the companion holds.

        The complement of the rule above — omitting ``SO_REUSEADDR`` stops *us* binding over
        someone else; this stops another local process's ``SO_REUSEADDR`` binding over *us*.
        """
        option = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        sock = loopback.track(server.bind_localhost_socket(loopback.free_port()))

        if option is None:
            # Absent everywhere but Windows; asserting that keeps this from silently becoming a
            # no-op test if the constant ever appears elsewhere.
            assert os.name != "nt"
            return
        assert bool(sock.getsockopt(socket.SOL_SOCKET, option)) is (os.name == "nt")

    def test_a_failing_ephemeral_bind_propagates(self, monkeypatch):
        """AC 2: the fallback absorbs a conflict, not a machine with no usable sockets at all."""

        def explode(self, address):
            raise OSError("no sockets for you")

        monkeypatch.setattr(socket.socket, "bind", explode)

        with pytest.raises(OSError, match="no sockets for you"):
            server.bind_localhost_socket(server.DEFAULT_PORT)


class TestBoundPortAccessor:
    """AC 4 (AD-4): the single seam c1-5 and c1-7 read the live port through."""

    def test_absence_means_not_bound(self):
        """Mirrors c1-2's ``instance_id`` convention: constructed is not serving."""
        assert bound_port(build_app()) is None

    def test_returns_the_port_the_lifespan_was_given(self):
        app = build_app()
        app.state.bound_port = 9321

        assert bound_port(app) == 9321


class _RecordingServe:
    """A stand-in for :func:`server._serve` that records its arguments and serves nothing.

    The socket's *own* port is read here, while the socket is still open — ``run()`` closes it
    before returning, so a test cannot ask afterwards. Recording it separately from the ``port``
    argument is what makes "state carries the real bound port" a genuine claim rather than a
    tautology about a number the runner passed itself.
    """

    def __init__(self):
        self.calls: list[tuple[object, socket.socket, int]] = []
        self.socket_ports: list[int] = []

    def __call__(self, app, sock, port):
        self.calls.append((app, sock, port))
        self.socket_ports.append(sock.getsockname()[1])

    @property
    def app(self):
        return self.calls[0][0]

    @property
    def sock(self) -> socket.socket:
        return self.calls[0][1]

    @property
    def port(self) -> int:
        return self.calls[0][2]

    @property
    def socket_port(self) -> int:
        """The port the socket actually held, read during the call."""
        return self.socket_ports[0]


@pytest.fixture
def recorded_serve(monkeypatch):
    """Replace the serving seam so no test in this module ever starts a server.

    Returns:
        The :class:`_RecordingServe` installed in place of ``server._serve``.
    """
    stub = _RecordingServe()
    monkeypatch.setattr(server, "_serve", stub)
    return stub


class TestRun:
    """AC 4 + AC 6 + AC 9: bind, publish the port, print the URL, never leak the socket."""

    def test_state_carries_the_real_bound_port(self, recorded_serve, loopback):
        server.run(port=loopback.free_port())

        app = recorded_serve.app
        assert app.state.bound_port == recorded_serve.socket_port
        assert bound_port(app) == recorded_serve.socket_port

    def test_the_url_line_lands_on_stdout_with_the_actual_port(
        self, recorded_serve, loopback, capsys
    ):
        wanted = loopback.free_port()

        server.run(port=wanted)

        out = capsys.readouterr().out
        assert (
            f"[planeswalker] companion running at http://127.0.0.1:{wanted} — "
            "open this URL in your browser (Ctrl-C to stop)"
        ) in out
        assert "localhost" not in out

    def test_no_fallback_line_when_the_preferred_port_was_free(
        self, recorded_serve, loopback, capsys
    ):
        server.run(port=loopback.free_port())

        assert "falling back" not in capsys.readouterr().out

    def test_a_conflict_prints_the_fallback_line_then_the_real_url(
        self, recorded_serve, loopback, capsys
    ):
        taken = _port_of(loopback.occupy())

        server.run(port=taken)

        out = capsys.readouterr().out
        actual = recorded_serve.socket_port
        assert actual != taken
        fallback = f"[planeswalker] port {taken} is unavailable — falling back to an ephemeral port"
        assert fallback in out
        assert out.index(fallback) < out.index(f"http://127.0.0.1:{actual}")

    def test_an_explicit_zero_is_not_reported_as_a_conflict(self, recorded_serve, capsys):
        """``0`` asks for an ephemeral port; getting one is success, not a fallback."""
        server.run(port=0)

        out = capsys.readouterr().out
        assert "falling back" not in out
        assert f"http://127.0.0.1:{recorded_serve.socket_port}" in out

    def test_the_env_var_reaches_the_bind(self, recorded_serve, loopback, monkeypatch):
        wanted = loopback.free_port()
        monkeypatch.setenv(server.PORT_ENV_VAR, str(wanted))

        server.run()

        assert recorded_serve.port == wanted

    def test_the_socket_is_closed_when_run_returns(self, recorded_serve, loopback):
        server.run(port=loopback.free_port())

        assert recorded_serve.sock.fileno() == -1

    def test_the_socket_is_closed_when_serving_raises(self, monkeypatch, loopback):
        captured: list[socket.socket] = []

        def boom(app, sock, port):
            captured.append(sock)
            raise RuntimeError("serve exploded")

        monkeypatch.setattr(server, "_serve", boom)

        with pytest.raises(RuntimeError, match="serve exploded"):
            server.run(port=loopback.free_port())

        assert captured[0].fileno() == -1


class TestServeConfiguration:
    """AC 7 + AC 10: uvicorn is handed the pre-bound socket, single-worker, lifespan on."""

    def test_uvicorn_is_given_the_socket_and_this_processs_settings(self, monkeypatch, loopback):
        captured: dict[str, object] = {}

        class FakeServer:
            def __init__(self, config):
                captured["config"] = config

            def run(self, sockets=None):
                captured["sockets"] = sockets

        monkeypatch.setattr(server.uvicorn, "Server", FakeServer)
        sock = loopback.track(server.bind_localhost_socket(loopback.free_port()))
        port = _port_of(sock)
        server._serve(build_app(), sock, port)

        config = captured["config"]
        assert captured["sockets"] == [sock], (
            "uvicorn must serve the pre-bound socket — letting it bind runs the lifespan "
            "before the port exists (Decide-once #1)"
        )
        assert config.lifespan == "on"
        assert config.workers == 1
        assert config.host == "127.0.0.1"
        assert config.port == port


def _python_files(*directories: Path) -> list[Path]:
    """Return every ``*.py`` file under *directories*, excluding ``__pycache__``.

    Args:
        *directories: Directories to walk recursively.

    Returns:
        A sorted list of Python source files.

    Raises:
        AssertionError: If any *single* directory yields nothing — an aggregate check would let a
            renamed or typo'd directory silently narrow the scan while the other side keeps it
            green (c1-1's dead-guard lesson, one level down).
    """
    files: list[Path] = []
    for directory in directories:
        found = [path for path in directory.rglob("*.py") if "__pycache__" not in path.parts]
        assert found, f"scan found no Python files under {directory} — check the path constants"
        files.extend(found)
    return sorted(files)


class TestNothingElseHardcodesThePort:
    """AC 5 (AD-4): the port number is defined once, and this test is what keeps it that way."""

    def test_only_the_runner_names_the_default_port(self):
        # tests/ is out of scope — this very file must name the number — and plugin/ is a verbatim
        # generated copy of src/, so scanning it would only ever double-report src/'s findings.
        # AST numeric literals, not a substring match: `8_765` and hex spellings cannot evade the
        # scan, and `18765` or a hash in a comment cannot false-positive it.
        offenders: list[str] = []
        legal = 0

        for path in _python_files(REPO_ROOT / "src", REPO_ROOT / "scripts"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            names_the_port = any(
                isinstance(node, ast.Constant)
                and not isinstance(node.value, bool)
                and node.value == 8765
                for node in ast.walk(tree)
            )
            if not names_the_port:
                continue
            relative = path.resolve().relative_to(REPO_ROOT).as_posix()
            if relative == "src/companion/app/server.py":
                legal += 1
            else:
                offenders.append(relative)

        assert not offenders, (
            f"8765 is hardcoded outside the runner: {offenders}. Read it from "
            "src.companion.app.server.DEFAULT_PORT, or the bound value via main.bound_port(app)."
        )
        assert legal == 1, (
            "the scan did not find 8765 in src/companion/app/server.py — the guard is vacuous "
            "and would pass even if the constant were deleted"
        )


class TestNothingBindsBeyondLoopback:
    """AC 1 / NFR-01: every bind in the companion targets the ``HOST`` constant, not a literal."""

    def test_every_bind_target_is_the_host_constant(self):
        binds: list[tuple[str, int, str]] = []

        for path in _python_files(REPO_ROOT / "src" / "companion"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            relative = path.resolve().relative_to(REPO_ROOT).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute) or node.func.attr != "bind":
                    continue
                if not node.args:
                    binds.append((relative, node.lineno, "<no address argument>"))
                    continue
                address = node.args[0]
                host = address.elts[0] if isinstance(address, ast.Tuple) and address.elts else None
                binds.append((relative, node.lineno, ast.unparse(host) if host else "<not a pair>"))

        assert binds, (
            "no bind() call found under src/companion/ — the NFR-01 guard is vacuous. If the bind "
            "moved, point this scan at its new home rather than deleting it."
        )
        # Exactly the bare name `HOST`, not a suffix match: `other_module.HOST` could carry any
        # value, so an attribute that merely *ends* in HOST must fail loudly and be reviewed here.
        offenders = [entry for entry in binds if entry[2] != "HOST"]
        assert not offenders, (
            f"a bind target other than the HOST constant was found: {offenders}. NFR-01 makes "
            "127.0.0.1 the security envelope — 0.0.0.0, '::', '' and 'localhost' are all forbidden."
        )

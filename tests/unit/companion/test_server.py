"""Story c1-3: port selection, the ephemeral fallback and the printed launch URL.

Every bind test here uses a **real** loopback socket. Mocking ``socket.socket.bind`` to raise would
prove only that an exception is caught, not that a genuinely occupied port produces a working
alternative — and the fallback is the whole point of the story (AC 11).

No test binds :data:`~src.companion.app.server.DEFAULT_PORT`. Occupying an ephemeral port and
passing it in as the *preferred* one exercises an identical code path while staying immune to a
real companion, another dev process, or a parallel CI job holding 8765 (Gotcha 8).
"""

import ast
import io
import logging
import os
import socket
import sys
import webbrowser
from pathlib import Path

import httpx
import pytest

from src.companion import client, discovery
from src.companion.app import server, singleton
from src.companion.app.main import bound_port, build_app
from tests.unit.companion.test_client import StubFleet, health_bytes, plant_discovery

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


@pytest.fixture
def stub_server():
    """Yield the stub-server factory c1-8's ``run()`` cases stand a live companion up with.

    Shares :class:`~tests.unit.companion.test_client.StubFleet` with ``test_client.py`` rather than
    copying its shutdown-and-join teardown; see that class's docstring for why the fixture itself
    is declared per module.

    Yields:
        ``start(*, status=200, body=b"", content_type="application/json")``.
    """
    fleet = StubFleet()
    yield fleet.start
    fleet.close_all()


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


class TestSingleInstanceCheck:
    """Story c1-8, AC 7-12: a live companion refuses the launch; anything else is reclaimed.

    Every test here plants its own discovery file, because ``recorded_serve`` means the lifespan
    never runs in this module and so nothing writes one. The files are written by hand rather than
    through ``write_discovery`` — a fixture built by the code under test proves nothing.

    The class pairs deliberately: each *refuses* case sits beside a *proceeds* case driven through
    the same ``run()`` call, so the suite cannot pass by refusing everything or by never refusing.
    """

    @pytest.fixture(autouse=True)
    def _fast_probe(self, monkeypatch):
        """Shrink the probe deadline for this class, so the dead-port cases cost milliseconds.

        ``run()`` takes no timeout argument — AC 20 keeps its signature — so the module constant is
        the only seam a test has. The *production* connect/read split is pinned by
        ``test_client.py::TestExportedSurface``, so shrinking it here cannot quietly erase the
        measured trade AC 3 made.
        """
        monkeypatch.setattr(
            client,
            "PROBE_TIMEOUT",
            httpx.Timeout(connect=0.25, read=0.25, write=0.25, pool=0.25),
        )

    def test_a_verified_live_instance_refuses_and_names_its_url(
        self, recorded_serve, stub_server, loopback, capsys
    ):
        """AC 8: one line on stdout carrying the *live* instance's port, not this launch's."""
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")

        server.run(port=loopback.free_port())

        out = capsys.readouterr().out
        assert (
            f"[planeswalker] companion is already running at http://127.0.0.1:{stub.port} — "
            "open that URL, or stop the other instance before starting a new one"
        ) in out
        assert "companion running at" not in out, "the launch line must not also be printed"

    def test_a_refusal_returns_rather_than_raising(self, recorded_serve, stub_server, loopback):
        """Decide-once #3: refusing is a success, so ``run()`` returns and the process exits 0."""
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")

        assert server.run(port=loopback.free_port()) is None

    def test_a_refusal_builds_no_app_and_never_serves(self, recorded_serve, stub_server, loopback):
        """AC 9: a launch that will not serve must not construct what it will never use."""
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")

        server.run(port=loopback.free_port())

        assert recorded_serve.calls == []

    def test_a_refusal_never_reaches_the_bind(self, recorded_serve, stub_server, loopback, capsys):
        """AC 7: ordering is behaviour — a refusing launch must not momentarily hold a port.

        The preferred port is occupied *first*. Had ``run()`` reached the bind it would have taken
        the ephemeral fallback and said so on stdout, exactly as
        ``TestRun::test_a_conflict_prints_the_fallback_line_then_the_real_url`` shows it does.
        Silence on that line is the evidence the bind never happened.
        """
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")
        taken = _port_of(loopback.occupy())

        server.run(port=taken)

        out = capsys.readouterr().out
        assert "already running" in out
        assert "falling back" not in out

    def test_a_refusal_leaves_the_preferred_port_free(self, recorded_serve, stub_server, loopback):
        """AC 9: nothing was claimed, so the port this launch wanted is still free afterwards."""
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")
        preferred = loopback.free_port()

        server.run(port=preferred)

        sock = loopback.track(server.bind_localhost_socket(preferred))
        assert _port_of(sock) == preferred

    def test_a_refusal_leaves_the_discovery_file_byte_identical(
        self, recorded_serve, stub_server, loopback
    ):
        """AC 9: the live instance's rendezvous survives a refused launch untouched.

        Not automatic — it is a consequence of returning before the lifespan, and a refactor that
        moved the check into the lifespan would break it silently.
        """
        stub = stub_server(body=health_bytes("inst-live"))
        path = plant_discovery(port=stub.port, instance_id="inst-live")
        before = path.read_bytes()

        server.run(port=loopback.free_port())

        assert path.read_bytes() == before

    def test_the_refusal_line_survives_a_non_utf8_stdout(
        self, recorded_serve, stub_server, loopback, monkeypatch
    ):
        """AC 8: printed *after* the reconfigure — it carries an em dash like every launch line.

        Encoding the message strictly as ASCII would raise ``UnicodeEncodeError``; the replacement
        character in its place is what proves the guard ran before the print rather than after it.
        """
        buffer = io.BytesIO()
        monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(buffer, encoding="ascii"))
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")

        server.run(port=loopback.free_port())
        sys.stdout.flush()

        text = buffer.getvalue().decode("ascii")
        assert "companion is already running at" in text
        assert "?" in text, "the em dash should have been replaced, not raised on"

    def test_a_stale_entry_is_reclaimed_and_the_launch_proceeds(
        self, recorded_serve, loopback, capsys
    ):
        """AC 10 (AD-15): a crashed instance's leftovers are the ordinary post-crash state."""
        path = plant_discovery(port=loopback.free_port(), instance_id="inst-crashed")
        before = path.read_bytes()

        server.run(port=loopback.free_port())

        assert recorded_serve.calls, "a stale file must not stop the launch"
        assert "already running" not in capsys.readouterr().out
        assert path.read_bytes() == before, "Decide-once #4: a reclaim deletes nothing"

    def test_the_reclaim_logs_at_info_not_warning(self, recorded_serve, loopback, caplog):
        """AC 10: a stale file after a crash is expected, not something worth warning about."""
        plant_discovery(port=loopback.free_port(), instance_id="inst-crashed")

        with caplog.at_level(logging.DEBUG, logger=server.__name__):
            server.run(port=loopback.free_port())

        reclaims = [r for r in caplog.records if "reclaim" in r.getMessage().lower()]
        assert len(reclaims) == 1, [r.getMessage() for r in caplog.records]
        assert reclaims[0].levelno == logging.INFO
        # Scoped to this project's loggers: a third-party library warning about something
        # unrelated must not read as "the reclaim path warned" (review finding, c1-8).
        assert not [
            r for r in caplog.records if r.name.startswith("src.") and r.levelno >= logging.WARNING
        ]

    def test_a_clean_machine_logs_no_reclaim(self, recorded_serve, loopback, caplog):
        """Non-vacuity for the test above: the INFO names a *reclaim*, so a first start is quiet."""
        assert not discovery.discovery_path().exists()

        with caplog.at_level(logging.DEBUG, logger=server.__name__):
            server.run(port=loopback.free_port())

        assert recorded_serve.calls
        assert not [r for r in caplog.records if "reclaim" in r.getMessage().lower()]

    def test_a_foreign_identity_on_the_recorded_port_is_treated_as_dead(
        self, recorded_serve, stub_server, loopback, capsys
    ):
        """AC 11: something answered, but it is not the process the file describes.

        The mechanism test for the runner half — delete the check and this launch would refuse
        rather than proceed.
        """
        stub = stub_server(body=health_bytes("some-other-process"))
        path = plant_discovery(port=stub.port, instance_id="inst-crashed", token="tok-not-sent")
        before = path.read_bytes()

        server.run(port=loopback.free_port())

        assert recorded_serve.calls
        assert "already running" not in capsys.readouterr().out
        assert path.read_bytes() == before
        assert len(stub.requests) == 1, "it was asked, and its answer was disbelieved"
        assert "tok-not-sent" not in stub.requests[0].as_text(), (
            "AC 11: a foreign process is reclaimed *having been sent nothing*"
        )

    def test_a_server_that_is_not_a_companion_at_all_is_treated_as_dead(
        self, recorded_serve, stub_server, loopback, capsys
    ):
        """AC 11: a recycled port held by an unrelated local server answering 200 to everything."""
        stub = stub_server(body=b"<html>some other dev server</html>", content_type="text/html")
        plant_discovery(port=stub.port, instance_id="inst-crashed")

        server.run(port=loopback.free_port())

        assert recorded_serve.calls
        assert "already running" not in capsys.readouterr().out

    def test_an_explicit_port_does_not_bypass_the_check(
        self, recorded_serve, stub_server, loopback, capsys
    ):
        """AC 12: the rendezvous is the singleton, not the port — one file, one instance."""
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")
        elsewhere = loopback.free_port()
        assert elsewhere != stub.port

        server.run(port=elsewhere)

        assert "already running" in capsys.readouterr().out
        assert recorded_serve.calls == []

    def test_the_env_var_port_does_not_bypass_the_check(
        self, recorded_serve, stub_server, loopback, monkeypatch, capsys
    ):
        """AC 12: the environment override is a port preference, not an escape hatch."""
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")
        monkeypatch.setenv(server.PORT_ENV_VAR, str(loopback.free_port()))

        server.run()

        assert "already running" in capsys.readouterr().out
        assert recorded_serve.calls == []


class TestHeldInstanceLock:
    """Story c1-9, AC 12-15: the lock closes the startup window the identity probe cannot.

    These pair with :class:`TestSingleInstanceCheck` above rather than duplicating it. That class
    covers the *informative* refusal — a verified-live companion whose URL can be named; this one
    covers the *atomic* refusal, where the probe has already found nothing findable and only the
    lock can answer "am I first?". Every test here contends with a lock the test itself holds, on a
    real descriptor under this test's own ``PLANESWALKER_DATA_DIR``.

    Refuses-cases sit beside proceeds-cases here too, so the class cannot pass by refusing
    everything: with the lock free, the identical ``run()`` call serves.
    """

    @pytest.fixture
    def held_elsewhere(self):
        """Hold the instance lock for the duration of a test, as a competing launch would.

        AC 9's primitive choice is what makes this possible in one process: ``flock`` is per
        open-file-description and Windows' ``msvcrt.locking`` denies a second descriptor outright,
        so the test needs no child process to contend realistically. Swap in ``lockf`` and this
        fixture stops contending at all — which is precisely the mutation AC 15 requires to go red.
        """
        fd = singleton.acquire_instance_lock()
        assert fd is not None, "the lock must be free before a contention test can hold it"
        try:
            yield fd
        finally:
            singleton.release_instance_lock(fd)

    def test_a_contended_launch_prints_the_refusal_line(
        self, recorded_serve, loopback, held_elsewhere, capsys
    ):
        """AC 13: one line, naming no URL, because none can be named honestly."""
        server.run(port=loopback.free_port())

        out = capsys.readouterr().out
        assert (
            "[planeswalker] another companion is already starting up — "
            "wait for it to print its URL, or stop it before starting a new one"
        ) in out
        assert "companion running at" not in out
        assert "already running at" not in out, "no second probe, so no URL may be claimed"

    def test_a_contended_launch_never_serves(self, recorded_serve, loopback, held_elsewhere):
        server.run(port=loopback.free_port())

        assert recorded_serve.calls == []

    def test_an_uncontended_launch_serves(self, recorded_serve, loopback):
        """The paired proceeds-case: the same call, with the lock free, does serve.

        Without this, deleting the ``acquire_instance_lock`` call from ``run()`` would leave the
        contention tests red and everything else green — but a ``run()`` that refused
        unconditionally would pass the contention tests too.
        """
        server.run(port=loopback.free_port())

        assert len(recorded_serve.calls) == 1

    def test_a_contended_launch_returns_rather_than_raising(
        self, recorded_serve, loopback, held_elsewhere
    ):
        """Decide-once #5: both refusals are successes, so the process exits 0."""
        assert server.run(port=loopback.free_port()) is None

    def test_a_contended_launch_leaves_the_preferred_port_free(
        self, recorded_serve, loopback, held_elsewhere
    ):
        """AC 13: a refusal touches nothing — no port resolution, no bind."""
        preferred = loopback.free_port()

        server.run(port=preferred)

        sock = loopback.track(server.bind_localhost_socket(preferred))
        assert _port_of(sock) == preferred

    def test_a_contended_launch_leaves_the_discovery_file_byte_identical(
        self, recorded_serve, loopback, held_elsewhere
    ):
        """AC 13: the rendezvous of whoever is starting up survives untouched."""
        path = plant_discovery(port=51234, instance_id="inst-other")
        before = path.read_bytes()

        server.run(port=loopback.free_port())

        assert path.read_bytes() == before

    def test_the_probe_runs_before_the_lock(self, recorded_serve, stub_server, loopback, capsys):
        """Decide-once #2: a verified-live instance still gets the *informative* refusal.

        The lock is free here, so a lock-first ordering would proceed to serve and this launch
        would never name the live instance's URL — which is exactly what would have invalidated
        c1-8's fourteen ``TestSingleInstanceCheck`` cases had the order been reversed.
        """
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")

        server.run(port=loopback.free_port())

        assert "already running at" in capsys.readouterr().out
        assert recorded_serve.calls == []

    def test_the_lock_is_released_when_run_returns(self, recorded_serve, loopback):
        """AC 12: the release is in the outermost ``finally``, so a fresh acquire succeeds after."""
        server.run(port=loopback.free_port())

        fd = singleton.acquire_instance_lock()
        assert fd is not None, "run() must not still be holding the lock after it returns"
        singleton.release_instance_lock(fd)

    def test_the_lock_file_survives_a_normal_run(self, recorded_serve, loopback, tmp_path):
        """AC 10: never unlinked — on POSIX ``flock`` binds to the inode."""
        server.run(port=loopback.free_port())

        assert (tmp_path / singleton.LOCK_FILENAME).exists()

    def test_the_lock_is_released_when_serving_raises(self, monkeypatch, loopback):
        """The outer ``finally`` sits below the socket's, so the lock outlives every resource."""

        def boom(app, sock, port):
            raise RuntimeError("serve exploded")

        monkeypatch.setattr(server, "_serve", boom)

        with pytest.raises(RuntimeError, match="serve exploded"):
            server.run(port=loopback.free_port())

        fd = singleton.acquire_instance_lock()
        assert fd is not None, "a crashing serve must still release the lock"
        singleton.release_instance_lock(fd)

    def test_the_lock_is_held_while_serving(self, monkeypatch, loopback):
        """The non-vacuity anchor for "held": during ``_serve`` the lock must be unavailable."""
        observed: list[int | None] = []

        def capture(app, sock, port):
            observed.append(singleton.acquire_instance_lock())

        monkeypatch.setattr(server, "_serve", capture)

        server.run(port=loopback.free_port())

        assert observed == [None], "run() must hold the lock for the whole serve"


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


class _RecordingBrowser:
    """Stands in for ``webbrowser.open``: records the URLs, answers or raises as scripted."""

    def __init__(self, *, result: bool = True, raises: Exception | None = None) -> None:
        self.result = result
        self.raises = raises
        self.urls: list[str] = []

    def __call__(self, url: str) -> bool:
        self.urls.append(url)
        if self.raises is not None:
            raise self.raises
        return self.result


@pytest.fixture
def browser(monkeypatch):
    """Replace ``webbrowser.open`` so no test here ever pops a real browser.

    Returns:
        ``install(result=True, raises=None)`` -> the recorder.
    """

    def install(*, result: bool = True, raises: Exception | None = None) -> _RecordingBrowser:
        recorder = _RecordingBrowser(result=result, raises=raises)
        monkeypatch.setattr(server.webbrowser, "open", recorder)
        return recorder

    return install


class TestOpenBrowser:
    """17.4: ``--open`` is its own ``webbrowser.open``, after the URL line, never fatal."""

    def test_off_by_default(self, recorded_serve, loopback, browser):
        opened = browser()

        server.run(port=loopback.free_port())

        assert opened.urls == []

    def test_opens_the_url_the_launch_line_printed(self, recorded_serve, loopback, browser, capsys):
        opened = browser()
        wanted = loopback.free_port()

        server.run(port=wanted, open_browser=True)

        assert opened.urls == [f"http://127.0.0.1:{wanted}"]
        assert f"http://127.0.0.1:{wanted}" in capsys.readouterr().out
        assert recorded_serve.calls, "the browser opening must not pre-empt serving"

    def test_opens_the_real_port_after_a_fallback(self, recorded_serve, loopback, browser):
        """The URL handed to the browser is the bound one, not the preferred one."""
        opened = browser()
        taken = _port_of(loopback.occupy())

        server.run(port=taken, open_browser=True)

        assert opened.urls == [f"http://127.0.0.1:{recorded_serve.socket_port}"]

    def test_already_running_opens_the_live_instances_url_and_returns(
        self, recorded_serve, stub_server, loopback, browser, capsys
    ):
        """Idempotent by design: the agent may run the launch command whenever no tab is open."""
        opened = browser()
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")

        assert server.run(port=loopback.free_port(), open_browser=True) is None

        assert opened.urls == [f"http://127.0.0.1:{stub.port}"]
        assert "already running" in capsys.readouterr().out
        assert recorded_serve.calls == []

    def test_already_running_without_open_pops_nothing(
        self, recorded_serve, stub_server, loopback, browser
    ):
        opened = browser()
        stub = stub_server(body=health_bytes("inst-live"))
        plant_discovery(port=stub.port, instance_id="inst-live")

        server.run(port=loopback.free_port())

        assert opened.urls == []

    @pytest.mark.parametrize(
        "failure",
        [
            {"result": False},
            {"raises": webbrowser.Error("no browser")},
            {"raises": OSError(2, "x")},
        ],
        ids=["returns-false", "raises-webbrowser-error", "raises-oserror"],
    )
    def test_a_browser_failure_warns_and_still_serves(
        self, recorded_serve, loopback, browser, caplog, failure
    ):
        browser(**failure)
        wanted = loopback.free_port()

        with caplog.at_level(logging.WARNING, logger=server.__name__):
            assert server.run(port=wanted, open_browser=True) is None

        assert recorded_serve.calls, "a browser failure must never stop the serve"
        assert any(
            record.levelno == logging.WARNING and "open it yourself" in record.getMessage()
            for record in caplog.records
        )

    def test_the_browser_is_asked_after_the_url_line(self, recorded_serve, loopback, monkeypatch):
        """Order is the contract: the agent waits for the URL line, and the tab follows it."""
        seen: list[str] = []

        class _Stdout(io.StringIO):
            def write(self, text: str) -> int:
                if "companion running at" in text:
                    seen.append("print")
                return super().write(text)

        def opener(url: str) -> bool:
            seen.append("open")
            return True

        monkeypatch.setattr(server.webbrowser, "open", opener)
        monkeypatch.setattr(sys, "stdout", _Stdout())

        server.run(port=loopback.free_port(), open_browser=True)

        assert "open" in seen
        assert seen.index("open") > seen.index("print")

    def test_the_port_accepts_a_connection_the_moment_the_browser_is_asked(
        self, recorded_serve, loopback, monkeypatch
    ):
        """Pre-cut R5: ``listen()`` precedes the browser, so a fast tab is queued, not refused.

        The connect happens INSIDE the stand-in browser — the exact moment ``_open_browser`` is
        invoked, with ``_serve`` stubbed so uvicorn's own ``listen()`` can never be the one that
        made it work. A bound-but-not-listening socket refuses this connect (``ConnectionRefused``
        on both platforms), so this test is red without the explicit ``listen()``.
        """
        connected: list[int] = []

        def opener(url: str) -> bool:
            port = int(url.rsplit(":", 1)[1])
            with socket.create_connection(("127.0.0.1", port), timeout=1) as probe:
                connected.append(probe.getpeername()[1])
            return True

        monkeypatch.setattr(server.webbrowser, "open", opener)

        server.run(port=loopback.free_port(), open_browser=True)

        assert connected == [recorded_serve.socket_port], (
            "the browser's first connect must land in the backlog of the already-listening "
            "socket, never be refused during the pre-uvicorn window"
        )

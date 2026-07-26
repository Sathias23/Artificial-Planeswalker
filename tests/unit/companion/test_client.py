"""Story c1-8: the leaf identity probe — ``GET /health``, and believing only a matching identity.

Every case here runs against a **real loopback listener**, never a mocked transport. That is c1-3's
ruling restated for a different reason: the failures this probe exists to absorb — a connect that
hangs, a port recycled to an unrelated server, a body that is not our shape — all live in the
transport, and a mocked one would prove only that a mock was called.

The stub servers deliberately come in three flavours, because httpx reports them three different
ways: an HTTP stub that answers (any status, any bytes), a bare listening socket that completes the
TCP handshake and then says nothing (``ReadTimeout``), and a port with nothing on it at all
(``ConnectTimeout`` under a short deadline). Each is one row of AC 4's matrix.

Discovery files are planted with ``Path.write_text(json.dumps(...))`` and never through
``write_discovery`` — a fixture built by the code under test proves nothing (c1-6's rule, restated
by c1-7 AC 15).
"""

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from src.companion import client, discovery
from src.companion.contracts import HealthResponse

FAST = httpx.Timeout(connect=0.25, read=0.25, write=0.25, pool=0.25)
"""The deadline every dead-or-silent case passes, so the suite costs milliseconds, not seconds.

Only those cases: a live stub answers in single-digit milliseconds, so the tests that talk to one
pass nothing and exercise the production default — 250 ms of thread-scheduling headroom on a
loaded CI runner is not margin worth flaking over (review finding, c1-8). Production callers get
:data:`~src.companion.client.PROBE_TIMEOUT`, whose measured connect/read split is pinned by
:class:`TestExportedSurface` — so shrinking this cannot quietly erase the trade AC 3 made.
"""


@dataclass(frozen=True)
class _RecordedRequest:
    """Every byte a stub server received on one request (AC 6).

    Attributes:
        request_line: The raw request line, e.g. ``GET /health HTTP/1.1``.
        headers: The raw header block as the handler parsed it.
        body: The request body, empty for a ``GET``.
    """

    request_line: str
    headers: str
    body: bytes

    def as_text(self) -> str:
        """Return the whole request as one searchable string.

        ``latin-1`` decodes any byte sequence without raising, so a token smuggled into a
        non-UTF-8 body would still be found rather than crashing the assertion.

        Returns:
            Request line, headers and body concatenated.
        """
        return f"{self.request_line}\n{self.headers}\n{self.body.decode('latin-1')}"


class _StubHandler(BaseHTTPRequestHandler):
    """Answers with whatever its server was configured to return, and records what it was sent."""

    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 — the name BaseHTTPRequestHandler dispatches to
        """Record the request, then reply with the stub's configured status and bytes."""
        stub = self.server
        length = int(self.headers.get("Content-Length") or 0)
        stub.requests.append(
            _RecordedRequest(
                request_line=self.requestline,
                headers=str(self.headers),
                body=self.rfile.read(length) if length else b"",
            )
        )
        self.send_response(stub.status)
        self.send_header("Content-Type", stub.content_type)
        self.send_header("Content-Length", str(len(stub.body)))
        self.end_headers()
        self.wfile.write(stub.body)

    # Recorded as well as GET on purpose: this story must send nothing but a GET (AC 20), and a
    # regression that started posting would otherwise meet a silent 501 and record nothing at all.
    do_POST = do_GET  # noqa: N815 — mirrors BaseHTTPRequestHandler's own do_* convention

    def log_message(self, format, *args) -> None:
        """Swallow the default stderr access log — the stub is scaffolding, not code under test."""


class _StubServer(ThreadingHTTPServer):
    """A loopback HTTP server on an ephemeral port that replies with fixed, arbitrary bytes.

    Arbitrary on purpose: AC 4's rows are "a foreign server returning HTML", "JSON of the wrong
    shape" and "a non-2xx", none of which a real FastAPI app can be made to produce.
    """

    daemon_threads = True

    def __init__(self, *, status: int, body: bytes, content_type: str) -> None:
        """Bind loopback on a kernel-assigned port and arm the canned response.

        Args:
            status: The HTTP status every request receives.
            body: The exact bytes returned as the body.
            content_type: The ``Content-Type`` header value.
        """
        self.status = status
        self.body = body
        self.content_type = content_type
        self.requests: list[_RecordedRequest] = []
        super().__init__((client.LOOPBACK_HOST, 0), _StubHandler)

    @property
    def port(self) -> int:
        """Return the ephemeral port the kernel assigned."""
        return int(self.server_address[1])


class StubFleet:
    """Starts loopback HTTP stubs and guarantees every one of them is torn down.

    A helper class with a one-line fixture per module, mirroring ``test_server.py``'s
    ``_Loopback`` / ``loopback`` pair. The fixture cannot simply be imported into the other module:
    a module-level ``stub_server`` binding and a test parameter of the same name are a redefinition
    (ruff F811), and ``conftest.py`` — the usual home for a shared fixture — is out of bounds for
    this story (AC 20). One implementation, two four-line fixtures.
    """

    def __init__(self):
        self._started: list[tuple[_StubServer, threading.Thread]] = []

    def start(
        self, *, status: int = 200, body: bytes = b"", content_type: str = "application/json"
    ) -> _StubServer:
        """Start a stub on an ephemeral loopback port.

        Args:
            status: The HTTP status it answers with.
            body: The exact bytes it returns.
            content_type: Its ``Content-Type`` header.

        Returns:
            The running :class:`_StubServer`; read ``.port`` and ``.requests`` from it.
        """
        stub = _StubServer(status=status, body=body, content_type=content_type)
        # poll_interval, not the 0.5 s default: shutdown() blocks until serve_forever's loop next
        # comes round, so the default would add half a second to *every* teardown in this module.
        thread = threading.Thread(
            target=stub.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        self._started.append((stub, thread))
        return stub

    def close_all(self) -> None:
        """Shut down **and join** every stub started.

        ``shutdown()`` returns before the serving thread has necessarily exited, so the join is not
        belt-and-braces: a leaked listener on Windows surfaces as a failure in some *later* test,
        which is why teardown lives here rather than in each test (c1-3's reason, Gotcha 8).
        """
        for stub, thread in self._started:
            stub.shutdown()
            stub.server_close()
            thread.join(timeout=5)
            assert not thread.is_alive(), "a stub server thread outlived its test"


@pytest.fixture
def stub_server():
    """Yield :meth:`StubFleet.start` and tear down every stub it handed out.

    Yields:
        The factory ``start(*, status=200, body=b"", content_type="application/json")``.
    """
    fleet = StubFleet()
    yield fleet.start
    fleet.close_all()


class _Sockets:
    """Hands out raw loopback ports in the two states no HTTP server can represent.

    Deliberately a small duplicate of ``test_server.py::_Loopback`` rather than a shared import:
    lifting that helper into ``conftest.py`` would edit a file AC 20 puts out of bounds, and Task 3
    rules the duplication cheaper than the refactor.
    """

    def __init__(self):
        self._opened: list[socket.socket] = []
        self._threads: list[threading.Thread] = []

    def silent(self) -> int:
        """Return a port that accepts connections and then never answers (AC 4, row 2).

        Nothing ever calls ``accept()``: the kernel completes the TCP handshake into the backlog
        queue, so the *connect* succeeds and the *read* is what times out — which is exactly the
        distinction the split timeout of AC 3 rests on.

        Returns:
            The listening port.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Tracked before bind/listen so teardown closes it even if either call raises.
        self._opened.append(sock)
        sock.bind((client.LOOPBACK_HOST, 0))
        sock.listen(1)
        return int(sock.getsockname()[1])

    def dead(self) -> int:
        """Return a port that was free a moment ago and has nothing listening (AC 4, row 1).

        Returns:
            A port number this process no longer holds.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((client.LOOPBACK_HOST, 0))
        port = int(sock.getsockname()[1])
        sock.close()
        return port

    def drip(self) -> int:
        """Return a port whose listener answers headers, then drips body bytes forever.

        Each byte arrives well inside any per-read deadline, so ``httpx``'s ``read`` timeout never
        fires — only :data:`~src.companion.client._PROBE_TOTAL_SECONDS`'s whole-probe deadline can
        end the exchange. The advertised ``Content-Length`` is never satisfied: were the total
        deadline removed, the probe would crawl for the drip's full duration instead of hanging
        outright, so a regression fails the caller's elapsed-time assertion rather than wedging
        the suite.

        Returns:
            The listening port.
        """
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._opened.append(listener)
        listener.bind((client.LOOPBACK_HOST, 0))
        listener.listen(1)

        def _drip() -> None:
            try:
                peer, _ = listener.accept()
            except OSError:
                return  # teardown closed the listener before anyone dialled
            self._opened.append(peer)
            try:
                peer.sendall(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: 1000000\r\n\r\n"
                )
                # ~30 s of dripping at most: enough that a missing total deadline is a loud,
                # red elapsed-time failure, bounded so a regression cannot hang the suite.
                for _ in range(1500):
                    peer.sendall(b"x")
                    time.sleep(0.02)
            except OSError:
                return  # the probe gave up and closed its end, or teardown closed ours

        thread = threading.Thread(target=_drip, daemon=True)
        self._threads.append(thread)
        thread.start()
        return int(listener.getsockname()[1])

    def close_all(self) -> None:
        """Close every socket handed out and join every thread; a leaked listener bites later.

        Closing the sockets first makes each drip thread's next ``sendall`` raise, so the joins
        cannot wait out the full drip (Gotcha 8's shutdown-and-join rule, same as the stub fleet).
        """
        for sock in self._opened:
            try:
                sock.close()
            except OSError:
                pass
        for thread in self._threads:
            thread.join(timeout=5)
            assert not thread.is_alive(), "a drip thread outlived its test"


@pytest.fixture
def sockets():
    """Yield a :class:`_Sockets` helper and close everything it opened at teardown.

    Yields:
        The helper.
    """
    helper = _Sockets()
    yield helper
    helper.close_all()


def health_bytes(instance_id: str, **extra: object) -> bytes:
    """Serialise a well-formed ``/health`` body.

    Args:
        instance_id: The identity the stub should echo.
        **extra: Additional keys, for the "a newer backend added a field" case.

    Returns:
        The JSON bytes a real companion would return.
    """
    return json.dumps({"status": "ok", "instance_id": instance_id, **extra}).encode()


def plant_discovery(*, port: int, instance_id: str, token: str = "planted-token-3xAmPl3") -> Path:
    """Write a discovery file by hand, never through ``write_discovery``.

    Args:
        port: The port the record advertises.
        instance_id: The identity the record claims.
        token: The credential the record carries; distinctive so AC 6 can search for it.

    Returns:
        The path written.
    """
    path = discovery.discovery_path()
    path.write_text(
        json.dumps({"port": port, "token": token, "instance_id": instance_id}), encoding="utf-8"
    )
    return path


class TestExportedSurface:
    """AC 1 + AC 3: the leaf's public names, and the measured timeout split they carry."""

    def test_the_dialled_address_is_loopback_ipv4(self):
        """AC 1: a literal, not an import of ``server.HOST`` — a leaf may not import the app."""
        assert client.LOOPBACK_HOST == "127.0.0.1"

    def test_the_health_path_is_the_endpoint_c1_2_serves(self):
        assert client.HEALTH_PATH == "/health"

    def test_base_url_is_the_one_place_the_url_is_assembled(self):
        assert client.base_url(51234) == "http://127.0.0.1:51234"
        assert "localhost" not in client.base_url(51234)

    def test_the_probe_timeout_splits_a_short_connect_from_a_longer_read(self):
        """AC 3: the measured trade — 1 s connect (a dead port stalls ~2 s), 2 s read."""
        assert client.PROBE_TIMEOUT.connect == 1.0
        assert client.PROBE_TIMEOUT.read == 2.0
        assert client.PROBE_TIMEOUT.write == 2.0
        assert client.PROBE_TIMEOUT.pool == 2.0
        assert client.PROBE_TIMEOUT.connect < client.PROBE_TIMEOUT.read, (
            "connect must stay the tight half: calling a live-but-busy app dead starts a second "
            "instance, which is the failure this story exists to prevent"
        )

    def test_the_whole_probe_has_a_total_deadline(self):
        """Review finding: ``read`` caps the gap between chunks, so a drip-feed needs this cap."""
        assert client._PROBE_TOTAL_SECONDS == 5.0
        ordinary = client.PROBE_TIMEOUT.connect + client.PROBE_TIMEOUT.read
        assert client._PROBE_TOTAL_SECONDS > ordinary, (
            "the total deadline must never be the reason an ordinary outcome is cut short"
        )


class TestProbeHealth:
    """AC 4: anything that is not this companion answering is ``None``, and nothing raises.

    The first test is the non-vacuity anchor for the whole class (c1-6's rule): every ``is None``
    below sits beside a populated :class:`HealthResponse` returned from the same call, so the
    matrix cannot pass by refusing everything.
    """

    async def test_a_well_formed_companion_is_parsed(self, stub_server):
        stub = stub_server(body=health_bytes("inst-alpha"))

        health = await client.probe_health(stub.port)

        assert health == HealthResponse(status="ok", instance_id="inst-alpha")
        assert len(stub.requests) == 1

    async def test_the_probe_asks_for_the_health_path_with_a_get(self, stub_server):
        stub = stub_server(body=health_bytes("inst-alpha"))

        await client.probe_health(stub.port)

        assert stub.requests[0].request_line == "GET /health HTTP/1.1"

    async def test_an_unknown_health_field_is_ignored(self, stub_server):
        """Probe A5: a newer backend that adds a field must not read as *app not running*."""
        stub = stub_server(body=health_bytes("inst-alpha", uptime_seconds=12))

        health = await client.probe_health(stub.port)

        assert health is not None
        assert health.instance_id == "inst-alpha"

    async def test_nothing_listening_is_none(self, sockets):
        """AC 4, row 1: ``ConnectTimeout`` under a short deadline, ``ConnectError`` under a long."""
        assert await client.probe_health(sockets.dead(), timeout=FAST) is None

    async def test_a_listener_that_never_answers_is_none(self, sockets):
        """AC 4, row 2: the handshake completes, the read does not — ``ReadTimeout``."""
        assert await client.probe_health(sockets.silent(), timeout=FAST) is None

    async def test_a_drip_feeding_listener_is_cut_off_by_the_total_deadline(
        self, sockets, monkeypatch
    ):
        """Review finding: a byte every 20 ms beats any read deadline; only the total cap ends it.

        The deadline is shrunk through the module attribute rather than a parameter — production
        callers must get the cap without opting in, so there deliberately is no argument to pass.
        """
        monkeypatch.setattr(client, "_PROBE_TOTAL_SECONDS", 0.4)
        started = time.monotonic()

        assert await client.probe_health(sockets.drip(), timeout=FAST) is None

        assert time.monotonic() - started < 2.0, (
            "the drip kept every chunk inside the read deadline, so only the whole-probe "
            "deadline can have ended this — crawling to the drip's end means the cap is gone"
        )

    async def test_a_proxy_environment_is_ignored_for_the_loopback_dial(
        self, stub_server, monkeypatch
    ):
        """Review finding: httpx grants loopback no proxy exemption, so ``trust_env=False`` must.

        Without it, this probe dials the proxy named below (a dead loopback port), judges the
        live stub dead, and ``run()`` starts the duplicate instance this story exists to prevent.
        """
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
        stub = stub_server(body=health_bytes("inst-alpha"))

        health = await client.probe_health(stub.port)

        assert health == HealthResponse(status="ok", instance_id="inst-alpha")
        assert len(stub.requests) == 1, "the probe must reach the companion, not the proxy"

    async def test_a_foreign_server_returning_html_is_none(self, stub_server):
        """AC 4, row 3: a recycled port answering ``200`` to everything is not evidence."""
        stub = stub_server(body=b"<html>not the companion</html>", content_type="text/html")

        assert await client.probe_health(stub.port) is None

    async def test_json_of_the_wrong_shape_is_none(self, stub_server):
        """AC 4, row 4: ``{"status": "ok"}`` alone proves nothing — no identity, no trust."""
        stub = stub_server(body=b'{"status": "ok"}')

        assert await client.probe_health(stub.port) is None

    async def test_a_non_2xx_is_none(self, stub_server):
        """AC 4, row 5: a companion-shaped error body is still not a live companion."""
        stub = stub_server(status=400, body=b'{"reason": "invalid_request"}')

        assert await client.probe_health(stub.port) is None

    async def test_bytes_that_are_not_utf8_are_none(self, stub_server):
        """AC 4, row 6: decode, parse and shape all fail into the same ``ValueError`` net."""
        stub = stub_server(body=b"\xff\xfe\x00not json at all")

        assert await client.probe_health(stub.port) is None

    async def test_a_transport_failure_logs_at_debug_naming_the_url(self, sockets, caplog):
        """AC 4: DEBUG, not WARNING — for c6-1 the expected case is that nothing is there."""
        port = sockets.dead()

        with caplog.at_level(logging.DEBUG, logger=client.__name__):
            assert await client.probe_health(port, timeout=FAST) is None

        messages = [record.getMessage() for record in caplog.records]
        assert any(client.base_url(port) in message for message in messages), messages
        assert not [record for record in caplog.records if record.levelno >= logging.INFO], (
            "a probe against a dead port is the ordinary post-crash state; warning about it "
            "trains the user to ignore warnings"
        )

    async def test_a_non_2xx_is_reported_without_travelling_through_an_exception(
        self, stub_server, caplog
    ):
        """Gotcha 3: ``raise_for_status`` would make this indistinguishable from a dead port."""
        stub = stub_server(status=400, body=b'{"reason": "invalid_request"}')

        with caplog.at_level(logging.DEBUG, logger=client.__name__):
            assert await client.probe_health(stub.port) is None

        messages = [record.getMessage() for record in caplog.records]
        assert any("400" in message for message in messages), messages

    async def test_a_memory_error_is_not_app_not_running(self, stub_server, monkeypatch):
        """AC 4: the net is ``(httpx.HTTPError, ValueError)`` and deliberately not ``Exception``."""
        stub = stub_server(body=health_bytes("inst-alpha"))

        def explode(*args, **kwargs):
            raise MemoryError("out of memory mid-probe")

        monkeypatch.setattr(client.HealthResponse, "model_validate_json", explode)

        with pytest.raises(MemoryError):
            await client.probe_health(stub.port)


class TestLiveInstance:
    """AC 5 + AC 6: the whole question in one call, short-circuited, and never a token sent."""

    async def test_no_file_returns_none_without_touching_the_network(self, stub_server):
        """AC 5: a launch on a clean machine must make no network call at all."""
        stub = stub_server(body=health_bytes("inst-alpha"))
        assert not discovery.discovery_path().exists()

        assert await client.live_instance() is None
        assert stub.requests == [], "a clean machine must not be probed"

    async def test_a_matching_identity_returns_the_record_field_for_field(self, stub_server):
        stub = stub_server(body=health_bytes("inst-alpha"))
        plant_discovery(port=stub.port, instance_id="inst-alpha", token="tok-for-c6-1")

        record = await client.live_instance()

        assert record is not None
        assert record.port == stub.port
        assert record.instance_id == "inst-alpha"
        assert record.token == "tok-for-c6-1", (
            "the record, not a bool: c6-1 needs the token the moment identity is proven"
        )

    async def test_a_foreign_identity_is_treated_as_dead(self, stub_server):
        """AC 5 + Decide-once #5: something answered is not evidence; only a match is.

        The mechanism test for the whole story — delete the ``instance_id`` comparison and this is
        the assertion that goes red.
        """
        stub = stub_server(body=health_bytes("some-other-process"))
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        assert await client.live_instance() is None
        assert len(stub.requests) == 1, "the port was asked, and its answer was disbelieved"

    async def test_a_body_that_is_not_a_health_response_is_treated_as_dead(self, stub_server):
        stub = stub_server(body=b"<html>some other dev server</html>", content_type="text/html")
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        assert await client.live_instance() is None

    async def test_a_file_naming_a_dead_port_is_none(self, sockets):
        """AC 10's reclaim case, seen from the leaf: the ordinary post-crash state."""
        plant_discovery(port=sockets.dead(), instance_id="inst-alpha")

        assert await client.live_instance(timeout=FAST) is None

    async def test_an_unusable_file_is_none_without_touching_the_network(self, stub_server):
        """``read_discovery`` already absorbs this; the short-circuit must survive it too."""
        stub = stub_server(body=health_bytes("inst-alpha"))
        discovery.discovery_path().write_text("{ this is not json", encoding="utf-8")

        assert await client.live_instance() is None
        assert stub.requests == []

    async def test_no_token_ever_leaves_the_process(self, stub_server):
        """AC 6: the scenario the rule is written for — a live port that is *not* our companion."""
        token = "s3cret-token-do-not-send-me"
        stub = stub_server(body=health_bytes("some-other-process"))
        plant_discovery(port=stub.port, instance_id="inst-alpha", token=token)

        assert await client.live_instance() is None

        assert stub.requests, "the stub must have been dialled, or this proves nothing"
        for request in stub.requests:
            assert token not in request.as_text()
            assert "authorization" not in request.headers.lower()
        assert all(request.body == b"" for request in stub.requests)

    async def test_the_probe_addresses_the_app_as_loopback_on_its_own_port(self, stub_server):
        """Probe A8: the ``Host`` httpx sends is what c1-5's envelope accepts from a live app."""
        stub = stub_server(body=health_bytes("inst-alpha"))
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        await client.live_instance()

        headers = stub.requests[0].headers.lower()
        assert f"host: 127.0.0.1:{stub.port}" in headers

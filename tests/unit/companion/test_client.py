"""The leaf client, both halves: ``GET /health`` identity (c1-8) and the ``POST`` push (c6-1).

Every case here runs against a **real loopback listener**, never a mocked transport. That is c1-3's
ruling restated for a different reason: the failures this client exists to absorb — a connect that
hangs, a port recycled to an unrelated server, a body that is not our shape, a token the backend
no longer recognises — all live in the transport, and a mocked one would prove only that a mock was
called.

The stub servers deliberately come in three flavours, because httpx reports them three different
ways: an HTTP stub that answers (any status, any bytes), a bare listening socket that completes the
TCP handshake and then says nothing (``ReadTimeout``), and a port with nothing on it at all
(``ConnectTimeout`` under a short deadline). Each is one row of AC 4's matrix.

The HTTP stub answers ``GET`` and ``POST`` from **separate scripts**, which c6-1 needs and c1-8 did
not: one push makes both requests against the same stub — a ``/health`` probe and then the event
POST — so a single canned response could not express "identity is fine, the credential is not".
The POST script is a queue whose **last entry repeats forever**, so ``[403, 200]`` is the retry
case and ``[403]`` alone is the terminal one, and neither can pass by the stub simply running out.

Discovery files are planted with ``Path.write_text(json.dumps(...))`` and never through
``write_discovery`` — a fixture built by the code under test proves nothing (c1-6's rule, restated
by c1-7 AC 15).
"""

import json
import logging
import socket
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from src.companion import client, discovery
from src.companion.contracts import (
    ActiveDeckChangedEvent,
    ActiveDeckChangedPayload,
    HealthResponse,
)

FAST = httpx.Timeout(connect=0.25, read=0.25, write=0.25, pool=0.25)
"""The deadline every dead-or-silent case passes, so the suite costs milliseconds, not seconds.

Only those cases: a live stub answers in single-digit milliseconds, so the tests that talk to one
pass nothing and exercise the production default — 250 ms of thread-scheduling headroom on a
loaded CI runner is not margin worth flaking over (review finding, c1-8). Production callers get
:data:`~src.companion.client.PROBE_TIMEOUT`, whose measured connect/read split is pinned by
:class:`TestExportedSurface` — so shrinking this cannot quietly erase the trade AC 3 made.
"""

HANGUP = 0
"""A scripted ``POST`` answer meaning *accept the request and close without replying*.

Not a status the stub sends — a status no server sends. It is how the push leg is failed at
transport level over a real socket, on a port whose ``/health`` probe succeeded moments earlier.
"""

DRIP = -1
"""A scripted ``POST`` answer meaning *reply with headers, then never finish the body*."""


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

    def _record(self) -> None:
        """Append everything this request carried to the stub's log."""
        length = int(self.headers.get("Content-Length") or 0)
        record = _RecordedRequest(
            request_line=self.requestline,
            headers=str(self.headers),
            body=self.rfile.read(length) if length else b"",
        )
        with self.server._lock:
            self.server.requests.append(record)

    def _reply(self, status: int, body: bytes, content_type: str) -> None:
        """Send one complete, correctly framed response."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 — the name BaseHTTPRequestHandler dispatches to
        """Record the request, then reply with the stub's configured status and bytes."""
        stub = self.server
        self._record()
        self._reply(stub.status, stub.body, stub.content_type)

    # POST is recorded as well as GET for c1-8's reason — the probe must send nothing but a GET, and
    # a regression that started posting would otherwise meet a silent 501 and record nothing at all
    # — and it is *answered from its own script* for c6-1's: the push probes and then posts against
    # this same stub, so the two legs need to be able to answer differently.
    def do_POST(self) -> None:  # noqa: N802 — the name BaseHTTPRequestHandler dispatches to
        """Record the request, fire the stub's hook, then answer per the next scripted entry."""
        stub = self.server
        self._record()
        if stub.on_post is not None:
            stub.on_post(len(stub.posts))
        status, body = stub.next_post_response()
        if status == HANGUP:
            # Nothing is written and the socket is closed: httpx sees an empty reply and raises
            # RemoteProtocolError. The only way to fail the *push* leg at transport level while
            # the *probe* leg against this same port succeeded a moment earlier.
            self.close_connection = True
            return
        if status == DRIP:
            self._drip()
            return
        self._reply(status, body, "application/json")

    def _drip(self) -> None:
        """Answer headers, then feed body bytes forever, one every 20 ms.

        Each byte lands well inside any per-read deadline, so ``httpx``'s ``read`` timeout can
        never fire — only a whole-operation deadline can end this. Bounded at ~30 s so a regression
        that removed the cap fails an elapsed-time assertion loudly instead of wedging the suite.
        """
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "1000000")
        self.end_headers()
        try:
            for _ in range(1500):
                self.wfile.write(b"x")
                self.wfile.flush()
                time.sleep(0.02)
        except OSError:
            self.close_connection = True  # the client gave up and closed its end

    def log_message(self, format, *args) -> None:
        """Swallow the default stderr access log — the stub is scaffolding, not code under test."""


class _StubServer(ThreadingHTTPServer):
    """A loopback HTTP server on an ephemeral port that replies with fixed, arbitrary bytes.

    Arbitrary on purpose: AC 4's rows are "a foreign server returning HTML", "JSON of the wrong
    shape" and "a non-2xx", none of which a real FastAPI app can be made to produce.
    """

    daemon_threads = True

    def __init__(
        self,
        *,
        status: int,
        body: bytes,
        content_type: str,
        post_script: Sequence[tuple[int, bytes]] | None = None,
        on_post: Callable[[int], None] | None = None,
    ) -> None:
        """Bind loopback on a kernel-assigned port and arm the canned responses.

        Args:
            status: The HTTP status every ``GET`` receives.
            body: The exact bytes every ``GET`` returns.
            content_type: The ``Content-Type`` header value on a ``GET``.
            post_script: The ``POST`` answers, in order; the last entry repeats forever. Defaults
                to a single delivered client, the ordinary success.
            on_post: Called with the 1-based ``POST`` count, after that request is recorded and
                before it is answered. The retry cases use it to restart the backend's identity
                the way a real restart does — *while the client is mid-call* — because a token
                re-planted before or after the call would not be re-read by anything.
        """
        self.status = status
        self.body = body
        self.content_type = content_type
        self.on_post = on_post
        self.post_script = list(post_script or [(200, b'{"clients": 1}')])
        self.requests: list[_RecordedRequest] = []
        # ThreadingHTTPServer serves each request on its own thread. The client under test is
        # sequential, so this lock is not load-bearing today — it is here so that a future
        # concurrent case cannot make the script pop and the request log race silently.
        self._lock = threading.Lock()
        super().__init__((client.LOOPBACK_HOST, 0), _StubHandler)

    def next_post_response(self) -> tuple[int, bytes]:
        """Return the next scripted ``POST`` answer, repeating the last one once exhausted.

        Repeating rather than exhausting is deliberate: a ``403``-only script must keep refusing so
        that "the client stopped after two POSTs" is proven by the client's restraint and not by
        the stub running out of answers.

        Returns:
            The status and body bytes to reply with.
        """
        with self._lock:
            if len(self.post_script) > 1:
                return self.post_script.pop(0)
            return self.post_script[0]

    @property
    def port(self) -> int:
        """Return the ephemeral port the kernel assigned."""
        return int(self.server_address[1])

    @property
    def posts(self) -> list[_RecordedRequest]:
        """Return only the ``POST`` requests received, in order.

        Returns:
            The recorded requests whose request line begins with ``POST``.
        """
        return [request for request in self.requests if request.request_line.startswith("POST ")]


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
        self,
        *,
        status: int = 200,
        body: bytes = b"",
        content_type: str = "application/json",
        post_script: Sequence[tuple[int, bytes]] | None = None,
        on_post: Callable[[int], None] | None = None,
    ) -> _StubServer:
        """Start a stub on an ephemeral loopback port.

        Args:
            status: The HTTP status it answers a ``GET`` with.
            body: The exact bytes it returns from a ``GET``.
            content_type: Its ``Content-Type`` header on a ``GET``.
            post_script: The ``POST`` answers, in order; the last entry repeats forever.
            on_post: Called with the 1-based ``POST`` count, mid-request.

        Returns:
            The running :class:`_StubServer`; read ``.port``, ``.requests`` and ``.posts`` from it.
        """
        stub = _StubServer(
            status=status,
            body=body,
            content_type=content_type,
            post_script=post_script,
            on_post=on_post,
        )
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


def an_event(deck_id: str | None = None) -> ActiveDeckChangedEvent:
    """Build one concrete envelope to push.

    ``active_deck_changed`` is the smallest of the six kinds, and the same one c5-8's real-socket
    test pushes — the payload is not what this module tests, so the cheapest valid envelope is the
    right one. A *concrete instance* rather than a dict: :data:`~src.companion.contracts.AgentEvent`
    is an ``Annotated`` discriminated union with no ``.model_validate``, so the client accepts what
    the caller already holds and never re-validates it.

    Args:
        deck_id: The deck the signal names; ``None`` means "refetch whatever is active".

    Returns:
        A valid envelope.
    """
    return ActiveDeckChangedEvent(
        kind="active_deck_changed",
        id=uuid4().hex,
        ts=datetime.now(UTC),
        payload=ActiveDeckChangedPayload(deck_id=deck_id),
    )


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

    def test_the_events_path_is_the_endpoint_c5_5_serves(self):
        """c6-1 AC 2: the one place the push URL's path is spelled."""
        assert client.EVENTS_PATH == "/agent/events"

    def test_the_whole_push_has_a_deadline_covering_both_attempts(self):
        """c6-1 Q4: one cap over probe + post + re-probe + retry, not per leg.

        It must clear two whole probes, or the retry the story exists to make transparent would be
        cut off by the very deadline meant to bound a pathological listener.
        """
        assert client._PUSH_TOTAL_SECONDS == 10.0
        assert client._PUSH_TOTAL_SECONDS >= 2 * client._PROBE_TOTAL_SECONDS, (
            "the push deadline must fit both attempts, or FR-12's retry can never complete"
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
        """AC 4: DEBUG, not WARNING — on the push path, nothing being there is the expected case."""
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


class TestOutcomeVocabulary:
    """c6-1 AC 3: five tokens, closed, carrying no counts and no free phrases."""

    def test_the_token_set_is_exactly_five_and_closed(self):
        """AD-8: the caller-side report is a closed set, not a string a future author can widen."""
        assert set(client.PUSH_OUTCOMES) == {
            "displayed",
            "app_not_running",
            "no_clients_connected",
            "payload_rejected",
            "backend_error",
        }

    def test_no_token_carries_a_count_or_a_free_phrase(self):
        """AC 3: counts travel in a sibling field; tokens stay machine-comparable."""
        for token in client.PUSH_OUTCOMES:
            assert token.islower() and token.replace("_", "").isalpha(), token
            assert " " not in token, token

    def test_the_count_is_a_sibling_field_named_clients(self):
        """AC 3 + dw:3098: the report field is ``outcome``, never ``status``.

        ``status`` already means something else in this repo — it is the MCP tool result key whose
        values include ``deck_not_found`` — and one skill file must never carry two meanings for
        one word.
        """
        outcome = client.PushOutcome(outcome="displayed", clients=2)

        assert outcome.outcome == "displayed"
        assert outcome.clients == 2
        assert not hasattr(outcome, "status")

    def test_the_result_is_frozen(self):
        """A report a caller can edit is not a report."""
        outcome = client.PushOutcome(outcome="app_not_running")

        assert outcome.clients is None
        with pytest.raises(ValidationError):
            outcome.outcome = "displayed"

    def test_a_token_outside_the_closed_set_is_refused(self):
        """The non-vacuity anchor: the ``Literal`` is real, not decorative."""
        with pytest.raises(ValidationError):
            client.PushOutcome(outcome="shown_it_probably")


class TestPushEvent:
    """c6-1 AC 2, 3, 5, 6: one push, one token, and the request that carried it.

    Every assertion here pins **the outcome token *and* the number of requests that left the
    client**. That pairing is the c5-5 green-probe lesson made mechanical: a test that asserts only
    "it did not raise" passes under the exact failure it exists to catch, and one that asserts only
    the token cannot see a client that posted twice to get it.
    """

    async def test_a_delivered_push_is_displayed_with_its_count(self, stub_server):
        """AC 3: the ordinary success — the wire's delivered count, surfaced as a sibling field."""
        stub = stub_server(body=health_bytes("inst-alpha"), post_script=[(200, b'{"clients": 3}')])
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="displayed", clients=3)
        assert len(stub.posts) == 1

    async def test_the_push_goes_to_the_events_path_as_a_post(self, stub_server):
        """AC 2: the URL the c5-5 route serves, and nothing else."""
        stub = stub_server(body=health_bytes("inst-alpha"))
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        await client.push_event(an_event())

        assert stub.posts[0].request_line == "POST /agent/events HTTP/1.1"
        assert f"host: 127.0.0.1:{stub.port}" in stub.posts[0].headers.lower()

    async def test_the_push_carries_the_recorded_token_as_a_bearer_credential(self, stub_server):
        """AC 2: RFC 9110 spelling — what c5-5's ``AgentToken`` dependency compares against."""
        stub = stub_server(body=health_bytes("inst-alpha"))
        plant_discovery(port=stub.port, instance_id="inst-alpha", token="tok-live-alpha")

        await client.push_event(an_event())

        headers = stub.posts[0].headers
        assert "Authorization: Bearer tok-live-alpha" in headers

    async def test_the_body_is_the_serialised_envelope_and_declares_json(self, stub_server):
        """AC 2: the envelope goes out as its own JSON, not re-validated and not re-shaped."""
        stub = stub_server(body=health_bytes("inst-alpha"))
        plant_discovery(port=stub.port, instance_id="inst-alpha")
        event = an_event(deck_id="deck-77")

        await client.push_event(event)

        post = stub.posts[0]
        assert "content-type: application/json" in post.headers.lower()
        assert json.loads(post.body.decode()) == json.loads(event.model_dump_json())

    async def test_zero_clients_is_no_clients_connected_not_a_failure(self, stub_server):
        """AC 6: a wire success the token turns into "nothing saw it" — and never a retry.

        c5-5's ruling: the backend will not re-send, so a client that retried on zero would push
        duplicates at the first tab to open. The single POST below is what proves it did not.
        """
        stub = stub_server(body=health_bytes("inst-alpha"), post_script=[(200, b'{"clients": 0}')])
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="no_clients_connected", clients=0)
        assert len(stub.posts) == 1, "zero delivered is a success; retrying it duplicates the push"

    @pytest.mark.parametrize("status", [400, 413])
    async def test_both_rejection_statuses_fold_into_payload_rejected(self, stub_server, status):
        """AC 5 + c5-5 Q7: a field cap answers 400, the byte cap answers 413, one token covers both.

        Parametrised rather than two tests because the ruling is that they are *the same outcome*;
        splitting them would invite a future author to give one of them its own token.
        """
        stub = stub_server(
            body=health_bytes("inst-alpha"),
            post_script=[(status, b'{"reason": "payload_too_large"}')],
        )
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="payload_rejected", clients=None)
        assert len(stub.posts) == 1

    async def test_a_server_error_is_backend_error(self, stub_server):
        stub = stub_server(
            body=health_bytes("inst-alpha"),
            post_script=[(500, b'{"reason": "internal_error"}')],
        )
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="backend_error", clients=None)
        assert len(stub.posts) == 1

    async def test_an_unexpected_status_is_backend_error(self, stub_server):
        """The mapping is a closed switch with a default, not a list of known codes."""
        stub = stub_server(body=health_bytes("inst-alpha"), post_script=[(418, b"{}")])
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        assert await client.push_event(an_event()) == client.PushOutcome(outcome="backend_error")

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param(b"<html>not the companion</html>", id="html"),
            pytest.param(b'{"delivered": 2}', id="wrong-shape"),
            pytest.param(b'{"clients": -1}', id="negative-count"),
            pytest.param(b"\xff\xfe\x00not json", id="undecodable"),
        ],
    )
    async def test_a_malformed_success_body_is_backend_error(self, stub_server, body):
        """A ``200`` whose body is not a receipt is not a delivery — there is no count to report.

        The negative-count row matters most: ``clients: -1`` parses as JSON and would sail through
        a hand-rolled ``body["clients"] >= 1`` check as *not displayed*, silently. Reusing the
        shipped :class:`~src.companion.contracts.EventIngestReceipt` — whose ``ge=0`` refuses it —
        is what makes this row red rather than a quiet ``no_clients_connected``.
        """
        stub = stub_server(body=health_bytes("inst-alpha"), post_script=[(200, body)])
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="backend_error", clients=None)

    async def test_a_proxy_environment_is_ignored_for_the_push_too(self, stub_server, monkeypatch):
        """``trust_env=False`` on the POST leg is load-bearing twice over.

        A proxy would misroute the loopback dial exactly as it would the probe — and on this leg
        ``.netrc`` could also attach an ``Authorization`` header of its own, over a request that
        already carries a credential.
        """
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
        stub = stub_server(body=health_bytes("inst-alpha"))
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event())

        assert outcome.outcome == "displayed"
        assert len(stub.posts) == 1, "the push must reach the companion, not the proxy"


class TestPushIdentityGate:
    """c6-1 AC 2 + AC 8: identity is proven before the token moves, or nothing moves at all."""

    async def test_no_discovery_file_is_app_not_running_without_touching_the_network(
        self, stub_server
    ):
        """AC 2: no record, no probe, no post — and an honest token."""
        stub = stub_server(body=health_bytes("inst-alpha"))
        assert not discovery.discovery_path().exists()

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="app_not_running", clients=None)
        assert stub.requests == []

    async def test_a_corrupt_discovery_file_is_app_not_running_never_an_error(self, stub_server):
        """AC 8: a partially written file is the ordinary mid-publish state, not a failure."""
        stub = stub_server(body=health_bytes("inst-alpha"))
        discovery.discovery_path().write_text('{"port": 5123, "tok', encoding="utf-8")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="app_not_running", clients=None)
        assert stub.requests == []

    async def test_a_foreign_identity_is_app_not_running_and_no_token_is_sent(self, stub_server):
        """AD-4's whole point: something answered is not evidence, and a mismatch sends nothing.

        This is the mechanism test for the gate — delete the ``live_instance`` call in front of the
        POST and this is the assertion that goes red, because the stub would receive the token.
        """
        token = "s3cret-token-do-not-send-me"
        stub = stub_server(body=health_bytes("some-other-process"))
        plant_discovery(port=stub.port, instance_id="inst-alpha", token=token)

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="app_not_running", clients=None)
        assert stub.requests, "the port was dialled, or this proves nothing"
        assert stub.posts == [], "identity failed; nothing may be posted"
        for request in stub.requests:
            assert token not in request.as_text()
            assert "authorization" not in request.headers.lower()

    async def test_a_dead_port_is_app_not_running(self, sockets):
        """The ordinary post-crash state, seen from the push path."""
        plant_discovery(port=sockets.dead(), instance_id="inst-alpha")

        outcome = await client.push_event(an_event(), timeout=FAST)

        assert outcome == client.PushOutcome(outcome="app_not_running", clients=None)

    async def test_a_silent_listener_is_app_not_running(self, sockets):
        """The probe never gets an identity, so the push never begins."""
        plant_discovery(port=sockets.silent(), instance_id="inst-alpha")

        outcome = await client.push_event(an_event(), timeout=FAST)

        assert outcome == client.PushOutcome(outcome="app_not_running", clients=None)


class TestPushRetriesOnceOnAForbiddenToken:
    """c6-1 AC 4 (FR-12): a restarted backend is picked up transparently, exactly once.

    The stub restarts its identity *mid-call*, through ``on_post`` — a token re-planted before the
    call would be read on the first attempt and prove nothing, and one planted after it would never
    be read at all. What is under test is that the client goes back to the file when it is refused.
    """

    async def test_a_refused_token_is_re_read_and_the_push_succeeds(self, stub_server):
        """AC 4: the headline — 403, re-read, retry, delivered."""

        def restart(post_count: int) -> None:
            if post_count == 1:
                plant_discovery(port=stub.port, instance_id="inst-alpha", token="tok-restarted")

        stub = stub_server(
            body=health_bytes("inst-alpha"),
            post_script=[(403, b'{"reason": "forbidden"}'), (200, b'{"clients": 1}')],
            on_post=restart,
        )
        plant_discovery(port=stub.port, instance_id="inst-alpha", token="tok-stale")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="displayed", clients=1)
        assert len(stub.posts) == 2
        assert "Authorization: Bearer tok-stale" in stub.posts[0].headers
        assert "Authorization: Bearer tok-restarted" in stub.posts[1].headers, (
            "c5-8 F5: proving the file was re-read is vacuous unless the retry carries the token "
            "the re-read found — a client that reused the refused record would pass a "
            "presence-only check"
        )

    async def test_the_retry_re_proves_identity_before_sending_the_new_token(self, stub_server):
        """Q2 ruling: AD-4's verify-before-you-send has no once-per-call exemption.

        Two probes and two posts, in that interleaving: the retry is a *full* discovery → health →
        identity cycle, not a bare file re-read.
        """

        def restart(post_count: int) -> None:
            if post_count == 1:
                plant_discovery(port=stub.port, instance_id="inst-alpha", token="tok-restarted")

        stub = stub_server(
            body=health_bytes("inst-alpha"),
            post_script=[(403, b'{"reason": "forbidden"}'), (200, b'{"clients": 1}')],
            on_post=restart,
        )
        plant_discovery(port=stub.port, instance_id="inst-alpha", token="tok-stale")

        await client.push_event(an_event())

        methods = [request.request_line.split(" ", 1)[0] for request in stub.requests]
        assert methods == ["GET", "POST", "GET", "POST"]

    async def test_a_second_refusal_is_backend_error_and_the_retry_is_spent(self, stub_server):
        """AC 4: exactly two POSTs, ever. The script refuses forever; the client stops anyway."""
        stub = stub_server(
            body=health_bytes("inst-alpha"), post_script=[(403, b'{"reason": "forbidden"}')]
        )
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="backend_error", clients=None)
        assert len(stub.posts) == 2, (
            "the stub keeps refusing, so a third POST would mean the client is retrying on a "
            "budget it has already spent"
        )

    async def test_a_backend_that_vanished_before_the_retry_is_app_not_running(self, stub_server):
        """Q2 ruling: the honest token when the re-read finds nothing live is *not running*.

        ``backend_error`` would be a lie here — nothing broke; the app went away between the
        refusal and the retry, which is precisely what ``app_not_running`` says.
        """

        def wipe(post_count: int) -> None:
            if post_count == 1:
                discovery.discovery_path().unlink()

        stub = stub_server(
            body=health_bytes("inst-alpha"),
            post_script=[(403, b'{"reason": "forbidden"}')],
            on_post=wipe,
        )
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="app_not_running", clients=None)
        assert len(stub.posts) == 1, "there was nothing left to retry against"

    async def test_the_retry_is_spent_on_403_alone_not_on_a_server_error(self, stub_server):
        """FR-12 is about an invalidated credential; a 500 is not one and buys no second attempt."""
        stub = stub_server(
            body=health_bytes("inst-alpha"),
            post_script=[(500, b'{"reason": "internal_error"}'), (200, b'{"clients": 1}')],
        )
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="backend_error", clients=None)
        assert len(stub.posts) == 1, "a 500 is not a stale token; retrying it re-sends the payload"


class TestPushNeverRaisesAndNeverLeaksTheToken:
    """c6-1 AC 7: every failure is a token, and the credential is in exactly one place."""

    async def test_a_backend_that_hangs_up_on_the_push_is_backend_error(self, stub_server):
        """A transport failure on the POST leg alone — identity was already proven.

        ``backend_error``, not ``app_not_running``: the ``/health`` probe against this very port
        succeeded a moment earlier, so "no app is there" would be the wrong report. Note the single
        POST — a dropped connection is not a refused credential and buys no retry.
        """
        stub = stub_server(body=health_bytes("inst-alpha"), post_script=[(HANGUP, b"")])
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        outcome = await client.push_event(an_event(), timeout=FAST)

        assert outcome == client.PushOutcome(outcome="backend_error", clients=None)
        assert len(stub.posts) == 1

    async def test_a_drip_feeding_backend_is_cut_off_by_the_whole_push_deadline(
        self, stub_server, monkeypatch
    ):
        """AC 7: httpx's ``read`` caps gaps between chunks; only the total cap ends a drip.

        The probe succeeds; the *push* is what never finishes, which is the leg no per-request
        deadline covers. Shrunk through the module attribute rather than a parameter, for c1-8's
        reason: production callers must get the cap without opting in, so there deliberately is no
        argument to pass.
        """
        monkeypatch.setattr(client, "_PUSH_TOTAL_SECONDS", 0.8)
        stub = stub_server(body=health_bytes("inst-alpha"), post_script=[(DRIP, b"")])
        plant_discovery(port=stub.port, instance_id="inst-alpha")
        started = time.monotonic()

        outcome = await client.push_event(an_event())

        assert outcome == client.PushOutcome(outcome="backend_error", clients=None)
        assert time.monotonic() - started < 5.0, (
            "every chunk beat the read deadline, so only the whole-push cap can have ended this — "
            "crawling to the drip's end means the cap is gone"
        )

    async def test_a_memory_error_is_not_an_outcome_token(self, stub_server, monkeypatch):
        """AC 7's net is ``(TimeoutError, httpx.HTTPError, ValueError)``, never ``Exception``.

        A broken machine must not be reported to the agent as "the app is not running" — c1-8's
        ruling, restated on the leg that now carries a credential.
        """
        stub = stub_server(body=health_bytes("inst-alpha"))
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        def explode(*args, **kwargs):
            raise MemoryError("out of memory mid-push")

        monkeypatch.setattr(client.EventIngestReceipt, "model_validate_json", explode)

        with pytest.raises(MemoryError):
            await client.push_event(an_event())

    @pytest.mark.parametrize(
        "post_script",
        [
            pytest.param([(200, b'{"clients": 1}')], id="delivered"),
            pytest.param([(403, b'{"reason": "forbidden"}')], id="refused-twice"),
            pytest.param([(413, b'{"reason": "payload_too_large"}')], id="rejected"),
            pytest.param([(500, b'{"reason": "internal_error"}')], id="server-error"),
            pytest.param([(200, b"<html>nope</html>")], id="malformed-success"),
        ],
    )
    async def test_the_token_never_reaches_a_log_line_on_any_path(
        self, stub_server, caplog, post_script
    ):
        """CM-1: the credential belongs in one header and nowhere else, at any level.

        DEBUG included — the rejection logs are the tempting place to "just print what we sent",
        and every one of the five paths above passes through one of them.
        """
        token = "planted-token-3xAmPl3"
        stub = stub_server(body=health_bytes("inst-alpha"), post_script=post_script)
        plant_discovery(port=stub.port, instance_id="inst-alpha", token=token)

        with caplog.at_level(logging.DEBUG, logger=client.__name__):
            await client.push_event(an_event())

        assert stub.posts, "nothing was posted, so this proves nothing about what was logged"
        for record in caplog.records:
            assert token not in record.getMessage()
            assert token not in str(record.args)

    async def test_a_rejection_logs_at_debug_not_warning(self, stub_server, caplog):
        """c1-8's rule, carried onto the push: a warning per push is noise in the terminal."""
        stub = stub_server(
            body=health_bytes("inst-alpha"),
            post_script=[(500, b'{"reason": "internal_error"}')],
        )
        plant_discovery(port=stub.port, instance_id="inst-alpha")

        with caplog.at_level(logging.DEBUG, logger=client.__name__):
            await client.push_event(an_event())

        messages = [record.getMessage() for record in caplog.records]
        assert any("500" in message for message in messages), messages
        assert not [record for record in caplog.records if record.levelno >= logging.INFO], (
            "a backend that is restarting or absent is the ordinary state; warning about it "
            "trains the user to ignore warnings"
        )

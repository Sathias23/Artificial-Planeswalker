"""Real loopback listeners standing in for a companion: an HTTP stub and raw sockets.

Every case that drives the leaf client, the companion runner or a mutation tool's emit runs
against a **real loopback listener**, never a mocked transport: the failures the client exists to
absorb (a connect that hangs, a port recycled to an unrelated server, a body that is not our
shape, a token the backend no longer recognises) all live in the transport, and a mocked one
would prove only that a mock was called.

The listeners come in three flavours, because httpx reports them three different ways: an HTTP
stub that answers (any status, any bytes; :class:`StubServer`), a bare socket that completes the
TCP handshake and then says nothing (:meth:`Loopback.silent`), and a port with nothing on it at
all (:meth:`Loopback.free_port`). :meth:`Loopback.drip` is a fourth: headers, then a body that
never finishes.

The HTTP stub answers ``GET``, ``POST`` and ``PUT`` from **three separate scripts**: the ``GET``
script is the ``/health`` body the probe reads, and the authenticated verbs each have their own,
because they answer **different 200 bodies** and a shared queue would let an active-deck test pass
while the client parsed an event receipt. Each script is a queue whose **last entry repeats
forever**, so ``[403, 200]`` is the retry case and ``[403]`` alone is the terminal one, and neither
can pass by the stub simply running out. Every response carries ``Connection: close`` because the
client under test pools connections and the stub joins its handler threads at teardown.

Discovery files are planted with ``Path.write_text(json.dumps(...))`` (:func:`plant_discovery`)
and never through ``write_discovery``: a fixture built by the code under test proves nothing.

The ``stub_server`` fixture lives in ``tests/conftest.py`` and ``loopback`` beside it, so every
suite gets the same teardown without importing a test module.
"""

import json
import socket
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.companion import discovery
from src.companion.client import LOOPBACK_HOST

HANGUP = 0
"""A scripted answer meaning *accept the request and close without replying*.

Not a status the stub sends; a status no server sends. It is how a body-carrying leg is failed at
transport level over a real socket, on a port whose ``/health`` probe succeeded moments earlier.
"""

DRIP = -1
"""A scripted answer meaning *reply with headers, then never finish the body*."""

_DRIP_HEADERS = (
    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 1000000\r\n\r\n"
)
"""Headers advertising a body :func:`drip_bytes` never finishes."""


def drip_bytes(send: Callable[[bytes], object]) -> None:
    """Feed one body byte every 20 ms through *send*, for ~30 s at most.

    Each byte lands well inside any per-read deadline, so ``httpx``'s ``read`` timeout can never
    fire; only a whole-operation deadline can end the exchange. Bounded so a regression that
    removed that deadline fails the caller's elapsed-time assertion loudly instead of wedging the
    suite. Returns quietly once the peer (or teardown) closes the socket.

    Args:
        send: Writes one chunk to the peer (``socket.sendall``, or a handler's write-and-flush).
    """
    try:
        for _ in range(1500):
            send(b"x")
            time.sleep(0.02)
    except OSError:
        pass  # the client gave up and closed its end, or teardown closed ours


@dataclass(frozen=True)
class RecordedRequest:
    """Every byte a stub server received on one request.

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


class StubHandler(BaseHTTPRequestHandler):
    """Answers with whatever its server was configured to return, and records what it was sent."""

    protocol_version = "HTTP/1.1"
    server: "StubServer"

    def _record(self) -> None:
        """Append everything this request carried to the stub's log."""
        length = int(self.headers.get("Content-Length") or 0)
        record = RecordedRequest(
            request_line=self.requestline,
            headers=str(self.headers),
            body=self.rfile.read(length) if length else b"",
        )
        with self.server._lock:
            self.server.requests.append(record)

    def _reply(self, status: int, body: bytes, content_type: str) -> None:
        """Send one complete, correctly framed response, then close the connection.

        ``Connection: close`` because the client under test pools its connections: a kept-alive
        socket would leave this handler thread blocked on the next request line, and the stub's
        ``server_close()`` joins its handler threads at teardown.
        """
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802 — the name BaseHTTPRequestHandler dispatches to
        """Record the request, then reply with the stub's configured status and bytes."""
        stub = self.server
        self._record()
        self._reply(stub.status, stub.body, stub.content_type)

    # POST is recorded as well as GET for c1-8's reason (the probe must send nothing but a GET, and
    # a regression that started posting would otherwise meet a silent 501 and record nothing at
    # all) and it is *answered from its own script* for c6-1's: the authenticated legs need to
    # answer differently from the ``/health`` GET that ``companion_status``'s probe reads.
    def do_POST(self) -> None:  # noqa: N802 — the name BaseHTTPRequestHandler dispatches to
        """Record the request, fire the stub's hook, then answer per the next scripted entry."""
        stub = self.server
        self._answer_from_script(stub.on_post, len(stub.posts), stub.next_post_response)

    # PUT joins POST at c6-2 for the identical reason: `BaseHTTPRequestHandler` answers an
    # unimplemented method with **501**, so without it every active-deck test would see
    # `backend_error` and prove nothing at all.
    def do_PUT(self) -> None:  # noqa: N802 — the name BaseHTTPRequestHandler dispatches to
        """Record the request, fire the stub's hook, then answer per the next scripted entry."""
        stub = self.server
        self._answer_from_script(stub.on_put, len(stub.puts), stub.next_put_response)

    def _answer_from_script(self, hook, sent_before, next_response) -> None:
        """Record, fire *hook* with the 1-based count, and reply with the next scripted entry.

        Args:
            hook: The stub's mid-request callback for this method, or ``None``.
            sent_before: How many requests of this method the stub had recorded before this one,
                read *before* :meth:`_record` runs, so the hook is handed a 1-based count.
            next_response: The stub's script reader for this method.
        """
        self._record()
        if hook is not None:
            hook(sent_before + 1)
        status, body = next_response()
        if status == HANGUP:
            # Nothing is written and the socket is closed: httpx sees an empty reply and raises
            # RemoteProtocolError. The only way to fail the *authenticated* leg at transport level
            # while the *probe* leg against this same port succeeded a moment earlier.
            self.close_connection = True
            return
        if status == DRIP:
            self._drip()
            return
        self._reply(status, body, "application/json")

    def _drip(self) -> None:
        """Answer headers, then feed body bytes through :func:`drip_bytes` until it gives up."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "1000000")
        self.send_header("Connection", "close")
        self.end_headers()

        def send(chunk: bytes) -> None:
            self.wfile.write(chunk)
            self.wfile.flush()

        drip_bytes(send)
        self.close_connection = True

    def log_message(self, format, *args) -> None:
        """Swallow the default stderr access log; the stub is scaffolding, not code under test."""


class StubServer(ThreadingHTTPServer):
    """A loopback HTTP server on an ephemeral port that replies with fixed, arbitrary bytes.

    Arbitrary on purpose: the client's failure rows are "a foreign server returning HTML", "JSON of
    the wrong shape" and "a non-2xx", none of which a real FastAPI app can be made to produce.
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
        put_script: Sequence[tuple[int, bytes]] | None = None,
        on_put: Callable[[int], None] | None = None,
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
                the way a real restart does (*while the client is mid-call*), because a token
                re-planted before or after the call would not be re-read by anything.
            put_script: The ``PUT`` answers, in order; the last entry repeats forever. Defaults to
                the active-deck receipt for one delivered client. A separate script from the
                POST's, because the two verbs answer different 200 bodies.
            on_put: Called with the 1-based ``PUT`` count, on the same terms as ``on_post``.
        """
        self.status = status
        self.body = body
        self.content_type = content_type
        self.on_post = on_post
        self.on_put = on_put
        self.post_script = list(post_script or [(200, b'{"clients": 1}')])
        self.put_script = list(put_script or [(200, b'{"deck_id": "deck-1", "clients": 1}')])
        self.requests: list[RecordedRequest] = []
        # ThreadingHTTPServer serves each request on its own thread. The client under test is
        # sequential, so this lock is not load-bearing today; it is here so that a future
        # concurrent case cannot make the script pop and the request log race silently.
        self._lock = threading.Lock()
        super().__init__((LOOPBACK_HOST, 0), StubHandler)

    def next_post_response(self) -> tuple[int, bytes]:
        """Return the next scripted ``POST`` answer, repeating the last one once exhausted.

        Repeating rather than exhausting is deliberate: a ``403``-only script must keep refusing so
        that "the client stopped after two POSTs" is proven by the client's restraint and not by
        the stub running out of answers.
        """
        with self._lock:
            if len(self.post_script) > 1:
                return self.post_script.pop(0)
            return self.post_script[0]

    def next_put_response(self) -> tuple[int, bytes]:
        """Return the next scripted ``PUT`` answer, repeating the last one once exhausted."""
        with self._lock:
            if len(self.put_script) > 1:
                return self.put_script.pop(0)
            return self.put_script[0]

    @property
    def port(self) -> int:
        """Return the ephemeral port the kernel assigned."""
        return int(self.server_address[1])

    @property
    def posts(self) -> list[RecordedRequest]:
        """Return only the ``POST`` requests received, in order."""
        return [request for request in self.requests if request.request_line.startswith("POST ")]

    @property
    def puts(self) -> list[RecordedRequest]:
        """Return only the ``PUT`` requests received, in order."""
        return [request for request in self.requests if request.request_line.startswith("PUT ")]


class StubFleet:
    """Starts loopback HTTP stubs and guarantees every one of them is torn down.

    The ``stub_server`` fixture in ``tests/conftest.py`` yields :meth:`start` and calls
    :meth:`close_all` at teardown.
    """

    def __init__(self) -> None:
        self._started: list[tuple[StubServer, threading.Thread]] = []

    def start(
        self,
        *,
        status: int = 200,
        body: bytes = b"",
        content_type: str = "application/json",
        post_script: Sequence[tuple[int, bytes]] | None = None,
        on_post: Callable[[int], None] | None = None,
        put_script: Sequence[tuple[int, bytes]] | None = None,
        on_put: Callable[[int], None] | None = None,
    ) -> StubServer:
        """Start a stub on an ephemeral loopback port.

        Args:
            status: The HTTP status it answers a ``GET`` with.
            body: The exact bytes it returns from a ``GET``.
            content_type: Its ``Content-Type`` header on a ``GET``.
            post_script: The ``POST`` answers, in order; the last entry repeats forever.
            on_post: Called with the 1-based ``POST`` count, mid-request.
            put_script: The ``PUT`` answers, in order; the last entry repeats forever.
            on_put: Called with the 1-based ``PUT`` count, mid-request.

        Returns:
            The running :class:`StubServer`; read ``.port``, ``.requests``, ``.posts`` and
            ``.puts`` from it.
        """
        stub = StubServer(
            status=status,
            body=body,
            content_type=content_type,
            post_script=post_script,
            on_post=on_post,
            put_script=put_script,
            on_put=on_put,
        )
        # poll_interval, not the 0.5 s default: shutdown() blocks until serve_forever's loop next
        # comes round, so the default would add half a second to *every* teardown.
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
        which is why teardown lives here rather than in each test.
        """
        for stub, thread in self._started:
            stub.shutdown()
            stub.server_close()
            thread.join(timeout=5)
            assert not thread.is_alive(), "a stub server thread outlived its test"


class Loopback:
    """Hands out raw loopback ports and sockets, and closes every one of them at teardown.

    The states no HTTP server can represent: a port held so nothing else can take it
    (:meth:`occupy`), a port with nothing on it (:meth:`free_port`), a listener that never answers
    (:meth:`silent`) and one that never finishes answering (:meth:`drip`).
    """

    def __init__(self) -> None:
        self._opened: list[socket.socket] = []
        self._threads: list[threading.Thread] = []

    def occupy(self, port: int = 0) -> socket.socket:
        """Bind *and listen on* a loopback port so nothing else can take it.

        ``listen()`` matters: on Linux a merely-bound socket can be re-bound by a second socket
        when both set ``SO_REUSEADDR``, which the companion runner does on POSIX. A listening
        socket is refused on every platform, so the "occupied" premise holds identically on
        Windows and on CI's Linux runners.

        Args:
            port: The port to take, or ``0`` to let the kernel choose.

        Returns:
            The listening socket.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Tracked before bind/listen: if either raises, teardown still closes the socket.
        self._opened.append(sock)
        sock.bind((LOOPBACK_HOST, port))
        sock.listen(1)
        return sock

    def track(self, sock: socket.socket) -> socket.socket:
        """Adopt an externally created socket into this helper's teardown, and return it."""
        self._opened.append(sock)
        return sock

    def free_port(self) -> int:
        """Return a loopback port that was free a moment ago and has nothing listening.

        Reserving an ephemeral port and immediately releasing it names a port that is very likely
        free without ever touching the companion's default port.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((LOOPBACK_HOST, 0))
        port = int(sock.getsockname()[1])
        sock.close()
        return port

    def silent(self) -> int:
        """Return a port that accepts connections and then never answers.

        Nothing ever calls ``accept()``: the kernel completes the TCP handshake into the backlog
        queue, so the *connect* succeeds and the *read* is what times out, which is exactly the
        distinction the client's split timeout rests on.
        """
        return int(self.occupy().getsockname()[1])

    def drip(self) -> int:
        """Return a port whose listener answers headers, then drips body bytes forever.

        Only a whole-exchange deadline can end it (see :func:`drip_bytes`). The advertised
        ``Content-Length`` is never satisfied, so a regression that removed that deadline crawls
        for the drip's full duration rather than hanging outright.
        """
        listener = self.occupy()

        def serve() -> None:
            try:
                peer, _ = listener.accept()
            except OSError:
                return  # teardown closed the listener before anyone dialled
            self._opened.append(peer)
            try:
                peer.sendall(_DRIP_HEADERS)
            except OSError:
                return
            drip_bytes(peer.sendall)

        thread = threading.Thread(target=serve, daemon=True)
        self._threads.append(thread)
        thread.start()
        return int(listener.getsockname()[1])

    def close_all(self) -> None:
        """Close every socket handed out, then join every drip thread.

        Closing the sockets first makes each drip thread's next ``sendall`` raise, so the joins
        cannot wait out the full drip. One failing close must not strand the rest.
        """
        for sock in self._opened:
            try:
                sock.close()
            except OSError:
                pass
        for thread in self._threads:
            thread.join(timeout=5)
            assert not thread.is_alive(), "a drip thread outlived its test"


def health_bytes(instance_id: str, **extra: object) -> bytes:
    """Serialise a well-formed ``/health`` body echoing *instance_id* plus any *extra* keys."""
    return json.dumps({"status": "ok", "instance_id": instance_id, **extra}).encode()


def plant_discovery(*, port: int, instance_id: str, token: str = "planted-token-3xAmPl3") -> Path:
    """Write a discovery file by hand, never through ``write_discovery``.

    Args:
        port: The port the record advertises.
        instance_id: The identity the record claims.
        token: The credential the record carries; distinctive so a test can search for it.

    Returns:
        The path written.
    """
    path = discovery.discovery_path()
    path.write_text(
        json.dumps({"port": port, "token": token, "instance_id": instance_id}), encoding="utf-8"
    )
    return path

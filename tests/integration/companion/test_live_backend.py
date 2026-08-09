"""The one test that boots a real backend on a real port (story c5-8, AD-10).

================= WHY EXACTLY ONE, AND WHY IT IS THIS ONE =================================

AD-10 fixes the shape: *"one integration test that boots the real backend on an ephemeral port
and drives the real channel"*, and ARCHITECTURE-SPINE.md:461 fixes the path this file occupies.
Seven stories (c5-1 … c5-7) built the whole channel in-process — ``tests/unit/companion/`` drives
the ASGI app through ``httpx.ASGITransport`` with no socket at all, which is why 2,770 tests run in
under two minutes. That coverage is real, and it is blind to exactly one class of defect: the
seams that only exist once a kernel, a port, a process boundary and a real WebSocket handshake are
involved. This file is the whole of the repo's answer to that class, and it is deliberately small.

**It is the only ``integration``-marked companion test and the only test anywhere that boots a real
backend process.** ``uv run pytest -m "not integration"`` deselects it and the suite still passes
at its full count — which is the proof that the unit suite covers the channel *logic* on its own,
rather than this test quietly becoming load-bearing for things it should not be.

**ONE test function, walking boot → channel → restart → retry in sequence** (Q3, Brad 2026-08-09).
A module of five functions each booting processes reads as five real-backend tests and makes AC 1's
"exactly one" a matter of interpretation; and the restart case needs the first backend's corpse
anyway, so splitting it would mean booting a third process to recreate state the walk already has.
The cost is a long function, paid down with phase comments rather than with splitting.

================= WHAT THIS TEST DOES NOT DO ==============================================

**It writes no production code and fixes nothing.** The broadcast overlap race and the slow-client
stall were both ruled acceptable residuals at c5-4; if a real socket ever surfaces them here, the
honest move is to record it, not to repair it from a test.

**It does not use** :func:`~src.companion.client.push_event`. The FR-12 retry in phase 9 stays
hand-rolled *inside this function* on purpose, and c6-1 shipping the real helper did not change
that (Q3, Brad 2026-08-09): what this file pins is the **wire contract**, and it can only pin it
independently of the client if it does not go through the client. Wired up, a client bug and a
backend bug would fail the same assertion and this test would stop being the second opinion it
exists to be. The shipped helper — ``client.push_event``, with the retry-once and the closed
outcome vocabulary — is unit-tested against real loopback listeners in
``tests/unit/companion/test_client.py``; the sequence below is the shape it had to implement,
proven here against a really restarted process.

**CI runs it on Windows.** ``.github/workflows/ci.yml``'s ``companion-integration`` job runs this
directory on ``windows-latest`` on every push and pull request. The ``quality`` jobs are ubuntu and
run ``-m "not integration"``, so they still deselect this test; that job is the only one that
executes it. Windows because the two facts below are Windows facts, and because it is the
maintainer's development platform — **not** because of "AD-2", a label this file used to attach to
the claim. AD-2 is *"the MCP server is the only writer"*; no AD names a platform of record.

Both CI and local runs are scoped **by path** rather than by marker, because ``-m integration``
also selects the live-network Scryfall contract tests and several tests that instantiate the real
fastembed model. It does **not** select the twice-sighted ``test_list_decks_with_strategy_field``
flake, which this file previously claimed: that test carries no marker at all and already runs in
the ``quality`` jobs (measured 2026-08-09).

================= THE TWO WINDOWS FACTS THIS FILE IS SHAPED AROUND ========================

1. **The child must be the server.** ``scripts/cdp_harness.py`` launches via ``uv run``, which makes
   the real server a *grandchild*: ``terminate()`` kills the launcher and leaves a process holding
   the port and ``cards.db``, which is why that harness needs ``taskkill /F /T``. Booting
   ``sys.executable -m src.mcp_server`` instead means the child *is* the server, so
   ``terminate()`` + ``wait()`` is sufficient and identical on every platform (Q1).
2. **A TCP connect to a dead loopback port takes ~2 s to refuse** (measured at c1-8) while a live
   ``/health`` answers in ~15 ms. That is why the boot deadline is generous rather than paranoid,
   and it is also the second backend's dominant startup cost: it probes the stale record before
   reclaiming it.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import websockets
from websockets.exceptions import InvalidStatus

from src.companion import client, discovery

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[3]

_BOOT_DEADLINE = 30.0
"""How long a backend gets to publish its discovery record.

Generous on purpose. The second boot pays a ~2 s dead-port probe against the stale record before
it reclaims it, an antivirus scan of a fresh ``python.exe`` costs seconds more, and a cold import
of FastAPI + uvicorn + SQLAlchemy is not fast. Never tighten a timeout to make a test quicker —
the failure that produces is a flake blamed on the code under test.
"""

_POLL_INTERVAL = 0.25
"""Between discovery reads. Small enough that the wait is not itself the measurement."""

_STOP_DEADLINE = 15.0
"""How long a terminated child gets to actually die before it is killed outright."""

_HTTP_TIMEOUT = 10.0
_RECV_DEADLINE = 10.0
"""Every await in this file carries a bound: a hung socket must fail the test, not the run."""


class _Backend:
    """One real companion process, and everything needed to shut it down again.

    Deliberately a small class rather than a fixture: phase 6 stops the first backend and starts a
    second one *inside* the test body, so the lifetime is the test's to manage. The fixture below
    owns only the guarantee that both are dead at the end.
    """

    def __init__(self, data_dir: Path, name: str) -> None:
        self.data_dir = data_dir
        self.name = name
        self.log_path = data_dir / f"{name}.log"
        self.proc: subprocess.Popen[bytes] | None = None
        self._log: object | None = None

    def start(self) -> None:
        """Launch the backend as a direct child, with its output going to a file.

        ``--port 0`` is a legal direct request for an ephemeral port: ``server.py`` binds it once
        and treats the assigned port as success rather than as a fallback. The port is then read
        from ``companion.json`` — never parsed out of the launch line, which carries an em dash and
        would make this test hostage to the child's console encoding.

        **The output goes to a FILE, never a pipe.** An undrained pipe fills its buffer and blocks
        the child mid-write, which presents as "the backend never started".
        """
        env = dict(os.environ)
        env["PLANESWALKER_DATA_DIR"] = str(self.data_dir)
        log = self.log_path.open("ab")
        self._log = log
        self.proc = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "src.mcp_server", "companion", "--port", "0"],
            cwd=str(_REPO_ROOT),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    def stop(self) -> None:
        """Terminate and **wait**, then close the log — idempotent, and total.

        Every step runs even when a previous one raised, which is c5-6's review lesson applied to
        teardown (its bug was a ``fail()`` that skipped ``schedule()`` when a callback threw). The
        handles are detached *first*, so a raising ``wait()`` cannot leave this object claiming to
        still own a process it has already terminated.

        The ``wait()`` is not optional and not cosmetic: on Windows an un-waited child keeps the
        port and ``cards.db`` open, which makes ``tmp_path`` cleanup fail for the *next* test.
        """
        proc, self.proc = self.proc, None
        log, self._log = self._log, None
        try:
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=_STOP_DEADLINE)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=_STOP_DEADLINE)
        finally:
            if log is not None:
                log.close()  # type: ignore[attr-defined]

    def log_tail(self, limit: int = 3000) -> str:
        """The child's own output, for an assertion message that says something useful."""
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")[-limit:]
        except OSError:
            return "<no log file>"


async def _await_record(
    backend: _Backend, *, replacing: str | None = None
) -> discovery.DiscoveryRecord:
    """Poll until *backend* has published a usable discovery record, or fail loudly.

    **Readiness IS the discovery file** (Q2) — not a fixed sleep and not the launch line.
    ``read_discovery()`` never raises, so ``None`` means only "not yet"; that promise is what lets
    this be a plain poll with no exception handling of its own.

    ``replacing`` is what makes the restart case honest. A hard kill deliberately leaves the first
    backend's ``companion.json`` on disk, so after the second boot the *file* is present from the
    first instant — waiting on presence alone would return the corpse's record. Waiting for a
    different ``instance_id`` waits for the reclaim to actually happen.

    A child that has already exited fails immediately with its own log rather than burning the
    whole deadline on a process that will never answer.

    Args:
        backend: The process to wait for.
        replacing: An ``instance_id`` that must be superseded before the record counts.

    Returns:
        The published record.
    """
    deadline = time.monotonic() + _BOOT_DEADLINE
    while time.monotonic() < deadline:
        record = discovery.read_discovery()
        if record is not None and record.instance_id != replacing:
            return record
        proc = backend.proc
        if proc is not None and proc.poll() is not None:
            raise AssertionError(
                f"{backend.name} exited with code {proc.returncode} before publishing a "
                f"discovery record.\n--- child output ---\n{backend.log_tail()}"
            )
        await asyncio.sleep(_POLL_INTERVAL)
    raise AssertionError(
        f"{backend.name} published no discovery record within {_BOOT_DEADLINE}s.\n"
        f"--- child output ---\n{backend.log_tail()}"
    )


@pytest.fixture
def live_data_dir(tmp_path, monkeypatch):
    """An isolated data directory, pointed at from **both** processes.

    The child gets it through its environment (see :meth:`_Backend.start`); this process gets it
    through ``monkeypatch`` so that ``src.paths.data_dir()`` — and therefore
    ``discovery.read_discovery()`` and ``client.live_instance()`` — resolve the same directory the
    backend is writing to. Both halves are required: the test reads the file the child writes.

    **This isolation is owned here rather than inherited.** ``tests/unit/companion/conftest.py``
    has an autouse fixture doing the same job, but it is scoped to that package and does not reach
    this one; ``tests/integration/conftest.py`` holds database fixtures and nothing else needs a
    data dir. Widening either would give a shared conftest a companion-shaped dependency for one
    caller.

    The isolation also means the singleton lock is per-test: this backend can never contend with a
    companion the developer actually has running, and vice versa.
    """
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def backends(live_data_dir):
    """Hand out backends, and guarantee every one of them is dead afterwards.

    The teardown loop is why this is a fixture at all: the test stops the first backend itself
    mid-walk, and an assertion failing anywhere between the two boots must still not leak a process
    that holds the port and blocks ``tmp_path`` cleanup. Each ``stop()`` is idempotent, and each is
    attempted even if an earlier one raised.
    """
    made: list[_Backend] = []

    def _make(name: str) -> _Backend:
        backend = _Backend(live_data_dir, name)
        made.append(backend)
        backend.start()
        return backend

    try:
        yield _make
    finally:
        errors: list[BaseException] = []
        for backend in made:
            try:
                backend.stop()
            except BaseException as exc:  # noqa: BLE001 - every backend gets its turn
                errors.append(exc)
        if errors:
            # Every failure is reported, not just the first: a second backend's teardown
            # failure is exactly the kind of signal "explicit and total" teardown must not hide.
            raise ExceptionGroup("backend teardown failed", errors)


async def test_the_real_channel_end_to_end(backends, live_data_dir):
    """Boot a real backend, drive the real channel, restart it, and retry through FR-12.

    Nine phases, in order, against two real processes. Each phase's own comment says which
    acceptance criterion it discharges and — where it matters — which failure it is shaped to
    catch rather than merely to observe.
    """
    # ==== PHASE 1: a real process, on a real ephemeral port (AC 2, AC 3) =====================
    # The record is the readiness signal and two of the assertions at once: if it parses and
    # carries a nonzero port, the child bound a socket and published where it is.
    backend_one = backends("backend-one")
    record_one = await _await_record(backend_one)

    assert record_one.port > 0
    assert record_one.token
    assert record_one.instance_id
    # The file really is in the isolated directory — otherwise every read below could be talking
    # to a companion the developer has running, and the test would pass for the wrong reason.
    assert (live_data_dir / discovery.COMPANION_FILENAME).is_file()

    base_url = f"http://127.0.0.1:{record_one.port}"

    # ==== PHASE 2: identity, through the shipped leaf (AC 4) ================================
    # `live_instance()` reads the discovery file, probes `/health` and compares the echoed
    # instance_id — the one-implementation-both-callers path AD-3 requires, and the same call
    # `client.push_event` makes before every send, retry included.
    # A hand-rolled probe here would be a second implementation of the question this app already
    # answers, and it would be the copy that drifted.
    live = await client.live_instance()
    assert live is not None, f"live_instance() found nothing.\n{backend_one.log_tail()}"
    assert live.instance_id == record_one.instance_id
    assert live.port == record_one.port

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, trust_env=False) as http:
        # ==== PHASE 3: a real ticket (AC 5) =================================================
        # Literal `127.0.0.1`, never `localhost`: on Windows `localhost` resolves `::1` first and
        # the bind is IPv4-only, so the friendly spelling is a connection refusal.
        minted = await http.get(f"{base_url}/api/session")
        assert minted.status_code == 200
        ticket_one = minted.json()["ticket"]
        assert isinstance(ticket_one, str) and ticket_one
        # The one header this credential's whole design depends on: a single-use ticket in a
        # back/forward cache or a proxy is a credential someone else can replay.
        assert minted.headers["cache-control"] == "no-store"

        # ==== PHASE 4: a real WebSocket upgrade, with an explicit Origin (AC 6) =============
        # THE EXPLICIT `origin=` IS THE POINT, and it pays dw:5459. `websockets.connect` sends no
        # Origin at all by default — it is not a browsing context — and `security.py:204` rejects a
        # missing Origin fail-closed, naming *this test* as the client that would set it. Without
        # this argument the handshake below is refused, which is the promise being kept.
        origin = f"http://127.0.0.1:{record_one.port}"
        socket = await websockets.connect(
            f"ws://127.0.0.1:{record_one.port}/ws?ticket={ticket_one}",
            origin=origin,
            open_timeout=_HTTP_TIMEOUT,
            close_timeout=_HTTP_TIMEOUT,
        )
        try:
            # ==== PHASE 5: the ticket was CONSUMED, proved as a pair (AC 7) =================
            # The rejection half. Every refused handshake is a byte-identical pre-accept 1008 that
            # uvicorn renders as HTTP 403 with no body, so the assertion is on the status and never
            # on a reason string — the indistinguishability is the security property.
            with pytest.raises(InvalidStatus) as refused:
                await websockets.connect(
                    f"ws://127.0.0.1:{record_one.port}/ws?ticket={ticket_one}",
                    origin=origin,
                    open_timeout=_HTTP_TIMEOUT,
                )
            assert refused.value.response.status_code == 403

            # ==== PHASE 6: a real token-authenticated push, arriving over the open socket ===
            # (AC 8). `clients` is the DELIVERED count, and it is exactly 1 here because exactly
            # one socket is open — which is why the fresh-ticket half of AC 7 is deliberately
            # deferred to phase 7 rather than run before this POST: a second socket opened and
            # closed above would race its own disconnect against this count.
            event_id = uuid.uuid4().hex
            envelope = {
                "kind": "active_deck_changed",
                "id": event_id,
                # AWARE, always: the envelope's `ts` is an `AwareDatetime` and a naive value is
                # refused with a 422 that would read here as "the push broke".
                "ts": datetime.now(UTC).isoformat(),
                "payload": {"deck_id": None},
            }
            pushed = await http.post(
                f"{base_url}/agent/events",
                json=envelope,
                headers={"Authorization": f"Bearer {record_one.token}"},
            )
            assert pushed.status_code == 200, pushed.text
            assert pushed.json() == {"clients": 1}

            received = await asyncio.wait_for(socket.recv(), timeout=_RECV_DEADLINE)
            delivered = json.loads(received)
            assert delivered["kind"] == "active_deck_changed"
            assert delivered["id"] == event_id

            # ==== PHASE 7: the acceptance half of AC 7, now that the count is spent ==========
            # Non-vacuity for phase 5: a FRESH ticket from the same store on the same socket path
            # is accepted, so the refusal above was about the ticket being spent and not about the
            # upgrade being broken in some way that refuses everything.
            second_mint = await http.get(f"{base_url}/api/session")
            assert second_mint.status_code == 200
            ticket_two = second_mint.json()["ticket"]
            assert ticket_two != ticket_one
            fresh_socket = await websockets.connect(
                f"ws://127.0.0.1:{record_one.port}/ws?ticket={ticket_two}",
                origin=origin,
                open_timeout=_HTTP_TIMEOUT,
                close_timeout=_HTTP_TIMEOUT,
            )
            await asyncio.wait_for(fresh_socket.close(), timeout=_HTTP_TIMEOUT)
        finally:
            # By hand, and before the server is stopped (AC 10). A socket closed by the process
            # dying underneath it is a different code path from an orderly close, and the orderly
            # one is what a browser tab does.
            await asyncio.wait_for(socket.close(), timeout=_HTTP_TIMEOUT)

        # ==== PHASE 8: the backend restarts, and takes its token with it (AC 9) =============
        # `terminate()` is a hard kill on Windows, which is exactly what this phase wants: it
        # leaves `companion.json` behind, so the second boot has to walk c1-8's reclaim path
        # (probe the recorded port, find it dead, take the file over). Deleting the stale file
        # here would make the restart case dishonest — it would test a clean boot.
        backend_one.stop()

        backend_two = backends("backend-two")
        record_two = await _await_record(backend_two, replacing=record_one.instance_id)

        assert record_two.instance_id != record_one.instance_id
        assert record_two.token != record_one.token, (
            "the restarted backend reused the previous process's token; FR-12's whole premise is "
            "that a restart invalidates it"
        )
        # NOT asserted: record_two.port != record_one.port. The OS can legally reissue the same
        # ephemeral port to backend_two once backend_one's listening socket is closed (Greptile
        # P2, caught on this story's PR) — that is a healthy restart, not a defect, and asserting
        # otherwise would make this test flake on a passing run.

        # ==== PHASE 9: FR-12 — stale token, 403, re-read, retry once, 200 (AC 9) ===========
        # Hand-rolled here on purpose, and deliberately NOT switched to `client.push_event` when
        # that shipped (Q3, Brad 2026-08-09): routing this through the client would make one bug
        # able to hide another. What is proven is the SHAPE the helper implements, against a real
        # restarted process, by a path that shares no code with it.
        new_base_url = f"http://127.0.0.1:{record_two.port}"
        stale_envelope = {
            "kind": "active_deck_changed",
            "id": uuid.uuid4().hex,
            "ts": datetime.now(UTC).isoformat(),
            "payload": {"deck_id": None},
        }
        stale = await http.post(
            f"{new_base_url}/agent/events",
            json=stale_envelope,
            headers={"Authorization": f"Bearer {record_one.token}"},
        )
        assert stale.status_code == 403
        assert stale.json() == {"reason": "forbidden"}

        # The retry: re-read the file rather than reusing the record already in hand, because
        # re-reading is what a caller that has just been refused actually does.
        reread = discovery.read_discovery()
        assert reread is not None
        assert reread.token == record_two.token

        retried = await http.post(
            f"{new_base_url}/agent/events",
            json=stale_envelope,
            headers={"Authorization": f"Bearer {reread.token}"},
        )
        assert retried.status_code == 200, retried.text
        # Zero listeners is a SUCCESS (c5-5's ruling): no socket has ever connected to
        # backend_two's `/ws` endpoint, the event was relayed exactly as instructed, and a caller
        # that retried on zero would push duplicates at the first tab to open.
        assert retried.json() == {"clients": 0}

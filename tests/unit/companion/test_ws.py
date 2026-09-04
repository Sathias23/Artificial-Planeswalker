"""The authenticated WebSocket upgrade: ``Origin``, the ticket, and the two things it must not do.

Every handshake here is driven through the **real** application — ``build_app()``, the shipped
``Host`` middleware, the shipped router — via ``conftest.drive_handshake``, because half of this
story's security is code that was already shipped and the whole point is proving the new route
inherits it rather than re-implementing it (AD-5). ``httpx.ASGITransport`` cannot drive a
``websocket`` scope at all, which is why the helper exists; see its docstring for why it is not
Starlette's ``TestClient``.

Two conventions inherited and kept: **every rejection test is paired with an acceptance from the
same call site**, so a guard cannot pass by refusing everything (c1-4's Greptile catch), and
**no test sleeps** — the 30-second TTL is proven with ``FakeClock`` at zero wall clock, because a
test that spends real time to prove an expiry is a defect (c3-6).

There is no real socket anywhere in this file, and there must not be: AD-10 homes the one
end-to-end proof on **c5-8**, which shipped it at
``tests/integration/companion/test_live_backend.py`` (2026-08-09). That directory did not exist
when this line was first written; it does now, it holds exactly one ``integration``-marked test,
and the reason this file still drives the in-process ASGI callable is unchanged — 2,770 tests in
under two minutes is a property of there being no sockets in them.
"""

import inspect
import logging
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import TypeAdapter

from src.companion.app import spa, state, ws
from src.companion.app.main import bound_port, build_app
from src.companion.app.state import (
    ConnectionRegistry,
    TicketStore,
    connection_registry,
    ticket_store,
)
from src.companion.contracts import (
    ActiveDeckChangedEvent,
    ActiveDeckChangedPayload,
    AgentEvent,
)
from tests.unit.companion.conftest import (
    FakeClock,
    FakeConnection,
    drive_handshake,
    open_socket,
)

_SESSION_PATH = "/api/session"
_WS_LOGGER = "src.companion.app.ws"

_POLICY_VIOLATION = 1008
"""What every refusal closes with. Spelled out here rather than imported from ``ws`` so the test
asserts the shipped number instead of agreeing with whatever the module currently says."""

_INTERNAL_ERROR = 1011
"""The fail-closed code, likewise spelled out rather than imported (c5-3, Q6)."""


async def _mint(client):
    """Mint one ticket through the shipped endpoint, and return it.

    Deliberately over the wire rather than by calling ``store.mint()``: the sequence under test is
    "browser reads a ticket from same-origin ``GET /api/session``, then upgrades", and a test that
    reached into the store would skip the half c5-2 shipped.
    """
    response = await client.get(_SESSION_PATH)
    assert response.status_code == 200, "the mint must work, or every test below is vacuous"
    return response.json()["ticket"]


def _close_codes(sent):
    """Return the close codes in *sent*, so an assertion reads as a list of codes."""
    return [message["code"] for message in sent if message["type"] == "websocket.close"]


def _was_accepted(sent):
    """Report whether the application accepted the handshake."""
    return any(message["type"] == "websocket.accept" for message in sent)


class TestTheHappyPath:
    """AC 1: a good Origin plus a live ticket establishes the socket and spends the ticket."""

    async def test_a_valid_ticket_from_our_own_origin_is_accepted(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)

            sent = await drive_handshake(app, ticket=ticket)

        assert _was_accepted(sent), sent
        assert _close_codes(sent) == [], "an accepted socket is not also closed by the handler"

    async def test_the_accepted_handshake_consumed_the_ticket(self, lifespan_client):
        """AD-5's single-use half, observed on the store rather than inferred from a second try.

        The wire assertion (replay is refused) is the next test; this one reads
        ``resident_count`` because that is the only thing that can distinguish *destroying* the
        ticket from merely *refusing to honour it twice* — the same reason ``TicketStore`` exposes
        the property at all.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            store = ticket_store(app)
            assert store.resident_count == 1, "non-vacuity: the mint really put one in the map"

            await drive_handshake(app, ticket=ticket)

            assert store.resident_count == 0

    async def test_replaying_a_consumed_ticket_is_refused(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)

            first = await drive_handshake(app, ticket=ticket)
            replay = await drive_handshake(app, ticket=ticket)

        assert _was_accepted(first), "non-vacuity: the first use of this ticket really worked"
        assert not _was_accepted(replay)
        assert _close_codes(replay) == [_POLICY_VIOLATION]

    async def test_two_sequential_sockets_each_need_their_own_ticket(self, lifespan_client):
        """The shape c5-6's reconnect loop actually performs: mint, upgrade, mint, upgrade.

        **Fulfilled 2026-08-08.** `ui/src/state/socket.ts` ships that loop and
        `socket.test.ts::mints once per attempt and never presents the same ticket twice` is this
        test's browser-side twin, asserting the same sequence against a fake socket.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            first = await drive_handshake(app, ticket=await _mint(client))
            second = await drive_handshake(app, ticket=await _mint(client))

        assert _was_accepted(first)
        assert _was_accepted(second)


class TestEveryRejectionLooksTheSame:
    """AC 2: four ticket failures, one wire answer, pre-accept.

    The store already refuses to say whether a ticket was unknown, expired or spent — *"a caller
    that could tell them apart could probe the store"*. This asserts the upgrade does not hand back
    the distinction the store withheld, by comparing the **whole message list**, not just the code:
    a difference in ``reason``, in message count, or an accept-then-close would all be visible.
    """

    async def _refusals(self, lifespan_client):
        """Drive all five refusals plus one acceptance against **one** app, and return both.

        The expired ticket needs a virtual clock, so the store is swapped for one built on
        ``FakeClock`` and then **swapped back** — which is why the real store is held in a local
        rather than re-read afterwards: ``ticket_store(app)`` would return whatever is currently
        installed, so "restoring" through the accessor restores nothing and would silently cost
        this class its only acceptance. Swapping an instance is not moving the store (AC 12): the
        accessor, the state key and the class are all untouched.
        """
        app = build_app()
        clock = FakeClock()
        async with lifespan_client(app) as client:
            real_store = ticket_store(app)
            live = await _mint(client)
            spent = await _mint(client)
            await drive_handshake(app, ticket=spent)

            app.state.ticket_store = TicketStore(clock=clock.time)
            expired = app.state.ticket_store.mint()
            clock.now += state.TICKET_TTL_SECONDS

            refusals = {
                "no ticket at all": await drive_handshake(app),
                "an empty ticket": await drive_handshake(app, ticket=""),
                "a ticket never minted": await drive_handshake(app, ticket="not-a-real-ticket"),
                "an expired ticket": await drive_handshake(app, ticket=expired),
                "an already-consumed ticket": await drive_handshake(app, ticket=spent),
            }

            app.state.ticket_store = real_store
            accepted = await drive_handshake(app, ticket=live)
        return refusals, accepted

    async def test_all_five_are_refused(self, lifespan_client):
        refusals, accepted = await self._refusals(lifespan_client)

        for description, sent in refusals.items():
            assert not _was_accepted(sent), f"{description} was accepted"
            assert _close_codes(sent) == [_POLICY_VIOLATION], description
        # Non-vacuity from the same call site, and it is the LAST handshake driven, so it cannot
        # have disturbed the five above: a live ticket still gets a socket.
        assert _was_accepted(accepted)

    async def test_the_refusals_are_byte_identical_to_one_another(self, lifespan_client):
        refusals, _ = await self._refusals(lifespan_client)

        distinct = {repr(sent) for sent in refusals.values()}
        assert len(distinct) == 1, (
            f"the upgrade distinguishes its rejection reasons on the wire: {distinct}"
        )

    async def test_nothing_is_sent_before_the_close(self, lifespan_client):
        """Pre-accept is the ASGI-legal denial: no accept, no frame, one close and nothing else."""
        app = build_app()
        async with lifespan_client(app):
            sent = await drive_handshake(app, ticket="not-a-real-ticket")

        assert [message["type"] for message in sent] == ["websocket.close"]

    async def test_the_expiry_boundary_costs_no_wall_clock(self, lifespan_client):
        """AC 2's expiry half, with the clock's own reading asserted so the fake cannot be inert."""
        app = build_app()
        clock = FakeClock()
        async with lifespan_client(app):
            app.state.ticket_store = TicketStore(clock=clock.time)
            ticket = app.state.ticket_store.mint()

            before = await drive_handshake(app, ticket=app.state.ticket_store.mint())
            clock.now += state.TICKET_TTL_SECONDS
            after = await drive_handshake(app, ticket=ticket)

        assert _was_accepted(before), "non-vacuity: this store accepts a ticket while it is live"
        assert not _was_accepted(after)
        assert clock.slept == [], "nothing in a handshake may sleep"

    async def test_the_ticket_value_is_never_logged(self, lifespan_client, caplog):
        """AD-5: the ticket is a credential, so a rejection log names the fact and no value."""
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            await drive_handshake(app, ticket=ticket)
            with caplog.at_level(logging.DEBUG, logger=_WS_LOGGER):
                await drive_handshake(app, ticket=ticket)

        records = [record for record in caplog.records if record.name == _WS_LOGGER]
        assert records, "non-vacuity: a refusal must log something, or this proves nothing"
        for record in records:
            assert ticket not in record.getMessage()


class TestOriginIsCheckedBeforeTheTicket:
    """AC 3: a foreign page cannot burn tickets at the upgrade.

    This is the ordering assertion, and it is stated as an **observable effect** rather than as a
    line number: the rejected handshake carries a perfectly valid ticket, and that ticket is still
    consumable afterwards. Only an implementation that evaluates ``Origin`` first can pass, because
    ``consume`` pops on every path — including the paths where it says no.
    """

    async def test_a_rejected_foreign_handshake_leaves_the_ticket_alive(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)

            refused = await drive_handshake(
                app, ticket=ticket, origin=f"http://evil.example.com:{bound_port(app)}"
            )
            # The same ticket, the same call site, now from our own origin.
            accepted = await drive_handshake(app, ticket=ticket)

        assert not _was_accepted(refused)
        assert _close_codes(refused) == [_POLICY_VIOLATION]
        assert _was_accepted(accepted), "the foreign handshake burned a ticket it was refused"

    async def test_the_store_never_saw_the_foreign_handshake(self, lifespan_client):
        """The same property read off the store, so it holds even if the second handshake broke."""
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            store = ticket_store(app)

            await drive_handshake(app, ticket=ticket, origin="http://evil.example.com")

        assert store.resident_count == 1


class TestTheOriginGate:
    """AC 7, 8, 10: the calling page is checked on the handshake, and a missing header refuses."""

    @pytest.mark.parametrize(
        "origin",
        [
            "http://evil.example.com",
            "https://127.0.0.1:54321",
            "http://127.0.0.1:1",
            "http://localhost.:54321",
            "null",
            "",
        ],
        ids=["foreign-host", "https", "wrong-port", "trailing-dot", "opaque", "empty"],
    )
    async def test_a_foreign_origin_is_refused(self, lifespan_client, origin):
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)

            sent = await drive_handshake(app, ticket=ticket, origin=origin)

        assert _close_codes(sent) == [_POLICY_VIOLATION]

    async def test_a_missing_origin_header_is_refused(self, lifespan_client):
        """Q4, ruled fail-closed: browsers always send it, and c5-8's real client does too.

        That second half stopped being a prediction on 2026-08-09:
        ``tests/integration/companion/test_live_backend.py`` passes ``origin=`` explicitly, and a
        probe that removed it saw the real handshake refused 403 — this rule, over a real socket.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)

            sent = await drive_handshake(app, ticket=ticket, origin=None)

        assert _close_codes(sent) == [_POLICY_VIOLATION]

    async def test_the_localhost_spelling_is_accepted_too(self, lifespan_client):
        """Non-vacuity for the whole class, and the second of the two spellings AC 7 names."""
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)

            sent = await drive_handshake(
                app, ticket=ticket, origin=f"http://localhost:{bound_port(app)}"
            )

        assert _was_accepted(sent)

    async def test_the_origin_must_name_the_port_the_runner_actually_bound(self, lifespan_client):
        """c1-5's rule, restated for Origin: never the configured default, always app state."""
        app = build_app()
        app.state.bound_port = 55555
        async with lifespan_client(app) as client:
            ticket = await _mint(client)

            matching = await drive_handshake(app, ticket=ticket, origin="http://127.0.0.1:55555")
            stale = await drive_handshake(
                app, ticket=await _mint(client), origin="http://127.0.0.1:8765"
            )

        assert bound_port(app) == 55555, "the seam must not have overwritten the stamped port"
        assert _was_accepted(matching)
        assert not _was_accepted(stale)


class TestHostIsTheShippedMiddlewareAndNotACopy:
    """AC 6, 10: the first route-driven proof of ``test_security.py:9``'s promise.

    Those middleware tests had to be driven at the ASGI level because *"the ``websocket`` and
    ``lifespan`` branches have no route to drive them yet"*. There is a route now, and this is that
    branch reached through it — with the ticket and the ``Origin`` both perfect, so the only thing
    that can be refusing is the ``Host`` check the middleware already shipped.
    """

    async def test_a_rebound_host_is_closed_before_the_route_runs(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            store = ticket_store(app)

            sent = await drive_handshake(
                app, ticket=ticket, host=f"evil.example.com:{bound_port(app)}"
            )

        assert _close_codes(sent) == [_POLICY_VIOLATION]
        assert store.resident_count == 1, (
            "the handler ran despite the middleware's refusal — a denied connection must never "
            "reach a route expecting to accept it"
        )

    async def test_a_good_host_with_a_bad_origin_is_refused(self, lifespan_client):
        """AC 10, first pairing: ``Host`` alone is not enough — an honest hostile tab passes it."""
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)

            sent = await drive_handshake(app, ticket=ticket, origin="http://evil.example.com")

        assert _close_codes(sent) == [_POLICY_VIOLATION]

    async def test_a_good_origin_with_a_bad_host_is_refused(self, lifespan_client):
        """AC 10, second pairing: the two checks are independent and both are required."""
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)

            sent = await drive_handshake(app, ticket=ticket, host="evil.example.com:1")

        assert _close_codes(sent) == [_POLICY_VIOLATION]

    async def test_both_good_is_accepted(self, lifespan_client):
        """The non-vacuity corner of the AC 10 matrix."""
        app = build_app()
        async with lifespan_client(app) as client:
            sent = await drive_handshake(app, ticket=await _mint(client))

        assert _was_accepted(sent)


class TestAfterTheSocketIsAccepted:
    """AC 4 / Q5: client frames are drained and ignored, and disconnect returns cleanly."""

    async def test_client_frames_do_not_close_the_socket(self, lifespan_client):
        app = build_app()
        frames = [
            {"type": "websocket.receive", "text": "hello"},
            {"type": "websocket.receive", "bytes": b"\x00\x01"},
            {"type": "websocket.receive", "text": '{"kind":"not-a-real-command"}'},
        ]
        async with lifespan_client(app) as client:
            sent = await drive_handshake(app, ticket=await _mint(client), frames=frames)

        assert _was_accepted(sent)
        assert _close_codes(sent) == [], "chatter must not close the socket (AD-6, one-way)"

    async def test_the_handler_returns_on_disconnect_and_sends_nothing_after_accept(
        self, lifespan_client
    ):
        """REVISED AT c5-4, and it survives revision rather than deletion (AC 7).

        The docstring this test used to carry said *"c5-4 owns the first message this app ever
        sends"*, and c5-4 does now send one — so the sentence is spent, but the **assertion is
        not**. A socket that connects and disconnects with no broadcast in between still sees
        exactly one ``websocket.accept`` and nothing else: joining the registry is a set insertion,
        not a frame. That is what this now pins, and it is the guard that would catch a future
        story deciding to greet a new client with a hello or a state dump.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            sent = await drive_handshake(app, ticket=await _mint(client))

        assert [message["type"] for message in sent] == ["websocket.accept"]


class TestThePathAndTheMountOrdering:
    """AC 5: the route is above the mount, and the plain-HTTP behaviour of /ws is deliberate."""

    def test_the_route_is_registered_before_the_spa_mount(self):
        """Proven by the mount's **frozen** reservation set, which is the honest evidence.

        A route index would only show where the router sits in a list. The reserved-prefix set is
        derived from the route table *at install time* and never recomputed, so ``ws`` can only be
        in it if the router was registered **above** the ``install_spa(app)`` line — which is the
        property ``main.py``'s ordering block actually states. A story that moved the include below
        that line would leave this set unchanged in shape and missing exactly this entry.
        """
        app = build_app()
        mount = app.routes[-1]

        assert mount.name == "spa", "non-vacuity: the SPA mount is still the last route"
        assert "ws" in mount._reserved_prefixes
        assert ws.WS_PATH in set(spa._route_paths(app.routes))

    async def test_a_handshake_never_reaches_staticfiles(self, lifespan_client):
        """``StaticFiles``'s first line is ``assert scope["type"] == "http"``.

        A handshake that fell through to the mount would die on that assertion dressed as a server
        error. It cannot: the mount declines every non-http scope (``test_spa.py``), and this route
        is above it in any case. Proven by the handshake producing the router's own answer.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            sent = await drive_handshake(app, ticket=await _mint(client))

        assert _was_accepted(sent)

    async def test_a_plain_http_get_of_the_ws_path_is_a_typed_404(self, lifespan_client):
        """**Q1 predicted the SPA index here, and the measurement says otherwise.**

        ``spa._reserved_prefixes`` derives its reservations from the live route table and descends
        into ``WebSocketRoute`` exactly as into ``Route``, so registering this router reserved the
        segment ``ws`` and the mount now declines it. Pinned deliberately rather than discovered:
        AC 5 asks only that whichever behaviour falls out is a decision, and the typed 404 is the
        better of the two — a path that is not an HTML page should not answer with one.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(ws.WS_PATH)

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    async def test_an_unreserved_path_still_falls_through_to_the_index(self, lifespan_client):
        """Non-vacuity for the reservation: the SPA's own client routes are untouched."""
        async with lifespan_client(build_app()) as client:
            response = await client.get("/decks/42")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

    async def test_a_handshake_to_an_unknown_path_is_refused_without_reaching_the_handler(
        self, lifespan_client
    ):
        app = build_app()
        async with lifespan_client(app) as client:
            sent = await drive_handshake(app, path="/nope", ticket=await _mint(client))

        assert not _was_accepted(sent)
        assert ticket_store(app).resident_count == 1, "the handler ran for a path it does not own"


class TestTheFailClosedNet:
    """AC 16 / Q6: a fault in the handshake closes 1011 instead of escaping raw.

    ``UnhandledErrorMiddleware`` covers ``http`` scopes only and **stays** that way — there is no
    JSON body to send on a websocket scope, so extending it would give one middleware a second
    shape for exactly one caller. The disposition is local, and it is asserted on both sides of
    ``accept`` because they are genuinely different: before, there is no socket; after, there is.
    """

    async def test_a_fault_while_validating_closes_1011_pre_accept(self, caplog):
        """Driven by real code, not a monkeypatch: an app whose lifespan never ran has no store.

        ``_store`` raises ``AttributeError`` for exactly that case, matching
        ``routes/session.py``'s shape — and the port is stamped by hand so the ``Origin`` check
        passes and the fault is genuinely reached rather than short-circuited.
        """
        app = build_app()
        app.state.bound_port = 54321

        with caplog.at_level(logging.ERROR, logger=_WS_LOGGER):
            sent = await drive_handshake(app, ticket="anything")

        assert not _was_accepted(sent)
        assert _close_codes(sent) == [_INTERNAL_ERROR]
        errors = [record for record in caplog.records if record.levelname == "ERROR"]
        assert len(errors) == 1 and errors[0].exc_info, "the traceback is logged exactly once"

    async def test_a_fault_accepting_the_socket_closes_1011_pre_accept(
        self, lifespan_client, monkeypatch, caplog
    ):
        """The gap between validation and accept: `accept()` itself is not exception-safe by
        default, and a peer that vanished between the two would otherwise escape this handler raw
        (code review of c5-3, all three layers converged on this one independently)."""
        app = build_app()

        async def exploding_accept(self, *args, **kwargs):
            raise RuntimeError("the peer is already gone")

        monkeypatch.setattr("starlette.websockets.WebSocket.accept", exploding_accept)

        async with lifespan_client(app) as client:
            with caplog.at_level(logging.ERROR, logger=_WS_LOGGER):
                sent = await drive_handshake(app, ticket=await _mint(client))

        assert not _was_accepted(sent), "the fault is inside accept() itself, before it lands"
        assert _close_codes(sent) == [_INTERNAL_ERROR]
        errors = [record for record in caplog.records if record.levelname == "ERROR"]
        assert len(errors) == 1 and errors[0].exc_info, "the traceback is logged exactly once"

    async def test_a_fault_after_accept_closes_1011_on_the_live_socket(
        self, lifespan_client, monkeypatch, caplog
    ):
        app = build_app()

        async def exploding_drain(websocket):
            raise RuntimeError("the drain loop broke")

        monkeypatch.setattr(ws, "_drain_until_disconnect", exploding_drain)

        async with lifespan_client(app) as client:
            with caplog.at_level(logging.ERROR, logger=_WS_LOGGER):
                sent = await drive_handshake(app, ticket=await _mint(client))

        assert _was_accepted(sent), "the fault must be reached *after* the socket is established"
        assert _close_codes(sent) == [_INTERNAL_ERROR]
        assert any(record.exc_info for record in caplog.records)

    async def test_nothing_escapes_the_handler(self, lifespan_client, monkeypatch):
        """The property the close code is only evidence for: no exception reaches the server."""
        app = build_app()

        async def exploding_drain(websocket):
            raise RuntimeError("the drain loop broke")

        monkeypatch.setattr(ws, "_drain_until_disconnect", exploding_drain)

        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            # No pytest.raises: the assertion is that this line simply returns.
            await drive_handshake(app, ticket=ticket)

    async def test_the_healthy_path_closes_nothing(self, lifespan_client):
        """Non-vacuity: 1011 must be reachable only through a fault."""
        app = build_app()
        async with lifespan_client(app) as client:
            sent = await drive_handshake(app, ticket=await _mint(client))

        assert _INTERNAL_ERROR not in _close_codes(sent)


class TestTheTwoCredentialsNeverTouch:
    """AC 12, 13 (AD-5): the ticket and the agent token share no storage and no code path.

    This is the guard ``main.py:279-281`` asked for by name — *"the agent token must not enter a
    WebSocket frame … c5-3's to pin when the socket exists — nothing guards it yet"*. Same shape as
    ``test_routes_active_deck.py``'s sibling over ``state.py``, now over the module that owns the
    socket.
    """

    def test_the_state_module_mechanism_is_untouched(self):
        """AC 12's other half, read against ``state.py`` rather than against this story's diff."""
        assert not inspect.iscoroutinefunction(TicketStore.consume)
        assert inspect.signature(TicketStore.consume).parameters.keys() == {"self", "ticket"}


class TestTheConsumeStaysSynchronous:
    """AC 14 (``deferred-work.md``'s consume-atomicity entry): the no-lock argument, re-made.

    ``state.py`` argues ``consume`` needs no lock because the compare-and-set is one ``dict.pop``
    with no ``await`` between the read and the delete. Until this story that argument had **zero
    production callers**, so the ledger asked the story that calls it to show the call sits in
    synchronous code. These are that showing, stated against the code rather than against prose.
    """

    def test_consume_is_still_a_plain_function(self):
        assert not inspect.iscoroutinefunction(TicketStore.consume)


class TestTheConnectionRegistry:
    """AC 1-5: the holder the fan-out counts clients from, beside the ticket store it copies.

    TWO SUCCESSIVE PREDICTIONS ABOUT WHO WANTS `connected_count` HAVE NOW BEEN FALSIFIED, and both
    are recorded rather than rewritten out. c5-5 was named first and ruled otherwise (Q1, Brad
    2026-08-08): its receipt carries the delivered count from `broadcast()`. This docstring then
    said the property was kept "for the live-gauge question c5-7 asks" — and c5-7 shipped on
    2026-08-08 asking no such question. Its connection pill reports the browser's OWN socket
    status and the active deck's name (FR-15, UX-DR29) and calls this backend not at all.

    The property is kept because this test module and `test_routes_active_deck.py` consume it —
    `ws.broadcast` itself reads only `snapshot`/`add`/`discard`, never this property. The honest
    owner of the live-gauge question is a future status surface, and c10-1 — the nearest
    candidate — reads `GET /health` rather than a client count.

    Driven entirely against :class:`FakeConnection`, which is the point of the structural protocol:
    the registry is a container, and a container's contract is provable without a web server.
    """

    def test_a_fresh_registry_is_empty(self):
        assert ConnectionRegistry().connected_count == 0

    def test_construction_takes_no_positional_arguments(self):
        """AC 1: keyword-only init, matching :class:`TicketStore`'s shape.

        **What it compares:** the signature's parameter kinds. **What it cannot see:** whether
        construction does I/O — which the next test covers by constructing one at import-safe
        time and asserting nothing but the object came back.
        """
        parameters = inspect.signature(ConnectionRegistry.__init__).parameters

        assert list(parameters) == ["self"], (
            "the registry grew a constructor parameter; if it needs one it must be keyword-only, "
            "the way TicketStore's are"
        )

    def test_two_registries_share_nothing(self):
        """AC 1: inert construction, and no module-level container behind it.

        A registry backed by a module-level set would make every app in the suite share one
        connection list — and would be the CM-3 violation ``security.py``'s stores-nothing guard
        exists to catch one module over.
        """
        first, second = ConnectionRegistry(), ConnectionRegistry()

        first.add(FakeConnection())

        assert first.connected_count == 1
        assert second.connected_count == 0

    def test_adding_a_connection_makes_it_countable_and_reachable(self):
        registry, connection = ConnectionRegistry(), FakeConnection()

        registry.add(connection)

        assert registry.connected_count == 1
        assert registry.snapshot() == (connection,)

    def test_adding_the_same_connection_twice_registers_it_once(self):
        """One socket is one client: the handler registers once, but a re-entrant add must not
        double it, or every count derived from this set would over-report the tabs that exist —
        c5-5's delivered count included, since the fan-out iterates a snapshot of this set and
        would write to the same socket twice. (This used to name "c5-7's pill directly" as the
        other consumer; that prediction was falsified when the pill shipped reading nothing from
        this backend — see the class docstring.)"""
        registry, connection = ConnectionRegistry(), FakeConnection()

        registry.add(connection)
        registry.add(connection)

        assert registry.connected_count == 1

    def test_discard_removes_the_connection(self):
        registry, connection = ConnectionRegistry(), FakeConnection()
        registry.add(connection)

        registry.discard(connection)

        assert registry.connected_count == 0
        assert registry.snapshot() == ()

    def test_discarding_an_absent_connection_is_a_silent_no_op(self):
        """AC 5, and it is load-bearing rather than defensive.

        The fan-out drops a socket it could not write to **and** the handler's ``finally`` drops the
        same socket when the drain returns. Both run, in either order, for one dying tab — so a
        ``discard`` that raised on a miss would turn the ordinary disconnect into a 1011.
        """
        registry, connection = ConnectionRegistry(), FakeConnection()

        registry.discard(connection)  # never added
        registry.add(connection)
        registry.discard(connection)
        registry.discard(connection)  # already gone

        assert registry.connected_count == 0

    def test_the_snapshot_is_a_copy_the_caller_may_outlive(self):
        """AC 5's other half: the fan-out mutates the registry **while** iterating its snapshot.

        **What it compares:** that a registration made after the snapshot is not visible in it, and
        that a discard during iteration does not raise. **What it cannot see:** anything about
        ordering — the registry promises none, and AD-6 puts ordering on ``ts`` rather than on the
        transport.
        """
        registry = ConnectionRegistry()
        first, second = FakeConnection(), FakeConnection()
        registry.add(first)
        registry.add(second)

        snapshot = registry.snapshot()
        for connection in snapshot:
            registry.discard(connection)
        registry.add(FakeConnection())

        assert len(snapshot) == 2
        assert set(snapshot) == {first, second}
        assert registry.connected_count == 1


def _an_event(deck_id="deck-under-test"):
    """Build one ``active_deck_changed`` envelope, so a fan-out test has something to send."""
    return ActiveDeckChangedEvent(
        kind="active_deck_changed",
        id="00000000000000000000000000000000",
        ts=datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
        payload=ActiveDeckChangedPayload(deck_id=deck_id),
    )


class TestTheFanOut:
    """AC 9-13: every client, once, byte-identical, and one failure contained to one socket.

    Driven against :class:`FakeConnection` rather than the router, because the properties here are
    the *fan-out's* — delivery, containment, accounting — and a socket adds nothing to any of them.
    The single proof that the router really reaches this code with two real clients open is
    ``TestTwoTabsOnePut`` below.
    """

    async def test_every_connected_client_receives_the_event(self, lifespan_client):
        """AC 9 (FR-06): every client, not the first, not a sample."""
        app = build_app()
        async with lifespan_client(app):
            registry = connection_registry(app)
            clients = [FakeConnection() for _ in range(3)]
            for client in clients:
                registry.add(client)

            delivered = await ws.broadcast(app, _an_event())

        assert delivered == 3
        assert all(len(client.sent) == 1 for client in clients)

    async def test_every_client_receives_byte_identical_text(self, lifespan_client):
        """AC 10: serialised once, so no client can be handed a differently-ordered rendering."""
        app = build_app()
        event = _an_event()
        async with lifespan_client(app):
            registry = connection_registry(app)
            clients = [FakeConnection() for _ in range(3)]
            for client in clients:
                registry.add(client)

            await ws.broadcast(app, event)

        texts = {client.sent[0] for client in clients}
        assert len(texts) == 1, "the clients received different bytes for one event"
        assert texts == {event.model_dump_json()}

    async def test_the_frame_parses_back_to_the_event_that_was_sent(self, lifespan_client):
        """AC 16: what lands on the wire is a union member, validated the way a client would.

        ``TypeAdapter(AgentEvent)`` is the discriminated union c5-1 froze, so this fails if the
        envelope loses its ``kind``, its ``id`` or its ``ts`` — not merely if the text changes.
        """
        app = build_app()
        async with lifespan_client(app):
            client = FakeConnection()
            connection_registry(app).add(client)

            await ws.broadcast(app, _an_event(deck_id="a-particular-deck"))

        event = TypeAdapter(AgentEvent).validate_json(client.sent[0])
        assert isinstance(event, ActiveDeckChangedEvent)
        assert event.kind == "active_deck_changed"
        assert event.payload.deck_id == "a-particular-deck"

    async def test_a_broadcast_to_nobody_succeeds_silently(self, lifespan_client, caplog):
        """AC 11 (NFR-04): the ordinary state of a companion with no tab open."""
        app = build_app()
        async with lifespan_client(app):
            with caplog.at_level(logging.WARNING, logger=_WS_LOGGER):
                delivered = await ws.broadcast(app, _an_event())

        assert delivered == 0
        assert caplog.records == [], "a broadcast nobody hears is not worth a warning"

    async def test_a_failing_client_is_contained_dropped_and_closed(self, lifespan_client, caplog):
        """AC 8, 12: the epic's verbatim AC — removed without error, others unaffected."""
        app = build_app()
        async with lifespan_client(app):
            registry = connection_registry(app)
            healthy, gone = FakeConnection(), FakeConnection(fails=True)
            registry.add(healthy)
            registry.add(gone)

            with caplog.at_level(logging.DEBUG, logger=_WS_LOGGER):
                delivered = await ws.broadcast(app, _an_event())

            assert registry.connected_count == 1, "the dead client is out of the set"
            assert registry.snapshot() == (healthy,)

        assert delivered == 1, "the count reports deliveries, not attempts"
        assert len(healthy.sent) == 1, "the surviving client still received the event"
        assert gone.closed == [_INTERNAL_ERROR], "the dead socket is closed best-effort"
        assert [record.levelname for record in caplog.records] == ["DEBUG"], (
            "a dying tab is routine; anything above DEBUG makes an operator's console noisy"
        )

    async def test_a_failing_client_does_not_stop_the_ones_after_it(self, lifespan_client):
        """AC 12: containment is per-socket, so position in the fan-out must not matter.

        Ten healthy clients around one broken one: a fan-out that aborted on the first failure
        would deliver to some prefix of them, whatever order the set happens to iterate in.
        """
        app = build_app()
        async with lifespan_client(app):
            registry = connection_registry(app)
            healthy = [FakeConnection() for _ in range(10)]
            for client in healthy:
                registry.add(client)
            registry.add(FakeConnection(fails=True))

            delivered = await ws.broadcast(app, _an_event())

        assert delivered == 10
        assert all(len(client.sent) == 1 for client in healthy)

    async def test_no_exception_escapes_to_the_caller(self, lifespan_client):
        """AC 12, 18: the mutation that triggered the broadcast must not learn about a dead tab."""
        app = build_app()
        async with lifespan_client(app):
            connection_registry(app).add(FakeConnection(fails=True))

            # No pytest.raises: the assertion is that this line returns a number.
            assert await ws.broadcast(app, _an_event()) == 0

    async def test_a_broadcast_before_the_lifespan_ran_is_a_no_op(self):
        """AC 12: there is no app state to reach, and that is still not the caller's problem."""
        assert await ws.broadcast(build_app(), _an_event()) == 0

    async def test_the_active_deck_helper_mints_an_opaque_id_and_an_aware_timestamp(
        self, lifespan_client
    ):
        """AC 16: backend-minted ``id``, aware-UTC ``ts``, and no two events share an id.

        The id is opaque and for dedupe only — AD-6 puts *ordering* on ``ts`` — so this asserts
        distinctness rather than any structure, which is the only property the contract promises.
        """
        app = build_app()
        async with lifespan_client(app):
            client = FakeConnection()
            connection_registry(app).add(client)

            await ws.broadcast_active_deck_changed(app, "deck-one")
            await ws.broadcast_active_deck_changed(app, "deck-one")

        adapter = TypeAdapter(AgentEvent)
        first, second = (adapter.validate_json(text) for text in client.sent)
        assert first.id != second.id, "two events shared an id; dedupe would drop the second"
        assert first.ts.tzinfo is not None, "naive timestamps are banned project-wide"
        assert first.ts.utcoffset() == timedelta(0), "aware UTC, not merely aware"

    async def test_the_cleared_case_carries_a_null_deck_id(self, lifespan_client):
        """The contract's nullable half, reachable through the helper rather than only by type."""
        app = build_app()
        async with lifespan_client(app):
            client = FakeConnection()
            connection_registry(app).add(client)

            assert await ws.broadcast_active_deck_changed(app, None) == 1

        assert TypeAdapter(AgentEvent).validate_json(client.sent[0]).payload.deck_id is None


class TestTheSocketLifecycle:
    """AC 6-8: a connection joins after accept and leaves on every exit path."""

    async def test_the_socket_is_registered_while_the_drain_is_running(self, lifespan_client):
        """AC 6: the positive half — a socket held open really is in the fan-out's set.

        This is what ``open_socket`` exists for: ``drive_handshake`` returns only after the handler
        has finished, so under it the count is always zero and this assertion would be vacuous.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            registry = connection_registry(app)
            assert registry.connected_count == 0  # non-vacuity: it starts empty

            async with open_socket(app, ticket=await _mint(client)):
                assert registry.connected_count == 1

            assert registry.connected_count == 0, "the finally ran on the ordinary disconnect"

    async def test_a_refused_handshake_never_joins(self, lifespan_client):
        """AC 6: a rejected upgrade has no channel to write to, so it is not in the fan-out.

        **What it cannot see — and this was found by its own R2 probe, not by reading it.** A
        refusal returns *before* the accept block entirely, so moving ``registry.add`` to the line
        above ``await websocket.accept()`` leaves this test green: the refused handshake still
        never reaches either line. The case that distinguishes "after accept" from "before accept"
        is an *authorised* handshake whose ``accept()`` fails, and that is the next test.
        """
        app = build_app()
        async with lifespan_client(app):
            registry = connection_registry(app)

            await drive_handshake(app, ticket="never-minted")

            assert registry.connected_count == 0

    async def test_a_socket_that_failed_to_accept_is_never_registered(
        self, lifespan_client, monkeypatch
    ):
        """AC 6: **only after** ``accept()`` succeeds — the half the refusal test cannot reach.

        A connection registered before the accept that then fails would sit in the fan-out as a
        socket the backend never established: every later broadcast would try to write to it,
        fail, and drop it — noise for a client that was never there.

        **What it compares:** the registry's count after an authorised handshake whose ``accept()``
        raised. **What it cannot see:** a registration placed between ``accept()`` returning and the
        drain starting, which is the shipped position and is what the two tests above observe.
        """
        app = build_app()

        async def exploding_accept(self, *args, **kwargs):
            raise RuntimeError("the peer is already gone")

        monkeypatch.setattr("starlette.websockets.WebSocket.accept", exploding_accept)

        async with lifespan_client(app) as client:
            registry = connection_registry(app)

            sent = await drive_handshake(app, ticket=await _mint(client))

            assert not _was_accepted(sent), "non-vacuity: the fault really was inside accept()"
            assert _close_codes(sent) == [_INTERNAL_ERROR]
            assert registry.connected_count == 0

    async def test_a_refused_origin_never_joins_either(self, lifespan_client):
        """AC 6, paired with the acceptance above so the guard cannot pass by refusing all."""
        app = build_app()
        async with lifespan_client(app) as client:
            registry = connection_registry(app)

            await drive_handshake(app, ticket=await _mint(client), origin="http://evil.example")
            assert registry.connected_count == 0

            await drive_handshake(app, ticket=await _mint(client))
            assert registry.connected_count == 0, "and the accepted one left again on disconnect"

    async def test_the_1011_fault_path_also_unregisters(self, lifespan_client, monkeypatch):
        """AC 6: **every** exit path, which is the half a plain ``discard`` after the drain misses.

        A handler that unregistered on the line after the drain would leak a connection for every
        fault — and the leaked object is a dead socket the next broadcast would try to write to.
        """
        app = build_app()

        async def exploding_drain(websocket):
            raise RuntimeError("the drain loop broke")

        monkeypatch.setattr(ws, "_drain_until_disconnect", exploding_drain)

        async with lifespan_client(app) as client:
            registry = connection_registry(app)

            sent = await drive_handshake(app, ticket=await _mint(client))

            assert _was_accepted(sent), "non-vacuity: the fault is genuinely post-accept"
            assert _close_codes(sent) == [_INTERNAL_ERROR]
            assert registry.connected_count == 0

    async def test_two_sockets_are_registered_at_once(self, lifespan_client):
        """AC 9's precondition: the registry really holds concurrent tabs, not one at a time."""
        app = build_app()
        async with lifespan_client(app) as client:
            registry = connection_registry(app)

            async with open_socket(app, ticket=await _mint(client)):
                async with open_socket(app, ticket=await _mint(client)):
                    assert registry.connected_count == 2
                assert registry.connected_count == 1

            assert registry.connected_count == 0


class TestTheRegistryAccessor:
    """AC 3: one construction site, one accessor, ``None`` when the lifespan never ran."""

    def test_a_constructed_app_has_no_registry(self):
        assert connection_registry(build_app()) is None

    async def test_the_lifespan_creates_one(self, lifespan_client):
        app = build_app()

        async with lifespan_client(app):
            assert isinstance(connection_registry(app), ConnectionRegistry)

    async def test_build_app_grew_no_side_effect(self):
        """AC 3 (AD-10): the registry is a lifespan value, not a ``build_app()`` one."""
        assert connection_registry(build_app()) is None
        assert not hasattr(build_app().state, "connections")

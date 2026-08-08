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
end-to-end browser-to-backend proof on **c5-8**, and no ``tests/integration/companion/`` exists.
"""

import ast
import doctest
import importlib
import inspect
import logging
from pathlib import Path

import pytest

from src.companion.app import spa, state, ws
from src.companion.app.main import bound_port, build_app
from src.companion.app.state import TicketStore, ticket_store
from tests.unit.companion.conftest import FakeClock, drive_handshake

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WS_SOURCE = _REPO_ROOT / "src/companion/app/ws.py"
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
        """The shape c5-6's reconnect loop will actually perform: mint, upgrade, mint, upgrade."""
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
        """Q4, ruled fail-closed: browsers always send it and c5-8's client sets it explicitly."""
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

    async def test_ws_py_contains_no_host_check_of_its_own(self):
        """AD-5's *reused, not duplicated* half, asserted structurally rather than by reading.

        **What it compares:** ``ws.py``'s syntax tree against the vocabulary a second ``Host``
        check would have to be written in. **What it cannot see:** a check spelled entirely in
        names it does not know — which is why the behavioural pair above exists, and why a bare
        ``"host"`` string constant is caught here too (``code_identifiers`` is AST-only and skips
        constants, so this walks the source for the literal separately).
        """
        tree = ast.parse(_WS_SOURCE.read_text(encoding="utf-8"))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        names |= {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }

        # Non-vacuity: the walk really found this module's own code.
        assert {"origin_is_allowed", "consume", "accept"} <= names

        assert not ({"host_is_allowed", "allowed_authorities", "HostValidationMiddleware"} & names)
        constants = {
            node.value.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert "host" not in constants, "ws.py reads a Host header of its own (AD-5: reuse it)"

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
        """The channel is one-way today: c5-4 owns the first message this app ever sends."""
        app = build_app()
        async with lifespan_client(app) as client:
            sent = await drive_handshake(app, ticket=await _mint(client))

        assert [message["type"] for message in sent] == ["websocket.accept"]

    async def test_no_connection_registry_was_scaffolded(self):
        """AC 4's other half: the registry and the broadcast are c5-4's, and are absent."""
        identifiers = {
            node.id
            for node in ast.walk(ast.parse(_WS_SOURCE.read_text(encoding="utf-8")))
            if isinstance(node, ast.Name)
        }

        assert "router" in identifiers  # non-vacuity
        assert not ({"broadcast", "connections", "ConnectionRegistry"} & identifiers)
        assert not hasattr(state, "ConnectionRegistry")


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


class TestTheBindAddressIsUnchanged:
    """AC 11 (NFR-01): the socket rides c1-3's bind; this story adds no bind surface."""

    def test_the_server_still_binds_loopback_only(self):
        from src.companion.app import server

        assert server.HOST == "127.0.0.1"

    def test_ws_py_opens_no_socket_of_its_own(self):
        identifiers = _identifiers(_WS_SOURCE)

        assert "websocket_upgrade" in identifiers  # non-vacuity
        assert not ({"socket", "uvicorn", "serve", "bind", "listen"} & identifiers)


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

    async def test_the_error_middleware_is_still_http_only(self):
        """Q6's other half: the fix is local, so the shipped middleware must not have grown."""
        from src.companion.app import errors

        source = inspect.getsource(errors.UnhandledErrorMiddleware.__call__)

        assert 'scope["type"] != "http"' in source

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

    def test_the_ws_module_names_no_agent_credential(self):
        """**What it compares:** ``ws.py``'s syntax tree against the eight ways the agent token is
        reachable in this package. **What it cannot see:** an indirection built from names it does
        not know (``getattr(app.state, "agent_" + "token")``), which is the residual its sibling
        over ``state.py`` also carries.
        """
        identifiers = _identifiers(_WS_SOURCE)

        # Non-vacuity, and a real one: the walk must be finding the upgrade's OWN code, or every
        # absence below is satisfied by scanning an empty set.
        assert {"websocket_upgrade", "origin_is_allowed", "ticket_store", "consume"} <= identifiers

        shared_paths = {
            "discovery",
            "mint_token",
            "agent_token",
            "presented_credential",
            "agent_token_is_valid",
            "require_agent_token",
            "AgentToken",
            "_AUTHORIZATION_HEADER",
        }
        assert not (shared_paths & identifiers), (
            f"the WebSocket upgrade shares a code path with the agent token: "
            f"{shared_paths & identifiers} (AD-5)"
        )

    def test_the_upgrade_reaches_the_store_through_the_one_accessor(self):
        """AC 12: the store is not moved, not wrapped and not duplicated."""
        identifiers = _identifiers(_WS_SOURCE)

        assert "ticket_store" in identifiers
        assert "TicketStore" in identifiers, "the type is imported for the annotation, not rebuilt"
        # A second holder would be a second construction site for one piece of state.
        tree = ast.parse(_WS_SOURCE.read_text(encoding="utf-8"))
        constructions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "TicketStore"
        ]
        assert constructions == [], "ws.py builds its own TicketStore"

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

    def test_the_consume_call_site_is_not_inside_an_await(self):
        """The AST half: no ``Await`` node anywhere in the function that pops the ticket.

        **What it compares:** the body of ``ws.py``'s authorisation function for ``Await`` nodes and
        for its own ``async`` -ness. **What it cannot see:** a suspension introduced *outside* that
        function and *between* the two decisions — which is impossible only because both decisions
        are inside it, and the next assertion pins that they are.
        """
        tree = ast.parse(_WS_SOURCE.read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }

        gate = functions["_handshake_is_authorised"]
        assert isinstance(gate, ast.FunctionDef), (
            "_handshake_is_authorised became `async def` — one of the three changes state.py "
            "names as breaking the no-lock argument"
        )
        assert not [node for node in ast.walk(gate) if isinstance(node, ast.Await)]

    def test_both_decisions_live_in_that_one_synchronous_function(self):
        """Non-vacuity for the guard above: an empty function has no ``Await`` either."""
        tree = ast.parse(_WS_SOURCE.read_text(encoding="utf-8"))
        gate = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_handshake_is_authorised"
        )
        called = {
            node.func.id
            for node in ast.walk(gate)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        attributes = {node.attr for node in ast.walk(gate) if isinstance(node, ast.Attribute)}

        assert "origin_is_allowed" in called
        assert "consume" in attributes

    def test_the_pop_is_still_one_statement(self):
        """The first of state.py's three breakers: splitting the pop into a get plus a del."""
        source = inspect.getsource(TicketStore.consume)

        assert source.count(".pop(") == 1
        assert "del " not in source


class TestTheDocstringExamplesRun:
    """AC 19 (``deferred-work.md``'s doctest entry): every ``Example:`` block in the package runs.

    **This is the prescribed fix, not the convenient one.** The ledger entry named
    ``security.py:97,116`` as two blocks nothing executed, and said the honest repair is *"one test
    that walks every ``src/companion`` module"* rather than two more bespoke lines — because two
    bespoke lines leave the third module's examples unexecuted and the next story owing the same
    entry again. c5-1 (``test_contracts.py``) and c5-2 (``test_routes_session.py``) each wired one
    module; this **supersedes** both by covering the package, and neither is deleted — a passing
    guard is not removed for being redundant (C4 retro).

    ``testpaths`` is scoped to ``tests/``, so ``--doctest-modules`` never reaches ``src/``; folding
    ``doctest.testmod`` into an ordinary test is the shape this package already uses.
    """

    @staticmethod
    def _companion_modules():
        """Import and return every module under ``src/companion``, discovered from the tree.

        Discovered rather than listed, which is the whole point: a module added tomorrow is
        covered without an edit here, and that is what closes the ledger entry instead of
        re-homing it.
        """
        package_root = _REPO_ROOT / "src/companion"
        modules = []
        for path in sorted(package_root.rglob("*.py")):
            if path.name == "__init__.py":
                dotted = ".".join(path.parent.relative_to(_REPO_ROOT).parts)
            else:
                dotted = ".".join(path.relative_to(_REPO_ROOT).with_suffix("").parts)
            modules.append(importlib.import_module(dotted))
        return modules

    def test_every_example_in_every_companion_module_passes(self):
        modules = self._companion_modules()

        # Non-vacuity on the walk itself: an empty discovery would satisfy every assertion below.
        assert len(modules) > 10, f"the module walk found only {len(modules)}"

        attempted = 0
        failures = []
        for module in modules:
            results = doctest.testmod(module, verbose=False)
            attempted += results.attempted
            if results.failed:
                failures.append(f"{module.__name__}: {results.failed} failed")

        assert not failures, failures
        # Non-vacuity on the execution: `testmod` reports 0 failed for a module with no examples,
        # so the attempted count is the half that proves anything ran at all.
        assert attempted > 0

    def test_the_security_module_examples_are_among_them(self):
        """The specific gap the ledger entry named, asserted by name so it cannot silently lapse."""
        from src.companion.app import security

        results = doctest.testmod(security, verbose=False)

        assert results.attempted > 0, "security.py's Example: blocks stopped being executable"
        assert results.failed == 0


def _identifiers(path):
    """Return every identifier a module's **code** mentions, ignoring prose and string constants.

    The same AST-only shape ``test_routes_active_deck.code_identifiers`` uses, and for the same
    reason: a raw-text scan is keyed on syntax rather than meaning, so the first thing it catches
    is the docstring explaining why the banned thing is absent. Re-stated here rather than imported
    across test modules, matching how the two existing copies in this package already relate.

    **One deliberate widening over the sibling: names a module *defines*.** ``code_identifiers``
    collects ``Name`` and ``Attribute`` nodes, and a ``def foo()`` is neither — so a scan of a
    module whose only interesting content is its own definitions has nothing to assert non-vacuity
    against, which is exactly the shape ``ws.py`` has. Adding definitions strengthens the
    non-vacuity half and cannot weaken the ban half: a module that *defined* ``agent_token``
    should fail these guards too.

    Args:
        path: A path to a Python module.

    Returns:
        Every imported module and name, every ``Name``, every attribute accessed, and every
        function, class and argument this module defines.
    """
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.add(node.name)
        elif isinstance(node, ast.arg):
            found.add(node.arg)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.update(alias.name.split("."))
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.update(node.module.split("."))
                found.add(node.module)
            for alias in node.names:
                found.add(alias.name)
                if alias.asname:
                    found.add(alias.asname)
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
    return found

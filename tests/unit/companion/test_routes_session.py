"""Story c5-2: the same-origin session endpoint and its single-use tickets (NFR-01, AD-5).

**The route is eight lines; the store is where the risk is, and the tests are weighted that way.**
Minting is a dict write that cannot fail. What can fail is *forgetting*: a ticket that survives its
consume is not single-use, a ticket that survives its deadline is not 30-second, and a store that
merely *ignores* expiry rather than *pruning* it passes every behavioural assertion in this file
while filling with garbage and evicting live tickets to make room for it. Only
:attr:`~src.companion.app.state.TicketStore.resident_count` can tell those two apart, which is why
it exists.

**Every rejection is paired with an acceptance from the same call.** A consume that returned
``False`` unconditionally would satisfy "a replayed ticket is refused", "an expired ticket is
refused" and "an unknown ticket is refused" simultaneously — so each of those is asserted beside a
fresh ticket that is *accepted*, in the same test, against the same store.

**No test here sleeps, and that is a rule rather than a preference (AC 25).** The TTL is 30 seconds
and it is proven at zero wall clock by injecting :class:`FakeClock`'s time source — directly for the
store's own unit tests, and through a monkeypatched *constructor* for the route-level ones, which is
the pattern ``test_routes_card_image.py`` established for the pacer and the negative cache.

**Mint-side route assertions go through the wire** (the rule ``test_routes_active_deck.py`` states
about the active-deck slot: a test that only inspected ``app.state`` would pass with the route
deleted). Two declared exceptions read the store directly, and each is forced: the consume half has
**no wire surface until c5-3**, so ``test_the_shipped_ttl_reaches_the_route`` must close its
mint-to-expiry loop through ``store.consume``; and ``TestTheStoreIsCreatedByTheLifespan`` is
*about* the lifespan's wiring of ``app.state``, so the state key is its subject, not its shortcut.
"""

import ast
import logging
from pathlib import Path

import httpx
import pytest

from src.companion.app import state
from src.companion.app.main import agent_token, build_app
from src.companion.app.state import MAX_TICKETS, TICKET_TTL_SECONDS, TicketStore, ticket_store

from .conftest import FakeClock

_PATH = "/api/session"

_PORT = 54321
"""The port ``lifespan_client`` stamps, restated here so the ``Host`` cases can address the app as
something else without importing a private conftest constant."""

_REPO_ROOT = Path(__file__).resolve().parents[3]

_ROUTE_MODULE = _REPO_ROOT / "src/companion/app/routes/session.py"
"""Resolved against the repo root rather than the CWD, matching every source-scanning guard in
``test_routes_active_deck.py``."""


@pytest.fixture
def clocked(monkeypatch):
    """Return a :class:`FakeClock` the lifespan's ticket store will be built against.

    Monkeypatches the **constructor** rather than the instance, because the store is created inside
    :func:`~src.companion.app.main.lifespan` and there is no seam between construction and the
    first request. ``test_routes_card_image.py:1946`` established this shape for the pacer; the
    ``**kwargs`` pass-through keeps the production defaults in play so the test proves the shipped
    TTL rather than one it chose.
    """
    clock = FakeClock()
    real_store = state.TicketStore
    monkeypatch.setattr(
        state, "TicketStore", lambda **kwargs: real_store(clock=clock.time, **kwargs)
    )
    return clock


class TestTheMint:
    """AC 1, 2, 4 (NFR-01, AD-5): the endpoint answers, and every answer is new."""

    async def test_it_answers_200_with_a_ticket(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH)

        assert response.status_code == 200
        body = response.json()
        # The shape is exactly the model and nothing more — no `expires_in`, no `issued_at`, no
        # envelope. AD-16 keeps the MCP result wrapper out of REST, and Q4 ruled the TTL
        # deliberately unpublished.
        assert set(body) == {"ticket"}
        assert isinstance(body["ticket"], str)
        assert body["ticket"]

    async def test_no_credential_is_required(self, lifespan_client):
        """AC 4: asserted **positively**, the way c3-4 asserts its own credential-free read.

        The browser holds no credential and never will (AD-5). A test that only checked "a bad
        token is refused" would pass on an endpoint that demanded one, so the assertable claim is
        that a client presenting *nothing but* ``Host`` is served.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH)

        assert response.status_code == 200
        # And no challenge was issued — a 200 that asked for a credential would be a contradiction
        # the status code alone cannot show.
        assert "WWW-Authenticate" not in response.headers

    async def test_consecutive_calls_never_return_the_same_ticket(self, lifespan_client):
        """AC 2: distinctness, over the wire, on one running app.

        Three calls rather than two: two consecutive equal values could be a coincidence in a
        mechanism that alternated, and three distinct ones from one process rules out any
        per-process memo as well as any per-request one.
        """
        async with lifespan_client(build_app()) as client:
            issued = [(await client.get(_PATH)).json()["ticket"] for _ in range(3)]

        assert len(set(issued)) == 3

    async def test_a_second_app_shares_no_tickets_with_the_first(self, lifespan_client):
        """AC 11: the store is per-process memory, so a restart begins empty.

        Two apps stand in for two processes — the closest this in-process seam can get to a
        restart, and enough to prove there is no module-level, class-level or on-disk store behind
        the accessor.
        """
        async with lifespan_client(build_app()) as first:
            first_ticket = (await first.get(_PATH)).json()["ticket"]
        async with lifespan_client(build_app()) as second:
            second_ticket = (await second.get(_PATH)).json()["ticket"]

        assert first_ticket != second_ticket

    async def test_the_ticket_is_not_the_agent_token(self, lifespan_client):
        """AC 2, 13 (AD-5): the two credentials are different values, measured.

        The strongest single wire-level statement of "no shared code path": if the mint had reached
        for ``discovery.mint_token()`` or read ``app.state.agent_token``, this is where it would
        show. The token is read from the app rather than from the discovery file so the comparison
        is against the real minted value.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = (await client.get(_PATH)).json()["ticket"]

        # Non-vacuity: the lifespan really minted a token, so the inequality is between two real
        # values rather than against None.
        assert agent_token(app)
        assert ticket != agent_token(app)


class TestTheAgentTokenNeverReachesTheBrowser:
    """AC 13 (AD-5): the token appears in no response and no log line this story writes."""

    async def test_the_response_carries_no_trace_of_the_token(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.get(_PATH)

        token = agent_token(app)
        assert token  # non-vacuity: there is a real token to look for
        # Body AND headers: a credential leaked into a `Set-Cookie` or a bespoke header would be
        # invisible to a body-only assertion.
        assert token not in response.text
        assert not any(token in value for value in response.headers.values())

    async def test_nothing_logged_while_serving_the_mint_names_the_token(
        self, lifespan_client, caplog
    ):
        """The log half, in the shape ``test_routes_active_deck.py`` uses for its rejection path.

        Captured at ``DEBUG`` so a diagnostic line added later by any layer in the request path is
        in scope, not just the ones this story writes.
        """
        app = build_app()
        with caplog.at_level(logging.DEBUG):
            async with lifespan_client(app) as client:
                ticket = (await client.get(_PATH)).json()["ticket"]

        token = agent_token(app)
        assert token
        for record in caplog.records:
            assert token not in record.getMessage()
        # …and the ticket itself is not logged either. It is a credential too, and a log file is
        # exactly the kind of client-side storage layer AC 19's `no-store` exists to deny.
        for record in caplog.records:
            assert ticket not in record.getMessage()


class TestTheHostEnvelopeIsInherited:
    """AC 5 (c1-5, AD-5): refused by the shipped middleware, not by a check in this route."""

    async def test_a_foreign_host_is_refused_with_invalid_request(self, lifespan_client):
        async with lifespan_client(
            build_app(), base_url=f"http://evil.example.com:{_PORT}"
        ) as client:
            response = await client.get(_PATH)

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}

    async def test_loopback_and_localhost_are_both_admitted(self, lifespan_client):
        """Non-vacuity for the rejection above, and it is a real pair.

        A middleware that refused *everything* would satisfy the rejection test alone. Both
        spellings c1-5 admits are asserted, because the route must be reachable under whichever one
        the SPA is loaded from.
        """
        for authority in (f"127.0.0.1:{_PORT}", f"localhost:{_PORT}"):
            async with lifespan_client(build_app(), base_url=f"http://{authority}") as client:
                response = await client.get(_PATH)

            assert response.status_code == 200, authority

    def test_the_route_module_contains_no_host_or_origin_check_of_its_own(self):
        """AC 5's "without duplicating the check", and Q1's ruling, asserted structurally.

        **Q1 (Brad 2026-08-08): no ``Origin`` validation on the mint.** AD-5 and review finding S-6
        both home it on the upgrade (c5-3), there is no CORS middleware and c1-5 ruled there never
        will be, so a foreign page can issue this GET but cannot read the response. Duplicating
        either check here would put one decision in two places to keep in sync.

        **What this compares:** the route module's source text against the two header names. **What
        it cannot see:** a check spelled without either literal — reading ``request.headers`` by a
        computed key, or delegating to a helper. Read against the code: the module reaches
        ``request`` only for ``request.app``, which the import-level assertion below pins.
        """
        source = (_ROUTE_MODULE).read_text(encoding="utf-8")
        # The prose discusses both headers at length and must be free to — the module docstring,
        # AND every function/class docstring, are prose. Stripped via the AST rather than by
        # splitting on the module docstring's closing quotes, so that documenting the Host envelope
        # in a *handler* docstring stays an editorial act instead of reddening a security test.
        doc_lines: set[int] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                first = node.body[0] if node.body else None
                if (
                    isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)
                    and first.end_lineno is not None
                ):
                    doc_lines.update(range(first.lineno, first.end_lineno + 1))
        body = "\n".join(
            line
            for number, line in enumerate(source.splitlines(), start=1)
            if number not in doc_lines and not line.lstrip().startswith("#")
        )

        assert "Origin" not in body
        assert "Host" not in body
        # Non-vacuity: the body really is the executable half and really contains the route.
        assert "mint_session_ticket" in body


class TestTheResponseIsNotCacheable:
    """AC 19 (Q5, Brad 2026-08-08): the first success path in this app to set ``no-store``."""

    async def test_the_200_carries_no_store(self, lifespan_client):
        """A single-use credential a client is free to cache is single-use in name only.

        The response is already unreadable cross-origin, so this defends the *client's own* storage
        layers — bfcache, an extension, an intermediary — which same-origin policy does not.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH)

        assert response.headers["Cache-Control"] == "no-store"

    async def test_a_cacheable_sibling_proves_the_header_is_this_route_s(self, lifespan_client):
        """Non-vacuity, and it is a real one: nothing sets this header app-wide.

        ``/health`` is served by the same app through the same middleware stack and sets no
        ``Cache-Control`` at all, so the header above is genuinely attached by this route rather
        than inherited from something that would have set it either way.
        """
        async with lifespan_client(build_app()) as client:
            health = await client.get("/health")

        assert health.status_code == 200
        assert "Cache-Control" not in health.headers


class TestSingleUse:
    """AC 6, 8 (AD-5): the first consume wins, and every later one loses."""

    def test_a_fresh_ticket_is_accepted_and_its_replay_is_refused(self):
        store = TicketStore()
        issued = store.mint()

        assert store.consume(issued) is True  # the acceptance…
        assert store.consume(issued) is False  # …and the rejection it makes non-vacuous

    def test_destruction_happens_at_consume_not_at_a_later_sweep(self):
        """AC 6's second sentence, which the replay assertion alone cannot show.

        A store that *marked* a ticket used and swept it later would refuse the replay above
        identically. Only the resident count can tell the two designs apart.
        """
        store = TicketStore()
        issued = store.mint()
        assert store.resident_count == 1

        store.consume(issued)

        assert store.resident_count == 0

    def test_an_unknown_ticket_is_refused_beside_a_real_one_that_is_accepted(self):
        """AC 8: never minted, and never mistaken for minted."""
        store = TicketStore()
        issued = store.mint()

        assert store.consume("a-ticket-this-store-never-issued") is False
        assert store.consume("") is False
        assert store.consume(issued) is True

    def test_a_refused_consume_leaves_no_ticket_behind(self):
        """A rejected value must not be *stored* by the act of being presented.

        The obvious implementation cannot do this, but a future one that logged presented tickets
        for diagnostics could — and would turn the map into an attacker-controlled unbounded set.
        """
        store = TicketStore()

        store.consume("not-a-ticket")

        assert store.resident_count == 0

    def test_two_tickets_are_independent(self):
        """Consuming one must not invalidate the other — the whole map is not the credential."""
        store = TicketStore()
        first, second = store.mint(), store.mint()

        assert store.consume(first) is True
        assert store.consume(second) is True


class TestTheThirtySecondTtl:
    """AC 7, 8, 9 (AD-5): the deadline, both sides of it, and the pruning behind it."""

    def test_a_ticket_just_under_the_deadline_is_still_accepted(self):
        clock = FakeClock()
        store = TicketStore(clock=clock.time)
        issued = store.mint()

        clock.now = TICKET_TTL_SECONDS - 0.001

        assert store.consume(issued) is True

    def test_a_ticket_exactly_at_the_deadline_is_already_expired(self):
        """The half-open boundary, and the pick is stated in :meth:`TicketStore.consume`.

        ``now < deadline`` — the same operator and the same rounding as
        ``NegativeCache.is_backing_off``, so the two expiring maps in this package round the same
        way rather than each having its own convention.
        """
        clock = FakeClock()
        store = TicketStore(clock=clock.time)
        issued = store.mint()

        clock.now = TICKET_TTL_SECONDS

        assert store.consume(issued) is False

    def test_a_ticket_past_the_deadline_is_refused_beside_a_fresh_one_accepted(self):
        """AC 8's non-vacuity pair for expiry, in one test against one store."""
        clock = FakeClock()
        store = TicketStore(clock=clock.time)
        stale = store.mint()

        clock.now = TICKET_TTL_SECONDS * 2
        fresh = store.mint()

        assert store.consume(stale) is False
        assert store.consume(fresh) is True

    def test_the_ttl_is_measured_from_the_mint_not_from_the_first_consume(self):
        """A ticket minted early and presented late is expired, whatever happened in between.

        Rules out a lazily-started clock — a design where the deadline is set on first touch would
        make a ticket's life unbounded for a client that never presents it.
        """
        clock = FakeClock()
        store = TicketStore(clock=clock.time)
        issued = store.mint()

        clock.now = TICKET_TTL_SECONDS - 1
        store.consume("something-else")  # a touch that must not restart anything
        clock.now = TICKET_TTL_SECONDS + 1

        assert store.consume(issued) is False

    def test_expired_tickets_are_removed_rather_than_merely_ignored(self):
        """AC 9, and this is the assertion the resident-count property exists for.

        Every behavioural test above is identical under "prune" and under "ignore on read". This
        one is not: it never consumes the expired ticket at all, so only an implementation that
        actually deletes it can pass.
        """
        clock = FakeClock()
        store = TicketStore(clock=clock.time)
        store.mint()
        store.mint()
        assert store.resident_count == 2

        clock.now = TICKET_TTL_SECONDS
        # Pruning happens on INSERT, not on read — so the mint is what must collect the two dead
        # tickets, leaving only itself.
        store.mint()

        assert store.resident_count == 1

    def test_pruning_does_not_take_live_tickets_with_it(self):
        """Non-vacuity for the prune: a sweep that emptied the map would pass the test above."""
        clock = FakeClock()
        store = TicketStore(clock=clock.time)
        old = store.mint()

        clock.now = TICKET_TTL_SECONDS / 2
        young = store.mint()
        clock.now = TICKET_TTL_SECONDS
        store.mint()  # triggers the prune: `old` is dead, `young` is not

        assert store.consume(old) is False
        assert store.consume(young) is True

    async def test_the_shipped_ttl_reaches_the_route(self, lifespan_client, clocked):
        """AC 7 + AC 25 end-to-end: the store the lifespan builds carries the 30-second TTL.

        The store unit tests above prove the mechanism; this proves the **wiring** — that the route
        is served by a store constructed with the production default rather than one a test
        supplied. Asserted through the wire on both sides of the deadline, at zero wall clock.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            issued = (await client.get(_PATH)).json()["ticket"]
            store = ticket_store(app)
            assert store is not None

            clocked.now = TICKET_TTL_SECONDS - 0.001
            assert store.consume(issued) is True

            replacement = (await client.get(_PATH)).json()["ticket"]
            # Strictly PAST the deadline, not exactly at it: the exact half-open boundary is the
            # unit tests' property (`test_a_ticket_exactly_at_the_deadline_is_already_expired`);
            # landing there from a float sum would re-prove it by bit-coincidence, and this test
            # is about the wiring, not the boundary.
            clocked.now += TICKET_TTL_SECONDS + 1.0

            assert store.consume(replacement) is False


class TestTheStoreIsBounded:
    """AC 10 (Q2, Brad 2026-08-08): an unauthenticated mint is unbounded-callable."""

    def test_the_resident_count_never_exceeds_the_cap(self):
        clock = FakeClock()
        store = TicketStore(clock=clock.time)

        for _ in range(MAX_TICKETS * 2):
            store.mint()

        assert store.resident_count == MAX_TICKETS

    def test_the_earliest_expiring_ticket_is_the_one_evicted(self):
        """The stated policy, asserted rather than described.

        A small cap so the assertion is about the policy and not about 256 iterations. Every ticket
        carries the same TTL, so earliest-expiring is also oldest-minted — the test therefore also
        pins that eviction is not random and not newest-first.
        """
        clock = FakeClock()
        store = TicketStore(max_tickets=3, clock=clock.time)
        oldest = store.mint()
        clock.now += 1
        middle = store.mint()
        clock.now += 1
        newest = store.mint()

        clock.now += 1
        overflow = store.mint()

        assert store.consume(oldest) is False  # evicted…
        assert store.consume(middle) is True  # …and the survivors prove it was not a purge
        assert store.consume(newest) is True
        assert store.consume(overflow) is True

    def test_pruning_runs_before_eviction_so_dead_tickets_never_cost_a_live_one(self):
        """The ordering inside :meth:`TicketStore.mint`, and it is the reason for the ordering.

        A store that evicted before pruning would drop a live ticket to make room while the map was
        full of expired ones — the exact defect ``NegativeCache.record_failure`` prunes on every
        insert to avoid.
        """
        clock = FakeClock()
        store = TicketStore(max_tickets=2, clock=clock.time)
        store.mint()
        store.mint()

        clock.now = TICKET_TTL_SECONDS
        survivor = store.mint()

        assert store.resident_count == 1
        assert store.consume(survivor) is True


class TestTheInjectedParametersAreGuarded:
    """A mis-injected test parameter fails loudly rather than silently disarming the store."""

    @pytest.mark.parametrize("ttl", [0, -1, -30.0])
    def test_a_non_positive_ttl_is_refused(self, ttl):
        # Every ticket would be born expired, so no handshake could ever succeed — a mechanism
        # that fails closed everywhere and explains nothing.
        with pytest.raises(ValueError, match="ttl must be positive"):
            TicketStore(ttl=ttl)

    @pytest.mark.parametrize("ttl", [float("nan"), float("inf")])
    def test_a_non_finite_ttl_is_refused(self, ttl):
        # Both sail through a bare sign check: nan compares False against everything, so with
        # nan deadlines every consume is refused AND pruning never fires; with inf nothing ever
        # expires. Either way the guard's own docstring claim — a mis-injected parameter fails
        # loudly — would be false, so the constructor refuses them the same way.
        with pytest.raises(ValueError, match="ttl must be positive and finite"):
            TicketStore(ttl=ttl)

    @pytest.mark.parametrize("max_tickets", [0, -1])
    def test_a_cap_below_one_is_refused(self, max_tickets):
        # The eviction would `min()` over an empty map on the very first mint.
        with pytest.raises(ValueError, match="max_tickets must be at least 1"):
            TicketStore(max_tickets=max_tickets)

    def test_the_production_defaults_construct_cleanly(self):
        """Non-vacuity, and it is the claim the lifespan depends on: construction cannot fail."""
        assert TicketStore().resident_count == 0

    def test_a_cap_of_exactly_one_is_legal(self):
        """The boundary the guard admits, asserted so ``< 1`` cannot drift to ``<= 1``."""
        store = TicketStore(max_tickets=1)
        first = store.mint()
        second = store.mint()

        assert store.consume(first) is False
        assert store.consume(second) is True


class TestTheStoreIsCreatedByTheLifespan:
    """AC 11 (AD-10, CM-3): ``build_app()`` keeps its zero-side-effect property."""

    def test_a_constructed_app_has_no_store(self):
        assert ticket_store(build_app()) is None

    async def test_a_started_app_has_one(self, lifespan_client):
        """Non-vacuity for the assertion above: the accessor really does find it after startup."""
        app = build_app()
        async with lifespan_client(app):
            assert isinstance(ticket_store(app), TicketStore)

    async def test_the_store_is_empty_at_startup(self, lifespan_client):
        """CM-3: a restart begins with no tickets, so nothing was restored from anywhere."""
        app = build_app()
        async with lifespan_client(app):
            store = ticket_store(app)
            assert store is not None
            assert store.resident_count == 0

    async def test_nothing_is_written_to_the_data_directory_by_minting(
        self, lifespan_client, tmp_path
    ):
        """AC 11's disk half. The autouse fixture points the data dir at ``tmp_path``.

        **Asserted inside the running lifespan, and that is not incidental**: teardown deletes
        ``companion.json``, so a listing taken after the context exits would show the discovery
        file missing and prove nothing about whether a ticket had been in it.

        The discovery file and the image cache are written by the lifespan and are expected; what
        must not appear is a *third* entry, or a ticket inside the one credential file there is.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = (await client.get(_PATH)).json()["ticket"]

            written = sorted(path.name for path in tmp_path.iterdir())
            # Non-vacuity: the discovery file IS there, so "the ticket is not in it" is a claim
            # about a real file rather than about a missing one.
            assert written == ["companion.json", "image_cache"]
            assert ticket not in (tmp_path / "companion.json").read_text(encoding="utf-8")


class TestTheRouteFailsLoudlyWithoutALifespan:
    """The deliberately unguarded ``AttributeError``, matching c3-4's ``_slot``.

    ``_store``'s docstring declines to model the missing holder, on the ground that a missing store
    can only mean the lifespan never ran. c3-4 shipped the same ruling and its review found the
    defended path had **never executed** — the only test driving it was the ``PUT``, where the
    credential gate answered first. So this drives it directly rather than assuming it.
    """

    @staticmethod
    def _unstarted_client(app):
        """A client into an app whose lifespan never ran, matching c3-4's helper."""
        app.state.bound_port = _PORT
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=f"http://127.0.0.1:{_PORT}"
        )

    async def test_the_app_under_test_really_has_no_store(self):
        """Non-vacuity for the class: the precondition is real, not assumed."""
        assert ticket_store(build_app()) is None

    async def test_a_mint_without_a_store_answers_a_typed_500(self):
        async with self._unstarted_client(build_app()) as client:
            response = await client.get(_PATH)

        assert response.status_code == 500
        assert response.json() == {"reason": "internal_error"}


class TestTheDocstringExamplesRun:
    """AC 27: an ``Example:`` block nobody executes is a comment that looks like a test.

    ``testpaths`` is scoped to ``tests/``, so ``--doctest-modules`` alone never reaches ``src/``.
    c5-1 solved this by folding ``doctest.testmod`` into an ordinary test
    (``test_contracts.py:661-673``); this follows it rather than widening shared pytest config.

    **Scope, stated as a decision (c5-2):** this runs :mod:`src.companion.app.state` only — the
    module this story touched. ``security.py:97,116`` carry ``Example:`` blocks that nothing runs;
    widening to them is a real improvement and deliberately **not** taken here, because a story
    that starts executing another module's untested examples owns whatever they turn out to say.
    Ledgered rather than silently skipped.
    """

    def test_the_state_module_examples_all_pass(self):
        import doctest

        results = doctest.testmod(state, verbose=False)

        # Non-vacuity: `testmod` reports 0 failed for a module with no examples at all, so the
        # attempted count is the half that proves anything ran.
        assert results.attempted > 0
        assert results.failed == 0

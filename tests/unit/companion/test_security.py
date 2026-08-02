"""The localhost-only security envelope: Host validation (c1-5) and the agent credential (c3-4).

The accept/reject matrix is driven twice on purpose: once against the pure predicate (fast,
exhaustive, no ASGI stack) and once end-to-end through a real ``build_app()``, so the guard is
proven to be *wired*, not merely written. Every structural assertion here is paired with a
non-vacuity assertion — c1-4's Greptile catch was a displacement test that passed because nothing
exercised the thing it displaced.

The ``websocket`` and ``lifespan`` branches have no route to drive them yet, so they are called at
the ASGI level directly, with real async ``receive``/``send`` stubs. An unexercised guard is c1-1's
dead-guard lesson; stubs of ``None`` are the c1-4 review's.
"""

import json
import logging

import pytest
from starlette.middleware.cors import CORSMiddleware

from src.companion.app import server
from src.companion.app.errors import UnhandledErrorMiddleware
from src.companion.app.main import build_app
from src.companion.app.security import (
    ALLOWED_HOSTNAMES,
    HostValidationMiddleware,
    agent_token_is_valid,
    allowed_authorities,
    host_is_allowed,
    presented_credential,
)
from tests.unit.companion.conftest import keep_spa_mount_last

_PORT = 54321
"""The port these tests pretend the runner bound. Deliberately not ``server.DEFAULT_PORT``. It
happens to equal the conftest seam's ``_TEST_BOUND_PORT``, but nothing enforces or relies on that:
the wire tests derive their ``base_url`` from whatever the seam actually stamped, and the
pure-function tests carry this value themselves."""

_OTHER_PORT = server.DEFAULT_PORT
"""A different port — and specifically the production default, so a check that quietly fell back to
the constant instead of reading application state fails here."""

_SECURITY_LOGGER = "src.companion.app.security"


# The AC 2 table, verbatim: (Host header, expected verdict, why).
_MATRIX = [
    (f"127.0.0.1:{_PORT}", True, "the two supported spellings"),
    (f"localhost:{_PORT}", True, "the two supported spellings"),
    (f"LOCALHOST:{_PORT}", True, "host names are case-insensitive"),
    (f"  localhost:{_PORT}  ", True, "surrounding whitespace is stripped before matching"),
    ("127.0.0.1", False, "bare host implies port 80, not the bound one"),
    ("localhost", False, "bare host implies port 80, not the bound one"),
    (f"127.0.0.1:{_OTHER_PORT}", False, "a mismatched port is a different server"),
    (f"localhost:{_OTHER_PORT}", False, "a mismatched port is a different server"),
    (f"evil.example.com:{_PORT}", False, "the DNS-rebinding case NFR-01 names"),
    (f"[::1]:{_PORT}", False, "the socket is IPv4-only, so ::1 never reaches us"),
    (f"localhost.:{_PORT}", False, "trailing-dot FQDN — a classic allow-list bypass"),
    (f"127.1:{_PORT}", False, "alternate loopback spelling"),
    (f"127.0.0.001:{_PORT}", False, "alternate loopback spelling"),
    (f"0x7f.1:{_PORT}", False, "alternate loopback spelling"),
    (None, False, "HTTP/1.1 requires Host; absence is not a pass"),
    ("", False, "an empty Host is absence by another name"),
]


class _RecordingApp:
    """A minimal inner ASGI app that records the scopes the middleware let through."""

    def __init__(self):
        self.seen = []

    async def __call__(self, scope, receive, send):
        self.seen.append(scope["type"])


def _scope(scope_type, *, app=None, hosts=(), path="/health"):
    """Build a minimal ASGI *scope_type* scope carrying *hosts* as raw header bytes.

    A ``lifespan`` scope is returned with no ``headers`` and no ``app`` key at all — which is the
    point of the passthrough test: a middleware that read either would raise during startup.
    """
    if scope_type == "lifespan":
        return {"type": "lifespan"}
    return {
        "type": scope_type,
        "app": app,
        "path": path,
        "method": "GET",
        "headers": [(b"host", host.encode("latin-1")) for host in hosts],
    }


async def _drive(middleware, scope):
    """Call *middleware* on *scope* with real async stubs and return everything it sent."""
    sent = []
    incoming = {
        "http": {"type": "http.disconnect"},
        "websocket": {"type": "websocket.connect"},
        "lifespan": {"type": "lifespan.startup"},
    }[scope["type"]]

    async def receive():
        return incoming

    async def send(message):
        sent.append(message)

    await middleware(scope, receive, send)
    return sent


def _app_bound_to(port):
    """Return a real application whose state names *port* as the port the runner bound."""
    app = build_app()
    app.state.bound_port = port
    return app


class TestTheAllowedAuthorities:
    """AC 2: the accepted set is exactly the two loopback authorities at the bound port."""

    def test_the_hostnames_are_the_two_loopback_spellings(self):
        assert ALLOWED_HOSTNAMES == frozenset({"127.0.0.1", "localhost"})

    def test_the_authorities_carry_the_bound_port(self):
        assert allowed_authorities(_PORT) == frozenset({f"127.0.0.1:{_PORT}", f"localhost:{_PORT}"})

    def test_port_80_also_accepts_the_bare_hostnames(self):
        # An HTTP client omits the default port from Host, so on :80 the bare spelling is the
        # *correct* one — the only case where a portless authority is honest.
        assert allowed_authorities(80) == frozenset(
            {"127.0.0.1:80", "localhost:80", "127.0.0.1", "localhost"}
        )

    def test_a_non_default_port_never_accepts_a_bare_hostname(self):
        assert "localhost" not in allowed_authorities(_PORT)


class TestHostIsAllowed:
    """AC 2: the whole accept/reject decision, as a pure function."""

    @pytest.mark.parametrize(
        ("host", "expected", "why"),
        _MATRIX,
        ids=[str(host) for host, _, _ in _MATRIX],
    )
    def test_the_matrix(self, host, expected, why):
        assert host_is_allowed(host, _PORT) is expected, why

    def test_a_bare_hostname_is_accepted_only_on_port_80(self):
        assert host_is_allowed("localhost", 80) is True
        assert host_is_allowed("localhost", _PORT) is False

    def test_no_bound_port_rejects_even_a_perfect_host(self):
        # Decide-once #2: fail closed. A runner that forgot to stamp the port must produce a loud
        # 400 on the first request, not a silently disabled envelope.
        assert host_is_allowed(f"127.0.0.1:{_PORT}", None) is False


class TestTheEnvelopeOnTheWire:
    """AC 3, 4, 5: the same decision, reached through the shipped middleware stack."""

    async def test_a_loopback_host_is_served_normally(self, lifespan_client):
        # Non-vacuity for every rejection test below: the guard cannot be passing by refusing
        # everything, because this returns a real 200 from a real route.
        async with lifespan_client(build_app()) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_a_rebound_hostname_is_a_typed_400(self, lifespan_client):
        async with lifespan_client(
            build_app(), base_url=f"http://evil.example.com:{_PORT}"
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}

    async def test_the_route_never_runs_when_the_host_is_rejected(self, lifespan_client):
        """AC 5: refusal happens *before* the router, not as a late veto on its result."""
        app = build_app()
        reached = []

        @app.get("/_reached")
        async def reached_route():
            reached.append(True)
            return {"ok": True}

        # A decorator can only append, and build_app() ends with the SPA mount at "/" (c2-2),
        # which matches every path. Without this the route above is shadowed: the accepted
        # request would get 200 + index.html and the handler would never run.
        keep_spa_mount_last(app)

        async with lifespan_client(app, base_url=f"http://evil.example.com:{_PORT}") as client:
            rejected = await client.get("/_reached")
        # The same route, addressed legitimately: without this the flag assertion above would hold
        # just as well for a route that never existed.
        async with lifespan_client(app) as client:
            accepted = await client.get("/_reached")

        assert rejected.status_code == 400
        assert accepted.status_code == 200
        assert reached == [True], "the handler ran exactly once — for the accepted request only"

    async def test_the_port_is_read_from_state_not_from_the_default(self, lifespan_client):
        """AC 3: under an ephemeral fallback the bound port is the only one that counts."""
        ephemeral = 61234
        app = _app_bound_to(ephemeral)

        async with lifespan_client(app, base_url=f"http://127.0.0.1:{_OTHER_PORT}") as client:
            named_the_default = await client.get("/health")
        async with lifespan_client(_app_bound_to(ephemeral)) as client:
            named_the_real_port = await client.get("/health")

        assert named_the_default.status_code == 400
        assert named_the_real_port.status_code == 200

    async def test_no_bound_port_rejects_rather_than_skips(self, lifespan_client):
        """AC 4: fail closed — a runner that forgot to stamp the port must go loudly wrong."""
        async with lifespan_client(
            build_app(), bound_port=None, base_url=f"http://127.0.0.1:{_PORT}"
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}

    async def test_on_port_80_a_bare_hostname_is_accepted_on_the_wire(self, lifespan_client):
        """The one case where a portless authority is honest, proven through the shipped stack.

        httpx omits the default port from ``Host`` for an ``http://`` URL, exactly as a browser
        would — so this drives the ``port == 80`` branch of ``allowed_authorities`` through the
        middleware rather than only through the pure functions.
        """
        async with lifespan_client(_app_bound_to(80), base_url="http://localhost") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_on_any_other_port_the_same_bare_hostname_is_refused(self, lifespan_client):
        # Non-vacuity for the port-80 acceptance above: the same bare Host against a non-80 bound
        # port is refused, so the acceptance is the special case doing the work, not a loose match.
        async with lifespan_client(build_app(), base_url="http://localhost") as client:
            response = await client.get("/health")

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}


class TestDuplicateHostHeaders:
    """AC 7: two Host headers are ambiguous by construction, so they are refused.

    Driven at the ASGI level because httpx collapses a duplicated Host before it reaches the app —
    and both values here are individually *valid*, so nothing but the duplication can be causing
    the refusal.
    """

    async def test_two_host_headers_are_rejected_even_when_both_are_allowed(self):
        inner = _RecordingApp()
        app = _app_bound_to(_PORT)
        scope = _scope("http", app=app, hosts=[f"127.0.0.1:{_PORT}", f"127.0.0.1:{_PORT}"])

        sent = await _drive(HostValidationMiddleware(inner), scope)

        assert sent[0]["status"] == 400
        assert json.loads(sent[1]["body"]) == {"reason": "invalid_request"}
        assert inner.seen == []

    async def test_one_of_those_same_headers_alone_is_accepted(self):
        # Non-vacuity: proves the refusal above is about the duplication, not the value.
        inner = _RecordingApp()
        app = _app_bound_to(_PORT)
        scope = _scope("http", app=app, hosts=[f"127.0.0.1:{_PORT}"])

        sent = await _drive(HostValidationMiddleware(inner), scope)

        assert sent == []
        assert inner.seen == ["http"]

    async def test_no_host_header_at_all_is_rejected(self):
        inner = _RecordingApp()
        scope = _scope("http", app=_app_bound_to(_PORT), hosts=[])

        sent = await _drive(HostValidationMiddleware(inner), scope)

        assert sent[0]["status"] == 400
        assert inner.seen == []


class TestNonHttpScopes:
    """AC 6: websocket shares the code path; everything else passes through untouched."""

    async def test_a_disallowed_websocket_is_closed_before_it_is_accepted(self, caplog):
        """Close-before-accept is the ASGI-legal denial; uvicorn renders it as an HTTP 403."""
        inner = _RecordingApp()
        scope = _scope(
            "websocket", app=_app_bound_to(_PORT), hosts=[f"evil.example.com:{_PORT}"], path="/ws"
        )

        with caplog.at_level(logging.WARNING, logger=_SECURITY_LOGGER):
            sent = await _drive(HostValidationMiddleware(inner), scope)

        assert sent == [{"type": "websocket.close", "code": 1008}]
        assert inner.seen == [], "a denied connection must never reach a route expecting to accept"
        # AC 13 claims one WARNING per rejection with no scope-type carve-out, so the ws denial
        # must log exactly like the http one — this pins the claim on the second scope type.
        records = [record for record in caplog.records if record.name == _SECURITY_LOGGER]
        assert len(records) == 1
        assert records[0].levelname == "WARNING"
        assert "evil.example.com" in records[0].getMessage()

    async def test_an_allowed_websocket_reaches_the_inner_app(self):
        # Non-vacuity for the close above, and the property c5-3 inherits: the upgrade is validated
        # by *this* middleware rather than by a duplicate check of its own.
        inner = _RecordingApp()
        scope = _scope(
            "websocket", app=_app_bound_to(_PORT), hosts=[f"127.0.0.1:{_PORT}"], path="/ws"
        )

        sent = await _drive(HostValidationMiddleware(inner), scope)

        assert sent == []
        assert inner.seen == ["websocket"]

    async def test_a_lifespan_scope_passes_straight_through(self):
        # The scope built here has no "headers" and no "app" key at all, so a middleware that
        # reached for either would raise here — during startup, where a failure is least legible.
        inner = _RecordingApp()

        sent = await _drive(HostValidationMiddleware(inner), _scope("lifespan"))

        assert sent == []
        assert inner.seen == ["lifespan"]


class TestMiddlewareOrder:
    """AC 8: the security middleware is installed *inside* the error middleware."""

    def test_the_stack_is_exactly_error_then_security(self):
        # user_middleware[0] is the most recently added, i.e. the outermost. Pinning the whole
        # list rather than index 0 makes a future insertion between the two visible.
        assert [m.cls for m in build_app().user_middleware] == [
            UnhandledErrorMiddleware,
            HostValidationMiddleware,
        ]


class TestCorsIsDeliberatelyAbsent:
    """AC 9: "restricted to the app's own origin" is implemented by installing no CORS.

    AD-13 serves the SPA from this same backend, so every legitimate request is same-origin and
    needs no grant. Three assertions rather than a comment, so a later story that wants
    ``CORSMiddleware`` has to come back to this ruling first.
    """

    async def test_a_preflight_is_answered_without_an_allow_origin_header(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.options(
                "/health",
                headers={
                    "Origin": "http://evil.example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

        assert "access-control-allow-origin" not in response.headers
        # Still the typed refusal c1-4 shipped, with the RFC-mandated Allow intact — installing
        # CORSMiddleware would have replaced this with an untyped text/plain body (AD-16).
        assert response.status_code == 405
        assert response.json() == {"reason": "invalid_request"}
        assert "GET" in response.headers["allow"]

    async def test_a_simple_cross_origin_request_gets_no_allow_origin_header(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get("/health", headers={"Origin": "http://evil.example.com"})

        # 200, because CORS is a browser-side rule: the request is issued, the *response* is what
        # the browser refuses to hand over. Omitting the header is the refusal.
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    def test_no_cors_middleware_is_installed(self):
        assert not any(m.cls is CORSMiddleware for m in build_app().user_middleware)


class TestRejectionLogging:
    """AC 13: one WARNING per rejection, carrying a truncated copy of the offending value."""

    async def test_a_rejection_logs_exactly_one_warning_naming_the_host(
        self, lifespan_client, caplog
    ):
        with caplog.at_level(logging.WARNING, logger=_SECURITY_LOGGER):
            async with lifespan_client(
                build_app(), base_url=f"http://evil.example.com:{_PORT}"
            ) as client:
                await client.get("/health")

        records = [record for record in caplog.records if record.name == _SECURITY_LOGGER]
        assert len(records) == 1
        assert records[0].levelname == "WARNING"
        assert "evil.example.com" in records[0].getMessage()

    async def test_an_accepted_request_logs_nothing(self, lifespan_client, caplog):
        # Non-vacuity for the count above: the WARNING is the rejection, not a per-request record.
        with caplog.at_level(logging.WARNING, logger=_SECURITY_LOGGER):
            async with lifespan_client(build_app()) as client:
                await client.get("/health")

        assert [record for record in caplog.records if record.name == _SECURITY_LOGGER] == []

    async def test_the_logged_host_is_truncated(self, lifespan_client, caplog):
        """The Host is attacker-controlled input on its way into a log file."""
        long_host = "e" * 500 + f".example.com:{_PORT}"

        with caplog.at_level(logging.WARNING, logger=_SECURITY_LOGGER):
            async with lifespan_client(build_app(), headers={"Host": long_host}) as client:
                await client.get("/health")

        message = next(r for r in caplog.records if r.name == _SECURITY_LOGGER).getMessage()
        assert "e" * 50 in message, "the offending value is still identifiable"
        assert long_host not in message, "…but not echoed in full"
        # The cap is 100 characters of the value; asserting on the run of 'e's pins the truncation
        # itself rather than the total length, which the surrounding prose would dominate.
        assert "e" * 101 not in message


# --------------------------------------------------------------------------------------------
# Story c3-4: the agent credential — the SECOND check in this envelope, and the first per-route
# one. Its matrix is driven here as a pure function, exactly as `host_is_allowed`'s is above;
# `test_routes_active_deck.py` drives it end-to-end through a real app, because a correct
# comparison wired to nothing would pass every assertion in this section.
# --------------------------------------------------------------------------------------------


class TestPresentedCredential:
    """Parsing the ``Authorization`` header, before any comparison happens.

    Kept separate from the comparison on purpose: "what did they send" and "is it right" are
    different questions, and collapsing them is how a lax parser hides behind a strict compare.
    """

    @pytest.mark.parametrize(
        ("header", "credential"),
        [
            ("Bearer abc", "abc"),
            # RFC 9110 §11.1: the auth-scheme is case-insensitive.
            ("bearer abc", "abc"),
            ("BEARER abc", "abc"),
            ("BeArEr abc", "abc"),
            # Surrounding whitespace on the credential is not part of it.
            ("Bearer   abc  ", "abc"),
        ],
    )
    def test_a_well_formed_header_yields_its_credential(self, header, credential):
        assert presented_credential(header) == credential

    @pytest.mark.parametrize(
        ("case", "header"),
        [
            ("absent entirely", None),
            ("empty", ""),
            ("a bare token with no scheme", "abc"),
            ("a different scheme", "Basic abc"),
            ("a scheme that merely starts with bearer", "BearerToken abc"),
            ("the scheme alone", "Bearer"),
            ("the scheme and a space", "Bearer "),
            ("the scheme and only whitespace", "Bearer     "),
        ],
    )
    def test_anything_else_reduces_to_no_credential(self, case, header):
        # All of these collapse to None so the comparison site has ONE branch to get right.
        # `BearerToken` is the one worth staring at: a `startswith("Bearer")` parser accepts it.
        assert presented_credential(header) is None, case


class TestAgentTokenIsValid:
    """The credential comparison — the one place in this codebase where a bug is a security hole.

    Mirrors :class:`TestHostIsAllowed` above, and the mirroring is the point rather than a stylistic
    echo: both refuse when *either* side is missing, and c3-4 matched this function to that shipped
    precedent deliberately.
    """

    def test_the_matching_case(self):
        # The paired positive, first: without it every assertion below is satisfied by a function
        # that returns False unconditionally.
        assert agent_token_is_valid("a-minted-token", "a-minted-token") is True

    @pytest.mark.parametrize(
        ("case", "presented", "expected"),
        [
            # THE FAIL-OPEN TRAP, in every spelling. `agent_token(app)` is None before the
            # lifespan runs and an absent header is naturally None, so `presented == expected`
            # would authenticate every request against an unstarted app.
            ("both absent", None, None),
            ("no credential presented", None, "minted"),
            ("nothing minted", "presented", None),
            # Empty is absent: "" == "" is True, so a None-only guard leaves the same hole
            # wearing a different spelling.
            ("both empty", "", ""),
            ("empty presented", "", "minted"),
            ("empty expected", "presented", ""),
        ],
    )
    def test_it_fails_closed_when_either_side_is_missing(self, case, presented, expected):
        assert agent_token_is_valid(presented, expected) is False, case

    @pytest.mark.parametrize(
        ("case", "presented", "expected"),
        [
            # Not a prefix, suffix or substring match. A comparison doing anything other than full
            # equality fails here rather than in production.
            ("a prefix of the real token", "mint", "minted"),
            ("a superstring of the real token", "minted-and-more", "minted"),
            ("the real token is a superstring", "minted", "minted-and-more"),
            ("an interior substring", "inte", "minted"),
            ("differing in one character", "minteD", "minted"),
            ("differing only in trailing whitespace", "minted ", "minted"),
        ],
    )
    def test_it_is_full_equality_and_nothing_looser(self, case, presented, expected):
        assert agent_token_is_valid(presented, expected) is False, case

    @pytest.mark.parametrize(
        ("case", "presented", "expected", "verdict"),
        [
            # `secrets.compare_digest` accepts `str` only when BOTH sides are ASCII-only and
            # raises TypeError otherwise. Header values decode as latin-1, so this input is
            # trivially reachable — and under a str comparison it becomes a caller-controlled
            # `500 internal_error`. Comparing bytes makes it an ordinary verdict.
            ("a non-ASCII credential against a real token", "schlüssel", "minted", False),
            ("a non-ASCII credential against itself", "schlüssel", "schlüssel", True),
            ("an emoji", "🔑", "minted", False),
            ("a non-ASCII token", "minted", "schlüssel", False),
        ],
    )
    def test_non_ascii_is_a_verdict_and_never_an_exception(
        self, case, presented, expected, verdict
    ):
        assert agent_token_is_valid(presented, expected) is verdict, case

"""Story c3-4: the active deck — readable by the glass, settable by the agent (FR-07, AD-16).

Four firsts land in this route pair, and the tests are organised around them rather than around
the two verbs: the first state the backend **owns** (rather than projects from ``cards.db``), the
first non-``GET``, the first request **body**, and the first **authenticated** endpoint.

**The riskiest thing here is not the happy path, it is the rejection path.**
:func:`src.companion.app.main.agent_token` returns ``None`` before the lifespan runs, and a caller
can present no credential — also naturally ``None``. Compared naively those are equal, and the app
would authenticate every request against an unstarted process. :class:`TestFailsClosedWithNoToken`
drives a real ``build_app()`` whose lifespan never ran, because a unit test of the comparison
function alone would not have caught a route wired to the wrong comparison.

Everything is asserted **through the wire**. The slot is never read directly — a test that
inspected ``app.state.active_deck`` would pass with the routes deleted.
"""

import json
import logging
from pathlib import Path

import httpx
import pytest
from pydantic import TypeAdapter

from src.companion.app.main import agent_token, build_app
from src.companion.app.state import active_deck, connection_registry
from src.companion.contracts import _MAX_ENVELOPE_BYTES, ActiveDeckChangedEvent, AgentEvent
from tests.unit.companion.conftest import FakeConnection, open_socket

_PATH = "/api/active-deck"

# Every source-scanning guard below resolves against this rather than the CWD, matching the
# committed-schema fixture's style further down: run from any directory, the guards must find the
# real modules or fail on their own non-vacuity asserts — not fail by scanning nothing.
# Deliberately distinguishable from each other and from every fixture id in the suite (c3-1's R3
# finding: nothing tied a nested value to its source because every fixture was identical on the
# asserted fields). A set-then-read sequence proves nothing if the id is the same string
# everywhere, so each id below names the test that uses it.
_FIRST_DECK = "deck-alpha-first-set"
_SECOND_DECK = "deck-beta-overwrites-alpha"
_UNKNOWN_DECK = "deck-that-is-definitely-not-in-any-database-00000"


def _bearer(token):
    """Return the ``Authorization`` header presenting *token*."""
    return {"Authorization": f"Bearer {token}"}


class TestTheReadRequiresNothing:
    """AC 1, AC 2: ``GET`` answers 200 in both states, with no credential and no session."""

    async def test_a_cold_open_reports_no_active_deck(self, lifespan_client):
        # `null` IS the answer, not a 404 and not a different shape: the resource always exists
        # and its value may be "no deck" (Q3).
        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH)

        assert response.status_code == 200
        assert response.json() == {"deck_id": None}

    async def test_the_read_needs_no_credential(self, lifespan_client):
        """AC 2 asserted **positively**: a client presenting nothing but ``Host`` gets 200.

        Paired with :class:`TestTheWriteNeedsTheCredential` in the same module (AC 25): if the
        credential dependency were accidentally attached to the ``GET`` as well, this goes red
        while every rejection test stays green — so "rejects everything" cannot pass the suite.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            # Belt and braces: prove the app really does hold a credential that this call is
            # simply not presenting, so the 200 means "not required" rather than "none exists".
            assert agent_token(app) is not None
            response = await client.get(_PATH)

        assert response.status_code == 200

    async def test_the_read_touches_no_database(self, lifespan_client, monkeypatch):
        """AD-16: no ``DbSession``, so no database URL is ever resolved on this path.

        Driven by pointing the database at a path that does not exist. Any route taking a session
        answers ``503 database_not_initialized`` under this condition (that is c1-6's contract);
        this one must answer 200, which is only possible if it never asked.
        """
        monkeypatch.setenv("CARDS_DATABASE_URL", "sqlite+aiosqlite:///./no/such/directory/x.db")

        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH)

        assert response.status_code == 200
        assert response.json() == {"deck_id": None}


class TestTheWriteNeedsTheCredential:
    """AC 4, AC 6: a valid credential stores the id; everything else is refused."""

    async def test_a_valid_credential_stores_the_deck_and_echoes_it(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(agent_token(app))
            )

        assert response.status_code == 200
        # Answers 200 echoing the stored value rather than 204 (Q3 part 4). The write's shape
        # DIVERGED from the read's at c6-2 (Q1, Brad 2026-08-09): the receipt adds the delivered
        # client count so the agent-side verb can distinguish "switched, and a tab is watching"
        # from "switched, and nobody is looking". Zero here because no client is registered.
        assert response.json() == {"deck_id": _FIRST_DECK, "clients": 0}

    async def test_the_set_deck_is_then_readable(self, lifespan_client):
        """AC 4 as a **sequence through the wire** — never by reading the holder."""
        app = build_app()
        async with lifespan_client(app) as client:
            await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(agent_token(app))
            )
            response = await client.get(_PATH)

        assert response.status_code == 200
        assert response.json() == {"deck_id": _FIRST_DECK}

    async def test_setting_twice_replaces_rather_than_accumulates(self, lifespan_client):
        # PUT is idempotent per resource, not additive: the second write wins outright. The two
        # ids are distinguishable, so a route that kept the first would fail here rather than
        # coincidentally agree.
        app = build_app()
        async with lifespan_client(app) as client:
            headers = _bearer(agent_token(app))
            await client.put(_PATH, json={"deck_id": _FIRST_DECK}, headers=headers)
            await client.put(_PATH, json={"deck_id": _SECOND_DECK}, headers=headers)
            response = await client.get(_PATH)

        assert response.json() == {"deck_id": _SECOND_DECK}

    @pytest.mark.parametrize(
        ("case", "headers"),
        [
            # The four cases AC 6 names. Each is a genuinely different code path through
            # `presented_credential`: absent, present-but-empty, well-formed-but-wrong, and a
            # PREFIX of the real one — the last exists so that a comparison doing anything other
            # than full equality (a `startswith`, a truncating compare) fails here rather than in
            # production.
            ("no header at all", {}),
            ("an empty header value", {"Authorization": ""}),
            ("a wrong token", {"Authorization": "Bearer completely-the-wrong-credential"}),
            ("a prefix of the real token", None),
        ],
    )
    async def test_a_bad_credential_is_refused_and_the_slot_does_not_move(
        self, lifespan_client, case, headers
    ):
        app = build_app()
        async with lifespan_client(app) as client:
            token = agent_token(app)
            # Seed a known value through the ACCEPTED path first, so "did not move" is a real
            # claim about a real value rather than about the None the slot starts at (AC 25).
            seeded = await client.put(_PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(token))
            assert seeded.status_code == 200, f"the accepted path broke, so {case} proves nothing"

            attempt = headers if headers is not None else _bearer(token[:16])
            response = await client.put(_PATH, json={"deck_id": _SECOND_DECK}, headers=attempt)
            after = await client.get(_PATH)

        assert response.status_code == 403, case
        # Asserted on the exact body, not just the status: 403 with the wrong token would be a
        # broken contract for c6-1, which branches on the reason.
        assert response.json() == {"reason": "forbidden"}, case
        assert after.json() == {"deck_id": _FIRST_DECK}, f"{case} moved the active deck"

    async def test_a_non_ascii_credential_is_refused_rather_than_crashing(self, lifespan_client):
        """Landmine 11: ``secrets.compare_digest`` raises ``TypeError`` on a non-ASCII ``str``.

        Under a ``str`` comparison this input produces ``500 internal_error`` — a caller-controlled
        value reported as a backend bug, and trivially reachable since header values decode as
        latin-1. Comparing bytes makes it an ordinary non-match.

        Sent as raw **bytes**, which is not incidental: httpx refuses to encode a non-ASCII header
        *string* (``UnicodeEncodeError`` from its own ascii encode, measured 2026-08-01), so a test
        written the obvious way never reaches the server and proves nothing. A hostile client has
        no such scruples.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.put(
                _PATH,
                json={"deck_id": _SECOND_DECK},
                headers={b"authorization": "Bearer schlüssel".encode("latin-1")},
            )

        assert response.status_code == 403
        assert response.json() == {"reason": "forbidden"}

    @pytest.mark.parametrize(
        ("case", "value"),
        [
            ("no scheme, bare token", "{token}"),
            ("the wrong scheme", "Basic {token}"),
            ("the scheme with no credential", "Bearer"),
            ("the scheme and only whitespace", "Bearer   "),
        ],
    )
    async def test_a_malformed_authorization_header_is_refused(self, lifespan_client, case, value):
        # Each of these carries the REAL token (or no token at all) in a spelling the parser must
        # reject, so a lax parser — one that split on whitespace and took the last field, say —
        # would authenticate them. Paired with the accepted case above, which uses the correct
        # spelling of the same token.
        app = build_app()
        async with lifespan_client(app) as client:
            header = value.replace("{token}", agent_token(app) or "")
            response = await client.put(
                _PATH, json={"deck_id": _SECOND_DECK}, headers={"Authorization": header}
            )

        assert response.status_code == 403, case
        assert response.json() == {"reason": "forbidden"}, case

    async def test_the_scheme_is_matched_case_insensitively(self, lifespan_client):
        # RFC 9110 §11.1: the auth-scheme is case-insensitive. This is the paired POSITIVE of the
        # wrong-scheme rejection above — without it, `presented_credential` could reject every
        # scheme and the four cases above would still pass.
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.put(
                _PATH,
                json={"deck_id": _FIRST_DECK},
                headers={"Authorization": f"bEaReR {agent_token(app)}"},
            )

        assert response.status_code == 200


class TestFailsClosedWithNoToken:
    """AC 7: an app whose lifespan never ran rejects **every** write (landmine 11).

    Deliberately bypasses the ``lifespan_client`` seam and drives ``ASGITransport`` directly —
    entering the lifespan is precisely what these tests must not do. ``bound_port`` is stamped by
    hand so the ``Host`` envelope admits the request; without it every response would be the
    envelope's own ``400`` and the credential check would never be reached.
    """

    @staticmethod
    def _unstarted_client(app):
        app.state.bound_port = 54321
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:54321"
        )

    async def test_the_app_under_test_really_has_no_token(self):
        """Non-vacuity for the whole class: the precondition is real, not assumed."""
        assert agent_token(build_app()) is None

    @pytest.mark.parametrize(
        ("case", "headers"),
        [
            # BOTH sides of the fail-open trap. The first presents nothing, so a naive
            # `presented == expected` compares None to None and returns True. The second presents
            # the literal string a careless `str(agent_token(app))` would produce.
            ("presenting no credential", {}),
            ("presenting the literal 'None'", {"Authorization": "Bearer None"}),
            ("presenting an empty bearer", {"Authorization": "Bearer "}),
        ],
    )
    async def test_every_write_is_refused(self, case, headers):
        app = build_app()
        async with self._unstarted_client(app) as client:
            response = await client.put(_PATH, json={"deck_id": _FIRST_DECK}, headers=headers)

        assert response.status_code == 403, case
        assert response.json() == {"reason": "forbidden"}, case

    async def test_the_credential_free_read_answers_the_documented_500(self):
        """The GET has no credential gate to refuse it first, so it reaches ``_slot`` — whose
        docstring spends fourteen lines defending "let the missing slot's ``AttributeError``
        reach the middleware as ``500 internal_error``". This is that ruling's one measured
        execution (c3-4 review): before it, the class only ever drove the PUT, where the 403
        outranks the slot and the defended path never ran.
        """
        app = build_app()
        async with self._unstarted_client(app) as client:
            response = await client.get(_PATH)

        assert response.status_code == 500
        assert response.json() == {"reason": "internal_error"}


class TestARestartForgets:
    """AC 3: the state dies with the process (FR-07, CM-3)."""

    async def test_a_fresh_app_reports_none_after_a_deck_was_set(self, lifespan_client):
        """Proved through the real seam across two lifespans, not by unit-testing the holder.

        The whole point is that the value cannot survive a restart, and a test of
        ``ActiveDeckSlot`` alone would still pass if the lifespan started caching the id on disk.
        """
        first = build_app()
        async with lifespan_client(first) as client:
            await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(agent_token(first))
            )
            confirmed = await client.get(_PATH)
        # Non-vacuity: the deck really was set in the first process, so the None below is
        # forgetting rather than never-having-known.
        assert confirmed.json() == {"deck_id": _FIRST_DECK}

        second = build_app()
        async with lifespan_client(second) as client:
            response = await client.get(_PATH)

        assert response.status_code == 200
        assert response.json() == {"deck_id": None}

    async def test_a_restart_also_invalidates_the_credential(self, lifespan_client):
        # The neighbouring half of the same property, and the reason c6-1 owes a retry-once: the
        # token is minted fresh per process, so a tool holding the old one is refused rather than
        # silently writing to a companion that has forgotten it.
        first = build_app()
        async with lifespan_client(first) as client:
            stale = agent_token(first)
            assert (await client.get(_PATH)).status_code == 200

        second = build_app()
        async with lifespan_client(second) as client:
            assert agent_token(second) != stale
            response = await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(stale)
            )

        assert response.status_code == 403
        assert response.json() == {"reason": "forbidden"}


class TestNoDeckExistenceCheck:
    """AC 5: the backend stores what it is given (AD-16, epic AC :1658)."""

    async def test_an_unknown_deck_id_is_accepted_and_read_back(self, lifespan_client):
        """A *positive* test of an absence, paired with a plausible id so it is not vacuous.

        The id used is one no database could hold. If the route ever grew a lookup, this goes red
        with ``deck_not_found`` or ``503`` — which is exactly the regression AD-16's ruling exists
        to prevent, because deck-existence validation belongs to the MCP tool that can report it
        to the agent meaningfully.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            stored = await client.put(
                _PATH, json={"deck_id": _UNKNOWN_DECK}, headers=_bearer(agent_token(app))
            )
            read_back = await client.get(_PATH)

        assert stored.status_code == 200
        assert read_back.json() == {"deck_id": _UNKNOWN_DECK}

    async def test_it_is_not_passing_because_the_route_accepts_nothing(self, lifespan_client):
        """AC 25's pairing: the same route, a well-formed id, and a body it genuinely refuses.

        Without this, "an unknown id is accepted" would also pass on a route that accepted every
        possible input including nonsense — which would not be the ruling, it would be an absent
        validator.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            headers = _bearer(agent_token(app))
            accepted = await client.put(_PATH, json={"deck_id": _FIRST_DECK}, headers=headers)
            refused = await client.put(_PATH, json={"deck_id": ""}, headers=headers)

        assert accepted.status_code == 200
        assert refused.status_code == 400
        assert refused.json() == {"reason": "invalid_request"}


class TestTheMethodSemantics:
    """AC 8: measured, not assumed. ``spa.py`` predicted this case for a route not yet written."""

    async def test_an_unsupported_method_answers_405_naming_both_supported_ones(
        self, lifespan_client
    ):
        """The measurement ``spa.py``'s docstring claims, on the first path with two methods.

        ``_SpaMount`` returns ``Match.NONE`` for a reserved prefix so the *router* answers, which
        is what produces a 405 with the RFC-mandated ``Allow`` rather than the mount's 404.

        **The Allow header is this app's, not Starlette's.** Starlette keeps only the first
        partially-matching route (``routing.py:738``) and builds the header from that route alone,
        so this measured ``Allow: GET`` before ``errors.supported_methods`` was added — omitting
        the ``PUT`` that is the whole point of the resource. Every path before c3-4 had exactly one
        method, so the defect was unreachable until now.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.post(_PATH, json={"deck_id": _FIRST_DECK})

        assert response.status_code == 405
        assert {m.strip() for m in response.headers["allow"].split(",")} == {"GET", "PUT"}
        # `http_exception_handler`'s 4xx arm: a framework miss has no token of its own.
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_single_method_path_still_reports_only_its_own_method(self, lifespan_client):
        # The pairing (AC 25): the union must be a real union, not "every method the app knows".
        # A `supported_methods` that returned the whole route table would pass the test above.
        async with lifespan_client(build_app()) as client:
            response = await client.post("/health")

        assert response.status_code == 405
        assert {m.strip() for m in response.headers["allow"].split(",")} == {"GET"}

    async def test_the_405_precedes_the_credential_check(self, lifespan_client):
        # A wrong method with a VALID credential is still 405: routing resolves before
        # dependencies, so the method answer cannot be bought with a token.
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.post(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(agent_token(app))
            )

        assert response.status_code == 405
        # The full answer, not just the status: this authenticated wrong-method request is the
        # closest thing in the suite to c6-1's real retry path, and the class exists because
        # `Allow` was silently wrong until this story (c3-4 review).
        assert {m.strip() for m in response.headers["allow"].split(",")} == {"GET", "PUT"}
        assert response.json() == {"reason": "invalid_request"}


class TestAMalformedBody:
    """AC 9: the shipped ``validation_error_handler`` answers, with no new code on this route."""

    @pytest.mark.parametrize(
        ("case", "kwargs"),
        [
            ("not JSON at all", {"content": b"this is not json"}),
            ("JSON that is not an object", {"json": [1, 2, 3]}),
            ("an object missing the id field", {"json": {}}),
            ("the id field of the wrong type", {"json": {"deck_id": 7}}),
            ("an explicit null id — there is no clearing verb (Q3)", {"json": {"deck_id": None}}),
            ("the empty id Q3's min_length refuses", {"json": {"deck_id": ""}}),
            (
                "a whitespace-only id — blank is empty, min_length counts characters not content",
                {"json": {"deck_id": " \t "}},
            ),
            ("an id past the length bound", {"json": {"deck_id": "x" * 257}}),
            (
                "an unknown extra field — 'the deck id and nothing else' is enforced, not prose",
                {"json": {"deck_id": _FIRST_DECK, "persist": True}},
            ),
        ],
    )
    async def test_it_answers_400_invalid_request(self, lifespan_client, case, kwargs):
        app = build_app()
        async with lifespan_client(app) as client:
            headers = dict(_bearer(agent_token(app)))
            if "content" in kwargs:
                headers["content-type"] = "application/json"
            response = await client.put(_PATH, headers=headers, **kwargs)

        assert response.status_code == 400, case
        assert response.json() == {"reason": "invalid_request"}, case

    async def test_a_malformed_body_does_not_move_the_active_deck(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            headers = _bearer(agent_token(app))
            await client.put(_PATH, json={"deck_id": _FIRST_DECK}, headers=headers)
            await client.put(_PATH, json={"deck_id": ""}, headers=headers)
            response = await client.get(_PATH)

        assert response.json() == {"deck_id": _FIRST_DECK}

    async def test_the_id_at_the_length_bound_is_accepted(self, lifespan_client):
        # The paired positive for the over-length rejection: an off-by-one that refused the
        # boundary value would otherwise look identical in the suite.
        app = build_app()
        boundary = "x" * 256
        async with lifespan_client(app) as client:
            response = await client.put(
                _PATH, json={"deck_id": boundary}, headers=_bearer(agent_token(app))
            )

        assert response.status_code == 200
        assert response.json() == {"deck_id": boundary, "clients": 0}

    async def test_a_malformed_body_without_a_credential_is_still_forbidden(self, lifespan_client):
        """Ordering, stated as a contract rather than left to be discovered.

        FastAPI reads and parses the body **before** solving dependencies (measured against
        0.140.0: body at ``routing.py:423-448``, ``solve_dependencies`` at ``:473``), so a body
        that fails to parse raises ``RequestValidationError`` before the credential is ever
        checked. A body that parses cleanly then meets the dependency. Both are pinned so a
        framework upgrade that reorders them is visible.

        **DISPOSITIONED AT c5-5 AS A SNAPSHOT, THEN EXTENDED RATHER THAN REVISED** (Q3, Brad
        2026-08-08). ``deferred-work.md`` flagged this pin as the thing c5-5's pre-parse body cap
        would redden, and asked the story to decide whether it recorded a *contract* the feature
        owes or a *snapshot* of measured framework behaviour. Ruled: **snapshot** — nothing
        designed this order, FastAPI did.

        What the ruling predicted, and what actually happened, differ, so both are recorded here.
        The prediction was that ``BodyCapMiddleware`` would redden this test and the pin would need
        revising through review. **It did not go red** (measured 2026-08-08, full suite). The cap
        only reorders *oversized* bodies, and both bodies below are a few dozen bytes — so the two
        assertions above continued to hold untouched, and the disposition cost an **addition**
        rather than a correction. The third assertion is that addition: the total ordering now has
        a cheaper rung above both, and it is pinned here beside them so the whole order is legible
        in one place rather than split across two files.
        """
        oversized = b'{"deck_id": "' + b"x" * (_MAX_ENVELOPE_BYTES + 1) + b'"}'
        async with lifespan_client(build_app()) as client:
            unparseable = await client.put(
                _PATH, content=b"{{{", headers={"content-type": "application/json"}
            )
            parseable_but_invalid = await client.put(_PATH, json={"deck_id": _FIRST_DECK})
            over_cap = await client.put(
                _PATH, content=oversized, headers={"content-type": "application/json"}
            )

        # Body first: the parse failure outranks the missing credential.
        assert unparseable.status_code == 400
        # Dependency second: a well-formed body reaches the credential check and is refused.
        assert parseable_but_invalid.status_code == 403
        # Size FIRST OF ALL, as of c5-5: the byte cap runs in middleware, above both the parser and
        # the dependency solver, so an oversized body is refused without a credential and without
        # being parsed. That is the correct fail-cheap order — the process must not buffer
        # megabytes on behalf of a caller it was going to refuse — and it is the one arm of this
        # ordering that IS a designed contract rather than a measured framework detail.
        assert over_cap.status_code == 413
        assert over_cap.json() == {"reason": "payload_too_large"}


class TestNotShadowedBySpa:
    """AC 14: asserted on status **and body** (c3-1 review R1)."""

    async def test_the_read_runs_the_endpoint_rather_than_serving_the_index(self, lifespan_client):
        # R1's finding: a content-type-only assertion passed with the router DELETED, because
        # /api is in `_RESERVED_SEED` and answers JSON either way. Only the body distinguishes
        # "the route ran" from "the reserved prefix produced a typed 404".
        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH)

        assert response.status_code == 200
        assert response.json() == {"deck_id": None}

    async def test_an_unrouted_sibling_path_is_refused_rather_than_falling_back(
        self, lifespan_client
    ):
        """The non-vacuity pair: what the test above would see if the router were missing."""
        async with lifespan_client(build_app()) as client:
            response = await client.get("/api/active-decks")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    async def test_the_spa_mount_is_still_the_last_route(self):
        """The mechanism itself: the new router was registered above ``install_spa``."""
        assert getattr(build_app().router.routes[-1], "name", None) == "spa"


class TestTheCommittedSchema:
    """The new path, the new operations and the new shapes, in the artifact the UI compiles from.

    The whole-artifact path and component pins live in ``test_committed_schema.py`` (c3-4 Q5).
    What is asserted here is this route's own contract.
    """

    @pytest.fixture(scope="class")
    def schema(self):
        path = Path(__file__).resolve().parents[3] / "ui" / "src" / "api" / "openapi.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_the_path_carries_exactly_the_two_operations(self, schema):
        assert set(schema["paths"][_PATH]) == {"get", "put"}

    def test_the_write_declares_its_own_token_and_the_read_does_not(self, schema):
        put_responses = schema["paths"][_PATH]["put"]["responses"]
        get_responses = schema["paths"][_PATH]["get"]["responses"]

        # Non-vacuity before the absence check (AC 25): a wrong key would make "403 absent" pass
        # by finding nothing at all.
        assert put_responses and get_responses
        assert "200" in put_responses and "200" in get_responses

        # A route declares only what it uniquely produces (c3-1 AC 6).
        assert "403" in put_responses
        assert "403" not in get_responses

    def test_neither_operation_documents_the_auto_422(self, schema):
        # The first route in the app with a request body, so the first real test of
        # `without_auto_validation_schema` against a body rather than a path parameter.
        assert "422" not in schema["paths"][_PATH]["put"]["responses"]
        assert "422" not in schema["paths"][_PATH]["get"]["responses"]

    def test_the_request_body_is_required_and_refers_to_the_request_model(self, schema):
        # The FIRST requestBody in the whole document (AC 16).
        body = schema["paths"][_PATH]["put"]["requestBody"]

        assert body["required"] is True
        ref = body["content"]["application/json"]["schema"]["$ref"]
        assert ref == "#/components/schemas/ActiveDeckRequest"

    def test_the_operation_declares_no_security_scheme(self, schema):
        # Q4: the credential is read from `request.headers` inside the dependency, so the header's
        # NAME never reaches the browser-facing document. A FastAPI security class would have put
        # a `security` block here and a `securitySchemes` component alongside.
        assert "security" not in schema["paths"][_PATH]["put"]

    def test_the_two_operations_answer_two_shapes_and_why(self, schema):
        """c6-2 Q1 (Brad 2026-08-09) **supersedes c3-4's Q3 one-shape ruling for the write.**

        c3-4 answered the ``PUT`` with :class:`~src.companion.contracts.ActiveDeck` so that "one
        shape serves the read, the write and the change notification". Two of those three still
        hold — the ``GET`` and (by field name and nullability, never by validation) the broadcast
        payload. The write diverged because the *agent* asks a question the browser never does:
        **did anyone see it?** The delivered count already existed —
        ``broadcast_active_deck_changed`` returns it and this route used to discard it — and the
        alternative was an MCP tool that could never distinguish "switched" from "switched, with
        no tab open".

        The read is untouched, which is the half that matters for AD-5: the SPA's shape did not
        move, and the SPA never calls the token-gated write.
        """
        get_ref = schema["paths"][_PATH]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        put_ref = schema["paths"][_PATH]["put"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]

        assert get_ref == "#/components/schemas/ActiveDeck"
        assert put_ref == "#/components/schemas/ActiveDeckSetReceipt"

    def test_the_receipt_is_the_read_shape_plus_a_non_negative_count(self, schema):
        """The divergence is **purely additive**, and the ``ge=0`` is the leaf client's net.

        ``deck_id`` keeps the read model's exact declaration — same name, same nullability — so the
        one thing that changed between the two operations is the added count. (There is still no
        clearing verb, so the write cannot in fact answer ``null`` today; the shape says ``null``
        for the same reason :class:`~src.companion.contracts.ActiveDeck` does, and a reader that
        handles the read handles this.)

        ``minimum: 0`` is c6-1's lesson made structural: ``{"clients": -1}`` sails through a
        hand-rolled ``body["clients"] >= 1`` read and is quietly reported as *nobody was listening*.
        That bound is what makes the client parse it as a ``backend_error`` instead — and the
        receipt is closed (``additionalProperties: false``) so a stray field is a parse failure
        rather than a silently ignored one.
        """
        receipt = schema["components"]["schemas"]["ActiveDeckSetReceipt"]
        read_model = schema["components"]["schemas"]["ActiveDeck"]

        assert set(receipt["required"]) == {"deck_id", "clients"}
        assert receipt["properties"]["deck_id"] == read_model["properties"]["deck_id"]
        assert {"type": "null"} in receipt["properties"]["deck_id"]["anyOf"]
        assert receipt["properties"]["clients"]["type"] == "integer"
        assert receipt["properties"]["clients"]["minimum"] == 0
        assert receipt["additionalProperties"] is False

    def test_the_response_model_admits_null_and_the_request_model_does_not(self, schema):
        response_field = schema["components"]["schemas"]["ActiveDeck"]["properties"]["deck_id"]
        request_field = schema["components"]["schemas"]["ActiveDeckRequest"]["properties"][
            "deck_id"
        ]

        # `null` is a value of the response shape — that IS the "none" state (Q3 part 1).
        assert {"type": "null"} in response_field["anyOf"]
        # …and is NOT accepted on the way in: there is deliberately no clearing verb (Q3 part 3).
        assert "anyOf" not in request_field
        assert request_field["type"] == "string"
        assert request_field["minLength"] == 1

    def test_the_request_model_forbids_unknown_fields_on_the_wire(self, schema):
        # "The deck id and nothing else" is enforced, and the artifact says so: a types.d.ts
        # consumer sees a closed object, not one that silently drops extras (c3-4 review, Brad).
        request_model = schema["components"]["schemas"]["ActiveDeckRequest"]
        assert request_model["additionalProperties"] is False


class TestNothingIsLoggedThatShouldNotBe:
    """AC 10's log half, stated as a positive requirement rather than only as an absence."""

    async def test_a_rejection_names_the_path_and_the_fact_and_nothing_else(
        self, lifespan_client, caplog
    ):
        app = build_app()
        with caplog.at_level(logging.DEBUG):
            async with lifespan_client(app) as client:
                token = agent_token(app)
                await client.put(
                    _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer("wrong-" + token)
                )

        rejections = [r for r in caplog.records if "Refusing" in r.getMessage()]

        # Non-vacuity: a rejection really was logged, so the assertions below are about a real
        # record rather than an empty list.
        assert rejections, "the refusal was not logged at all"
        message = rejections[0].getMessage()
        # Diagnostic enough to be worth writing: which route, and whether anything was presented.
        assert _PATH in message
        assert "credential" in message
        # …and not one byte more.
        assert token not in message
        assert "wrong-" + token not in message


async def _mint_ticket(client):
    """Mint one WebSocket ticket over the shipped ``GET /api/session``, and return it."""
    response = await client.get("/api/session")
    assert response.status_code == 200, "the mint must work, or the socket tests are vacuous"
    return response.json()["ticket"]


class TestThePutBroadcasts:
    """AC 16-19 (c5-4): the store is followed by exactly one ``active_deck_changed`` fan-out.

    **This is the seam the comment at ``:132`` predicted, now asserted rather than described.** The
    fan-out's own behaviour is proven in ``test_ws.py``; what belongs here is the *wiring* — that
    the route calls it, on the success path only, with the id it stored, and that nothing the
    broadcast does can change what the ``PUT`` answers.
    """

    async def test_a_successful_put_broadcasts_the_stored_id(self, lifespan_client):
        """AC 16: through the real router, to a registered client, parsed as a union member."""
        app = build_app()
        async with lifespan_client(app) as client:
            connection = FakeConnection()
            connection_registry(app).add(connection)

            response = await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(agent_token(app))
            )

        assert response.status_code == 200
        assert len(connection.sent) == 1, "exactly one event per set — not zero, not two"
        event = TypeAdapter(AgentEvent).validate_json(connection.sent[0])
        assert isinstance(event, ActiveDeckChangedEvent)
        assert event.kind == "active_deck_changed"
        assert event.payload.deck_id == _FIRST_DECK

    async def test_the_broadcast_id_comes_from_the_slot_not_the_body(self, lifespan_client):
        """AC 16: the notification and the response body must never be able to disagree.

        Reading ``body.deck_id`` would pass every other test in this class and diverge silently the
        day :meth:`ActiveDeckSlot.set` gains normalisation — so the property is asserted directly,
        by making the slot store something the body never said and checking both answers follow.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            connection = FakeConnection()
            connection_registry(app).add(connection)
            slot = active_deck(app)
            slot.set = lambda deck_id: setattr(slot, "_deck_id", "rewritten-by-the-slot")

            response = await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(agent_token(app))
            )

        assert response.json() == {"deck_id": "rewritten-by-the-slot", "clients": 1}
        event = TypeAdapter(AgentEvent).validate_json(connection.sent[0])
        assert event.payload.deck_id == "rewritten-by-the-slot", (
            "the broadcast read the request body; it must read what was stored"
        )

    async def test_it_fires_again_on_a_same_id_rewrite(self, lifespan_client):
        """AC 17 (Q10, ``contracts.py:890-894``): no only-if-changed suppression.

        Suppressing the duplicate is a read-modify-write, which is exactly what the slot's no-lock
        design forbids. A duplicate signal costs one idempotent refetch; the alternative costs a
        lock.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            connection = FakeConnection()
            connection_registry(app).add(connection)
            headers = _bearer(agent_token(app))

            await client.put(_PATH, json={"deck_id": _FIRST_DECK}, headers=headers)
            await client.put(_PATH, json={"deck_id": _FIRST_DECK}, headers=headers)

        assert len(connection.sent) == 2, "the same-id rewrite was suppressed (Q10 says it is not)"
        adapter = TypeAdapter(AgentEvent)
        first, second = (adapter.validate_json(text) for text in connection.sent)
        assert first.payload.deck_id == second.payload.deck_id == _FIRST_DECK
        assert first.id != second.id, "two distinct events, so a client can tell them apart"

    async def test_the_receipt_reports_the_count_the_fan_out_returned(self, lifespan_client):
        """c6-2 Q1: the number the route used to discard is the number it now answers with.

        Two registered clients rather than one, so a receipt hard-coding ``1`` — or reporting
        ``connected_count`` instead of the fan-out's return — is distinguishable from one that
        actually threads the value through. The paired zero row lives in
        :meth:`TestTheWriteNeedsTheCredential.test_a_valid_credential_stores_the_deck_and_echoes_it`,
        so this cannot pass by always answering the registry's size either.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            registry = connection_registry(app)
            first, second = FakeConnection(), FakeConnection()
            registry.add(first)
            registry.add(second)

            response = await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(agent_token(app))
            )

        assert response.json() == {"deck_id": _FIRST_DECK, "clients": 2}
        assert len(first.sent) == len(second.sent) == 1, "both really received it"

    async def test_a_refused_credential_broadcasts_nothing(self, lifespan_client):
        """AC 18: the call sits after the store, on the success path only."""
        app = build_app()
        async with lifespan_client(app) as client:
            connection = FakeConnection()
            connection_registry(app).add(connection)

            refused = await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer("not-the-token")
            )
            assert refused.status_code == 403
            assert connection.sent == []

            # Paired acceptance from the same call site, so this cannot pass by never broadcasting.
            await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(agent_token(app))
            )

        assert len(connection.sent) == 1

    async def test_a_rejected_body_broadcasts_nothing(self, lifespan_client):
        """AC 18: a body that never reaches the handler cannot reach the fan-out either.

        ``400``, not ``422`` — AD-16 superseded the auto-422 and ``test_committed_schema.py``
        asserts FastAPI's 422 components are stripped, so the typed ``invalid_request`` answer is
        the shipped one.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            connection = FakeConnection()
            connection_registry(app).add(connection)

            response = await client.put(
                _PATH, json={"deck_id": "   "}, headers=_bearer(agent_token(app))
            )

        assert response.status_code == 400
        assert connection.sent == []

    async def test_a_dead_client_does_not_cost_the_put_its_200(self, lifespan_client):
        """AC 18's headline, driven through the **shipped** helper rather than a planted fault.

        This is the realistic failure — a tab that went away between the registry snapshot and the
        write — and the requirement is that the mutation's own result is untouched by it.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            registry = connection_registry(app)
            registry.add(FakeConnection(fails=True))

            response = await client.put(
                _PATH, json={"deck_id": _FIRST_DECK}, headers=_bearer(agent_token(app))
            )
            stored = await client.get(_PATH)

        assert response.status_code == 200
        # `clients: 0` and a `200` together: the count is *delivered*, so the tab that could not be
        # written to is absent from it — and its absence still costs the mutation nothing.
        assert response.json() == {"deck_id": _FIRST_DECK, "clients": 0}
        assert stored.json() == {"deck_id": _FIRST_DECK}
        assert registry.connected_count == 0, "and the dead client was dropped on the way past"


class TestTwoTabsOnePut:
    """AC 9 (FR-06, UX-DR37): the multi-tab requirement, on the wire, through the real machinery.

    **The one route-driven proof in this story, and the reason** ``conftest.open_socket``
    **exists.**
    Everything else about the fan-out is proven against fakes, which is cheaper and sharper — but
    "every connected client receives it" is a claim about *concurrently open* sockets, and
    ``drive_handshake`` structurally cannot hold two: it runs one handshake to completion. So this
    drives two real handshakes through ``build_app()``, keeps both parked in their drain loops,
    issues one ordinary authenticated ``PUT`` over the ordinary HTTP seam, and reads what each
    socket was handed. Nothing synchronises the tabs — each receives the same broadcast
    independently, which is UX-DR37's rule.

    The real-socket version of this — an actual port, an actual process — is **c5-8's**, not this
    story's (AD-10: exactly one integration-marked socket test in the whole feature). It shipped on
    2026-08-09 at ``tests/integration/companion/test_live_backend.py``, with one deliberate
    narrowing worth knowing: it drives **one** real socket, not two, because what it exists to
    prove is the process boundary rather than the fan-out arity. The two-tab claim stays here,
    where it can be made without booting anything.
    """

    async def test_both_tabs_receive_the_same_event(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            async with (
                open_socket(app, ticket=await _mint_ticket(client)) as first,
                open_socket(app, ticket=await _mint_ticket(client)) as second,
            ):
                assert connection_registry(app).connected_count == 2  # non-vacuity

                response = await client.put(
                    _PATH, json={"deck_id": _SECOND_DECK}, headers=_bearer(agent_token(app))
                )

                assert response.status_code == 200
                assert len(first.frames) == 1, "the first tab was not reached"
                assert len(second.frames) == 1, "the second tab was not reached"
                assert first.frames == second.frames, "byte-identical, from one serialisation"

                event = TypeAdapter(AgentEvent).validate_json(first.frames[0])
                assert isinstance(event, ActiveDeckChangedEvent)
                assert event.payload.deck_id == _SECOND_DECK

    async def test_a_tab_that_closed_stops_receiving_and_the_other_does_not(self, lifespan_client):
        """AC 8, verbatim from the epic: removed without error, and others are unaffected.

        Driven as the sequence a user performs — two tabs, close one, set another deck — rather
        than by reaching into the registry, so it fails if the handler's ``finally`` stops running.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            headers = _bearer(agent_token(app))
            async with open_socket(app, ticket=await _mint_ticket(client)) as survivor:
                async with open_socket(app, ticket=await _mint_ticket(client)) as closing:
                    await client.put(_PATH, json={"deck_id": _FIRST_DECK}, headers=headers)
                    assert len(closing.frames) == 1  # non-vacuity: it really was reachable

                assert connection_registry(app).connected_count == 1

                await client.put(_PATH, json={"deck_id": _SECOND_DECK}, headers=headers)

                assert len(closing.frames) == 1, "the closed tab received a second event"
                assert len(survivor.frames) == 2, "the surviving tab missed the second event"

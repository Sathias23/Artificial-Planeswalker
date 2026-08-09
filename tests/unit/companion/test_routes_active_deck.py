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

import ast
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
_REPO_ROOT = Path(__file__).resolve().parents[3]


def code_identifiers(path):
    """Return every identifier a module's **code** mentions, ignoring prose.

    AST-only, for the reason ``test_import_boundary.py`` states about its own guards: a scan of
    raw source is keyed on syntax rather than on meaning, and the first thing it catches is the
    docstring explaining why the banned thing is absent. That is not hypothetical — the raw-text
    version of :meth:`TestNoDeckExistenceCheck.test_the_route_module_imports_no_data_layer` failed
    on this module's own paragraph explaining why it does **not** take a ``DbSession`` (measured
    2026-08-01, and the same shape as c3-3's headline finding).

    String *constants* are excluded, so a docstring can discuss ``DbSession`` freely while an
    actual reference fails. That is the right way round: the claim is about what the code does.

    Args:
        path: A repo-relative path to a Python module.

    Returns:
        A set containing every imported module and name, every ``Name`` and every attribute
        accessed anywhere in the module.
    """
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.update(alias.name.split("."))
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # A relative `from . import x` has module=None; guard it rather than `or ""`, which
            # would seed the empty string into every identifier set (c3-4 review).
            if node.module:
                found.update(node.module.split("."))
                found.add(node.module)
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.arg):
            found.add(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.add(node.name)
    return found


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
        # Answers 200 echoing the stored value rather than 204 (Q3 part 4): one shape serves the
        # read, the write, and (since c5-4) the change notification it broadcasts.
        assert response.json() == {"deck_id": _FIRST_DECK}

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

    def test_the_route_module_reaches_for_no_data_layer(self):
        """Explicitly absent from the diff: any repository, session or ``src.data`` reference.

        Asserted rather than trusted: ``test_import_boundary.py`` bans *write* paths, so a
        read-only ``DeckRepository`` here would pass every existing guard while quietly making this
        route the database-dependent thing AD-16 says it must not be.

        Keyed on the **code**, not the text — the module's docstring discusses ``DbSession`` at
        length, explaining why this route does not take one, and a raw-text scan fails on that
        paragraph (which is how this test was first written, and how it first failed).
        """
        identifiers = code_identifiers(_REPO_ROOT / "src/companion/app/routes/active_deck.py")

        # Non-vacuity, and specific enough to prove the walk reached real code rather than an
        # empty parse: these are things the module genuinely does reference.
        assert {"set_active_deck", "read_active_deck", "ActiveDeckRequest"} <= identifiers

        # Deliberately NOT the bare names `data` or `deps`: code_identifiers collects every Name
        # and attribute, so a future legitimate local (`data = response.model_dump()`) would red a
        # database-layering guard for a change with no database in it — the exact noise-trap the
        # MCP-side test below argues against. The layer is caught by its unambiguous names, and
        # the dotted `src.data` (which code_identifiers records whole) covers the package import
        # the bare word was standing in for.
        banned = {"DbSession", "AsyncSession", "get_session", "sqlalchemy", "src.data"}
        for name in identifiers:
            assert "Repository" not in name, f"the active-deck route reached for {name}"
        assert not (banned & identifiers), (
            f"the active-deck route reached for {banned & identifiers}"
        )


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
        assert response.json() == {"deck_id": boundary}

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

    def test_both_operations_answer_the_same_shape(self, schema):
        """Q3's one-shape ruling, in the artifact: no union, no ``X | None`` response model."""
        get_ref = schema["paths"][_PATH]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        put_ref = schema["paths"][_PATH]["put"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]

        assert get_ref == put_ref == "#/components/schemas/ActiveDeck"

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


class TestTheBoundariesThisRouteMustNotCross:
    """AC 11, AC 12, AC 13: what this story deliberately did **not** open."""

    def test_the_mcp_server_holds_no_active_deck_state(self):
        """AC 12 (CM-3): the active deck lives in the backend, and nowhere else.

        Scans the MCP package rather than trusting AD-3's import guard alone. That guard proves
        ``src/mcp_server`` cannot *import* ``src.companion.app``; it does not prove the MCP side
        has not grown a slot of its own, which is the thing CM-3 actually forbids and the thing
        project-context D5 ("no per-session server state") exists to prevent.

        **Keyed on state-holding, deliberately not on the phrase "active deck".** c6-2 adds a tool
        called ``companion_set_active_deck``, which is *supposed* to exist — it calls this endpoint
        and keeps nothing. A guard banning that name would go red at c6-2 for a correct change, get
        deleted in irritation, and take the real property with it. What is banned is a **module-
        level binding** that could hold the value across calls, and any reference to the backend's
        slot.
        """
        sources = sorted((_REPO_ROOT / "src" / "mcp_server").rglob("*.py"))

        # Non-vacuity: the package was found and really contains code.
        assert sources, "no MCP server sources found — the scan would be vacuous"

        offenders = []
        for path in sources:
            identifiers = code_identifiers(path)
            for banned in ("ActiveDeckSlot", "active_deck", "ActiveDeck"):
                if banned in identifiers:
                    offenders.append(f"{path}: references {banned}")
            # Module-level mutable state named for the deck being displayed — the shape CM-3
            # forbids, whatever it is spelled.
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                targets = []
                if isinstance(node, ast.Assign):
                    targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    targets = [node.target.id]
                for target in targets:
                    if "active" in target.lower() and "deck" in target.lower():
                        offenders.append(f"{path}: module-level {target}")

        assert not offenders, f"the MCP server grew active-deck state: {offenders}"

    def test_the_state_module_names_no_agent_credential(self):
        """AC 13 (AD-5): the agent credential is absent from the module holding display state.

        **NARROWED AT c5-2 (AC 14), and the narrowing is the interesting part.** c3-4 wrote this
        guard forward-looking, banning ``ticket`` alongside the agent-token names *"so c5-2
        inherits a rule rather than a coincidence"* — on the assumption that the ticket store would
        land in ``security.py``. c5-2's Q3 ruled the other way (``security.py``'s one proven
        structural property is that it *stores nothing*, and a compare-and-set cannot be split from
        its storage), so ``state.py`` legitimately grew a :class:`TicketStore` — and this guard
        reddened on the noun ``ticket``, which is the opposite of what it exists to catch.

        ``ticket`` therefore leaves the ban list; **every agent-token-specific name stays**, and
        ``token`` staying is what keeps ``discovery.mint_token``'s bare sibling out. Note the ban
        is on *identifiers*, not prose: ``code_identifiers`` is AST-only, so the paragraphs above
        may discuss the agent token freely while a reference to one fails.

        **What this now proves, read against the code rather than against its own comment:** that
        no name in ``state.py``'s syntax tree is spelled like the agent credential. **What it
        cannot see:** the credential reached indirectly — ``getattr(app.state, "agent_" + "token")``
        or an import aliased to a different name. That residual hole is why AC 15's sibling below
        exists, and why it asserts the *call graph* rather than a second vocabulary.
        """
        identifiers = code_identifiers(_REPO_ROOT / "src/companion/app/state.py")

        # Non-vacuity, both holders: a scan that found neither would satisfy any ban list.
        assert {"ActiveDeckSlot", "active_deck", "deck_id"} <= identifiers
        assert {"TicketStore", "ticket_store", "mint", "consume"} <= identifiers
        banned = {"token", "agent_token", "credential", "secret", "mint_token"}
        assert not (banned & identifiers), f"the state module reached for {banned & identifiers}"

    def test_the_ticket_store_shares_no_code_path_with_the_agent_token(self):
        """AC 15 (AD-5): the two credentials share no code path, asserted structurally.

        **This replaces the coverage AC 14 gave up, and it is strictly stronger than the noun-ban
        it replaces.** Banning the word ``ticket`` never proved anything about the agent token; it
        proved that ``state.py`` had not yet grown a ticket store. What AD-5 actually requires is
        that the ticket and the agent token *"share no storage and no code path"* — so this walks
        the module that holds the ticket store and asserts the four ways a code path could be
        shared, each of which is a real construct in this codebase rather than a hypothetical:

        * importing :mod:`src.companion.discovery` (whose ``mint_token`` mints the agent token);
        * reading the ``agent_token`` accessor or ``app.state.agent_token``;
        * calling ``presented_credential`` / ``agent_token_is_valid`` / ``require_agent_token``;
        * reaching the ``Bearer`` channel via ``AgentToken`` or ``_AUTHORIZATION_HEADER``.

        **What it compares:** the set of identifiers ``state.py``'s AST mentions against that
        vocabulary. **What it cannot see:** a shared path built entirely out of names it does not
        know — the same indirection hole its sibling has — and anything the *route* module does,
        which is why ``test_routes_session.py`` re-asserts the property over the wire on a real
        response and real captured logs.
        """
        identifiers = code_identifiers(_REPO_ROOT / "src/companion/app/state.py")

        # Non-vacuity, and a real one: the walk must be finding the ticket store's OWN code, or
        # every absence below is satisfied by scanning an empty set.
        assert {"TicketStore", "secrets", "token_urlsafe", "MAX_TICKETS"} <= identifiers

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
            f"the ticket store shares a code path with the agent token: "
            f"{shared_paths & identifiers} (AD-5)"
        )

    def test_the_credential_check_reads_one_accessor_and_stores_nothing(self):
        """AC 13's other half: the check is stateless.

        A credential check that cached its verdict — a set of seen tokens, a memo — would be the
        shared storage AD-5 forbids, and would also outlive the restart that is supposed to
        invalidate the token. Asserted structurally: the module has no module-level mutable
        container at all, so there is nowhere for a cache to live.
        """
        path = _REPO_ROOT / "src/companion/app/security.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))

        assert "agent_token_is_valid" in code_identifiers(path)  # non-vacuity

        # Probed with planted violations, per the C2 standing agreement (c3-4 review): the first
        # version banned only literal Dict/List/Set on ast.Assign, and all four plants below
        # sailed through it — `_seen = set()` and `_memo = defaultdict(list)` are ast.Call, an
        # annotated `_cache: dict[str, str] = {}` is ast.AnnAssign (which has `target`, not
        # `targets`), and `_tokens = frozenset() | {x}` is a BinOp. Hence: both assignment node
        # shapes, and the *family* — any call whose callee name is a mutable-container
        # constructor — rather than an enumeration of literal node types alone.
        mutable_constructors = {"set", "dict", "list", "defaultdict", "OrderedDict", "deque"}

        def is_mutable_container(value):
            literal_containers = (
                ast.Dict | ast.List | ast.Set | ast.ListComp | ast.SetComp | ast.DictComp
            )
            if isinstance(value, literal_containers):
                return True
            if isinstance(value, ast.Call):
                callee = value.func
                name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", None)
                return name in mutable_constructors
            if isinstance(value, ast.BinOp):
                return is_mutable_container(value.left) or is_mutable_container(value.right)
            return False

        for node in tree.body:
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            else:
                continue
            for name in names:
                # frozenset/str/int constants are fine — a mutable container is not.
                assert not is_mutable_container(node.value), (
                    f"security.py holds mutable module-level state in {name}; "
                    "a credential check must store nothing (AD-5)"
                )


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

        assert response.json() == {"deck_id": "rewritten-by-the-slot"}
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
        assert response.json() == {"deck_id": _FIRST_DECK}
        assert stored.json() == {"deck_id": _FIRST_DECK}
        assert registry.connected_count == 0, "and the dead client was dropped on the way past"

    async def test_the_broadcast_helpers_are_total(self):
        """AC 18's structural half, and the honest statement of **where** the containment lives.

        The route adds one awaited call and no ``try`` (Q4: *"the route adds literally one awaited
        call"*), so AC 18's "a fault inside the broadcast never affects the 200" holds only because
        the two helpers **cannot raise** — every call they make is inside a ``try`` whose handler
        catches ``Exception``. That is the property this pins.

        **What it compares:** that every ``Call`` node in either helper's body sits inside a
        ``Try`` — *or* is a call to the other helper, which this same test proves total. That
        exemption is the composition rule made explicit: ``broadcast_active_deck_changed`` ends in
        a bare ``return await broadcast(...)``, and wrapping a call that cannot raise would be
        ceremony. **What it cannot see:** an exception raised by an ``except`` handler itself (a
        logging call that blows up), which is the residual every catch-all in this package shares.
        """
        totals = {"broadcast", "broadcast_active_deck_changed"}
        tree = ast.parse((_REPO_ROOT / "src/companion/app/ws.py").read_text(encoding="utf-8"))
        helpers = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name in totals
        }

        assert set(helpers) == totals  # non-vacuity
        for name, helper in helpers.items():
            guarded = {
                id(node)
                for statement in helper.body
                if isinstance(statement, ast.Try)
                for node in ast.walk(statement)
                if isinstance(node, ast.Call)
            }
            unguarded = [
                ast.unparse(node)
                for node in ast.walk(helper)
                if isinstance(node, ast.Call)
                and id(node) not in guarded
                and not (isinstance(node.func, ast.Name) and node.func.id in totals)
            ]
            assert unguarded == [], f"{name} can raise at {unguarded}; the route has no net"
            handlers = [
                handler
                for statement in helper.body
                if isinstance(statement, ast.Try)
                for handler in statement.handlers
            ]
            assert handlers, f"{name} has no except clause"
            assert all(
                isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
                for handler in handlers
            ), f"{name} catches something narrower than Exception"

    async def test_the_insertion_point_comment_was_replaced_by_the_call(self):
        """AC 19: the marked line predicted a call; the call is what stands there now.

        **What it compares:** the route module's identifiers for the awaited broadcast, and its
        source for the comment that reserved the line. **What it cannot see:** whether the call is
        positioned *after* the store — which the behavioural tests above cover by observing the
        stored id arrive on the wire.
        """
        route_source = _REPO_ROOT / "src/companion/app/routes/active_deck.py"

        assert "broadcast_active_deck_changed" in code_identifiers(route_source)
        assert "c5-4 adds its active_deck_changed broadcast on the line below" not in (
            route_source.read_text(encoding="utf-8")
        )


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

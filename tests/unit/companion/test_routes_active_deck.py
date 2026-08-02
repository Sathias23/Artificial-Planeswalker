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

from src.companion.app.main import agent_token, build_app

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
        # read, the write, and c5-4's change notification.
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
        """
        async with lifespan_client(build_app()) as client:
            unparseable = await client.put(
                _PATH, content=b"{{{", headers={"content-type": "application/json"}
            )
            parseable_but_invalid = await client.put(_PATH, json={"deck_id": _FIRST_DECK})

        # Body first: the parse failure outranks the missing credential.
        assert unparseable.status_code == 400
        # Dependency second: a well-formed body reaches the credential check and is refused.
        assert parseable_but_invalid.status_code == 403


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

    def test_the_active_deck_slot_holds_no_credential(self):
        """AC 13 (AD-5): the two credentials share no storage.

        c5-2's WebSocket ticket does not exist yet, so the assertable half is that the display
        state and the credential live in different objects and the state module's code knows
        nothing about tokens. Stated so c5-2 inherits a rule rather than a coincidence.
        """
        identifiers = code_identifiers(_REPO_ROOT / "src/companion/app/state.py")

        assert {"ActiveDeckSlot", "active_deck", "deck_id"} <= identifiers  # non-vacuity
        banned = {"token", "agent_token", "credential", "secret", "mint_token", "ticket"}
        assert not (banned & identifiers), f"the slot reached for {banned & identifiers}"

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

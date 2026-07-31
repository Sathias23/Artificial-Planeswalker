"""Story c1-4: every non-2xx response carries one token from a closed set (AD-16).

The response assertions here deliberately go through a **real** ``build_app()`` instance with
test-local routes attached in the test itself (AC 11) rather than through a hand-built app or a
mocked handler: middleware order, handler registration and JSON serialisation are exactly the
things that break, and only the shipped stack exercises all three. No boom route ships in ``src/``
(Gotcha 8) — a permanent unauthenticated 500 generator on a localhost port is not a debug aid.
"""

import logging
from typing import get_args

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import ClientDisconnect

from src.companion.app.errors import (
    STATUS_BY_REASON,
    CompanionError,
    UnhandledErrorMiddleware,
    error_responses,
)
from src.companion.app.main import build_app
from src.companion.contracts import ErrorReason, ErrorResponse
from tests.unit.companion.conftest import keep_spa_mount_last

_ERRORS_MODULE = "src.companion.app.errors"

_REASONS = get_args(ErrorReason)

_EXPECTED_STATUS = {
    "deck_not_found": 404,
    "card_not_found": 404,
    "database_not_initialized": 503,
    "database_unavailable": 503,
    "invalid_request": 400,
    "payload_too_large": 413,
    "internal_error": 500,
}


_OBJECT_SHAPE_KEYS = frozenset(
    {"properties", "additionalProperties", "patternProperties", "allOf", "anyOf", "oneOf", "not"}
)
"""Keys that give a schema a shape of its own, rather than annotating one it already has."""


def _is_ref_rooted(schema: dict) -> bool:
    """Is *schema* a declared response model, rather than a hand-built inline shape?

    AD-16's ban is on the **envelope** — a ``{"status": "ok", "deck": {...}}`` assembled in a
    handler, which appears in the OpenAPI document as an inline object with ``properties``. What it
    permits is any body generated from a ``response_model``, and there are two rooted shapes that
    can be: a component reference, and an **array of** one (c3-1's ``GET /api/decks`` returns
    ``list[DeckSummary]``, an unwrapped bare array — AD-16's own example of an unwrapped body).

    Keyed on the family — "the schema bottoms out in a ``$ref``" — rather than on a list of the
    two spellings seen so far, so a future ``list[list[X]]`` is admitted and an array *of* an
    inline envelope is still refused.

    Args:
        schema: The ``content["application/json"]["schema"]`` subtree of one response.

    Returns:
        ``True`` if the shape is rooted in a component reference.
    """
    if set(schema) == {"$ref"}:
        return True
    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        # An array that ALSO carries an object-shaping key is a hand-assembled shape wearing an
        # array's clothes, and a plain "is it an array? recurse into items" check waves it through
        # (review, 2026-07-31). Keyed on the shaping FAMILY rather than on an allowlist of
        # permitted siblings, because FastAPI legitimately adds annotation keys of its own —
        # `title` on every generated array response, and `description` wherever a docstring
        # reaches it. Those describe the shape; the keys below CHANGE it.
        if _OBJECT_SHAPE_KEYS & set(schema):
            return False
        return _is_ref_rooted(schema["items"])
    return False


def _app_with_test_routes():
    """Return a real ``build_app()`` instance with the routes these tests need attached.

    The routes are added **here** rather than shipped in ``src/`` (Gotcha 8): a debug route that
    raises on demand would be a permanent unauthenticated 500 generator on a localhost port.
    Starlette builds the middleware stack lazily on the first request, so a route decorated after
    ``add_middleware`` — which is what this is — is served normally.

    Returns:
        A constructed application; enter its lifespan before driving it.
    """
    app = build_app()

    @app.get("/_raise/{reason}")
    async def raise_companion_error(reason: str):
        raise CompanionError(reason)

    @app.get("/_typed/{n}")
    async def typed_param(n: int):
        return {"n": n}

    @app.get("/_http/{status}")
    async def raise_http_exception(status: int):
        raise HTTPException(status_code=status)

    @app.get("/_boom")
    async def boom():
        raise RuntimeError("kaboom")

    # A decorator can only append, and build_app() ends with the SPA mount at "/" (c2-2), which
    # matches every path. Without this the four routes above are shadowed and answer 200 with
    # index.html instead of running.
    return keep_spa_mount_last(app)


class TestReasonTokenContract:
    """AC 1 + AC 2: the token set is closed at seven and the body carries nothing else."""

    def test_the_token_set_is_exactly_these_seven(self):
        # Adding a token is a deliberate act with a failing test attached (AD-16's own extension
        # rule). `internal_error` was added under that rule by the c1-4 review (Brad, 2026-07-25),
        # and `card_not_found` by c3-2 under the C2 retro's R1 — which tightened the rule: the
        # token and the UI state it drives land in the SAME COMMIT, because `internal_error`
        # shipping alone had already cost c2-9 a repair AC.
        #
        # THE SET IS NOW CLOSED AT SEVEN WITH NOTHING PLANNED. An eighth is not forbidden, but it
        # is a decision, not a chore: it reddens this test, `STATUS_BY_REASON`'s pin below,
        # `ui/src/api/schema.test.ts`'s union and `states.ts`'s `satisfies` clause — and the last
        # two fail under `npm run typecheck` only, never under `npm test`.
        assert set(_REASONS) == {
            "deck_not_found",
            "card_not_found",
            "database_not_initialized",
            "database_unavailable",
            "invalid_request",
            "payload_too_large",
            "internal_error",
        }

    @pytest.mark.parametrize("reason", _REASONS)
    def test_every_token_is_accepted(self, reason):
        assert ErrorResponse(reason=reason).reason == reason

    def test_an_unknown_token_is_rejected(self):
        with pytest.raises(ValidationError):
            ErrorResponse(reason="kaboom")

    def test_the_serialised_body_carries_the_token_and_nothing_else(self):
        # No message, no detail, no status (Decide-once #3): the copy lives in the UI and a prose
        # field would echo caller input back over a port any page can reach.
        assert ErrorResponse(reason="deck_not_found").model_dump() == {"reason": "deck_not_found"}
        assert set(ErrorResponse(reason="deck_not_found").model_dump().keys()) == {"reason"}


class TestStatusMapping:
    """AC 3: the status is derived from the token, in exactly one place."""

    def test_every_token_has_a_status_and_no_token_is_invented(self):
        # The enumeration pin: a token with no status fails here rather than defaulting to some
        # catch-all at the call site. This is the row c3-2 reddened by adding `card_not_found` to
        # the Literal — deliberately, and the reason the two sets are compared rather than counted.
        assert set(STATUS_BY_REASON) == set(_REASONS)

    def test_the_two_404_tokens_are_distinct_and_both_map_to_404(self):
        # Two tokens now share 404, which is new at c3-2 and is the case a naive "one token per
        # status" reading would have got wrong. They are NOT interchangeable: `deck_not_found`
        # clears the SPA to the No-active-deck panel, `card_not_found` leaves the view intact and
        # replaces one slot with a placeholder (c4-3). Same status, different UI.
        assert STATUS_BY_REASON["deck_not_found"] == STATUS_BY_REASON["card_not_found"] == 404
        assert "deck_not_found" != "card_not_found"

    @pytest.mark.parametrize("reason", _REASONS)
    def test_the_mapping_is_the_table_in_the_story(self, reason):
        assert STATUS_BY_REASON[reason] == _EXPECTED_STATUS[reason]


class TestCompanionError:
    """AC 4: the exception carries the token and reads usefully in a log."""

    def test_it_carries_its_reason(self):
        assert CompanionError("deck_not_found").reason == "deck_not_found"

    def test_its_string_form_names_the_reason(self):
        assert "deck_not_found" in str(CompanionError("deck_not_found"))

    def test_a_runtime_invalid_token_fails_at_the_raise_site(self):
        # mypy guards typed call sites only; a dynamic string must fail loudly here, not as a
        # KeyError inside the handler masked as a misleading internal_error.
        with pytest.raises(ValueError, match="bogus"):
            CompanionError("bogus")


class TestErrorResponsesHelper:
    """AC 8: one construction site for the OpenAPI declaration; c3-1 and c3-2 use it, c5-5 next."""

    def test_it_keys_by_the_mapped_status_and_declares_the_model(self):
        declared = error_responses("deck_not_found", "invalid_request")

        assert set(declared) == {404, 400}
        assert declared[404]["model"] is ErrorResponse
        assert declared[400]["model"] is ErrorResponse

    def test_two_tokens_sharing_a_status_collapse_into_one_documented_entry(self):
        # 503 is spoken by two tokens; a naive dict comprehension would silently drop one from the
        # description, leaving the generated TypeScript's docs claiming only half the truth.
        declared = error_responses("database_not_initialized", "database_unavailable")

        assert set(declared) == {503}
        assert "database_not_initialized" in declared[503]["description"]
        assert "database_unavailable" in declared[503]["description"]

    def test_a_repeated_token_is_documented_once(self):
        # c3-1 and c3-2 reuse this helper and c5-5 will; a careless double declaration must not
        # ship "reason: x | x" into the generated docs.
        declared = error_responses("invalid_request", "invalid_request")

        assert declared[400]["description"] == "reason: invalid_request"

    def test_the_two_404_tokens_collapse_into_one_documented_entry_naming_both(self):
        # The 503 pair above proved the collapse for tokens that always travel together. c3-2
        # created a SECOND shared status (404), and no route declares both — so this is the case
        # where a silent overwrite would be invisible in the shipped schema. Pinned anyway,
        # because the helper is the thing under test, not any one route's use of it.
        declared = error_responses("deck_not_found", "card_not_found")

        assert set(declared) == {404}
        assert "deck_not_found" in declared[404]["description"]
        assert "card_not_found" in declared[404]["description"]


class TestRaisedErrorsReachTheWire:
    """AC 4 + AC 11: an endpoint raises a token; the shipped stack turns it into the response."""

    @pytest.mark.parametrize("reason", _REASONS)
    async def test_every_token_round_trips_through_a_real_app(self, reason, lifespan_client):
        async with lifespan_client(_app_with_test_routes()) as client:
            response = await client.get(f"/_raise/{reason}")

        assert response.status_code == _EXPECTED_STATUS[reason]
        assert response.json() == {"reason": reason}


class TestFrameworkFailuresAreTypedToo:
    """AC 5: the failures FastAPI and Starlette answer by default speak the same vocabulary."""

    async def test_a_validation_failure_is_400_invalid_request(self, lifespan_client):
        async with lifespan_client(_app_with_test_routes()) as client:
            response = await client.get("/_typed/xx")

        assert response.status_code == 400, "422 belongs to payload_too_large (AD-16)"
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_validation_failure_never_echoes_the_input_back(self, lifespan_client):
        # FastAPI's default body carries the offending value; the companion is one fetch away from
        # any page in the browser, so the detail belongs in the log and nowhere else.
        async with lifespan_client(_app_with_test_routes()) as client:
            response = await client.get("/_typed/xx")

        assert "detail" not in response.json()
        assert "xx" not in response.text

    async def test_the_validation_detail_reaches_the_log(self, lifespan_client, caplog):
        # The other half of AC 5's promise — "the detail goes to the log" — needs its own pin, or
        # the logger.warning could be deleted without a red test (c1-1's dead-guard lesson).
        with caplog.at_level(logging.WARNING, logger=_ERRORS_MODULE):
            async with lifespan_client(_app_with_test_routes()) as client:
                await client.get("/_typed/xx")

        records = [
            record
            for record in caplog.records
            if record.name == _ERRORS_MODULE and record.levelno == logging.WARNING
        ]
        assert len(records) == 1
        assert "xx" in records[0].getMessage(), "the offending value belongs in the log"

    @pytest.mark.parametrize(
        "path",
        [
            "/api/no-such-path",  # reserved prefix: API territory, never a document
            "/no-such-file.json",  # has an extension: a broken deployment, not a client route
            "/health/no-such-path",  # under a registered route's prefix
        ],
    )
    async def test_an_unknown_path_is_a_typed_404(self, lifespan_client, path):
        # Since c2-2 mounted the SPA at "/", "unknown path" splits in two. An extension-less path
        # outside the API is a **client-side route** and correctly answers 200 with index.html
        # (pinned in test_spa.py); the paths below are the ones that must still 404, and they are
        # what this test now guards. The typed body is unchanged either way.
        async with lifespan_client(_app_with_test_routes()) as client:
            response = await client.get(path)

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_wrong_method_is_a_typed_405(self, lifespan_client):
        async with lifespan_client(_app_with_test_routes()) as client:
            response = await client.post("/health")

        assert response.status_code == 405
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_405_keeps_its_mandatory_allow_header(self, lifespan_client):
        # RFC 9110: "the origin server MUST generate an Allow header" on a 405. Starlette's
        # route-miss raises with it; the typed handler must forward it, not swallow it.
        async with lifespan_client(_app_with_test_routes()) as client:
            response = await client.post("/health")

        assert "allow" in response.headers
        assert "GET" in response.headers["allow"]

    async def test_a_5xx_http_exception_keeps_its_status_and_reads_as_internal(
        self, lifespan_client
    ):
        # A stray 5xx HTTPException is "us, unmodelled" — internal_error. A *modelled* database
        # outage raises CompanionError("database_unavailable"/"database_not_initialized") and
        # never lands in this handler.
        async with lifespan_client(_app_with_test_routes()) as client:
            response = await client.get("/_http/503")

        assert response.status_code == 503
        assert response.json() == {"reason": "internal_error"}

    async def test_a_bodiless_status_passes_through_without_an_error_body(self, lifespan_client):
        # 304 forbids a body; stamping a token onto it would be a protocol violation, and a
        # sub-400 status is not an error at all.
        async with lifespan_client(_app_with_test_routes()) as client:
            response = await client.get("/_http/304")

        assert response.status_code == 304
        assert response.content == b""


class TestUnhandledExceptions:
    """AC 6: a bug is a typed 500 plus a log record — never a traceback on the wire.

    ``internal_error`` rather than ``database_unavailable`` per the c1-4 review ruling (Brad,
    2026-07-25): a deterministic bug must not drive the retry-forever "database is updating" panel.
    """

    async def test_it_answers_a_typed_500(self, lifespan_client):
        # If this raises RuntimeError instead of returning, the middleware is missing or mis-ordered
        # (Gotcha 10): httpx.ASGITransport propagates an escaping exception to the caller.
        async with lifespan_client(_app_with_test_routes()) as client:
            response = await client.get("/_boom")

        assert response.status_code == 500
        assert response.json() == {"reason": "internal_error"}
        assert "kaboom" not in response.text
        assert "Traceback" not in response.text

    async def test_it_logs_the_exception_exactly_once_with_a_traceback(
        self, lifespan_client, caplog
    ):
        with caplog.at_level(logging.ERROR):
            async with lifespan_client(_app_with_test_routes()) as client:
                await client.get("/_boom")

        # Assert the record, not caplog.text: the level and exc_info are the real claim, and the
        # message string alone would pass for the wrong reasons.
        records = [record for record in caplog.records if record.name == _ERRORS_MODULE]
        assert len(records) == 1
        assert records[0].levelno == logging.ERROR
        assert records[0].exc_info is not None
        assert "kaboom" in str(records[0].exc_info[1])

    async def test_a_failure_after_the_response_started_is_re_raised_not_answered_twice(self):
        """Gotcha 6: a second response on a live stream corrupts the ASGI protocol.

        Driven at the ASGI level rather than through a route, because the point is what the
        middleware does with ``send`` — a second ``http.response.start`` is the bug being pinned.
        """
        sent = []

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            raise RuntimeError("failed mid-stream")

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request"}

        middleware = UnhandledErrorMiddleware(app)

        with pytest.raises(RuntimeError, match="failed mid-stream"):
            await middleware({"type": "http", "method": "GET", "path": "/x"}, receive, send)

        assert [message["type"] for message in sent] == ["http.response.start"]

    async def test_non_http_scopes_pass_straight_through(self):
        """There is no JSON body to send on a ``lifespan`` or (c5-3's) ``websocket`` scope."""
        seen = []

        async def app(scope, receive, send):
            seen.append(scope["type"])

        # Real async channels, not None: the test must honour the ASGI contract itself, so a
        # future middleware change that touches them on non-http scopes fails readably.
        async def receive():
            return {"type": "lifespan.startup"}

        async def send(message):
            pass

        await UnhandledErrorMiddleware(app)({"type": "lifespan"}, receive, send)

        assert seen == ["lifespan"]

    async def test_a_client_disconnect_is_not_logged_as_a_bug(self, caplog):
        """A client dropping mid-read is routine — no ERROR record, no answer to a dead stream."""

        async def app(scope, receive, send):
            raise ClientDisconnect()

        async def receive():
            return {"type": "http.request"}

        sent = []

        async def send(message):
            sent.append(message)

        with caplog.at_level(logging.DEBUG, logger=_ERRORS_MODULE):
            with pytest.raises(ClientDisconnect):
                await UnhandledErrorMiddleware(app)(
                    {"type": "http", "method": "GET", "path": "/x"}, receive, send
                )

        assert sent == [], "nothing should be answered into a dead stream"
        error_records = [
            record
            for record in caplog.records
            if record.name == _ERRORS_MODULE and record.levelno >= logging.ERROR
        ]
        assert error_records == [], "a routine disconnect must not raise a false-alarm ERROR"


class TestStructuralPins:
    """AC 7 + AC 8 + AC 9: the things a later story could silently undo."""

    def test_the_error_middleware_is_outermost(self):
        # user_middleware[0] is the *last* one added, which is why install_error_handling() is
        # called last in build_app(). c1-5's Host middleware must insert itself before that call.
        assert build_app().user_middleware[0].cls is UnhandledErrorMiddleware

    def test_the_error_body_is_in_the_schema(self):
        schema = build_app().openapi()

        assert "ErrorResponse" in schema["components"]["schemas"]

    def test_fastapis_own_validation_shape_is_gone(self):
        # AC 5 makes a 422 HTTPValidationError permanently unreachable; leaving it in the schema
        # would put a shape we never emit into c2-3's generated TypeScript. Non-vacuous since the
        # Greptile finding on PR #12: the app under test must carry a *validated* route
        # (/_typed/{n}), because that is exactly what resurrects FastAPI's auto-422 — a bare
        # build_app() has none and passes this test with the stripping deleted.
        schema = _app_with_test_routes().openapi()

        assert "HTTPValidationError" not in schema["components"]["schemas"]
        assert "ValidationError" not in schema["components"]["schemas"]
        assert "422" not in schema["paths"]["/_typed/{n}"]["get"]["responses"], (
            "the auto-422 is back on a validated route — the schema now documents a response "
            "the runtime 400 handler never emits"
        )

    def test_the_error_body_is_declared_on_the_routes(self):
        responses = build_app().openapi()["paths"]["/health"]["get"]["responses"]

        for status in ("400", "413", "500", "503"):
            schema = responses[status]["content"]["application/json"]["schema"]
            assert schema == {"$ref": "#/components/schemas/ErrorResponse"}

    @staticmethod
    def _ref_rooted_cases():
        """The shapes :func:`_is_ref_rooted` must accept and reject. The table is the proof."""
        return [
            ({"$ref": "#/components/schemas/DeckDetail"}, True),
            (
                {"type": "array", "items": {"$ref": "#/components/schemas/DeckSummary"}},
                True,
            ),
            # The real generated shape: FastAPI titles every array response. An annotation key
            # must not be mistaken for a shaping key.
            (
                {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/DeckSummary"},
                    "title": "Response Read Decks Api Decks Get",
                },
                True,
            ),
            # An envelope: the exact hand-built {"status": ..., "deck": ...} this bans.
            ({"type": "object", "properties": {"status": {}, "deck": {}}}, False),
            # An array *of* an envelope — the evasion a shallow "type == array" check would miss.
            ({"type": "array", "items": {"type": "object", "properties": {}}}, False),
            # An untyped bag, and a bare scalar: neither is a declared model.
            ({"type": "object"}, False),
            ({"type": "string"}, False),
            # An array carrying a sibling `properties` alongside `items` — the shape a shallow
            # "type == array, recurse into items" check waves through (review, 2026-07-31).
            (
                {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/DeckSummary"},
                    "properties": {"total": {}},
                },
                False,
            ),
        ]

    def test_the_ref_rooted_helper_accepts_and_rejects(self):
        """Non-vacuity for the walk below: the predicate itself has both halves proven."""
        for shape, expected in self._ref_rooted_cases():
            assert _is_ref_rooted(shape) is expected, shape

    def test_every_success_body_is_a_component_ref_never_an_envelope(self):
        # AD-16 structurally: an inline object is what a hand-built {"status": "ok", "deck": {...}}
        # return looks like in the schema. A $ref means a declared response_model.
        schema = build_app().openapi()
        checked = []

        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                if not isinstance(operation, dict):
                    continue  # path-level "parameters" (a list) or "summary" (a str) is legal.
                for status, response in operation.get("responses", {}).items():
                    if not status.startswith("2"):
                        continue
                    body = response.get("content", {}).get("application/json")
                    if body is None:
                        continue  # c3-5's image route declares image/*, not JSON.
                    checked.append(f"{method.upper()} {path} {status}")
                    assert "schema" in body, (
                        f"{method.upper()} {path} {status} declares JSON content with no schema"
                    )
                    assert _is_ref_rooted(body["schema"]), (
                        f"{method.upper()} {path} {status} returns an inline JSON object — declare "
                        "a response_model so the shape is generated, not hand-built (AD-12/AD-16)"
                    )

        # Non-vacuity (c1-1's dead-guard lesson): a walk that visited nothing passes silently.
        # Both rooted shapes are named, so a walk that found only one kind cannot pass either.
        assert "GET /health 200" in checked
        assert "GET /api/decks 200" in checked
        assert "GET /api/deck/{deck_id} 200" in checked


class TestConstructionStaysInert:
    """AC 10: handlers and middleware are in-process objects, so AD-10 is untouched."""

    def test_installing_the_handlers_creates_no_directory(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "never-created"
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(data_dir))

        app = build_app()

        assert app is not None
        assert not data_dir.exists()

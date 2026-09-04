"""Story c5-5: ``POST /agent/events`` — the agent pushes, and learns who was listening (FR-06).

**What this file is *not* about.** ``test_contracts.py`` already validates the six-kind union
exhaustively — every field cap, every blank guard, every naive-timestamp refusal — driven directly
against the models. Re-testing payload shape here would be a second hand-synchronised copy of that
matrix. What is asserted below is the **route's** behaviour: that the union is what the endpoint
accepts, that the credential gate is the shipped one, that an accepted push reaches real open
sockets, and that the number in the response is the one Q1 ruled.

**Everything is asserted through the wire.** The registry is never read to prove a delivery — a
test that counted ``connection_registry(app)`` would pass with the broadcast call deleted. The
proof is two concurrently open sockets whose frame lists gain the serialised envelope, which is
what :func:`~tests.unit.companion.conftest.open_socket` exists for.

**The two rejection classes are kept distinct, deliberately** (Q7, Brad 2026-08-08). A violated
*field* cap is a pydantic ``RequestValidationError`` and answers **400** ``invalid_request`` via
the shipped AD-16 handler; only a violated *byte* cap answers **413** ``payload_too_large``. The
epic AC asks for 413 on "any cap", and this story ruled a deviation rather than introspecting
pydantic error internals per route — see the story record. Both arms are proved here, side by side,
so the deviation is visible rather than implied.

The one real-socket proof is c5-8's, and it shipped on 2026-08-09:
``tests/integration/companion/test_live_backend.py`` drives this route over a real port with a real
``Authorization: Bearer`` header from a real ``companion.json``, and walks the FR-12 restart case
(stale token → 403 → re-read → retry → 200) that no in-process test can stage. Nothing here is
integration-marked, and nothing here should become so.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import TypeAdapter

from src.companion.app.body_cap import BodyCapMiddleware
from src.companion.app.main import agent_token, build_app
from src.companion.app.state import connection_registry
from src.companion.contracts import (
    _MAX_BUCKETS,
    _MAX_CARD_ID_LENGTH,
    _MAX_ENVELOPE_BYTES,
    _MAX_ITEMS,
    _MAX_RATIONALE_LENGTH,
    _MAX_TITLE_LENGTH,
    AgentEvent,
)
from tests.unit.companion.conftest import FakeConnection, open_socket

_AGENT_EVENT = TypeAdapter(AgentEvent)
"""The union as a standalone validator — the alias is ``Annotated``, so it has no
``model_validate`` of its own. Used here only to prove a test fixture is genuinely valid."""

_PATH = "/agent/events"

_REPO_ROOT = Path(__file__).resolve().parents[3]

# A card id the shipped `_CardId` cap accepts, distinguishable from every fixture id in the suite
# so that a frame asserted to carry it cannot be satisfied by some other module's envelope.
_CARD_ID = "c5c5c5c5-0000-4000-8000-00000000e5e5"
_EVENT_ID = "event-c5-5-ingest-under-test"


def _event(**overrides):
    """Return a valid ``suggestions`` envelope as JSON-ready data, with *overrides* applied."""
    body = {
        "kind": "suggestions",
        "id": _EVENT_ID,
        "ts": datetime.now(UTC).isoformat(),
        "payload": {
            "title": "Resilience options",
            "items": [
                {
                    "card_id": _CARD_ID,
                    "reason": "Fills the two-drop gap.",
                    "category": "Curve",
                    "confidence": "high",
                }
            ],
        },
    }
    body.update(overrides)
    return body


def _oversized_but_valid():
    """Return a ``groups`` envelope that violates no field cap and still exceeds the byte cap.

    Every string sits at its own limit and every list at its own length, so pydantic accepts it —
    and the result serialises to roughly 104 KB, comfortably past the 64 KB envelope ceiling. That
    combination is what makes the 413 tests discriminating: a rejection of *this* body cannot be a
    field cap firing, because there is no field cap left for it to violate.

    ``groups`` rather than ``suggestions`` because it is the largest of the six by construction —
    twelve buckets, each carrying sixty full-length card ids plus a 600-character rationale.
    """
    card_ids = ["c" * _MAX_CARD_ID_LENGTH] * _MAX_ITEMS
    return _event(
        kind="groups",
        payload={
            "title": "t" * _MAX_TITLE_LENGTH,
            "items": [
                {
                    "title": "g" * _MAX_TITLE_LENGTH,
                    "rationale": "r" * _MAX_RATIONALE_LENGTH,
                    "card_ids": card_ids,
                }
                for _ in range(_MAX_BUCKETS)
            ],
        },
    )


def _bearer(token):
    """Return the ``Authorization`` header presenting *token*."""
    return {"Authorization": f"Bearer {token}"}


async def _mint(client):
    """Mint one WebSocket ticket through the shipped endpoint, and return it."""
    response = await client.get("/api/session")
    assert response.status_code == 200, response.text
    return response.json()["ticket"]


class TestTheHappyPath:
    """AC 1, 2, 6: an authenticated valid envelope is accepted, relayed, and counted."""

    async def test_a_valid_envelope_is_accepted(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.post(_PATH, json=_event(), headers=_bearer(agent_token(app)))

        assert response.status_code == 200
        # Zero connected clients is a success, not a failure: a companion with no tab open is the
        # ordinary state and the push was delivered exactly as instructed.
        assert response.json() == {"clients": 0}

    async def test_an_empty_payload_is_accepted_and_relayed(self, lifespan_client):
        # EXPERIENCE.md: an empty push is accepted. Zero suggestions is a legitimate answer to
        # "what should I change?" — the view renders its own empty state rather than the endpoint
        # refusing to carry the finding.
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            async with open_socket(app, ticket=ticket) as socket:
                response = await client.post(
                    _PATH,
                    json=_event(payload={"items": []}),
                    headers=_bearer(agent_token(app)),
                )
                frames = list(socket.frames)

        assert response.status_code == 200
        assert response.json() == {"clients": 1}
        assert len(frames) == 1
        assert json.loads(frames[0])["payload"]["items"] == []

    async def test_the_response_carries_no_echo_of_the_payload(self, lifespan_client):
        # CM-1. The agent already holds what it sent; a body that repeated it would double the cost
        # of every push to say nothing new. Asserted as an exact body rather than an absence, so a
        # future field cannot slip in unnoticed.
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.post(_PATH, json=_event(), headers=_bearer(agent_token(app)))

        assert set(response.json()) == {"clients"}
        assert _CARD_ID not in response.text


class TestTheRelayReachesEveryClient:
    """AC 2: FR-06's "every connected client", proved at the wire with real open sockets."""

    async def test_both_open_sockets_receive_the_serialised_envelope(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            first_ticket = await _mint(client)
            second_ticket = await _mint(client)
            async with (
                open_socket(app, ticket=first_ticket) as first,
                open_socket(app, ticket=second_ticket) as second,
            ):
                response = await client.post(
                    _PATH, json=_event(), headers=_bearer(agent_token(app))
                )
                first_frames = list(first.frames)
                second_frames = list(second.frames)

        assert response.status_code == 200
        assert response.json() == {"clients": 2}
        # Byte-identical, because `broadcast` serialises once before the loop — the property that
        # makes a fan-out to twenty tabs cost one serialisation rather than twenty.
        assert first_frames == second_frames
        assert len(first_frames) == 1
        delivered = json.loads(first_frames[0])
        assert delivered["kind"] == "suggestions"
        assert delivered["id"] == _EVENT_ID
        assert delivered["payload"]["items"][0]["card_id"] == _CARD_ID

    async def test_a_second_push_is_relayed_to_the_same_open_socket(self, lifespan_client):
        # Non-vacuity for the count above: proves the socket keeps receiving rather than the first
        # frame being an artefact of the handshake. Two pushes, two frames, both counted 1.
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            async with open_socket(app, ticket=ticket) as socket:
                first = await client.post(
                    _PATH, json=_event(id="first-push"), headers=_bearer(agent_token(app))
                )
                second = await client.post(
                    _PATH, json=_event(id="second-push"), headers=_bearer(agent_token(app))
                )
                frames = list(socket.frames)

        assert (first.json(), second.json()) == ({"clients": 1}, {"clients": 1})
        assert [json.loads(frame)["id"] for frame in frames] == ["first-push", "second-push"]


class TestTheNumberIsTheDeliveredCount:
    """AC 2, Q1: the receipt reports what ``broadcast()`` achieved, not what the registry holds.

    The two numbers agree except in the failure race, so a test that only ever drove healthy
    clients would pass under either implementation. :class:`FakeConnection` with ``fails=True``
    registered directly on the registry is what makes them disagree — the one case that
    discriminates.
    """

    async def test_a_client_that_cannot_be_written_to_is_not_counted(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            registry = connection_registry(app)
            healthy = FakeConnection()
            gone = FakeConnection(fails=True)
            registry.add(healthy)
            registry.add(gone)

            response = await client.post(_PATH, json=_event(), headers=_bearer(agent_token(app)))

        # Two registered, one delivered. `connected_count` sampled before the fan-out would have
        # said 2; the delivered count says 1, which is the truthful answer to "how many browsers
        # saw it" and the reason Q1 chose it.
        assert response.json() == {"clients": 1}
        assert len(healthy.sent) == 1
        assert gone.sent == []

    async def test_the_same_registry_would_have_reported_two(self, lifespan_client):
        # The non-vacuity half, and the thing that makes the test above a real discriminator: with
        # both clients healthy the two accountings agree at 2, so the 1 above is caused by the
        # failure and not by some unrelated undercount.
        app = build_app()
        async with lifespan_client(app) as client:
            registry = connection_registry(app)
            registry.add(FakeConnection())
            registry.add(FakeConnection())

            response = await client.post(_PATH, json=_event(), headers=_bearer(agent_token(app)))

        assert response.json() == {"clients": 2}


class TestTheCredentialGate:
    """AC 4: the shipped ``AgentToken`` dependency, and nothing is broadcast on a refusal."""

    @pytest.mark.parametrize(
        ("description", "headers"),
        [
            ("no credential at all", {}),
            ("a wrong credential", {"Authorization": "Bearer completely-the-wrong-credential"}),
            ("a malformed header", {"Authorization": "NotBearer whatever"}),
        ],
    )
    async def test_a_refused_credential_answers_forbidden(
        self, lifespan_client, description, headers
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.post(_PATH, json=_event(), headers=headers)

        assert response.status_code == 403, description
        # Byte-identical to every other refusal in the app: the caller cannot tell which of the
        # three it tripped, and the one-word distinction goes to the log alone.
        assert response.json() == {"reason": "forbidden"}

    async def test_the_paired_acceptance_proves_the_rejections_are_not_vacuous(
        self, lifespan_client
    ):
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.post(_PATH, json=_event(), headers=_bearer(agent_token(app)))

        assert response.status_code == 200

    async def test_nothing_is_broadcast_when_the_credential_is_refused(self, lifespan_client):
        # The half that matters for AD-5: a refused push must not reach the glass. Proved with a
        # real open socket whose frame list stays EMPTY, which a status-only assertion cannot show.
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            async with open_socket(app, ticket=ticket) as socket:
                refused = await client.post(_PATH, json=_event())
                after_refusal = list(socket.frames)

                accepted = await client.post(
                    _PATH, json=_event(), headers=_bearer(agent_token(app))
                )
                after_acceptance = list(socket.frames)

        assert refused.status_code == 403
        assert after_refusal == []
        # The paired acceptance on the SAME socket: the empty list above is a refusal, not a
        # socket that never receives anything.
        assert accepted.status_code == 200
        assert len(after_acceptance) == 1

    async def test_an_app_whose_lifespan_never_ran_refuses_rather_than_accepting(self):
        # The fail-closed case `agent_token_is_valid` exists for: before startup the minted token
        # is None, and a caller can present nothing — also None. Driven through a real build_app()
        # rather than against the comparison function, because the risk is a route wired to the
        # wrong comparison.
        app = build_app()
        assert agent_token(app) is None

        transport = httpx.ASGITransport(app=app)
        app.state.bound_port = 54321
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:54321") as c:
            response = await c.post(_PATH, json=_event())

        assert response.status_code == 403
        assert response.json() == {"reason": "forbidden"}


class TestFieldCapsAnswerFourHundred:
    """AC 5, Q7: a violated *field* cap is ``invalid_request``, not ``payload_too_large``.

    This is the ruled deviation from the epic AC, asserted rather than left implicit. The epic
    demands 413 for a payload exceeding *any* Story 5.1 cap; field caps are pydantic constraints
    and the shipped AD-16 handler maps ``RequestValidationError`` to 400 app-wide. The AC's real
    teeth — rejected, never truncated, no partial render — hold either way, and AD-8's tool layer
    folds both statuses into one ``payload_rejected`` token before an agent ever sees them.
    """

    @pytest.mark.parametrize(
        ("description", "body"),
        [
            (
                "one item over the item cap",
                _event(
                    payload={
                        "items": [
                            {"card_id": _CARD_ID, "reason": "over"} for _ in range(_MAX_ITEMS + 1)
                        ]
                    }
                ),
            ),
            ("a blank envelope id", _event(id="   ")),
            ("a naive timestamp", _event(ts="2026-08-08T09:15:00")),
            ("an unknown kind", _event(kind="not-a-kind")),
            ("an unparseable body shape", {"nonsense": True}),
        ],
    )
    async def test_a_violated_field_constraint_answers_invalid_request(
        self, lifespan_client, description, body
    ):
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.post(_PATH, json=body, headers=_bearer(agent_token(app)))

        assert response.status_code == 400, description
        assert response.json() == {"reason": "invalid_request"}

    async def test_the_cap_boundary_itself_is_accepted(self, lifespan_client):
        # The paired acceptance: exactly at the cap is legal, one over is not. A rejection test
        # without this proves the model refuses things, not that it accepts the legal maximum.
        app = build_app()
        items = [{"card_id": _CARD_ID, "reason": "at cap"} for _ in range(_MAX_ITEMS)]
        at_cap = _event(payload={"items": items})
        async with lifespan_client(app) as client:
            response = await client.post(_PATH, json=at_cap, headers=_bearer(agent_token(app)))

        assert response.status_code == 200

    async def test_nothing_is_broadcast_when_the_envelope_is_rejected(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            async with open_socket(app, ticket=ticket) as socket:
                rejected = await client.post(
                    _PATH, json=_event(id="   "), headers=_bearer(agent_token(app))
                )
                frames = list(socket.frames)

        assert rejected.status_code == 400
        assert frames == []


class TestTheByteCapAnswersFourHundredAndThirteen:
    """AC 5, 8, 9: the envelope byte cap, the first and only producer of ``payload_too_large``.

    The cap is **pre-parse** by construction (Q2, Brad 2026-08-08). A pydantic model validator runs
    after the body has been read into memory, so it could reject an oversized envelope but could
    not stop an unauthenticated caller from making the process buffer it — which is the whole
    property AD-7's ceiling exists for. What is asserted here is the observable half: the status,
    the token, that nothing is relayed, and that a lying ``Content-Length`` does not get through.
    """

    async def test_a_fully_valid_envelope_can_still_exceed_the_byte_cap(self):
        """The two caps are **not nested**, measured rather than assumed (c5-5, 2026-08-08).

        This is the finding that makes every test below a real discriminator, and it is worth
        stating on its own: an envelope that violates **no** field cap — every string at its
        limit, every list at its length — serialises to 104,067 bytes for the ``groups`` kind,
        which is 1.6x the 64 KB ceiling. So the byte cap is not merely a backstop behind the field
        caps; it can refuse an envelope pydantic would have accepted, and the two rejection classes
        genuinely overlap rather than partitioning the input space.

        That is AD-7's ceiling working as specified (a bound on the *request*, independent of any
        field), but it means an agent can build a legal push that this endpoint refuses, so the
        413 arm is reachable by well-formed content and not only by garbage.
        """
        legal_and_oversized = _oversized_but_valid()

        # It really is valid: the union accepts it, so a 413 for it cannot be a field cap in
        # disguise. This is the assertion the whole class rests on.
        assert _AGENT_EVENT.validate_python(legal_and_oversized)
        assert len(json.dumps(legal_and_oversized).encode("utf-8")) > _MAX_ENVELOPE_BYTES

    async def test_an_oversized_body_is_refused_with_the_typed_token(self, lifespan_client):
        app = build_app()
        payload = json.dumps(_oversized_but_valid()).encode("utf-8")

        async with lifespan_client(app) as client:
            response = await client.post(
                _PATH,
                content=payload,
                headers={"content-type": "application/json", **_bearer(agent_token(app))},
            )

        # 413, not 400 — and because the body above is a VALID envelope, this can only be the byte
        # cap. A field cap firing here would have said `invalid_request`.
        assert response.status_code == 413
        assert response.json() == {"reason": "payload_too_large"}

    async def test_a_body_just_under_the_cap_is_accepted(self, lifespan_client):
        # The paired acceptance. Without it, a middleware that refused EVERY body would satisfy the
        # rejection test above — the c5-4 lesson about driving the case that discriminates.
        app = build_app()
        body = _event()
        encoded = json.dumps(body).encode("utf-8")
        assert len(encoded) < _MAX_ENVELOPE_BYTES  # non-vacuity

        async with lifespan_client(app) as client:
            response = await client.post(
                _PATH,
                content=encoded,
                headers={"content-type": "application/json", **_bearer(agent_token(app))},
            )

        assert response.status_code == 200

    async def test_a_lying_content_length_does_not_get_through(self):
        """The counted-bytes bound, driven at the ASGI level because httpx cannot lie for us.

        ``httpx`` computes ``Content-Length`` from the body it is given and overrides any header a
        caller supplies, so an *over-the-wire* test can only ever exercise the honest path — which
        would leave the bound that actually holds the ceiling unproven. So this builds the scope
        by hand, exactly as ``test_security.py`` drives the ``Host`` middleware, and declares a
        body of 10 bytes while feeding 100 KB through ``receive``.

        This is the case that discriminates: with the counted-bytes check removed the
        ``Content-Length`` check alone waves this straight through, and every other 413 test in
        this file stays green.
        """
        oversized = json.dumps(_oversized_but_valid()).encode("utf-8")
        assert len(oversized) > _MAX_ENVELOPE_BYTES  # non-vacuity

        sent = []
        chunks = iter(
            [
                {"type": "http.request", "body": oversized[:1000], "more_body": True},
                {"type": "http.request", "body": oversized[1000:], "more_body": False},
            ]
        )

        async def receive():
            return next(chunks, {"type": "http.disconnect"})

        async def send(message):
            sent.append(message)

        inner_was_called = []

        async def inner(scope, receive, send):
            inner_was_called.append(scope["path"])

        scope = {
            "type": "http",
            "method": "POST",
            "path": _PATH,
            "headers": [
                (b"content-type", b"application/json"),
                # The lie: ten bytes declared, a hundred kilobytes delivered.
                (b"content-length", b"10"),
            ],
        }
        await BodyCapMiddleware(inner)(scope, receive, send)

        start = next(m for m in sent if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        assert start["status"] == 413
        assert json.loads(body) == {"reason": "payload_too_large"}
        # Rejected, never truncated: the inner application was never called at all, so no route
        # ever saw a partial body.
        assert inner_was_called == []

    async def test_an_honest_small_body_reaches_the_inner_application(self):
        # The paired acceptance for the ASGI-level test above: the middleware is not simply
        # refusing everything it is handed.
        sent = []
        reached = []

        async def receive():
            return {"type": "http.request", "body": b'{"ok": true}', "more_body": False}

        async def send(message):
            sent.append(message)

        async def inner(scope, receive_, send_):
            # The body must arrive intact — the middleware read it only to measure it.
            reached.append((await receive_())["body"])

        scope = {
            "type": "http",
            "method": "POST",
            "path": _PATH,
            "headers": [(b"content-type", b"application/json"), (b"content-length", b"12")],
        }
        await BodyCapMiddleware(inner)(scope, receive, send)

        assert reached == [b'{"ok": true}']
        assert sent == []

    async def test_nothing_is_broadcast_when_the_body_is_over_cap(self, lifespan_client):
        app = build_app()
        oversized = json.dumps(_oversized_but_valid()).encode("utf-8")

        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            async with open_socket(app, ticket=ticket) as socket:
                refused = await client.post(
                    _PATH,
                    content=oversized,
                    headers={"content-type": "application/json", **_bearer(agent_token(app))},
                )
                after_refusal = list(socket.frames)

                accepted = await client.post(
                    _PATH, json=_event(), headers=_bearer(agent_token(app))
                )
                after_acceptance = list(socket.frames)

        assert refused.status_code == 413
        assert after_refusal == []
        # Paired acceptance on the same socket: the empty list is a refusal, not a dead socket.
        assert accepted.status_code == 200
        assert len(after_acceptance) == 1

    async def test_the_refusal_body_is_byte_identical_to_every_other_typed_error(
        self, lifespan_client
    ):
        # The middleware SENDS rather than raises (c1-5), and it sends through the same
        # `error_response` construction site as every other typed failure — so the wire shape,
        # including `Cache-Control: no-store`, cannot drift from the rest of the app.
        #
        # THE STATUS AND TOKEN ASSERTIONS BELOW ARE THE ONES THAT DO THE WORK, and they are here
        # because an R2 probe proved the others do not (2026-08-08). Planting `raise
        # CompanionError("payload_too_large")` in place of the send reddened six tests in this file
        # and left THIS one green: a raised CompanionError from user middleware is swallowed by
        # `UnhandledErrorMiddleware` into `500 {"reason": "internal_error"}`, which is *also*
        # `no-store`, *also* `application/json` and *also* a single-key `reason` body. Every
        # assertion this test originally carried was satisfied by the exact failure it was written
        # to catch. Asserting the status and the token is what closes it.
        app = build_app()
        oversized = json.dumps(_oversized_but_valid()).encode("utf-8")

        async with lifespan_client(app) as client:
            response = await client.post(
                _PATH,
                content=oversized,
                headers={"content-type": "application/json", **_bearer(agent_token(app))},
            )
            forbidden = await client.post(_PATH, json=_event())

        # The discriminators: a raising middleware answers 500 `internal_error` here.
        assert response.status_code == 413
        assert response.json() == {"reason": "payload_too_large"}
        # The shape assertions, which are about drift rather than about this failure mode.
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"].startswith("application/json")
        assert set(response.json()) == set(forbidden.json()) == {"reason"}

    async def test_an_oversized_body_is_refused_before_the_credential_is_checked(
        self, lifespan_client
    ):
        # Q3's ruling made observable: the cap is pre-parse and pre-dependency, so an oversized
        # body answers 413 even with NO credential. That is the correct fail-cheap order — the
        # process should not buffer megabytes on behalf of a caller it was going to refuse — and
        # it is why the c3-4 ordering pin was revised rather than preserved.
        app = build_app()
        oversized = json.dumps(_oversized_but_valid()).encode("utf-8")

        async with lifespan_client(app) as client:
            response = await client.post(
                _PATH, content=oversized, headers={"content-type": "application/json"}
            )

        assert response.status_code == 413
        assert response.json() == {"reason": "payload_too_large"}


class TestOneMechanismForBothBodyEndpoints:
    """AC 8: the cap bounds ``PUT /api/active-deck`` too, with no per-route code.

    The ledgered deferral this closes (``dw:2604-2620``, from c3-4's Q4) asks for exactly this: one
    mechanism, both endpoints. A dependency-shaped cap would have been per-route by construction
    and would have left the buffering hole open on every future body route by default.
    """

    async def test_the_active_deck_put_refuses_an_oversized_body(self, lifespan_client):
        app = build_app()
        # Deliberately not a valid `ActiveDeckRequest` — it never gets that far. The cap runs
        # before parsing, which is the property being asserted.
        oversized = b'{"deck_id": "' + b"x" * (_MAX_ENVELOPE_BYTES + 1) + b'"}'

        async with lifespan_client(app) as client:
            response = await client.put(
                "/api/active-deck",
                content=oversized,
                headers={"content-type": "application/json", **_bearer(agent_token(app))},
            )

        assert response.status_code == 413
        assert response.json() == {"reason": "payload_too_large"}

    async def test_an_ordinary_put_is_untouched(self, lifespan_client):
        # The paired acceptance, and the don't-break guard: an under-cap body must still pass the
        # middleware through to c3-4's endpoint untouched. The response shape gained `clients` at
        # c6-2 — that is the route's own change, not the cap's; what this asserts about the cap is
        # the 200 beside the 413 above.
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.put(
                "/api/active-deck",
                json={"deck_id": "deck-alpha-first-set"},
                headers=_bearer(agent_token(app)),
            )

        assert response.status_code == 200
        assert response.json() == {"deck_id": "deck-alpha-first-set", "clients": 0}

    async def test_a_body_less_get_is_unaffected(self, lifespan_client):
        # The middleware wraps `receive` on every http scope; a route that never reads a body must
        # not notice it exists.
        async with lifespan_client(build_app()) as client:
            health = await client.get("/health")
            session = await client.get("/api/session")

        assert health.status_code == 200
        assert session.status_code == 200

    async def test_a_websocket_scope_passes_through_untouched(self, lifespan_client):
        # AC 8's last clause. The upgrade must still work: a middleware that treated `websocket`
        # scopes as capped http ones would break the handshake outright.
        app = build_app()
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            async with open_socket(app, ticket=ticket) as socket:
                assert socket.was_accepted


class TestTheCapIsDeclaredOnlyWhereItCanAnswer:
    """AC 13: the curation. ``payload_too_large`` is declared by two operations and no others."""

    def test_exactly_the_two_body_bearing_operations_declare_it(self):
        schema = build_app().openapi()

        declaring = {
            (path, method)
            for path, operations in schema["paths"].items()
            for method, operation in operations.items()
            if "413" in operation.get("responses", {})
        }

        assert declaring == {("/agent/events", "post"), ("/api/active-deck", "put")}

    def test_the_body_less_gets_no_longer_promise_a_branch_they_cannot_reach(self):
        # The wart itself, stated as the absence it now is: six GETs used to publish an
        # unreachable 413 through the two shared include sets.
        schema = build_app().openapi()

        for path in ("/health", "/api/decks", "/api/session", "/api/active-deck"):
            assert "413" not in schema["paths"][path]["get"]["responses"], path

    def test_the_remaining_declarations_are_otherwise_unchanged(self):
        # Non-vacuity plus a don't-break: removing the 413 must not have taken anything else with
        # it. `/health` keeps exactly the rest of c1-2's historical set.
        responses = build_app().openapi()["paths"]["/health"]["get"]["responses"]

        assert set(responses) == {"200", "400", "503", "500"}


class TestNoDatabaseAnywhereNearThisRoute:
    """AC 7 (AD-7, NFR-05): the push path opens no session and validates no card id."""

    async def test_an_unknown_card_id_is_accepted_and_relayed(self, lifespan_client):
        # EXPERIENCE.md: an unknown card degrades per entry in the UI, it does not reject the push.
        # Validating ids here would put a database read on a path AD-7 forbids one on, and would
        # make one bad id discard a whole legitimate finding.
        app = build_app()
        unknown = "00000000-dead-4000-8000-000000000000"
        async with lifespan_client(app) as client:
            ticket = await _mint(client)
            async with open_socket(app, ticket=ticket) as socket:
                response = await client.post(
                    _PATH,
                    json=_event(
                        payload={"items": [{"card_id": unknown, "reason": "not in the corpus"}]}
                    ),
                    headers=_bearer(agent_token(app)),
                )
                frames = list(socket.frames)

        assert response.status_code == 200
        assert json.loads(frames[0])["payload"]["items"][0]["card_id"] == unknown

    def test_the_route_declares_no_service_unavailable(self, lifespan_client):
        # The operation has no database dependency, so it can answer neither 503 token. Declaring
        # one would promise a `types.d.ts` consumer a branch that can never arrive.
        responses = build_app().openapi()["paths"][_PATH]["post"]["responses"]

        assert "503" not in responses
        # Non-vacuity: the operation was found and does declare its real failures.
        assert set(responses) == {"200", "400", "403", "413", "500"}


class TestNotShadowedBySpa:
    """AC 1: ``/agent`` is a novel prefix, protected only by registration order."""

    async def test_the_endpoint_runs_rather_than_serving_the_index(self, lifespan_client):
        # Asserted on the BODY, not the content type: `/agent` is NOT in `_RESERVED_SEED`, so a
        # shadowed route would answer 200 with index.html. Only the body distinguishes "the route
        # ran" from "the mount swallowed it".
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.post(_PATH, json=_event(), headers=_bearer(agent_token(app)))

        assert response.json() == {"clients": 0}

    async def test_an_unrouted_sibling_path_is_refused_rather_than_falling_back(
        self, lifespan_client
    ):
        # The non-vacuity pair: `agent` enters `spa._reserved_prefixes` by DERIVATION from the
        # route table (the `/ws` precedent), so a typo under it answers a typed 404 rather than
        # the index — which is what proves the derivation ran.
        async with lifespan_client(build_app()) as client:
            response = await client.get("/agent/eventz")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_get_of_the_post_only_path_is_a_typed_405_carrying_allow(self, lifespan_client):
        # `spa.py`'s `_DecliningStaticFiles` exists for exactly this, and `/agent/events` is the
        # first path in the app served by exactly ONE method — the cleanest case for it. Without
        # the decline, the mount at "/" would take the first Match.FULL and answer 200 with
        # index.html; with it, Starlette's partial match produces 405 and `errors.py` recomputes
        # the `Allow` union. Measured 2026-08-08 rather than asserted from the docstring.
        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH)

        assert response.status_code == 405
        assert response.headers["allow"] == "POST"
        assert response.json() == {"reason": "invalid_request"}

    def test_the_spa_mount_is_still_the_last_route(self):
        assert getattr(build_app().router.routes[-1], "name", None) == "spa"

    def test_agent_is_a_reserved_prefix(self):
        from src.companion.app import spa

        assert "agent" in spa._reserved_prefixes(build_app())


class TestTheCommittedSchema:
    """AC 11: the union reaches ``components.schemas`` by being declared as the request body.

    The whole-artifact path and component pins live in ``test_committed_schema.py``. What is
    asserted here is this operation's own contract.
    """

    @pytest.fixture(scope="class")
    def schema(self):
        path = _REPO_ROOT / "ui" / "src" / "api" / "openapi.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_the_request_body_is_the_six_kind_union(self, schema):
        body = schema["paths"][_PATH]["post"]["requestBody"]["content"]["application/json"]
        arms = body["schema"]["oneOf"]

        # Every member is its own `$ref`, never an inline object — the shape that makes narrowing
        # on `kind` a single step in the generated TypeScript.
        assert [arm["$ref"].rsplit("/", 1)[-1] for arm in arms] == [
            "SuggestionsEvent",
            "SwapsEvent",
            "TierListEvent",
            "GroupsEvent",
            "DeckChangedEvent",
            "ActiveDeckChangedEvent",
        ]

    def test_the_success_body_is_the_receipt(self, schema):
        content = schema["paths"][_PATH]["post"]["responses"]["200"]["content"]

        assert content["application/json"]["schema"]["$ref"].endswith("/EventIngestReceipt")

    def test_the_operation_declares_exactly_its_four_failures(self, schema):
        responses = schema["paths"][_PATH]["post"]["responses"]

        assert set(responses) == {"200", "400", "403", "413", "500"}

    def test_the_envelope_examples_reach_the_document(self, schema):
        # c5-1's `json_schema_extra` examples cross the wire for the first time here. The
        # `_DATA_KEYS` truncator fix that keeps `without_python_docstring_sections` out of example
        # payloads is already shipped and tested; this is its first live exercise.
        suggestions = schema["components"]["schemas"]["SuggestionsEvent"]

        assert suggestions["examples"][0]["kind"] == "suggestions"
        assert suggestions["examples"][0]["payload"]["items"][0]["reason"]


class TestNoSecondAuthCheck:
    """AC 4: the credential contract is inherited whole, never re-implemented."""

    def test_no_security_scheme_was_introduced(self):
        # `require_agent_token` reads the header by hand precisely so the artifact stays clean. A
        # FastAPI security class would have added a `securitySchemes` component and a per-operation
        # `security` block, and would have raised its own HTTPException past the `forbidden` token.
        schema = build_app().openapi()

        assert "securitySchemes" not in schema.get("components", {})
        assert "security" not in schema["paths"][_PATH]["post"]

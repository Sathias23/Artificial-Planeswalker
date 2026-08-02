"""Story c3-5: ``GET /api/card-image/{scryfall_id}``, driven end to end.

The pattern ``test_routes_cards.py`` established: every test builds a **real** ``build_app()`` and
drives it through the ``lifespan_client`` seam against a **real** temporary SQLite file, seeded
with the shared ``image_shapes`` corpus in ``conftest.py``. What is under test is the whole
shipped path — the session dependency, both ``503``s, the id constraint routing into the app-wide
validation handler, the face resolver, the allow-list, the two new tokens and the cache headers.

**No test here touches the network.** The outbound transport is replaced at the seam
``images.build_image_client`` provides, by a recorder that captures every URL it was asked for.
Every test asserts on **what was requested** as well as on what came back — a route that answered
correctly from the wrong URL is exactly the bug this endpoint exists to avoid, and a response-only
assertion cannot see it.

**Assert on the bytes, not merely the status** (c3-1's R1 finding: ``TestNotShadowedBySpa`` once
passed with the router deleted, because ``/api`` is reserved and answers JSON either way). A
wrong-but-JSON answer is precisely the shape that slips through on a binary endpoint.
"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from src.companion.app import images
from src.companion.app.main import build_app
from src.companion.app.spa import _IMMUTABLE_CACHE_CONTROL
from src.data.models.deck import DeckModel
from src.data.models.deck_card import DeckCardModel
from tests.unit.companion.conftest import (
    _TOP_LEVEL_IMAGES,
    ABSENT_ID,
    MANY_FACE_ID,
    MULTI_FACE_ID,
    NO_IMAGE_ID,
    SCHEMA_ONLY_ID,
    SINGLE_FACE_ID,
    SPLIT_FACE_ID,
    FakeClock,
    StallableUpstream,
    _point_at,
    _seed,
    _uuid,
)

# --------------------------------------------------------------------------------------------
# The path under test. A literal, not built from the router — a test that imported the prefix
# would still pass if the prefix were wrong. Singular `card-image`, matching the epic.
# --------------------------------------------------------------------------------------------

_IMAGE_PATH = "/api/card-image/{scryfall_id}"

_PNG = b"\x89PNG\r\n\x1a\n-pretend-this-is-a-picture"
_JPEG = b"\xff\xd8\xff\xe0-pretend-this-is-a-photograph"


class Recorder:
    """A stand-in CDN that records every request and answers from a scripted table.

    Attributes:
        requested: Every URL the transport was asked for, in order. Empty is a *meaningful*
            assertion in several tests below — "no fetch was attempted" is a behaviour AD-11
            requires, not an implementation detail.
    """

    def __init__(self, *, body: bytes = _JPEG, content_type: str = "image/jpeg") -> None:
        self.requested: list[str] = []
        self.headers: list[httpx.Headers] = []
        self._body = body
        self._content_type = content_type
        self.status = 200
        self.raises: Exception | None = None

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requested.append(str(request.url))
        self.headers.append(request.headers)
        if self.raises is not None:
            raise self.raises
        # The body is keyed on the URL so two faces of one card cannot answer identically —
        # c3-1's R3 finding was that identical fixtures prove nothing.
        body = self._body + str(request.url).encode().split(b"/")[-1]
        return httpx.Response(
            self.status, content=body, headers={"content-type": self._content_type}
        )

    def body_for(self, url: str) -> bytes:
        """The exact bytes this recorder answers *url* with."""
        return self._body + url.encode().split(b"/")[-1]


@pytest.fixture
def cdn(monkeypatch):
    """Replace the outbound transport for the duration of one test.

    Patches the **factory**, not the client: the lifespan calls
    ``images.build_image_client()`` on startup, so a test that swapped ``app.state.image_client``
    beforehand would have it overwritten. Patching here means the app under test builds its own
    client exactly as production does, and only its socket layer is fictional.
    """
    recorder = Recorder()
    real = images.build_image_client
    monkeypatch.setattr(
        images,
        "build_image_client",
        lambda **kwargs: real(transport=httpx.MockTransport(recorder.handle)),
    )
    return recorder


# =============================================================================================
# AC 8: each of the four measured shapes, against a real fixture card
# =============================================================================================


class TestTheFourShapes:
    """35,036 + 368 + 2,778 + 79 = 38,261. Every one of them has a named test."""

    async def test_shape_a_serves_the_top_level_image(self, image_shapes, lifespan_client, cdn):
        # 35,036 rows: `image_uris` present, `card_faces` null.
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert response.status_code == 200
        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]]
        assert response.content == cdn.body_for(_TOP_LEVEL_IMAGES["normal"])
        assert response.headers["content-type"] == "image/jpeg"

    async def test_shape_b_serves_the_top_level_image_at_face_zero(
        self, image_shapes, lifespan_client, cdn
    ):
        """368 rows. A split card has faces AND one image — the halves share one artwork.

        This is the case the epic calls *"falls out as single-image automatically"*, and it only
        falls out because the resolver keys on per-face ``image_uris`` rather than on the presence
        of ``card_faces``.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SPLIT_FACE_ID))

        assert response.status_code == 200
        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]]
        assert response.content == cdn.body_for(_TOP_LEVEL_IMAGES["normal"])

    async def test_shape_b_has_no_face_one(self, image_shapes, lifespan_client, cdn):
        """`face=1` on a split card is OUT OF RANGE, not "the other half"."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=SPLIT_FACE_ID), params={"face": 1}
            )

        assert response.status_code == 404
        assert response.json() == {"reason": "no_image_data"}
        assert cdn.requested == []

    async def test_shape_c_serves_a_different_image_per_face(
        self, image_shapes, lifespan_client, cdn
    ):
        """2,778 rows — and the two faces must be told apart on the BYTES, not just the status.

        c3-1's R3 finding: nothing tied a nested value to its source because every fixture was
        identical on the asserted fields. If this test only checked ``200``, a resolver that
        always returned face 0 would pass it.
        """
        async with lifespan_client(build_app()) as client:
            front = await client.get(
                _IMAGE_PATH.format(scryfall_id=MULTI_FACE_ID), params={"face": 0}
            )
            back = await client.get(
                _IMAGE_PATH.format(scryfall_id=MULTI_FACE_ID), params={"face": 1}
            )

        assert front.status_code == back.status_code == 200
        assert cdn.requested == [
            "https://cards.scryfall.io/normal/front/f.jpg?1700000101",
            "https://cards.scryfall.io/normal/back/b.jpg?1700000201",
        ]
        assert front.content != back.content
        assert front.content == cdn.body_for(cdn.requested[0])
        assert back.content == cdn.body_for(cdn.requested[1])

    async def test_shape_d_answers_no_image_data(self, image_shapes, lifespan_client, cdn):
        """79 rows: faces present, no images anywhere. Ordinary, and not an error in the log."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=NO_IMAGE_ID))

        assert response.status_code == 404
        assert response.json() == {"reason": "no_image_data"}
        assert cdn.requested == []

    async def test_the_schema_only_shape_answers_no_image_data(
        self, image_shapes, lifespan_client, cdn
    ):
        """0 rows in the corpus, permitted by the schema — behaviour known, not assumed."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SCHEMA_ONLY_ID))

        assert response.status_code == 404
        assert response.json() == {"reason": "no_image_data"}

    async def test_a_five_faced_card_serves_every_face(self, image_shapes, lifespan_client, cdn):
        """The face index is not capped at 1: 2 -> 3,222 · 3 -> 2 · 5 -> 1 in the real corpus."""
        async with lifespan_client(build_app()) as client:
            served = [
                await client.get(_IMAGE_PATH.format(scryfall_id=MANY_FACE_ID), params={"face": n})
                for n in range(5)
            ]
            beyond = await client.get(
                _IMAGE_PATH.format(scryfall_id=MANY_FACE_ID), params={"face": 5}
            )

        assert [r.status_code for r in served] == [200] * 5
        assert len({r.content for r in served}) == 5, "five faces must serve five distinct images"
        assert beyond.status_code == 404
        assert beyond.json() == {"reason": "no_image_data"}


# =============================================================================================
# AC 9: the no-image case takes precedence, and no fetch is ever attempted for it
# =============================================================================================


class TestNoImagePrecedence:
    """A card with no image data reports that, whatever face was asked for."""

    async def test_a_no_image_card_asked_for_face_seven_reports_no_image_data(
        self, image_shapes, lifespan_client, cdn
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=NO_IMAGE_ID), params={"face": 7}
            )

        assert response.status_code == 404
        assert response.json() == {"reason": "no_image_data"}

    async def test_no_fetch_is_attempted_for_a_card_with_no_image_data(
        self, image_shapes, lifespan_client, cdn
    ):
        """AD-11: the backend never guesses at a URL for a card that has none."""
        async with lifespan_client(build_app()) as client:
            await client.get(_IMAGE_PATH.format(scryfall_id=NO_IMAGE_ID))

        assert cdn.requested == []

    async def test_the_same_recorder_does_see_a_card_that_fetches(
        self, image_shapes, lifespan_client, cdn
    ):
        """NON-VACUITY PAIRING for the assertion above, from the same recorder.

        An empty ``requested`` list proves nothing if the transport was never reachable at all —
        a broken seam and a correctly-refused fetch look identical from there.
        """
        async with lifespan_client(build_app()) as client:
            await client.get(_IMAGE_PATH.format(scryfall_id=NO_IMAGE_ID))
            assert cdn.requested == []
            await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]]


# =============================================================================================
# AC 3, AC 4: the parameter contract
# =============================================================================================


class TestParameterContract:
    """``size`` is a closed set, ``face`` a non-negative integer, both with defaults."""

    @pytest.mark.parametrize("size", ["small", "normal", "large", "png", "art_crop", "border_crop"])
    async def test_every_measured_size_is_accepted_and_selects_its_own_url(
        self, image_shapes, lifespan_client, cdn, size
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": size}
            )

        assert response.status_code == 200
        # Every fixture URL is distinct, so this fails if `size` is ignored — which a route that
        # hardcoded `normal` would otherwise pass six times over.
        assert cdn.requested == [_TOP_LEVEL_IMAGES[size]]

    @pytest.mark.parametrize("size", ["huge", "NORMAL", "", "normal ", "art-crop", "thumbnail"])
    async def test_an_unrecognised_size_is_400_from_the_shipped_handler(
        self, image_shapes, lifespan_client, cdn, size
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": size}
            )

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}
        assert cdn.requested == []

    async def test_no_query_at_all_means_the_normal_size_front_face(
        self, image_shapes, lifespan_client, cdn
    ):
        """The request c4-4 makes a hundred times per deck."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=MULTI_FACE_ID))

        assert response.status_code == 200
        assert cdn.requested == ["https://cards.scryfall.io/normal/front/f.jpg?1700000101"]

    # `" 1"` is deliberately absent: Pydantic strips surrounding whitespace before coercing an
    # int, so it is a VALID 1 rather than malformed. Recorded rather than silently dropped —
    # a reader adding it back should know it was measured, not overlooked.
    @pytest.mark.parametrize("face", ["-1", "-999", "1.5", "abc", "", "0x1"])
    async def test_a_negative_or_non_integer_face_is_400(
        self, image_shapes, lifespan_client, cdn, face
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"face": face}
            )

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}
        assert cdn.requested == []

    async def test_a_large_but_valid_face_is_404_not_400(self, image_shapes, lifespan_client, cdn):
        """No upper bound in the TYPE: the bound is the resolved list, and exceeding it is
        information (this card has fewer faces), not malformation."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"face": 999}
            )

        assert response.status_code == 404
        assert response.json() == {"reason": "no_image_data"}

    async def test_a_malformed_id_is_400_with_no_code_in_the_route(
        self, image_shapes, lifespan_client, cdn
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id="not-a-uuid"))

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_trailing_newline_id_is_refused_by_the_regex_engine(
        self, image_shapes, lifespan_client, cdn
    ):
        """Pinned by name, because the guarantee comes from Pydantic's engine, not the anchor.

        Python's ``re`` matches ``$`` *before* a trailing newline, so under ``re`` this spelling
        would validate, miss and answer ``404`` instead of ``400``. Pydantic 2.12 defaults to the
        Rust engine, where ``$`` is end-of-input. Anything that changes the engine reopens it
        silently — hence a test that names the spelling rather than trusting the pattern.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(f"/api/card-image/{SINGLE_FACE_ID}%0A")

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}

    async def test_an_unknown_but_well_formed_id_is_card_not_found(
        self, image_shapes, lifespan_client, cdn
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=ABSENT_ID))

        assert response.status_code == 404
        assert response.json() == {"reason": "card_not_found"}
        assert cdn.requested == []


# =============================================================================================
# AC 5: the 503-before-400 precedence, re-measured for THIS route
# =============================================================================================


class TestDatabaseStatesOutrankParameterValidation:
    """Dependencies resolve before parameter validation is reported. Both orders pinned."""

    async def test_a_bogus_size_against_an_absent_database_answers_503(
        self, tmp_path, monkeypatch, lifespan_client, cdn
    ):
        _point_at(monkeypatch, tmp_path / "missing.db")

        async with lifespan_client(build_app()) as client:
            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": "bogus"}
            )

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_the_same_bogus_size_against_a_ready_database_answers_400(
        self, image_shapes, lifespan_client, cdn
    ):
        """The other half of the ordering, from the same request shape — without it the test
        above would pass against a route that answered 503 unconditionally."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": "bogus"}
            )

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_schema_only_database_is_not_initialized(
        self, tmp_path, monkeypatch, lifespan_client, cdn
    ):
        from src.data.database import create_engine, init_database

        empty = _point_at(monkeypatch, tmp_path / "empty.db")
        engine = create_engine(f"sqlite+aiosqlite:///{empty.as_posix()}")
        try:
            await init_database(engine)
        finally:
            await engine.dispose()

        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}


# =============================================================================================
# AC 10, AC 12, AC 13: what goes out on the wire
# =============================================================================================


class TestTheOutboundRequest:
    """The only URL ever requested is one that came out of the local row."""

    async def test_no_live_scryfall_metadata_call_is_ever_made(
        self, image_shapes, lifespan_client, cdn
    ):
        """Behavioural half of AC 10: every URL asked for is a value from the card's own row."""
        stored = set(_TOP_LEVEL_IMAGES.values()) | {
            "https://cards.scryfall.io/normal/front/f.jpg?1700000101",
            "https://cards.scryfall.io/normal/back/b.jpg?1700000201",
        }

        async with lifespan_client(build_app()) as client:
            for card_id in (SINGLE_FACE_ID, SPLIT_FACE_ID, MULTI_FACE_ID):
                await client.get(_IMAGE_PATH.format(scryfall_id=card_id))
            await client.get(_IMAGE_PATH.format(scryfall_id=MULTI_FACE_ID), params={"face": 1})

        assert cdn.requested, "the recorder saw nothing; this test would assert vacuously"
        assert set(cdn.requested) <= stored
        assert not any("api.scryfall.com" in url for url in cdn.requested)

    async def test_the_user_agent_names_this_application(self, image_shapes, lifespan_client, cdn):
        async with lifespan_client(build_app()) as client:
            await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        agent = cdn.headers[0]["user-agent"]
        assert "Artificial-Planeswalker" in agent
        assert "github.com/Sathias23" in agent
        assert cdn.headers[0]["accept"].startswith("image/")

    async def test_a_row_pointing_off_the_allow_list_is_a_fetch_failure_never_a_fetch(
        self, ready_db, lifespan_client, cdn, monkeypatch
    ):
        """The row is third-party data. "The database said so" is not a reason to open a socket."""
        from tests.unit.companion.conftest import _card, _seed

        hostile = _uuid("bad")

        async def seeder(session):
            session.add(
                _card(
                    hostile,
                    "Hostile Row",
                    image_uris={"normal": "https://169.254.169.254/latest/meta-data/"},
                )
            )
            await session.commit()

        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=hostile))

        assert response.status_code == 502
        assert response.json() == {"reason": "image_fetch_failed"}
        assert cdn.requested == [], "a disallowed origin must be refused BEFORE the request"

    async def test_the_measured_errors_scryfall_com_cards_are_served_not_refused(
        self, ready_db, lifespan_client, cdn
    ):
        """Sparkspitter, Ondu Champion and Gorehorn Minotaurs — three real ids, by name.

        All three store ``https://errors.scryfall.com/soon.jpg`` in all six size keys (18 of the
        245,760 stored URLs). Q5 put that host on the allow-list precisely so these are not
        reported as failures for data that is exactly as Scryfall shipped it.
        """
        from tests.unit.companion.conftest import _card, _seed

        real_ids = [
            "0070bbf6-fdee-44ec-bfb8-3e99d6338e6e",  # Sparkspitter
            "7206cdd5-3f86-4415-a236-9b331b4ac42a",  # Ondu Champion
            "7dc76d47-e9c1-4bcf-9134-70052aafa67f",  # Gorehorn Minotaurs
        ]
        placeholder = {key: "https://errors.scryfall.com/soon.jpg" for key in _TOP_LEVEL_IMAGES}

        async def seeder(session):
            for index, card_id in enumerate(real_ids):
                session.add(_card(card_id, f"Errors Card {index}", image_uris=placeholder))
            await session.commit()

        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            responses = [
                await client.get(_IMAGE_PATH.format(scryfall_id=card_id)) for card_id in real_ids
            ]

        assert [r.status_code for r in responses] == [200, 200, 200]
        assert cdn.requested == ["https://errors.scryfall.com/soon.jpg"] * 3


# =============================================================================================
# AC 14: upstream failures, mapped
# =============================================================================================


class TestUpstreamFailures:
    """Every one answers ``502 image_fetch_failed`` and none returns a substitute image."""

    @pytest.fixture
    def _served(self, image_shapes):
        return _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

    async def test_a_cdn_404(self, _served, lifespan_client, cdn):
        cdn.status = 404

        async with lifespan_client(build_app()) as client:
            response = await client.get(_served)

        assert response.status_code == 502
        assert response.json() == {"reason": "image_fetch_failed"}

    async def test_a_cdn_500(self, _served, lifespan_client, cdn):
        cdn.status = 500

        async with lifespan_client(build_app()) as client:
            response = await client.get(_served)

        assert response.status_code == 502
        assert response.json() == {"reason": "image_fetch_failed"}

    async def test_a_timeout(self, _served, lifespan_client, cdn):
        cdn.raises = httpx.ReadTimeout("too slow")

        async with lifespan_client(build_app()) as client:
            response = await client.get(_served)

        assert response.status_code == 502
        assert response.json() == {"reason": "image_fetch_failed"}

    async def test_a_connect_failure(self, _served, lifespan_client, cdn):
        cdn.raises = httpx.ConnectError("no route to host")

        async with lifespan_client(build_app()) as client:
            response = await client.get(_served)

        assert response.status_code == 502
        assert response.json() == {"reason": "image_fetch_failed"}

    async def test_a_non_image_content_type(self, image_shapes, lifespan_client, monkeypatch):
        recorder = Recorder(body=b"<html>nope</html>", content_type="text/html")
        real = images.build_image_client
        monkeypatch.setattr(
            images,
            "build_image_client",
            lambda **kwargs: real(transport=httpx.MockTransport(recorder.handle)),
        )

        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert response.status_code == 502
        assert response.json() == {"reason": "image_fetch_failed"}
        # The body the upstream sent must not reach the caller: serving foreign HTML from the
        # companion's own origin is the failure this check exists to prevent.
        assert b"<html>" not in response.content

    async def test_a_failure_never_returns_a_substitute_image(self, _served, lifespan_client, cdn):
        """AD-11, non-negotiable: no grey rectangle, no 1x1 pixel, no generic card back."""
        cdn.status = 503

        async with lifespan_client(build_app()) as client:
            response = await client.get(_served)

        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"reason": "image_fetch_failed"}
        assert len(response.content) < 100, "an error body is a token, not a picture"


# =============================================================================================
# AC 15: caching
# =============================================================================================


class TestCacheHeaders:
    """A served image is cacheable for a year; a failure is not cached at all."""

    async def test_a_served_image_is_immutable_for_a_year(self, image_shapes, lifespan_client, cdn):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"

    async def test_a_served_image_carries_nosniff(self, image_shapes, lifespan_client, cdn):
        """The body and its type are an upstream's word, not ours (review 2026-08-01).

        Without it a browser may sniff a mislabelled body into something executable on this
        app's own origin — `fetch_image` refuses SVG by name, and this is the belt to that brace.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert response.headers["x-content-type-options"] == "nosniff"

    @pytest.mark.parametrize(
        ("card_id", "status"),
        [(NO_IMAGE_ID, 404), (ABSENT_ID, 404)],
    )
    async def test_a_failure_is_never_cached(
        self, image_shapes, lifespan_client, cdn, card_id, status
    ):
        """One flaky minute must not leave a permanently broken tile in an open tab."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=card_id))

        assert response.status_code == status
        assert response.headers["cache-control"] == "no-store"

    async def test_a_fetch_failure_is_never_cached(self, image_shapes, lifespan_client, cdn):
        cdn.status = 500

        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert response.status_code == 502
        assert response.headers["cache-control"] == "no-store"

    def test_the_image_constant_agrees_with_the_static_surfaces(self):
        """Same value, two reasons, one gate — see ``IMAGE_CACHE_CONTROL``'s docstring.

        A fingerprinted asset is immutable because its name changes; an image is immutable because
        AD-11 accepts staleness. If either reason ever stops holding, this is where the divergence
        becomes visible rather than silent.
        """
        assert images.IMAGE_CACHE_CONTROL == _IMMUTABLE_CACHE_CONTROL


# =============================================================================================
# AC 16, AC 23: what is deliberately absent
# =============================================================================================


_IMAGES_MODULE = Path(__file__).resolve().parents[3] / "src" / "companion" / "app" / "images.py"

_BANNED_IDENTIFIERS = frozenset(
    {
        # NOT c3-8's reservation any more — c3-8 SHIPPED, and these stay banned. See below.
        "functools.cache",
        "functools.lru_cache",
    }
)
"""What ``images.py`` must not reach for, keyed on the resolved NAME rather than the spelling.

An identifier set over the parsed AST, not a substring scan over the source text, and the
difference is the whole design of this guard: this module's docstring *names* the disk cache and
``data_dir()`` in prose — deliberately, because the absences are decisions — so a text scan fires
on the documentation of the rule instead of on a breach of it. (Measured: the first version of
this test did exactly that, on its own module docstring.) The frontend hit the same wall at c3-2
and answered it the same way, by stripping comments before matching.

**c3-7 removed the disk-cache family, which was eight of the ten names** (2026-08-01), following
the procedure c3-6 wrote down by doing it. ``mkdir``, ``makedirs``, ``open``, ``write_bytes``,
``write_text``, ``data_dir``, ``NamedTemporaryFile`` and ``replace`` were banned here under the
comment *"c3-7's disk cache"*; that story then shipped the disk cache, so every one of them became
a fence around the thing it was built to hold back. c3-6 had already removed a third family
(``Semaphore``, ``BoundedSemaphore``, ``sleep``, ``Lock``) for the same reason.

**c3-8 SHIPPED THE NEGATIVE CACHE AND THESE TWO NAMES STAY BANNED — the first family in this epic
that the story owning it did not remove** (Q5, Brad 2026-08-02). That is deliberately against the
pattern its two predecessors set, and the reason is that this family was never the same kind of
ban as theirs.

``Semaphore`` and ``mkdir`` were banned **because c3-6 and c3-7 had not happened yet**. The day
each shipped, its ban fenced the very thing that had just been built, so removal was not merely
allowed — it was required, or the guard would have been refusing the design. **These two were
banned for that reason *and* for a second one that outlives the story:**

* ``functools.cache`` and ``functools.lru_cache`` **cannot express a TTL**, so a remembered failure
  would never expire — the permanently-broken-tile defect AD-11's *"with backoff"* exists to
  prevent, and a tile no recovery could ever clear; and
* ``cache_clear()`` **is all-or-nothing**, so AC 7's *clear this one key on recovery* — the clause
  that makes a recovered key start its next failure at the base delay rather than the escalated one
  — is unimplementable on top of either.

Both are still true the day :class:`~src.companion.app.images.NegativeCache` ships. **The fence is
therefore not around the thing that was built**, which is the whole test c3-6's procedure applies,
and this stops being a *reservation for an unwritten story* and becomes a *permanent ruling with a
stated reason*. A ruling is stronger than a reservation, and restating it cost one paragraph where
retiring it would have cost four reworked pairings.

**Retiring it and pointing at the new positive gate would have LOST coverage rather than replacing
it** — the first time that would have been true in this epic. ``test_images.py``'s
``TestExactlyOneNegativeCache`` says *"there is exactly one negative cache, in the lifespan"* and
``TestTheMapIsBounded`` says *"and it is bounded"*. Neither says *"and it is not a ``functools``
memoisation"*: a bounded single instance built on ``lru_cache`` satisfies both completely while
reintroducing exactly the defect this ban prevents. The claims are orthogonal, so c3-8 adds the
positive gate **on top of** this ban rather than instead of it — which is what AC 18 and AC 19
together actually ask for.

**The two survivors are re-keyed onto** ``functools`` **rather than left as bare tokens, and that
is a strengthening rather than a courtesy to this story.** A bare ``cache`` cannot tell
``functools.cache`` the decorator from ``cache`` the local variable — and after c3-7 this module
legitimately holds cache vocabulary throughout, so a bare-token ban would fire on the disk cache's
own accessor. Resolving through the import (``from functools import cache as memo`` and
``import functools as ft; ft.cache``) is both narrower where it was wrong and *wider* where it
matters: the alias spellings a real negative cache would most plausibly arrive under are now
caught, and neither was before. See :func:`_negative_cache_reaches`.

**The removals are not a loss of coverage, because each family's replacement is stronger than the
ban was.** In order:

* the pacer's is *"``src/companion`` constructs exactly **one** pacer"*
  (``test_images.py::TestExactlyOnePacer``);
* the blocking-wait half became ``TestTheLoopIsNeverBlocked``, re-keyed onto *synchronous* waits
  resolved through import aliases, because a ban on ``sleep`` by name could not survive this
  module gaining an injected ``asyncio.sleep``;
* and **c3-7's is two gates, not one**: every rename-into-place site in ``src/companion`` is
  accounted for by module (``test_images.py::TestExactlyOneImageWriteSite`` — a *ban* on
  ``replace`` could only ever say "not here", where the scan says "here, and nowhere else"), and
  every file-I/O call site must be lexically inside a non-``async`` helper reached only through
  ``asyncio.to_thread`` (``test_images.py::TestFileIoNeverRunsOnTheLoop``), which is a property
  the old ban could not express at all.
"""


def _negative_cache_reaches(path: Path) -> set[str]:
    """Return the ``functools`` memoisation spellings the module at *path* reaches for.

    c3-8's fence, resolved through imports rather than matched as a bare token — c3-3's headline
    finding was a guard that caught 0 of 12 planted evasions because every family was keyed on the
    syntax its own firing test happened to use. The three spellings a negative cache would arrive
    under are all resolved here:

    * ``from functools import cache`` / ``lru_cache``, aliased or not — caught at the import, so
      no local name has to be tracked;
    * ``import functools`` followed by ``functools.cache(...)``;
    * ``import functools as ft`` followed by ``ft.lru_cache(...)`` — the module alias resolved.

    Args:
        path: The module to inspect.

    Returns:
        The dotted spellings found, e.g. ``{"functools.lru_cache"}``.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    members = {"cache", "lru_cache"}
    aliases: dict[str, str] = {}
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module == "functools":
            found.update(f"functools.{alias.name}" for alias in node.names if alias.name in members)
            if any(alias.name == "*" for alias in node.names):
                # A star-import makes a bare `@cache` reachable with no bound name left to track.
                found.update(f"functools.{member}" for member in members)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in members
            and isinstance(node.value, ast.Name)
            and aliases.get(node.value.id, node.value.id) == "functools"
        ):
            found.add(f"functools.{node.attr}")
    return found


def _identifiers_and_strings(path: Path) -> tuple[set[str], list[str]]:
    """Return every identifier and every string literal in the module at *path*.

    Parsed, never imported, and **prose is excluded by position rather than by content**: any
    string that is a bare expression statement is documentation, not a value. That one rule covers
    module, class and function docstrings *and* the attribute docstrings this module uses under
    most of its constants — while a string that is actually assigned, passed or compared is kept,
    which is the only kind a breach can hide in.

    Args:
        path: The module to inspect.

    Returns:
        The set of names (bare, attribute and imported) and the list of non-documentation strings.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    documentation = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    names: set[str] = set()
    strings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(f"{node.module or ''}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in documentation:
                strings.append(node.value)
    return names, strings


class TestNothingThisStoryDoesNotOwn:
    """What remains banned, and why it stayed banned through the story that owned it.

    **Renamed in spirit rather than in fact.** Two of the three claims below are c3-5's originals;
    the first one changed its meaning entirely at c3-8 and its docstring says so.
    """

    def test_the_negative_cache_is_not_built_on_a_functools_memoisation(self):
        """**Re-aimed at c3-8, and the old name would have been a lie the day this shipped.**

        This assertion used to be ``test_no_negative_cache_is_built`` — a reservation, holding the
        mechanism for the story that owned it. c3-8 shipped that mechanism, so the old claim became
        false by construction and something had to change here. What it did **not** become is
        *retired*: the two names are still the wrong tool (see :data:`_BANNED_IDENTIFIERS`), so the
        claim narrowed from *"there is no negative cache"* to *"the negative cache is not built on
        one of these"*, which is the half that survives and always was the load-bearing half.

        The scan is unchanged and needed no edit — it always resolved ``functools`` through the
        import, never the mechanism's name — so the module can now hold ``NegativeCache``,
        ``negative_cache`` and cache vocabulary throughout while this stays exact.
        """
        breaches = sorted(_negative_cache_reaches(_IMAGES_MODULE) & _BANNED_IDENTIFIERS)

        assert not breaches, (
            f"images.py reaches for {breaches}. Neither can express a TTL, so a remembered failure "
            "would never expire; and cache_clear() is all-or-nothing, so clearing ONE key on "
            "recovery is unimplementable on it. Both are still true now that c3-8 has shipped, "
            "which is why this family was not retired with its story (Q5, Brad 2026-08-02)."
        )

    def test_the_shipped_negative_cache_really_is_the_thing_this_ban_is_about(self):
        """NON-VACUITY for the ban's *relevance*, which the silence above cannot establish.

        A ban on a mechanism nobody builds is satisfied trivially — and until this story that was
        precisely the situation, so the assertion above passed for a reason that had nothing to do
        with its stated one. Now that ``images.py`` genuinely holds a memoisation-shaped thing, this
        pins that the banned names are being avoided **by a real alternative** rather than by the
        absence of any implementation at all.

        Keyed on the two capabilities the ban is justified by, not on the class's shape: a TTL that
        expires, and a clear that addresses one key.
        """
        assert hasattr(images, "NegativeCache"), "the ban outlived the mechanism it was about"

        cache = images.NegativeCache(clock=lambda: 0.0)
        cache.record_failure("aaa", "normal", 0)
        cache.record_failure("bbb", "normal", 0)
        cache.clear("aaa", "normal", 0)

        assert cache.is_backing_off("aaa", "normal", 0) is False
        assert cache.is_backing_off("bbb", "normal", 0) is True, (
            "clearing one key cleared its sibling too — which is exactly what cache_clear() does, "
            "and exactly why functools is banned here"
        )

    def test_the_module_imports_nothing_from_the_banned_write_path(self):
        """Source-level half of AC 10. ``test_import_boundary.py`` bans this repo-wide; this
        states it for the one module most likely to want it."""
        names, _ = _identifiers_and_strings(_IMAGES_MODULE)

        assert not any(name.startswith("src.data.importers") for name in names)

    def test_no_scryfall_metadata_host_is_reachable_in_code(self):
        """The other half of AC 10: no live metadata call, asserted over string literals."""
        _, strings = _identifiers_and_strings(_IMAGES_MODULE)

        assert not [s for s in strings if "api.scryfall.com" in s]

    def test_the_scan_sees_a_planted_breach_of_each_family(self, tmp_path):
        """NON-VACUITY PAIRING, and it plants an evasion against BOTH halves.

        c3-3's headline finding: a guard caught 0 of 12 planted evasions because every family was
        keyed on the syntax its own firing tests used. So the plant below is deliberately *not*
        spelled the way a naive scan would look for it — the write arrives as a method call on a
        local, the cache as an aliased decorator, and the host inside a split f-string.

        **Two of the three plants are now names that are no longer banned, and that is
        deliberate** — ``Semaphore`` since c3-6, ``mkdir`` since c3-7. Seeing either is no longer
        a *breach*: this module owns a pacer and a disk cache now. But the claim this assertion
        makes is about the **scanner**, not about the ban — an alias-blind scanner, or one that
        could not see a method call on a local, would let a real breach through under the
        identical spelling, and c3-8's family is the one still depending on that property. So both
        names are asserted against ``names`` and neither is asserted against
        ``_BANNED_IDENTIFIERS``, which is exactly the distinction each removal turned on.

        **Unchanged at c3-8, and that is the finding rather than the omission** (2026-08-02). This
        is the one pairing of the four that Q5's ruling left genuinely untouched: its ``functools``
        arm is the only one still tied to a live ban, and it stayed live. The two retired arms
        continue to prove the *scanner's* properties, which is what they were re-scoped to at c3-6
        and c3-7 — and those properties are now load-bearing for a **shipped** mechanism rather
        than a hypothetical one, since ``images.py`` today genuinely holds cache vocabulary that a
        bare-token scan would trip over.
        """
        planted = tmp_path / "planted.py"
        planted.write_text(
            "import asyncio as aio\n"
            "from functools import lru_cache as memoize\n"
            "from src.data.importers.scryfall_api import fetch\n"
            "\n"
            "GATE = aio.Semaphore(4)\n"
            "BASE = 'api.scryfall.com'\n"
            "URL = f'https://{BASE}/cards/named'\n"
            "\n"
            "\n"
            "@memoize\n"
            "def go(path):\n"
            "    path.mkdir(parents=True, exist_ok=True)\n",
            encoding="utf-8",
        )

        names, strings = _identifiers_and_strings(planted)

        assert "Semaphore" in names, (
            "the scanner missed an aliased import — the property c3-7's and c3-8's families still "
            "depend on, even though a semaphore is no longer a breach"
        )
        assert "Semaphore" not in _BANNED_IDENTIFIERS, (
            "c3-6 shipped the pacer; banning it here would fence the thing that was built"
        )
        assert "mkdir" in names, (
            "the scanner missed a method call on a local — the property c3-8's family still "
            "depends on, even though a mkdir is no longer a breach now that c3-7 has shipped the "
            "disk cache"
        )
        assert "mkdir" not in _BANNED_IDENTIFIERS, (
            "c3-7 shipped the disk cache; banning it here would fence the thing that was built"
        )
        assert "functools.lru_cache" in names or "lru_cache" in names, (
            "the negative-cache family missed a renamed decorator import"
        )
        assert any(name.startswith("src.data.importers") for name in names)
        assert [s for s in strings if "api.scryfall.com" in s], (
            "the host scan missed a split f-string — the exact evasion c3-3 found 12 of"
        )

    def test_a_planted_breach_of_a_surviving_family_actually_fires_the_ban(self, tmp_path):
        """The firing half, over the set itself — the surviving family still has teeth.

        Separate from the scanner test above because c3-6 split the two claims apart: *"the
        scanner sees it"* and *"the ban refuses it"* used to be one assertion, and conflating them
        is what would have made removing the pacer family look like removing coverage.

        **This plant was re-aimed at c3-7** (2026-08-01). It used to plant a ``NamedTemporaryFile``
        write, which this story unbanned — leaving the assertion as ``set() == set()``, a test that
        passes *because* it now proves nothing. That is the failure mode a firing test degrades
        into silently, so it is re-planted on the family that survives, in the aliased spelling the
        bare-token version of this ban could never have caught.

        **c3-8 left the plant alone and added the guard below instead** (2026-08-02). Q5 kept the
        family, so for the first time in this epic a story's arrival did not retire the name this
        test plants — there was nothing to re-aim. What that exposed is that "nothing to re-aim"
        and "silently degraded to ``set() == set()``" look **identical from inside this test**, and
        c3-7 only caught its own degradation by noticing. So the non-emptiness of the set is now
        asserted explicitly rather than relied on: whichever story finally empties this frozenset
        gets a red here instead of a green that proves nothing.
        """
        assert _BANNED_IDENTIFIERS, (
            "the ban list is empty, so the assertion below is `set() == set()` — a test that "
            "passes BECAUSE it proves nothing. Whichever story emptied it owes this file a "
            "positive gate that is stronger than the ban, per c3-6's written procedure."
        )

        planted = tmp_path / "memoises.py"
        planted.write_text(
            "from functools import lru_cache as memoize\n"
            "\n"
            "\n"
            "@memoize(maxsize=512)\n"
            "def known_bad(url):\n"
            "    return None\n",
            encoding="utf-8",
        )

        assert _negative_cache_reaches(planted) & _BANNED_IDENTIFIERS == {"functools.lru_cache"}

    def test_the_ban_catches_the_module_alias_spelling_too(self, tmp_path):
        """The second evasion, and the one the retired bare-token ban was blind to.

        ``import functools as ft; @ft.cache`` reaches exactly the same decorator under a name no
        member list contains. c3-3's lesson is that a family keyed on the syntax its own firing
        test uses catches nothing else — so the firing test above uses the ``from`` form and this
        one uses the attribute form, deliberately.

        **Still both members, still both live, after c3-8** (2026-08-02). The two spellings are
        asserted by two separate tests rather than one parametrised pair precisely so that retiring
        *one* member could never silently weaken the other's proof.
        """
        assert _BANNED_IDENTIFIERS >= {"functools.cache"}, (
            "`functools.cache` left the ban list; this assertion is now vacuous. Q5 ruled it a "
            "PERMANENT ruling rather than a reservation — removing it needs a stated reason that "
            "survives the TTL and single-key-clear arguments, not merely a story's turn."
        )

        planted = tmp_path / "aliased.py"
        planted.write_text(
            "import functools as ft\n\n\n@ft.cache\ndef known_bad(url):\n    return None\n",
            encoding="utf-8",
        )

        assert _negative_cache_reaches(planted) & _BANNED_IDENTIFIERS == {"functools.cache"}

    def test_the_scan_ignores_prose_that_merely_names_the_banned_things(self, tmp_path):
        """…and the other direction, which is what the first version of this guard got wrong.

        A module that *documents* the absence must stay green. Without this pairing, the guard
        above could be satisfied by deleting the docstrings that explain the design.

        **The planted sentence has now been rewritten twice, and for the same reason both times.**
        At c3-6 it read *"No Semaphore here — the pacer is c3-6's"*, which stopped being true the
        day that story shipped. At c3-7 it read *"Nothing here calls mkdir or data_dir, and there
        is no lru_cache"* — two thirds of which stopped being a ban the day *this* story shipped,
        leaving the plant proving prose-immunity for names that were no longer banned. A plant
        nobody rewrites is how a test file starts asserting yesterday's design.

        **Reworked at the 2026-08-01 review, in both directions.** The claim this docstring used
        to make — that ``images.py``'s own docstring "names ``lru_cache``" — was false (it does
        not, verified by grep), and the functools half of the assertion could never fail anyway:
        ``_negative_cache_reaches`` resolves imports and attributes, so prose is structurally
        invisible to it, and asserting its silence alone proved nothing. What CAN fail is the
        **discrimination** now planted: the identical ``functools`` spelling fires as *code* and
        stays silent as *prose*, from the same test — so the silence is proven against a scanner
        demonstrably capable of firing. The host-string half keeps its claim, which was always
        the real prose-immunity property: ``_identifiers_and_strings`` excludes documentation by
        *position*, and a scan that included docstrings would fire on the plant below.

        **Rewritten a THIRD time at c3-8** (2026-08-02), and for the third distinct reason. The
        previous plant read *"No negative cache here — functools.cache and lru_cache are both
        c3-8's."* Both **names** are still banned, so unlike its two predecessors this plant did not
        go stale at the ban — but the **sentence** did: ``images.py`` now holds a negative cache, so
        a plant asserting there is none documents a design that no longer exists. That is the same
        rot in a different place, and the reason this docstring's own warning is quoted rather than
        paraphrased: *a plant nobody rewrites is how a test file starts asserting yesterday's
        design.* The replacement says the thing that is now true and will stay true — the mechanism
        exists and is deliberately **not** built on these two.
        """
        documented = tmp_path / "documented.py"
        documented.write_text(
            '"""The negative cache here is a dict and a clock — deliberately NOT '
            'functools.cache or lru_cache, neither of which can expire an entry."""\n'
            "\n"
            "VALUE = 1\n"
            '"""Not a call to api.scryfall.com either; this is an attribute docstring."""\n',
            encoding="utf-8",
        )
        spelled_as_code = tmp_path / "spelled_as_code.py"
        spelled_as_code.write_text(
            "import functools\n\n\n@functools.cache\ndef known_bad(url):\n    return None\n",
            encoding="utf-8",
        )

        _, strings = _identifiers_and_strings(documented)

        assert not (_negative_cache_reaches(documented) & _BANNED_IDENTIFIERS)
        assert _negative_cache_reaches(spelled_as_code) & _BANNED_IDENTIFIERS == {
            "functools.cache"
        }, "the same spelling as code must fire, or the prose silence above proves nothing"
        assert not [s for s in strings if "api.scryfall.com" in s]


# =============================================================================================
# Story c3-6: the pacer, at the level of the running app. AC 6, 7, 13; Q6.
#
# The pacer's own mechanics are proved as units in `test_images.py` on a fake clock. What can
# ONLY be proved here is what a real request does: that a queued burst does not stall the rest
# of the app, that a disconnecting browser gives its slot back, and that reading a deck fetches
# nothing at all.
# =============================================================================================


async def _until(predicate, *, what: str) -> None:
    """Spin the event loop until *predicate* holds, then return immediately.

    **This is not a rate measurement and does not violate AC 9.** The distinction is what is
    being waited for: these tests wait for the app to *reach a state* — N requests admitted, the
    permits exhausted — and then assert **exact counts** on it. Nothing here measures elapsed
    seconds; machine speed moves only how quickly the settle returns, up to the 0.5 s ceiling
    below — a bound on patience that fails loudly, not a rate assertion (review 2026-08-01: an
    earlier version of this sentence claimed no assertion would change on a slower machine, which
    the ceiling itself contradicts in the limit).

    A fixed number of ``asyncio.sleep(0)`` turns was tried first and is wrong: every request
    really does read SQLite through ``aiosqlite``'s worker thread before it reaches the pacer, so
    a bare yield count is a race against a thread rather than a deterministic settle (measured —
    the burst reached 2 of 4 permits, not 4). This returns on the first turn the condition holds,
    which in practice is a few milliseconds, and fails loudly rather than silently proceeding to
    assert on a half-arrived state.

    Args:
        predicate: Called on each turn; waiting stops when it returns true.
        what: Named in the failure, so a timeout says which state never arrived.

    Raises:
        AssertionError: The condition never became true.
    """
    for _ in range(500):
        if predicate():
            return
        await asyncio.sleep(0.001)
    raise AssertionError(f"timed out waiting for: {what}")


@pytest.fixture
def stalled_cdn(monkeypatch):
    """A CDN that answers nothing until released, plus a pacer with its spacing zeroed.

    Zeroed spacing, not a virtual clock (review 2026-08-01 — an earlier version of this line said
    "on virtual time", which is `test_images.py`'s regime, not this one): with spacing 0.0 the
    turnstile never waits at all, so these app-level tests exercise the **cap** alone, on the real
    clock. The spacing behaviour is proved in `test_images.py`, where the clock and sleep are
    injected.

    Both halves are patched at the **factory**, for the reason the ``cdn`` fixture documents: the
    lifespan builds them on startup and would overwrite anything a test put on ``app.state``
    beforehand. Patching ``images.Pacer`` is what keeps this file's runtime honest — the shipped
    0.1 s spacing would otherwise add real seconds to a burst test, which is precisely the
    slow-when-it-passes pattern AC 9 forbids.

    The **cap is left at the shipped value**: it is the thing under test here, and a test that
    quietly relaxed it would prove nothing.
    """
    # `hold=True` is what the retired `StallableCdn` did unconditionally. The consolidated fake
    # defaults to releasing immediately so the same class also serves as an ordinary fast CDN —
    # so the stall has to be asked for here, explicitly, rather than inherited from the name.
    stalled = StallableUpstream(hold=True)
    real_client = images.build_image_client
    monkeypatch.setattr(
        images,
        "build_image_client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(stalled.handle)),
    )
    real_pacer = images.Pacer
    monkeypatch.setattr(
        images,
        "Pacer",
        lambda **kwargs: real_pacer(spacing=0.0, **kwargs),
    )
    return stalled


class TestAQueuedBurstDoesNotStallTheApp:
    """AC 6, behavioural half. `async` throughout, proved by an unrelated route answering."""

    async def test_health_answers_repeatedly_while_a_burst_of_images_is_queued(
        self, image_shapes, lifespan_client, stalled_cdn
    ):
        """The epic's AC names `POST /agent/events`, which does not exist until c5-1/c5-5.

        `/health` is the honest stand-in available today, and the substitution is recorded rather
        than passed off as the same test — the literal AC (a concurrent push meeting its 250 ms
        budget while images are queued) is homed on **c10-3**, whose own AC already says exactly
        that.

        **The interleaving COUNT is what has teeth.** A test that merely asserted "/health
        answered" would pass on a serialised loop that ran it after every image completed. Five
        health probes must all complete while every image is still parked upstream — under a
        blocking pacer that number is zero, and under a serialised loop the first probe never
        returns at all.
        """
        app = build_app()
        async with lifespan_client(app) as client:
            burst = [
                asyncio.create_task(
                    client.get(
                        _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": size}
                    )
                )
                for size in ("small", "normal", "large", "png", "art_crop", "border_crop")
            ]
            # Wait on `requested`, which only ever GROWS, rather than on `in_flight`, which does
            # not. Probe (a) of this story's mutation set — the semaphore deleted — passed this
            # test in its first form: `in_flight == 4` is true for an instant on the way up from
            # 1 to 6, and by the final assertion the first four had completed and decremented it
            # back under the cap. A monotonic quantity cannot be caught mid-ramp.
            await _until(
                lambda: len(stalled_cdn.requested) >= images.FETCH_CONCURRENCY,
                what="the burst to fill the concurrency cap",
            )
            # …and then give the two that must NOT be admitted every chance to be admitted.
            # Real 1 ms turns, not bare yields, for `_until`'s own documented reason: requests
            # 5 and 6 cross aiosqlite's worker thread on their way to the semaphore, and a
            # zero-time turn gives a thread no time — 200 of them can pass before the excess
            # requests even reach the thing that must refuse them (review 2026-08-01).
            for _ in range(20):
                await asyncio.sleep(0.001)

            assert len(stalled_cdn.requested) == images.FETCH_CONCURRENCY, (
                f"{len(stalled_cdn.requested)} of 6 requests reached the CDN while none had "
                f"completed; the cap is {images.FETCH_CONCURRENCY}"
            )
            assert stalled_cdn.in_flight == images.FETCH_CONCURRENCY
            assert stalled_cdn.completed == 0, "an image finished; nothing is actually queued"

            interleaved = 0
            for _ in range(5):
                health = await client.get("/health")
                assert health.status_code == 200
                interleaved += 1

            assert interleaved == 5, (
                "the event loop was blocked: /health could not be served while image fetches "
                "were queued and in flight"
            )
            assert stalled_cdn.completed == 0, (
                "the images completed while /health ran, so they were never really queued"
            )

            stalled_cdn.release.set()
            responses = await asyncio.gather(*burst)

        assert [r.status_code for r in responses] == [200] * 6
        assert stalled_cdn.peak_in_flight <= images.FETCH_CONCURRENCY, (
            f"{stalled_cdn.peak_in_flight} simultaneous upstream requests against a cap of "
            f"{images.FETCH_CONCURRENCY}"
        )

    async def test_the_cap_bounds_what_the_route_opens_upstream(
        self, image_shapes, lifespan_client, stalled_cdn
    ):
        """AC 5 through the real route, from the transport's own accounting."""
        app = build_app()
        async with lifespan_client(app) as client:
            burst = [
                asyncio.create_task(
                    client.get(
                        _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": size}
                    )
                )
                for size in ("small", "normal", "large", "png", "art_crop", "border_crop")
            ]
            # `requested` rather than `in_flight`, for the reason the sibling test above records:
            # only a monotonic quantity is safe to wait on.
            await _until(
                lambda: len(stalled_cdn.requested) >= images.FETCH_CONCURRENCY,
                what="the burst to fill the concurrency cap",
            )
            # Give the two that should NOT be admitted every chance to be admitted anyway —
            # real 1 ms turns, for the reason the sibling test above records.
            for _ in range(20):
                await asyncio.sleep(0.001)
            admitted = len(stalled_cdn.requested)
            stalled_cdn.release.set()
            await asyncio.gather(*burst)

        assert admitted == images.FETCH_CONCURRENCY, (
            f"{admitted} requests were open against a stalled CDN; the cap is "
            f"{images.FETCH_CONCURRENCY}"
        )
        assert len(stalled_cdn.requested) == 6, "every request eventually reached the CDN"


class TestADisconnectingClientReleasesItsSlot:
    """AC 7 through the real route: a browser navigating away from a deck view, ~99 times."""

    async def test_a_cancelled_request_does_not_narrow_the_pacer(
        self, image_shapes, lifespan_client, stalled_cdn
    ):
        app = build_app()
        async with lifespan_client(app) as client:
            pacer = images.image_pacer(app)
            assert pacer is not None
            before = pacer.available_permits

            burst = [
                asyncio.create_task(
                    client.get(
                        _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": size}
                    )
                )
                for size in ("small", "normal", "large", "png", "art_crop", "border_crop")
            ]
            await _until(lambda: pacer.available_permits == 0, what="every permit to be taken")
            assert pacer.available_permits == 0

            # Two callers give up — a navigation away, twice.
            for task in burst[:2]:
                task.cancel()
            for task in burst[:2]:
                with pytest.raises(asyncio.CancelledError):
                    await task

            stalled_cdn.release.set()
            await asyncio.gather(*burst[2:])

            after = pacer.available_permits

        assert after == before, (
            f"{before - after} permits leaked across two cancelled requests — a pacer that "
            "narrows over a session of scrolling eventually serves nothing"
        )

    async def test_a_fetch_still_succeeds_after_a_cancellation(
        self, image_shapes, lifespan_client, cdn
    ):
        """The proof that matters: the NEXT request gets through."""
        app = build_app()
        async with lifespan_client(app) as client:
            doomed = asyncio.create_task(client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)))
            await asyncio.sleep(0)
            doomed.cancel()
            with pytest.raises((asyncio.CancelledError, httpx.HTTPError)):
                await doomed

            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": "large"}
            )

        assert response.status_code == 200
        assert _TOP_LEVEL_IMAGES["large"] in cdn.requested


class TestNothingIsEverPreFetched:
    """AC 13. Fetching is lazy; the backend never pre-fetches a deck (AD-11, epic :1732-1734)."""

    @pytest.fixture
    async def deck_of_imaged_cards(self, image_shapes):
        """A real deck whose every entry is a card that HAS an image.

        The point of seeding imaged cards specifically: a zero-fetch assertion over a deck of
        image-less cards would be vacuous — nothing could have been fetched anyway.
        """
        deck_id = "deck-with-pictures"

        async def seeder(session):
            deck = DeckModel(name="Cold Deck", format="commander", strategy=None, tags=None)
            # `id` is init=False with a uuid default_factory; assigned here so the test can
            # address the deck by a readable name rather than reading one back.
            deck.id = deck_id
            session.add(deck)
            await session.flush()
            for card_id in (SINGLE_FACE_ID, MULTI_FACE_ID, SPLIT_FACE_ID):
                session.add(DeckCardModel(deck_id=deck_id, card_id=card_id, quantity=1))
            await session.commit()

        await _seed(image_shapes, seeder)
        return deck_id

    async def test_reading_a_deck_triggers_no_outbound_request_at_all(
        self, deck_of_imaged_cards, lifespan_client, cdn
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(f"/api/deck/{deck_of_imaged_cards}")

        assert response.status_code == 200
        assert len(response.json()["cards"]) == 3, "the deck read must actually have returned cards"
        assert cdn.requested == [], (
            "reading a deck fetched images. Fetching is lazy (AD-11): the browser asks for a tile "
            "when it decides to draw one, and a backend that pre-fetches turns one deck view into "
            "~99 unrequested CDN requests"
        )

    async def test_but_asking_for_a_tile_does_fetch_exactly_one(
        self, deck_of_imaged_cards, lifespan_client, cdn
    ):
        """NON-VACUITY for the zero above (AC 23): the recorder CAN see a fetch on this fixture.

        Without this pairing, `cdn.requested == []` would also pass with the transport unwired,
        the route deleted, or the recorder never attached.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert response.status_code == 200
        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]]

    async def test_reading_a_deck_writes_no_cache_file_either(
        self, deck_of_imaged_cards, lifespan_client, cdn
    ):
        """c3-7's half of the same rule: the cache is filled **only** by a request that was
        actually served (AC 10).

        "Nothing pre-fetches" and "nothing pre-writes" are different claims and a cache makes the
        second one newly possible — a backend that warmed a deck's tiles on the deck read would
        satisfy the zero-fetch assertion above only until someone decided warming was helpful.
        The cache root is listed through ``images.cache_root()`` (AC 22), so a cache writing
        somewhere unexpected reads as a failure rather than as an empty directory.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(f"/api/deck/{deck_of_imaged_cards}")

        assert response.status_code == 200
        assert len(response.json()["cards"]) == 3, "the deck read must actually have returned cards"
        assert _cache_files() == [], (
            "reading a deck wrote cache files. Nothing pre-warms: the cache is filled by a tile "
            "request that was served, and by nothing else."
        )

    async def test_but_asking_for_a_tile_does_write_exactly_one(
        self, deck_of_imaged_cards, lifespan_client, cdn
    ):
        """NON-VACUITY for the zero above (AC 20): the listing CAN see a file on this fixture.

        Without this pairing, an empty cache root also passes with the cache disabled, the write
        silently failing, or ``_cache_files()`` pointed at a directory nothing ever writes to.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert response.status_code == 200
        assert [entry.name for entry in _cache_files()] == ["normal_0.jpg"]


class TestTheBurstDoesNotOutlastTheConnectionPool:
    """Q6, pinned rather than fixed: the session is held ACROSS the queue wait.

    Measured at Task 0 and not inherited: FastAPI runs a ``yield``-dependency's teardown *after*
    the endpoint returns, so the route's ``DbSession`` — and its checked-out connection — is held
    for the whole endpoint body, including the pacer wait. The pool is SQLAlchemy's default
    ``AsyncAdaptedQueuePool``, **size 5 + overflow 10 = 15 connections, ``pool_timeout`` 30 s**
    (all four values read off the live pool object, not off a document).

    The consequence is that at most 15 requests sit *inside* the route at once and the rest wait
    outside it — a second queue in front of the first, which is inefficient and harmless at the
    shipped constants: a 99-tile burst drains in ~9.9 s, comfortably inside 30 s. **It works by
    arithmetic, not by design**, so this test exists to make the interaction visible to whichever
    later story slows the pacer down. Above roughly 0.3 s per tile the burst would outlast the
    pool timeout and raise ``sqlalchemy.exc.TimeoutError`` — which is **not** a ``DatabaseError``
    and would therefore surface as ``500 internal_error``, not ``503``. Ledgered on **c4-1**.
    """

    async def test_a_full_deck_sized_burst_completes_without_a_pool_timeout(
        self, image_shapes, lifespan_client, monkeypatch
    ):
        """99 concurrent requests for 99 **distinct** card ids — a real 100-card deck's shape.

        **The ids were not distinct until c3-7, and this test's own docstring said they were.**
        It drove ``SINGLE_FACE_ID`` ninety-nine times, which modelled a deck of one card repeated;
        that was invisible while every request fetched, and became a red the moment a cache
        existed — ``len(recorder.requested)`` fell to **3** (one fetch, plus two more admitted
        before the first write landed) and the concurrent writers raced ``os.replace``, which
        logged the ``PermissionError`` AC 9 exists for. The fetch count was right and the fixture
        was wrong.

        Fixed rather than relaxed, because the assertion is what makes this a *pool* test: 99
        distinct keys means 99 requests really traverse the whole route, which is the condition
        the pool arithmetic below is about. Reading which of "CM-2 working" or "a key collision"
        had happened was the point — it was the first.
        """
        from tests.unit.companion.conftest import _seed

        # One seeder, shared with `_seed_burst`'s other consumers rather than re-implemented
        # inline (review 2026-08-01) — two hand-synchronised copies of one fixture in one file is
        # the exact defect class this story's own deferred-work closure celebrated removing.
        burst_ids, seeder = _seed_burst(99)
        await _seed(image_shapes, seeder)

        recorder = Recorder()
        real_client = images.build_image_client
        monkeypatch.setattr(
            images,
            "build_image_client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(recorder.handle)),
        )
        real_pacer = images.Pacer
        monkeypatch.setattr(images, "Pacer", lambda **kwargs: real_pacer(spacing=0.0, **kwargs))

        app = build_app()
        async with lifespan_client(app) as client:
            responses = await asyncio.gather(
                *(
                    client.get(_IMAGE_PATH.format(scryfall_id=card_id), params={"face": 0})
                    for card_id in burst_ids
                )
            )
            pool = app.state.database.engine.sync_engine.pool

            # The measurement this test is really about, asserted rather than described.
            assert pool.size() == 5
            assert pool._max_overflow == 10
            assert pool._timeout == 30.0
            # The tripwire that makes "pinned" true (review 2026-08-01): the burst above runs at
            # spacing=0.0, so the SHIPPED constant never participates in it — a later story could
            # slow the pacer tenfold and the gather would still drain instantly. THIS line is
            # where that goes red, in the same register the hazard exists in: arithmetic. Margin
            # of 2 because the drain time assumes an instant CDN and production does not have one.
            assert 99 * images.FETCH_SPACING_SECONDS < pool._timeout / 2, (
                f"a deck-sized burst no longer fits the pool: 99 tiles at "
                f"{images.FETCH_SPACING_SECONDS} s spacing approaches the {pool._timeout} s pool "
                "timeout, and sqlalchemy.exc.TimeoutError surfaces as 500 internal_error, NOT "
                "503. Release the session before fetching (ledgered on c4-1) before slowing the "
                "pacer."
            )

        assert [r.status_code for r in responses] == [200] * 99, (
            "a request failed under a deck-sized burst; a pool timeout surfaces as 500 "
            "internal_error, NOT 503, because sqlalchemy.exc.TimeoutError is not a DatabaseError"
        )
        assert len(recorder.requested) == 99


class TestTheCommittedSchema:
    """The generated document describes bytes, not JSON."""

    @pytest.fixture(scope="class")
    def schema(self):
        path = Path(__file__).resolve().parents[3] / "ui" / "src" / "api" / "openapi.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_the_literal_path_is_present(self, schema):
        assert "/api/card-image/{scryfall_id}" in schema["paths"]

    def test_the_success_response_is_binary_and_not_json(self, schema):
        content = schema["paths"]["/api/card-image/{scryfall_id}"]["get"]["responses"]["200"][
            "content"
        ]

        assert "application/json" not in content, (
            "the success body is bytes; a JSON content type here would make the generated "
            "TypeScript lie to c4-4"
        )
        assert content["image/*"]["schema"] == {"type": "string", "format": "binary"}

    def test_the_route_declares_exactly_the_tokens_it_can_answer(self, schema):
        responses = schema["paths"]["/api/card-image/{scryfall_id}"]["get"]["responses"]

        assert "422" not in responses, "the auto-422 is permanently unreachable (AD-16)"
        assert "no_image_data" in responses["404"]["description"]
        assert "card_not_found" in responses["404"]["description"]
        assert "image_fetch_failed" in responses["502"]["description"]

    def test_the_size_enum_is_published_for_the_ui_to_read(self, schema):
        params = {
            p["name"]: p
            for p in schema["paths"]["/api/card-image/{scryfall_id}"]["get"]["parameters"]
        }

        assert set(params["size"]["schema"]["enum"]) == {
            "small",
            "normal",
            "large",
            "png",
            "art_crop",
            "border_crop",
        }
        assert params["size"]["schema"]["default"] == "normal"
        assert params["face"]["schema"]["minimum"] == 0
        assert params["face"]["schema"]["default"] == 0

    def test_the_id_constraint_is_the_same_one_the_sibling_route_publishes(self, schema):
        image_param = next(
            p
            for p in schema["paths"]["/api/card-image/{scryfall_id}"]["get"]["parameters"]
            if p["name"] == "scryfall_id"
        )
        card_param = next(
            p
            for p in schema["paths"]["/api/cards/{card_id}"]["get"]["parameters"]
            if p["name"] == "card_id"
        )

        # Imported, not retyped — two copies of a uuid pattern is exactly the drift this epic
        # keeps finding.
        assert image_param["schema"]["pattern"] == card_param["schema"]["pattern"]


class TestNotShadowedBySpa:
    """c2-2's mount matches every path; this route must still run."""

    async def test_the_route_answers_bytes_and_not_the_index(
        self, image_shapes, lifespan_client, cdn
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        # Status AND body: c3-1's review found a mount-ordering test that passed with the router
        # DELETED, because /api is reserved and answers JSON either way.
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content.startswith(b"\xff\xd8\xff")
        assert b"<!doctype html>" not in response.content.lower()


# =============================================================================================
# Story c3-7: the disk cache at the level of the running app.
#
# The mechanism's units are in `test_images.py` — the path, the extension rule, the atomicity of
# the write, each failure mode. What can ONLY be proved HERE is what a real request does: that a
# repeat fetches nothing, that a warm tile never enters the pacer, that the app serves with the
# network gone, that cold and warm answers agree byte for byte, and that a cache failure never
# reaches the client.
# =============================================================================================


def _seed_burst(count: int) -> tuple[list[str], object]:
    """Return *count* distinct card ids and a seeder that inserts them, each with one image.

    Distinct **ids** and distinct **URLs**, both deliberately: a cache mis-keyed on either would
    otherwise be invisible, and c3-1's R3 finding was that identical fixtures prove nothing.

    Args:
        count: How many cards to seed.

    Returns:
        The ids, and an async seeder to hand to ``_seed``.
    """
    from tests.unit.companion.conftest import _card

    ids = [_uuid(f"a{index:03x}") for index in range(count)]

    async def seeder(session):
        for index, card_id in enumerate(ids):
            session.add(
                _card(
                    card_id,
                    f"Burst Card {index}",
                    image_uris={"normal": f"https://cards.scryfall.io/normal/burst/{index}.jpg?17"},
                )
            )
        await session.commit()

    return ids, seeder


def _cache_files() -> list[Path]:
    """Every file currently in the image cache, resolved THROUGH THE APP'S OWN CODE.

    ``images.cache_root()`` rather than ``tmp_path / "image_cache"`` (AC 22). Rebuilding the path
    from the fixture would pass with the production path wrong — the test would be asserting on a
    directory it invented, and a cache writing somewhere else entirely would read as an empty one.
    """
    root = images.cache_root()
    return sorted(path for path in root.rglob("*") if path.is_file())


class TestARepeatRequestMakesNoCdnRequest:
    """**CM-2**, the epic's own acceptance criterion (epic :1728-1730) — satisfied here at last.

    c3-6 homed it on this story by name, in ``images.py``'s module docstring, in its own story
    record and in ``deferred-work.md``. It is the only one of this epic's six acceptance criteria
    that another story had been waiting on.
    """

    async def test_two_requests_for_one_key_produce_one_fetch_and_two_identical_answers(
        self, image_shapes, lifespan_client, cdn
    ):
        """The whole of CM-2 in one assertion pair — and it asserts the FETCH COUNT, not merely
        that the second response was 200.

        c3-1's R1 finding is the reason: a test that checks only ``200`` on the second request
        passes with the cache deleted. ``cdn.requested`` is what a missing cache cannot produce.
        """
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            first = await client.get(path)
            second = await client.get(path)

        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]], (
            f"the CDN was asked {len(cdn.requested)} times for one key. CM-2: an image fetched "
            "once is not fetched again within the cache lifetime"
        )
        assert first.status_code == second.status_code == 200
        assert first.content == second.content == cdn.body_for(_TOP_LEVEL_IMAGES["normal"])
        assert first.content, "the recorder answered empty bytes; this assertion would be vacuous"

    async def test_a_distinct_key_does_fetch(self, image_shapes, lifespan_client, cdn):
        """NON-VACUITY PAIRING for the zero-second-fetch claim (AC 20), from the same recorder.

        Without it, "one recorded URL" also passes against a route that fetched nothing at all,
        a broken transport seam, or a cache that returned the same entry for every key.
        """
        async with lifespan_client(build_app()) as client:
            await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))
            await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))
            await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": "png"})
            await client.get(_IMAGE_PATH.format(scryfall_id=MULTI_FACE_ID), params={"face": 1})

        assert cdn.requested == [
            _TOP_LEVEL_IMAGES["normal"],
            _TOP_LEVEL_IMAGES["png"],
            "https://cards.scryfall.io/normal/back/b.jpg?1700000201",
        ], "a different size or a different face is a different key and must fetch"

    async def test_the_second_request_is_served_from_a_file_that_actually_exists(
        self, image_shapes, lifespan_client, cdn
    ):
        """The other thing a missing cache cannot produce: a file on disk, at the path AD-11 names.

        Asserted through ``images.cache_root()`` (AC 22) rather than rebuilt from ``tmp_path``.
        """
        async with lifespan_client(build_app()) as client:
            await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        [entry] = _cache_files()
        assert entry.name == "normal_0.jpg"
        assert entry.parent.name == SINGLE_FACE_ID
        assert entry.parent.parent.name == SINGLE_FACE_ID[:2]
        assert entry.read_bytes() == cdn.body_for(_TOP_LEVEL_IMAGES["normal"])

    async def test_two_simultaneous_requests_for_one_key_both_succeed_through_the_real_race(
        self, image_shapes, lifespan_client, monkeypatch
    ):
        """Q5 declined coalescing, so this race is REAL and stays: two requests for one key miss
        together, fetch twice, and both write the same target through the actual filesystem —
        where the loser's ``os.replace`` can raise ``PermissionError`` on Windows, the exact case
        AC 9's posture exists for. It was observed live when the burst fixture still drove one id
        99 times; repairing that fixture to 99 distinct ids removed the only route-level
        reproduction (review 2026-08-01), leaving the race covered solely by a unit test that
        monkeypatches ``os.replace``. This is the replacement: the real filesystem, the real
        replace, and both answers asserted — not merely the absence of an exception.
        """
        upstream = StallableUpstream(hold=True)
        real_client = images.build_image_client
        monkeypatch.setattr(
            images,
            "build_image_client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(upstream.handle)),
        )
        real_pacer = images.Pacer
        monkeypatch.setattr(images, "Pacer", lambda **kwargs: real_pacer(spacing=0.0, **kwargs))
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            first = asyncio.create_task(client.get(path))
            second = asyncio.create_task(client.get(path))
            while upstream.in_flight < 2:
                await asyncio.sleep(0)
            upstream.release.set()
            responses = await asyncio.gather(first, second)

        assert [response.status_code for response in responses] == [200, 200], (
            "the loser of a same-key write race answered an error; AC 9 makes that a log line, "
            "never a failed request"
        )
        assert responses[0].content == responses[1].content
        assert len(upstream.requested) == 2, (
            "both requests were in flight before either write landed, so both must fetch — "
            "in-flight coalescing is c3-8's, declined here by Q5"
        )
        [entry] = _cache_files()
        assert entry.name == "normal_0.jpg", "whichever writer won, the key holds one entry"

    async def test_a_refreshed_row_with_a_new_cache_buster_still_hits_the_existing_entry(
        self, image_shapes, lifespan_client, cdn
    ):
        """AC 3's second consequence, driven END TO END rather than assumed from the signature.

        The unit-level assertion (``test_the_cache_buster_query_is_not_part_of_the_key``) is true
        by construction — ``DiskCache.read`` takes no URL, so it *cannot* miss on one. This test
        is the one that can actually fail (review 2026-08-01): the stored row's ``image_uris``
        move to a new ``?<timestamp>`` between two requests, the way a real data refresh moves
        them, and the second request must still hit the existing entry with ZERO new fetches.
        That staleness is AD-11's accepted trade — a URL-keyed cache would turn every refresh
        into a ~130 MB total re-fetch — and this is where it is measured rather than described.
        """
        from sqlalchemy import update

        from src.data.models.card import CardModel

        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            cold = await client.get(path)

        refreshed = {
            key: f"{url.split('?')[0]}?1800000000" for key, url in _TOP_LEVEL_IMAGES.items()
        }

        async def refresher(session):
            await session.execute(
                update(CardModel).where(CardModel.id == SINGLE_FACE_ID).values(image_uris=refreshed)
            )
            await session.commit()

        await _seed(image_shapes, refresher)

        async with lifespan_client(build_app()) as client:
            warm = await client.get(path)

        assert warm.status_code == 200
        assert warm.content == cold.content, (
            "the warm hit must serve the OLDER picture — the documented staleness AD-11 accepts"
        )
        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]], (
            "a refreshed row re-fetched: the cache key leaked the URL (or its cache-buster), "
            "which would make every data refresh a total cache miss"
        )

    async def test_three_cards_sharing_one_url_are_three_entries_and_three_fetches(
        self, ready_db, lifespan_client, cdn
    ):
        """AC 3, and it is the assertion that proves the key is **id + size + face, not the URL**.

        Sparkspitter, Ondu Champion and Gorehorn Minotaurs all store
        ``https://errors.scryfall.com/soon.jpg`` in all six size keys. The shipped test at
        ``test_the_measured_errors_scryfall_com_cards_are_served_not_refused`` predicted this
        would keep passing **unchanged** under a correct key, and it did — see the story record.
        This one states the cache half of the same fact directly: three entries on disk, one per
        id, rather than one entry shared by URL.
        """
        from tests.unit.companion.conftest import _card

        real_ids = [
            "0070bbf6-fdee-44ec-bfb8-3e99d6338e6e",  # Sparkspitter
            "7206cdd5-3f86-4415-a236-9b331b4ac42a",  # Ondu Champion
            "7dc76d47-e9c1-4bcf-9134-70052aafa67f",  # Gorehorn Minotaurs
        ]
        placeholder = {key: "https://errors.scryfall.com/soon.jpg" for key in _TOP_LEVEL_IMAGES}

        async def seeder(session):
            for index, card_id in enumerate(real_ids):
                session.add(_card(card_id, f"Errors Card {index}", image_uris=placeholder))
            await session.commit()

        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            for card_id in real_ids:
                assert (
                    await client.get(_IMAGE_PATH.format(scryfall_id=card_id))
                ).status_code == 200

        assert cdn.requested == ["https://errors.scryfall.com/soon.jpg"] * 3, (
            "a URL-keyed cache would have collapsed three different cards into one entry — and "
            "would also make every data refresh a total cache miss"
        )
        assert {entry.parent.name for entry in _cache_files()} == set(real_ids)
        assert {entry.name for entry in _cache_files()} == {"normal_0.jpg"}, (
            "the `png` size of these three resolves to a .jpg URL; only `normal` was requested "
            "here, but the extension must come from the URL either way"
        )

    @pytest.mark.parametrize(
        ("card_id", "card_name"),
        [
            ("0070bbf6-fdee-44ec-bfb8-3e99d6338e6e", "Sparkspitter"),
            ("7206cdd5-3f86-4415-a236-9b331b4ac42a", "Ondu Champion"),
            ("7dc76d47-e9c1-4bcf-9134-70052aafa67f", "Gorehorn Minotaurs"),
        ],
    )
    async def test_a_png_size_that_resolves_to_a_jpg_is_served_as_jpeg_when_warm(
        self, ready_db, lifespan_client, monkeypatch, card_id, card_name
    ):
        """AC 2 at the level a **browser** sees, which is where the damage would land.

        Each of the three real cards' ``png`` entry is ``https://errors.scryfall.com/soon.jpg``,
        so ``?size=png`` on them fetches JPEG bytes. If the cache took ``<ext>`` from the size
        key, those bytes would be stored at ``png_0.png`` and the warm hit would serve them as
        ``image/png`` — a mislabelled body stamped ``immutable`` for a year, on this app's own
        origin, behind the very ``nosniff`` header that tells the browser not to second-guess it.

        Added after probe (d): the size-key mutation was caught by only two unit tests and by
        nothing at the route level, so the assertion that mattered most — *what the client is
        told the bytes are* — was the one not being made. Parametrized over **all three** named
        cards rather than Sparkspitter alone (review 2026-08-01): AC 2's text pins the trio.
        """
        from tests.unit.companion.conftest import _card

        recorder = Recorder(body=_JPEG, content_type="image/jpeg")
        real_client = images.build_image_client
        monkeypatch.setattr(
            images,
            "build_image_client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(recorder.handle)),
        )

        async def seeder(session):
            session.add(
                _card(
                    card_id,
                    card_name,
                    image_uris={
                        key: "https://errors.scryfall.com/soon.jpg" for key in _TOP_LEVEL_IMAGES
                    },
                )
            )
            await session.commit()

        await _seed(ready_db, seeder)
        path = _IMAGE_PATH.format(scryfall_id=card_id)

        async with lifespan_client(build_app()) as client:
            cold = await client.get(path, params={"size": "png"})
            warm = await client.get(path, params={"size": "png"})

        assert cold.headers["content-type"] == "image/jpeg"
        assert warm.headers["content-type"] == "image/jpeg", (
            "a `png`-size request served as image/png would be JPEG bytes under a PNG media type "
            "— the silent corruption <ext>-from-the-size-key produces on exactly three real cards"
        )
        assert cold.content == warm.content
        assert len(recorder.requested) == 1, "this test would be vacuous if the second call fetched"
        assert [entry.name for entry in _cache_files()] == ["png_0.jpg"]


class TestAWarmTileNeverEntersThePacer:
    """AC 6's second half, and NFR-06's real content — proved on c3-6's injected clock.

    A cache check that sat *inside* ``pacer.slot()`` would cache perfectly and still make a warm
    99-tile deck take 9.9 seconds, holding the CDN's rate budget against requests that never leave
    the machine. Every functional assertion in this file would pass. **So the claim is measured on
    the clock, not on the bytes** — which is c3-6's probe (f) lesson applied before the fact rather
    than after.
    """

    @pytest.fixture
    def paced(self, monkeypatch):
        """A real pacer on virtual time, at the SHIPPED spacing, plus a recording CDN.

        The shipped spacing deliberately: a test that quietly paced at zero would prove nothing
        about the number that ships. Only the clock is fictional, so this costs no wall time at
        all — the cold burst below "takes" 9.8 seconds and runs in milliseconds.
        """
        clock = FakeClock()
        recorder = Recorder()
        real_client = images.build_image_client
        monkeypatch.setattr(
            images,
            "build_image_client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(recorder.handle)),
        )
        real_pacer = images.Pacer
        monkeypatch.setattr(
            images,
            "Pacer",
            lambda **kwargs: real_pacer(clock=clock.time, sleep=clock.sleep, **kwargs),
        )
        return clock, recorder

    async def test_a_cold_burst_pays_98_spacings_and_the_warm_repeat_pays_zero(
        self, image_shapes, lifespan_client, paced
    ):
        """99 tiles cold, then the same 99 warm. **98 spacing intervals, then none.**

        98 rather than 99 because the first fetch of a cold process starts immediately — the
        pacer's cursor is ``None`` until something has started, so a fresh process paints its
        first tile without waiting.
        """
        clock, recorder = paced
        ids, seeder = _seed_burst(99)
        await _seed(image_shapes, seeder)

        async with lifespan_client(build_app()) as client:
            for card_id in ids:
                assert (
                    await client.get(_IMAGE_PATH.format(scryfall_id=card_id))
                ).status_code == 200

            cold_sleeps = len(clock.slept)
            cold_time = clock.now
            cold_fetches = len(recorder.requested)

            for card_id in ids:
                assert (
                    await client.get(_IMAGE_PATH.format(scryfall_id=card_id))
                ).status_code == 200

        assert cold_fetches == 99, "the cold burst did not actually fetch 99 tiles"
        assert cold_sleeps == 98, (
            f"a cold 99-tile deck paid {cold_sleeps} spacing intervals, not 98 — the first fetch "
            "of a cold process should start immediately"
        )
        assert cold_time == pytest.approx(98 * images.FETCH_SPACING_SECONDS)

        assert len(recorder.requested) == 99, "the warm repeat fetched something (CM-2 is broken)"
        assert len(clock.slept) == cold_sleeps, (
            f"the warm burst paid {len(clock.slept) - cold_sleeps} spacing intervals. The cache "
            "check must sit OUTSIDE pacer.slot(): a warm deck that queues behind the CDN's rate "
            "budget takes 9.9 s to paint from a local disk and holds Scryfall's budget while it "
            "does — and every functional test in this file passes anyway (landmine 11)."
        )
        assert clock.now == cold_time, "virtual time moved during a burst that touched no network"


class TestWithTheNetworkGone:
    """AC 7 / NFR-06: *after image-cache warm-up, the app is fully functional with no network*.

    The transport **raises** rather than 404ing, deliberately: a 404 makes a cache miss look like
    a plausible upstream answer, where a raise makes it a loud one. This is the first test in this
    feature that proves NFR-06 for images at all.
    """

    async def test_a_warm_tile_is_served_after_the_network_disappears(
        self, image_shapes, lifespan_client, cdn
    ):
        warm = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            first = await client.get(warm)
            assert first.status_code == 200

            cdn.raises = httpx.ConnectError("the network is gone")
            offline = await client.get(warm)

        assert offline.status_code == 200
        assert offline.content == first.content
        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]], (
            "the offline request reached the transport; it should never have left the disk"
        )

    async def test_a_cold_key_through_the_same_dead_transport_is_still_a_502(
        self, image_shapes, lifespan_client, cdn
    ):
        """NON-VACUITY PAIRING (AC 20): without it, the 200 above also passes against a route that
        answers 200 unconditionally, or a transport that was never actually broken."""
        async with lifespan_client(build_app()) as client:
            assert (
                await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))
            ).status_code == 200

            cdn.raises = httpx.ConnectError("the network is gone")
            cold = await client.get(
                _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"size": "large"}
            )

        assert cold.status_code == 502
        assert cold.json() == {"reason": "image_fetch_failed"}
        assert cold.headers["cache-control"] == "no-store"


class TestTheWarmAnswerMatchesTheColdOne:
    """AC 8: a cache hit is byte-identical to the cold answer, headers included."""

    async def test_every_field_of_the_success_response_agrees(
        self, image_shapes, lifespan_client, cdn
    ):
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            cold = await client.get(path)
            warm = await client.get(path)

        assert cold.status_code == warm.status_code == 200
        assert cold.content == warm.content
        assert cold.headers["content-type"] == warm.headers["content-type"] == "image/jpeg"
        assert (
            cold.headers["cache-control"]
            == warm.headers["cache-control"]
            == images.IMAGE_CACHE_CONTROL
        )
        assert (
            cold.headers["x-content-type-options"]
            == warm.headers["x-content-type-options"]
            == "nosniff"
        )

    async def test_the_one_named_divergence_is_the_content_type_parameter(
        self, ready_db, lifespan_client, monkeypatch
    ):
        """Q4's honest consequence, **asserted rather than discovered** (AC 8).

        The cold path echoes the upstream's own header verbatim, parameters included — c3-5's
        shipped ruling, because what the upstream said about its own bytes beats anything derived
        from the size key. A warm hit has only the stored extension, so it answers the bare media
        type from ``images.CACHE_MEDIA_TYPES``.

        So *if* an upstream ever sends ``image/jpeg; charset=binary``, the cold answer carries the
        parameter and the warm answer does not. It is bounded to parameters, no browser behaves
        differently for one, and **no measured Scryfall response actually sends one** — but it is
        pinned here by name so c4-4 does not discover that the second render of a tile has a
        different media type from the first.

        The alternative — a sidecar file holding the exact header — doubles the entries on disk and
        re-opens the atomicity question for a *pair* of files, to preserve a parameter nothing
        sends.
        """
        from tests.unit.companion.conftest import _card

        recorder = Recorder(content_type="image/jpeg; charset=binary")
        real_client = images.build_image_client
        monkeypatch.setattr(
            images,
            "build_image_client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(recorder.handle)),
        )
        card_id = _uuid("cc")

        async def seeder(session):
            session.add(
                _card(
                    card_id,
                    "Parameterised Type",
                    image_uris={"normal": "https://cards.scryfall.io/normal/p.jpg?1"},
                )
            )
            await session.commit()

        await _seed(ready_db, seeder)
        path = _IMAGE_PATH.format(scryfall_id=card_id)

        async with lifespan_client(build_app()) as client:
            cold = await client.get(path)
            warm = await client.get(path)

        assert cold.content == warm.content, "the bodies must still be identical"
        assert cold.headers["content-type"] == "image/jpeg; charset=binary"
        assert warm.headers["content-type"] == "image/jpeg", (
            "the warm answer derives its type from the stored extension through a two-entry map; "
            "the divergence is bounded to PARAMETERS and is named in Q4"
        )
        assert len(recorder.requested) == 1, "this test would be vacuous if the second call fetched"


class TestACacheFailureNeverReachesTheClient:
    """AC 9, at the level of the served response — not merely "nothing raised".

    Both directions are driven separately, because they fail in different places: a **read**
    failure must degrade to a fetch, and a **write** failure must not disturb a response that has
    already been produced. Neither adds a reason token: ``ErrorReason`` is closed at ten.
    """

    async def test_a_read_failure_is_answered_by_fetching(
        self, image_shapes, lifespan_client, cdn, monkeypatch
    ):
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            assert (await client.get(path)).status_code == 200

            def explode(self, *args, **kwargs):
                raise PermissionError("another process holds the entry open")

            monkeypatch.setattr(images.Path, "read_bytes", explode)
            answered = await client.get(path)

        assert answered.status_code == 200
        assert answered.content == cdn.body_for(_TOP_LEVEL_IMAGES["normal"])
        assert answered.headers["cache-control"] == images.IMAGE_CACHE_CONTROL
        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]] * 2, (
            "an unreadable entry must be REFETCHED — never served as-is, and never answered with "
            "a substitute image (AD-11)"
        )

    async def test_a_write_failure_still_serves_the_image(
        self, image_shapes, lifespan_client, cdn, monkeypatch
    ):
        """**The patch goes on INSIDE the lifespan, and that is not a style choice.**

        ``images.tempfile`` and ``discovery.tempfile`` are the *same module object*, so patching
        ``mkstemp`` before startup breaks ``write_discovery`` — which is the one startup step
        allowed to fail the launch, so the app never starts and the test fails for a reason that
        has nothing to do with the cache. Patching after startup scopes the failure to the only
        caller left standing. (Found by this test on its first run; recorded because the same trap
        is waiting for anyone who adds a second filesystem failure case here.)
        """
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        def explode(*args, **kwargs):
            raise PermissionError("the cache directory is not writable")

        async with lifespan_client(build_app()) as client:
            monkeypatch.setattr(images.tempfile, "mkstemp", explode)
            first = await client.get(path)
            second = await client.get(path)

        assert first.status_code == second.status_code == 200
        assert first.content == second.content == cdn.body_for(_TOP_LEVEL_IMAGES["normal"])
        assert first.headers["content-type"] == "image/jpeg"
        assert _cache_files() == [], "something was stored despite the write failing"
        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]] * 2, (
            "with nothing stored, the second request must fetch again — the app is slower and "
            "entirely correct, which is the whole of AC 9"
        )

    async def test_an_app_with_no_cache_at_all_serves_normally(
        self, image_shapes, lifespan_client, cdn, monkeypatch
    ):
        """Q6's served consequence: a cache root that could not be created disables the cache for
        the process, and **the route must not read that as a wiring bug**.

        This is the one place ``image_cache``'s ``None`` diverges in meaning from
        ``image_client``'s and ``image_pacer``'s, where ``None`` is ``internal_error``. A route
        that treated them alike would turn a degradation into an outage.
        """
        monkeypatch.setattr(images, "build_image_cache", lambda: None)
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            first = await client.get(path)
            second = await client.get(path)

        assert first.status_code == second.status_code == 200
        assert first.content == cdn.body_for(_TOP_LEVEL_IMAGES["normal"])
        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]] * 2


# =============================================================================================
# Story c3-8: distinguishable failure signalling, and the negative cache at the level of the
# running app.
#
# The mechanism's units are in `test_images.py` — the schedule, the ceiling, the retention
# horizon, the cap, the eviction tiebreak. What can ONLY be proved HERE is what a real request
# does: that a remembered failure issues no request AND pays no spacing turn, that it is byte
# for byte the answer a fresh failure gives, that recovery is complete, that a cancelled request
# is not a failure, and that nothing is written to disk by any of it.
#
# THE THREE VERIFICATION ACs COME FIRST (AC 1-3), because the story's single most dangerous fact
# is that three of its five epic acceptance criteria shipped at c3-5 — so an implementer either
# rebuilds them or, much likelier, never verifies them and ships a story whose headline claim is
# inherited rather than proved.
# =============================================================================================


@pytest.fixture
def remembered(monkeypatch):
    """A real pacer AND a real negative cache, both on ONE virtual clock, plus a recording CDN.

    The shipped constants throughout: only the clock is fictional. That matters twice over — a
    test that quietly paced at zero would prove nothing about the number that ships, and a backoff
    proved by sleeping 30 real seconds is the one thing this story could plausibly get wrong and
    still pass.

    Both mechanisms share **one** clock deliberately. They are the two things on this path whose
    correctness is time, and giving them separate clocks would let a test assert a backoff window
    against a pacer that had drifted away from it.

    Returns:
        The clock, and the recorder every outbound URL lands in.
    """
    clock = FakeClock()
    recorder = Recorder()
    real_client = images.build_image_client
    monkeypatch.setattr(
        images,
        "build_image_client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(recorder.handle)),
    )
    real_pacer = images.Pacer
    monkeypatch.setattr(
        images,
        "Pacer",
        lambda **kwargs: real_pacer(clock=clock.time, sleep=clock.sleep, **kwargs),
    )
    real_negative = images.NegativeCache
    monkeypatch.setattr(
        images,
        "NegativeCache",
        lambda **kwargs: real_negative(clock=clock.time, **kwargs),
    )
    return clock, recorder


class TestTheTwoFailuresAreDistinguishable:
    """**AC 1 — verified, not rebuilt.** The epic's ``:1784-1787`` criterion, and AD-11's rule.

    This shipped at c3-5 and ``contracts.py:98-108`` says so by name. What was NOT asserted
    anywhere until this story is the **discrimination itself**: the two answers were proved in
    separate classes on separate fixtures, so nothing in the suite pinned that they differ. A
    single test that makes both requests is the only shape that can go red if a later story
    collapses them into one token.
    """

    async def test_one_request_each_and_the_answers_differ_in_status_and_token(
        self, image_shapes, lifespan_client, cdn
    ):
        """The discrimination, from ONE test — which is the assertion that is new here."""
        cdn.raises = httpx.ConnectError("the CDN is unreachable")

        async with lifespan_client(build_app()) as client:
            no_artwork = await client.get(_IMAGE_PATH.format(scryfall_id=NO_IMAGE_ID))
            fetch_failed = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert (no_artwork.status_code, fetch_failed.status_code) == (404, 502)
        assert no_artwork.json() == {"reason": "no_image_data"}
        assert fetch_failed.json() == {"reason": "image_fetch_failed"}
        # The claim stated as a claim: a client CAN tell these apart, on both axes.
        assert no_artwork.status_code != fetch_failed.status_code
        assert no_artwork.json()["reason"] != fetch_failed.json()["reason"]

    async def test_neither_answer_carries_a_substitute_image(
        self, image_shapes, lifespan_client, cdn
    ):
        """AD-11's non-negotiable half, asserted on the **BYTES** for both tokens.

        ``test_a_failure_never_returns_a_substitute_image`` already did this for the 502. The 404
        half had only ever been asserted on the status and the parsed JSON — and a status-only
        assertion passes with a grey rectangle in the body, which is the exact thing AD-11 forbids.
        """
        cdn.raises = httpx.ConnectError("the CDN is unreachable")

        async with lifespan_client(build_app()) as client:
            no_artwork = await client.get(_IMAGE_PATH.format(scryfall_id=NO_IMAGE_ID))
            fetch_failed = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        for response in (no_artwork, fetch_failed):
            assert response.headers["content-type"].startswith("application/json")
            assert len(response.content) < 100, "an error body is a token, not a picture"
            assert not response.content.startswith(b"\xff\xd8"), "a JPEG was served as a failure"
            assert not response.content.startswith(b"\x89PNG"), "a PNG was served as a failure"

    async def test_the_pixels_are_identical_but_the_retry_semantics_are_not(
        self, image_shapes, lifespan_client, cdn
    ):
        """Why two tokens rather than one, stated as behaviour (``contracts.py:158-163``).

        The client draws the same named placeholder for both — so the distinction is worth its
        eight-site ripple only because exactly one of them may ever be retried. The observable
        difference is that ``no_image_data`` never reaches the CDN at all, whatever the network is
        doing, and ``image_fetch_failed`` did.
        """
        cdn.raises = httpx.ConnectError("the CDN is unreachable")

        async with lifespan_client(build_app()) as client:
            await client.get(_IMAGE_PATH.format(scryfall_id=NO_IMAGE_ID))
            assert cdn.requested == [], "a permanent failure attempted a fetch"

            await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert cdn.requested == [_TOP_LEVEL_IMAGES["normal"]], (
            "the transient failure did NOT attempt a fetch — so the zero above proves nothing"
        )


class TestACardWithNoImageDataNeverReachesTheNegativeCache:
    """**AC 2 — verified, and the negative cache is explicitly NOT what makes it true.**

    The epic's ``:1793-1795``. The ``no_image_data`` answer precedes the cache by several lines,
    so the **79** image-less cards in the corpus never produce a cache key at all — the criterion
    is satisfied *structurally*, and saying so is the point. A story that let this AC read as
    "the negative cache handles it" would be claiming credit for the wrong mechanism.
    """

    async def test_no_fetch_and_no_negative_entry_are_different_claims(
        self, image_shapes, lifespan_client, cdn
    ):
        """The pairing that distinguishes *never fetched* from *fetched and remembered as failed*.

        ``cdn.requested == []`` alone cannot tell those apart: a route that fetched, failed and
        recorded would also show an empty list on the SECOND request. Reading the map is what
        separates them, and this is the assertion the mechanism made newly possible.
        """
        app = build_app()

        async with lifespan_client(app) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=NO_IMAGE_ID))
            entries = images.negative_cache(app).entry_count

        assert response.status_code == 404
        assert response.json() == {"reason": "no_image_data"}
        assert cdn.requested == []
        assert entries == 0, (
            "a card with no image data left an entry in the negative cache. It has no URL to "
            "fail, so there is nothing to remember — and remembering it would put 79 permanently "
            "image-less cards on a 30-second retry cycle for no reason."
        )

    async def test_but_a_real_fetch_failure_does_leave_one(
        self, image_shapes, lifespan_client, cdn
    ):
        """NON-VACUITY for the zero above (AC 23), from the same accessor.

        Without it, ``entry_count == 0`` passes with the negative cache never wired in at all,
        with the accessor returning a fresh instance each call, or with recording deleted.
        """
        cdn.raises = httpx.ConnectError("the CDN is unreachable")
        app = build_app()

        async with lifespan_client(app) as client:
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))
            entries = images.negative_cache(app).entry_count

        assert response.status_code == 502
        assert entries == 1

    async def test_an_out_of_range_face_is_also_answered_before_the_cache(
        self, image_shapes, lifespan_client, cdn
    ):
        """The second ``no_image_data`` path — a real face index beyond what the card has.

        Same structural guarantee, different branch, and it is asserted separately because the two
        raise sites are four lines apart and only one of them was covered by the test above.
        """
        app = build_app()

        async with lifespan_client(app) as client:
            response = await client.get(
                _IMAGE_PATH.format(scryfall_id=SPLIT_FACE_ID), params={"face": 1}
            )
            entries = images.negative_cache(app).entry_count

        assert response.status_code == 404
        assert cdn.requested == []
        assert entries == 0


class TestTheClientCanDrawTheNamedPlaceholder:
    """**AC 3 — verified as a CONTRACT claim, not re-implemented.** Epic ``:1801-1803``, UX-DR22.

    The SPA half already ships and is already gated: ``states.test.ts`` pins that both image
    tokens map to the ``named-card`` placeholder and specifically **not** to ``unknown-card``.
    What is verified here is the backend half of the same claim — that the data the placeholder
    needs is genuinely reachable, from a route this story does not touch.
    """

    async def test_the_card_route_carries_the_three_fields_the_placeholder_draws(
        self, image_shapes, lifespan_client, cdn
    ):
        """Name, mana cost and type line — over the wire, from the shipped route.

        Asserted on the VALUES rather than on key presence: a placeholder rendered from three
        empty strings is the failure this is really about, and ``model_validate``'s silent
        defaulting is c3-1's landmine 10 in this story's costume.
        """
        async with lifespan_client(build_app()) as client:
            image = await client.get(_IMAGE_PATH.format(scryfall_id=NO_IMAGE_ID))
            card = await client.get(f"/api/cards/{NO_IMAGE_ID}")

        assert image.status_code == 404
        assert card.status_code == 200
        body = card.json()
        assert body["name"], "the placeholder has no name to draw"
        assert "mana_cost" in body
        assert body["type_line"], "the placeholder has no type line to draw"

    def test_both_image_tokens_stay_inside_the_closed_set(self):
        """AC 5's half of the contract: ``ErrorReason`` is closed at ten and this story adds none.

        Pinned here as well as in ``test_errors.py`` because this is the file that would notice a
        story reaching for an eleventh token to mean *"remembered failure"* — which is precisely
        the temptation the negative cache creates and ``contracts.py:104`` predicted in writing.
        """
        from src.companion.contracts import ErrorReason

        tokens = set(ErrorReason.__args__)

        assert len(tokens) == 10
        assert {"no_image_data", "image_fetch_failed"} <= tokens
        assert not [token for token in tokens if "backoff" in token or "cached" in token]


class TestARememberedFailureIssuesNoRequestAndPaysNoRate:
    """**AC 4.** The headline, and it is measured on the CLOCK as well as on the fetch count.

    Two independent claims, and the second is the one with teeth. A negative check placed **inside**
    ``pacer.slot()`` remembers perfectly — the fetch count assertion passes — and still makes every
    remembered failure wait its turn against a CDN it never contacts. That is c3-5/c3-6/c3-7's
    shared review theme in this story's costume (c3-7's probe (f) was caught by exactly one test of
    911, the injected-clock one), so the clock is asserted here for the same reason.
    """

    async def test_a_second_request_adds_no_fetch_and_no_spacing_while_a_third_key_pays_both(
        self, image_shapes, lifespan_client, remembered
    ):
        """The whole of AC 4 and its non-vacuity pairing, from ONE invocation.

        Three requests, deliberately in this order:

        1. key A fails — this is what opens the window, and it also sets the pacer's cursor, so the
           spacing measurements below are against a warm pacer rather than a cold one (a cold
           process paints its first tile immediately, which would make a zero meaningless);
        2. key A again — must add **zero** fetches and **zero** spacing intervals;
        3. key B, distinct, through the same transport — must add **one** of each, which is what
           proves the two zeros above are real rather than an artefact of a broken seam.
        """
        clock, recorder = remembered
        recorder.raises = httpx.ConnectError("the CDN is unreachable")
        key_a = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)
        key_b = _IMAGE_PATH.format(scryfall_id=MULTI_FACE_ID)

        async with lifespan_client(build_app()) as client:
            first = await client.get(key_a)
            fetches_after_first = len(recorder.requested)
            sleeps_after_first = len(clock.slept)
            time_after_first = clock.now

            second = await client.get(key_a)
            fetches_after_second = len(recorder.requested)
            sleeps_after_second = len(clock.slept)
            time_after_second = clock.now

            third = await client.get(key_b)

        assert first.status_code == second.status_code == third.status_code == 502
        assert fetches_after_first == 1, "the first request did not actually reach the transport"

        assert fetches_after_second == fetches_after_first, (
            "the remembered failure issued a CDN request. Every paint after the first against a "
            "failing CDN would re-issue all 99 of them."
        )
        assert sleeps_after_second == sleeps_after_first, (
            "the remembered failure paid a spacing turn. The negative check must sit OUTSIDE "
            "pacer.slot(): a request that issues no request owes the rate nothing, and a check "
            "inside the slot remembers correctly while holding the CDN's budget against traffic "
            "it never sends. Every functional assertion in this file passes anyway."
        )
        assert time_after_second == time_after_first, "virtual time moved on a remembered failure"

        # NON-VACUITY (AC 23), from the same clock and the same recorder: a DISTINCT key through
        # the identical transport pays exactly one fetch and exactly one spacing turn.
        assert len(recorder.requested) == fetches_after_second + 1, (
            "a distinct key did not fetch — so the zeros above prove nothing about the mechanism"
        )
        assert len(clock.slept) == sleeps_after_second + 1
        assert clock.now == pytest.approx(time_after_second + images.FETCH_SPACING_SECONDS)

    async def test_the_size_and_the_face_are_part_of_the_key_over_the_wire(
        self, image_shapes, lifespan_client, remembered
    ):
        """A failure on one rendition must not blank the others (AD-11's key, end to end).

        The unit test proves the map keys on all three; this proves the ROUTE passes all three.
        A route that recorded on the id alone would silently blank every size and face of a card
        whose ``normal`` tile blipped once — and the unit test could not see it.
        """
        _clock, recorder = remembered
        recorder.raises = httpx.ConnectError("the CDN is unreachable")
        path = _IMAGE_PATH.format(scryfall_id=MULTI_FACE_ID)

        async with lifespan_client(build_app()) as client:
            await client.get(path, params={"face": 0})
            after_first = len(recorder.requested)
            await client.get(path, params={"face": 0})
            after_repeat = len(recorder.requested)
            await client.get(path, params={"face": 1})
            after_other_face = len(recorder.requested)
            await client.get(path, params={"face": 0, "size": "large"})
            after_other_size = len(recorder.requested)

        assert after_repeat == after_first, "the same key refetched"
        assert after_other_face == after_first + 1, "a sibling FACE was silenced by the backoff"
        assert after_other_size == after_first + 2, "a sibling SIZE was silenced by the backoff"


class TestTheDeckScaleClaim:
    """**AC 4b.** The user-visible version, and the honest statement of what it does not fix."""

    async def test_a_first_paint_issues_99_and_the_second_issues_none(
        self, image_shapes, lifespan_client, remembered
    ):
        """99 distinct ids against a dead CDN: 99 fetches and 99 502s, then **zero** and 99 502s.

        ``_seed_burst`` gives genuinely distinct ids — repaired by c3-7 after its own docstring had
        claimed distinctness for a fixture driving one id 99 times.

        **What this test deliberately does NOT claim.** The first paint still costs all 99 requests,
        because 99 distinct keys have nothing remembered yet; at the shipped constants against an
        unreachable CDN that is roughly 124 s. The pacer bounds that paint and this bounds every one
        after it. A test named "the storm is solved" would be this story's own version of prose
        outrunning code (c3-4's review theme).
        """
        clock, recorder = remembered
        recorder.raises = httpx.ConnectError("the CDN is unreachable")
        ids, seeder = _seed_burst(99)
        await _seed(image_shapes, seeder)

        async with lifespan_client(build_app()) as client:
            cold = [await client.get(_IMAGE_PATH.format(scryfall_id=card_id)) for card_id in ids]
            cold_fetches = len(recorder.requested)
            cold_sleeps = len(clock.slept)

            warm = [await client.get(_IMAGE_PATH.format(scryfall_id=card_id)) for card_id in ids]

        assert [r.status_code for r in cold] == [502] * 99
        assert cold_fetches == 99, "the first paint did not actually issue 99 requests"

        assert [r.status_code for r in warm] == [502] * 99, (
            "the second paint answered something other than the failure it remembered"
        )
        assert len(recorder.requested) == 99, (
            f"the second paint issued {len(recorder.requested) - 99} CDN requests. Every reload, "
            "second tab and scroll-back against a failing CDN is a fresh 99-request storm without "
            "this — which is what EXPERIENCE.md's 'no request storms' promises."
        )
        assert len(clock.slept) == cold_sleeps, (
            "the second paint paid spacing turns for requests it never issued"
        )


class TestARememberedFailureIsByteIdenticalToAFreshOne:
    """**AC 5.** Asserted as an EQUALITY between the two responses, not as two status assertions.

    A negative hit raises the same typed error through the same handler, so it inherits
    ``errors.error_response``'s ``Cache-Control: no-store`` and its status-from-token derivation
    with no code at all. That is what makes this claim cheap to assert — and a divergence a defect
    rather than a subtlety.
    """

    async def test_every_field_of_the_two_failure_responses_agrees(
        self, image_shapes, lifespan_client, cdn
    ):
        cdn.raises = httpx.ConnectError("the CDN is unreachable")
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            cold = await client.get(path)
            fetches_after_cold = len(cdn.requested)
            remembered_answer = await client.get(path)

        assert fetches_after_cold == 1
        assert len(cdn.requested) == 1, "this test is vacuous if the second call refetched"

        assert cold.status_code == remembered_answer.status_code == 502
        assert cold.content == remembered_answer.content
        assert cold.json() == remembered_answer.json() == {"reason": "image_fetch_failed"}
        assert cold.headers["content-type"] == remembered_answer.headers["content-type"]
        assert cold.headers["cache-control"] == remembered_answer.headers["cache-control"]
        assert remembered_answer.headers["cache-control"] == "no-store"

    async def test_neither_carries_any_of_the_success_headers(
        self, image_shapes, lifespan_client, cdn
    ):
        """The absence half, which an equality between two identical mistakes cannot catch.

        Both responses agreeing proves nothing if both wrongly carry the image route's
        year-long ``Cache-Control`` or its ``nosniff``. These are the headers a SUCCESS sets.
        """
        cdn.raises = httpx.ConnectError("the CDN is unreachable")
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            cold = await client.get(path)
            remembered_answer = await client.get(path)

        for response in (cold, remembered_answer):
            assert response.headers["cache-control"] != images.IMAGE_CACHE_CONTROL
            assert "x-content-type-options" not in response.headers
            assert not response.headers["content-type"].startswith("image/")


class TestRecoveryIsComplete:
    """**AC 7.** The retry after the window, the disk write, and the cleared history."""

    async def test_after_the_window_the_fetch_is_retried_and_cached_on_disk(
        self, image_shapes, lifespan_client, remembered
    ):
        """The epic's ``:1797-1799``, end to end and on the injected clock."""
        clock, recorder = remembered
        recorder.raises = httpx.ConnectError("the CDN is unreachable")
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            failed = await client.get(path)
            inside_window = await client.get(path)
            fetches_inside = len(recorder.requested)

            # The CDN comes back, and so does the clock — one tick past the base window.
            recorder.raises = None
            clock.now += images.NEGATIVE_CACHE_BASE_SECONDS
            recovered = await client.get(path)

        assert failed.status_code == inside_window.status_code == 502
        assert fetches_inside == 1, "the request inside the window reached the CDN"

        assert recovered.status_code == 200
        assert len(recorder.requested) == 2, "the retry after the window never happened"
        assert recovered.content == recorder.body_for(_TOP_LEVEL_IMAGES["normal"])
        assert [entry.name for entry in _cache_files()] == ["normal_0.jpg"], (
            "the recovered image was served but not cached — recovery must put the key back on "
            "the ordinary warm path, or the next paint fetches it again"
        )

    async def test_a_recovered_key_starts_its_next_failure_at_the_base_window(
        self, image_shapes, lifespan_client, remembered, monkeypatch
    ):
        """The clause a functional test misses, proved through the ROUTE (AC 7).

        Fail the **same key** twice so its window escalates to 60 s, recover it, then fail it once
        more — and show the new window is the **base** 30 s rather than the escalated 120 s.

        **The disk cache is disabled for this test, and that is the whole reason it works.** An
        earlier version of this test dodged the warm path by switching to ``size=large`` after the
        recovery — which changes the KEY, so the second failure was on a key that had never failed
        and the assertion held whether or not the route cleared anything. **Probe (e) caught that:
        deleting the route's ``clear`` call left all 980 tests green.** With the cache off, the same
        key can succeed and then fail again, which is the only shape that can see the defect.

        The arithmetic the timings encode: two failures put ``retry_after`` at 90 with a 60 s delay
        stored. Cleared, the next failure is 30 s and expires at 120. Uncleared, it is 60x2 = 120 s
        and expires at 210 — so a request at 120 fetches under the correct behaviour and is still
        backing off under the defect.
        """
        monkeypatch.setattr(images, "build_image_cache", lambda: None)
        clock, recorder = remembered
        recorder.raises = httpx.ConnectError("the CDN is unreachable")
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)
        base = images.NEGATIVE_CACHE_BASE_SECONDS

        async with lifespan_client(build_app()) as client:
            await client.get(path)
            clock.now += base
            await client.get(path)  # second consecutive failure -> escalates to 60 s

            recorder.raises = None
            clock.now += 2 * base
            success = await client.get(path)
            assert success.status_code == 200, "the escalated window never expired"

            # The SAME key fails again, immediately after recovering.
            recorder.raises = httpx.ConnectError("the CDN is unreachable again")
            failed_again = await client.get(path)
            assert failed_again.status_code == 502

            recorder.raises = None
            clock.now += base
            after_base = await client.get(path)

        assert after_base.status_code == 200, (
            "one base window after a single failure the key was STILL backing off, so its "
            "escalated history survived the success — a later blip leaves the tile blank for two "
            "minutes instead of thirty seconds, and every 'the retry happened' test passes anyway"
        )


class TestACancelledRequestIsNotAFailure:
    """**AC 10.** A browser navigating away from a deck view cancels ~99 requests.

    Recording those would poison the whole deck for one backoff window over a user action that
    failed at nothing. The mechanism is the narrow ``except CompanionError``:
    ``asyncio.CancelledError`` inherits ``BaseException``, so a bare ``except Exception`` would
    already miss it and this catch cannot see it at all.

    **The cancellation is parked MID-FETCH, and that placement is the test** (review 2026-08-02).
    The first draft cancelled after one bare yield, which lands the ``CancelledError`` at the
    route's *first* await — the database read — before the ``try`` block is ever entered, with the
    CDN in success mode: a zero that would survive a record-on-``BaseException`` mutation, proving
    nothing about the catch. ``stalled_cdn`` holds the fetch open so the cancel arrives inside
    ``fetch_image``, and the recorded upstream request is the positive observation that there was
    genuinely something in flight to mis-record.
    """

    async def test_a_cancelled_request_leaves_no_entry_behind(
        self, image_shapes, lifespan_client, stalled_cdn
    ):
        app = build_app()

        async with lifespan_client(app) as client:
            doomed = asyncio.create_task(client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)))
            await _until(
                lambda: stalled_cdn.in_flight >= 1,
                what="the doomed request to reach the upstream",
            )
            doomed.cancel()
            with pytest.raises((asyncio.CancelledError, httpx.HTTPError)):
                await doomed

            entries = images.negative_cache(app).entry_count

        assert stalled_cdn.requested, (
            "the fetch never started, so the cancellation exercised nothing cancellable"
        )
        assert entries == 0, (
            "a cancelled request was recorded as a CDN failure. One navigation away from a deck "
            "view would blank ~99 tiles for a full backoff window."
        )

    async def test_the_next_request_for_the_same_key_still_reaches_the_cdn(
        self, image_shapes, lifespan_client, stalled_cdn
    ):
        """The observable consequence, and it is the SAME key or it is nothing (review 2026-08-02).

        The zero above is an implementation detail; THIS is what the user experiences. The first
        draft's follow-up asked for ``size=large`` — a *different* key, which would have fetched
        happily even if the cancellation had been recorded against ``normal``: the change-the-key
        dodge probe (e) caught in the AC 7 test, reshipped. Asserted now on the two recorded URLs
        being identical, which a key change cannot fake.
        """
        async with lifespan_client(build_app()) as client:
            doomed = asyncio.create_task(client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)))
            await _until(
                lambda: stalled_cdn.in_flight >= 1,
                what="the doomed request to reach the upstream",
            )
            doomed.cancel()
            with pytest.raises((asyncio.CancelledError, httpx.HTTPError)):
                await doomed

            # The CDN is healthy — only the user went away — so release it for the retry.
            stalled_cdn.release.set()
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))

        assert response.status_code == 200
        assert len(stalled_cdn.requested) == 2, (
            "the retry never reached the CDN: the cancellation was remembered as a failure"
        )
        assert stalled_cdn.requested[0] == stalled_cdn.requested[1], (
            "the follow-up requested a different key, which proves nothing about the first"
        )

    async def test_a_wiring_bug_is_not_recorded_as_a_cdn_failure(
        self, image_shapes, lifespan_client, cdn, monkeypatch
    ):
        """The other half of the narrow catch: ``internal_error`` must not open a backoff window.

        A missing client or pacer means the lifespan did not run. Backing the key off for 30
        seconds would remember a CDN outage that never happened, and would do it for a fault the
        CDN had no part in. The guard runs AFTER the negative check by design, so this also pins
        that ordering from the outside.
        """
        app = build_app()

        async with lifespan_client(app) as client:
            app.state.image_pacer = None
            response = await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))
            entries = images.negative_cache(app).entry_count

        assert response.status_code == 500
        assert response.json() == {"reason": "internal_error"}
        assert entries == 0, "a wiring bug was remembered as a CDN failure"


class TestTheNegativeCacheTouchesNoDiskAndNoOtherApp:
    """**AC 9 and AC 11.** Nothing persisted, nothing shared, and the two caches independent."""

    async def test_a_failing_burst_writes_nothing_to_the_cache_root(
        self, image_shapes, lifespan_client, cdn
    ):
        """Listed through ``images.cache_root()`` (AC 22), so a cache writing somewhere unexpected
        reads as a failure rather than as an empty directory."""
        cdn.raises = httpx.ConnectError("the CDN is unreachable")
        ids, seeder = _seed_burst(20)
        await _seed(image_shapes, seeder)

        async with lifespan_client(build_app()) as client:
            for card_id in ids:
                assert (
                    await client.get(_IMAGE_PATH.format(scryfall_id=card_id))
                ).status_code == 502

        assert _cache_files() == [], (
            "the negative path wrote to disk; it is memory and nothing else"
        )

    async def test_but_a_served_image_still_lands_on_disk(self, image_shapes, lifespan_client, cdn):
        """NON-VACUITY for the empty listing above (AC 23): a write that DOES happen.

        Without it, ``_cache_files() == []`` also passes with the disk cache disabled, the write
        silently failing, or the listing pointed at a directory nothing writes to.
        """
        async with lifespan_client(build_app()) as client:
            assert (
                await client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID))
            ).status_code == 200

        assert [entry.name for entry in _cache_files()] == ["normal_0.jpg"]

    async def test_a_fresh_app_remembers_nothing(self, image_shapes, lifespan_client, cdn):
        """AC 9's ruling, as behaviour: restarting the companion is the user's one obvious remedy
        for a transient failure, and a state that outlived the restart would make it not work."""
        cdn.raises = httpx.ConnectError("the CDN is unreachable")
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            assert (await client.get(path)).status_code == 502
        fetches_after_first_process = len(cdn.requested)

        # A brand-new app — the "restart" this ruling is about.
        async with lifespan_client(build_app()) as client:
            assert (await client.get(path)).status_code == 502

        assert len(cdn.requested) == fetches_after_first_process + 1, (
            "the second process answered from a failure the FIRST one recorded. Nothing is "
            "persisted, so a restart must genuinely retry."
        )

    async def test_an_app_with_no_disk_cache_still_negative_caches(
        self, image_shapes, lifespan_client, cdn, monkeypatch
    ):
        """**AC 11**, first half: the two caches are independent.

        Q6's disable-don't-fail path leaves ``image_cache`` at ``None``; the negative cache cannot
        fail to construct, so it is unaffected. A route that read one guard for both would lose the
        backoff on exactly the installs that need it most.
        """
        monkeypatch.setattr(images, "build_image_cache", lambda: None)
        cdn.raises = httpx.ConnectError("the CDN is unreachable")
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            first = await client.get(path)
            second = await client.get(path)

        assert first.status_code == second.status_code == 502
        assert len(cdn.requested) == 1, (
            "with no disk cache the negative cache stopped working too — they are independent"
        )

    async def test_a_warm_disk_entry_is_served_whatever_the_failure_history(
        self, image_shapes, lifespan_client, remembered
    ):
        """**AC 11**, second half — seam 2's ordering claim stated as behaviour.

        The disk read comes FIRST. A key with a warm entry is served whatever it remembers, because
        the picture is already on this machine and no memory of a past outage should hide it. A
        negative check placed before the disk read would blank a tile the app could serve offline.
        """
        clock, recorder = remembered
        path = _IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID)

        async with lifespan_client(build_app()) as client:
            # Warm the disk on `normal`, then fail `large` so the app has a failure history.
            assert (await client.get(path)).status_code == 200
            recorder.raises = httpx.ConnectError("the CDN is unreachable")
            assert (await client.get(path, params={"size": "large"})).status_code == 502
            fetches_before = len(recorder.requested)
            time_before = clock.now

            warm = await client.get(path)

        assert warm.status_code == 200, "a warm tile was hidden by a sibling key's failure history"
        assert warm.content == recorder.body_for(_TOP_LEVEL_IMAGES["normal"])
        assert len(recorder.requested) == fetches_before, "the warm hit reached the transport"
        assert clock.now == time_before, (
            "the warm hit advanced the pacer's clock — it is served before the pacer is entered "
            "and before the negative check, so it owes neither a permit nor a spacing turn"
        )

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
        # c3-7's disk cache.
        "mkdir",
        "makedirs",
        "open",
        "write_bytes",
        "write_text",
        "data_dir",
        "NamedTemporaryFile",
        "replace",
        # c3-8's negative cache.
        "lru_cache",
        "cache",
    }
)
"""What ``images.py`` must not reach for, keyed on the NAME rather than on the spelling.

An identifier set over the parsed AST, not a substring scan over the source text, and the
difference is the whole design of this guard: this module's docstring *names* the disk cache and
``data_dir()`` in prose — deliberately, because the absences are decisions — so a text scan fires
on the documentation of the rule instead of on a breach of it. (Measured: the first version of
this test did exactly that, on its own module docstring.) The frontend hit the same wall at c3-2
and answered it the same way, by stripping comments before matching.

**c3-6 removed a third family from this set, and removed exactly that one** (2026-08-01).
``Semaphore``, ``BoundedSemaphore``, ``sleep`` and ``Lock`` were banned here under the comment
*"c3-6's pacer"*; that story then shipped the pacer, so the ban became a fence around the thing it
was built to schedule. The ten names above are **c3-7's and c3-8's**, they are untouched, and
deleting this frozenset wholesale would have taken two unwritten stories' fences with it silently.

The removal is not a loss of coverage, because the pacer's gate is stronger than a ban was: it is
no longer *"images.py has no semaphore"* but *"``src/companion`` constructs exactly **one**
pacer"*, asserted over the AST with a planted second construction site, in
``test_images.py::TestExactlyOnePacer``. The blocking-wait half moved there too, as
``TestTheLoopIsNeverBlocked`` — a ban on ``sleep`` by name could not survive this module gaining
an injected ``asyncio.sleep``, so it was re-keyed onto the family that actually matters:
*synchronous* waits, resolved through import aliases.
"""


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
    """The absences are decisions, and c3-7/c3-8 own them by name (c3-6 shipped and left)."""

    def test_no_disk_cache_and_no_negative_cache_are_built(self):
        names, _ = _identifiers_and_strings(_IMAGES_MODULE)

        breaches = sorted(names & _BANNED_IDENTIFIERS)
        assert not breaches, (
            f"images.py reaches for {breaches} — the disk cache is c3-7's and the negative cache "
            "c3-8's. An unused hook is a design decision made by a story that cannot see the "
            "requirements."
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

        **The aliased ``asyncio as aio`` semaphore stays in the plant, and that is deliberate**
        (c3-6). Seeing one is no longer a *breach* — this module owns a pacer now — but the claim
        this assertion makes is about the **scanner**, not about the ban: an alias-blind scanner
        would let c3-7's ``mkdir`` through under the identical spelling. So the name is asserted
        against ``names`` and is no longer asserted against ``_BANNED_IDENTIFIERS``, which is
        exactly the distinction the removal turned on.
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
        assert "mkdir" in names, "the disk-cache family missed a method call on a local"
        assert "functools.lru_cache" in names or "lru_cache" in names, (
            "the negative-cache family missed a renamed decorator import"
        )
        assert any(name.startswith("src.data.importers") for name in names)
        assert [s for s in strings if "api.scryfall.com" in s], (
            "the host scan missed a split f-string — the exact evasion c3-3 found 12 of"
        )

    def test_a_planted_breach_of_a_surviving_family_actually_fires_the_ban(self, tmp_path):
        """The firing half, over the set itself — the two surviving families still have teeth.

        Separate from the scanner test above because c3-6 split the two claims apart: *"the
        scanner sees it"* and *"the ban refuses it"* used to be one assertion, and conflating them
        is what would have made removing the pacer family look like removing coverage.
        """
        planted = tmp_path / "writes.py"
        planted.write_text(
            "from tempfile import NamedTemporaryFile\n"
            "\n"
            "\n"
            "def store(payload):\n"
            "    with NamedTemporaryFile(delete=False) as handle:\n"
            "        handle.write(payload)\n",
            encoding="utf-8",
        )

        names, _ = _identifiers_and_strings(planted)

        assert names & _BANNED_IDENTIFIERS == {"NamedTemporaryFile"}

    def test_the_scan_ignores_prose_that_merely_names_the_banned_things(self, tmp_path):
        """…and the other direction, which is what the first version of this guard got wrong.

        A module that *documents* the absence must stay green. Without this pairing, the guard
        above could be satisfied by deleting the docstrings that explain the design.

        The planted sentence changed at c3-6: it used to read *"No Semaphore here — the pacer is
        c3-6's"*, which stopped being true the day that story shipped. A plant nobody rewrites is
        how a test file starts asserting yesterday's design.
        """
        planted = tmp_path / "documented.py"
        planted.write_text(
            '"""Nothing here calls mkdir or data_dir, and there is no lru_cache."""\n'
            "\n"
            "VALUE = 1\n"
            '"""Not a call to api.scryfall.com either; this is an attribute docstring."""\n',
            encoding="utf-8",
        )

        names, strings = _identifiers_and_strings(planted)

        assert not (names & _BANNED_IDENTIFIERS)
        assert not [s for s in strings if "api.scryfall.com" in s]


# =============================================================================================
# Story c3-6: the pacer, at the level of the running app. AC 6, 7, 13; Q6.
#
# The pacer's own mechanics are proved as units in `test_images.py` on a fake clock. What can
# ONLY be proved here is what a real request does: that a queued burst does not stall the rest
# of the app, that a disconnecting browser gives its slot back, and that reading a deck fetches
# nothing at all.
# =============================================================================================


class StallableCdn:
    """A recorder whose responses can be held open indefinitely, with no time involved.

    An arbitrarily slow CDN expressed as an ``asyncio.Event`` rather than a duration: every
    request parks until a test releases it. That is what lets AC 6's interleaving *count* and
    AC 7's permit accounting be exact rather than probabilistic.

    Attributes:
        requested: Every URL asked for, in order.
        in_flight: How many upstream requests are open right now.
        completed: How many have finished.
    """

    def __init__(self) -> None:
        self.requested: list[str] = []
        self.in_flight = 0
        self.peak_in_flight = 0
        self.completed = 0
        self.release = asyncio.Event()

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requested.append(str(request.url))
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await self.release.wait()
        finally:
            self.in_flight -= 1
        self.completed += 1
        return httpx.Response(200, content=_JPEG, headers={"content-type": "image/jpeg"})


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
    stalled = StallableCdn()
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
        """99 concurrent requests — the measured distinct-id count of a real 100-card deck."""
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
                    client.get(_IMAGE_PATH.format(scryfall_id=SINGLE_FACE_ID), params={"face": 0})
                    for _ in range(99)
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

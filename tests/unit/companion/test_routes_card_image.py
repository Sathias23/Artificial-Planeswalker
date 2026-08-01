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

import json
from pathlib import Path

import httpx
import pytest

from src.companion.app import images
from src.companion.app.main import build_app
from src.companion.app.spa import _IMMUTABLE_CACHE_CONTROL
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
        # c3-6's pacer.
        "Semaphore",
        "BoundedSemaphore",
        "sleep",
        "Lock",
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
difference is the whole design of this guard: this module's docstring *names* the pacer, the disk
cache and ``data_dir()`` in prose — deliberately, because the absences are decisions — so a text
scan fires on the documentation of the rule instead of on a breach of it. (Measured: the first
version of this test did exactly that, on its own module docstring.) The frontend hit the same
wall at c3-2 and answered it the same way, by stripping comments before matching.
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
    """The absences are decisions, and c3-6/c3-7/c3-8 own them by name."""

    def test_no_pacer_no_disk_cache_and_no_negative_cache_are_built(self):
        names, _ = _identifiers_and_strings(_IMAGES_MODULE)

        breaches = sorted(names & _BANNED_IDENTIFIERS)
        assert not breaches, (
            f"images.py reaches for {breaches} — the pacer is c3-6's, the disk cache c3-7's and "
            "the negative cache c3-8's. An unused hook is a design decision made by a story that "
            "cannot see the requirements."
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
        spelled the way a naive scan would look for it — the semaphore arrives under an alias, the
        host arrives in an f-string, and the write arrives as a method call on a local.
        """
        planted = tmp_path / "planted.py"
        planted.write_text(
            "import asyncio as aio\n"
            "from src.data.importers.scryfall_api import fetch\n"
            "\n"
            "GATE = aio.Semaphore(4)\n"
            "BASE = 'api.scryfall.com'\n"
            "URL = f'https://{BASE}/cards/named'\n"
            "\n"
            "\n"
            "def go(path):\n"
            "    path.mkdir(parents=True, exist_ok=True)\n",
            encoding="utf-8",
        )

        names, strings = _identifiers_and_strings(planted)

        assert "Semaphore" in names, "the pacer family missed an aliased import"
        assert "mkdir" in names, "the disk-cache family missed a method call on a local"
        assert any(name.startswith("src.data.importers") for name in names)
        assert [s for s in strings if "api.scryfall.com" in s], (
            "the host scan missed a split f-string — the exact evasion c3-3 found 12 of"
        )

    def test_the_scan_ignores_prose_that_merely_names_the_banned_things(self, tmp_path):
        """…and the other direction, which is what the first version of this guard got wrong.

        A module that *documents* the absence must stay green. Without this pairing, the guard
        above could be satisfied by deleting the docstrings that explain the design.
        """
        planted = tmp_path / "documented.py"
        planted.write_text(
            '"""No Semaphore here — the pacer is c3-6\'s, and nothing calls mkdir or data_dir."""\n'
            "\n"
            "VALUE = 1\n"
            '"""Not a call to api.scryfall.com either; this is an attribute docstring."""\n',
            encoding="utf-8",
        )

        names, strings = _identifiers_and_strings(planted)

        assert not (names & _BANNED_IDENTIFIERS)
        assert not [s for s in strings if "api.scryfall.com" in s]


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

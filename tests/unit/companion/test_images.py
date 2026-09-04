"""Story c3-5: the face resolver and the fetch helpers, as pure units.

The route is driven end to end in ``test_routes_card_image.py``. **This file exists because the
resolver must be provable without a request** (AC 6): it is the one piece of code in the app that
decides which of a card's images answers a request, it keys on a rule four docstrings state in
prose, and getting it wrong means a split card silently serves the wrong half rather than raising
anything.

Every shape below is a **measured** row count against the shipped 38,261-card database
(re-verified on this machine at ``3bfe95f``, read-only):

    A  top-level ``image_uris``, ``card_faces`` null ......................... 35,036
    B  top-level ``image_uris`` + faces carrying NO images (split/adventure) ..... 368
    C  ``image_uris`` null + every face carrying its own ``image_uris`` ........ 2,778
    D  ``image_uris`` null + faces present, no images anywhere .................... 79
    -  ``image_uris`` null AND ``card_faces`` null .................................. 0

35,036 + 368 + 2,778 + 79 = 38,261, and **zero** cards carry both a top-level and a per-face map.
"""

import asyncio
from pathlib import Path

import httpx
import pytest

from src.companion.app import images
from src.companion.app.errors import CompanionError
from src.data.schemas.card import CardFace
from tests.unit.companion.conftest import FakeClock, StallableUpstream

_SIX = {
    "small": "https://cards.scryfall.io/small/x.jpg?1",
    "normal": "https://cards.scryfall.io/normal/x.jpg?1",
    "large": "https://cards.scryfall.io/large/x.jpg?1",
    "png": "https://cards.scryfall.io/png/x.png?1",
    "art_crop": "https://cards.scryfall.io/art_crop/x.jpg?1",
    "border_crop": "https://cards.scryfall.io/border_crop/x.jpg?1",
}
"""The one key-set that exists across all 40,960 stored ``image_uris`` objects — all six, always."""


def _pacer(*, spacing: float | None = None, limit: int | None = None) -> images.Pacer:
    """A pacer on virtual time — what every unit test in this file uses.

    Defaults to the **production** constants deliberately: a test that quietly paced at zero would
    prove nothing about the numbers that ship. Only the clock is fictional.

    Args:
        spacing: Override the shipped spacing, for a test that needs a distinguishable number.
        limit: Override the shipped concurrency cap.

    Returns:
        A pacer whose ``clock`` attribute is the :class:`FakeClock` driving it.
    """
    clock = FakeClock()
    pacer = images.Pacer(
        spacing=images.FETCH_SPACING_SECONDS if spacing is None else spacing,
        limit=images.FETCH_CONCURRENCY if limit is None else limit,
        clock=clock.time,
        sleep=clock.sleep,
    )
    # Attached so a test can read the virtual clock the pacer is actually running on, rather than
    # threading a second object through every helper.
    pacer.clock = clock  # type: ignore[attr-defined]
    return pacer


def _face(name: str, **extra: object) -> CardFace:
    """Build a face the way the database stores one: a dict, validated into the model."""
    return CardFace.model_validate({"name": name, **extra})


def _front_back() -> list[CardFace]:
    """Shape C: two faces, each with its own image, visibly different from the other."""
    return [
        _face("Front", image_uris={"normal": "https://cards.scryfall.io/normal/front.jpg?1"}),
        _face("Back", image_uris={"normal": "https://cards.scryfall.io/normal/back.jpg?1"}),
    ]


# ---------------------------------------------------------------------------------------------
# AC 6, AC 7: the four shapes, resolved
# ---------------------------------------------------------------------------------------------


class TestResolveFaceImages:
    """The rule this story exists to write: presence of per-face ``image_uris``, never a layout."""

    def test_shape_a_top_level_only_resolves_to_exactly_one_image(self) -> None:
        assert images.resolve_face_images(_SIX, None) == [_SIX]

    def test_shape_b_faces_without_images_still_resolve_to_the_top_level_image(self) -> None:
        # 368 real printings. Branching on `card_faces is not None` renders nothing for these,
        # which is the single most likely bug in this story.
        faces = [_face("Wear"), _face("Tear")]

        assert images.resolve_face_images(_SIX, faces) == [_SIX]

    def test_shape_b_five_faced_card_still_resolves_to_one_image(self) -> None:
        # `Who // What // When // Where // Why` — five faces, zero per-face images. A
        # `[front, back]` destructuring would be wrong on it; a face count would be wrong on it.
        faces = [_face(f"Face {n}") for n in range(5)]

        assert images.resolve_face_images(_SIX, faces) == [_SIX]

    def test_shape_c_resolves_one_entry_per_face_in_face_order(self) -> None:
        resolved = images.resolve_face_images(None, _front_back())

        assert len(resolved) == 2
        # Asserted distinguishably — c3-1's R3 finding was that identical fixtures prove nothing.
        assert resolved[0]["normal"].endswith("front.jpg?1")
        assert resolved[1]["normal"].endswith("back.jpg?1")
        assert resolved[0] != resolved[1]

    def test_shape_d_faces_with_no_images_anywhere_resolve_to_nothing(self) -> None:
        assert images.resolve_face_images(None, [_face("A"), _face("B")]) == []

    def test_neither_field_resolves_to_nothing(self) -> None:
        # Zero rows in the corpus; permitted by the schema, so its behaviour is known not assumed.
        assert images.resolve_face_images(None, None) == []

    def test_an_empty_face_list_falls_back_to_the_top_level_image(self) -> None:
        assert images.resolve_face_images(_SIX, []) == [_SIX]

    def test_an_empty_top_level_map_is_not_an_image(self) -> None:
        # `{}` is falsy but not None. A map with no sizes in it can serve nothing, so it must
        # resolve to the no-image answer rather than to an entry that indexes to a KeyError.
        assert images.resolve_face_images({}, None) == []

    def test_a_face_with_an_empty_image_map_does_not_count_as_imaged(self) -> None:
        assert images.resolve_face_images(_SIX, [_face("A", image_uris={})]) == [_SIX]

    def test_per_face_images_win_over_a_top_level_map(self) -> None:
        # Zero rows carry both, measured. The order is asserted anyway so the precedence is a
        # decision rather than an accident of which `if` came first.
        resolved = images.resolve_face_images(_SIX, _front_back())

        assert len(resolved) == 2
        assert resolved[0]["normal"].endswith("front.jpg?1")

    def test_a_partially_imaged_card_keeps_only_the_imaged_faces_in_face_order(self) -> None:
        # Zero rows today (a card's faces either all have images or none do). Pinned so the
        # chosen behaviour is recorded rather than discovered by whoever first meets one.
        faces = [
            _face("Plain"),
            _face("Imaged", image_uris={"normal": "https://cards.scryfall.io/normal/b.jpg?1"}),
        ]

        assert images.resolve_face_images(None, faces) == [
            {"normal": "https://cards.scryfall.io/normal/b.jpg?1"}
        ]

    def test_the_resolver_reads_no_layout_and_no_face_count(self) -> None:
        # The empirical form of AD-11's rule: `cards` has no `layout` column (23 columns,
        # verified) and only 66 of 6,455 stored face objects carry one. A resolver that consulted
        # either would answer differently for these two, and it must not.
        with_layout = [
            _face("A", layout="transform", image_uris={"normal": "https://cards.scryfall.io/a"}),
            _face("B", layout="transform", image_uris={"normal": "https://cards.scryfall.io/b"}),
        ]
        without_layout = [
            _face("A", image_uris={"normal": "https://cards.scryfall.io/a"}),
            _face("B", image_uris={"normal": "https://cards.scryfall.io/b"}),
        ]

        assert images.resolve_face_images(None, with_layout) == images.resolve_face_images(
            None, without_layout
        )

    def test_the_resolver_does_not_mutate_what_it_was_given(self) -> None:
        original = dict(_SIX)

        images.resolve_face_images(_SIX, None)[0]["normal"] = "https://evil.example/x.jpg"

        assert _SIX == original


# ---------------------------------------------------------------------------------------------
# AC 12: the URL is validated before it is fetched
# ---------------------------------------------------------------------------------------------


class TestUrlAllowList:
    """A stored URL is third-party data, not a licence to fetch from inside the user's network."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://cards.scryfall.io/normal/front/0/0/x.jpg?1700000000",
            # 3 real cards store this in all six size keys — Sparkspitter, Ondu Champion and
            # Gorehorn Minotaurs. Refusing it would report a fetch failure for data that is
            # exactly as Scryfall shipped it.
            "https://errors.scryfall.com/soon.jpg",
        ],
    )
    def test_an_allowed_origin_passes(self, url: str) -> None:
        assert images.is_fetchable(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "http://cards.scryfall.io/normal/x.jpg",  # scheme
            "https://cards.scryfall.io.evil.example/x.jpg",  # suffix-confusion
            "https://evilcards.scryfall.io/x.jpg",  # prefix-confusion
            "https://scryfall.io/x.jpg",  # the apex is not a member
            "https://127.0.0.1:8765/health",  # SSRF at the loopback the companion itself serves
            "https://169.254.169.254/latest/meta-data/",  # cloud metadata
            "file:///c:/windows/win.ini",
            "https://cards.scryfall.io@evil.example/x.jpg",  # userinfo confusion
            "",
            "not a url at all",
        ],
    )
    def test_a_disallowed_origin_is_refused(self, url: str) -> None:
        assert images.is_fetchable(url) is False

    def test_the_host_comparison_is_case_and_port_insensitive_in_the_right_directions(
        self,
    ) -> None:
        # DNS is case-insensitive, so an upper-cased host is the same origin…
        assert images.is_fetchable("https://CARDS.SCRYFALL.IO/x.jpg") is True
        # …but a non-default port is a different endpoint and is not on the list.
        assert images.is_fetchable("https://cards.scryfall.io:8443/x.jpg") is False


# ---------------------------------------------------------------------------------------------
# AC 11, AC 13, AC 14: the fetch itself
# ---------------------------------------------------------------------------------------------


def _client(handler) -> httpx.AsyncClient:
    """An image client whose transport is *handler* — no socket is ever opened."""
    return images.build_image_client(transport=httpx.MockTransport(handler))


class TestFetchImage:
    """Every upstream outcome maps to one of this story's two answers, and never to a substitute."""

    async def test_a_200_image_returns_its_bytes_and_its_own_content_type(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"\x89PNG-body", headers={"content-type": "image/png"}
            )

        async with _client(handler) as client:
            body, content_type = await images.fetch_image(client, _SIX["png"], _pacer())

        assert body == b"\x89PNG-body"
        assert content_type == "image/png"

    async def test_the_request_identifies_this_application(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

        async with _client(handler) as client:
            await images.fetch_image(client, _SIX["normal"], _pacer())

        agent = seen[0].headers["user-agent"]
        assert "Artificial-Planeswalker" in agent
        # Scryfall routinely blocks generic clients; a bare httpx default is one.
        assert "python-httpx" not in agent
        assert seen[0].headers["accept"].startswith("image/")

    async def test_the_url_is_sent_verbatim_including_its_cache_busting_query(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

        url = "https://cards.scryfall.io/normal/front/a/b/c.jpg?1700000000"
        async with _client(handler) as client:
            await images.fetch_image(client, url, _pacer())

        # Stripping the query would 404 upstream; rebuilding the path would be a construction.
        assert seen == [url]

    @pytest.mark.parametrize("status", [404, 403, 429, 500, 503])
    async def test_a_non_200_upstream_status_is_a_fetch_failure(self, status: int) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, content=b"nope", headers={"content-type": "image/jpeg"})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_non_image_content_type_is_a_fetch_failure(self) -> None:
        # A captive portal, an error page, or an HTML "soon" placeholder. Serving it through
        # would put attacker-influenced HTML on the companion's own origin.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_missing_content_type_is_a_fetch_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x", headers={})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_transport_failure_is_a_fetch_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host", request=request)

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_timeout_is_a_fetch_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_disallowed_url_is_refused_without_any_request_being_made(self) -> None:
        attempted: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempted.append(str(request.url))
            return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, "https://evil.example/x.jpg", _pacer())

        assert raised.value.reason == "image_fetch_failed"
        # The whole point: refused BEFORE the request, not after it.
        assert attempted == []

    async def test_the_allowed_case_does_reach_the_transport(self) -> None:
        # Non-vacuity pairing for the assertion above, from the same recorder shape: a guard that
        # blocked everything would pass that test and be useless.
        attempted: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempted.append(str(request.url))
            return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

        async with _client(handler) as client:
            await images.fetch_image(client, _SIX["normal"], _pacer())

        assert attempted == [_SIX["normal"]]

    async def test_an_unparseable_url_is_refused_not_crashed(self) -> None:
        # The refusal log names the host, and the first cut re-parsed the URL bare inside the
        # log line — an unparseable stored value crashed the refusal path itself with the
        # ValueError the guard had just survived (review 2026-08-01).
        attempted: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempted.append(str(request.url))
            return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, "https://[half-an-ipv6/x.jpg", _pacer())

        assert raised.value.reason == "image_fetch_failed"
        assert attempted == []

    async def test_an_empty_body_is_a_fetch_failure_not_a_success(self) -> None:
        # A 200 with an image type and ZERO bytes passes the status, type and size checks and
        # would be served — then cached immutable for a year: a permanently broken tile through
        # the success door (Greptile P1, PR #33). Zero bytes is not a picture.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"", headers={"content-type": "image/jpeg"})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_redirect_is_a_fetch_failure_and_is_never_followed(self) -> None:
        # The allow-list is checked on the STORED url only, so a followed redirect would fetch
        # whatever Location an allowed host answered — the exact SSRF the list exists to stop.
        # Ruled 2026-08-01 (review, Brad): the client does not follow; a 3xx is a fetch failure.
        attempted: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempted.append(str(request.url))
            return httpx.Response(301, headers={"location": "https://evil.example/steal.jpg"})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"
        # One request — the stored URL. The Location target was never contacted.
        assert attempted == [_SIX["normal"]]

    async def test_an_svg_content_type_is_a_fetch_failure(self) -> None:
        # SVG is the one image/* type that can carry script, and this route serves upstream
        # bytes from the SPA's own origin (review 2026-08-01). Parameters must not disguise it.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=b"<svg onload=alert(1)/>",
                headers={"content-type": "image/svg+xml; charset=utf-8"},
            )

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"

    async def test_an_oversized_declared_body_is_refused_before_it_is_read(self) -> None:
        read: list[bool] = []

        async def never_read():
            read.append(True)
            yield b"x"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=never_read(),
                headers={
                    "content-type": "image/png",
                    "content-length": str(images._MAX_IMAGE_BYTES + 1),
                },
            )

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["png"], _pacer())

        assert raised.value.reason == "image_fetch_failed"
        assert read == []

    async def test_an_oversized_streamed_body_is_abandoned_mid_stream(self, monkeypatch) -> None:
        # The ceiling is enforced WHILE streaming (review 2026-08-01): the first cut ran len()
        # on a body client.get() had already buffered whole, which protected nothing. An
        # upstream that lies about (or omits) Content-Length must still be cut off.
        monkeypatch.setattr(images, "_MAX_IMAGE_BYTES", 64)
        chunks_served: list[int] = []

        async def unbounded_body():
            for i in range(1000):
                chunks_served.append(i)
                yield b"x" * 32

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=unbounded_body(), headers={"content-type": "image/jpeg"}
            )

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"
        # Abandoned at the ceiling, not at the upstream's pleasure: 3 chunks crossed 64 bytes.
        assert len(chunks_served) < 1000


class TestImageClient:
    """AD-10: the client is inert to construct, and its deadlines are bounded on both axes."""

    async def test_the_client_carries_a_split_timeout_and_never_an_unbounded_one(self) -> None:
        async with images.build_image_client() as client:
            timeout = client.timeout

        # httpx's `read` deadline caps the gap BETWEEN CHUNKS, not the whole exchange — every
        # axis must be set, and `fetch_image` adds the whole-exchange bound separately.
        assert timeout.connect is not None
        assert timeout.read is not None
        assert timeout.write is not None
        assert timeout.pool is not None

    async def test_a_slow_drip_response_is_cut_off_by_the_whole_exchange_deadline(
        self, monkeypatch
    ) -> None:
        # The case `httpx`'s read timeout cannot see: every chunk arrives inside the read
        # deadline, but the body never ends. Without the outer bound one tile holds a connection
        # (and, from c3-6, a pacer slot) open forever.
        import asyncio

        monkeypatch.setattr(images, "_FETCH_TOTAL_SECONDS", 0.05)

        async def slow_body():
            for _ in range(1000):
                await asyncio.sleep(0.01)
                yield b"x"

        async def drip(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=slow_body(), headers={"content-type": "image/jpeg"})

        async with images.build_image_client(transport=httpx.MockTransport(drip)) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"], _pacer())

        assert raised.value.reason == "image_fetch_failed"


# =============================================================================================
# Story c3-6: the pacer. AC 3, 4, 5, 6, 7, 9, 10.
#
# Everything below asserts a NUMBER on virtual time. Not one of these tests waits.
# =============================================================================================


def _urls(count: int) -> list[str]:
    """*count* distinguishable allowed URLs.

    Distinguishable because c3-1's R3 finding was that identical fixtures prove nothing: an
    "ordering" assertion over one repeated URL is comparing a thing to itself.
    """
    return [
        f"https://cards.scryfall.io/normal/tile-{n:04d}.jpg?17000000{n:02d}" for n in range(count)
    ]


class TestSpacingBetweenStarts:
    """AC 4. Spacing is measured between fetch STARTS, globally, first-come-first-served."""

    async def test_consecutive_fetches_start_one_spacing_apart(self) -> None:
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock)

        async with _client(upstream.handle) as client:
            for url in _urls(4):
                await images.fetch_image(client, url, pacer)

        # Not an elapsed-seconds measurement: these are the START offsets the pacer itself
        # computed. The first is free and every later one is held to the spacing. `approx` is for
        # binary float accumulation only — the numbers are otherwise exact and reproducible.
        assert upstream.started_at == pytest.approx([0.0, 0.1, 0.2, 0.3])
        assert clock.slept == pytest.approx([0.1, 0.1, 0.1])

    async def test_the_first_fetch_of_a_process_is_not_delayed(self) -> None:
        """A cold app must paint its first tile immediately — the spacing is a gap between
        starts, not a toll on the first one."""
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock)

        async with _client(upstream.handle) as client:
            await images.fetch_image(client, _urls(1)[0], pacer)

        assert upstream.started_at == [0.0]
        assert clock.slept == [], "the first fetch paid a spacing turn it does not owe"

    async def test_spacing_is_global_across_unrelated_concurrent_callers(self) -> None:
        """AC 4's real claim: two fetches begun by UNRELATED requests are still spaced.

        Concurrent tasks, not a loop — a per-call delay would pass the sequential test above and
        fail this one, because nothing would be coordinating between the two callers.
        """
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock)
        urls = _urls(5)

        async with _client(upstream.handle) as client:
            await asyncio.gather(*(images.fetch_image(client, url, pacer) for url in urls))

        assert len(upstream.started_at) == 5
        gaps = [b - a for a, b in zip(upstream.started_at, upstream.started_at[1:])]
        assert gaps == pytest.approx([0.1, 0.1, 0.1, 0.1])

    async def test_the_queue_is_first_come_first_served(self) -> None:
        """Ordering is asserted where it was ARRANGED, not claimed as a general property.

        `asyncio.Lock` wakes waiters FIFO on CPython, and this pins that the pacer inherits it
        rather than reordering — the tasks are started one await apart so their arrival order is
        arranged rather than assumed.
        """
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock)
        urls = _urls(4)

        async with _client(upstream.handle) as client:
            tasks = []
            for url in urls:
                tasks.append(asyncio.create_task(images.fetch_image(client, url, pacer)))
                # One scheduling turn between creations, so arrival order is established here
                # rather than left to gather's internals.
                await asyncio.sleep(0)
            await asyncio.gather(*tasks)

        assert upstream.requested == urls

    async def test_spacing_is_between_starts_even_when_nothing_has_completed(self) -> None:
        """AC 4's actual claim, and the one assertion that separates the two designs.

        **Found by probe (f) of this story's mutation set, which every other test in this file
        passed.** Spacing computed from the previous *completion* rather than the previous *start*
        is invisible against a mock transport, because a mocked fetch is instantaneous and the two
        timestamps coincide. It is not invisible in production: completion-based spacing degrades
        into serialisation exactly when the CDN slows down, which is the opposite of what a
        concurrency cap is for. This is c3-5's review theme in this story's costume — a check that
        reads correct and measures the wrong moment.

        The CDN here **never answers**. Under start-based spacing all four fetches are admitted
        (the cap is 4) one spacing apart, because a start does not need a completion. Under
        completion-based spacing there are no completions to space from, so the four either pile
        up at t=0 or stall entirely — either way this assertion fails.
        """
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock, hold=True)

        async with _client(upstream.handle) as client:
            tasks = [asyncio.create_task(images.fetch_image(client, u, pacer)) for u in _urls(4)]
            for _ in range(200):
                await asyncio.sleep(0)

            started = list(upstream.started_at)

            upstream.release.set()
            await asyncio.gather(*tasks)

        assert started == pytest.approx([0.0, 0.1, 0.2, 0.3]), (
            f"four fetches started at {started} against a CDN that had answered NOTHING. "
            "Spacing must be measured between starts; measured between completions it "
            "serialises the moment the upstream slows down."
        )
        assert len(upstream.started_at) == 4
        assert upstream.in_flight == 0, "every fetch drained once the CDN was released"

    async def test_a_refused_url_costs_no_spacing_turn(self) -> None:
        """A URL the allow-list refuses makes no outbound request, so it must not consume a
        turn — otherwise a page full of refused URLs would throttle the fetches that are real."""
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock)

        async with _client(upstream.handle) as client:
            with pytest.raises(CompanionError):
                await images.fetch_image(client, "https://evil.example/x.jpg", pacer)
            await images.fetch_image(client, _urls(1)[0], pacer)

        assert upstream.started_at == [0.0], "the refusal burned a spacing turn it never used"
        assert clock.slept == []


class TestTheConcurrencyCap:
    """AC 5. The cap binds when the spacing cannot: a slow CDN."""

    async def test_simultaneous_upstream_requests_never_exceed_the_cap(self) -> None:
        """Asserted from the TRANSPORT's own accounting, never inferred from timing.

        The CDN is made arbitrarily slow with an `asyncio.Event` rather than a duration, so this
        test is exact and instant: eight fetches are launched, and no more than the cap are ever
        open at once no matter how long the upstream takes.
        """
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock, hold=True)
        urls = _urls(8)

        async with _client(upstream.handle) as client:
            tasks = [asyncio.create_task(images.fetch_image(client, url, pacer)) for url in urls]
            # Let the pacer admit everything it is willing to admit.
            for _ in range(200):
                await asyncio.sleep(0)

            admitted = upstream.in_flight
            peak = upstream.peak_in_flight
            upstream.release.set()
            await asyncio.gather(*tasks)

        assert admitted == images.FETCH_CONCURRENCY, (
            f"{admitted} requests were open against a stalled CDN; the cap is "
            f"{images.FETCH_CONCURRENCY}"
        )
        assert peak <= images.FETCH_CONCURRENCY
        assert len(upstream.started_at) == 8, "every fetch eventually ran"

    async def test_a_completed_fetch_hands_its_slot_to_the_next(self) -> None:
        pacer = _pacer(limit=2)
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock, hold=True)

        async with _client(upstream.handle) as client:
            tasks = [asyncio.create_task(images.fetch_image(client, u, pacer)) for u in _urls(4)]
            for _ in range(100):
                await asyncio.sleep(0)
            assert upstream.in_flight == 2

            upstream.release.set()
            await asyncio.gather(*tasks)

        assert upstream.peak_in_flight == 2
        assert len(upstream.started_at) == 4

    async def test_the_cap_does_not_bind_at_ordinary_latency(self) -> None:
        """The cap's justification is asymmetry: at normal latency the SPACING is what binds.

        min(1/S, N/L) = min(10/s, 4/0.2s = 20/s) = 10/s. If this ever inverts, one of the two
        constants moved and the docstrings' arithmetic went stale with it.
        """
        assert images.FETCH_CONCURRENCY / 0.2 > 1 / images.FETCH_SPACING_SECONDS


class TestCancellationReleasesTheSlot:
    """AC 7. A pacer that narrows over a session of scrolling is the failure mode."""

    async def test_a_cancelled_queued_fetch_leaks_no_permit(self) -> None:
        """A browser navigating away from a deck view is ~99 of these cancellations."""
        pacer = _pacer(limit=2)
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock, hold=True)
        before = pacer.available_permits

        async with _client(upstream.handle) as client:
            holding = [asyncio.create_task(images.fetch_image(client, u, pacer)) for u in _urls(2)]
            queued = asyncio.create_task(images.fetch_image(client, _urls(3)[2], pacer))
            for _ in range(50):
                await asyncio.sleep(0)
            assert upstream.in_flight == 2
            assert pacer.available_permits == 0

            queued.cancel()
            with pytest.raises(asyncio.CancelledError):
                await queued

            upstream.release.set()
            await asyncio.gather(*holding)

        assert pacer.available_permits == before, (
            "a cancelled fetch kept its permit — the pacer permanently narrowed"
        )

    async def test_the_next_fetch_proceeds_after_a_cancellation(self) -> None:
        pacer = _pacer(limit=1)
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock, hold=True)

        async with _client(upstream.handle) as client:
            holder = asyncio.create_task(images.fetch_image(client, _urls(1)[0], pacer))
            for _ in range(50):
                await asyncio.sleep(0)
            queued = asyncio.create_task(images.fetch_image(client, _urls(2)[1], pacer))
            for _ in range(50):
                await asyncio.sleep(0)

            queued.cancel()
            with pytest.raises(asyncio.CancelledError):
                await queued
            upstream.release.set()
            await holder

            # The proof that matters: a fetch AFTER the cancellation still gets through.
            await images.fetch_image(client, _urls(3)[2], pacer)

        assert len(upstream.started_at) == 2
        assert pacer.available_permits == 1

    async def test_a_cancellation_mid_spacing_wait_does_not_lose_the_turn(self) -> None:
        """The spacing half of AC 7, which is the easy one to get wrong.

        The cursor is advanced AFTER the wait, so a task cancelled while waiting its turn hands
        the turnstile straight to the next one rather than burning a 100 ms gap on nothing.

        The sleep is **gated on an event** rather than on the virtual clock, so the cancellation
        is guaranteed to land *inside* the wait. On the ordinary fake clock a spacing wait is one
        scheduling turn long, and a test that tried to cancel during it would be racing the thing
        it is trying to observe — which is how a timing test becomes a coin flip.
        """
        clock = FakeClock()
        gate = asyncio.Event()

        async def gated_sleep(delay: float) -> None:
            await gate.wait()
            clock.now += delay

        pacer = images.Pacer(clock=clock.time, sleep=gated_sleep)
        upstream = StallableUpstream(clock)

        async with _client(upstream.handle) as client:
            await images.fetch_image(client, _urls(1)[0], pacer)

            waiting = asyncio.create_task(images.fetch_image(client, _urls(2)[1], pacer))
            for _ in range(20):
                await asyncio.sleep(0)
            assert len(upstream.started_at) == 1, "the second fetch should still be waiting"

            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting

            gate.set()
            await images.fetch_image(client, _urls(3)[2], pacer)

        assert len(upstream.started_at) == 2
        # One spacing gap between the two fetches that actually happened — the cancelled one in
        # between neither delayed nor accelerated anything, and crucially did not consume the turn.
        assert upstream.started_at[1] - upstream.started_at[0] == pytest.approx(0.1)


class TestTheColdDeckPaint:
    """AC 10. The epic's stated observation, reproduced as a computation."""

    async def test_ninety_nine_distinct_tiles_model_the_epics_ten_seconds(self) -> None:
        """99 is MEASURED, not a round 100 (Task 0, re-verified against the live corpus).

        A real 100-card deck resolves to 67-99 **distinct card ids** because basic lands collapse;
        both `Atraxa Counter Cabinet` decks are 99, and the grid asks for face 0 only. So a cold
        deck paint is ~99 fetches, and this drives exactly that many through the shipped pacer on
        virtual time.

        The ~12 MB half of the epic's observation was ARITHMETIC on an assumed 124 KB average
        (12 MB / 99 tiles), not a byte measurement — the real-bytes profiling is c10-3's
        (epic :3588-3590). It is asserted here as arithmetic and nothing more. The C3
        retrospective (2026-08-02) then measured it at 8.5 MB / ~90 KB per tile, a 38 %
        overestimate, and story 15.3 corrected the epic to the measured figure on 2026-08-18 — so
        the epic no longer carries "12 MB" as a claim, only as a labelled superseded estimate.
        Nothing below changes: this test asserts the fetch COUNT and the spacing, not bytes.

        NFR-05 excludes first-fetch image paint from its budget, so this is an EXPECTED
        OBSERVATION rather than a defect.
        """
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock)
        urls = _urls(99)

        async with _client(upstream.handle) as client:
            await asyncio.gather(*(images.fetch_image(client, url, pacer) for url in urls))

        assert len(upstream.started_at) == 99
        assert upstream.started_at[0] == 0.0
        # 98 gaps of 0.1 s between 99 starts. The epic says "roughly 10 seconds"; this is it.
        assert upstream.started_at[-1] == pytest.approx(9.8, abs=1e-6)
        assert 9.5 <= upstream.started_at[-1] <= 10.0, "the epic's ~10 s is not reproduced"

        # And the megabytes, stated as the arithmetic it is.
        average_bytes = 124 * 1024
        assert round(99 * average_bytes / (1024 * 1024)) == 12

    async def test_the_same_burst_unpaced_would_be_instant(self) -> None:
        """NON-VACUITY for the test above: without the pacer the 99 starts collapse to t=0.

        Without this pairing the assertion "the last start is at 9.8 s" could not distinguish a
        working pacer from a broken clock.
        """
        pacer = _pacer(spacing=0.0, limit=99)
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = StallableUpstream(clock)

        async with _client(upstream.handle) as client:
            await asyncio.gather(*(images.fetch_image(client, u, pacer) for u in _urls(99)))

        assert upstream.started_at == [0.0] * 99
        assert clock.slept == []


# ---------------------------------------------------------------------------------------------
# AC 1, AC 2, AC 6: the structural half — one pacer, and nothing synchronous on the path.
# ---------------------------------------------------------------------------------------------


class TestFetchImageCannotBeCalledUnpaced:
    """AC 1's structural half: there is no signature that fetches without pacing (Q1)."""

    async def test_the_pacer_is_a_required_parameter(self) -> None:
        import inspect

        signature = inspect.signature(images.fetch_image)
        pacer_param = signature.parameters["pacer"]

        assert pacer_param.default is inspect.Parameter.empty, (
            "a defaulted pacer is a pacer a future caller can forget; AC 1 asks for a choke point "
            "no caller can route around, which means the parameter has no default"
        )
        assert pacer_param.annotation is images.Pacer

    async def test_calling_it_without_a_pacer_is_a_type_error(self) -> None:
        async with _client(lambda request: httpx.Response(200)) as client:
            with pytest.raises(TypeError):
                await images.fetch_image(client, _SIX["small"])  # type: ignore[call-arg]


# =============================================================================================
# Story c3-7: the sharded, atomically written disk cache, as units.
#
# The route-level behaviour (CM-2, offline, cold-vs-warm, the two failure postures) is driven in
# `test_routes_card_image.py`. What belongs HERE is the mechanism: the path, the extension rule,
# the atomicity of the write, and what each failure degrades to. `images.py` owns the mechanism,
# so `images.py`'s test module owns its unit tests (AC 21).
# =============================================================================================


_CARD = "0070bbf6-fdee-44ec-bfb8-3e99d6338e6e"
"""Sparkspitter's real id — one of the three cards whose ``png`` size resolves to a ``.jpg``."""


def _cache(tmp_path) -> images.DiskCache:
    """A cache rooted under *tmp_path*, built the way the lifespan builds one."""
    root = tmp_path / images.CACHE_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    return images.DiskCache(root)


class TestTheCachePath:
    """AC 1: the path is AD-11's, character for character."""

    def test_the_path_is_the_architecture_decision_spelled_out(self, tmp_path) -> None:
        """A CONSTRUCTED string against a known id, size and face — not a regex, and not the
        writer's own output round-tripped through the reader (which passes with both halves
        wrong, in matching ways).

        The two-hex shard is measured, not chosen: all **256** shards are used by the shipped
        corpus at **107-218** cards each (mean 149.5), against a flat **38,261** directories —
        AD-11's "roughly 60,000 entries" problem.
        """
        cache = _cache(tmp_path)

        path = cache.path_for(_CARD, "normal", 0, ".jpg")

        root = tmp_path / "image_cache"
        assert path == root / "00" / _CARD / "normal_0.jpg"
        assert str(path) == str(root / "00" / _CARD / "normal_0.jpg")

    def test_the_shard_is_the_first_two_characters_of_the_id_and_nothing_else(
        self, tmp_path
    ) -> None:
        cache = _cache(tmp_path)

        other = "ff70bbf6-fdee-44ec-bfb8-3e99d6338e6e"

        assert cache.path_for(other, "normal", 0, ".jpg").parent.parent.name == "ff"
        assert cache.path_for(_CARD, "normal", 0, ".jpg").parent.parent.name == "00"

    def test_the_size_and_face_are_both_in_the_filename(self, tmp_path) -> None:
        """Every one of the six sizes and a second face must land somewhere different, or the
        key is not id + size + face at all."""
        cache = _cache(tmp_path)

        names = {
            cache.path_for(_CARD, size, face, ".jpg").name
            for size in ("small", "normal", "large", "png", "art_crop", "border_crop")
            for face in (0, 1)
        }

        assert len(names) == 12
        assert "art_crop_0.jpg" in names, (
            "`art_crop` and `border_crop` contain underscores, so `<size>_<face>` yields "
            "`art_crop_0.jpg`. The filename is only ever CONSTRUCTED, never parsed back - the "
            "split is ambiguous and nothing in this module attempts it."
        )
        assert "border_crop_1.jpg" in names

    def test_every_id_the_route_can_accept_produces_a_path_inside_the_root(self, tmp_path) -> None:
        """AC 5's containment half, over the ids the route actually admits.

        ``_CARD_ID_PATTERN`` constrains the id to lowercase hex and hyphens before this code is
        ever reached (the cache sits behind ``card_not_found``, ``no_image_data`` and the size
        lookup), so there is deliberately no runtime containment guard here - an unused guard is
        a design decision made by a story that cannot see the requirements. What is asserted is
        the relationship: nothing matching that pattern escapes.
        """
        cache = _cache(tmp_path)
        root = cache.root.resolve()
        ids = (
            _CARD,
            "ffffffff-ffff-4fff-8fff-ffffffffffff",
            "00000000-0000-0000-0000-000000000000",
        )

        for card_id in ids:
            for size in ("small", "png", "border_crop"):
                for face in (0, 1, 7):
                    resolved = cache.path_for(card_id, size, face, ".png").resolve()
                    assert resolved.is_relative_to(root), resolved

    def test_the_containment_check_fires_on_a_path_that_escapes(self, tmp_path) -> None:
        """NON-VACUITY PAIRING (AC 20). ``is_relative_to`` proves nothing about the ids above
        unless it is seen to refuse something - a containment assertion that cannot fail is a
        sentence, not a gate. The escaping value is fed through the REAL ``path_for``.
        """
        cache = _cache(tmp_path)
        root = cache.root.resolve()

        escaped = cache.path_for("../../..", "normal", 0, ".jpg").resolve()

        assert not escaped.is_relative_to(root), (
            "the containment predicate accepted a path outside the root, so its use above is "
            "vacuous"
        )


class TestTheDocumentedCacheLayout:
    """``docs/companion.md`` shows one example cache path; it must be the path the code builds."""

    def test_the_documented_cache_layout_is_the_path_the_code_builds(self) -> None:
        guide = Path(__file__).resolve().parents[3] / "docs" / "companion.md"
        built = images._cache_path(
            Path(images.CACHE_DIRECTORY_NAME),
            "813d0434-8e0f-4b0a-9c7e-1f2a3b4c5d6e",
            "normal",
            0,
            ".jpg",
        )

        assert built.as_posix() in guide.read_text(encoding="utf-8"), (
            "docs/companion.md no longer shows the layout images._cache_path builds: "
            f"{built.as_posix()!r}"
        )


class TestTheExtensionIsNeverTakenFromTheSizeKey:
    """AC 2, and the defect it exists to prevent is SILENT: `png_0.png` holding JPEG bytes."""

    def test_a_png_size_resolving_to_a_jpg_url_is_stored_as_jpg(self) -> None:
        """The three real cards - Sparkspitter, Ondu Champion, Gorehorn Minotaurs - whose ``png``
        size is ``https://errors.scryfall.com/soon.jpg``, served as ``image/jpeg``. Measured:
        exactly **3** of the 245,760 stored URLs, and the reason `<ext>` may never be derived
        from the size name.
        """
        assert images.cache_extension("image/jpeg") == ".jpg"

    def test_an_ordinary_png_card_is_stored_as_png(self) -> None:
        """NON-VACUITY PAIRING: a discrimination, not a constant. Without this the assertion
        above passes against a function that returns ``".jpg"`` unconditionally.
        """
        assert images.cache_extension("image/png") == ".png"

    def test_a_content_type_with_parameters_still_resolves(self) -> None:
        assert images.cache_extension("image/jpeg; charset=binary") == ".jpg"

    def test_an_accepted_but_unmapped_image_type_is_served_and_not_cached(self) -> None:
        """Greptile P1 (2026-08-02), and the reason the URL is not even a fallback source.

        Everything that reaches the cache has already passed ``_is_servable_image_type``, so its
        header is always ``image/*`` — a header outside the two-entry map is therefore never
        octet-stream noise, it is a REAL third image format (``image/webp``). The first D1 patch
        kept the URL suffix as a fallback for exactly this case, which would have stored webp
        bytes as ``.jpg`` and re-served them warm as ``image/jpeg`` under ``nosniff`` +
        ``immutable`` — the identical media-type flip D1 existed to close, one branch deeper.
        A header the map cannot name means served, not cached; c3-2's finding applied: *this
        corpus* holds only `.jpg` and `.png`, a true count, not a rule Scryfall promises.
        """
        assert images.cache_extension("image/webp") is None
        assert images.cache_extension("image/avif") is None
        assert images.cache_extension("") is None

    def test_neither_the_size_key_nor_the_url_appears_in_the_derivation(self) -> None:
        """The signature itself is the guard: ``cache_extension`` cannot consult the size key OR
        the URL, because it is given neither (the URL was removed at Greptile P1, 2026-08-02 —
        an argument the function ignored would have been a lie in its contract)."""
        import inspect

        assert set(inspect.signature(images.cache_extension).parameters) == {"content_type"}


class TestTheCacheReadAndWrite:
    """AC 3, AC 4: what lands on disk, and what comes back."""

    async def test_a_written_entry_reads_back_byte_identical_with_its_media_type(
        self, tmp_path
    ) -> None:
        cache = _cache(tmp_path)
        payload = b"\xff\xd8\xff\xe0-a-photograph"

        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=payload,
        )

        assert await cache.read(_CARD, "normal", 0) == (payload, "image/jpeg")

    async def test_the_file_lands_at_exactly_the_constructed_path(self, tmp_path) -> None:
        """The write and the path rule are asserted against each other, not against themselves."""
        cache = _cache(tmp_path)

        await cache.write(
            card_id=_CARD,
            size="png",
            face=0,
            content_type="image/jpeg",
            body=b"\xff\xd8\xff\xe0-soon",
        )

        landed = tmp_path / "image_cache" / "00" / _CARD / "png_0.jpg"
        assert landed.is_file()
        assert not (tmp_path / "image_cache" / "00" / _CARD / "png_0.png").exists(), (
            "the extension came from the size key - silent on 245,757 of 245,760 URLs"
        )

    async def test_an_ordinary_png_card_lands_as_png_on_disk(self, tmp_path) -> None:
        """NON-VACUITY PAIRING for the assertion above, **at the level of the file** (AC 2).

        The extension rule is already proved as a discrimination on
        :func:`images.cache_extension`; this pairs it where the damage would actually happen. Both
        cards ask for ``size="png"``, and they must land under *different* extensions — so a write
        path that derived the extension from the size key would satisfy exactly one of the two,
        which is what makes the pair a discrimination rather than two constants.
        """
        cache = _cache(tmp_path)

        await cache.write(
            card_id=_CARD,
            size="png",
            face=0,
            content_type="image/png",
            body=b"\x89PNG\r\n\x1a\n-real",
        )

        assert (tmp_path / "image_cache" / "00" / _CARD / "png_0.png").is_file()
        assert not (tmp_path / "image_cache" / "00" / _CARD / "png_0.jpg").exists()
        assert await cache.read(_CARD, "png", 0) == (b"\x89PNG\r\n\x1a\n-real", "image/png")

    async def test_the_media_type_read_back_follows_the_bytes_not_the_size_key(
        self, tmp_path
    ) -> None:
        """The **corruption** the extension rule exists to prevent, stated as the round trip.

        This is the assertion that makes the rule matter rather than merely hold: a ``png``-size
        request whose URL is a ``.jpg`` must read back as ``image/jpeg``. Under a size-derived
        extension the bytes would be stored at ``png_0.png`` and served as ``image/png`` — JPEG
        bytes under a PNG media type, stamped ``immutable`` for a year. Silent on 245,757 of
        245,760 URLs and wrong on the other three.
        """
        cache = _cache(tmp_path)

        await cache.write(
            card_id=_CARD,
            size="png",
            face=0,
            content_type="image/jpeg",
            body=b"\xff\xd8\xff\xe0-soon",
        )

        assert await cache.read(_CARD, "png", 0) == (b"\xff\xd8\xff\xe0-soon", "image/jpeg")

    async def test_a_miss_is_none_rather_than_an_error(self, tmp_path) -> None:
        cache = _cache(tmp_path)

        assert await cache.read(_CARD, "normal", 0) is None

    async def test_the_three_parts_of_the_key_are_each_load_bearing(self, tmp_path) -> None:
        """A cache keyed on two of the three would serve one of these for another."""
        cache = _cache(tmp_path)
        other_id = "ff70bbf6-fdee-44ec-bfb8-3e99d6338e6e"

        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"a",
        )

        assert await cache.read(other_id, "normal", 0) is None, "the id is not part of the key"
        assert await cache.read(_CARD, "large", 0) is None, "the size is not part of the key"
        assert await cache.read(_CARD, "normal", 1) is None, "the face is not part of the key"
        assert await cache.read(_CARD, "normal", 0) == (b"a", "image/jpeg")

    async def test_the_cache_buster_query_is_not_part_of_the_key(self, tmp_path) -> None:
        """AD-11 keys on id + size + face and **accepts** the staleness that follows (epic
        :1763-1766). A refreshed row carrying a new ``?<timestamp>`` therefore HITS the existing
        entry. This is documented and asserted, not solved - keying on the URL would make every
        data refresh a full cache miss.
        """
        cache = _cache(tmp_path)

        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"the-old-bytes",
        )

        assert await cache.read(_CARD, "normal", 0) == (b"the-old-bytes", "image/jpeg")

    async def test_an_uncacheable_media_type_writes_nothing_at_all(self, tmp_path) -> None:
        cache = _cache(tmp_path)

        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/webp",
            body=b"webp",
        )

        assert list(cache.root.rglob("*")) == []

    async def test_a_rewrite_under_the_other_extension_displaces_the_stale_sibling(
        self, tmp_path
    ) -> None:
        """A key can change extensions across a data refresh (the placeholder trio's ``png`` size
        is a ``.jpg`` today and would be a ``.png`` if Scryfall ever supplied the real art), and
        ``_read_cached`` probes extensions in **fixed order** — so without displacement a stale
        ``.jpg`` would permanently shadow the fresh ``.png`` just written, and the new bytes
        would be unreachable forever (review 2026-08-01). The write therefore removes the same
        key's entry under every other extension after a successful replace.
        """
        cache = _cache(tmp_path)
        await cache.write(
            card_id=_CARD,
            size="png",
            face=0,
            content_type="image/jpeg",
            body=b"\xff\xd8\xff\xe0-placeholder",
        )

        await cache.write(
            card_id=_CARD,
            size="png",
            face=0,
            content_type="image/png",
            body=b"\x89PNG\r\n\x1a\n-the-real-art",
        )

        assert await cache.read(_CARD, "png", 0) == (b"\x89PNG\r\n\x1a\n-the-real-art", "image/png")
        assert not (tmp_path / "image_cache" / "00" / _CARD / "png_0.jpg").exists(), (
            "the stale sibling survived and, probed first, would shadow the fresh entry forever"
        )
        assert (tmp_path / "image_cache" / "00" / _CARD / "png_0.png").is_file()


class TestTheWriteIsAtomic:
    """AC 4: a crash mid-write can never leave a truncated file a later read would serve."""

    async def test_an_interrupted_write_leaves_no_target_and_no_temp_litter(
        self, tmp_path, monkeypatch
    ) -> None:
        """Interrupted **after the temp file exists and before the replace** - the only window
        in which a partial file could become visible under the real name.

        c3-5's review theme applied: atomicity is a property of the write SEQUENCE, not of a
        post-hoc check on the target. So the failure is injected at ``os.replace`` itself.
        """
        cache = _cache(tmp_path)
        directory = tmp_path / "image_cache" / "00" / _CARD

        def explode(*args, **kwargs):
            raise OSError("interrupted between the temp file and the rename")

        monkeypatch.setattr(images.os, "replace", explode)

        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"half",
        )

        assert not (directory / "normal_0.jpg").exists(), "a partial file became visible"
        assert list(directory.glob("*.tmp")) == [], "the interrupted write left .tmp litter"
        assert await cache.read(_CARD, "normal", 0) is None

    async def test_an_interrupted_rewrite_leaves_the_previous_entry_untouched(
        self, tmp_path, monkeypatch
    ) -> None:
        """The other half of "never a truncated file": an existing entry survives a failed
        rewrite exactly as it was, rather than being clobbered halfway."""
        cache = _cache(tmp_path)
        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"the-good-bytes",
        )

        def explode(*args, **kwargs):
            raise OSError("interrupted")

        monkeypatch.setattr(images.os, "replace", explode)
        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"x",
        )

        assert await cache.read(_CARD, "normal", 0) == (b"the-good-bytes", "image/jpeg")
        assert list((tmp_path / "image_cache" / "00" / _CARD).glob("*.tmp")) == []

    async def test_the_temp_file_is_uniquely_named_and_sits_beside_its_target(
        self, tmp_path, monkeypatch
    ) -> None:
        """``mkstemp`` in the TARGET'S OWN directory, not a fixed ``.tmp`` name and not ``%TEMP%``.

        Two writers cannot splice a fixed name, and ``os.replace`` is atomic only within one
        filesystem - a temp file in the system temp directory can be on another volume.
        Inherited from ``discovery.write_discovery``'s reasoning rather than re-derived.
        """
        cache = _cache(tmp_path)
        seen: list[tuple[str, str]] = []
        real_mkstemp = images.tempfile.mkstemp

        def record(**kwargs):
            descriptor, name = real_mkstemp(**kwargs)
            seen.append((str(kwargs.get("dir")), name))
            return descriptor, name

        monkeypatch.setattr(images.tempfile, "mkstemp", record)

        for _ in range(2):
            await cache.write(
                card_id=_CARD,
                size="normal",
                face=0,
                content_type="image/jpeg",
                body=b"a",
            )

        target_directory = str(tmp_path / "image_cache" / "00" / _CARD)
        assert [directory for directory, _ in seen] == [target_directory, target_directory]
        assert seen[0][1] != seen[1][1], "a fixed temp name lets two writers splice one file"

    async def test_nothing_is_fsynced(self, tmp_path, monkeypatch) -> None:
        """Q3, asserted rather than asserted-about. **Atomic is not durable, deliberately.**

        Temp + ``os.replace`` is what makes a reader never see a partial file; ``fsync`` is what
        makes the file survive a power cut, and a cache entry lost to a power cut costs exactly
        one refetch. Measured on this machine at Task 0: ``fsync`` costs **2.909 ms** against the
        whole write's **0.460 ms** - 6.3x, or 0.288 s of forced flushes on a cold 99-tile deck.
        The reason is the semantics; the number is the corroboration.
        """
        cache = _cache(tmp_path)
        calls: list[int] = []
        monkeypatch.setattr(images.os, "fsync", lambda fd: calls.append(fd))

        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"a",
        )

        assert calls == [], "the cache bought durability the architecture did not ask for"


class TestAnUnwritableRootStopsWarningEventually:
    """**AC 12, Q4 (Brad 2026-08-02): the disk cache learns from its own failures.**

    The louder of the two ``deferred-work.md`` entries c3-7's review homed on this story: *a root
    that exists but is unwritable leaves the cache "enabled" and logs a WARNING on every write —
    ~99 times per cold deck paint, forever.* It is not a defect (requests are unharmed, c3-7 AC 9)
    but *"logs 99 warnings per deck paint forever"* is what reads as broken to the first person who
    opens a log, and this is the story already reasoning about *how many times do we try before we
    stop*: a count, a threshold, a state change — the same shape as the backoff beside it.

    **The other entry — a transient startup ``OSError`` disabling the cache for the whole process —
    was NOT taken**, and is re-homed on **c8-2** with an honest reason: retrying the root means
    deciding *when* (at first write? on a timer?), which is a lifecycle question nothing here
    measures and this story has no requirement to answer.
    """

    @staticmethod
    def _always_fails(monkeypatch) -> None:
        """Make every write fail at the file layer, the way an unwritable root does."""

        def explode(*args, **kwargs):
            raise PermissionError("the root exists but is not writable")

        monkeypatch.setattr(images.tempfile, "mkstemp", explode)

    async def _paint(self, cache: images.DiskCache, tiles: int) -> None:
        for index in range(tiles):
            await cache.write(
                card_id=_CARD,
                size="normal",
                face=index,
                content_type="image/jpeg",
                body=b"a",
            )

    async def test_a_cold_paint_logs_a_bounded_number_of_warnings_not_one_per_tile(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        """The entry's own words, turned into a number: **~99 per paint** becomes at most the limit.

        Asserted on the count of WARNING records rather than on the disabled flag, because the log
        noise IS the reported problem — a fix that flipped an internal boolean and kept warning
        would satisfy every other assertion in this class.
        """
        cache = _cache(tmp_path)
        self._always_fails(monkeypatch)

        with caplog.at_level("WARNING", logger=images.logger.name):
            await self._paint(cache, 99)

        warnings = [record for record in caplog.records if record.levelname == "WARNING"]

        assert len(warnings) <= images.DISK_CACHE_WRITE_FAILURE_LIMIT, (
            f"a 99-tile paint against an unwritable root logged {len(warnings)} warnings. The "
            "whole point of the counter is that it stops."
        )
        assert warnings, "it logged NOTHING, which hides a real misconfiguration entirely"

    async def test_the_last_warning_says_the_cache_is_being_disabled(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        """Falling silent without saying so is worse than the noise it replaces.

        Someone reading the log has to be able to tell *"the cache gave up"* from *"the cache is
        working"* — otherwise the fix for a noisy log is indistinguishable from a cache that
        silently stopped storing anything.
        """
        cache = _cache(tmp_path)
        self._always_fails(monkeypatch)

        with caplog.at_level("WARNING", logger=images.logger.name):
            await self._paint(cache, 20)

        # Filtered to THIS module's logger (review 2026-08-02): `caplog.records` collects every
        # captured logger, so an unfiltered `[-1]` can be flipped by an unrelated library's
        # record for reasons that have nothing to do with this claim.
        ours = [record for record in caplog.records if record.name == images.logger.name]
        final = ours[-1].getMessage().lower()

        assert "disab" in final, f"the last word on the subject was {final!r}"

    async def test_requests_are_still_served_after_the_cache_disables_itself(
        self, tmp_path, monkeypatch
    ) -> None:
        """AC 9 is untouched by this: a cache failure is still never a request failure.

        The counter changes how LOUD the failure is, never what the caller gets. ``write`` returns
        normally whether it stored anything or not, which is what the route depends on.
        """
        cache = _cache(tmp_path)
        self._always_fails(monkeypatch)

        await self._paint(cache, 20)

        assert await cache.read(_CARD, "normal", 0) is None

    async def test_reads_keep_working_after_writes_are_disabled(
        self, tmp_path, monkeypatch
    ) -> None:
        """Disabling WRITES must not disable READS — they fail for unrelated reasons.

        A root that became unwritable may still hold everything a previous session cached, and
        NFR-06's *"fully functional with no network after warm-up"* depends on those reads. A fix
        that disabled the whole cache would trade a noisy log for an offline app.
        """
        cache = _cache(tmp_path)
        await cache.write(
            card_id=_CARD, size="normal", face=0, content_type="image/jpeg", body=b"warm"
        )
        assert await cache.read(_CARD, "normal", 0) is not None

        self._always_fails(monkeypatch)
        await self._paint(cache, 20)

        assert await cache.read(_CARD, "normal", 0) == (b"warm", "image/jpeg")

    async def test_one_success_resets_the_counter(self, tmp_path, monkeypatch) -> None:
        """NON-VACUITY, and the property that makes this safe (AC 23).

        **Consecutive** is the whole claim. Without the reset, an app that failed a handful of
        writes spread across an entire session — a transient lock, a virus scanner holding a
        handle — would eventually disable a cache that works perfectly well. Asserted by driving
        the counter to one below the limit, succeeding once, and then showing the cache still
        stores.
        """
        cache = _cache(tmp_path)

        for _ in range(images.DISK_CACHE_WRITE_FAILURE_LIMIT - 1):
            with monkeypatch.context() as failing:
                self._always_fails(failing)
                await cache.write(
                    card_id=_CARD, size="normal", face=0, content_type="image/jpeg", body=b"a"
                )

        await cache.write(
            card_id=_CARD, size="large", face=0, content_type="image/jpeg", body=b"good"
        )

        with monkeypatch.context() as failing:
            self._always_fails(failing)
            for _ in range(images.DISK_CACHE_WRITE_FAILURE_LIMIT - 1):
                await cache.write(
                    card_id=_CARD, size="normal", face=0, content_type="image/jpeg", body=b"a"
                )

        await cache.write(
            card_id=_CARD, size="png", face=0, content_type="image/jpeg", body=b"still working"
        )

        assert await cache.read(_CARD, "png", 0) == (b"still working", "image/jpeg"), (
            "the cache disabled itself over failures that were never consecutive"
        )

    async def test_a_lost_same_key_race_does_not_count_toward_disabling(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        """The Windows ``os.replace`` race carve-out (review 2026-08-02), both halves (AC 23).

        Two requests fetch one key, both write, and the loser's ``os.replace`` raises
        ``PermissionError`` over the file the winner still holds. The entry IS stored — by the
        winner — so the loser must neither warn nor feed the consecutive-failure counter: a lost
        race is not a broken root, and a handful of lost races during one paint must not latch
        writes off. The same exception with NO stored entry is the genuine unwritable root, still
        counts, and still disables — asserted from the same invocation.
        """
        cache = _cache(tmp_path)
        await cache.write(
            card_id=_CARD, size="normal", face=0, content_type="image/jpeg", body=b"winner"
        )

        def locked(source, destination):
            raise PermissionError("the winner still holds the freshly replaced file")

        with caplog.at_level("WARNING", logger=images.logger.name):
            with monkeypatch.context() as racing:
                racing.setattr(images.os, "replace", locked)
                for _ in range(images.DISK_CACHE_WRITE_FAILURE_LIMIT * 2):
                    await cache.write(
                        card_id=_CARD,
                        size="normal",
                        face=0,
                        content_type="image/jpeg",
                        body=b"loser",
                    )

        assert not caplog.records, (
            "a lost same-key race was counted or warned about; ten of them during one paint "
            "would have latched writes off over a root that works perfectly well"
        )
        assert await cache.read(_CARD, "normal", 0) == (b"winner", "image/jpeg")

        with caplog.at_level("WARNING", logger=images.logger.name):
            with monkeypatch.context() as broken:
                broken.setattr(images.os, "replace", locked)
                await self._paint(cache, images.DISK_CACHE_WRITE_FAILURE_LIMIT * 2)

        ours = [record for record in caplog.records if record.name == images.logger.name]
        assert ours, "a genuinely unwritable root fell silent without ever being counted"
        assert any("disab" in record.getMessage().lower() for record in ours), (
            "the carve-out swallowed the genuine unwritable-root case too"
        )

    async def test_a_locked_empty_target_is_counted_not_swallowed(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        """Greptile P1 (2026-08-02): presence is not the winner's signature — CONTENT is.

        ``_read_cached`` treats a zero-byte file as a miss, so a locked or read-only EMPTY target
        swallowed as a lost race would loop forever: every read misses, every write "wins", the
        counter resets, and the latch never announces a root that is genuinely stuck. A race
        winner's entry is never empty (``fetch_image`` refuses empty bodies), so the carve-out
        keys on ``st_size > 0`` and this case stays a counted failure.
        """
        cache = _cache(tmp_path)
        target = tmp_path / "image_cache" / _CARD[:2] / _CARD / "normal_0.jpg"
        target.parent.mkdir(parents=True)
        target.touch()

        def locked(source, destination):
            raise PermissionError("an indexer holds the zero-byte entry open")

        with caplog.at_level("WARNING", logger=images.logger.name):
            with monkeypatch.context() as broken:
                broken.setattr(images.os, "replace", locked)
                await self._paint(cache, images.DISK_CACHE_WRITE_FAILURE_LIMIT * 2)

        ours = [record for record in caplog.records if record.name == images.logger.name]
        assert ours, (
            "a locked zero-byte entry was swallowed as a lost race; that key would refetch "
            "forever and the latch would never announce the stuck root"
        )
        assert any("disab" in record.getMessage().lower() for record in ours)

    async def test_an_unreadable_non_empty_target_is_counted_not_swallowed(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        """Greptile round 2's residual (2026-08-02): size is not the winner's signature either.

        A non-empty target whose READS are denied while ``stat`` still reports a positive size —
        an exclusive external lock, a broken ACL — is a miss to ``_read_cached``, so swallowing
        its write as a lost race on size alone would refetch forever with the latch never
        announcing it. The carve-out therefore proves servability by reading a byte, exactly as
        the cache's own reader will, and this case stays a counted failure.
        """
        cache = _cache(tmp_path)
        target = tmp_path / "image_cache" / _CARD[:2] / _CARD / "normal_0.jpg"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"present but exclusively locked")

        def locked(source, destination):
            raise PermissionError("an external process holds the entry exclusively")

        real_open = Path.open

        def deny_reads(self, *args, **kwargs):
            if self == target:
                raise PermissionError("reads denied too")
            return real_open(self, *args, **kwargs)

        with caplog.at_level("WARNING", logger=images.logger.name):
            with monkeypatch.context() as broken:
                broken.setattr(images.os, "replace", locked)
                broken.setattr(Path, "open", deny_reads)
                await self._paint(cache, images.DISK_CACHE_WRITE_FAILURE_LIMIT * 2)

        ours = [record for record in caplog.records if record.name == images.logger.name]
        assert ours, (
            "an unreadable non-empty entry was swallowed as a lost race; that key would "
            "refetch forever and the latch would never announce the stuck root"
        )
        assert any("disab" in record.getMessage().lower() for record in ours)

    async def test_a_lost_race_does_not_reset_the_counter_either(
        self, tmp_path, monkeypatch
    ) -> None:
        """The other half of the Greptile P1: a lost race is not a SUCCESS any more than a failure.

        A run of genuine failures on other keys, one lost race in the middle, and the run must
        still latch: only a replace that actually lands proves the root works. Before the patch
        the benign path took the success branch and reset the count, so alternating races and
        failures could keep a broken root below the limit forever.
        """
        cache = _cache(tmp_path)
        await cache.write(
            card_id=_CARD, size="normal", face=0, content_type="image/jpeg", body=b"winner"
        )

        def locked(source, destination):
            raise PermissionError("locked")

        with monkeypatch.context() as failing:
            self._always_fails(failing)
            await self._paint(cache, images.DISK_CACHE_WRITE_FAILURE_LIMIT - 1)

        with monkeypatch.context() as racing:
            racing.setattr(images.os, "replace", locked)
            await cache.write(
                card_id=_CARD, size="normal", face=0, content_type="image/jpeg", body=b"loser"
            )

        with monkeypatch.context() as failing:
            self._always_fails(failing)
            await cache.write(
                card_id=_CARD, size="large", face=0, content_type="image/jpeg", body=b"a"
            )

        with monkeypatch.context() as failing:
            self._always_fails(failing)
            await self._paint(cache, 3)

        await cache.write(
            card_id=_CARD, size="png", face=0, content_type="image/jpeg", body=b"late"
        )
        assert await cache.read(_CARD, "png", 0) is None, (
            "the lost race reset the consecutive-failure count, so the run of genuine failures "
            "around it never latched — a broken root alternating with races stays unannounced"
        )

    async def test_two_caches_disable_independently(self, tmp_path, monkeypatch) -> None:
        """Per-instance state, like everything else in this module — never a module global.

        ``deps.Database``'s shipped ruling against globals, applied once more: a module-level flag
        would let one app's unwritable root disable an unrelated app's perfectly good cache, and in
        a test run it would make the order of tests decide the result.
        """
        first = _cache(tmp_path / "one")
        second = _cache(tmp_path / "two")

        with monkeypatch.context() as failing:
            self._always_fails(failing)
            await self._paint(first, images.DISK_CACHE_WRITE_FAILURE_LIMIT * 2)

        await second.write(
            card_id=_CARD, size="normal", face=0, content_type="image/jpeg", body=b"b"
        )

        assert await second.read(_CARD, "normal", 0) == (b"b", "image/jpeg"), (
            "one cache instance's failures disabled another instance's writes — the counter is a "
            "module global rather than per-instance state"
        )


class TestACacheFailureIsNeverARequestFailure:
    """AC 9: every failure degrades to *fetch it* and logs. No new reason token, no exception."""

    async def test_an_unwritable_directory_is_swallowed(self, tmp_path, monkeypatch) -> None:
        cache = _cache(tmp_path)

        def explode(*args, **kwargs):
            raise PermissionError("the directory is not writable")

        monkeypatch.setattr(images.tempfile, "mkstemp", explode)

        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"a",
        )

        assert await cache.read(_CARD, "normal", 0) is None

    async def test_a_permission_error_on_the_replace_is_swallowed(
        self, tmp_path, monkeypatch
    ) -> None:
        """The realistic Windows case: another handle holds the target open, so the loser of two
        concurrent writes for one key gets ``PermissionError`` from ``os.replace``. Q5 declined
        in-flight coalescing, which makes this reachable rather than theoretical."""
        cache = _cache(tmp_path)

        def explode(*args, **kwargs):
            raise PermissionError("another handle holds the target")

        monkeypatch.setattr(images.os, "replace", explode)

        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"a",
        )

        assert await cache.read(_CARD, "normal", 0) is None

    async def test_an_unreadable_entry_is_a_miss_not_a_raise(self, tmp_path, monkeypatch) -> None:
        cache = _cache(tmp_path)
        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"a",
        )

        def explode(self, *args, **kwargs):
            raise PermissionError("locked by another process")

        monkeypatch.setattr(images.Path, "read_bytes", explode)

        assert await cache.read(_CARD, "normal", 0) is None

    async def test_a_truncated_entry_is_a_miss_rather_than_an_empty_picture(self, tmp_path) -> None:
        """Zero bytes is not a picture (c3-5's Greptile P1, in the cache's costume). Temp +
        replace makes this unreachable through this module's own write path - but the file is on
        the user's disk and this module is not the only thing that can touch it."""
        cache = _cache(tmp_path)
        entry = tmp_path / "image_cache" / "00" / _CARD / "normal_0.jpg"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"")

        assert await cache.read(_CARD, "normal", 0) is None

    async def test_an_oversized_entry_is_a_miss_not_a_served_body(self, tmp_path) -> None:
        """The warm path enforces the same ceiling the fetch path enforces on the wire (review
        2026-08-01). Nothing this cache's own writer stores can exceed ``_MAX_IMAGE_BYTES`` —
        the fetch refuses the body first — so an oversized file is by definition not this app's
        work, and it is not loaded whole into memory and stamped ``immutable`` for a year.
        """
        cache = _cache(tmp_path)
        entry = tmp_path / "image_cache" / "00" / _CARD / "normal_0.jpg"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"\xff" * (images._MAX_IMAGE_BYTES + 1))

        assert await cache.read(_CARD, "normal", 0) is None

    async def test_a_failure_above_the_file_layer_is_still_never_a_raise(
        self, tmp_path, monkeypatch
    ) -> None:
        """``_read_cached``/``_write_atomically`` answer every *file*-layer failure, but
        ``asyncio.to_thread`` itself can refuse to schedule (interpreter shutdown, a closed
        default executor) — and that arrives as ``RuntimeError``, not ``OSError``. AC 9 does not
        distinguish by provenance: a cache failure of ANY kind is a fetch, never a failed
        request (review 2026-08-01 — the catch used to be ``OSError``-narrow while the docstring
        said "every failure").
        """
        cache = _cache(tmp_path)

        async def refuse(*args, **kwargs):
            raise RuntimeError("cannot schedule new futures after interpreter shutdown")

        monkeypatch.setattr(images.asyncio, "to_thread", refuse)

        assert await cache.read(_CARD, "normal", 0) is None
        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"a",
        )

    async def test_a_cache_root_that_is_a_file_degrades_rather_than_raising(self, tmp_path) -> None:
        """``mkdir(parents=True, exist_ok=True)`` still raises on this shape - a *file* where a
        directory belongs is ``FileExistsError``/``NotADirectoryError``, not an idempotent
        no-op."""
        root = tmp_path / "image_cache"
        root.write_text("not a directory", encoding="utf-8")
        cache = images.DiskCache(root)

        await cache.write(
            card_id=_CARD,
            size="normal",
            face=0,
            content_type="image/jpeg",
            body=b"a",
        )

        assert await cache.read(_CARD, "normal", 0) is None
        assert root.is_file(), "the cache clobbered something that was not its own"


class TestBuildingTheCache:
    """Q6: the lifespan creates the root; a failure disables the cache, never the launch."""

    def test_the_root_is_resolved_under_the_data_directory(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))

        assert images.cache_root() == tmp_path / "image_cache"

    def test_building_one_creates_the_root(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))

        cache = images.build_image_cache()

        assert cache is not None
        assert cache.root == tmp_path / "image_cache"
        assert cache.root.is_dir()

    def test_a_root_that_cannot_be_created_disables_the_cache_rather_than_raising(
        self, tmp_path, monkeypatch
    ) -> None:
        """Q6, and it is the half that keeps ``test_app.py::test_startup_failure_propagates``
        literally true: publishing the discovery file is still the ONLY startup step that can
        fail the launch. An app with no cache works and is slower; a half-launched rendezvous
        leaves every agent tool reporting ``app_not_running`` while the app visibly runs.
        """
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
        (tmp_path / "image_cache").write_text("a file where a directory belongs", encoding="utf-8")

        assert images.build_image_cache() is None


# =============================================================================================
# Story c3-7: the two positive gates that replace the eight names removed from
# `_BANNED_IDENTIFIERS` and the one removed from `_BLOCKING_CALLS`.
#
# c3-6 wrote the procedure down by doing it: remove your family, leave the rest, restate the
# comment, and replace the ban with a positive gate that is STRONGER than the ban was. A ban can
# only ever say "not here". These say "here, and nowhere else" and "on a thread, never on the
# loop" — neither of which the ban could express.
# =============================================================================================


# ---------------------------------------------------------------------------------------------
# Story c3-8: the negative cache, as a unit. AC 6, 8, 9.
#
# **Everything hard about this mechanism is expiry and bounds, and neither is visible in a
# functional test that makes two requests.** So the units below are where the schedule, the
# ceiling, the prune and the cap are actually proved; `test_routes_card_image.py` proves what a
# real request does with them. Every assertion here runs on `FakeClock` — a backoff test that
# sleeps for real time is the one thing this story could plausibly get wrong and still pass.
# ---------------------------------------------------------------------------------------------

_KEY = (_CARD, "normal", 0)
"""One key, in the id + size + face shape AD-11 gives the disk cache — the same key, on purpose."""


def _negative(clock: FakeClock, **overrides) -> images.NegativeCache:
    """A negative cache on virtual time, at the shipped numbers unless a test says otherwise.

    The clock is injected for the same reason ``Pacer``'s is (``images.py``): a window proved by
    measuring elapsed real time is slow when it passes and mysterious when it fails.
    """
    return images.NegativeCache(clock=clock.time, **overrides)


def _distinct_id(index: int) -> str:
    """A distinct, well-formed printing id per *index* — distinct KEYS are the point here."""
    return f"{index:08x}-fdee-44ec-bfb8-3e99d6338e6e"


class TestTheBackoffConstants:
    """AC 6, AC 8: the four numbers Q2 fixed, and the arithmetic that chose each one."""

    def test_the_shipped_numbers_are_the_ones_q2_ruled(self) -> None:
        assert images.NEGATIVE_CACHE_BASE_SECONDS == 30.0
        assert images.NEGATIVE_CACHE_MULTIPLIER == 2.0
        assert images.NEGATIVE_CACHE_CEILING_SECONDS == 300.0
        assert images.NEGATIVE_CACHE_MAX_ENTRIES == 2048

    def test_the_base_exceeds_one_full_cold_deck_paint(self) -> None:
        """The arithmetic that chose 30 s, asserted rather than described (AC 6).

        A base **shorter than one cold paint** re-admits the storm it exists to prevent: a second
        paint beginning after the first ended would find every window already expired. A cold
        99-tile paint is 98 spacings = 9.8 s at the shipped constants, so this inequality is what
        has to survive — not the number.
        """
        cold_paint = 98 * images.FETCH_SPACING_SECONDS

        assert images.NEGATIVE_CACHE_BASE_SECONDS > cold_paint, (
            f"a {images.NEGATIVE_CACHE_BASE_SECONDS} s base does not outlast a {cold_paint} s cold "
            "deck paint, so a reload would re-issue every request the backoff exists to suppress"
        )
        # ~3x rather than merely ">", which is the margin the ruling actually claims.
        assert images.NEGATIVE_CACHE_BASE_SECONDS > 3 * cold_paint

    def test_the_schedule_is_five_steps_and_the_last_one_lands_on_the_ceiling(self) -> None:
        """ "Five steps from base to ceiling" is a claim about the numbers, so it is asserted."""
        base = images.NEGATIVE_CACHE_BASE_SECONDS
        multiplier = images.NEGATIVE_CACHE_MULTIPLIER
        ceiling = images.NEGATIVE_CACHE_CEILING_SECONDS

        schedule = [min(base * multiplier**step, ceiling) for step in range(5)]

        assert schedule == [30.0, 60.0, 120.0, 240.0, 300.0]
        assert schedule[-1] == ceiling, "the fifth consecutive failure must land ON the ceiling"

    def test_the_cap_is_twice_this_users_library_and_a_fraction_of_the_key_space(self) -> None:
        """AC 8's arithmetic: 2,048 against a 1,061-id library and 245,760 reachable keys.

        Both bounds matter and they pull in opposite directions — too small and an ordinary
        session evicts, too large and "bounded" is a word rather than a bound.
        """
        whole_library = 1061
        reachable_keys = 245_760

        assert images.NEGATIVE_CACHE_MAX_ENTRIES > 1.5 * whole_library
        assert images.NEGATIVE_CACHE_MAX_ENTRIES < 0.01 * reachable_keys


class TestConstructionRefusesTheParametersThatBreakIt:
    """Review 2026-08-02: the injected-kwarg surface is real — this file injects it — so guard it.

    Not a startup risk, and the distinction is the accessor's whole "construction cannot fail"
    claim: the lifespan constructs with no arguments, which cannot raise. What these guard is a
    mis-injected TEST parameter, which previously produced a ``ValueError`` from ``min()`` on an
    empty dict deep inside the failure path (``max_entries=0``) or a backoff that silently shrank
    (``multiplier=0.5``) — both worse than refusing at the door.
    """

    def test_a_zero_entry_map_is_refused_at_construction(self) -> None:
        with pytest.raises(ValueError, match="max_entries"):
            images.NegativeCache(max_entries=0, clock=FakeClock().time)

    def test_a_shrinking_multiplier_is_refused_at_construction(self) -> None:
        with pytest.raises(ValueError, match="multiplier"):
            images.NegativeCache(multiplier=0.5, clock=FakeClock().time)

    def test_the_default_construction_cannot_fail(self) -> None:
        """The non-vacuity pair, and the lifespan's own path: no arguments, no raise (AC 23)."""
        assert images.NegativeCache().entry_count == 0

    def test_a_base_above_the_ceiling_is_clamped_from_the_first_failure(self) -> None:
        """`_RememberedFailure.delay` documents itself as "already clamped to the ceiling".

        Before the review patch only the ESCALATION branch clamped, so an injected
        ``base > ceiling`` served its entire first window above the documented maximum.
        """
        clock = FakeClock()
        cache = images.NegativeCache(base=500.0, ceiling=300.0, clock=clock.time)

        assert cache.record_failure(*_KEY) == 300.0


class TestTheBackoffWindow:
    """AC 6: the exact expiry boundaries, on virtual time and never on wall time."""

    def test_a_cold_key_is_not_backing_off(self) -> None:
        clock = FakeClock()
        cache = _negative(clock)

        assert cache.is_backing_off(*_KEY) is False
        assert cache.entry_count == 0

    def test_one_failure_opens_the_base_window(self) -> None:
        clock = FakeClock()
        cache = _negative(clock)

        delay = cache.record_failure(*_KEY)

        assert delay == images.NEGATIVE_CACHE_BASE_SECONDS
        assert cache.is_backing_off(*_KEY) is True
        assert cache.entry_count == 1

    def test_a_request_just_before_the_expiry_still_backs_off(self) -> None:
        """``expiry - eps``. A boundary is asserted from BOTH sides or it is not asserted."""
        clock = FakeClock()
        cache = _negative(clock)
        cache.record_failure(*_KEY)

        clock.now = images.NEGATIVE_CACHE_BASE_SECONDS - 0.001

        assert cache.is_backing_off(*_KEY) is True

    def test_a_request_exactly_at_the_expiry_fetches(self) -> None:
        """``expiry`` itself is a FETCH — the window is half-open, and which way it rounds is a
        decision rather than an accident."""
        clock = FakeClock()
        cache = _negative(clock)
        cache.record_failure(*_KEY)

        clock.now = images.NEGATIVE_CACHE_BASE_SECONDS

        assert cache.is_backing_off(*_KEY) is False

    def test_consecutive_failures_escalate_through_the_whole_schedule(self) -> None:
        """AC 6's escalation, measured as the delays actually applied."""
        clock = FakeClock()
        cache = _negative(clock)

        applied = []
        for _ in range(5):
            applied.append(cache.record_failure(*_KEY))
            # Step past each window, so every failure is genuinely the NEXT consecutive one
            # rather than a repeat inside one that is still open.
            clock.now += applied[-1]

        assert applied == [30.0, 60.0, 120.0, 240.0, 300.0]

    def test_the_delay_stops_at_the_ceiling_rather_than_growing_forever(self) -> None:
        """The half a "consecutive failures escalate" test misses (AC 6).

        Without it, ``base * 2 ** n`` passes every escalation assertion above and reaches a
        four-hour window by the twelfth failure — a tile broken for the rest of the session, which
        is the permanently-broken-tile defect AD-11's *"with backoff"* exists to prevent.
        """
        clock = FakeClock()
        cache = _negative(clock)

        applied = []
        for _ in range(12):
            applied.append(cache.record_failure(*_KEY))
            clock.now += applied[-1]

        assert applied[4:] == [300.0] * 8, "the delay grew past the ceiling"
        assert max(applied) == images.NEGATIVE_CACHE_CEILING_SECONDS

    def test_a_repeat_failure_inside_an_open_window_still_escalates(self) -> None:
        """A failure recorded while a window is open is still a failure.

        Reachable in production: two tabs, or a request already in flight when the first one
        failed. It escalates rather than resetting, because *"how bad is this outage"* is what the
        count measures.
        """
        clock = FakeClock()
        cache = _negative(clock)

        first = cache.record_failure(*_KEY)
        second = cache.record_failure(*_KEY)

        assert (first, second) == (30.0, 60.0)

    def test_keys_back_off_independently(self) -> None:
        """id, size and face are all part of the key, so a failure on one must not silence a
        sibling. Three separate assertions, because a key that dropped ANY of the three would pass
        a test that varied only the id."""
        clock = FakeClock()
        cache = _negative(clock)

        cache.record_failure(_CARD, "normal", 0)

        assert cache.is_backing_off(_CARD, "normal", 0) is True
        assert cache.is_backing_off("ff70bbf6-fdee-44ec-bfb8-3e99d6338e6e", "normal", 0) is False
        assert cache.is_backing_off(_CARD, "large", 0) is False
        assert cache.is_backing_off(_CARD, "normal", 1) is False


class TestRecoveryClearsTheHistory:
    """AC 7's last clause — the one a functional test misses entirely."""

    def test_clearing_a_key_ends_its_backoff(self) -> None:
        clock = FakeClock()
        cache = _negative(clock)
        cache.record_failure(*_KEY)

        cache.clear(*_KEY)

        assert cache.is_backing_off(*_KEY) is False
        assert cache.entry_count == 0

    def test_a_recovered_key_starts_its_next_failure_at_the_base_delay(self) -> None:
        """Fail x4, succeed, fail once — measuring the window against the base, not against step 5.

        This is the assertion the story names as the one no functional test can make: every *"the
        retry happened"* test passes with the history left intact, and the defect surfaces only as a
        tile broken for five minutes after a single blip, weeks later.
        """
        clock = FakeClock()
        cache = _negative(clock)

        for _ in range(4):
            clock.now += cache.record_failure(*_KEY)
        assert cache.record_failure(*_KEY) == 300.0, "four failures must have escalated at all"

        cache.clear(*_KEY)
        after_recovery = cache.record_failure(*_KEY)

        assert after_recovery == images.NEGATIVE_CACHE_BASE_SECONDS, (
            f"a key that recovered and then failed once backed off for {after_recovery} s instead "
            "of the base 30 s — its failure history survived the success"
        )

    def test_clearing_a_key_that_never_failed_is_silent(self) -> None:
        """The route clears on EVERY success, so the overwhelmingly common call is this one."""
        clock = FakeClock()
        cache = _negative(clock)

        cache.clear(*_KEY)

        assert cache.entry_count == 0

    def test_clearing_one_key_leaves_its_siblings_alone(self) -> None:
        """Q5's reason for keeping the ban, restated as a property that is actually asserted:
        ``functools.cache``'s ``cache_clear()`` is all-or-nothing, and this is not."""
        clock = FakeClock()
        cache = _negative(clock)
        cache.record_failure(_CARD, "normal", 0)
        cache.record_failure(_CARD, "large", 0)

        cache.clear(_CARD, "normal", 0)

        assert cache.is_backing_off(_CARD, "normal", 0) is False
        assert cache.is_backing_off(_CARD, "large", 0) is True


class TestTheMapIsBounded:
    """AC 8: 245,760 keys are reachable, so an unbounded map is the absence of a design."""

    def test_a_closed_window_does_not_erase_the_failure_history(self) -> None:
        """The distinction the first implementation of this class got wrong, pinned first.

        A window closing means *this key may be fetched again*. It does **not** mean *this key never
        failed* — and an implementation that drops the entry at ``retry_after`` resets the
        escalation on every attempt, so a key against a permanently dead CDN cycles at 30 s forever
        and the schedule is unreachable in production. This is the assertion that separates the two
        designs; the escalation tests above do not, because they step the clock only as far as they
        must and pass under both.
        """
        clock = FakeClock()
        cache = _negative(clock)

        first = cache.record_failure(*_KEY)
        clock.now = images.NEGATIVE_CACHE_BASE_SECONDS
        assert cache.is_backing_off(*_KEY) is False, "the window must genuinely have closed"

        second = cache.record_failure(*_KEY)

        assert (first, second) == (30.0, 60.0), (
            "a failure after the window closed restarted at the base delay — the backoff never "
            "escalates against the one upstream it exists for, a permanently dead one"
        )

    def test_a_key_is_forgotten_a_full_ceiling_after_its_window_closes(self) -> None:
        """The retention horizon, asserted from BOTH sides (AC 8).

        ``retry_after + ceiling``: a key that has gone the longest backoff this cache can apply
        without failing again is not having a run of failures, it is having a new one. This is the
        fifth number in the mechanism and Q2 did not fix it, so it is asserted rather than assumed.
        """
        clock = FakeClock()
        cache = _negative(clock)
        cache.record_failure(*_KEY)
        horizon = images.NEGATIVE_CACHE_BASE_SECONDS + images.NEGATIVE_CACHE_CEILING_SECONDS

        clock.now = horizon - 0.001
        assert cache.record_failure(*_KEY) == 60.0, "forgotten one tick too early"

        # A fresh cache, so the second half measures the horizon rather than the escalation above.
        cache = _negative(clock)
        clock.now = 0.0
        cache.record_failure(*_KEY)
        clock.now = horizon

        assert cache.record_failure(*_KEY) == images.NEGATIVE_CACHE_BASE_SECONDS, (
            "the key was still remembered a full ceiling past its window; a map that never forgets "
            "reaches its cap on garbage and then evicts LIVE entries to make room for it"
        )

    def test_stale_entries_are_pruned_rather_than_merely_ignored(self) -> None:
        """*"Ignored"* reaches the cap on garbage; *"pruned"* does not.

        Asserted on ``entry_count``, which is the only thing that can tell the two designs apart —
        every behavioural assertion in this file is identical under both.
        """
        clock = FakeClock()
        cache = _negative(clock)
        for face in range(4):
            cache.record_failure(_CARD, "normal", face)
        assert cache.entry_count == 4

        clock.now = images.NEGATIVE_CACHE_BASE_SECONDS + images.NEGATIVE_CACHE_CEILING_SECONDS
        cache.record_failure("ff70bbf6-fdee-44ec-bfb8-3e99d6338e6e", "normal", 0)

        assert cache.entry_count == 1, (
            "the four stale entries were still resident. A map that only IGNORES expiry reaches "
            "its cap on garbage and then evicts LIVE entries to make room for it."
        )

    def test_the_map_never_exceeds_its_cap(self) -> None:
        """A plant of cap + N distinct failing keys leaves the map at exactly the cap."""
        clock = FakeClock()
        cache = _negative(clock, max_entries=4)

        for index in range(4 + 3):
            cache.record_failure(_distinct_id(index), "normal", 0)

        assert cache.entry_count == 4

    def test_eviction_drops_the_entry_closest_to_being_useless(self) -> None:
        """The tiebreak, asserted by WHICH key survived rather than by the count.

        Earliest ``retry_after`` first: that entry is nearest to expiring anyway, so dropping it
        costs the least. A cap enforced by evicting an arbitrary key passes the count assertion
        above while throwing away the entry with the most time left on it.

        **The clock advances by 10 s and not by 30 s, and that is the whole test.** At 30 s every
        entry has expired, so the prune alone produces the same three assertions and the eviction
        path is never reached — the test would pass with the tiebreak deleted. Caught while
        implementing it; the story's own warning about assertions that pass for the wrong reason.
        """
        clock = FakeClock()
        cache = _negative(clock, max_entries=2)

        cache.record_failure("aaa", "normal", 0)
        # Escalate this one, so its window reaches further out than a first failure's.
        cache.record_failure("bbb", "normal", 0)
        clock.now += 10.0
        cache.record_failure("bbb", "normal", 0)

        cache.record_failure("ccc", "normal", 0)

        assert cache.entry_count == 2
        assert cache.is_backing_off("aaa", "normal", 0) is False, "the earliest expiry survived"
        assert cache.is_backing_off("bbb", "normal", 0) is True
        assert cache.is_backing_off("ccc", "normal", 0) is True

    def test_an_evicted_key_simply_fetches_again(self) -> None:
        """NON-VACUITY for the bound (AC 8, AC 23): the honest cost, asserted rather than described.

        An eviction is not a failure — it costs **exactly one extra fetch**, which is what makes a
        cap acceptable at all. Stated as behaviour: the evicted key reports *not backing off*.
        """
        clock = FakeClock()
        cache = _negative(clock, max_entries=1)
        cache.record_failure("aaa", "normal", 0)
        assert cache.is_backing_off("aaa", "normal", 0) is True

        cache.record_failure("bbb", "normal", 0)

        assert cache.is_backing_off("aaa", "normal", 0) is False
        assert cache.is_backing_off("bbb", "normal", 0) is True

    def test_re_recording_a_resident_key_does_not_grow_the_map(self) -> None:
        """The realistic shape of a real outage: the same 99 keys failing over and over.

        Without this, *"bounded"* could be true only because eviction ran constantly — which would
        make every escalation asserted above unreachable in production.
        """
        clock = FakeClock()
        cache = _negative(clock, max_entries=4)

        for _ in range(50):
            cache.record_failure(*_KEY)

        assert cache.entry_count == 1


class TestTheNegativeCacheHoldsNothingButMemory:
    """AC 9: nothing is persisted, and nothing survives the process."""

    def test_constructing_one_cannot_fail_and_touches_no_disk(self, tmp_path, monkeypatch) -> None:
        """The prediction Q1 rests on, confirmed by measurement rather than by argument.

        ``Pacer``-shaped, not ``DiskCache``-shaped: no ``build_*`` factory, no ``_shutdown`` change,
        and ``test_app.py::test_startup_failure_propagates`` stays literally true. Proved by
        pointing the data directory somewhere that does not exist — a ``DiskCache`` needs
        ``build_image_cache`` here, and this needs nothing at all.
        """
        unwritable = tmp_path / "definitely" / "not" / "there"
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(unwritable / "nope"))

        cache = images.NegativeCache()

        assert cache.entry_count == 0
        assert not unwritable.exists(), "constructing a negative cache created a directory"

    def test_two_caches_do_not_share_state(self) -> None:
        """Q1's rejection of a module-level dict, as a property rather than a paragraph.

        A global would serialise unrelated apps in a test run and hide a real double-creation bug —
        ``deps.Database``'s shipped ruling. Per-app instances are also what make AC 9's *"a fresh
        app remembers nothing"* testable at all.
        """
        clock = FakeClock()
        first = _negative(clock)
        second = _negative(clock)

        first.record_failure(*_KEY)

        assert first.is_backing_off(*_KEY) is True
        assert second.is_backing_off(*_KEY) is False

    def test_the_default_clock_is_monotonic_and_never_the_wall_clock(self) -> None:
        """A wall clock moves backwards on an NTP step and across a DST boundary, which would
        either free every entry at once or freeze one for an hour. ``Pacer`` made this choice first
        and this inherits it — asserted, because the two spellings differ by four characters.
        """
        import inspect
        import time as time_module

        default = inspect.signature(images.NegativeCache.__init__).parameters["clock"].default

        assert default is time_module.monotonic
        assert default is not time_module.time

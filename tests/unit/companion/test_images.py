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

import ast
import asyncio
from pathlib import Path

import httpx
import pytest

from src.companion.app import images
from src.companion.app.errors import CompanionError
from src.data.schemas.card import CardFace

_SIX = {
    "small": "https://cards.scryfall.io/small/x.jpg?1",
    "normal": "https://cards.scryfall.io/normal/x.jpg?1",
    "large": "https://cards.scryfall.io/large/x.jpg?1",
    "png": "https://cards.scryfall.io/png/x.png?1",
    "art_crop": "https://cards.scryfall.io/art_crop/x.jpg?1",
    "border_crop": "https://cards.scryfall.io/border_crop/x.jpg?1",
}
"""The one key-set that exists across all 40,960 stored ``image_uris`` objects — all six, always."""


class FakeClock:
    """Virtual time: the clock moves only when the pacer sleeps on it (c3-6 AC 9, Q3).

    **This is the whole answer to "how do you test a rate without spending one".** The pacer takes
    its clock and its sleep as constructor parameters, so a test can hand it a pair that advances a
    counter instead of waiting. Start offsets are then asserted **exactly** — ``0.0``, ``0.1``,
    ``0.2`` — at zero wall-clock cost, where a real-time proof would be both slow and flaky on a
    loaded box.

    ``await asyncio.sleep(0)`` inside :meth:`sleep` is a bare yield to the event loop, not a wait:
    it costs no wall clock and it is what keeps the *concurrency* real while the *time* is fake.
    Other tasks genuinely run at that point, so an ordering bug is still visible.

    **The re-entrancy assertion is load-bearing and is the fake checking its own premise.**
    ``now += delay`` is only exact while at most one task sleeps at a time, which holds because the
    pacer sleeps inside its turnstile lock. If a redesign ever sleeps outside that lock, two
    concurrent sleepers would double-advance the clock and every pacing assertion in this file
    would quietly start measuring fiction — so the fake refuses instead.

    Attributes:
        now: The current virtual time, in seconds.
        slept: Every delay the pacer asked for, in order. A pacer that never sleeps leaves this
            empty, which several tests below assert directly.
    """

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []
        self._sleeping = False

    def time(self) -> float:
        """Return the current virtual time, in the shape ``time.monotonic`` has."""
        return self.now

    async def sleep(self, delay: float) -> None:
        """Advance virtual time by *delay* and yield to the loop.

        Args:
            delay: Seconds to wait for, as the pacer computed them.
        """
        assert not self._sleeping, (
            "two tasks slept on this clock at once — `now += delay` is only exact while the "
            "pacer sleeps inside its turnstile, so this fake would be lying about the numbers"
        )
        self._sleeping = True
        try:
            self.slept.append(delay)
            self.now += delay
            await asyncio.sleep(0)
        finally:
            self._sleeping = False


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


class Upstream:
    """A CDN that records when each request STARTED and can be held open indefinitely.

    Three things it exists to measure, none of which a response body can show:

    * **when** each fetch began, read off the pacer's own virtual clock — AC 4 is about start
      times, and c3-5's review theme was a check that ran after the thing it was meant to prevent;
    * **how many** requests are open at once, from the transport's own accounting (entered minus
      completed) rather than inferred from timing — AC 5;
    * **that a fetch began at all**, so "zero outbound requests" is a positive observation.

    Attributes:
        started_at: The virtual time each request began, in start order.
        urls: The URL of each request, in start order.
        in_flight: How many requests are open right now.
        peak_in_flight: The high-water mark of :attr:`in_flight` — the number AC 5 asserts on.
    """

    def __init__(self, clock: FakeClock, *, hold: bool = False) -> None:
        self._clock = clock
        self.started_at: list[float] = []
        self.urls: list[str] = []
        self.in_flight = 0
        self.peak_in_flight = 0
        # An arbitrarily slow CDN, expressed with no time at all: every request parks on this
        # event until a test sets it. AC 5's "made arbitrarily slow" without a single second.
        self.release = asyncio.Event()
        if not hold:
            self.release.set()

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.started_at.append(self._clock.time())
        self.urls.append(str(request.url))
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await self.release.wait()
        finally:
            self.in_flight -= 1
        return httpx.Response(200, content=b"\xff\xd8body", headers={"content-type": "image/jpeg"})


class TestTheTwoConstants:
    """AC 3. The numbers that ship, and the arithmetic that chose them."""

    def test_the_spacing_is_the_top_of_scryfalls_published_band(self) -> None:
        assert images.FETCH_SPACING_SECONDS == 0.1

    def test_the_cap_bounds_simultaneous_upstream_requests(self) -> None:
        assert images.FETCH_CONCURRENCY == 4

    def test_the_spacing_reproduces_the_epics_cold_deck_observation(self) -> None:
        """The epic's "roughly 12 MB over roughly 10 seconds" IS this constant (AC 10).

        99 distinct ids on a real 100-card deck (measured: 67-99 across the 18 saved decks with
        >=90 cards, and 99 on both `Atraxa Counter Cabinet` decks) x 0.1 s spacing. The first
        start is free, so the last of 99 begins after 98 gaps.
        """
        assert round(98 * images.FETCH_SPACING_SECONDS, 6) == 9.8

    def test_the_docstrings_say_the_guidance_does_not_apply_to_this_host_family(self) -> None:
        """AC 3's teeth: a constant justified by a rule that EXEMPTS this route is prose
        outrunning code (c3-4's review theme), pre-committed as a gate rather than a promise.

        Keyed on the exemption, not on the number: the number is already asserted above, and a
        docstring that recites `10 requests/second` without the exemption is exactly the defect.
        """
        spacing_doc = _attribute_docstring("FETCH_SPACING_SECONDS")

        assert "scryfall.io" in spacing_doc, (
            "the spacing constant must name the host family it actually fetches from"
        )
        assert "exempt" in spacing_doc.lower(), (
            "the *.scryfall.io file origins are EXEMPT from Scryfall's rate guidance; a docstring "
            "that presents this number as compliance is the prose-outruns-code finding"
        )
        assert "good citizen" in spacing_doc.lower() or "good-citizen" in spacing_doc.lower()

    def test_the_cap_docstring_carries_the_arithmetic_it_is_justified_by(self) -> None:
        cap_doc = _attribute_docstring("FETCH_CONCURRENCY")

        # The cap NEVER binds at normal latency and binds hard on a degraded CDN — that asymmetry
        # is its entire justification, so it has to be written down where the number is.
        assert "min(" in cap_doc, "the throughput model min(1/S, N/L) is the cap's justification"


def _attribute_docstring(name: str) -> str:
    """Return the attribute docstring written under module-level ``name`` in ``images.py``.

    Read off the parsed source rather than at runtime, because Python discards attribute
    docstrings entirely — they exist only in the AST, which is also where c3-5's guard reads.

    Args:
        name: The module-level constant to read the docstring of.

    Returns:
        The docstring text, or ``""`` when the constant carries none.
    """
    tree = ast.parse(_IMAGES_SOURCE.read_text(encoding="utf-8"))
    body = tree.body
    for index, node in enumerate(body):
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            first = node.targets[0]
            target = first.id if isinstance(first, ast.Name) else None
        if target != name:
            continue
        following = body[index + 1] if index + 1 < len(body) else None
        if (
            isinstance(following, ast.Expr)
            and isinstance(following.value, ast.Constant)
            and isinstance(following.value.value, str)
        ):
            return following.value.value
        return ""
    raise AssertionError(f"images.py has no module-level constant named {name!r}")


_IMAGES_SOURCE = Path(images.__file__)


class TestSpacingBetweenStarts:
    """AC 4. Spacing is measured between fetch STARTS, globally, first-come-first-served."""

    async def test_consecutive_fetches_start_one_spacing_apart(self) -> None:
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = Upstream(clock)

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
        upstream = Upstream(clock)

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
        upstream = Upstream(clock)
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
        upstream = Upstream(clock)
        urls = _urls(4)

        async with _client(upstream.handle) as client:
            tasks = []
            for url in urls:
                tasks.append(asyncio.create_task(images.fetch_image(client, url, pacer)))
                # One scheduling turn between creations, so arrival order is established here
                # rather than left to gather's internals.
                await asyncio.sleep(0)
            await asyncio.gather(*tasks)

        assert upstream.urls == urls

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
        upstream = Upstream(clock, hold=True)

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
        upstream = Upstream(clock)

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
        upstream = Upstream(clock, hold=True)
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
        upstream = Upstream(clock, hold=True)

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
        upstream = Upstream(clock, hold=True)
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
        upstream = Upstream(clock, hold=True)

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
        upstream = Upstream(clock)

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

        The ~12 MB half of the epic's observation is ARITHMETIC on the measured 124 KB average
        (12 MB / 99 tiles), not a byte measurement — the real-bytes profiling is c10-3's
        (epic :3588-3590). It is asserted here as arithmetic and nothing more.

        NFR-05 excludes first-fetch image paint from its budget, so this is an EXPECTED
        OBSERVATION rather than a defect.
        """
        pacer = _pacer()
        clock = pacer.clock  # type: ignore[attr-defined]
        upstream = Upstream(clock)
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
        upstream = Upstream(clock)

        async with _client(upstream.handle) as client:
            await asyncio.gather(*(images.fetch_image(client, u, pacer) for u in _urls(99)))

        assert upstream.started_at == [0.0] * 99
        assert clock.slept == []


# ---------------------------------------------------------------------------------------------
# AC 1, AC 2, AC 6: the structural half — one pacer, and nothing synchronous on the path.
# ---------------------------------------------------------------------------------------------

_COMPANION_SOURCES = sorted((Path(images.__file__).parents[2] / "companion").rglob("*.py"))


def _pacer_construction_sites() -> list[tuple[str, int]]:
    """Every place in ``src/companion`` that constructs a :class:`~images.Pacer`.

    **Keyed on the class, resolved through import aliases — never on the spelling** (c3-3's
    headline finding: a guard caught 0 of 12 planted evasions because every family was keyed on
    the syntax its own firing tests used). Three spellings all count as one family here:
    ``Pacer()``, ``images.Pacer()``, and ``from ...images import Pacer as Anything`` followed by
    ``Anything()``.

    Returns:
        ``(relative path, line number)`` for each construction site found.
    """
    sites: list[tuple[str, int]] = []
    for path in _COMPANION_SOURCES:
        sites.extend(
            (path.name, line) for line in _pacer_calls_in(path.read_text(encoding="utf-8"))
        )
    return sites


def _pacer_calls_in(source: str) -> list[int]:
    """Return the line numbers at which *source* constructs a ``Pacer``.

    The declared residual hole (house rule — every AST guard names what it cannot see, review
    2026-08-01): a construction reached through a bound callable — ``cls = Pacer; cls()``, or
    ``getattr(images, "Pacer")()`` — is invisible here, as it is to every scanner in this suite.
    Writing one of those in ``src/companion`` is obfuscation of the choke point, not a pass.

    Args:
        source: Python source text.

    Returns:
        One line number per construction site.
    """
    tree = ast.parse(source)
    # Local names bound to the Pacer class, however the import spelled it.
    bound = {"Pacer"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            bound.update(
                alias.asname or alias.name for alias in node.names if alias.name == "Pacer"
            )
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in bound:
            lines.append(node.lineno)
        elif isinstance(func, ast.Attribute) and func.attr == "Pacer":
            lines.append(node.lineno)
    return lines


class TestExactlyOnePacer:
    """AC 1, AC 2. "One backend-global choke point" as a gate, not a sentence."""

    def test_the_whole_backend_constructs_exactly_one_pacer(self) -> None:
        sites = _pacer_construction_sites()

        assert len(sites) == 1, (
            f"src/companion constructs {len(sites)} pacers ({sites}). AD-11 asks for ONE "
            "backend-global semaphore plus request spacing — not one per route, per card or per "
            "client. A second one silently doubles the rate this app offers Scryfall."
        )

    def test_the_one_construction_site_is_the_lifespan(self) -> None:
        [(module, _line)] = _pacer_construction_sites()

        assert module == "main.py", (
            "the pacer is created beside the image client in the lifespan (Q1, Brad 2026-08-01); "
            "AD-10 keeps build_app() free of side effects and only the lifespan owns startup state"
        )

    def test_the_scan_catches_a_second_pacer_spelled_to_evade(self) -> None:
        """NON-VACUITY, spelled the way a real second one would arrive (AC 2, AC 23).

        Not `Pacer()` — that spelling is what the firing test above already looks for, and c3-3's
        lesson is that a guard keyed on its own examples proves only that it catches them. So the
        plant arrives under an aliased import bound to a differently-named local.
        """
        planted = (
            "from src.companion.app.images import Pacer as RateGate\n"
            "from src.companion.app import images as _img\n"
            "\n"
            "GATE = RateGate(spacing=0.05, limit=8)\n"
            "OTHER = _img.Pacer()\n"
        )

        assert _pacer_calls_in(planted) == [4, 5], (
            "the single-pacer scan missed an aliased import and/or a module-attribute call — "
            "the two spellings a second pacer would most plausibly arrive under (the bound-"
            "callable spelling is the scan's declared residual hole)"
        )

    def test_the_scan_does_not_fire_on_prose_or_on_a_mere_reference(self) -> None:
        """…and the other direction, from the same function (standing agreement).

        Type annotations, imports and docstrings NAME the class constantly — this module's own
        `fetch_image` signature does. Only a CALL is a construction site.
        """
        quiet = (
            '"""The Pacer is constructed once, in the lifespan — see Pacer()."""\n'
            "from src.companion.app.images import Pacer\n"
            "\n"
            "\n"
            "def fetch(pacer: Pacer) -> Pacer:\n"
            "    reference = Pacer\n"
            "    return reference\n"
        )

        assert _pacer_calls_in(quiet) == []


_BLOCKING_MODULES = frozenset({"threading", "concurrent.futures", "multiprocessing", "subprocess"})
"""Module families whose whole surface is a synchronous wait (AD-11, AC 6).

Banned wholesale rather than member by member — the C2 retro's standing agreement, and the reason
this survives `from threading import Semaphore as S`: the *module* is resolved through the import,
so no alias helps.
"""

_BLOCKING_CALLS = frozenset({"run_in_executor", "to_thread"})
"""The two ways an ``async def`` reaches a thread pool anyway. Banned by name, wherever reached."""


def _blocking_waits_in(source: str) -> list[str]:
    """Return every synchronous-wait spelling *source* reaches for (AC 6, source-level half).

    ``time`` itself cannot be banned — the pacer's default clock is ``time.monotonic``, which is
    the one thing in that module that does not wait — so ``sleep`` is banned **through** it, with
    import aliases resolved so ``import time as t; t.sleep(1)`` is still caught, and caught at the
    import itself for the ``from`` form, so ``from time import sleep as pause`` (or via ``*``) has
    no alias that helps either (review 2026-08-01 — the first shipped version keyed only on the
    attribute access and missed the plainest spelling, the one the retired name ban did catch).

    Args:
        source: Python source text.

    Returns:
        A sorted list of the offending dotted spellings, resolved to their real module names.
    """
    tree = ast.parse(source)
    # alias -> real module, for every module imported here.
    modules: dict[str, str] = {}
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules[alias.asname or alias.name.split(".")[0]] = alias.name
                if alias.name in _BLOCKING_MODULES:
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in _BLOCKING_MODULES or module.split(".")[0] in _BLOCKING_MODULES:
                found.update(f"{module}.{alias.name}" for alias in node.names)
            elif module == "time":
                # `from time import sleep [as anything]` — the plainest spelling of the banned
                # member, flagged at the import so no alias helps. `*` is included: a star-import
                # makes a bare `sleep(1)` reachable with no bound name left to track.
                found.update("time.sleep" for alias in node.names if alias.name in {"sleep", "*"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in _BLOCKING_CALLS:
                found.add(node.attr)
            if isinstance(node.value, ast.Name):
                real = modules.get(node.value.id, node.value.id)
                if real == "time" and node.attr == "sleep":
                    found.add("time.sleep")
                elif real in _BLOCKING_MODULES:
                    found.add(f"{real}.{node.attr}")
        elif isinstance(node, ast.Name) and node.id in _BLOCKING_CALLS:
            found.add(node.id)
    return sorted(found)


class TestTheLoopIsNeverBlocked:
    """AC 6, source-level half. `async` throughout: no thread, no synchronous sleep."""

    def test_the_image_module_reaches_for_no_synchronous_wait(self) -> None:
        offences = _blocking_waits_in(_IMAGES_SOURCE.read_text(encoding="utf-8"))

        assert offences == [], (
            f"images.py reaches for {offences}. AD-11: the pacer is async throughout and must "
            "never block the event loop — a blocking wait paces correctly and stalls every other "
            "request in the process while it does."
        )

    def test_the_scan_catches_every_synchronous_spelling_including_aliased_ones(self) -> None:
        """NON-VACUITY, and every plant is deliberately spelled to evade (AC 23).

        `import time as clock_mod` is the one that matters: the module cannot be banned outright
        because `time.monotonic` is the pacer's default clock, so the ban keys on the member
        THROUGH the alias.
        """
        planted = (
            "import time as clock_mod\n"
            "from threading import Semaphore as Gate\n"
            "from concurrent.futures import ThreadPoolExecutor\n"
            "import multiprocessing\n"
            "\n"
            "\n"
            "async def go(loop, fn):\n"
            "    clock_mod.sleep(0.1)\n"
            "    await loop.run_in_executor(None, fn)\n"
        )

        offences = _blocking_waits_in(planted)

        assert "time.sleep" in offences, "an aliased `import time as x` walked straight through"
        assert "threading.Semaphore" in offences, "a renamed `from threading import ... as` evaded"
        assert "concurrent.futures.ThreadPoolExecutor" in offences
        assert "multiprocessing" in offences
        assert "run_in_executor" in offences

    def test_the_from_import_spelling_is_caught_at_the_import_itself(self) -> None:
        """The hole the first shipped scanner had (review 2026-08-01): its `ImportFrom` arm only
        knew the wholesale-banned modules, so `from time import sleep` — the plainest spelling of
        the banned member, and the one the retired `_BANNED_IDENTIFIERS` name ban DID catch —
        walked straight through, aliased or not. A guard that replaces a ban must not be weaker
        than the ban on the ban's own examples."""
        assert _blocking_waits_in("from time import sleep\n") == ["time.sleep"]
        assert _blocking_waits_in("from time import sleep as pause\n\npause(1)\n") == [
            "time.sleep"
        ], "the alias hid the from-import"
        assert _blocking_waits_in("from time import *\n") == ["time.sleep"], (
            "a star-import makes a bare sleep(1) reachable with no name left to track"
        )

    def test_the_scan_stays_silent_on_the_clock_the_pacer_actually_uses(self) -> None:
        """The pairing: `time.monotonic` and `asyncio.sleep` are the RIGHT answers and must not
        fire. Without this, the guard above could be satisfied by deleting the injected clock."""
        legitimate = (
            "import asyncio\n"
            "import time\n"
            "from time import monotonic\n"
            "\n"
            "\n"
            "async def wait(delay):\n"
            "    started = monotonic()\n"
            "    await asyncio.sleep(delay)\n"
            "    return time.monotonic() - started\n"
        )

        assert _blocking_waits_in(legitimate) == []


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

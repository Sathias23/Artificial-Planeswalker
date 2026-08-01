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
            body, content_type = await images.fetch_image(client, _SIX["png"])

        assert body == b"\x89PNG-body"
        assert content_type == "image/png"

    async def test_the_request_identifies_this_application(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

        async with _client(handler) as client:
            await images.fetch_image(client, _SIX["normal"])

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
            await images.fetch_image(client, url)

        # Stripping the query would 404 upstream; rebuilding the path would be a construction.
        assert seen == [url]

    @pytest.mark.parametrize("status", [404, 403, 429, 500, 503])
    async def test_a_non_200_upstream_status_is_a_fetch_failure(self, status: int) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, content=b"nope", headers={"content-type": "image/jpeg"})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"])

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_non_image_content_type_is_a_fetch_failure(self) -> None:
        # A captive portal, an error page, or an HTML "soon" placeholder. Serving it through
        # would put attacker-influenced HTML on the companion's own origin.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"])

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_missing_content_type_is_a_fetch_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x", headers={})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"])

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_transport_failure_is_a_fetch_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host", request=request)

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"])

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_timeout_is_a_fetch_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, _SIX["normal"])

        assert raised.value.reason == "image_fetch_failed"

    async def test_a_disallowed_url_is_refused_without_any_request_being_made(self) -> None:
        attempted: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempted.append(str(request.url))
            return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

        async with _client(handler) as client:
            with pytest.raises(CompanionError) as raised:
                await images.fetch_image(client, "https://evil.example/x.jpg")

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
            await images.fetch_image(client, _SIX["normal"])

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
                await images.fetch_image(client, "https://[half-an-ipv6/x.jpg")

        assert raised.value.reason == "image_fetch_failed"
        assert attempted == []

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
                await images.fetch_image(client, _SIX["normal"])

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
                await images.fetch_image(client, _SIX["normal"])

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
                await images.fetch_image(client, _SIX["png"])

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
                await images.fetch_image(client, _SIX["normal"])

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
                await images.fetch_image(client, _SIX["normal"])

        assert raised.value.reason == "image_fetch_failed"

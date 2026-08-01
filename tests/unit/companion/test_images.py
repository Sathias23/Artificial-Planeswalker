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

        The ~12 MB half of the epic's observation is ARITHMETIC on the measured 124 KB average
        (12 MB / 99 tiles), not a byte measurement — the real-bytes profiling is c10-3's
        (epic :3588-3590). It is asserted here as arithmetic and nothing more.

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

_BLOCKING_CALLS = frozenset({"run_in_executor"})
"""Reaching a thread pool by hand. Banned by name, wherever reached.

**c3-7 removed** ``to_thread`` **from this set, and the removal is the point of Q2 rather than a
concession to it** (Brad, 2026-08-01). Both names were banned here by c3-6 under one rule — *an*
``async def`` *must not reach a thread pool* — which was the right rule while the only thing on
this path was a rate. c3-7 put **file I/O** on it, and a synchronous 124 KB read measured at
**4.97 ms** on this machine: 99 warm tiles inline is ~0.49 s of blocked event loop, twice NFR-05's
whole 250 ms push budget, from the path the cache exists to make fast. So ``asyncio.to_thread`` is
no longer the evasion — it is the **sanctioned** way to keep AD-11's *"async throughout"*
literally true, and it is what Starlette's own ``FileResponse`` does.

``run_in_executor`` stays banned, and the difference is not cosmetic: it takes a caller-supplied
loop and executor, so it can silently reintroduce an unbounded pool or a loop this app does not
own, where ``to_thread`` uses the running loop's default bounded executor and nothing else.

**The ban is replaced by something stronger, not merely dropped** — the same procedure c3-6 used
on ``_BANNED_IDENTIFIERS``. ``TestFileIoNeverRunsOnTheLoop`` gates that every file-I/O call site in
``images.py`` is *lexically inside a non-``async`` helper*, which is a property this ban could not
express at all: it could say "no thread", never "the thread is where the blocking call is".
"""


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


def _module_level_calls(source: str, name: str) -> list[int]:
    """Return the lines where *name* is called OUTSIDE any function body.

    Args:
        source: Python source text.
        name: The callee to look for, bare or as an attribute.

    Returns:
        The line numbers of module-level (or default-argument) call sites.
    """
    tree = ast.parse(source)
    inside: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for statement in node.body:
                for child in ast.walk(statement):
                    inside.add(id(child))
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = (
            node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        )
        if called == name and id(node) not in inside:
            lines.append(node.lineno)
    return sorted(lines)


class TestNoDataPathIsResolvedAtImportTime:
    """AD-10's easiest mistake in this story, and the one landmine 4 calls the easiest available.

    ``paths.data_dir()`` ends in ``mkdir(parents=True, exist_ok=True)``, so a module-level
    ``_CACHE_ROOT = paths.data_dir() / "image_cache"`` — or a ``def f(root=cache_root())``
    default argument — would create the user's data directory merely by IMPORTING this module,
    and ``build_app()`` imports it. ``discovery.discovery_path()``'s docstring is the precedent.

    Asserted over the AST rather than by watching for a directory: by the time any test runs the
    import has already happened, so an observational check here is unfalsifiable.
    """

    def test_images_resolves_no_data_path_outside_a_function_body(self) -> None:
        source = _IMAGES_SOURCE.read_text(encoding="utf-8")

        offences = _module_level_calls(source, "data_dir") + _module_level_calls(
            source, "cache_root"
        )

        assert offences == [], (
            f"images.py resolves a data path at line(s) {offences} outside any function body — "
            "data_dir() mkdirs, so this creates the user's data directory at IMPORT time and "
            "breaks AD-10's inertness guarantee"
        )

    def test_the_scan_sees_both_a_module_constant_and_a_default_argument(self) -> None:
        """NON-VACUITY PAIRING, and the second plant is the spelling a reader would not think of:
        a default argument is evaluated at import too, and it does not look like a constant."""
        constant = "from src import paths\n\nROOT = paths.data_dir() / 'image_cache'\n"
        default = "from src import paths\n\n\ndef go(root=paths.data_dir()):\n    return root\n"

        assert _module_level_calls(constant, "data_dir") == [3]
        assert _module_level_calls(default, "data_dir") == [4], (
            "a default argument is evaluated at import; a scan that only walks module-level "
            "assignments walks straight past it"
        )

    def test_the_scan_stays_silent_on_a_call_inside_a_function_body(self) -> None:
        """…and the other direction: resolving at CALL time is the right answer and must not
        fire, or the guard could be satisfied by deleting the resolution entirely."""
        correct = "from src import paths\n\n\ndef go():\n    return paths.data_dir() / 'x'\n"

        assert _module_level_calls(correct, "data_dir") == []


# =============================================================================================
# Story c3-7: the two positive gates that replace the eight names removed from
# `_BANNED_IDENTIFIERS` and the one removed from `_BLOCKING_CALLS`.
#
# c3-6 wrote the procedure down by doing it: remove your family, leave the rest, restate the
# comment, and replace the ban with a positive gate that is STRONGER than the ban was. A ban can
# only ever say "not here". These say "here, and nowhere else" and "on a thread, never on the
# loop" — neither of which the ban could express.
# =============================================================================================


_COMPANION_ROOT = Path(__file__).resolve().parents[3] / "src" / "companion"

_RENAME_INTO_PLACE = frozenset({"replace", "rename", "move"})
"""Every way a file is moved into its final name — the FAMILY, never a member list.

``os.replace`` is what this project uses; ``os.rename`` is the spelling that looks equivalent and
raises ``FileExistsError`` over an existing file on Windows; ``shutil.move`` is the one a reader
reaches for when neither seems to work. All three are rename-into-place, so all three are what the
scan counts — banning only the one the code happens to use is c3-3's finding pre-committed.
"""


def _write_sites_in(source: str) -> list[tuple[str, int]]:
    """Return every rename-into-place call in *source*, resolved through import aliases.

    The four evasions this must survive, each spelled the way a real second write site would
    arrive rather than the way this scan's own firing test spells them:

    * ``from os import replace as move`` — the member aliased at the import, so the local name
      matches nothing;
    * ``import os as operating_system`` — the module aliased, so the attribute access matches
      nothing either;
    * ``handler = os.replace; handler(temp, target)`` — the member rebound to a local, AC 5's own
      named plant, which this scan's first shipped version treated as *sanctioned* (review
      2026-08-01: the quiet-direction test planted exactly this and asserted silence);
    * ``temp_path.replace(target)`` — **pathlib's** rename-into-place, genuine, atomic and
      stdlib, and the one spelling the retired identifier ban DID catch (review 2026-08-01).
      The discriminator that keeps ``str.replace`` and ``datetime.replace`` quiet is the
      signature: rename-into-place takes exactly **one positional argument** (the destination),
      where ``str.replace`` takes two and ``datetime.replace`` takes keywords.

    Args:
        source: Python source text.

    Returns:
        ``(callee, line)`` pairs, with the callee resolved to its real spelling; pathlib-shaped
        method calls are reported as ``Path.<name>`` since their owner's type is unknowable to a
        static scan.
    """
    tree = ast.parse(source)
    modules: dict[str, str] = {}
    members: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in {"os", "shutil"}:
            for alias in node.names:
                if alias.name in _RENAME_INTO_PLACE:
                    members[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    for node in ast.walk(tree):
        # handler = os.replace — the member rebound to a local name. Tracked exactly like a
        # from-import alias: the binding alone is not a write site, but a call through it is.
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Attribute):
            value = node.value
            if (
                value.attr in _RENAME_INTO_PLACE
                and isinstance(value.value, ast.Name)
                and modules.get(value.value.id, value.value.id) in {"os", "shutil"}
            ):
                real = f"{modules.get(value.value.id, value.value.id)}.{value.attr}"
                for bound in node.targets:
                    if isinstance(bound, ast.Name):
                        members[bound.id] = real
    sites: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr in _RENAME_INTO_PLACE:
            owner = function.value
            if isinstance(owner, ast.Name) and modules.get(owner.id, owner.id) in {"os", "shutil"}:
                sites.append((f"{modules.get(owner.id, owner.id)}.{function.attr}", node.lineno))
            elif len(node.args) == 1 and not node.keywords:
                # Path.replace(target) / Path.rename(target): one positional argument is the
                # rename-into-place signature. str.replace takes two, datetime.replace keywords.
                sites.append((f"Path.{function.attr}", node.lineno))
        elif isinstance(function, ast.Name) and function.id in members:
            sites.append((members[function.id], node.lineno))
    return sorted(sites, key=lambda site: site[1])


def _write_sites_in_companion() -> dict[str, list[tuple[str, int]]]:
    """Scan every module under ``src/companion`` for rename-into-place sites, by module name."""
    found: dict[str, list[tuple[str, int]]] = {}
    for path in sorted(_COMPANION_ROOT.rglob("*.py")):
        sites = _write_sites_in(path.read_text(encoding="utf-8"))
        if sites:
            found[path.name] = sites
    return found


class TestExactlyOneImageWriteSite:
    """AC 5, the positive gate replacing eight of the ten removed bans.

    **The acceptance criterion asks for "a single ``os.replace``/rename-into-place site" and that
    is not achievable, because one already existed before this story.**
    ``discovery.write_discovery`` has published the rendezvous atomically since c1-7. So the
    honest gate is the one asserted here: rename-into-place happens in exactly **two** modules,
    each **once**, and both are named. That is strictly stronger than a bare count — a third site
    fires it, and so does a second site inside either of the two named modules — and it is the
    shape ``TestExactlyOnePacer`` already uses, which asserts the count *and* the module.
    """

    def test_the_whole_backend_renames_into_place_in_exactly_two_named_places(self) -> None:
        sites = _write_sites_in_companion()

        assert {module: len(found) for module, found in sites.items()} == {
            "discovery.py": 1,
            "images.py": 1,
        }, (
            f"src/companion renames files into place at {sites}. Exactly two are sanctioned: "
            "discovery.py publishes the rendezvous (c1-7) and images.py stores a cached image "
            "(c3-7). A third is a write path nobody decided on."
        )

    def test_the_image_write_site_is_the_cache_and_uses_replace_not_rename(self) -> None:
        [(callee, _line)] = _write_sites_in_companion()["images.py"]

        assert callee == "os.replace", (
            "os.rename raises FileExistsError over an existing file on Windows, so a cache entry "
            "would be written exactly once and never refreshed — silently, and only on Brad's "
            "platform"
        )

    def test_the_scan_catches_a_second_site_spelled_to_evade(self) -> None:
        """NON-VACUITY, and both plants are spelled the way c3-3's lesson demands: not the way
        this scan's own firing tests spell it.

        A guard written by someone who knows exactly how it will be spelled proves only that it
        catches its own examples — which is precisely what c3-6's review found for the third story
        running.
        """
        planted = (
            "from os import replace as move\n"
            "import os as operating_system\n"
            "import shutil\n"
            "\n"
            "\n"
            "def store(temp, target):\n"
            "    move(temp, target)\n"
            "    operating_system.replace(temp, target)\n"
            "    shutil.move(temp, target)\n"
            "    temp.replace(target)\n"
            "    handler = operating_system.replace\n"
            "    handler(temp, target)\n"
        )

        assert _write_sites_in(planted) == [
            ("os.replace", 7),
            ("os.replace", 8),
            ("shutil.move", 9),
            ("Path.replace", 10),
            ("os.replace", 12),
        ], (
            "an aliased member import, an aliased module import, shutil.move, pathlib's "
            "Path.replace, or a call through a rebound local walked through — the last two are "
            "the review-found holes (2026-08-01): Path.replace is the spelling the retired "
            "identifier ban DID catch, and the rebound local is the evasion AC 5 names"
        )

    def test_the_scan_does_not_fire_on_prose_or_on_an_unrelated_replace(self) -> None:
        """…and the other direction, from the same function (standing agreement).

        ``str.replace`` is everywhere in ordinary code and is not a write of any kind. A scan
        that fired on it would be satisfied only by code that never manipulates a string, which
        is not a property anybody wants — and the temptation would be to delete the guard.

        The discriminators, each planted: ``str.replace`` takes **two** positional arguments and
        ``datetime.replace`` takes **keywords**, where rename-into-place takes exactly one bare
        positional (the destination). A rebound ``os.replace`` that is referenced but never
        **called** is also quiet — the binding is tracked, and the call through it fires (proved
        in the firing test above); the reference alone writes nothing.
        """
        quiet = (
            '"""The cache calls os.replace to move the temp file into place."""\n'
            "import os\n"
            "\n"
            "\n"
            "def normalise(text, path, stamp):\n"
            "    cleaned = text.replace('-', '_')\n"
            "    naive = stamp.replace(tzinfo=None)\n"
            "    handler = os.replace\n"
            "    return cleaned, naive, handler, os.path.join(path, cleaned)\n"
        )

        assert _write_sites_in(quiet) == [], (
            "a str.replace, a keyword-only datetime.replace, an uncalled rebound reference or a "
            "docstring fired the write-site scan"
        )


def _to_thread_callables(source: str) -> set[str]:
    """Every name passed to ``asyncio.to_thread`` as its callable, anywhere in *source*.

    Matches both spellings (``asyncio.to_thread(f, ...)`` and a from-imported ``to_thread(f,
    ...)``) so the gate cannot be evaded by changing the import form (review 2026-08-01).
    """
    tree = ast.parse(source)
    callables: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.args):
            continue
        function = node.func
        named = (isinstance(function, ast.Attribute) and function.attr == "to_thread") or (
            isinstance(function, ast.Name) and function.id == "to_thread"
        )
        if named and isinstance(node.args[0], ast.Name):
            callables.add(node.args[0].id)
    return callables


def _direct_calls_to(source: str, names: set[str]) -> list[tuple[str, int]]:
    """Every ordinary call to a member of *names* in *source* — the on-the-loop spelling.

    A name appearing as ``asyncio.to_thread``'s first argument is a *reference*, not a call, and
    does not match here; ``helper(...)`` does. This is what makes Q2's "reached only through
    ``to_thread``" enforceable rather than trusted (review 2026-08-01).
    """
    tree = ast.parse(source)
    return sorted(
        (node.func.id, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names
    )


_FILE_IO_CALLS = frozenset(
    {
        "open",
        "read_bytes",
        "read_text",
        "write_bytes",
        "write_text",
        "mkstemp",
        "mkdtemp",
        "mkdir",
        "makedirs",
        "replace",
        "rename",
        "unlink",
        "remove",
        "fsync",
        "fdopen",
        # The probe-shaped members (review 2026-08-01): a "check before read" optimisation is the
        # single most likely next edit to the async route, and stat/exists are how it would be
        # spelled. They touch the disk exactly like a read does.
        "stat",
        "exists",
        "is_file",
        "is_dir",
        "touch",
    }
)
"""Synchronous filesystem calls — the family c3-6's blocking-wait scan is structurally blind to.

``_BLOCKING_MODULES`` covers ``threading``, ``concurrent.futures``, ``multiprocessing``,
``subprocess`` and ``time.sleep``. A ``Path.read_bytes()`` is **none of those**, which is the
landmine this story was contexted around: AD-11 says the image path is *"async throughout — it
must never block the event loop"*, and a synchronous file read satisfies every test in this
repository while contradicting that sentence outright.

Listed as calls rather than as modules because there is no module to ban: the offenders live in
``os``, ``pathlib``, ``tempfile`` and the builtins at once, and ``os`` and ``pathlib`` are both
needed on the sanctioned path.
"""


def _file_io_on_the_loop(source: str) -> list[tuple[str, int]]:
    """Return every file-I/O call lexically inside an ``async def`` in *source*.

    **The rule this expresses, which the retired ban could not**: the blocking call must live in a
    plain ``def`` helper, and the async path may reach it only through ``asyncio.to_thread``. A
    call sitting directly in an ``async def`` runs on the event loop no matter how the module is
    otherwise arranged.

    Innermost enclosing function wins, so a plain ``def`` nested inside an ``async def`` is
    correctly clean — that is a real spelling (a closure handed to ``to_thread``) and flagging it
    would push the fix toward hiding the call rather than moving it.

    Import aliases are resolved for the ``from``-form (``from os import replace as move``) so a
    renamed member has no spelling that helps.

    Args:
        source: Python source text.

    Returns:
        ``(callee, line)`` pairs for every offending call site.
    """
    tree = ast.parse(source)
    members: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _FILE_IO_CALLS:
                    members[alias.asname or alias.name] = alias.name

    offences: list[tuple[str, int]] = []

    def walk(node: ast.AST, in_async: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.AsyncFunctionDef):
                walk(child, True)
                continue
            if isinstance(child, ast.FunctionDef | ast.Lambda):
                walk(child, False)
                continue
            if in_async and isinstance(child, ast.Call):
                function = child.func
                if isinstance(function, ast.Attribute):
                    called = function.attr
                elif isinstance(function, ast.Name):
                    called = members.get(function.id, function.id)
                else:
                    called = ""
                if called in _FILE_IO_CALLS:
                    offences.append((called, child.lineno))
            walk(child, in_async)

    walk(tree, False)
    return sorted(offences, key=lambda offence: offence[1])


class TestFileIoNeverRunsOnTheLoop:
    """Q2's ruling, as a gate that can SEE the shape it rules on.

    The guard removed from ``_BLOCKING_CALLS`` said *no thread*. This one says *the blocking call
    is on a thread and never on the loop*, which is the property AD-11 actually asks for and the
    one the old ban was structurally unable to express.

    Measured, so the rule is not merely stylistic (Task 0, 200 iterations, 124 KB, this machine):
    a read is **4.97 ms**, an atomic write **0.46 ms**, an ``asyncio.to_thread`` hop **0.13 ms**.
    Inline, a warm 99-tile deck paint blocks the loop for ~0.49 s — twice NFR-05's whole 250 ms
    push budget. The thread hop costs ~38x less than the read it moves.
    """

    def test_the_image_module_does_no_file_io_on_the_event_loop(self) -> None:
        offences = _file_io_on_the_loop(_IMAGES_SOURCE.read_text(encoding="utf-8"))

        assert offences == [], (
            f"images.py performs file I/O directly inside an async def at {offences}. AD-11: the "
            "image path is async throughout and must never block the event loop. Move the call "
            "into a plain `def` helper and reach it with `asyncio.to_thread` — a 124 KB read is "
            "~5 ms on this machine, and 99 of them is twice NFR-05's whole push budget."
        )

    def test_the_module_actually_reaches_a_thread_so_the_gate_is_not_vacuous(self) -> None:
        """The gate above passes trivially against a module that does no file I/O at all — which
        is exactly what ``images.py`` was one commit ago. This is the half that makes it mean
        something: the file I/O exists, and it is reached through ``asyncio.to_thread``.

        Asserted on the AST, not as a substring (review 2026-08-01): the first shipped version
        checked ``"to_thread" in source``, which this module's own comments and docstrings
        satisfy after every real call is deleted — a vacuity check that was itself vacuous. The
        shape now pinned is Q2's ruling verbatim: each sync file-I/O helper appears as
        ``asyncio.to_thread``'s callable, and **nothing in the module calls either helper
        directly** — so inlining ``_read_cached(...)`` into ``DiskCache.read`` (the one-line
        mutation that blocks the loop 4.97 ms per warm tile and passes every functional test)
        goes red here.
        """
        source = _IMAGES_SOURCE.read_text(encoding="utf-8")

        assert _to_thread_callables(source) == {"_read_cached", "_write_atomically"}, (
            "the sync file-I/O helpers are no longer what asyncio.to_thread runs, so either the "
            "module stopped doing file I/O (the gate above proves nothing) or the I/O moved "
            "somewhere the gate cannot see"
        )
        assert _direct_calls_to(source, {"_read_cached", "_write_atomically"}) == [], (
            "a sync file-I/O helper is called directly — on the event loop — instead of through "
            "asyncio.to_thread; Q2's ruling is 'the thread is where the blocking call is'"
        )
        assert _file_io_on_the_loop(source) == []
        assert [call for call, _line in _write_sites_in(source)] == ["os.replace"], (
            "the module stopped writing at all, so the gate above proves nothing"
        )

    def test_the_reachability_scan_catches_an_inlined_helper_call(self) -> None:
        """NON-VACUITY for the reachability half: the exact mutation it exists to catch —
        ``await asyncio.to_thread(_read_cached, ...)`` rewritten as ``_read_cached(...)`` — must
        fire, and the sanctioned spelling from the same source must not."""
        inlined = (
            "import asyncio\n"
            "\n"
            "\n"
            "def _read_cached(root):\n"
            "    return root.read_bytes()\n"
            "\n"
            "\n"
            "async def read(root):\n"
            "    return _read_cached(root)\n"
        )
        sanctioned = (
            "import asyncio\n"
            "\n"
            "\n"
            "def _read_cached(root):\n"
            "    return root.read_bytes()\n"
            "\n"
            "\n"
            "async def read(root):\n"
            "    return await asyncio.to_thread(_read_cached, root)\n"
        )

        assert _direct_calls_to(inlined, {"_read_cached"}) == [("_read_cached", 9)], (
            "the inline mutation — helper called on the loop — walked through"
        )
        assert _direct_calls_to(sanctioned, {"_read_cached"}) == []
        assert _to_thread_callables(sanctioned) == {"_read_cached"}

    def test_the_scan_catches_a_call_moved_directly_into_an_async_def(self) -> None:
        """NON-VACUITY, plant 1: the regression this gate exists to catch. It is a ONE-LINE edit
        from the shipped code — delete the helper, inline the call — and it passes every
        functional test in this repository."""
        planted = "import asyncio\n\n\nasync def read(path):\n    return path.read_bytes()\n"

        assert _file_io_on_the_loop(planted) == [("read_bytes", 5)]

    def test_the_scan_catches_an_aliased_member_import_inside_an_async_def(self) -> None:
        """NON-VACUITY, plant 2, spelled to evade — c3-6's review theme was a guard keyed on the
        syntax its own firing test used, found by all three layers. So this plant arrives under a
        name no member of ``_FILE_IO_CALLS`` spells."""
        planted = (
            "from os import replace as move\n"
            "from tempfile import mkstemp as scratch\n"
            "\n"
            "\n"
            "async def store(temp, target):\n"
            "    handle, name = scratch(dir=target.parent)\n"
            "    move(temp, target)\n"
        )

        assert _file_io_on_the_loop(planted) == [("mkstemp", 6), ("replace", 7)], (
            "an aliased member import walked straight into an async def"
        )

    def test_the_scan_stays_silent_on_the_sanctioned_arrangement(self) -> None:
        """…and the other direction, which is what keeps the gate from being satisfiable by
        deleting the cache. The shipped shape — a plain ``def`` doing the I/O, an ``async def``
        reaching it through ``asyncio.to_thread`` — must not fire, and neither must a plain
        ``def`` nested inside an async one."""
        legitimate = (
            "import asyncio\n"
            "\n"
            "\n"
            "def _read(path):\n"
            "    return path.read_bytes()\n"
            "\n"
            "\n"
            "async def read(path):\n"
            "    def nested():\n"
            "        return path.read_bytes()\n"
            "\n"
            "    first = await asyncio.to_thread(_read, path)\n"
            "    return first, await asyncio.to_thread(nested)\n"
        )

        assert _file_io_on_the_loop(legitimate) == []

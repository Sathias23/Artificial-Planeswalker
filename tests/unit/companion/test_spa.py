"""Story c2-2: the committed SPA bundle is served, and the typed error contract survives it.

The mount at ``/`` is the first thing in the feature that can *shadow* the c1-4 contract, so most
of this module is about what must **not** answer with ``index.html``. The pairing is deliberate
throughout: every "the fallback fires" test has a sibling proving it does not fire where it
must not.

Everything drives the app through the ``lifespan_client`` seam (AD-10) — in-process over
``httpx.ASGITransport``, no socket.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.routing import Mount

from src.companion.app import spa
from src.companion.app.main import build_app
from src.companion.app.routes import cards, decks, health

_TYPED_ERROR_MEDIA_TYPE = "application/json"

_INDEX = "index.html"

_REPO_ROOT = Path(__file__).resolve().parents[3]
"""tests/unit/companion/test_spa.py -> the repository root."""

_MIRRORED_STATIC = _REPO_ROOT / "plugin" / "server" / "src" / "companion" / "app" / "static"


def _asset(suffix: str) -> str:
    """Return the request path of an emitted bundle asset with *suffix*.

    Read from the real committed bundle rather than hard-coded: Vite's filenames carry a content
    hash, so any literal here would rot on the next build and the test would decay into asserting
    a 404.

    Args:
        suffix: The file extension to look for, e.g. ``".js"``.

    Returns:
        The request path, e.g. ``/assets/index-kbn8nqvM.js``.
    """
    matches = sorted((spa.STATIC_DIR / "assets").glob(f"*{suffix}"))
    if not matches:
        pytest.fail(
            f"No {suffix} asset in {spa.STATIC_DIR / 'assets'} — the bundle is missing or stale. "
            f"Rebuild with: cd ui && npm run build"
        )
    # Prefer the entry bundle: once a later story introduces code-split chunks, sorted()[0] is
    # an arbitrary pick (alphabetical by content hash) and these tests would exercise a random
    # chunk instead of the entry point.
    preferred = [match for match in matches if match.name.startswith("index-")]
    return f"/assets/{(preferred or matches)[0].name}"


class TestTheBundleIsPresent:
    """The premise every other test here rests on (AC 1, AC 4)."""

    def test_the_committed_bundle_has_an_index(self):
        assert (spa.STATIC_DIR / _INDEX).is_file(), (
            f"{spa.STATIC_DIR / _INDEX} is missing. It is a committed build artifact — "
            f"rebuild with: cd ui && npm run build"
        )

    def test_the_committed_bundle_has_hashed_assets(self):
        # Non-vacuity for _asset(): if the assets directory were empty, every content-type
        # assertion below would fail confusingly rather than here, with the reason.
        assert list((spa.STATIC_DIR / "assets").glob("*.js"))
        assert list((spa.STATIC_DIR / "assets").glob("*.css"))


class TestServingTheIndex:
    """AC 7: ``GET /`` serves the SPA, and client-side routes fall back to it."""

    async def test_root_serves_the_index_document(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get("/")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert '<div id="root">' in response.text

    async def test_the_served_index_is_the_committed_one(self, lifespan_client):
        expected = (spa.STATIC_DIR / _INDEX).read_bytes()

        async with lifespan_client(build_app()) as client:
            response = await client.get("/")

        assert response.content == expected

    @pytest.mark.parametrize(
        "path",
        [
            "/decks/42",
            "/decks",
            "/settings/appearance/theme",
            "/api-docs",  # near-miss on the reserved `api` prefix — a client route, not the API
            "/healthcheck",  # near-miss on /health, the exact shape c2-1's proxy got wrong
        ],
    )
    async def test_client_routes_fall_back_to_the_index(self, lifespan_client, path):
        async with lifespan_client(build_app()) as client:
            response = await client.get(path)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

    async def test_a_query_string_does_not_change_the_decision(self, lifespan_client):
        # An ASGI scope["path"] never carries the query string, unlike Vite's dev proxy, which
        # regex-matches the full URL — the bug c2-1's round-2 review found. Pinned, not assumed.
        async with lifespan_client(build_app()) as client:
            fallback = await client.get("/decks/42?tab=curve")
            reserved = await client.get("/api/unknown?tab=curve")

        assert fallback.status_code == 200
        assert fallback.headers["content-type"].startswith("text/html")
        assert reserved.status_code == 404
        assert reserved.json() == {"reason": "invalid_request"}

    async def test_head_of_a_client_route_also_falls_back(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.head("/decks/42")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")


class TestContentTypes:
    """AC 8: content types are asserted, not assumed (landmine #4)."""

    async def test_javascript_is_served_as_a_module_script_type(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_asset(".js"))

        assert response.status_code == 200
        # text/plain here means the browser refuses to execute the module and the page renders
        # blank behind a 200 — the whole reason spa.py registers its own mimetypes.
        assert response.headers["content-type"].startswith("text/javascript")

    async def test_stylesheets_are_served_as_css(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_asset(".css"))

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/css")

    async def test_the_index_is_served_as_html(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get("/")

        assert response.headers["content-type"].startswith("text/html")

    @pytest.mark.parametrize(
        ("suffix", "expected"),
        [
            (".js", "text/javascript"),
            (".mjs", "text/javascript"),
            (".css", "text/css"),
            (".svg", "image/svg+xml"),
            (".json", "application/json"),
            (".woff2", "font/woff2"),  # the self-hosted Space Grotesk subset in the bundle
        ],
    )
    def test_the_registration_survives_a_hostile_mimetypes_database(self, suffix, expected):
        # The hostility is real, not assumed: mimetypes.init() rebuilds the maps from scratch
        # (on Windows, re-reading the very registry spa.py defends against) and DISCARDS every
        # prior add_type — and any third-party import is free to call it. install_spa
        # re-registers, so building an app repairs the damage; .woff2 is the suffix that proves
        # it (no stock database resolves it, so only the re-registration can make this pass).
        import mimetypes

        mimetypes.init()
        build_app()

        assert mimetypes.guess_type(f"file{suffix}")[0] == expected


class TestTheTypedErrorContractSurvivesTheFallback:
    """AC 9: the mount must not shadow the c1-4 contract (AD-16). The heart of this story."""

    async def test_an_unknown_api_path_is_a_typed_404_not_the_index(self, lifespan_client):
        # /api has no routes until c3-1; the reservation must hold anyway, or the UI would be
        # written against a 200-with-HTML today and a 404 after c3-1 lands.
        async with lifespan_client(build_app()) as client:
            response = await client.get("/api/anything-unknown")

        assert response.status_code == 404
        assert response.headers["content-type"].startswith(_TYPED_ERROR_MEDIA_TYPE)
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_missing_asset_is_a_typed_404_not_the_index(self, lifespan_client):
        # An asset miss answering with HTML and a 200 is the "health probe gets HTML that claims
        # success" failure class. A broken deployment must say so.
        async with lifespan_client(build_app()) as client:
            response = await client.get("/assets/does-not-exist.js")

        assert response.status_code == 404
        assert response.headers["content-type"].startswith(_TYPED_ERROR_MEDIA_TYPE)
        assert response.json() == {"reason": "invalid_request"}

    async def test_an_extensionless_asset_miss_is_also_a_typed_404(self, lifespan_client):
        # assets/ is guaranteed asset territory. Without an explicit rule the extension test
        # alone would classify /assets/does-not-exist as a client route and answer 200 + HTML —
        # the same broken deployment as above, hidden behind a success.
        async with lifespan_client(build_app()) as client:
            response = await client.get("/assets/does-not-exist")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_post_to_a_client_route_is_never_the_index(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.post("/decks/42")

        assert response.status_code >= 400
        assert response.headers["content-type"].startswith(_TYPED_ERROR_MEDIA_TYPE)
        assert response.json() == {"reason": "invalid_request"}
        assert "<div id=" not in response.text

    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    async def test_no_mutating_method_reaches_the_index(self, lifespan_client, method):
        async with lifespan_client(build_app()) as client:
            response = await getattr(client, method)("/decks/42")

        # The status matters too: a 200 carrying a typed-error body would be a differently
        # broken contract, and content-type + body alone cannot see it.
        assert response.status_code >= 400
        assert response.headers["content-type"].startswith(_TYPED_ERROR_MEDIA_TYPE)
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_wrong_method_on_a_real_route_keeps_its_allow_header(self, lifespan_client):
        # The regression this story nearly shipped. Starlette's router takes the first Match.FULL
        # and returns, and a Mount at "/" matches everything — so it beat the Match.PARTIAL that
        # /health reports for a wrong method, which is precisely how Starlette produces a 405 with
        # the RFC-mandated Allow header. _SpaMount declines reserved prefixes so the router gets
        # the request back and answers correctly.
        async with lifespan_client(build_app()) as client:
            response = await client.post("/health")

        assert response.status_code == 405
        assert "GET" in response.headers["allow"]
        assert response.json() == {"reason": "invalid_request"}

    async def test_the_mounts_own_405_also_names_its_methods(self, lifespan_client):
        # The other half: for a path the API has not reserved, the mount answers the 405 itself
        # and must still say what it allows. StaticFiles raises a bare one.
        async with lifespan_client(build_app()) as client:
            response = await client.post("/decks/42")

        assert response.status_code == 405
        assert response.headers["allow"] == "GET, HEAD"

    async def test_health_still_answers_json(self, lifespan_client):
        app = build_app()
        async with lifespan_client(app) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["instance_id"] == app.state.instance_id

    @pytest.mark.parametrize(
        ("path", "marker"),
        [("/docs", "swagger"), ("/openapi.json", '"paths"')],
    )
    async def test_the_documentation_surfaces_still_answer(self, lifespan_client, path, marker):
        # Retro ruling R2 keeps them enabled. They are registered by FastAPI.__init__, i.e. before
        # any mount, so they precede the catch-all — this is the regression pair for that.
        # The marker is what makes this non-vacuous: if the route were shadowed or removed, the
        # SPA fallback would ALSO answer 200 for these extension-less paths — with the index,
        # which contains neither Swagger's bootstrap nor an OpenAPI document.
        async with lifespan_client(build_app()) as client:
            response = await client.get(path)

        assert response.status_code == 200
        assert marker in response.text.lower()

    def test_the_mount_leaks_no_path_into_the_openapi_schema(self):
        # c2-3 generates the UI's types from this schema and drift-checks them in CI. A mount that
        # leaked a path into `paths` would surface two stories later as unexplained generated-file
        # churn.
        #
        # Asserts the mount's own path shape is absent rather than pinning the full path set: this
        # test is about the *mount*, and a hardcoded set makes every story that adds a route edit a
        # SPA test for no reason. The completeness half is the differential below, which is the
        # test that genuinely knows what the schema should contain.
        paths = build_app().openapi()["paths"]

        assert "/" not in paths
        # Non-vacuity: there are paths for the mount to have leaked into, so an empty or failed
        # schema walk cannot satisfy the assertion above by finding nothing.
        assert paths

    def test_the_schema_is_unchanged_by_installing_the_mount(self):
        # The non-vacuity pair: prove the assertion above is comparing against a schema that the
        # mount genuinely could have changed, by building one without it.
        #
        # The routers here must mirror build_app()'s. That coupling is deliberate and self-
        # announcing: a story that adds a router and forgets this line gets a red test naming the
        # missing path, which is a cheaper failure than a mount silently swallowing a route.
        #
        # The tax is on adding a ROUTER, not on adding a route. Measured at c3-3, which added
        # /api/deck/{deck_id}/format-check to the existing decks router and needed no line here:
        # both sides of the comparison build their path sets from these same router objects, so a
        # new path on an already-listed router appears on both. deferred-work.md lists c3-3 among
        # the stories owing this line; it did not. Check which kind of story you are before
        # assuming you owe an edit.
        without_spa = FastAPI()
        without_spa.include_router(health.router)
        without_spa.include_router(decks.router)
        without_spa.include_router(cards.router)

        assert set(build_app().openapi()["paths"]) == set(without_spa.openapi()["paths"])


class TestCacheHeaders:
    """Decide-once #4 (ruled 'do it here'): a stale index after a ``git pull`` is a blank page."""

    async def test_the_index_must_revalidate(self, lifespan_client):
        # Vite's emptyOutDir DELETES the previous hashed assets, so a heuristically-cached index
        # references files that no longer exist — and a reload does not fix it. no-cache means
        # revalidate, not do-not-store, so the common case is still a cheap 304.
        async with lifespan_client(build_app()) as client:
            response = await client.get("/")

        assert response.headers["cache-control"] == "no-cache"

    async def test_a_client_route_fallback_also_revalidates(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get("/decks/42")

        assert response.headers["cache-control"] == "no-cache"

    @pytest.mark.parametrize("suffix", [".js", ".css"])
    async def test_hashed_assets_are_immutable(self, lifespan_client, suffix):
        # Safe precisely because the filename is a content hash: changed bytes, changed name.
        async with lifespan_client(build_app()) as client:
            response = await client.get(_asset(suffix))

        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"

    async def test_an_unhashed_root_file_is_not_immutable(self, lifespan_client):
        # favicon.svg sits outside assets/ and carries no hash, so it must revalidate.
        async with lifespan_client(build_app()) as client:
            response = await client.get("/favicon.svg")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"


class TestConditionalRequestsStillWork:
    """AC 7: subclassing StaticFiles rather than hand-rolling means ETag/304 come free."""

    async def test_a_matching_etag_gets_a_304(self, lifespan_client):
        async with lifespan_client(build_app()) as client:
            first = await client.get(_asset(".js"))
            second = await client.get(
                _asset(".js"), headers={"if-none-match": first.headers["etag"]}
            )

        assert first.status_code == 200
        assert second.status_code == 304


class TestMountOrdering:
    """AC 10: the mount is last, and a registered route still wins."""

    def test_the_spa_mount_is_the_final_route(self):
        app = build_app()

        assert isinstance(app.routes[-1], Mount), (
            "The SPA mount is no longer the last entry in app.routes.\n\n"
            "A Mount at '/' matches EVERY path and Starlette matches routes in list order, so "
            "anything registered after it is silently shadowed — GET /api/decks would answer 200 "
            "with index.html instead of running the endpoint.\n\n"
            "FIX: in src/companion/app/main.py's build_app(), register your router ABOVE the "
            "install_spa(app) line. install_spa(app) must stay the last call."
        )
        assert app.routes[-1].name == "spa"

    def test_only_one_mount_exists(self):
        mounts = [route for route in build_app().routes if isinstance(route, Mount)]

        assert len(mounts) == 1

    async def test_a_registered_route_still_wins_over_the_mount(self, lifespan_client):
        # The non-vacuity pair for the ordering assertion: proving the mount is last is worthless
        # unless a real route in front of it is still reachable.
        async with lifespan_client(build_app()) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        # Plain "application/json" here, not the typed-error constant: this is the one response
        # in the module that is a success, and JSON-ness is all it shares with the contract.
        assert response.headers["content-type"].startswith("application/json")
        assert "status" in response.json()

    def test_the_reserved_prefixes_are_derived_from_the_route_table(self):
        app = build_app()
        reserved = spa._reserved_prefixes(app)

        # Exact equality, deliberately — it guards BOTH failure directions:
        #
        # * Under-reservation. `health` arrives via include_router, which FastAPI wraps in an
        #   _IncludedRouter carrying neither .path nor .routes. A naive `getattr(route, "path")`
        #   walk misses it — and misses every prefix c3-1 (/api) and c5-5 (/agent) will register
        #   the same way, so their typo paths would answer 200 with index.html instead of a
        #   typed 404. (`api` is seeded; `docs`/`redoc`/`openapi.json` are plain Routes from
        #   FastAPI.__init__.)
        #
        # * Over-reservation. If a future FastAPI gave _IncludedRouter a delegating .routes,
        #   _route_paths would yield each child twice — once WITHOUT the include prefix — and a
        #   bare child segment (e.g. `decks` from prefix="/api") would be silently stolen from
        #   the SPA's client-route namespace. `in`-assertions stay green on that; equality does
        #   not.
        assert reserved == {"api", "health", "docs", "redoc", "openapi.json"}, (
            f"Reserved prefixes changed: {sorted(reserved)}.\n\n"
            "If a prefix is MISSING: spa._route_paths reads FastAPI internals "
            "(_IncludedRouter.original_router and .include_context.prefix) to descend into "
            "included routers, and a FastAPI upgrade has most likely moved them — update the "
            "walk, or every router-registered prefix falls through to the SPA index instead of "
            "the typed error contract.\n\n"
            "If there is an EXTRA prefix: either a new router was added (fine — add it here), "
            "or the walk is double-yielding paths without their include prefix and stealing "
            "client-route names from the SPA."
        )

    async def test_an_unknown_path_under_a_router_prefix_is_a_typed_404(self, lifespan_client):
        # The behavioural half of the assertion above: /health is reserved, so a typo beneath it
        # keeps the contract instead of rendering the app.
        async with lifespan_client(build_app()) as client:
            response = await client.get("/health/unknown-subpath")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    def test_the_mount_declines_non_http_scopes(self):
        # Starlette's Mount matches websocket scopes too, but StaticFiles serves only HTTP — its
        # first line is `assert scope["type"] == "http"`. A WebSocket handshake to an unreserved
        # path (c5-6's /ws, or any client route) must get the router's clean no-such-route
        # rejection, not an AssertionError dressed as a server error.
        mount = build_app().routes[-1]

        match, _ = mount.matches({"type": "websocket", "path": "/decks/42", "root_path": ""})

        assert match is spa.Match.NONE

    def test_the_mount_still_claims_http_scopes(self):
        # The non-vacuity pair: declining everything would also "pass" the test above.
        mount = build_app().routes[-1]

        match, _ = mount.matches(
            {"type": "http", "method": "GET", "path": "/decks/42", "root_path": ""}
        )

        assert match is spa.Match.FULL


class TestAMissingBundleFailsLegibly:
    """AC 11: construction stays inert, and an absent bundle says how to fix itself."""

    def test_a_missing_directory_names_the_rebuild_command(self, tmp_path):
        with pytest.raises(RuntimeError) as excinfo:
            spa.install_spa(FastAPI(), static_dir=tmp_path / "nope")

        message = str(excinfo.value)
        assert "npm run build" in message
        assert str(tmp_path / "nope") in message

    def test_a_directory_without_an_index_also_fails(self, tmp_path):
        empty = tmp_path / "static"
        empty.mkdir()
        (empty / "assets").mkdir()

        with pytest.raises(RuntimeError) as excinfo:
            spa.install_spa(FastAPI(), static_dir=empty)

        assert "npm run build" in str(excinfo.value)

    def test_the_happy_path_installs_without_raising(self, tmp_path):
        directory = tmp_path / "static"
        directory.mkdir()
        (directory / "index.html").write_text("<html></html>", encoding="utf-8")
        app = FastAPI()

        spa.install_spa(app, static_dir=directory)

        assert isinstance(app.routes[-1], Mount)

    def test_installing_creates_no_directory(self, tmp_path):
        # AD-10 in the narrow place this story could have broken it: a stat is not a side effect,
        # a mkdir is. (test_app.py::TestConstructionIsInert covers build_app() as a whole.)
        absent = tmp_path / "never-created"

        with pytest.raises(RuntimeError):
            spa.install_spa(FastAPI(), static_dir=absent)

        assert not absent.exists()


class TestThePluginMirror:
    """AC 15: both copies are generated artifacts, and the mirror is really a copy."""

    def test_the_mirrored_index_is_byte_identical(self):
        # Caught locally rather than only on CI: the plugin/ drift check covers this, but a
        # plugin/ committed without a rebuild should not need a CI round-trip to notice.
        assert _MIRRORED_STATIC.is_dir(), (
            f"{_MIRRORED_STATIC} is missing — the plugin mirror was committed without the SPA "
            f"bundle. Rebuild with: uv run python -m scripts.build_plugin"
        )
        assert (_MIRRORED_STATIC / _INDEX).read_bytes() == (spa.STATIC_DIR / _INDEX).read_bytes(), (
            "plugin/ holds a different index.html than src/. Both are generated artifacts — "
            "rebuild with: uv run python -m scripts.build_plugin, and commit plugin/."
        )

    def test_the_mirrored_assets_are_byte_identical(self):
        # Names AND bytes: CRLF mangling (the fresh-Windows-clone failure the second
        # .gitattributes line exists for) does not change a filename, so a name-only comparison
        # would pass with byte-divergent assets.
        source = sorted((spa.STATIC_DIR / "assets").iterdir())
        mirrored = sorted((_MIRRORED_STATIC / "assets").iterdir())

        assert [p.name for p in mirrored] == [p.name for p in source]
        for source_file, mirrored_file in zip(source, mirrored, strict=True):
            assert mirrored_file.read_bytes() == source_file.read_bytes(), (
                f"plugin/ holds a byte-divergent copy of assets/{source_file.name}. Both are "
                f"generated artifacts — rebuild with: uv run python -m scripts.build_plugin, "
                f"and commit plugin/."
            )


class TestTheBundleIsInternallyConsistent:
    """Guards the one thing a byte-comparison cannot: that index.html references real assets."""

    def test_every_asset_the_index_references_exists(self):
        index = (spa.STATIC_DIR / _INDEX).read_text(encoding="utf-8")

        referenced = [token.split('"')[0] for token in index.split('="/assets/')[1:]]

        assert referenced, "index.html references no /assets/ file — the build output is wrong"
        for name in referenced:
            assert (spa.STATIC_DIR / "assets" / name).is_file(), (
                f"index.html references /assets/{name}, which is not in the bundle. This is the "
                f"stale-bundle failure emptyOutDir exists to prevent."
            )

    def test_the_index_names_itself_as_generated(self):
        # AC 6: the notice a person who opens the built file to "just fix one string" will read.
        index = (spa.STATIC_DIR / _INDEX).read_text(encoding="utf-8")

        assert "GENERATED OUTPUT" in index
        assert "npm run build" in index

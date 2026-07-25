"""Story c1-2: the companion ASGI app is inert to construct and honest about its identity.

The inertness tests (AC 2) are the ones that must still catch a regression years from now, so they
assert **observable filesystem and socket state**, never that a mock went uncalled.
"""

import importlib
import logging
import socket
import sys
import uuid

import pytest
from pydantic import ValidationError

from src.companion.app.main import build_app
from src.companion.contracts import HealthResponse

_MAIN_MODULE = "src.companion.app.main"


def _fresh_main(monkeypatch):
    """Import ``src.companion.app.main`` from scratch, restoring ``sys.modules`` afterwards.

    ``monkeypatch.delitem`` puts the original module objects back at teardown, so a fresh import
    here cannot leave a second copy of the module behind for later tests to trip over.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        A freshly executed ``src.companion.app.main`` module.
    """
    for name in [name for name in sys.modules if name.startswith("src.companion.app")]:
        monkeypatch.delitem(sys.modules, name)
    return importlib.import_module(_MAIN_MODULE)


class TestHealthResponseContract:
    """AC 5 / AD-12: the wire shape is a pydantic model in the leaf, not an ad-hoc dict."""

    def test_accepts_the_health_shape(self):
        model = HealthResponse(status="ok", instance_id="abc")

        assert model.status == "ok"
        assert model.instance_id == "abc"

    def test_status_is_a_closed_token(self):
        with pytest.raises(ValidationError):
            HealthResponse(status="degraded", instance_id="abc")


class TestConstructionIsInert:
    """AC 1 + AC 2 (AD-10): ``build_app()`` touches nothing outside the process."""

    def test_import_and_construction_create_no_directory(self, tmp_path, monkeypatch):
        # A *non-existent* subdirectory: src.paths.data_dir() ends in mkdir(parents=True), so a
        # single call anywhere on the import or construction path would create this.
        data_dir = tmp_path / "never-created"
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(data_dir))
        before = set(tmp_path.iterdir())

        module = _fresh_main(monkeypatch)
        app = module.build_app()

        assert app is not None
        assert not data_dir.exists(), (
            "build_app() (or importing main) resolved a data path — data_dir() mkdirs, so the "
            "companion would create state on a fresh install before the UI could report it (AD-10)"
        )
        assert set(tmp_path.iterdir()) == before, (
            "construction wrote to the data directory's parent"
        )

    def test_construction_binds_no_socket(self, monkeypatch):
        def explode(*args, **kwargs):
            raise AssertionError("build_app() must not bind a socket — c1-3 owns the port")

        monkeypatch.setattr(socket.socket, "bind", explode)

        assert build_app() is not None

    def test_construction_mints_no_identity(self):
        """AC 3: a constructed-but-never-started app has no identity to leak."""
        app = build_app()

        assert not hasattr(app.state, "instance_id")


class TestInstanceIdentity:
    """AC 3: the lifespan mints ``instance_id`` and holds it for the life of the process."""

    async def test_startup_mints_a_uuid(self, lifespan_client):
        app = build_app()

        async with lifespan_client(app):
            minted = app.state.instance_id

        assert isinstance(minted, str)
        assert uuid.UUID(minted)

    async def test_identity_is_stable_across_requests_in_one_lifespan(self, lifespan_client):
        app = build_app()

        async with lifespan_client(app) as client:
            first = await client.get("/health")
            second = await client.get("/health")

        assert first.json()["instance_id"] == second.json()["instance_id"]
        assert first.json()["instance_id"] == app.state.instance_id

    async def test_each_fresh_app_gets_its_own_identity(self, lifespan_client):
        first_app, second_app = build_app(), build_app()

        async with lifespan_client(first_app):
            first = first_app.state.instance_id
        async with lifespan_client(second_app):
            second = second_app.state.instance_id

        assert first != second


class TestHealthEndpoint:
    """AC 4 / FR-14: the unauthenticated identity probe, driven with no network (AC 7)."""

    async def test_health_returns_the_typed_body(self, lifespan_client):
        app = build_app()

        async with lifespan_client(app) as client:
            # No auth header: /health is what a caller reads *before* deciding to send a token.
            response = await client.get("/health")

        assert response.status_code == 200
        body = HealthResponse.model_validate(response.json())
        assert body.status == "ok"
        assert body.instance_id == app.state.instance_id

    def test_openapi_carries_the_health_contract(self):
        """AD-12: c2-3 generates TypeScript from this schema, so it must exist from day one."""
        schema = build_app().openapi()

        assert "/health" in schema["paths"]
        assert "HealthResponse" in schema["components"]["schemas"]


class TestShutdown:
    """AC 6: teardown always runs, and never lets a failure escape upward."""

    async def test_teardown_runs_on_clean_exit(self, monkeypatch):
        main = importlib.import_module(_MAIN_MODULE)
        calls = []

        async def record(app):
            calls.append(app)

        monkeypatch.setattr(main, "_shutdown", record)
        app = main.build_app()

        async with main.lifespan(app):
            pass

        assert calls == [app]

    async def test_failing_teardown_is_logged_and_swallowed(self, monkeypatch, caplog):
        main = importlib.import_module(_MAIN_MODULE)

        async def boom(app):
            raise RuntimeError("engine dispose failed")

        monkeypatch.setattr(main, "_shutdown", boom)
        app = main.build_app()

        with caplog.at_level(logging.ERROR):
            async with main.lifespan(app):
                pass

        assert "engine dispose failed" in caplog.text

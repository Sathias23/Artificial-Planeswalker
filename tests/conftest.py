"""Shared fixtures for the whole test suite.

The legacy agent/UI fixtures (``mock_session_manager``, ``mock_user_session``,
``mock_action``, ``action_message``) were removed together with the PydanticAI agent +
Chainlit UI (archived in Story 1.1, then deleted for public release). The active suite
(``testpaths = ["tests"]``) no longer depends on them.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from src.companion import client as _companion_client
from tests.fixtures.companion_stubs import Loopback, StubFleet, StubServer
from tests.fixtures.real_data import MODEL_CACHE_DIR

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every test's data directory at its own ``tmp_path``, and return it.

    Without this, anything that resolves ``src.paths`` reaches the developer's real data
    directory: every MCP deck mutation's ``deck_changed`` emit reads the real ``companion.json``
    (a stale one costs a 1 s connect timeout per mutation), the subprocess tests inherit the
    environment, and a lifespan entry writes a discovery file over a companion the developer has
    running. So, for every test:

    * ``PLANESWALKER_DATA_DIR`` is ``tmp_path`` itself, not a subfolder, because the companion
      tests assume ``discovery_path().parent == tmp_path``;
    * ``CARDS_DATABASE_URL`` is removed, since an exported URL outranks the data dir;
    * ``FASTEMBED_CACHE_DIR`` is pinned to the persistent model cache
      (:data:`tests.fixtures.real_data.MODEL_CACHE_DIR`). The model is a download cache, not
      operator data, and isolating it would re-download ~80 MB per test.

    A test (or a fixture it requests) that sets any of these itself still wins: autouse fixtures
    set up first. Module-scoped fixtures set up before this one, so none may resolve a default
    path. ``tests/unit/test_isolation.py`` pins the behaviour.

    Returns:
        This test's data directory (``tmp_path``).
    """
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CARDS_DATABASE_URL", raising=False)
    monkeypatch.setenv("FASTEMBED_CACHE_DIR", str(MODEL_CACHE_DIR))
    return tmp_path


@pytest.fixture(autouse=True)
async def _fresh_shared_companion_client():
    """Each test gets its own pooled companion HTTP client, closed on its own loop at teardown.

    The leaf client caches one ``httpx.AsyncClient`` per running loop; a test that leaves it
    behind would hand the next test (on a new loop) a pool bound to a closed one, and a stub
    listener with a kept-alive socket would block its own teardown. Autouse here so the unit
    client tests, the deck-changed wiring tests and the companion tool tests all get it.
    """
    _companion_client.reset_shared_client()
    yield
    await _companion_client.aclose_shared_client()


@pytest.fixture
def sample_json_file() -> Path:
    """Return the path of the sample Scryfall bulk-data JSON fixture."""
    return _FIXTURES_DIR / "scryfall_sample.json"


@pytest.fixture
def stub_server() -> Iterator[Callable[..., StubServer]]:
    """Yield :meth:`~tests.fixtures.companion_stubs.StubFleet.start`; tear every stub down after.

    Yields:
        ``start(*, status=200, body=b"", content_type="application/json", post_script=None,
        on_post=None, put_script=None, on_put=None)``, returning a running loopback stub.
    """
    fleet = StubFleet()
    yield fleet.start
    fleet.close_all()


@pytest.fixture
def loopback() -> Iterator[Loopback]:
    """Yield a :class:`~tests.fixtures.companion_stubs.Loopback`; close all it opened after.

    Teardown lives here rather than in per-test ``try/finally`` because a leaked listener on
    Windows surfaces as a failure in some *later* test, the worst kind of flake to diagnose.
    """
    helper = Loopback()
    yield helper
    helper.close_all()

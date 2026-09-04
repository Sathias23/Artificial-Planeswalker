"""Shared fixtures for the active (core) test suite.

The legacy agent/UI fixtures (``mock_session_manager``, ``mock_user_session``,
``mock_action``, ``action_message``) were removed together with the PydanticAI agent +
Chainlit UI (archived in Story 1.1, then deleted for public release). The active suite
(``testpaths = ["tests"]``) no longer depends on them.
"""

import pytest

from src.companion import client as _companion_client


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

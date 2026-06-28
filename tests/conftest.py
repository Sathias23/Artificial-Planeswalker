"""Shared fixtures for the active (core) test suite.

The legacy agent/UI fixtures (``mock_session_manager``, ``mock_user_session``,
``mock_action``, ``action_message``) were removed together with the PydanticAI agent +
Chainlit UI (archived in Story 1.1, then deleted for public release). The active suite
(``testpaths = ["tests"]``) no longer depends on them.
"""

"""Shared fixtures for the active (core) test suite.

The legacy agent/UI fixtures (``mock_session_manager``, ``mock_user_session``,
``mock_action``, ``action_message``) were relocated to ``legacy/tests/conftest.py`` when
``src/agent`` and ``src/ui`` were archived to ``legacy/`` (Story 1.1). The active suite
(``testpaths = ["tests"]``) no longer depends on them.
"""

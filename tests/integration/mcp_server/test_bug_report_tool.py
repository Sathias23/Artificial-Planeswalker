"""Integration tests for the file_bug_report helper (Story 1.3, Task 3).

Covers the success path (row persisted + confirmation including the id) and the
graceful-error path (DB failure returns a friendly message, never raises). The
end-to-end MCP-client wiring is covered separately in test_mcp_tools.py.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.bug_report import BugReportModel
from src.mcp_server.tools.bug_report import BugReportResult, file_bug_report


@pytest.fixture
async def in_memory_engine():
    """Create an in-memory SQLite engine with tables created."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(in_memory_engine):
    """Create a test session against the initialized DB."""
    session_factory = create_session_factory(in_memory_engine)
    async with session_factory() as session:
        yield session


async def test_file_bug_report_persists_and_confirms(session: AsyncSession):
    """A successful report returns the id in the confirmation and writes a row."""
    result = await file_bug_report(session, "Lightning Bolt lookup returned wrong card")

    assert isinstance(result, BugReportResult)
    assert result.id
    assert result.id in result.message

    stmt = select(BugReportModel).where(BugReportModel.id == result.id)
    row = (await session.execute(stmt)).scalar_one()
    assert row.description == "Lightning Bolt lookup returned wrong card"
    assert row.status == "open"


async def test_file_bug_report_handles_db_error_gracefully():
    """A DB failure returns a graceful message instead of surfacing an exception."""
    # Engine WITHOUT init_database → the bug_reports table does not exist, so the
    # insert fails. The helper must catch it and return a friendly result.
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            result = await file_bug_report(session, "this will fail to persist")

        assert isinstance(result, BugReportResult)
        assert result.id == ""
        assert result.message  # non-empty, user-friendly
    finally:
        await engine.dispose()

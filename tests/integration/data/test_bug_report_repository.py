"""Integration tests for BugReportRepository (Story 1.3 — additive bug-report slice)."""

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.bug_report import BugReportModel
from src.data.repositories.bug_report import BugReportRepository
from src.data.schemas.bug_report import BugReport, BugReportStatus


@pytest.fixture
async def in_memory_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(in_memory_engine):
    """Create a test session."""
    session_factory = create_session_factory(in_memory_engine)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def bug_repo(session: AsyncSession):
    """Create a BugReportRepository instance."""
    return BugReportRepository(session)


async def test_create_returns_validated_schema(bug_repo: BugReportRepository):
    """create() returns a BugReport schema with generated id, defaults, and timestamps."""
    report = await bug_repo.create(description="Search returned the wrong card for 'bolt'")

    assert isinstance(report, BugReport)
    assert report.id  # non-empty generated UUID
    assert report.description == "Search returned the wrong card for 'bolt'"
    assert report.status == BugReportStatus.OPEN
    assert report.context is None
    # Timestamps are populated (stored via SQLite DateTime, which round-trips tz-naive,
    # matching DeckModel's established behavior).
    assert isinstance(report.created_at, datetime)
    assert isinstance(report.updated_at, datetime)


async def test_create_with_context(bug_repo: BugReportRepository):
    """create() persists optional free-text context when provided."""
    report = await bug_repo.create(description="Crash on lookup", context="format=standard")

    assert report.context == "format=standard"


async def test_create_persists_row(bug_repo: BugReportRepository, session: AsyncSession):
    """The created report is actually written to the bug_reports table."""
    report = await bug_repo.create(description="Persisted bug")

    stmt = select(BugReportModel).where(BugReportModel.id == report.id)
    result = await session.execute(stmt)
    row = result.scalar_one()

    assert row.description == "Persisted bug"
    assert row.status == "open"

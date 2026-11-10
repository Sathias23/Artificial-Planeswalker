"""Shared CardRepository fixtures, built on the production engine and session factory.

Built through ``src.data.database`` (``create_engine`` + ``init_database`` +
``create_session_factory``) rather than a bare ``create_async_engine``, so every session here runs
with the connect hooks production runs with (``PRAGMA foreign_keys = ON``) and the factory's
``autoflush=False``. A test that depends on a pending row being visible to a query flushes or
commits explicitly, as production code must.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.repositories.card import CardRepository
from tests.fixtures.card_data import create_sample_cards, create_standard_legal_cards


@pytest.fixture
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """An in-memory SQLite engine with the full schema, from the production engine factory."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """A session from the production session factory over :func:`async_engine`."""
    async with create_session_factory(async_engine)() as session:
        yield session


@pytest.fixture
async def mixed_format_session(async_session: AsyncSession) -> AsyncSession:
    """A session holding both Standard-legal and non-Standard-legal cards, committed."""
    async_session.add_all(create_sample_cards())
    async_session.add_all(create_standard_legal_cards())
    await async_session.commit()
    return async_session


@pytest.fixture
def mixed_format_repo(mixed_format_session: AsyncSession) -> CardRepository:
    """A CardRepository over :func:`mixed_format_session`."""
    return CardRepository(mixed_format_session)

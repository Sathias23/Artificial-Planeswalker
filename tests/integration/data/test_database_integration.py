"""Integration tests for database operations."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, health_check, init_database
from src.data.models.card import CardModel
from src.data.schemas.card import Card


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


async def test_init_database_creates_tables(in_memory_engine) -> None:
    """Test that init_database creates all tables."""
    # Tables should be created by the fixture
    # Verify by attempting to query the cards table
    session_factory = create_session_factory(in_memory_engine)
    async with session_factory() as session:
        result = await session.execute(select(CardModel))
        cards = result.scalars().all()
        assert cards == []  # Empty table exists


async def test_init_database_idempotent(in_memory_engine) -> None:
    """Test that calling init_database multiple times doesn't fail."""
    # First initialization happened in fixture
    # Second initialization should succeed
    await init_database(in_memory_engine)

    # Verify table still exists
    session_factory = create_session_factory(in_memory_engine)
    async with session_factory() as session:
        result = await session.execute(select(CardModel))
        cards = result.scalars().all()
        assert cards == []


async def test_insert_and_select_card(session: AsyncSession) -> None:
    """Test inserting and retrieving a card."""
    card = CardModel(
        id="test-integration-123",
        name="Lightning Bolt",
        oracle_id="oracle-123",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="161",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "not_legal", "modern": "legal"},
    )

    # Insert
    session.add(card)
    await session.commit()

    # Select
    stmt = select(CardModel).where(CardModel.id == "test-integration-123")
    result = await session.execute(stmt)
    retrieved_card = result.scalar_one()

    assert retrieved_card.id == "test-integration-123"
    assert retrieved_card.name == "Lightning Bolt"
    assert retrieved_card.colors == ["R"]
    assert retrieved_card.legalities == {"standard": "not_legal", "modern": "legal"}


async def test_sqlalchemy_to_pydantic_conversion(session: AsyncSession) -> None:
    """Test converting SQLAlchemy model to Pydantic schema."""
    card_model = CardModel(
        id="test-pydantic-456",
        name="Counterspell",
        oracle_id="oracle-456",
        mana_cost="{U}{U}",
        cmc=2.0,
        type_line="Instant",
        oracle_text="Counter target spell.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="54",
        colors=["U"],
        color_identity=["U"],
        legalities={"standard": "not_legal", "modern": "legal"},
    )

    session.add(card_model)
    await session.commit()

    # Retrieve and convert
    stmt = select(CardModel).where(CardModel.id == "test-pydantic-456")
    result = await session.execute(stmt)
    retrieved_model = result.scalar_one()

    # Convert to Pydantic schema
    card_schema = Card.model_validate(retrieved_model)

    assert card_schema.id == "test-pydantic-456"
    assert card_schema.name == "Counterspell"
    assert card_schema.mana_cost == "{U}{U}"
    assert card_schema.cmc == 2.0
    assert card_schema.colors == ["U"]


async def test_health_check_success(session: AsyncSession) -> None:
    """Test health check successfully inserts and retrieves test card."""
    result = await health_check(session)

    assert result is True

    # Verify test card was cleaned up
    stmt = select(CardModel).where(CardModel.name == "__HEALTH_CHECK__")
    check_result = await session.execute(stmt)
    remaining_cards = check_result.scalars().all()

    assert len(remaining_cards) == 0


async def test_health_check_cleanup(session: AsyncSession) -> None:
    """Test health check leaves database in clean state."""
    # Add a real card
    real_card = CardModel(
        id="real-card-789",
        name="Forest",
        oracle_id="oracle-789",
        mana_cost="",
        cmc=0.0,
        type_line="Basic Land — Forest",
        oracle_text="{T}: Add {G}.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="295",
        colors=[],
        color_identity=["G"],
        legalities={"standard": "legal", "modern": "legal"},
    )

    session.add(real_card)
    await session.commit()

    # Run health check
    await health_check(session)

    # Verify only the real card remains
    stmt = select(CardModel)
    result = await session.execute(stmt)
    all_cards = result.scalars().all()

    assert len(all_cards) == 1
    assert all_cards[0].id == "real-card-789"


async def test_session_context_manager(in_memory_engine) -> None:
    """Test session lifecycle with async context manager."""
    session_factory = create_session_factory(in_memory_engine)

    async with session_factory() as session:
        card = CardModel(
            id="context-test-999",
            name="Test Card",
            oracle_id="oracle-999",
            mana_cost="{1}",
            cmc=1.0,
            type_line="Artifact",
            oracle_text="Test card",
            rarity="common",
            set_code="TST",
            set_name="Test Set",
            collector_number="1",
            colors=[],
            color_identity=[],
            legalities={},
        )

        session.add(card)
        await session.commit()

    # Session should be closed now, create new one to verify data persists
    async with session_factory() as new_session:
        stmt = select(CardModel).where(CardModel.id == "context-test-999")
        result = await new_session.execute(stmt)
        retrieved_card = result.scalar_one()

        assert retrieved_card.name == "Test Card"

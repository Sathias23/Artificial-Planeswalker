#!/usr/bin/env python3
"""Simple script to test database setup and basic operations."""

import asyncio

from src.data import CardModel, create_engine, create_session_factory, health_check, init_database


async def main() -> None:
    """Test database initialization and basic operations."""
    print("Testing database setup...")

    # Create in-memory database for testing
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    print("✓ Engine created")

    # Initialize database schema
    await init_database(engine)
    print("✓ Database schema initialized")

    # Create session factory
    session_factory = create_session_factory(engine)
    print("✓ Session factory created")

    # Test database operations
    async with session_factory() as session:
        # Insert a test card
        test_card = CardModel(
            id="test-123",
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

        session.add(test_card)
        await session.commit()
        print("✓ Test card inserted")

        # Run health check
        health_result = await health_check(session)
        print(f"✓ Health check: {'PASSED' if health_result else 'FAILED'}")

    # Cleanup
    await engine.dispose()
    print("✓ Engine disposed")

    print("\n🎉 All database operations completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())

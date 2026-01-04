#!/usr/bin/env python3
"""CLI script to demonstrate CardRepository query functionality.

This script creates an in-memory test database, populates it with sample cards,
and demonstrates all query methods with visible output.

Usage:
    uv run python scripts/test_queries.py
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path to allow imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.models.base import Base  # noqa: E402
from src.data.repositories.card import CardRepository  # noqa: E402
from tests.fixtures.card_data import (  # noqa: E402
    create_multiface_card,
    create_sample_cards,
)


async def main() -> None:
    """Main demonstration function."""
    print("=" * 80)
    print("CardRepository Query Demonstration")
    print("=" * 80)
    print()

    # Create in-memory database
    print("[1] Creating in-memory test database...")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("    ✓ Database created")
    print()

    # Create session
    async_session_maker = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        # Populate with sample data
        print("[2] Populating database with sample cards...")
        sample_cards = create_sample_cards()
        session.add_all(sample_cards)

        multiface_card = create_multiface_card()
        session.add(multiface_card)

        await session.commit()
        print(f"    ✓ Added {len(sample_cards) + 1} cards to database")
        print()

        # Create repository
        repo = CardRepository(session)

        # Demonstrate exact name search
        print("[3] Demonstrating exact name search: find_by_name_exact()")
        print("-" * 80)
        card = await repo.find_by_name_exact("Lightning Bolt")
        if card:
            print(f"    Found: {card.name}")
            print(f"           Type: {card.type_line}")
            print(f"           Mana Cost: {card.mana_cost}")
            print(f"           Colors: {card.colors}")
            print(f"           Text: {card.oracle_text}")
        else:
            print("    Card not found")
        print()

        # Test case-insensitive
        print("    Testing case-insensitive search ('counterspell')...")
        card = await repo.find_by_name_exact("counterspell")
        if card:
            print(f"    Found: {card.name} (original case preserved)")
        print()

        # Test not found
        print("    Testing card not found ('Nonexistent Card')...")
        card = await repo.find_by_name_exact("Nonexistent Card")
        print(f"    Result: {card}")
        print()

        # Demonstrate partial name search
        print("[4] Demonstrating partial name search: find_by_name_partial()")
        print("-" * 80)
        print("    Searching for 'lightning'...")
        cards = await repo.find_by_name_partial("lightning")
        print(f"    Found {len(cards)} cards:")
        for card in cards:
            print(f"      • {card.name} ({card.type_line})")
        print()

        print("    Searching for 'dragon' (case-insensitive)...")
        cards = await repo.find_by_name_partial("dragon")
        print(f"    Found {len(cards)} cards:")
        for card in cards:
            print(f"      • {card.name} ({card.type_line})")
        print()

        # Demonstrate color filtering
        print("[5] Demonstrating color filtering: find_by_colors()")
        print("-" * 80)
        print("    Searching for red cards (R)...")
        cards = await repo.find_by_colors("R")
        print(f"    Found {len(cards)} red cards:")
        for card in cards:
            print(f"      • {card.name} - Colors: {card.colors}")
        print()

        print("    Searching for blue cards (U)...")
        cards = await repo.find_by_colors("U")
        print(f"    Found {len(cards)} blue cards:")
        for card in cards:
            print(f"      • {card.name} - Colors: {card.colors}")
        print()

        print("    Searching for colorless cards (empty string)...")
        cards = await repo.find_by_colors("")
        print(f"    Found {len(cards)} colorless cards:")
        for card in cards:
            print(f"      • {card.name} - Colors: {card.colors}")
        print()

        print("    Searching for black cards (B) - should be none...")
        cards = await repo.find_by_colors("B")
        print(f"    Found {len(cards)} black cards")
        print()

        # Demonstrate type filtering
        print("[6] Demonstrating type filtering: find_by_type()")
        print("-" * 80)
        print("    Searching for Instant cards...")
        cards = await repo.find_by_type("Instant")
        print(f"    Found {len(cards)} Instant cards:")
        for card in cards:
            print(f"      • {card.name} ({card.type_line})")
        print()

        print("    Searching for Dragon creatures...")
        cards = await repo.find_by_type("Dragon")
        print(f"    Found {len(cards)} Dragon cards:")
        for card in cards:
            print(f"      • {card.name} ({card.type_line})")
        print()

        print("    Searching for Legendary cards...")
        cards = await repo.find_by_type("Legendary")
        print(f"    Found {len(cards)} Legendary cards:")
        for card in cards:
            print(f"      • {card.name} ({card.type_line})")
        print()

        print("    Searching for Planeswalker cards (should be none)...")
        cards = await repo.find_by_type("Planeswalker")
        print(f"    Found {len(cards)} Planeswalker cards")
        print()

        # Demonstrate multi-face card
        print("[7] Demonstrating multi-face card query")
        print("-" * 80)
        card = await repo.find_by_name_exact("Delver of Secrets")
        if card and card.card_faces:
            print(f"    Found multi-face card: {card.name}")
            print("    Faces:")
            for face in card.card_faces:
                print(f"      • {face['name']} ({face['type_line']})")
        print()

    # Cleanup
    await engine.dispose()

    print("=" * 80)
    print("Demonstration complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nError during demonstration: {e}")
        raise

#!/usr/bin/env python3
"""Verify that image URIs are present in the database."""

import asyncio
import sys

from src.data.database import create_engine, create_session_factory
from src.data.repositories.card import CardRepository


async def main() -> int:
    """Check if cards have image URIs."""
    # Create database connection
    engine = create_engine()
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        repo = CardRepository(session)

        # Check a few well-known cards
        test_cards = ["Lightning Bolt", "Black Lotus", "Counterspell"]

        print("Checking image URI data:\n")
        cards_with_images = 0

        for card_name in test_cards:
            card = await repo.find_by_name_exact(card_name)
            if card:
                has_images = card.image_uris is not None and len(card.image_uris) > 0
                cards_with_images += 1 if has_images else 0

                print(f"✓ {card.name}")
                print(f"  Set: {card.set_name} ({card.set_code})")
                print(f"  Has images: {'Yes' if has_images else 'No'}")

                if has_images:
                    print(f"  Image sizes: {', '.join(card.image_uris.keys())}")
                    print(f"  Normal image: {card.image_uris.get('normal', 'N/A')[:60]}...")

                print()
            else:
                print(f"✗ {card_name} - Not found")
                print()

        # Get total statistics
        from sqlalchemy import text

        stmt = text("SELECT COUNT(*) FROM cards WHERE image_uris IS NOT NULL")
        result = await session.execute(stmt)
        total_with_images = result.scalar_one()

        stmt = text("SELECT COUNT(*) FROM cards")
        result = await session.execute(stmt)
        total_cards = result.scalar_one()

        print("Database Statistics:")
        print(f"  Total cards: {total_cards:,}")
        print(f"  Cards with images: {total_with_images:,}")
        print(f"  Percentage: {(total_with_images / total_cards * 100):.1f}%")

        if total_with_images == 0:
            print("\n⚠️  No cards have image URIs!")
            print("You need to re-import the database:")
            print("  1. Backup: mv data/cards.db data/cards.db.backup")
            print("  2. Re-import: uv run python scripts/import_scryfall_data.py")
            return 1
        else:
            print("\n✓ Image URIs are present!")
            return 0

    await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

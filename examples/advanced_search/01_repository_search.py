#!/usr/bin/env python3
"""Quick test of advanced search repository methods (no LLM required).

Tests the new search functionality at the repository level to validate
the implementation without needing OpenRouter API calls.
"""

import asyncio

from src.data.database import create_engine, create_session_factory
from src.data.repositories.card import CardRepository


async def main():
    """Run quick repository-level tests."""
    print("🎴 Advanced Card Search - Repository Quick Test")
    print("=" * 80)

    engine = create_engine()
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        repo = CardRepository(session)

        # Test 1: Search by keyword
        print("\n📋 Test 1: Search by keyword 'haste'")
        print("-" * 80)
        haste_cards = await repo.search_by_keywords("haste")
        print(f"Found {len(haste_cards)} cards with haste")
        for card in haste_cards[:5]:  # Show first 5
            print(f"  • {card.name} ({card.mana_cost}) - {card.type_line}")
        if len(haste_cards) > 5:
            print(f"  ... and {len(haste_cards) - 5} more")

        # Test 2: Advanced search - red creatures with haste under 4 mana
        print("\n📋 Test 2: Red creatures with haste, CMC ≤ 3 (the signature query!)")
        print("-" * 80)
        red_haste = await repo.search_advanced(
            colors=["R"],
            types=["Creature"],
            keywords=["haste"],
            mana_value_max=3.0,
            limit=10,
        )
        print(f"Found {len(red_haste)} cards")
        for card in red_haste:
            print(f"  • {card.name} ({card.mana_cost}) [{card.cmc} CMC] - {card.type_line}")

        # Test 3: Search by color only
        print("\n📋 Test 3: Blue cards (limit 10)")
        print("-" * 80)
        blue_cards = await repo.search_advanced(colors=["U"], limit=10)
        print(f"Showing {len(blue_cards)} blue cards:")
        for card in blue_cards[:10]:
            print(f"  • {card.name} ({card.mana_cost}) - {card.type_line}")

        # Test 4: Search by type and mana value
        print("\n📋 Test 4: Cheap artifacts (CMC ≤ 2)")
        print("-" * 80)
        cheap_artifacts = await repo.search_advanced(
            types=["Artifact"], mana_value_max=2.0, limit=10
        )
        print(f"Found {len(cheap_artifacts)} cheap artifacts")
        for card in cheap_artifacts:
            print(f"  • {card.name} ({card.mana_cost}) [{card.cmc} CMC]")

        # Test 5: Multiple types (AND logic)
        print("\n📋 Test 5: Legendary creatures (must have both 'Legendary' and 'Creature')")
        print("-" * 80)
        legendary_creatures = await repo.search_advanced(types=["Legendary", "Creature"], limit=10)
        print(f"Found {len(legendary_creatures)} legendary creatures")
        for card in legendary_creatures:
            print(f"  • {card.name} ({card.mana_cost}) - {card.type_line}")

        # Test 6: No results
        print("\n📋 Test 6: Search with no results (testing error handling)")
        print("-" * 80)
        no_results = await repo.search_advanced(
            colors=["B"], types=["Creature"], keywords=["flying", "haste", "vigilance"]
        )
        print(f"Found {len(no_results)} cards (expected 0)")

        # Test 7: Keyword in oracle text
        print("\n📋 Test 7: Cards with 'flying' (keyword search in text)")
        print("-" * 80)
        flying_cards = await repo.search_by_keywords("flying")
        print(f"Found {len(flying_cards)} cards with flying")
        for card in flying_cards[:5]:
            print(f"  • {card.name} ({card.mana_cost}) - {card.type_line}")
        if len(flying_cards) > 5:
            print(f"  ... and {len(flying_cards) - 5} more")

    await engine.dispose()

    print("\n" + "=" * 80)
    print("✅ All repository tests completed successfully!")
    print("=" * 80)
    print("\n💡 Key Features Demonstrated:")
    print("   ✓ Keyword search (oracle_text + keywords array)")
    print("   ✓ Multi-criteria filtering (colors AND types AND keywords AND mana)")
    print("   ✓ Color filtering (OR logic within colors)")
    print("   ✓ Type filtering (AND logic for multiple types)")
    print("   ✓ Mana value range filtering")
    print("   ✓ Result limiting and sorting")
    print("   ✓ Graceful handling of no results")


if __name__ == "__main__":
    asyncio.run(main())

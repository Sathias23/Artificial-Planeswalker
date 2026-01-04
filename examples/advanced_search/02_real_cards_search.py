#!/usr/bin/env python3
"""Test advanced search with real playable cards (excluding tokens)."""

import asyncio

from src.data.database import create_engine, create_session_factory
from src.data.repositories.card import CardRepository


async def main():
    """Test search for real playable cards."""
    print("🎴 Advanced Card Search - Real Playable Cards Test")
    print("=" * 80)

    engine = create_engine()
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        repo = CardRepository(session)

        # Search for famous red creatures with haste
        print("\n📋 Famous Red Creatures with Haste (CMC 1-4)")
        print("-" * 80)

        # More targeted search - look for specific CMC values
        for cmc in [1, 2, 3, 4]:
            print(f"\n🔍 {cmc} Mana:")
            cards = await repo.search_advanced(
                colors=["R"],
                types=["Creature"],
                keywords=["haste"],
                mana_value_min=float(cmc),
                mana_value_max=float(cmc),
                limit=5,
            )

            # Filter out tokens (they have empty mana_cost)
            real_cards = [c for c in cards if c.mana_cost and "{" in c.mana_cost]

            if real_cards:
                for card in real_cards[:5]:
                    print(f"  • {card.name} {card.mana_cost}")
                    if card.oracle_text:
                        # Show first line of oracle text
                        first_line = card.oracle_text.split("\n")[0][:60]
                        print(f"    {first_line}...")
            else:
                print("  (No non-token cards found)")

        # Test some classic cards
        print("\n\n📋 Testing Classic Card Searches")
        print("-" * 80)

        # Mono-red burn spells
        print("\n🔥 Red Instant/Sorcery Spells (1-3 mana):")
        burn_spells = await repo.search_advanced(
            colors=["R"], types=["Instant"], mana_value_max=3.0, limit=10
        )
        real_spells = [c for c in burn_spells if c.mana_cost and "{" in c.mana_cost]
        for spell in real_spells[:5]:
            print(f"  • {spell.name} {spell.mana_cost} - {spell.type_line}")

        # Blue card draw
        print("\n💧 Blue Cards with 'draw' in text (2 mana or less):")
        draw_spells = await repo.search_advanced(
            colors=["U"], keywords=["draw"], mana_value_max=2.0, limit=10
        )
        real_draw = [c for c in draw_spells if c.mana_cost and "{" in c.mana_cost]
        for spell in real_draw[:5]:
            print(f"  • {spell.name} {spell.mana_cost}")

        # Dragons with flying
        print("\n🐉 Dragons with Flying:")
        dragons = await repo.search_advanced(types=["Dragon"], keywords=["flying"], limit=10)
        real_dragons = [c for c in dragons if c.mana_cost and "{" in c.mana_cost]
        for dragon in real_dragons[:5]:
            print(f"  • {dragon.name} {dragon.mana_cost} - {dragon.type_line}")

    await engine.dispose()

    print("\n" + "=" * 80)
    print("✅ Real card search completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

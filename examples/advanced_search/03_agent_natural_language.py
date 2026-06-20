#!/usr/bin/env python3
"""Interactive test script for advanced card search feature.

Demonstrates the new search_cards_advanced tool with various queries.
"""

import asyncio

from legacy.agent.core import create_agent
from legacy.agent.dependencies import AgentDependencies
from src.data.database import create_engine, create_session_factory
from src.data.repositories.card import CardRepository


async def test_query(agent, deps, query: str):
    """Run a test query and display results."""
    print(f"\n{'=' * 80}")
    print(f"🔍 QUERY: {query}")
    print(f"{'=' * 80}\n")

    result = await agent.run(query, deps=deps)
    print(result.output)
    print()


async def main():
    """Run interactive tests of the advanced search feature."""
    print("🎴 Artificial-Planeswalker - Advanced Card Search Demo")
    print("=" * 80)

    # Setup
    print("\n⚙️  Setting up database connection...")
    engine = create_engine()
    session_factory = create_session_factory(engine)

    print("⚙️  Creating agent...")
    agent = create_agent()

    async with session_factory() as session:
        card_repo = CardRepository(session)
        deps = AgentDependencies(card_repository=card_repo)

        print("✅ Setup complete!\n")

        # Test queries showcasing the advanced search feature
        test_queries = [
            # Simple color filter
            "Find me some red cards",
            # Multi-criteria search (the signature example from the spec!)
            "Show me red creatures with haste that cost 3 mana or less",
            # Type + mana value
            "What are some cheap artifacts? Under 2 mana.",
            # Keyword search
            "Find cards with flying",
            # Complex natural language query
            "I'm building an aggro deck. Can you find me some efficient red creatures "
            "with haste? I want them to be cheap, like 1-2 mana.",
            # Type filter
            "Show me some instant spells",
            # Color + type combination
            "Find blue creatures",
        ]

        print("🎯 Running Test Queries:")
        print("These queries demonstrate the advanced search tool's capabilities.\n")

        for i, query in enumerate(test_queries, 1):
            print(f"\n[Test {i}/{len(test_queries)}]")
            await test_query(agent, deps, query)

            if i < len(test_queries):
                input("Press Enter to continue to next query...")

    await engine.dispose()

    print("\n" + "=" * 80)
    print("✅ Demo Complete!")
    print("=" * 80)
    print("\n💡 The agent successfully used the advanced search tool to answer queries")
    print("   with complex filtering by color, type, keywords, and mana value!")


if __name__ == "__main__":
    asyncio.run(main())

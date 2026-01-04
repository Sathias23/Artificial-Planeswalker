#!/usr/bin/env python3
"""End-to-end validation script for the complete data layer.

This script validates:
1. Database initialization
2. Scryfall data import (100+ cards)
3. Query by name (exact and partial)
4. Query by colors
5. Query by type
6. Query by format legality
7. Performance requirements (NFR7: <500ms)
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from sqlalchemy import select

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.importer import import_cards
from src.data.importers.parser import stream_cards
from src.data.importers.transformers import transform_scryfall_card
from src.data.models.card import CardModel
from src.data.repositories.card import CardRepository


class ValidationResult:
    """Track validation results."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.passed = False
        self.message = ""
        self.duration_ms = 0.0

    def success(self, message: str, duration_ms: float = 0.0) -> None:
        """Mark validation as successful."""
        self.passed = True
        self.message = message
        self.duration_ms = duration_ms

    def failure(self, message: str, duration_ms: float = 0.0) -> None:
        """Mark validation as failed."""
        self.passed = False
        self.message = message
        self.duration_ms = duration_ms

    def __str__(self) -> str:
        """String representation."""
        status = "✅ PASS" if self.passed else "❌ FAIL"
        duration_str = f" ({self.duration_ms:.1f}ms)" if self.duration_ms > 0 else ""
        return f"{status} - {self.name}{duration_str}\n      {self.message}"


async def create_test_dataset(tmp_path: Path, num_cards: int = 100) -> Path:
    """Create a test dataset with diverse card types.

    Args:
        tmp_path: Temporary directory for test data.
        num_cards: Number of cards to generate (minimum 100).

    Returns:
        Path to the generated JSON file.
    """
    cards = []

    # Add diverse card types for testing
    card_templates = [
        # Red instant
        {
            "name": "Lightning Bolt",
            "colors": ["R"],
            "color_identity": ["R"],
            "type_line": "Instant",
            "mana_cost": "{R}",
            "cmc": 1.0,
            "legalities": {"modern": "legal", "standard": "not_legal", "commander": "legal"},
        },
        # Blue creature
        {
            "name": "Delver of Secrets",
            "colors": ["U"],
            "color_identity": ["U"],
            "type_line": "Creature — Human Wizard",
            "mana_cost": "{U}",
            "cmc": 1.0,
            "legalities": {"modern": "legal", "legacy": "legal", "commander": "legal"},
        },
        # Green land
        {
            "name": "Forest",
            "colors": [],
            "color_identity": ["G"],
            "type_line": "Basic Land — Forest",
            "mana_cost": "",
            "cmc": 0.0,
            "legalities": {"standard": "legal", "modern": "legal", "commander": "legal"},
        },
        # Artifact
        {
            "name": "Sol Ring",
            "colors": [],
            "color_identity": [],
            "type_line": "Artifact",
            "mana_cost": "{1}",
            "cmc": 1.0,
            "legalities": {"commander": "legal", "vintage": "legal", "legacy": "banned"},
        },
        # Multi-color creature
        {
            "name": "Reflector Mage",
            "colors": ["W", "U"],
            "color_identity": ["W", "U"],
            "type_line": "Creature — Human Wizard",
            "mana_cost": "{1}{W}{U}",
            "cmc": 3.0,
            "legalities": {"modern": "legal", "pioneer": "banned", "commander": "legal"},
        },
    ]

    for i in range(num_cards):
        template = card_templates[i % len(card_templates)]
        card = {
            "id": f"test-card-{i:04d}",
            "name": f"{template['name']} {i}" if i >= len(card_templates) else template["name"],
            "oracle_id": f"oracle-{i:04d}",
            "type_line": template["type_line"],
            "mana_cost": template["mana_cost"],
            "cmc": template["cmc"],
            "oracle_text": f"Test card {i}",
            "colors": template["colors"],
            "color_identity": template["color_identity"],
            "keywords": [],
            "legalities": template["legalities"],
            "rarity": "common",
            "set": "tst",
            "set_name": "Test Set",
            "collector_number": str(i),
        }
        cards.append(card)

    json_path = tmp_path / "test_cards.json"
    json_path.write_text(json.dumps(cards))

    return json_path


async def validate_data_layer() -> list[ValidationResult]:
    """Run all validation tests.

    Returns:
        List of ValidationResult objects.
    """
    results: list[ValidationResult] = []

    # Setup test database
    db_path = Path("data/test_validation.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite+aiosqlite:///{db_path.absolute()}"

    print("=" * 70)
    print("DATA LAYER VALIDATION")
    print("=" * 70)
    print()

    try:
        # Test 1: Database Initialization
        print("Test 1: Database Initialization")
        result = ValidationResult("Database initialization")
        start_time = time.time()

        try:
            engine = create_engine(database_url)
            await init_database(engine)
            session_factory = create_session_factory(engine)
            duration_ms = (time.time() - start_time) * 1000
            result.success("Database initialized successfully", duration_ms)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result.failure(f"Failed to initialize database: {e}", duration_ms)
            results.append(result)
            return results

        results.append(result)
        print(f"  {result}")
        print()

        # Test 2: Import Sample Data
        print("Test 2: Import Sample Scryfall Data (100+ cards)")
        result = ValidationResult("Data import")
        start_time = time.time()

        try:
            # Create test dataset
            test_json = await create_test_dataset(Path("/tmp"), num_cards=150)

            async with session_factory() as session:
                cards_stream = stream_cards(test_json)

                def transform_cards():
                    for card_json in cards_stream:
                        yield transform_scryfall_card(card_json)

                stats = await import_cards(session, transform_cards(), batch_size=50)

            duration_ms = (time.time() - start_time) * 1000

            if stats.total_inserted >= 100:
                result.success(
                    f"Imported {stats.total_inserted} cards successfully "
                    f"(errors: {stats.total_errors})",
                    duration_ms,
                )
            else:
                result.failure(
                    f"Only imported {stats.total_inserted} cards (minimum 100 required)",
                    duration_ms,
                )

            # Clean up test file
            test_json.unlink()
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result.failure(f"Import failed: {e}", duration_ms)

        results.append(result)
        print(f"  {result}")
        print()

        # Test 3: Query by Name (Exact)
        print("Test 3: Query by Name (Exact Match)")
        result = ValidationResult("Query by exact name")

        try:
            async with session_factory() as session:
                repo = CardRepository(session)

                start_time = time.time()
                card = await repo.find_by_name_exact("Lightning Bolt")
                duration_ms = (time.time() - start_time) * 1000

                if card and card.name == "Lightning Bolt":
                    result.success(
                        f"Found card: '{card.name}' (ID: {card.id})",
                        duration_ms,
                    )
                else:
                    result.failure("Card not found or incorrect", duration_ms)
        except Exception as e:
            result.failure(f"Query failed: {e}")

        results.append(result)
        print(f"  {result}")
        print()

        # Test 4: Query by Name (Partial)
        print("Test 4: Query by Name (Partial Match)")
        result = ValidationResult("Query by partial name")

        try:
            async with session_factory() as session:
                repo = CardRepository(session)

                start_time = time.time()
                cards = await repo.find_by_name_partial("Bolt")
                duration_ms = (time.time() - start_time) * 1000

                if len(cards) > 0 and any("Bolt" in c.name for c in cards):
                    result.success(
                        f"Found {len(cards)} cards matching 'Bolt'",
                        duration_ms,
                    )
                else:
                    result.failure("No cards found", duration_ms)
        except Exception as e:
            result.failure(f"Query failed: {e}")

        results.append(result)
        print(f"  {result}")
        print()

        # Test 5: Query by Colors
        print("Test 5: Query by Colors")
        result = ValidationResult("Query by colors")

        try:
            async with session_factory() as session:
                repo = CardRepository(session)

                start_time = time.time()
                red_cards = await repo.find_by_colors("R")
                duration_ms = (time.time() - start_time) * 1000

                if len(red_cards) > 0:
                    result.success(
                        f"Found {len(red_cards)} red cards",
                        duration_ms,
                    )
                else:
                    result.failure("No red cards found", duration_ms)
        except Exception as e:
            result.failure(f"Query failed: {e}")

        results.append(result)
        print(f"  {result}")
        print()

        # Test 6: Query by Type
        print("Test 6: Query by Type")
        result = ValidationResult("Query by type")

        try:
            async with session_factory() as session:
                repo = CardRepository(session)

                start_time = time.time()
                creatures = await repo.find_by_type("Creature")
                duration_ms = (time.time() - start_time) * 1000

                if len(creatures) > 0:
                    result.success(
                        f"Found {len(creatures)} creatures",
                        duration_ms,
                    )
                else:
                    result.failure("No creatures found", duration_ms)
        except Exception as e:
            result.failure(f"Query failed: {e}")

        results.append(result)
        print(f"  {result}")
        print()

        # Test 7: Query by Format Legality
        print("Test 7: Query by Format Legality")
        result = ValidationResult("Query by format legality")

        try:
            async with session_factory() as session:
                # Query using raw SQL for legality check
                stmt = select(CardModel).where(
                    CardModel.legalities["modern"].as_string() == "legal"
                )

                start_time = time.time()
                query_result = await session.execute(stmt)
                modern_legal_cards = query_result.scalars().all()
                duration_ms = (time.time() - start_time) * 1000

                if len(modern_legal_cards) > 0:
                    result.success(
                        f"Found {len(modern_legal_cards)} Modern-legal cards",
                        duration_ms,
                    )
                else:
                    result.failure("No Modern-legal cards found", duration_ms)
        except Exception as e:
            result.failure(f"Query failed: {e}")

        results.append(result)
        print(f"  {result}")
        print()

        # Test 8: Performance Check (NFR7: <500ms)
        print("Test 8: Performance Validation (NFR7: <500ms per query)")
        result = ValidationResult("Query performance")

        # Check if any query exceeded 500ms
        slow_queries = [r for r in results if r.duration_ms > 500]

        if len(slow_queries) == 0:
            max_duration = max(r.duration_ms for r in results if r.duration_ms > 0)
            result.success(
                f"All queries under 500ms (max: {max_duration:.1f}ms)",
                max_duration,
            )
        else:
            slow_query_names = ", ".join(r.name for r in slow_queries)
            result.failure(f"{len(slow_queries)} queries exceeded 500ms: {slow_query_names}")

        results.append(result)
        print(f"  {result}")
        print()

        # Cleanup
        await engine.dispose()

    finally:
        # Clean up test database
        if db_path.exists():
            db_path.unlink()
            print("Cleaned up test database")
            print()

    return results


def print_summary(results: list[ValidationResult]) -> bool:
    """Print validation summary and return success status.

    Args:
        results: List of validation results.

    Returns:
        True if all tests passed, False otherwise.
    """
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print()

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"Results: {passed}/{total} tests passed")
    print()

    if passed == total:
        print("🎉 ALL VALIDATIONS PASSED!")
        print()
        print("Epic 1: Foundation & Data Infrastructure is COMPLETE!")
        print()
        print("The data layer is ready for production use:")
        print("  ✅ Database initialization working")
        print("  ✅ Scryfall data import functional")
        print("  ✅ All query types working")
        print("  ✅ Performance requirements met (<500ms)")
        return True
    else:
        print("⚠️  SOME VALIDATIONS FAILED")
        print()
        print("Failed tests:")
        for result in results:
            if not result.passed:
                print(f"  - {result.name}: {result.message}")
        return False


async def main() -> int:
    """Main entry point."""
    try:
        results = await validate_data_layer()
        success = print_summary(results)
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
        return 130

    except Exception as e:
        print(f"\nValidation failed with error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

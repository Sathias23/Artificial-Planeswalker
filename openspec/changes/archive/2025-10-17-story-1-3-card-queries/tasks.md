# Implementation Tasks: Story 1.3 Card Query Functionality

## 1. Repository Implementation
- [x] 1.1 Implement `find_by_name_exact()` in CardRepository with exact case-insensitive match
- [x] 1.2 Implement `find_by_name_partial()` with `.ilike()` substring search
- [x] 1.3 Implement `find_by_colors()` with JSON array containment query
- [x] 1.4 Implement `find_by_type()` with case-insensitive substring search
- [x] 1.5 Add Pydantic schema conversion in all query methods using `Card.model_validate()`
- [x] 1.6 Add type hints to all methods (return `Card | None` or `list[Card]`)
- [x] 1.7 Add comprehensive docstrings with parameter and return type documentation

## 2. Test Fixtures
- [x] 2.1 Create `tests/fixtures/card_data.py` with sample card data factory
- [x] 2.2 Add diverse test cards: single-color, multi-color, colorless, various types
- [x] 2.3 Add multi-face card fixtures (Transform, Modal DFC)
- [x] 2.4 Create pytest fixture for in-memory test database setup

## 3. Unit Tests
- [x] 3.1 Write tests for `find_by_name_exact()`: found, not found, case insensitivity
- [x] 3.2 Write tests for `find_by_name_partial()`: multiple matches, no matches, case insensitivity
- [x] 3.3 Write tests for `find_by_colors()`: single color, multi-color cards, colorless, not found
- [x] 3.4 Write tests for `find_by_type()`: exact type, subtype matches, case insensitivity, not found
- [x] 3.5 Add tests verifying Pydantic schema return types (not ORM models)
- [x] 3.6 Add async session fixture and repository fixture
- [x] 3.7 Verify test coverage >80% with `uv run pytest --cov=src/data/repositories`

## 4. CLI Demonstration Script
- [x] 4.1 Create `scripts/test_queries.py` with async main function
- [x] 4.2 Add database initialization and sample card insertion
- [x] 4.3 Demonstrate exact name search with visible output
- [x] 4.4 Demonstrate partial name search with multiple results
- [x] 4.5 Demonstrate color filtering (red, blue, colorless)
- [x] 4.6 Demonstrate type filtering (Instant, Creature, etc.)
- [x] 4.7 Add error handling and clean shutdown
- [x] 4.8 Test script execution: `uv run python scripts/test_queries.py`

## 5. Documentation
- [x] 5.1 Add usage examples to CardRepository docstrings
- [x] 5.2 Update `README.md` with query examples (if README exists)
- [x] 5.3 Document edge cases and limitations in code comments

## 6. Validation
- [x] 6.1 Run `openspec validate story-1-3-card-queries --strict` and fix any issues
- [x] 6.2 Run full test suite with `uv run pytest` and ensure all tests pass
- [x] 6.3 Run mypy/pyright type checking and resolve type errors
- [x] 6.4 Verify CLI script runs successfully without errors
- [x] 6.5 Mark all tasks in this checklist as complete before requesting review

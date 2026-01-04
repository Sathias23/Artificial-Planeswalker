# Implementation Tasks

## 1. Repository Layer Implementation

- [x] 1.1 Add `color_mode` parameter to `CardRepository.search_advanced()` method signature
  - [x] 1.1.1 Add parameter with default `color_mode: Literal["any", "all", "exact", "at_most"] = "any"`
  - [x] 1.1.2 Update method docstring with color_mode examples
  - [x] 1.1.3 Update type imports (`from typing import Literal`)

- [x] 1.2 Implement color filtering logic for `"any"` mode (existing behavior)
  - [x] 1.2.1 Refactor existing OR logic into conditional block
  - [x] 1.2.2 Add comment explaining OR logic

- [x] 1.3 Implement color filtering logic for `"all"` mode
  - [x] 1.3.1 Use AND logic with `and_()` instead of `or_()`
  - [x] 1.3.2 Keep same string pattern matching approach

- [x] 1.4 Implement color filtering logic for `"exact"` mode
  - [x] 1.4.1 Add all-colors-present check (AND logic)
  - [x] 1.4.2 Add `json_array_length()` check for exact count
  - [x] 1.4.3 Handle special case: empty colors list → colorless cards

- [x] 1.5 Implement color filtering logic for `"at_most"` mode
  - [x] 1.5.1 Implement using NOT LIKE for excluded colors (simple approach)
  - [x] 1.5.2 Add performance measurement logging
  - [x] 1.5.3 Document optimization path if performance threshold exceeded

## 2. Agent Tools Layer Implementation

- [x] 2.1 Add `color_mode` field to `CardSearchFilters` model
  - [x] 2.1.1 Add field with default `color_mode: Literal["any", "all", "exact", "at_most"] | None = "any"`
  - [x] 2.1.2 Add comprehensive Field description with examples
  - [x] 2.1.3 Include MTG terminology examples (Azorius, Boros, etc.)

- [x] 2.2 Pass `color_mode` parameter through to repository
  - [x] 2.2.1 Update `search_cards_advanced()` function to extract `color_mode` from filters
  - [x] 2.2.2 Pass to `repo.search_advanced(color_mode=filters.color_mode)`

- [x] 2.3 Update tool docstrings
  - [x] 2.3.1 Add color_mode to function docstring
  - [x] 2.3.2 Add examples of each mode in docstring
  - [x] 2.3.3 Update notes section with mode behavior

## 3. Testing

- [x] 3.1 Repository unit tests (`test_card_repository.py`)
  - [x] 3.1.1 Test `"any"` mode with multiple colors (existing behavior)
  - [x] 3.1.2 Test `"all"` mode - cards must have ALL specified colors
  - [x] 3.1.3 Test `"exact"` mode - cards must have EXACTLY specified colors
  - [x] 3.1.4 Test `"at_most"` mode - cards must have subset of specified colors
  - [x] 3.1.5 Test edge case: single color with different modes (should be identical)
  - [x] 3.1.6 Test edge case: empty colors list with `"exact"` mode (colorless)
  - [x] 3.1.7 Test edge case: all 5 colors with different modes
  - [x] 3.1.8 Test color_mode with format filter combination
  - [x] 3.1.9 Test color_mode with pagination

- [x] 3.2 Agent tools unit tests (`test_card_search.py`)
  - [x] 3.2.1 Test CardSearchFilters validation with color_mode
  - [x] 3.2.2 Test default color_mode="any" behavior
  - [x] 3.2.3 Test each mode passes correctly to repository

- [ ] 3.3 Integration tests
  - [ ] 3.3.1 Test with real Scryfall data (sample multicolor cards)
  - [ ] 3.3.2 Test LLM agent interpretation of color mode queries
  - [ ] 3.3.3 Test Azorius query: "show me white and blue cards"
  - [ ] 3.3.4 Test color identity query: "cards that fit in white-blue"

- [ ] 3.4 Performance benchmarks
  - [ ] 3.4.1 Benchmark `"any"` mode (baseline)
  - [ ] 3.4.2 Benchmark `"all"` mode
  - [ ] 3.4.3 Benchmark `"exact"` mode
  - [ ] 3.4.4 Benchmark `"at_most"` mode with full dataset
  - [ ] 3.4.5 Document performance results
  - [ ] 3.4.6 If >500ms, implement optimization strategy

## 4. Documentation

- [x] 4.1 Update CLAUDE.md
  - [x] 4.1.1 Add color_mode parameter to CardRepository section
  - [x] 4.1.2 Add examples for each mode
  - [x] 4.1.3 Document MTG terminology mappings

- [x] 4.2 Update code comments
  - [x] 4.2.1 Add inline comments explaining each mode's SQL logic
  - [x] 4.2.2 Add examples in docstrings

- [x] 4.3 Update examples (if any color search examples exist)
  - [x] 4.3.1 Add example for `"exact"` mode (Azorius cards)
  - [x] 4.3.2 Add example for `"at_most"` mode (color identity)

## 5. Validation

- [x] 5.1 Run OpenSpec validation
  - [x] 5.1.1 `openspec validate add-color-mode-filtering --strict`
  - [x] 5.1.2 Fix any validation errors

- [x] 5.2 Run test suite
  - [x] 5.2.1 `uv run pytest tests/unit/data/test_card_repository.py -v`
  - [x] 5.2.2 `uv run pytest tests/unit/agent/tools/test_card_search.py -v`
  - [x] 5.2.3 `uv run pytest --cov=src` (ensure >80% coverage for new code)

- [x] 5.3 Run type checking
  - [x] 5.3.1 `uv run mypy src/data/repositories/card.py`
  - [x] 5.3.2 `uv run mypy src/agent/tools/card_search.py`

- [x] 5.4 Run linting
  - [x] 5.4.1 `uv run ruff check . --fix`
  - [x] 5.4.2 `uv run ruff format .`

## 6. Manual Testing

- [ ] 6.1 Test with Chainlit UI
  - [ ] 6.1.1 Query: "Show me white and blue cards" (should use `"all"` or `"exact"`)
  - [ ] 6.1.2 Query: "Find Azorius cards" (should use `"exact"`)
  - [ ] 6.1.3 Query: "White or blue creatures" (should use `"any"`)
  - [ ] 6.1.4 Query: "Cards that fit in my white-blue deck" (should use `"at_most"`)

- [x] 6.2 Verify backward compatibility
  - [x] 6.2.1 Existing queries without color_mode work unchanged
  - [x] 6.2.2 Default behavior matches current OR logic

## 7. Pre-Merge Checklist

- [x] 7.1 All tests passing
- [x] 7.2 Type checking passes (mypy)
- [x] 7.3 Linting passes (ruff)
- [x] 7.4 OpenSpec validation passes
- [x] 7.5 Documentation updated
- [ ] 7.6 Performance benchmarks documented (especially `"at_most"` mode)
- [x] 7.7 Backward compatibility verified

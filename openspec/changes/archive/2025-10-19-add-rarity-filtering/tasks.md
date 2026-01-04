# Implementation Tasks

## 1. Update Card Repository

- [x] 1.1 Add `rarity` parameter to `search_advanced()` method signature with type hint `str | list[str] | None`
- [x] 1.2 Add SQL filtering logic for single rarity value (e.g., `rarity="rare"`)
- [x] 1.3 Add SQL filtering logic for multiple rarity values (e.g., `rarity=["rare", "mythic"]`)
- [x] 1.4 Update method docstring to document rarity parameter and valid values
- [x] 1.5 Ensure rarity filtering combines correctly with existing filters (colors, types, keywords, mana_value)

## 2. Update Agent Tool

- [x] 2.1 Add `rarity` parameter to `search_cards_advanced` tool function with PydanticAI type annotation
- [x] 2.2 Pass rarity parameter through to repository `search_advanced()` call
- [x] 2.3 Update tool docstring to document rarity filtering capability
- [x] 2.4 Add examples showing rarity filtering usage in docstring

## 3. Add Unit Tests for Repository

- [x] 3.1 Add test case: filter by single rarity value (`rarity="rare"`)
- [x] 3.2 Add test case: filter by multiple rarity values (`rarity=["rare", "mythic"]`)
- [x] 3.3 Add test case: rarity filter combined with color filter
- [x] 3.4 Add test case: rarity filter with format filter (Standard + rare)
- [x] 3.5 Add test case: rarity filter returns empty list when no matches
- [x] 3.6 Add test case: None rarity parameter returns all rarities (no filtering)
- [x] 3.7 Run repository test suite and verify all tests pass

## 4. Add Unit Tests for Agent Tool

- [x] 4.1 Add test case: tool invoked with `rarity="rare"` parameter
- [x] 4.2 Add test case: tool invoked with `rarity=["rare", "mythic"]` parameter
- [x] 4.3 Add test case: rarity filter combined with other filters (colors, types, keywords)
- [x] 4.4 Add test case: verify tool docstring includes rarity parameter
- [x] 4.5 Run agent tool test suite and verify all tests pass

## 5. Integration Testing

- [x] 5.1 Start Chainlit app and test query: "show me rare red creatures"
- [x] 5.2 Test query: "find mythic black cards under 4 mana"
- [x] 5.3 Test query: "show me rare or mythic instants with haste"
- [x] 5.4 Test query with format filter: "find rare Standard-legal creatures"
- [x] 5.5 Verify tool Steps display correct rarity filter in parameters
- [x] 5.6 Verify results match expected rarity values

## 6. Code Quality

- [x] 6.1 Run `uv run ruff check . --fix` and resolve any linting issues
- [x] 6.2 Run `uv run ruff format .` to ensure consistent formatting
- [x] 6.3 Run `uv run mypy src/` and fix any type checking issues
- [x] 6.4 Update inline comments to clarify rarity filtering logic
- [x] 6.5 Ensure all modified functions have clear docstrings with examples

## 7. Documentation

- [x] 7.1 Document valid rarity values in repository method docstring (common, uncommon, rare, mythic, special, bonus)
- [x] 7.2 Update CLAUDE.md with rarity filtering example usage
- [x] 7.3 Add rarity filtering to CLI demonstration script if applicable

## 8. Bug Report Resolution

- [x] 8.1 Update bug report 5c15209f status to "resolved" using `scripts/manage_bug_reports.py`
- [x] 8.2 Verify bug report log shows resolution timestamp

# Implementation Tasks

## 1. Card Formatting Module

- [x] 1.1 Create `src/ui/formatters.py` module with proper imports and type hints
- [x] 1.2 Implement `format_card_details(card: Card) -> str` function
  - Card name on first line
  - Mana cost with text symbols (e.g., "{1}{R}{G}")
  - Type line on separate line
  - Oracle text formatted with line breaks
- [x] 1.3 Implement `format_mana_symbols(mana_cost: str) -> str` function
  - Convert Scryfall mana notation to readable text/unicode
  - Handle colorless {C}, colored {W}{U}{B}{R}{G}, hybrid, and Phyrexian symbols
- [x] 1.4 Add `format_card_list(cards: list[Card], limit: int = 10) -> str` function
  - Numbered list format
  - Show card name, mana cost, and type for each
  - Limit results to prevent overflow (default 10, max 15)
  - Add "...and X more" message if truncated
- [x] 1.5 Write unit tests for all formatting functions
  - Test various card types (creature, instant, sorcery, land)
  - Test edge cases (missing mana cost, long oracle text)
  - Test list truncation and formatting

## 2. Visual Emphasis and Styling

- [x] 2.1 Add markdown formatting for card types
  - Bold for card name: `**{card_name}**`
  - Emphasis for card types
- [x] 2.2 Implement color indicator formatting
  - Use color names or symbols for visual clarity
  - Example: "Colors: Red, Green" or "🔴🟢"
- [x] 2.3 Add visual separators between card sections
  - Use markdown horizontal rules or line breaks
  - Ensure readability on Chainlit interface

## 3. Chainlit Integration

- [x] 3.1 Update agent tools to use formatters (card_lookup.py and card_search.py)
- [x] 3.2 Remove old formatting functions from agent tools
- [x] 3.3 Handle single card vs. multiple card display scenarios
  - Single card: detailed format with all fields (format_card_details)
  - Multiple cards: compact list format (format_card_list)
- [x] 3.4 Error handling inherited from agent tools (graceful failures maintained)

## 4. Testing and Validation

- [x] 4.1 Run unit tests for formatting functions (`uv run pytest tests/unit/ui/`)
- [x] 4.2 Update agent tool tests to match new formatting
- [x] 4.3 All unit tests passing (181 passed, 1 skipped)
- [ ] 4.4 Manual testing: Verify formatting in running Chainlit application
  - Test with creature, instant, sorcery, planeswalker, land
  - Verify markdown renders correctly in Chainlit
  - Test with 5, 10, 15, 20+ results
  - Verify pagination/truncation works
- [x] 4.5 Type checking: Run `uv run mypy src/ui/formatters.py` - PASSED
- [x] 4.6 Code quality: Run `uv run ruff check src/ui/ --fix` - PASSED

## 5. Documentation

- [x] 5.1 Add docstrings to all formatting functions
- [x] 5.2 Document mana symbol format conventions
- [x] 5.3 No UI module README needed (simple single-file addition)

# Implementation Tasks

## 1. Business Logic Layer - Deck Validation

- [ ] 1.1 Create `src/logic/deck_validator.py` module
- [ ] 1.2 Implement `validate_card_addition(deck: Deck, card: Card, quantity: int) -> ValidationResult` function
  - [ ] 1.2.1 Check if card is a basic land (unlimited copies allowed)
  - [ ] 1.2.2 Check if adding quantity would exceed 4-copy limit for non-basic lands
  - [ ] 1.2.3 Return `ValidationResult` with is_valid bool and error message
- [ ] 1.3 Implement `is_basic_land(card: Card) -> bool` helper function
  - [ ] 1.3.1 Check if type_line contains "Basic Land"
- [ ] 1.4 Implement `get_current_card_count(deck: Deck, card_id: str) -> int` helper function
  - [ ] 1.4.1 Sum quantities of card in deck (mainboard only)
- [ ] 1.5 Export functions in `src/logic/__init__.py`

## 2. Agent Tool Implementation

- [ ] 2.1 Add `add_card_to_deck` tool to `src/agent/tools/deck_tools.py`
  - [ ] 2.1.1 Accept `name: str` (card name) and `quantity: int = 1` parameters
  - [ ] 2.1.2 Check if active_deck_id is set in dependencies context (fail gracefully if not)
  - [ ] 2.1.3 Look up card by name using `CardRepository.find_by_name_exact()`
  - [ ] 2.1.4 Handle card not found (partial match suggestions)
  - [ ] 2.1.5 Validate card is Standard-legal by checking card.legalities
  - [ ] 2.1.6 Get current deck using `DeckRepository.get_deck_with_cards()`
  - [ ] 2.1.7 Call `validate_card_addition()` to check deck construction rules
  - [ ] 2.1.8 If validation passes, call `DeckRepository.add_card_to_deck()`
  - [ ] 2.1.9 Return confirmation with card name, quantity, and updated deck count
  - [ ] 2.1.10 Return clear error message if validation fails
- [ ] 2.2 Update tool docstring with usage examples

## 3. Unit Tests

- [ ] 3.1 Create `tests/unit/logic/test_deck_validator.py`
  - [ ] 3.1.1 Test `validate_card_addition` with valid addition (under 4 copies)
  - [ ] 3.1.2 Test validation failure when exceeding 4-copy limit
  - [ ] 3.1.3 Test basic land exception (allow >4 copies)
  - [ ] 3.1.4 Test `is_basic_land` with various card types
  - [ ] 3.1.5 Test `get_current_card_count` with empty deck and deck with cards
- [ ] 3.2 Create `tests/unit/agent/test_deck_tools.py` (or extend existing)
  - [ ] 3.2.1 Test `add_card_to_deck` tool with valid card and quantity
  - [ ] 3.2.2 Test tool with no active deck (graceful failure)
  - [ ] 3.2.3 Test tool with card not found
  - [ ] 3.2.4 Test tool with non-Standard legal card
  - [ ] 3.2.5 Test tool when adding would exceed 4-copy limit
  - [ ] 3.2.6 Test tool with basic land (allow >4 copies)
  - [ ] 3.2.7 Test tool with quantity parameter variations (1, 2, 3, 4)

## 4. Integration Tests

- [ ] 4.1 Create `tests/integration/agent/test_deck_building.py`
  - [ ] 4.1.1 Test end-to-end: create deck → add card → verify card in deck
  - [ ] 4.1.2 Test adding multiple different cards to same deck
  - [ ] 4.1.3 Test adding same card multiple times (quantity tracking)
  - [ ] 4.1.4 Test validation failure scenario (exceed limit → card not added)
  - [ ] 4.1.5 Test basic land scenario (add >4 copies successfully)

## 5. Documentation and Error Messages

- [ ] 5.1 Document error message patterns in tool docstring
  - [ ] 5.1.1 "No active deck. Create a deck first with 'create a new deck'."
  - [ ] 5.1.2 "Card '{name}' not found. Did you mean: {suggestions}?"
  - [ ] 5.1.3 "'{card_name}' is not legal in Standard format."
  - [ ] 5.1.4 "Cannot add {quantity} copies of '{card_name}'. Deck would have {total} copies (max 4 for non-basic lands)."
- [ ] 5.2 Add usage examples to CLAUDE.md if needed

## 6. Type Safety and Code Quality

- [ ] 6.1 Run `uv run mypy src/` and fix any type errors
- [ ] 6.2 Run `uv run ruff check . --fix` and address linting issues
- [ ] 6.3 Run `uv run ruff format .` to format code
- [ ] 6.4 Ensure all functions have proper type hints

## 7. Validation and Completion

- [ ] 7.1 Run all unit tests: `uv run pytest tests/unit/`
- [ ] 7.2 Run integration tests: `uv run pytest tests/integration/`
- [ ] 7.3 Manual test in Chainlit: create deck → add cards → verify behavior
- [ ] 7.4 Verify error messages are clear and actionable
- [ ] 7.5 Update this checklist (mark all items [x]) after completion

# Change Proposal: Add Card to Deck Tool with Validation

## Why

Users need to add cards to their decks through natural language commands while ensuring deck construction rules are followed. This implements Story 4.3 from the PRD and is essential for the deck building workflow. Without proper validation, users could create illegal decks that violate Standard format rules.

## What Changes

- Add `add_card_to_deck` PydanticAI tool for adding cards to the active deck
- Implement deck construction rule validation in business logic layer (`src/logic/deck_validator.py`):
  - **Validate max 4 copies rule** (except basic lands which are unlimited)
  - **Validate Standard format legality** before adding cards
  - **Check if adding would exceed copy limit** with clear error messages
- Tool accepts card name and quantity parameters (quantity defaults to 1)
- Tool requires an active deck to be set in session context (fails gracefully if none)
- Return confirmation with updated deck count and card details
- Provide clear, actionable error messages for rule violations
- Add unit tests for validation logic and tool behavior
- Add integration tests for end-to-end card addition workflow

## Impact

- **Affected specs**:
  - `agent-tools` (new tool requirements)
  - New capability: `deck-validation` (business logic for deck construction rules)
- **Affected code**:
  - `src/agent/tools/deck_tools.py` - add `add_card_to_deck` tool function
  - `src/logic/deck_validator.py` - **NEW FILE** with validation functions
  - `src/logic/__init__.py` - export validation functions
  - `tests/unit/logic/test_deck_validator.py` - **NEW FILE** for validation unit tests
  - `tests/unit/agent/test_deck_tools.py` - add tests for `add_card_to_deck` tool
  - `tests/integration/agent/test_deck_building.py` - **NEW FILE** for end-to-end tests
- **Dependencies**:
  - Requires `DeckRepository.add_card_to_deck()` from Story 4.1 (already implemented)
  - Requires active deck context from Story 4.2 `add-create-deck-tool` change (in progress)
- **User-facing**: Enables "add 4 Lightning Bolt to my deck" with validation feedback

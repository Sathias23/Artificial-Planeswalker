# Implementation Tasks: Deck View and Management Tools

## 1. Core Infrastructure

- [ ] 1.1 Update `src/agent/dependencies.py` to add `deck_context` dict to `AgentDependencies`
  - Add field: `deck_context: dict[str, Any]` with default `{"active_deck_id": None}`
  - Update initialization to ensure deck_context is always present
  - Add type hints for deck_context keys

- [ ] 1.2 Update `src/ui/app.py` to initialize deck_context in `get_agent_dependencies()`
  - Ensure deck_context is created per session
  - Initialize with `active_deck_id: None` for new sessions

## 2. Deck Display Formatting

- [ ] 2.1 Create `format_deck_for_display()` in `src/ui/formatters.py`
  - Accept parameters: `deck: Deck`, `grouping: str = "type"`
  - Group cards by type: Creatures, Spells, Lands
  - Sort within groups: mana cost ascending, then alphabetically
  - Return markdown string with deck header and summary statistics

- [ ] 2.2 Add `_group_cards_by_type()` helper function
  - Parse type_line to categorize cards
  - Return dict with keys: "Creatures", "Spells", "Lands"

- [ ] 2.3 Add `_format_card_entry()` helper function
  - Format single card as: `Quantity - Card Name (Mana Cost) [Type Line]`
  - Handle missing mana cost (0-cost cards)

- [ ] 2.4 Add `_format_deck_summary()` helper function
  - Create header with deck name, format, card counts
  - Add legality indicator for Standard (60+ cards mainboard)

- [ ] 2.5 Add unit tests for formatting functions
  - Test grouping by type
  - Test sorting within groups
  - Test empty deck formatting
  - Test sideboard formatting
  - Test summary statistics

## 3. View Deck Tool

- [ ] 3.1 Create `src/agent/tools/deck_tools.py` module
  - Set up imports: RunContext, AgentDependencies, DeckRepository
  - Add docstring header for module

- [ ] 3.2 Implement `view_deck()` tool function
  - Decorator: `@agent.tool`
  - Parameters: `ctx: RunContext[AgentDependencies]`
  - Check if active_deck_id exists in context
  - Retrieve deck from repository with cards
  - Call `format_deck_for_display()` for formatting
  - Return formatted deck string or error message

- [ ] 3.3 Add error handling for view_deck
  - Handle no active deck set → "No active deck. Create or load a deck first."
  - Handle empty deck → "Your deck is empty. Add cards to get started."
  - Handle database errors → Raise exception for agent framework

- [ ] 3.4 Add docstring for LLM schema generation
  - Document tool purpose: "View the current active deck contents"
  - Document return format

- [ ] 3.5 Add unit tests for view_deck tool
  - Test viewing deck with cards
  - Test viewing empty deck
  - Test no active deck error
  - Mock repository and format function

## 4. Remove Card from Deck Tool

- [ ] 4.1 Implement `remove_card_from_deck()` tool function
  - Decorator: `@agent.tool`
  - Parameters: `ctx: RunContext[AgentDependencies]`, `card_name: str`, `sideboard: bool = False`
  - Check active_deck_id exists
  - Look up card by name (exact match preferred)
  - Call `deck_repository.remove_card_from_deck()`
  - Return confirmation or error message

- [ ] 4.2 Add card lookup logic
  - Use `card_repository.find_by_name_exact()` first
  - If not found, try `find_by_name_partial()` for suggestions
  - Handle ambiguous matches with "Did you mean?" response

- [ ] 4.3 Add error handling for remove_card
  - Handle no active deck
  - Handle card not found in database
  - Handle card not in deck
  - Handle database errors

- [ ] 4.4 Add docstring for LLM schema generation
  - Document parameters: card_name, sideboard flag
  - Document return format

- [ ] 4.5 Add unit tests for remove_card tool
  - Test successful removal from mainboard
  - Test successful removal from sideboard
  - Test card not in deck error
  - Test card not found in database error
  - Test no active deck error

## 5. Update Card Quantity Tool

- [ ] 5.1 Implement `update_card_quantity()` tool function
  - Decorator: `@agent.tool`
  - Parameters: `ctx: RunContext[AgentDependencies]`, `card_name: str`, `quantity: int`, `sideboard: bool = False`
  - Check active_deck_id exists
  - Look up card by name
  - Validate quantity against deck construction rules
  - Call repository method (update or add or remove based on quantity)
  - Return confirmation or error message

- [ ] 5.2 Add deck construction rule validation
  - Check max 4 copies for non-basic lands
  - Allow unlimited basic lands (check type_line for "Basic Land")
  - Return error message if validation fails

- [ ] 5.3 Add quantity=0 handling
  - Treat quantity=0 as remove operation
  - Call `deck_repository.remove_card_from_deck()`

- [ ] 5.4 Add error handling for update_quantity
  - Handle no active deck
  - Handle card not found in database
  - Handle invalid quantity (negative numbers)
  - Handle deck construction rule violations

- [ ] 5.5 Add docstring for LLM schema generation
  - Document parameters: card_name, quantity, sideboard flag
  - Document validation rules
  - Document return format

- [ ] 5.6 Add unit tests for update_quantity tool
  - Test increasing quantity
  - Test decreasing quantity
  - Test quantity=0 removal
  - Test max 4 copy validation
  - Test unlimited basic lands
  - Test adding card not in deck

## 6. Tool Registration

- [ ] 6.1 Register deck tools with agent in `src/agent/core.py`
  - Import deck_tools module
  - Ensure tools are decorated and discoverable
  - Verify tools appear in agent tool list

- [ ] 6.2 Test tool invocation via agent
  - Create test agent instance
  - Invoke tools with test dependencies
  - Verify tool calls execute correctly

## 7. Integration Tests

- [ ] 7.1 Create `tests/integration/agent/test_deck_tools_integration.py`
  - Set up test database fixture with sample deck and cards
  - Set up test agent with dependencies

- [ ] 7.2 Add integration test: view deck workflow
  - Create deck with cards in test DB
  - Set active deck in context
  - Invoke view_deck tool via agent
  - Assert formatted output matches expected format

- [ ] 7.3 Add integration test: remove card workflow
  - Add card to test deck
  - Invoke remove_card_from_deck tool
  - Verify card removed from database
  - Invoke view_deck to confirm removal

- [ ] 7.4 Add integration test: update quantity workflow
  - Add card with quantity 2 to test deck
  - Invoke update_card_quantity with quantity=4
  - Verify quantity updated in database
  - Invoke view_deck to confirm update

- [ ] 7.5 Add integration test: deck context persistence
  - Set active deck in context
  - Invoke multiple tools in sequence
  - Verify all tools use same active deck

- [ ] 7.6 Add integration test: edge case handling
  - Test empty deck view
  - Test no active deck errors
  - Test card not found errors
  - Test deck construction rule violations

## 8. Documentation and Cleanup

- [ ] 8.1 Update CLAUDE.md with deck tool usage examples
  - Add section on deck viewing and management
  - Document active deck context behavior
  - Add example tool calls

- [ ] 8.2 Run type checking and linting
  - `uv run mypy src/`
  - `uv run ruff check . --fix`
  - `uv run ruff format .`

- [ ] 8.3 Run all tests
  - `uv run pytest tests/unit/` (unit tests)
  - `uv run pytest tests/integration/` (integration tests)
  - Ensure all tests pass

- [ ] 8.4 Manual testing in Chainlit UI
  - Start Chainlit: `uv run chainlit run src/ui/app.py`
  - Create a deck (Story 4.2 prerequisite)
  - Test: "show my deck"
  - Test: "add 4 Lightning Bolt to my deck"
  - Test: "view my deck"
  - Test: "remove 2 Lightning Bolt"
  - Test: "change Lightning Bolt to 1 copy"
  - Verify formatted output is readable and correct

## 9. Final Checklist

- [ ] 9.1 All acceptance criteria from Story 4.4 satisfied
  - ✓ PydanticAI tool to display current deck contents with card counts
  - ✓ Tool formats deck list by card type (creatures, spells, lands)
  - ✓ Tool shows total deck size and card count summary
  - ✓ PydanticAI tool to remove cards or update quantities in deck
  - ✓ User can ask "show my deck" or "remove 2 Lightning Bolt from my deck"
  - ✓ Tool handles edge cases (removing more cards than present, empty deck)
  - ✓ Integration tests verify deck viewing and modification operations

- [ ] 9.2 All tasks in tasks.md marked complete
- [ ] 9.3 Code quality checks pass (mypy, ruff)
- [ ] 9.4 All tests pass (unit + integration)
- [ ] 9.5 Manual testing confirms expected behavior
- [ ] 9.6 Ready for code review and archive

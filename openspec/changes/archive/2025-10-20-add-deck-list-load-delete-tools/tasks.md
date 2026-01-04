# Implementation Tasks

## 1. Repository Layer Enhancements

- [ ] 1.1 Add `list_decks(format_filter: str | None = None)` method to `DeckRepository` in `src/data/repositories/deck.py`
- [ ] 1.2 Add `find_deck_by_name(name: str)` method to `DeckRepository` for case-insensitive partial name matching
- [ ] 1.3 Add unit tests for new repository methods in `tests/unit/data/repositories/test_deck_repository.py`
- [ ] 1.4 Add integration tests for new repository methods in `tests/integration/data/test_deck_repository_integration.py`

## 2. Agent Tools Implementation

- [ ] 2.1 Implement `list_decks(ctx: RunContext[AgentDependencies], format_filter: str | None = None)` tool in `src/agent/tools/deck_tools.py`
- [ ] 2.2 Implement `load_deck(ctx: RunContext[AgentDependencies], name: str | None = None, deck_id: str | None = None)` tool in `src/agent/tools/deck_tools.py`
- [ ] 2.3 Implement `delete_deck(ctx: RunContext[AgentDependencies], name: str | None = None, deck_id: str | None = None, confirmed: bool = False)` tool in `src/agent/tools/deck_tools.py`
- [ ] 2.4 Update active deck session management logic to support:
  - Setting active deck on load (update `ctx.deps.format_context['active_deck_id']`)
  - Clearing active deck on delete if deleted deck was active
  - Switching between decks seamlessly

## 3. Formatting Helpers

- [ ] 3.1 Add `format_deck_list(decks: list[Deck])` function in `src/ui/formatters.py` for list_decks output
- [ ] 3.2 Add `format_deck_summary(deck: Deck, card_count_mainboard: int, card_count_sideboard: int)` function in `src/ui/formatters.py` for load_deck output
- [ ] 3.3 Update existing formatting functions if needed to support new display patterns

## 4. Unit Tests

- [ ] 4.1 Write unit tests for `list_decks` tool in `tests/unit/agent/tools/test_deck_tools.py`:
  - Test successful list with multiple decks
  - Test empty deck list
  - Test format filtering
  - Test database error handling
- [ ] 4.2 Write unit tests for `load_deck` tool in `tests/unit/agent/tools/test_deck_tools.py`:
  - Test load by exact name
  - Test load by ID
  - Test load by partial name match
  - Test deck not found scenarios (name and ID)
  - Test active deck switching
  - Test database error handling
- [ ] 4.3 Write unit tests for `delete_deck` tool in `tests/unit/agent/tools/test_deck_tools.py`:
  - Test delete with confirmation (name and ID)
  - Test delete without confirmation (should fail)
  - Test deck not found
  - Test active deck clearing after deletion
  - Test database error handling

## 5. Integration Tests

- [ ] 5.1 Write integration test for complete list workflow in `tests/integration/agent/test_deck_tools_integration.py`:
  - Create multiple decks
  - List all decks and verify output
  - List with format filter
- [ ] 5.2 Write integration test for complete load workflow in `tests/integration/agent/test_deck_tools_integration.py`:
  - Create deck
  - Load deck by name
  - Verify active deck is set
  - Add card to loaded deck
  - Verify card is in correct deck
- [ ] 5.3 Write integration test for complete delete workflow in `tests/integration/agent/test_deck_tools_integration.py`:
  - Create deck
  - Delete without confirmation (should fail)
  - Delete with confirmation (should succeed)
  - Verify deck is gone from database
  - Verify active deck is cleared
- [ ] 5.4 Write integration test for deck switching workflow:
  - Create "Deck A" and "Deck B"
  - Set "Deck A" as active
  - Add card to "Deck A"
  - Load "Deck B" (switch active deck)
  - Add card to "Deck B"
  - Verify each deck has only its respective cards

## 6. Agent Registration

- [ ] 6.1 Ensure all three new tools are registered with the agent in `src/agent/core.py` via `@agent.tool` decorators

## 7. End-to-End Manual Testing

- [ ] 7.1 Manual test via Chainlit UI:
  - Create 2-3 decks with different names
  - Ask "show my decks" and verify list display
  - Ask "load my [deck name]" and verify deck summary
  - Add cards to loaded deck
  - Switch to different deck and verify context changes
  - Ask "delete [deck name]" and verify confirmation prompt
  - Confirm deletion and verify deck is gone
  - Verify error messages for non-existent decks

## 8. Type Safety and Code Quality

- [ ] 8.1 Run `uv run mypy src/` and fix any type errors
- [ ] 8.2 Run `uv run ruff check . --fix` and address linting issues
- [ ] 8.3 Run `uv run ruff format .` to ensure consistent formatting

## 9. Documentation

- [ ] 9.1 Update `CLAUDE.md` if new patterns or conventions are introduced
- [ ] 9.2 Add docstrings to all new repository methods and agent tools with clear parameter and return type documentation

## 10. Validation and Deployment

- [ ] 10.1 Run all tests: `uv run pytest`
- [ ] 10.2 Run coverage report: `uv run pytest --cov=src --cov-report=html` and verify coverage >70% for new code
- [ ] 10.3 Validate OpenSpec change: `openspec validate add-deck-list-load-delete-tools --strict`
- [ ] 10.4 Create git commit following project conventions

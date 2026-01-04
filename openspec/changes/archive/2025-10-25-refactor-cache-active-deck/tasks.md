# Implementation Tasks

## 1. Update AgentDependencies Structure
- [x] 1.1 Add `active_deck: Deck | None` field to `AgentDependencies` dataclass
- [x] 1.2 Remove `active_deck_id` property (replaced by `active_deck`)
- [x] 1.3 Update docstrings to reflect new caching behavior

## 2. Update Dependency Creation in UI Layer
- [x] 2.1 Modify `get_agent_dependencies()` to fetch active deck from repository
- [x] 2.2 Pass loaded `Deck` object to `AgentDependencies` constructor
- [x] 2.3 Handle case where deck ID exists but deck not found (defensive)
- [x] 2.4 Ensure transaction rollback behavior remains correct

## 3. Refactor Deck Tools
- [x] 3.1 Update `add_card_to_deck()` to use `deps.active_deck`
- [x] 3.2 Update `view_deck()` to use `deps.active_deck`
- [x] 3.3 Update `remove_card_from_deck()` to use `deps.active_deck`
- [x] 3.4 Update `update_card_quantity()` to use `deps.active_deck`
- [x] 3.5 Update `update_deck_strategy()` to use `deps.active_deck`
- [x] 3.6 Simplify error handling (single null check instead of two)
- [x] 3.7 Remove redundant `get_deck_with_cards()` calls

## 4. Update Tests
- [x] 4.1 Update unit tests to mock `active_deck` field instead of `active_deck_id`
- [x] 4.2 Update integration tests to verify deck caching behavior
- [x] 4.3 Add test for deck-not-found defensive case
- [x] 4.4 Verify all deck tool tests pass with new pattern

## 5. Validation
- [x] 5.1 Run full test suite (`uv run pytest`)
- [x] 5.2 Run type checker (`uv run mypy src/`)
- [x] 5.3 Run linter (`uv run ruff check .`)
- [x] 5.4 Manual smoke test: create deck, add cards, view deck

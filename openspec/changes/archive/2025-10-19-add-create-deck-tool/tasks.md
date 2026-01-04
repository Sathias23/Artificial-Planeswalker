# Implementation Tasks

## 1. Agent Dependencies Setup
- [ ] 1.1 Add `DeckRepository` import to `src/agent/dependencies.py`
- [ ] 1.2 Add `deck_repository: DeckRepository` field to `AgentDependencies` dataclass
- [ ] 1.3 Add `active_deck_id: str | None` field to `AgentDependencies` dataclass
- [ ] 1.4 Add session manager methods to `ConversationSessionManager` in `src/agent/core.py`:
  - [ ] `get_active_deck_id(session_id: str) -> str | None`
  - [ ] `set_active_deck_id(session_id: str, deck_id: str) -> None`
  - [ ] `clear_active_deck_id(session_id: str) -> None`
- [ ] 1.5 Add `_active_deck_ids: dict[str, str]` storage to `ConversationSessionManager.__init__()`
- [ ] 1.6 Update `ConversationSessionManager.clear_session()` to clear active deck ID
- [ ] 1.7 Update `get_agent_dependencies()` in `src/ui/app.py` to:
  - [ ] Import and create `DeckRepository` instance
  - [ ] Retrieve `active_deck_id` from `_session_manager.get_active_deck_id(session_id)`
  - [ ] Pass both to `AgentDependencies` constructor

## 2. Create Deck Tool Implementation
- [ ] 2.1 Create `src/agent/tools/deck_tools.py` module
- [ ] 2.2 Import `_session_manager` from `src.agent.core`
- [ ] 2.3 Implement `create_deck` tool function (NOT decorated yet - decorator applied in core.py)
- [ ] 2.4 Add tool parameters: `ctx: RunContext[AgentDependencies]`, `name: str`, `format: str = "standard"`
- [ ] 2.5 Extract `deps` and `session_id` from `ctx.deps`
- [ ] 2.6 Call `deps.deck_repository.create_deck()` with validated parameters
- [ ] 2.7 Store returned deck ID using `_session_manager.set_active_deck_id(ctx.deps.session_id, deck.id)`
- [ ] 2.8 Return user-friendly confirmation message with deck name and ID
- [ ] 2.9 Handle duplicate name scenario (allow duplicates - deck IDs are unique)
- [ ] 2.10 Add error handling for database failures (catch exceptions, return error message)
- [ ] 2.11 Add proper type hints and docstring

## 3. Tool Registration
- [ ] 3.1 Import `create_deck` from `src.agent.tools.deck_tools` in `src/agent/core.py`
- [ ] 3.2 Register tool in `create_agent()` function using `agent.tool(create_deck)`
- [ ] 3.3 Verify tool appears in agent's tool list (manual test or debug output)

## 4. Unit Tests
- [ ] 4.1 Create `tests/unit/agent/test_deck_tools.py`
- [ ] 4.2 Mock `_session_manager` and `DeckRepository` for unit tests
- [ ] 4.3 Test successful deck creation with default format
  - [ ] Verify `deck_repository.create_deck()` called with correct params
  - [ ] Verify `_session_manager.set_active_deck_id()` called with deck ID
  - [ ] Verify confirmation message returned
- [ ] 4.4 Test deck creation with explicit format parameter
- [ ] 4.5 Test duplicate name handling (verify duplicates are allowed)
- [ ] 4.6 Test database error handling (mock repository raises exception)
  - [ ] Verify error message returned
  - [ ] Verify `_session_manager.set_active_deck_id()` NOT called
- [ ] 4.7 Verify all tests pass with `uv run pytest tests/unit/agent/test_deck_tools.py`

## 5. Integration Tests
- [ ] 5.1 Create `tests/integration/agent/test_deck_creation.py`
- [ ] 5.2 Set up test with in-memory database and real session manager
- [ ] 5.3 Test end-to-end deck creation through agent with natural language input
  - [ ] Verify deck persisted to test database
  - [ ] Verify `active_deck_id` stored in session manager
- [ ] 5.4 Test multiple decks can be created in same session
  - [ ] Verify active deck ID updates to most recent deck
  - [ ] Verify all decks retrievable from database
- [ ] 5.5 Test active deck persists across conversation turns
  - [ ] Create deck in first message
  - [ ] Verify `deps.active_deck_id` populated in second message
- [ ] 5.6 Test deck creation with various natural language phrasings
- [ ] 5.7 Verify all integration tests pass with `uv run pytest tests/integration/agent/`

## 6. Type Safety & Code Quality
- [ ] 6.1 Run `uv run mypy src/agent/tools/deck_tools.py` - must pass strict mode
- [ ] 6.2 Run `uv run ruff check src/agent/tools/deck_tools.py --fix` - no violations
- [ ] 6.3 Run `uv run ruff format src/agent/tools/deck_tools.py`
- [ ] 6.4 Verify pre-commit hooks pass

## 7. Manual Testing
- [ ] 7.1 Start Chainlit UI: `uv run chainlit run src/ui/app.py`
- [ ] 7.2 Test: "create a new deck called Test Deck" - verify confirmation message
- [ ] 7.3 Test: "create deck named Mono Red Aggro" - verify deck created
- [ ] 7.4 Test: "make a new standard deck called Control" - verify format defaults to standard
- [ ] 7.5 Verify deck visible in database: `sqlite3 data/cards.db "SELECT * FROM decks;"`
- [ ] 7.6 Test duplicate names allowed (create two decks with same name)
- [ ] 7.7 Test active deck persists: create deck, then ask unrelated question, verify deck still active (future tools will need this)

## 8. Documentation
- [ ] 8.1 Add comprehensive docstring to `create_deck` tool explaining:
  - [ ] Parameters (name, format)
  - [ ] Behavior (creates deck, sets as active)
  - [ ] Return value (confirmation message)
  - [ ] Example usage
- [ ] 8.2 Add docstrings to new `ConversationSessionManager` methods
- [ ] 8.3 Update `AgentDependencies` docstring to document `active_deck_id` field
- [ ] 8.4 Update `CLAUDE.md` to document active deck session management pattern
- [ ] 8.5 Ensure all type hints are complete and self-documenting

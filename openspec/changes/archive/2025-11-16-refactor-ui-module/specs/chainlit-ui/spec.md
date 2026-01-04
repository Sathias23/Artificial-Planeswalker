# chainlit-ui Specification Delta

## MODIFIED Requirements

### Requirement: UI Module Structure and Organization
The system SHALL organize the UI layer into focused modules with clear separation of concerns to improve maintainability and testability.

#### Scenario: Modular directory structure exists
- **WHEN** the `src/ui/` directory is examined
- **THEN** a `handlers/` subdirectory exists for message orchestration
- **AND** an `actions/` subdirectory exists for Chainlit action callbacks
- **AND** a `components/` subdirectory exists for UI component logic
- **AND** the main `app.py` file serves as a thin entry point

#### Scenario: Entry point delegates to handlers
- **WHEN** the `src/ui/app.py` file is examined
- **THEN** the file contains Chainlit lifecycle hooks only
- **AND** the `@cl.on_message` decorator delegates to `message_handler.handle_user_message()`
- **AND** the `@cl.on_chat_start` decorator delegates to `welcome.show_welcome_message()`
- **AND** the file is no more than 250 lines

#### Scenario: No single function exceeds complexity threshold
- **WHEN** all functions in the UI module are examined
- **THEN** no single function exceeds 150 lines of code
- **AND** functions with complexity >150 lines are decomposed into focused helpers

---

### Requirement: Message Handler Orchestration
The system SHALL implement message handling as an orchestration layer that coordinates agent execution, result processing, and UI updates.

#### Scenario: Message handler module exists
- **WHEN** the `src/ui/handlers/` directory is examined
- **THEN** a `message_handler.py` module exists
- **AND** the module exports `async def handle_user_message(message, agent, session_id)`
- **AND** the function orchestrates the complete message handling workflow

#### Scenario: Message handling workflow
- **WHEN** `handle_user_message()` is invoked with a user message
- **THEN** a thinking message is displayed to the user
- **AND** the agent is executed with session context via `run_agent_with_session()`
- **AND** tool calls are extracted and converted to Chainlit Steps
- **AND** the agent response is sent to the chat
- **AND** signal detection logic identifies special return values from tools
- **AND** detected signals are delegated to appropriate signal handlers
- **AND** the sidebar is updated if `deps.sidebar_needs_update` is True
- **AND** errors are caught and displayed as user-friendly messages

#### Scenario: Agent layer independence preserved
- **WHEN** the message handler module is examined
- **THEN** it imports agent core functions (`run_agent_with_session`)
- **AND** it imports Chainlit for UI operations
- **AND** the agent layer does NOT import Chainlit (one-way dependency)
- **AND** the handler acts as adapter between agent and UI concerns

---

### Requirement: Signal Detection and Action Creation
The system SHALL implement signal handlers that detect agent tool return signals and create corresponding Chainlit action button UIs.

#### Scenario: Signal handlers module exists
- **WHEN** the `src/ui/handlers/` directory is examined
- **THEN** a `signal_handlers.py` module exists
- **AND** the module exports handler functions for each signal type
- **AND** handler functions are prefixed with `handle_` (e.g., `handle_pagination_signal`)

#### Scenario: Confirmation signal handler
- **WHEN** a tool returns `{"needs_confirmation": True, "deck_id": "...", "deck_name": "..."}` signal
- **AND** `handle_confirmation_signal(signal)` is invoked
- **THEN** a confirmation message is created with deck deletion warning
- **AND** two action buttons are attached: "Confirm Delete" and "Cancel"
- **AND** the action buttons have callbacks `confirm_delete_deck` and `cancel_delete_deck`
- **AND** the confirmation message is stored for later removal

#### Scenario: Pagination signal handler
- **WHEN** a tool returns `{"has_pagination": True, "page": 2, "total_pages": 5}` signal
- **AND** `handle_pagination_signal(signal)` is invoked
- **THEN** pagination action buttons are created (Previous/Next)
- **AND** buttons are enabled/disabled based on current page boundaries
- **AND** the pagination message is stored for later removal

#### Scenario: Synergy signal handler
- **WHEN** a tool returns `{"has_synergies": True, "synergy_cards": [card1, card2, ...]}` signal
- **AND** `handle_synergy_signal(signal)` is invoked
- **THEN** quick-add action buttons are created (maximum 7 cards)
- **AND** each button is labeled "Add {card_name}"
- **AND** each button has callback `add_suggested_card` with card data payload
- **AND** the synergy message is stored for later removal

#### Scenario: Deck list signal handler
- **WHEN** a tool returns `{"has_decks": True, "decks": [...]}` signal
- **AND** `handle_deck_list_signal(signal)` is invoked
- **THEN** quick-load action buttons are created (maximum 7 decks)
- **AND** each button is labeled with deck name and format
- **AND** each button has callback `quick_load_deck` with deck ID payload
- **AND** the deck list message is stored for later removal

#### Scenario: Disambiguation signal handler
- **WHEN** a tool returns `{"needs_disambiguation": True, "cards": [...], "context": "..."}` signal
- **AND** `handle_disambiguation_signal(signal)` is invoked
- **THEN** card selection action buttons are created
- **AND** each button shows card name and disambiguation context
- **AND** each button has callback `select_card` with card data payload
- **AND** the disambiguation message is stored for later removal

---

### Requirement: Action Callback Module Organization
The system SHALL organize Chainlit action callbacks into focused modules grouped by feature domain (filters, deck operations, card operations, pagination).

#### Scenario: Filter actions module
- **WHEN** the `src/ui/actions/` directory is examined
- **THEN** a `filter_actions.py` module exists
- **AND** the module contains `@cl.action_callback("set_format_filter")` decorator
- **AND** the module contains `@cl.action_callback("set_games_filter")` decorator
- **AND** callback functions update agent dependencies and display confirmation messages

#### Scenario: Deck actions module
- **WHEN** the `src/ui/actions/` directory is examined
- **THEN** a `deck_actions.py` module exists
- **AND** the module contains `@cl.action_callback("confirm_delete_deck")` decorator
- **AND** the module contains `@cl.action_callback("cancel_delete_deck")` decorator
- **AND** the module contains `@cl.action_callback("quick_load_deck")` decorator
- **AND** callback functions interact with agent tools and update UI state

#### Scenario: Card actions module
- **WHEN** the `src/ui/actions/` directory is examined
- **THEN** a `card_actions.py` module exists
- **AND** the module contains `@cl.action_callback("add_suggested_card")` decorator
- **AND** the module contains `@cl.action_callback("select_card")` decorator
- **AND** callback functions add cards to decks or resolve disambiguation

#### Scenario: Pagination actions module
- **WHEN** the `src/ui/actions/` directory is examined
- **THEN** a `pagination_actions.py` module exists
- **AND** the module contains `@cl.action_callback("navigate_page")` decorator
- **AND** the callback function retrieves stored pagination context and re-executes search

#### Scenario: Action callbacks are discoverable
- **WHEN** Chainlit loads the application
- **THEN** all `@cl.action_callback` decorated functions are registered
- **AND** callbacks work identically regardless of which module they're defined in
- **AND** Chainlit routes action button clicks to correct callback functions

---

### Requirement: Deck Sidebar Component
The system SHALL implement deck sidebar functionality as a reusable component with clear separation between data fetching, calculation, and formatting logic.

#### Scenario: Sidebar component module exists
- **WHEN** the `src/ui/components/` directory is examined
- **THEN** a `sidebar.py` module exists
- **AND** the module exports `async def update_deck_sidebar(session_id)`
- **AND** the module contains helper functions for data processing and formatting

#### Scenario: Sidebar component decomposition
- **WHEN** the `sidebar.py` module is examined
- **THEN** an `async def _fetch_deck_data(session_id)` helper exists for database queries
- **AND** a `def _calculate_color_identity(cards)` helper exists for color computation
- **AND** a `def _group_cards_by_type(cards)` helper exists for card grouping
- **AND** a `def _format_sidebar_markdown(deck, cards, colors)` helper exists for UI generation
- **AND** the main `update_deck_sidebar()` function orchestrates these helpers

#### Scenario: Sidebar update workflow
- **WHEN** `update_deck_sidebar(session_id)` is invoked
- **THEN** deck data and cards are fetched from the database
- **AND** color identity is calculated from the card list
- **AND** cards are grouped by type (Creatures, Spells, Lands)
- **AND** deck info and card list markdown are generated
- **AND** Chainlit sidebar elements are created with unique timestamps
- **AND** existing sidebar elements are cleared before new ones are sent

#### Scenario: Sidebar component testability
- **WHEN** unit tests are written for sidebar functionality
- **THEN** `_calculate_color_identity()` can be tested with mock card data
- **AND** `_group_cards_by_type()` can be tested with mock card data
- **AND** `_format_sidebar_markdown()` can be tested with mock deck/card/color data
- **AND** helper functions are pure (no side effects) and independently testable

---

### Requirement: Welcome Screen Component
The system SHALL implement welcome screen functionality as a focused component responsible for initial user onboarding and filter UI setup.

#### Scenario: Welcome component module exists
- **WHEN** the `src/ui/components/` directory is examined
- **THEN** a `welcome.py` module exists
- **AND** the module exports `async def show_welcome_message()`
- **AND** the module exports `async def initialize_filter_actions()`

#### Scenario: Welcome message display
- **WHEN** `show_welcome_message()` is invoked during chat start
- **THEN** a welcome message is displayed introducing the assistant
- **AND** the message includes quick-start tips and capabilities overview
- **AND** the message has appropriate Magic: The Gathering themed styling

#### Scenario: Filter initialization
- **WHEN** `initialize_filter_actions()` is invoked during chat start
- **THEN** format filter action buttons are created and sent
- **AND** games filter action buttons are created and sent
- **AND** filter actions are available immediately for user interaction

---

### Requirement: Backward Compatibility and Migration Safety
The system SHALL ensure that refactoring preserves all existing functionality and behavior without breaking changes.

#### Scenario: Existing tests pass after refactoring
- **WHEN** the UI module refactoring is complete
- **THEN** all existing integration tests pass without modification
- **AND** all existing agent tests pass (agent-UI contract unchanged)
- **AND** manual testing confirms identical user-facing behavior

#### Scenario: No breaking changes to agent contract
- **WHEN** the refactored UI layer is examined
- **THEN** it uses the same agent functions (`run_agent_with_session`, `create_agent`)
- **AND** it uses the same `AgentDependencies` structure
- **AND** agent tools return signals in the same format
- **AND** the agent layer has zero awareness of UI refactoring

#### Scenario: Phased migration reduces risk
- **WHEN** each refactoring phase is completed
- **THEN** the application remains functional and deployable
- **AND** partial progress provides value even if later phases are deferred
- **AND** rollback is possible at phase boundaries

---

## ADDED Requirements

### Requirement: UI Module Size Constraints
The system SHALL enforce size constraints on UI module files to prevent monolithic file growth and maintain code navigability.

#### Scenario: Entry point file size limit
- **WHEN** the `src/ui/app.py` file is examined
- **THEN** the file contains no more than 250 lines of code
- **AND** the file contains only initialization and lifecycle hook registration
- **AND** substantive logic is delegated to handler and component modules

#### Scenario: Handler module size limits
- **WHEN** handler modules in `src/ui/handlers/` are examined
- **THEN** no single handler module exceeds 300 lines of code
- **AND** handler functions focus on orchestration, not implementation details
- **AND** complex logic is extracted to helper functions or component modules

#### Scenario: Component module size limits
- **WHEN** component modules in `src/ui/components/` are examined
- **THEN** no single component module exceeds 300 lines of code
- **AND** components are decomposed into pipeline stages (fetch → calculate → format)
- **AND** pure functions are extracted for testability

---

### Requirement: UI Module Import Discipline
The system SHALL maintain clear import boundaries to preserve layered architecture and enable future UI framework replacement.

#### Scenario: Entry point imports
- **WHEN** the `src/ui/app.py` file imports are examined
- **THEN** it imports Chainlit (`chainlit as cl`)
- **AND** it imports handler modules (`from src.ui.handlers import ...`)
- **AND** it imports component modules (`from src.ui.components import ...`)
- **AND** it imports agent core (`from src.agent import create_agent`)
- **AND** it does NOT import database repositories directly

#### Scenario: Handler imports
- **WHEN** handler module imports are examined
- **THEN** handlers import Chainlit for UI operations
- **AND** handlers import agent core for orchestration
- **AND** handlers import component modules for UI building blocks
- **AND** handlers do NOT import database repositories (use AgentDependencies)

#### Scenario: Component imports
- **WHEN** component module imports are examined
- **THEN** components import Chainlit for UI element creation
- **AND** components import formatters and utilities
- **AND** components import data layer types (Card, Deck schemas)
- **AND** components avoid importing agent core (UI-focused)

#### Scenario: Action callback imports
- **WHEN** action module imports are examined
- **THEN** actions import Chainlit for session access
- **AND** actions import agent core for tool invocation
- **AND** actions import component modules for UI updates
- **AND** actions follow same import discipline as handlers

---

### Requirement: UI Module Testing Strategy
The system SHALL enable comprehensive testing of UI layer components through clear separation of concerns and testable interfaces.

#### Scenario: Signal handler unit tests
- **WHEN** signal handlers are tested in isolation
- **THEN** tests can pass mock signal dictionaries to handler functions
- **AND** tests can verify correct Chainlit actions are created
- **AND** tests do NOT require full application initialization
- **AND** tests mock Chainlit message sending for fast execution

#### Scenario: Component unit tests
- **WHEN** component helper functions are tested
- **THEN** pure functions (calculate, group, format) can be tested with mock data
- **AND** tests verify correct transformations without I/O
- **AND** tests run in <10ms per test (no database, no async overhead for pure functions)

#### Scenario: Integration tests remain stable
- **WHEN** existing integration tests are executed against refactored code
- **THEN** tests interact with the UI layer through the same entry points
- **AND** tests verify end-to-end workflows (message → agent → UI update)
- **AND** refactoring does NOT require test rewrite (behavior unchanged)

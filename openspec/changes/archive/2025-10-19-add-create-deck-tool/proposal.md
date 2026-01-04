# Change Proposal: Add Create Deck Tool

## Why

Users need the ability to create new decks through natural language conversation in the Chainlit chat interface. This implements Story 4.2 from the PRD and builds on the existing deck database models (Story 4.1) to enable the first step of the deck building workflow.

## What Changes

- Add `create_deck` tool to PydanticAI agent for natural language deck creation
- Tool accepts deck name and optional format parameter (defaults to "standard")
- Extend `AgentDependencies` with `deck_repository` and `active_deck_id` fields
- Extend `ConversationSessionManager` with active deck ID storage methods
- Store newly created deck as "active deck" via session manager for subsequent operations
- Handle duplicate deck name scenarios gracefully (allow duplicates - IDs are unique)
- Return confirmation message with deck ID and name
- Add unit and integration tests for deck creation through agent

## Impact

- **Affected specs**: `agent-tools` (new tool and requirements)
- **Affected code**:
  - `src/agent/tools/deck_tools.py` - new file with `create_deck` tool
  - `src/agent/dependencies.py` - add `deck_repository` and `active_deck_id` fields
  - `src/agent/core.py` - add active deck methods to `ConversationSessionManager`
  - `src/ui/app.py` - update `get_agent_dependencies()` to create `DeckRepository` and retrieve active deck
  - `tests/unit/agent/test_deck_tools.py` - new test file
  - `tests/integration/agent/test_deck_creation.py` - new integration test
- **Dependencies**: Requires deck models and `DeckRepository` from Story 4.1 (already implemented)
- **User-facing**: Enables users to say "create a new deck called Mono Red Aggro" and receive confirmation

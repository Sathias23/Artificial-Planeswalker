# agent-core Spec Delta

## ADDED Requirements

### Requirement: Active Deck Context Injection

The system SHALL inject active deck information into the conversation history as a system message on every agent run when a deck is active, ensuring the agent maintains awareness of deck state regardless of conversation history length.

#### Scenario: Inject deck context when active deck exists
- **GIVEN** a user has an active deck "Fire Lord Zuko Deck" with 5 cards
- **WHEN** `run_agent_with_session` is called with `deps.active_deck` populated
- **THEN** the agent history SHALL include a system message with active deck context
- **AND** the message SHALL contain deck name, ID (first 8 chars), format, and card count
- **AND** the message SHALL instruct agent to add cards to THIS deck by default
- **AND** the context SHALL be prepended to the most recent system message OR added as new system message

#### Scenario: No context injection when no active deck
- **GIVEN** a user has no active deck
- **WHEN** `run_agent_with_session` is called with `deps.active_deck=None`
- **THEN** no deck context SHALL be injected into history
- **AND** the agent runs with standard system prompt only
- **AND** no additional tokens are consumed for deck context

#### Scenario: Context injection preserves deck state across large conversations
- **GIVEN** a user created deck "Test Deck" in message 1
- **AND** messages 2-10 contained large search results (100+ cards, 20K tokens)
- **WHEN** message 11 requests "add Lightning Bolt"
- **THEN** the system message SHALL include "ACTIVE DECK: Test Deck"
- **AND** the agent SHALL recognize the active deck from system context
- **AND** the agent SHALL NOT create a new deck
- **AND** the agent SHALL call `add_card_to_deck` on the existing deck

#### Scenario: Context message format is concise and high-signal
- **GIVEN** an active deck "Mono Red Aggro" with 15 cards in Standard format
- **WHEN** deck context message is built
- **THEN** the message SHALL include exactly: deck name, deck ID (8 chars), format, card count
- **AND** the message SHALL include explicit instruction to add cards to THIS deck
- **AND** the message SHALL be no more than 200 tokens
- **AND** the message SHALL use clear, unambiguous language

#### Scenario: Context injection works with empty conversation history
- **GIVEN** a user starts a new message with an active deck
- **AND** the conversation history is empty (first message)
- **WHEN** `run_agent_with_session` is called
- **THEN** a new system message SHALL be created with deck context
- **AND** the message SHALL be inserted at the start of history
- **AND** subsequent messages append after this system message

#### Scenario: Context injection prepends to existing system message
- **GIVEN** conversation history has an existing system message at index 0
- **AND** a user has an active deck
- **WHEN** `run_agent_with_session` is called
- **THEN** deck context SHALL be prepended to the existing system message content
- **AND** the format SHALL be "{deck_context}\n\n{original_system_message}"
- **AND** no duplicate system messages are created

### Requirement: Tool-First Deck Operation System Prompt

The system SHALL include explicit instructions in the agent system prompt mandating tool-first behavior for deck operations, preventing premature agent decisions about deck state.

#### Scenario: System prompt includes tool-first deck rules
- **GIVEN** the agent is initialized via `create_agent()`
- **WHEN** the agent system prompt is constructed
- **THEN** the prompt SHALL include a "DECK OPERATION RULES" section
- **AND** the rules SHALL mandate calling `add_card_to_deck` before `create_deck`
- **AND** the rules SHALL instruct agent to trust tool errors over assumptions
- **AND** the rules SHALL specify agent should only create deck if tool says "No active deck"

#### Scenario: Agent follows tool-first approach when adding cards
- **GIVEN** a user with active deck says "add Lightning Bolt"
- **WHEN** the agent processes the request
- **THEN** the agent SHALL call `add_card_to_deck` tool first
- **AND** the agent SHALL NOT call `create_deck` if `add_card_to_deck` succeeds
- **AND** the agent SHALL NOT make assumptions about deck existence without calling tools

#### Scenario: Agent creates deck only after tool confirmation
- **GIVEN** a user with NO active deck says "add Lightning Bolt"
- **WHEN** the agent processes the request
- **THEN** the agent SHALL call `add_card_to_deck` first
- **AND** the tool SHALL return "No active deck. Create a deck first..."
- **AND** ONLY THEN SHALL the agent suggest or create a new deck
- **AND** the agent SHALL explain why deck creation is needed

#### Scenario: Agent explicitly creates deck when user requests it
- **GIVEN** a user says "create a new deck called Control Deck"
- **WHEN** the agent processes the request
- **THEN** the agent SHALL call `create_deck` tool directly
- **AND** the agent SHALL NOT call `add_card_to_deck` first
- **AND** explicit deck creation requests bypass tool-first validation

#### Scenario: Tool-first rules prevent duplicate deck creation
- **GIVEN** a user with active deck "Deck A"
- **AND** the agent has lost deck context in conversation history
- **WHEN** user says "add Boros Charm"
- **THEN** the agent SHALL call `add_card_to_deck` (per tool-first rules)
- **AND** the tool SHALL succeed using active deck from dependencies
- **AND** the agent SHALL NOT create "Deck B" despite lack of context awareness
- **AND** the tool enforces correct behavior even if agent is confused

## MODIFIED Requirements

### Requirement: Agent Helper with Session Support

The system SHALL provide `run_agent_with_session` function that manages conversation history AND injects active deck context when present, ensuring consistent agent awareness of deck state.

#### Scenario: Run agent with session includes deck context injection
- **GIVEN** a session with active deck and conversation history
- **WHEN** `run_agent_with_session(user_input, session_id, deps, agent)` is called
- **THEN** the function SHALL retrieve conversation history from session manager
- **AND** IF `deps.active_deck` exists, function SHALL inject deck context into history
- **AND** the function SHALL run the agent with enhanced history
- **AND** the function SHALL update history with new messages after agent completes
- **AND** deck context injection SHALL occur BEFORE agent runs, not after

#### Scenario: Session helper logs deck context injection
- **GIVEN** a session with active deck
- **WHEN** `run_agent_with_session` injects deck context
- **THEN** the function SHALL log at INFO level: "Injected deck context for session={session_id}, deck={deck_name}"
- **AND** the log SHALL include deck ID (first 8 chars) for debugging
- **AND** the log SHALL NOT include full conversation history (privacy)

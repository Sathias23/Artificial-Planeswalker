# agent-core Specification Deltas

## MODIFIED Requirements

### Requirement: Session-Aware Agent Dependencies

The system SHALL provide session-aware dependency injection that retrieves format filter from session storage and loads the active deck from the database once per request, caching it for all tools in the same agent run.

#### Scenario: Get dependencies with session context
- **WHEN** `get_agent_dependencies(session_id)` is called
- **THEN** the function retrieves the format filter from the session manager for that session ID
- **AND** the function retrieves the active deck ID from the session manager
- **AND** if an active deck ID exists, the function loads the full `Deck` object from the database with cards
- **AND** an `AgentDependencies` instance is created with the loaded deck cached in `active_deck` field
- **AND** if no deck is active or deck not found, `active_deck=None` is set
- **AND** the dependencies are yielded within a context manager

#### Scenario: Dependencies restore session state with cached deck
- **WHEN** a user creates a deck in message 1
- **AND** message 2 is processed for the same session
- **AND** `get_agent_dependencies(session_id)` is called
- **THEN** the `AgentDependencies` instance has `active_deck` set to the loaded `Deck` object
- **AND** agent tools can access the deck directly via `ctx.deps.active_deck`
- **AND** no additional database queries are needed to fetch deck data

#### Scenario: Different sessions get different cached decks
- **WHEN** `get_agent_dependencies(session_a)` is called with session A having deck "deck-123" active
- **AND** `get_agent_dependencies(session_b)` is called with session B having deck "deck-456" active
- **THEN** session A's dependencies have `active_deck` containing data for "deck-123"
- **AND** session B's dependencies have `active_deck` containing data for "deck-456"
- **AND** the dependencies are isolated and independent

#### Scenario: Cached deck provides immediate access to cards
- **GIVEN** a deck tool needs to check if a card exists in the active deck
- **WHEN** the tool accesses `ctx.deps.active_deck.deck_cards`
- **THEN** the card list is immediately available from the cached object
- **AND** no database query is executed
- **AND** the tool can iterate over cards without additional repository calls

#### Scenario: No active deck results in None cache
- **GIVEN** a session has no active deck set
- **WHEN** `get_agent_dependencies(session_id)` is called
- **THEN** `active_deck=None` is set in the dependencies
- **AND** no database query is executed to load a deck
- **AND** tools checking `deps.active_deck` receive `None`

#### Scenario: Defensive handling of missing deck
- **GIVEN** the session manager returns deck ID "deck-999"
- **AND** the deck repository returns `None` (deck was deleted)
- **WHEN** `get_agent_dependencies(session_id)` is called
- **THEN** `active_deck=None` is set in the dependencies
- **AND** a warning is logged about the missing deck
- **AND** no error is raised during dependency creation

#### Scenario: Single database query per request
- **GIVEN** an agent run invokes 3 deck tools in sequence
- **WHEN** dependencies are created once at the start of the request
- **THEN** the deck is loaded from database exactly once
- **AND** all 3 tools access the same cached `Deck` object
- **AND** no redundant database queries occur

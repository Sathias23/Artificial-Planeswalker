# agent-core Specification Delta

## MODIFIED Requirements

### Requirement: Session-Aware Agent Dependencies

The system SHALL provide session-aware dependency injection that retrieves both format filter and active deck ID from session storage in real-time using property accessors.

#### Scenario: Get dependencies with session context
- **WHEN** `get_agent_dependencies(session_id)` is called
- **THEN** the function retrieves the format filter from the session manager for that session ID
- **AND** an `AgentDependencies` instance is created with a reference to the session manager
- **AND** if no format filter exists for the session, `format_filter=None` is used
- **AND** the dependencies are yielded within a context manager

#### Scenario: Dependencies restore session state
- **WHEN** a user sets a format filter in message 1
- **AND** message 2 is processed for the same session
- **AND** `get_agent_dependencies(session_id)` is called
- **THEN** the `AgentDependencies` instance has `format_filter` set to the value from message 1
- **AND** agent tools can access the persisted filter via `ctx.deps.format_filter`

#### Scenario: Different sessions get different dependencies
- **WHEN** `get_agent_dependencies(session_a)` is called with session A having "standard" filter
- **AND** `get_agent_dependencies(session_b)` is called with session B having no filter
- **THEN** session A's dependencies have `format_filter="standard"`
- **AND** session B's dependencies have `format_filter=None`
- **AND** the dependencies are isolated and independent

#### Scenario: Active deck ID accessed as property
- **GIVEN** a tool sets the active deck ID via `_session_manager.set_active_deck_id(session_id, "deck-123")`
- **WHEN** another tool in the SAME agent run accesses `ctx.deps.active_deck_id`
- **THEN** the property SHALL read the current value from the session manager
- **AND** the returned value SHALL be "deck-123" (not stale)
- **AND** tools receive consistent state within a single agent run

#### Scenario: Active deck synchronization between tools
- **GIVEN** an agent run starts with no active deck (`deps.active_deck_id = None`)
- **WHEN** Tool 1 calls `_session_manager.set_active_deck_id(session_id, "deck-456")`
- **AND** Tool 2 immediately accesses `deps.active_deck_id` in the same run
- **THEN** Tool 2 SHALL receive "deck-456"
- **AND** no stale data SHALL be present
- **AND** both tools see the same active deck ID

#### Scenario: Session manager reference enables real-time access
- **GIVEN** `AgentDependencies` is initialized with a session manager reference
- **WHEN** `deps.active_deck_id` property is accessed
- **THEN** the property SHALL call `_session_manager.get_active_deck_id(session_id)`
- **AND** return the current value from session storage
- **AND** provide no local caching of the value

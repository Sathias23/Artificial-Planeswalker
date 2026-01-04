# Agent Tools Spec Delta

## ADDED Requirements

### Requirement: Set Games Filter Tool

The agent SHALL provide a `set_games_filter()` tool to configure in-memory session games availability filtering.

#### Scenario: Set games filter for Arena

- **GIVEN** the agent is in a conversation session
- **WHEN** the user requests "set games filter to arena"
- **THEN** the `set_games_filter()` tool is called with games=["arena"]
- **AND** the session games_filter preference is set to ["arena"]
- **AND** subsequent card searches filter to Arena-available cards only

#### Scenario: Set games filter for multiple platforms

- **GIVEN** the agent is in a conversation session
- **WHEN** the user requests "show me cards for paper and arena"
- **THEN** the `set_games_filter()` tool is called with games=["paper", "arena"]
- **AND** the session games_filter preference is set to ["paper", "arena"]
- **AND** subsequent searches return cards available in paper OR arena

#### Scenario: Clear games filter

- **GIVEN** a games filter is currently set to ["arena"]
- **WHEN** the user requests "clear games filter"
- **THEN** the `set_games_filter()` tool is called with games=None
- **AND** the session games_filter preference is cleared
- **AND** subsequent searches return cards from all platforms

#### Scenario: Games filter persists across messages

- **GIVEN** games filter set to ["arena"] in message 1
- **WHEN** the user sends message 2 with a card search request
- **THEN** the games filter ["arena"] is still active
- **AND** the search automatically filters to Arena-available cards

#### Scenario: Invalid game value rejection

- **GIVEN** the user requests an invalid game platform
- **WHEN** `set_games_filter(games=["invalid_platform"])` is attempted
- **THEN** the tool returns an error message
- **AND** valid values are listed: "paper", "arena", "mtgo"
- **AND** the session games_filter remains unchanged

### Requirement: Games Filter in Session State

The AgentDependencies SHALL store games_filter as session state accessible to all agent tools.

#### Scenario: Games filter in dependencies

- **GIVEN** a conversation session with games filter set to ["arena"]
- **WHEN** an agent tool accesses `ctx.deps.games_filter`
- **THEN** the value ["arena"] is available
- **AND** the tool can use this filter in card queries

#### Scenario: Games filter defaults to None

- **GIVEN** a new conversation session with no games filter set
- **WHEN** an agent tool accesses `ctx.deps.games_filter`
- **THEN** the value is None
- **AND** no games filtering is applied by default

#### Scenario: Games filter serialization

- **GIVEN** a session with games_filter=["arena", "paper"]
- **WHEN** the session state is accessed
- **THEN** the games_filter is available in session preferences
- **AND** the filter persists for the lifetime of the session

## MODIFIED Requirements

### Requirement: Card Lookup by Name

The agent SHALL provide a `lookup_card_by_name()` tool that finds cards by exact name with optional format and games filtering.

#### Scenario: Lookup card with games filter active

- **GIVEN** session games_filter is set to ["arena"]
- **AND** a card "Cosmic Spider-Man" exists with games=["paper"]
- **WHEN** the user requests "lookup Cosmic Spider-Man"
- **THEN** the tool returns "Card not found" (filtered by games)
- **AND** an explanation mentions the active games filter

#### Scenario: Lookup card bypassing games filter

- **GIVEN** session games_filter is set to ["arena"]
- **AND** a card "Cosmic Spider-Man" exists with games=["paper"]
- **WHEN** `lookup_card_by_name("Cosmic Spider-Man", auto_filter=False)` is called
- **THEN** the card is found and returned
- **AND** the games filter is bypassed for this specific query

#### Scenario: Lookup card with no games filter

- **GIVEN** session games_filter is None
- **AND** a card "Lightning Bolt" exists with games=["paper", "arena", "mtgo"]
- **WHEN** the user requests "lookup Lightning Bolt"
- **THEN** the card is found and returned
- **AND** no games filtering is applied

#### Scenario: Lookup card show games availability

- **GIVEN** any card is found
- **WHEN** the card details are formatted for display
- **THEN** the card's games availability is shown (e.g., "Available in: Paper, Arena, MTGO")
- **AND** the user can see which platforms the card is playable on

### Requirement: Advanced Card Search with Multiple Filters

The agent SHALL provide a `search_cards_advanced()` tool that supports games filtering with auto-filter bypass capability.

#### Scenario: Search with active games filter

- **GIVEN** session games_filter is set to ["arena"]
- **WHEN** the user searches for "red creatures with haste"
- **THEN** the `search_cards_advanced()` tool uses games=["arena"] from session
- **AND** only Arena-available red creatures with haste are returned

#### Scenario: Search with explicit games parameter

- **GIVEN** session games_filter is None
- **WHEN** the user requests "show me paper-only red creatures"
- **THEN** the `search_cards_advanced()` tool is called with games=["paper"]
- **AND** only paper-available cards are returned

#### Scenario: Search bypassing games filter with auto_filter

- **GIVEN** session games_filter is set to ["arena"]
- **WHEN** the user explicitly requests "show me all cards, ignore filters"
- **THEN** `search_cards_advanced(auto_filter=False)` is called
- **AND** the games filter is bypassed
- **AND** cards from all platforms are returned

#### Scenario: Search results show games availability

- **GIVEN** any search returns results
- **WHEN** the results are formatted for display
- **THEN** each card shows its games availability
- **AND** the user can see which platforms each card is available on

#### Scenario: Search with both format and games filters

- **GIVEN** session format_filter is "standard" and games_filter is ["arena"]
- **WHEN** the user searches for "blue instants"
- **THEN** the tool applies BOTH filters
- **AND** only Standard-legal Arena-available blue instants are returned

### Requirement: Load Deck Tool

The agent SHALL provide a `load_deck()` tool that sets the active deck and auto-syncs the format filter to match the deck's format, without modifying the games filter.

#### Scenario: Load deck preserves games filter

- **GIVEN** session games_filter is set to ["arena"]
- **AND** a deck with format="standard" exists
- **WHEN** `load_deck()` is called to load the deck
- **THEN** the format_filter is set to "standard"
- **AND** the games_filter remains ["arena"]
- **AND** the games filter is NOT modified by loading a deck

#### Scenario: Load deck with no games filter set

- **GIVEN** session games_filter is None
- **AND** a deck exists
- **WHEN** `load_deck()` is called
- **THEN** the games_filter remains None
- **AND** no automatic games filter is applied based on deck format

## MODIFIED Requirements

### Requirement: Load Deck Tool

The agent SHALL provide a tool that loads a previously saved deck by name or ID, sets it as the active deck in the session, and automatically synchronizes the format filter to match the deck's format.

#### Scenario: Load deck by exact name match

- **GIVEN** a deck named "Mono Red Aggro" exists in the database
- **WHEN** the tool is invoked with name="Mono Red Aggro"
- **THEN** the deck SHALL be retrieved from the database
- **AND** the deck SHALL be set as the active deck in the session context
- **AND** a summary SHALL be returned containing:
  - Deck name
  - Format
  - Total mainboard card count
  - Total sideboard card count
  - Message confirming the deck is now active

#### Scenario: Load deck by ID

- **GIVEN** a deck exists with id="deck-abc-123"
- **WHEN** the tool is invoked with deck_id="deck-abc-123"
- **THEN** the deck SHALL be loaded and set as active
- **AND** a deck summary SHALL be returned

#### Scenario: Load deck with partial name match

- **GIVEN** a deck named "Mono Red Aggro" exists
- **WHEN** the tool is invoked with name="mono red"
- **THEN** the tool SHALL find the deck via case-insensitive partial match
- **AND** set it as the active deck

#### Scenario: Deck not found by name

- **GIVEN** no deck exists with name matching "Nonexistent Deck"
- **WHEN** the tool is invoked with name="Nonexistent Deck"
- **THEN** the tool SHALL return an error message indicating deck not found
- **AND** suggest listing decks to see available options
- **AND** the active deck SHALL NOT be changed

#### Scenario: Deck not found by ID

- **GIVEN** no deck exists with id="invalid-id"
- **WHEN** the tool is invoked with deck_id="invalid-id"
- **THEN** the tool SHALL return an error message indicating deck not found
- **AND** the active deck SHALL NOT be changed

#### Scenario: Natural language invocation

- **GIVEN** a user asks "load my Mono Red Aggro deck"
- **WHEN** the agent processes the query
- **THEN** the agent SHALL invoke the load_deck tool with name="Mono Red Aggro"
- **AND** return the deck summary to confirm loading

#### Scenario: Switch between decks

- **GIVEN** "Deck A" is currently the active deck
- **AND** "Deck B" exists in the database
- **WHEN** the tool is invoked to load "Deck B"
- **THEN** "Deck B" SHALL become the active deck
- **AND** subsequent deck operations (add card, view, etc.) SHALL operate on "Deck B"

#### Scenario: Database error during load operation

- **GIVEN** the database is unavailable
- **WHEN** the tool is invoked
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework

#### Scenario: Auto-set format filter for Standard deck

- **GIVEN** a deck with format="standard" exists
- **WHEN** the load_deck tool is invoked to load this deck
- **THEN** the session format filter SHALL be automatically set to "standard"
- **AND** subsequent card searches SHALL return only Standard-legal cards
- **AND** the user SHALL NOT need to manually invoke set_format_filter

#### Scenario: Auto-set format filter for Modern deck

- **GIVEN** a deck with format="modern" exists
- **WHEN** the load_deck tool is invoked to load this deck
- **THEN** the session format filter SHALL be automatically set to "modern"
- **AND** subsequent card searches SHALL return only Modern-legal cards

#### Scenario: Auto-clear format filter for "all formats" deck

- **GIVEN** a deck with format="all" or format=None exists
- **WHEN** the load_deck tool is invoked to load this deck
- **THEN** the session format filter SHALL be cleared (set to None)
- **AND** subsequent card searches SHALL return cards from all formats

#### Scenario: Format filter synchronization message

- **GIVEN** a Standard deck is loaded
- **WHEN** the load_deck tool completes
- **THEN** the tool's response MAY include a message indicating format filter was auto-set
- **AND** inform the user that searches are now filtered to Standard-legal cards

#### Scenario: Prevent non-Standard cards in search results

- **GIVEN** a user is building a Standard deck named "Sephiroth Sacrifice"
- **AND** the deck is loaded (format filter auto-set to "standard")
- **WHEN** the user searches for "creature with sacrifice"
- **THEN** the search results SHALL exclude token creatures
- **AND** SHALL exclude cards not legal in Standard format
- **AND** SHALL only return Standard-legal cards

### Requirement: Card Lookup by Name

The agent SHALL provide a card lookup tool that respects the session format filter by default, with an optional `auto_filter` parameter to temporarily bypass format filtering.

#### Scenario: Lookup with auto-filter enabled (default)

- **GIVEN** a Standard deck is loaded (format filter = "standard")
- **WHEN** the lookup_card_by_name tool is invoked with card_name="Lightning Bolt" (auto_filter defaults to True)
- **THEN** the tool SHALL use the session format filter
- **AND** return only Standard-legal versions of Lightning Bolt
- **AND** exclude non-Standard printings

#### Scenario: Lookup with auto-filter disabled

- **GIVEN** a Standard deck is loaded (format filter = "standard")
- **WHEN** the lookup_card_by_name tool is invoked with card_name="Lightning Bolt" and auto_filter=False
- **THEN** the tool SHALL bypass the session format filter
- **AND** return Lightning Bolt from any format
- **AND** search all cards in the database regardless of format legality

#### Scenario: Auto-filter with no active format filter

- **GIVEN** no format filter is set in the session
- **WHEN** the lookup_card_by_name tool is invoked with any auto_filter value
- **THEN** the tool SHALL search all cards in the database
- **AND** auto_filter parameter has no effect (no filter to bypass)

#### Scenario: Natural language auto-filter request

- **GIVEN** a Standard deck is loaded
- **AND** a user asks "show me Lightning Bolt from any format"
- **WHEN** the agent processes the query
- **THEN** the agent SHALL invoke lookup_card_by_name with auto_filter=False
- **AND** return results from all formats

### Requirement: Advanced Card Search with Multiple Filters

The agent SHALL provide an advanced card search tool that respects the session format filter by default, with an optional `auto_filter` parameter to temporarily bypass format filtering.

#### Scenario: Search with auto-filter enabled (default)

- **GIVEN** a Standard deck is loaded (format filter = "standard")
- **WHEN** the search_cards_advanced tool is invoked with filters (colors=["R"], types=["Creature"])
- **THEN** the tool SHALL use the session format filter
- **AND** return only Standard-legal red creatures
- **AND** exclude non-Standard cards from results

#### Scenario: Search with auto-filter disabled

- **GIVEN** a Standard deck is loaded (format filter = "standard")
- **WHEN** the search_cards_advanced tool is invoked with filters and auto_filter=False
- **THEN** the tool SHALL bypass the session format filter
- **AND** return cards from all formats matching the search criteria
- **AND** include non-Standard cards in results

#### Scenario: Auto-filter prevents token creatures

- **GIVEN** a Standard deck is loaded
- **WHEN** search_cards_advanced is invoked with keywords=["sacrifice"] and auto_filter=True
- **THEN** the results SHALL exclude token creatures (not Standard-legal)
- **AND** only include Standard-legal cards with sacrifice mechanics

#### Scenario: Bypass auto-filter to see token creatures

- **GIVEN** a Standard deck is loaded
- **WHEN** search_cards_advanced is invoked with keywords=["sacrifice"] and auto_filter=False
- **THEN** the results SHALL include token creatures
- **AND** include cards from all formats

#### Scenario: Natural language auto-filter bypass

- **GIVEN** a Standard deck is loaded
- **AND** a user asks "show me all red creatures with haste, including non-Standard"
- **WHEN** the agent processes the query
- **THEN** the agent SHALL invoke search_cards_advanced with auto_filter=False
- **AND** return results from all formats

#### Scenario: Auto-filter indicator in results

- **GIVEN** search results are returned
- **WHEN** auto_filter=True and format filter is active
- **THEN** the results SHALL indicate format filtering is active (e.g., "Showing Standard-legal cards only")
- **WHEN** auto_filter=False
- **THEN** the results SHALL NOT indicate format filtering
- **AND** MAY indicate "searching all formats"

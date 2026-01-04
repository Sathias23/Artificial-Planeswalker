# Chainlit UI Spec Delta

## MODIFIED Requirements

### Requirement: Deck Information Formatting
The system SHALL format deck information in the sidebar as clear, readable markdown text with all relevant deck attributes, including the optional strategy field.

#### Scenario: Sidebar shows all deck attributes
- **WHEN** the sidebar displays deck information
- **THEN** the sidebar shows deck name in bold markdown
- **AND** the sidebar shows deck ID on a separate line
- **AND** the sidebar shows format (or "All" if no format specified)
- **AND** if strategy is set, the sidebar shows "Strategy: {strategy}" on a separate line
- **AND** the sidebar shows color identity (or "Colorless" if no colors)
- **AND** the sidebar shows current card count with "X/60" format

#### Scenario: Sidebar displays deck with strategy
- **WHEN** the sidebar displays deck information for a deck with strategy="Fast aggro with burn spells"
- **THEN** the sidebar includes a line reading "Strategy: Fast aggro with burn spells"
- **AND** the strategy appears after the format and before the color identity

#### Scenario: Sidebar displays deck without strategy
- **WHEN** the sidebar displays deck information for a deck with strategy=NULL
- **THEN** the sidebar does NOT show a strategy line
- **AND** no blank "Strategy:" line appears
- **AND** the sidebar layout remains consistent with other fields

#### Scenario: Sidebar truncates long strategy text
- **WHEN** the sidebar displays a deck with strategy longer than 200 characters
- **THEN** the sidebar displays only the first 200 characters
- **AND** the truncated text ends with "..." to indicate truncation
- **AND** the full strategy is still stored in the database

#### Scenario: Sidebar handles empty color identity
- **WHEN** a deck has no color identity (colorless deck)
- **THEN** the sidebar displays "Colorless" for the colors field
- **AND** no blank lines or "None" values appear

#### Scenario: Sidebar handles "All" format
- **WHEN** a deck has format set to None or "all"
- **THEN** the sidebar displays "All" for the format field
- **AND** the format is shown consistently with other format values

### Requirement: Persistent Deck Information Sidebar
The system SHALL display active deck information in a persistent sidebar using Chainlit's ElementSidebar API, providing continuous visibility of deck context during deck building, including strategy information.

#### Scenario: Sidebar displays when deck is active
- **WHEN** a user has an active deck loaded in their session
- **AND** the user is viewing the chat interface
- **THEN** a sidebar appears on the side of the chat
- **AND** the sidebar title shows "🃏 Active Deck"
- **AND** the sidebar displays deck name, ID, format, strategy (if set), and colors
- **AND** the sidebar shows current mainboard card count

#### Scenario: Sidebar closes when no active deck
- **WHEN** a user has no active deck (new session or deleted deck)
- **AND** the chat interface loads
- **THEN** the sidebar does NOT appear
- **AND** the chat interface shows only the main conversation area

#### Scenario: Sidebar updates after deck creation
- **WHEN** a user creates a new deck via the `create_deck` tool with strategy
- **THEN** the sidebar appears immediately after creation
- **AND** the sidebar displays the newly created deck's information including strategy
- **AND** the sidebar shows 0 cards in mainboard initially

#### Scenario: Sidebar updates after loading deck
- **WHEN** a user loads an existing deck via the `load_deck` tool
- **THEN** the sidebar updates immediately after loading
- **AND** the sidebar displays the loaded deck's information including strategy (if set)
- **AND** the sidebar shows the current card count from the loaded deck

#### Scenario: Sidebar updates after adding cards
- **WHEN** a user adds cards to the active deck via `add_card_to_deck`
- **THEN** the sidebar card count updates to reflect the new total
- **AND** the sidebar updates without requiring a page refresh
- **AND** the update happens immediately after the tool completes

#### Scenario: Sidebar updates after strategy change
- **WHEN** a user updates the deck strategy via `update_deck_strategy` tool
- **THEN** the sidebar strategy field updates immediately
- **AND** the new strategy text appears in the sidebar
- **AND** the update happens without requiring a page refresh

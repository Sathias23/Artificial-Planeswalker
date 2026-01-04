# Chainlit UI Spec Delta

## ADDED Requirements

### Requirement: Session Filters Display in Sidebar

The Chainlit UI SHALL display both the active games filter and format filter in the sidebar above the active deck information.

#### Scenario: Display both filters in sidebar

- **GIVEN** the session format_filter is "standard" and games_filter is ["arena"]
- **WHEN** the sidebar is rendered
- **THEN** a "Filters" section is displayed above the deck information
- **AND** the section shows "Format: Standard"
- **AND** the section shows "Games: Arena"

#### Scenario: Display format filter only

- **GIVEN** the session format_filter is "standard" and games_filter is None
- **WHEN** the sidebar is rendered
- **THEN** the sidebar shows "Format: Standard"
- **AND** the sidebar shows "Games: All" or omits the games line

#### Scenario: Display games filter only

- **GIVEN** the session format_filter is None and games_filter is ["arena"]
- **WHEN** the sidebar is rendered
- **THEN** the sidebar shows "Format: All" or omits the format line
- **AND** the sidebar shows "Games: Arena"

#### Scenario: Display multiple games in filter

- **GIVEN** the session games_filter is set to ["paper", "arena"]
- **WHEN** the sidebar is rendered
- **THEN** the sidebar shows "Games: Paper, Arena"
- **AND** games are comma-separated and capitalized

#### Scenario: No filters shows "All" or omits section

- **GIVEN** the session format_filter is None and games_filter is None
- **WHEN** the sidebar is rendered
- **THEN** the sidebar shows "Format: All, Games: All"
- **OR** the filters section is omitted entirely

#### Scenario: Filters update in real-time

- **GIVEN** the games filter is changed from None to ["arena"]
- **OR** the format filter is changed from None to "standard"
- **WHEN** the `set_games_filter()` or `set_format_filter()` tool completes
- **THEN** the sidebar updates automatically
- **AND** the new filter values are displayed immediately

#### Scenario: Filters positioned above deck info

- **GIVEN** filters are active and an active deck exists
- **WHEN** the sidebar is rendered
- **THEN** the filters section appears first (top of sidebar)
- **AND** the active deck information appears below the filters section

### Requirement: Games Availability Display on Cards

The card formatters SHALL display game availability information on all card displays.

#### Scenario: Single card display shows games

- **GIVEN** a card with games=["paper", "arena"]
- **WHEN** the card is formatted for display (e.g., lookup result)
- **THEN** the card details include "Available in: Paper, Arena"
- **AND** the games are comma-separated and capitalized

#### Scenario: Card list shows games in table

- **GIVEN** multiple cards with various games values are displayed in a table
- **WHEN** the card list is formatted
- **THEN** each card row includes a "Games" column
- **AND** the column shows comma-separated game values (e.g., "Paper, Arena, MTGO")

#### Scenario: Card with all games shows "All Platforms"

- **GIVEN** a card with games=["paper", "arena", "mtgo"]
- **WHEN** the card is formatted for display
- **THEN** the games are shown as "Paper, Arena, MTGO"
- **OR** a shorthand "All Platforms" is displayed

#### Scenario: Card with single game

- **GIVEN** a card with games=["paper"]
- **WHEN** the card is formatted for display
- **THEN** "Available in: Paper" is shown
- **AND** the singular form is used

#### Scenario: Games display in card hover tooltips

- **GIVEN** card hover tooltips are enabled
- **WHEN** a user hovers over a card name
- **THEN** the tooltip shows the card image
- **AND** a text overlay or caption shows games availability (e.g., "Arena")

### Requirement: Sidebar Update Trigger for Games Filter

The UI layer SHALL update the sidebar when the games filter changes, using the same trigger mechanism as deck updates.

#### Scenario: Games filter change triggers sidebar update

- **GIVEN** the `set_games_filter()` tool is executed
- **WHEN** the tool sets `deps.sidebar_needs_update = True`
- **THEN** the UI layer checks the flag after tool execution
- **AND** `update_deck_sidebar(session_id)` is called
- **AND** the sidebar refreshes with the new games filter

#### Scenario: Sidebar shows both filters and deck

- **GIVEN** session has format_filter="standard", games_filter=["arena"], and an active deck
- **WHEN** the sidebar is rendered
- **THEN** the sidebar displays (in order from top):
  - **Filters Section:**
    - Format: Standard
    - Games: Arena
  - **Deck Section:**
    - Active Deck: [deck name and details]
    - Card list

## ADDED Requirements (Formatting)

### Requirement: Card Details Formatting with Games

The `format_card_details()` function SHALL include games availability information in the formatted output.

#### Scenario: Format card with games availability

- **GIVEN** a card with name="Lightning Bolt" and games=["paper", "arena", "mtgo"]
- **WHEN** `format_card_details(card)` is called
- **THEN** the output includes a "Games" field showing "Paper, Arena, MTGO"
- **AND** the games field appears after the card's other metadata (mana cost, type, etc.)

#### Scenario: Format card with limited games

- **GIVEN** a card with name="Cosmic Spider-Man" and games=["paper"]
- **WHEN** `format_card_details(card)` is called
- **THEN** the output includes "Games: Paper"
- **AND** a note may indicate the card is not available on digital platforms

### Requirement: Card List Formatting with Games

The `format_card_list()` function SHALL include a games availability column in the card table.

#### Scenario: Card table includes games column

- **GIVEN** multiple cards with various games values
- **WHEN** `format_card_list(cards)` is called
- **THEN** the output table has a "Games" column
- **AND** each row shows the card's games as comma-separated values

#### Scenario: Card table games column width

- **GIVEN** a card list is formatted as a markdown table
- **WHEN** the table is rendered in Chainlit
- **THEN** the games column has sufficient width to display "Paper, Arena, MTGO"
- **AND** long values do not cause layout issues

### Requirement: Deck Sidebar Card List with Games

The deck sidebar card list SHALL display games availability for each card in the active deck.

#### Scenario: Sidebar card list shows games

- **GIVEN** an active deck contains cards with various games values
- **WHEN** `update_deck_sidebar(session_id)` is called
- **THEN** the card list in the sidebar shows games for each card
- **AND** the games are displayed inline or as an icon (e.g., "Lightning Bolt (Paper, Arena)")

#### Scenario: Sidebar highlights platform mismatches

- **GIVEN** the active games filter is ["arena"]
- **AND** the active deck contains a card with games=["paper"]
- **WHEN** the sidebar is rendered
- **THEN** the paper-only card is highlighted or marked (e.g., with a warning icon)
- **AND** the user is informed that this card is not available in the filtered platform

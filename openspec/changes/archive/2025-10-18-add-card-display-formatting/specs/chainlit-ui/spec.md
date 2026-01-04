## ADDED Requirements

### Requirement: Structured Card Data Display
The system SHALL format card data with clear structure separating name, cost, type, and oracle text on separate lines.

#### Scenario: Single card display formatting
- **WHEN** the agent returns a single card result
- **THEN** the UI displays the card name on the first line in bold markdown
- **AND** the mana cost appears on the second line with readable symbol notation
- **AND** the type line appears on a separate line
- **AND** the oracle text is formatted with proper line breaks
- **AND** all fields are visually separated for clarity

#### Scenario: Card with missing fields
- **WHEN** a card has optional fields missing (e.g., no mana cost for lands)
- **THEN** the UI gracefully handles missing data
- **AND** no blank lines or "None" values are displayed
- **AND** the formatting remains consistent

### Requirement: Mana Symbol Representation
The system SHALL represent mana symbols as readable text or unicode symbols for clear visual identification.

#### Scenario: Basic mana symbols
- **WHEN** a card has mana cost with basic colors
- **THEN** mana symbols are displayed as text notation (e.g., "{1}{R}{G}")
- **AND** symbols use standard Magic notation: {W}, {U}, {B}, {R}, {G}, {C}
- **AND** generic mana uses numbers: {1}, {2}, {3}, etc.

#### Scenario: Complex mana symbols
- **WHEN** a card has hybrid, Phyrexian, or snow mana costs
- **THEN** the UI displays these using appropriate text notation
- **AND** hybrid mana uses slash notation: {W/U}, {2/R}
- **AND** Phyrexian mana uses P notation: {W/P}, {U/P}
- **AND** snow mana uses {S} notation

### Requirement: Multiple Card Results Display
The system SHALL display multiple card results as a numbered or bulleted list with consistent formatting.

#### Scenario: List of 5-10 cards
- **WHEN** the agent returns 5-10 card results
- **THEN** the UI displays them as a numbered list
- **AND** each list item shows card name, mana cost, and type line
- **AND** the list uses consistent formatting for all entries
- **AND** all cards are visible without scrolling issues

#### Scenario: More than 10 cards returned
- **WHEN** the agent returns more than 10 card results
- **THEN** the UI displays the first 10 cards in the list
- **AND** a message appears indicating "...and X more results"
- **AND** the message suggests refining the search query

### Requirement: Chainlit Element Usage
The system SHALL use Chainlit message elements (cl.Text, cl.Message) for structured card information display.

#### Scenario: Single card with cl.Text element
- **WHEN** displaying a single card
- **THEN** the UI creates a cl.Text element with formatted card content
- **AND** the element display mode is set to "inline"
- **AND** the element is included in a cl.Message
- **AND** the message is sent to the user

#### Scenario: Multiple cards with message content
- **WHEN** displaying multiple cards
- **THEN** the UI formats the card list in the message content
- **AND** the message uses markdown for structure
- **AND** the message is sent without requiring separate elements for each card

### Requirement: Result Limiting and Pagination
The system SHALL limit long card lists to prevent chat overflow and maintain interface usability.

#### Scenario: Default result limit
- **WHEN** a card query returns results
- **THEN** the UI applies a default limit of 10 cards maximum
- **AND** results beyond the limit are not displayed
- **AND** a count of hidden results is shown ("...and 15 more")

#### Scenario: Configurable result limit
- **WHEN** the formatting function is called
- **THEN** the caller can specify a custom limit parameter
- **AND** the limit can be set between 1 and 15 cards
- **AND** limits exceeding 15 are capped at 15 to prevent overflow

### Requirement: Visual Card Type and Color Emphasis
The system SHALL highlight or emphasize card colors and types for visual clarity.

#### Scenario: Card type visual emphasis
- **WHEN** a card is displayed
- **THEN** the card type uses markdown emphasis (e.g., *Creature*, **Instant**)
- **AND** the type emphasis is consistent across all card displays
- **AND** the emphasis improves readability without excessive styling

#### Scenario: Color indication
- **WHEN** a card has color identity
- **THEN** the UI displays color names or symbols
- **AND** colors are shown in a standardized format (e.g., "Colors: Red, Green")
- **AND** colorless cards indicate "Colorless" clearly

### Requirement: Professional Formatting Validation
The system SHALL ensure card formatting is readable and professional through manual testing confirmation.

#### Scenario: Manual formatting review
- **WHEN** manual testing is performed
- **THEN** testers verify card information is easy to read at a glance
- **AND** testers confirm mana symbols are recognizable
- **AND** testers validate multi-card lists are scannable
- **AND** testers approve visual emphasis improves (not hinders) readability
- **AND** no formatting issues are present (overflow, wrapping, alignment)

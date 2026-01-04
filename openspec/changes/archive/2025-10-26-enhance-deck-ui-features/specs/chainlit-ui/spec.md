# chainlit-ui Delta

## ADDED Requirements

### Requirement: Configurable Card Hover Direction
The system SHALL allow users to configure the direction (left or right) in which card image hover previews appear, to accommodate different screen layouts and prevent UI overlap.

#### Scenario: Configure hover direction to right
- **GIVEN** the CARD_HOVER_DIRECTION environment variable is set to "right"
- **WHEN** a card name with hover preview is rendered
- **THEN** the hover preview appears on the right side of the card name
- **AND** the CSS class "card-hover-right" is applied to the span element

#### Scenario: Configure hover direction to left
- **GIVEN** the CARD_HOVER_DIRECTION environment variable is set to "left"
- **WHEN** a card name with hover preview is rendered
- **THEN** the hover preview appears on the left side of the card name
- **AND** the CSS class "card-hover-left" is applied to the span element

#### Scenario: Default hover direction
- **GIVEN** the CARD_HOVER_DIRECTION environment variable is not set
- **WHEN** a card name with hover preview is rendered
- **THEN** the hover preview defaults to appearing on the right side
- **AND** the CSS class "card-hover-right" is applied

#### Scenario: Invalid hover direction
- **GIVEN** the CARD_HOVER_DIRECTION environment variable is set to "invalid"
- **WHEN** a card name with hover preview is rendered
- **THEN** the hover preview defaults to appearing on the right side
- **AND** a warning is logged about invalid configuration

### Requirement: Sidebar Deck Panel Hover Position
The system SHALL ensure the sidebar deck panel card hovers always appear on the left side to prevent overlap with main content hover previews, regardless of the global hover direction setting.

#### Scenario: Sidebar overrides global hover direction
- **GIVEN** the CARD_HOVER_DIRECTION is set to "right"
- **AND** a deck is active and displayed in the sidebar
- **WHEN** a card name in the sidebar is rendered with hover preview
- **THEN** the hover preview appears on the left side
- **AND** the CSS class "card-hover-left" is applied
- **AND** the global hover direction setting is ignored for sidebar cards

#### Scenario: Sidebar hover prevents overlap
- **GIVEN** the sidebar is displaying a deck card list
- **AND** the main chat area is displaying cards with right-side hovers
- **WHEN** a user hovers over cards in both areas
- **THEN** sidebar hovers appear on the left
- **AND** main content hovers appear on the right (or configured direction)
- **AND** no visual overlap occurs between the two hover previews

## MODIFIED Requirements

### Requirement: Card Hover CSS Styling
The system SHALL provide CSS styles for card image hover previews that work across different screen sizes and contexts, with support for configurable positioning.

#### Scenario: Responsive hover preview styling
- **GIVEN** the card-preview.css file is loaded
- **THEN** it defines styles for card name hover elements
- **AND** it supports both left and right positioning via CSS classes
- **AND** hover tooltip dimensions are responsive (250px desktop, 175px tablet, 140px mobile)
- **AND** tooltips maintain MTG card aspect ratio (5:7)
- **AND** tooltips use absolute positioning relative to the card name span

#### Scenario: Right-side hover positioning
- **GIVEN** a card name has the "card-hover-right" CSS class
- **WHEN** the card is hovered
- **THEN** the tooltip appears to the right of the card name
- **AND** the tooltip is offset appropriately to prevent text overlap

#### Scenario: Left-side hover positioning
- **GIVEN** a card name has the "card-hover-left" CSS class
- **WHEN** the card is hovered
- **THEN** the tooltip appears to the left of the card name
- **AND** the tooltip is offset appropriately to prevent text overlap
- **AND** the tooltip is positioned to avoid clipping off the screen edge

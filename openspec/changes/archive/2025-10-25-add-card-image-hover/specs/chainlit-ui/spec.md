# chainlit-ui Delta Specification

## ADDED Requirements

### Requirement: Card Name Hover Preview
The system SHALL display card images as hover previews when users mouse over card names in chat messages.

#### Scenario: Hover shows card image
- **WHEN** a user hovers their mouse over a card name in a chat message
- **THEN** a tooltip appears showing the card's image from Scryfall CDN
- **AND** the tooltip is positioned near the card name
- **AND** the tooltip disappears when the mouse moves away
- **AND** the tooltip does not obstruct other content unnecessarily

#### Scenario: Card image URL available
- **WHEN** a card is displayed with a valid image_uris field
- **THEN** the card name is wrapped in an HTML span element
- **AND** the span element contains a data-image-url attribute with the Scryfall CDN URL
- **AND** the span element has a CSS class for hover styling

#### Scenario: Card image URL unavailable
- **WHEN** a card is displayed without a valid image_uris field
- **THEN** the card name is displayed as plain text
- **AND** no hover preview is available
- **AND** no error is raised or logged

### Requirement: Card Hover CSS Styling
The system SHALL provide CSS styles for card image hover previews that work across different screen sizes and contexts.

#### Scenario: Hover tooltip styling
- **WHEN** the card-preview.css file is loaded
- **THEN** it defines styles for card name hover elements
- **AND** it defines styles for tooltip container positioning
- **AND** it defines styles for card image display (size, border, shadow)
- **AND** it includes responsive positioning to prevent screen overflow

#### Scenario: CSS file configuration
- **WHEN** the Chainlit configuration is examined
- **THEN** the custom_css setting includes "public/card-preview.css"
- **AND** the CSS file is served from the public directory
- **AND** the CSS is applied to all chat messages

### Requirement: Card Hover Feature Toggle
The system SHALL allow the card image hover feature to be disabled via environment variable.

#### Scenario: Feature enabled by default
- **WHEN** the CARD_IMAGE_HOVER_ENABLED environment variable is not set
- **THEN** card names are wrapped with hover functionality
- **AND** card image previews appear on hover

#### Scenario: Feature explicitly disabled
- **WHEN** the CARD_IMAGE_HOVER_ENABLED environment variable is set to "false"
- **THEN** card names are displayed as plain text
- **AND** no hover HTML wrapper is applied
- **AND** no card image previews appear

#### Scenario: Environment variable documented
- **WHEN** the .env.example file is examined
- **THEN** it includes CARD_IMAGE_HOVER_ENABLED with description
- **AND** it documents the default value (true)
- **AND** it explains acceptable values (true/false)

### Requirement: Card Hover in All Display Contexts
The system SHALL apply card image hover functionality consistently across all card display contexts.

#### Scenario: Hover in card lookup results
- **WHEN** a user performs a card lookup and receives results
- **THEN** the card name in the result has hover preview enabled
- **AND** hovering displays the card image

#### Scenario: Hover in card search results
- **WHEN** a user performs a card search and receives multiple results
- **THEN** each card name in the results list has hover preview enabled
- **AND** hovering any card name displays its corresponding image

#### Scenario: Hover in deck view output
- **WHEN** a user views a deck with the view_deck tool
- **THEN** each card name in the deck list has hover preview enabled
- **AND** hovering any card name displays its corresponding image

#### Scenario: Hover in sidebar deck display
- **WHEN** a deck is active and displayed in the sidebar
- **THEN** each card name in the sidebar list has hover preview enabled
- **AND** hovering any card name displays its corresponding image

### Requirement: Card Hover Image Size Selection
The system SHALL use the appropriate Scryfall image size for hover previews to balance quality and loading speed.

#### Scenario: Prefer normal size image
- **WHEN** a card has multiple image sizes in image_uris
- **THEN** the formatter extracts the "normal" size image URL
- **AND** uses it as the hover preview source

#### Scenario: Fallback to available size
- **WHEN** a card does not have "normal" size image
- **THEN** the formatter tries other available sizes in order: "large", "small", "png"
- **AND** uses the first available size as the hover preview source

#### Scenario: No image URL available
- **WHEN** a card has an empty or null image_uris field
- **THEN** no hover wrapper is applied
- **AND** the card name displays as plain text

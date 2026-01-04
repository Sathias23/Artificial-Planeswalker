## ADDED Requirements

### Requirement: Card Image Display
The system SHALL display Scryfall card images inline within chat messages when card information is requested and image URIs are available.

#### Scenario: Display card with image
- **WHEN** a user requests card information for a card with image_uris populated
- **AND** the agent retrieves the card data
- **THEN** the response includes both formatted text details and the card image
- **AND** the image is displayed inline within the chat message
- **AND** the image uses the "normal" size variant from image_uris

#### Scenario: Display card without image fallback
- **WHEN** a user requests card information for a card without image_uris (e.g., old data or double-faced card)
- **AND** the agent retrieves the card data
- **THEN** the response includes formatted text details only
- **AND** no error or missing image indicator is shown
- **AND** the conversation continues normally

#### Scenario: Image element creation
- **WHEN** the UI formatter creates a card message with image
- **THEN** a cl.Image element is created with url parameter pointing to Scryfall CDN
- **AND** the image element has display mode set to "inline"
- **AND** the image element name is set to the card name
- **AND** the image element is attached to the message via elements parameter

#### Scenario: Multiple card images in search results
- **WHEN** a user searches for multiple cards and results include 3+ cards with images
- **THEN** all card images are displayed inline in the response
- **AND** images are limited to the same result limit as text (10-15 cards max)
- **AND** the UI remains usable without excessive scrolling

### Requirement: Image Source Validation
The system SHALL only display card images from trusted Scryfall CDN sources to prevent security issues.

#### Scenario: Scryfall CDN URL validation
- **WHEN** the UI formatter prepares to display a card image
- **THEN** the image URL is verified to match Scryfall CDN pattern (cards.scryfall.io or c[0-9].scryfall.com)
- **AND** only HTTPS URLs are accepted
- **AND** malformed or non-Scryfall URLs result in text-only fallback

#### Scenario: Missing or invalid image URL handling
- **WHEN** image_uris exists but contains invalid URLs or is malformed
- **THEN** the formatter gracefully falls back to text-only display
- **AND** an error is logged for debugging purposes
- **AND** the user sees the card information without error messages

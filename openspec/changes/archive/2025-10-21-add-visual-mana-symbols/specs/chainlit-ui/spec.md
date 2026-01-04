## ADDED Requirements

### Requirement: Visual Mana Symbol Rendering

The UI SHALL render mana costs and symbols using Scryfall's SVG images instead of plain text notation, with graceful fallback to text when visual rendering is unavailable.

#### Scenario: Display mana cost with visual symbols in card details

- **GIVEN** a card with mana cost `{2}{R}{G}` is being displayed
- **WHEN** the card details are rendered via `format_card_details()`
- **AND** visual symbols are enabled
- **THEN** the mana cost SHALL be displayed as three inline images
- **AND** the first image SHALL display the {2} symbol from Scryfall CDN
- **AND** the second image SHALL display the {R} symbol (red mana)
- **AND** the third image SHALL display the {G} symbol (green mana)
- **AND** each image SHALL have alt text matching the symbol notation (e.g., alt="{R}")
- **AND** images SHALL be styled with class "mana-symbol" for consistent sizing

#### Scenario: Display mana cost with visual symbols in card lists

- **GIVEN** a card list contains cards with mana costs
- **WHEN** the card list is formatted via `format_card_list()`
- **AND** visual symbols are enabled
- **THEN** all mana costs SHALL render with visual SVG symbols
- **AND** symbols SHALL be inline with card names and text
- **AND** symbols SHALL maintain consistent height with surrounding text

#### Scenario: Display mana symbols in deck lists

- **GIVEN** a deck contains cards with mana costs
- **WHEN** the deck is displayed via `format_deck_for_display()`
- **AND** visual symbols are enabled
- **THEN** all card mana costs SHALL render with visual symbols
- **AND** symbols SHALL be grouped and aligned correctly in deck list entries

#### Scenario: Fallback to text when visual symbols disabled

- **GIVEN** visual symbols are disabled via configuration
- **WHEN** any card with mana cost is displayed
- **THEN** the mana cost SHALL render as plain text notation (e.g., "{2}{R}{G}")
- **AND** text SHALL be properly escaped to prevent HTML injection

#### Scenario: Fallback to text when symbol not found

- **GIVEN** a card has an unrecognized symbol in mana cost
- **WHEN** the symbol is not in Scryfall's symbology cache
- **THEN** the system SHALL log a warning
- **AND** the unrecognized symbol SHALL render as text
- **AND** other recognized symbols SHALL still render visually

#### Scenario: Handle hybrid mana symbols

- **GIVEN** a card with hybrid mana cost `{W/U}` (white/blue)
- **WHEN** the mana cost is rendered visually
- **THEN** the hybrid symbol SHALL display as a single image
- **AND** the image SHALL show Scryfall's hybrid mana symbol
- **AND** alt text SHALL be "{W/U}"

#### Scenario: Handle Phyrexian mana symbols

- **GIVEN** a card with Phyrexian mana cost `{W/P}` (white/Phyrexian)
- **WHEN** the mana cost is rendered visually
- **THEN** the Phyrexian symbol SHALL display as a single image
- **AND** the image SHALL show Scryfall's Phyrexian mana symbol
- **AND** alt text SHALL be "{W/P}"

#### Scenario: Handle special symbols (tap, untap, snow)

- **GIVEN** a card with oracle text containing special symbols like {T} (tap) or {Q} (untap)
- **WHEN** the oracle text is rendered
- **THEN** special symbols SHALL render as visual images
- **AND** images SHALL use Scryfall's SVG for the symbol
- **AND** symbols SHALL be inline with surrounding text

#### Scenario: Handle colorless and generic mana

- **GIVEN** a card with mana cost `{5}{C}` (5 generic, 1 colorless)
- **WHEN** the mana cost is rendered visually
- **THEN** the {5} symbol SHALL display as Scryfall's generic mana 5 symbol
- **AND** the {C} symbol SHALL display as Scryfall's colorless mana symbol
- **AND** symbols SHALL be visually distinct from each other

### Requirement: Scryfall Symbology API Integration

The system SHALL integrate with Scryfall's Card Symbols API to fetch symbol metadata and SVG URIs, with in-memory caching for performance.

#### Scenario: Fetch all symbols on first use

- **GIVEN** the application starts with empty symbol cache
- **WHEN** the first card with mana symbols is displayed
- **THEN** the system SHALL make a single GET request to `https://api.scryfall.com/symbology`
- **AND** the response SHALL be parsed as JSON containing card symbol objects
- **AND** each symbol object SHALL be cached with keys: symbol, svg_uri, colors, english
- **AND** subsequent symbol lookups SHALL use the cache without API calls

#### Scenario: Cache lookup for symbol SVG URL

- **GIVEN** the symbol cache is populated with Scryfall symbols
- **WHEN** a formatter requests the SVG URL for "{R}"
- **THEN** the system SHALL return `https://svgs.scryfall.io/card-symbols/R.svg` from cache
- **AND** no API call SHALL be made

#### Scenario: Handle API timeout gracefully

- **GIVEN** the Scryfall API is slow or unresponsive
- **WHEN** fetching symbology data times out after 5 seconds
- **THEN** the system SHALL log an error message
- **AND** SHALL fall back to text notation for all symbols
- **AND** the application SHALL continue functioning normally

#### Scenario: Handle API error response

- **GIVEN** the Scryfall API returns a 5xx error
- **WHEN** attempting to fetch symbology data
- **THEN** the system SHALL log the error with details
- **AND** SHALL fall back to text notation for all symbols
- **AND** SHALL retry on the next application restart (no persistent failure state)

#### Scenario: Populate cache with symbol metadata

- **GIVEN** a successful API response from `/symbology`
- **WHEN** parsing the response data
- **THEN** the cache SHALL store each symbol with structure:
  ```python
  {
    "symbol": "{R}",
    "svg_uri": "https://svgs.scryfall.io/card-symbols/R.svg",
    "colors": ["R"],
    "english": "one red mana",
    "mana_value": 1.0
  }
  ```
- **AND** cache SHALL be indexed by symbol string for O(1) lookup

### Requirement: Symbol Rendering Configuration

The system SHALL provide configuration to toggle between visual and text symbol rendering for accessibility and debugging purposes.

#### Scenario: Enable visual symbols by default

- **GIVEN** no explicit configuration is set
- **WHEN** the application initializes
- **THEN** visual symbols SHALL be enabled by default
- **AND** all mana symbols SHALL render as images

#### Scenario: Disable visual symbols via environment variable

- **GIVEN** the environment variable `VISUAL_MANA_SYMBOLS=false` is set
- **WHEN** any formatter renders mana symbols
- **THEN** all symbols SHALL render as plain text notation
- **AND** no API calls to Scryfall SHALL be made

#### Scenario: Disable visual symbols via Chainlit config

- **GIVEN** the Chainlit config file has `features.visual_symbols = false`
- **WHEN** any formatter renders mana symbols
- **THEN** all symbols SHALL render as plain text notation

### Requirement: Symbol Display Styling

The system SHALL provide CSS styling for mana symbols to ensure consistent sizing, alignment, and spacing across all UI contexts.

#### Scenario: Style symbols with consistent height

- **GIVEN** visual mana symbols are rendered in any context
- **WHEN** the HTML is styled with CSS
- **THEN** the `.mana-symbol` class SHALL set `height: 1em`
- **AND** symbols SHALL scale proportionally with surrounding text
- **AND** `width: auto` SHALL maintain aspect ratio

#### Scenario: Align symbols vertically with text

- **GIVEN** mana symbols are inline with card names or oracle text
- **WHEN** rendered in the UI
- **THEN** symbols SHALL have `vertical-align: middle` or `vertical-align: text-bottom`
- **AND** symbols SHALL not appear higher or lower than surrounding text baseline

#### Scenario: Space symbols appropriately

- **GIVEN** multiple mana symbols are adjacent (e.g., {2}{R}{G})
- **WHEN** rendered as images
- **THEN** each symbol SHALL have small horizontal margin (1-2px)
- **AND** symbols SHALL not overlap or appear cramped
- **AND** spacing SHALL be visually similar to official MTG card layouts

#### Scenario: Display symbols inline with content

- **GIVEN** mana symbols appear in card lists, details, or deck views
- **WHEN** rendered in markdown or HTML
- **THEN** symbols SHALL use `display: inline-block`
- **AND** symbols SHALL flow naturally within text lines
- **AND** line breaks SHALL occur at word boundaries, not mid-symbol

### Requirement: Accessibility and Fallback

The system SHALL ensure mana symbols are accessible to screen readers and provide robust fallback when visual rendering fails.

#### Scenario: Provide alt text for all symbol images

- **GIVEN** a mana symbol is rendered as an IMG tag
- **WHEN** the HTML is generated
- **THEN** the IMG tag SHALL include an `alt` attribute with the symbol notation
- **AND** alt text SHALL match the original notation (e.g., `alt="{R}"`)
- **AND** screen readers SHALL announce the symbol text

#### Scenario: Escape text fallback for HTML safety

- **GIVEN** visual symbols are disabled or unavailable
- **WHEN** mana cost is rendered as text
- **THEN** the text SHALL be HTML-escaped to prevent injection
- **AND** special characters like `<`, `>`, `&` SHALL be properly encoded

#### Scenario: Log symbol rendering failures

- **GIVEN** a symbol fails to render visually
- **WHEN** the error occurs
- **THEN** the system SHALL log a warning with details:
  - Symbol that failed
  - Reason (API error, not found, timeout, etc.)
  - Context (card name, mana cost)
- **AND** the log SHALL be at WARNING level (not ERROR)
- **AND** the failure SHALL not block other operations

#### Scenario: Maintain readability with text fallback

- **GIVEN** a card mana cost rendered as text due to fallback
- **WHEN** displayed in any UI context
- **THEN** the text notation SHALL remain readable and properly formatted
- **AND** curly braces SHALL be preserved (e.g., "{2}{R}{G}" not "2RG")
- **AND** text SHALL be distinguishable from card names or descriptions

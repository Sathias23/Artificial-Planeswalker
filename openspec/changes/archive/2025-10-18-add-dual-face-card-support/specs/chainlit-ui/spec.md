# chainlit-ui Spec Delta

## ADDED Requirements

### Requirement: Dual-Faced Card Detection

The formatter module SHALL provide a helper function to detect if a card has multiple faces.

#### Scenario: Detect dual-faced card

- **GIVEN** a Card with `card_faces` containing 2 face objects
- **WHEN** the dual-face detection logic is applied
- **THEN** the card is identified as dual-faced

#### Scenario: Detect single-faced card

- **GIVEN** a Card with `card_faces = None`
- **WHEN** the dual-face detection logic is applied
- **THEN** the card is identified as single-faced

### Requirement: Dual-Faced Card Detail Formatting

The `format_card_details()` function SHALL display both faces of dual-faced cards with clear separation and complete oracle text for each face.

#### Scenario: Format transform card details

- **GIVEN** a transform card like "Delver of Secrets // Insectile Aberration"
- **WHEN** `format_card_details(card)` is called
- **THEN** the output contains "**Front Face:**" and "**Back Face:**" labels
- **AND** both faces show their oracle text, mana cost, and type line
- **AND** shared data (colors, set info) appears once at the end

#### Scenario: Format modal DFC details

- **GIVEN** a modal DFC like "Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel"
- **WHEN** `format_card_details(card)` is called
- **THEN** the output contains "**Front Face:**" and "**Back Face:**" labels
- **AND** oracle text from `card_faces[0]["oracle_text"]` is displayed for front
- **AND** oracle text from `card_faces[1]["oracle_text"]` is displayed for back

#### Scenario: Format flip card details

- **GIVEN** a flip card with two vertical faces
- **WHEN** `format_card_details(card)` is called
- **THEN** both faces are displayed with appropriate labels
- **AND** each face shows its complete oracle text

#### Scenario: Format single-faced card (backward compatibility)

- **GIVEN** a normal single-faced card with `card_faces = None`
- **WHEN** `format_card_details(card)` is called
- **THEN** the output uses root-level `oracle_text`, `mana_cost`, `type_line`
- **AND** the output format is unchanged from previous behavior

### Requirement: Dual-Faced Card List Formatting

The `format_card_list()` function SHALL display dual-faced card names using both face names separated by " // ".

#### Scenario: Format list with dual-faced cards

- **GIVEN** a list containing both single-faced and dual-faced cards
- **WHEN** `format_card_list(cards)` is called
- **THEN** dual-faced cards show as "Front Name // Back Name"
- **AND** single-faced cards show as "Card Name" (unchanged)

#### Scenario: Truncate dual-faced card oracle text

- **GIVEN** a dual-faced card with long oracle text on both faces
- **WHEN** `format_card_list(cards, limit=10)` is called
- **THEN** the oracle text is truncated to 150 characters
- **AND** ellipsis "..." is appended if truncated

### Requirement: Dual-Faced Card Image Extraction

The `format_card_with_image()` function SHALL extract image URIs from `card_faces[0].image_uris` when root-level `image_uris` is None.

#### Scenario: Extract image from card_faces

- **GIVEN** a dual-faced card with `image_uris = None` at root level
- **AND** `card_faces[0]["image_uris"]["normal"]` contains a valid Scryfall CDN URL
- **WHEN** `format_card_with_image(card)` is called
- **THEN** a Chainlit Image element is created using the front face image URL
- **AND** the image display mode is "inline"

#### Scenario: Fallback when no images available

- **GIVEN** a dual-faced card with no `image_uris` at root or in `card_faces`
- **WHEN** `format_card_with_image(card)` is called
- **THEN** `(text, None)` is returned (text-only display)

#### Scenario: Single-faced card image (backward compatibility)

- **GIVEN** a single-faced card with `image_uris["normal"]` at root level
- **WHEN** `format_card_with_image(card)` is called
- **THEN** the image is extracted from root `image_uris["normal"]` (unchanged behavior)

### Requirement: Dual-Faced Card Test Coverage

All dual-faced card formatting logic SHALL have comprehensive unit tests with >80% code coverage.

#### Scenario: Test all card layouts

- **GIVEN** the formatter test suite
- **WHEN** tests are reviewed
- **THEN** tests exist for flip, transform, modal_dfc, and split card layouts
- **AND** all dual-face formatting paths are tested

#### Scenario: Test edge cases

- **GIVEN** the formatter test suite
- **WHEN** edge case tests are reviewed
- **THEN** tests cover: missing card_faces, empty card_faces array, missing image_uris in faces
- **AND** all edge cases pass without errors

## MODIFIED Requirements

### Requirement: Card Detail Formatting

The `format_card_details()` function SHALL format a single card with detailed information for display, with support for both single-faced and dual-faced cards.

Creates a structured display with:
- Bold card name on first line
- For dual-faced cards: "**Front Face:**" and "**Back Face:**" section labels
- For each face (or root for single-faced): Mana cost (if present), Type line with emphasis, Oracle text with proper formatting
- Color identity (once, for all faces)
- Set information (once, for all faces)

#### Scenario: Format single-faced card

- **GIVEN** a single-faced card like "Lightning Bolt"
- **WHEN** `format_card_details(card)` is called
- **THEN** the output contains bold card name, mana cost, type line, oracle text
- **AND** color and set information are displayed
- **AND** no face labels are shown

#### Scenario: Format dual-faced card

- **GIVEN** a dual-faced card with `card_faces` array containing 2 faces
- **WHEN** `format_card_details(card)` is called
- **THEN** the output contains "**Front Face:**" and "**Back Face:**" labels
- **AND** each face shows its oracle text from `card_faces[i]["oracle_text"]`
- **AND** shared data (colors, set) appears once after all faces

### Requirement: Card List Formatting

The `format_card_list()` function SHALL format a list of cards with consistent structure and truncation, supporting both single-faced and dual-faced cards.

Creates a numbered list showing:
- Card name (for dual-faced: "Front Name // Back Name")
- Mana cost
- Type line (for dual-faced: may show both type lines)
- Oracle text (truncated if long)

Limits results to prevent chat overflow and includes count of hidden cards.

#### Scenario: Format list with single-faced cards

- **GIVEN** a list of 3 single-faced cards
- **WHEN** `format_card_list(cards, limit=10)` is called
- **THEN** each card shows: number, bold name, mana cost, type line, oracle text
- **AND** oracle text is truncated to 150 characters if needed

#### Scenario: Format list with dual-faced cards

- **GIVEN** a list containing dual-faced cards
- **WHEN** `format_card_list(cards, limit=10)` is called
- **THEN** dual-faced cards show "Front Name // Back Name" format
- **AND** type line and oracle text are appropriately formatted

#### Scenario: Truncate list when exceeding limit

- **GIVEN** a list of 15 cards
- **WHEN** `format_card_list(cards, limit=10)` is called
- **THEN** only first 10 cards are shown
- **AND** message "...and 5 more results" appears
- **AND** suggestion to refine search is shown

### Requirement: Card Image Formatting

The `format_card_with_image()` function SHALL format a card with image element for Chainlit display, with support for extracting images from `card_faces` when needed.

Creates a formatted card display with an inline image element using Chainlit's Image API. For dual-faced cards, attempts to extract image from `card_faces[0].image_uris` when root `image_uris` is None.

Uses "normal" size image by default for best balance of quality and load time (~200-300KB). Images are fetched from Scryfall CDN.

#### Scenario: Format single-faced card with image

- **GIVEN** a single-faced card with `image_uris["normal"]` at root level
- **WHEN** `format_card_with_image(card)` is called
- **THEN** formatted text is returned with full card details
- **AND** Chainlit Image element is created with "normal" size URL
- **AND** image display mode is "inline"

#### Scenario: Format dual-faced card with image

- **GIVEN** a dual-faced card with `card_faces[0]["image_uris"]["normal"]` containing image URL
- **AND** root-level `image_uris = None`
- **WHEN** `format_card_with_image(card)` is called
- **THEN** formatted text shows both faces
- **AND** Chainlit Image element is created using front face image URL

#### Scenario: Format card without images

- **GIVEN** a card with no `image_uris` at root or in `card_faces`
- **WHEN** `format_card_with_image(card)` is called
- **THEN** `(text, None)` tuple is returned
- **AND** formatted text contains full card details

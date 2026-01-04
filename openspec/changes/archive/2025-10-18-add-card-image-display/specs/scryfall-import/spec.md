## MODIFIED Requirements

### Requirement: Card Data Transformation
The system SHALL transform Scryfall API card JSON into CardModel instances with all relevant fields including image URIs.

#### Scenario: Transform complete card with all fields
- **GIVEN** a complete Scryfall card JSON with all fields including image_uris
- **WHEN** transform_scryfall_card() is called
- **THEN** a CardModel instance is returned with all fields populated
- **AND** the image_uris field contains the dictionary with size-variant URLs
- **AND** no transformation errors occur

#### Scenario: Transform card with missing optional fields
- **GIVEN** a Scryfall card JSON with missing keywords, card_faces, and image_uris
- **WHEN** transform_scryfall_card() is called
- **THEN** a CardModel instance is returned with optional fields set to None
- **AND** required fields are still populated
- **AND** no transformation errors occur

#### Scenario: Transform multi-face card without top-level image_uris
- **GIVEN** a double-faced Scryfall card with image_uris only in card_faces array
- **WHEN** transform_scryfall_card() is called
- **THEN** a CardModel instance is returned
- **AND** the top-level image_uris field is None
- **AND** card_faces data is preserved (containing per-face image_uris)
- **AND** the card is stored successfully in the database

#### Scenario: Extract image URIs with all size variants
- **GIVEN** a Scryfall card JSON with complete image_uris object
- **WHEN** the transformer extracts the image_uris field
- **THEN** all size keys are preserved (small, normal, large, png, art_crop, border_crop)
- **AND** all URL values are preserved as strings
- **AND** the image_uris dictionary structure matches Scryfall format exactly

#### Scenario: Handle missing image_uris gracefully
- **GIVEN** a Scryfall card JSON without image_uris field
- **WHEN** transform_scryfall_card() attempts to extract image_uris
- **THEN** the image_uris field is set to None
- **AND** no KeyError or exception is raised
- **AND** the transformation completes successfully

## MODIFIED Requirements

### Requirement: SQLAlchemy Async ORM Models
The system SHALL provide SQLAlchemy 2.0 async ORM models for Scryfall card data with proper type hints, async attribute access support, and image URI storage.

#### Scenario: Card model creation with required fields
- **GIVEN** a Scryfall card JSON object with core fields (id, name, mana_cost, type_line, oracle_text)
- **WHEN** the CardModel is instantiated with these fields
- **THEN** the model instance is created successfully with all fields accessible
- **AND** the model supports async attribute access via AsyncAttrs mixin

#### Scenario: Card model with optional fields
- **GIVEN** a Scryfall card with optional fields (color_indicator, keywords, card_faces, image_uris)
- **WHEN** the CardModel is instantiated
- **THEN** optional fields are set to None when not provided
- **AND** optional fields accept their expected types when provided

#### Scenario: Multi-face card support
- **GIVEN** a double-faced card from Scryfall with card_faces array
- **WHEN** the CardModel stores the card_faces data in JSON column
- **THEN** the card_faces data is preserved with all face details
- **AND** the data can be retrieved as a Python list of dictionaries

#### Scenario: Image URIs storage
- **GIVEN** a Scryfall card with image_uris object containing image URLs
- **WHEN** the CardModel stores the image_uris in JSON column
- **THEN** the image_uris object is preserved with all size variants (small, normal, large, png, art_crop, border_crop)
- **AND** the data can be retrieved as a Python dictionary

#### Scenario: Card without image URIs
- **GIVEN** a Scryfall card without image_uris field (e.g., double-faced card)
- **WHEN** the CardModel is instantiated with image_uris=None
- **THEN** the model instance is created successfully
- **AND** the image_uris field is None

### Requirement: Pydantic Schema for Type-Safe Data Transfer
The system SHALL provide Pydantic schemas corresponding to SQLAlchemy models for type-safe data transfer between application layers, including image URI data.

#### Scenario: Convert SQLAlchemy model to Pydantic schema
- **GIVEN** a CardModel instance retrieved from the database with image_uris populated
- **WHEN** Card.model_validate() is called with the CardModel instance
- **THEN** a Card Pydantic schema is returned with all fields populated including image_uris
- **AND** the schema passes Pydantic validation

#### Scenario: Pydantic schema enforces type constraints
- **GIVEN** a Card Pydantic schema definition
- **WHEN** instantiating with invalid types (e.g., cmc as string instead of float)
- **THEN** Pydantic raises a ValidationError
- **AND** the error message indicates the field and expected type

#### Scenario: Pydantic schema handles optional fields
- **GIVEN** a Card schema with optional fields (keywords, card_faces, color_indicator, image_uris)
- **WHEN** instantiating without these fields
- **THEN** the schema instance is created with optional fields set to None
- **AND** no validation errors are raised

#### Scenario: Pydantic schema with image URIs
- **GIVEN** a Card Pydantic schema with image_uris field
- **WHEN** instantiating with image_uris dictionary containing valid URLs
- **THEN** the schema instance is created successfully
- **AND** the image_uris field contains the provided dictionary

### Requirement: Card Schema Field Mapping
The system SHALL map Scryfall card JSON fields to SQLAlchemy model columns with appropriate types and constraints, including image URI data.

#### Scenario: Core card fields mapping
- **GIVEN** Scryfall card JSON with id, name, mana_cost, cmc, type_line, oracle_text
- **WHEN** these fields are mapped to CardModel columns
- **THEN** id is stored as String (UUID) primary key
- **AND** name is stored as String with index and not-null constraint
- **AND** cmc is stored as Float
- **AND** type_line and oracle_text are stored as String

#### Scenario: Color fields mapping
- **GIVEN** Scryfall card with colors, color_identity, color_indicator arrays
- **WHEN** these fields are mapped to CardModel columns
- **THEN** colors is stored as JSON array
- **AND** color_identity is stored as JSON array
- **AND** color_indicator is stored as optional JSON array

#### Scenario: Legalities field mapping
- **GIVEN** Scryfall card with legalities object (Standard: legal, Modern: not_legal)
- **WHEN** the legalities field is mapped to CardModel column
- **THEN** legalities is stored as JSON object
- **AND** the JSON preserves format names as keys and legality status as values

#### Scenario: Keywords and set info mapping
- **GIVEN** Scryfall card with keywords array, set, collector_number, rarity
- **WHEN** these fields are mapped to CardModel columns
- **THEN** keywords is stored as JSON array
- **AND** set, collector_number, and rarity are stored as String columns

#### Scenario: Image URIs field mapping
- **GIVEN** Scryfall card with image_uris object containing size-variant URLs
- **WHEN** the image_uris field is mapped to CardModel column
- **THEN** image_uris is stored as optional JSON object
- **AND** the JSON preserves all size keys (small, normal, large, png, art_crop, border_crop) and URL values
- **AND** cards without image_uris store NULL in this column

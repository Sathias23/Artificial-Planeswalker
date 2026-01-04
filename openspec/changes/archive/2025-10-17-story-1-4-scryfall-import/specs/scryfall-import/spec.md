# Scryfall Import Capability

## ADDED Requirements

### Requirement: Bulk Data Endpoint Discovery
The import system SHALL fetch the Scryfall bulk data metadata endpoint to discover available bulk data files and their download URIs.

#### Scenario: Successful bulk data list retrieval
- **GIVEN** the Scryfall API is accessible
- **WHEN** the system requests `GET https://api.scryfall.com/bulk-data`
- **THEN** it SHALL return a JSON object with a `data` array
- **AND** each item SHALL contain `type`, `download_uri`, `updated_at`, and `size` fields

#### Scenario: Network error during metadata fetch
- **GIVEN** the Scryfall API is unreachable or returns an error
- **WHEN** the system attempts to fetch bulk data metadata
- **THEN** it SHALL retry up to 3 times with exponential backoff
- **AND** if all retries fail, it SHALL raise a clear error message

### Requirement: Bulk Data Type Selection
The import system SHALL support selecting between different Scryfall bulk data types (oracle-cards, default-cards, unique-artwork) with oracle-cards as the default.

#### Scenario: Default to oracle-cards bulk data
- **GIVEN** no bulk data type is specified by the user
- **WHEN** the import script is executed
- **THEN** it SHALL download the "oracle-cards" bulk data file

#### Scenario: User specifies alternative bulk data type
- **GIVEN** the user passes `--type default-cards` flag
- **WHEN** the import script is executed
- **THEN** it SHALL download the "default-cards" bulk data file

### Requirement: Streaming JSON Download
The import system SHALL download bulk data JSON files asynchronously with streaming to handle large files (155-486 MB) without memory overflow.

#### Scenario: Successful streaming download of large file
- **GIVEN** the download URI is valid
- **WHEN** the system downloads a 155 MB oracle-cards file
- **THEN** it SHALL stream the response body in chunks (not load entirely into memory)
- **AND** memory usage SHALL remain under 200 MB during download
- **AND** the downloaded file SHALL be saved to a local temporary path

#### Scenario: Download progress tracking
- **GIVEN** a bulk data file is being downloaded
- **WHEN** the download progresses
- **THEN** the system SHALL log download progress every 10 MB
- **AND** display total bytes downloaded and percentage complete

#### Scenario: Download interrupted mid-stream
- **GIVEN** a download is in progress
- **WHEN** a network error occurs mid-download
- **THEN** the system SHALL retry the download from the beginning
- **AND** log the retry attempt

### Requirement: Incremental JSON Parsing
The import system SHALL parse downloaded JSON files incrementally using a streaming parser (ijson) to process card objects one at a time without loading the entire file into memory.

#### Scenario: Stream-parse oracle-cards JSON array
- **GIVEN** a downloaded oracle-cards JSON file with 30,000+ card objects
- **WHEN** the parser reads the file
- **THEN** it SHALL iterate over the top-level array one card object at a time
- **AND** memory usage SHALL remain under 100 MB during parsing
- **AND** each card object SHALL be yielded as a Python dict

#### Scenario: Malformed JSON detection
- **GIVEN** the downloaded JSON file is corrupted or incomplete
- **WHEN** the parser attempts to read the file
- **THEN** it SHALL raise a `JSONDecodeError` with the file position
- **AND** log the error with context for debugging

### Requirement: Card Data Transformation
The import system SHALL transform Scryfall JSON card objects into SQLAlchemy CardModel instances, handling missing fields and data type conversions.

#### Scenario: Transform complete card object
- **GIVEN** a Scryfall card JSON object with all required fields
- **WHEN** the transformer processes the object
- **THEN** it SHALL return a valid CardModel instance
- **AND** all fields SHALL match the Scryfall schema (id, name, mana_cost, cmc, type_line, etc.)

#### Scenario: Handle missing optional fields
- **GIVEN** a Scryfall card with missing `keywords` field (null or absent)
- **WHEN** the transformer processes the object
- **THEN** it SHALL create a CardModel with `keywords=None`
- **AND** NOT raise a validation error

#### Scenario: Handle empty string mana costs
- **GIVEN** a Scryfall card with `mana_cost=""` (e.g., land cards)
- **WHEN** the transformer processes the object
- **THEN** it SHALL create a CardModel with `mana_cost=""`
- **AND** set `cmc=0.0`

#### Scenario: Transform multi-face cards
- **GIVEN** a double-faced card with `card_faces` array
- **WHEN** the transformer processes the object
- **THEN** it SHALL store the `card_faces` JSON array in the CardModel
- **AND** use the card's top-level `name`, `mana_cost`, `type_line` fields (not face-specific)

#### Scenario: Invalid card data rejection
- **GIVEN** a Scryfall card object missing required field `id`
- **WHEN** the transformer processes the object
- **THEN** it SHALL log a warning with the card name
- **AND** skip the card (not insert into database)
- **AND** increment error counter

### Requirement: Batch Insertion with Upserts
The import system SHALL insert cards into the database in batches of 1,000 rows using upsert logic (INSERT OR REPLACE) to handle duplicate primary keys.

#### Scenario: Successful batch insert of 1,000 cards
- **GIVEN** a batch of 1,000 valid CardModel instances
- **WHEN** the importer commits the batch
- **THEN** it SHALL execute a single bulk INSERT statement
- **AND** commit the transaction
- **AND** log "Inserted 1,000 cards"

#### Scenario: Upsert on duplicate primary key
- **GIVEN** a card with `id="abc123"` already exists in the database
- **WHEN** the importer inserts a card with the same `id`
- **THEN** it SHALL replace the existing row with the new data (ON CONFLICT DO UPDATE)
- **AND** NOT raise a duplicate key error

#### Scenario: Partial batch at end of import
- **GIVEN** 30,557 total cards (30 batches of 1,000 + 557 remaining)
- **WHEN** the importer processes the final 557 cards
- **THEN** it SHALL insert the partial batch
- **AND** commit successfully

### Requirement: Progress Logging and Statistics
The import system SHALL log progress during import and display summary statistics upon completion.

#### Scenario: Progress logging every 1,000 cards
- **GIVEN** an import is in progress
- **WHEN** 1,000 cards have been processed
- **THEN** the system SHALL log "Processed 1,000 cards (3.3% complete)"
- **AND** log elapsed time since import start

#### Scenario: Final summary statistics
- **GIVEN** an import has completed
- **WHEN** all cards have been processed
- **THEN** the system SHALL log total cards inserted, errors encountered, and total time
- **EXAMPLE**: "Import complete: 30,557 cards inserted, 3 errors, 45.2 seconds"

#### Scenario: Error statistics tracking
- **GIVEN** 5 cards fail validation during import
- **WHEN** the import completes
- **THEN** the summary SHALL report "5 errors"
- **AND** log details of each error to a file or stderr

### Requirement: CLI Script with UV
The import system SHALL provide a command-line script runnable via UV with options for bulk data type and database path.

#### Scenario: Run import with default options
- **GIVEN** the user runs `uv run scripts/import_scryfall_data.py`
- **WHEN** the script executes
- **THEN** it SHALL download oracle-cards bulk data
- **AND** import into the default database path (`data/cards.db`)
- **AND** exit with status code 0 on success

#### Scenario: Specify custom database path
- **GIVEN** the user runs `uv run scripts/import_scryfall_data.py --db-path /tmp/test.db`
- **WHEN** the script executes
- **THEN** it SHALL import cards into `/tmp/test.db`

#### Scenario: Specify alternative bulk data type
- **GIVEN** the user runs `uv run scripts/import_scryfall_data.py --type default-cards`
- **WHEN** the script executes
- **THEN** it SHALL download the "default-cards" bulk data file (~486 MB)

#### Scenario: Display help information
- **GIVEN** the user runs `uv run scripts/import_scryfall_data.py --help`
- **WHEN** the script executes
- **THEN** it SHALL display usage instructions, available options, and exit with status code 0

### Requirement: Error Handling and Recovery
The import system SHALL handle errors gracefully with clear error messages and enable recovery from partial imports.

#### Scenario: Database connection failure
- **GIVEN** the database path is invalid or inaccessible
- **WHEN** the import script attempts to connect
- **THEN** it SHALL log a clear error message
- **AND** exit with status code 1

#### Scenario: Disk space exhaustion during import
- **GIVEN** the disk runs out of space mid-import
- **WHEN** a database write fails with "disk full" error
- **THEN** the system SHALL rollback the current batch
- **AND** log the error with remaining disk space info
- **AND** exit gracefully with status code 1

#### Scenario: Resume import after interruption
- **GIVEN** a previous import was interrupted at card 15,000
- **WHEN** the user re-runs the import script
- **THEN** the upsert logic SHALL allow re-importing without manual cleanup
- **AND** existing cards SHALL be updated, new cards inserted

### Requirement: Memory Efficiency
The import system SHALL maintain memory usage under 200 MB during the entire import process, regardless of bulk data file size.

#### Scenario: Import 486 MB default-cards file
- **GIVEN** the user imports the large default-cards bulk data
- **WHEN** the import is in progress
- **THEN** memory usage SHALL remain under 200 MB
- **AND** NOT load the entire JSON file into memory at once

### Requirement: Import Performance
The import system SHALL complete an oracle-cards import (30,000+ cards) in under 2 minutes on typical hardware (SSD, 4+ core CPU).

#### Scenario: Oracle-cards import performance
- **GIVEN** a fresh database and oracle-cards bulk data
- **WHEN** the import script executes
- **THEN** it SHALL complete in under 120 seconds
- **AND** achieve throughput of at least 250 cards/second

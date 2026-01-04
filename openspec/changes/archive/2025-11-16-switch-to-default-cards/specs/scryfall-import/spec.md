# Scryfall Import Spec Deltas

## MODIFIED Requirements

### Requirement: Bulk Data Type Selection

The import system SHALL support selecting between different Scryfall bulk data types (oracle-cards, default-cards, unique-artwork) with **default-cards** as the default.

**Changed**: Default bulk data type from `oracle_cards` to `default_cards`

**Rationale**: `oracle_cards` excludes alternate printings with same Oracle ID (e.g., Universes Within sets like "Through the Omenpaths"). `default_cards` includes all printings, fixing missing OM1 cards bug while maintaining reasonable database size.

#### Scenario: Default to default-cards bulk data

- **GIVEN** no bulk data type is specified by the user
- **WHEN** the import script is executed via `uv run scripts/import_scryfall_data.py`
- **THEN** it SHALL download the "default-cards" bulk data file
- **AND** import approximately 60,000 cards (~200MB database)
- **AND** include all printings, including Universes Within variants (OM1, etc.)

#### Scenario: User specifies oracle-cards for smaller database

- **GIVEN** the user passes `--type oracle_cards` flag
- **WHEN** the import script is executed
- **THEN** it SHALL download the "oracle-cards" bulk data file
- **AND** import approximately 30,000 cards (~79MB database)
- **AND** exclude alternate printings with duplicate Oracle IDs
- **AND** warn user that some cards may be missing (e.g., OM1 Universes Within cards)

#### Scenario: User specifies unique-artwork for comprehensive database

- **GIVEN** the user passes `--type unique_artwork` flag
- **WHEN** the import script is executed
- **THEN** it SHALL download the "unique-artwork" bulk data file
- **AND** import approximately 123,000+ cards (~486MB database)
- **AND** include all artwork variants (promos, alternate frames, etc.)
- **AND** complete import in 15-20 minutes (longer due to larger dataset)

#### Scenario: Help text documents bulk data type trade-offs

- **GIVEN** the user runs `uv run scripts/import_scryfall_data.py --help`
- **WHEN** the help text is displayed
- **THEN** it SHALL clearly document all three bulk data type options
- **AND** explain default-cards is the default (~60k cards, 200MB, all printings)
- **AND** explain oracle-cards is smaller but may miss alternate printings (~30k cards, 79MB)
- **AND** explain unique-artwork is comprehensive but large (~123k cards, 486MB)

### Requirement: Import Performance

The import system SHALL complete a **default-cards** import (60,000+ cards) in under **10 minutes** on typical hardware (SSD, 4+ core CPU).

**Changed**: Performance target from 2 minutes (oracle-cards) to 10 minutes (default-cards)

**Rationale**: `default_cards` has ~2x more cards than `oracle_cards`, proportionally increasing import time while maintaining same throughput (cards/second).

#### Scenario: Default-cards import performance

- **GIVEN** a fresh database and default-cards bulk data (~60,000 cards)
- **WHEN** the import script executes via `uv run scripts/import_scryfall_data.py`
- **THEN** it SHALL complete in under 600 seconds (10 minutes)
- **AND** achieve throughput of at least 100 cards/second
- **AND** log progress every 1,000 cards processed
- **AND** display final summary with total time and throughput

#### Scenario: Oracle-cards import performance (legacy option)

- **GIVEN** a fresh database and oracle-cards bulk data (~30,000 cards)
- **WHEN** the import script executes via `uv run scripts/import_scryfall_data.py --type oracle_cards`
- **THEN** it SHALL complete in under 120 seconds (2 minutes)
- **AND** achieve throughput of at least 250 cards/second
- **AND** maintain legacy performance characteristics for users preferring smaller database

#### Scenario: Throughput consistency across bulk data types

- **GIVEN** import script runs with any bulk data type
- **WHEN** processing cards in batches of 1,000
- **THEN** throughput SHALL remain consistent at ~100-250 cards/second
- **AND** performance scaling is linear with card count (not exponential)
- **AND** memory usage remains under 200MB regardless of bulk data type

### Requirement: Memory Efficiency

The import system SHALL maintain memory usage under 200 MB during the entire import process, regardless of bulk data file size (including **default-cards** at 200MB and **unique-artwork** at 486MB).

**Changed**: Clarified that memory efficiency applies to all bulk data types, not just oracle-cards

**Rationale**: Streaming parser (ijson) and batch insertion ensure memory usage is independent of file size.

#### Scenario: Import 200 MB default-cards file

- **GIVEN** the user imports the default-cards bulk data (~200MB file)
- **WHEN** the import is in progress
- **THEN** memory usage SHALL remain under 200 MB
- **AND** NOT load the entire JSON file into memory at once
- **AND** use streaming parser (ijson) to process one card object at a time
- **AND** commit cards in batches of 1,000 rows

#### Scenario: Import 486 MB unique-artwork file

- **GIVEN** the user imports the large unique-artwork bulk data (~486MB file)
- **WHEN** the import is in progress
- **THEN** memory usage SHALL remain under 200 MB
- **AND** streaming parser handles file size efficiently
- **AND** memory usage is proportional to batch size (1,000 cards), not file size

## ADDED Requirements

### Requirement: Universes Within Card Support

The import system SHALL include all "Universes Within" alternate printings when using **default-cards** bulk data type, ensuring digital-only variants (e.g., OM1) are available for Arena/MTGO players.

**Added**: New requirement to explicitly support Universes Within sets and clarify Oracle ID handling.

**Context**: Wizards of the Coast creates "Universes Within" sets as mechanically-identical, digital-only versions of licensed IP sets (e.g., Marvel's Spider-Man → Through the Omenpaths). These cards share Oracle IDs with paper versions but have different names, art, and platform availability.

#### Scenario: Import OM1 (Through the Omenpaths) cards

- **GIVEN** user imports database with default-cards bulk data type
- **WHEN** import completes successfully
- **THEN** database SHALL contain all 188 "Through the Omenpaths" (OM1) cards
- **AND** OM1 cards have `games=["arena", "mtgo"]` (digital-only platforms)
- **AND** OM1 cards have same Oracle IDs as corresponding Marvel's Spider-Man (SPM) cards
- **AND** Both OM1 and SPM versions are present in database (not mutually exclusive)

#### Scenario: Search for OM1 card by name

- **GIVEN** database imported with default-cards bulk data type
- **WHEN** user searches for "Ultimate Green Goblin" (OM1 card)
- **THEN** `find_by_name_exact("Ultimate Green Goblin")` SHALL return the OM1 card
- **AND** card details include `set="om1"`, `games=["arena", "mtgo"]`
- **AND** card oracle text matches corresponding SPM card (mechanically identical)

#### Scenario: Platform filtering for Arena-only cards

- **GIVEN** database contains both OM1 (Arena/MTGO) and SPM (paper) versions
- **WHEN** user searches with `games=["arena"]` filter
- **THEN** results SHALL include OM1 cards (available on Arena)
- **AND** results SHALL exclude SPM cards (paper-only)
- **AND** search correctly respects `games` field from Scryfall data

#### Scenario: Oracle ID collision handling with default-cards

- **GIVEN** OM1 card "Ultimate Green Goblin" has Oracle ID `b5b43d01-fce6-4a00-9c19-7a7e2a09d833`
- **AND** SPM card "Green Goblin" has same Oracle ID
- **WHEN** import processes both cards
- **THEN** both cards SHALL be inserted into database (different primary keys: scryfall_id)
- **AND** queries by Oracle ID may return multiple results (expected behavior)
- **AND** queries by name return specific printing (e.g., OM1 vs SPM)

#### Scenario: Documentation clarifies Universes Within support

- **GIVEN** user reads CLAUDE.md or help documentation
- **WHEN** reviewing database management section
- **THEN** documentation SHALL explain Universes Within card support
- **AND** clarify that default-cards includes both paper and digital-only versions
- **AND** explain oracle-cards may exclude digital-only variants (OM1, etc.)
- **AND** provide example: "Through the Omenpaths (OM1) cards available with default-cards only"

### Requirement: Bulk Data Type Documentation

The import system SHALL clearly document bulk data type trade-offs (card count, database size, import time, completeness) in user-facing documentation and help text.

**Added**: New requirement for comprehensive documentation of bulk data type options.

**Rationale**: Users need to understand trade-offs between database size, import time, and card completeness to choose appropriate bulk data type for their use case.

#### Scenario: CLAUDE.md documents bulk data types

- **GIVEN** user reads `CLAUDE.md` in Database Management section
- **WHEN** reviewing import documentation
- **THEN** it SHALL include a table comparing three bulk data types:
  - **default-cards**: ~60k cards, 200MB, 6-9 min import, all printings including Universes Within
  - **oracle-cards**: ~30k cards, 79MB, 2-3 min import, canonical versions only (may miss OM1)
  - **unique-artwork**: ~123k cards, 486MB, 15-20 min import, all artwork variants (overkill for most users)
- **AND** document default is default-cards (recommended for completeness)
- **AND** explain when to use oracle-cards (disk-constrained environments, faster setup)

#### Scenario: Help text shows bulk data type examples

- **GIVEN** user runs `uv run scripts/import_scryfall_data.py --help`
- **WHEN** help text displays examples section
- **THEN** it SHALL include examples for each bulk data type:
  - Default: `uv run scripts/import_scryfall_data.py` (uses default-cards)
  - Smaller DB: `uv run scripts/import_scryfall_data.py --type oracle_cards`
  - Comprehensive: `uv run scripts/import_scryfall_data.py --type unique_artwork`
- **AND** explain use case for each option

#### Scenario: .env.example documents bulk data type behavior

- **GIVEN** user reads `.env.example` file (if exists)
- **WHEN** reviewing database configuration section
- **THEN** it SHALL include comment documenting bulk data type options
- **AND** explain default is default-cards
- **AND** clarify trade-offs between options (size, completeness, time)
- **AND** provide example environment variable (if applicable)

## Validation Notes

### Performance Validation
- Verify default-cards import completes in <10 minutes on typical hardware (SSD, 4-core CPU)
- Verify memory usage remains <200MB during import (monitor with `htop` or similar)
- Verify query performance remains <500ms after switching to default-cards (2x more rows)

### Functional Validation
- Verify all 188 OM1 cards are present: `SELECT COUNT(*) FROM cards WHERE "set" = 'om1'`
- Verify platform filtering works: Search with `games=["arena"]` includes OM1 cards
- Verify Oracle ID handling: Both OM1 and SPM versions present for same Oracle ID

### Documentation Validation
- Verify CLAUDE.md updated with bulk data type comparison table
- Verify help text shows correct default (default-cards)
- Verify .env.example includes bulk data type documentation (if applicable)

### Backward Compatibility
- Verify oracle-cards option still works: `--type oracle_cards` imports successfully
- Verify existing decks and queries work with default-cards database (no API changes)
- Verify migration path documented: Users can re-import to switch bulk data types

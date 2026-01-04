# deck-cli-tool Specification

## Purpose
Provides a command-line interface for direct deck management operations through the data layer, enabling lightweight deck operations without the agent or UI stack.

## ADDED Requirements

### Requirement: CLI Tool Architecture
The system SHALL provide a standalone CLI script that directly accesses the DeckRepository and CardRepository for deck operations.

#### Scenario: Script imports data layer only
- **GIVEN** the manage_decks.py script is executed
- **WHEN** Python imports are loaded
- **THEN** the script imports from src.data.repositories only
- **AND** no imports from src.agent or src.ui are present
- **AND** the script can run without PydanticAI or Chainlit dependencies

#### Scenario: Script creates database session
- **GIVEN** the CLI tool needs to execute a command
- **WHEN** the command handler is invoked
- **THEN** an AsyncEngine is created using create_engine()
- **AND** a session factory is created using create_session_factory()
- **AND** a session context manager is used for the operation
- **AND** the session is properly closed after the operation

#### Scenario: Script uses asyncio for async operations
- **GIVEN** the CLI tool needs to call async repository methods
- **WHEN** a command is executed
- **THEN** asyncio.run() is used to execute the async operation
- **AND** the async context is properly managed

### Requirement: List Decks Command
The system SHALL provide a "list" command to display all decks with summary metadata.

#### Scenario: List all decks with default format
- **GIVEN** multiple decks exist in the database
- **WHEN** running "uv run python scripts/manage_decks.py list"
- **THEN** all decks are displayed in a table format
- **AND** each row shows: name, ID (truncated to 8 chars), format, colors, mainboard count, sideboard count, created date
- **AND** decks are ordered by created_at descending (newest first)

#### Scenario: List decks filtered by format
- **GIVEN** decks exist with formats "standard" and "modern"
- **WHEN** running "uv run python scripts/manage_decks.py list --format standard"
- **THEN** only Standard format decks are displayed
- **AND** Modern decks are excluded

#### Scenario: List decks with no decks in database
- **GIVEN** the database has no decks
- **WHEN** running "uv run python scripts/manage_decks.py list"
- **THEN** a message "No decks found" is displayed
- **AND** the script exits with code 0

#### Scenario: Display color identity in WUBRG format
- **GIVEN** a deck has color_identity ["R", "G"]
- **WHEN** the deck is listed
- **THEN** the colors column shows "RG"
- **AND** an empty color identity shows "-"

### Requirement: Show Deck Details Command
The system SHALL provide a "show" command to display full deck details including all cards.

#### Scenario: Show deck by ID
- **GIVEN** a deck exists with ID "12345678-1234-1234-1234-123456789abc"
- **WHEN** running "uv run python scripts/manage_decks.py show 12345678"
- **THEN** the full deck details are displayed
- **AND** deck metadata is shown (name, ID, format, colors, strategy, created/updated dates)
- **AND** all mainboard cards are listed with quantities
- **AND** all sideboard cards are listed separately with quantities
- **AND** cards are grouped by type (Creatures, Spells, Lands)

#### Scenario: Show deck by name
- **GIVEN** a deck exists with name "Mono Red Aggro"
- **WHEN** running "uv run python scripts/manage_decks.py show --name 'Mono Red Aggro'"
- **THEN** the deck is found by case-insensitive partial match
- **AND** full deck details are displayed

#### Scenario: Show non-existent deck
- **GIVEN** no deck exists with ID "invalid-id"
- **WHEN** running "uv run python scripts/manage_decks.py show invalid-id"
- **THEN** an error message "Deck not found: invalid-id" is displayed
- **AND** the script exits with code 1

#### Scenario: Display card details in deck view
- **GIVEN** a deck contains "Lightning Bolt"
- **WHEN** the deck is shown
- **THEN** each card shows: quantity, name, mana cost, type line
- **AND** cards are sorted by CMC within each type group

### Requirement: Create Deck Command
The system SHALL provide a "create" command to create new decks with name and format.

#### Scenario: Create deck with required fields
- **GIVEN** the user wants to create a new Standard deck
- **WHEN** running "uv run python scripts/manage_decks.py create 'Mono Red Aggro' standard"
- **THEN** a new deck is created in the database
- **AND** the deck name is "Mono Red Aggro"
- **AND** the deck format is "standard"
- **AND** a success message is displayed with the new deck ID
- **AND** the script exits with code 0

#### Scenario: Create deck with optional strategy
- **GIVEN** the user wants to create a deck with strategy description
- **WHEN** running "uv run python scripts/manage_decks.py create 'Control Deck' standard --strategy 'Reactive control with counters'"
- **THEN** a new deck is created with the specified strategy
- **AND** the strategy field is set to "Reactive control with counters"

#### Scenario: Create deck with duplicate name
- **GIVEN** a deck named "Test Deck" already exists
- **WHEN** running "uv run python scripts/manage_decks.py create 'Test Deck' standard"
- **THEN** an error message is displayed (deck names must be unique)
- **AND** the script exits with code 1

### Requirement: Delete Deck Command
The system SHALL provide a "delete" command to remove decks by name or ID with confirmation.

#### Scenario: Delete deck with confirmation flag
- **GIVEN** a deck exists with name "Old Deck"
- **WHEN** running "uv run python scripts/manage_decks.py delete --name 'Old Deck' --confirm"
- **THEN** the deck is deleted from the database
- **AND** all associated deck cards are deleted (cascade)
- **AND** a success message is displayed
- **AND** the script exits with code 0

#### Scenario: Delete deck without confirmation
- **GIVEN** a deck exists with ID "12345678"
- **WHEN** running "uv run python scripts/manage_decks.py delete 12345678"
- **THEN** an error message is displayed requiring --confirm flag
- **AND** the deck is NOT deleted
- **AND** the script exits with code 1

#### Scenario: Delete non-existent deck
- **GIVEN** no deck exists with name "Invalid Deck"
- **WHEN** running "uv run python scripts/manage_decks.py delete --name 'Invalid Deck' --confirm"
- **THEN** an error message "Deck not found" is displayed
- **AND** the script exits with code 1

### Requirement: Add Card Command
The system SHALL provide an "add-card" command to add cards to decks by card name and deck identifier.

#### Scenario: Add card to deck by exact name
- **GIVEN** a deck exists with name "Red Deck"
- **AND** a card exists with name "Lightning Bolt"
- **WHEN** running "uv run python scripts/manage_decks.py add-card 'Red Deck' 'Lightning Bolt' --quantity 4"
- **THEN** the card is added to the deck's mainboard with quantity 4
- **AND** a success message is displayed
- **AND** the script exits with code 0

#### Scenario: Add card to sideboard
- **GIVEN** a deck exists and a card exists
- **WHEN** running "uv run python scripts/manage_decks.py add-card 'Red Deck' 'Abrade' --quantity 2 --sideboard"
- **THEN** the card is added to the deck's sideboard with quantity 2
- **AND** the sideboard flag is set correctly

#### Scenario: Add card with non-existent card name
- **GIVEN** no card exists with name "Invalid Card"
- **WHEN** running "uv run python scripts/manage_decks.py add-card 'Red Deck' 'Invalid Card' --quantity 4"
- **THEN** an error message "Card not found: Invalid Card" is displayed
- **AND** the script exits with code 1

#### Scenario: Add card already in deck
- **GIVEN** a deck already contains "Lightning Bolt" in mainboard
- **WHEN** running "uv run python scripts/manage_decks.py add-card 'Red Deck' 'Lightning Bolt' --quantity 4"
- **THEN** an error message "Card already exists in deck" is displayed
- **AND** a suggestion to use "update-quantity" is shown
- **AND** the script exits with code 1

#### Scenario: Default quantity is 1
- **GIVEN** a user wants to add a card without specifying quantity
- **WHEN** running "uv run python scripts/manage_decks.py add-card 'Red Deck' 'Lightning Bolt'"
- **THEN** the card is added with quantity 1
- **AND** the default quantity is applied

### Requirement: Remove Card Command
The system SHALL provide a "remove-card" command to remove cards from decks.

#### Scenario: Remove card from mainboard
- **GIVEN** a deck contains "Lightning Bolt" in mainboard
- **WHEN** running "uv run python scripts/manage_decks.py remove-card 'Red Deck' 'Lightning Bolt' --confirm"
- **THEN** the card is removed from the deck's mainboard
- **AND** a success message is displayed
- **AND** the script exits with code 0

#### Scenario: Remove card from sideboard
- **GIVEN** a deck contains "Abrade" in sideboard
- **WHEN** running "uv run python scripts/manage_decks.py remove-card 'Red Deck' 'Abrade' --sideboard --confirm"
- **THEN** the card is removed from the deck's sideboard

#### Scenario: Remove card not in deck
- **GIVEN** a deck does not contain "Invalid Card"
- **WHEN** running "uv run python scripts/manage_decks.py remove-card 'Red Deck' 'Invalid Card' --confirm"
- **THEN** an error message "Card not found in deck" is displayed
- **AND** the script exits with code 1

#### Scenario: Remove card without confirmation
- **GIVEN** a deck contains "Lightning Bolt"
- **WHEN** running "uv run python scripts/manage_decks.py remove-card 'Red Deck' 'Lightning Bolt'"
- **THEN** an error message requiring --confirm flag is displayed
- **AND** the card is NOT removed
- **AND** the script exits with code 1

### Requirement: Update Card Quantity Command
The system SHALL provide an "update-quantity" command to change card quantities in decks.

#### Scenario: Update card quantity in mainboard
- **GIVEN** a deck contains "Lightning Bolt" with quantity 2
- **WHEN** running "uv run python scripts/manage_decks.py update-quantity 'Red Deck' 'Lightning Bolt' 4"
- **THEN** the card quantity is updated to 4
- **AND** a success message is displayed
- **AND** the script exits with code 0

#### Scenario: Update card quantity in sideboard
- **GIVEN** a deck contains "Abrade" in sideboard with quantity 1
- **WHEN** running "uv run python scripts/manage_decks.py update-quantity 'Red Deck' 'Abrade' 3 --sideboard"
- **THEN** the sideboard card quantity is updated to 3

#### Scenario: Update quantity for card not in deck
- **GIVEN** a deck does not contain "Invalid Card"
- **WHEN** running "uv run python scripts/manage_decks.py update-quantity 'Red Deck' 'Invalid Card' 4"
- **THEN** an error message "Card not found in deck" is displayed
- **AND** the script exits with code 1

#### Scenario: Update quantity to zero
- **GIVEN** a deck contains "Lightning Bolt"
- **WHEN** running "uv run python scripts/manage_decks.py update-quantity 'Red Deck' 'Lightning Bolt' 0"
- **THEN** an error message "Quantity must be at least 1" is displayed
- **AND** a suggestion to use "remove-card" is shown
- **AND** the script exits with code 1

### Requirement: Merge Decks Command
The system SHALL provide a "merge" command to combine cards from a source deck into a target deck using configurable merge strategies.

#### Scenario: Merge decks with COMBINE strategy (default)
- **GIVEN** a target deck "Deck A" contains 2x Lightning Bolt in mainboard
- **AND** a source deck "Deck B" contains 3x Lightning Bolt in mainboard
- **WHEN** running "uv run python scripts/manage_decks.py merge 'Deck A' 'Deck B'"
- **THEN** the target deck contains 5x Lightning Bolt (2 + 3)
- **AND** the source deck remains unchanged (non-destructive)
- **AND** a success message shows cards added and merged
- **AND** the script exits with code 0

#### Scenario: Merge decks with MAXIMUM strategy
- **GIVEN** a target deck contains 2x Lightning Bolt
- **AND** a source deck contains 3x Lightning Bolt
- **WHEN** running "uv run python scripts/manage_decks.py merge 'Deck A' 'Deck B' --strategy MAXIMUM"
- **THEN** the target deck contains 3x Lightning Bolt (max of 2 and 3)
- **AND** the source deck remains unchanged

#### Scenario: Merge decks with REPLACE strategy
- **GIVEN** a target deck contains 2x Lightning Bolt
- **AND** a source deck contains 3x Lightning Bolt
- **WHEN** running "uv run python scripts/manage_decks.py merge 'Deck A' 'Deck B' --strategy REPLACE"
- **THEN** the target deck contains 3x Lightning Bolt (replaced with source quantity)
- **AND** the source deck remains unchanged

#### Scenario: Merge decks with disjoint card sets
- **GIVEN** a target deck contains Lightning Bolt only
- **AND** a source deck contains Shock only
- **WHEN** running "uv run python scripts/manage_decks.py merge 'Deck A' 'Deck B'"
- **THEN** the target deck contains both Lightning Bolt and Shock
- **AND** quantities match original decks (no overlap)

#### Scenario: Merge respects mainboard/sideboard separation
- **GIVEN** a target deck contains 4x Lightning Bolt in mainboard
- **AND** a source deck contains 2x Lightning Bolt in sideboard
- **WHEN** merge is executed
- **THEN** target deck has 4x in mainboard (unchanged) and 2x in sideboard (added)
- **AND** mainboard and sideboard are tracked separately

#### Scenario: Merge updates color identity
- **GIVEN** target deck is mono-red (color_identity = ["R"])
- **AND** source deck is mono-blue (color_identity = ["U"])
- **WHEN** merge is executed
- **THEN** target deck color_identity is updated to ["R", "U"]
- **AND** colors are sorted in WUBRG order

#### Scenario: Merge with non-existent target deck
- **GIVEN** no deck exists named "Invalid Deck"
- **WHEN** running "uv run python scripts/manage_decks.py merge 'Invalid Deck' 'Valid Deck'"
- **THEN** an error message "Target deck not found: Invalid Deck" is displayed
- **AND** the script exits with code 1

#### Scenario: Merge with non-existent source deck
- **GIVEN** no deck exists named "Invalid Deck"
- **WHEN** running "uv run python scripts/manage_decks.py merge 'Valid Deck' 'Invalid Deck'"
- **THEN** an error message "Source deck not found: Invalid Deck" is displayed
- **AND** the script exits with code 1

#### Scenario: Merge with invalid strategy
- **GIVEN** a user specifies an invalid strategy
- **WHEN** running "uv run python scripts/manage_decks.py merge 'Deck A' 'Deck B' --strategy INVALID"
- **THEN** an error message lists valid strategies (COMBINE, MAXIMUM, REPLACE)
- **AND** the script exits with code 1

#### Scenario: Merge with confirmation for destructive operation
- **GIVEN** a user wants to merge decks
- **WHEN** running "uv run python scripts/manage_decks.py merge 'Deck A' 'Deck B' --confirm"
- **THEN** the merge proceeds immediately without prompting
- **AND** confirmation flag is optional (merge is non-destructive to source)

#### Scenario: Display merge summary
- **GIVEN** a merge operation completes successfully
- **WHEN** the operation finishes
- **THEN** a summary is displayed showing:
  - Number of cards added to target deck
  - Number of cards with quantities merged
  - Strategy used
  - Updated color identity
- **AND** the summary is user-friendly and concise

### Requirement: Export Deck Command
The system SHALL provide an "export" command to export decks to text decklist format.

#### Scenario: Export deck to file
- **GIVEN** a deck exists with name "Red Deck" containing multiple cards
- **WHEN** running "uv run python scripts/manage_decks.py export 'Red Deck' --output deck.txt"
- **THEN** a text file is created at "deck.txt"
- **AND** the file contains deck name as header
- **AND** mainboard cards are listed as "Nx Card Name" format
- **AND** sideboard cards are listed under "Sideboard" section
- **AND** a success message is displayed

#### Scenario: Export deck to stdout
- **GIVEN** a deck exists with name "Red Deck"
- **WHEN** running "uv run python scripts/manage_decks.py export 'Red Deck'"
- **THEN** the deck list is printed to stdout
- **AND** the format is suitable for copying to clipboard

#### Scenario: Export deck with metadata
- **GIVEN** a deck has strategy and tags set
- **WHEN** running "uv run python scripts/manage_decks.py export 'Red Deck' --include-metadata"
- **THEN** the exported file includes deck metadata as comments
- **AND** comments show: format, colors, strategy, tags

### Requirement: Case-Insensitive Card Lookup
The system SHALL perform case-insensitive exact card name matching for all card operations.

#### Scenario: Add card with different case
- **GIVEN** a card exists in database as "Lightning Bolt"
- **WHEN** running "uv run python scripts/manage_decks.py add-card 'Red Deck' 'lightning bolt' --quantity 4"
- **THEN** the card is found by case-insensitive match
- **AND** the card is added successfully using the canonical name "Lightning Bolt"

#### Scenario: Card name with special characters
- **GIVEN** a card exists with name "Ætherling"
- **WHEN** running add-card with name "Ætherling"
- **THEN** the card is found correctly
- **AND** special characters are preserved

### Requirement: User-Friendly Error Messages
The system SHALL provide clear, actionable error messages for common failure scenarios.

#### Scenario: Deck not found error
- **GIVEN** a user tries to show a non-existent deck
- **WHEN** the deck lookup fails
- **THEN** the error message includes the searched identifier
- **AND** the error suggests using "list" command to view available decks

#### Scenario: Card not found error
- **GIVEN** a user tries to add a card that doesn't exist
- **WHEN** the card lookup fails
- **THEN** the error message includes the searched card name
- **AND** the error suggests checking the card name spelling

#### Scenario: Database connection error
- **GIVEN** the CARDS_DATABASE_URL points to an invalid location
- **WHEN** any command is executed
- **THEN** a clear error message about database connection is displayed
- **AND** the error includes the database path being used

#### Scenario: Permission denied error
- **GIVEN** the database file has restrictive permissions
- **WHEN** a write operation is attempted
- **THEN** a clear error message about file permissions is displayed
- **AND** the error suggests checking file ownership/permissions

### Requirement: Help and Usage Documentation
The system SHALL provide comprehensive help text for all commands via --help flag.

#### Scenario: Display main help
- **GIVEN** a user runs the script without arguments
- **WHEN** running "uv run python scripts/manage_decks.py --help"
- **THEN** a help message is displayed showing all available commands
- **AND** each command has a brief description
- **AND** usage examples are shown

#### Scenario: Display command-specific help
- **GIVEN** a user wants help for the "add-card" command
- **WHEN** running "uv run python scripts/manage_decks.py add-card --help"
- **THEN** detailed help for add-card is displayed
- **AND** all parameters are documented
- **AND** usage examples are shown

### Requirement: Performance for Typical Operations
The system SHALL complete typical CLI operations in under 1 second for decks with <100 cards.

#### Scenario: List decks performance
- **GIVEN** 20 decks exist in the database
- **WHEN** running the "list" command
- **THEN** the operation completes in <500ms
- **AND** all decks are displayed

#### Scenario: Show deck performance
- **GIVEN** a deck contains 75 cards (60 mainboard + 15 sideboard)
- **WHEN** running the "show" command
- **THEN** the operation completes in <800ms
- **AND** all cards are loaded and displayed

#### Scenario: Add card performance
- **GIVEN** a user adds a card to a deck
- **WHEN** running the "add-card" command
- **THEN** the operation completes in <500ms
- **AND** the database transaction is committed

### Requirement: Argparse CLI Framework
The system SHALL use Python's argparse module for command-line argument parsing with subcommands.

#### Scenario: Subcommand structure
- **GIVEN** the CLI script uses argparse
- **WHEN** the script is executed
- **THEN** a main parser is created with subparsers for each command
- **AND** each subcommand has its own argument parser
- **AND** common arguments (--help) are available for all commands

#### Scenario: Type conversion for arguments
- **GIVEN** the quantity argument expects an integer
- **WHEN** a user provides "4"
- **THEN** argparse converts it to int(4) automatically
- **AND** invalid inputs (e.g., "abc") raise a clear error

### Requirement: Integration with Existing Data Layer
The system SHALL use existing DeckRepository and CardRepository without modifications.

#### Scenario: Use DeckRepository methods
- **GIVEN** the CLI needs to list decks
- **WHEN** the list command is executed
- **THEN** DeckRepository.list_decks() is called
- **AND** the returned Deck Pydantic schemas are formatted for display

#### Scenario: Use CardRepository for lookups
- **GIVEN** the CLI needs to find a card by name
- **WHEN** the add-card command is executed
- **THEN** CardRepository.find_by_name_exact() is called
- **AND** the returned Card schema is used for deck operations

#### Scenario: Session management pattern
- **GIVEN** a CLI command needs database access
- **WHEN** the command handler is invoked
- **THEN** a session context manager is used (async with session_factory())
- **AND** repositories are instantiated with the session
- **AND** the session is committed and closed after the operation

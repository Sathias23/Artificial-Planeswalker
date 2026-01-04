# Proposal: Add Deck Management CLI Tool

## User Story
As a user of Artificial-Planeswalker, I want a simple CLI for interacting with the deck management data layer, so I can perform deck operations without needing the entire agent codebase.

## Why
Currently, deck operations can only be performed through the Chainlit chat interface, which requires running the full PydanticAI agent stack and UI layer. For quick deck management tasks, debugging data layer issues, or scripting deck operations, a lightweight CLI tool would be more efficient. This follows the established pattern of `scripts/manage_bug_reports.py` and enables direct data layer access without agent/UI overhead.

## Problem Statement
Currently, deck operations (creating decks, adding cards, listing decks, etc.) can only be performed through the Chainlit chat interface, which requires:
- Running the full PydanticAI agent stack
- Loading the UI layer (Chainlit)
- Interactive chat sessions

For quick deck management tasks, debugging data layer issues, or scripting deck operations, a lightweight CLI tool that directly accesses the data layer would be more efficient.

## Proposed Solution
Create a standalone CLI script (`scripts/manage_decks.py`) that provides direct access to the `DeckRepository` for common deck operations. This mirrors the existing pattern established by `scripts/manage_bug_reports.py`.

### Commands
1. **list** - List all decks with metadata (name, ID, format, card counts, colors)
2. **show** - Show full details of a specific deck including all cards
3. **create** - Create a new deck with name and format
4. **delete** - Delete a deck by name or ID with confirmation
5. **add-card** - Add a card to a deck by card name and deck name/ID
6. **remove-card** - Remove a card from a deck
7. **update-quantity** - Update card quantity in a deck
8. **merge** - Merge cards from source deck into target deck with configurable strategy (COMBINE/MAXIMUM/REPLACE)
9. **export** - Export deck to decklist format (text file)

### Architecture
- **Data Layer Only**: Script directly instantiates `DeckRepository` and `CardRepository` without agent/UI dependencies
- **Async Pattern**: Uses `asyncio.run()` for repository calls (same pattern as data layer)
- **Session Management**: Creates engine and session factory per command execution
- **Error Handling**: User-friendly error messages for common issues (deck not found, card not found, etc.)
- **Output Format**: Tabular display using simple text formatting (similar to `manage_bug_reports.py`)

### Benefits
- **Lightweight**: No agent or UI overhead for simple data operations
- **Scriptable**: Can be used in automation or batch operations
- **Debugging**: Easier to test data layer in isolation
- **Developer Experience**: Quick access to deck data during development

### Constraints
- **Read-only by default**: Destructive operations (delete, remove-card) require confirmation flag
- **Local database only**: Uses `CARDS_DATABASE_URL` environment variable (same as main app)
- **No validation logic**: Script does not enforce deck construction rules (60-card minimum, 4-copy limit) - this is intentional for flexibility
- **Manual card lookup**: Users must provide exact card names (case-insensitive match)

## Scope
This proposal is tightly scoped to:
1. Creating `scripts/manage_decks.py` CLI tool
2. Adding new capability spec `deck-cli-tool` with requirements
3. Adding tasks for implementation and testing
4. Exposing existing `DeckRepository.merge_decks()` functionality via CLI

Out of scope:
- Deck validation logic (already exists in `src/logic/` layer)
- Import/export from external deck formats (MTG Arena, MTGO) - future enhancement
- Integration with agent layer or UI layer
- Web-based deck management interface

## Dependencies
- Requires completed `add-deck-merge-function` change (already implemented in `DeckRepository`)

## Impact Analysis
- **No changes to existing code**: Pure addition, no modifications to data layer or agent layer
- **No new dependencies**: Uses existing SQLAlchemy, argparse (stdlib), and data layer code
- **Testing**: Unit tests for CLI argument parsing, integration tests for repository operations

## Success Criteria
- User can list all decks without running Chainlit
- User can create a new deck and add cards using exact card names
- User can view deck contents with card details
- User can delete decks with confirmation
- All operations complete in <1 second for typical decks (<100 cards)
- CLI provides helpful error messages for common issues

## Open Questions
None - straightforward implementation following established patterns.

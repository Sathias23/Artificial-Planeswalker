# Add Deck Merge Function

## Why

Users building multiple deck variants often need to combine cards from different decks into a single unified deck. Currently, this requires manually adding cards one-by-one through conversational commands, which is tedious for large card lists. A data-layer merge function provides a reusable, testable primitive that can be leveraged by future agent tools or UI actions for efficient deck combination workflows.

## What Changes

- Add `merge_decks()` method to `DeckRepository` for combining two decks into a single deck
- Support configurable merge strategies (COMBINE quantities, MAXIMUM quantity, REPLACE with source)
- Handle mainboard/sideboard card locations separately during merge
- Update deck timestamps and color identity after merge
- Preserve source deck(s) by default (non-destructive merge)
- Add comprehensive error handling with rollback on database errors

## Impact

- **Affected specs**: `data-layer` (new requirement for deck merging operations)
- **Affected code**:
  - `src/data/repositories/deck.py` (add `merge_decks()` method)
  - `tests/integration/data/test_deck_repository.py` (integration tests for merge workflows)
  - `tests/unit/data/test_deck_repository.py` (unit tests for merge edge cases)
- **No breaking changes**: Pure addition to existing API
- **Future extensibility**: Enables agent tools for deck merging, variant management, and deck templates

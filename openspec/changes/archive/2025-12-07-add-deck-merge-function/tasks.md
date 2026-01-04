# Implementation Tasks

## 1. Data Layer Implementation
- [x] 1.1 Add `MergeStrategy` enum to `src/data/repositories/deck.py` (COMBINE, MAXIMUM, REPLACE)
- [x] 1.2 Implement `merge_decks()` method in `DeckRepository` with strategy parameter
- [x] 1.3 Add card quantity merging logic (respects strategy: COMBINE sums, MAXIMUM takes max, REPLACE uses source)
- [x] 1.4 Handle mainboard/sideboard locations separately (merge mainboard to mainboard, sideboard to sideboard)
- [x] 1.5 Add automatic deck color identity update after merge
- [x] 1.6 Add automatic deck timestamp update (updated_at) after merge
- [x] 1.7 Add transaction management with explicit rollback on errors (IntegrityError, DatabaseError)
- [x] 1.8 Add logging for merge operations (source/target deck IDs, card count, strategy)

## 2. Type Safety
- [x] 2.1 Add strict type hints to `merge_decks()` method signature
- [x] 2.2 Define `MergeStrategy` Literal type or Enum
- [x] 2.3 Ensure mypy validation passes in strict mode

## 3. Unit Tests
- [x] 3.1 Test merge with COMBINE strategy (quantities sum correctly)
- [x] 3.2 Test merge with MAXIMUM strategy (takes higher quantity)
- [x] 3.3 Test merge with REPLACE strategy (target deck gets source quantities)
- [x] 3.4 Test merge respects mainboard/sideboard locations (no cross-contamination)
- [x] 3.5 Test merge with non-existent target deck (returns None)
- [x] 3.6 Test merge with non-existent source deck (returns None)
- [x] 3.7 Test merge updates color identity correctly
- [x] 3.8 Test merge updates updated_at timestamp
- [x] 3.9 Test merge with empty source deck (no-op, target unchanged)
- [x] 3.10 Test merge with empty target deck (copies all cards from source)

## 4. Integration Tests
- [x] 4.1 Integration test: merge two decks with overlapping cards
- [x] 4.2 Integration test: merge decks with disjoint card sets
- [x] 4.3 Integration test: merge with COMBINE strategy (verify quantity sums in database)
- [x] 4.4 Integration test: merge with MAXIMUM strategy (verify max quantities in database)
- [x] 4.5 Integration test: merge preserves source deck (verify source unchanged after merge)
- [x] 4.6 Integration test: merge updates target deck color identity
- [x] 4.7 Integration test: database rollback on IntegrityError (session state clean)
- [x] 4.8 Integration test: merge with mainboard and sideboard cards (verify location separation)

## 5. Documentation
- [x] 5.1 Add docstring to `merge_decks()` with parameter descriptions and examples
- [x] 5.2 Update `CLAUDE.md` to document merge function in data layer section
- [x] 5.3 Add merge examples to repository docstring

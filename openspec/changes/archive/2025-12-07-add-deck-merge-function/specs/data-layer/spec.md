## ADDED Requirements

### Requirement: Deck Merging Operations

The system SHALL provide a repository method to merge cards from a source deck into a target deck with configurable merge strategies.

#### Scenario: Merge decks with COMBINE strategy

- **GIVEN** a target deck contains 2 copies of "Lightning Bolt" in mainboard
- **AND** a source deck contains 3 copies of "Lightning Bolt" in mainboard
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck contains 5 copies of "Lightning Bolt" in mainboard
- **AND** the source deck remains unchanged (2 copies)
- **AND** the target deck's updated_at timestamp is refreshed
- **AND** an updated Deck schema is returned

#### Scenario: Merge decks with MAXIMUM strategy

- **GIVEN** a target deck contains 2 copies of "Lightning Bolt" in mainboard
- **AND** a source deck contains 3 copies of "Lightning Bolt" in mainboard
- **WHEN** `merge_decks(target_id, source_id, strategy="MAXIMUM")` is called
- **THEN** the target deck contains 3 copies of "Lightning Bolt" in mainboard (max of 2 and 3)
- **AND** the source deck remains unchanged
- **AND** the target deck's updated_at timestamp is refreshed
- **AND** an updated Deck schema is returned

#### Scenario: Merge decks with REPLACE strategy

- **GIVEN** a target deck contains 2 copies of "Lightning Bolt" in mainboard
- **AND** a source deck contains 3 copies of "Lightning Bolt" in mainboard
- **WHEN** `merge_decks(target_id, source_id, strategy="REPLACE")` is called
- **THEN** the target deck contains 3 copies of "Lightning Bolt" in mainboard (replaced with source quantity)
- **AND** the source deck remains unchanged
- **AND** the target deck's updated_at timestamp is refreshed
- **AND** an updated Deck schema is returned

#### Scenario: Merge decks with disjoint card sets

- **GIVEN** a target deck contains "Lightning Bolt" in mainboard
- **AND** a source deck contains "Shock" in mainboard (no overlap with target)
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck contains both "Lightning Bolt" and "Shock" in mainboard
- **AND** quantities match the original decks (no cards existed in both decks)
- **AND** the source deck remains unchanged

#### Scenario: Merge decks respects mainboard/sideboard separation

- **GIVEN** a target deck contains "Lightning Bolt" with 4 copies in mainboard
- **AND** a source deck contains "Lightning Bolt" with 2 copies in sideboard
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck contains 4 copies in mainboard (unchanged)
- **AND** the target deck contains 2 copies in sideboard (added from source)
- **AND** mainboard and sideboard cards are tracked separately (no cross-contamination)

#### Scenario: Merge updates deck color identity

- **GIVEN** a target deck contains only red cards (color_identity = ["R"])
- **AND** a source deck contains only blue cards (color_identity = ["U"])
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck's color_identity is updated to ["R", "U"]
- **AND** colors are sorted in WUBRG order
- **AND** the updated Deck schema reflects the new color_identity

#### Scenario: Merge with non-existent target deck

- **GIVEN** no deck exists with target_id "invalid-id"
- **WHEN** `merge_decks(target_id="invalid-id", source_id="valid-source", strategy="COMBINE")` is called
- **THEN** None is returned
- **AND** no database modifications occur
- **AND** no exceptions are raised

#### Scenario: Merge with non-existent source deck

- **GIVEN** no deck exists with source_id "invalid-id"
- **WHEN** `merge_decks(target_id="valid-target", source_id="invalid-id", strategy="COMBINE")` is called
- **THEN** None is returned
- **AND** the target deck remains unchanged
- **AND** no exceptions are raised

#### Scenario: Merge with empty source deck

- **GIVEN** a target deck contains cards
- **AND** a source deck exists but has no cards (deck_cards is empty)
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck remains unchanged (no cards added)
- **AND** the updated Deck schema is returned
- **AND** the updated_at timestamp is refreshed (operation occurred)

#### Scenario: Merge with empty target deck

- **GIVEN** a target deck exists but has no cards
- **AND** a source deck contains 4 copies of "Lightning Bolt"
- **WHEN** `merge_decks(target_id, source_id, strategy="COMBINE")` is called
- **THEN** the target deck contains 4 copies of "Lightning Bolt"
- **AND** quantities match the source deck (COMBINE with 0 yields source quantity)
- **AND** the source deck remains unchanged

#### Scenario: Merge transaction rollback on IntegrityError

- **GIVEN** a merge operation triggers an IntegrityError (e.g., database constraint violation)
- **WHEN** the repository catches the IntegrityError
- **THEN** the session is explicitly rolled back via `await session.rollback()`
- **AND** the IntegrityError is re-raised for upper layers to handle
- **AND** the session is left in a clean state (not rolled-back)
- **AND** subsequent operations on the same session succeed

#### Scenario: Merge transaction rollback on DatabaseError

- **GIVEN** a merge operation encounters a database-level error
- **WHEN** the repository catches the DatabaseError
- **THEN** the session is explicitly rolled back
- **AND** the error is logged with operation context (target_id, source_id, strategy)
- **AND** the original exception is re-raised with preserved exception chain
- **AND** the session is left in a clean state

### Requirement: Merge Strategy Type Safety

The system SHALL define a type-safe merge strategy parameter with explicit valid values.

#### Scenario: Merge strategy accepts valid strategy strings

- **GIVEN** the `merge_decks()` method signature
- **WHEN** the method is called with strategy="COMBINE", "MAXIMUM", or "REPLACE"
- **THEN** the method executes successfully
- **AND** mypy validates only valid strategy strings can be passed

#### Scenario: Merge strategy type definition

- **GIVEN** the merge strategy parameter type
- **WHEN** analyzing with mypy in strict mode
- **THEN** the parameter has type hint `Literal["COMBINE", "MAXIMUM", "REPLACE"]` or Enum
- **AND** passing invalid strategy strings causes type errors
- **AND** the type system enforces valid strategies at compile time

### Requirement: Merge Operation Logging

The system SHALL log deck merge operations with sufficient context for debugging and audit trails.

#### Scenario: Successful merge operation logged

- **GIVEN** a merge operation completes successfully
- **WHEN** the operation finishes
- **THEN** the system logs at INFO level with:
  - Target deck ID
  - Source deck ID
  - Merge strategy used
  - Number of cards merged
  - Number of new cards added to target
- **AND** the log message is concise and parseable

#### Scenario: Merge error logged with context

- **GIVEN** a merge operation encounters an error
- **WHEN** the error is caught
- **THEN** the system logs at ERROR level with:
  - Target deck ID
  - Source deck ID
  - Merge strategy
  - Session transaction state
  - Original exception message
- **AND** the log includes sufficient context for debugging

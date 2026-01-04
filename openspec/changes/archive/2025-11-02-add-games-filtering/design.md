# Games Filtering Design

## Context

Magic: The Gathering cards are available across three different platforms:
- **Paper**: Physical Magic cards
- **Arena**: MTG Arena (digital platform with limited card pool)
- **MTGO**: Magic Online (digital platform with comprehensive card pool)

Scryfall provides a `games` field on each card indicating which platforms the card is available on. Currently, the application imports and filters cards by format (Standard, Modern, etc.) but does not distinguish between platform availability. This causes issues for Arena players who find cards in search results that are not playable in Arena (e.g., Spider-Man series cards, which are paper-only promotional cards).

**Stakeholders:**
- Arena players building Arena-playable decks
- Paper players who want paper-only cards
- MTGO players seeking MTGO-legal cards

**Constraints:**
- Must maintain backward compatibility (additive change only)
- Must follow existing filtering patterns (format_filter architecture)
- Must persist preference across conversation sessions
- Must work with offline-first architecture (no API calls during queries)

## Goals / Non-Goals

### Goals
- Import and store the `games` field from Scryfall bulk data
- Enable filtering card searches by game availability (paper, arena, mtgo)
- Persist games filter preference in session state like format filter
- Display active games filter in UI sidebar
- Show game availability on individual cards in results
- Allow auto-filter bypass for specific queries

### Non-Goals
- Automatic games filter based on deck context (future enhancement)
- Games filter validation against deck format (not in scope)
- Multi-platform filter (e.g., "both paper AND arena") - use OR logic initially
- Historical games availability tracking (use current Scryfall data only)

## Decisions

### Decision 1: JSON Array Storage
Store `games` as a JSON array in SQLite, matching Scryfall's data structure.

**Why:**
- Consistent with existing JSON column patterns (legalities, colors, keywords)
- Supports multiple platforms per card efficiently
- Enables JSON query functions in SQLite
- Future-proof for additional platforms

**Alternatives considered:**
- Three boolean columns (is_paper, is_arena, is_mtgo): More complex schema, harder to query
- Comma-separated string: Less type-safe, harder to query
- Join table: Overkill for simple array data

### Decision 2: OR Logic for Multi-Game Filtering
When multiple games are specified in filter, use OR logic (card available in ANY specified game).

**Why:**
- Matches user mental model ("show me cards playable in Arena OR MTGO")
- Consistent with existing color filtering OR mode
- More permissive (users can further restrict results themselves)

**Example:**
```python
# games=["paper", "arena"] returns cards available in paper OR arena
stmt = self._apply_games_filter(stmt, games=["paper", "arena"])
```

**Alternatives considered:**
- AND logic (card must be in ALL games): Too restrictive, less useful
- Separate mode parameter: Adds complexity; OR covers 90% of use cases

### Decision 3: Session-Persisted Preference (In-Memory)
Store games_filter in ConversationSessionManager as in-memory session state.

**Why:**
- Consistent with existing format_filter pattern
- Reduces repetitive filter specification
- Improves UX for platform-specific deck building
- Simple implementation with no additional complexity

**Implementation:**
```python
# AgentDependencies
games_filter: list[str] | None = field(default=None)

# ConversationSessionManager maintains in-memory preferences
# Session state persists for the lifetime of the session
```

**Alternatives considered:**
- Per-query only: Forces users to repeat filter on every search
- Global config: Less flexible than per-session
- File-based persistence: Adds complexity; deferred to future enhancement

### Decision 4: UI Sidebar Display
Show active games filter in sidebar above current deck information.

**Why:**
- Provides persistent visibility of active filter
- Matches format_filter sidebar pattern
- Keeps filter context visible during deck building
- Users can easily verify which platform they're building for

**Format:**
```
Games Filter: Arena, Paper
--------------------------
Active Deck: White-Blue Flying
...
```

### Decision 5: SQLite JSON Query Pattern
Use `json_array_length()` and `LIKE` for filtering, not `json_extract()` with iteration.

**Why:**
- SQLite JSON array filtering is more efficient with LIKE pattern
- Avoids complex json_each() joins
- Consistent with codebase patterns for array filtering

**Implementation:**
```python
def _apply_games_filter(self, stmt, games: list[str] | None):
    if games is None or not games:
        return stmt

    from sqlalchemy import or_, cast, String

    # Build OR conditions - card must be available in at least one specified game
    conditions = []
    for game in games:
        conditions.append(
            cast(CardModel.games, String).like(f'%"{game}"%')
        )
    return stmt.where(or_(*conditions))
```

**Alternatives considered:**
- `json_extract()` with array indexing: Requires knowing array size
- `json_each()` subquery: More complex, slower
- Python-side filtering: Defeats database optimization

## Risks / Trade-offs

### Risk 1: Database Re-import Required
**Risk:** Users must re-import Scryfall data to populate games field.
**Mitigation:**
- Provide clear migration instructions in proposal
- Add migration task to implementation checklist
- Default to empty array for missing data (backward compatible)

### Risk 2: SQLite JSON Query Performance
**Risk:** JSON array filtering may be slower than native column queries.
**Mitigation:**
- Acceptable for offline-first architecture (<500ms target still achievable)
- Games filter typically used with format filter, reducing result set
- Can add composite index if performance becomes issue: `CREATE INDEX idx_cards_games ON cards (json_array_length(games))`

### Risk 3: Scryfall Data Changes
**Risk:** Scryfall may add new platforms or change games field structure.
**Mitigation:**
- Design supports adding new platform strings without schema changes
- Import pipeline handles unexpected values gracefully (stores as-is)
- Validation happens at query time, not import time

## Migration Plan

### Phase 1: Schema & Import (Non-Breaking)
1. Add `games` field to models with default empty array (`default_factory=list`)
2. Update transformer to extract games from Scryfall
3. Existing database continues to work (NULL games treated as empty array)

### Phase 2: Data Population
4. Run `uv run python scripts/import_scryfall_data.py` to re-import Scryfall data
5. Verify games field populated: `sqlite3 data/cards.db "SELECT name, games FROM cards LIMIT 10;"`

### Phase 3: Filtering & Tools
6. Add filtering methods to repository
7. Create agent tools
8. Update UI to display filter

### Phase 4: Testing & Validation
9. Run test suite with updated fixtures
10. Manual testing with Arena vs paper card queries

### Rollback Plan
If games filtering causes issues:
1. Set `games_filter=None` in session state (disables filtering)
2. Remove games filtering from search tools (queries continue to work)
3. Games field remains in database but unused (no data loss)

## Open Questions

- **Q:** Should load_deck() auto-set games filter based on deck format?
  - **A:** Deferred to future enhancement. Not all formats have clear game mappings (e.g., Standard is both paper and Arena, but with different legal card pools).

- **Q:** Should sidebar show game availability for cards in deck?
  - **A:** Deferred to future enhancement. Initial implementation focuses on filtering, not deck validation.

- **Q:** How to handle cards with empty games array?
  - **A:** Treat as "all games" (no restriction). Scryfall always provides games field, so empty arrays should be rare.

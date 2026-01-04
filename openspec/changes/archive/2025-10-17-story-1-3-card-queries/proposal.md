# Story 1.3: Basic Card Query Functionality and Validation

## Why

**Epic 1 Story 1.3** - Implement the query layer for the card database by adding search functions to the CardRepository. This enables the PydanticAI agent to retrieve cards by name (exact/partial), color, and type, which are the core query patterns needed for deck building assistance and rules lookups.

Building on Story 1.2's database foundation, this story delivers the first user-facing functionality: the ability to find specific cards or filter cards by attributes. These queries will be exposed as PydanticAI tools in later stories, enabling natural language card searches like "Find all blue instant cards" or "Show me Lightning Bolt."

## What Changes

- **NEW** CardRepository query methods: `find_by_name_exact()`, `find_by_name_partial()`, `find_by_colors()`, `find_by_type()`
- **NEW** Type-safe query interfaces returning Pydantic Card schemas
- **NEW** Case-insensitive search patterns with SQLAlchemy filters
- **NEW** Comprehensive unit tests for all query functions
- **NEW** Simple CLI test script to demonstrate query operations with sample data
- **NEW** Test fixture data creation for card queries

## Impact

### Affected Specs
- **NEW CAPABILITY:** `card-queries` - Repository query methods, search patterns, and validation

### Affected Code
- `src/data/repositories/card.py` - CardRepository query implementation
- `tests/unit/data/test_card_repository.py` - Query function unit tests
- `tests/fixtures/card_data.py` - Test fixture data for card queries
- `scripts/test_queries.py` - CLI demonstration script

### Dependencies
- No new dependencies (builds on Story 1.2's SQLAlchemy + aiosqlite)

## Research Summary

### Archon RAG Sources
- **FastAPI docs** (fastapi.tiangolo.com): SQLAlchemy async patterns, session handling
- **Scryfall API** (scryfall.com): Card schema structure, multi-face card handling

### Key Research Findings

1. **SQLAlchemy Async Query Patterns**
   - Use `select()` construct with `await session.execute()`
   - `scalar_one_or_none()` for single results (returns None if not found)
   - `scalars().all()` for multiple results (returns list)
   - Filter with `.where()` clauses
   - Case-insensitive: `CardModel.name.ilike(f"%{query}%")`

2. **Repository Method Design**
   - Accept AsyncSession in __init__ (already implemented in BaseRepository)
   - Return Pydantic Card schemas, not SQLAlchemy models
   - Use type hints: `async def find_by_name(...) -> Card | None`
   - Encapsulate all database operations within repository methods

3. **Card Schema Query Patterns** (from Scryfall research)
   - Name queries: Exact match (primary key lookups), partial match (autocomplete)
   - Color filtering: JSON array field `colors` contains color codes (W/U/B/R/G)
   - Type filtering: String search in `type_line` field (e.g., "Instant", "Creature")
   - Multi-face cards: Query `card_faces` JSON for double-faced cards

4. **Testing Strategy**
   - Pytest fixtures for test database setup (in-memory SQLite)
   - Create sample cards with diverse attributes (colors, types, names)
   - Test edge cases: empty results, case sensitivity, multi-face cards
   - Integration tests with real database operations

### Technical Decisions

**Decision 1: Return Pydantic Schemas, Not ORM Models**
- **What**: All repository methods return `Card` Pydantic schemas, not `CardModel` SQLAlchemy objects
- **Why**: Maintains clean separation between data layer (ORM) and application layer (schemas); prevents async detached instance errors
- **Alternatives**: Return ORM models directly (rejected: leaks implementation details, async issues)

**Decision 2: Case-Insensitive Partial Name Search**
- **What**: Use SQLAlchemy `.ilike()` for case-insensitive LIKE queries
- **Why**: Better UX for card searches (users shouldn't need exact capitalization)
- **Alternatives**: Case-sensitive `.like()` (rejected: poor UX); full-text search (deferred: overkill for MVP)

**Decision 3: Simple CLI Test Script**
- **What**: Create `scripts/test_queries.py` with basic card insertions and query demonstrations
- **Why**: Provides manual validation path and usage examples for developers
- **Alternatives**: Unit tests only (rejected: harder to visualize for non-test users)

**Decision 4: Color Filtering with JSON Containment**
- **What**: Use SQLAlchemy JSON operators to check if color codes exist in `colors` array
- **Why**: Scryfall schema stores colors as JSON arrays; need to query within array
- **Alternatives**: Separate color table with joins (rejected: premature normalization for MVP)

## Validation Criteria

- `openspec validate story-1-3-card-queries --strict` passes
- All requirements have at least one scenario
- Spec deltas use proper `## ADDED Requirements` format
- Tasks checklist is comprehensive and actionable

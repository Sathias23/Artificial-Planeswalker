# Design Document: Card Query Functionality

## Context

Story 1.3 builds the query layer on top of Story 1.2's database foundation. The CardRepository needs methods to search cards by:
- **Name**: Exact match (for known cards) and partial match (for autocomplete/search)
- **Colors**: Filter by color identity (W/U/B/R/G)
- **Type**: Filter by card type (Creature, Instant, Sorcery, etc.)

These queries support the core deck-building use cases: finding specific cards by name, filtering by color for mana base consistency, and searching by type for deck composition analysis.

## Goals / Non-Goals

### Goals
- Implement four query methods in CardRepository with type-safe interfaces
- Support case-insensitive partial name searches for better UX
- Handle multi-face cards correctly in type/color queries
- Provide comprehensive unit tests with >80% coverage
- Create CLI demonstration script for manual testing

### Non-Goals
- Full-text search or fuzzy matching (deferred to future stories)
- Query optimization or indexing beyond basic SQLite indexes (premature)
- Pagination or result limiting (add when needed)
- Complex filters (e.g., mana cost ranges, rarity) - future stories

## Research Findings

### Archon RAG Knowledge

**Source: FastAPI SQLAlchemy patterns**
- Async session handling with `select()` construct
- Pattern: `stmt = select(Model).where(condition)`
- Execution: `result = await session.execute(stmt)`
- Single result: `result.scalar_one_or_none()`
- Multiple results: `result.scalars().all()`

**Source: Scryfall card schema**
- Colors stored as JSON array: `["W", "U"]` for white/blue
- Type line format: "Creature — Human Wizard" or "Instant"
- Multi-face cards: `card_faces` array with per-face colors/types

### Additional Research

- SQLAlchemy JSON operators: `.contains()` for array membership checks (SQLite JSON support)
- Case-insensitive search: `.ilike(pattern)` for LIKE with case folding
- Type hints: `Card | None` for single results, `list[Card]` for multiple

## Decisions

### Decision 1: Repository Method Signatures

**What**: All query methods follow this pattern:
```python
async def method_name(self, params: str) -> Card | None | list[Card]:
    """Docstring with params and return type."""
    # Query implementation
    # Convert ORM to Pydantic
    return result
```

**Why**:
- Type safety with mypy/pyright
- Consistent async interface
- Clear return types (single vs multiple results)

**Alternatives**:
- Sync methods (rejected: breaks async stack)
- Generic `query()` method (rejected: less type-safe, harder to use)

### Decision 2: Pydantic Conversion Pattern

**What**: Convert SQLAlchemy models to Pydantic schemas within repository:
```python
card_model = result.scalar_one_or_none()
if card_model is None:
    return None
return Card.model_validate(card_model)
```

**Why**:
- Prevents async detached instance errors
- Maintains clean layer separation
- Enables easy serialization for API responses later

**Alternatives**:
- Return ORM models (rejected: leaks implementation, async issues)
- Convert at service layer (rejected: duplicates conversion logic)

### Decision 3: Color Query Implementation

**What**: Use SQLAlchemy JSON `.contains()` operator:
```python
stmt = select(CardModel).where(
    CardModel.colors.contains([color])
)
```

**Why**:
- Leverages SQLite JSON1 extension (built-in since SQLite 3.38)
- Efficient for MVP scale (<10K cards)
- Matches Scryfall schema structure

**Alternatives**:
- Normalize colors to separate table (rejected: over-engineering for MVP)
- String search with LIKE (rejected: fragile, error-prone)

### Decision 4: Type Query with Case-Insensitive Substring

**What**: Filter type_line with `.ilike()`:
```python
stmt = select(CardModel).where(
    CardModel.type_line.ilike(f"%{card_type}%")
)
```

**Why**:
- Handles partial matches (e.g., "Instant" matches "Legendary Instant")
- Case-insensitive for UX
- Simple implementation for MVP

**Alternatives**:
- Exact match only (rejected: too restrictive, misses subtypes)
- Regex search (rejected: overkill, performance overhead)

## Risks / Trade-offs

### Risk: SQLite JSON Performance
**Mitigation**:
- Acceptable for MVP scale (<10K cards, <500ms query requirement)
- Add indexes on JSON fields if needed (SQLite supports JSON indexes)
- Monitor query times in integration tests

### Risk: Multi-Face Card Handling
**Mitigation**:
- Document behavior: queries search `card_faces` array if present
- Test cases for double-faced cards (Delver of Secrets, etc.)
- Future: Add explicit face selection parameter if needed

### Trade-off: Simplicity vs. Features
**Decision**: Start with basic queries, add complexity when needed
- No fuzzy matching → exact/partial name search only
- No complex filters → single-attribute queries
- No pagination → return all results (acceptable for MVP)

## Migration Plan

N/A - This is a new capability, no migration required.

## Implementation Notes

### Test Fixture Design
Create diverse test data covering:
- Single-color cards (Red, Blue, etc.)
- Multi-color cards (Azorius, Izzet, etc.)
- Colorless cards (artifacts)
- Multi-face cards (Transform, Modal DFC)
- Various types (Creature, Instant, Sorcery, Enchantment, etc.)

### CLI Test Script Structure
```python
async def main():
    # Initialize database
    engine = create_engine()
    await init_database(engine)

    # Create session and repository
    session_factory = create_session_factory(engine)
    async with get_session(session_factory) as session:
        repo = CardRepository(session)

        # Insert test cards
        # ... (Lightning Bolt, Counterspell, etc.)

        # Demonstrate queries
        print("=== Exact Name Search ===")
        card = await repo.find_by_name_exact("Lightning Bolt")
        print(card)

        # ... (more query demonstrations)
```

## Open Questions

- **Q**: Should color queries support multi-color filtering (e.g., "all red OR blue cards")?
  - **A**: Deferred to future story - start with single-color queries

- **Q**: Do we need pagination for large result sets?
  - **A**: Not for MVP - add when we have >1000 cards in database

# Design: Story 1.2 SQLite Database Setup with SQLAlchemy Models

## Context

Story 1.2 establishes the foundational data persistence layer for Artificial-Planeswalker. This design covers SQLAlchemy 2.0 async ORM models, session management, and database initialization for storing Scryfall card data locally.

**Constraints:**
- Async-first architecture (PydanticAI and Chainlit are async)
- Type safety required (strict mypy)
- Repository pattern for clean layer separation
- SQLite for MVP (zero-config, file-based)
- Support Scryfall card schema with multi-face cards

**Stakeholders:**
- Development team (data layer foundation)
- Future Epic 2-3 (PydanticAI agent tools depend on this layer)

## Goals / Non-Goals

### Goals
- Define SQLAlchemy ORM models for Scryfall card schema
- Configure async session management with proper lifecycle handling
- Establish repository pattern interface for data access
- Create Pydantic schemas for type-safe data transfer
- Enable database initialization and health check validation
- Support multi-face cards (double-faced, split cards)

### Non-Goals
- Implementing query functions (deferred to Story 1.3)
- Scryfall bulk data import (deferred to Story 1.4)
- Alembic migrations (deferred to post-MVP)
- Deck models (deferred to Epic 4)
- Complex indexes or performance optimization (deferred until data imported)

## Research Findings

### Archon RAG Knowledge

#### Source: fastapi.tiangolo.com
**Async Session Management Pattern:**
```python
async def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()
```

**Pydantic ORM Integration:**
- Use `ConfigDict(from_attributes=True)` in Pydantic v2
- Enables parsing SQLAlchemy model instances
- Convert with `PydanticModel.model_validate(sqlalchemy_obj)`

#### Source: scryfall.com
**Card Object Schema (oracle-cards):**
- **Core fields:** id (UUID), oracle_id, name, mana_cost, cmc, type_line, oracle_text
- **Color data:** colors (array), color_identity, color_indicator
- **Legalities:** legalities object mapping format → legality status
- **Multi-face:** card_faces array for DFCs
- **Keywords:** keywords array for ability words
- **Set info:** set, collector_number, rarity

### Additional Research

#### SQLAlchemy 2.0 Async Best Practices (Web Search)
1. **Session Concurrency:** One AsyncSession per asyncio task (not thread-safe)
2. **expire_on_commit=False:** Prevents "IO attempted in unexpected place" errors
3. **AsyncAttrs Mixin:** Enables async attribute access for lazy-loading
4. **Eager Loading:** Use `selectinload()` for relationships to avoid N+1 queries
5. **Context Managers:** Ensure proper session lifecycle with async with

#### SQLAlchemy-Pydantic Patterns (Web Search + Pydantic docs)
- **Architecture:** SQLAlchemy for DB models, Pydantic for schemas/DTOs
- **Repository Pattern:** Return Pydantic schemas from repositories, keep ORM internal
- **Avoid SQLModel:** Not production-ready as of 2025
- **Avoid pydantic-sqlalchemy:** Deprecated in favor of native Pydantic `from_attributes`

## Decisions

### Decision 1: Async SQLAlchemy 2.0 with AsyncSession
**What:** Use SQLAlchemy 2.0 async API with AsyncSession and aiosqlite driver

**Why:**
- PydanticAI and Chainlit are async-first frameworks
- Maintaining async throughout stack prevents blocking I/O
- SQLAlchemy 2.0 provides mature async support
- aiosqlite is the standard async SQLite driver

**Alternatives Considered:**
- **Sync SQLAlchemy:** Would require sync-to-async wrappers, adding complexity and potential deadlocks
- **Raw SQL with aiosqlite:** No ORM benefits, manual mapping, prone to errors
- **TortoiseORM:** Less mature, weaker ecosystem than SQLAlchemy

**Trade-offs:**
- Learning curve for SQLAlchemy 2.0 async patterns
- Must manage AsyncSession lifecycle carefully (one per task)

### Decision 2: Repository Pattern with Pydantic Schemas
**What:** Repositories return Pydantic schemas, keeping SQLAlchemy ORM models internal to data layer

**Why:**
- Clean architectural boundary (ORM implementation detail)
- Type-safe data transfer with Pydantic validation
- Business logic layer has no SQLAlchemy dependencies
- Enables future UI replacement without refactoring logic

**Alternatives Considered:**
- **Expose SQLAlchemy models directly:** Tight coupling, breaks architectural separation
- **SQLModel (hybrid models):** Not production-ready, limited async support, maintenance concerns

**Implementation:**
```python
# Internal ORM model (data/models/card.py)
class CardModel(AsyncAttrs, Base):
    __tablename__ = "cards"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ...

# External schema (data/schemas/card.py)
class Card(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    ...

# Repository (data/repositories/card.py)
class CardRepository:
    async def get_by_id(self, card_id: str) -> Card | None:
        result = await self.session.execute(select(CardModel).where(...))
        model = result.scalar_one_or_none()
        return Card.model_validate(model) if model else None
```

### Decision 3: JSON Columns for Arrays and Objects
**What:** Store `colors`, `keywords`, `legalities`, and `card_faces` as JSON columns

**Why:**
- SQLite JSON support is sufficient for query and storage
- Avoids complex many-to-many relationships for MVP
- Simplifies schema and reduces joins
- Scryfall data already in JSON format

**Alternatives Considered:**
- **Normalized tables:** Over-engineering for MVP, complex migrations, slower queries
- **Text serialization:** No type safety, manual parsing

**Trade-offs:**
- JSON queries less efficient than indexed foreign keys
- Acceptable for MVP scale (<100k cards)
- Can normalize post-MVP if performance requires

### Decision 4: expire_on_commit=False for AsyncSession
**What:** Configure session factory with `expire_on_commit=False`

**Why:**
- Prevents SQLAlchemy from expiring object attributes after commit
- Avoids "IO attempted in unexpected place" errors in async code
- Objects remain usable after commit without refresh queries

**Alternatives Considered:**
- **Default behavior (expire_on_commit=True):** Requires explicit refresh, adds async I/O complexity

**Implementation:**
```python
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # Critical for async usage
)
```

### Decision 5: Skip Alembic Migrations for MVP
**What:** Use SQLAlchemy metadata.create_all() for initial schema creation, no Alembic

**Why:**
- SQLite is file-based, easy to recreate database
- MVP development phase with evolving schema
- Alembic adds complexity without clear MVP benefit
- Can add migrations post-MVP if needed

**Alternatives Considered:**
- **Alembic from start:** Overhead for MVP, slows iteration

**Migration Path:**
- Post-MVP: Initialize Alembic, generate initial migration from existing schema
- Production deployments would use Alembic for schema changes

### Decision 6: Single Card Model (No Separate Tables for Faces)
**What:** Store multi-face cards (DFCs, split cards) in single `cards` table with `card_faces` JSON column

**Why:**
- Simplifies queries (single table scan)
- Matches Scryfall data structure
- Most queries target full card, not individual faces

**Alternatives Considered:**
- **Separate faces table:** Added complexity, requires joins, over-engineering for MVP

**Implementation:**
```python
# card_faces stored as JSON array
card_faces: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
```

## Risks / Trade-offs

### Risk 1: AsyncSession Misuse in Concurrent Tasks
**Risk:** Sharing AsyncSession across concurrent asyncio tasks causes errors

**Mitigation:**
- Document session-per-task pattern clearly
- Use context managers (`async with session`) to enforce scoping
- Unit tests verify proper session lifecycle

**Monitoring:**
- Integration tests with concurrent queries
- Log warnings if session used outside context manager

### Risk 2: JSON Column Query Performance
**Risk:** JSON column queries may be slow at scale (>100k cards)

**Mitigation:**
- SQLite JSON functions support indexed queries (`JSON_EXTRACT`)
- Can add indexes on JSON paths if needed: `CREATE INDEX idx_colors ON cards(json_extract(colors, '$'))`
- Monitor query performance in Story 1.5 validation

**Fallback:**
- Normalize tables post-MVP if performance unacceptable

### Risk 3: Pydantic Validation Overhead
**Risk:** Converting SQLAlchemy models to Pydantic schemas adds CPU overhead

**Mitigation:**
- Pydantic v2 is Rust-based, highly optimized
- Validation overhead negligible compared to I/O
- Can skip validation with `model_construct()` if proven bottleneck

**Monitoring:**
- Performance tests in Story 1.5 (<500ms query target)

## Migration Plan

N/A - This is initial database setup, no existing data to migrate.

**Future Migration Path (Post-MVP):**
1. Initialize Alembic in project
2. Generate baseline migration from current schema
3. Apply migrations in production deployments
4. Use Alembic for future schema changes

## Open Questions

1. **Q:** Should we index `mana_cost`, `type_line`, and `oracle_text` columns for search?
   **A:** Defer to Story 1.3 after implementing queries. Add indexes if tests show performance issues.

2. **Q:** Should we store card images locally or reference Scryfall URLs?
   **A:** Store Scryfall image URIs only (MVP uses text-based UI). Local image caching deferred to post-MVP.

3. **Q:** How to handle Scryfall schema changes (new fields added)?
   **A:** Design models to accept unknown JSON fields gracefully. Scryfall is append-only (no breaking changes). Update models when importing new bulk data in Story 1.4.

4. **Q:** Should we support multiple database backends (PostgreSQL for production)?
   **A:** SQLite only for MVP. AsyncEngine abstraction supports swapping drivers post-MVP without code changes (only connection string differs).

## Implementation Notes

### File Structure
```
src/data/
├── __init__.py
├── database.py          # Engine, session factory, init
├── models/
│   ├── __init__.py
│   ├── base.py          # DeclarativeBase
│   └── card.py          # CardModel ORM
├── schemas/
│   ├── __init__.py
│   └── card.py          # Card Pydantic schema
└── repositories/
    ├── __init__.py
    ├── base.py          # BaseRepository (interface)
    └── card.py          # CardRepository (queries in Story 1.3)

tests/
├── unit/data/
│   ├── test_models.py   # Model validation, constraints
│   └── test_database.py # Session factory, engine creation
└── integration/data/
    └── test_database_integration.py  # Health check (INSERT/SELECT)
```

### Testing Strategy
- **Unit Tests:** Model creation, field validation, Pydantic schema conversion (no DB)
- **Integration Tests:** Database creation, session lifecycle, INSERT/SELECT health check
- **Use in-memory SQLite** (`:memory:`) for fast test execution

### Environment Variables
```bash
# .env (gitignored)
DATABASE_URL=sqlite+aiosqlite:///./data/cards.db  # MVP default
# DATABASE_URL=sqlite+aiosqlite:///:memory:        # For tests
```

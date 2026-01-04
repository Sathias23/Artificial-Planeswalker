# Story 1.2: SQLite Database Setup with SQLAlchemy Models

## Why

**Epic 1 Story 1.2** - Establish the data persistence layer for Artificial-Planeswalker by creating SQLAlchemy ORM models for Scryfall card data, configuring async session management, and setting up SQLite database infrastructure. This enables the application to store and query Magic: The Gathering cards locally without relying on external API calls (NFR1).

The database layer is critical for the MVP's offline-first architecture, providing fast card lookups (<500ms per NFR7) and enabling the PydanticAI agent to perform natural language queries against a local card database.

## What Changes

- **NEW** SQLAlchemy 2.0 async ORM models for Scryfall card schema
- **NEW** Async session management with proper lifecycle handling
- **NEW** Database initialization module for SQLite file creation
- **NEW** Repository pattern foundation (interface only - queries in Story 1.3)
- **NEW** Pydantic schemas for type-safe data transfer
- **NEW** Unit tests for models, sessions, and database health checks

## Impact

### Affected Specs
- **NEW CAPABILITY:** `data-layer` - SQLAlchemy models, session management, and database initialization

### Affected Code
- `src/data/models/` - SQLAlchemy ORM models (Card, multi-face support)
- `src/data/schemas/` - Pydantic schemas for data transfer objects
- `src/data/database.py` - Async engine, session factory, initialization
- `src/data/repositories/` - Repository base classes (queries in Story 1.3)
- `tests/unit/data/` - Unit tests for models and sessions
- `tests/integration/data/` - Integration tests for database operations

### Dependencies
- **uv add**: `sqlalchemy[asyncio]`, `aiosqlite` (async SQLite driver)
- **uv add --dev**: `pytest-asyncio` (async test support)

## Research Summary

### Archon RAG Sources
- **FastAPI docs** (fastapi.tiangolo.com): Pydantic model patterns, async dependency injection
- **Scryfall API** (scryfall.com): Card object schema, bulk data formats

### Key Research Findings

1. **SQLAlchemy 2.0 Async Session Management**
   - AsyncSession per asyncio task (not safe for concurrent tasks)
   - Use `expire_on_commit=False` to prevent detached instance errors
   - AsyncAttrs mixin for lazy-loading relationships
   - Context managers for proper session lifecycle

2. **SQLAlchemy-Pydantic Integration**
   - Pydantic v2: `ConfigDict(from_attributes=True)` enables ORM mode
   - Convert with `PydanticModel.model_validate(sqlalchemy_obj)`
   - Repository pattern: SQLAlchemy internal, Pydantic schemas exposed
   - Avoid SQLModel (not production-ready) and pydantic-sqlalchemy (deprecated)

3. **Scryfall Card Schema** (oracle-cards bulk data)
   - Core fields: `id`, `oracle_id`, `name`, `mana_cost`, `cmc`, `type_line`, `oracle_text`
   - Colors: `colors`, `color_identity`, `color_indicator`
   - Legalities: `legalities` object (Standard/Modern → legal/not_legal/banned/restricted)
   - Multi-face: `card_faces` array for double-faced cards
   - Keywords: `keywords` array, set info, rarity, finishes

4. **Async Session Patterns**
   - Dependency injection with `yield` for session management
   - Pattern: `async def get_db()` with try/yield/finally/close
   - Handle exceptions: catch, rollback, re-raise

### Technical Decisions
- **Async SQLAlchemy 2.0**: Maintains async throughout PydanticAI + Chainlit stack
- **Repository Pattern**: Clean separation between ORM (internal) and schemas (exposed)
- **oracle-cards bulk data**: Smaller file (~165MB), one card per Oracle ID
- **expire_on_commit=False**: Prevents async detached instance errors
- **Skip Alembic for MVP**: SQLite file-based, easy to recreate; add migrations post-MVP

## Validation Criteria

- `openspec validate story-1-2-database-models --strict` passes
- All requirements have at least one scenario
- Spec deltas use proper `## ADDED Requirements` format
- Tasks checklist is comprehensive and actionable

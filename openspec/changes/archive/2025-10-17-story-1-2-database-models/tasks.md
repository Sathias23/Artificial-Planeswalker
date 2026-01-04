# Implementation Tasks: Story 1.2 Database Models

## 1. Project Setup and Dependencies
- [x] 1.1 Add SQLAlchemy dependencies: `uv add 'sqlalchemy[asyncio]' aiosqlite`
- [x] 1.2 Add development dependencies: `uv add --dev pytest-asyncio`
- [x] 1.3 Create `src/data/` directory structure (models/, schemas/, repositories/)
- [x] 1.4 Create `tests/unit/data/` and `tests/integration/data/` directories
- [x] 1.5 Add `.env.example` with `DATABASE_URL=sqlite+aiosqlite:///./data/cards.db`

## 2. SQLAlchemy Base and Engine Configuration
- [x] 2.1 Create `src/data/models/base.py` with DeclarativeBase using AsyncAttrs mixin
- [x] 2.2 Create `src/data/database.py` with async engine creation function
- [x] 2.3 Configure async_sessionmaker with `expire_on_commit=False`
- [x] 2.4 Implement session dependency function with yield (async context manager)
- [x] 2.5 Add DATABASE_URL loading from environment variables
- [x] 2.6 Write unit tests for engine and session factory creation

## 3. Card SQLAlchemy Model
- [x] 3.1 Create `src/data/models/card.py` with CardModel class
- [x] 3.2 Define core fields: id (String PK), name (String, indexed), mana_cost (String)
- [x] 3.3 Define numeric fields: cmc (Float), collector_number (String)
- [x] 3.4 Define text fields: type_line (String), oracle_text (String), rarity (String)
- [x] 3.5 Define JSON fields: colors (JSON array), color_identity (JSON array), color_indicator (JSON array, optional)
- [x] 3.6 Define JSON fields: keywords (JSON array), legalities (JSON object), card_faces (JSON array, optional)
- [x] 3.7 Define set fields: set_code (String), set_name (String), oracle_id (String)
- [x] 3.8 Add __tablename__ = "cards" and proper Mapped[] type hints
- [x] 3.9 Write unit tests for CardModel instantiation and field access

## 4. Pydantic Schemas
- [x] 4.1 Create `src/data/schemas/card.py` with Card Pydantic schema
- [x] 4.2 Add `model_config = ConfigDict(from_attributes=True)` for ORM mode
- [x] 4.3 Define all fields matching CardModel with proper Python types
- [x] 4.4 Use `Optional[]` or `| None` for nullable fields (color_indicator, keywords, card_faces)
- [x] 4.5 Add type hints for JSON fields (colors: list[str], legalities: dict[str, str])
- [x] 4.6 Write unit tests for Card schema validation and model_validate()
- [x] 4.7 Test invalid data raises ValidationError with appropriate messages

## 5. Repository Pattern Base
- [x] 5.1 Create `src/data/repositories/base.py` with BaseRepository class
- [x] 5.2 Define `__init__(self, session: AsyncSession)` constructor
- [x] 5.3 Store session as instance variable
- [x] 5.4 Add type hints and docstrings for base repository interface
- [x] 5.5 Create `src/data/repositories/card.py` with CardRepository class (empty for now)
- [x] 5.6 Write unit tests for BaseRepository initialization

## 6. Database Initialization
- [x] 6.1 Add `init_database(engine: AsyncEngine)` function in `database.py`
- [x] 6.2 Implement async table creation using `metadata.create_all()`
- [x] 6.3 Add logging for database initialization start and completion
- [x] 6.4 Handle errors gracefully (log and raise)
- [x] 6.5 Write integration test for database initialization with in-memory SQLite
- [x] 6.6 Test idempotent initialization (calling twice doesn't fail)

## 7. Health Check Function
- [x] 7.1 Add `health_check(session: AsyncSession)` function in `database.py`
- [x] 7.2 Implement test card INSERT with minimal required fields
- [x] 7.3 Implement test card SELECT by id to verify retrieval
- [x] 7.4 Implement cleanup (DELETE test card after verification)
- [x] 7.5 Return True on success, raise exception on failure
- [x] 7.6 Write integration test for health check with in-memory database
- [x] 7.7 Test health check cleanup leaves database in clean state

## 8. Type Safety Validation
- [x] 8.1 Add type hints to all functions and methods in data layer
- [x] 8.2 Run `mypy src/data/ --strict` and fix all errors
- [x] 8.3 Ensure all SQLAlchemy Mapped[] columns have explicit types
- [x] 8.4 Ensure all Pydantic schema fields have explicit types
- [x] 8.5 Ensure all async functions use proper async/await syntax
- [x] 8.6 Add `py.typed` marker file in `src/data/` for type checking

## 9. Unit Tests
- [x] 9.1 Write `tests/unit/data/test_models.py` for CardModel unit tests
- [x] 9.2 Test CardModel instantiation with required fields
- [x] 9.3 Test CardModel with optional fields (None and provided values)
- [x] 9.4 Test multi-face card with card_faces JSON data
- [x] 9.5 Write `tests/unit/data/test_schemas.py` for Card schema tests
- [x] 9.6 Test Card.model_validate() with SQLAlchemy model instance (mock)
- [x] 9.7 Test Card schema ValidationError on invalid data
- [x] 9.8 Write `tests/unit/data/test_database.py` for session factory tests
- [x] 9.9 Test engine creation with mock DATABASE_URL
- [x] 9.10 Test session factory configuration (expire_on_commit=False)

## 10. Integration Tests
- [x] 10.1 Write `tests/integration/data/test_database_integration.py`
- [x] 10.2 Use pytest fixture to create in-memory SQLite engine and session
- [x] 10.3 Test init_database() creates tables successfully
- [x] 10.4 Test INSERT and SELECT operations with CardModel
- [x] 10.5 Test health_check() function end-to-end
- [x] 10.6 Test health_check() cleanup (no test records left behind)
- [x] 10.7 Test session lifecycle with context manager (async with)
- [x] 10.8 Test SQLAlchemy model to Pydantic schema conversion

## 11. Documentation and Validation
- [x] 11.1 Add docstrings to all public functions and classes
- [x] 11.2 Update main README.md with database setup instructions
- [x] 11.3 Document environment variables (DATABASE_URL)
- [x] 11.4 Run all unit and integration tests: `uv run pytest tests/`
- [x] 11.5 Run mypy: `uv run mypy src/data/ --strict`
- [x] 11.6 Run ruff: `uv run ruff check src/data/ tests/`
- [x] 11.7 Validate OpenSpec proposal: `openspec validate story-1-2-database-models --strict`
- [x] 11.8 Ensure all tests pass and no linting/type errors

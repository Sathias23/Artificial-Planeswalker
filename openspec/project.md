# Project Context

## Purpose

Artificial-Planeswalker is a PydanticAI-powered Magic: The Gathering deck building assistant that provides:
- **Instant Card Lookups**: Natural language card queries against local Scryfall data (no API rate limits)
- **Intelligent Deck Building**: Format-aware (Standard) deck creation with real-time validation
- **Deck Building Intelligence**: Mana curve analysis and synergy detection for cooperative deck construction
- **Offline-First**: Local SQLite database populated from Scryfall bulk data for fast queries
- **Clean Architecture**: UI/logic separation enables future frontend replacement (CopilotKit + AG-UI planned)

**MVP Scope**: Chainlit chat interface for Standard format deck building with basic synergy features.

## Tech Stack

### Core Technologies
- **Python 3.12+** - Modern type hints, PEP 695 generic syntax
- **UV** - Package and environment management (per user preference)
- **PydanticAI 0.0.14+** - AI agent framework with type-safe tool definitions
- **OpenRouter API** - Multi-provider LLM gateway (GPT-4 Turbo primary, Claude 3.5 Sonnet alternative)
- **SQLAlchemy 2.0+** - ORM for type-safe database access
- **SQLite 3.45+** - Local database (zero-config, file-based)
- **Chainlit 1.3+** - Chat UI framework (MVP frontend)
- **httpx 0.27+** - HTTP client for Scryfall bulk data downloads

### Development Tools
- **pytest 8.3+** - Testing framework with asyncio support
- **Ruff 0.6+** - Fast linting and formatting (replaces Black + Flake8 + isort)
- **mypy 1.11+** - Static type checking (strict mode)
- **pre-commit 3.8+** - Git hook management for quality gates

## Project Conventions

### Code Style
- **Line length**: 100 characters
- **Linting/Formatting**: Ruff (configured in pyproject.toml)
- **Type hints**: MANDATORY for all functions (Python 3.12 syntax: `list[Card]` not `List[Card]`)
- **Imports**: Sorted via Ruff (isort compatible)
- **Logging**: Use `logging` module, NEVER `print()` in application code

### Naming Conventions
| Element | Convention | Example |
|---------|-----------|---------|
| Modules | snake_case | `deck_validator.py` |
| Classes | PascalCase | `CardRepository` |
| Functions | snake_case | `validate_deck_construction()` |
| Variables | snake_case | `active_deck_id` |
| Constants | UPPER_SNAKE_CASE | `MAX_CARD_COPIES = 4` |
| Private members | _leading_underscore | `_internal_state` |
| Type aliases | PascalCase | `CardList = list[Card]` |

### Architecture Patterns

**Modular Monolith** - Four-layer architecture in single Python process:

1. **Data Layer** (`src/data/`):
   - Repository pattern for all database access
   - SQLAlchemy ORM models → Pydantic schemas (returned by repositories)
   - No business logic in this layer

2. **Business Logic Layer** (`src/logic/`):
   - Domain rules: deck validation, curve analysis, synergy detection
   - No database or UI dependencies
   - Pure Python with Pydantic model inputs

3. **Agent Core** (`src/agent/`):
   - PydanticAI agent with type-safe tool definitions
   - OpenRouter integration for LLM calls
   - No UI dependencies (enables future UI replacement)

4. **UI Layer** (`src/ui/`):
   - Chainlit chat interface (MVP)
   - Thin layer - delegates to agent
   - No direct database access

**Key Patterns**:
- **Repository Pattern**: All DB queries through repositories returning Pydantic models
- **Tool-Based Agent Architecture**: PydanticAI tools for extensible capabilities
- **Session-Based Context Management**: Chainlit sessions maintain active deck state
- **Dependency Injection**: Repositories injected into agent tools

### Testing Strategy

**Test Pyramid**:
- 70% unit tests (fast, isolated, mocked dependencies)
- 25% integration tests (database, agent workflows)
- 5% manual testing (Chainlit UI, conversation quality)

**Coverage Goals**:
- Business logic (`logic/`): 90%+
- Repositories (`data/repositories/`): 80%+
- Agent tools (`agent/tools/`): 70%+
- UI layer (`ui/`): Manual testing for MVP

**Testing Approach**:
- **Unit Tests**: pytest, AAA pattern (Arrange-Act-Assert), mock external dependencies
- **Integration Tests**: In-memory SQLite (`:memory:`), fixture JSON files for sample data
- **Pre-commit Hooks**: Ruff + mypy + optional pytest unit tests

### Git Workflow

**Branching**: (TBD - typical flow would be feature branches → main)

**Commit Conventions**: (TBD - consider Conventional Commits if desired)

**Pre-commit Quality Gates**:
- Ruff linting and formatting
- mypy strict type checking
- Optional: pytest unit tests

## Domain Context

### Magic: The Gathering Deck Building

**Deck Construction Rules (Standard Format)**:
- Minimum 60 cards in mainboard
- Maximum 4 copies of any card (except basic lands - unlimited)
- All cards must be Standard-legal (checked via Scryfall `legalities` field)
- Sideboard: 0-15 cards (post-MVP feature)

**Card Attributes**:
- **Mana Cost**: e.g., `{2}{R}{R}` (2 generic + 2 red mana)
- **CMC/Mana Value**: Converted mana cost (e.g., 4 for above)
- **Type Line**: "Creature - Dragon", "Instant", "Enchantment - Aura", etc.
- **Colors**: W (white), U (blue), B (black), R (red), G (green), or colorless
- **Keywords**: Haste, Flying, Trample, First Strike, etc.

**Deck Archetypes**:
- **Aggro**: Low mana curve (avg 1-2 CMC), fast creature damage
- **Control**: High removal/counters, late-game win conditions
- **Midrange**: Balanced curve, efficient creatures and interaction
- **Combo**: Specific card combinations for powerful synergies

**Mana Curve**: Distribution of cards by mana value (ideally resembles a bell curve for balanced decks)

**Synergies**: Cards that work well together (e.g., tribal synergies, keyword synergies, sacrifice themes)

### Scryfall Data

**Bulk Data Source**: https://api.scryfall.com/bulk-data
- **oracle-cards**: ~70MB, unique cards only (MVP uses this)
- **default-cards**: ~180MB, all printings

**JSON Schema**: Cards have `id`, `name`, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `colors`, `keywords`, `legalities` (format → legal/not_legal/restricted/banned)

## Important Constraints

### Technical Constraints
- **Offline-First**: All card queries against local database (no Scryfall API calls during queries)
- **Type Safety**: Strict mypy checking throughout codebase
- **UI Abstraction**: Agent layer MUST NOT import Chainlit (enables future UI replacement)
- **Async/Await**: PydanticAI tools and Chainlit handlers are async - maintain async throughout
- **Performance**: Query performance target <500ms (NFR7)

### Business Constraints
- **MVP Format**: Standard only (Modern, Commander deferred to post-MVP)
- **MVP UI**: Chainlit only (CopilotKit + AG-UI deferred)
- **Single-User**: Local development only (no multi-user auth for MVP)
- **Manual Data Updates**: Scryfall bulk data refresh is manual (automated updates post-MVP)

### Security Constraints
- **Secrets Management**: NEVER hardcode API keys - use `.env` file (gitignored)
- **Input Validation**: ALL external inputs validated with Pydantic models
- **SQL Injection Prevention**: SQLAlchemy parameterized queries only
- **Logging**: NEVER log API keys or sensitive data (redact in logs)

## External Dependencies

### Scryfall API (Bulk Data Only)
- **Purpose**: One-time download of MTG card database for local storage
- **Documentation**: https://scryfall.com/docs/api/bulk-data
- **Base URL**: https://api.scryfall.com
- **Authentication**: None required (public API)
- **Rate Limits**: Bulk downloads not rate-limited (large files ~70-180MB)
- **Usage**: One-time setup operation, not during regular application use
- **File Selection**: `oracle-cards` endpoint for MVP (unique cards, smaller size)

### OpenRouter API
- **Purpose**: LLM gateway for PydanticAI agent (multi-model testing)
- **Documentation**: https://openrouter.ai/docs
- **Base URL**: https://openrouter.ai/api/v1
- **Authentication**: Bearer token (`OPENROUTER_API_KEY` env var)
- **Rate Limits**: Varies by model (~200 req/min for GPT-4 Turbo)
- **Models**:
  - Primary: `openai/gpt-4-turbo` (gpt-4-turbo-2024-04-09)
  - Alternative: `anthropic/claude-3.5-sonnet` (claude-3-5-sonnet-20241022)
- **Features**: OpenAI-compatible chat completions, streaming, tool/function calling
- **Error Handling**:
  - 429 Rate Limit: Exponential backoff
  - 401 Auth: Clear error, check API key
  - 503 Unavailable: Fall back to alternative model

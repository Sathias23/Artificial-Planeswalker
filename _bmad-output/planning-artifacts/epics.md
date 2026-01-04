# Artificial-Planeswalker - Epic Breakdown

**Author:** Bradmin
**Date:** 2025-12-07
**Project Level:** MVP
**Target Scale:** Single-user local application

---

## Overview

This document provides the complete epic and story breakdown for Artificial-Planeswalker, decomposing the requirements from the [PRD](./prd.md) into implementable stories with full technical context from [Architecture](./architecture.md).

**Living Document Notice:** This is the implementation-ready version incorporating PRD requirements and Architecture decisions.

### Epic Summary

| Epic | Title | User Value | Stories |
|------|-------|------------|---------|
| 1 | Foundation & Data Infrastructure | Working local card database for instant queries | 5 |
| 2 | PydanticAI Agent Core | AI-powered natural language card lookups | 4 |
| 3 | Chainlit Chat Interface | Conversational web UI for card queries | 4 |
| 4 | Deck Creation and Management | Create, save, and manage Standard decks | 5 |
| 5 | Deck Building Intelligence | Real-time curve analysis and synergy suggestions | 5 |

**Total Stories:** 23

---

## Functional Requirements Inventory

| FR ID | Description | Priority |
|-------|-------------|----------|
| FR1 | Download and store Scryfall bulk data locally in SQL database | Critical |
| FR2 | Natural language card lookup through PydanticAI agent | Critical |
| FR3 | Card queries filtered by Standard format | High |
| FR4 | Deck creation and management for Standard format | Critical |
| FR5 | Deck construction rule validation (60+ cards, max 4 copies) | High |
| FR6 | Mana curve distribution analysis and feedback | Medium |
| FR7 | Card synergy identification and suggestions | Medium |
| FR8 | Deck persistence with CRUD operations | Critical |
| FR9 | Chainlit chat interface for user interactions | Critical |
| FR10 | UI/agent layer separation for future replacement | High |

---

## FR Coverage Map

| FR | Epic 1 | Epic 2 | Epic 3 | Epic 4 | Epic 5 |
|----|--------|--------|--------|--------|--------|
| FR1 | 1.2, 1.4 | - | - | - | - |
| FR2 | - | 2.2, 2.3 | - | - | - |
| FR3 | - | 2.4 | - | - | - |
| FR4 | - | - | - | 4.2, 4.4, 4.5 | - |
| FR5 | - | - | - | 4.3 | 5.5 |
| FR6 | - | - | - | - | 5.1, 5.2 |
| FR7 | - | - | - | - | 5.3, 5.4 |
| FR8 | - | - | - | 4.1, 4.5 | - |
| FR9 | - | - | 3.1, 3.2 | - | - |
| FR10 | 1.1 | 2.1 | 3.2 | - | - |

---

## Epic Structure Plan

### Design Principles Applied

1. **User-Value First**: Each epic enables users to accomplish something meaningful
2. **Leverage Architecture**: Built upon Repository Pattern, Tool-Based Agent, Session Management
3. **Incremental Delivery**: Each epic is independently valuable and testable
4. **Natural Dependencies**: Dependencies flow logically from data → agent → UI → features

### Epic Dependency Graph

```
Epic 1: Foundation & Data Infrastructure
    │
    ▼
Epic 2: PydanticAI Agent Core ◄── Card queries need local DB
    │
    ▼
Epic 3: Chainlit Chat Interface ◄── UI needs agent to invoke
    │
    ▼
Epic 4: Deck Creation & Management ◄── Deck tools need UI context
    │
    ▼
Epic 5: Deck Building Intelligence ◄── Analysis needs deck data
```

### Technical Context Summary

| Epic | Architecture Patterns | Key Components |
|------|----------------------|----------------|
| 1 | Repository Pattern, Bulk Import | SQLAlchemy, CardRepository, Scryfall importer |
| 2 | Tool-Based Agent, Strategy Pattern | PydanticAI, OpenRouter, card_tools.py |
| 3 | Session-Based Context | Chainlit handlers, formatters, session.py |
| 4 | Repository Pattern (Deck) | DeckRepository, DeckValidator, deck_tools.py |
| 5 | Business Logic Layer | CurveAnalyzer, SynergyDetector, analysis_tools.py |

---

## Epic 1: Foundation & Data Infrastructure

**Epic Goal:** Establish project foundation including Python environment, SQLite database with SQLAlchemy ORM, Scryfall bulk data import, and basic card query capabilities.

**User Value:** Users get instant card queries from a local database without API rate limits or network latency.

**FRs Addressed:** FR1, FR10

**Technical Context:**
- Repository Pattern (`src/data/repositories/`)
- SQLAlchemy 2.0+ with Pydantic schema separation
- Bulk Import Pattern for Scryfall JSON
- Four-layer architecture: data → logic → agent → ui

---

### Story 1.1: Project Initialization and Environment Setup

As a **developer**,
I want **a properly configured Python project with UV package management and development tooling**,
So that **I can develop the application with type safety, code quality checks, and consistent dependency management**.

**Acceptance Criteria:**

**Given** a fresh project directory
**When** I run the setup commands
**Then** the following is configured:

- [ ] Project structure created per Architecture Source Tree:
  - `src/data/`, `src/logic/`, `src/agent/`, `src/ui/`
  - `src/config/settings.py`, `src/config/constants.py`
  - `scripts/`, `tests/unit/`, `tests/integration/`
- [ ] UV-based dependency management with `pyproject.toml`
- [ ] Core dependencies installed:
  - `pydantic>=2.9`, `pydanticai>=0.0.14`
  - `sqlalchemy>=2.0`, `chainlit>=1.3`, `httpx>=0.27`
- [ ] Dev dependencies: `pytest>=8.3`, `pytest-asyncio>=0.24`, `mypy>=1.11`, `ruff>=0.6`
- [ ] Pre-commit hooks configured (`.pre-commit-config.yaml`):
  - Ruff linting and formatting
  - mypy type checking
- [ ] `.env.example` created with placeholder values
- [ ] `.gitignore` configured for Python, SQLite, `.env`
- [ ] Git repository initialized
- [ ] All pre-commit hooks pass on initial commit

**Technical Notes:**
- Python 3.12+ required (Architecture: PEP 695 type improvements)
- Use modern type hints: `list[Card]` not `List[Card]`
- Configure `pyproject.toml` per Architecture lines 1039-1078
- Settings module uses `pydantic-settings` for env loading

**Prerequisites:** None (first story)

---

### Story 1.2: SQLite Database Setup with SQLAlchemy Models

As a **developer**,
I want **a SQLite database with SQLAlchemy ORM models for Scryfall card data**,
So that **I can store and query Magic: The Gathering card information efficiently with type safety**.

**Acceptance Criteria:**

**Given** the project structure from Story 1.1
**When** I run the database initialization
**Then** the following exists:

- [ ] SQLAlchemy Card model defined in `src/data/models.py`:
  - `id`: TEXT PRIMARY KEY (Scryfall UUID)
  - `name`: TEXT NOT NULL
  - `mana_cost`: TEXT (nullable for lands)
  - `cmc`: REAL NOT NULL DEFAULT 0.0
  - `type_line`: TEXT NOT NULL
  - `oracle_text`: TEXT
  - `colors`: TEXT (JSON array)
  - `color_identity`: TEXT (JSON array)
  - `keywords`: TEXT (JSON array)
  - `legalities`: TEXT NOT NULL (JSON object)
  - `set_code`: TEXT NOT NULL
  - `rarity`: TEXT NOT NULL
  - `image_uris`: TEXT (JSON object)
- [ ] Pydantic Card schema in `src/data/schemas.py` with `ConfigDict(from_attributes=True)`
- [ ] Database module `src/data/database.py`:
  - `create_engine()` function with SQLite URL
  - `get_session()` context manager
  - `init_database()` function creates tables
- [ ] Indexes created per Architecture schema:
  - `idx_cards_name` (case-insensitive)
  - `idx_cards_cmc`
  - `idx_cards_legalities_standard` (JSON extract)
- [ ] Init script `scripts/init_db.py` creates `data/planeswalker.db`
- [ ] Unit tests verify model definitions and connection
- [ ] Health check test: INSERT card → SELECT card → verify match

**Technical Notes:**
- Use SQLAlchemy 2.0 declarative syntax
- JSON fields use SQLite JSON1 extension
- Database URL from `DATABASE_URL` env var, default `sqlite:///data/planeswalker.db`
- Schema DDL reference: Architecture lines 769-887

**Prerequisites:** Story 1.1

---

### Story 1.3: Basic Card Query Functionality and Validation

As a **developer**,
I want **basic query functions to retrieve cards from the database by name or criteria**,
So that **I can validate the data layer works before bulk import and provide foundation for agent tools**.

**Acceptance Criteria:**

**Given** the database models from Story 1.2
**When** I use the CardRepository
**Then** the following queries work:

- [ ] `CardRepository` class in `src/data/repositories/card_repository.py`
- [ ] Query methods implemented:
  - `search_by_name(name: str) -> Card | None` - exact match (case-insensitive)
  - `search_by_name_partial(query: str) -> list[Card]` - partial match
  - `filter_by_colors(colors: list[str]) -> list[Card]`
  - `filter_by_type(type_query: str) -> list[Card]`
  - `filter_by_format(format: str) -> list[Card]` - JSON legalities check
- [ ] All methods return **Pydantic models**, not SQLAlchemy objects
- [ ] Repository uses injected session (dependency injection pattern)
- [ ] Unit tests cover all query functions:
  - Exact name match
  - Partial name match (multiple results)
  - Color filtering (single and multi-color)
  - Type filtering (creature, instant, sorcery)
  - Format legality filtering
- [ ] Test script `scripts/test_queries.py` demonstrates queries with sample data

**Technical Notes:**
- Repository pattern: Architecture lines 101-110
- Return Pydantic schemas from `schemas.py`
- Use SQLAlchemy `ilike` for case-insensitive search
- JSON queries: `json_extract(legalities, '$.standard') = 'legal'`

**Prerequisites:** Story 1.2

---

### Story 1.4: Scryfall Bulk Data Download and Import

As a **developer**,
I want **a script to download Scryfall bulk data and import it into the local database**,
So that **the application has a complete, up-to-date card database without relying on API calls**.

**Acceptance Criteria:**

**Given** the database and repository from Stories 1.2-1.3
**When** I run the import script
**Then** the following happens:

- [ ] Import script at `scripts/import_scryfall.py`
- [ ] Script downloads from Scryfall bulk data API:
  - GET `https://api.scryfall.com/bulk-data` for URLs
  - Download `oracle-cards` JSON (~70MB)
- [ ] Download features:
  - Streaming download with httpx (10MB chunks)
  - Progress logging every 10MB
  - Exponential backoff retry (3 retries, max 30s)
  - 60s timeout for large file
- [ ] JSON parsing:
  - Stream-parse with memory efficiency (ijson or chunked)
  - Transform to Card Pydantic models
  - Handle missing optional fields gracefully
- [ ] Bulk insert:
  - Batch size 1000 cards per commit
  - INSERT OR REPLACE for duplicate handling
  - Transaction rollback on errors
- [ ] Completion logging:
  - Cards imported count
  - Time elapsed
  - Import rate (cards/second)
- [ ] Temporary JSON file cleanup after import
- [ ] Runnable via `uv run scripts/import_scryfall.py`

**Technical Notes:**
- Scryfall JSON schema: Architecture lines 521-538
- Use `oracle-cards` endpoint (unique cards only, smaller)
- Bulk import workflow: Architecture lines 576-608
- Map Scryfall fields to Card model carefully

**Prerequisites:** Story 1.3

---

### Story 1.5: End-to-End Data Layer Validation

As a **developer**,
I want **a comprehensive smoke test that validates the complete data layer pipeline**,
So that **I can confirm Epic 1 is fully functional before proceeding to Epic 2**.

**Acceptance Criteria:**

**Given** the complete data layer from Stories 1.1-1.4
**When** I run the validation script
**Then** all checks pass:

- [ ] Validation script at `scripts/validate_data_layer.py`
- [ ] Test database created (separate from main DB)
- [ ] Import validation:
  - Import minimum 100 sample cards
  - Verify card count matches expected
- [ ] Query validation:
  - Search by exact name: "Lightning Bolt" → 1 result
  - Search partial name: "Lightning" → multiple results
  - Filter by color: "R" (red) → red cards only
  - Filter by type: "Instant" → instants only
  - Filter by format: "standard" → Standard-legal only
- [ ] Performance validation:
  - Each query < 500ms (NFR7)
  - Log actual query times
- [ ] Output summary report:
  ```
  ✓ Database initialized
  ✓ 100 cards imported
  ✓ Exact name search: PASS (12ms)
  ✓ Partial name search: PASS (45ms)
  ✓ Color filter: PASS (38ms)
  ✓ Type filter: PASS (41ms)
  ✓ Format filter: PASS (52ms)
  ✓ All queries under 500ms

  EPIC 1 VALIDATION: PASSED
  ```
- [ ] Test database cleanup after validation
- [ ] Runnable via `uv run scripts/validate_data_layer.py`

**Technical Notes:**
- Use in-memory SQLite for speed, or temp file for debugging
- Sample cards fixture in `tests/fixtures/sample_cards.json`
- This is the GATE for Epic 1 - must pass before Epic 2

**Prerequisites:** Stories 1.1-1.4

---

### Epic 1 Summary

| Story | Title | FRs | Key Deliverables |
|-------|-------|-----|------------------|
| 1.1 | Project Initialization | FR10 | UV config, pre-commit, directory structure |
| 1.2 | Database Setup | FR1 | SQLAlchemy models, Pydantic schemas, init script |
| 1.3 | Query Functionality | FR1 | CardRepository with 5 query methods |
| 1.4 | Scryfall Import | FR1 | Bulk download and import script |
| 1.5 | E2E Validation | FR1 | Smoke test validating full pipeline |

**Epic 1 Complete Criteria:**
- All 5 stories implemented and tested
- Story 1.5 validation passes 100%
- Pre-commit hooks pass
- Ready to proceed to Epic 2

---

## Epic 2: PydanticAI Agent Core with Card Query Tools

**Epic Goal:** Implement the PydanticAI agent with OpenRouter integration and tool definitions for natural language card lookups and format-aware queries.

**User Value:** Users can ask natural language questions about MTG cards and receive intelligent, accurate answers from the local database.

**FRs Addressed:** FR2, FR3, FR10

**Technical Context:**
- Tool-Based Agent Architecture (`src/agent/tools/`)
- Strategy Pattern for LLM provider abstraction (OpenRouter)
- PydanticAI typed tool definitions
- Agent has NO UI dependencies (enables future UI replacement)

---

### Story 2.1: PydanticAI Agent Setup with OpenRouter Integration

As a **developer**,
I want **a PydanticAI agent configured to use OpenRouter as the LLM backend**,
So that **I can test different AI models and leverage the agent framework for tool-based card queries**.

**Acceptance Criteria:**

**Given** the project foundation from Epic 1
**When** I configure and run the agent
**Then** the following works:

- [ ] Agent configuration in `src/agent/config.py`:
  - Load `OPENROUTER_API_KEY` from environment
  - Load `OPENROUTER_MODEL` with default `openai/gpt-4-turbo`
  - Support alternative models: `anthropic/claude-3.5-sonnet`
- [ ] PydanticAI agent in `src/agent/planeswalker_agent.py`:
  - Agent instance created with OpenRouter provider
  - System prompt establishes MTG deck building assistant persona
  - Agent configured for tool calling
- [ ] OpenRouter integration:
  - Use OpenAI-compatible endpoint (`https://openrouter.ai/api/v1`)
  - Bearer token authentication
  - Streaming response support
- [ ] Error handling:
  - 401 Unauthorized → clear API key error message
  - 429 Rate Limit → exponential backoff retry
  - 503 Unavailable → fallback model if configured
- [ ] Basic test:
  - Agent responds to "Hello" with greeting
  - Agent responds to MTG question without tools (baseline)
- [ ] Unit tests verify agent initialization
- [ ] Integration test validates OpenRouter communication

**Technical Notes:**
- OpenRouter API details: Architecture lines 543-572
- PydanticAI uses OpenAI-compatible format natively
- Store API key in `.env`, never in code
- 30s timeout per LLM request

**Prerequisites:** Epic 1 complete (Story 1.5 passes)

---

### Story 2.2: Card Lookup Tool Implementation

As a **user**,
I want **to ask the agent for specific cards by name using natural language**,
So that **I can quickly find card details without memorizing exact card names**.

**Acceptance Criteria:**

**Given** the agent from Story 2.1 and CardRepository from Epic 1
**When** I ask about a card by name
**Then** the agent finds and returns card details:

- [ ] Tool defined in `src/agent/tools/card_tools.py`:
  ```python
  @agent.tool
  async def lookup_card(name: str) -> CardResult:
      """Find a Magic: The Gathering card by name."""
  ```
- [ ] Tool behavior:
  - Exact match first, then partial match fallback
  - Returns structured card data (name, mana cost, type, oracle text, colors)
  - Handles multiple matches with disambiguation
- [ ] CardRepository injected via PydanticAI dependency injection
- [ ] Natural language queries work:
  - "Show me Lightning Bolt" → finds Lightning Bolt
  - "What is Black Lotus?" → finds Black Lotus
  - "Find Sheoldred" → finds Sheoldred, the Apocalypse
- [ ] Partial match handling:
  - "Lightning" → returns top 5 matches, asks for clarification
  - "Jace" → returns Jace planeswalkers, asks which one
- [ ] Not found handling:
  - "Find Lightening Bolt" → "No exact match. Did you mean 'Lightning Bolt'?"
- [ ] Unit tests:
  - Exact name match
  - Partial name match with multiple results
  - Card not found
- [ ] Integration test: agent + tool + database flow

**Technical Notes:**
- Tool pattern: Architecture lines 112-122
- Return Pydantic `CardResult` model, not raw dict
- Tool receives CardRepository via `RunContext`
- Log tool invocations for debugging

**Prerequisites:** Story 2.1

---

### Story 2.3: Advanced Card Search Tool (Filters and Criteria)

As a **user**,
I want **to search for cards using complex criteria like color, type, mana cost, and keywords**,
So that **I can discover cards that match my deck building needs**.

**Acceptance Criteria:**

**Given** the agent with card lookup from Story 2.2
**When** I describe card criteria in natural language
**Then** the agent finds matching cards:

- [ ] Tool defined in `src/agent/tools/card_tools.py`:
  ```python
  @agent.tool
  async def search_cards(
      colors: list[str] | None = None,
      card_types: list[str] | None = None,
      min_cmc: int | None = None,
      max_cmc: int | None = None,
      keywords: list[str] | None = None,
      text_contains: str | None = None,
  ) -> CardSearchResult:
      """Search for cards matching multiple criteria."""
  ```
- [ ] Filter combinations work:
  - Colors: "R" (red), "U,B" (blue and black), colorless
  - Types: "creature", "instant", "sorcery", "enchantment", "artifact", "land"
  - CMC range: min/max mana value
  - Keywords: "haste", "flying", "trample", etc.
  - Text search: oracle text contains phrase
- [ ] Natural language interpretation:
  - "red creatures with haste under 4 mana" → colors=["R"], types=["creature"], keywords=["haste"], max_cmc=3
  - "blue instant draw spells" → colors=["U"], types=["instant"], text_contains="draw"
  - "colorless artifacts" → colors=[], types=["artifact"]
- [ ] Result handling:
  - Return top 10 matches with pagination hint
  - "Found 47 cards matching criteria. Showing top 10..."
  - Include total count for user awareness
- [ ] Edge cases:
  - No results → helpful message with relaxed criteria suggestion
  - Too broad → "Found 500+ results. Try adding more filters."
- [ ] Unit tests: filter combinations, natural language parsing
- [ ] Integration test: complex queries against real card data

**Technical Notes:**
- Build on CardRepository query methods from Story 1.3
- May need new repository method for combined filters
- LLM interprets natural language → structured tool parameters
- Consider caching frequent queries

**Prerequisites:** Story 2.2

---

### Story 2.4: Standard Format Filtering Tool

As a **user**,
I want **card searches to be automatically filtered for Standard format legality**,
So that **I only see cards I can use in Standard decks**.

**Acceptance Criteria:**

**Given** the search tools from Stories 2.2-2.3
**When** I search for cards
**Then** format filtering is applied:

- [ ] Tool for setting format context:
  ```python
  @agent.tool
  async def set_format_filter(format: str | None) -> str:
      """Set the format filter for card searches. Use 'standard', 'modern', etc., or None for all cards."""
  ```
- [ ] Session-level format state:
  - Format filter stored in agent context/session
  - Persists across queries within conversation
  - Default: Standard format enabled
- [ ] All card tools respect format filter:
  - `lookup_card` → only returns Standard-legal matches
  - `search_cards` → filters results by format legality
- [ ] User feedback:
  - "Searching Standard-legal cards only..."
  - "Lightning Bolt is not legal in Standard" (if searching banned card)
- [ ] Opt-out capability:
  - "Show me all cards, not just Standard" → clears filter
  - "Search Modern format" → switches format
  - "Include banned cards" → temporary filter bypass
- [ ] Legality data from `legalities` JSON field:
  - Check `json_extract(legalities, '$.standard') = 'legal'`
  - Handle "not_legal", "banned", "restricted" values
- [ ] Unit tests: format filtering logic
- [ ] Integration test: Standard filter applied to searches

**Technical Notes:**
- Format filter stored in agent RunContext or session state
- CardRepository already has `filter_by_format()` from Story 1.3
- Standard is MVP focus; other formats (Modern, Commander) extensible
- Clear UI indication when format filter is active

**Prerequisites:** Story 2.3

---

### Epic 2 Summary

| Story | Title | FRs | Key Deliverables |
|-------|-------|-----|------------------|
| 2.1 | Agent Setup | FR10 | PydanticAI + OpenRouter config, error handling |
| 2.2 | Card Lookup Tool | FR2 | `lookup_card` tool with fuzzy matching |
| 2.3 | Advanced Search Tool | FR2 | `search_cards` with multi-filter support |
| 2.4 | Format Filtering | FR3 | Session-based Standard filter for all queries |

**Epic 2 Complete Criteria:**
- Agent responds to natural language card queries
- All 3 card tools functional and tested
- Standard format filtering works by default
- Agent testable without UI (FR10)
- Ready to proceed to Epic 3

---

## Epic 3: Chainlit Chat Interface Integration

**Status:** ✅ COMPLETED

See PRD for original stories. Implementation complete in `src/ui/`.

---

## Epic 4: Deck Creation and Management

**Status:** ✅ COMPLETED

See PRD for original stories. Implementation complete with DeckRepository, deck tools, and sidebar integration.

---

## Epic 5: Deck Building Intelligence (Curve & Synergy)

**Epic Goal:** Enhance the deck building experience with real-time mana curve analysis and synergy detection to guide cooperative deck construction.

**User Value:** Users receive intelligent, proactive feedback on their deck's mana curve and card synergies, transforming the assistant into a true deck building partner.

**FRs Addressed:** FR6, FR7

**Technical Context:**
- Business Logic Layer (`src/logic/mana_curve.py`, `src/logic/synergy.py`)
- Analysis tools (`src/agent/tools/analysis_tools.py`)
- Automatic feedback system with throttling
- LLM-hybrid synergy suggestions

---

### Story 5.1: Mana Curve Analysis Tool

As a **user**,
I want **the agent to analyze my deck's mana curve and provide feedback**,
So that **I can build a balanced deck with appropriate mana distribution**.

**Acceptance Criteria:**

**Given** an active deck with cards
**When** I ask "analyze my mana curve"
**Then** the agent provides curve analysis:

- [ ] `CurveAnalyzer` class in `src/logic/mana_curve.py`:
  - Calculate CMC distribution (0, 1, 2, 3, 4, 5, 6, 7+)
  - Compute average CMC
  - Identify curve shape (aggro, midrange, control)
- [ ] `analyze_deck_mana_curve` tool in `src/agent/tools/analysis_tools.py`
- [ ] Curve insights provided:
  - "Your average CMC is 2.3 - aggressive curve"
  - "Top-heavy: 40% of spells cost 4+ mana"
  - "Missing early plays: only 2 one-drops"
- [ ] Archetype-aware feedback:
  - Aggro decks: encourage low CMC, warn on high CMC
  - Control decks: validate early interaction + late-game finishers
  - Midrange: balanced 2-4 CMC curve
- [ ] Text-based curve visualization in chat
- [ ] Unit tests for curve calculation logic

**Technical Notes:**
- Reference: CLAUDE.md `src/logic/mana_curve.py`
- CurveAnalyzer should be stateless, receive deck as input
- Return structured `CurveAnalysis` Pydantic model

**Prerequisites:** Epic 4 (deck with cards exists)

**Status:** ✅ COMPLETE

**Verification:**
- ✅ `analyze_mana_curve()` in `src/logic/mana_curve.py` (lines 58-119)
- ✅ `analyze_deck_mana_curve` tool in `src/agent/tools/mana_curve.py`
- ✅ `ManaCurveAnalysis` dataclass with distribution, issues, recommendations
- ✅ CMC distribution (0-7+), average CMC, land ratio
- ✅ Issue detection: top-heavy, mana screw/flood, curve gaps
- ✅ Text-based visualization in chat output

---

### Story 5.2: Automatic Curve Feedback During Deck Building

As a **user**,
I want **the agent to automatically comment on curve impact when I add cards**,
So that **I receive real-time guidance without explicitly asking**.

**Acceptance Criteria:**

**Given** auto-feedback is enabled (default)
**When** I add a card to my deck
**Then** I receive contextual curve feedback:

- [ ] Proactive feedback system in `src/logic/mana_curve.py:generate_contextual_feedback()`
- [ ] Throttling strategy to avoid fatigue:
  - Always show for first 4 cards (establishing curve)
  - Trigger when CMC distribution shifts > 15%
  - Trigger when curve problems detected
- [ ] Feedback types:
  - **Positive:** "Great addition! Strong early-game presence"
  - **Warning:** "Deck getting top-heavy - consider 1-3 mana plays"
  - **Neutral:** "Curve remains balanced"
- [ ] Archetype inference from average CMC
- [ ] `toggle_auto_feedback` tool to enable/disable
- [ ] Session persistence of preference
- [ ] Conversational tone (suggestive, not prescriptive)

**Technical Notes:**
- Reference: CLAUDE.md "Automatic Curve Feedback" section
- Feedback generated in tool layer, displayed by UI
- Don't spam user - throttle intelligently

**Prerequisites:** Story 5.1

**Status:** ✅ COMPLETE

**Verification:**
- ✅ `generate_contextual_feedback()` in `src/logic/mana_curve.py` (lines 243-354)
- ✅ `CurveFeedback` dataclass with message, feedback_type, triggered_by, should_display
- ✅ Throttling: first 5 cards, >15% CMC shift, problem detection
- ✅ Feedback types: positive, warning, neutral
- ✅ Archetype inference: aggro (≤2.5), midrange (2.5-3.5), control (>3.5)
- ✅ `toggle_auto_feedback` tool in `src/agent/tools/preferences.py`
- ✅ Session persistence via `AgentDependencies.set_auto_feedback_enabled()`

---

### Story 5.3: Basic Synergy Detection

As a **user**,
I want **the agent to identify card synergies within my deck**,
So that **I can build more cohesive and powerful decks**.

**Acceptance Criteria:**

**Given** a deck with multiple cards
**When** I ask "what synergies does my deck have?"
**Then** the agent identifies patterns:

- [ ] `SynergyDetector` class in `src/logic/synergy.py`
- [ ] Pattern detection types:
  - **Tribal:** "8 Goblins - strong tribal synergy"
  - **Keyword:** "6 creatures with flying"
  - **Mechanic combos:** "Sacrifice synergy with 4 sacrifice outlets"
- [ ] `detect_deck_synergies` tool returns structured synergy report
- [ ] Synergy explanations:
  - Why cards work together
  - Which cards are the synergy payoffs
  - Which cards enable the synergy
- [ ] Handle no synergies gracefully:
  - "No strong synergies detected. Consider focusing on a theme."
- [ ] Unit tests for pattern recognition

**Technical Notes:**
- Rule-based pattern matching for MVP (not ML)
- Analyze card types, subtypes, keywords, oracle text
- Return `SynergyReport` Pydantic model with `has_synergies` flag

**Prerequisites:** Epic 4

**Status:** ✅ COMPLETE

**Verification:**
- ✅ `detect_synergies()` in `src/logic/synergy.py` (lines 80-113)
- ✅ `SynergyPattern` model with pattern_type, subtype, affected_cards, explanation, strength
- ✅ `SynergyAnalysis` model with synergies list and deck_cohesion
- ✅ Tribal detection: `_detect_tribal_synergies()` (creature types + payoffs)
- ✅ Keyword detection: `_detect_keyword_synergies()` (flying, lifelink, etc.)
- ✅ Mechanic combos: sacrifice, graveyard, card_draw patterns
- ✅ `detect_deck_synergies` tool in `src/agent/tools/synergy_detection.py`
- ✅ Returns structured dict with `has_synergies` for UI action buttons

---

### Story 5.4: Proactive Synergy Suggestions

As a **user**,
I want **the agent to suggest cards that synergize with my current deck**,
So that **I can discover cards I might not have considered**.

**Acceptance Criteria:**

**Given** a deck with identified synergies
**When** I ask "suggest cards for my deck"
**Then** the agent recommends synergistic cards:

- [ ] `suggest_synergy_cards` tool with LLM-hybrid approach
- [ ] Suggestion process:
  1. Detect current deck themes/synergies
  2. Query database for cards matching themes
  3. Use LLM to curate and explain top suggestions
- [ ] Suggestions are:
  - Standard-legal (respect format filter)
  - Not already in deck
  - Contextually relevant to strategy
- [ ] Explanation for each suggestion:
  - "Goblin Chainwhirler - tribal synergy + board presence"
  - "Claim the Firstborn - enables sacrifice theme"
- [ ] Limit to 5-7 suggestions to avoid overwhelming
- [ ] Quick-add action buttons in UI (Chainlit actions)
- [ ] Performance: ~5-10 seconds acceptable for LLM call

**Technical Notes:**
- Reference: CLAUDE.md "Synergy Quick-Add" actions
- LLM evaluates card fit, not just pattern matching
- Cache suggestions per deck state to avoid repeated LLM calls

**Prerequisites:** Story 5.3

**Status:** ❌ NOT IMPLEMENTED (OpenSpec proposal exists)

**Verification:**
- ❌ `suggest_synergy_cards` tool does NOT exist in codebase
- ⚠️ OpenSpec proposal exists: `openspec/changes/add-llm-card-suggestions/`
- ⚠️ Design complete: 3-stage LLM-hybrid workflow (analysis → search → curation)
- ❌ Implementation not started

**Gap:** This story requires implementation via the OpenSpec proposal.

---

### Story 5.5: Deck Validation and Improvement Recommendations

As a **user**,
I want **the agent to validate my deck is complete and suggest improvements**,
So that **I can finalize a competitive, well-rounded deck**.

**Acceptance Criteria:**

**Given** a deck in progress
**When** I ask "is my deck ready?" or "review my deck"
**Then** the agent provides comprehensive validation:

- [ ] Validation checks:
  - Minimum 60 cards (Standard)
  - Maximum 4 copies per non-basic card
  - All cards Standard-legal
  - Reasonable land count (typically 20-26)
- [ ] Issue detection:
  - "Only 18 lands - consider adding 2-4 more"
  - "No removal spells - vulnerable to threats"
  - "Missing win condition - how do you close games?"
- [ ] Prioritized recommendations:
  1. Critical issues (illegal deck)
  2. Major concerns (too few lands)
  3. Suggestions (synergy improvements)
- [ ] Formatted report in chat:
  ```
  📋 Deck Review: Mono Red Aggro

  ✅ 60 cards (valid)
  ✅ All cards Standard-legal
  ⚠️ 18 lands (recommend 20-22 for aggro)
  ⚠️ No interaction spells

  Recommendations:
  1. Add 2-3 Mountains
  2. Consider Lightning Strike for removal
  ```
- [ ] Integration with curve and synergy analysis

**Technical Notes:**
- Combine DeckValidator, CurveAnalyzer, SynergyDetector
- Validation rules in `src/logic/format_rules.py`
- Return structured `DeckValidationReport`

**Prerequisites:** Stories 5.1-5.4

**Status:** ⚠️ PARTIAL (card addition validation only)

**Verification:**
- ✅ `validate_card_addition()` in `src/logic/deck_validator.py` - max 4 copies rule
- ✅ `is_basic_land()` - basic land exemption
- ✅ `get_current_card_count()` - mainboard card counting
- ❌ No 60-card minimum validation tool
- ❌ No land count recommendation tool
- ❌ No "deck review" tool combining curve + synergy + validation
- ❌ No missing removal/win condition detection

**Gap:** Need a comprehensive `review_deck` tool that combines all analyses.

---

### Epic 5 Summary

| Story | Title | FRs | Status |
|-------|-------|-----|--------|
| 5.1 | Mana Curve Analysis | FR6 | ✅ Complete |
| 5.2 | Auto Curve Feedback | FR6 | ✅ Complete |
| 5.3 | Synergy Detection | FR7 | ✅ Complete |
| 5.4 | Synergy Suggestions | FR7 | ❌ Not Implemented |
| 5.5 | Deck Validation | FR5, FR6, FR7 | ⚠️ Partial |

**Epic 5 Status: 60% Complete (3/5 stories)**

**Completed:**
- ✅ 5.1: Full mana curve analysis with issues/recommendations
- ✅ 5.2: Contextual auto-feedback with throttling
- ✅ 5.3: Tribal, keyword, and mechanic synergy detection

**Gaps to Address:**
- ❌ 5.4: `suggest_synergy_cards` tool (OpenSpec proposal ready)
- ⚠️ 5.5: Comprehensive deck review tool needed

---

## FR Coverage Matrix

| FR | Description | Stories | Status |
|----|-------------|---------|--------|
| FR1 | Scryfall bulk data in local DB | 1.2, 1.4 | ✅ Complete |
| FR2 | Natural language card lookup | 2.2, 2.3 | ✅ Complete |
| FR3 | Standard format filtering | 2.4 | ✅ Complete |
| FR4 | Deck creation and management | 4.2, 4.4, 4.5 | ✅ Complete |
| FR5 | Deck construction validation | 4.3, 5.5 | ⚠️ Partial (4-copy rule only) |
| FR6 | Mana curve analysis | 5.1, 5.2 | ✅ Complete |
| FR7 | Synergy identification | 5.3, 5.4 | ⚠️ Partial (5.4 not implemented) |
| FR8 | Deck persistence (CRUD) | 4.1, 4.5 | ✅ Complete |
| FR9 | Chainlit chat interface | 3.1, 3.2 | ✅ Complete |
| FR10 | UI/agent separation | 1.1, 2.1, 3.2 | ✅ Complete |

**Coverage:** 8/10 FRs fully complete, 2 FRs partially complete

---

## Summary

This epic breakdown documents Artificial-Planeswalker's transition to BMAD workflow management.

**Completed Epics (1-4):** Foundation, Agent, UI, Deck Management - all implemented and working.

**Epic 5 Status:** 60% Complete (3/5 stories fully implemented)

### Verified Implementation

| Story | Status | Key Components |
|-------|--------|----------------|
| 5.1 | ✅ | `analyze_mana_curve()`, `ManaCurveAnalysis`, issue detection |
| 5.2 | ✅ | `generate_contextual_feedback()`, throttling, `toggle_auto_feedback` |
| 5.3 | ✅ | `detect_synergies()`, tribal/keyword/mechanic detection |
| 5.4 | ❌ | OpenSpec proposal ready, implementation not started |
| 5.5 | ⚠️ | 4-copy validation exists, no comprehensive review tool |

### Remaining Work

1. **Story 5.4: Synergy Suggestions** - Implement via OpenSpec proposal at `openspec/changes/add-llm-card-suggestions/`
2. **Story 5.5: Deck Review Tool** - Create comprehensive `review_deck` tool combining:
   - 60-card minimum check
   - Land count validation
   - Curve + synergy analysis integration
   - Missing archetypes detection (removal, win cons)

---

_Generated via BMAD Method workflow. Verified 2025-12-07._


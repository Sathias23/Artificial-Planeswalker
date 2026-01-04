# Artificial-Planeswalker Project Documentation

> **AI-powered Magic: The Gathering deck-building assistant**
>
> Generated: 2025-12-07 | Scan Type: Exhaustive | Project Type: Backend (Python)

---

## Quick Reference

| Property | Value |
|----------|-------|
| **Language** | Python 3.12+ |
| **Framework** | PydanticAI 1.0+ |
| **Database** | SQLite + SQLAlchemy 2.0 (async) |
| **UI** | Chainlit 2.8+ |
| **LLM Providers** | Anthropic API (primary), OpenRouter (fallback) |
| **Architecture** | Four-layer modular monolith |

---

## Project Structure

```
Artificial-Planeswalker/
├── src/                          # Main source code
│   ├── agent/                    # AI Agent Layer
│   │   ├── core.py               # Agent factory, session management
│   │   ├── config.py             # Environment configuration
│   │   ├── dependencies.py       # Dependency injection container
│   │   ├── errors.py             # Custom exception hierarchy
│   │   ├── retry.py              # Exponential backoff retry
│   │   └── tools/                # PydanticAI tools
│   │       ├── card_lookup.py    # lookup_card_by_name
│   │       ├── card_search.py    # search_cards_advanced
│   │       ├── deck_tools.py     # Deck CRUD operations
│   │       ├── mana_curve.py     # analyze_deck_mana_curve
│   │       ├── synergy_detection.py  # detect_deck_synergies
│   │       ├── format_filter.py  # set_format_filter
│   │       ├── games_filter.py   # set_games_filter
│   │       ├── preferences.py    # toggle_auto_feedback
│   │       └── bug_report.py     # report_bug
│   │
│   ├── data/                     # Data Layer
│   │   ├── database.py           # Engine, session factory, init
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── base.py           # Base class with MappedAsDataclass
│   │   │   ├── card.py           # CardModel
│   │   │   ├── deck.py           # DeckModel
│   │   │   └── deck_card.py      # DeckCardModel (association)
│   │   ├── schemas/              # Pydantic schemas
│   │   │   ├── card.py           # Card schema
│   │   │   ├── deck.py           # Deck, DeckCard schemas
│   │   │   └── pagination.py     # PaginatedResult[T]
│   │   ├── repositories/         # Repository pattern
│   │   │   ├── base.py           # BaseRepository
│   │   │   ├── card.py           # CardRepository
│   │   │   └── deck.py           # DeckRepository
│   │   └── importers/            # Data import
│   │       └── scryfall.py       # Bulk data importer
│   │
│   ├── logic/                    # Business Logic Layer
│   │   ├── deck_validator.py     # Deck validation rules
│   │   ├── mana_curve.py         # Curve analysis, feedback
│   │   └── synergy.py            # Synergy detection patterns
│   │
│   └── ui/                       # UI Layer (Chainlit)
│       ├── app.py                # Main entry point
│       ├── formatters.py         # Card formatting, hover
│       ├── symbols.py            # Mana symbol rendering
│       ├── action_callbacks.py   # Action button infrastructure
│       ├── handlers/             # Message/signal handlers
│       │   ├── message_handler.py
│       │   └── signal_handlers.py
│       ├── actions/              # Interactive action callbacks
│       │   ├── card_actions.py
│       │   ├── deck_actions.py
│       │   ├── filter_actions.py
│       │   └── pagination_actions.py
│       └── components/           # UI components
│           └── sidebar.py        # Deck sidebar
│
├── tests/                        # Test suite
│   ├── unit/                     # Fast, isolated tests
│   │   ├── agent/
│   │   ├── data/
│   │   └── logic/
│   └── integration/              # Database/API tests
│       ├── agent/
│       └── data/
│
├── scripts/                      # Utility scripts
│   ├── import_scryfall_data.py   # Card data import
│   └── manage_bug_reports.py     # Bug report CLI
│
├── docs/                         # Documentation
├── data/                         # SQLite database
├── public/                       # Static assets (CSS, JS)
└── openspec/                     # Change proposals
```

---

## Architecture Overview

### Four-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     UI Layer (Chainlit)                     │
│  app.py → handlers/ → actions/ → components/                │
│  - Chat interface, actions, sidebar                         │
│  - NO direct database access                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agent Layer (PydanticAI)                │
│  core.py → tools/ → dependencies.py                         │
│  - Tool definitions, session management                     │
│  - Conversation history, context injection                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Business Logic Layer                        │
│  mana_curve.py, synergy.py, deck_validator.py               │
│  - Pure Python, no I/O dependencies                         │
│  - Input: Pydantic models                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
│  repositories/ → models/ → database.py                       │
│  - SQLAlchemy async, Repository pattern                     │
│  - Returns Pydantic schemas (NOT ORM objects)               │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Repository returns Pydantic | Type-safe boundaries, auto-serialization |
| Async throughout | Chainlit is async-first, prevents blocking |
| UI layer thin | Enables UI replacement without agent changes |
| Session-based state | Filters, active deck persist per session |
| Dual LLM providers | Anthropic for Claude (reliable), OpenRouter for fallback |

---

## Data Models

### Card (Scryfall Data)

```python
# ORM Model: src/data/models/card.py
class CardModel(Base):
    id: str                     # Scryfall UUID (primary key)
    name: str                   # Card name (indexed)
    printed_name: str | None    # Alternate name (OM1 cards)
    oracle_id: str              # Oracle ID for deduplication
    mana_cost: str              # e.g., "{2}{R}{R}"
    cmc: float                  # Converted mana cost
    type_line: str              # e.g., "Creature — Goblin"
    oracle_text: str            # Rules text
    rarity: str                 # common, uncommon, rare, mythic
    colors: list[str]           # ["R", "G"] - JSON
    color_identity: list[str]   # Commander identity
    keywords: list[str]         # ["Haste", "Trample"]
    legalities: dict[str, str]  # {"standard": "legal", ...}
    card_faces: list[dict]      # Multi-face card data
    image_uris: dict[str, str]  # Scryfall CDN URLs
    games: list[str]            # ["paper", "arena", "mtgo"]
```

### Deck

```python
# ORM Model: src/data/models/deck.py
class DeckModel(Base):
    id: str                     # UUID (auto-generated)
    name: str                   # Deck name (indexed)
    format: str                 # "standard", "modern", etc.
    strategy: str | None        # Deck strategy description
    color_identity: str         # JSON: ["W", "R"]
    tags: str                   # JSON: ["aggro", "burn"]
    created_at: datetime        # Auto-managed
    updated_at: datetime        # Auto-managed
    deck_cards: list[DeckCardModel]  # Relationship
```

---

## Repository Methods

### CardRepository

| Method | Description |
|--------|-------------|
| `find_by_name_exact(name, format_filter, games)` | Case-insensitive exact match |
| `find_by_name_partial(query, format_filter, games)` | Substring search |
| `find_by_colors(color, format_filter, games)` | Color filter (W/U/B/R/G) |
| `find_by_type(type_query, format_filter, games)` | Type line search |
| `search_by_keywords(keyword, format_filter, games)` | Oracle text/keywords search |
| `search_advanced(colors, types, keywords, ...)` | Multi-criteria with pagination |

**Advanced Search Parameters:**
- `colors` + `color_mode` (any/all/exact/at_most)
- `oracle_text_phrases` (AND logic)
- `mana_value_min/max`
- `rarity` (single or list)
- `page`, `page_size` (max 50)
- `format_filter`, `games`

### DeckRepository

| Method | Description |
|--------|-------------|
| `create_deck(name, format, strategy, tags)` | Create new deck |
| `get_deck(deck_id)` | Get deck metadata |
| `get_deck_with_cards(deck_id)` | Eager load with cards |
| `update_deck(deck_id, name, strategy, tags)` | Update metadata |
| `delete_deck(deck_id)` | Cascade delete |
| `list_decks(format_filter)` | List all decks |
| `find_deck_by_name(name)` | Partial name match |
| `add_card_to_deck(deck_id, card_id, quantity, sideboard)` | Add card |
| `remove_card_from_deck(deck_id, card_id, sideboard)` | Remove card |
| `update_card_quantity(deck_id, card_id, quantity, sideboard)` | Update quantity |
| `update_deck_color_identity(deck_id)` | Compute from cards |
| `merge_decks(target_id, source_id, strategy)` | Combine/Maximum/Replace |

---

## Agent Tools

### Card Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `lookup_card_by_name` | `name: str`, `auto_filter: bool` | Exact card lookup |
| `search_cards_advanced` | Multiple filters | Multi-criteria search |

### Deck Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `create_deck` | `name: str`, `format: str` | Create and set active |
| `add_card_to_deck` | `name: str`, `quantity: int` | Add to active deck |
| `view_deck` | (none) | Display active deck |
| `remove_card_from_deck` | `card_name: str`, `sideboard: bool` | Remove from deck |
| `update_card_quantity` | `card_name: str`, `quantity: int`, `sideboard: bool` | Update quantity |
| `list_decks` | `format_filter: str | None` | List saved decks |
| `load_deck` | `name: str | None`, `deck_id: str | None` | Load as active |
| `delete_deck` | `name/deck_id`, `confirmed: bool` | Delete with confirmation |

### Analysis Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `analyze_deck_mana_curve` | (none) | Full curve analysis |
| `detect_deck_synergies` | (none) | Tribal/keyword/mechanic synergies |

### Session Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `set_format_filter` | `format: str | None` | Filter by format |
| `set_games_filter` | `games: list[str] | None` | Filter by platform |
| `toggle_auto_feedback` | `enabled: bool` | Curve feedback toggle |

---

## Business Logic

### Mana Curve Analysis (`src/logic/mana_curve.py`)

**ManaCurveAnalysis** dataclass:
- `distribution`: CMC → card count
- `total_lands`, `total_spells`
- `average_cmc`
- `playable_cards_by_turn`: Turn → playable count
- `land_ratio`: Percentage of lands
- `issues`: Detected problems
- `recommendations`: Improvement suggestions

**Contextual Feedback** (on card addition):
- Throttled to avoid fatigue (>15% shift, problems, or first 4 cards)
- Archetype inference (aggro ≤2.5, midrange 2.5-3.5, control >3.5)
- Feedback types: positive, warning, neutral

### Synergy Detection (`src/logic/synergy.py`)

**Pattern Types:**
1. **Tribal** - Creature type density (5+ creatures + payoffs)
2. **Keyword** - Keyword abilities + keyword-matters cards
3. **Mechanic Combo** - Sacrifice, graveyard, card draw synergies

**Strength Classification:**
- Strong: >30% of deck
- Moderate: 10-30% of deck
- Weak: <10% of deck

**Deck Cohesion:** low/moderate/high based on synergy count and coverage

---

## Session Management

**ConversationSessionManager** (`src/agent/core.py`):

| State | Description |
|-------|-------------|
| `_sessions` | Message history per session |
| `_format_filters` | Format filter per session |
| `_games_filters` | Games filter per session |
| `_active_deck_ids` | Active deck per session |
| `_preferences` | Boolean preferences (auto_feedback) |
| `_search_contexts` | Pagination context |

**Deck Context Injection:**
- Active deck info injected as system message
- Prevents agent from losing track of deck
- Includes: name, ID (truncated), format, card count

---

## UI Layer

### Entry Point (`src/ui/app.py`)

- `initialize_app()` - Database, agent, symbol cache
- `on_chat_start()` - Welcome message, format/games buttons
- `on_message()` - Delegate to message handler
- `get_agent_dependencies()` - Context manager per request

### Interactive Actions

| Action | Callback | Purpose |
|--------|----------|---------|
| `add_suggested_card` | `card_actions.py` | Quick-add from synergy suggestions |
| `quick_load_deck` | `deck_actions.py` | One-click deck loading |
| `select_card` | `card_actions.py` | Disambiguation selection |
| `confirm_delete_deck` | `deck_actions.py` | Delete confirmation |
| `next_page` / `prev_page` | `pagination_actions.py` | Search pagination |
| `set_format_filter` | `filter_actions.py` | Format selection |
| `set_games_filter` | `filter_actions.py` | Platform selection |

### Visual Features

- **Mana Symbols** - Scryfall SVG images (cached)
- **Card Hover** - Image preview on hover
- **Deck Sidebar** - Active deck card list

---

## Development

### Commands

```bash
# Run Application
uv run chainlit run src/ui/app.py -w  # With auto-reload

# Testing
uv run pytest                         # All tests
uv run pytest tests/unit/             # Unit only
uv run pytest --cov=src               # With coverage

# Code Quality
uv run ruff check . --fix             # Lint + fix
uv run ruff format .                  # Format
uv run mypy src/                      # Type check

# Database
uv run python scripts/import_scryfall_data.py  # Import cards
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | One of | Claude direct access |
| `OPENROUTER_API_KEY` | these | Multi-model access |
| `AGENT_MODEL` | No | Default: claude-haiku-4-5 |
| `AGENT_TEMPERATURE` | No | Default: 0.7 |
| `AGENT_MAX_TOKENS` | No | Default: 4096 |
| `CARDS_DATABASE_URL` | No | Default: sqlite+aiosqlite:///./data/cards.db |
| `LOGFIRE_ENABLED` | No | Default: false |
| `VISUAL_MANA_SYMBOLS` | No | Default: true |
| `CARD_IMAGE_HOVER_ENABLED` | No | Default: true |

---

## External Integrations

| Service | Usage | Auth |
|---------|-------|------|
| Scryfall API | Bulk card data (one-time) | None |
| Anthropic API | Claude LLM (primary) | x-api-key header |
| OpenRouter API | Multi-model (fallback) | Bearer token |
| Scryfall CDN | Card images, mana symbols | None |

---

## Related Documentation

- [PRD](prd.md) - Product Requirements Document
- [Architecture](architecture.md) - Detailed architecture decisions
- [LOGFIRE](LOGFIRE.md) - Observability setup guide
- [CLAUDE.md](../CLAUDE.md) - Claude Code instructions

---

*Generated by document-project workflow (BMad Method)*

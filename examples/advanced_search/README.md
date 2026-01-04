# 🎴 Advanced Card Search - Examples & Demos

This directory contains example scripts demonstrating the advanced card search feature
implemented in Story 2.3. The feature enables multi-criteria card searches with support
for colors, types, keywords, and mana value filtering.

## 📁 Example Scripts

### 1. `01_repository_search.py` - Repository-Level Search (Fastest)
Quick demonstration of the repository methods without requiring API calls.
Shows all filter types and combinations.

**Run:** `uv run python examples/advanced_search/01_repository_search.py`
**Note:** Run from project root directory

**Features demonstrated:**
- Keyword search (haste, flying, etc.)
- Multi-criteria filtering
- Color, type, and mana value filters
- Result limiting and sorting

### 2. `02_real_cards_search.py` - Real Playable Cards
Focused tests showing real playable cards (excludes tokens) across different
mana costs and card types.

**Run:** `uv run python examples/advanced_search/02_real_cards_search.py`
**Note:** Run from project root directory

**Features demonstrated:**
- Filtering out token cards
- Searches by specific mana values (1, 2, 3, 4 CMC)
- Famous card searches (burn spells, card draw, dragons)

### 3. `03_agent_natural_language.py` - Full Agent with Natural Language
Interactive demo showing the PydanticAI agent processing natural language queries
and using the advanced search tool.

**Run:** `uv run python examples/advanced_search/03_agent_natural_language.py`
**Note:** Run from project root directory
**Requires:** `OPENROUTER_API_KEY` environment variable

**Features demonstrated:**
- Natural language query processing
- Agent automatically extracting filter parameters
- Conversational result formatting
- Interactive query progression

---

## 📖 Usage Examples

### Repository-Level Queries (Fast, No API)

#### Basic Searches
```python
from src.data.database import create_engine, create_session_factory
from src.data.repositories.card import CardRepository

engine = create_engine()
session_factory = create_session_factory(engine)

async with session_factory() as session:
    repo = CardRepository(session)

    # Find all red cards
    cards = await repo.search_advanced(colors=["R"], limit=20)

    # Find creatures
    cards = await repo.search_advanced(types=["Creature"], limit=20)

    # Find cards with flying
    cards = await repo.search_by_keywords("flying")
```

#### Multi-Criteria Searches
```python
# Red creatures with haste under 4 mana (the signature query!)
cards = await repo.search_advanced(
    colors=["R"],
    types=["Creature"],
    keywords=["haste"],
    mana_value_max=3.0,
    limit=20
)

# Cheap artifacts (CMC ≤ 2)
cards = await repo.search_advanced(
    types=["Artifact"],
    mana_value_max=2.0,
    limit=20
)

# Legendary dragons
cards = await repo.search_advanced(
    types=["Legendary", "Dragon"],
    limit=20
)

# Blue instants that draw cards
cards = await repo.search_advanced(
    colors=["U"],
    types=["Instant"],
    keywords=["draw"],
    limit=20
)
```

### Agent-Level Natural Language Queries

With the PydanticAI agent, users can ask natural language questions:

- "Find red creatures with haste under 4 mana"
- "Show me cheap artifacts, like 1-2 mana"
- "What are some blue instants that let me draw cards?"
- "I'm building an aggro deck. Find me efficient red creatures with haste."
- "Show me legendary dragons"
- "Find white creatures with vigilance"

The agent will automatically:
1. Parse the natural language query
2. Extract filter parameters (colors, types, keywords, mana range)
3. Call the `search_cards_advanced` tool
4. Format and present the results conversationally

---

## ✅ What's Working

- ✅ **Multi-criteria filtering** - colors, types, keywords, mana value
- ✅ **Smart result limiting** - default 20, customizable
- ✅ **Result sorting** - by CMC then name
- ✅ **Keyword search** - in oracle_text AND keywords array
- ✅ **Color filtering** - OR logic (["R", "G"] = red OR green)
- ✅ **Type filtering** - AND logic (["Legendary", "Dragon"] = must be both)
- ✅ **Keyword filtering** - AND logic (["flying", "haste"] = must have both)
- ✅ **Graceful error handling** - no results, too many results
- ✅ **Performance** - <500ms for typical queries

---

## 🎯 Filter Logic Summary

### Colors (OR Logic)
`colors=["R", "G"]` → Cards that are red OR green (or both)

### Types (AND Logic)
`types=["Legendary", "Dragon"]` → Cards that are BOTH legendary AND dragons

### Keywords (AND Logic)
`keywords=["flying", "haste"]` → Cards that have BOTH flying AND haste

### Mana Value (Range)
```python
mana_value_min=2.0  # CMC >= 2
mana_value_max=4.0  # CMC <= 4
# Combined: CMC between 2 and 4 inclusive
```

---

## 📊 Sample Results

From the test runs, the feature successfully finds:

- **1,633 cards** with "haste" keyword
- **4,608 cards** with "flying"
- Famous cards like:
  - Fervent Champion (1 CMC red haste)
  - Adeliz, the Cinder Wind (3 CMC red/blue haste)
  - Ancestral Recall (blue card draw)
  - Classic red burn spells

---

## 🔗 Related Documentation

- **Implementation**: `src/agent/tools/card_search.py`
- **Repository Methods**: `src/data/repositories/card.py`
- **Tests**: `tests/unit/agent/tools/test_card_search.py`
- **OpenSpec Change**: `openspec/changes/archive/2025-10-17-add-advanced-card-search/`

---

## 🚀 Next Steps

This feature is the foundation for:
- Story 2.4: Standard Format Filtering
- Story 4.x: Deck Building Tools
- Story 5.x: Synergy Detection

Enjoy exploring the 43MB Scryfall database with powerful, flexible searches!

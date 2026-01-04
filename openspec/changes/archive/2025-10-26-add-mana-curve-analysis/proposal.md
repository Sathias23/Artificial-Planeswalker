# Add Mana Curve Analysis Tool

## Why

Magic: The Gathering deck building requires careful attention to mana curve distribution to ensure decks can consistently cast spells throughout the game. Currently, the assistant can help users add and remove cards but provides no feedback on whether the deck's mana distribution is balanced. Users building aggro decks may unknowingly create top-heavy curves, while control players might lack sufficient early interaction.

This proposal implements Story 5.1 from the PRD (Epic 5: Deck Building Intelligence) to transform the assistant from a passive deck manager into an active deck building partner that provides real-time mana curve analysis and strategic feedback.

## What Changes

- **NEW capability**: `deck-intelligence` specification for mana curve analysis and future deck building intelligence features
- Business logic module (`src/logic/mana_curve.py`) for calculating and analyzing mana curves
- PydanticAI agent tool (`analyze_mana_curve`) for user-facing curve analysis
- UI formatter for text-based curve visualization in Chainlit chat
- Comprehensive unit tests for curve calculation and analysis logic

## Impact

### Affected Specs
- **NEW**: `deck-intelligence` - Mana curve analysis capability (new spec)
- **MODIFIED**: `agent-tools` - New `analyze_mana_curve` tool

### Affected Code
- `src/logic/mana_curve.py` (new) - Core analysis business logic
- `src/agent/tools/deck_analysis.py` (new) - Agent tool for curve analysis
- `src/ui/formatters.py` (modified) - Add curve visualization formatting
- `tests/unit/logic/test_mana_curve.py` (new) - Unit tests
- `tests/integration/agent/test_deck_analysis_tools.py` (new) - Integration tests

### Research Summary

**Archon RAG Sources Used:**
- PydanticAI documentation (source: `ai.pydantic.dev`) - Tool implementation patterns
- Scryfall API documentation (source: `scryfall.com`) - Mana cost data structure

**Web Research:**
- Draftsim: "Everything You Ever Needed to Know About Mana Curves in Magic" (2025)
- Wizards of the Coast: "How to Build a Mana Curve" (2025)
- TheGamer: "What Is The Ideal Mana Curve For Your Commander Deck?"

**Key Findings:**
- Aggro decks typically feature a ladder-shaped curve with numerous 1-2 drops
- Midrange decks form a triangle/bell curve peaking at 3-4 mana
- Control decks prioritize higher-cost spells with peaks at 4-6 mana
- Standard Limited decks typically run ~17 lands with specific creature distribution:
  - Aggressive: 6-9 creatures < 3 mana, 5-10 at 3-4 mana, 2-3 at 5+ mana
  - Midrange: Balanced distribution across 2-5 mana
  - Control: Focus on 3-6 mana with fewer 1-2 drops

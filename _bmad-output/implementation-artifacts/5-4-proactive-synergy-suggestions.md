# Story 5.4: Proactive Synergy Suggestions

Status: done

## Story

As a **deck builder**,
I want **the agent to suggest cards that synergize with my current deck**,
So that **I can discover cards I might not have considered and build more cohesive decks**.

## Acceptance Criteria

### AC1: LLM-Hybrid Suggestion Workflow
- [x] `suggest_synergy_cards` tool implements 3-stage workflow:
  1. **Analysis Stage**: LLM agent analyzes deck composition and synergies → generates structured search criteria
  2. **Search Stage**: Application code executes parallel database searches → retrieves 50-150 candidates (default 75)
  3. **Curation Stage**: LLM agent evaluates candidates → selects best 5-7 cards with priority rankings and explanations

### AC2: Structured Output Models
- [x] `DeckAnalysis` Pydantic model with fields: `primary_synergy`, `search_criteria`, `reasoning`
- [x] `CuratedCard` Pydantic model with fields: `card_name`, `synergy_fit`, `priority` (1-5)
- [x] `CardSuggestions` Pydantic model with fields: `top_picks` (5-7 items), `overall_strategy`
- [x] Validation ensures type safety at every stage

### AC3: Format, Games, and Color Identity Enforcement
- [x] All suggestions respect active format filter (Standard, Modern, etc.)
- [x] All suggestions respect active games filter (Arena, Paper, MTGO) via `deps.games_filter`
- [x] All suggestions respect deck's color identity (mono-red deck gets only red/colorless suggestions)
- [x] Cards already in deck are excluded from suggestions

### AC4: Mana Curve Integration
- [x] Analysis stage considers mana curve distribution alongside synergies
- [x] If deck is top-heavy (avg CMC > 3.5), bias toward lower-CMC suggestions
- [x] If deck lacks early plays (few 1-2 drops), prioritize early-game suggestions
- [x] Curve-aware reasoning included in analysis output

### AC5: Parallel Database Searches
- [x] Stage 2 executes 3-5 searches via `asyncio.gather()` (parallel, not serial)
- [x] Total search latency < 1 second (target: ~500ms)
- [x] Results deduplicated by card name across queries
- [x] Candidate pool configurable: 50-150 range, default 75

### AC6: Hallucination Prevention
- [x] Validation filters suggestions against candidate list
- [x] Invalid suggestions logged as warnings and excluded
- [x] Fallback mechanism: if all suggestions invalid, return top 5 candidates by CMC with generic explanations

### AC7: UI Quick-Add Integration
- [x] Tool returns structured dict with `has_suggestions: True` signal when successful
- [x] Response includes `suggested_cards: list[Card]` for UI action button rendering
- [x] New `handle_suggestion_signal()` in `src/ui/handlers/signal_handlers.py` handles signal
- [x] Reuses existing `add_suggested_card` callback from `src/ui/actions/card_actions.py`
- [x] Buttons self-remove after card is added

### AC8: Performance Budget
- [x] Total latency < 10 seconds for typical request (60-card deck)
- [x] Stage 1 (analysis): < 5 seconds
- [x] Stage 2 (search): < 1 second
- [x] Stage 3 (curation): < 7 seconds
- [x] Token usage < 20,000 per request

### AC9: Error Handling
- [x] LLM analysis failure → user-friendly error message with session context in logs
- [x] No candidates found → message with suggestion to adjust deck/format
- [x] All suggestions invalid → fallback to top 5 candidates by CMC

### AC10: Natural Language Triggers
- [x] Agent detects suggestion intent from queries like:
  - "Suggest cards for my deck"
  - "What cards would work well in my deck?"
  - "Recommend cards to improve my strategy"
  - "Find cards that fit my deck"
  - "What should I add to my Goblin deck?"

## Tasks / Subtasks

### Task 1: Core Implementation (AC: 1, 2, 5, 6)
- [x] 1.1 Create `src/agent/tools/synergy_suggestions.py`
  - [x] Add required imports (see Dev Notes: Required Imports)
  - [x] Define `DeckAnalysis` Pydantic model (primary_synergy, search_criteria, reasoning)
  - [x] Define `DeckNeedAnalysis` model for individual search criteria
  - [x] Define `CuratedCard` model (card_name, synergy_fit, priority 1-5)
  - [x] Define `CardSuggestions` model (top_picks 5-7, overall_strategy)
- [x] 1.2 Create analysis agent
  - [x] Use provider pattern from `src/agent/core.py:_determine_provider()` for model creation
  - [x] Use PydanticAI Agent with `output_type=DeckAnalysis`
  - [x] System prompt: analyze deck composition, synergies, and mana curve
  - [x] Generate 3-5 search criteria based on deck needs
- [x] 1.3 Implement `_build_deck_context()` helper
  - [x] Format deck cards by type (creatures, spells, lands)
  - [x] Include average CMC and curve distribution
  - [x] Include synergy summary from `detect_synergies()`
  - [x] Include color identity (with fallback computation if empty)
- [x] 1.4 Implement `_search_candidates()` helper
  - [x] Parse search criteria from DeckAnalysis
  - [x] Execute 3-5 parallel `CardRepository.search_advanced()` calls
  - [x] Apply format filter via `format_filter=deps.format_filter`
  - [x] Apply games filter via `games=deps.games_filter` (Arena, Paper, MTGO)
  - [x] Apply color identity filter with `color_mode="at_most"`
  - [x] Exclude cards already in deck by card ID
  - [x] Deduplicate results by card name
  - [x] Target 75 candidates (configurable 50-150)
- [x] 1.5 Implement `_format_candidates()` helper
  - [x] Format each card: "Name (cost, type): oracle_text_truncated"
  - [x] Use `get_display_name(card)` from `src/ui/formatters.py` for card names
  - [x] One card per line for LLM consumption
  - [x] ~150 tokens per card estimate
- [x] 1.6 Create curation agent
  - [x] Use same provider pattern as analysis agent
  - [x] Use PydanticAI Agent with `output_type=CardSuggestions`
  - [x] System prompt: evaluate candidates, select best 5-7 with explanations
  - [x] Prioritize cards that address identified deck needs
- [x] 1.7 Implement `suggest_synergy_cards()` main tool
  - [x] Orchestrate 3-stage workflow
  - [x] Validate suggestions against candidate list (hallucination prevention)
  - [x] Implement fallback for invalid suggestions

### Task 2: Mana Curve Integration (AC: 4)
- [x] 2.1 Extend `_build_deck_context()` with curve analysis
  - [x] Convert DeckCards to Cards: `cards = [dc.card for dc in deck.deck_cards for _ in range(dc.quantity)]`
  - [x] Call `analyze_mana_curve(cards)` from `src/logic/mana_curve.py`
  - [x] Include CMC distribution and identified issues
  - [x] Flag if deck is top-heavy or lacks early plays
- [x] 2.2 Update analysis agent prompt
  - [x] Consider curve gaps in search criteria generation
  - [x] If avg CMC > 3.5, include "max_cmc: 3" in criteria
  - [x] If few 1-2 drops, add search for low-CMC cards

### Task 3: Color Identity, Format & Games Filtering (AC: 3)
- [x] 3.1 Extract deck color identity in `_build_deck_context()`
  - [x] Primary: use `deck.color_identity` if non-empty
  - [x] Fallback: compute from cards if empty: `{c for dc in deck.deck_cards for c in (dc.card.color_identity or [])}`
- [x] 3.2 Apply color identity filter in `_search_candidates()`
  - [x] Use `color_mode="at_most"` with deck's colors
  - [x] Ensures suggestions fit deck's mana base
- [x] 3.3 Apply format filter from `deps.format_filter`
  - [x] Pass `format_filter=deps.format_filter` to all `search_advanced()` calls
  - [x] Include format note in output
- [x] 3.4 Exclude existing deck cards
  - [x] Build exclusion set: `existing_card_ids = {dc.card.id for dc in deck.deck_cards}`
  - [x] Filter candidates: `[c for c in candidates if c.id not in existing_card_ids]`
- [x] 3.5 Apply games filter from `deps.games_filter`
  - [x] Pass `games=deps.games_filter` to all `search_advanced()` calls
  - [x] Ensures Arena-only decks get Arena-available suggestions
  - [x] Pattern reference: `src/agent/tools/card_lookup.py:107`

### Task 4: UI Signal Handling (AC: 7)
- [x] 4.1 Update tool return structure
  - [x] Return dict with `has_suggestions: True` when successful
  - [x] Include `suggested_cards: list[Card]` (Card objects, not just names)
  - [x] Include `formatted_text: str` for display
  - [x] Use `wrap_card_name_with_hover()` from `src/ui/formatters.py` for card names
- [x] 4.2 Create signal handler in `src/ui/handlers/signal_handlers.py`
  - [x] Create `handle_suggestion_signal()` function (follow pattern from `handle_synergy_signal()` at line 126)
  - [x] Check for `has_suggestions` key in signal
  - [x] Generate Chainlit action buttons for each suggestion
  - [x] Reuse existing `add_suggested_card` callback from `src/ui/actions/card_actions.py`
- [x] 4.3 Update `src/ui/handlers/message_handler.py` to detect and handle suggestion signals
  - [x] Check for `has_suggestions` key in tool response
  - [x] Call `handle_suggestion_signal()` when detected

### Task 5: Tool Registration (AC: 10)
- [x] 5.1 Register tool in `src/agent/core.py`
  - [x] Import `suggest_synergy_cards` from `synergy_suggestions`
  - [x] Add to main agent's tools list (after line 724)
- [x] 5.2 Verify natural language intent detection
  - [x] Tool docstring supports LLM understanding of suggestion intent

### Task 6: Error Handling (AC: 9)
- [x] 6.1 Implement analysis failure handling
  - [x] Catch exceptions from analysis agent
  - [x] Return user-friendly error message
  - [x] Log with session context: `logger.error(f"Analysis failed for session {deps.session_id}: {e}")`
- [x] 6.2 Implement no-candidates handling
  - [x] Check if candidate list is empty after search
  - [x] Return helpful message with suggestions
- [x] 6.3 Implement fallback mechanism
  - [x] If validation filters all suggestions, use fallback
  - [x] Sort candidates by mana_value, take top 5
  - [x] Generate generic explanations

### Task 7: Documentation (AC: all)
- [x] 7.1 Update `CLAUDE.md`
  - [x] Add `suggest_synergy_cards()` to tools list (already present)
  - [x] Document signal handling pattern for suggestions
- [x] 7.2 Add comprehensive docstrings
  - [x] Main tool: full docstring with examples
  - [x] Helper functions: purpose, parameters, returns
  - [x] Pydantic models: field descriptions

### Task 8: Testing
- [x] 8.1 Unit tests for Pydantic models (`tests/unit/agent/tools/test_synergy_suggestions.py`)
  - [x] Valid/invalid inputs for DeckAnalysis
  - [x] CardSuggestions validation (5-7 picks, priorities 1-5)
- [x] 8.2 Unit tests for helper functions (`tests/unit/agent/tools/test_synergy_suggestions.py`)
  - [x] `_build_deck_context()` with various decks
  - [x] `_format_candidates()` output format
- [x] 8.3 Unit tests for main tool
  - [x] Error scenarios (no deck, empty deck, small deck)
  - [x] Error handling when agent creation fails

## Dev Notes

### Required Imports

```python
# Standard library
import asyncio
import logging
from typing import Any

# Pydantic & PydanticAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

# Project imports
from src.agent.config import AgentConfig
from src.agent.dependencies import AgentDependencies
from src.data.repositories.card import CardRepository
from src.data.schemas import Card
from src.logic.mana_curve import analyze_mana_curve
from src.logic.synergy import detect_synergies
from src.ui.formatters import get_display_name, wrap_card_name_with_hover

logger = logging.getLogger(__name__)
```

### Architecture Pattern: Agent Delegation with Dual-Provider Support

Use the same provider pattern as the main agent in `src/agent/core.py`:

```python
def _create_suggestion_agents() -> tuple[Agent, Agent]:
    """Create analysis and curation agents using project's provider pattern."""
    config = AgentConfig()

    # Reuse provider determination logic from core.py
    from src.agent.core import _determine_provider
    use_anthropic, model_name = _determine_provider(config)

    # Create model instance (same pattern as create_agent())
    if use_anthropic:
        provider = AnthropicProvider(api_key=config.anthropic_api_key)
        model = AnthropicModel(model_name=model_name, provider=provider)
    else:
        provider = OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.openrouter_api_key,
        )
        model = OpenAIChatModel(model_name=model_name, provider=provider)

    analysis_agent = Agent(
        model=model,
        output_type=DeckAnalysis,
        system_prompt="Analyze deck composition and generate search criteria..."
    )

    curation_agent = Agent(
        model=model,
        output_type=CardSuggestions,
        system_prompt="Evaluate candidate cards and select the best 5-7..."
    )

    return analysis_agent, curation_agent
```

### Mana Curve Integration (Critical: Type Conversion)

```python
def _build_deck_context(deck: Deck) -> str:
    """Build deck context string for analysis agent."""
    # CRITICAL: Convert DeckCard to Card list for mana_curve.analyze_mana_curve()
    # analyze_mana_curve expects list[Card], not list[DeckCard]
    cards_expanded = [
        dc.card
        for dc in deck.deck_cards
        for _ in range(dc.quantity)  # Expand by quantity
    ]

    curve_analysis = analyze_mana_curve(cards_expanded)

    # Color identity with fallback
    if deck.color_identity:
        colors = deck.color_identity
    else:
        # Compute from cards if deck.color_identity is empty (new decks)
        colors = list({
            c for dc in deck.deck_cards
            for c in (dc.card.color_identity or [])
        })

    context = f"Deck: {deck.name}\n"
    context += f"Format: {deck.format}\n"
    context += f"Colors: {', '.join(colors) if colors else 'Colorless'}\n"
    context += f"Average CMC: {curve_analysis.average_cmc:.1f}\n"
    context += f"Curve Issues: {', '.join(curve_analysis.issues) or 'None'}\n"
    # ... rest of context building
    return context
```

### Card Exclusion Logic

```python
async def _search_candidates(
    analysis: DeckAnalysis,
    card_repo: CardRepository,
    deps: AgentDependencies,
    deck: Deck,
) -> list[Card]:
    """Search for candidate cards, excluding those already in deck."""
    # Build exclusion set from current deck cards
    existing_card_ids = {dc.card.id for dc in deck.deck_cards}

    # Get filters from deps (pattern: src/agent/tools/card_lookup.py:107)
    format_filter = deps.format_filter
    games_filter = deps.games_filter  # Arena, Paper, MTGO availability

    # Build search tasks with filters applied
    search_tasks = [
        card_repo.search_advanced(
            ...,
            format_filter=format_filter,
            games=games_filter,
            color_mode="at_most",
            colors=deck_colors,
        )
        for criteria in analysis.search_criteria
    ]

    # Execute parallel searches...
    all_candidates = await asyncio.gather(*search_tasks)

    # Flatten and deduplicate
    seen_names: set[str] = set()
    unique_candidates: list[Card] = []
    for candidates in all_candidates:
        for card in candidates.items:
            # Skip if already in deck
            if card.id in existing_card_ids:
                continue
            # Skip duplicates from different searches
            if card.name in seen_names:
                continue
            seen_names.add(card.name)
            unique_candidates.append(card)

    return unique_candidates[:75]  # Target candidate pool size
```

### Key File Locations

| File | Action | Purpose |
|------|--------|---------|
| `src/agent/tools/synergy_suggestions.py` | CREATE | Main orchestration + nested agents |
| `src/agent/core.py:724` | MODIFY | Register tool after line 724 |
| `src/ui/handlers/signal_handlers.py` | MODIFY | Add `handle_suggestion_signal()` |
| `src/ui/actions/card_actions.py` | REFERENCE | Existing `add_suggested_card` callback |
| `src/ui/app.py` | MODIFY | Detect suggestion signals |
| `CLAUDE.md` | MODIFY | Document new tool |

### Signal Handler Pattern (Reference: line 126-173 in signal_handlers.py)

```python
async def handle_suggestion_signal(signal: dict[str, Any]) -> None:
    """Create quick-add buttons for suggested cards.

    Pattern matches handle_synergy_signal() but checks for 'has_suggestions' key.
    """
    suggested_cards = signal.get("suggested_cards", [])

    if suggested_cards:
        suggestion_actions = []
        for card in suggested_cards[:7]:
            display_name = get_display_name(card)  # Handles printed_name
            suggestion_actions.append(
                cl.Action(
                    name="add_suggested_card",  # Reuses existing callback
                    payload={"card_name": card.name, "card_id": str(card.id)},
                    label=f"Add {display_name}",
                    tooltip="Add 1 copy to active deck",
                    icon="plus-circle",
                )
            )

        suggestion_message = cl.Message(content="", actions=suggestion_actions)
        await suggestion_message.send()
        store_action_message("suggestion_message", suggestion_message)
```

### UI Formatted Output with Card Hover

```python
def _format_suggestions_output(
    suggestions: CardSuggestions,
    candidate_cards: dict[str, Card],  # name -> Card mapping
) -> str:
    """Format suggestions with card hover previews."""
    output = "## Card Suggestions for Your Deck\n\n"

    for i, pick in enumerate(suggestions.top_picks, 1):
        card = candidate_cards.get(pick.card_name)
        if card:
            # Use hover wrapper for card image preview
            name_with_hover = wrap_card_name_with_hover(pick.card_name, card)
            output += f"{i}. **{name_with_hover}** "
            output += f"(Priority: {'⭐' * pick.priority})\n"
            output += f"   {pick.synergy_fit}\n\n"

    output += f"\n**Strategy:** {suggestions.overall_strategy}"
    return output
```

### Performance Budget

| Stage | Target | Max |
|-------|--------|-----|
| Analysis LLM | 2s | 5s |
| Database search | 0.5s | 1s |
| Curation LLM | 3s | 7s |
| **Total** | **5.5s** | **10s** |

### Token Budget (~12,550 total)

- Deck context + curve: ~700 tokens
- Analysis output: ~300 tokens
- Candidates (75 cards): ~11,250 tokens
- Curation output: ~500 tokens

### Observability Note

Nested agent calls are automatically traced when Logfire is enabled. The `logfire.instrument_pydantic_ai()` call in `src/agent/core.py:76` instruments ALL PydanticAI agents, including the analysis and curation agents created in this tool.

### Project Structure Notes

- Follows existing tool pattern in `src/agent/tools/` (reference: `synergy_detection.py`)
- Reuses signal handling pattern from `detect_deck_synergies` (line 15-80)
- Integrates with existing mana curve analysis from Story 5.1
- Compatible with existing format and games filters

### References

- [Source: openspec/changes/add-llm-card-suggestions/proposal.md] - Feature rationale
- [Source: openspec/changes/add-llm-card-suggestions/design.md] - Architecture decisions
- [Source: openspec/changes/add-llm-card-suggestions/tasks.md] - Implementation tasks
- [Source: openspec/changes/add-llm-card-suggestions/specs/agent-tools/spec.md] - BDD scenarios
- [Source: src/logic/synergy.py] - Existing synergy detection
- [Source: src/logic/mana_curve.py:58] - `analyze_mana_curve(cards: list[Card])` signature
- [Source: src/agent/tools/synergy_detection.py:15-80] - Signal return pattern reference
- [Source: src/agent/core.py:532-588] - Provider selection logic
- [Source: src/ui/handlers/signal_handlers.py:126-173] - Signal handler pattern
- [Source: src/ui/actions/card_actions.py] - `add_suggested_card` callback
- [Source: src/ui/formatters.py] - `get_display_name()`, `wrap_card_name_with_hover()`
- [Source: CLAUDE.md#Agent-Tools] - Tool registration pattern

## Dev Agent Record

### Context Reference

- OpenSpec: `openspec/changes/add-llm-card-suggestions/`
- Epic: `docs/epics.md` - Epic 5, Story 5.4

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

Implementation completed on 2025-12-07 by Dev Agent (Amelia) using Claude Opus 4.5.

**Summary:**
- Created `suggest_synergy_cards` tool with 3-stage LLM-hybrid workflow (analysis → search → curation)
- All 4 Pydantic models implemented with validation constraints
- Parallel database searches using `asyncio.gather()` with format, games, and color identity filtering
- Hallucination prevention via candidate validation and fallback mechanism
- UI signal handling integrated with existing `add_suggested_card` callback
- 29 unit tests covering models, helpers, and error scenarios - all passing
- Pre-existing test failures in other modules are unrelated to this implementation

### Code Review Follow-ups (AI)

**Reviewed on 2025-12-08 by Dev Agent (Amelia) using Claude Opus 4.5**

Issues found and fixed:
- [x] [AI-Review][CRITICAL] Fixed type mismatch in `_search_candidates()` - `types` and `keywords` were passed as strings instead of `list[str]`. This caused character-by-character iteration instead of proper type/keyword filtering. [synergy_suggestions.py:415-423]
- [x] [AI-Review][MEDIUM] Fixed priority stars display inversion - priority 1 (highest) now shows 5 stars, priority 5 (lowest) shows 1 star. [synergy_suggestions.py:519-527]
- [x] [AI-Review][MEDIUM] Added 7 unit tests for `_search_candidates()` covering parallel execution, deduplication, exclusion, color identity filtering, type/keyword parameter types, and exception handling.
- [x] [AI-Review][MEDIUM] Added 3 unit tests for `_format_suggestions_output()` covering formatting, priority star inversion, and fallback for missing cards.

### File List

- [x] `src/agent/tools/synergy_suggestions.py` (NEW, REVIEW-FIX: type mismatch + priority stars)
- [x] `src/agent/core.py` (MODIFY - line 724-726)
- [x] `src/ui/handlers/signal_handlers.py` (MODIFY - add handle_suggestion_signal)
- [x] `src/ui/handlers/message_handler.py` (MODIFY - detect has_suggestions signal)
- [x] `CLAUDE.md` (MODIFY)
- [x] `tests/unit/agent/tools/test_synergy_suggestions.py` (NEW - 29 tests, REVIEW-ADD: 10 new tests)

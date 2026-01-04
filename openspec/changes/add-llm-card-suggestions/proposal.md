# LLM-Hybrid Card Suggestions Proposal

## Why

Deck builders need intelligent, context-aware card suggestions to enhance their decks. The existing synergy detection (`detect_deck_synergies`) identifies patterns but doesn't recommend specific cards. Users must manually search for cards that fit their deck's strategy, which is time-consuming and requires deep Magic: The Gathering knowledge.

**User pain point**: "My deck has a Goblin tribal theme, but I don't know which Goblin cards would best strengthen it."

An AI-powered suggestion system can analyze deck composition, identify strategic needs, search the database for candidates, and curate the best recommendations with explanations.

## What Changes

**ADDED**: New `suggest_synergy_cards()` agent tool that provides AI-curated card suggestions using a 3-stage LLM-hybrid workflow:

1. **Analysis Stage**: Dedicated LLM agent analyzes deck and synergies → generates structured search criteria (Pydantic model)
2. **Search Stage**: Application code executes database searches → retrieves 50-150 candidate cards (configurable, default 75)
3. **Curation Stage**: Dedicated LLM agent evaluates candidates → selects best 5-7 cards with priority rankings and explanations (Pydantic model)

**Key architectural decisions**:
- Use PydanticAI's agent delegation pattern (specialized agents for analysis and curation)
- Structured outputs via Pydantic models (`DeckAnalysis`, `CardSuggestions`) for type safety
- Configurable candidate pool size (50-150, default 75) to balance quality vs performance
- Parallel database searches (3-5 concurrent queries) for ~500ms search latency
- Format-filter enforcement ensures all suggestions are legal in active format

**Why NOT LangChain**: LangChain + PydanticAI causes Pydantic v1/v2 version conflicts and adds unnecessary complexity. PydanticAI's native agent delegation provides sufficient orchestration.

**Why NOT Thinking Mode**: Incompatible with structured outputs (disables tool calling). Also increases latency 15-20x and token usage 15-20x for marginal accuracy gains on this task.

## Impact

### Affected Specs
- **agent-tools** (ADDED): New `suggest_synergy_cards()` tool with configurable candidate pool
- **deck-intelligence** (unchanged): Reuses existing `detect_synergies()` for context

### Affected Code
- `src/agent/tools/synergy_suggestions.py` (NEW): Main orchestration tool + specialized agents
- `src/agent/core.py` (MODIFIED): Register new tool with main agent
- `src/ui/formatters.py` (MINOR): May need suggestion formatting helpers
- `CLAUDE.md` (MODIFIED): Document new tool and performance characteristics

### User Impact
- **Positive**: Users get intelligent, context-aware card suggestions (requested feature)
- **Positive**: Suggestions include explanations (why each card fits)
- **Positive**: Format-legal cards only (respects active format filter)
- **Neutral**: 5-10 second latency (2 LLM calls + database search) - acceptable for on-demand feature
- **Neutral**: ~$0.015-0.025 per request in API costs (2 LLM calls with 75 candidates)

### Performance Characteristics
- **Analysis LLM call**: ~2-3 seconds (structured output)
- **Database search**: ~0.5 seconds (3-5 parallel queries)
- **Curation LLM call**: ~2-5 seconds (75 candidates → 5-7 picks)
- **Total latency**: ~5-10 seconds (acceptable for complex AI task)
- **Token usage**: ~15k tokens per request (~11k for candidates, ~4k for deck/analysis)
- **Cost per request**: ~$0.02 (2 LLM calls at current OpenRouter rates)

### Dependencies
- **None new**: Uses existing PydanticAI, OpenRouter, CardRepository
- **Compatible**: Works with existing synergy detection and deck management

### Migration Plan
- No migration needed (new feature, not replacing anything)
- Existing `detect_deck_synergies` tool continues to work independently
- Users can use both: analyze synergies first, then get suggestions

## Open Questions

1. **Should candidate pool size be exposed to users?**
   - Proposal: No, keep it internal. Default 75 is sufficient for most decks. Advanced users can't meaningfully evaluate "search with 50 vs 100 candidates."
   - Alternative: Expose as optional parameter for power users
   - **Decision needed before implementation**

2. **Should we cache suggestions per deck hash?**
   - Proposal: No caching for MVP. Decks change frequently (adding cards), cache invalidation is complex.
   - Future: Consider if latency feedback is negative or costs spike
   - **Not blocking for MVP**

3. **Fallback behavior if LLM fails?**
   - Proposal: Return user-friendly error message with retry prompt (no silent failures)
   - Alternative: Fallback to simple heuristic (top N cards by CMC from synergy types)
   - **Design doc will specify**

## Success Criteria

- Users can request card suggestions for any active deck
- Suggestions are always real, format-legal cards (validation prevents hallucination)
- Explanations are specific to deck strategy (not generic descriptions)
- Latency is <10 seconds for typical requests
- Token usage is <20k per request (cost-effective)
- Code is <500 lines total (maintainable complexity)
- Integration tests cover full workflow (analysis → search → curation)

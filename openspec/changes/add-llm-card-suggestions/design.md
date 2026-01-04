# Design: LLM-Hybrid Card Suggestions

## Context

Users need intelligent card suggestions to improve their decks. Current `detect_deck_synergies` tool identifies patterns (tribal, keyword, combos) but doesn't recommend specific cards.

**Constraints**:
- Must use existing PydanticAI + OpenRouter infrastructure
- Must return format-legal cards only (respect active format filter)
- Target latency: <10 seconds for user experience
- Must prevent LLM hallucination (suggesting non-existent cards)
- Single-user local development (no distributed caching)

**Stakeholders**:
- Deck builders seeking card recommendations
- Future: Competitive players optimizing for meta positioning

## Goals / Non-Goals

### Goals
- Provide 5-7 AI-curated card suggestions per request
- Include explanations for why each card fits deck strategy
- Enforce format legality (Standard/Modern/etc.)
- Complete within <10 seconds (acceptable for on-demand feature)
- Type-safe structured outputs at every stage
- Extensible architecture for future enhancements

### Non-Goals
- Real-time suggestions as user types (too latency-sensitive)
- Complete deck building from scratch (different use case)
- Meta-game analysis or tournament-specific optimization (future scope)
- Caching/optimization for high-volume usage (single-user MVP)
- Support for non-English cards (Scryfall data limitation)

## Architecture Decision: Agent Delegation Pattern

### Decision: Use PydanticAI's native agent delegation (specialized agents)

**Why**:
- Type-safe structured outputs via Pydantic models at each stage
- Clean separation of concerns (analysis agent ≠ curation agent)
- PydanticAI's designed pattern (not fighting framework)
- Reusable agents (can test independently)
- Usage tracking across all LLM calls

**Alternatives considered**:

1. **LangChain Orchestration** ❌
   - Pydantic v1/v2 version conflicts
   - Dual framework maintenance burden
   - Unnecessary abstraction layer
   - No type safety for chained outputs

2. **Single Agent with Multiple Prompts** ❌
   - Main agent does double duty (conversation + specialized tasks)
   - Can't optimize prompts per task
   - Harder to tune temperature/settings per stage
   - Less modular (can't reuse analysis/curation separately)

3. **Programmatic Hand-off (Sequential Agent Calls)** 🤔
   - Simpler than agent delegation (no nested tools)
   - Still gets structured outputs
   - Acceptable alternative if delegation proves too complex
   - **Backup plan if agent delegation has issues**

### Architecture Diagram

```
User: "Suggest cards for my deck"
   ↓
Main Agent (conversational)
   ↓ (detects intent, calls tool)
Tool: suggest_synergy_cards(ctx: RunContext[AgentDependencies])
   ↓
   ├─ Stage 1: Analysis Agent
   │    Input: Deck summary + synergies
   │    Output: DeckAnalysis (structured JSON)
   │    LLM Call: ~2-3 seconds
   │    └─ Pydantic model: {primary_synergy, search_criteria, reasoning}
   │
   ├─ Stage 2: Database Search (app code)
   │    Input: search_criteria from Stage 1
   │    Execute: 3-5 parallel CardRepository.search_advanced() calls
   │    Output: 50-150 candidate cards (default 75)
   │    Latency: ~500ms
   │    └─ Deduplication by card name
   │
   └─ Stage 3: Curation Agent
        Input: Deck needs + 75 candidates
        Output: CardSuggestions (structured JSON)
        LLM Call: ~2-5 seconds
        └─ Pydantic model: {top_picks: [5-7], overall_strategy}
             └─ Validation: card names must exist in candidate list
   ↓
Format output as markdown → return to user
```

## Technical Decisions

### Decision 1: Structured Outputs via Pydantic Models

**Why**: Type safety prevents errors, validates data at runtime, self-documenting.

**Models**:

```python
# Stage 1 Output
class DeckAnalysis(BaseModel):
    primary_synergy: str  # e.g., "tribal-goblin"
    search_criteria: dict[str, Any]  # {colors, types, oracle_text_phrases}
    reasoning: str  # Why these cards would help

# Stage 3 Output
class CuratedCard(BaseModel):
    card_name: str
    synergy_fit: str  # 1 sentence explanation
    priority: int = Field(ge=1, le=5)  # 1=must-have

class CardSuggestions(BaseModel):
    top_picks: list[CuratedCard] = Field(min_length=5, max_length=7)
    overall_strategy: str  # How these cards work together
```

**Validation guarantees**:
- Analysis always returns valid search criteria (types, phrases, CMC)
- Curation always returns 5-7 picks with priorities 1-5
- LLM can't return malformed JSON (Pydantic validates)

### Decision 2: Configurable Candidate Pool (50-150, Default 75)

**Why**: Balance between suggestion quality and performance.

**Token analysis**:
- 30 candidates: ~4,500 tokens (too limiting, might miss gems)
- 75 candidates: ~11,250 tokens (good diversity, <8% of context window)
- 100 candidates: ~15,000 tokens (excellent coverage, still only 7.5%)
- 150 candidates: ~22,500 tokens (diminishing returns, choice overload)

**Decision**: Default to 75, allow 50-150 range.

**Rationale**:
- 75 cards = good coverage from 3-5 searches (15-25 per search)
- Claude Sonnet 4.5 context window = 200k tokens (75 cards = 5.6% usage)
- LLM curation quality stays high up to ~100 items (research-backed)
- Token cost increase: ~$0.005 vs 30 candidates (negligible)

**Configuration**:
```python
async def _search_candidates(
    analysis_result: DeckAnalysisResult,
    card_repo: CardRepository,
    format_filter: FormatFilter,
    target_candidates: int = 75,  # Configurable
) -> list[Card]:
    # Validate range
    target_candidates = max(50, min(150, target_candidates))

    # Calculate per-search limit
    num_searches = len(analysis_result.analyses)  # 3-5
    per_search = math.ceil(target_candidates / num_searches)  # 15-30

    # Execute parallel searches...
```

### Decision 3: Parallel Database Searches

**Why**: Keep search latency low despite multiple queries.

**Implementation**:
```python
search_tasks = [
    card_repo.search_advanced(...)
    for analysis in deck_analysis.analyses
]
results = await asyncio.gather(*search_tasks)  # Parallel execution
```

**Performance**:
- Serial: 3 searches × 200ms = 600ms
- Parallel: max(200ms, 200ms, 200ms) = 200ms
- Speedup: 3x faster

### Decision 4: Hallucination Prevention via Validation

**Why**: LLM might suggest cards not in candidate list (hallucination).

**Strategy**:
```python
# After curation LLM returns suggestions
candidate_names = {c.name for c in candidates}  # Set for O(1) lookup

for suggested in curation_result.suggestions:
    if suggested.card_name not in candidate_names:
        logger.warning(f"LLM hallucinated card: {suggested.card_name}")
        continue  # Skip invalid suggestion

    validated_suggestions.append(...)
```

**Fallback**: If all suggestions invalid, return top 5 candidates by CMC with generic explanations.

### Decision 5: No Caching for MVP

**Why**: Complexity outweighs benefits for single-user application.

**Considerations**:
- Decks change frequently (adding/removing cards)
- Cache invalidation is non-trivial (deck hash? card list hash?)
- Single-user load doesn't justify caching overhead
- Latency (5-10s) is acceptable for on-demand feature

**Future**: Revisit if latency feedback is negative or multi-user scenarios emerge.

## Data Flow

```
1. User Request
   ↓
2. Tool: suggest_synergy_cards(ctx)
   ↓
3. Load active deck + detect synergies (existing logic)
   ↓
4. Build deck context string (~500 chars)
   ├─ Card counts by type
   ├─ Average CMC
   └─ Synergy summary
   ↓
5. Analysis Agent.run(deck_context)
   → Returns: DeckAnalysis {primary_synergy, search_criteria, reasoning}
   ↓
6. Parse search_criteria → Execute 3-5 parallel searches
   → Returns: 50-150 Card objects
   ↓
7. Build candidate list string (~11k tokens for 75 cards)
   ├─ Format: "Name (cost, type): oracle_text..."
   └─ One per line
   ↓
8. Curation Agent.run(deck_needs + candidates)
   → Returns: CardSuggestions {top_picks[5-7], overall_strategy}
   ↓
9. Validate: filter suggestions to only those in candidate list
   ↓
10. Format as markdown with card hover previews
    ↓
11. Return to user
```

## Error Handling

### LLM Failures

**Scenario**: Analysis agent times out or returns invalid JSON

**Handling**:
```python
try:
    result = await analysis_agent.run(deck_context)
    analysis = result.output
except Exception as e:
    logger.error(f"Analysis failed: {e}")
    return "Unable to analyze deck for suggestions. Please try again."
```

**No silent failures**: User always gets feedback.

### No Candidates Found

**Scenario**: Database search returns 0 results (restrictive format + criteria)

**Handling**:
```python
if not candidates:
    return (
        f"No matching cards found in {format_filter}. "
        f"Try adjusting deck composition or format filter."
    )
```

### All Suggestions Invalid (Hallucination)

**Scenario**: Curation agent suggests cards not in candidate list

**Handling**:
```python
if not validated_suggestions:
    # Fallback: top 5 by CMC
    sorted_candidates = sorted(candidates, key=lambda c: c.mana_value)[:5]
    return [
        CardSuggestion(
            card=card,
            explanation=f"{card.name} is a format-legal card that may fit your deck.",
            synergy_type="fallback",
            priority=3
        )
        for card in sorted_candidates
    ]
```

**Logging**: Always log hallucinations for debugging.

## Performance Budgets

| Stage | Target | Max |
|-------|--------|-----|
| Analysis LLM | 2s | 5s |
| Database search | 0.5s | 1s |
| Curation LLM | 3s | 7s |
| **Total** | **5.5s** | **10s** |

**Token Budget**:
- Deck context: ~500 tokens
- Analysis output: ~300 tokens
- Candidates (75): ~11,250 tokens
- Curation output: ~500 tokens
- **Total**: ~12,550 tokens/request

**Cost Budget** (at OpenRouter rates ~$0.015/1k tokens):
- ~$0.19 per request × 2 LLM calls = **~$0.38/request**
- Acceptable for premium AI feature

## Testing Strategy

### Unit Tests
- Test Pydantic model validation (valid/invalid inputs)
- Test `_search_candidates()` with mock repository
- Test hallucination filter logic

### Integration Tests
- Test full workflow with real database + mock LLM
- Test format filter enforcement
- Test error scenarios (no deck, empty deck, no candidates)

### Performance Tests
- Measure latency for typical deck (60 cards, 3 synergies)
- Verify parallel searches work (not serial)
- Measure token usage per request

## Risks / Trade-offs

### Risk: LLM Quality Inconsistency

**Risk**: Suggestions quality varies based on LLM performance.

**Mitigation**:
- Structured outputs reduce variance (enforces format)
- Validation prevents hallucinations
- Detailed prompts guide LLM reasoning
- Fallback mechanism ensures graceful degradation

### Risk: Latency Unacceptable to Users

**Risk**: 5-10 seconds feels slow in interactive flow.

**Mitigation**:
- Set expectations ("Analyzing deck... ~10 seconds")
- Magic-themed loading messages (already implemented)
- Consider: "Quick suggestions" mode with fewer candidates (30) and faster turnaround (3-5s)

**Trade-off**: Fast but lower quality vs slow but high quality.

### Risk: Token Costs Spiral

**Risk**: 75 candidates × many requests = high costs.

**Mitigation**:
- Monitor usage with ctx.usage tracking
- Set per-user rate limits if needed (future)
- Candidate pool is configurable (can reduce to 50)

**Trade-off**: Quality vs cost.

## Migration Plan

### Phase 1: Implementation
1. Create specialized agents (analysis, curation)
2. Implement orchestration tool
3. Write tests
4. Manual testing with various deck archetypes

### Phase 2: Deployment
1. Register tool with main agent
2. Update documentation (CLAUDE.md)
3. No data migration needed (new feature)

### Phase 3: Monitoring
1. Track token usage per request
2. Monitor latency distribution
3. Collect user feedback on suggestion quality
4. Adjust candidate pool size if needed

### Rollback Plan
If feature has issues:
1. Unregister tool from main agent (1-line change)
2. Users can still use `detect_deck_synergies` (unaffected)
3. No data corruption risk (read-only feature)

## Open Questions

### Q1: Expose candidate pool size to users?

**Options**:
1. Internal only (default 75) - **Recommended**
2. Optional parameter: `suggest_synergy_cards(candidate_pool_size=100)`
3. User preference setting (persists across sessions)

**Decision**: Start with internal only. Add parameter if power users request it.

### Q2: Should analysis agent consider mana curve gaps?

**Current**: Uses synergy analysis output (tribal, keyword, combos)

**Enhancement**: Also analyze mana curve distribution and suggest cards that fill gaps.

**Decision**: Start simple (synergies only). Add curve analysis if user feedback indicates need.

### Q3: Support for "exclude cards" parameter?

**Use case**: "Suggest cards but not Lightning Bolt" (user already owns/dislikes card)

**Implementation**: Filter candidates list before curation.

**Decision**: Nice-to-have, not MVP. Add if requested.

## References

- PydanticAI Agents: https://ai.pydantic.dev/agents/
- PydanticAI Structured Outputs: https://ai.pydantic.dev/output/
- Research: LLM selection quality (n=100 items): High quality, n=200: Degrades
- OpenRouter pricing: https://openrouter.ai/models (Claude Sonnet 4.5 rates)

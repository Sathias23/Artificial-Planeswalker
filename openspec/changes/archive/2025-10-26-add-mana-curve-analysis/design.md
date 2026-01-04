# Mana Curve Analysis - Technical Design

## Context

Mana curve analysis is a fundamental deck building concept in Magic: The Gathering. The distribution of cards by mana value directly impacts a deck's ability to play spells on curve and execute its game plan. This feature enables the AI assistant to provide strategic deck building feedback beyond simple rule validation.

### Constraints
- Must work with existing `Deck` and `Card` Pydantic models
- Pure business logic (no database dependencies in analysis functions)
- Integration with PydanticAI agent tool system
- Text-based visualization suitable for Chainlit chat interface
- Performance target: < 100ms for analysis of 60-card deck

### Stakeholders
- MTG Arena players building Standard format decks
- Users learning deck building fundamentals
- Future: Advanced players seeking optimization insights

## Goals / Non-Goals

### Goals
- Calculate mana value distribution for any deck
- Identify common curve problems (top-heavy, missing early plays, insufficient lands)
- Provide archetype-specific curve recommendations (aggro vs control)
- Display curve as readable text chart in chat interface
- Enable natural language queries ("analyze my mana curve", "is my curve good?")

### Non-Goals
- Advanced statistical analysis (percentiles, opening hand probabilities) - deferred to post-MVP
- Curve simulation or Monte Carlo analysis - deferred
- Multivariate analysis (curve + card types + synergies) - deferred to Story 5.3-5.4
- Graphical curve visualization - deferred to CopilotKit UI phase

## Decisions

### Decision 1: Rule-Based Analysis vs AI-Driven Insights

**Chosen Approach**: Rule-based analysis with predefined heuristics

**Rationale**:
- Mana curve best practices are well-established in MTG theory
- Rule-based approach is deterministic, testable, and explainable
- Faster execution (no LLM calls for analysis logic)
- AI agent handles natural language query interpretation, business logic handles analysis

**Alternatives Considered**:
- LLM-driven analysis: Would require additional API calls, slower, less predictable
- Machine learning model: Overkill for MVP, no training data available

**Implementation**:
```python
# Business logic analyzes curve with predefined rules
def analyze_curve(curve: dict[int, int], total_cards: int, archetype: str | None = None) -> CurveAnalysis:
    # Rule-based heuristics
    problems = detect_curve_problems(curve, total_cards)
    recommendations = suggest_ideal_curve(archetype or infer_archetype(curve))
    return CurveAnalysis(distribution=curve, problems=problems, recommendations=recommendations)
```

### Decision 2: Mana Value Grouping Strategy

**Chosen Approach**: Bucket mana values 0-7+ (8 buckets)

**Rationale**:
- Aligns with MTG conventions (most decks max out at 6-7 mana)
- Prevents chart clutter from rarely-used high mana values
- Matches industry standards (MTGGoldfish, Archidekt use similar bucketing)

**Buckets**: `{0, 1, 2, 3, 4, 5, 6, 7+}`

**Example**:
```
0 CMC: ▮▮ (2 cards)
1 CMC: ▮▮▮▮▮▮▮▮ (8 cards)
2 CMC: ▮▮▮▮▮▮▮▮▮▮▮▮ (12 cards)
3 CMC: ▮▮▮▮▮▮▮ (7 cards)
4 CMC: ▮▮▮▮ (4 cards)
5 CMC: ▮▮ (2 cards)
6 CMC: ▮ (1 card)
7+ CMC: ▮ (1 card)
```

### Decision 3: Archetype Detection vs User-Specified

**Chosen Approach**: Hybrid - infer archetype from curve, allow user override (future)

**Rationale**:
- MVP: Infer archetype from curve shape (low curve = aggro, high curve = control)
- Simple heuristic: avg CMC < 2.5 = aggro, 2.5-3.5 = midrange, > 3.5 = control
- Future: Allow users to specify archetype explicitly for better recommendations

**Implementation**:
```python
def infer_archetype(curve: dict[int, int]) -> str:
    avg_cmc = calculate_average_cmc(curve)
    if avg_cmc < 2.5:
        return "aggro"
    elif avg_cmc < 3.5:
        return "midrange"
    else:
        return "control"
```

### Decision 4: Problem Detection Heuristics

**Chosen Approach**: Flagging based on established MTG deck building principles

**Problem Categories**:
1. **Top-heavy curve**: > 30% of cards at CMC 5+
2. **Missing early plays**: < 20% of cards at CMC ≤ 2
3. **Insufficient lands**: Land count < 33% of total deck (< 20 lands in 60-card deck)
4. **Mana flood risk**: Land count > 45% of deck
5. **Awkward curve**: Large gaps in mana values (e.g., 0 cards at CMC 3)

**Thresholds Based on Research**:
- Draftsim recommends 17 lands in 40-card Limited decks (42.5%)
- Standard Constructed typically runs 22-26 lands in 60-card decks (36-43%)
- Aggro decks want 60-70% of spells at CMC ≤ 3
- Control decks want 50-60% at CMC 3-6

### Decision 5: Text Visualization Format

**Chosen Approach**: Markdown table + horizontal bar chart

**Rationale**:
- Chainlit renders markdown natively
- Horizontal bars more readable than vertical ASCII charts in chat
- Include both absolute counts and percentages

**Example Output**:
```markdown
## Mana Curve Analysis

| CMC | Count | % of Deck | Chart |
|-----|-------|-----------|-------|
| 0   | 2     | 3%        | ▮▮ |
| 1   | 8     | 13%       | ▮▮▮▮▮▮▮▮ |
| 2   | 12    | 20%       | ▮▮▮▮▮▮▮▮▮▮▮▮ |
| 3   | 10    | 17%       | ▮▮▮▮▮▮▮▮▮▮ |
| 4   | 6     | 10%       | ▮▮▮▮▮▮ |
| 5   | 3     | 5%        | ▮▮▮ |
| 6   | 1     | 2%        | ▮ |
| 7+  | 1     | 2%        | ▮ |

**Total Cards**: 60
**Average CMC**: 2.8
**Lands**: 17 (28%)
```

### Decision 6: Data Flow Architecture

**Chosen Approach**: Three-layer separation (data → logic → agent)

**Flow**:
1. **Agent Tool** (`analyze_mana_curve`) - Fetches deck via repository
2. **Business Logic** (`src/logic/mana_curve.py`) - Pure functions, no I/O
3. **UI Formatter** (`format_mana_curve`) - Converts analysis to markdown

**Why**:
- Business logic independently testable (no mocking repositories)
- Follows existing architecture patterns (deck validation, card queries)
- Enables future UI replacement (logic stays unchanged)

**Example**:
```python
# Agent tool (orchestration)
@agent.tool
async def analyze_mana_curve(ctx: RunContext[AgentDependencies]) -> str:
    deck = await ctx.deps.deck_repository.get_deck(ctx.deps.active_deck_id)
    analysis = calculate_and_analyze_curve(deck)  # Pure business logic
    return format_mana_curve(analysis)  # UI formatting

# Business logic (pure function)
def calculate_and_analyze_curve(deck: Deck) -> CurveAnalysis:
    curve = calculate_mana_curve(deck.deck_cards)
    problems = detect_curve_problems(curve, deck.total_cards)
    archetype = infer_archetype(curve)
    recommendations = suggest_ideal_curve(archetype)
    return CurveAnalysis(curve, problems, recommendations, archetype)
```

## Risks / Trade-offs

### Risk 1: Heuristic Accuracy
- **Risk**: Rule-based curve analysis may not match expert player intuition for complex archetypes
- **Mitigation**: Start with conservative, well-established heuristics; gather user feedback; iterate
- **Trade-off**: Simpler implementation, faster execution vs potentially less nuanced advice

### Risk 2: Archetype Misclassification
- **Risk**: Inferring archetype from curve alone may misidentify hybrid strategies (aggro-control, tempo)
- **Mitigation**: MVP uses broad categories; future iterations can incorporate card types and synergies
- **Acceptance**: Minor misclassification acceptable for MVP; users can work around with natural language ("analyze my aggro deck")

### Risk 3: Text Chart Readability
- **Risk**: Horizontal bar charts may not scale well for mobile or small screens
- **Mitigation**: Test on tablets; Chainlit mobile not prioritized for MVP
- **Future**: CopilotKit UI phase can add graphical charts

### Risk 4: Performance on Large Decks
- **Risk**: Curve calculation might be slow for Commander decks (100 cards)
- **Mitigation**: MVP focuses on Standard (60 cards); O(n) calculation is trivial for n=60-100
- **Measurement**: Benchmark with 100-card deck, ensure < 100ms

## Migration Plan

### Phase 1: Core Implementation (This Change)
1. Implement business logic in `src/logic/mana_curve.py`
2. Add `analyze_mana_curve` tool to agent
3. Add text formatting to `src/ui/formatters.py`
4. Write comprehensive unit tests

### Phase 2: Integration Testing (This Change)
1. Test with sample aggro/midrange/control decks
2. Validate natural language query handling
3. Ensure formatting renders correctly in Chainlit

### Phase 3: Future Enhancements (Post-MVP)
1. Story 5.2: Automatic curve feedback during deck building (proactive suggestions)
2. Story 5.3-5.4: Synergy detection integration (curve + card types)
3. CopilotKit UI: Graphical curve visualization

### Rollback Plan
- Feature is additive (new tool, no breaking changes)
- Rollback: Remove `analyze_mana_curve` tool from agent tools list
- No database migrations required
- No data loss risk

## Open Questions

1. **Q**: Should lands be included in curve calculation or tracked separately?
   - **A**: Track separately - lands are fundamental to curve but not part of spell curve analysis

2. **Q**: How to handle split cards, double-faced cards, and X-cost spells?
   - **A**:
     - Split cards: Use minimum CMC of either side
     - Double-faced cards: Use front face CMC
     - X spells: Use X=0 (count as CMC of non-X mana symbols)
     - Follow Scryfall's `cmc` field from bulk data

3. **Q**: Should we analyze mainboard only or include sideboard?
   - **A**: Mainboard only for curve analysis (sideboard is situational tech)

4. **Q**: How to handle user queries about specific archetypes?
   - **A**: Agent can pass archetype hint to analysis function via natural language processing
   - Example: "analyze my aggro deck's curve" → `analyze_curve(deck, archetype_hint="aggro")`

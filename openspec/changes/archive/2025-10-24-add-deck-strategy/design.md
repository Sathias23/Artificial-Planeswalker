# Design: Add Deck Strategy Field

## Context

The AI agent currently lacks context about a deck's intended strategy when making card recommendations. Users want to specify strategies like "control", "aggro", "midrange", or provide detailed strategic descriptions that the agent can use to suggest synergistic cards.

**Background**:
- Current deck model: id, name, format, timestamps
- Agent makes recommendations based only on format and existing cards
- No way to communicate strategic intent to the agent

**Constraints**:
- Must be backward compatible (existing decks without strategy)
- Must support both simple labels and detailed explanations
- Must integrate with existing agent tools and UI sidebar

**Stakeholders**:
- End users (deck builders)
- Agent (card recommendation logic)
- UI layer (strategy display)

## Goals / Non-Goals

### Goals
- Add flexible strategy field to deck model (supports labels and descriptions)
- Display strategy in deck information sidebar
- Enable agent to use strategy for better card recommendations
- Maintain backward compatibility with existing decks
- Enable future strategy-based filtering

### Non-Goals
- Validate strategy against predefined list (free-form text)
- Implement strategy-based deck archetypes (future work)
- Add strategy-specific validation rules (future work)
- Implement strategy auto-detection from cards (future work)

## Decisions

### Decision 1: Use String column type (not JSON or enum)

**Choice**: SQLAlchemy String column, nullable, indexed

**Rationale**:
- String type supports both short labels ("control") and detailed explanations
- More flexible than enum (no predefined strategy list)
- Simpler than JSON (no complex nested data needed)
- Nullable enables backward compatibility
- Index enables future filtering (e.g., "show all aggro decks")

**Alternatives considered**:
1. **Enum type** - Too rigid, requires predefined strategy list
2. **JSON column** - Unnecessary complexity for simple text field
3. **Text type (no index)** - Loses ability to filter by strategy efficiently

### Decision 2: Make strategy optional (nullable)

**Choice**: `strategy: Mapped[str | None] = mapped_column(String, nullable=True, index=True, default=None)`

**Rationale**:
- Backward compatible with existing decks (no migration data needed)
- Users can create decks without specifying strategy immediately
- Can be added or updated later via update tool

**Alternatives considered**:
1. **Required field with default** - Forces migration, reduces flexibility
2. **Separate strategy table** - Over-engineered for simple text field

### Decision 3: Pass strategy to agent via dependencies

**Choice**: Include strategy in agent context via `AgentDependencies` when deck is active

**Rationale**:
- Existing pattern for passing context to tools (format_filter, active_deck_id)
- Tools can access strategy through deps without changing signatures
- Agent system prompt can include strategy context when available

**Alternatives considered**:
1. **Separate strategy parameter in each tool** - More coupling, harder to maintain
2. **Global strategy state** - Harder to test, less explicit

### Decision 4: Display strategy in sidebar with deck metadata

**Choice**: Add strategy to deck info section in `update_deck_sidebar()`, below format and above card count

**Rationale**:
- Strategy is deck metadata (like format)
- Visible context for users while building
- Consistent with existing sidebar layout

**Alternatives considered**:
1. **Separate strategy section** - Adds visual clutter
2. **Inline with deck name** - Too crowded
3. **Tooltip/hover** - Less discoverable

## Database Migration

### Migration Steps
1. Add nullable `strategy` column to `decks` table with index
2. Existing decks automatically have `strategy=NULL`
3. No data backfill required (backward compatible)

### Migration Code (Alembic)
```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('decks', sa.Column('strategy', sa.String(), nullable=True))
    op.create_index('ix_decks_strategy', 'decks', ['strategy'])

def downgrade():
    op.drop_index('ix_decks_strategy', 'decks')
    op.drop_column('decks', 'strategy')
```

### Rollback Plan
- Downgrade migration removes column and index
- No data loss risk (strategy is optional metadata)

## Agent Integration

### Strategy Context in Tools

**Pattern**: Tools access strategy via `deps.active_deck.strategy` (when deck is loaded)

**Example usage in `search_cards_advanced` tool**:
```python
@agent.tool
async def search_cards_advanced(
    ctx: RunContext[AgentDependencies],
    colors: str | None = None,
    types: str | None = None,
    keywords: str | None = None,
    # ... other params
) -> str:
    deps = ctx.deps

    # Access strategy from active deck
    if deps.active_deck and deps.active_deck.strategy:
        strategy_context = f"\n\nDeck strategy: {deps.active_deck.strategy}"
        # Agent can use this context for better recommendations
```

**System prompt enhancement**:
When deck is loaded with strategy, inject into agent context:
```
Current deck: {deck_name} ({format})
Strategy: {strategy}
Use this strategy to guide card recommendations.
```

## UI Integration

### Sidebar Display

**Location**: Deck info section, after format, before card count

**Format**:
```markdown
**Strategy**: {strategy}
```

**Conditional display**:
- Only show if strategy is not None/empty
- Truncate long strategies (show first 200 chars, "..." if longer)

### Example Sidebar Output
```
Deck: Mono Red Aggro (standard)
ID: abc123...
Strategy: Fast aggressive deck aiming to win by turn 5 with burn spells and efficient creatures
Colors: R
Total Cards: 60 (60 mainboard, 0 sideboard)
```

## Risks / Trade-offs

### Risk 1: Free-form text quality
- **Issue**: Users may enter unclear or contradictory strategies
- **Mitigation**: Agent interprets best-effort, users can iterate

### Risk 2: Strategy drift
- **Issue**: Deck evolves but strategy text becomes outdated
- **Mitigation**: Users can update strategy via update_deck tool

### Risk 3: Long strategy text
- **Issue**: Detailed explanations may clutter sidebar
- **Mitigation**: Truncate display to 200 chars with "..."

## Open Questions

1. **Should we suggest strategies to users?** (Future work)
   - Could provide common examples ("aggro", "control", "midrange", "combo")
   - Not required for MVP

2. **Should we validate strategy format?** (Future work)
   - Could warn if strategy is very long (>500 chars)
   - Could suggest structure (goal, win condition, key cards)
   - Not required for MVP

3. **Should we auto-detect strategy from cards?** (Future work)
   - Could analyze existing cards and suggest strategy
   - Requires sophisticated deck analysis
   - Not required for MVP

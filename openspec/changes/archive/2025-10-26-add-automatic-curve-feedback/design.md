# Design: Automatic Curve Feedback During Deck Building

## Context

This change builds on Story 5.1 (add-mana-curve-analysis) by adding **proactive, automatic** feedback when users add cards to their decks. The goal is to provide real-time guidance during deck construction without requiring explicit analysis requests.

**Constraints:**
- Must not overwhelm users with feedback on every single card addition
- Should balance positive reinforcement with constructive warnings
- Must respect user preference to disable auto-feedback
- Session-level preference must persist across messages

**Stakeholders:**
- Deck builders who benefit from real-time guidance
- Users who prefer manual control (must be able to disable)

## Goals / Non-Goals

**Goals:**
- Provide automatic curve feedback after `add_card_to_deck` operations
- Enable users to toggle auto-feedback on/off via agent tool
- Generate contextually appropriate feedback (positive reinforcement + warnings)
- Persist auto-feedback preference across conversation session

**Non-Goals:**
- Feedback for card removals (Story 5.2 scope is additions only)
- Advanced AI-driven feedback generation (pattern-based logic sufficient for MVP)
- Feedback during deck loading or batch imports (triggers on explicit user additions only)

## Decisions

### Decision 1: Feedback Trigger Point
**What:** Auto-feedback triggers **after** `add_card_to_deck` tool completes successfully, appending to the tool result message.

**Why:**
- Ensures feedback is contextually relevant to the just-added card
- Leverages existing tool execution flow (no separate agent invocation needed)
- Agent can naturally incorporate feedback into response stream

**Alternatives Considered:**
- Separate "background" feedback agent running after every turn → Too complex, adds latency
- Pre-flight feedback before card addition → Requires predictive analysis, less natural UX

### Decision 2: Feedback Throttling Strategy
**What:** Generate feedback **only when** curve changes are significant:
- Deck is empty or has < 5 cards (establishing initial curve)
- Added card changes curve distribution by > 15% in any CMC bucket
- Curve issues detected (e.g., zero 1-2 drops in aggro deck)

**Why:**
- Prevents feedback fatigue from repetitive messages ("great addition!" every single time)
- Focuses feedback on meaningful curve shifts
- Balances helpfulness with user autonomy

**Alternatives Considered:**
- Feedback on every addition → Too noisy, users will disable feature
- Feedback only on warnings → Misses positive reinforcement opportunities

### Decision 3: Session Preference Storage
**What:** Store `auto_feedback_enabled` in `AgentDependencies` with persistence via `ConversationSessionManager`.

**Why:**
- `AgentDependencies` already manages session-level state (active deck, format filter)
- `ConversationSessionManager` provides session persistence infrastructure
- Preference survives across messages in same session

**Implementation Pattern:**
```python
# AgentDependencies
@property
def auto_feedback_enabled(self) -> bool:
    return self._session_manager.get_preference("auto_feedback_enabled", default=True)

def set_auto_feedback_enabled(self, enabled: bool) -> None:
    self._session_manager.set_preference("auto_feedback_enabled", enabled)
```

**Alternatives Considered:**
- Database-backed user preferences → Over-engineering for MVP (no user accounts yet)
- Environment variable → Not per-session, affects all users globally

### Decision 4: Feedback Content Strategy
**What:** Contextual feedback includes:
- **Positive reinforcement**: "Good early game addition" (1-2 drops in aggro)
- **Warnings**: "Deck getting top-heavy - consider more early plays" (too many 5+ CMC)
- **Neutral observations**: "Curve balanced across 2-4 mana" (healthy distribution)

**Why:**
- Positive feedback encourages good deck building habits
- Warnings guide users toward corrections before deck is finalized
- Neutral observations validate user's strategic direction

**Tone:** Conversational coach, not authoritative judge. Use "consider" not "must", "might want to" not "you should".

## Risks / Trade-offs

### Risk: Feedback Fatigue
**Mitigation:** Throttling strategy ensures feedback is selective, not constant. User can disable via `toggle_auto_feedback` tool.

### Risk: Incorrect Feedback
**Mitigation:** Feedback is based on statistical curve analysis (defensible) and uses suggestive language ("consider") rather than prescriptive ("you must"). Users retain full control.

### Trade-off: Default Enabled vs Disabled
**Decision:** Default to **enabled** (opt-out model).
**Rationale:** Story 5.2 goal is proactive assistance. Users who find it annoying can easily disable with "turn off auto-feedback" message.

## Migration Plan

**No migration required** - This is a new feature with default-enabled preference.

**User Impact:**
- Existing users will begin receiving auto-feedback on next card addition after deployment
- Users can immediately disable if unwanted: "disable curve feedback"

**Rollback:**
- Remove auto-feedback trigger from `add_card_to_deck` tool
- Preference data persists harmlessly (no cleanup needed)

## Open Questions

- Should feedback frequency be configurable (e.g., "feedback every 3 cards" vs "only on significant changes")? → **Defer to post-MVP** (fixed throttling sufficient for MVP)
- Should feedback reference specific archetype (aggro/control/midrange)? → **Yes, if deck archetype is detectable** (e.g., low average CMC suggests aggro)

# Add Automatic Curve Feedback During Deck Building

## Why

While Story 5.1 (add-mana-curve-analysis) enables users to explicitly request mana curve analysis, deck builders benefit most from **proactive, real-time feedback** as they construct their decks. Without automatic curve feedback, users must remember to manually request analysis, potentially missing critical curve issues until after investing significant time in deck construction.

This proposal implements Story 5.2 from the PRD (Epic 5: Deck Building Intelligence) to transform the agent into a proactive deck building coach that automatically comments on mana curve impact when cards are added, providing contextual guidance without requiring explicit user requests.

## What Changes

- **Agent enhancement**: Automatic curve feedback triggered after `add_card_to_deck` tool execution
- **Session preference**: User-controllable auto-feedback toggle (enable/disable)
- **Contextual feedback logic**: Smart feedback that balances helpfulness with brevity (avoids feedback fatigue)
- **Positive reinforcement**: Highlights good deck building choices in addition to warnings
- **Delta specs**: Modify `agent-tools` for auto-feedback hooks and `deck-intelligence` for contextual feedback logic

## Impact

### Affected Specs
- **MODIFIED**: `agent-tools` - Add auto-feedback hooks to `add_card_to_deck` tool
- **MODIFIED**: `deck-intelligence` - Add contextual feedback generation logic

### Affected Code
- `src/logic/mana_curve.py` (modified) - Add contextual feedback logic functions
- `src/agent/tools/deck_builder.py` (modified) - Trigger auto-feedback after card additions
- `src/agent/dependencies.py` (modified) - Add `auto_feedback_enabled` session preference
- `tests/unit/logic/test_mana_curve.py` (modified) - Test contextual feedback logic
- `tests/integration/agent/test_deck_analysis_tools.py` (modified) - Test auto-feedback triggers

### Research Summary

**Archon RAG Sources Used:**
- PydanticAI documentation (source: `ai.pydantic.dev`) - Agent context and system prompt patterns
- Chainlit documentation (source: `docs.chainlit.io`) - Session state management

**Key Findings:**
- PydanticAI supports dynamic system prompts via context dependencies
- Agent tools can append to result messages with contextual suggestions
- Session-level preferences can be managed via `AgentDependencies`
- Feedback should be limited to significant changes (e.g., not every single card addition in a multi-card batch)

### Dependencies
- **REQUIRED**: `add-mana-curve-analysis` change must be completed first (provides core curve calculation logic)

# Implementation Tasks

## 1. Data Structures and Core Logic
- [ ] 1.1 Define `SynergyPattern` dataclass/Pydantic model (pattern_type, affected_cards, explanation, strength)
- [ ] 1.2 Define `SynergyAnalysis` dataclass/Pydantic model (synergies: list[SynergyPattern], total_count: int)
- [ ] 1.3 Create `src/logic/synergy.py` module with `detect_synergies()` function signature
- [ ] 1.4 Implement tribal synergy detection (extract creature types, find shared types, count occurrences)
- [ ] 1.5 Implement keyword synergy detection (extract keywords from oracle text, find keyword-matters cards)
- [ ] 1.6 Implement mechanic combo detection (sacrifice outlets + death triggers, card draw engines + discard outlets)

## 2. Agent Tool Integration
- [ ] 2.1 Add `detect_synergies` PydanticAI tool to `src/agent/tools/deck_intelligence.py`
- [ ] 2.2 Implement tool function: check for active deck, fetch deck from repository, call `detect_synergies()`
- [ ] 2.3 Add error handling for no active deck scenario
- [ ] 2.4 Return formatted synergy analysis to agent

## 3. UI Formatting
- [ ] 3.1 Add `format_synergies()` function to `src/ui/formatters.py`
- [ ] 3.2 Format synergies as markdown with sections by pattern type (Tribal, Keyword, Mechanic)
- [ ] 3.3 Display card pairs/groups for each synergy with explanations
- [ ] 3.4 Handle empty synergy list gracefully ("No obvious synergies detected yet")

## 4. Testing
- [ ] 4.1 Create `tests/unit/logic/test_synergy.py` with unit tests for each pattern detector
- [ ] 4.2 Test tribal synergy detection with Goblin deck, Elf deck, mixed tribal deck
- [ ] 4.3 Test keyword synergy detection (flying matters + creatures with flying, etc.)
- [ ] 4.4 Test mechanic combo detection (sacrifice + death triggers)
- [ ] 4.5 Test edge cases: empty deck, single card, no synergies found
- [ ] 4.6 Create `tests/integration/test_synergy_tool.py` with end-to-end tool tests
- [ ] 4.7 Test tool with real deck data, natural language queries, error cases
- [ ] 4.8 Verify 90%+ code coverage for synergy logic

## 5. Documentation
- [ ] 5.1 Update CLAUDE.md with synergy detection tool reference
- [ ] 5.2 Add docstrings to all public functions in `src/logic/synergy.py`
- [ ] 5.3 Document pattern detection heuristics and limitations

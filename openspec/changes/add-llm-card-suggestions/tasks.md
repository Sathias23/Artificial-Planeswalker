# Implementation Tasks

## 1. Core Implementation

- [ ] 1.1 Create `src/agent/tools/synergy_suggestions.py` file
  - Define Pydantic models: `DeckAnalysis`, `DeckNeedAnalysis`, `CuratedCard`, `CardSuggestions`
  - Create `analysis_agent` (output_type=DeckAnalysis)
  - Create `curation_agent` (output_type=CardSuggestions)
  - Implement `_build_deck_context()` helper (formats deck for analysis)
  - Implement `_search_candidates()` helper (parallel database searches)
  - Implement `_format_candidates()` helper (formats cards for curation)
  - Implement main `suggest_synergy_cards()` tool with 3-stage orchestration

- [ ] 1.2 Register tool with main agent in `src/agent/core.py`
  - Import `suggest_synergy_cards` from `synergy_suggestions`
  - Add to main agent's tools list
  - Verify tool registration in agent initialization

- [ ] 1.3 Add output formatting helpers to `src/ui/formatters.py`
  - Implement `format_card_suggestions()` (converts CardSuggestions to markdown)
  - Include card hover previews for suggested cards
  - Format priority stars (⭐⭐⭐⭐⭐ for priority 1, etc.)

## 2. Testing

- [ ] 2.1 Write unit tests for Pydantic models (`tests/unit/agent/tools/test_suggestion_models.py`)
  - Test `DeckAnalysis` validation (valid/invalid search_criteria)
  - Test `CardSuggestions` validation (5-7 picks, priorities 1-5)
  - Test model serialization/deserialization

- [ ] 2.2 Write unit tests for helper functions (`tests/unit/agent/tools/test_suggestion_helpers.py`)
  - Test `_build_deck_context()` with various deck compositions
  - Test `_search_candidates()` with mock repository
  - Test `_format_candidates()` output format
  - Test hallucination filtering logic

- [ ] 2.3 Write integration tests (`tests/integration/agent/tools/test_suggestion_workflow.py`)
  - Test full workflow: deck → analysis → search → curation → output
  - Test with real database + mock LLM responses
  - Test format filter enforcement
  - Test error scenarios:
    - No active deck
    - Empty deck
    - LLM analysis failure
    - No candidates found
    - All suggestions invalid (hallucination)

- [ ] 2.4 Write performance tests (`tests/integration/agent/tools/test_suggestion_performance.py`)
  - Measure latency for typical request (60-card deck)
  - Verify parallel searches execute concurrently (not serially)
  - Measure token usage per request
  - Verify stays under 10-second budget

## 3. Documentation

- [ ] 3.1 Update `CLAUDE.md`
  - Add `suggest_synergy_cards()` to tools list
  - Document performance characteristics (~5-10 seconds)
  - Add example usage scenarios
  - Note candidate pool default (75) and range (50-150)

- [ ] 3.2 Add docstrings to all functions
  - Specialized agents: system prompts and output types
  - Helper functions: purpose, parameters, return types
  - Main tool: comprehensive docstring with examples

- [ ] 3.3 Add inline code comments
  - Document LLM prompt strategies
  - Explain validation logic
  - Note error handling approaches

## 4. Manual Testing

- [ ] 4.1 Test with Goblin tribal deck
  - Create deck with 15+ Goblin creatures
  - Request suggestions
  - Verify suggestions are Goblin creatures or Goblin-matters cards
  - Verify no hallucinations (all cards exist)

- [ ] 4.2 Test with Dinosaur tribal deck
  - Create deck with 10+ Dinosaur creatures
  - Request suggestions
  - Verify suggestions are Dinosaurs (not mis-classified)
  - Check explanation quality

- [ ] 4.3 Test with aggressive deck (low CMC)
  - Create deck with avg CMC ~2.0
  - Request suggestions
  - Verify analysis identifies deck strategy
  - Verify suggestions match aggressive strategy

- [ ] 4.4 Test with control deck (high CMC)
  - Create deck with avg CMC ~4.0
  - Request suggestions
  - Verify suggestions include removal/interaction
  - Check for late-game finishers

- [ ] 4.5 Test format filter enforcement
  - Load Standard deck → verify suggestions are Standard-legal
  - Load Modern deck → verify suggestions are Modern-legal
  - Load deck with no format → verify suggestions respect filter setting

## 5. Error Handling & Edge Cases

- [ ] 5.1 Test LLM failure scenarios
  - Mock analysis agent timeout → verify graceful error message
  - Mock curation agent invalid JSON → verify fallback behavior
  - Verify no silent failures (user always gets feedback)

- [ ] 5.2 Test database failure scenarios
  - Mock empty search results → verify "no candidates" message
  - Mock repository exception → verify error handling

- [ ] 5.3 Test hallucination scenarios
  - Mock curation agent suggesting non-existent cards
  - Verify validation filters invalid suggestions
  - Verify fallback mechanism activates

## 6. Performance Optimization

- [ ] 6.1 Verify parallel search execution
  - Add timing logs to `_search_candidates()`
  - Confirm total time ≈ max(individual searches), not sum
  - Target: <1 second for 3-5 parallel searches

- [ ] 6.2 Monitor token usage
  - Add usage tracking to both LLM calls
  - Log total tokens per request
  - Verify stays under 20k tokens/request budget

- [ ] 6.3 Profile candidate list formatting
  - Measure time to format 75 cards for curation prompt
  - Optimize if formatting takes >100ms

## 7. Code Quality

- [ ] 7.1 Run type checking
  - `uv run mypy src/agent/tools/synergy_suggestions.py`
  - Fix all type errors
  - Ensure strict type safety throughout

- [ ] 7.2 Run linting
  - `uv run ruff check src/agent/tools/synergy_suggestions.py --fix`
  - `uv run ruff format src/agent/tools/synergy_suggestions.py`
  - Fix all linting issues

- [ ] 7.3 Run test suite
  - `uv run pytest tests/ -v`
  - Verify all tests pass
  - Target: 80%+ coverage for new code

## 8. Validation

- [ ] 8.1 Run OpenSpec validation
  - `openspec validate add-llm-card-suggestions --strict`
  - Fix any validation errors
  - Ensure all scenarios properly formatted

- [ ] 8.2 Cross-reference with design doc
  - Verify implementation matches architecture decisions
  - Confirm performance budgets are met
  - Check error handling matches design

- [ ] 8.3 User acceptance criteria
  - Suggestions are always real, format-legal cards ✓
  - Explanations are specific to deck strategy ✓
  - Latency is <10 seconds for typical requests ✓
  - Token usage is <20k per request ✓
  - Code is <500 lines total ✓

## Dependencies and Parallelization

**Sequential Dependencies**:
- 1.1 must complete before 1.2, 1.3 (code needed for registration/formatting)
- 1.1-1.3 must complete before 2.x (implementation needed for tests)
- 2.x must complete before 4.x (tests validate before manual testing)
- All above must complete before 8.x (validation is final step)

**Parallelizable Work**:
- 2.1, 2.2, 2.3, 2.4 can run in parallel (independent test suites)
- 3.1, 3.2, 3.3 can be done anytime after 1.1 completes (documentation)
- 4.1-4.5 can run in parallel (independent manual tests)
- 5.1-5.3 can run in parallel (independent error scenarios)
- 6.1-6.3 can run concurrently with 4.x (performance testing)
- 7.1-7.3 can be done anytime after 1.1 completes (code quality)

**Critical Path**: 1.1 → 1.2 → 1.3 → 2.x → 4.x → 8.x

**Estimated Time**: 6-8 hours total
- Implementation: 3-4 hours (1.1-1.3)
- Testing: 2-3 hours (2.x + 4.x + 5.x)
- Documentation: 1 hour (3.x)
- Validation: 30 minutes (8.x)

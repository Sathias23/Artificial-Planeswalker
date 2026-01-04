# Implementation Tasks

## 1. Business Logic Layer
- [ ] 1.1 Create `src/logic/mana_curve.py` module
- [ ] 1.2 Implement `calculate_mana_curve()` function (returns distribution dict)
- [ ] 1.3 Implement `analyze_curve()` function (returns analysis insights)
- [ ] 1.4 Implement `detect_curve_problems()` function (identifies issues)
- [ ] 1.5 Implement `suggest_ideal_curve()` function (archetype-based recommendations)
- [ ] 1.6 Define `CurveAnalysis` dataclass for structured results

## 2. Agent Tools Layer
- [ ] 2.1 Create `src/agent/tools/deck_analysis.py` module
- [ ] 2.2 Implement `analyze_mana_curve` PydanticAI tool
- [ ] 2.3 Integrate tool with agent dependencies (deck repository)
- [ ] 2.4 Add error handling for empty decks and edge cases

## 3. UI Formatting Layer
- [ ] 3.1 Add `format_mana_curve()` function to `src/ui/formatters.py`
- [ ] 3.2 Implement text-based curve chart visualization (ASCII/markdown)
- [ ] 3.3 Format curve statistics (total cards, avg CMC, distribution %)

## 4. Testing
- [ ] 4.1 Write unit tests for `calculate_mana_curve()` with various deck compositions
- [ ] 4.2 Write unit tests for `analyze_curve()` with aggro/midrange/control archetypes
- [ ] 4.3 Write unit tests for `detect_curve_problems()` edge cases
- [ ] 4.4 Write integration tests for `analyze_mana_curve` tool end-to-end
- [ ] 4.5 Achieve 90%+ coverage for business logic layer

## 5. Documentation
- [ ] 5.1 Add docstrings to all mana curve functions
- [ ] 5.2 Update CLAUDE.md with mana curve analysis patterns
- [ ] 5.3 Add example queries to README ("analyze my mana curve")

## 6. Validation
- [ ] 6.1 Run `openspec validate add-mana-curve-analysis --strict`
- [ ] 6.2 Run full test suite (`uv run pytest`)
- [ ] 6.3 Run type checking (`uv run mypy src/`)
- [ ] 6.4 Manual testing with sample decks (aggro, midrange, control)

# Implementation Tasks

## 1. Repository Layer Enhancement
- [x] 1.1 Review existing `CardRepository` query methods for filter support
- [x] 1.2 Add `search_by_keywords()` method if not present (oracle_text search)
- [x] 1.3 Add `search_advanced()` method supporting combined filters (colors AND type AND mana_value range)
- [x] 1.4 Write unit tests for new repository methods

## 2. Advanced Search Tool Implementation
- [x] 2.1 Create `search_cards_advanced()` tool function in `src/agent/tools/card_search.py`
- [x] 2.2 Define Pydantic parameter model for filter criteria (colors, types, mana_value_min/max, keywords)
- [x] 2.3 Implement tool logic calling repository's `search_advanced()` method
- [x] 2.4 Add result limiting/pagination logic (default max 20 results)
- [x] 2.5 Format results as structured text (card names + key attributes)
- [x] 2.6 Add comprehensive docstring for LLM schema generation

## 3. Error Handling and Edge Cases
- [x] 3.1 Handle "no results found" gracefully with helpful suggestions
- [x] 3.2 Handle "too many results" with count + refinement suggestions
- [x] 3.3 Handle invalid filter combinations (e.g., non-existent color codes)
- [x] 3.4 Add logging for query patterns and result statistics

## 4. Testing and Validation
- [x] 4.1 Write unit tests for tool invocation with various filter combinations
- [x] 4.2 Write integration tests for end-to-end agent + tool + database flow
- [x] 4.3 Test natural language queries: "red creatures with haste under 4 mana"
- [x] 4.4 Test edge cases: empty results, 100+ matching cards, invalid keywords
- [x] 4.5 Validate query performance meets NFR7 (<500ms) for typical searches

## 5. Documentation
- [x] 5.1 Update CLAUDE.md with advanced search tool example
- [x] 5.2 Add inline code comments explaining filter parameter handling

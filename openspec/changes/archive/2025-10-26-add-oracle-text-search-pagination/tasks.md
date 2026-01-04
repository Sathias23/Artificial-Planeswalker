# Implementation Tasks

## 1. Database Layer

- [ ] 1.1 Add pagination support to `CardRepository.search_advanced`
  - [ ] 1.1.1 Add `page: int = 1` parameter
  - [ ] 1.1.2 Add `page_size: int = 20` parameter (max 50)
  - [ ] 1.1.3 Calculate OFFSET and LIMIT from page/page_size
  - [ ] 1.1.4 Return total count of matching records (for pagination metadata)
- [ ] 1.2 Add oracle text search to `CardRepository.search_advanced`
  - [ ] 1.2.1 Add `oracle_text_phrases: list[str] | None` parameter
  - [ ] 1.2.2 Implement case-insensitive substring matching with SQL LIKE
  - [ ] 1.2.3 Apply AND logic (all phrases must appear in oracle_text)
  - [ ] 1.2.4 Handle None/empty oracle text gracefully
- [ ] 1.3 Create pagination result model
  - [ ] 1.3.1 Define `PaginatedResult[T]` Pydantic model
  - [ ] 1.3.2 Include: items, total_count, page, page_size, total_pages
  - [ ] 1.3.3 Add to `src/data/schemas/pagination.py`

## 2. Agent Tool Layer

- [ ] 2.1 Update `CardSearchFilters` model
  - [ ] 2.1.1 Add `oracle_text: list[str] | None` field
  - [ ] 2.1.2 Add `page: int = 1` field
  - [ ] 2.1.3 Add `page_size: int = 20` field
  - [ ] 2.1.4 Deprecate `max_results` (maintain for backward compatibility)
  - [ ] 2.1.5 Update field descriptions and examples
- [ ] 2.2 Update `search_cards_advanced` tool function
  - [ ] 2.2.1 Pass oracle_text to repository
  - [ ] 2.2.2 Pass page and page_size to repository
  - [ ] 2.2.3 Handle pagination metadata in response
  - [ ] 2.2.4 Maintain backward compatibility with max_results
- [ ] 2.3 Update result formatting (`_format_search_results`)
  - [ ] 2.3.1 Display pagination status (e.g., "Page 1 of 3")
  - [ ] 2.3.2 Show total results count
  - [ ] 2.3.3 Indicate when more pages are available
  - [ ] 2.3.4 Add oracle text phrases to filter summary
  - [ ] 2.3.5 Update "no results" suggestions to mention oracle text search

## 3. Testing

- [ ] 3.1 Unit tests for repository layer
  - [ ] 3.1.1 Test oracle text phrase matching (single phrase)
  - [ ] 3.1.2 Test oracle text phrase matching (multiple phrases with AND)
  - [ ] 3.1.3 Test oracle text case-insensitivity
  - [ ] 3.1.4 Test oracle text with None/empty values
  - [ ] 3.1.5 Test pagination (first page, middle page, last page)
  - [ ] 3.1.6 Test pagination metadata (total_pages, total_count)
  - [ ] 3.1.7 Test pagination with oracle text + other filters
  - [ ] 3.1.8 Test page_size limits (max 50)
- [ ] 3.2 Unit tests for agent tool
  - [ ] 3.2.1 Test oracle_text parameter forwarding
  - [ ] 3.2.2 Test pagination parameter forwarding
  - [ ] 3.2.3 Test result formatting with pagination
  - [ ] 3.2.4 Test backward compatibility with max_results
  - [ ] 3.2.5 Test combined filters (oracle_text + colors + types + pagination)
- [ ] 3.3 Integration tests
  - [ ] 3.3.1 Test bug 77c559f3 scenario: "target creature you control" + "gains flying"
  - [ ] 3.3.2 Verify returns only 3 cards (Acrobatic Leap, Fleeting Flight, Secret Identity)
  - [ ] 3.3.3 Test pagination through large result sets (50+ cards)
  - [ ] 3.3.4 Test oracle text with format filtering

## 4. Documentation

- [ ] 4.1 Update `CLAUDE.md`
  - [ ] 4.1.1 Document new oracle_text parameter in agent-tools section
  - [ ] 4.1.2 Document pagination parameters (page, page_size)
  - [ ] 4.1.3 Add usage examples for oracle text search
  - [ ] 4.1.4 Add usage examples for pagination
- [ ] 4.2 Update tool docstrings
  - [ ] 4.2.1 Add oracle_text examples to CardSearchFilters
  - [ ] 4.2.2 Add pagination examples to search_cards_advanced
  - [ ] 4.2.3 Document max_results deprecation
- [ ] 4.3 Update bug report
  - [ ] 4.3.1 Mark bug 77c559f3 as "resolved" in bug_reports.jsonl

## 5. Validation

- [ ] 5.1 Run unit tests: `uv run pytest tests/unit/data/repositories/test_card.py -v`
- [ ] 5.2 Run agent tool tests: `uv run pytest tests/unit/agent/tools/test_card_search.py -v`
- [ ] 5.3 Run integration tests: `uv run pytest tests/integration/ -m integration -v`
- [ ] 5.4 Manual testing via Chainlit UI
  - [ ] 5.4.1 Test: "find cards with 'target creature you control' and 'gains flying'"
  - [ ] 5.4.2 Test: "show me blue creatures" → "show me more" (pagination)
  - [ ] 5.4.3 Test: Combined filters with oracle text
- [ ] 5.5 Performance verification
  - [ ] 5.5.1 Verify oracle text search completes in <500ms
  - [ ] 5.5.2 Verify pagination doesn't degrade query performance

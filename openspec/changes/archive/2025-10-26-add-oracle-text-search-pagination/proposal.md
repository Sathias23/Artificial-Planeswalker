# Add Oracle Text Search and Pagination to Advanced Card Search

## Why

Bug report 77c559f3 identified a critical limitation in the `search_cards_advanced` tool: users cannot search for specific card effects in oracle text. When a user requested cards with "target creature you control" AND "gains flying", the tool returned all 31 cards with the flying keyword instead of only cards whose oracle text contains those specific phrases. Additionally, users cannot navigate through large result sets beyond the current 20-card limit, making comprehensive searches difficult.

This prevents users from finding cards with specific mechanics and effects, which is a core use case for deck building. For example, searching for tempo cards that grant flying to your creatures should return Acrobatic Leap and Fleeting Flight, not every creature with flying.

## What Changes

- **ADDED**: Oracle text search capability to `search_cards_advanced` tool
  - New `oracle_text` parameter accepting list of text phrases
  - All phrases must appear in card's oracle text (AND logic)
  - Case-insensitive substring matching
  - Works in combination with existing filters (colors, types, keywords, etc.)

- **ADDED**: Pagination support to `search_cards_advanced` tool
  - New `page` parameter (default: 1) for navigating result pages
  - New `page_size` parameter (default: 20, max: 50) for controlling results per page
  - Replaces current `max_results` parameter (deprecated but maintained for backward compatibility)
  - Returns pagination metadata (current page, total pages, total results)
  - Agent can automatically paginate when users request "show me more" or "next page"

- **MODIFIED**: Repository layer (`CardRepository.search_advanced`)
  - Add `oracle_text_phrases` parameter for text search
  - Add `page` and `page_size` parameters for pagination
  - Return pagination metadata along with results

- **MODIFIED**: Result formatting
  - Display pagination status (e.g., "Page 1 of 3, showing 20 of 52 results")
  - Update suggestions to mention oracle text search when no results found
  - Indicate when more pages are available

## Impact

**Affected specs:**
- `specs/agent-tools/spec.md` - New oracle text search and pagination requirements
- `specs/card-queries/spec.md` - Repository layer pagination support

**Affected code:**
- `src/agent/tools/card_search.py` - Add oracle_text parameter and pagination to tool
- `src/data/repositories/card.py` - Add oracle_text_phrases and pagination to search_advanced
- `tests/unit/agent/tools/test_card_search.py` - Test oracle text filtering and pagination
- `tests/unit/data/repositories/test_card.py` - Test repository pagination behavior

**User Impact:**
- ✅ Users can search for specific card effects ("target creature you control gains flying")
- ✅ Users can navigate through large result sets (e.g., "show me more blue creatures")
- ✅ More precise searches reduce irrelevant results
- ✅ No breaking changes - existing searches continue to work

**Performance Considerations:**
- Oracle text search uses SQL `LIKE` with wildcards (indexed on oracle_text column)
- Pagination reduces result set size, improving response times
- Query performance target: <500ms maintained with combined filters

## Research Summary

**Bug Report Context** (bug 77c559f3):
- User requested: "target creature you control" + "gains flying"
- Tool returned: 31 cards with flying keyword (too broad)
- Expected: 3 cards (Acrobatic Leap, Fleeting Flight, Secret Identity)
- Root cause: No oracle text phrase search, only keyword search

**Database Schema** (`src/data/models/card.py`):
- `oracle_text: str | None` column exists and is populated
- Contains full card effect text from Scryfall
- Currently only searched via `keywords` parameter (keyword extraction)
- Ready for `LIKE` queries with proper indexing

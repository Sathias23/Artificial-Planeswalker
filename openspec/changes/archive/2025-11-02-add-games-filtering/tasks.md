# Implementation Tasks

## 1. Data Layer - Add Games Field
- [x] 1.1 Add games field to CardModel in src/data/models/card.py
- [x] 1.2 Add games field to Card Pydantic schema in src/data/schemas/card.py
- [x] 1.3 Update transformer to extract games in src/data/importers/transformers.py
- [x] 1.4 Add games to test fixtures in tests/fixtures/card_data.py

## 2. Data Layer - Filtering
- [x] 2.1 Add GamesFilter type alias in src/data/repositories/card.py
- [x] 2.2 Implement _apply_games_filter() method in CardRepository
- [x] 2.3 Add games parameter to find_by_name_exact()
- [x] 2.4 Add games parameter to find_by_name_partial()
- [x] 2.5 Add games parameter to find_by_colors()
- [x] 2.6 Add games parameter to find_by_type()
- [x] 2.7 Add games parameter to search_by_keywords()
- [x] 2.8 Add games parameter to search_advanced()

## 3. Agent Layer - Session State
- [x] 3.1 Add games_filter field to AgentDependencies
- [x] 3.2 Update ConversationSessionManager to persist games_filter preference in-memory
- [x] 3.3 Add games_filter to session serialization

## 4. Agent Layer - Tools
- [x] 4.1 Create src/agent/tools/games_filter.py with set_games_filter() tool
- [x] 4.2 Update lookup_card_by_name() to use games filter from session
- [x] 4.3 Update search_cards_advanced() to accept games parameter with auto_filter
- [x] 4.4 Register games_filter tool in src/agent/core.py

## 5. UI Layer - Display
- [x] 5.1 Update format_card_details() to show games availability
- [x] 5.2 Update format_card_list() to show games availability in table
- [x] 5.3 Update update_deck_sidebar() to display active games filter above deck info (PLUS format filter)
- [x] 5.4 Add games availability to card hover tooltips

## 6. Database Migration
- [x] 6.1 Re-import Scryfall data to populate games field
- [x] 6.2 Verify games field populated correctly in database

## 7. Testing
- [x] 7.1 Add unit tests for _apply_games_filter() in tests/unit/data/test_card_repository.py
- [x] 7.2 Add unit tests for set_games_filter() tool
- [x] 7.3 Add integration tests for games filtering in card searches
- [x] 7.4 Test games filter persistence across sessions
- [x] 7.5 Test auto-filter bypass with auto_filter=False

## 8. Documentation
- [x] 8.1 Update CLAUDE.md with games filtering documentation
- [x] 8.2 Add games filtering examples to CLAUDE.md CardRepository section
- [x] 8.3 Update .env.example if any new environment variables added

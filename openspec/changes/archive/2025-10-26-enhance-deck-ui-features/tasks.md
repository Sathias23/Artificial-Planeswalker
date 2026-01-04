# Implementation Tasks

## 1. Enhanced Deck List Display
- [ ] 1.1 Add `created_at` and `updated_at` timestamp fields to Deck model
- [ ] 1.2 Add `tags` field to Deck model for win conditions/deck tags
- [ ] 1.3 Update DeckRepository.list_decks() to include new fields in response
- [ ] 1.4 Calculate color identity from deck cards in list_decks tool
- [ ] 1.5 Format deck list output with color symbols, timestamps, and detailed counts
- [ ] 1.6 Add tests for enhanced deck list formatting

## 2. Configurable Card Hover Direction
- [ ] 2.1 Add `CARD_HOVER_DIRECTION` environment variable (default: "right")
- [ ] 2.2 Update `.env.example` with hover direction configuration
- [ ] 2.3 Create CSS classes for left-side and right-side hover positioning
- [ ] 2.4 Update `wrap_card_name_with_hover()` to apply direction-based CSS class
- [ ] 2.5 Ensure sidebar deck panel always uses left positioning (override)
- [ ] 2.6 Add tests for hover direction configuration

## 3. Documentation
- [ ] 3.1 Update CLAUDE.md with new deck list fields
- [ ] 3.2 Document hover direction configuration in CLAUDE.md
- [ ] 3.3 Add migration notes for database schema changes

# Implementation Tasks

## 1. Data Layer Schema Updates
- [ ] 1.1 Add `image_uris` JSON column to `CardModel` in `src/data/models/card.py`
- [ ] 1.2 Add `image_uris` optional field to `Card` Pydantic schema in `src/data/schemas/card.py`
- [ ] 1.3 Update unit tests in `tests/unit/data/test_models.py` to verify `image_uris` field
- [ ] 1.4 Update unit tests in `tests/unit/data/test_schemas.py` for Pydantic schema validation

## 2. Data Import Updates
- [ ] 2.1 Update `transform_scryfall_card()` in `src/data/importers/transformers.py` to extract `image_uris`
- [ ] 2.2 Add unit test in `tests/unit/data/importers/test_transformers.py` for `image_uris` extraction
- [ ] 2.3 Test transformer with double-faced cards (verify graceful handling when `image_uris` is absent)

## 3. Database Migration
- [ ] 3.1 Document migration steps in `docs/` or `MIGRATION.md`
- [ ] 3.2 Back up existing database before re-import
- [ ] 3.3 Re-run Scryfall bulk data import with updated transformer
- [ ] 3.4 Verify sample cards have `image_uris` populated in database

## 4. UI Formatter Implementation
- [ ] 4.1 Create `format_card_with_image()` function in `src/ui/formatters.py`
- [ ] 4.2 Implement fallback logic: use image formatter if `card.image_uris` exists, else text-only
- [ ] 4.3 Add unit tests in `tests/unit/ui/test_formatters.py` for image formatter
- [ ] 4.4 Test formatter with cards that have no `image_uris` (ensure graceful degradation)

## 5. Agent Tool Integration
- [ ] 5.1 Update `lookup_card_by_name()` in `src/agent/tools/card_lookup.py` to use image formatter
- [ ] 5.2 Update `search_cards_advanced()` in `src/agent/tools/card_search.py` to use image formatter
- [ ] 5.3 Update tool tests to verify image formatter usage when `image_uris` present

## 6. Manual Testing and Verification
- [ ] 6.1 Start Chainlit app and request card with image ("show me Lightning Bolt with image")
- [ ] 6.2 Verify image displays inline in chat interface
- [ ] 6.3 Test with multi-card search results (verify images don't overflow UI)
- [ ] 6.4 Test with double-faced cards or cards without `image_uris` (verify text fallback)
- [ ] 6.5 Test image loading performance with slow network (verify timeout/error handling)

## 7. Documentation
- [ ] 7.1 Update CLAUDE.md to document image display capability
- [ ] 7.2 Add migration notes for existing deployments
- [ ] 7.3 Document image size selection rationale ("normal" size chosen for balance)

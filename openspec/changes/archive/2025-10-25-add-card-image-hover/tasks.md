# Implementation Tasks: Add Card Image Hover Preview

## 1. CSS Styling
- [ ] 1.1 Create `public/card-preview.css` with hover tooltip styles
- [ ] 1.2 Add tooltip container styles (position, z-index, visibility)
- [ ] 1.3 Add hover trigger styles (pointer cursor, transition effects)
- [ ] 1.4 Add image styles (size, border, shadow, loading spinner)
- [ ] 1.5 Add responsive positioning (prevent overflow at screen edges)
- [ ] 1.6 Test across different screen sizes and layouts

## 2. Formatter Updates
- [ ] 2.1 Add `wrap_card_name_with_hover()` function in formatters.py
- [ ] 2.2 Extract image URL from Card.image_uris (prefer 'normal' size)
- [ ] 2.3 Generate HTML span with data-image-url attribute
- [ ] 2.4 Add fallback for cards without image URLs
- [ ] 2.5 Update `format_card_for_display()` to use hover wrapper
- [ ] 2.6 Update `format_card_list()` to use hover wrapper
- [ ] 2.7 Update deck list formatter (`_format_deck_cards_by_type()`) to use hover wrapper
- [ ] 2.8 Update sidebar deck list formatter to use hover wrapper

## 3. Configuration
- [ ] 3.1 Update `.chainlit/config.toml` to include card-preview.css in custom_css
- [ ] 3.2 Add environment variable `CARD_IMAGE_HOVER_ENABLED` for feature toggle
- [ ] 3.3 Update `.env.example` with new environment variable

## 4. Testing
- [ ] 4.1 Test hover on single card lookup results
- [ ] 4.2 Test hover on multiple card search results
- [ ] 4.3 Test hover on deck list view
- [ ] 4.4 Test hover on sidebar deck cards
- [ ] 4.5 Test fallback for cards without images
- [ ] 4.6 Test responsive behavior on small screens
- [ ] 4.7 Test with feature flag disabled
- [ ] 4.8 Add unit tests for `wrap_card_name_with_hover()` function

## 5. Documentation
- [ ] 5.1 Update CLAUDE.md with card image hover feature documentation
- [ ] 5.2 Add code comments explaining HTML structure and CSS classes
- [ ] 5.3 Document fallback behavior
- [ ] 5.4 Update .env.example comments

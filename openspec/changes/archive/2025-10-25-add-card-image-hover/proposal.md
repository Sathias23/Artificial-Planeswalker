# Change Proposal: Add Card Image Hover Preview

## Why

Users need a quick visual reference when browsing card search results or deck lists. Currently, card names appear as plain text, requiring users to mentally recall card images or navigate away to view them. This interrupts the natural flow of deck building and card evaluation.

Adding hover-preview functionality will:
- Reduce cognitive load by showing card images inline
- Speed up card evaluation and deck building workflow
- Improve user experience with visual feedback
- Leverage existing Scryfall card image data already available in the system

## What Changes

- Add HTML-based hover tooltip functionality for card names in chat messages
- Utilize Scryfall card image URLs from existing `Card.image_uris` field
- Implement CSS styling for hover preview (similar to visual mana symbol approach)
- Update card formatters to wrap card names in hover-enabled HTML spans
- Apply to all card displays: lookup results, search results, deck lists, view deck output
- Add graceful fallback when image URLs unavailable

## Impact

### Affected Specs
- `chainlit-ui` - New requirements for card name formatting with hover previews

### Affected Code
- `src/ui/formatters.py` - Update card formatting functions to add hover HTML
- `public/card-preview.css` - New CSS file for hover tooltip styling
- `.chainlit/config.toml` - Add card-preview.css to custom_css config (already supports multiple CSS files)

### Non-Breaking
- HTML already enabled via `unsafe_allow_html=true` (used for mana symbols)
- Card image URLs already available in Card schema
- No changes to data layer, repositories, or agent tools
- No database migrations required
- Fallback to plain text if images unavailable

## Research Summary

### Sources Used
- Archon RAG: Chainlit documentation (source: docs.chainlit.io)
- Local codebase: Card schema, formatters, config.toml

### Key Findings
1. **Chainlit Limitations**: Native hover/tooltip not supported; only click-to-view with `cl.Image` elements
2. **HTML Approach**: `unsafe_allow_html=true` already enabled for mana symbols; can extend for card previews
3. **Image Data**: `Card.image_uris` dict contains Scryfall CDN URLs for multiple image sizes (small, normal, large, png, art_crop, border_crop)
4. **CSS Support**: Custom CSS already used via `public/mana-symbols.css`; can add `public/card-preview.css`

### Technical Pattern
Follow existing visual mana symbol implementation:
- Wrap card names in HTML spans with data attributes
- Use CSS `:hover` pseudo-class for tooltip display
- Position image using `position: absolute` with overflow handling
- Fetch images from Scryfall CDN (already authorized in image_uris)

# Change Proposal: Add Visual Mana Symbols Using Scryfall SVG API

## Why

Currently, the UI displays mana costs and symbols as plain text (e.g., `{2}{R}{G}`), which is functional but lacks the visual polish and readability that Magic players expect. Scryfall provides a free Card Symbols API with high-quality SVG images for all mana symbols, including:
- Basic colors (W, U, B, R, G)
- Colorless and generic mana (C, 0-20, X, Y, Z)
- Hybrid mana (W/U, 2/R, etc.)
- Phyrexian mana (W/P, U/P, etc.)
- Special symbols (Tap, Untap, Snow, etc.)

Using visual symbols will significantly improve the user experience by:
1. **Better readability** - Instantly recognizable color-coded symbols
2. **Professional appearance** - Matches MTGA, Arena, and other MTG tools
3. **Reduced cognitive load** - Players don't need to parse text notation
4. **Accessibility** - SVG symbols can be styled and scaled for different screen sizes

The Scryfall API provides these symbols for free with no authentication required, making this a zero-cost enhancement.

## What Changes

- Add Scryfall symbology API integration to fetch symbol metadata and SVG URIs
- Create symbol caching layer to avoid repeated API calls (symbols are static)
- Update `format_mana_symbols()` in `src/ui/formatters.py` to render HTML with inline SVG or IMG tags
- Add CSS styling for mana symbols (size, alignment, spacing)
- Update card display formatters to use visual symbols in:
  - Card detail views (`format_card_details()`)
  - Card list views (`format_card_list()`)
  - Deck list views (`format_deck_for_display()`)
- Add fallback to text notation if SVG fails to load
- Add configuration option to toggle between visual and text symbols (for accessibility)

## Impact

- **Affected specs**: `chainlit-ui` (new symbol rendering requirements)
- **Affected code**:
  - `src/ui/formatters.py` (update all mana symbol rendering)
  - `src/ui/symbols.py` (new file - symbol fetching and caching)
  - `src/ui/styles.py` or inline CSS (new file - symbol styling)
  - `.chainlit/config.toml` (optional config for symbol display)
- **Dependencies**:
  - Scryfall Card Symbols API (`GET https://api.scryfall.com/symbology`)
  - No new Python packages required (uses standard library `urllib` or existing `httpx`)
- **Breaking changes**: None (purely additive, with text fallback)
- **Performance**:
  - Initial load: Single API call to fetch all symbols (~150 symbols, ~50KB JSON)
  - Runtime: Zero overhead (symbols cached in-memory after first load)
  - Page render: Minimal impact (inline SVGs or cached IMG tags)

# Implementation Tasks: Visual Mana Symbols with Scryfall SVG API

## 1. Symbol Fetching and Caching Infrastructure

- [ ] 1.1 Create `src/ui/symbols.py` module
  - Add module docstring explaining Scryfall symbology integration
  - Add imports: `dataclasses`, `logging`, `httpx` or `urllib`
  - Define `SymbolMetadata` dataclass with fields: symbol, svg_uri, colors, english, mana_value

- [ ] 1.2 Implement `fetch_scryfall_symbols()` function
  - Make GET request to `https://api.scryfall.com/symbology`
  - Set timeout to 5 seconds
  - Parse JSON response as list of symbol objects
  - Return `dict[str, SymbolMetadata]` indexed by symbol string
  - Raise `SymbologyAPIError` on failure

- [ ] 1.3 Implement symbol cache singleton
  - Create module-level `_symbol_cache: dict[str, SymbolMetadata] | None = None`
  - Implement `get_symbol_cache()` function with lazy initialization
  - On first call, fetch symbols and populate cache
  - Log cache population success/failure
  - Handle exceptions gracefully (log error, return empty dict on failure)

- [ ] 1.4 Implement `get_symbol_svg_url(symbol: str) -> str | None`
  - Look up symbol in cache
  - Return `svg_uri` if found
  - Return `None` if symbol not in cache
  - Log warning for unknown symbols

- [ ] 1.5 Add error handling and logging
  - Define custom exception `SymbologyAPIError`
  - Log symbol cache initialization at INFO level
  - Log API failures at WARNING level
  - Log unknown symbol lookups at DEBUG level

- [ ] 1.6 Add unit tests for symbol caching
  - Test successful symbol fetch and cache population
  - Test cache lookup for known symbols
  - Test cache lookup returns None for unknown symbols
  - Test API timeout handling
  - Test API error response handling
  - Mock httpx/urllib responses for tests

## 2. Visual Symbol Rendering

- [ ] 2.1 Update `format_mana_symbols()` in `src/ui/formatters.py`
  - Add `use_visual: bool = True` parameter
  - If `use_visual=False`, return text notation unchanged
  - Parse mana cost string into individual symbols (e.g., "{2}{R}{G}" → ["{2}", "{R}", "{G}"])
  - For each symbol, generate IMG tag with SVG URL from cache
  - Return HTML string with inline images
  - Fall back to text if any symbol lookup fails

- [ ] 2.2 Implement `parse_mana_cost(mana_cost: str) -> list[str]`
  - Use regex to extract symbols: `\{[^}]+\}`
  - Return list of symbols in order
  - Handle empty or None mana cost → return empty list
  - Handle malformed notation (log warning, return text as-is)

- [ ] 2.3 Implement `render_symbol_as_html(symbol: str) -> str`
  - Look up symbol SVG URL via `get_symbol_svg_url()`
  - If found, return `<img src="{url}" alt="{symbol}" class="mana-symbol" />`
  - If not found, return HTML-escaped text of symbol
  - Ensure alt text is properly escaped

- [ ] 2.4 Update `format_card_details()` to use visual symbols
  - Mana cost rendering should call updated `format_mana_symbols()`
  - Test with various mana costs (basic, hybrid, Phyrexian, colorless)
  - Verify symbols appear in dual-faced card rendering

- [ ] 2.5 Update `format_card_list()` to use visual symbols
  - Mana cost rendering in list entries should use visual symbols
  - Verify symbols align properly in numbered list format

- [ ] 2.6 Update `format_deck_for_display()` to use visual symbols
  - Deck card entry formatting should use visual symbols
  - Verify symbols render in mainboard and sideboard sections

- [ ] 2.7 Add HTML escaping utility
  - Implement or import HTML escape function for text fallback
  - Ensure all text fallback paths properly escape special characters
  - Test escaping with mana costs containing HTML-like characters

## 3. Oracle Text Symbol Rendering

- [ ] 3.1 Update `format_card_details()` to render symbols in oracle text
  - Parse oracle text for inline symbols (e.g., "{T}: Add {R}")
  - Replace symbols with visual images
  - Preserve line breaks and formatting in oracle text

- [ ] 3.2 Add oracle text symbol parsing
  - Implement `render_oracle_text_symbols(text: str) -> str`
  - Use regex to find all `{...}` patterns in text
  - Replace each with IMG tag for visual symbols
  - Maintain text structure (newlines, formatting)

- [ ] 3.3 Handle special symbols (tap, untap, snow, energy)
  - Test with cards containing {T}, {Q}, {S}, {E} symbols
  - Verify symbols render inline with oracle text
  - Ensure spacing doesn't break text readability

## 4. CSS Styling

- [ ] 4.1 Add mana symbol CSS styles
  - Create `.mana-symbol` class definition
  - Set `height: 1em` for scalable sizing
  - Set `width: auto` to maintain aspect ratio
  - Set `display: inline-block` for inline flow
  - Set `vertical-align: middle` or `text-bottom` for alignment
  - Add small horizontal margin: `margin: 0 1px`

- [ ] 4.2 Determine CSS injection method for Chainlit
  - Option A: Add to Chainlit's custom CSS file (`.chainlit/custom.css`)
  - Option B: Inject inline `<style>` tag in formatted output
  - Option C: Use Chainlit's theme customization
  - Choose method based on Chainlit's capabilities

- [ ] 4.3 Test symbol rendering at different font sizes
  - Test in card details (larger text)
  - Test in card lists (smaller text)
  - Test in deck lists (varied contexts)
  - Ensure symbols scale proportionally

- [ ] 4.4 Test symbol alignment in various contexts
  - Test alignment with card names
  - Test alignment in oracle text paragraphs
  - Test alignment in deck list entries
  - Adjust `vertical-align` if needed

## 5. Configuration and Feature Toggle

- [ ] 5.1 Add configuration for visual symbols
  - Add `VISUAL_MANA_SYMBOLS` environment variable (default: `true`)
  - Document in `.env.example`
  - Load in application startup or config module

- [ ] 5.2 Pass configuration to formatters
  - Update formatter functions to read `VISUAL_MANA_SYMBOLS` setting
  - Pass `use_visual` parameter to `format_mana_symbols()`
  - Ensure setting is respected throughout rendering pipeline

- [ ] 5.3 Add Chainlit config option (optional)
  - If Chainlit supports custom config, add `features.visual_symbols` option
  - Document in `.chainlit/config.toml` or equivalent
  - Integrate with existing config loading

- [ ] 5.4 Document configuration in CLAUDE.md
  - Add section on visual symbols feature
  - Document how to disable for accessibility
  - Document how to debug with text fallback

## 6. Error Handling and Fallback

- [ ] 6.1 Implement robust fallback logic
  - If Scryfall API fails, use text notation for all symbols
  - If individual symbol not found, use text for that symbol only
  - If rendering error occurs, log and fall back to text

- [ ] 6.2 Add logging for symbol rendering issues
  - Log API fetch attempts at INFO level
  - Log API failures at WARNING level
  - Log individual symbol lookup failures at DEBUG level
  - Include context: card name, mana cost, error details

- [ ] 6.3 Test fallback scenarios
  - Test with Scryfall API unreachable (mock network error)
  - Test with Scryfall API returning 5xx error
  - Test with unknown/invalid symbol in mana cost
  - Test with malformed mana cost notation
  - Verify app remains functional in all cases

## 7. Testing

- [ ] 7.1 Add unit tests for `src/ui/symbols.py`
  - Test `fetch_scryfall_symbols()` with mocked API response
  - Test `get_symbol_cache()` lazy initialization
  - Test `get_symbol_svg_url()` cache lookups
  - Test error handling for API failures
  - Test cache population with real API data (integration test)

- [ ] 7.2 Add unit tests for updated `format_mana_symbols()`
  - Test basic mana cost: "{2}{R}{G}" → HTML with 3 images
  - Test hybrid mana: "{W/U}" → single hybrid image
  - Test Phyrexian: "{W/P}" → single Phyrexian image
  - Test colorless: "{C}" → colorless image
  - Test empty mana cost → empty string
  - Test text fallback when `use_visual=False`
  - Test text fallback when symbol not found

- [ ] 7.3 Add unit tests for oracle text symbol rendering
  - Test oracle text with tap symbol: "{T}: Add {R}" → mixed text and images
  - Test oracle text with multiple symbols
  - Test oracle text with no symbols → unchanged
  - Test line breaks and formatting preserved

- [ ] 7.4 Add integration tests for symbol rendering in formatters
  - Test `format_card_details()` with various mana costs
  - Test `format_card_list()` with mixed mana costs
  - Test `format_deck_for_display()` with full deck
  - Verify HTML output structure and IMG tags

- [ ] 7.5 Manual testing in Chainlit UI
  - Start Chainlit: `uv run chainlit run src/ui/app.py`
  - Test: "Show me Lightning Bolt" (simple {R} cost)
  - Test: "Show me Breeding Pool" (hybrid {G/U})
  - Test: "Show me Phyrexian Obliterator" (Phyrexian {B/P})
  - Test: "Show me my deck" (multiple cards with symbols)
  - Verify symbols render, scale, and align correctly
  - Test text fallback by setting `VISUAL_MANA_SYMBOLS=false`

## 8. Documentation and Cleanup

- [ ] 8.1 Update CLAUDE.md with visual symbols feature
  - Add section: "Visual Mana Symbols"
  - Document Scryfall API integration
  - Document configuration options
  - Document fallback behavior
  - Add troubleshooting tips

- [ ] 8.2 Add code comments and docstrings
  - Document `symbols.py` module and all functions
  - Document `parse_mana_cost()` and `render_symbol_as_html()`
  - Document caching strategy and performance considerations

- [ ] 8.3 Run type checking and linting
  - `uv run mypy src/`
  - `uv run ruff check . --fix`
  - `uv run ruff format .`

- [ ] 8.4 Run all tests
  - `uv run pytest tests/unit/` (unit tests)
  - `uv run pytest tests/integration/` (integration tests)
  - Ensure all tests pass

## 9. Final Checklist

- [ ] 9.1 All acceptance criteria satisfied
  - ✓ Mana symbols render as visual SVG images in all UI contexts
  - ✓ Scryfall symbology API integrated with caching
  - ✓ Text fallback works for API failures and unknown symbols
  - ✓ CSS styling ensures consistent display and alignment
  - ✓ Configuration toggle available for visual vs text symbols
  - ✓ Accessibility: alt text on all images, HTML escaping for text
  - ✓ Error handling: graceful fallback, logging, no app crashes

- [ ] 9.2 All tasks in tasks.md marked complete
- [ ] 9.3 Code quality checks pass (mypy, ruff)
- [ ] 9.4 All tests pass (unit + integration)
- [ ] 9.5 Manual testing confirms visual symbols work in Chainlit
- [ ] 9.6 Documentation updated
- [ ] 9.7 Ready for code review and archive

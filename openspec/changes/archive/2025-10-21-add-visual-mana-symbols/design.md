# Design Document: Add Visual Mana Symbols Using Scryfall SVG API

## Context

The current UI displays mana costs as plain text notation (e.g., `{2}{R}{G}`), which works but lacks the visual polish players expect from MTG applications. Scryfall provides a comprehensive Card Symbols API that offers high-quality SVG images for all Magic symbols, including standard mana, hybrid, Phyrexian, and special symbols.

**Constraints**:
- Must maintain text fallback for accessibility and error cases
- Symbol rendering must work in Chainlit's markdown-based chat interface
- No external dependencies beyond standard HTTP library
- Must be fast (symbols should be cached, not fetched per render)

**Stakeholders**:
- End users (better visual experience)
- UI layer (cleaner symbol rendering)
- Future UI implementations (reusable symbol logic)

## Goals / Non-Goals

### Goals
- Render mana symbols as inline SVG or IMG elements in Chainlit chat
- Cache symbol metadata to avoid repeated API calls
- Support all Scryfall symbol types (basic, hybrid, Phyrexian, special)
- Maintain text fallback for accessibility and robustness
- Keep symbol rendering UI-independent (works with future UIs)

### Non-Goals
- Custom symbol artwork (use Scryfall's official SVGs only)
- Symbol animation or interactive effects (deferred to Epic 8: Polish)
- Offline symbol support (requires internet for first load)
- Symbol parsing beyond Scryfall's notation (rely on existing card data)

## Decisions

### Decision 1: Inline SVG vs IMG Tags with CDN URLs

**What**: Use IMG tags with Scryfall's CDN URLs (`https://svgs.scryfall.io/card-symbols/*.svg`) instead of inline SVG embedding.

**Why**:
- **Simpler implementation**: No XML parsing or SVG manipulation required
- **Browser caching**: CDN URLs are cached by the browser automatically
- **Smaller HTML payload**: IMG tags are 1-2 lines vs dozens of lines for inline SVG
- **Scryfall's infrastructure**: Their CDN is fast, reliable, and purpose-built for symbols

**Alternatives considered**:
1. **Inline SVG embedding** - Rejected: More complex, larger HTML, no caching benefit
2. **Download and self-host SVGs** - Rejected: Adds maintenance burden, no offline requirement
3. **Unicode symbols (⚪⚫🔴🔵🟢)** - Rejected: Limited set, inconsistent rendering across platforms

**Implementation**:
```python
# Example: Convert {2}{R}{G} to HTML with IMG tags
def format_mana_symbols(mana_cost: str, use_visual: bool = True) -> str:
    if not use_visual:
        return mana_cost  # Fallback to text

    # Replace each {X} with <img src="..." alt="{X}" class="mana-symbol" />
    symbols = parse_mana_cost(mana_cost)  # ["{2}", "{R}", "{G}"]
    html = ""
    for symbol in symbols:
        svg_url = get_symbol_svg_url(symbol)  # Cache lookup
        html += f'<img src="{svg_url}" alt="{symbol}" class="mana-symbol" />'
    return html
```

### Decision 2: Symbol Metadata Caching Strategy

**What**: Fetch all symbols from Scryfall API on first use and cache in-memory for the application lifetime.

**Why**:
- **Performance**: Symbols are static - they don't change, so one-time fetch is sufficient
- **Reliability**: If API is down after initial load, app still works with cached data
- **Simplicity**: No complex cache invalidation logic needed

**Alternatives considered**:
1. **Fetch on-demand per symbol** - Rejected: Too many API calls, slower UX
2. **Persistent disk cache** - Rejected: Over-engineering for static data
3. **Hardcode symbol URLs** - Rejected: Brittle if Scryfall changes CDN structure

**Implementation**:
- Store `symbol_cache: dict[str, SymbolMetadata]` at module level
- Fetch on first call to `format_mana_symbols()` if cache is empty
- `SymbolMetadata = {"symbol": "{R}", "svg_uri": "https://...", "colors": ["R"]}`

### Decision 3: Fallback Strategy for API Failures

**What**: If Scryfall API fails or symbol not found, gracefully fall back to text notation.

**Error cases**:
- Scryfall API returns 5xx (cache existing symbols, use text for new ones)
- Symbol not in Scryfall's symbology (use text as-is)
- Network timeout (log warning, use text)
- Invalid mana notation from card data (use text)

**Why**:
- **Robustness**: App should never crash due to symbol rendering
- **Accessibility**: Text notation is still readable
- **Debugging**: Text fallback makes issues visible without breaking UX

**Implementation**:
```python
try:
    html = render_visual_symbols(mana_cost)
except (APIError, SymbolNotFoundError):
    logger.warning(f"Failed to render symbols for {mana_cost}, using text fallback")
    html = escape(mana_cost)  # Escape HTML special chars
```

### Decision 4: CSS Styling for Symbol Display

**What**: Add CSS class `.mana-symbol` with fixed height, inline display, and vertical alignment.

**Why**:
- **Consistent sizing**: Symbols should be same height as text (~14-16px)
- **Inline flow**: Symbols appear inline with card names/text
- **Readability**: Proper spacing and alignment prevent visual clutter

**CSS example**:
```css
.mana-symbol {
    display: inline-block;
    height: 1em;  /* Scale with font size */
    width: auto;
    vertical-align: middle;
    margin: 0 1px;  /* Small spacing between symbols */
}
```

### Decision 5: Configuration Toggle for Visual vs Text

**What**: Add `VISUAL_MANA_SYMBOLS` setting in `.env` or Chainlit config to toggle between visual and text symbols.

**Why**:
- **Accessibility**: Some users may prefer text for screen readers
- **Debugging**: Easier to copy/paste text notation
- **Flexibility**: Easy to disable if visual symbols cause issues

**Implementation**:
- Default: `VISUAL_MANA_SYMBOLS=true`
- Environment variable override for testing or accessibility needs
- Passed to `format_mana_symbols(mana_cost, use_visual=USE_VISUAL_SYMBOLS)`

## Risks / Trade-offs

### Risk 1: Scryfall API Dependency

**Risk**: If Scryfall API or CDN goes down, symbols won't render.

**Mitigation**:
- Cache symbols in-memory after first load (survives temporary outages)
- Text fallback ensures app remains functional
- Scryfall has excellent uptime track record (>99.9%)
- Consider periodic cache refresh (daily) to handle new symbols

**Trade-off**: Acceptable risk given Scryfall's reliability and fallback strategy.

### Risk 2: Markdown Rendering Limitations in Chainlit

**Risk**: Chainlit's markdown renderer may not support HTML IMG tags or may strip them.

**Mitigation**:
- Test with Chainlit's markdown renderer before full implementation
- If Chainlit strips IMG tags, use Chainlit's `cl.Image` elements instead
- Document workaround in implementation notes

**Trade-off**: May need Chainlit-specific rendering if markdown doesn't support HTML.

### Risk 3: Symbol Size and Layout Issues

**Risk**: Symbols may appear too large, too small, or misaligned with text.

**Mitigation**:
- Use `em` units for height to scale with font size
- Test on multiple screen sizes and zoom levels
- Add CSS for vertical alignment (`vertical-align: middle`)
- Make symbol size configurable via CSS variable

**Trade-off**: May require UI polish iteration to get sizing perfect.

## Migration Plan

**No migration required** - This is a purely additive change with no breaking changes.

**Rollout**:
1. Implement symbol fetching and caching in `src/ui/symbols.py`
2. Update `format_mana_symbols()` to use visual symbols (with feature flag)
3. Add CSS styling for `.mana-symbol` class
4. Test in Chainlit UI with sample cards
5. Enable by default with `VISUAL_MANA_SYMBOLS=true`
6. Document configuration in CLAUDE.md

**Rollback**: Set `VISUAL_MANA_SYMBOLS=false` to revert to text notation.

## Open Questions

1. **Should symbols be clickable with tooltips?**
   - **Answer (for now)**: No - keep it simple. Tooltips can be added in Epic 8 (Polish) if needed.

2. **Should we cache symbols to disk for offline support?**
   - **Answer (for now)**: No - not a priority. Symbols are small and fetched once per session.

3. **Should we support custom symbol colors or styling?**
   - **Answer (for now)**: No - use Scryfall's official colors. Custom styling deferred to Epic 8.

4. **How to handle symbols in search results vs card details vs deck lists?**
   - **Answer (for now)**: Use visual symbols everywhere consistently. Size is controlled by CSS `em` units, so it scales with context.

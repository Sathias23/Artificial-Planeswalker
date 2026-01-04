# Proposal: Add Auto-Format-Filter for Decks

## Why
Users building Standard format decks are receiving search results containing non-Standard cards (tokens, cards from other sets) because the format filter must be manually enabled. This creates a poor user experience requiring explicit "set format to standard" requests mid-workflow. When a user loads a Standard deck for building, the format filter should automatically match the deck's format to ensure all search results are format-legal.

**Bug Report Reference**: Bug #f2c05a23 (2025-10-19) - User building "Sephiroth Sacrifice" (Standard) received token creatures and non-Standard cards in search results.

## What Changes
- Automatically set format filter to match deck format when loading a Standard deck
- Clear format filter when loading decks with format="all" (future compatibility)
- Synchronize format filter with active deck format throughout session
- Add `auto_filter` parameter to card search tools (`lookup_card_by_name`, `search_cards_advanced`)
  - Default: `auto_filter=True` (respect session format filter)
  - When `auto_filter=False`, bypass session format filter and search all cards
  - Enables users to temporarily see non-Standard cards without clearing format filter
- Document auto-filter behavior in tool descriptions

## Impact
- Affected specs: `agent-tools` (3 modified requirements: Load Deck, Card Lookup, Advanced Search)
- Affected code:
  - `src/agent/tools/deck_tools.py` - Update `load_deck()` to auto-set format filter
  - `src/agent/tools/card_lookup.py` - Add `auto_filter` parameter to `lookup_card_by_name()`
  - `src/agent/tools/card_search.py` - Add `auto_filter` parameter to `search_cards_advanced()`
  - Tests may need updates to verify auto-filter behavior
- Breaking changes: **None** (additive enhancement to existing behavior)
- User experience improvements:
  - Users building Standard decks no longer need to manually set format filter
  - Users can temporarily bypass format filtering without clearing session state

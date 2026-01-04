# Enhance Deck UI Features

## Why
Users need better deck management and UI customization capabilities. Currently, the deck list view provides minimal information (name, format, card count), forcing users to load each deck individually to see important details. Additionally, card hover previews always appear on the right side, which can cause overlap issues with the sidebar deck panel and doesn't accommodate different screen layouts.

## What Changes
- **Enhanced deck list display**: Expand `list_decks` tool to show deck colors/color identity, strategy description, detailed card counts (mainboard vs sideboard), creation/modification timestamps, and deck tags/win conditions
- **Configurable card hover direction**: Add user preference for card image hover preview positioning (left or right), with sidebar deck panel always hovering left to prevent overlap

## Impact
- Affected specs: `deck-management`, `ui-components`
- Affected code:
  - `src/agent/tools/deck_tools.py` (list_decks function)
  - `src/data/repositories/deck.py` (DeckRepository)
  - `src/ui/formatters.py` (card hover formatting)
  - `public/card-preview.css` (hover positioning styles)
  - `.chainlit/config.toml` (new user preference setting)
- Migration: None required - backward compatible enhancements

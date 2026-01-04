# Proposal: Add Deck List, Load, and Delete Tools

## Why

Users need the ability to manage multiple decks over time, but the agent currently lacks tools to list saved decks, load a previously saved deck for editing, or delete unwanted decks. This proposal implements Story 4.5 from the PRD, completing the core deck management workflow.

## What Changes

- Add "List Decks" agent tool to show all saved decks with names, formats, and card counts
- Add "Load Deck" agent tool to retrieve and set a deck as the active deck in the session
- Add "Delete Deck" agent tool to remove decks by name or ID with confirmation workflow
- Update deck session management to support switching between decks (not just creating new ones)
- Add appropriate error handling for deck not found, confirmation requirements, and database failures

## Impact

- Affected specs: `agent-tools` (3 new requirements added)
- Affected code:
  - `src/agent/tools/deck_tools.py` - Add three new tool functions
  - `src/agent/dependencies.py` - May need to extend session context for confirmation workflows
  - `tests/unit/agent/tools/test_deck_tools.py` - New unit tests for each tool
  - `tests/integration/agent/test_deck_tools_integration.py` - Integration tests for list/load/delete workflows

## PRD Reference

This proposal implements **Story 4.5: Save, Load, and Delete Decks** from `docs/prd.md`:

> As a **user**,
> I want **to save my deck, load previously saved decks, and delete unwanted decks**,
> so that **I can work on multiple deck ideas over time**.

Acceptance Criteria:
1. PydanticAI tool to list all saved decks with names and formats
2. PydanticAI tool to load a saved deck by name or ID (sets as active deck)
3. PydanticAI tool to delete a deck by name or ID with confirmation
4. User can ask "show my decks", "load my Mono Red Aggro deck", "delete Test Deck"
5. Loading a deck displays basic deck summary (name, format, card count)
6. Deck deletion requires explicit confirmation to prevent accidents
7. Integration tests verify save/load/delete workflows

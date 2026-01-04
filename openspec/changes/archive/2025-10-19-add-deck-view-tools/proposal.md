# Change Proposal: Add Deck View and Management Tools

## Why

Users need to view their deck contents and manage cards (add/remove/update quantities) through natural language conversation. Story 4.4 from the PRD requires PydanticAI tools that enable users to ask "show my deck" or "remove 2 Lightning Bolt from my deck" while receiving formatted deck displays grouped by card type or mana cost.

## What Changes

- Add `view_deck` tool to display current active deck with formatted card list
  - Group cards by type (creatures, spells, lands) or mana cost
  - Show card counts, total deck size, and summary statistics
  - Handle empty deck gracefully
- Add `remove_card_from_deck` tool to remove cards or reduce quantities
  - Support natural language like "remove 2 Lightning Bolt"
  - Validate quantities (prevent removing more cards than present)
  - Provide clear feedback on remaining quantities
- Add `update_card_quantity` tool to modify card quantities in deck
  - Support increasing or decreasing quantities
  - Validate deck construction rules (max 4 copies except basic lands)
  - Handle edge cases (quantity 0 = remove card)
- Add session context for "active deck" tracking
  - Enable users to work on a deck without repeating deck name
  - Persist active deck ID across tool invocations
- Add deck display formatter for Chainlit UI
  - Create reusable formatting function for deck lists
  - Support multiple grouping strategies (by type, by mana cost)

## Impact

- **Affected specs**: `agent-tools` (new tool requirements), `chainlit-ui` (deck formatting)
- **Affected code**:
  - `src/agent/tools/deck_tools.py` (new file - deck management tools)
  - `src/agent/dependencies.py` (add active_deck_id to session context)
  - `src/ui/formatters.py` (add deck list formatting functions)
  - `src/agent/core.py` (update AgentDependencies to include deck context)
- **Dependencies**: Requires existing `DeckRepository` from `deck-management` capability
- **Breaking changes**: None (purely additive)

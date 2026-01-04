# Add Chainlit UI - Story 3.1

## Why

Users need a web-based chat interface to interact with the PydanticAI agent conversationally for card lookups and deck building assistance. This delivers the first end-to-end user-facing application, enabling natural language interaction with the card database and agent tools built in Epics 1-2.

## What Changes

- Add Chainlit web application as the UI layer
- Configure Chainlit with custom app name and settings
- Implement basic chat message handling with echo functionality
- Add welcome message for user onboarding
- Integrate graceful startup and shutdown handling
- Provide UV-based command to run the application locally

This change introduces a new capability (`chainlit-ui`) that serves as the UI layer in the four-layer architecture (Data → Logic → Agent → UI).

## Impact

- **New capability**: `chainlit-ui` - Chat interface layer
- **Affected code**: New `src/ui/` module will be created
- **Dependencies**: Adds Chainlit to project dependencies
- **Architecture**: Completes the four-layer separation (UI layer now implemented)
- **User experience**: Enables first interactive user-facing feature
- **Testing**: Manual testing required for UI interactions (per CLAUDE.md testing strategy)

## Notes

This is Story 3.1 from Epic 3 (Chainlit Chat Interface Integration). The actual agent integration happens in Story 3.2, so this story focuses purely on establishing the Chainlit infrastructure and basic functionality. The UI layer must remain thin and delegate to the agent layer without direct database access.

# deck-confirmations Specification Delta

**Target Spec:** `agent-tools`

## MODIFIED Requirements

### Requirement: Deck Deletion with Inline Action Confirmation
The system SHALL display inline action buttons for deck deletion confirmation instead of requiring a second conversational message, while maintaining backward compatibility with conversational confirmation.

#### Scenario: Deletion warning shows action buttons (MODIFIED)
- **WHEN** a user requests deck deletion via agent tool
- **AND** the `confirmed` parameter is False (default)
- **THEN** the delete_deck tool returns a response instructing the UI to show confirmation actions
- **AND** the response includes deck ID and deck name for payload construction
- **AND** the tool does NOT proceed with deletion
- **AND** the tool does NOT return a text-only confirmation prompt

#### Scenario: UI displays confirmation action buttons (NEW)
- **WHEN** the delete_deck tool response indicates confirmation needed
- **THEN** the UI layer creates a confirmation message with action buttons
- **AND** the message includes two actions: "Confirm Delete" and "Cancel"
- **AND** the "Confirm Delete" button has payload `{"deck_id": <id>, "deck_name": <name>, "confirmed": True}`
- **AND** the "Cancel" button has payload `{}`
- **AND** the message text warns "Are you sure you want to delete '{deck_name}'? This cannot be undone."

#### Scenario: Confirmation message stored for cleanup (NEW)
- **WHEN** the deletion confirmation message with actions is sent
- **THEN** the message reference is stored in user session with key "delete_confirmation_message"
- **AND** the reference can be retrieved in action callbacks

#### Scenario: Confirm deletion via action (NEW)
- **WHEN** the user clicks "Confirm Delete" button
- **THEN** the `confirm_delete_deck` action callback is invoked
- **AND** the callback retrieves deck_id from `action.payload.get("deck_id")`
- **AND** the callback retrieves deck_name from `action.payload.get("deck_name")`
- **AND** the callback removes all action buttons from the confirmation message
- **AND** the callback calls the deck repository to delete the deck
- **AND** the callback sends a success message "Deck '{deck_name}' deleted successfully"
- **AND** the callback triggers sidebar update via `await update_deck_sidebar(session_id)`

#### Scenario: Cancel deletion via action (NEW)
- **WHEN** the user clicks "Cancel" button
- **THEN** the `cancel_delete_deck` action callback is invoked
- **AND** the callback removes all action buttons from the confirmation message
- **AND** the callback sends a cancellation message "Deck deletion cancelled"
- **AND** the deck is NOT deleted
- **AND** the sidebar is NOT updated

#### Scenario: Conversational confirmation still works (MODIFIED - backward compatibility)
- **WHEN** a user requests deck deletion conversationally
- **AND** the UI shows action buttons but user ignores them
- **AND** the user types a conversational confirmation (e.g., "yes, delete it")
- **THEN** the agent recognizes the confirmation intent
- **AND** the agent invokes delete_deck tool with `confirmed=True`
- **AND** the deck is deleted via the tool (not action callback)
- **AND** both patterns (action and conversational) achieve the same result

### Requirement: Deletion Confirmation Error Handling (NEW)
The system SHALL handle errors during action-based deck deletion gracefully with clear user feedback.

#### Scenario: Deck not found during confirmation
- **WHEN** the user clicks "Confirm Delete"
- **AND** the deck ID from the payload does not exist in the database
- **THEN** an error message is sent "Error: Deck not found. It may have already been deleted."
- **AND** the action buttons are removed
- **AND** the sidebar is updated to reflect current state

#### Scenario: Repository error during deletion
- **WHEN** the user clicks "Confirm Delete"
- **AND** the deck repository raises an exception during deletion
- **THEN** the error is caught and logged
- **AND** a user-friendly error message is sent "Error deleting deck: {brief error}"
- **AND** the action buttons are NOT removed (user can retry)
- **AND** the sidebar is NOT updated (deck still exists)

#### Scenario: Missing payload fields
- **WHEN** the "Confirm Delete" action is triggered
- **AND** the payload is missing deck_id or deck_name
- **THEN** an error message is sent "Invalid deletion request: missing deck information"
- **AND** the action buttons are removed
- **AND** the deck is NOT deleted

#### Scenario: Session context missing
- **WHEN** the confirmation action callback is invoked
- **AND** the session ID is not found in user session
- **THEN** an error message is sent "Session error: unable to process deletion"
- **AND** the action buttons are removed
- **AND** the deck is NOT deleted

## Target Spec: chainlit-ui

## ADDED Requirements

### Requirement: Deck Deletion Confirmation UI Pattern
The system SHALL provide UI-layer functionality to display and handle deck deletion confirmation actions.

#### Scenario: Confirmation message creation
- **WHEN** the agent indicates deck deletion confirmation is needed
- **THEN** the UI layer creates a `cl.Message` with confirmation text
- **AND** the message includes two `cl.Action` instances
- **AND** the actions are configured with appropriate icons ("trash-2" for confirm, "x-circle" for cancel)
- **AND** the actions include tooltips explaining their purpose

#### Scenario: Confirm delete action callback registration
- **WHEN** the UI module is loaded
- **THEN** a callback decorated with `@cl.action_callback("confirm_delete_deck")` is registered
- **AND** the callback is async and accepts `action: cl.Action` parameter
- **AND** the callback implements deck deletion logic with error handling

#### Scenario: Cancel delete action callback registration
- **WHEN** the UI module is loaded
- **THEN** a callback decorated with `@cl.action_callback("cancel_delete_deck")` is registered
- **AND** the callback is async and accepts `action: cl.Action` parameter
- **AND** the callback implements cancellation logic with message cleanup

#### Scenario: Action button cleanup after decision
- **WHEN** either confirm or cancel action is triggered
- **THEN** the callback retrieves the confirmation message from user session
- **AND** the callback calls `await message.remove_actions()` to remove both buttons
- **AND** the confirmation message content remains visible
- **AND** no orphaned buttons persist in the UI

#### Scenario: Sidebar update after confirmed deletion
- **WHEN** the user confirms deletion via action button
- **AND** the deletion succeeds
- **THEN** the `update_deck_sidebar(session_id)` function is called
- **AND** the sidebar reflects the deletion (deck no longer shown)
- **AND** if the deleted deck was active, the sidebar shows "No active deck"

#### Scenario: Active deck cleared after deletion
- **WHEN** the user deletes the currently active deck via action
- **AND** the deletion succeeds
- **THEN** the session manager's active deck ID is cleared
- **AND** subsequent deck operations require selecting/creating a new deck
- **AND** the sidebar update reflects the cleared active deck state

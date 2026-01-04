# Chainlit UI Spec Delta

## ADDED Requirements

### Requirement: Tool Call Visibility with Chainlit Steps
The system SHALL display PydanticAI tool calls visually in the chat interface using Chainlit's Step API to provide transparency into agent operations.

#### Scenario: Single tool call displays Step
- **WHEN** the agent invokes a single tool (e.g., `lookup_card_by_name`)
- **THEN** a Chainlit Step appears in the chat interface
- **AND** the Step shows the tool name as the step label
- **AND** the Step displays the tool parameters as input
- **AND** the Step shows a summary of the tool result as output
- **AND** the Step is marked with type="tool"

#### Scenario: Multiple parallel tool calls display multiple Steps
- **WHEN** the agent invokes multiple tools in parallel
- **THEN** each tool call appears as a separate Chainlit Step
- **AND** the Steps are displayed as siblings (not nested)
- **AND** all Steps show execution status independently
- **AND** the final agent response appears after all Steps complete

#### Scenario: Step shows tool execution lifecycle
- **WHEN** a tool call Step is created
- **THEN** the Step initially shows as "running" status
- **AND** the Step updates to "completed" when the tool finishes
- **AND** if the tool fails, the Step shows "failed" status with error message

### Requirement: Tool Parameter Display in Steps
The system SHALL format tool parameters in a readable, non-verbose format suitable for user consumption.

#### Scenario: Simple parameters displayed clearly
- **WHEN** a tool is called with simple parameters (e.g., card_name="Lightning Bolt")
- **THEN** the Step input shows parameters as key-value pairs
- **AND** the format is human-readable (not raw JSON)
- **AND** string values are quoted for clarity

#### Scenario: Complex parameters simplified
- **WHEN** a tool is called with complex parameters (e.g., nested filters)
- **THEN** the Step input shows a simplified representation
- **AND** the simplification focuses on user-relevant information
- **AND** technical details are omitted if not useful to users

#### Scenario: No parameters displayed for parameterless tools
- **WHEN** a tool requires no parameters
- **THEN** the Step input is omitted or shows "No parameters"
- **AND** the Step focuses on the tool name and result

### Requirement: Tool Result Summarization in Steps
The system SHALL summarize tool results in Steps without duplicating full card data that appears in the final message.

#### Scenario: Card query result summary
- **WHEN** a tool returns card search results
- **THEN** the Step output shows a count (e.g., "Found 3 cards")
- **AND** the Step does NOT display full card details
- **AND** full card details appear in the final agent message

#### Scenario: Single card lookup summary
- **WHEN** a tool returns a single card
- **THEN** the Step output shows the card name found
- **AND** the Step does NOT duplicate the full card formatting
- **AND** full card details appear in the final agent message

#### Scenario: Tool execution with no results
- **WHEN** a tool returns no results (e.g., no cards found)
- **THEN** the Step output shows "No results found"
- **AND** the Step status is still "completed" (not failed)
- **AND** the agent message explains the empty result

### Requirement: Agent Layer Independence Maintained
The system SHALL implement tool visibility in the UI layer without modifying the agent layer to import Chainlit.

#### Scenario: No Chainlit imports in agent layer
- **WHEN** the agent layer code is examined
- **THEN** the agent layer does NOT import Chainlit (cl module)
- **AND** the agent tools do NOT reference cl.Step
- **AND** the agent remains UI-framework agnostic

#### Scenario: Tool visibility implemented via UI wrappers
- **WHEN** the UI layer code is examined
- **THEN** tool visibility is implemented by wrapping agent calls with cl.Step
- **AND** the wrappers are located in src/ui/ module
- **AND** the agent layer functions remain unchanged

### Requirement: Step Configuration for Tool Types
The system SHALL configure Steps with appropriate metadata to identify them as tool calls.

#### Scenario: Step type set to "tool"
- **WHEN** a Step is created for a tool call
- **THEN** the Step type parameter is set to "tool"
- **AND** this allows Chainlit to style tool Steps distinctively
- **AND** users can visually distinguish tool calls from other operations

#### Scenario: Step name reflects tool purpose
- **WHEN** a Step is created for a tool call
- **THEN** the Step name clearly describes the tool action (e.g., "Looking up card", "Searching cards")
- **AND** the name is user-friendly, not technical (e.g., not "lookup_card_by_name")
- **AND** the name provides context about what the agent is doing

### Requirement: Error Handling in Tool Steps
The system SHALL gracefully handle tool errors and display them clearly in Steps.

#### Scenario: Tool raises exception
- **WHEN** a tool call raises an exception
- **THEN** the Step status changes to "failed"
- **AND** the Step output shows a user-friendly error message
- **AND** the error does NOT include sensitive information or full stack traces
- **AND** the agent can still respond with a helpful message

#### Scenario: Tool timeout or delay
- **WHEN** a tool call takes longer than expected
- **THEN** the Step remains in "running" status
- **AND** users can see the tool is still executing
- **AND** the Step eventually completes or fails with timeout message

### Requirement: Performance Considerations for Steps
The system SHALL ensure Step creation does not significantly impact response time or user experience.

#### Scenario: Step overhead is minimal
- **WHEN** tool calls are wrapped with Steps
- **THEN** the overhead per Step is less than 50ms
- **AND** users do not perceive noticeable delay
- **AND** the system remains responsive

#### Scenario: Many tool calls handled efficiently
- **WHEN** the agent makes 5+ tool calls in a single conversation turn
- **THEN** all Steps are created and displayed efficiently
- **AND** the UI does not freeze or lag
- **AND** Steps load progressively (not all at once)

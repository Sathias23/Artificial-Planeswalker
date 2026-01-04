# Chainlit UI Specification Delta

## MODIFIED Requirements

### Requirement: Tool Call Visibility with Chainlit Steps
The system SHALL display PydanticAI tool calls visually in the chat interface using Chainlit's Step API to provide transparency into agent operations, AND SHALL only display tool calls from the most recent agent turn to prevent historical clutter.

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

#### Scenario: Only current turn tool calls are shown
- **WHEN** a multi-turn conversation has occurred with tool calls in previous messages
- **AND** the agent responds to the current message with new tool calls
- **THEN** only the tool calls from the current response are displayed as Steps
- **AND** tool calls from previous turns do NOT appear as Steps in the current response
- **AND** the UI remains clean without historical tool call clutter

#### Scenario: Steps appear above streaming response
- **WHEN** the agent executes tool calls and generates a text response
- **THEN** the tool call Steps are created and displayed BEFORE the response text begins streaming
- **AND** users see the tool executions before reading the agent's answer
- **AND** the visual flow shows "what was queried" followed by "the answer"

#### Scenario: Step shows tool execution lifecycle
- **WHEN** a tool call Step is created
- **THEN** the Step initially shows as "running" status
- **AND** the Step updates to "completed" when the tool finishes
- **AND** if the tool fails, the Step shows "failed" status with error message

## ADDED Requirements

### Requirement: Tool Call Extraction Logic
The system SHALL extract tool call information only from the most recent agent response to prevent displaying historical tool calls from previous conversation turns.

#### Scenario: Extract tool calls from current turn only
- **WHEN** `extract_tool_calls(messages)` is called with agent result messages
- **AND** the messages list contains conversation history from multiple turns
- **THEN** the function identifies and returns only tool calls from the most recent model response
- **AND** tool calls from previous turns are excluded from the returned list
- **AND** the extraction logic differentiates between historical and current tool calls

#### Scenario: Multi-turn conversation without tool call duplication
- **WHEN** a user has a 3-message conversation where each message triggers tool calls
- **THEN** message 1 displays only tool calls from turn 1
- **AND** message 2 displays only tool calls from turn 2 (not turn 1 + turn 2)
- **AND** message 3 displays only tool calls from turn 3
- **AND** no tool call Steps are duplicated across messages

#### Scenario: Handle conversation with no tool calls
- **WHEN** the agent responds to a message without invoking any tools
- **THEN** `extract_tool_calls(messages)` returns an empty list
- **AND** no tool call Steps are created
- **AND** only the agent's text response is displayed

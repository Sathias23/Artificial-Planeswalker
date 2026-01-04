# chainlit-ui Spec Delta

## ADDED Requirements

### Requirement: Magic-Themed Thinking Indicator
The system SHALL display Magic: The Gathering-themed thinking messages while the agent processes user requests to provide clear, on-brand feedback.

#### Scenario: Thinking message appears on request
- **WHEN** a user sends a message to the agent
- **THEN** a thinking message is immediately displayed
- **AND** the message uses Magic-themed text (e.g., "🧙‍♂️ Consulting the multiverse...")
- **AND** the message appears as a system message in the chat interface

#### Scenario: Thinking message removed after response
- **WHEN** the agent completes processing and begins responding
- **THEN** the thinking message is removed from the chat interface
- **AND** the removal occurs before the agent response streams
- **AND** no placeholder or artifact remains in the conversation

#### Scenario: Multiple thinking message variants
- **WHEN** users send multiple messages across different sessions
- **THEN** the thinking message text varies randomly for engagement
- **AND** messages include MTG-themed phrases like:
  - "🧙‍♂️ Consulting the multiverse..."
  - "⚡ Searching the aether..."
  - "📜 Shuffling through the library..."
  - "✨ Planeswalking..."
  - "🔮 Scrying for answers..."
- **AND** the random selection provides variety without user configuration

#### Scenario: Thinking message doesn't interfere with tool Steps
- **WHEN** the agent executes tool calls that display as Chainlit Steps
- **THEN** the thinking message does not overlap or interfere with Step display
- **AND** the thinking message is removed before Steps appear
- **AND** the visual flow remains: thinking message → removed → Steps → response

#### Scenario: Thinking message removed on error
- **WHEN** the agent encounters an error during processing
- **THEN** the thinking message is still removed from the interface
- **AND** the error message is displayed normally
- **AND** no thinking message remains visible after error display

#### Scenario: Thinking message uses Chainlit Message API
- **WHEN** the thinking message is created in code
- **THEN** it uses `cl.Message()` with appropriate content
- **AND** the message is sent with `.send()` method
- **AND** the message is removed with `.remove()` method after processing
- **AND** no custom CSS or JavaScript is required for basic functionality

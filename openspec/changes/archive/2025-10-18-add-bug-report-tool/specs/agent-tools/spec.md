# agent-tools Spec Delta

## ADDED Requirements

### Requirement: Bug Report Tool

The agent SHALL provide a tool that enables users to explicitly report bugs and unexpected behavior encountered during chat interactions.

#### Scenario: User explicitly reports a bug

- **GIVEN** a user encounters unexpected behavior
- **WHEN** the user explicitly asks to "report a bug" or "file a bug report"
- **AND** provides a description of the issue
- **THEN** the tool SHALL capture:
  - Unique report ID (UUID)
  - Session ID
  - Timestamp (ISO 8601 format)
  - User's bug description
  - Last 10 conversation messages (user + agent)
  - Agent model name and configuration
- **AND** append the report as a single JSON line to `data/bug_reports.jsonl`
- **AND** return confirmation: "Bug report [ID] submitted. Thank you for reporting this issue!"

#### Scenario: Agent suggests bug report but does not submit

- **GIVEN** the agent detects potential issues or errors
- **WHEN** the agent recognizes a situation worth reporting
- **THEN** the agent MAY suggest filing a bug report
- **BUT** the agent SHALL NOT invoke the `report_bug` tool autonomously
- **AND** the agent SHALL wait for explicit user confirmation to proceed

#### Scenario: User provides detailed description

- **GIVEN** a user asks to report a bug
- **WHEN** the user provides a detailed description (e.g., "The search returned wrong cards for Lightning Bolt")
- **THEN** the tool SHALL capture the full user description in the report
- **AND** include it in the `description` field of the JSONL entry

#### Scenario: Minimal bug report without description

- **GIVEN** a user asks to report a bug
- **WHEN** the user does not provide specific details
- **THEN** the tool SHALL capture conversation context from the last 10 messages
- **AND** set description to a default value: "User reported an issue (no details provided)"
- **AND** still create the bug report entry

#### Scenario: File write failure

- **GIVEN** a user submits a bug report
- **WHEN** the `data/bug_reports.jsonl` file cannot be written (permissions, disk full, etc.)
- **THEN** the tool SHALL raise an exception with error details
- **AND** the agent SHALL inform the user: "Unable to save bug report due to file system error. Please try again or contact support."

#### Scenario: Conversation context capture

- **GIVEN** a user reports a bug during an active session
- **WHEN** the tool captures conversation context
- **THEN** the tool SHALL include the last 10 messages (user + agent) from session history
- **AND** each message SHALL include:
  - Role (user or assistant)
  - Content (text)
  - Timestamp
- **AND** exclude any sensitive information (API keys, tokens)

### Requirement: Bug Report JSONL Format

Bug reports SHALL be stored in `data/bug_reports.jsonl` with one JSON object per line for efficient append and parsing.

#### Scenario: JSONL entry structure

- **GIVEN** a bug report is submitted
- **WHEN** the report is written to the file
- **THEN** each entry SHALL be a single-line JSON object with fields:
  - `id` (string, UUID): Unique report identifier
  - `session_id` (string): Chainlit session ID
  - `timestamp` (string, ISO 8601): When report was created
  - `description` (string): User-provided bug description
  - `conversation_context` (array): Last 10 messages with role, content, timestamp
  - `metadata` (object): Agent model, temperature, session info
- **AND** each entry SHALL be followed by a newline character

#### Scenario: Append-only file operations

- **GIVEN** the bug report file exists
- **WHEN** a new bug report is submitted
- **THEN** the tool SHALL append the new entry to the end of the file
- **AND** NOT modify or rewrite existing entries
- **AND** use atomic file operations to prevent corruption

#### Scenario: File creation on first report

- **GIVEN** the `data/bug_reports.jsonl` file does not exist
- **WHEN** the first bug report is submitted
- **THEN** the tool SHALL create the file with appropriate permissions (644)
- **AND** write the first report entry
- **AND** ensure the `data/` directory exists

#### Scenario: Human-readable timestamps

- **GIVEN** a bug report is created
- **WHEN** the timestamp is written to JSONL
- **THEN** the timestamp SHALL use ISO 8601 format: "YYYY-MM-DDTHH:MM:SS.ffffffZ"
- **AND** use UTC timezone
- **AND** be parseable by standard datetime libraries

### Requirement: Bug Report Conversation Context

The bug report tool SHALL capture relevant conversation history to aid in debugging and issue reproduction.

#### Scenario: Context limited to last 10 messages

- **GIVEN** a session has more than 10 conversation messages
- **WHEN** a bug report is submitted
- **THEN** the tool SHALL capture only the last 10 messages (user + agent)
- **AND** exclude older messages to keep report size manageable

#### Scenario: Context includes message metadata

- **GIVEN** conversation messages are captured
- **WHEN** formatting context for bug report
- **THEN** each message SHALL include:
  - `role`: "user" or "assistant"
  - `content`: Message text
  - `timestamp`: When message was sent
- **AND** exclude internal tool calls or system prompts

#### Scenario: Empty conversation context

- **GIVEN** a bug report is submitted at the start of a session
- **WHEN** there are fewer than 2 messages in history
- **THEN** the tool SHALL capture whatever messages exist (even if 0)
- **AND** set `conversation_context` to empty array `[]` if no messages

### Requirement: Bug Report Metadata

The bug report tool SHALL capture system and session metadata to aid in issue diagnosis.

#### Scenario: Capture agent configuration

- **GIVEN** a bug report is submitted
- **WHEN** collecting metadata
- **THEN** the tool SHALL include:
  - `model`: Agent model name (e.g., "anthropic/claude-sonnet-4.5")
  - `temperature`: Model temperature setting
  - `max_tokens`: Model max tokens setting
  - `timestamp`: Report creation timestamp

#### Scenario: Capture session context

- **GIVEN** a bug report is submitted
- **WHEN** collecting metadata
- **THEN** the tool SHALL include session information:
  - `session_id`: Chainlit session identifier
  - `format_filter`: Active format filter (if any)
- **AND** exclude sensitive session data (user IDs, auth tokens)

#### Scenario: Metadata JSON serialization

- **GIVEN** metadata is collected for bug report
- **WHEN** writing to JSONL file
- **THEN** all metadata fields SHALL be JSON-serializable
- **AND** datetime objects SHALL be converted to ISO 8601 strings
- **AND** None values SHALL be preserved as JSON `null`

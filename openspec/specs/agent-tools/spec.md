# agent-tools Specification

## Purpose
TBD - created by archiving change story-2-2-card-lookup-tool. Update Purpose after archive.
## Requirements
### Requirement: Card Lookup by Name

The agent SHALL provide a `lookup_card_by_name()` tool that finds cards by exact name with optional format and games filtering.

#### Scenario: Lookup card with games filter active

- **GIVEN** session games_filter is set to ["arena"]
- **AND** a card "Cosmic Spider-Man" exists with games=["paper"]
- **WHEN** the user requests "lookup Cosmic Spider-Man"
- **THEN** the tool returns "Card not found" (filtered by games)
- **AND** an explanation mentions the active games filter

#### Scenario: Lookup card bypassing games filter

- **GIVEN** session games_filter is set to ["arena"]
- **AND** a card "Cosmic Spider-Man" exists with games=["paper"]
- **WHEN** `lookup_card_by_name("Cosmic Spider-Man", auto_filter=False)` is called
- **THEN** the card is found and returned
- **AND** the games filter is bypassed for this specific query

#### Scenario: Lookup card with no games filter

- **GIVEN** session games_filter is None
- **AND** a card "Lightning Bolt" exists with games=["paper", "arena", "mtgo"]
- **WHEN** the user requests "lookup Lightning Bolt"
- **THEN** the card is found and returned
- **AND** no games filtering is applied

#### Scenario: Lookup card show games availability

- **GIVEN** any card is found
- **WHEN** the card details are formatted for display
- **THEN** the card's games availability is shown (e.g., "Available in: Paper, Arena, MTGO")
- **AND** the user can see which platforms the card is playable on

### Requirement: Agent Dependency Injection

The agent SHALL support dependency injection for repositories and services via a type-safe dependencies structure.

#### Scenario: Dependencies provided to agent at runtime

- **GIVEN** an agent is created with `AgentDependencies` as the deps type
- **WHEN** the agent is invoked with `agent.run(deps=dependencies_instance)`
- **THEN** tools SHALL access repositories via `ctx.deps.card_repository`

#### Scenario: Tool accesses repository via context

- **GIVEN** a tool function decorated with `@agent.tool`
- **WHEN** the tool receives `RunContext[AgentDependencies]` as first parameter
- **THEN** the tool SHALL access the card repository via `ctx.deps.card_repository`
- **AND** invoke repository methods for database queries

### Requirement: Tool Documentation

The card lookup tool SHALL provide clear documentation via docstring for LLM schema generation.

#### Scenario: LLM receives tool description

- **GIVEN** the agent is processing a user query
- **WHEN** the LLM decides which tool to use
- **THEN** the LLM SHALL receive a tool description extracted from the function docstring

#### Scenario: LLM receives parameter descriptions

- **GIVEN** the card lookup tool has parameters
- **WHEN** the LLM constructs a tool call
- **THEN** the LLM SHALL receive parameter descriptions extracted from docstring Args section

### Requirement: Tool Error Handling

The card lookup tool SHALL handle expected errors gracefully with user-friendly messages.

#### Scenario: User-friendly error for not found

- **GIVEN** a card query returns no results
- **WHEN** the tool returns an error message
- **THEN** the message SHALL be conversational and suggest next steps
- **AND** the message SHALL NOT include technical error codes or stack traces

#### Scenario: User-friendly error for ambiguous query

- **GIVEN** a card query returns too many results
- **WHEN** the tool returns an error message
- **THEN** the message SHALL list matching options (up to 10)
- **AND** suggest refining the search

### Requirement: Advanced Card Search with Multiple Filters

The agent SHALL provide a `search_cards_advanced()` tool that supports games filtering with auto-filter bypass capability.

#### Scenario: Search with active games filter

- **GIVEN** session games_filter is set to ["arena"]
- **WHEN** the user searches for "red creatures with haste"
- **THEN** the `search_cards_advanced()` tool uses games=["arena"] from session
- **AND** only Arena-available red creatures with haste are returned

#### Scenario: Search with explicit games parameter

- **GIVEN** session games_filter is None
- **WHEN** the user requests "show me paper-only red creatures"
- **THEN** the `search_cards_advanced()` tool is called with games=["paper"]
- **AND** only paper-available cards are returned

#### Scenario: Search bypassing games filter with auto_filter

- **GIVEN** session games_filter is set to ["arena"]
- **WHEN** the user explicitly requests "show me all cards, ignore filters"
- **THEN** `search_cards_advanced(auto_filter=False)` is called
- **AND** the games filter is bypassed
- **AND** cards from all platforms are returned

#### Scenario: Search results show games availability

- **GIVEN** any search returns results
- **WHEN** the results are formatted for display
- **THEN** each card shows its games availability
- **AND** the user can see which platforms each card is available on

#### Scenario: Search with both format and games filters

- **GIVEN** session format_filter is "standard" and games_filter is ["arena"]
- **WHEN** the user searches for "blue instants"
- **THEN** the tool applies BOTH filters
- **AND** only Standard-legal Arena-available blue instants are returned

### Requirement: Advanced Search Result Formatting

The advanced search tool SHALL format results in a clear, scannable list optimized for chat display, including pagination metadata when applicable.

#### Scenario: Standard result formatting

- **GIVEN** the advanced search returns 5 matching cards
- **WHEN** the results are formatted for display
- **THEN** each card SHALL be displayed as:
  - Card name
  - Mana cost (using text notation like "{2}{R}")
  - Type line
  - Power/toughness (if creature)
- **AND** results SHALL be numbered for easy reference

#### Scenario: Result formatting with pagination

- **GIVEN** the advanced search returns 52 cards with page=1, page_size=20
- **WHEN** the results are formatted for display
- **THEN** the header SHALL include "Found 52 cards (Page 1 of 3, showing 1-20)"
- **AND** the footer SHALL indicate "32 more results available"
- **AND** suggest "Say 'next page' or 'show me more' to see page 2"

#### Scenario: Result formatting with oracle text filter

- **GIVEN** the advanced search uses oracle_text=["target creature", "gains flying"]
- **WHEN** the results are formatted for display
- **THEN** the filter summary SHALL include "Oracle text: 'target creature', 'gains flying'"
- **AND** clearly indicate that oracle text filtering was applied

#### Scenario: Result grouping by mana value

- **GIVEN** the advanced search returns cards with various mana values
- **WHEN** formatting for display
- **THEN** results MAY be optionally grouped by mana value
- **AND** include section headers (e.g., "0-1 Mana", "2-3 Mana")

#### Scenario: No results with oracle text suggestion

- **GIVEN** a search with multiple filters returns no results
- **WHEN** oracle text search is available but not used
- **THEN** the "no results" message SHALL suggest "try oracle text search for specific effects"
- **AND** provide an example (e.g., "oracle_text=['destroy target creature']")

### Requirement: Advanced Search Performance

The advanced search tool SHALL execute queries efficiently to meet system performance requirements.

#### Scenario: Query execution time within limits

- **GIVEN** a multi-criteria search is performed
- **WHEN** the repository executes the combined filter query
- **THEN** the query SHALL complete in less than 500ms (per NFR7)
- **AND** use appropriate database indexes for common filter combinations

#### Scenario: Efficient keyword search

- **GIVEN** a keyword ability search is performed
- **WHEN** searching oracle_text for keyword terms
- **THEN** the query SHALL use case-insensitive substring matching
- **AND** limit text search to indexed columns where possible

### Requirement: Format Filter Control Tool

The agent SHALL provide a tool that enables users to set or clear the format legality filter for card queries.

#### Scenario: Enable Standard format filter

- **GIVEN** the format filter is currently disabled (None)
- **WHEN** the user asks "only show me Standard-legal cards"
- **AND** the `set_format_filter` tool is invoked with format="standard"
- **THEN** the session context format filter is set to "standard"
- **AND** the agent responds with confirmation: "Format filter set to Standard. I'll only show Standard-legal cards in searches."

#### Scenario: Disable format filter

- **GIVEN** the format filter is currently set to "standard"
- **WHEN** the user asks "show me all cards regardless of format"
- **AND** the `set_format_filter` tool is invoked with format=None
- **THEN** the session context format filter is cleared
- **AND** the agent responds with confirmation: "Format filter disabled. I'll show all cards regardless of format legality."

#### Scenario: Check current filter status

- **GIVEN** a format filter is currently set
- **WHEN** the user asks "what format filter is active?"
- **THEN** the agent responds with the current filter status
- **AND** indicates whether filtering is enabled or disabled

#### Scenario: Invalid format value

- **GIVEN** the user attempts to set an unsupported format
- **WHEN** the `set_format_filter` tool is invoked with format="modern"
- **THEN** the tool returns an error message: "Format 'modern' is not supported yet. Supported formats: standard"
- **AND** the session context format filter remains unchanged

### Requirement: Format-Aware Card Lookup

The card lookup tool SHALL respect the session format filter when querying cards.

#### Scenario: Card lookup with Standard filter active

- **GIVEN** the session format filter is set to "standard"
- **WHEN** the user asks "Show me Sol Ring"
- **AND** Sol Ring has `legalities.standard = "not_legal"`
- **THEN** the tool returns: "Sol Ring not found in Standard-legal cards. (Format filter: Standard)"
- **AND** suggests: "To see all cards, disable the format filter."

#### Scenario: Card lookup without format filter

- **GIVEN** the session format filter is None
- **WHEN** the user asks "Show me Sol Ring"
- **THEN** the tool returns Sol Ring's card details
- **AND** no format legality message is included

#### Scenario: Partial match with format filter

- **GIVEN** the session format filter is set to "standard"
- **WHEN** the user asks "Show me Bolt"
- **AND** only Standard-legal "Bolt" cards exist in results
- **THEN** the tool returns only Standard-legal matching cards
- **AND** includes note: "(Showing Standard-legal cards only)"

### Requirement: Format-Aware Advanced Search

The advanced card search tool SHALL respect the session format filter when executing multi-criteria searches.

#### Scenario: Advanced search with Standard filter active

- **GIVEN** the session format filter is set to "standard"
- **WHEN** the user asks "show me red creatures with haste under 4 mana"
- **THEN** the tool applies all search criteria AND format filter
- **AND** returns only cards with `legalities.standard = "legal"`
- **AND** includes header: "Standard-legal red creatures with haste under 4 mana:"

#### Scenario: Advanced search without format filter

- **GIVEN** the session format filter is None
- **WHEN** the user asks "show me red creatures with haste under 4 mana"
- **THEN** the tool applies search criteria without format restriction
- **AND** returns all matching cards regardless of format
- **AND** no format indicator is included in results

#### Scenario: Format filter reduces results to zero

- **GIVEN** the session format filter is set to "standard"
- **WHEN** the user performs a search that returns no Standard-legal cards
- **THEN** the tool returns: "No Standard-legal cards found matching your criteria."
- **AND** suggests: "Try relaxing your search criteria or disable the format filter to see all cards."

### Requirement: Format Filter Session Context

The agent dependencies SHALL include format filter state that persists across tool invocations within a session.

#### Scenario: Format filter persists across tool calls

- **GIVEN** the format filter is set to "standard"
- **WHEN** multiple card queries are made in the same session
- **THEN** all queries use the "standard" format filter
- **AND** the user does not need to specify format on each query

#### Scenario: New session resets format filter

- **GIVEN** a previous session had format filter set to "standard"
- **WHEN** a new session is started
- **THEN** the format filter is initialized to None (disabled)
- **AND** the user must explicitly set format filter if desired

#### Scenario: Format filter accessible to all tools

- **GIVEN** the format filter is stored in session context
- **WHEN** any card query tool accesses the context
- **THEN** the tool can read the current format filter value
- **AND** apply it to repository queries

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

### Requirement: Bug Report Status Lifecycle

Bug reports SHALL include a status field that tracks the lifecycle state from creation through resolution and archival.

#### Scenario: New bug report created with open status

- **GIVEN** a user reports a bug via the `report_bug` tool
- **WHEN** the bug report is written to `data/bug_reports.jsonl`
- **THEN** the report SHALL include `status="open"` by default
- **AND** SHALL include `updated_at` timestamp matching the creation timestamp

#### Scenario: Bug status updated to investigating

- **GIVEN** a bug report with status="open" exists
- **WHEN** a developer updates the status to "investigating"
- **THEN** a new JSONL entry SHALL be appended with:
  - Same `id` as original bug
  - `status="investigating"`
  - `updated_at` with current timestamp
  - `update_type="status_change"`
- **AND** the original bug entry SHALL remain unchanged (append-only)

#### Scenario: Bug marked as resolved

- **GIVEN** a bug report with status="investigating" exists
- **WHEN** a developer updates the status to "resolved"
- **THEN** a new JSONL entry SHALL be appended indicating resolution
- **AND** the bug is eligible for archival after 90 days

#### Scenario: Bug closed without resolution

- **GIVEN** a bug report with any status exists
- **WHEN** a developer updates the status to "closed" (duplicate, won't fix, etc.)
- **THEN** a new JSONL entry SHALL be appended with status="closed"
- **AND** the bug is eligible for archival after 90 days

#### Scenario: Bug archived for historical reference

- **GIVEN** a bug report with status="resolved" or "closed" exists
- **AND** the `updated_at` timestamp is more than 90 days old
- **WHEN** the archive process is executed
- **THEN** the bug SHALL be copied to `data/bug_reports_archive.jsonl`
- **AND** a new entry SHALL be appended to main file with status="archived"

#### Scenario: Reading bug with multiple status entries

- **GIVEN** a bug ID has multiple JSONL entries (status updates)
- **WHEN** the bug report is read from the file
- **THEN** the system SHALL use the entry with the **latest** `updated_at` timestamp
- **AND** discard earlier entries for the same bug ID

### Requirement: Bug Status Values

The bug status field SHALL use a defined set of lifecycle values with clear semantics.

#### Scenario: Valid status values

- **GIVEN** a bug report is created or updated
- **WHEN** setting the status field
- **THEN** the status SHALL be one of:
  - `"open"`: New bug, not yet triaged
  - `"investigating"`: Bug confirmed and being researched
  - `"resolved"`: Bug fixed or addressed
  - `"closed"`: Bug not reproducible, duplicate, or won't fix
  - `"archived"`: Old bug moved to archive file
- **AND** invalid status values SHALL be rejected with an error

#### Scenario: Invalid status value rejected

- **GIVEN** a bug status update is attempted
- **WHEN** the status value is not in the allowed set (e.g., "pending", "complete")
- **THEN** the system SHALL raise a validation error
- **AND** the bug report SHALL NOT be updated

### Requirement: Bug Report Schema with Status

Bug reports SHALL include status and update timestamp fields in the JSONL schema.

#### Scenario: JSONL entry with status fields

- **GIVEN** a bug report is written to `data/bug_reports.jsonl`
- **WHEN** the JSONL entry is created
- **THEN** the entry SHALL include these fields:
  - `id` (string, UUID): Unique report identifier
  - `session_id` (string): Chainlit session ID
  - `timestamp` (string, ISO 8601): When report was created
  - `description` (string): User-provided bug description
  - `conversation_context` (array): Last 10 messages
  - `metadata` (object): Agent model and session info
  - `status` (string): Current lifecycle state (default: "open")
  - `updated_at` (string, ISO 8601): When status was last updated
- **AND** for new reports, `updated_at` SHALL equal `timestamp`

#### Scenario: Status update JSONL entry

- **GIVEN** a bug status is being updated
- **WHEN** the update entry is written to JSONL
- **THEN** the entry SHALL include:
  - `id` (same as original bug)
  - `status` (new status value)
  - `updated_at` (current timestamp)
  - `update_type` (string): "status_change"
- **AND** SHALL NOT include full conversation context (update-only entry)

#### Scenario: Backward compatibility with legacy reports

- **GIVEN** existing bug reports in JSONL format without `status` field
- **WHEN** reading the bug reports file
- **THEN** reports without `status` SHALL be treated as status="open"
- **AND** reports without `updated_at` SHALL use `timestamp` as `updated_at`
- **AND** no data migration is required

### Requirement: Bug Report Status Management CLI

Developers SHALL have a CLI tool to manage bug report statuses and perform archival operations.

#### Scenario: List all bugs with status filter

- **GIVEN** the CLI tool `manage_bug_reports.py` is available
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py list --status open`
- **THEN** the tool SHALL display all bugs with status="open"
- **AND** output SHALL include: bug ID, description (truncated), status, updated_at

#### Scenario: List all bugs without filter

- **GIVEN** the CLI tool is available
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py list`
- **THEN** the tool SHALL display all active bugs (non-archived)
- **AND** group by status (open, investigating, resolved, closed)

#### Scenario: Update bug status

- **GIVEN** the CLI tool is available
- **AND** a bug with ID "abc-123" exists with status="open"
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py update abc-123 --status investigating`
- **THEN** the tool SHALL append a new JSONL entry with:
  - `id="abc-123"`
  - `status="investigating"`
  - `updated_at=<current timestamp>`
  - `update_type="status_change"`
- **AND** confirm the update to the developer

#### Scenario: Update status with invalid bug ID

- **GIVEN** the CLI tool is available
- **WHEN** developer runs update command with non-existent bug ID
- **THEN** the tool SHALL return error: "Bug ID not found: [id]"
- **AND** no JSONL entry SHALL be created

#### Scenario: Archive old resolved bugs

- **GIVEN** the CLI tool is available
- **AND** bugs exist with status="resolved" or "closed"
- **AND** `updated_at` is older than 90 days
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py archive --older-than-days 90`
- **THEN** the tool SHALL:
  1. Copy matching bugs to `data/bug_reports_archive.jsonl`
  2. Append archive entry to main file with status="archived"
  3. Report count of bugs archived

#### Scenario: Dry run archive operation

- **GIVEN** the CLI tool is available
- **WHEN** developer runs `uv run python scripts/manage_bug_reports.py archive --older-than-days 90 --dry-run`
- **THEN** the tool SHALL display which bugs would be archived
- **AND** NOT modify any files

### Requirement: Bug Report Archival Process

Old resolved or closed bugs SHALL be moved to an archive file to keep the active bug list manageable.

#### Scenario: Archive file creation

- **GIVEN** the archive process is executed for the first time
- **WHEN** bugs are archived
- **THEN** the file `data/bug_reports_archive.jsonl` SHALL be created
- **AND** archived bugs SHALL be appended to this file
- **AND** file permissions SHALL be set to 0o644 (rw-r--r--)

#### Scenario: Bug copied to archive

- **GIVEN** a bug with status="resolved" and updated_at > 90 days old
- **WHEN** the archive process runs
- **THEN** the complete bug report entry SHALL be copied to archive file
- **AND** retain all original fields (id, description, conversation_context, etc.)

#### Scenario: Archive marker in main file

- **GIVEN** a bug has been copied to archive file
- **WHEN** the archive process completes
- **THEN** a new entry SHALL be appended to main JSONL with:
  - Same bug `id`
  - `status="archived"`
  - `updated_at=<current timestamp>`
  - `update_type="archived"`
- **AND** future reads SHALL treat this bug as archived

#### Scenario: Archived bugs excluded from active list

- **GIVEN** bugs have been archived
- **WHEN** listing bugs without `--include-archived` flag
- **THEN** archived bugs SHALL NOT appear in results
- **AND** only bugs with status in (open, investigating, resolved, closed) SHALL be shown

#### Scenario: Include archived bugs in query

- **GIVEN** bugs have been archived
- **WHEN** developer runs `list --include-archived`
- **THEN** both active and archived bugs SHALL be displayed
- **AND** archived bugs SHALL be marked with status="archived"

### Requirement: Bug Status Filtering

The CLI tool SHALL support filtering bug reports by status to aid in triage and workflow management.

#### Scenario: Filter by single status

- **GIVEN** the bug reports file contains bugs with various statuses
- **WHEN** developer runs `list --status investigating`
- **THEN** only bugs with status="investigating" SHALL be displayed
- **AND** bugs with other statuses SHALL be excluded

#### Scenario: Filter by multiple statuses

- **GIVEN** the bug reports file contains bugs with various statuses
- **WHEN** developer runs `list --status open,investigating`
- **THEN** bugs with status="open" OR status="investigating" SHALL be displayed
- **AND** bugs with status="resolved", "closed", or "archived" SHALL be excluded

#### Scenario: Default filter excludes archived

- **GIVEN** the bug reports file contains archived bugs
- **WHEN** developer runs `list` without status filter
- **THEN** archived bugs SHALL be excluded by default
- **AND** only active bugs (open, investigating, resolved, closed) SHALL be shown

### Requirement: Bug Status Audit Trail

All status changes SHALL be recorded as append-only JSONL entries to maintain a complete audit trail.

#### Scenario: Full status history preserved

- **GIVEN** a bug has been updated multiple times (open → investigating → resolved → archived)
- **WHEN** reading all JSONL entries for that bug ID
- **THEN** all status transitions SHALL be present in the file
- **AND** each entry SHALL have an `updated_at` timestamp
- **AND** entries SHALL be in chronological order (appended sequentially)

#### Scenario: Status change attribution

- **GIVEN** a bug status update is recorded
- **WHEN** the JSONL entry is written
- **THEN** the entry MAY include an optional `updated_by` field
- **AND** this field SHALL indicate who/what updated the status (e.g., "developer", "automated-script")
- **AND** if omitted, defaults to "manual"

#### Scenario: Reconstruct bug lifecycle

- **GIVEN** a bug with multiple status entries in JSONL
- **WHEN** a developer reviews the bug history
- **THEN** the full lifecycle SHALL be reconstructable:
  - Created at timestamp X with status="open"
  - Updated at timestamp Y to status="investigating"
  - Updated at timestamp Z to status="resolved"
  - Archived at timestamp W with status="archived"
- **AND** timeline is deterministic based on `updated_at` fields

### Requirement: Add Card to Deck Tool

The agent SHALL provide a tool that enables adding cards to the active deck with quantity specification, Standard format validation, deck construction rule enforcement, **and automatic mana curve feedback when enabled**.

#### Scenario: Add card to active deck successfully

- **GIVEN** an active deck is set in session context
- **AND** a user requests "add 4 Lightning Bolt to my deck"
- **WHEN** the tool is invoked with name="Lightning Bolt" and quantity=4
- **AND** Lightning Bolt is Standard-legal
- **AND** the deck currently has 0 copies of Lightning Bolt
- **THEN** the tool SHALL add 4 copies of Lightning Bolt to the deck
- **AND** return a confirmation message with card name, quantity, and updated total deck count

#### Scenario: Add single card with default quantity

- **GIVEN** an active deck exists
- **AND** a user requests "add Sheoldred to my deck"
- **WHEN** the tool is invoked with name="Sheoldred" (no quantity specified)
- **THEN** the tool SHALL add 1 copy of the card (quantity defaults to 1)
- **AND** return confirmation with the added card details

#### Scenario: Automatic curve feedback after addition

- **GIVEN** an active deck exists
- **AND** auto-feedback is enabled (default)
- **AND** a user adds a card that significantly changes the curve
- **WHEN** the add_card_to_deck tool completes successfully
- **THEN** the tool SHALL invoke contextual feedback generation logic
- **AND** append curve feedback to the tool result message
- **AND** the agent SHALL include feedback in its response to the user

#### Scenario: Auto-feedback respects disabled preference

- **GIVEN** an active deck exists
- **AND** auto-feedback is disabled (user explicitly disabled)
- **WHEN** the add_card_to_deck tool completes successfully
- **THEN** the tool SHALL NOT generate curve feedback
- **AND** return only the standard card addition confirmation

#### Scenario: Auto-feedback skips insignificant changes

- **GIVEN** an active deck with 20 cards and balanced curve
- **AND** auto-feedback is enabled
- **WHEN** a user adds 1 card that doesn't significantly change curve distribution (< 15% shift in any CMC bucket)
- **THEN** the tool SHALL skip feedback generation
- **AND** return only the standard card addition confirmation
- **AND** avoid feedback fatigue from repetitive messages

#### Scenario: Positive reinforcement feedback

- **GIVEN** an aggro deck with few early drops
- **AND** auto-feedback is enabled
- **WHEN** a user adds a 1-mana creature
- **THEN** the feedback SHALL include positive reinforcement
- **AND** message like "Great addition! Strong early-game presence for an aggressive deck."

#### Scenario: Warning feedback for curve issues

- **GIVEN** a deck with many 5+ CMC cards
- **AND** auto-feedback is enabled
- **WHEN** a user adds another high-cost card
- **THEN** the feedback SHALL include a warning
- **AND** message like "Your deck is getting top-heavy. Consider adding more 1-3 mana plays for early-game consistency."

### Requirement: Deck Construction Rule Validation

The system SHALL validate deck construction rules in the business logic layer before adding cards to decks.

#### Scenario: Validate 4-copy limit for non-basic cards

- **GIVEN** a deck with 2 copies of Lightning Bolt
- **WHEN** `validate_card_addition(deck, card=Lightning Bolt, quantity=3)` is called
- **THEN** the validator SHALL return `ValidationResult(is_valid=False, error_message="Cannot add 3 copies...")`

#### Scenario: Allow unlimited basic lands

- **GIVEN** a deck with 20 copies of Forest
- **WHEN** `validate_card_addition(deck, card=Forest, quantity=10)` is called
- **AND** Forest has `type_line` containing "Basic Land"
- **THEN** the validator SHALL return `ValidationResult(is_valid=True, error_message=None)`

#### Scenario: Validate card not already at 4-copy limit

- **GIVEN** a deck with 4 copies of Llanowar Elves
- **WHEN** `validate_card_addition(deck, card=Llanowar Elves, quantity=1)` is called
- **THEN** the validator SHALL return `ValidationResult(is_valid=False, error_message="Cannot add 1 copy of 'Llanowar Elves'. Deck already has 4 copies (max 4 for non-basic lands).")`

#### Scenario: Helper function identifies basic lands correctly

- **GIVEN** a card with `type_line = "Basic Land — Mountain"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `True`

#### Scenario: Helper function identifies non-basic lands correctly

- **GIVEN** a card with `type_line = "Creature — Goblin"`
- **WHEN** `is_basic_land(card)` is called
- **THEN** the function SHALL return `False`

#### Scenario: Get current card count from deck

- **GIVEN** a deck with 3 copies of Shock in mainboard and 1 copy in sideboard
- **WHEN** `get_current_card_count(deck, card_id="shock-id")` is called
- **THEN** the function SHALL return 3 (mainboard only, sideboard excluded)

### Requirement: Create Deck Tool
The system SHALL provide a `create_deck` PydanticAI tool that enables users to create new decks through natural language conversation, including optional strategy specification.

#### Scenario: Create deck with name only
- **GIVEN** the agent has `create_deck` tool registered
- **WHEN** user says "create a new deck called Mono Red Aggro"
- **THEN** the agent invokes `create_deck` tool with name="Mono Red Aggro" and default format="standard"
- **AND** a new deck is created in the database
- **AND** the agent responds with confirmation including deck name and ID
- **AND** the deck ID is stored as the active deck in session context
- **AND** the strategy field is NULL (not specified)

#### Scenario: Create deck with explicit format
- **GIVEN** the agent has `create_deck` tool registered
- **WHEN** user says "create a commander deck named Dragon Tribal"
- **THEN** the agent invokes `create_deck` tool with name="Dragon Tribal" and format="commander"
- **AND** a new deck is created with the specified format
- **AND** the agent confirms the deck creation with format information
- **AND** the strategy field is NULL

#### Scenario: Create deck with strategy
- **GIVEN** the agent has `create_deck` tool registered
- **WHEN** user says "create a control deck called Counter Magic with strategy focused on counters and card draw"
- **THEN** the agent invokes `create_deck` tool with name="Counter Magic", format="standard", strategy="focused on counters and card draw"
- **AND** a new deck is created with the specified strategy
- **AND** the agent confirms deck creation including strategy information
- **AND** the strategy is stored in the database

#### Scenario: Create deck and track in session
- **GIVEN** the agent has an active session with session_id
- **WHEN** a deck is created via the tool
- **THEN** the tool calls `_session_manager.set_active_deck_id(session_id, deck_id)`
- **AND** the deck ID is stored in session manager
- **AND** subsequent messages in the session will have `deps.active_deck_id` populated

#### Scenario: Handle duplicate deck names
- **GIVEN** a deck named "Test Deck" already exists
- **WHEN** user says "create a deck called Test Deck"
- **THEN** the tool creates a new deck with duplicate name allowed
- **AND** the agent confirms creation and mentions duplicate name scenario
- **OR** the tool appends a timestamp/counter suffix (e.g., "Test Deck 2")
- **AND** the agent confirms creation with the modified name

#### Scenario: Invalid format parameter
- **GIVEN** the agent attempts to create a deck with an invalid format
- **WHEN** the tool is invoked with format="invalid_format"
- **THEN** Pydantic validation raises a ValidationError
- **AND** the agent responds with a helpful error message listing valid formats

#### Scenario: Database error during creation
- **GIVEN** the database is unavailable or encounters an error
- **WHEN** the tool attempts to create a deck
- **THEN** the tool catches the exception
- **AND** the agent responds with an error message asking user to retry
- **AND** no active deck ID is stored in session manager

### Requirement: Deck Repository in Agent Dependencies
The system SHALL provide `DeckRepository` and `active_deck_id` as part of `AgentDependencies` for deck tool access to database operations and session state.

#### Scenario: DeckRepository available in tools
- **GIVEN** an agent tool requires deck database access
- **WHEN** the tool is invoked with `deps: AgentDependencies` parameter
- **THEN** `deps.deck_repository` is available and initialized
- **AND** the repository can perform CRUD operations

#### Scenario: Active deck ID available in dependencies
- **GIVEN** a session has an active deck set
- **WHEN** `get_agent_dependencies(session_id)` creates dependencies
- **THEN** `deps.active_deck_id` contains the stored deck ID
- **AND** tools can access the active deck without additional lookups

#### Scenario: DeckRepository lifecycle
- **GIVEN** a user message is being processed by the agent
- **WHEN** `get_agent_dependencies()` context manager is used
- **THEN** a `DeckRepository` instance is created with the session
- **AND** `active_deck_id` is retrieved from session manager
- **AND** the repository is properly cleaned up when the context exits

### Requirement: Active Deck Session Management

The system SHALL maintain an active deck in the session context to support deck building operations across multiple user interactions, and SHALL support switching between decks when loading a different deck.

#### Scenario: Set active deck on creation

- **GIVEN** no active deck exists in the session
- **WHEN** a user creates a new deck via the create_deck tool
- **THEN** the newly created deck SHALL be set as the active deck
- **AND** the session context SHALL store the deck ID and name

#### Scenario: Set active deck on load

- **GIVEN** "Deck A" is currently the active deck
- **WHEN** a user loads "Deck B" via the load_deck tool
- **THEN** "Deck B" SHALL become the active deck
- **AND** the session context SHALL be updated with "Deck B" ID and name
- **AND** subsequent operations SHALL target "Deck B"

#### Scenario: Clear active deck on deletion

- **GIVEN** "Deck A" is the active deck
- **WHEN** "Deck A" is deleted via the delete_deck tool
- **THEN** the active deck SHALL be cleared from the session context
- **AND** the session SHALL have no active deck
- **AND** deck operations requiring an active deck SHALL prompt user to create or load a deck

#### Scenario: Retrieve active deck context

- **GIVEN** an active deck is set in the session
- **WHEN** any deck operation tool is invoked
- **THEN** the tool SHALL access the active deck ID from `ctx.deps.format_context['active_deck_id']`
- **AND** use the ID for deck-specific operations

#### Scenario: No active deck context

- **GIVEN** no active deck is set in the session
- **WHEN** a user attempts an operation requiring an active deck (e.g., "add card to deck")
- **THEN** the tool SHALL return a friendly error message
- **AND** prompt the user to create a new deck or load an existing deck

#### Scenario: Active deck persists across multiple turns

- **GIVEN** a user creates "Deck A" in turn 1
- **WHEN** the user adds cards in turns 2-5
- **THEN** all operations SHALL target "Deck A"
- **AND** the session context SHALL maintain the active deck ID throughout the conversation

### Requirement: Create Deck Tool Type Safety
The system SHALL maintain strict type hints for the `create_deck` tool with mypy validation.

#### Scenario: Tool function type hints
- **GIVEN** the `create_deck` tool function definition
- **WHEN** mypy analyzes the function in strict mode
- **THEN** no type errors are reported
- **AND** all parameters have explicit type annotations
- **AND** the return type is explicitly declared

#### Scenario: Dependency injection type hints
- **GIVEN** the tool accepts `deps: AgentDependencies`
- **WHEN** mypy analyzes the dependency injection
- **THEN** no type errors are reported
- **AND** `deps.deck_repository` is recognized as `DeckRepository` type

### Requirement: Create Deck Tool Unit Tests
The system SHALL provide unit tests verifying deck creation tool behavior with mocked dependencies.

#### Scenario: Test successful deck creation
- **GIVEN** a unit test with mocked DeckRepository and mocked session manager
- **WHEN** `create_deck` is called with name="Test Deck"
- **THEN** the repository's `create_deck` method is called once
- **AND** `_session_manager.set_active_deck_id` is called with the deck ID
- **AND** a confirmation message is returned

#### Scenario: Test duplicate name handling
- **GIVEN** a unit test with mocked repository
- **WHEN** creating a deck with a duplicate name
- **THEN** the tool handles the scenario per design decision
- **AND** the test verifies the expected behavior (allow duplicate or append suffix)

#### Scenario: Test error handling
- **GIVEN** a unit test with mocked repository that raises an exception
- **WHEN** `create_deck` is called
- **THEN** the tool catches the exception
- **AND** returns an error message
- **AND** `_session_manager.set_active_deck_id` is NOT called

### Requirement: Create Deck Tool Integration Tests
The system SHALL provide integration tests verifying end-to-end deck creation through the agent with a test database.

#### Scenario: End-to-end deck creation via agent
- **GIVEN** an integration test with test database and agent instance
- **WHEN** agent processes natural language input "create deck named Integration Test"
- **THEN** the `create_deck` tool is invoked
- **AND** a deck is persisted to the test database
- **AND** the deck can be retrieved by ID

#### Scenario: Multiple deck creations in session
- **GIVEN** an integration test with test database and session manager
- **WHEN** creating multiple decks in sequence
- **THEN** each deck is persisted with unique ID
- **AND** the active deck ID in session manager updates to the most recently created deck
- **AND** all decks are retrievable from the database
- **AND** `deps.active_deck_id` reflects the latest deck ID

#### Scenario: Natural language variations
- **GIVEN** an integration test with the agent
- **WHEN** using various phrasings ("create deck X", "new deck called Y", "make a deck named Z")
- **THEN** all variations successfully invoke the tool
- **AND** decks are created for each variation
- **AND** the agent responds appropriately to each phrasing

### Requirement: View Deck Tool
The agent SHALL provide a `view_deck` tool that displays the current active deck contents with formatted card list, total counts, summary statistics, and strategy information.

#### Scenario: View non-empty deck grouped by card type
- **GIVEN** an active deck exists with cards in mainboard and sideboard
- **WHEN** the user asks "show my deck" or "what's in my deck?"
- **AND** the `view_deck` tool is invoked
- **THEN** the tool SHALL return a formatted deck list grouped by card type
- **AND** cards SHALL be grouped as: Creatures, Spells (Instants/Sorceries/Enchantments/Artifacts), Lands
- **AND** within each group, cards SHALL be sorted by mana cost ascending, then alphabetically
- **AND** each card SHALL display: quantity, name, mana cost, type line
- **AND** the display SHALL include total mainboard count and total sideboard count
- **AND** the display SHALL indicate if the deck meets minimum deck size (60+ cards for Standard)
- **AND** if strategy is set, display "Strategy: {strategy}" at the top

#### Scenario: View empty deck
- **GIVEN** an active deck exists with no cards added
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL return message: "Your deck is empty. Add cards to get started."
- **AND** indicate deck name and format
- **AND** if strategy is set, include "Strategy: {strategy}"

#### Scenario: View deck with no active deck set
- **GIVEN** no active deck is set in session context (active_deck_id is None)
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL return message: "No active deck. Create a new deck or load an existing one to get started."
- **AND** suggest using deck creation or loading commands

#### Scenario: View deck with mainboard and sideboard
- **GIVEN** an active deck has cards in both mainboard and sideboard
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL display mainboard cards first, grouped by type
- **AND** then display sideboard cards separately with header "Sideboard:"
- **AND** sideboard cards SHALL also be grouped and sorted by type and mana cost
- **AND** if strategy is set, display at the top

#### Scenario: View deck summary statistics
- **GIVEN** an active deck with multiple cards
- **WHEN** the `view_deck` tool is invoked
- **THEN** the tool SHALL include summary statistics:
  - Deck name and format
  - Strategy (if set)
  - Total mainboard cards
  - Total sideboard cards
  - Number of unique cards
- **AND** indicate whether deck is legal for format (60+ cards for Standard)

### Requirement: Remove Card from Deck Tool

The agent SHALL provide a `remove_card_from_deck` tool that removes cards from the active deck with quantity validation and user-friendly error handling.

#### Scenario: Remove card from mainboard

- **GIVEN** an active deck contains 4 copies of "Lightning Bolt" in mainboard
- **WHEN** the user asks "remove 2 Lightning Bolt from my deck"
- **AND** the `remove_card_from_deck` tool is invoked with card_name="Lightning Bolt", sideboard=False
- **THEN** the tool SHALL look up the card by name to resolve card_id
- **AND** call `deck_repository.remove_card_from_deck(deck_id, card_id, sideboard=False)`
- **AND** return confirmation: "Removed Lightning Bolt from your deck."

#### Scenario: Remove card from sideboard

- **GIVEN** an active deck contains 2 copies of "Rest in Peace" in sideboard
- **WHEN** the user asks "remove Rest in Peace from sideboard"
- **AND** the `remove_card_from_deck` tool is invoked with card_name="Rest in Peace", sideboard=True
- **THEN** the tool SHALL remove the card from sideboard
- **AND** return confirmation: "Removed Rest in Peace from sideboard."

#### Scenario: Remove card not in deck

- **GIVEN** an active deck does not contain "Sol Ring"
- **WHEN** the `remove_card_from_deck` tool is invoked with card_name="Sol Ring"
- **THEN** the tool SHALL return message: "Sol Ring not found in your deck. Check the card name or view your deck to see current contents."
- **AND** NOT raise an exception

#### Scenario: Remove card with invalid name

- **GIVEN** the user attempts to remove "Nonexistent Card XYZ"
- **WHEN** the `remove_card_from_deck` tool looks up the card
- **AND** the card is not found in the card database
- **THEN** the tool SHALL return message: "Card 'Nonexistent Card XYZ' not found in card database. Check spelling or use card search."

#### Scenario: Remove card with no active deck

- **GIVEN** no active deck is set in session context
- **WHEN** the `remove_card_from_deck` tool is invoked
- **THEN** the tool SHALL return message: "No active deck. Create or load a deck first."
- **AND** NOT attempt database operations

### Requirement: Update Card Quantity Tool

The agent SHALL provide an `update_card_quantity` tool that modifies the quantity of a card in the active deck with validation against deck construction rules.

#### Scenario: Increase card quantity

- **GIVEN** an active deck contains 2 copies of "Lightning Bolt" in mainboard
- **WHEN** the user asks "add 2 more Lightning Bolt to my deck" or "change Lightning Bolt to 4 copies"
- **AND** the `update_card_quantity` tool is invoked with card_name="Lightning Bolt", quantity=4, sideboard=False
- **THEN** the tool SHALL validate the new quantity against deck rules (max 4 for non-basic lands)
- **AND** call `deck_repository.update_card_quantity(deck_id, card_id, quantity=4, sideboard=False)`
- **AND** return confirmation: "Updated Lightning Bolt to 4 copies in your deck."

#### Scenario: Decrease card quantity

- **GIVEN** an active deck contains 4 copies of "Lightning Bolt"
- **WHEN** the `update_card_quantity` tool is invoked with quantity=1
- **THEN** the tool SHALL update the quantity to 1
- **AND** return confirmation: "Updated Lightning Bolt to 1 copy in your deck."

#### Scenario: Set quantity to zero (equivalent to remove)

- **GIVEN** an active deck contains 3 copies of "Lightning Bolt"
- **WHEN** the `update_card_quantity` tool is invoked with quantity=0
- **THEN** the tool SHALL remove the card from the deck
- **AND** call `deck_repository.remove_card_from_deck(deck_id, card_id, sideboard)`
- **AND** return confirmation: "Removed Lightning Bolt from your deck."

#### Scenario: Validate max 4 copy rule

- **GIVEN** an active deck contains 2 copies of "Lightning Bolt" (non-basic land)
- **WHEN** the `update_card_quantity` tool is invoked with quantity=5
- **THEN** the tool SHALL return error: "Standard format allows maximum 4 copies of Lightning Bolt. (Basic lands are unlimited.)"
- **AND** NOT update the quantity in the database

#### Scenario: Allow unlimited basic lands

- **GIVEN** an active deck contains 10 copies of "Mountain" (basic land)
- **WHEN** the `update_card_quantity` tool is invoked with quantity=15
- **THEN** the tool SHALL allow the update (basic lands are unlimited)
- **AND** return confirmation: "Updated Mountain to 15 copies in your deck."

#### Scenario: Update card not in deck (add instead)

- **GIVEN** an active deck does not contain "Lightning Bolt"
- **WHEN** the `update_card_quantity` tool is invoked with card_name="Lightning Bolt", quantity=4
- **THEN** the tool SHALL add the card to the deck with quantity 4
- **AND** call `deck_repository.add_card_to_deck(deck_id, card_id, quantity=4, sideboard=False)`
- **AND** return confirmation: "Added 4 copies of Lightning Bolt to your deck."

#### Scenario: Update with no active deck

- **GIVEN** no active deck is set in session context
- **WHEN** the `update_card_quantity` tool is invoked
- **THEN** the tool SHALL return message: "No active deck. Create or load a deck first."

### Requirement: Active Deck Session Context

The agent dependencies SHALL include `deck_context` dictionary to track the active deck across tool invocations within a session.

#### Scenario: Active deck set on creation

- **GIVEN** a user creates a new deck via `create_deck` tool (Story 4.2)
- **WHEN** the deck is created successfully
- **THEN** the tool SHALL set `ctx.deps.deck_context["active_deck_id"]` to the new deck's ID
- **AND** subsequent deck operations SHALL use this deck by default

#### Scenario: Active deck set on load

- **GIVEN** a user loads an existing deck via `load_deck` tool (Story 4.5)
- **WHEN** the deck is loaded successfully
- **THEN** the tool SHALL set `ctx.deps.deck_context["active_deck_id"]` to the loaded deck's ID
- **AND** subsequent deck operations SHALL use this deck

#### Scenario: Active deck persists across tool calls

- **GIVEN** an active deck is set to "deck-123"
- **WHEN** multiple deck tools are invoked in the same session (view, add, remove)
- **THEN** all tools SHALL access the same active deck ID from context
- **AND** the user SHALL NOT need to specify deck name in each command

#### Scenario: New session initializes with no active deck

- **GIVEN** a new Chainlit session is started
- **WHEN** AgentDependencies is initialized for the session
- **THEN** `deck_context["active_deck_id"]` SHALL be None
- **AND** deck tools SHALL prompt user to create or load a deck

#### Scenario: Active deck context accessible to all tools

- **GIVEN** the `deck_context` is stored in AgentDependencies
- **WHEN** any agent tool accesses the context via `ctx.deps.deck_context`
- **THEN** the tool SHALL read the current `active_deck_id` value
- **AND** use it for deck operations without requiring deck parameter

### Requirement: Deck Display Formatting

The system SHALL provide a `format_deck_for_display` function that formats deck contents as readable markdown grouped by card type.

#### Scenario: Format deck grouped by type

- **GIVEN** a deck contains creatures, spells, and lands
- **WHEN** `format_deck_for_display(deck, grouping="type")` is called
- **THEN** the function SHALL return markdown with sections:
  - "Creatures (X cards)"
  - "Spells (Y cards)" (Instants, Sorceries, Enchantments, Artifacts)
  - "Lands (Z cards)"
- **AND** each card SHALL be formatted as: `Quantity - Card Name (Mana Cost) [Type Line]`

#### Scenario: Sort cards within groups

- **GIVEN** a deck type group contains multiple cards
- **WHEN** formatting the group for display
- **THEN** cards SHALL be sorted by mana cost (ascending), then alphabetically by name
- **AND** maintain consistent ordering across multiple invocations

#### Scenario: Format empty card group

- **GIVEN** a deck has no creatures
- **WHEN** formatting the deck for display
- **THEN** the "Creatures" section SHALL be omitted (not shown as empty)
- **AND** only non-empty groups SHALL be displayed

#### Scenario: Format sideboard separately

- **GIVEN** a deck has cards in both mainboard and sideboard
- **WHEN** formatting the deck for display
- **THEN** mainboard cards SHALL be displayed first with all type groupings
- **AND** sideboard cards SHALL be displayed after with header "Sideboard:"
- **AND** sideboard cards SHALL also be grouped by type

#### Scenario: Include deck summary in formatting

- **GIVEN** a deck with cards
- **WHEN** formatting the deck for display
- **THEN** the output SHALL include header with:
  - Deck name
  - Format (e.g., "Standard")
  - Total mainboard count (e.g., "60 cards")
  - Total sideboard count (e.g., "15 cards")
- **AND** indicate legality: "✓ Legal for Standard" or "⚠ Needs 60+ cards for Standard"

#### Scenario: Format with UI independence

- **GIVEN** the formatting function is called
- **WHEN** generating the output
- **THEN** the function SHALL return plain markdown string
- **AND** NOT import or depend on Chainlit UI elements
- **AND** be reusable across different UI implementations

### Requirement: Deck Tool Error Handling

Deck management tools SHALL handle edge cases with user-friendly error messages and graceful degradation.

#### Scenario: Handle database connection failure

- **GIVEN** the database is unavailable or connection fails
- **WHEN** any deck tool attempts to access the repository
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework
- **AND** the agent SHALL display a user-friendly error message

#### Scenario: Handle card name ambiguity

- **GIVEN** the user says "remove Bolt"
- **WHEN** the card lookup finds multiple matches ("Lightning Bolt", "Lava Burst", etc.)
- **AND** none are exact matches
- **THEN** the tool SHALL return: "Multiple cards match 'Bolt'. Did you mean: Lightning Bolt, Lava Burst? Please specify."
- **AND** NOT perform the removal operation

#### Scenario: Handle exact match preference

- **GIVEN** the user says "remove Lightning Bolt"
- **WHEN** the card lookup finds both exact match "Lightning Bolt" and partial match "Lightning Bolt Horde"
- **THEN** the tool SHALL use the exact match
- **AND** proceed with removing "Lightning Bolt"

#### Scenario: Handle concurrent deck modifications

- **GIVEN** an active deck is being modified by the user
- **WHEN** a deck tool reads the deck state
- **THEN** the tool SHALL use the current database state (no caching)
- **AND** reflect any recent modifications made by other tools in the same session

### Requirement: Integration Tests for Deck View Tools

The system SHALL provide integration tests verifying end-to-end deck viewing and management operations through agent tools.

#### Scenario: Integration test view deck workflow

- **GIVEN** an in-memory test database with a deck containing cards
- **WHEN** the `view_deck` tool is invoked via agent
- **THEN** the tool SHALL return formatted deck list
- **AND** include all cards with correct quantities and groupings
- **AND** display summary statistics

#### Scenario: Integration test remove card workflow

- **GIVEN** a deck with "Lightning Bolt" exists in test database
- **WHEN** `remove_card_from_deck` tool is invoked with card_name="Lightning Bolt"
- **THEN** the card SHALL be removed from the deck in database
- **AND** subsequent `view_deck` SHALL NOT show the card
- **AND** confirmation message is returned

#### Scenario: Integration test update quantity workflow

- **GIVEN** a deck with 2 copies of "Lightning Bolt" exists
- **WHEN** `update_card_quantity` tool is invoked with quantity=4
- **THEN** the quantity SHALL be updated in database
- **AND** subsequent `view_deck` SHALL show 4 copies
- **AND** confirmation message is returned

#### Scenario: Integration test deck context persistence

- **GIVEN** an active deck is set in session context
- **WHEN** multiple tools are invoked (view, remove, view again)
- **THEN** all tools SHALL operate on the same active deck
- **AND** changes SHALL be reflected across invocations

#### Scenario: Integration test edge case handling

- **GIVEN** various edge cases (empty deck, invalid card, no active deck)
- **WHEN** tools are invoked with edge case inputs
- **THEN** all tools SHALL return appropriate error messages
- **AND** NOT raise unhandled exceptions
- **AND** database state SHALL remain consistent

### Requirement: List Decks Tool

The agent SHALL provide a tool that lists all saved decks with their names, formats, and basic statistics.

#### Scenario: List all decks successfully

- **GIVEN** the user has 3 saved decks in the database
- **WHEN** the tool is invoked
- **THEN** the tool SHALL return a formatted string containing:
  - Deck name
  - Deck format (e.g., "standard", "commander")
  - Total card count (mainboard)
  - Deck ID for reference
- **AND** decks SHALL be ordered by created_at descending (newest first)

#### Scenario: List decks when no decks exist

- **GIVEN** the user has no saved decks
- **WHEN** the tool is invoked
- **THEN** the tool SHALL return a message indicating no decks are saved
- **AND** suggest creating a new deck

#### Scenario: List decks filtered by format

- **GIVEN** the user has decks in "standard" and "commander" formats
- **WHEN** the tool is invoked with format_filter="standard"
- **THEN** the tool SHALL return only decks with format="standard"
- **AND** other format decks are excluded

#### Scenario: Natural language invocation

- **GIVEN** a user asks "show my decks" or "what decks do I have?"
- **WHEN** the agent processes the query
- **THEN** the agent SHALL invoke the list_decks tool
- **AND** return the formatted deck list to the user

#### Scenario: Database error during list operation

- **GIVEN** the database is unavailable
- **WHEN** the tool is invoked
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework

### Requirement: Load Deck Tool

The agent SHALL provide a `load_deck()` tool that sets the active deck and auto-syncs the format filter to match the deck's format, without modifying the games filter.

#### Scenario: Load deck preserves games filter

- **GIVEN** session games_filter is set to ["arena"]
- **AND** a deck with format="standard" exists
- **WHEN** `load_deck()` is called to load the deck
- **THEN** the format_filter is set to "standard"
- **AND** the games_filter remains ["arena"]
- **AND** the games filter is NOT modified by loading a deck

#### Scenario: Load deck with no games filter set

- **GIVEN** session games_filter is None
- **AND** a deck exists
- **WHEN** `load_deck()` is called
- **THEN** the games_filter remains None
- **AND** no automatic games filter is applied based on deck format

### Requirement: Delete Deck Tool

The agent SHALL provide a tool that deletes a deck by name or ID with an explicit confirmation requirement to prevent accidental deletion.

#### Scenario: Delete deck by name with confirmation

- **GIVEN** a deck named "Test Deck" exists in the database
- **WHEN** the tool is invoked with name="Test Deck" and confirmed=True
- **THEN** the deck SHALL be deleted from the database
- **AND** all associated deck_cards records SHALL be deleted (cascade)
- **AND** a confirmation message SHALL be returned
- **AND** if "Test Deck" was the active deck, the active deck SHALL be cleared from session

#### Scenario: Delete deck by ID with confirmation

- **GIVEN** a deck exists with id="deck-xyz-789"
- **WHEN** the tool is invoked with deck_id="deck-xyz-789" and confirmed=True
- **THEN** the deck SHALL be deleted
- **AND** a confirmation message SHALL be returned

#### Scenario: Delete deck without confirmation

- **GIVEN** a deck named "Important Deck" exists
- **WHEN** the tool is invoked with name="Important Deck" and confirmed=False
- **THEN** the deck SHALL NOT be deleted
- **AND** a warning message SHALL be returned asking for explicit confirmation
- **AND** suggest invoking again with confirmation

#### Scenario: Deck not found during delete

- **GIVEN** no deck exists with name="Nonexistent Deck"
- **WHEN** the tool is invoked with name="Nonexistent Deck"
- **THEN** the tool SHALL return an error message indicating deck not found
- **AND** no deletion operation SHALL be attempted

#### Scenario: Natural language invocation with confirmation flow

- **GIVEN** a user asks "delete Test Deck"
- **WHEN** the agent processes the query
- **THEN** the agent SHALL invoke the delete_deck tool with confirmed=False initially
- **AND** prompt the user for confirmation
- **WHEN** the user confirms deletion
- **THEN** the agent SHALL invoke the tool again with confirmed=True
- **AND** the deck SHALL be deleted

#### Scenario: Clear active deck after deletion

- **GIVEN** "Deck A" is the active deck in the session
- **WHEN** "Deck A" is deleted via the tool
- **THEN** the active deck SHALL be cleared from the session context
- **AND** subsequent deck operations SHALL indicate no active deck

#### Scenario: Database error during delete operation

- **GIVEN** the database is unavailable
- **WHEN** the tool is invoked
- **THEN** the tool SHALL raise a database exception to be handled by the agent framework

### Requirement: Tool-Level Session State Management for Write Operations

The agent SHALL implement defensive session state validation in all deck write tools to ensure clean transaction state before executing database operations.

#### Scenario: Deck write tool validates session state before operation

- **GIVEN** a deck write tool (add_card_to_deck, remove_card_from_deck, update_card_quantity, create_deck, delete_deck)
- **WHEN** the tool begins execution
- **THEN** the tool SHALL check if the repository session has an active rolled-back transaction
- **AND** if rolled back, the tool SHALL call `await session.rollback()` to clear the state
- **AND** proceed with the intended operation

#### Scenario: Tool executes after previous tool's rollback

- **GIVEN** a PydanticAI agent execution with multiple deck write tools in sequence
- **AND** the first tool triggers an IntegrityError and rolls back the session
- **WHEN** the second tool begins execution
- **THEN** the second tool SHALL detect the rolled-back session state
- **AND** clear the state with a defensive rollback
- **AND** execute its database operation successfully

#### Scenario: Deck write tool handles IntegrityError gracefully

- **GIVEN** a deck write tool that encounters an IntegrityError (e.g., duplicate card)
- **WHEN** the repository raises the IntegrityError after rolling back
- **THEN** the tool SHALL catch the IntegrityError
- **AND** return a user-friendly error message (e.g., "Card is already in your deck")
- **AND** NOT re-raise the exception to the agent runtime

#### Scenario: Deck read tool unaffected by rolled-back session

- **GIVEN** a deck read tool (view_deck, list_decks) executing after a write tool's rollback
- **WHEN** the read tool executes on the same session
- **THEN** the read tool SHALL execute successfully without session state errors
- **AND** return accurate deck data from the database

### Requirement: UI Layer Session Lifecycle Management

The system SHALL implement session lifecycle management in the UI layer to ensure clean session state at request boundaries.

#### Scenario: Session factory provides clean session state

- **GIVEN** the UI layer's `get_agent_dependencies()` context manager
- **WHEN** the context manager enters and creates a new session
- **THEN** the session SHALL be in a clean state (no active rolled-back transactions)
- **AND** if the session has a pending rolled-back transaction, it SHALL be cleared with `await session.rollback()`

#### Scenario: Session factory handles tool execution errors

- **GIVEN** the UI layer's `get_agent_dependencies()` context manager
- **AND** agent tools are executing within the context
- **WHEN** any tool raises an exception during execution
- **THEN** the context manager SHALL catch the exception
- **AND** call `await session.rollback()` to clean up the session
- **AND** re-raise the exception for the message handler to process

#### Scenario: Session factory cleans up on context exit

- **GIVEN** the UI layer's `get_agent_dependencies()` context manager
- **WHEN** the context manager exits (normally or via exception)
- **THEN** the session SHALL be closed properly
- **AND** any uncommitted transactions SHALL be rolled back automatically by SQLAlchemy
- **AND** the session SHALL be returned to the session pool

### Requirement: Improved Error Messages for Transaction Failures

The agent SHALL provide clear, actionable error messages when database transaction failures occur.

#### Scenario: IntegrityError translated to user-friendly message

- **GIVEN** a deck write tool that catches an IntegrityError
- **WHEN** the error is due to a UNIQUE constraint violation (duplicate card)
- **THEN** the tool SHALL return a message like "This card is already in your deck"
- **AND** the message SHALL NOT include SQL error codes or technical details

#### Scenario: Rolled-back session error translated to actionable advice

- **GIVEN** a tool that encounters a "transaction has been rolled back" error
- **WHEN** the error propagates to the user
- **THEN** the error message SHALL suggest trying the operation again
- **AND** include guidance like "Please try again or contact support if this issue persists"
- **AND** NOT expose SQLAlchemy internal error messages

### Requirement: Update Deck Strategy Tool
The system SHALL provide an `update_deck_strategy` tool that allows users to modify the strategy of the active deck.

#### Scenario: Update deck strategy with new text
- **GIVEN** an active deck exists with strategy="aggro"
- **WHEN** user says "update the deck strategy to control deck with counters"
- **THEN** the agent invokes `update_deck_strategy` tool with strategy="control deck with counters"
- **AND** the deck strategy is updated in the database
- **AND** the agent confirms the strategy update

#### Scenario: Clear deck strategy
- **GIVEN** an active deck exists with strategy="midrange"
- **WHEN** user says "remove the deck strategy" or "clear strategy"
- **THEN** the agent invokes `update_deck_strategy` tool with strategy=None
- **AND** the deck strategy is set to NULL
- **AND** the agent confirms strategy was cleared

#### Scenario: Update strategy with no active deck
- **GIVEN** no active deck is set in session context
- **WHEN** user tries to update strategy
- **THEN** the tool returns error message "No active deck. Create or load a deck first."

### Requirement: Strategy Context in Card Recommendations
The system SHALL use deck strategy as context when making card recommendations through search and lookup tools.

#### Scenario: Search cards with strategy context
- **GIVEN** an active deck exists with strategy="Fast aggro with burn spells"
- **WHEN** user says "find me some good creatures"
- **AND** the agent invokes `search_cards_advanced` tool
- **THEN** the tool SHALL include strategy context in the search
- **AND** the agent SHALL prioritize low-cost, aggressive creatures
- **AND** recommendations align with the aggro strategy

#### Scenario: Card lookup with strategy context
- **GIVEN** an active deck exists with strategy="Control with card advantage"
- **WHEN** user searches for removal spells
- **THEN** the agent SHALL consider the strategy when presenting options
- **AND** prioritize cards that provide card advantage (e.g., multi-target removal, card draw)

#### Scenario: No strategy context available
- **GIVEN** an active deck exists with strategy=NULL
- **WHEN** user searches for cards
- **THEN** the tool SHALL search normally without strategy bias
- **AND** recommendations are based only on format and deck composition

### Requirement: Oracle Text Search in Advanced Search

The agent SHALL provide oracle text phrase search capability in the advanced card search tool to enable precise effect-based queries.

#### Scenario: Single oracle text phrase match

- **GIVEN** the user searches for cards with oracle_text=["target creature you control"]
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return only cards whose oracle text contains the phrase "target creature you control"
- **AND** the search SHALL be case-insensitive
- **AND** the phrase can appear anywhere in the oracle text

#### Scenario: Multiple oracle text phrases with AND logic

- **GIVEN** the user searches for cards with oracle_text=["target creature you control", "gains flying"]
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return only cards whose oracle text contains BOTH phrases
- **AND** all phrases must be present in the oracle text
- **AND** the order of phrases in the card's oracle text does not matter

#### Scenario: Oracle text with other filters

- **GIVEN** the user searches for oracle_text=["target creature"], colors=["U"], types=["Instant"]
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return only blue instants whose oracle text contains "target creature"
- **AND** all filter criteria must be satisfied (AND logic across all filters)

#### Scenario: Oracle text search case-insensitivity

- **GIVEN** the user searches for oracle_text=["flying"]
- **WHEN** cards in the database have oracle text with "Flying", "flying", or "FLYING"
- **THEN** all variations SHALL match
- **AND** the search is case-insensitive

#### Scenario: Oracle text with format filter

- **GIVEN** a Standard deck is loaded (format filter = "standard")
- **AND** the user searches for oracle_text=["destroy target creature"]
- **WHEN** the search_cards_advanced tool is invoked with auto_filter=True
- **THEN** the tool SHALL return only Standard-legal cards matching the oracle text
- **AND** non-Standard cards are excluded even if they match the oracle text

#### Scenario: Oracle text search with no matches

- **GIVEN** the user searches for oracle_text=["this exact phrase does not exist"]
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return zero results
- **AND** provide helpful suggestions including "try different oracle text phrases"

#### Scenario: Bug 77c559f3 resolution

- **GIVEN** the user searches for oracle_text=["target creature you control", "gains flying"]
- **AND** the format filter is set to "standard"
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL return exactly 3 cards: Acrobatic Leap, Fleeting Flight, and Secret Identity
- **AND** SHALL NOT return all 31 cards with the flying keyword
- **AND** only cards whose oracle text contains both exact phrases are included

### Requirement: Pagination in Advanced Search

The agent SHALL provide pagination support in the advanced card search tool to enable navigation through large result sets.

#### Scenario: First page of results

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=1, page_size=20
- **THEN** the tool SHALL return cards 1-20
- **AND** the response SHALL indicate "Page 1 of 3"
- **AND** the response SHALL indicate "showing 1-20 of 52 results"
- **AND** the response SHALL suggest how to view next page

#### Scenario: Middle page of results

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=2, page_size=20
- **THEN** the tool SHALL return cards 21-40
- **AND** the response SHALL indicate "Page 2 of 3"
- **AND** the response SHALL indicate "showing 21-40 of 52 results"

#### Scenario: Last page of results

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=3, page_size=20
- **THEN** the tool SHALL return cards 41-52 (12 cards)
- **AND** the response SHALL indicate "Page 3 of 3"
- **AND** the response SHALL indicate "showing 41-52 of 52 results"
- **AND** the response SHALL NOT suggest viewing next page

#### Scenario: Page beyond last page

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=4, page_size=20
- **THEN** the tool SHALL return zero cards
- **AND** the response SHALL indicate "Page 4 of 3 (no results)"
- **AND** suggest returning to valid page range

#### Scenario: Custom page size

- **GIVEN** a search query returns 52 matching cards
- **WHEN** the search_cards_advanced tool is invoked with page=1, page_size=10
- **THEN** the tool SHALL return cards 1-10
- **AND** the response SHALL indicate "Page 1 of 6"
- **AND** the response SHALL indicate "showing 1-10 of 52 results"

#### Scenario: Page size limit enforcement

- **GIVEN** the user requests page_size=100
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL cap page_size at 50
- **AND** return maximum 50 results per page
- **AND** recalculate total pages based on capped page_size

#### Scenario: Pagination with oracle text search

- **GIVEN** the user searches for oracle_text=["draw a card"] with page=1, page_size=20
- **WHEN** the search returns 45 matching cards
- **THEN** the first page SHALL return cards 1-20 matching the oracle text
- **AND** the response SHALL indicate "Page 1 of 3"
- **AND** subsequent pages can be requested to view remaining 25 cards

#### Scenario: Natural language pagination request

- **GIVEN** the user previously searched and received page 1 of 3
- **AND** the user says "show me more" or "next page"
- **WHEN** the agent processes the request
- **THEN** the agent SHALL invoke search_cards_advanced with page=2
- **AND** repeat the previous search filters
- **AND** return the next page of results

#### Scenario: Default pagination behavior

- **GIVEN** the user performs a search without specifying page or page_size
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL default to page=1, page_size=20
- **AND** return the first 20 results
- **AND** indicate pagination metadata if more results exist

### Requirement: Backward Compatibility with max_results

The advanced search tool SHALL maintain backward compatibility with the deprecated max_results parameter while transitioning to page/page_size pagination.

#### Scenario: Legacy max_results parameter

- **GIVEN** existing code uses filters with max_results=30
- **WHEN** the search_cards_advanced tool is invoked without page or page_size
- **THEN** the tool SHALL interpret max_results as page_size=30
- **AND** default to page=1
- **AND** return up to 30 results
- **AND** function as before (no breaking change)

#### Scenario: page_size overrides max_results

- **GIVEN** filters specify both max_results=30 and page_size=20
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL use page_size=20
- **AND** ignore max_results
- **AND** max_results is deprecated in favor of page_size

#### Scenario: max_results with pagination

- **GIVEN** filters specify max_results=30 and page=2
- **WHEN** the search_cards_advanced tool is invoked
- **THEN** the tool SHALL use page_size=30 (from max_results)
- **AND** return page 2 with 30-result pages
- **AND** calculate pagination metadata accordingly

### Requirement: Analyze Mana Curve Tool

The agent SHALL provide an `analyze_mana_curve` tool that analyzes the active deck's mana curve and returns formatted analysis with visualization.

#### Scenario: Tool available in agent tools list

- **GIVEN** the PydanticAI agent is initialized
- **WHEN** querying available tools
- **THEN** `analyze_mana_curve` SHALL be present in the tools list
- **AND** tool metadata SHALL describe its purpose as "Analyze the mana curve of the active deck"

#### Scenario: Tool execution with active deck

- **GIVEN** a user has loaded deck "Mono Red Aggro" as active deck
- **WHEN** agent invokes `analyze_mana_curve` tool
- **THEN** tool SHALL retrieve active deck from repository
- **AND** calculate mana curve distribution
- **AND** analyze curve for problems and archetype
- **AND** return formatted markdown string with chart and recommendations

#### Scenario: Tool returns formatted markdown

- **GIVEN** `analyze_mana_curve` tool executes successfully
- **WHEN** the tool returns its result
- **THEN** result SHALL be markdown-formatted string
- **AND** include mana curve chart as markdown table
- **AND** include summary statistics (total cards, avg CMC, lands)
- **AND** include detected problems (if any)
- **AND** include archetype-specific recommendations

#### Scenario: Natural language query triggers tool

- **GIVEN** agent is running with conversation session
- **WHEN** user sends message "analyze my mana curve"
- **THEN** agent SHALL select and invoke `analyze_mana_curve` tool
- **AND** stream formatted analysis back to user in chat

### Requirement: Toggle Auto-Feedback Tool

The agent SHALL provide a tool that enables users to toggle automatic mana curve feedback on or off.

#### Scenario: Disable auto-feedback

- **GIVEN** auto-feedback is currently enabled (default state)
- **AND** a user requests "disable curve feedback" or "turn off auto-feedback"
- **WHEN** the toggle_auto_feedback tool is invoked with enabled=False
- **THEN** the tool SHALL set `deps.auto_feedback_enabled = False` in session state
- **AND** return a confirmation message "Automatic curve feedback disabled. You can still request analysis with 'analyze my mana curve'."

#### Scenario: Enable auto-feedback

- **GIVEN** auto-feedback is currently disabled
- **AND** a user requests "enable curve feedback" or "turn on auto-feedback"
- **WHEN** the toggle_auto_feedback tool is invoked with enabled=True
- **THEN** the tool SHALL set `deps.auto_feedback_enabled = True` in session state
- **AND** return a confirmation message "Automatic curve feedback enabled. I'll provide real-time curve guidance as you build."

#### Scenario: Preference persists across messages

- **GIVEN** a user has disabled auto-feedback
- **WHEN** the user sends subsequent messages in the same session
- **THEN** auto-feedback SHALL remain disabled
- **AND** the preference SHALL persist until explicitly changed or session ends

#### Scenario: Default state is enabled

- **GIVEN** a new session starts with no prior auto-feedback preference
- **WHEN** a user adds their first card to a deck
- **THEN** auto-feedback SHALL be enabled by default
- **AND** the system SHALL generate contextual curve feedback

### Requirement: Set Games Filter Tool

The agent SHALL provide a `set_games_filter()` tool to configure in-memory session games availability filtering.

#### Scenario: Set games filter for Arena

- **GIVEN** the agent is in a conversation session
- **WHEN** the user requests "set games filter to arena"
- **THEN** the `set_games_filter()` tool is called with games=["arena"]
- **AND** the session games_filter preference is set to ["arena"]
- **AND** subsequent card searches filter to Arena-available cards only

#### Scenario: Set games filter for multiple platforms

- **GIVEN** the agent is in a conversation session
- **WHEN** the user requests "show me cards for paper and arena"
- **THEN** the `set_games_filter()` tool is called with games=["paper", "arena"]
- **AND** the session games_filter preference is set to ["paper", "arena"]
- **AND** subsequent searches return cards available in paper OR arena

#### Scenario: Clear games filter

- **GIVEN** a games filter is currently set to ["arena"]
- **WHEN** the user requests "clear games filter"
- **THEN** the `set_games_filter()` tool is called with games=None
- **AND** the session games_filter preference is cleared
- **AND** subsequent searches return cards from all platforms

#### Scenario: Games filter persists across messages

- **GIVEN** games filter set to ["arena"] in message 1
- **WHEN** the user sends message 2 with a card search request
- **THEN** the games filter ["arena"] is still active
- **AND** the search automatically filters to Arena-available cards

#### Scenario: Invalid game value rejection

- **GIVEN** the user requests an invalid game platform
- **WHEN** `set_games_filter(games=["invalid_platform"])` is attempted
- **THEN** the tool returns an error message
- **AND** valid values are listed: "paper", "arena", "mtgo"
- **AND** the session games_filter remains unchanged

### Requirement: Games Filter in Session State

The AgentDependencies SHALL store games_filter as session state accessible to all agent tools.

#### Scenario: Games filter in dependencies

- **GIVEN** a conversation session with games filter set to ["arena"]
- **WHEN** an agent tool accesses `ctx.deps.games_filter`
- **THEN** the value ["arena"] is available
- **AND** the tool can use this filter in card queries

#### Scenario: Games filter defaults to None

- **GIVEN** a new conversation session with no games filter set
- **WHEN** an agent tool accesses `ctx.deps.games_filter`
- **THEN** the value is None
- **AND** no games filtering is applied by default

#### Scenario: Games filter serialization

- **GIVEN** a session with games_filter=["arena", "paper"]
- **WHEN** the session state is accessed
- **THEN** the games_filter is available in session preferences
- **AND** the filter persists for the lifetime of the session

### Requirement: Abbreviated Search Results for Context Optimization

The system SHALL provide abbreviated search results when result count exceeds 10 cards, reducing context window consumption while maintaining full functionality through pagination.

#### Scenario: Search with 10 or fewer results shows full details
- **GIVEN** a search query that matches 5 cards
- **WHEN** `search_cards_advanced` is called
- **THEN** all 5 cards SHALL be displayed with full details (name, mana cost, type, oracle text, rarity, set)
- **AND** each card SHALL include hover-enabled HTML formatting
- **AND** each card SHALL include visual mana symbols
- **AND** the result SHALL NOT include compact view message

#### Scenario: Search with more than 10 results shows abbreviated format
- **GIVEN** a search query that matches 50 cards (page 1, page_size=20)
- **WHEN** `search_cards_advanced` is called
- **THEN** the first 10 cards SHALL be displayed with full details
- **AND** cards 11-20 SHALL be displayed in compact format (name, mana cost, type line only)
- **AND** compact entries SHALL still include hover-enabled HTML and mana symbols
- **AND** the result SHALL include message "_Use filters or pagination to see more details._"

#### Scenario: Abbreviated format reduces token consumption
- **GIVEN** a search returning 100 cards with full details (baseline: ~20,000 tokens)
- **WHEN** abbreviated format is applied (10 full + 90 compact)
- **THEN** token consumption SHALL be approximately 4,800 tokens
- **AND** token reduction SHALL be ~70% compared to baseline
- **AND** all 100 cards SHALL still be accessible (no data loss)

#### Scenario: Compact format maintains essential information
- **GIVEN** cards displayed in compact format
- **WHEN** a compact card entry is rendered
- **THEN** each entry SHALL include: number, hover-enabled card name, mana cost (visual symbols), type line
- **AND** the format SHALL be: "{number}. {card_name_with_hover} {mana_symbols} - {type_line}\n"
- **AND** oracle text, rarity, and set SHALL be omitted
- **AND** users can see full details via pagination or filtering

#### Scenario: Pagination works correctly with abbreviated results
- **GIVEN** a search with 104 results across 6 pages (page_size=20)
- **WHEN** user requests page 2
- **THEN** page 2 SHALL show first 10 results with full details, remaining 10 compact
- **AND** page navigation message SHALL indicate "Page 2 of 6, showing 21-40"
- **AND** users can navigate to any page to see different card details

#### Scenario: Abbreviated results include clear guidance
- **GIVEN** abbreviated results are displayed
- **WHEN** the compact view section is rendered
- **THEN** the section SHALL have header "**Additional Results** (compact view):"
- **AND** the section SHALL end with "_Use filters or pagination to see more details._"
- **AND** the message SHALL guide users to narrow results for more detail

#### Scenario: Filter count threshold is configurable
- **GIVEN** the abbreviated format threshold is defined
- **WHEN** the tool initializes
- **THEN** a constant `FULL_DETAIL_COUNT = 10` SHALL exist at module level
- **AND** the constant SHALL be easy to adjust if threshold needs tuning
- **AND** the constant SHALL be documented with rationale (balance detail vs. context)

#### Scenario: Search tools preserve context for deck operations
- **GIVEN** a user with active deck performs large search (50+ cards)
- **AND** search results use abbreviated format
- **WHEN** user subsequently adds a card to deck
- **THEN** the agent SHALL still have deck creation context in history
- **AND** the agent SHALL add card to correct deck (not create new deck)
- **AND** abbreviated results SHALL have preserved deck operation context

#### Scenario: Backward compatibility with existing UI
- **GIVEN** existing Chainlit UI expects search results as formatted markdown
- **WHEN** abbreviated results are rendered
- **THEN** all HTML formatting SHALL remain valid (spans, mana symbols)
- **AND** compact entries SHALL render correctly in chat interface
- **AND** hover functionality SHALL work for both full and compact entries
- **AND** no UI layout breakage occurs

### Requirement: Card Image Hover Preservation in Abbreviated Results

The system SHALL preserve card image hover functionality in abbreviated search results, ensuring users can preview card images regardless of result format (full or compact).

#### Scenario: Compact format includes hover-enabled card names
- **GIVEN** a search returns 50 cards with abbreviated formatting
- **WHEN** cards 11-50 are displayed in compact format
- **THEN** each card name SHALL be wrapped with `wrap_card_name_with_hover(card.name, card)` function
- **AND** hovering over card name SHALL display Scryfall card image in tooltip
- **AND** hover functionality SHALL be identical to full-detail card display
- **AND** no visual distinction between full and compact card hover

#### Scenario: Card hover uses existing card image infrastructure
- **GIVEN** abbreviated results include compact card entries
- **WHEN** compact entries are formatted
- **THEN** the same `wrap_card_name_with_hover` function SHALL be used as full results
- **AND** card image URLs SHALL come from `card.image_uris` field
- **AND** CSS class `.card-hover` SHALL be applied to card name spans
- **AND** no duplicate hover implementation required

#### Scenario: Hover gracefully degrades when images unavailable
- **GIVEN** a card in compact format has no image URLs
- **WHEN** the card name is formatted
- **THEN** `wrap_card_name_with_hover` SHALL fall back to plain text
- **AND** no broken image tooltips appear
- **AND** card name remains readable without hover

#### Scenario: Abbreviated results maintain visual consistency
- **GIVEN** a search displays 10 full-detail + 40 compact cards
- **WHEN** user hovers over any card name (full or compact)
- **THEN** the hover tooltip SHALL appear with identical styling
- **AND** card image size SHALL be consistent (250px desktop, 175px tablet, 140px mobile)
- **AND** tooltip position SHALL be consistent (above/below card name)
- **AND** user experience SHALL feel unified across both formats

### Requirement: Search Result Token Usage Optimization

The system SHALL optimize token usage for large search results through abbreviated formatting, preventing conversation history bloat while maintaining user experience.

#### Scenario: Token usage tracked and logged
- **GIVEN** a search is executed with abbreviated results
- **WHEN** results are formatted and returned
- **THEN** the tool SHALL log token count estimate at DEBUG level
- **AND** the log SHALL include: result count, full detail count, compact count, estimated tokens
- **AND** metrics SHALL enable monitoring of token optimization effectiveness

#### Scenario: Token optimization preserves all functionality
- **GIVEN** abbreviated results reduce token usage by 70%
- **WHEN** users interact with search results
- **THEN** users SHALL have access to all card information (via pagination/filters)
- **AND** no features SHALL be removed or degraded
- **AND** user experience SHALL remain intuitive
- **AND** token optimization SHALL be transparent to users

#### Scenario: Large result sets provide actionable guidance
- **GIVEN** a search returns 100+ results (indicating overly broad query)
- **WHEN** abbreviated results are displayed
- **THEN** the tool SHALL suggest refining search with filters
- **AND** the message SHALL be actionable: "Use filters to narrow results"
- **AND** the guidance SHALL appear in the compact view footer
- **AND** users understand how to get more specific results


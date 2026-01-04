# Agent Core Specification Delta

## ADDED Requirements

### Requirement: Logfire Configuration Management
The system SHALL provide type-safe configuration management for Pydantic Logfire observability settings via environment variables.

#### Scenario: Load Logfire configuration from environment
- **GIVEN** a `.env` file with `LOGFIRE_ENABLED=true`, `LOGFIRE_TOKEN=lf_test_token`, and `LOGFIRE_PROJECT=my-project`
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** the configuration SHALL load `logfire_enabled=True`, `logfire_token="lf_test_token"`, and `logfire_project="my-project"`

#### Scenario: Apply Logfire default configuration values
- **GIVEN** no environment variables are set for Logfire parameters
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** `logfire_enabled` SHALL default to `False`, `logfire_token` SHALL default to `None`, and `logfire_project` SHALL default to `"artificial-planeswalker"`

#### Scenario: Validate Logfire token requirement
- **GIVEN** environment variable `LOGFIRE_ENABLED=true` without `LOGFIRE_TOKEN` set
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** a validation error SHALL be raised indicating "LOGFIRE_TOKEN required when LOGFIRE_ENABLED=true"

#### Scenario: Allow disabled Logfire without token
- **GIVEN** environment variable `LOGFIRE_ENABLED=false` without `LOGFIRE_TOKEN` set
- **WHEN** the `AgentConfig` class is instantiated
- **THEN** the configuration SHALL load successfully without requiring a token

### Requirement: Observability Initialization
The system SHALL provide a function to initialize Pydantic Logfire observability when enabled via configuration.

#### Scenario: Initialize Logfire when enabled
- **GIVEN** agent configuration with `logfire_enabled=True` and valid token
- **WHEN** `configure_observability(config)` is called
- **THEN** Logfire SHALL be configured with the provided token and project name
- **AND** PydanticAI instrumentation SHALL be enabled via `logfire.instrument_pydantic_ai()`

#### Scenario: Skip Logfire initialization when disabled
- **GIVEN** agent configuration with `logfire_enabled=False`
- **WHEN** `configure_observability(config)` is called
- **THEN** no Logfire configuration SHALL occur
- **AND** no instrumentation SHALL be enabled
- **AND** the function SHALL return without error

#### Scenario: Handle Logfire configuration errors gracefully
- **GIVEN** agent configuration with invalid Logfire token
- **WHEN** `configure_observability(config)` is called
- **THEN** the function SHALL log an error message
- **AND** the function SHALL NOT crash the application
- **AND** the application SHALL continue running without observability

#### Scenario: Initialize Logfire exactly once
- **GIVEN** the agent module is loaded
- **WHEN** `configure_observability(config)` is called during module initialization
- **THEN** Logfire SHALL be configured exactly once
- **AND** subsequent agent invocations SHALL NOT reconfigure Logfire

### Requirement: PydanticAI Agent Tracing
The system SHALL automatically trace all PydanticAI agent invocations when Logfire is enabled.

#### Scenario: Trace agent run with prompt and response
- **GIVEN** Logfire is enabled and configured
- **WHEN** an agent run is executed with prompt "Find Lightning Bolt"
- **THEN** a trace SHALL be created in Logfire with span name "agent.run"
- **AND** the trace SHALL include the prompt text
- **AND** the trace SHALL include the agent response
- **AND** the trace SHALL include token usage metadata

#### Scenario: Trace tool calls within agent run
- **GIVEN** Logfire is enabled and configured
- **WHEN** an agent run executes a tool call (e.g., `lookup_card_by_name`)
- **THEN** a child span SHALL be created for the tool call
- **AND** the span SHALL include tool name, arguments, and return value
- **AND** the span SHALL be correlated with the parent agent run trace

#### Scenario: No tracing when Logfire disabled
- **GIVEN** Logfire is disabled (`logfire_enabled=False`)
- **WHEN** an agent run is executed
- **THEN** no traces SHALL be created
- **AND** no data SHALL be sent to Logfire platform
- **AND** agent execution SHALL proceed normally with zero observability overhead

### Requirement: Database Query Tracing
The system SHALL automatically trace SQLAlchemy database queries when Logfire is enabled.

#### Scenario: Trace database queries during agent tool execution
- **GIVEN** Logfire is enabled and SQLAlchemy instrumentation is configured
- **WHEN** a card lookup tool executes a database query
- **THEN** a span SHALL be created for the SQL query
- **AND** the span SHALL include SQL statement text
- **AND** the span SHALL include query execution time
- **AND** the span SHALL be correlated with the parent tool call span

#### Scenario: No database tracing when Logfire disabled
- **GIVEN** Logfire is disabled
- **WHEN** a database query is executed
- **THEN** no query traces SHALL be created
- **AND** query execution SHALL proceed normally without instrumentation overhead

### Requirement: HTTP Request Tracing
The system SHALL automatically trace httpx HTTP requests when Logfire is enabled.

#### Scenario: Trace external HTTP requests
- **GIVEN** Logfire is enabled and httpx instrumentation is configured
- **WHEN** an HTTP request is made to Scryfall symbol API
- **THEN** a span SHALL be created for the HTTP request
- **AND** the span SHALL include request URL, method, and status code
- **AND** the span SHALL include request/response timing

#### Scenario: No HTTP tracing when Logfire disabled
- **GIVEN** Logfire is disabled
- **WHEN** an HTTP request is made
- **THEN** no HTTP traces SHALL be created
- **AND** HTTP requests SHALL proceed normally without instrumentation overhead

### Requirement: Logging Integration
The system SHALL send Python application logs to Logfire when enabled, with automatic correlation to distributed traces.

#### Scenario: Send logs to Logfire with trace correlation
- **GIVEN** Logfire is enabled and logging handler is configured
- **WHEN** application code calls `logging.info("Tool executed successfully")`
- **THEN** the log message SHALL be sent to Logfire
- **AND** the log SHALL be correlated with the current trace span (if active)
- **AND** the log SHALL include timestamp, level, and message

#### Scenario: Logs use standard Python logging when Logfire disabled
- **GIVEN** Logfire is disabled
- **WHEN** application code calls `logging.info()`
- **THEN** logs SHALL be output to console as normal
- **AND** no logs SHALL be sent to Logfire platform

### Requirement: Zero Performance Overhead When Disabled
The system SHALL ensure zero performance impact when Logfire observability is disabled.

#### Scenario: No instrumentation loaded when disabled
- **GIVEN** Logfire is disabled (`logfire_enabled=False`)
- **WHEN** the agent is initialized
- **THEN** no Logfire modules SHALL be imported
- **AND** no instrumentation hooks SHALL be registered
- **AND** no observability code SHALL execute during agent runs

#### Scenario: Equivalent performance with Logfire disabled
- **GIVEN** Logfire is disabled
- **WHEN** agent performance is measured for 100 invocations
- **THEN** the average latency SHALL be statistically equivalent to baseline (pre-Logfire)
- **AND** memory usage SHALL be statistically equivalent to baseline

### Requirement: Graceful Degradation on Logfire Errors
The system SHALL continue operating normally when Logfire platform is unavailable or returns errors.

#### Scenario: Handle Logfire API unavailability
- **GIVEN** Logfire is enabled but the platform API is unreachable
- **WHEN** an agent run is executed
- **THEN** the agent SHALL complete successfully
- **AND** an error SHALL be logged about Logfire unavailability
- **AND** traces SHALL be dropped (not sent)
- **AND** the application SHALL NOT crash or hang

#### Scenario: Handle invalid Logfire token
- **GIVEN** Logfire is enabled with invalid/expired token
- **WHEN** observability is initialized
- **THEN** an error SHALL be logged about authentication failure
- **AND** the application SHALL continue running without observability
- **AND** the agent SHALL function normally

#### Scenario: Handle Logfire rate limits
- **GIVEN** Logfire is enabled and rate limits are exceeded
- **WHEN** traces are sent to Logfire platform
- **THEN** traces SHALL be dropped or buffered according to Logfire SDK behavior
- **AND** the application SHALL NOT be blocked or slowed down
- **AND** a warning SHALL be logged about rate limiting

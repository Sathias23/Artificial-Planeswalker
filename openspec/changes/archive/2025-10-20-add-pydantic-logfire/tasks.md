# Implementation Tasks: Pydantic Logfire Integration

## 1. Dependency and Configuration Setup
- [ ] 1.1 Add `logfire>=3.0.0` to `pyproject.toml` dependencies
- [ ] 1.2 Run `uv sync` to install Logfire SDK
- [ ] 1.3 Add Logfire configuration fields to `AgentConfig` class in `src/agent/config.py`:
  - [ ] 1.3.1 `logfire_enabled: bool = Field(default=False)`
  - [ ] 1.3.2 `logfire_token: str | None = Field(default=None)`
  - [ ] 1.3.3 `logfire_project: str = Field(default="artificial-planeswalker")`
  - [ ] 1.3.4 Add `model_validator` to validate token when enabled
- [ ] 1.4 Update `.env.example` with Logfire configuration documentation:
  - [ ] 1.4.1 Add `LOGFIRE_ENABLED=false` (default disabled)
  - [ ] 1.4.2 Add `LOGFIRE_TOKEN=` (empty, user must provide)
  - [ ] 1.4.3 Add `LOGFIRE_PROJECT=artificial-planeswalker`
  - [ ] 1.4.4 Add comments explaining how to obtain token
- [ ] 1.5 Update type stubs/imports for Logfire (if needed for mypy)

## 2. Agent Core Instrumentation
- [ ] 2.1 Create `configure_observability(config: AgentConfig) -> None` function in `src/agent/core.py`
- [ ] 2.2 Implement conditional Logfire initialization:
  - [ ] 2.2.1 Check `if config.logfire_enabled`
  - [ ] 2.2.2 Call `logfire.configure(token=..., project_name=...)`
  - [ ] 2.2.3 Call `logfire.instrument_pydantic_ai()` for agent tracing
  - [ ] 2.2.4 Add error handling for configuration failures
  - [ ] 2.2.5 Log successful Logfire initialization (or silent skip if disabled)
- [ ] 2.3 Integrate `configure_observability()` into agent initialization:
  - [ ] 2.3.1 Call function before `create_agent()` in module initialization
  - [ ] 2.3.2 Ensure function is called exactly once (not per request)
  - [ ] 2.3.3 Verify agent creation still works when Logfire disabled
- [ ] 2.4 Add logging for observability status (enabled/disabled)

## 3. Database Instrumentation
- [ ] 3.1 Add SQLAlchemy instrumentation in `src/data/database.py`:
  - [ ] 3.1.1 Import `logfire` conditionally
  - [ ] 3.1.2 Call `logfire.instrument_sqlalchemy(engine=...)` after engine creation
  - [ ] 3.1.3 Ensure instrumentation only runs when Logfire enabled
  - [ ] 3.1.4 Test database queries appear in traces
- [ ] 3.2 Verify instrumentation doesn't affect database functionality
- [ ] 3.3 Test query tracing with sample card lookups

## 4. HTTP Client Instrumentation
- [ ] 4.1 Add httpx instrumentation for Scryfall symbol API:
  - [ ] 4.1.1 Import `logfire` in `src/ui/symbols.py` or globally
  - [ ] 4.1.2 Call `logfire.instrument_httpx()` (auto-instruments all httpx clients)
  - [ ] 4.1.3 Verify symbol API requests appear in traces
- [ ] 4.2 Test HTTP tracing with symbol cache initialization
- [ ] 4.3 Verify instrumentation doesn't break symbol rendering

## 5. Logging Integration
- [ ] 5.1 Configure Python logging to send to Logfire:
  - [ ] 5.1.1 Set up Logfire logging handler in `configure_observability()`
  - [ ] 5.1.2 Configure log level (INFO or DEBUG for development)
  - [ ] 5.1.3 Test logs appear in Logfire dashboard
- [ ] 5.2 Verify log-trace correlation:
  - [ ] 5.2.1 Logs from tool calls appear nested under agent traces
  - [ ] 5.2.2 Logs include span context for correlation
- [ ] 5.3 Test structured logging with metadata

## 6. Testing
- [ ] 6.1 Unit test `AgentConfig` Logfire validation:
  - [ ] 6.1.1 Test `logfire_enabled=False` loads successfully
  - [ ] 6.1.2 Test `logfire_enabled=True` without token raises error
  - [ ] 6.1.3 Test `logfire_enabled=True` with token loads successfully
  - [ ] 6.1.4 Test default values (disabled, project name)
- [ ] 6.2 Integration test agent with Logfire disabled:
  - [ ] 6.2.1 Verify agent runs successfully with `LOGFIRE_ENABLED=false`
  - [ ] 6.2.2 Verify no Logfire API calls made
  - [ ] 6.2.3 Verify zero performance impact
- [ ] 6.3 Integration test agent with Logfire enabled:
  - [ ] 6.3.1 Set up test Logfire project/token
  - [ ] 6.3.2 Run agent with `LOGFIRE_ENABLED=true`
  - [ ] 6.3.3 Verify traces appear in Logfire dashboard
  - [ ] 6.3.4 Verify tool calls are traced
  - [ ] 6.3.5 Verify database queries are traced
  - [ ] 6.3.6 Verify HTTP requests are traced
- [ ] 6.4 Test graceful fallback on Logfire API errors:
  - [ ] 6.4.1 Test with invalid token (should log error, not crash)
  - [ ] 6.4.2 Test with network unavailable (should continue without tracing)
- [ ] 6.5 Run full test suite with Logfire disabled (ensure no regressions)
- [ ] 6.6 Run manual testing with Chainlit UI and Logfire enabled

## 7. Documentation
- [ ] 7.1 Create `docs/LOGFIRE.md` with comprehensive observability documentation:
  - [ ] 7.1.1 Overview of what Logfire provides
  - [ ] 7.1.2 How to sign up for Logfire account
  - [ ] 7.1.3 How to get API token from Logfire dashboard
  - [ ] 7.1.4 How to configure `.env` to enable tracing
  - [ ] 7.1.5 How to access and navigate Logfire dashboard
  - [ ] 7.1.6 How to interpret traces (agent runs, tool calls, queries)
  - [ ] 7.1.7 Screenshots of example traces (optional)
  - [ ] 7.1.8 Performance impact (minimal when enabled, zero when disabled)
  - [ ] 7.1.9 Privacy and security considerations
  - [ ] 7.1.10 Troubleshooting common issues
- [ ] 7.2 Add observability references to `CLAUDE.md`:
  - [ ] 7.2.1 Add pointer to `docs/LOGFIRE.md` in relevant sections
  - [ ] 7.2.2 Mention Logfire as optional observability tool
- [ ] 7.3 Create `.env.example` comments with Logfire setup instructions

## 8. Code Quality and Validation
- [ ] 8.1 Run type checking: `uv run mypy src/`
- [ ] 8.2 Run linting: `uv run ruff check . --fix`
- [ ] 8.3 Run formatting: `uv run ruff format .`
- [ ] 8.4 Run all tests: `uv run pytest`
- [ ] 8.5 Run tests with coverage: `uv run pytest --cov=src --cov-report=html`
- [ ] 8.6 Review coverage for new Logfire configuration code
- [ ] 8.7 Run pre-commit hooks: `uv run pre-commit run --all-files`

## 9. OpenSpec Validation
- [ ] 9.1 Validate change proposal: `openspec validate add-pydantic-logfire --strict`
- [ ] 9.2 Review validation errors and fix spec formatting
- [ ] 9.3 Verify all requirements have scenarios
- [ ] 9.4 Verify scenario formatting uses `#### Scenario:` headers
- [ ] 9.5 Confirm proposal passes strict validation

## 10. Final Review and Deployment Readiness
- [ ] 10.1 Manual test with Logfire enabled:
  - [ ] 10.1.1 Start Chainlit: `uv run chainlit run src/ui/app.py`
  - [ ] 10.1.2 Perform card lookup and verify trace
  - [ ] 10.1.3 Create deck and verify tool calls traced
  - [ ] 10.1.4 Check database query spans
  - [ ] 10.1.5 Verify logs correlated with traces
- [ ] 10.2 Manual test with Logfire disabled:
  - [ ] 10.2.1 Set `LOGFIRE_ENABLED=false`
  - [ ] 10.2.2 Verify application works identically
  - [ ] 10.2.3 Verify no observability overhead
- [ ] 10.3 Review all code changes against proposal requirements
- [ ] 10.4 Ensure no breaking changes introduced
- [ ] 10.5 Confirm documentation is complete and accurate
- [ ] 10.6 Mark all tasks as complete in `tasks.md`
- [ ] 10.7 Ready for approval and merge

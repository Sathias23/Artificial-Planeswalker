# Design: Pydantic Logfire Integration

## Context

Artificial-Planeswalker uses PydanticAI for its agent framework and has limited visibility into agent behavior, LLM performance, and tool execution. The current logging approach provides basic console output but lacks:

- **Distributed tracing** - No correlation of agent invocations, tool calls, and database queries
- **Performance metrics** - No token usage tracking, latency measurement, or cost analysis
- **Structured observability** - Logs are unstructured and lack contextual metadata
- **Historical analysis** - No retention or querying of historical agent behavior

Pydantic Logfire is the official observability platform from the Pydantic team, designed specifically for Python applications using Pydantic and PydanticAI. It provides:

- Native PydanticAI instrumentation with one-line setup
- OpenTelemetry-based tracing (vendor-neutral, standardized)
- Automatic instrumentation for SQLAlchemy, httpx, and other libraries
- Cloud-hosted SaaS platform with free tier for development

**Stakeholders:**
- Developers: Need debugging tools to understand agent behavior
- Operations (future): Need monitoring and alerting for production deployments
- End users (indirect): Benefit from faster debugging and performance optimization

## Goals / Non-Goals

**Goals:**
- Enable comprehensive tracing of agent invocations, tool calls, and LLM requests
- Provide visibility into token usage and LLM costs per conversation
- Instrument database queries to identify slow queries
- Maintain zero performance impact when observability is disabled
- Keep integration minimal and non-invasive to existing codebase
- Support local development without requiring Logfire account (graceful fallback)

**Non-Goals:**
- Custom metrics or dashboards (use Logfire defaults)
- Self-hosted observability infrastructure (use Logfire SaaS)
- Performance optimization based on traces (future work after data collection)
- Integration with external APM tools (Logfire only for MVP)
- Production deployment configuration (focus on development use case)

## Decisions

### Decision 1: Use Pydantic Logfire vs. Alternatives

**Chosen:** Pydantic Logfire

**Alternatives considered:**
1. **OpenTelemetry directly** - Requires manual setup of exporters, collectors, and backend. More complex than Logfire's opinionated wrapper.
2. **LangSmith** - LangChain-focused, not optimized for PydanticAI. Requires converting agent to LangChain patterns.
3. **Weights & Biases** - ML experiment tracking, not designed for production LLM tracing. Overkill for conversational agent.
4. **Custom logging** - Insufficient structured data, no distributed tracing, no visualization.

**Rationale:**
- Logfire has native PydanticAI integration (`logfire.instrument_pydantic_ai()`)
- Built by Pydantic team, ensuring long-term compatibility
- OpenTelemetry foundation provides vendor neutrality if migration needed
- Free tier sufficient for development and MVP use
- Minimal code changes required (opt-in via environment variables)

### Decision 2: Opt-In Configuration

**Chosen:** Observability is opt-in via `LOGFIRE_ENABLED=true` environment variable

**Rationale:**
- Local development shouldn't require Logfire account signup
- Developers can work offline without observability platform
- Zero performance overhead when disabled (no instrumentation loaded)
- Explicit opt-in avoids accidental data transmission to external service
- Consistent with project's environment-based configuration pattern

**Implementation:**
```python
if config.logfire_enabled:
    logfire.configure(token=config.logfire_token, project_name=config.logfire_project)
    logfire.instrument_pydantic_ai()
```

### Decision 3: Instrumentation Scope

**Chosen:** Instrument PydanticAI, SQLAlchemy, and httpx via Logfire auto-instrumentation

**Scope:**
- **PydanticAI**: Agent runs, tool calls, LLM requests/responses, token usage
- **SQLAlchemy**: Database queries, execution time, connection pool metrics
- **httpx**: External HTTP requests (e.g., Scryfall symbol API)
- **Python logging**: Send application logs to Logfire for correlation with traces

**Rationale:**
- Covers all major external interactions (LLM API, database, HTTP)
- Auto-instrumentation minimizes code changes (uses OpenTelemetry integrations)
- Provides end-to-end tracing from user message → agent → tools → database → response
- Logging integration enables log-trace correlation in Logfire dashboard

### Decision 4: Configuration Schema

**Chosen:** Add Logfire settings to `AgentConfig` class

```python
class AgentConfig(BaseSettings):
    # Existing fields...

    # Logfire configuration
    logfire_enabled: bool = Field(default=False)
    logfire_token: str | None = Field(default=None)
    logfire_project: str = Field(default="artificial-planeswalker")

    @model_validator(mode="after")
    def validate_logfire_config(self) -> "AgentConfig":
        if self.logfire_enabled and not self.logfire_token:
            raise ValueError("LOGFIRE_TOKEN required when LOGFIRE_ENABLED=true")
        return self
```

**Rationale:**
- Centralized configuration in existing `AgentConfig` pattern
- Type-safe validation via Pydantic
- Environment variable mapping via `pydantic-settings`
- Clear validation error if enabled without token
- Default project name matches repository name

### Decision 5: Integration Point

**Chosen:** Initialize Logfire in `src/agent/core.py` before agent creation

**Location:** New function `configure_observability(config: AgentConfig)` called in module initialization

**Rationale:**
- Agent core is the central orchestration point
- Initialization happens once at startup (not per request)
- Instrumentation must be set up before agent creation
- Clean separation: configuration in one function, easy to disable

**Alternative considered:** Initialize in UI layer (`src/ui/app.py`)
- **Rejected:** Violates architecture principle that agent layer shouldn't depend on UI layer
- Agent layer should be UI-agnostic for future frontend replacement

## Risks / Trade-offs

### Risk 1: External SaaS Dependency
**Impact:** Application sends trace data to Pydantic's cloud platform

**Mitigation:**
- Opt-in configuration (disabled by default)
- Document data transmission in `.env.example` and `CLAUDE.md`
- Logfire is OpenTelemetry-compatible (can migrate to self-hosted OTEL later)
- Free tier sufficient for development (no cost risk)

### Risk 2: Performance Overhead
**Impact:** Instrumentation adds latency to agent invocations and tool calls

**Mitigation:**
- Logfire designed for production use (minimal overhead per documentation)
- Async instrumentation doesn't block application code
- Completely disabled when `LOGFIRE_ENABLED=false` (zero overhead)
- Measure baseline vs. instrumented performance in testing

### Risk 3: Sensitive Data in Traces
**Impact:** User prompts and card data may be sent to Logfire platform

**Mitigation:**
- Logfire supports data scrubbing/redaction (not implemented in MVP)
- Document privacy considerations in developer documentation
- Future: Implement custom span processors to filter sensitive data
- Alternative: Self-host OpenTelemetry collector (post-MVP)

### Trade-off: SaaS Platform vs. Self-Hosted
**Chosen:** SaaS platform (Logfire cloud)

**Trade-offs:**
- **Pro:** Zero infrastructure management, instant setup, free tier
- **Con:** Data leaves local machine, requires internet connectivity
- **Con:** Vendor lock-in (mitigated by OpenTelemetry foundation)

**Decision:** MVP uses SaaS, revisit for production deployment

## Migration Plan

**Phases:**

### Phase 1: Install and Configure (Breaking Ground)
1. Add `logfire>=3.0.0` to `pyproject.toml` dependencies
2. Add Logfire configuration to `AgentConfig` class
3. Document environment variables in `.env.example`
4. Update `CLAUDE.md` with Logfire setup instructions

### Phase 2: Instrument Agent Core
1. Create `configure_observability()` function in `src/agent/core.py`
2. Call function during agent initialization (conditional on `LOGFIRE_ENABLED`)
3. Add `logfire.instrument_pydantic_ai()` instrumentation
4. Test agent invocation with tracing enabled

### Phase 3: Add Database and HTTP Instrumentation
1. Add `logfire.instrument_sqlalchemy()` in `src/data/database.py`
2. Add `logfire.instrument_httpx()` in `src/ui/app.py` (or globally)
3. Verify traces appear in Logfire dashboard

### Phase 4: Logging Integration
1. Configure Python logging to send to Logfire
2. Replace critical `logging.info()` calls with structured logging
3. Verify log-trace correlation in Logfire

### Phase 5: Documentation
1. Create `docs/LOGFIRE.md` with comprehensive observability guide
2. Document how to:
   - Sign up for Logfire account
   - Get API token
   - Enable tracing locally
   - Navigate Logfire dashboard
   - Interpret traces and logs
3. Add reference to `docs/LOGFIRE.md` in `CLAUDE.md`

**Rollback:** If Logfire integration causes issues:
1. Set `LOGFIRE_ENABLED=false` in `.env`
2. Application continues working without observability
3. Remove Logfire-specific code in future commit if needed

**No database migrations required** - This is purely instrumentation code.

## Open Questions

1. **Should we instrument Chainlit UI layer?**
   - **Consideration:** Chainlit has its own request/response cycle
   - **Recommendation:** Start with agent/tools only, add UI tracing if needed

2. **What trace sampling rate should we use?**
   - **Consideration:** Free tier may have limits on trace volume
   - **Recommendation:** 100% sampling for development, revisit for production

3. **Should we add custom spans for business logic?**
   - **Consideration:** Domain logic in `src/logic/` currently has no instrumentation
   - **Recommendation:** Use auto-instrumentation for MVP, add custom spans if needed

4. **How do we handle Logfire account setup for contributors?**
   - **Consideration:** New contributors need Logfire token to use observability
   - **Recommendation:** Document as optional feature, provide screenshots for setup

5. **Should we use Logfire's evaluation framework for LLM testing?**
   - **Consideration:** Logfire includes evaluation/benchmarking tools (Q1 2025 release)
   - **Recommendation:** Out of scope for this change, evaluate in future proposal

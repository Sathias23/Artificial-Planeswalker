# Add Pydantic Logfire Observability

## Why

Artificial-Planeswalker currently lacks observability into agent behavior, tool execution, and LLM performance. Without tracing and monitoring, debugging agent decisions, optimizing LLM costs, and understanding user interactions is difficult. Pydantic Logfire provides native PydanticAI integration with minimal setup, enabling comprehensive observability through OpenTelemetry-based tracing.

## What Changes

- Add Pydantic Logfire SDK dependency (`logfire>=3.0.0`)
- Integrate Logfire instrumentation into PydanticAI agent initialization
- Add configuration for Logfire API token and project settings
- Implement automatic tracing of:
  - Agent invocations (prompts, responses, token usage)
  - Tool calls (arguments, results, execution time)
  - Database queries via SQLAlchemy instrumentation
  - HTTP requests via httpx instrumentation
- Add logging integration to send Python logs to Logfire
- Create developer documentation for using Logfire dashboard
- Configure environment variables for opt-in observability (`LOGFIRE_ENABLED`, `LOGFIRE_TOKEN`, `LOGFIRE_PROJECT`)
- Add graceful fallback when Logfire is disabled (local development without observability)

## Impact

**Affected specs:**
- `agent-core` - Add Logfire instrumentation to agent initialization
- `data-layer` - Add SQLAlchemy tracing (optional, via Logfire auto-instrumentation)

**Affected code:**
- `src/agent/core.py` - Add Logfire configuration and instrumentation
- `src/agent/config.py` - Add Logfire configuration parameters
- `src/data/database.py` - Add SQLAlchemy instrumentation (optional)
- `src/ui/app.py` - Add httpx instrumentation for Scryfall symbol API
- `pyproject.toml` - Add `logfire` dependency
- `.env.example` - Document Logfire environment variables
- `docs/LOGFIRE.md` - New documentation file for observability setup and usage

**Breaking changes:** None (opt-in feature via environment variables)

## Research Summary

**Sources:**
- Web search: "Pydantic Logfire observability tracing 2025"
- Pydantic.dev landing page: https://pydantic.dev/logfire
- Logfire documentation: https://logfire.pydantic.dev/docs/ (attempted)
- PydanticAI Logfire integration docs: https://ai.pydantic.dev/logfire/ (attempted)

**Key Findings:**
- Logfire is built on OpenTelemetry standards (vendor-neutral)
- Native PydanticAI integration via `logfire.instrument_pydantic_ai()`
- Supports multiple languages (Python-first, any language via OpenTelemetry)
- Provides traces, logs, and metrics in a unified platform
- MIT-licensed SDK, closed-source platform (SaaS)
- SOC2 and HIPAA compliant with EU data residency options
- Includes evaluation framework for LLM benchmarking
- Model Context Protocol (MCP) integration available

# Pydantic Logfire Observability

This guide explains how to use Pydantic Logfire for observability in Artificial-Planeswalker. Logfire provides distributed tracing, logging, and performance monitoring for your agent's operations.

## What is Logfire?

[Pydantic Logfire](https://logfire.pydantic.dev/) is an observability platform built by the Pydantic team specifically for Python applications. It provides:

- **Distributed tracing** - Track agent invocations, tool calls, database queries, and HTTP requests
- **Automatic instrumentation** - One-line setup for PydanticAI, SQLAlchemy, and httpx
- **Log-trace correlation** - Application logs appear inline with traces for easier debugging
- **Performance metrics** - Token usage tracking, latency measurement, and cost analysis
- **OpenTelemetry foundation** - Vendor-neutral standard (can migrate to self-hosted later)

## Getting Started

### 1. Sign Up for Logfire (Free)

1. Visit [https://logfire.pydantic.dev/](https://logfire.pydantic.dev/)
2. Click "Sign Up" and create a free account
3. The free tier includes:
   - Unlimited development use
   - 7-day retention
   - Full feature access
   - No credit card required

### 2. Get Your API Token

1. Log in to the Logfire dashboard
2. Navigate to **Settings** → **API Tokens**
3. Click **Create Token**
4. Give it a name (e.g., "Artificial-Planeswalker Dev")
5. Copy the token (starts with `lf_`)
6. **Important**: Save this token securely - it won't be shown again

### 3. Configure Your .env File

Add the following to your `.env` file:

```bash
# Enable Logfire observability
LOGFIRE_ENABLED=true

# Your Logfire API token from the dashboard
LOGFIRE_TOKEN=lf_your_token_here

# Project name (optional - defaults to "artificial-planeswalker")
LOGFIRE_PROJECT=artificial-planeswalker
```

### 4. Restart the Application

After updating `.env`, restart Chainlit:

```bash
uv run chainlit run src/ui/app.py
```

You should see a log message confirming Logfire is enabled:

```
INFO: Logfire observability enabled for project 'artificial-planeswalker'
```

## Using the Logfire Dashboard

### Accessing Traces

1. Log in to [https://logfire.pydantic.dev/](https://logfire.pydantic.dev/)
2. Select your project from the dropdown
3. Click **Traces** in the left sidebar
4. You'll see a list of all agent runs, with each trace showing:
   - **Duration**: How long the operation took
   - **Status**: Success or error
   - **Timestamp**: When it occurred

### Viewing a Trace

Click on any trace to see the full execution timeline:

```
agent.run (2.3s)
├─ lookup_card_by_name (124ms)
│  └─ SELECT FROM cards WHERE name = 'Lightning Bolt' (12ms)
├─ LLM API call (1.8s)
│  ├─ Request: anthropic/claude-sonnet-4.5
│  ├─ Tokens: 1,247 input, 342 output
│  └─ Cost: $0.012
└─ Response formatting (45ms)
```

Each span shows:
- **Name**: Operation type (agent run, tool call, query)
- **Duration**: How long it took
- **Attributes**: Input/output data, parameters, metadata
- **Logs**: Application logs that occurred during this span

### Interpreting Agent Traces

**Agent Runs**:
- Span name: `agent.run`
- Shows the full conversation turn from user input to response
- Includes prompt text, response text, and token usage
- Child spans show tool calls and LLM requests

**Tool Calls**:
- Span names: `lookup_card_by_name`, `search_cards_advanced`, etc.
- Shows tool arguments (e.g., card name, search filters)
- Shows tool return values (card data)
- Child spans show database queries triggered by the tool

**Database Queries**:
- Span name: SQL query text (e.g., `SELECT FROM cards...`)
- Shows query execution time
- Shows database connection details
- Helps identify slow queries for optimization

**HTTP Requests**:
- Span name: HTTP method + URL (e.g., `GET https://api.scryfall.com/symbology`)
- Shows request/response headers and status codes
- Shows request timing (DNS, connection, response)
- Useful for debugging external API calls

### Log-Trace Correlation

Application logs appear inline with traces. For example:

```
agent.run
├─ INFO: Processing user query: "Find Lightning Bolt"
├─ lookup_card_by_name
│  ├─ DEBUG: Searching for card: Lightning Bolt
│  └─ INFO: Found card: Lightning Bolt
└─ INFO: Agent response generated successfully
```

This makes it easy to see what the code was doing at each point in the trace.

### Searching and Filtering

Use the Logfire dashboard to:
- **Filter by status**: Show only errors or successes
- **Filter by duration**: Find slow operations
- **Search logs**: Find traces containing specific keywords
- **Group by endpoint**: See aggregate statistics per tool

## Performance Impact

### When Disabled (Default)

- **Zero overhead** - No instrumentation code is loaded
- **No network calls** - Application runs entirely offline
- **No performance impact** - Identical to pre-Logfire behavior

### When Enabled

- **Minimal overhead** - Logfire is designed for production use
- **Async instrumentation** - Tracing doesn't block application code
- **Typical overhead**: <5% latency increase (measured in milliseconds)
- **Network**: Traces sent asynchronously in the background

### Measuring Impact

To measure performance impact yourself:

```bash
# Run 10 queries with Logfire disabled
LOGFIRE_ENABLED=false uv run python -m timeit "..."

# Run 10 queries with Logfire enabled
LOGFIRE_ENABLED=true uv run python -m timeit "..."

# Compare average latency
```

## Privacy and Security Considerations

### What Data is Sent to Logfire?

When enabled, the following data is transmitted to Pydantic's Logfire platform:

- **Agent prompts and responses** - User queries and AI-generated text
- **Tool call arguments** - Card names, search filters, deck names
- **Database query text** - SQL statements (but not result data by default)
- **HTTP request URLs** - External API endpoints called
- **Application logs** - Log messages from your Python code
- **Performance metadata** - Timestamps, durations, token counts

### What is NOT Sent?

- **Database result data** - Query results stay local (only query text is traced)
- **API keys** - OpenRouter and other credentials are not transmitted
- **Local file paths** - Your filesystem structure is not shared
- **Source code** - Application code is not uploaded

### Data Retention

- **Free tier**: 7 days of retention
- **Paid tiers**: Up to 90 days (configurable)
- **Deletion**: Data is automatically deleted after retention period

### Compliance

Logfire is:
- **SOC 2 compliant** - Industry-standard security controls
- **HIPAA compliant** - For healthcare applications (paid tiers)
- **EU data residency** - Option to store data in EU servers (paid tiers)

### Best Practices

1. **Disable in production initially** - Start with `LOGFIRE_ENABLED=false` until you're comfortable
2. **Use separate projects** - Create different Logfire projects for dev/staging/prod
3. **Rotate tokens** - Regenerate API tokens periodically
4. **Review traces** - Periodically check what data is being sent
5. **Document for users** - If deploying as a service, inform users about observability

## Disabling Logfire

To disable observability at any time:

```bash
# In .env file
LOGFIRE_ENABLED=false
```

Or remove the `LOGFIRE_TOKEN` entirely. The application will continue working without observability.

## Troubleshooting

### "LOGFIRE_TOKEN required when LOGFIRE_ENABLED=true"

**Problem**: Environment variable validation failed

**Solution**: Ensure your `.env` file has both:
```bash
LOGFIRE_ENABLED=true
LOGFIRE_TOKEN=lf_your_token_here
```

### No traces appearing in dashboard

**Possible causes**:
1. **Wrong project selected** - Check the project dropdown in Logfire dashboard
2. **Invalid token** - Regenerate token and update `.env`
3. **Network blocked** - Check if your firewall allows HTTPS to `logfire.pydantic.dev`
4. **Not enabled** - Verify `LOGFIRE_ENABLED=true` in `.env`

**Debug steps**:
```bash
# Check if Logfire is initialized
uv run chainlit run src/ui/app.py
# Look for: "Logfire observability enabled for project '...'"

# If you see "Logfire observability disabled", check your .env file
```

### Application crashed after enabling Logfire

**Problem**: Logfire initialization error

**Solution**: Check the error logs for specific errors. Common issues:
- **Invalid token format** - Must start with `lf_`
- **Network timeout** - Increase timeout or check internet connection
- **Dependency conflict** - Run `uv sync` to ensure `logfire>=3.0.0` is installed

The application is designed to continue running even if Logfire fails to initialize (with a warning logged).

### Slow performance with Logfire enabled

**Check**:
1. **Network latency** - Logfire sends data asynchronously, but initial handshake requires network
2. **Trace volume** - Very high request rates may cause buffering
3. **Baseline comparison** - Measure performance with `LOGFIRE_ENABLED=false` to confirm impact

**Mitigation**:
- Disable Logfire temporarily for performance-critical operations
- Use sampling (future feature) to trace only a subset of requests

## Advanced Usage

### Custom Spans (Future)

While not implemented in the MVP, you can add custom spans for domain logic:

```python
import logfire

with logfire.span("calculate_mana_curve"):
    # Your business logic here
    mana_curve = calculate_mana_distribution(deck)
```

### Sampling (Future)

For production deployments with high traffic, configure sampling:

```python
# In configure_observability()
logfire.configure(
    token=config.logfire_token,
    service_name=config.logfire_project,
    sampling={"rate": 0.1}  # Trace 10% of requests
)
```

### Self-Hosted Alternative (Future)

Logfire is built on OpenTelemetry, allowing migration to self-hosted solutions:

1. Export traces to OpenTelemetry Collector
2. Store in Jaeger, Tempo, or other OTEL-compatible backends
3. No application code changes required (Logfire SDK is OTEL-based)

## Getting Help

- **Logfire Documentation**: [https://logfire.pydantic.dev/docs/](https://logfire.pydantic.dev/docs/)
- **Logfire Discord**: Join the Pydantic Discord for support
- **Project Issues**: Report integration issues at the Artificial-Planeswalker GitHub repository

## Summary

Pydantic Logfire provides powerful observability for understanding agent behavior, debugging tool calls, and optimizing performance. It's:

- **Easy to enable** - Three environment variables in `.env`
- **Zero overhead when disabled** - No performance impact
- **Minimal overhead when enabled** - <5% typical latency increase
- **Opt-in** - Disabled by default, explicit consent required
- **Free for development** - No cost for local use

Start by enabling it in development to see your agent's execution in detail. You can always disable it by setting `LOGFIRE_ENABLED=false`.

# Performance Analysis and Observability

**Author**: AI Analysis
**Date**: 2025-10-20
**Related Bug**: #b0e0fc30 - Streaming slowdown in long conversations

---

## Executive Summary

This document analyzes the performance degradation issue where streaming responses slow down as conversations lengthen, and provides recommendations for implementing observability best practices in Artificial-Planeswalker.

**Key Finding**: The current implementation does NOT use PydanticAI's native streaming capabilities, instead waiting for complete responses and then manually iterating character-by-character. This is the primary cause of perceived slowdown.

---

## Performance Issue Analysis: Streaming Slowdown

### Current Implementation (Inefficient)

**File**: `src/ui/app.py:239-242`

```python
# PROBLEM: Waits for complete response, then streams character-by-character
result = await run_agent_with_session(...)  # Waits for FULL response
for char in result.output:                  # Manual character iteration
    await response_message.stream_token(char)  # Async overhead per character
```

### Root Causes

#### 1. **No True LLM Streaming** (CRITICAL)
- Current: Uses `agent.run()` which waits for complete response
- Impact: User experiences full latency before any streaming begins
- Solution: Use `agent.run_stream()` with `stream_text(delta=True)`

**Why this causes perceived slowdown**:
- As conversations grow, LLM responses become more contextual and potentially longer
- Waiting for complete response before streaming = longer wait times
- Character-by-character iteration adds ~N async operations for an N-character response

#### 2. **Character-by-Character Async Overhead**
- Each character requires:
  - Async context switch (`await`)
  - WebSocket message to Chainlit frontend
  - Event loop scheduling overhead
- For a 500-character response: **500 async operations**
- Overhead compounds with response length

#### 3. **Conversation Context Processing**
- History processor (`keep_recent_messages`) runs on every message
- Although limited to 10 messages, still requires:
  - Filtering system vs. non-system messages
  - List slicing operations
  - Message serialization for API call
- Minimal impact but measurable at scale

#### 4. **Tool Step Creation Overhead**
- Before streaming, code extracts tool calls and creates Chainlit Steps
- Each Step requires:
  - Message parsing
  - UI component creation
  - Parameter formatting
- Impact grows with number of tool calls per turn

#### 5. **Database Session Per Request**
- New session created for each message
- Repositories instantiated fresh each time
- Generally fast with SQLite, but could accumulate with concurrent users

#### 6. **In-Memory Session Storage**
- Global `_session_manager` dictionary stores all sessions
- Memory footprint grows with concurrent users
- Not a direct cause of slowdown, but could affect GC pauses

### Recommended Solutions

#### Priority 1: Implement True Streaming (HIGH IMPACT)

**Replace** `src/ui/app.py:206-242` **with**:

```python
async with get_agent_dependencies(session_id) as deps:
    # Extract tool calls first (before streaming)
    # Note: This requires running once to get messages, or using run_stream_events
    # For MVP, we can accept showing tool calls AFTER streaming completes

    response_message = cl.Message(content="")

    # TRUE STREAMING from LLM
    async with _agent.run_stream(
        user_input,
        deps=deps,
        message_history=_session_manager.get_history(session_id)
    ) as result:
        # Stream text deltas (token-by-token from LLM)
        async for delta_text in result.stream_text(delta=True):
            await response_message.stream_token(delta_text)

        # After streaming completes, update session history
        all_messages = result.all_messages()
        _session_manager.update_history(session_id, all_messages)

        # Attach UI elements if any
        if deps.ui_elements:
            response_message.elements = deps.ui_elements

    await response_message.update()
```

**Expected Impact**:
- **Time to first token**: ~90% reduction (streaming starts immediately)
- **Perceived responsiveness**: Dramatically improved user experience
- **Async overhead**: Reduced from N operations to M operations (M = number of tokens, M << N)

**Trade-offs**:
- Tool Steps would need to be shown AFTER streaming completes (or use `run_stream_events`)
- Slightly more complex error handling

#### Priority 2: Add Performance Logging (MEDIUM IMPACT)

Add instrumentation to identify bottlenecks:

```python
import time
import logging

logger = logging.getLogger(__name__)

@cl.on_message
async def on_message(message: cl.Message) -> None:
    start_time = time.perf_counter()

    # ... existing code ...

    async with get_agent_dependencies(session_id) as deps:
        deps_ready_time = time.perf_counter()
        logger.info(f"Dependencies ready in {deps_ready_time - start_time:.3f}s")

        result = await run_agent_with_session(...)
        llm_time = time.perf_counter()
        logger.info(f"LLM response in {llm_time - deps_ready_time:.3f}s")

        # Tool extraction
        tool_calls = extract_tool_calls(...)
        tool_extraction_time = time.perf_counter()
        logger.info(f"Tool extraction in {tool_extraction_time - llm_time:.3f}s")

        # Streaming
        for char in result.output:
            await response_message.stream_token(char)
        streaming_time = time.perf_counter()
        logger.info(f"Streaming {len(result.output)} chars in {streaming_time - tool_extraction_time:.3f}s")

    total_time = time.perf_counter() - start_time
    logger.info(f"Total request time: {total_time:.3f}s")
```

#### Priority 3: Batch Streaming Tokens (LOW IMPACT, QUICK WIN)

If true streaming is not immediately feasible, batch characters:

```python
# Batch characters into chunks of 5-10 characters
BATCH_SIZE = 10
for i in range(0, len(result.output), BATCH_SIZE):
    chunk = result.output[i:i+BATCH_SIZE]
    await response_message.stream_token(chunk)
```

**Expected Impact**: ~80-90% reduction in async overhead

---

## Observability Best Practices for Solo Developers

### Overview

Based on 2025 industry standards, AI agent observability encompasses four pillars:
1. **Tracing**: Execution flows, reasoning paths, tool selection
2. **Logging**: Decisions, state changes, errors
3. **Metrics**: Latency, token usage, cost, success rates
4. **Evaluation**: Quality, safety, compliance

### Recommended Approach for Artificial-Planeswalker

#### Phase 1: Foundation (Current - Immediate)

**Goal**: Basic visibility with minimal overhead

**Implementation**:

1. **Structured Logging** (Already partially implemented)
   ```python
   # src/ui/app.py, src/agent/core.py
   import logging
   import json

   logger = logging.getLogger(__name__)

   # Add structured context
   logger.info("Agent invocation", extra={
       "session_id": session_id,
       "user_input_length": len(user_input),
       "message_count": len(history),
       "active_deck_id": active_deck_id,
       "format_filter": format_filter
   })
   ```

2. **Performance Metrics Logging**
   ```python
   # src/agent/core.py - augment run_agent_with_session
   import time

   async def run_agent_with_session(user_input, session_id, deps, agent=None):
       start_time = time.perf_counter()
       history = _session_manager.get_history(session_id)

       result = await agent.run(user_input, deps=deps, message_history=history)

       elapsed = time.perf_counter() - start_time
       logger.info(f"Agent run completed", extra={
           "session_id": session_id,
           "latency_seconds": elapsed,
           "message_history_size": len(history),
           "new_messages": len(result.new_messages()),
           "response_length": len(result.output)
       })

       # ... rest of function
   ```

3. **Tool Call Tracking**
   ```python
   # src/agent/tools/* - add to each tool
   @agent.tool
   async def lookup_card_by_name(ctx, name: str, auto_filter: bool = True) -> str:
       start_time = time.perf_counter()

       # ... existing logic ...

       elapsed = time.perf_counter() - start_time
       logger.debug(f"Tool: lookup_card_by_name", extra={
           "card_name": name,
           "auto_filter": auto_filter,
           "latency_seconds": elapsed,
           "found": card is not None
       })

       return result
   ```

4. **Token Usage Tracking** (OpenRouter provides this)
   ```python
   # Future enhancement - OpenRouter API responses include usage metadata
   # Store in session manager for cost tracking
   def update_history(self, session_id: str, messages: list[ModelMessage]) -> None:
       self._sessions[session_id] = messages

       # Track cumulative token usage
       # Note: Requires extracting usage from result metadata
       # if hasattr(result, 'usage'):
       #     self._token_usage[session_id] = self._token_usage.get(session_id, 0) + result.usage.total_tokens
   ```

#### Phase 2: Enhanced Observability (Future)

**Goal**: Comprehensive visibility for production use

**Recommended Tools** (Solo Developer Friendly):

1. **Pydantic Logfire** (STRONGLY RECOMMENDED ⭐)
   - **Perfect fit**: Made by the same team as PydanticAI - native integration
   - **One-line setup**: Single function call to enable instrumentation
   - **Generous free tier**: No card required, perpetual free tier for side projects
   - **Built on OpenTelemetry**: Industry-standard observability
   - **Automatic tracing**: Token counts, tool calls, latency - all tracked automatically
   - **Simple pricing**: Pay-as-you-go, no per-host fees
   - **1-month data retention** on free tier

   ```bash
   pip install logfire
   ```

   ```python
   # src/agent/core.py - add at module level
   import logfire

   # Initialize Logfire (one-time setup)
   logfire.configure()  # Uses LOGFIRE_TOKEN from environment

   # Instrument ALL PydanticAI agents automatically
   logfire.instrument_pydantic_ai()

   # Optional: Trace HTTP requests to OpenRouter
   logfire.instrument_httpx(capture_all=True)

   # That's it! All agent runs, tool calls, and LLM requests are now traced
   ```

   **What you get automatically**:
   - Full execution traces for each agent run
   - Token usage and costs per request
   - Tool call spans with parameters and results
   - Latency metrics for LLM calls
   - HTTP request/response details
   - Session-based conversation tracking

   **Environment Setup**:
   ```bash
   # .env
   LOGFIRE_TOKEN=your_token_here  # Get from https://logfire.pydantic.dev
   ```

   **Advanced: Instrument specific agents only**:
   ```python
   # Instead of global instrumentation
   agent = create_agent()
   logfire.instrument_pydantic_ai(agent)  # Just this agent
   ```

2. **Langfuse** (Alternative - Self-Hostable)
   - Open-source, self-hostable
   - Provides tracing, analytics, prompt management
   - Good if you need data sovereignty
   - More setup overhead than Logfire

   ```bash
   pip install langfuse
   ```

   ```python
   from langfuse import Langfuse

   langfuse = Langfuse()

   # Wrap agent calls
   trace = langfuse.trace(name="agent_run", session_id=session_id)
   span = trace.span(name="llm_call")

   result = await agent.run(...)

   span.end(
       output=result.output,
       metadata={"token_count": len(result.output.split())}
   )
   ```

3. **Helicone** (Alternative - Proxy-Based)
   - Lightweight proxy for LLM API calls
   - Automatic logging without code changes
   - Free tier: 10k requests/month

   ```python
   # Just change base URL
   provider = OpenAIProvider(
       base_url="https://oai.helicone.ai/v1/openrouter",  # Proxy
       api_key=config.openrouter_api_key,
       extra_headers={"Helicone-Auth": "Bearer <key>"}
   )
   ```

4. **OpenTelemetry** (Advanced - DIY)
   - Industry standard, vendor-neutral
   - More setup overhead, but maximum flexibility
   - Good for future scaling or custom needs

   ```python
   from opentelemetry import trace
   from opentelemetry.sdk.trace import TracerProvider

   tracer = trace.get_tracer(__name__)

   with tracer.start_as_current_span("agent_run"):
       result = await agent.run(...)
   ```

**Why Logfire is recommended for this project**:
- You're already using PydanticAI - Logfire is purpose-built for it
- Single line of code: `logfire.instrument_pydantic_ai()`
- Free tier is genuinely generous for solo developers
- Automatic token/cost tracking (critical for LLM apps)
- Q1 2025: Enhanced PydanticAI tracing with tool call details
- Built on OpenTelemetry, so you can switch later if needed

#### Observability Tools Comparison

| Feature | Logfire ⭐ | Langfuse | Helicone | OpenTelemetry |
|---------|-----------|----------|----------|---------------|
| **Setup Complexity** | ⚡ 2 lines | 🔧 Moderate | 🔧 Moderate | 🛠️ High |
| **PydanticAI Integration** | ✅ Native | ⚠️ Manual | ⚠️ Manual | ⚠️ Manual |
| **Free Tier** | ✅ Generous | ✅ Self-host | ✅ 10k req/mo | ✅ Free (DIY) |
| **Self-Hostable** | ❌ Enterprise | ✅ Yes | ❌ No | ✅ Yes |
| **Token Tracking** | ✅ Automatic | ⚠️ Manual | ✅ Automatic | ⚠️ Manual |
| **Tool Call Tracing** | ✅ Automatic | ⚠️ Manual | ❌ Limited | ⚠️ Manual |
| **Setup Time** | ⏱️ 5 min | ⏱️ 30-60 min | ⏱️ 15 min | ⏱️ 2+ hours |
| **Best For** | PydanticAI apps | Data sovereignty | LLM proxying | Custom needs |

**Verdict**: For this project (solo dev, PydanticAI-based, MVP phase), **Logfire is the clear winner**.

### Key Metrics to Track

Based on 2025 best practices, track these SLOs:

| Metric | Target | Priority |
|--------|--------|----------|
| **Time to First Token** | < 500ms | HIGH |
| **End-to-End Latency** | < 5s | HIGH |
| **Tool Call Success Rate** | > 95% | HIGH |
| **Token Usage (per session)** | < 100k | MEDIUM |
| **Cost per Task** | < $0.10 | MEDIUM |
| **Answer Quality** | Manual review | LOW (MVP) |
| **Cache Hit Rate** | > 50% | LOW (future) |

### Implementation Roadmap

#### Week 1: Fix Streaming (Bug #b0e0fc30)
- [ ] Implement `agent.run_stream()` with `stream_text(delta=True)`
- [ ] Test streaming performance with long conversations
- [ ] Verify tool Step display works (or accept delayed display)

#### Week 2: Basic Instrumentation
- [ ] Add structured logging to agent layer
- [ ] Implement performance timing in UI layer
- [ ] Add tool call duration tracking
- [ ] Create simple log analysis script (parse JSON logs)

#### Week 3: Pydantic Logfire Integration (Recommended)
- [ ] Sign up for Logfire (no card required): https://logfire.pydantic.dev
- [ ] Add `LOGFIRE_TOKEN` to `.env`
- [ ] Add two lines to `src/agent/core.py`: `logfire.configure()` and `logfire.instrument_pydantic_ai()`
- [ ] Test observability dashboard - view traces, token usage, tool calls
- [ ] Optional: Set up alerts for latency/cost thresholds

---

## Testing Recommendations

### Performance Benchmarking

Create a test harness to measure improvements:

```python
# tests/performance/test_streaming.py
import asyncio
import time
from legacy.agent import create_agent, run_agent_with_session

async def benchmark_streaming(conversation_length: int):
    """Benchmark streaming performance with varying conversation lengths."""
    agent = create_agent()
    session_id = f"benchmark-{conversation_length}"

    # Simulate conversation history
    for i in range(conversation_length):
        start = time.perf_counter()
        result = await run_agent_with_session(
            f"Message {i}",
            session_id=session_id,
            deps=deps,
            agent=agent
        )
        elapsed = time.perf_counter() - start
        print(f"Turn {i}: {elapsed:.3f}s, {len(result.output)} chars")

# Run benchmarks
asyncio.run(benchmark_streaming(5))   # Short conversation
asyncio.run(benchmark_streaming(20))  # Long conversation
```

### Load Testing

```python
# tests/performance/test_concurrent.py
async def test_concurrent_sessions():
    """Test performance with multiple concurrent sessions."""
    tasks = []
    for session_id in range(10):
        task = run_agent_with_session(
            "Show me Lightning Bolt",
            session_id=f"session-{session_id}",
            deps=deps,
            agent=agent
        )
        tasks.append(task)

    start = time.perf_counter()
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    print(f"10 concurrent sessions: {elapsed:.3f}s total")
    print(f"Average: {elapsed/10:.3f}s per session")
```

---

## Logging Configuration

### Recommended Setup

```python
# src/ui/app.py - at module level
import logging
import sys

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/app.log')  # Rotate with logrotate
    ]
)

# Set levels per module
logging.getLogger('legacy.agent').setLevel(logging.DEBUG)
logging.getLogger('src.data').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)  # Suppress HTTP logs
logging.getLogger('pydantic_ai').setLevel(logging.INFO)
```

### JSON Logging for Production

```python
# For easier parsing and analysis
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            **getattr(record, 'extra', {})
        }
        return json.dumps(log_data)

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.getLogger().addHandler(handler)
```

---

## Conclusion

### Immediate Actions

1. **Fix streaming implementation** using `agent.run_stream()` - will resolve bug #b0e0fc30
2. **Add basic performance logging** to identify other bottlenecks
3. **Benchmark before/after** to validate improvements

### Future Considerations

1. **Adopt Pydantic Logfire** (2 lines of code) for comprehensive observability
2. **Implement token usage tracking** via Logfire automatic instrumentation
3. **Create performance regression tests** to prevent future slowdowns
4. **Consider caching** for frequently accessed cards/decks
5. **Set up cost alerts** in Logfire when token usage exceeds thresholds

### Expected Outcomes

- **Bug #b0e0fc30**: RESOLVED - Streaming will maintain consistent speed regardless of conversation length
- **Time to First Token**: ~90% improvement (from 3-5s to <500ms)
- **User Experience**: Dramatically improved perceived responsiveness
- **Developer Experience**: Clear visibility into performance bottlenecks
- **Production Readiness**: Foundation for monitoring and optimization at scale

---

## References

### Primary Resources
- [Pydantic Logfire - Official Site](https://pydantic.dev/logfire)
- [Logfire PydanticAI Integration](https://logfire.pydantic.dev/docs/integrations/llms/pydanticai/)
- [PydanticAI Logfire Guide](https://ai.pydantic.dev/logfire/)
- [PydanticAI Streaming Documentation](https://ai.pydantic.dev/agents/)
- [Chainlit Streaming Guide](https://docs.chainlit.io/advanced-features/streaming)

### Best Practices & Standards
- [OpenTelemetry AI Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [Microsoft Azure: Agent Observability Best Practices](https://azure.microsoft.com/en-us/blog/agent-factory-top-5-agent-observability-best-practices-for-reliable-ai/)
- [Uptrace: AI Agent Observability Explained](https://uptrace.dev/blog/ai-agent-observability)

### Alternative Tools
- [Langfuse Documentation](https://langfuse.com/docs) (Self-hostable alternative)
- [Helicone Documentation](https://docs.helicone.ai/) (Proxy-based alternative)

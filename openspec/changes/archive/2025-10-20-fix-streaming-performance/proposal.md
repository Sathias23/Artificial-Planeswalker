# Fix Streaming Performance

## Why

The current character-by-character streaming implementation in Chainlit creates massive performance degradation for long agent responses. In production testing, responses over 10,000 characters take 50-100 seconds to stream, causing:
- Session timeouts and reconnections
- Welcome message re-appearing mid-conversation (symptom of timeout/reconnect)
- Poor user experience as conversation length increases

**Root Cause**: Each character requires a separate async operation (`await response_message.stream_token(char)`), resulting in 10,000+ operations for long responses. The math: 10,000 chars × ~5-10ms per operation = 50-100 seconds streaming overhead.

**Evidence**: Pydantic Logfire traces show agent execution completes in <2 seconds, but UI streaming continues for 50+ seconds. The bottleneck is purely in the streaming loop, not agent performance.

## What Changes

- **Modify streaming implementation** to use chunk-based streaming instead of character-by-character
- **Implement word-boundary chunking** to stream 10-20 words per chunk (balances performance with smooth UX)
- **Reduce streaming operations** from 10,000+ to ~200 for typical long responses (50x improvement)
- **Maintain streaming UX** - responses still stream progressively, just in larger chunks
- **Fix timeout/reconnection issue** - streaming completes before Chainlit session timeout triggers welcome message bug

## Impact

### Affected specs
- `chainlit-ui` - Modifying message streaming behavior

### Affected code
- `src/ui/app.py:241-242` - Replace character-by-character loop with chunk-based streaming

### Performance improvements
- **Streaming time**: 50-100 seconds → 2-5 seconds for long responses (20-50x faster)
- **Operations**: 10,000+ → 200 (50x reduction)
- **User experience**: Eliminates timeouts, welcome message bug disappears
- **No regressions**: Maintains progressive streaming UX, just with larger chunks

### Testing impact
- No new tests required (behavior is performance optimization, not functional change)
- Manual testing confirms streaming still works smoothly
- Validates timeout/reconnection bug is resolved

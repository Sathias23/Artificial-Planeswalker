# Migrate to Native Anthropic Provider

## Why

OpenRouter's OpenAI-compatible API has a critical incompatibility with Claude/Anthropic tool calls. When Claude returns tool calls through OpenRouter, the `function.arguments` field comes back as `None` instead of a properly formatted JSON string, causing PydanticAI validation errors:

```
Invalid response from OpenAI chat completions endpoint: 3 validation errors for ChatCompletion
choices.0.message.tool_calls.0.ChatCompletionMessageFunctionToolCall.function.arguments
  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]
```

This breaks all agent tool functionality, making the application unusable. The root cause is OpenRouter's translation layer between Anthropic's native tool call format and OpenAI's format - the translation is lossy and breaks PydanticAI's strict validation.

PydanticAI provides a native `AnthropicModel` provider that communicates directly with Anthropic's API, avoiding OpenRouter's compatibility layer entirely.

## What Changes

- **Switch from OpenRouter to Anthropic API** for Claude models
- Add support for `ANTHROPIC_API_KEY` environment variable
- Update agent initialization to use `AnthropicModel` instead of `OpenAIChatModel` with OpenRouter provider
- Install `pydantic-ai-slim[anthropic]` dependency
- Update configuration to support both OpenRouter (for non-Claude models) and Anthropic (for Claude models)
- Update documentation and examples to reflect new provider setup
- Maintain backward compatibility with OpenRouter for users who want to use non-Claude models

## Impact

**Affected specs:**
- `agent-core` - Provider integration, configuration management, model initialization

**Affected code:**
- `src/agent/config.py` - Add `ANTHROPIC_API_KEY` configuration field
- `src/agent/core.py` - Update `create_agent()` to use `AnthropicModel` when Anthropic key provided
- `pyproject.toml` - Add `anthropic` extra to pydantic-ai dependency
- `.env.example` - Document `ANTHROPIC_API_KEY` variable
- `tests/integration/agent/test_openrouter.py` - Update or create Anthropic-specific tests
- `README.md` / `CLAUDE.md` - Update setup and configuration instructions

**Benefits:**
- ✅ Fixes critical tool call validation errors
- ✅ More reliable tool execution
- ✅ Direct API communication (no translation layer)
- ✅ Access to Anthropic-specific features (prompt caching)
- ✅ Better error messages from native provider
- ✅ Maintains flexibility to use OpenRouter for other models if needed

**Migration path for users:**
1. Sign up for Anthropic API key at console.anthropic.com
2. Add `ANTHROPIC_API_KEY` to `.env` file
3. Remove or keep `OPENROUTER_API_KEY` (for non-Claude models)
4. Run application - agent automatically uses Anthropic provider when key is detected

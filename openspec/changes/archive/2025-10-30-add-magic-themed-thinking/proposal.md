# Add Magic-Themed Thinking Indicators

## Why

Chainlit's default loading spinner is unsatisfying and provides a generic user experience. Additionally, there are known issues with the built-in spinner not displaying correctly in recent Chainlit versions (>= 1.1.400). Users deserve clear, on-brand feedback when the agent is processing their requests.

## What Changes

- Replace default Chainlit loading spinner with custom Magic: The Gathering-themed "thinking" messages
- Display messages like "🧙‍♂️ Consulting the multiverse..." while agent processes requests
- Remove thinking message after agent response is ready
- Maintain clean, unobtrusive UI with themed feedback

**Implementation approach**: Simple message-based indicator (Option 2 from research) chosen for reliability and brand alignment.

## Impact

**Affected specs**:
- `chainlit-ui` - Adding new requirement for thinking indicator display

**Affected code**:
- `src/ui/app.py:on_message()` - Add thinking message creation/removal around agent call

**User experience impact**:
- More engaging, thematic loading feedback
- Clear indication that request is processing
- Eliminates reliance on broken Chainlit spinner
- Maintains conversation immersion with MTG-themed messages

**Technical impact**:
- Minimal code change (<10 lines)
- No new dependencies
- No performance impact
- Easy to modify/customize messages in future
